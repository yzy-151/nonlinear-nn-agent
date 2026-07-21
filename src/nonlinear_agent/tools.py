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


class ToolRegistry:
    def __init__(self, default_timeout_seconds: float = 30.0):
        self.default_timeout_seconds = default_timeout_seconds
        self._tools: dict[str, ToolFunction] = {}

    def register(self, name: str, func: ToolFunction) -> None:
        if not name:
            raise ValueError("Tool name must not be empty.")
        self._tools[name] = func

    async def run(self, call: ToolCall) -> ToolResult:
        if call.name not in self._tools:
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
