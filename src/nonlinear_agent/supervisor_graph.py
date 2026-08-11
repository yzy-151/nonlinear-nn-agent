"""LangGraph-wired ExperimentSupervisor (v3.7.0).

The minimal supervisor core is expressed as a StateGraph: one supervisor
node performs the role-based model call, a PlanGate validates the returned
plan, and budget / invalid JSON / model timeout / cancel injections all
terminate in a unique terminal state.
"""

from __future__ import annotations

import json
import operator
from dataclasses import asdict, dataclass
from typing import Annotated, Any, Callable, Optional, TypedDict

from nonlinear_agent.model_router import ModelRouter
from nonlinear_agent.plan_gate import PlanGate
from nonlinear_agent.execution_agent import ExecutionResult
from nonlinear_agent.failure_handoff import FailureHandoff


class SupervisorState(TypedDict, total=False):
    goal: str
    plan_id: Optional[str]
    status: str
    error: str
    terminal: dict[str, Any]
    cancelled: bool


TERMINAL_STATUSES = (
    "completed",
    "stopped",
    "budget_exceeded",
    "error",
    "invalid_plan",
    "cancelled",
)


Worker = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class MultiAgentWorkers:
    """Narrow worker ports used by the supervisor state graph."""

    idea_plan: Worker
    coding: Worker
    execution: Worker
    writing: Worker


class MultiAgentRunState(TypedDict, total=False):
    run_id: str
    goal: str
    status: str
    cancelled: bool
    plan: dict[str, Any]
    code_result: dict[str, Any]
    execution_result: dict[str, Any]
    report_result: dict[str, Any]
    failure_facts: dict[str, Any]
    failures: Annotated[list[dict[str, Any]], operator.add]
    replan_count: int
    error: str
    terminal: dict[str, Any]
    timeline: Annotated[list[dict[str, Any]], operator.add]


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


