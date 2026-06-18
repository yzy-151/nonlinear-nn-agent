"""Tests for SSE replay (v2.0.0)."""

from __future__ import annotations

import unittest

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
