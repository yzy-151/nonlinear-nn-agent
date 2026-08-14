import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nonlinear_agent.server import (
    HarnessRunSpec,
    _public_experiment_summary,
    build_harness_request,
    encode_sse_event,
    stream_sse_events,
    stream_multi_agent_events,
)
from nonlinear_agent.trace import TraceEvent


class ServerStreamingTest(unittest.TestCase):
    def test_public_experiment_summary_excludes_candidate_code(self):
        summary = _public_experiment_summary({
            "experiment_id": "round-2-exp-3",
            "candidate_name": "lut_spline",
            "candidate": {"model_type": "lut_spline", "source_code": "secret code"},
            "status": "completed",
            "metrics": {
                "nmse_db": -23.08,
                "parameter_count": 24,
                "source_code": "secret code",
            },
            "artifacts": ["reports/demo/psd.png"],
            "failure_facts": ["secret code"],
            "evaluation_kind": "search",
            "code_result": {"source_code": "secret code"},
        })

        self.assertEqual(summary["model_type"], "lut_spline")
        self.assertEqual(summary["metrics"]["parameter_count"], 24)
        self.assertNotIn("candidate", summary)
        self.assertNotIn("code_result", summary)
        self.assertNotIn("failure_facts", summary)
        self.assertNotIn("source_code", str(summary))

    def test_load_domain_defaults_to_nonlinear_for_blank_name(self):
        """An empty/None domain_name must fall back to the nonlinear domain,
        otherwise the planner loses the prompt contract and the guard
        rejects most real-LLM plans."""
        from nonlinear_agent.domains.nonlinear_modeling import NonlinearModelingDomain
        from nonlinear_agent.domains.synthetic_regression import SyntheticRegressionDomain
        from nonlinear_agent.server import _load_domain

        self.assertIsInstance(_load_domain(""), NonlinearModelingDomain)
        self.assertIsInstance(_load_domain(None), NonlinearModelingDomain)
        self.assertIsInstance(_load_domain("nonlinear"), NonlinearModelingDomain)
        self.assertIsInstance(_load_domain("synthetic"), SyntheticRegressionDomain)

    def test_encode_sse_event_uses_event_type_and_json_payload(self):
        event = TraceEvent(
            session_id="sse-demo",
            event_type="metric",
            tool="run_training",
            status="succeeded",
            payload={"name": "nmse_db", "value": -37.42},
        )

        encoded = encode_sse_event(event)

        self.assertTrue(encoded.startswith("event: metric\n"))
        self.assertTrue(encoded.endswith("\n\n"))
        data_line = encoded.splitlines()[1]
        payload = json.loads(data_line.removeprefix("data: "))
        self.assertEqual(payload["session_id"], "sse-demo")
        self.assertEqual(payload["payload"]["name"], "nmse_db")

    def test_stream_sse_events_wraps_runtime_events(self):
        class FakeRuntime:
            async def run(self, request):
                yield TraceEvent(session_id=request.session_id, event_type="start", status="running")
                yield TraceEvent(session_id=request.session_id, event_type="complete", status="succeeded")

        request = build_harness_request(HarnessRunSpec(session_id="stream-demo"))

        chunks = asyncio.run(_collect(stream_sse_events(FakeRuntime(), request)))

        self.assertEqual(len(chunks), 2)
        self.assertIn("event: start", chunks[0])
        self.assertIn("event: complete", chunks[1])

    def test_multi_agent_stream_exposes_aggregate_coding_outcome(self):
        class FakeGraph:
            def stream(self, initial, stream_mode):
                yield {
                    "coding": {
                        "timeline": [{"role": "coding", "status": "completed"}],
                        "code_results": [
                            {"passed": True, "attempt_count": 2},
                            {"passed": False, "attempt_count": 3},
                        ],
                    }
                }
                yield {
                    "terminal": {
                        "timeline": [{"role": "terminal", "status": "completed"}],
                        "terminal": {"run_id": "multi-summary", "status": "completed"},
                    }
                }

        chunks = asyncio.run(_collect(stream_multi_agent_events(
            FakeGraph(), "multi-summary", "test summary"
        )))
        data_line = next(
            line for line in chunks[0].splitlines() if line.startswith("data: ")
        )
        role_payload = json.loads(data_line.removeprefix("data: "))

        self.assertEqual(role_payload["payload"]["coding_summary"], {
            "candidate_count": 2,
            "passed_count": 1,
            "failed_count": 1,
            "repair_attempts": 5,
        })

    def test_build_harness_request_creates_real_experiment_tool_chain(self):
        request = build_harness_request(
            HarnessRunSpec(
                session_id="server-demo",
                base_config="configs/baselines/lstsq-complexmp-o12-m150.yaml",
                output_dir="reports/server-demo",
                epochs=0,
                nmse_threshold_db=-35.0,
            )
        )

        self.assertEqual(request.session_id, "server-demo")
        self.assertEqual([step.name for step in request.steps], [
            "generate_config",
            "run_training",
            "verify_artifacts",
            "write_report",
        ])
        self.assertEqual(request.steps[0].args["overrides"]["output_dir"], "reports/server-demo")
        self.assertEqual(request.steps[2].args["nmse_threshold_db"], -35.0)

    def test_create_app_health_route(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("FastAPI test client is not installed")
        from nonlinear_agent.server import create_app

        client = TestClient(create_app(PROJECT_ROOT))
        response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_create_app_home_route_exposes_operations_console(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("FastAPI test client is not installed")
        from nonlinear_agent.server import create_app

        client = TestClient(create_app(PROJECT_ROOT))
        response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertIn("Nonlinear Agent Operations", response.text)
        self.assertIn("wfBtn", response.text)
        self.assertIn("agBtn", response.text)
        self.assertIn("csBtn", response.text)
        self.assertIn("agent-runtime-dashboard.html", response.text)

    def test_controlled_search_forwards_strict_model_and_field_whitelists(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("FastAPI test client is not installed")
        from nonlinear_agent.server import create_app

        captured = {}

        async def fake_stream(*args, **kwargs):
            captured.update(kwargs)
            yield "event: complete\ndata: {}\n\n"

        with patch("nonlinear_agent.server.stream_agent_events", fake_stream):
            response = TestClient(create_app(PROJECT_ROOT)).post(
                "/controlled-search/controlled-001/events",
                json={
                    "provider": "fake",
                    "allowed_models": ["complex_lstsq", "spline_mlp"],
                    "enabled_fields": ["memory_depth", "mp_order_count"],
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            captured["allowed_models"],
            ["complex_lstsq", "spline_mlp"],
        )
        self.assertEqual(
            captured["enabled_fields"],
            ["model_type", "memory_depth", "mp_order_count"],
        )

    def test_controlled_search_rejects_unknown_models_and_fields(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("FastAPI test client is not installed")
        from nonlinear_agent.server import create_app

        client = TestClient(create_app(PROJECT_ROOT))
        bad_model = client.post(
            "/controlled-search/bad-model/events",
            json={"allowed_models": ["invented_model"]},
        )
        bad_field = client.post(
            "/controlled-search/bad-field/events",
            json={
                "allowed_models": ["complex_lstsq"],
                "enabled_fields": ["shell_command"],
            },
        )

        self.assertEqual(bad_model.status_code, 400)
        self.assertIn("Unknown allowed models", bad_model.json()["detail"])
        self.assertEqual(bad_field.status_code, 400)
        self.assertIn("Unknown tunable fields", bad_field.json()["detail"])

    def test_create_app_serves_allowlisted_ui_assets(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("FastAPI test client is not installed")
        from nonlinear_agent.server import create_app

        client = TestClient(create_app(PROJECT_ROOT))
        css = client.get("/ui/styles.css")
        script = client.get("/ui/app.js")
        blocked = client.get("/ui/../server.py")

        self.assertEqual(css.status_code, 200)
        self.assertIn("text/css", css.headers["content-type"])
        self.assertIn("grid-template-columns: 232px", css.text)
        self.assertEqual(script.status_code, 200)
        self.assertIn("/runs/", script.text)
        self.assertEqual(blocked.status_code, 404)

    def test_diagnostics_route_rejects_windows_path_escape(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("FastAPI test client is not installed")
        from nonlinear_agent.server import create_app

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            diagnostics = root / "docs" / "diagnostics"
            diagnostics.mkdir(parents=True)
            (diagnostics / "ok.md").write_text("ok", encoding="utf-8")
            (root / "docs" / "secret.txt").write_text("secret", encoding="utf-8")
            client = TestClient(create_app(root))

            ok = client.get("/diagnostics/ok.md")
            escaped = client.get("/diagnostics/%5C..%5Csecret.txt")

        self.assertEqual(ok.status_code, 200)
        self.assertEqual(escaped.status_code, 404)
        self.assertNotIn("secret", escaped.text)

    def test_cancel_only_signals_owned_session(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("FastAPI test client is not installed")
        from nonlinear_agent.server import create_app

        client = TestClient(create_app(PROJECT_ROOT))
        with patch("subprocess.run") as process_run:
            response = client.post("/cancel/no-running-session")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "cancelling")
        process_run.assert_not_called()

    def test_create_app_serves_safe_artifact_images(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("FastAPI test client is not installed")
        from tempfile import TemporaryDirectory
        from nonlinear_agent.server import create_app

        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            image_path = root / "reports" / "demo" / "psd.png"
            image_path.parent.mkdir(parents=True)
            image_path.write_bytes(b"fake png")
            client = TestClient(create_app(root))

            ok = client.get("/artifacts/reports/demo/psd.png")
            blocked = client.get("/artifacts/../secret.txt")

        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.content, b"fake png")
        self.assertEqual(blocked.status_code, 404)

async def _collect(stream):
    return [chunk async for chunk in stream]


if __name__ == "__main__":
    unittest.main()
