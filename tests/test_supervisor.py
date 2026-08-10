"""TDD tests for v3.7.0 Supervisor: budgeted orchestration with unique terminal states."""

from __future__ import annotations

import asyncio
import unittest


def _fake_router():
    from nonlinear_agent.model_router import ModelRouter

    class Client:
        model = "fake"
        provider = "fake"
        total_prompt_tokens = 0
        total_completion_tokens = 0

        def __init__(self, reply: str):
            self.reply = reply

        def complete(self, prompt: str) -> str:
            self.total_prompt_tokens += 10
            self.total_completion_tokens += 5
            if self.reply == "RAISE":
                raise RuntimeError("model timeout")
            return self.reply

    clients: dict[str, Client] = {}

    def factory(role: str, config: dict):
        clients[role] = Client("{}")
        return clients[role]

    return ModelRouter(
        roles={
            "supervisor": {"provider": "fake", "model": "fake", "temperature": 0.0},
        },
        client_factory=factory,
    ), clients


class TestSupervisor(unittest.TestCase):
    def test_budget_exhaustion_yields_unique_terminal_state(self):
        from nonlinear_agent.supervisor import ExperimentSupervisor

        router, _ = _fake_router()
        supervisor = ExperimentSupervisor(
            router=router,
            max_actions=1,
            time_budget_seconds=10,
        )
        result = asyncio.run(supervisor.run(goal="test"))
        self.assertIn(result.status, {"completed", "stopped", "budget_exceeded"})
        self.assertIsNotNone(result.terminal_state)

    def test_model_timeout_injection_yields_error_terminal_state(self):
        from nonlinear_agent.supervisor import ExperimentSupervisor

        router, clients = _fake_router()
        router.complete("supervisor", "warmup")  # 先创建并缓存 client
        clients["supervisor"].reply = "RAISE"
        supervisor = ExperimentSupervisor(router=router, max_actions=3)
        result = asyncio.run(supervisor.run(goal="trigger timeout"))
        self.assertEqual(result.status, "error")
        self.assertIn("timeout", result.error.lower())

    def test_child_agent_never_sees_api_key_or_raw_history(self):
        from nonlinear_agent.supervisor import ExperimentSupervisor

        router, _ = _fake_router()
        supervisor = ExperimentSupervisor(
            router=router,
            max_actions=1,
            secrets={"DEEPSEEK_API_KEY": "sk-super-secret"},
        )
        result = asyncio.run(supervisor.run(goal="secret isolation"))
        self.assertNotIn("sk-super-secret", str(result.terminal_state))


if __name__ == "__main__":
    unittest.main()
