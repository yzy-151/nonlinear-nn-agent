import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nonlinear_agent.diagnostics import (
    collect_diagnostics,
    render_diagnostics_markdown,
    write_diagnostics_report,
)


class DiagnosticsTest(unittest.TestCase):
    def test_collect_diagnostics_aggregates_benchmark_and_run_artifacts(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            benchmark_dir = root / "benchmarks" / "run-a"
            benchmark_dir.mkdir(parents=True)
            (benchmark_dir / "results.json").write_text(json.dumps({
                "summary": {
                    "case_count": 2,
                    "target_hit_rate": 0.5,
                    "rejected_rate": 0.25,
                    "runtime_failure_rate": 0.25,
                    "average_experiments_used": 1.5,
                    "best_nmse_db": -37.4,
                },
                "results": [
                    {
                        "case_id": "case-a",
                        "target_hit": True,
                        "best_nmse_db": -37.4,
                        "best_experiment_id": "exp-a",
                        "best_parameter_count": 3626,
                        "rejected_count": 1,
                        "failed_count": 0,
                        "succeeded_count": 1,
                    },
                    {
                        "case_id": "case-b",
                        "target_hit": False,
                        "best_nmse_db": None,
                        "best_experiment_id": "",
                        "best_parameter_count": None,
                        "rejected_count": 0,
                        "failed_count": 1,
                        "succeeded_count": 0,
                    },
                ],
            }), encoding="utf-8")
            run_dir = root / "runs" / "loop-a"
            run_dir.mkdir(parents=True)
            (run_dir / "result.json").write_text(json.dumps({
                "status": "stopped",
                "rounds": 2,
                "history": [
                    {"id": "exp-a", "run_status": "succeeded", "nmse_db": -37.4, "parameter_count": 3626},
                    {"id": "bad", "run_status": "failed", "error_type": "timeout_error"},
                ],
                "reflections": [
                    {"error_type_counts": {"timeout_error": 1}}
                ],
            }), encoding="utf-8")

            diagnostics = collect_diagnostics(root)

        self.assertEqual(diagnostics["benchmark_count"], 1)
        self.assertEqual(diagnostics["run_count"], 1)
        self.assertEqual(diagnostics["totals"]["case_count"], 2)
        self.assertEqual(diagnostics["totals"]["target_hit_rate"], 0.5)
        self.assertEqual(diagnostics["status_counts"], {"succeeded": 1, "failed": 1})
        self.assertEqual(diagnostics["error_type_counts"], {"timeout_error": 1})
        self.assertEqual(diagnostics["best_candidate"]["id"], "exp-a")
        self.assertEqual(diagnostics["best_candidate"]["nmse_db"], -37.4)

    def test_render_diagnostics_markdown_contains_tables_and_interpretation(self):
        diagnostics = {
            "benchmark_count": 1,
            "run_count": 1,
            "totals": {
                "case_count": 2,
                "target_hit_rate": 0.5,
                "rejected_rate": 0.25,
                "runtime_failure_rate": 0.25,
                "average_experiments_used": 1.5,
                "best_nmse_db": -37.4,
            },
            "status_counts": {"succeeded": 1, "failed": 1},
            "error_type_counts": {"timeout_error": 1},
            "best_candidate": {"id": "exp-a", "nmse_db": -37.4, "parameter_count": 3626, "source": "runs/loop-a/result.json"},
            "benchmark_rows": [
                {"source": "benchmarks/run-a/results.json", "case_count": 2, "target_hit_rate": 0.5, "best_nmse_db": -37.4}
            ],
            "run_rows": [
                {"source": "runs/loop-a/result.json", "status": "stopped", "rounds": 2, "history_count": 2}
            ],
        }

        markdown = render_diagnostics_markdown(diagnostics)

        self.assertIn("# Agent Runtime Diagnostics Dashboard", markdown)
        self.assertIn("| target_hit_rate | `0.5` |", markdown)
        self.assertIn("| timeout_error | 1 |", markdown)
        self.assertIn("exp-a", markdown)
        self.assertIn("面试解释", markdown)

    def test_write_diagnostics_report_creates_markdown_file(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            output_path = root / "docs" / "diagnostics" / "agent-runtime-dashboard.md"

            written = write_diagnostics_report(root, output_path)

            self.assertEqual(written, output_path)
            self.assertTrue(output_path.exists())
            self.assertIn("Agent Runtime Diagnostics Dashboard", output_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
