"""TDD tests for the runtime reliability stress test (v2.0.0)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nonlinear_agent.stress import run_stress_test


class TestStressTest(unittest.TestCase):
    """The stress harness must meet the v2.0 acceptance lines."""

    def test_stress_meets_acceptance_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = run_stress_test(
                concurrency=8,
                requests=20,
                failure_rate=0.1,
                output_dir=Path(tmp) / "out",
            )

        self.assertEqual(report["duplicate_execution_rate"], 0.0)
        self.assertEqual(report["event_loss_rate"], 0.0)
        self.assertEqual(report["terminal_consistency"], 1.0)
        self.assertGreaterEqual(report["recovery_rate"], 0.95)

    def test_stress_writes_report_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            run_stress_test(
                concurrency=4,
                requests=5,
                failure_rate=0.1,
                output_dir=out,
            )
            report_path = out / "stress.json"
            self.assertTrue(report_path.exists())
            data = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertIn("duplicate_execution_rate", data)


if __name__ == "__main__":
    unittest.main()
