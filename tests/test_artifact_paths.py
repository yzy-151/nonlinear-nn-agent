"""Tests for artifact path governance (v1.7.0).

Generated trial configs must land under runs/<run_id>/configs/, never at the
configs/ top level. Hand-maintained baselines live under configs/baselines/
and configs/examples/.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from nonlinear_agent.artifact_paths import (
    normalize_experiment_output_dir,
    trial_config_path,
)


class TestTrialConfigPath(unittest.TestCase):
    def test_generated_trial_config_is_written_under_run_directory(self):
        path = trial_config_path("run-1", "trial-1")
        self.assertEqual(path, Path("runs") / "run-1" / "configs" / "trial-1.yaml")

    def test_trial_config_path_with_workspace(self):
        ws = Path("/tmp/project")
        path = trial_config_path("smoke-001", "exp-007", workspace=ws)
        self.assertEqual(path, ws / "runs" / "smoke-001" / "configs" / "exp-007.yaml")

    def test_trial_config_directory_created_under_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            path = trial_config_path("bench-1", "trial-3", workspace=ws)
            self.assertEqual(path, ws / "runs" / "bench-1" / "configs" / "trial-3.yaml")


class TestNormalizeOutputDir(unittest.TestCase):
    def test_preserves_absolute_path(self):
        self.assertEqual(
            normalize_experiment_output_dir("/abs/path/to/output"),
            "/abs/path/to/output",
        )

    def test_preserves_existing_reports_path(self):
        self.assertEqual(
            normalize_experiment_output_dir("reports/my-experiment"),
            "reports/my-experiment",
        )

    def test_routes_bare_exp_prefix_to_reports(self):
        self.assertEqual(normalize_experiment_output_dir("exp_001"), "reports/exp_001")
        self.assertEqual(
            normalize_experiment_output_dir("experiment-foo"), "reports/experiment-foo"
        )
        self.assertEqual(normalize_experiment_output_dir("output_42"), "reports/output_42")
        self.assertEqual(normalize_experiment_output_dir("result-bar"), "reports/result-bar")

    def test_preserves_non_matching_path(self):
        self.assertEqual(normalize_experiment_output_dir("my_dir"), "my_dir")
        self.assertEqual(normalize_experiment_output_dir("foo/bar"), "foo/bar")

    def test_handles_blank_and_non_string(self):
        self.assertEqual(normalize_experiment_output_dir(""), "")
        self.assertIsNone(normalize_experiment_output_dir(None))
        self.assertEqual(normalize_experiment_output_dir(42), 42)
