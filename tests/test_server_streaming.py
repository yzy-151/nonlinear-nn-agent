import asyncio
import json
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nonlinear_agent.server import (
    HarnessRunSpec,
    build_harness_request,
    encode_sse_event,
    stream_sse_events,
)
from nonlinear_agent.trace import TraceEvent


class ServerStreamingTest(unittest.TestCase):
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

    def test_build_harness_request_creates_real_experiment_tool_chain(self):
        request = build_harness_request(
            HarnessRunSpec(
                session_id="server-demo",
                base_config="configs/model-search/lstsq-complexmp-o12-m150.yaml",
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

    def test_create_app_home_route_exposes_demo_ui(self):
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("FastAPI test client is not installed")
        from nonlinear_agent.server import create_app

        client = TestClient(create_app(PROJECT_ROOT))
        response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertIn("Nonlinear Agent Harness", response.text)
        self.assertIn("runForm", response.text)
        self.assertIn("/runs/", response.text)
        self.assertIn("agent-runtime-dashboard.html", response.text)

async def _collect(stream):
    return [chunk async for chunk in stream]


if __name__ == "__main__":
    unittest.main()

