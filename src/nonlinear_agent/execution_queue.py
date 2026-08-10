"""Execution queue with concurrency limit and resume (v3.8.x)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from nonlinear_agent.execution_agent import ExecutionAgent, ExecutionResult


@dataclass(frozen=True)
class QueueTask:
    task_id: str
    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class QueueTaskResult:
    task_id: str
    result: ExecutionResult
    resumed: bool = False


class ExecutionQueue:
    """Runs tasks through an ExecutionAgent with bounded concurrency.

    Completed task IDs are recorded so a resumed queue skips already-finished
    work instead of re-executing it.
    """

    def __init__(
        self,
        agent: ExecutionAgent,
        max_concurrency: int = 2,
        completed_tasks: set[str] | None = None,
    ):
        self._agent = agent
        self._max_concurrency = max(1, max_concurrency)
        self._completed: set[str] = set(completed_tasks or {})

    def completed_task_ids(self) -> set[str]:
        return set(self._completed)

    async def run(self, tasks: list[QueueTask]) -> list[QueueTaskResult]:
        semaphore = asyncio.Semaphore(self._max_concurrency)

        async def run_one(task: QueueTask) -> QueueTaskResult:
            if task.task_id in self._completed:
                return QueueTaskResult(
                    task_id=task.task_id,
                    result=ExecutionResult(
                        status="completed",
                        classification="resumed",
                        tool_name=task.tool_name,
                    ),
                    resumed=True,
                )
            async with semaphore:
                result = await self._agent.execute(
                    task.tool_name, task.arguments
                )
                if result.status == "completed":
                    self._completed.add(task.task_id)
                return QueueTaskResult(
                    task_id=task.task_id, result=result, resumed=False
                )

        return list(await asyncio.gather(*(run_one(t) for t in tasks)))
