"""TDD tests for v3.7.0 LangGraph supervisor + single-agent baseline adapter."""

from __future__ import annotations

import asyncio
import unittest


def _graph(reply: str = "{}", fail: bool = False, cost_budget: float | None = None):
    from nonlinear_agent.model_router import ModelRouter
    from nonlinear_agent.supervisor_graph import build_supervisor_graph

    class Client:
        model = "fake"
        provider = "fake"
        total_prompt_tokens = 0
        total_completion_tokens = 0

        def __init__(self):
            self.reply = reply
            self.fail = fail

        def complete(self, prompt: str) -> str:
            self.total_prompt_tokens += 10
            self.total_completion_tokens += 5
            if self.fail:
                raise RuntimeError("model timeout")
            return self.reply

    router = ModelRouter(
        roles={"supervisor": {"provider": "fake", "model": "fake", "temperature": 0.0}},
        client_factory=lambda role, config: Client(),
    )
    if cost_budget is not None:
        router.set_budgets(cost_budget_usd=cost_budget)
    return build_supervisor_graph(router), router


def _valid_plan_json() -> str:
    return (
        '{"plan_id":"plan-001","hypotheses":[{"hypothesis":"h","rationale":"r",'
        '"citation":"docs/a.md"}],"candidate_experiments":[{"model_type":"tiny_mlp",'
        '"params_estimate":100,"budget":{"parameter_count_max":20000,"epochs_max":10},'
        '"stop_condition":"nmse<=-35","rationale":"r","citation":"docs/a.md"}],'
        '"experiment_dag":{"nodes":["e1"],"edges":[]},"expected_information_gain":0.5,'
        '"risk":"low","fallback":[],"required_code_changes":[]}'
    )


class TestSupervisorGraph(unittest.TestCase):
    def test_valid_plan_completes(self):
        from nonlinear_agent.supervisor_graph import run_supervisor_graph

        graph, _ = _graph(reply=_valid_plan_json())
        result = run_supervisor_graph(graph, goal="test")
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["plan_id"], "plan-001")

    def test_invalid_json_injection_yields_error(self):
        from nonlinear_agent.supervisor_graph import run_supervisor_graph

        graph, _ = _graph(reply="this is not json")
        result = run_supervisor_graph(graph, goal="test")
        self.assertEqual(result["status"], "error")
        self.assertIn("invalid json", result["error"])

    def test_model_timeout_injection_yields_error(self):
        from nonlinear_agent.supervisor_graph import run_supervisor_graph

        graph, _ = _graph(reply="{}", fail=True)
        result = run_supervisor_graph(graph, goal="trigger timeout")
        self.assertEqual(result["status"], "error")
        self.assertIn("timeout", result["error"])

    def test_budget_injection_yields_budget_exceeded(self):
        from nonlinear_agent.supervisor_graph import run_supervisor_graph

        graph, _ = _graph(reply="{}", cost_budget=1e-9)
        result = run_supervisor_graph(graph, goal="test")
        self.assertEqual(result["status"], "budget_exceeded")

    def test_cancel_injection_yields_cancelled(self):
        from nonlinear_agent.supervisor_graph import run_supervisor_graph

        graph, _ = _graph(reply=_valid_plan_json())
        result = run_supervisor_graph(graph, goal="test", cancelled=True)
        self.assertEqual(result["status"], "cancelled")


class TestSingleAgentBaselineAdapter(unittest.TestCase):
    def test_adapter_wraps_action_loop_result(self):
        from nonlinear_agent.single_agent_adapter import SingleAgentBaselineAdapter

        class FakeLoopResult:
            status = "stopped"
            history = [{"action_id": "a1"}]

        async def runner(goal: str):
            return FakeLoopResult()

        adapter = SingleAgentBaselineAdapter(runner)
        result = asyncio.run(adapter.run("goal"))
        self.assertEqual(result.status, "stopped")
        self.assertEqual(result.terminal_state["history_len"], 1)

    def test_adapter_maps_max_actions_to_budget_exceeded(self):
        from nonlinear_agent.single_agent_adapter import SingleAgentBaselineAdapter

        class FakeLoopResult:
            status = "max_actions_reached"
            history = []

        async def runner(goal: str):
            return FakeLoopResult()

        adapter = SingleAgentBaselineAdapter(runner)
        result = asyncio.run(adapter.run("goal"))
        self.assertEqual(result.status, "budget_exceeded")


if __name__ == "__main__":
    unittest.main()
