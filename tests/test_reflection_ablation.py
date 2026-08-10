import sys
import unittest
from pathlib import Path
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nonlinear_agent.domains.synthetic_regression import SyntheticLargeDomain
from nonlinear_agent.llm import FakeLLMClient
from nonlinear_agent.search.base import SearchContext


class ReflectionAblationTest(unittest.TestCase):
    def _strategy(self, method):
        from nonlinear_agent.search.llm_search import RealLLMSearch

        context = SearchContext(
            domain=SyntheticLargeDomain(),
            seed=7,
            trial_budget=3,
            parameter_count_max=100,
            llm_provider="deepseek",
        )
        fake = FakeLLMClient(responses=[
            '{"overrides":{"degree":5,"reg_strength":0.001},"reason":"try"}'
        ])
        patcher = mock.patch(
            "nonlinear_agent.search.llm_search._get_shared_deepseek_client",
            return_value=fake,
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        return RealLLMSearch(method, context)

    def test_four_context_groups_are_orthogonal(self):
        history = [{
            "candidate": {"degree": 8, "reg_strength": 0.1},
            "val_mse": 0.5,
            "rejected": False,
            "runtime_failed": False,
        }]

        direct = self._strategy("llm_direct")
        history_only = self._strategy("llm_history_only")
        facts = self._strategy("llm_history_facts")
        full = self._strategy("llm_history_facts_priors")
        facts.observe(history[0]["candidate"], history[0].copy())
        full.observe(history[0]["candidate"], history[0].copy())

        prompts = {
            "direct": direct._build_prompt(history),
            "history": history_only._build_prompt(history),
            "facts": facts._build_prompt(history),
            "full": full._build_prompt(history),
        }

        self.assertNotIn("Recent trials", prompts["direct"])
        self.assertNotIn("Reflection facts", prompts["direct"])
        self.assertNotIn("Known best candidates", prompts["direct"])

        self.assertIn("Recent trials", prompts["history"])
        self.assertNotIn("Reflection facts", prompts["history"])
        self.assertNotIn("Known best candidates", prompts["history"])

        self.assertIn("Recent trials", prompts["facts"])
        self.assertIn("Reflection facts", prompts["facts"])
        self.assertNotIn("Known best candidates", prompts["facts"])

        self.assertIn("Recent trials", prompts["full"])
        self.assertIn("Reflection facts", prompts["full"])
        self.assertIn("Known best candidates", prompts["full"])

    def test_legacy_program_reflection_alias_keeps_full_context(self):
        strategy = self._strategy("llm_program_reflection")

        self.assertTrue(strategy._use_history)
        self.assertTrue(strategy._use_facts)
        self.assertTrue(strategy._use_priors)

    def test_compare_runner_builds_all_four_ablation_strategies(self):
        from nonlinear_agent.compare_runner import build_strategy

        context = SearchContext(
            domain=SyntheticLargeDomain(),
            seed=7,
            trial_budget=3,
            parameter_count_max=100,
            llm_provider="simulated",
        )
        methods = [
            "llm_direct",
            "llm_history_only",
            "llm_history_facts",
            "llm_history_facts_priors",
        ]

        strategies = [build_strategy(method, context) for method in methods]

        self.assertEqual([strategy.name for strategy in strategies], methods)


if __name__ == "__main__":
    unittest.main()
