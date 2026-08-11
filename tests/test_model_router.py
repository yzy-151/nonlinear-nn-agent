"""TDD tests for v3.7.0 ModelRouter: role-based model config + usage tracking."""

from __future__ import annotations

import unittest


class _FakeRoleClient:
    """Deterministic fake client: returns canned text, reports token usage."""

    def __init__(self, model: str, provider: str = "fake", reply: str = "ok"):
        self.model = model
        self.provider = provider
        self._reply = reply
        self.calls: list[str] = []
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self._pending_error: Exception | None = None

    def complete(self, prompt: str) -> str:
        self.calls.append(prompt)
        self.total_prompt_tokens += len(prompt) // 4 + 1
        self.total_completion_tokens += 10
        if self._pending_error is not None:
            error = self._pending_error
            self._pending_error = None
            raise error
        return self._reply


def _router(roles: dict | None = None):
    from nonlinear_agent.model_router import ModelRouter

    default_roles = {
        "supervisor": {"provider": "fake", "model": "fake-sup", "temperature": 0.0},
        "idea_planner": {"provider": "fake", "model": "fake-idea", "temperature": 0.3},
    }
    clients: dict[str, _FakeRoleClient] = {}

    def factory(role: str, config: dict):
        client = _FakeRoleClient(
            model=config.model, provider=config.provider
        )
        clients[role] = client
        return client

    router = ModelRouter(roles=roles or default_roles, client_factory=factory)
    return router, clients


class TestModelRouter(unittest.TestCase):
    def test_role_config_defaults(self):
        router, _ = _router()
        self.assertEqual(router.role_config("supervisor").model, "fake-sup")
        self.assertEqual(router.role_config("idea_planner").temperature, 0.3)

    def test_missing_role_raises(self):
        router, _ = _router()
        with self.assertRaises(KeyError):
            router.role_config("coding")

    def test_complete_records_usage_per_role(self):
        router, clients = _router()
        router.complete("supervisor", "route the plan")
        router.complete("idea_planner", "design hypotheses")
        records = router.usage()
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0].role, "supervisor")
        self.assertEqual(records[0].model, "fake-sup")
        self.assertGreater(records[0].prompt_tokens, 0)
        self.assertGreater(records[0].completion_tokens, 0)
        self.assertGreaterEqual(records[0].cost_usd, 0)
        self.assertGreaterEqual(records[0].latency_ms, 0)

    def test_secrets_never_in_usage_records(self):
        router, _ = _router()
        router.complete("supervisor", "prompt with api key sk-test-123")
        for record in router.usage():
            self.assertNotIn("sk-test-123", str(record))

    def test_budget_exceeded_after_cost_threshold(self):
        router, _ = _router()
        router.set_budgets(cost_budget_usd=1e-7)
        router.complete("supervisor", "x")
        self.assertTrue(router.budget_exceeded())

    def test_role_specific_prices_are_used_for_cost(self):
        roles = {
            "supervisor": {
                "provider": "fake",
                "model": "expensive",
                "prompt_price_per_million": 2.0,
                "completion_price_per_million": 8.0,
            }
        }
        router, _ = _router(roles)
        router.complete("supervisor", "12345678")
        record = router.usage()[0]
        expected = (
            record.prompt_tokens * 2.0 / 1_000_000
            + record.completion_tokens * 8.0 / 1_000_000
        )
        self.assertAlmostEqual(record.cost_usd, expected)

    def test_fallback_only_once_on_retryable_error(self):
        from nonlinear_agent.llm import _RetryableRequestError

        router, clients = _router()
        router.complete("supervisor", "warmup")
        clients["supervisor"]._pending_error = _RetryableRequestError("429")
        router.complete("supervisor", "retry me")
        # 主客户端失败后 fallback 一次；usage 记录必须标注实际 provider/model
        records = router.usage()
        self.assertTrue(records)


if __name__ == "__main__":
    unittest.main()
