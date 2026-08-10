"""Single-agent baseline adapter (v3.7.0).

Wraps the existing ActionPlannerLoop so a multi-agent supervisor can be
ablation-tested against the single-agent baseline with the same terminal
state contract.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from nonlinear_agent.supervisor import SupervisorResult


class SingleAgentBaselineAdapter:
    """Adapts any ``async run(goal) -> result`` runner to SupervisorResult."""

    def __init__(
        self,
        runner: Callable[[str], Awaitable[Any]],
        runner_name: str = "action_loop",
    ):
        self._runner = runner
        self._runner_name = runner_name

    async def run(self, goal: str) -> SupervisorResult:
        result = await self._runner(goal)
        status = str(getattr(result, "status", "completed"))
        if status == "stopped":
            status = "stopped"
        elif status == "max_actions_reached":
            status = "budget_exceeded"
        elif status in ("error", "planner_error"):
            status = "error"
        else:
            status = "completed"
        history = list(getattr(result, "history", []))
        return SupervisorResult(
            status=status,
            terminal_state={
                "adapter": self._runner_name,
                "history_len": len(history),
                "history": history[-5:],
            },
        )
