from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class TraceSummary:
    session_id: str
    event_count: int
    tool_calls: int
    total_latency_ms: float
    retry_count: int
    tool_latency_ms: dict[str, float] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def load_trace_events(path: Path | str) -> list[dict[str, Any]]:
    trace_path = Path(path)
    events = []
    for line in trace_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(json.loads(line))
    return events


def summarize_trace(events: Iterable[dict[str, Any]]) -> TraceSummary:
    rows = list(events)
    session_id = str(rows[0].get("session_id", "unknown")) if rows else "unknown"
    tool_latency: dict[str, float] = {}
    metrics: dict[str, Any] = {}
    errors: list[str] = []
    tool_calls = 0
    total_latency = 0.0
    retry_count = 0

    for event in rows:
        event_type = event.get("event_type")
        if event_type == "tool_end":
            tool_calls += 1
            tool = str(event.get("tool", "unknown"))
            latency = float(event.get("latency_ms") or 0.0)
            attempts = int((event.get("payload") or {}).get("attempts", 1))
            tool_latency[tool] = tool_latency.get(tool, 0.0) + latency
            total_latency += latency
            retry_count += max(0, attempts - 1)
        elif event_type == "metric":
            payload = event.get("payload") or {}
            if "name" in payload:
                metrics[str(payload["name"])] = payload.get("value")
        elif event_type == "error":
            tool = str(event.get("tool", "unknown"))
            errors.append(f"{tool}: {event.get('error')}")

    return TraceSummary(
        session_id=session_id,
        event_count=len(rows),
        tool_calls=tool_calls,
        total_latency_ms=total_latency,
        retry_count=retry_count,
        tool_latency_ms=tool_latency,
        metrics=metrics,
        errors=errors,
    )


def build_replay_markdown(summary: TraceSummary) -> str:
    tool_rows = ["| Tool | Latency ms |", "|---|---:|"]
    for tool, latency in sorted(summary.tool_latency_ms.items()):
        tool_rows.append(f"| {tool} | {latency:.2f} |")
    metric_rows = ["| Metric | Value |", "|---|---:|"]
    for name, value in sorted(summary.metrics.items()):
        metric_rows.append(f"| {name} | {value} |")
    error_text = "\n".join(f"- {error}" for error in summary.errors) if summary.errors else "- None"
    return (
        "# Trace Replay Report\n\n"
        "## Summary\n\n"
        f"- Session: `{summary.session_id}`\n"
        f"- Events: {summary.event_count}\n"
        f"- Tool calls: {summary.tool_calls}\n"
        f"- Total tool latency: {summary.total_latency_ms:.2f} ms\n"
        f"- Retries: {summary.retry_count}\n\n"
        "## Tool Latency\n\n"
        + "\n".join(tool_rows)
        + "\n\n## Metrics\n\n"
        + "\n".join(metric_rows)
        + "\n\n## Errors\n\n"
        + error_text
        + "\n\n## Hiring Evidence\n\n"
        "This replay report demonstrates observable Agent execution: each tool call can be inspected by latency, retry count, metric output, and failure path.\n"
    )


def write_replay_report(trace_path: Path | str, output_path: Path | str) -> Path:
    events = load_trace_events(trace_path)
    summary = summarize_trace(events)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_replay_markdown(summary), encoding="utf-8")
    return path
