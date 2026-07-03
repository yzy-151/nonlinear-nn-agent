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
        self.assertIn("Result Preview", html)
        self.assertIn("psdPreview", html)
        self.assertIn("/artifacts/", html)
        self.assertIn("baseline_nmse_db", html)
        self.assertIn("nmse_improvement_db", html)

    def test_home_page_uses_dark_console_theme(self):
        html = render_home_page()

        self.assertIn("--bg:#030712", html)
        self.assertIn("--surface:#0f172a", html)
        self.assertNotIn("--bg:#f6f7fb", html)
        self.assertNotIn("background:#fff", html)

    def test_runtime_event_colors_are_grouped_by_event_semantics(self):
        html = render_home_page()

        self.assertIn(".ev-running", html)
        self.assertIn(".ev-success", html)
        self.assertIn(".ev-failure", html)
        self.assertIn(".ev-warning", html)
        self.assertIn(".ev-planner", html)
        self.assertIn(".ev-reflection", html)
        self.assertIn(".ev-benchmark", html)
        self.assertIn("metric_threshold_error", html)
        self.assertIn('return"ev-warning"', html)

    def test_plan_generated_console_reads_reflection_facts_from_top_level_event(self):
        html = render_home_page()

        self.assertIn("previous reflection facts", html)
        self.assertIn("root.previous_reflection_facts", html)
        self.assertIn("previous error reasons", html)
        self.assertIn("new plan:", html)


if __name__ == "__main__":
    unittest.main()
