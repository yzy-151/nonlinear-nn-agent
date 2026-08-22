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
        script = read_web_asset("app.js")

        self.assertIn('data-view="multiagent"', html)
        self.assertIn('data-default-view="multiagent"', html)
        self.assertIn("Multi-Agent", html)
        self.assertIn("Idea / Plan", html)
        self.assertIn("Coding", html)
        self.assertIn("Execution", html)
        self.assertIn("Writing", html)
        self.assertIn('id="multiExperimentTable"', html)
        self.assertIn('id="runSummary"', html)
        self.assertIn('id="comparisonBasis"', html)
        self.assertIn('id="resultLinks"', html)
        self.assertIn('id="maRounds"', html)
        self.assertIn('id="maExperiments"', html)
        self.assertIn('id="maFinalEvaluation"', html)
        self.assertIn('rounds: number("maRounds")', script)
        self.assertIn('experiments_per_round: number("maExperiments")', script)
        self.assertNotIn("rounds: 3, experiments_per_round: 3", script)
        self.assertIn('id="agentGraph"', html)
        self.assertIn('["idea_plan", "Idea / Plan"', script)
        self.assertIn('["coding", "Coding"', script)
        self.assertIn('["execution", "Execution"', script)
        self.assertIn('["writing", "Writing"', script)
        self.assertIn('id="approvalMode"', html)
        self.assertIn('value="review"', html)

    def test_sidebar_exposes_all_runtime_surfaces(self):
        html = render_home_page()

        for view in (
            "multiagent",
            "controlled",
            "agent",
            "workflow",
            "experiments",
            "benchmark",
            "memory",
            "reports",
            "diagnostics",
        ):
            self.assertIn(f'data-view="{view}"', html)

    def test_controlled_search_exposes_model_and_parameter_whitelists(self):
        html = render_home_page()
        script = read_web_asset("app.js")

        self.assertIn('id="csModels"', html)
        self.assertIn('id="csTune"', html)
        self.assertIn('id="csBtn"', html)
        self.assertIn("/controlled-search/", script)
        self.assertIn("allowed_models", script)
        self.assertIn("enabled_fields", script)
        self.assertIn("CONTROLLED_DEFAULT_FIELDS", script)
        self.assertIn("normalizeControlledResult", script)
        self.assertIn("renderRunSummary", script)

    def test_search_comparison_names_its_reference_and_paired_deltas(self):
        html = render_home_page()
        script = read_web_asset("app.js")

        self.assertIn("随机搜索（参照组）", html)
        self.assertIn('id="cmpPaired"', html)
        self.assertIn("delta vs random_search", script)

    def test_knowledge_interface_is_connected_and_truthful_about_scope(self):
        html = render_home_page()

        self.assertIn("知识上下文", html)
        self.assertIn("已接入", html)
        self.assertIn("docs/knowledge/nonlinear-modeling/", html)
        self.assertIn('id="knowledgeFiles"', html)
        self.assertIn('id="knowledgeContextEnabled"', html)
        self.assertIn('id="knowledgePreviewBtn"', html)
        self.assertNotIn('id="knowledgeContextEnabled" type="checkbox" disabled', html)

        script = read_web_asset("app.js")
        self.assertIn("knowledge_context_enabled", script)
        self.assertIn("knowledge_top_k", script)
        self.assertIn("/knowledge/sources", script)

    def test_static_assets_keep_existing_endpoints_and_metric_explanations(self):
        script = read_web_asset("app.js")
        html = render_home_page()

        for endpoint in (
            "/runs/",
            "/agent/",
            "/controlled-search/",
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

    def test_styles_define_dark_responsive_node_console(self):
        css = read_web_asset("styles.css")

        self.assertIn("--bg: #090b10", css)
        self.assertIn(".agent-graph", css)
        self.assertIn("stroke-dasharray", css)
        self.assertIn("flowPulse", css)
        self.assertIn(".agent-node.running", css)
        self.assertIn("overflow-wrap: anywhere", css)
        self.assertIn("overflow-x: auto", css)
        self.assertNotIn("linear-gradient", css)

    def test_node_runtime_exposes_cost_latency_report_and_approval_actions(self):
        html = render_home_page()
        script = read_web_asset("app.js")

        self.assertIn('id="approvalDialog"', html)
        self.assertIn('id="approvalReject"', html)
        self.assertIn("/approvals/", script)
        self.assertIn("updateAgentGraph", script)
        self.assertIn("latency_ms", script)
        self.assertIn("cost_usd", script)
        self.assertIn("report:", script)

    def test_each_runtime_mode_has_a_distinct_graph_template(self):
        script = read_web_asset("app.js")

        for mode in ("multiagent", "controlled", "agent", "workflow"):
            self.assertIn(f'{mode}: {{', script)
        for node in ("plan_gate", "reflection", "guard", "verify_artifacts"):
            self.assertIn(node, script)
        self.assertIn("renderWorkflowGraph", script)

    def test_graph_has_typed_ports_artifact_edges_and_feedback_routes(self):
        html = render_home_page()
        script = read_web_asset("app.js")
        css = read_web_asset("styles.css")

        self.assertIn('id="graphLegend"', html)
        self.assertIn("port-control", script + css)
        self.assertIn("port-artifact", script + css)
        self.assertIn("port-feedback", script + css)
        self.assertIn("edge-feedback", script + css)
        self.assertIn("edge-artifact", script + css)
        self.assertIn("routeGraphEvent", script)
        self.assertIn("execution-plan", script)
        self.assertIn("coding-plan", script)
        self.assertIn("writing-plan", script)
        self.assertIn("payload.next_node", script)
        self.assertNotIn('preserveAspectRatio="none"', script)
        self.assertIn("width: 1000px", css)
        self.assertIn('setEdgeState("execution-writing", null)', script)
        self.assertIn('"rejected", "invalid_plan"', script)


    def test_writing_node_and_review_dialog_expose_required_actions(self):
        html = render_home_page()
        script = read_web_asset("app.js")

        self.assertIn('id="nodeArtifactPanel"', html)
        self.assertIn("PDF path", script)
        self.assertIn("审批说明 / Review reason", html)
        self.assertIn("风险与检查点 / Risks and checks", html)
        self.assertIn("✓ Yes", html)
        self.assertIn("× No", html)


if __name__ == "__main__":
    unittest.main()
