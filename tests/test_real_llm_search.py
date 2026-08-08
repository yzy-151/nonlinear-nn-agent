"""Tests for the real-API LLM search strategy (RealLLMSearch)."""

from __future__ import annotations

import unittest
from unittest import mock

from nonlinear_agent.domains.synthetic_regression import SyntheticLargeDomain
from nonlinear_agent.llm import FakeLLMClient
from nonlinear_agent.search.base import SearchContext


def _ctx(llm_provider: str = "deepseek") -> SearchContext:
    return SearchContext(
        domain=SyntheticLargeDomain(),
        seed=7,
        trial_budget=10,
        parameter_count_max=100,
        llm_provider=llm_provider,
    )


class TestRealLLMSearch(unittest.TestCase):
    def _make(self, responses: list[str], method: str = "llm_direct"):
        from nonlinear_agent.search.llm_search import RealLLMSearch

        fake = FakeLLMClient(responses=responses)
        patcher = mock.patch(
            "nonlinear_agent.search.llm_search._get_shared_deepseek_client",
            return_value=fake,
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        return RealLLMSearch(method, _ctx())

    def test_suggest_parses_valid_candidate(self):
        s = self._make(
            ['{"overrides": {"degree": 8, "reg_strength": 0.001}, "reason": "try"}']
        )
        candidate = s.suggest([], 0)
        self.assertEqual(candidate["degree"], 8)
        self.assertEqual(candidate["reg_strength"], 0.001)

    def test_suggest_retries_on_guard_rejection(self):
        s = self._make(
            [
                '{"overrides": {"degree": 8, "bad_field": 1}, "reason": "bad"}',
                '{"overrides": {"degree": 5, "reg_strength": 1e-4}, "reason": "fixed"}',
            ]
        )
        candidate = s.suggest([], 0)
        self.assertEqual(candidate["degree"], 5)
        self.assertEqual(candidate["reg_strength"], 1e-4)
        # 第二次 prompt 必须回喂 guard 的拒绝原因
        self.assertIn("rejected by the guard", s._client.prompts[1])

    def test_suggest_exhausts_retries_and_returns_last_candidate(self):
        s = self._make(
            [
                '{"overrides": {"degree": 8, "bad_field": 1}, "reason": "bad"}',
                '{"overrides": {"degree": 7, "another_bad": 2}, "reason": "still bad"}',
                '{"overrides": {"degree": 6, "bad": 3}, "reason": "worse"}',
                '{"overrides": {"degree": 5, "bad": 4}, "reason": "last"}',
            ]
        )
        candidate = s.suggest([], 0)
        # 重试耗尽 → 返回最后一次候选，由主循环记 rejected
        self.assertEqual(candidate.get("degree"), 5)

    def test_observe_writes_candidate_and_usage(self):
        s = self._make(
            ['{"overrides": {"degree": 5, "reg_strength": 1e-4}, "reason": "x"}']
        )
        candidate = s.suggest([], 0)
        result: dict = {}
        s.observe(candidate, result)
        self.assertEqual(result["candidate"], candidate)
        self.assertIn("prompt_tokens", result)
        self.assertIn("completion_tokens", result)
        self.assertIn("planner_latency_ms", result)
        self.assertIn("estimated_cost_usd", result)

    def test_reflection_prompt_injects_historical_priors(self):
        s_ref = self._make(
            ['{"overrides": {"degree": 5, "reg_strength": 0.001}, "reason": "x"}'],
            method="llm_program_reflection",
        )
        prompt_ref = s_ref._build_prompt([], retry_error=None)
        self.assertIn("Known best candidates from project history", prompt_ref)
        self.assertIn("synthetic-prior-b", prompt_ref)

        s_dir = self._make(
            ['{"overrides": {"degree": 5, "reg_strength": 0.001}, "reason": "x"}'],
            method="llm_direct",
        )
        prompt_dir = s_dir._build_prompt([], retry_error=None)
        self.assertNotIn("Known best candidates from project history", prompt_dir)


class TestProviderRouting(unittest.TestCase):
    def test_deepseek_provider_routes_to_real_llm(self):
        from nonlinear_agent.compare_runner import build_strategy
        from nonlinear_agent.search.llm_search import RealLLMSearch

        fake = FakeLLMClient(responses=["{}"])
        with mock.patch(
            "nonlinear_agent.search.llm_search._get_shared_deepseek_client",
            return_value=fake,
        ):
            strategy = build_strategy("llm_direct", _ctx(llm_provider="deepseek"))
        self.assertIsInstance(strategy, RealLLMSearch)

    def test_simulated_provider_keeps_offline_simulator(self):
        from nonlinear_agent.compare_runner import _LLMSearch, build_strategy

        strategy = build_strategy("llm_direct", _ctx(llm_provider="simulated"))
        self.assertIsInstance(strategy, _LLMSearch)


if __name__ == "__main__":
    unittest.main()
