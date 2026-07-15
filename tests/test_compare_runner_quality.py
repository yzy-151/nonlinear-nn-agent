"""TDD tests: compare_runner data quality and fair reflection ablation.

Covers the gaps found in the v1.7 plan audit:
  - trials must carry real config/dataset/git hashes (not "unknown")
  - llm_with_reflection must actually consume reflection facts, so the
    two LLM strategies are distinguishable
  - metric_threshold_error is an experiment outcome, not a runtime failure
  - missing optuna must fail loudly instead of silently degrading to random
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nonlinear_agent.compare_runner import (
    _LLMSearch,
    _classify_runtime_failure,
    build_strategy,
    run_compare_protocol,
    write_best_so_far_plot,
    write_reflection_ablation_plot,
)
from nonlinear_agent.domains.nonlinear_modeling import NonlinearModelingDomain
from nonlinear_agent.domains.synthetic_regression import SyntheticRegressionDomain
from nonlinear_agent.evaluation_protocol import EvaluationProtocol
from nonlinear_agent.runtime_errors import ErrorType
from nonlinear_agent.search.base import SearchContext


def _git_head() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True
    ).strip()


class TestTrialHashQuality(unittest.TestCase):
    """Trial records must carry reproducible provenance hashes."""

    def test_trials_carry_real_git_commit_and_hashes(self):
        domain = SyntheticRegressionDomain()
        protocol = EvaluationProtocol(
            methods=["random_search"], seeds=[7], trial_budget=1,
            parameter_count_max=100,
        )
        with tempfile.TemporaryDirectory() as tmp:
            rows, _, _ = asyncio.run(run_compare_protocol(
                protocol, domain, Path(tmp),
            ))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["git_commit"], _git_head())
        self.assertNotEqual(row["config_hash"], "unknown")
        self.assertEqual(len(row["config_hash"]), 64)
        self.assertNotEqual(row["dataset_hash"], "unknown")
        self.assertEqual(len(row["dataset_hash"]), 64)


class TestReflectionAblation(unittest.TestCase):
    """llm_with_reflection must differ from llm_no_reflection."""

    def _failed_history(self) -> list[dict]:
        return [
            {
                "run_id": "r0", "method": "llm_with_reflection", "seed": 7,
                "trial_index": 0, "model_type": "spline_mlp", "rejected": False,
                "runtime_failed": True, "nmse_db": 0.0, "reflection_used": True,
            },
            {
                "run_id": "r1", "method": "llm_with_reflection", "seed": 7,
                "trial_index": 1, "model_type": "complex_lstsq", "rejected": False,
                "runtime_failed": False, "nmse_db": -36.0, "reflection_used": True,
            },
        ]

    def test_with_reflection_avoids_failed_model_type(self):
        ctx = SearchContext(domain=NonlinearModelingDomain(), seed=7, trial_budget=10)
        strategy = _LLMSearch("llm_with_reflection", ctx)
        history = self._failed_history()
        for row in history:
            strategy.observe({"model_type": row["model_type"]}, row)
        candidates = [strategy.suggest(history, i) for i in range(30)]
        self.assertTrue(
            all(c["model_type"] != "spline_mlp" for c in candidates),
            "with_reflection must not re-propose a model type that failed",
        )

    def test_with_reflection_tracks_failed_types_but_without_does_not(self):
        ctx = SearchContext(domain=NonlinearModelingDomain(), seed=7, trial_budget=10)
        history = self._failed_history()
        with_ref = _LLMSearch("llm_with_reflection", ctx)
        without_ref = _LLMSearch("llm_no_reflection", ctx)
        for row in history:
            with_ref.observe({"model_type": row["model_type"]}, row)
            without_ref.observe({"model_type": row["model_type"]}, row)
        self.assertIn("spline_mlp", with_ref._failed_model_types)
        self.assertNotIn("spline_mlp", without_ref._failed_model_types)

    def test_rejected_model_type_is_remembered_and_avoided(self):
        ctx = SearchContext(domain=NonlinearModelingDomain(), seed=7, trial_budget=10)
        strategy = _LLMSearch("llm_with_reflection", ctx)
        strategy.observe(
            {"model_type": "spline_mlp"},
            {"rejected": True, "model_type": "spline_mlp"},
        )
        candidates = [strategy.suggest([], i) for i in range(30)]
        self.assertTrue(
            all(c["model_type"] != "spline_mlp" for c in candidates),
            "with_reflection must avoid a model type that was rejected",
        )


class TestRuntimeFailureClassification(unittest.TestCase):
    """metric_threshold_error is an outcome; tool/timeout errors are failures."""

    def test_metric_threshold_error_is_not_runtime_failure(self):
        self.assertFalse(
            _classify_runtime_failure(ErrorType.METRIC_THRESHOLD_ERROR.value)
        )

    def test_tool_and_timeout_errors_are_runtime_failures(self):
        self.assertTrue(_classify_runtime_failure(ErrorType.TOOL_ERROR.value))
        self.assertTrue(_classify_runtime_failure(ErrorType.TIMEOUT_ERROR.value))
        self.assertTrue(_classify_runtime_failure(None))


class TestOptunaDependency(unittest.TestCase):
    """Missing optuna must fail loudly, not silently degrade to random."""

    def test_build_strategy_raises_informative_error_when_optuna_missing(self):
        import unittest.mock

        ctx = SearchContext(domain=SyntheticRegressionDomain(), seed=7, trial_budget=3)
        with unittest.mock.patch("nonlinear_agent.search.optuna_search.optuna", None):
            with self.assertRaises(RuntimeError) as cm:
                build_strategy("optuna_tpe", ctx)
        self.assertIn("optuna", str(cm.exception).lower())

    def test_build_strategy_returns_known_strategies(self):
        ctx = SearchContext(domain=SyntheticRegressionDomain(), seed=7, trial_budget=3)
        for method in ("random_search", "llm_no_reflection", "llm_with_reflection"):
            strategy = build_strategy(method, ctx)
            self.assertEqual(strategy.name, method)


class TestPlotGeneration(unittest.TestCase):
    """compare-search must produce the two required PNG artifacts."""

    def _rows(self) -> list[dict]:
        domain = SyntheticRegressionDomain()
        protocol = EvaluationProtocol(
            methods=["random_search", "llm_no_reflection", "llm_with_reflection"],
            seeds=[7, 17],
            trial_budget=2,
            parameter_count_max=100,
        )
        with tempfile.TemporaryDirectory() as tmp:
            rows, summary, _ = asyncio.run(run_compare_protocol(
                protocol, domain, Path(tmp),
            ))
        return rows, summary

    def test_best_so_far_plot_is_created(self):
        rows, _ = self._rows()
        with tempfile.TemporaryDirectory() as tmp:
            path = write_best_so_far_plot(rows, Path(tmp))
            self.assertTrue(path.exists())
            self.assertGreater(path.stat().st_size, 0)

    def test_reflection_ablation_plot_is_created(self):
        rows, summary = self._rows()
        with tempfile.TemporaryDirectory() as tmp:
            path = write_reflection_ablation_plot(rows, summary, Path(tmp))
            self.assertTrue(path.exists())
            self.assertGreater(path.stat().st_size, 0)


class TestEffectiveTrialBudget(unittest.TestCase):
    """Rejected plans must not consume the effective training-trial budget."""

    def test_rejected_trials_do_not_consume_effective_budget(self):
        from nonlinear_agent.compare_runner import run_compare_protocol
        from nonlinear_agent.domains.synthetic_regression import SyntheticRegressionDomain

        class RejectingDomain(SyntheticRegressionDomain):
            """Reject degree==3 to force some candidates through the guard."""

            def validate_candidate(self, overrides, parameter_count_max=100):
                errors = super().validate_candidate(overrides, parameter_count_max)
                if int(overrides.get("degree", 0)) == 3:
                    errors.append("degree==3 rejected by test domain")
                return errors

        protocol = EvaluationProtocol(
            methods=["random_search"],
            seeds=[7],
            trial_budget=3,
            parameter_count_max=100,
        )
        with tempfile.TemporaryDirectory() as tmp:
            rows, _, _ = asyncio.run(run_compare_protocol(
                protocol, RejectingDomain(), Path(tmp),
            ))

        effective = [r for r in rows if not r.get("rejected")]
        rejected = [r for r in rows if r.get("rejected")]
        self.assertGreater(len(rejected), 0, "test must actually exercise rejection")
        self.assertEqual(len(effective), 3, "rejected trials must not consume budget")


if __name__ == "__main__":
    unittest.main()
