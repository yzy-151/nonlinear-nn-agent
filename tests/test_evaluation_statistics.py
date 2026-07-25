"""Tests for evaluation statistics (v1.9.0)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from nonlinear_agent.evaluation_protocol import build_trial_record
from nonlinear_agent.evaluation_statistics import (
    bootstrap_confidence_interval,
    paired_method_delta,
    compute_method_statistics,
    write_summary_json,
    write_summary_csv,
)


def _fake_rows_for_methods_and_seeds() -> list[dict]:
    """Generate fake trial data: 2 methods x 5 seeds x 3 trials."""
    rows = []
    import numpy as np
    rng = np.random.default_rng(42)
    for method in ("llm_program_reflection", "llm_direct"):
        for seed in (7, 17, 29, 43, 61):
            for trial in range(3):
                base_nmse = -37.0 if method == "llm_program_reflection" else -36.0
                nmse = base_nmse + rng.normal(0, 0.5)
                rows.append(build_trial_record(
                    run_id=f"v19-{method}-seed{seed}-t{trial}",
                    method=method,
                    seed=seed,
                    trial_index=trial,
                    nmse_db=float(nmse),
                    target_hit=nmse <= -35.0,
                    reflection_used=(method == "llm_program_reflection"),
                    model_type="complex_lstsq",
                    parameter_count=3980,
                ))
    return rows


class TestBootstrapCI(unittest.TestCase):

    def test_bootstrap_ci_returns_three_values(self):
        samples = [1.0, 2.0, 3.0, 4.0, 5.0]
        mean_val, low, high = bootstrap_confidence_interval(samples)
        self.assertIsInstance(mean_val, float)
        self.assertIsInstance(low, float)
        self.assertIsInstance(high, float)
        self.assertLessEqual(low, mean_val)
        self.assertGreaterEqual(high, mean_val)

    def test_bootstrap_ci_with_single_value(self):
        mean_val, low, high = bootstrap_confidence_interval([42.0])
        self.assertEqual(mean_val, 42.0)

    def test_bootstrap_ci_with_empty_list(self):
        mean_val, low, high = bootstrap_confidence_interval([])
        self.assertEqual(mean_val, 0.0)

    def test_bootstrap_ci_reproducible_with_fixed_seed(self):
        samples = [float(i) for i in range(20)]
        m1, l1, h1 = bootstrap_confidence_interval(samples, seed=20260802)
        m2, l2, h2 = bootstrap_confidence_interval(samples, seed=20260802)
        self.assertEqual(m1, m2)
        self.assertEqual(l1, l2)
        self.assertEqual(h1, h2)


class TestPairedDelta(unittest.TestCase):

    def test_paired_delta_matches_same_seed_runs(self):
        rows = _fake_rows_for_methods_and_seeds()
        summary = paired_method_delta(rows, "llm_program_reflection", "llm_direct")
        self.assertEqual(summary["paired_seed_count"], 5)
        self.assertIn("nmse_delta_mean_db", summary)

    def test_paired_delta_dynamic_metric_key(self):
        rows = [
            build_trial_record("r1", "method_a", 7, 0, metric_name="val_mse", metric_value=0.1),
            build_trial_record("r2", "method_b", 7, 0, metric_name="val_mse", metric_value=0.2),
            build_trial_record("r1", "method_a", 17, 0, metric_name="val_mse", metric_value=0.3),
            build_trial_record("r2", "method_b", 17, 0, metric_name="val_mse", metric_value=0.4),
        ]
        summary = paired_method_delta(rows, "method_a", "method_b", metric="val_mse")
        self.assertEqual(summary["paired_seed_count"], 2)
        self.assertIn("val_mse_delta_mean", summary)

    def test_paired_delta_is_zero_for_identical_methods(self):
        rows = _fake_rows_for_methods_and_seeds()
        summary = paired_method_delta(rows, "llm_program_reflection", "llm_program_reflection")
        if summary["paired_seed_count"] > 0:
            self.assertAlmostEqual(summary["nmse_delta_mean_db"], 0.0, places=6)

    def test_paired_delta_no_common_seeds(self):
        rows = [
            build_trial_record("r1", "method_a", 7, 0, nmse_db=-38.0),
            build_trial_record("r2", "method_b", 17, 0, nmse_db=-37.0),
        ]
        summary = paired_method_delta(rows, "method_a", "method_b")
        self.assertEqual(summary["paired_seed_count"], 0)


class TestMethodStatistics(unittest.TestCase):

    def test_compute_method_statistics_returns_expected_keys(self):
        rows = _fake_rows_for_methods_and_seeds()
        stats = compute_method_statistics(rows, "llm_program_reflection")
        self.assertEqual(stats["method"], "llm_program_reflection")
        self.assertEqual(stats["n_seeds"], 5)
        self.assertIn("best_nmse_db_mean", stats)

    def test_compute_method_statistics_empty(self):
        stats = compute_method_statistics([], "nonexistent")
        self.assertEqual(stats["n_trials"], 0)


class TestSummaryReports(unittest.TestCase):

    def test_write_summary_json_creates_file(self):
        rows = _fake_rows_for_methods_and_seeds()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "summary.json"
            summary = write_summary_json(
                rows,
                ["llm_program_reflection", "llm_direct"],
                path,
            )
            self.assertTrue(path.exists())
            self.assertIn("per_method", summary)
            self.assertIn("paired_comparisons", summary)

    def test_write_summary_csv_creates_file(self):
        rows = _fake_rows_for_methods_and_seeds()
        with tempfile.TemporaryDirectory() as tmp:
            json_path = Path(tmp) / "summary.json"
            csv_path = Path(tmp) / "summary.csv"
            summary = write_summary_json(
                rows,
                ["llm_program_reflection", "llm_direct"],
                json_path,
            )
            write_summary_csv(summary, csv_path)
            self.assertTrue(csv_path.exists())
            content = csv_path.read_text()
            self.assertIn("llm_program_reflection", content)
            self.assertIn("llm_direct", content)
