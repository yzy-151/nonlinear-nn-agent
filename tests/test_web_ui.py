import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nonlinear_agent.web_ui import read_web_asset, render_home_page


class WebUITest(unittest.TestCase):
    def test_home_page_uses_external_assets(self):
        html = render_home_page()

        self.assertIn('href="/ui/styles.css"', html)
        self.assertIn('src="/ui/app.js"', html)
        self.assertNotIn("<style>", html)
        self.assertNotIn("nav.tabs", html)

    def test_multi_agent_is_default_operations_view(self):
        html = render_home_page()

        self.assertIn('data-view="multiagent"', html)
        self.assertIn('data-default-view="multiagent"', html)
        self.assertIn("Multi-Agent", html)
        self.assertIn("Idea / Plan", html)
        self.assertIn("Coding", html)
        self.assertIn("Execution", html)
        self.assertIn("Writing", html)
        self.assertIn('id="multiExperimentTable"', html)
        self.assertIn('id="resultLinks"', html)

    def test_sidebar_exposes_all_runtime_surfaces(self):
        html = render_home_page()

        for view in (
            "multiagent",
            "agent",
            "workflow",
            "experiments",
            "benchmark",
            "memory",
            "reports",
            "diagnostics",
        ):
            self.assertIn(f'data-view="{view}"', html)

    def test_knowledge_interface_is_visible_but_truthful_about_backend(self):
        html = render_home_page()

        self.assertIn("知识上下文", html)
        self.assertIn("尚未接入", html)
        self.assertIn("docs/knowledge/nonlinear-modeling/", html)
        self.assertIn('id="knowledgeFiles"', html)
        self.assertIn('id="knowledgeContextEnabled"', html)
        self.assertIn('id="knowledgePreviewBtn"', html)

    def test_static_assets_keep_existing_endpoints_and_metric_explanations(self):
        script = read_web_asset("app.js")
        html = render_home_page()

        for endpoint in (
            "/runs/",
            "/agent/",
            "/multi-agent/",
            "/benchmark/events",
            "/agent-benchmark/events",
            "/compare/events",
            "/memory",
            "/artifacts/",
        ):
            self.assertIn(endpoint, script + html)
        for metric in (
            "target_hit_rate",
            "rejected_rate",
            "runtime_failure_rate",
            "average_experiments_used",
            "best_nmse_db",
            "baseline_nmse_db",
            "nmse_improvement_db",
        ):
            self.assertIn(metric, script + html)

    def test_event_view_model_tracks_reflection_and_multi_agent_provenance(self):
        script = read_web_asset("event_view_model.js")

        self.assertIn("previous_reflection_facts", script)
        self.assertIn("previous_reflection_failure_causes", script)
        self.assertIn("multi_agent_role", script)
        self.assertIn("input_refs", script)
        self.assertIn("output_refs", script)
        self.assertIn("model_usage", script)
        self.assertIn("multi_agent_terminal", script)
        self.assertIn("metric_threshold_error", script)
        self.assertIn("experiments", script)
        self.assertIn("final_evaluation", script)

    def test_styles_define_dark_responsive_three_column_console(self):
        css = read_web_asset("styles.css")

        self.assertIn("--bg: #090b10", css)
        self.assertIn("grid-template-columns: 232px", css)
        self.assertIn("grid-template-columns: minmax(260px, 320px) minmax(0, 1fr) minmax(280px, 360px)", css)
        self.assertIn("overflow-wrap: anywhere", css)
        self.assertIn("overflow-x: auto", css)
        self.assertNotIn("linear-gradient", css)


if __name__ == "__main__":
    unittest.main()