def build_multi_agent_graph(
    workers: MultiAgentWorkers,
    plan_gate: PlanGate | None = None,
    max_replans: int = 1,
    model_router: ModelRouter | None = None,
    cancel_check: Callable[[], bool] | None = None,
) -> Any:
    """Build the Idea -> Code -> Execute -> Write supervisor graph.

    Workers receive only their structured handoff. The graph owns routing,
    failure budgets, role events, cancellation and the unique terminal state.
    """
    if max_replans < 0:
        raise ValueError("max_replans must be non-negative")
    from langgraph.graph import END, START, StateGraph

    gate = plan_gate or PlanGate()

    def idea_plan_node(state: MultiAgentRunState) -> dict[str, Any]:
        if _is_cancelled(state, cancel_check):
            return _terminal_update(state, "cancelled", "cancelled by user", "idea_plan")
        request = {
            "run_id": state["run_id"],
            "goal": state["goal"],
            "replan_count": state.get("replan_count", 0),
            "failure_facts": dict(state.get("failure_facts", {})),
        }
        usage_start = len(model_router.usage()) if model_router else 0
        try:
            plan = workers.idea_plan(request)
            if not isinstance(plan, dict):
                raise TypeError("idea_plan worker must return an object")
        except Exception as exc:
            return _terminal_update(state, "error", str(exc), "idea_plan")
        usage = _usage_since(model_router, usage_start)
        if model_router is not None and model_router.budget_exceeded():
            return {
                "status": "budget_exceeded",
                "error": "token/cost budget exceeded",
                "plan": plan,
                "timeline": [
                    _role_event(
                        state,
                        "idea_plan",
                        "budget_exceeded",
                        output_refs=[f"plan:{plan.get('plan_id', 'unknown')}"],
                        model_usage=usage,
                    )
                ],
            }
        return {
            "status": "running",
            "plan": plan,
            "timeline": [_role_event(
                state,
                "idea_plan",
                "completed",
                input_refs=_failure_refs(state.get("failure_facts", {})),
                output_refs=[f"plan:{plan.get('plan_id', 'unknown')}"],
                model_usage=usage,
                failure_facts=dict(state.get("failure_facts", {})),
            )],
        }

    def plan_gate_node(state: MultiAgentRunState) -> dict[str, Any]:
        if _is_cancelled(state, cancel_check):
            return _terminal_update(state, "cancelled", "cancelled by user", "plan_gate")
        errors = gate.validate(state.get("plan", {}))
        if errors:
            return _terminal_update(state, "invalid_plan", "; ".join(errors), "plan_gate")
        return {
            "status": "running",
            "timeline": [
                _role_event(
                    state,
                    "plan_gate",
                    "completed",
                    input_refs=[
                        f"plan:{state['plan'].get('plan_id', 'unknown')}"
                    ],
                )
            ],
        }

    def coding_node(state: MultiAgentRunState) -> dict[str, Any]:
        if _is_cancelled(state, cancel_check):
            return _terminal_update(state, "cancelled", "cancelled by user", "coding")
        plan = state["plan"]
        if not plan.get("required_code_changes"):
            result = {"passed": True, "status": "skipped"}
            event_status = "skipped"
        else:
            usage_start = len(model_router.usage()) if model_router else 0
            try:
                result = workers.coding(
                    {"run_id": state["run_id"], "goal": state["goal"], "plan": plan}
                )
                if not isinstance(result, dict):
                    raise TypeError("coding worker must return an object")
            except Exception as exc:
                return _terminal_update(state, "error", str(exc), "coding")
            if not result.get("passed", False):
                return _terminal_update(
                    state,
                    "error",
                    str(result.get("error") or "coding gate failed"),
                    "coding",
                )
            usage = _usage_since(model_router, usage_start)
            if model_router is not None and model_router.budget_exceeded():
                return {
                    "status": "budget_exceeded",
                    "error": "token/cost budget exceeded",
                    "code_result": result,
                    "timeline": [
                        _role_event(
                            state,
                            "coding",
                            "budget_exceeded",
                            input_refs=[f"plan:{plan.get('plan_id', 'unknown')}"],
                            model_usage=usage,
                        )
                    ],
                }
            event_status = "completed"
        if not plan.get("required_code_changes"):
            usage = []
        return {
            "status": "running",
            "code_result": result,
            "timeline": [
                _role_event(
                    state,
                    "coding",
                    event_status,
                    input_refs=[f"plan:{plan.get('plan_id', 'unknown')}"],
                    model_usage=usage,
                )
            ],
        }

    def execution_node(state: MultiAgentRunState) -> dict[str, Any]:
        if _is_cancelled(state, cancel_check):
            return _terminal_update(state, "cancelled", "cancelled by user", "execution")
        request = {
            "run_id": state["run_id"],
            "goal": state["goal"],
            "plan": state["plan"],
            "code_result": state.get("code_result", {}),
        }
        try:
            result = workers.execution(request)
            if not isinstance(result, dict):
                raise TypeError("execution worker must return an object")
        except Exception as exc:
            result = {
                "status": "failed",
                "classification": "error",
                "tool_name": "unknown",
                "error": str(exc),
            }
        if result.get("status") == "completed":
            return {
                "status": "running",
                "execution_result": result,
                "failure_facts": {},
                "timeline": [
                    _role_event(
                        state,
                        "execution",
                        "completed",
                        output_refs=_artifact_refs(result),
                    )
                ],
            }

        failure = _execution_failure(result)
        can_replan = failure["retryable"] and state.get("replan_count", 0) < max_replans
        if can_replan:
            return {
                "status": "replanning",
                "execution_result": result,
                "failure_facts": failure,
                "failures": [failure],
                "replan_count": state.get("replan_count", 0) + 1,
                "timeline": [_role_event(
                    state,
                    "execution",
                    "failed",
                    output_refs=[f"failure:{failure['classification']}"],
                    failure_facts=failure,
                )],
            }
        status = "cancelled" if failure["classification"] == "cancelled" else "error"
        return _terminal_update(
            state,
            status,
            failure["error"],
            "execution",
            output_refs=[f"failure:{failure['classification']}"],
        )

    def writing_node(state: MultiAgentRunState) -> dict[str, Any]:
        if _is_cancelled(state, cancel_check):
            return _terminal_update(state, "cancelled", "cancelled by user", "writing")
        request = {
            "run_id": state["run_id"],
            "goal": state["goal"],
            "plan": state["plan"],
            "code_result": state.get("code_result", {}),
            "execution_result": state["execution_result"],
            "failures": list(state.get("failures", [])),
        }
        usage_start = len(model_router.usage()) if model_router else 0
        try:
            result = workers.writing(request)
            if not isinstance(result, dict):
                raise TypeError("writing worker must return an object")
        except Exception as exc:
            return _terminal_update(state, "error", str(exc), "writing")
        usage = _usage_since(model_router, usage_start)
        if model_router is not None and model_router.budget_exceeded():
            return {
                "status": "budget_exceeded",
                "error": "token/cost budget exceeded",
                "report_result": result,
                "timeline": [
                    _role_event(
                        state,
                        "writing",
                        "budget_exceeded",
                        output_refs=_report_refs(result),
                        model_usage=usage,
                    )
                ],
            }
        return {
            "status": "completed",
            "report_result": result,
            "timeline": [
                _role_event(
                    state,
                    "writing",
                    "completed",
                    output_refs=_report_refs(result),
                    model_usage=usage,
                )
            ],
        }

    def terminal_node(state: MultiAgentRunState) -> dict[str, Any]:
        status = state.get("status", "error")
        terminal = {
            "run_id": state["run_id"],
            "status": status if status in TERMINAL_STATUSES else "error",
            "error": state.get("error", ""),
        }
        terminal.update(
            {
                key: value
                for key, value in state.get("report_result", {}).items()
                if key.endswith("_path")
            }
        )
        return {
            "status": terminal["status"],
            "terminal": terminal,
            "timeline": [
                _role_event(
                    state,
                    "terminal",
                    terminal["status"],
                    output_refs=_report_refs(
                        state.get("report_result", {})
                    ),
                )
            ],
        }

    def after_idea(state: MultiAgentRunState) -> str:
        return "plan_gate" if state.get("status") == "running" else "terminal"

    def after_gate(state: MultiAgentRunState) -> str:
        return "coding" if state.get("status") == "running" else "terminal"

    def after_coding(state: MultiAgentRunState) -> str:
        return "execution" if state.get("status") == "running" else "terminal"

    def after_execution(state: MultiAgentRunState) -> str:
        if state.get("status") == "replanning":
            return "idea_plan"
        return "writing" if state.get("status") == "running" else "terminal"

    graph = StateGraph(MultiAgentRunState)
    graph.add_node("idea_plan", idea_plan_node)
    graph.add_node("plan_gate", plan_gate_node)
    graph.add_node("coding", coding_node)
    graph.add_node("execution", execution_node)
    graph.add_node("writing", writing_node)
    graph.add_node("terminal", terminal_node)
    graph.add_edge(START, "idea_plan")
    graph.add_conditional_edges("idea_plan", after_idea)
    graph.add_conditional_edges("plan_gate", after_gate)
    graph.add_conditional_edges("coding", after_coding)
    graph.add_conditional_edges("execution", after_execution)
    graph.add_edge("writing", "terminal")
    graph.add_edge("terminal", END)
    return graph.compile()


