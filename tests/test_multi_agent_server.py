from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.test_supervisor_e2e import _plan


class TestMultiAgentServer(unittest.TestCase):
    def test_approval_endpoints_list_and_decide_pending_review(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("fastapi test dependencies unavailable")
        import threading
        import time
        from nonlinear_agent.approval import ApprovalController
        from nonlinear_agent.server import create_app

        app = create_app(".")
        controller = ApprovalController("review-api", mode="review", timeout_seconds=2)
        app.state.approval_controllers["review-api"] = controller
        result = []
        worker = threading.Thread(
            target=lambda: result.append(
                controller.review("coding", "output", {"reason": "inspect code gate"})
            )
        )
        worker.start()
        for _ in range(20):
            if controller.pending():
                break
            time.sleep(0.01)
        client = TestClient(app)

        pending = client.get("/approvals/review-api").json()["pending"]
        response = client.post(
            f"/approvals/review-api/{pending[0]['approval_id']}/decision",
            json={"approved": False, "reason": "Add a shape check."},
        )
        worker.join(timeout=1)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(result[0].approved)
        self.assertIn("shape check", result[0].reason)

    def test_registered_model_catalog_exposes_planner_selectable_tools(self):
        from nonlinear_agent.server import _registered_model_catalog

        catalog = _registered_model_catalog()

        self.assertIn("tiny_mlp", catalog)
        self.assertIn("spline_mlp", catalog)
        self.assertIn("complex_lstsq", catalog)
        self.assertIn("memory_depth", catalog["tiny_mlp"]["config_fields"])
        self.assertEqual(catalog["tiny_mlp"]["implementation_source"], "registered_model")

    def test_registered_anchor_profile_is_fixed_and_trace_backed(self):
        from nonlinear_agent.server import _registered_anchor_from_payload

        disabled = _registered_anchor_from_payload({})
        enabled = _registered_anchor_from_payload(
            {"registered_anchor_profile": "tiny-mem15-mp3-h80-40db"}
        )

        self.assertIsNone(disabled)
        self.assertEqual(enabled["model_type"], "tiny_mlp")
        self.assertEqual(enabled["config"]["memory_depth"], 15)
        self.assertEqual(enabled["config"]["mp_order_count"], 3)
        self.assertEqual(enabled["config"]["epochs"], 1500)
        self.assertEqual(enabled["parameter_count_max"], 8000)

        high_accuracy = _registered_anchor_from_payload(
            {"registered_anchor_profile": "tiny-mem20-mp3-h96-42db"}
        )
        self.assertEqual(high_accuracy["model_type"], "tiny_mlp")
        self.assertEqual(high_accuracy["config"]["memory_depth"], 20)
        self.assertEqual(high_accuracy["config"]["mp_order_count"], 3)
        self.assertEqual(high_accuracy["config"]["hidden_units"], 96)
        self.assertEqual(high_accuracy["config"]["epochs"], 10000)
        self.assertEqual(high_accuracy["parameter_count_max"], 13000)

        with self.assertRaisesRegex(ValueError, "unsupported registered anchor profile"):
            _registered_anchor_from_payload({"registered_anchor_profile": "arbitrary-code"})

    def test_knowledge_sources_endpoint_lists_whitelisted_chunks(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("fastapi test dependencies unavailable")

        from nonlinear_agent.server import create_app

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            knowledge = root / "docs" / "knowledge" / "nonlinear-modeling"
            knowledge.mkdir(parents=True)
            (knowledge / "prior.md").write_text(
                "# Compact prior\n\nUse a shallow LUT spline candidate.",
                encoding="utf-8",
            )
            response = TestClient(create_app(root)).get("/knowledge/sources")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["root"], "docs/knowledge/nonlinear-modeling/")
        self.assertEqual(body["sources"][0]["name"], "prior.md")
        self.assertGreater(body["sources"][0]["chunk_count"], 0)
        self.assertTrue(body["sources"][0]["content_hashes"])

    def test_role_client_limits_bound_long_coding_responses(self):
        from nonlinear_agent.server import _configure_multi_agent_client

        class Client:
            max_tokens = None
            max_retries = 3
            temperature = 0.2

        coding = _configure_multi_agent_client(
            Client(), "coding", temperature=0.0, payload={}
        )
        writing = _configure_multi_agent_client(
            Client(), "writing", temperature=0.1, payload={}
        )

        self.assertEqual(coding.max_tokens, 8000)
        self.assertEqual(writing.max_tokens, 5000)
        self.assertEqual(coding.max_retries, 1)
        self.assertEqual(coding.temperature, 0.0)

    def test_sse_endpoint_streams_each_role_and_one_terminal(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("fastapi test dependencies unavailable")

        from nonlinear_agent.server import create_app
        from nonlinear_agent.supervisor_graph import MultiAgentWorkers, build_multi_agent_graph

        graph = build_multi_agent_graph(
            MultiAgentWorkers(
                idea_plan=lambda request: _plan(),
                coding=lambda request: {"passed": True},
                execution=lambda request: {
                    "status": "completed",
                    "classification": "ok",
                    "metrics": {"nmse_db": -37.5},
                    "artifacts": ["reports/e2e/psd.png"],
                },
                writing=lambda request: {"pdf_path": "reports/e2e/report.pdf"},
            )
        )
        client = TestClient(
            create_app(".", multi_agent_graph_factory=lambda payload: graph)
        )

        response = client.post(
            "/multi-agent/run-web/events",
            json={"goal": "stream a complete multi-agent run"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text.count("event: multi_agent_terminal"), 1)
        for role in ("idea_plan", "plan_gate", "coding", "execution", "writing"):
            self.assertIn(f'"role": "{role}"', response.text)
        self.assertIn('"status": "completed"', response.text)
        self.assertIn('"latency_ms":', response.text)
        self.assertIn('"cost_usd":', response.text)


if __name__ == "__main__":
    unittest.main()
