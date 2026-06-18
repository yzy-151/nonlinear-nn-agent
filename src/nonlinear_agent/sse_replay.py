"""SSE replay and collection utilities (v2.0.0).

Provides client-side helpers for parsing SSE streams and resuming
from a given Last-Event-ID.
"""

from __future__ import annotations

from typing import Any, AsyncIterator


class SSEReplayManager:
    """Client-side SSE stream replay logic."""

    @staticmethod
    def parse_sse_stream(raw_text: str) -> list[dict[str, Any]]:
        """Parse raw SSE text into list of {id, event, data} dicts."""
        events: list[dict[str, Any]] = []
        current: dict[str, Any] = {}
        for line in raw_text.splitlines():
            line = line.rstrip("\r")
            if not line:
                if current:
                    events.append(current)
                    current = {}
                continue
            if line.startswith(":"):
                continue  # SSE comment (heartbeat)
            if ":" in line:
                field, _, value = line.partition(":")
                field = field.strip()
                value = value.lstrip(" ")
                if field == "id":
                    current["id"] = int(value)
                elif field == "event":
                    current["event"] = value
                elif field == "data":
                    import json
                    try:
                        current["data"] = json.loads(value)
                    except json.JSONDecodeError:
                        current["data"] = value
        if current:
            events.append(current)
        return events

    @staticmethod
    async def collect_until(
        event_source: AsyncIterator[str],
        stop_after: int,
        last_event_id: int | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """Collect events from an async SSE generator.

        Returns (events_list, last_observed_id).
        """
        events: list[dict[str, Any]] = []
        last_id = last_event_id or -1

        async for raw in event_source:
            parsed = SSEReplayManager.parse_sse_stream(raw)
            for evt in parsed:
                events.append(evt)
                if "id" in evt:
                    last_id = max(last_id, evt["id"])
            if len(events) >= stop_after:
                break

        return events, last_id
