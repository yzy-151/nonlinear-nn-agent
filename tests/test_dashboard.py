import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nonlinear_agent.dashboard import render_dashboard_html, write_dashboard_html


class DashboardTest(unittest.TestCase):
    def test_render_dashboard_html_includes_core_metrics_and_tables(self):
        diagnostics = {
            "benchmark_count": 1,
            "run_count": 2,
            "totals": {
                "case_count": 3,
                "target_hit_rate": 0.33,
                "rejected_rate": 0.2,
                "runtime_failure_rate": 0.1,
                "average_experiments_used": 2.0,
                "best_nmse_db": -37.4,
            },
            "best_candidate": {"id": "exp016", "nmse_db": -37.4, "parameter_count": 3980, "source": "runs/x/result.json"},
            "status_counts": {"succeeded": 2, "failed": 1},
            "error_type_counts": {"tool_error": 1},
            "benchmark_rows": [{"source": "benchmarks/a/results.json", "case_count": 3, "target_hit_rate": 0.33, "best_nmse_db": -37.4}],
            "run_rows": [{"source": "runs/a/result.json", "status": "stopped", "rounds": 2, "history_count": 1}],
        }

        html = render_dashboard_html(diagnostics)

        self.assertIn("Agent Runtime Dashboard", html)
        self.assertIn("target_hit_rate", html)
        self.assertIn("exp016", html)
        self.assertIn("tool_error", html)

    def test_write_dashboard_html_creates_parent_directories(self):
        with TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "nested" / "dashboard.html"

            written = write_dashboard_html(Path(tmpdir), output)

            self.assertEqual(written, output)
            self.assertTrue(output.exists())


if __name__ == "__main__":
    unittest.main()
