import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nonlinear_agent.web_ui import render_home_page


class WebUITest(unittest.TestCase):
    def test_home_page_exposes_core_actions_and_benchmark_metric_notes(self):
        html = render_home_page()

        self.assertIn("Fixed Workflow", html)
        self.assertIn("LLM Agent Planner", html)
        self.assertIn("Agent Benchmark", html)
        self.assertIn("target_hit_rate", html)
        self.assertIn("rejected_rate", html)
        self.assertIn("runtime_failure_rate", html)
        self.assertIn("average_experiments_used", html)
        self.assertIn("best_nmse_db", html)
        self.assertIn("/benchmark/events", html)

    def test_home_page_uses_dark_console_theme(self):
        html = render_home_page()

        self.assertIn("--bg:#030712", html)
        self.assertIn("--surface:#0f172a", html)
        self.assertNotIn("--bg:#f6f7fb", html)
        self.assertNotIn("background:#fff", html)


if __name__ == "__main__":
    unittest.main()
