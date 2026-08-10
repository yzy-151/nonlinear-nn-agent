"""Structured one-step actions for the agent-controlled execution mode."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from nonlinear_agent.tools import ToolCall, ToolRegistry


@dataclass(frozen=True)
class AgentAction:
    """One auditable planner decision: call one tool or stop."""

    action_type: str
    action_id: str
    reason: str
    tool_name: str | None = None
    arguments: dict[str, Any] = field(default_factory=dict)
    caused_by_event_ids: tuple[str, ...] = ()

    @property
    def is_stop(self) -> bool:
        return self.action_type == "stop"


def parse_agent_action(text: str) -> AgentAction:
    """Parse a planner JSON response into one action."""
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("Agent action must be a JSON object.")

    action_type = str(payload.get("type", "")).strip()
    if action_type not in {"tool_call", "stop"}:
        raise ValueError("Agent action type must be tool_call or stop.")

    action_id = str(payload.get("action_id", "")).strip()
    if not action_id:
        raise ValueError("Agent action is missing action_id.")

    arguments = payload.get("arguments", {})
    if not isinstance(arguments, dict):
        raise ValueError("Agent action arguments must be an object.")

    caused_by = payload.get("caused_by_event_ids", [])
    if not isinstance(caused_by, list) or not all(
        isinstance(event_id, str) for event_id in caused_by
    ):
        raise ValueError("caused_by_event_ids must be an array of strings.")

    tool_name = payload.get("tool")
    if action_type == "tool_call" and not str(tool_name or "").strip():
        raise ValueError("Tool-call action is missing tool.")

    return AgentAction(
        action_type=action_type,
        action_id=action_id,
        reason=str(payload.get("reason", "")),
        tool_name=str(tool_name).strip() if tool_name is not None else None,
        arguments=dict(arguments),
        caused_by_event_ids=tuple(caused_by),
    )


def validate_agent_action(
    action: AgentAction, registry: ToolRegistry
) -> ToolCall | None:
    """Validate an action against the registered ToolSpec schema."""
    if action.is_stop:
        return None
    if action.action_type != "tool_call":
        raise ValueError(f"Unsupported action type: {action.action_type}")

    tool_name = str(action.tool_name or "")
    try:
        spec = registry.get_tool_spec(tool_name)
    except KeyError as exc:
        raise ValueError(f"Unknown tool: {tool_name}") from exc

    schema = spec.input_schema or {}
    required = [str(name) for name in schema.get("required", [])]
    missing = [name for name in required if name not in action.arguments]
    if missing:
        raise ValueError(f"Missing required arguments: {', '.join(sorted(missing))}")

    properties = schema.get("properties", {})
    if schema.get("additionalProperties") is False and isinstance(properties, dict):
        unexpected = sorted(set(action.arguments) - set(properties))
        if unexpected:
            raise ValueError(f"Unexpected arguments: {', '.join(unexpected)}")

    if isinstance(properties, dict):
        for name, value in action.arguments.items():
            field_schema = properties.get(name)
            if not isinstance(field_schema, dict) or "type" not in field_schema:
                continue
            expected = str(field_schema["type"])
            if not _matches_json_type(value, expected):
                raise ValueError(f"{name} must be {expected}")

    return ToolCall(name=tool_name, args=dict(action.arguments))


def _matches_json_type(value: Any, expected: str) -> bool:
    if expected == "string":
        return isinstance(value, str)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "null":
        return value is None
    return True
