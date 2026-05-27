import asyncio
import json
import sys
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nonlinear_agent.run_control import RunController
from nonlinear_agent.reflection import ReflectionPolicy
from nonlinear_agent.runtime import ExperimentHarnessRuntime, HarnessRequest
from nonlinear_agent.runtime_errors import ErrorType
from nonlinear_agent.session import SessionStore
from nonlinear_agent.tools import RetryPolicy, ToolCall, ToolRegistry
from nonlinear_agent.trace import TraceLogger
from nonlinear_agent.llm import FakeLLMClient
from nonlinear_agent.loop import ExperimentPlannerLoop
from nonlinear_agent.planner import ExperimentPlanner
from nonlinear_agent.trace import TraceEvent


class RuntimeHardeningTest(unittest.TestCase):
    def test_tool_timeout_is_classified_and_retryable_by_policy(self):
        attempts = {"count": 0}
        registry = ToolRegistry(default_timeout_seconds=0.01)

        async def sometimes_slow():
            attempts["count"] += 1
            if attempts["count"] == 1:
                await asyncio.sleep(0.05)
            return {"ok": True}

        registry.register("sometimes_slow", sometimes_slow)

        result = asyncio.run(registry.run(ToolCall(
            name="sometimes_slow",
            retries=1,
            retry_policy=RetryPolicy.RETRY_TIMEOUT,
        )))

        self.assertEqual(result.status, "succeeded")
        self.assertEqual(result.attempts, 2)
        self.assertEqual(result.output["ok"], True)

    def test_tool_failure_has_error_type_and_never_retry_policy(self):
        attempts = {"count": 0}
        registry = ToolRegistry(default_timeout_seconds=1.0)

        def broken():
            attempts["count"] += 1
            raise RuntimeError("bad config")

        registry.register("broken", broken)

        result = asyncio.run(registry.run(ToolCall(
            name="broken",
            retries=3,
            retry_policy=RetryPolicy.NEVER,
        )))

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.attempts, 1)
        self.assertEqual(result.error_type, ErrorType.TOOL_ERROR.value)
        self.assertFalse(result.retryable)

    def test_runtime_records_structured_error_type_in_trace_and_session(self):
        with TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            registry = ToolRegistry(default_timeout_seconds=1.0)
            registry.register("broken", lambda: (_ for _ in ()).throw(RuntimeError("bad config")))
            runtime = ExperimentHarnessRuntime(
                tool_registry=registry,
                session_store=SessionStore(workspace / "sessions"),
                trace_logger=TraceLogger(workspace / "traces" / "session-err.jsonl"),
            )

            events = asyncio.run(_collect(runtime.run(HarnessRequest(
                session_id="session-err",
                goal="classify runtime error",
                steps=[ToolCall(name="broken")],
            ))))
            session = SessionStore(workspace / "sessions").load("session-err")
            trace_rows = [
                json.loads(line)
                for line in (workspace / "traces" / "session-err.jsonl").read_text(encoding="utf-8").splitlines()
            ]

        self.assertEqual(events[-1].event_type, "error")
        self.assertEqual(events[-1].error_type, ErrorType.TOOL_ERROR.value)
        self.assertEqual(session.error_types, [ErrorType.TOOL_ERROR.value])
        self.assertEqual(trace_rows[-1]["error_type"], ErrorType.TOOL_ERROR.value)

    def test_runtime_can_cancel_before_next_tool_and_records_cancelled_event(self):
        with TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            controller = RunController()
            registry = ToolRegistry(default_timeout_seconds=1.0)

            def first():
                controller.cancel("user interrupt")
                return {"metrics": {"first_done": 1}}

            registry.register("first", first)
            registry.register("second", lambda: {"metrics": {"second_done": 1}})
            runtime = ExperimentHarnessRuntime(
                tool_registry=registry,
                session_store=SessionStore(workspace / "sessions"),
                trace_logger=TraceLogger(workspace / "traces" / "cancel.jsonl"),
                controller=controller,
            )

            events = asyncio.run(_collect(runtime.run(HarnessRequest(
                session_id="cancel",
                goal="cancel after first tool",
                steps=[ToolCall(name="first"), ToolCall(name="second")],
            ))))
            session = SessionStore(workspace / "sessions").load("cancel")

        self.assertEqual(events[-1].event_type, "cancelled")
        self.assertEqual(events[-1].error_type, ErrorType.CANCELLED.value)
        self.assertEqual(session.status, "cancelled")
        self.assertEqual(session.completed_steps, [1])
        self.assertNotIn("second_done", session.metrics)

    def test_runtime_can_resume_from_step_without_repeating_completed_steps(self):
        with TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            calls = []
            registry = ToolRegistry(default_timeout_seconds=1.0)
            registry.register("first", lambda: calls.append("first") or {"metrics": {"first_done": 1}})
            registry.register("second", lambda: calls.append("second") or {"metrics": {"second_done": 1}})
            runtime = ExperimentHarnessRuntime(
                tool_registry=registry,
                session_store=SessionStore(workspace / "sessions"),
                trace_logger=TraceLogger(workspace / "traces" / "resume.jsonl"),
            )
            request = HarnessRequest(
                session_id="resume",
                goal="resume from failed run",
                steps=[ToolCall(name="first"), ToolCall(name="second")],
                resume_from_step=2,
            )

            events = asyncio.run(_collect(runtime.run(request)))
            session = SessionStore(workspace / "sessions").load("resume")

        self.assertEqual(calls, ["second"])
        self.assertEqual(events[0].payload["resume_from_step"], 2)
        self.assertEqual(session.completed_steps, [2])
        self.assertEqual(session.metrics["second_done"], 1)

    def test_reflection_summarizes_error_types_for_recovery_analysis(self):
        reflection = ReflectionPolicy().reflect(round_index=1, round_records=[
            {
                "id": "timeout",
                "run_status": "failed",
                "error": "tool timed out",
                "error_type": ErrorType.TIMEOUT_ERROR.value,
            },
            {
                "id": "bad-schema",
                "run_status": "rejected",
                "error": "Unsupported planner override fields: rank",
                "error_type": ErrorType.VALIDATION_ERROR.value,
            },
        ])

        self.assertEqual(reflection["error_type_counts"], {
            ErrorType.TIMEOUT_ERROR.value: 1,
            ErrorType.VALIDATION_ERROR.value: 1,
        })
        self.assertIn("timeout", " ".join(reflection["recovery_actions"]).lower())

    def test_planner_loop_carries_runtime_error_type_into_history_and_reflection(self):
        llm = FakeLLMClient(responses=[
            '{"summary":"run failing tool", "stop": false, "experiments": ['
            '{"id":"timeout-demo", "reason":"timeout test", "overrides":{"epochs":0}}]}',
            '{"summary":"stop", "stop": true, "experiments": []}',
        ])

        class TimeoutRuntime:
            async def run(self, request):
                yield TraceEvent(
                    session_id=request.session_id,
                    event_type="error",
                    error="tool timed out",
                    error_type=ErrorType.TIMEOUT_ERROR.value,
                )

        with TemporaryDirectory() as tmpdir:
            loop = ExperimentPlannerLoop(
                planner=ExperimentPlanner(llm_client=llm),
                workspace=Path(tmpdir),
                runtime_factory=lambda session_id: TimeoutRuntime(),
                artifact_dir=Path(tmpdir) / "runs" / "loop",
            )
            result = asyncio.run(loop.run(goal="preserve error type", max_rounds=2))

        self.assertEqual(result.history[0]["error_type"], ErrorType.TIMEOUT_ERROR.value)
        self.assertEqual(result.reflections[0]["error_type_counts"], {ErrorType.TIMEOUT_ERROR.value: 1})


async def _collect(stream):
    return [event async for event in stream]


if __name__ == "__main__":
    unittest.main()