def run_multi_agent_graph(
    graph: Any,
    goal: str,
    run_id: str,
    cancelled: bool = False,
) -> dict[str, Any]:
    """Run a compiled multi-agent graph from a minimal initial state."""
    result = graph.invoke(
        {
            "run_id": run_id,
            "goal": goal,
            "status": "running",
            "cancelled": cancelled,
            "replan_count": 0,
            "timeline": [],
            "failures": [],
        }
    )
    terminal = result.get("terminal") or {"run_id": run_id, "status": "error"}
    result["status"] = terminal.get("status", "error")
    result["terminal"] = terminal
    return result


def _role_event(
    state: MultiAgentRunState,
    role: str,
    status: str,
    input_refs: list[str] | None = None,
    output_refs: list[str] | None = None,
    model_usage: list[dict[str, Any]] | None = None,
    failure_facts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    sequence = len(state.get("timeline", [])) + 1
    return {
        "event_id": f"{state['run_id']}:{sequence:03d}:{role}",
        "run_id": state["run_id"],
        "sequence": sequence,
        "role": role,
        "status": status,
        "input_refs": list(input_refs or []),
        "output_refs": list(output_refs or []),
        "model_usage": list(model_usage or []),
        "failure_facts": dict(failure_facts or {}),
    }


def _terminal_update(
    state: MultiAgentRunState,
    status: str,
    error: str,
    role: str,
    output_refs: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "error": error,
        "timeline": [_role_event(state, role, status, output_refs=output_refs)],
    }


def _execution_failure(result: dict[str, Any]) -> dict[str, Any]:
    classification = str(result.get("classification", "error"))
    execution_result = ExecutionResult(
        status=str(result.get("status", "failed")),
        classification=classification,
        tool_name=str(result.get("tool_name", "unknown")),
        error=str(result.get("error", classification)),
    )
    return asdict(FailureHandoff().to_spec(execution_result))


def _artifact_refs(result: dict[str, Any]) -> list[str]:
    return [f"artifact:{path}" for path in result.get("artifacts", [])]


def _report_refs(result: dict[str, Any]) -> list[str]:
    return [f"report:{value}" for key, value in result.items() if key.endswith("_path")]


def _failure_refs(failure: dict[str, Any]) -> list[str]:
    classification = failure.get("classification")
    return [f"failure:{classification}"] if classification else []


def _usage_since(
    router: ModelRouter | None, start: int
) -> list[dict[str, Any]]:
    if router is None:
        return []
    return [asdict(record) for record in router.usage()[start:]]


def _is_cancelled(
    state: MultiAgentRunState,
    cancel_check: Callable[[], bool] | None,
) -> bool:
    return bool(state.get("cancelled")) or bool(cancel_check and cancel_check())
