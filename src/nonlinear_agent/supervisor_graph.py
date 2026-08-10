"""LangGraph-wired ExperimentSupervisor (v3.7.0).

The minimal supervisor core is expressed as a StateGraph: one supervisor
node performs the role-based model call, a PlanGate validates the returned
plan, and budget / invalid JSON / model timeout / cancel injections all
terminate in a unique terminal state.
"""

from __future__ import annotations

import json
from typing import Any, Optional, TypedDict

from nonlinear_agent.model_router import ModelRouter
from nonlinear_agent.plan_gate import PlanGate


class SupervisorState(TypedDict, total=False):
    goal: str
    plan_id: Optional[str]
    status: str
    error: str
    terminal: dict[str, Any]
    cancelled: bool


TERMINAL_STATUSES = ("completed", "stopped", "budget_exceeded", "error", "invalid_plan", "cancelled")


def build_supervisor_graph(
    router: ModelRouter,
    plan_gate: PlanGate | None = None,
) -> Any:
    """Build a compiled LangGraph StateGraph."""
    from langgraph.graph import END, START, StateGraph

    gate = plan_gate or PlanGate()

    def supervisor_node(state: SupervisorState) -> dict[str, Any]:
        if state.get("cancelled"):
            return {"status": "cancelled", "error": "cancelled by user"}
        if router.budget_exceeded():
            return {"status": "budget_exceeded", "error": "token/cost budget exceeded"}
        try:
            raw = router.complete(
                "supervisor", f"goal: {state.get('goal', '')}"
            )
        except Exception as exc:
            return {"status": "error", "error": str(exc)}
        if router.budget_exceeded():
            return {"status": "budget_exceeded", "error": "token/cost budget exceeded"}
        try:
            plan = json.loads(raw)
            if not isinstance(plan, dict):
                raise ValueError("plan must be a JSON object")
        except (json.JSONDecodeError, ValueError) as exc:
            return {"status": "error", "error": f"invalid json: {exc}"}
        errors = gate.validate(plan)
        if errors:
            return {"status": "invalid_plan", "error": "; ".join(errors)}
        return {
            "status": "completed",
            "plan_id": str(plan.get("plan_id", "")),
        }

    graph = StateGraph(SupervisorState)
    graph.add_node("supervisor", supervisor_node)
    graph.add_edge(START, "supervisor")
    graph.add_edge("supervisor", END)
    return graph.compile()


def run_supervisor_graph(
    graph: Any,
    goal: str,
    cancelled: bool = False,
) -> dict[str, Any]:
    """Invoke the compiled graph and return the unique terminal state."""
    result = graph.invoke(
        {"goal": goal, "cancelled": cancelled, "status": "running"}
    )
    status = result.get("status", "error")
    if status not in TERMINAL_STATUSES:
        status = "error"
    result["status"] = status
    return result
