"""ExperimentSupervisor — budgeted orchestration with unique terminal states (v3.7.0).

Minimal LangGraph-ready supervisor core: routes a goal through role-based
model calls, enforces action/time/token/cost budgets, and always returns a
unique terminal state. Child agents never receive raw secrets.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from nonlinear_agent.model_router import ModelRouter, UsageRecord


@dataclass(frozen=True)
class SupervisorResult:
    status: str  # completed | stopped | budget_exceeded | error
    plan_id: str | None = None
    terminal_state: dict[str, Any] = field(default_factory=dict)
    usage: tuple[UsageRecord, ...] = ()
    error: str = ""


class ExperimentSupervisor:
    """Routes one goal through role-based calls under hard budgets."""

    def __init__(
        self,
        router: ModelRouter,
        max_actions: int = 10,
        time_budget_seconds: float | None = None,
        token_budget: int | None = None,
        cost_budget: float | None = None,
        secrets: dict[str, str] | None = None,
    ):
        self.router = router
        self.max_actions = max(1, max_actions)
        self.time_budget = time_budget_seconds
        self.token_budget = token_budget
        self.cost_budget = cost_budget
        self._secrets = secrets or {}
        if token_budget is not None:
            router.set_budgets(token_budget=token_budget)
        if cost_budget is not None:
            router.set_budgets(cost_budget_usd=cost_budget)

    async def run(self, goal: str) -> SupervisorResult:
        started = time.perf_counter()
        for _ in range(self.max_actions):
            if self.time_budget is not None and (
                time.perf_counter() - started > self.time_budget
            ):
                return self._result("budget_exceeded", reason="time budget exceeded")
            if self.router.budget_exceeded():
                return self._result("budget_exceeded", reason="token/cost budget exceeded")
            try:
                self.router.complete("supervisor", f"goal: {goal}")
            except Exception as exc:
                return self._result("error", error=str(exc))
        if self.router.budget_exceeded():
            return self._result("budget_exceeded", reason="token/cost budget exceeded")
        return self._result("completed")

    def _result(self, status: str, reason: str = "", error: str = "") -> SupervisorResult:
        terminal_state = {
            "status": status,
            "reason": reason,
            "max_actions": self.max_actions,
            "usage": {
                "total_cost_usd": round(self.router.total_cost(), 6),
                "total_tokens": self.router.total_tokens(),
                "calls": len(self.router.usage()),
            },
        }
        return SupervisorResult(
            status=status,
            terminal_state=terminal_state,
            usage=tuple(self.router.usage()),
            error=error,
        )
