import asyncio
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nonlinear_agent.hooks import HookManager
from nonlinear_agent.runtime import ExperimentHarnessRuntime, HarnessRequest
from nonlinear_agent.session import SessionStore
from nonlinear_agent.tools import ToolCall, ToolRegistry, ToolSpec
from nonlinear_agent.trace import TraceLogger


class HarnessRuntimeTest(unittest.TestCase):
    def test_tool_registry_retries_failed_tool_and_returns_result(self):
        attempts = {"count": 0}
        registry = ToolRegistry(default_timeout_seconds=1.0)

        def flaky_tool(value):
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise RuntimeError("temporary failure")
            return {"metric": value}

        registry.register("flaky", flaky_tool)
        result = asyncio.run(registry.run(ToolCall(name="flaky", args={"value": -37.4}, retries=1)))

        self.assertEqual(result.status, "succeeded")
        self.assertEqual(result.output["metric"], -37.4)
        self.assertEqual(result.attempts, 2)
        self.assertGreaterEqual(result.latency_ms, 0.0)

    def test_tool_registry_exposes_tool_specs_for_progressive_disclosure(self):
        registry = ToolRegistry(default_timeout_seconds=1.0)

        def generate_config(experiment_id):
            return {"config_path": f"configs/{experiment_id}.yaml"}

        registry.register(
            "generate_config",
            generate_config,
            spec=ToolSpec(
                name="generate_config",
                description="Generate an experiment YAML config.",
                input_schema={"type": "object", "required": ["experiment_id"]},
                category="experiment",
                error_policy="fail_fast",
            ),
        )

        descriptions = registry.describe_tools(category="experiment")

        self.assertEqual(descriptions, [
            {
                "name": "generate_config",
                "description": "Generate an experiment YAML config.",
                "input_schema": {"type": "object", "required": ["experiment_id"]},
                "category": "experiment",
                "error_policy": "fail_fast",
            }
        ])

    def test_tool_registry_can_return_structured_unknown_tool_failure(self):
        registry = ToolRegistry(default_timeout_seconds=1.0, unknown_tool_policy="return_error")

        result = asyncio.run(registry.run(ToolCall(name="missing", args={})))

        self.assertEqual(result.name, "missing")
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.attempts, 0)
        self.assertIn("Unknown tool", result.error)

    def test_session_store_saves_and_loads_resume_state(self):
        with TemporaryDirectory() as tmpdir:
            store = SessionStore(Path(tmpdir) / "sessions")
            session = store.create(goal="run nonlinear experiment", session_id="session-001")
            session.status = "running"
            session.current_step = "evaluate_nmse"
            session.metrics["nmse_db"] = -41.8
            session.artifacts.append("reports/demo/psd.png")
            store.save(session)

            loaded = store.load("session-001")

            self.assertEqual(loaded.goal, "run nonlinear experiment")
            self.assertEqual(loaded.status, "running")
            self.assertEqual(loaded.current_step, "evaluate_nmse")
            self.assertEqual(loaded.metrics["nmse_db"], -41.8)
            self.assertEqual(loaded.artifacts, ["reports/demo/psd.png"])

    def test_runtime_streams_events_calls_hooks_and_writes_trace(self):
        with TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            trace_path = workspace / "traces" / "session-001.jsonl"
            seen_hooks = []
            registry = ToolRegistry(default_timeout_seconds=1.0)
            hooks = HookManager()

            def generate_config(experiment_id):
                return {"config_path": f"configs/{experiment_id}.yaml"}

            async def evaluate_nmse(config_path):
                return {"metrics": {"nmse_db": -38.2}, "artifacts": ["reports/demo/psd.png"]}

            registry.register("generate_config", generate_config)
            registry.register("evaluate_nmse", evaluate_nmse)
            hooks.register("before_tool", lambda event: seen_hooks.append(("before", event.tool)))
            hooks.register("after_tool", lambda event: seen_hooks.append(("after", event.tool)))
            hooks.register("on_metric", lambda event: seen_hooks.append(("metric", event.payload["name"])))

            runtime = ExperimentHarnessRuntime(
                tool_registry=registry,
                session_store=SessionStore(workspace / "sessions"),
                trace_logger=TraceLogger(trace_path),
                hooks=hooks,
            )
            request = HarnessRequest(
                session_id="session-001",
                goal="produce reproducible nonlinear experiment evidence",
                steps=[
                    ToolCall(name="generate_config", args={"experiment_id": "demo"}),
                    ToolCall(name="evaluate_nmse", args={"config_path": "configs/demo.yaml"}),
                ],
            )

            events = asyncio.run(_collect(runtime.run(request)))
            loaded_session = SessionStore(workspace / "sessions").load("session-001")
            trace_rows = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]

            self.assertEqual(events[0].event_type, "start")
            self.assertEqual(events[-1].event_type, "complete")
            self.assertEqual(loaded_session.status, "succeeded")
            self.assertEqual(loaded_session.metrics["nmse_db"], -38.2)
            self.assertEqual(loaded_session.artifacts, ["reports/demo/psd.png"])
            self.assertIn(("before", "generate_config"), seen_hooks)
            self.assertIn(("after", "evaluate_nmse"), seen_hooks)
            self.assertIn(("metric", "nmse_db"), seen_hooks)
            self.assertTrue(any(row["event_type"] == "tool_end" for row in trace_rows))
            self.assertTrue(all(row["session_id"] == "session-001" for row in trace_rows))

    def test_runtime_records_error_event_and_failed_session(self):
        with TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            registry = ToolRegistry(default_timeout_seconds=1.0)
            hooks = HookManager()
            seen_errors = []

            def broken_tool():
                raise ValueError("bad config")

            registry.register("broken", broken_tool)
            hooks.register("on_error", lambda event: seen_errors.append(event.error))
            runtime = ExperimentHarnessRuntime(
                tool_registry=registry,
                session_store=SessionStore(workspace / "sessions"),
                trace_logger=TraceLogger(workspace / "traces" / "session-err.jsonl"),
                hooks=hooks,
            )

            events = asyncio.run(_collect(runtime.run(HarnessRequest(
                session_id="session-err",
                goal="show failure observability",
                steps=[ToolCall(name="broken", args={})],
            ))) )
            loaded_session = SessionStore(workspace / "sessions").load("session-err")

            self.assertEqual(events[-1].event_type, "error")
            self.assertEqual(loaded_session.status, "failed")
            self.assertIn("bad config", loaded_session.errors[0])
            self.assertEqual(seen_errors, ["bad config"])


async def _collect(stream):
    return [event async for event in stream]


if __name__ == "__main__":
    unittest.main()
