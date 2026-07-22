from __future__ import annotations

import asyncio
import inspect
import time
from dataclasses import dataclass, field
from typing import Any, Callable

ToolFunction = Callable[..., Any]


@dataclass(frozen=True)
class ToolCall:
    name: str
    args: dict[str, Any] = field(default_factory=dict)
    timeout_seconds: float | None = None
    retries: int = 0


@dataclass(frozen=True)
class ToolResult:
    name: str
    status: str
    output: dict[str, Any]
    attempts: int
    latency_ms: float
    error: str | None = None


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)
    category: str = "general"
    error_policy: str = "return_error"


class ToolRegistry:
    def __init__(self, default_timeout_seconds: float = 30.0, unknown_tool_policy: str = "raise"):
        self.default_timeout_seconds = default_timeout_seconds
        self.unknown_tool_policy = unknown_tool_policy
        self._tools: dict[str, ToolFunction] = {}
        self._specs: dict[str, ToolSpec] = {}

    def register(self, name: str, func: ToolFunction, spec: ToolSpec | None = None) -> None:
        if not name:
            raise ValueError("Tool name must not be empty.")
        self._tools[name] = func
        self._specs[name] = spec or ToolSpec(name=name)

    def tool_names(self) -> list[str]:
        return sorted(self._tools)

    def describe_tools(self, category: str | None = None) -> list[dict[str, Any]]:
        specs = [self._specs[name] for name in self.tool_names()]
        if category is not None:
            specs = [spec for spec in specs if spec.category == category]
        return [
            {
                "name": spec.name,
                "description": spec.description,
                "input_schema": spec.input_schema,
                "category": spec.category,
                "error_policy": spec.error_policy,
            }
            for spec in specs
        ]

    async def run(self, call: ToolCall) -> ToolResult:
        if call.name not in self._tools:
            if self.unknown_tool_policy == "return_error":
                return ToolResult(
                    name=call.name,
                    status="failed",
                    output={},
                    attempts=0,
                    latency_ms=0.0,
                    error=f"Unknown tool: {call.name}",
                )
            raise KeyError(f"Unknown tool: {call.name}")
        timeout = call.timeout_seconds or self.default_timeout_seconds
        attempts = 0
        started = time.perf_counter()
        last_error: Exception | None = None
        for attempts in range(1, call.retries + 2):
            try:
                output = await asyncio.wait_for(self._invoke(self._tools[call.name], call.args), timeout=timeout)
                if output is None:
                    payload: dict[str, Any] = {}
                elif isinstance(output, dict):
                    payload = output
                else:
                    payload = {"value": output}
                return ToolResult(
                    name=call.name,
                    status="succeeded",
                    output=payload,
                    attempts=attempts,
                    latency_ms=(time.perf_counter() - started) * 1000,
                )
            except Exception as exc:  # noqa: BLE001 - returned as observable tool failure
                last_error = exc
        return ToolResult(
            name=call.name,
            status="failed",
            output={},
            attempts=attempts,
            latency_ms=(time.perf_counter() - started) * 1000,
            error=str(last_error),
        )

    async def _invoke(self, func: ToolFunction, args: dict[str, Any]) -> Any:
        if inspect.iscoroutinefunction(func):
            return await func(**args)
        return await asyncio.to_thread(func, **args)

