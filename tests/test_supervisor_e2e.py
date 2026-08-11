from __future__ import annotations

import unittest


def _plan(plan_id: str = "plan-001") -> dict:
    return {
        "plan_id": plan_id,
        "hypotheses": [
            {"hypothesis": "memory helps", "rationale": "physics", "citation": "kb:1"}
        ],
        "candidate_experiments": [
            {
                "model_type": "adaptive_wavelet_lut",
                "params_estimate": 128,
                "budget": {"parameter_count_max": 4000, "epochs_max": 10},
                "stop_condition": "nmse<=-35",
                "rationale": "test a compact nonlinear basis",
                "citation": "kb:1",
            }
        ],
        "experiment_dag": {"nodes": ["e1"], "edges": []},
        "expected_information_gain": 0.6,
        "risk": "low",
        "fallback": [],
        "required_code_changes": ["models/candidates/adaptive_wavelet_lut/plugin.py"],
    }


class TestSupervisorE2E(unittest.TestCase):
    def test_success_path_records_role_timeline_and_unique_terminal(self):
        from nonlinear_agent.supervisor_graph import (
            MultiAgentWorkers,
            build_multi_agent_graph,
            run_multi_agent_graph,
        )

        workers = MultiAgentWorkers(
            idea_plan=lambda request: _plan(),
            coding=lambda request: {"passed": True, "manifest_path": "models/candidate.json"},
            execution=lambda request: {
                "status": "completed",
                "classification": "ok",
                "metrics": {"nmse_db": -37.5},
                "artifacts": ["reports/exp001/psd.png"],
            },
            writing=lambda request: {"report_path": "reports/task/report.pdf"},
        )

        result = run_multi_agent_graph(
            build_multi_agent_graph(workers),
            goal="design and evaluate a compact nonlinear model",
            run_id="run-001",
        )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["terminal"]["status"], "completed")
        self.assertEqual(result["terminal"]["report_path"], "reports/task/report.pdf")
        self.assertEqual(
            [event["role"] for event in result["timeline"]],
            ["idea_plan", "plan_gate", "coding", "execution", "writing", "terminal"],
        )
        self.assertTrue(all(event["run_id"] == "run-001" for event in result["timeline"]))

    def test_retryable_execution_failure_replans_with_failure_facts(self):
        from nonlinear_agent.supervisor_graph import (
            MultiAgentWorkers,
            build_multi_agent_graph,
            run_multi_agent_graph,
        )

        plan_requests: list[dict] = []
        execution_count = 0

        def idea_plan(request: dict) -> dict:
            plan_requests.append(request)
            return _plan(f"plan-{len(plan_requests):03d}")

        def execute(request: dict) -> dict:
            nonlocal execution_count
            execution_count += 1
            if execution_count == 1:
                return {
                    "status": "failed",
                    "classification": "timeout",
                    "tool_name": "run_training",
                    "error": "training timeout",
                }
            return {
                "status": "completed",
                "classification": "ok",
                "metrics": {"nmse_db": -36.0},
                "artifacts": ["reports/exp002/psd.png"],
            }

        workers = MultiAgentWorkers(
            idea_plan=idea_plan,
            coding=lambda request: {"passed": True},
            execution=execute,
            writing=lambda request: {"report_path": "reports/task/report.pdf"},
        )
        result = run_multi_agent_graph(
            build_multi_agent_graph(workers, max_replans=1),
            goal="recover from a timeout",
            run_id="run-replan",
        )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["replan_count"], 1)
        self.assertEqual(plan_requests[1]["failure_facts"]["classification"], "timeout")
        self.assertNotIn("raw_history", plan_requests[1])
        failed_event = next(
            event
            for event in result["timeline"]
            if event["role"] == "execution" and event["status"] == "failed"
        )
        self.assertEqual(failed_event["failure_facts"]["error"], "training timeout")
        replanned_event = [
            event for event in result["timeline"] if event["role"] == "idea_plan"
        ][1]
        self.assertIn("failure:timeout", replanned_event["input_refs"])
        self.assertEqual(
            [event["role"] for event in result["timeline"]].count("idea_plan"), 2
        )

    def test_model_usage_is_attributed_to_roles_and_budget_has_one_terminal(self):
        from nonlinear_agent.model_router import ModelRouter
        from nonlinear_agent.supervisor_graph import (
            MultiAgentWorkers,
            build_multi_agent_graph,
            run_multi_agent_graph,
        )

        class Client:
            provider = "fake"
            model = "fake-model"
            total_prompt_tokens = 0
            total_completion_tokens = 0

            def complete(self, prompt: str) -> str:
                self.total_prompt_tokens += 10
                self.total_completion_tokens += 5
                return "ok"

        roles = {
            name: {"provider": "fake", "model": f"{name}-model", "temperature": 0.0}
            for name in ("idea_plan", "coding", "writing")
        }
        router = ModelRouter(roles, client_factory=lambda role, config: Client())
        router.set_budgets(cost_budget_usd=1e-9)
        coding_calls = 0

        def idea_plan(request: dict) -> dict:
            router.complete("idea_plan", request["goal"])
            return _plan()

        def coding(request: dict) -> dict:
            nonlocal coding_calls
            coding_calls += 1
            return {"passed": True}

        workers = MultiAgentWorkers(
            idea_plan=idea_plan,
            coding=coding,
            execution=lambda request: {"status": "completed", "classification": "ok"},
            writing=lambda request: {"report_path": "never.pdf"},
        )
        result = run_multi_agent_graph(
            build_multi_agent_graph(workers, model_router=router),
            goal="budgeted run",
            run_id="run-budget",
        )

        self.assertEqual(result["status"], "budget_exceeded")
        self.assertEqual(coding_calls, 0)
        self.assertEqual(
            [event["role"] for event in result["timeline"]],
            ["idea_plan", "terminal"],
        )
        self.assertEqual(result["timeline"][0]["model_usage"][0]["role"], "idea_plan")
        self.assertEqual(
            len([event for event in result["timeline"] if event["role"] == "terminal"]),
            1,
        )

    def test_cooperative_cancel_stops_before_the_next_worker(self):
        from nonlinear_agent.supervisor_graph import (
            MultiAgentWorkers,
            build_multi_agent_graph,
            run_multi_agent_graph,
        )

        cancelled = False
        coding_calls = 0

        def idea_plan(request: dict) -> dict:
            nonlocal cancelled
            cancelled = True
            return _plan()

        def coding(request: dict) -> dict:
            nonlocal coding_calls
            coding_calls += 1
            return {"passed": True}

        graph = build_multi_agent_graph(
            MultiAgentWorkers(
                idea_plan=idea_plan,
                coding=coding,
                execution=lambda request: {"status": "completed"},
                writing=lambda request: {"pdf_path": "never.pdf"},
            ),
            cancel_check=lambda: cancelled,
        )
        result = run_multi_agent_graph(
            graph, goal="cancel after planning", run_id="run-cancel"
        )

        self.assertEqual(result["status"], "cancelled")
        self.assertEqual(coding_calls, 0)
        self.assertEqual(
            [event["role"] for event in result["timeline"]],
            ["idea_plan", "plan_gate", "terminal"],
        )


if __name__ == "__main__":
    unittest.main()
