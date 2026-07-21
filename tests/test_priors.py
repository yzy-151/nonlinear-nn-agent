"""TDD tests for historical-prior injection (reflection knowledge base)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nonlinear_agent.priors import HistoricalPrior, load_historical_priors


class TestHistoricalPriors(unittest.TestCase):
    def test_loads_priors_sorted_best_first(self):
        priors = load_historical_priors()
        self.assertGreaterEqual(len(priors), 8)
        self.assertEqual(priors[0].id, "tiny_mlp_hu96_md20")
        self.assertEqual(priors[0].known_nmse_db, -42.26)
        nmse_values = [p.known_nmse_db for p in priors]
        self.assertEqual(nmse_values, sorted(nmse_values))

    def test_priors_are_within_parameter_budget(self):
        priors = load_historical_priors()
        for p in priors:
            self.assertLessEqual(p.parameter_count, 20000)

    def test_priors_expose_usable_overrides(self):
        priors = load_historical_priors()
        best = priors[0]
        self.assertEqual(best.overrides["model_type"], "tiny_mlp")
        self.assertEqual(best.overrides["memory_depth"], 20)
        self.assertEqual(best.overrides["mp_order_count"], 3)
        self.assertEqual(best.overrides["hidden_units"], 96)

    def test_over_budget_prior_is_filtered(self):
        payload = {
            "parameter_count_max": 100,
            "candidates": [
                {
                    "id": "too-big",
                    "model_type": "complex_lstsq",
                    "memory_depth": 500,
                    "mp_order_count": 16,
                    "parameter_count": 16034,
                    "known_nmse_db": -38.56,
                },
                {
                    "id": "ok",
                    "model_type": "complex_lstsq",
                    "memory_depth": 24,
                    "mp_order_count": 4,
                    "parameter_count": 50,
                    "known_nmse_db": -35.0,
                },
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "priors.json"
            import json

            path.write_text(json.dumps(payload), encoding="utf-8")
            priors = load_historical_priors(path)

        self.assertEqual([p.id for p in priors], ["ok"])

    def test_nonlinear_domain_exposes_priors(self):
        from nonlinear_agent.domains.nonlinear_modeling import NonlinearModelingDomain

        priors = NonlinearModelingDomain().historical_priors()
        self.assertGreater(len(priors), 0)
        self.assertIsInstance(priors[0], HistoricalPrior)

    def test_synthetic_domain_has_no_priors(self):
        from nonlinear_agent.domains.synthetic_regression import SyntheticRegressionDomain

        self.assertEqual(SyntheticRegressionDomain().historical_priors(), [])


if __name__ == "__main__":
    unittest.main()
