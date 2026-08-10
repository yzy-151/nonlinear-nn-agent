"""Execution Agent — tool-registry-only execution with failure taxonomy (v3.8.0).

The execution agent cannot run arbitrary shell commands: every action goes
through the registered ToolRegistry. Failures are classified into a unique
terminal state (timeout / oom / nan / missing_artifact / error / cancelled).
"""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass, field
from typing import Any

from nonlinear_agent.tools import ToolRegistry


@dataclass(frozen=True)
class ExecutionResult:
    status: str  # completed | failed | cancelled
    classification: str  # ok | timeout | oom | nan | missing_artifact | error | cancelled
    tool_name: str
    metrics: dict[str, Any] = field(default_factory=dict)
    artifacts: tuple[str, ...] = ()
    error: str = ""


class ExecutionAgent:
    """Executes registered tools only; audits direct shell usage as zero."""

    def __init__(self, registry: ToolRegistry):
        self._registry = registry
        self._shell_calls = 0

    def audit_shell_calls(self) -> int:
        """Direct shell invocations bypassing the registry (must stay 0)."""
        return self._shell_calls

    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        cancelled: bool = False,
    ) -> ExecutionResult:
        if cancelled:
            return ExecutionResult(
                status="cancelled",
                classification="cancelled",
                tool_name=tool_name,
            )
        if tool_name not in self._registry.tool_names():
            raise ValueError(f"Unregistered tool: {tool_name}")
        tool = self._registry.get_tool(tool_name)
        try:
            output = await asyncio.to_thread(tool, **arguments)
        except TimeoutError as exc:
            return self._failed(tool_name, "timeout", str(exc))
        except MemoryError as exc:
            return self._failed(tool_name, "oom", str(exc))
        except Exception as exc:
            return self._failed(tool_name, "error", str(exc))

        metrics = dict(output.get("metrics", {}))
        artifacts = tuple(str(a) for a in output.get("artifacts", []))
        if any(
            isinstance(value, float) and math.isnan(value)
            for value in metrics.values()
        ):
            return self._failed(tool_name, "nan", "metrics contain NaN")
        if not artifacts and ("artifacts" in output or "nmse_db" in metrics):
            return self._failed(
                tool_name, "missing_artifact", "training metrics without artifacts"
            )
        return ExecutionResult(
            status="completed",
            classification="ok",
            tool_name=tool_name,
            metrics=metrics,
            artifacts=artifacts,
        )

    @staticmethod
    def _failed(tool_name: str, classification: str, error: str) -> ExecutionResult:
        return ExecutionResult(
            status="failed",
            classification=classification,
            tool_name=tool_name,
            error=error,
        )
