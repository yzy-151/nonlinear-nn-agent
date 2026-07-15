"""Tests for SSE replay (v2.0.0)."""

from __future__ import annotations

import asyncio
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nonlinear_agent.sse_replay import SSEReplayManager


class TestSSEReplay(unittest.TestCase):

    def test_parse_sse_stream_basic(self):
        raw = (
            "id: 1\n"
            "event: start\n"
            'data: {"session_id":"s1"}\n'
            "\n"
            "id: 2\n"
            "event: tool_start\n"
            'data: {"tool":"generate_config"}\n'
            "\n"
        )
        events = SSEReplayManager.parse_sse_stream(raw)
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["id"], 1)
        self.assertEqual(events[0]["event"], "start")
        self.assertEqual(events[0]["data"]["session_id"], "s1")
        self.assertEqual(events[1]["id"], 2)
        self.assertEqual(events[1]["event"], "tool_start")

    def test_parse_sse_ignores_heartbeat_comments(self):
        raw = (
            ": heartbeat\n"
            "\n"
            "id: 1\n"
            "event: tool_start\n"
            'data: {}\n'
            "\n"
            ": heartbeat\n"
            "\n"
        )
        events = SSEReplayManager.parse_sse_stream(raw)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["id"], 1)

    def test_parse_sse_empty_stream(self):
        events = SSEReplayManager.parse_sse_stream("")
        self.assertEqual(events, [])

    def test_parse_sse_stream_with_non_json_data(self):
        raw = (
            "event: message\n"
            "data: plain text here\n"
            "\n"
        )
        events = SSEReplayManager.parse_sse_stream(raw)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["data"], "plain text here")

    def test_parse_sse_stream_preserves_multiple_events(self):
        raw = ""
        for i in range(5):
            raw += f"id: {i}\nevent: test\n" + 'data: {"i":' + f"{i}" + "}\n\n"
        events = SSEReplayManager.parse_sse_stream(raw)
        self.assertEqual(len(events), 5)
        self.assertEqual([e["id"] for e in events], [0, 1, 2, 3, 4])


class TestSSEReplayResume(unittest.TestCase):
    """A disconnected client can resume from Last-Event-ID without losing events."""

    def test_reconnect_replays_events_after_last_event_id(self):
        from nonlinear_agent.control_plane import RuntimeControlPlane
        from nonlinear_agent.runtime import ExperimentHarnessRuntime, HarnessRequest
        from nonlinear_agent.server import stream_sse_events
        from nonlinear_agent.session import SessionStore
        from nonlinear_agent.tools import ToolCall, ToolRegistry
        from nonlinear_agent.trace import TraceLogger

        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            cp = RuntimeControlPlane(ws / "runtime.sqlite")
            registry = ToolRegistry(default_timeout_seconds=1.0)
            registry.register("step", lambda: {"metrics": {"done": 1}})
            runtime = ExperimentHarnessRuntime(
                tool_registry=registry,
                session_store=SessionStore(ws / "sessions"),
                trace_logger=TraceLogger(ws / "traces" / "s1.jsonl"),
                control_plane=cp,
            )
            request = HarnessRequest(
                session_id="s1",
                goal="replay me",
                steps=[
                    ToolCall(name="step"),
                    ToolCall(name="step"),
                    ToolCall(name="step"),
                ],
            )

            async def collect_first():
                out = []
                async for raw in stream_sse_events(runtime, request):
                    out.extend(SSEReplayManager.parse_sse_stream(raw))
                    if len(out) >= 3:
                        break
                return out

            async def collect_resumed(last_id):
                out = []
                async for raw in stream_sse_events(
                    runtime, request, last_event_id=last_id
                ):
                    out.extend(SSEReplayManager.parse_sse_stream(raw))
                return out

            first = asyncio.run(collect_first())
            resumed = asyncio.run(collect_resumed(first[-1]["id"]))
            cp.close()

        self.assertGreater(resumed[0]["id"], first[-1]["id"])
        self.assertIn(resumed[-1]["event"], {"complete", "failed", "cancelled"})
