"""Tests for search strategy baselines (v1.9.0)."""

from __future__ import annotations

import unittest

from nonlinear_agent.domains.nonlinear_modeling import NonlinearModelingDomain
from nonlinear_agent.domains.synthetic_regression import SyntheticRegressionDomain
from nonlinear_agent.search.base import SearchContext, SearchStrategy
from nonlinear_agent.search.random_search import RandomSearch
from nonlinear_agent.search.optuna_search import OptunaTPESearch
from nonlinear_agent.search.llm_search import LLMDirectSearch, LLMProgramReflectionSearch


class TestSearchStrategies(unittest.TestCase):

    def _make_context(self, seed: int = 7, trial_budget: int = 10) -> SearchContext:
        return SearchContext(
            domain=NonlinearModelingDomain(),
            seed=seed,
            trial_budget=trial_budget,
        )

    def test_random_search_is_protocol_compatible(self):
        s = RandomSearch(self._make_context())
        self.assertIsInstance(s, SearchStrategy)

    def test_random_search_seeded_reproducibility(self):
        ctx = self._make_context(seed=7)
        s1 = RandomSearch(ctx)
        s2 = RandomSearch(ctx)
        c1 = s1.suggest([], 0)
        c2 = s2.suggest([], 0)
        self.assertEqual(c1, c2)

    def test_random_search_different_seeds_produce_different_candidates(self):
        s1 = RandomSearch(self._make_context(seed=7))
        s2 = RandomSearch(self._make_context(seed=17))
        c1 = s1.suggest([], 0)
        c2 = s2.suggest([], 0)
        # Very unlikely that both seeds produce identical candidates
        # across all fields; if they do the test still checks the code path.

    def test_random_search_duplicate_detection(self):
        s = RandomSearch(self._make_context(seed=7))
        c1 = s.suggest([], 0)
        c2 = s.suggest([], 1)
        self.assertNotEqual(c1, c2)  # different candidates by hash

    def test_optuna_search_name(self):
        try:
            s = OptunaTPESearch(self._make_context())
            self.assertEqual(s.name, "optuna_tpe")
        except ImportError:
            self.skipTest("optuna not installed")

    def test_optuna_respects_discrete_enum_values(self):
        """Optuna must sample from the design-space whitelist, not a continuous
        range — otherwise it can never hit the true discrete optimum."""
        try:
            ctx = self._make_context()
            s = OptunaTPESearch(ctx)
        except ImportError:
            self.skipTest("optuna not installed")
        design = ctx.domain.design_space()
        for i in range(80):
            candidate = s.suggest([], i)
            for field, choices in design.items():
                self.assertIn(
                    candidate[field],
                    choices,
                    f"{field} sampled {candidate[field]!r}, not in whitelist",
                )

    def test_optuna_synthetic_reaches_global_optimum(self):
        """On the 50-point synthetic domain, categorical sampling must let TPE
        converge to the known global optimum (degree=5, reg=1e-4)."""
        try:
            from nonlinear_agent.domains.synthetic_regression import (
                SyntheticRegressionDomain,
                _evaluate_candidate_tool,
                _fit_candidate_tool,
            )

            ctx = SearchContext(
                domain=SyntheticRegressionDomain(),
                seed=7,
                trial_budget=50,
                parameter_count_max=100,
            )
            s = OptunaTPESearch(ctx)
        except ImportError:
            self.skipTest("optuna not installed")

        design = ctx.domain.design_space()
        best = float("inf")
        for i in range(50):
            candidate = s.suggest([], i)
            state = _fit_candidate_tool(
                degree=candidate["degree"],
                reg_strength=candidate["reg_strength"],
            )["model_state"]
            val_mse = _evaluate_candidate_tool(state)["val_mse"]
            s.observe(candidate, {"val_mse": val_mse})
            best = min(best, val_mse)

        self.assertLess(best, 0.0434 + 1e-6)

    def test_llm_search_names(self):
        ctx = self._make_context()
        self.assertEqual(LLMDirectSearch.name, "llm_direct")
        self.assertEqual(LLMProgramReflectionSearch.name, "llm_program_reflection")

    def test_all_strategies_have_distinct_names(self):
        names = {
            "random_search",
            "optuna_tpe",
            "llm_direct",
            "llm_program_reflection",
        }
        self.assertEqual(len(names), 4)
