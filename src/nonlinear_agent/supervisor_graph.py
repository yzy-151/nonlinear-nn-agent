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
ApprovalGate = Callable[[str, str, dict[str, Any]], Any]


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
    round_index: int
    round_records: Annotated[list[dict[str, Any]], operator.add]
    exploration_outcomes: Annotated[list[dict[str, Any]], operator.add]
    available_fact_refs: list[str]
    code_results: list[dict[str, Any]]
    execution_results: list[dict[str, Any]]
    final_evaluation: dict[str, Any]
    planner_context: dict[str, Any]
    plan_failure_facts: dict[str, Any]


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
    rounds: int = 1,
    experiments_per_round: int = 1,
    final_evaluation: bool = False,
    approval_gate: ApprovalGate | None = None,
) -> Any:
    """Build the Idea -> Code -> Execute -> Write supervisor graph.

    Workers receive only their structured handoff. The graph owns routing,
    failure budgets, role events, cancellation and the unique terminal state.
    """
    if max_replans < 0:
        raise ValueError("max_replans must be non-negative")
    if rounds < 1:
        raise ValueError("rounds must be positive")
    if experiments_per_round < 1:
        raise ValueError("experiments_per_round must be positive")
    if rounds > 1 or experiments_per_round > 1 or final_evaluation or approval_gate:
        return _build_batch_multi_agent_graph(
            workers=workers,
            plan_gate=plan_gate,
            model_router=model_router,
            cancel_check=cancel_check,
            rounds=rounds,
            experiments_per_round=experiments_per_round,
            final_evaluation=final_evaluation,
            max_replans=max_replans,
            approval_gate=approval_gate,
        )
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
        planner_context = dict(plan.pop("_planner_context", {}) or {})
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
            "planner_context": planner_context,
            "timeline": [_role_event(
                state,
                "idea_plan",
                "completed",
                input_refs=(
                    _failure_refs(state.get("failure_facts", {}))
                    + list(planner_context.get("allowed_citation_ids", []))
                ),
                output_refs=[f"plan:{plan.get('plan_id', 'unknown')}"],
                model_usage=usage,
                failure_facts=dict(state.get("failure_facts", {})),
                context_evidence=_context_trace_evidence(planner_context),
            )],
        }

    def plan_gate_node(state: MultiAgentRunState) -> dict[str, Any]:
        if _is_cancelled(state, cancel_check):
            return _terminal_update(state, "cancelled", "cancelled by user", "plan_gate")
        context = dict(state.get("planner_context") or {})
        errors = gate.validate(
            state.get("plan", {}),
            available_citation_ids=(
                set(context.get("allowed_citation_ids", []))
                if context.get("enabled")
                else None
            ),
        )
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


def _build_batch_multi_agent_graph(
    workers: MultiAgentWorkers,
    plan_gate: PlanGate | None,
    model_router: ModelRouter | None,
    cancel_check: Callable[[], bool] | None,
    rounds: int,
    experiments_per_round: int,
    final_evaluation: bool,
    max_replans: int,
    approval_gate: ApprovalGate | None,
) -> Any:
    """Build the round-aware batch search graph used by real 3x3 runs."""
    from langgraph.graph import END, START, StateGraph

    gate = plan_gate or PlanGate()

    def idea_plan_node(state: MultiAgentRunState) -> dict[str, Any]:
        if _is_cancelled(state, cancel_check):
            return _terminal_update(state, "cancelled", "cancelled by user", "idea_plan")
        request = {
            "run_id": state["run_id"],
            "goal": state["goal"],
            "round_index": state.get("round_index", 1),
            "rounds_total": rounds,
            "experiments_per_round": experiments_per_round,
            "available_fact_refs": list(state.get("available_fact_refs", [])),
            "round_records": _planner_round_records(
                list(state.get("round_records", []))
            ),
            "plan_failure_facts": dict(state.get("plan_failure_facts", {})),
        }
        usage_start = len(model_router.usage()) if model_router else 0
        try:
            plan = workers.idea_plan(request)
            if not isinstance(plan, dict):
                raise TypeError("idea_plan worker must return an object")
        except Exception as exc:
            return _terminal_update(state, "error", str(exc), "idea_plan")
        usage = _usage_since(model_router, usage_start)
        planner_context = dict(plan.pop("_planner_context", {}) or {})
        review = _review(
            approval_gate,
            "idea_plan",
            "output",
            {
                "goal": state["goal"],
                "round_index": state.get("round_index", 1),
                "reason": plan.get("decision_rationale") or plan.get("risk", ""),
                "risk": plan.get("risk", ""),
                "hypotheses": plan.get("hypotheses", []),
                "plan": plan,
                "historical_best": _historical_best(
                    list(state.get("exploration_outcomes", []))
                ),
            },
        )
        if not review["approved"]:
            return _replan_from_review(state, "idea_plan", review, max_replans)
        if model_router is not None and model_router.budget_exceeded():
            return {
                "status": "budget_exceeded",
                "error": "token/cost budget exceeded",
                "plan": plan,
                "timeline": [_role_event(
                    state, "idea_plan", "budget_exceeded", model_usage=usage
                )],
            }
        return {
            "status": "running",
            "plan": plan,
            "planner_context": planner_context,
            "timeline": [_role_event(
                state,
                "idea_plan",
                "completed",
                input_refs=(
                    list(state.get("available_fact_refs", []))
                    + _failure_refs(state.get("plan_failure_facts", {}))
                    + list(planner_context.get("allowed_citation_ids", []))
                ),
                output_refs=[f"plan:{plan.get('plan_id', 'unknown')}"],
                model_usage=usage,
                context_evidence=_context_trace_evidence(planner_context),
            )],
        }

    def plan_gate_node(state: MultiAgentRunState) -> dict[str, Any]:
        if _is_cancelled(state, cancel_check):
            return _terminal_update(state, "cancelled", "cancelled by user", "plan_gate")
        errors = gate.validate_batch(
            state.get("plan", {}),
            expected_experiments=experiments_per_round,
            round_index=state.get("round_index", 1),
            available_fact_refs=set(state.get("available_fact_refs", [])),
            available_citation_ids=(
                set(dict(state.get("planner_context") or {}).get("allowed_citation_ids", []))
                if dict(state.get("planner_context") or {}).get("enabled")
                else None
            ),
        )
        if errors:
            error = "; ".join(errors)
            failure = {
                "classification": "invalid_plan",
                "error": error,
                "retryable": True,
            }
            if state.get("replan_count", 0) < max_replans:
                return {
                    "status": "replanning",
                    "plan_failure_facts": failure,
                    "replan_count": state.get("replan_count", 0) + 1,
                    "failures": [failure],
                    "timeline": [_role_event(
                        state,
                        "plan_gate",
                        "failed",
                        input_refs=[f"plan:{state['plan'].get('plan_id', 'unknown')}"],
                        output_refs=["failure:invalid_plan"],
                        failure_facts=failure,
                    )],
                }
            return _terminal_update(state, "invalid_plan", error, "plan_gate")
        return {
            "status": "running",
            "plan_failure_facts": {},
            "timeline": [_role_event(
                state,
                "plan_gate",
                "completed",
                input_refs=[f"plan:{state['plan'].get('plan_id', 'unknown')}"],
            )],
        }

    def coding_node(state: MultiAgentRunState) -> dict[str, Any]:
        if _is_cancelled(state, cancel_check):
            return _terminal_update(state, "cancelled", "cancelled by user", "coding")
        results: list[dict[str, Any]] = []
        usage_start = len(model_router.usage()) if model_router else 0
        round_index = state.get("round_index", 1)
        for raw_candidate in state["plan"]["candidate_experiments"]:
            candidate = _scoped_candidate(raw_candidate, round_index)
            experiment_id = str(candidate["experiment_id"])
            try:
                result = workers.coding(
                    {
                        "run_id": state["run_id"],
                        "goal": state["goal"],
                        "round_index": state.get("round_index", 1),
                        "experiment_id": experiment_id,
                        "candidate": dict(candidate),
                        "plan": state["plan"],
                        "prior_facts": _coding_prior_facts(
                            list(state.get("round_records", []))
                        ),
                        "historical_best": _historical_best(
                            list(state.get("exploration_outcomes", []))
                        ),
                    }
                )
                if not isinstance(result, dict):
                    raise TypeError("coding worker must return an object")
            except Exception as exc:
                result = {"passed": False, "status": "failed", "error": str(exc)}
            result = dict(result)
            result["experiment_id"] = experiment_id
            results.append(result)
        usage = _usage_since(model_router, usage_start)
        review = _review(
            approval_gate,
            "coding",
            "output",
            {
                "goal": state["goal"],
                "round_index": round_index,
                "reason": state["plan"].get("decision_rationale", ""),
                "risk": state["plan"].get("risk", ""),
                "candidate_count": len(results),
                "output": [
                    {
                        "experiment_id": item.get("experiment_id"),
                        "passed": item.get("passed"),
                        "candidate_name": item.get("candidate_name"),
                        "failure_facts": item.get("failure_facts", []),
                    }
                    for item in results
                ],
            },
        )
        if not review["approved"]:
            return _replan_from_review(state, "coding", review, max_replans)
        return {
            "status": "running",
            "code_results": results,
            "code_result": results[0] if results else {},
            "timeline": [_role_event(
                state,
                "coding",
                "completed",
                input_refs=[f"plan:{state['plan'].get('plan_id', 'unknown')}"],
                output_refs=[f"code:{item['experiment_id']}" for item in results],
                model_usage=usage,
            )],
        }

    def execution_node(state: MultiAgentRunState) -> dict[str, Any]:
        if _is_cancelled(state, cancel_check):
            return _terminal_update(state, "cancelled", "cancelled by user", "execution")
        round_index = state.get("round_index", 1)
        review = _review(
            approval_gate,
            "execution",
            "input",
            {
                "goal": state["goal"],
                "round_index": round_index,
                "reason": state["plan"].get("decision_rationale", ""),
                "risk": state["plan"].get("risk", ""),
                "hypotheses": state["plan"].get("hypotheses", []),
                "candidates": state["plan"].get("candidate_experiments", []),
                "historical_best": _historical_best(
                    list(state.get("exploration_outcomes", []))
                ),
            },
        )
        if not review["approved"]:
            return _replan_from_review(state, "execution", review, max_replans)
        outcomes: list[dict[str, Any]] = []
        executions: list[dict[str, Any]] = []
        code_by_id = {
            str(item.get("experiment_id")): item
            for item in state.get("code_results", [])
        }
        for raw_candidate in state["plan"]["candidate_experiments"]:
            candidate = _scoped_candidate(raw_candidate, round_index)
            experiment_id = str(candidate["experiment_id"])
            code_result = dict(code_by_id.get(experiment_id, {}))
            if not code_result.get("passed", False):
                coding_facts = [
                    str(item) for item in code_result.get("failure_facts", [])
                ]
                result = {
                    "status": "failed",
                    "classification": "coding_error",
                    "error": "; ".join(coding_facts)
                    or str(code_result.get("error") or "coding gate failed"),
                    "metrics": {},
                    "artifacts": [],
                }
            else:
                try:
                    result = workers.execution(
                        {
                            "run_id": state["run_id"],
                            "goal": state["goal"],
                            "round_index": round_index,
                            "experiment_id": experiment_id,
                            "evaluation_kind": "search",
                            "candidate": dict(candidate),
                            "plan": state["plan"],
                            "code_result": code_result,
                            "hypotheses": list(state["plan"].get("hypotheses", [])),
                            "historical_best": _historical_best(
                                list(state.get("exploration_outcomes", []))
                            ),
                        }
                    )
                    if not isinstance(result, dict):
                        raise TypeError("execution worker must return an object")
                except Exception as exc:
                    result = {
                        "status": "failed",
                        "classification": "error",
                        "error": str(exc),
                        "metrics": {},
                        "artifacts": [],
                    }
            result = dict(result)
            result["experiment_id"] = experiment_id
            result["evaluation_kind"] = "search"
            executions.append(result)
            failure_facts = []
            if result.get("status") != "completed":
                failure_facts.append(
                    str(result.get("error") or result.get("classification") or "failed")
                )
            outcomes.append(
                {
                    "experiment_id": experiment_id,
                    "candidate_name": str(candidate.get("model_type", "unknown")),
                    "candidate": dict(candidate),
                    "code_result": code_result,
                    "status": str(result.get("status", "failed")),
                    "metrics": dict(result.get("metrics") or {}),
                    "artifacts": list(result.get("artifacts") or []),
                    "failure_facts": failure_facts,
                    "evaluation_kind": "search",
                    "execution_result": result,
                }
            )

        fact_refs = [
            f"fact:round-{round_index}:{item['experiment_id']}:{item['status']}"
            for item in outcomes
        ]
        best = _select_best_outcome(outcomes)
        if best is not None:
            fact_refs.append(f"fact:round-{round_index}:best:{best['experiment_id']}")
        record = {
            "round_index": round_index,
            "incoming_fact_refs": list(
                {
                    str(ref)
                    for candidate in state["plan"]["candidate_experiments"]
                    for ref in candidate.get("based_on_fact_refs", [])
                }
            ),
            "hypothesis": "; ".join(
                str(item.get("hypothesis", ""))
                for item in state["plan"].get("hypotheses", [])
                if item.get("hypothesis")
            ),
            "decision_rationale": str(
                state["plan"].get("decision_rationale")
                or state["plan"].get("risk", "")
            ),
            "experiment_ids": [item["experiment_id"] for item in outcomes],
            "outcomes": outcomes,
            "extracted_facts": fact_refs,
            "next_round_intent": (
                "Use these verified facts to revise the next causal design."
                if round_index < rounds
                else "Select the global best candidate for final evaluation."
            ),
        }
        has_next_round = round_index < rounds
        return {
            "status": "next_round" if has_next_round else "running",
            "round_index": round_index + 1 if has_next_round else round_index,
            "round_records": [record],
            "exploration_outcomes": outcomes,
            "available_fact_refs": list(state.get("available_fact_refs", [])) + fact_refs,
            "execution_results": executions,
            "execution_result": executions[0] if executions else {},
            "timeline": [_role_event(
                state,
                "execution",
                "completed",
                output_refs=fact_refs,
                failure_facts={
                    "failed_count": sum(item["status"] != "completed" for item in outcomes)
                },
            )],
        }

    def final_evaluation_node(state: MultiAgentRunState) -> dict[str, Any]:
        best = _select_best_outcome(list(state.get("exploration_outcomes", [])))
        if best is None:
            result = {
                "status": "failed",
                "classification": "no_valid_candidate",
                "error": "no successful exploration candidate",
                "evaluation_kind": "final",
            }
        else:
            try:
                result = workers.execution(
                    {
                        "run_id": state["run_id"],
                        "goal": state["goal"],
                        "round_index": rounds,
                        "experiment_id": f"{best['experiment_id']}-final",
                        "source_experiment_id": best["experiment_id"],
                        "evaluation_kind": "final",
                        "candidate": dict(best["candidate"]),
                        "plan": state["plan"],
                        "code_result": dict(best["code_result"]),
                        "hypotheses": list(state["plan"].get("hypotheses", [])),
                        "historical_best": _historical_best(
                            list(state.get("exploration_outcomes", []))
                        ),
                    }
                )
                if not isinstance(result, dict):
                    raise TypeError("execution worker must return an object")
            except Exception as exc:
                result = {
                    "status": "failed",
                    "classification": "error",
                    "error": str(exc),
                }
            result = dict(result)
            result.update(
                {
                    "evaluation_kind": "final",
                    "source_experiment_id": best["experiment_id"],
                    "candidate": dict(best["candidate"]),
                    "code_result": dict(best["code_result"]),
                }
            )
        return {
            "status": "running",
            "final_evaluation": result,
            "timeline": [_role_event(
                state,
                "final_evaluation",
                str(result.get("status", "failed")),
                input_refs=(
                    [f"experiment:{result['source_experiment_id']}"]
                    if result.get("source_experiment_id")
                    else []
                ),
                output_refs=_artifact_refs(result),
            )],
        }

    def writing_node(state: MultiAgentRunState) -> dict[str, Any]:
        request = {
            "run_id": state["run_id"],
            "goal": state["goal"],
            "plan": state["plan"],
            "round_records": list(state.get("round_records", [])),
            "exploration_outcomes": list(state.get("exploration_outcomes", [])),
            "final_evaluation": dict(state.get("final_evaluation", {})),
            "failures": list(state.get("failures", [])),
            "historical_best": _historical_best(
                list(state.get("exploration_outcomes", []))
            ),
            "usage_summary": _usage_summary(model_router),
        }
        usage_start = len(model_router.usage()) if model_router else 0
        try:
            result = workers.writing(request)
            if not isinstance(result, dict):
                raise TypeError("writing worker must return an object")
        except Exception as exc:
            return _terminal_update(state, "error", str(exc), "writing")
        review = _review(
            approval_gate,
            "writing",
            "output",
            {
                "goal": state["goal"],
                "reason": "Verify report evidence, attribution, cost and downloadable artifacts.",
                "risk": "The report must not claim unsupported model performance.",
                "metrics": request.get("historical_best", {}).get("metrics", {}),
                "usage_summary": request.get("usage_summary", {}),
                "output": result,
                "artifacts": _report_refs(result),
            },
        )
        if not review["approved"]:
            return _replan_from_review(state, "writing", review, max_replans)
        return {
            "status": "completed",
            "report_result": result,
            "timeline": [_role_event(
                state,
                "writing",
                "completed",
                output_refs=_report_refs(result),
                model_usage=_usage_since(model_router, usage_start),
            )],
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
            "timeline": [_role_event(
                state,
                "terminal",
                terminal["status"],
                output_refs=_report_refs(state.get("report_result", {})),
            )],
        }

    graph = StateGraph(MultiAgentRunState)
    graph.add_node("idea_plan", idea_plan_node)
    graph.add_node("plan_gate", plan_gate_node)
    graph.add_node("coding", coding_node)
    graph.add_node("execution", execution_node)
    graph.add_node("final_evaluation", final_evaluation_node)
    graph.add_node("writing", writing_node)
    graph.add_node("terminal", terminal_node)
    graph.add_edge(START, "idea_plan")
    graph.add_conditional_edges(
        "idea_plan",
        lambda state: (
            "plan_gate" if state.get("status") == "running"
            else "idea_plan" if state.get("status") == "replanning"
            else "terminal"
        ),
    )
    graph.add_conditional_edges(
        "plan_gate",
        lambda state: (
            "coding" if state.get("status") == "running"
            else "idea_plan" if state.get("status") == "replanning"
            else "terminal"
        ),
    )
    graph.add_conditional_edges(
        "coding",
        lambda state: "execution" if state.get("status") == "running" else "idea_plan",
    )
    graph.add_conditional_edges(
        "execution",
        lambda state: (
            "idea_plan"
            if state.get("status") in {"next_round", "replanning"}
            else "final_evaluation" if final_evaluation else "writing"
        ),
    )
    graph.add_edge("final_evaluation", "writing")
    graph.add_conditional_edges(
        "writing",
        lambda state: "terminal" if state.get("status") == "completed" else "idea_plan",
    )
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
            "round_index": 1,
            "round_records": [],
            "exploration_outcomes": [],
            "available_fact_refs": [],
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
    context_evidence: list[dict[str, Any]] | None = None,
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
        "context_evidence": list(context_evidence or []),
    }


def _context_trace_evidence(
    planner_context: dict[str, Any],
) -> list[dict[str, Any]]:
    """Project retrieval provenance without prompt text into public trace."""
    allowed = {
        "evidence_id",
        "kind",
        "citation",
        "source_path",
        "content_hash",
        "version",
        "score",
        "memory_kind",
        "run_id",
        "config_hash",
        "confidence",
        "evidence_refs",
        "metrics",
        "known_nmse_db",
        "parameter_count",
        "config",
    }
    return [
        {key: value for key, value in item.items() if key in allowed}
        for item in planner_context.get("evidence", [])
        if isinstance(item, dict)
    ]


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


def _select_best_outcome(
    outcomes: list[dict[str, Any]],
) -> dict[str, Any] | None:
    valid = [
        item
        for item in outcomes
        if item.get("status") == "completed"
        and isinstance(dict(item.get("metrics") or {}).get("nmse_db"), (int, float))
    ]
    return min(
        valid,
        key=lambda item: float(dict(item.get("metrics") or {})["nmse_db"]),
    ) if valid else None


def _planner_round_records(
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Expose verified observations to planning without code/runtime payloads."""
    summaries: list[dict[str, Any]] = []
    for record in records:
        outcomes = [
            {
                "experiment_id": str(outcome.get("experiment_id", "")),
                "candidate_name": str(outcome.get("candidate_name", "")),
                "status": str(outcome.get("status", "")),
                "metrics": dict(outcome.get("metrics") or {}),
                "failure_facts": list(outcome.get("failure_facts", [])),
            }
            for outcome in record.get("outcomes", [])
            if isinstance(outcome, dict)
        ]
        summaries.append(
            {
                "round_index": record.get("round_index"),
                "incoming_fact_refs": list(record.get("incoming_fact_refs", [])),
                "hypothesis": str(record.get("hypothesis", "")),
                "decision_rationale": str(record.get("decision_rationale", "")),
                "outcomes": outcomes,
                "extracted_facts": list(record.get("extracted_facts", [])),
                "next_round_intent": str(record.get("next_round_intent", "")),
            }
        )
    return summaries


def _coding_prior_facts(
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Flatten prior outcomes into the bounded facts needed to repair code."""
    return [
        {
            "round_index": record.get("round_index"),
            "experiment_id": str(outcome.get("experiment_id", "")),
            "candidate_name": str(outcome.get("candidate_name", "")),
            "status": str(outcome.get("status", "")),
            "metrics": dict(outcome.get("metrics") or {}),
            "config": dict(dict(outcome.get("candidate") or {}).get("config") or {}),
            "failure_facts": list(outcome.get("failure_facts", [])),
        }
        for record in records
        for outcome in record.get("outcomes", [])
        if isinstance(outcome, dict)
    ]


def _historical_best(outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    best = _select_best_outcome(outcomes)
    if best is None:
        return {}
    return {
        "experiment_id": str(best.get("experiment_id", "")),
        "model_type": str(best.get("candidate_name", "")),
        "config": dict(dict(best.get("candidate") or {}).get("config") or {}),
        "metrics": dict(best.get("metrics") or {}),
    }


def _usage_summary(router: ModelRouter | None) -> dict[str, Any]:
    records = router.usage() if router is not None else []
    return {
        "calls": len(records),
        "prompt_tokens": sum(item.prompt_tokens for item in records),
        "completion_tokens": sum(item.completion_tokens for item in records),
        "cost_usd": sum(item.cost_usd for item in records),
        "latency_ms": sum(item.latency_ms for item in records),
    }


def _review(
    gate: ApprovalGate | None,
    role: str,
    phase: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if gate is None:
        return {"approved": True, "reason": "auto mode"}
    raw = gate(role, phase, payload)
    if isinstance(raw, dict):
        return {
            "approved": bool(raw.get("approved")),
            "reason": str(raw.get("reason") or ""),
            "approval_id": str(raw.get("approval_id") or ""),
        }
    return {
        "approved": bool(getattr(raw, "approved", False)),
        "reason": str(getattr(raw, "reason", "")),
        "approval_id": str(getattr(raw, "approval_id", "")),
    }


def _replan_from_review(
    state: MultiAgentRunState,
    role: str,
    review: dict[str, Any],
    max_replans: int,
) -> dict[str, Any]:
    reason = review.get("reason") or f"human rejected {role} output"
    failure = {
        "classification": "human_rejected",
        "error": str(reason),
        "retryable": True,
        "role": role,
        "approval_id": review.get("approval_id", ""),
    }
    if state.get("replan_count", 0) >= max_replans:
        return _terminal_update(state, "error", str(reason), role)
    return {
        "status": "replanning",
        "plan_failure_facts": failure,
        "replan_count": state.get("replan_count", 0) + 1,
        "failures": [failure],
        "timeline": [_role_event(
            state,
            role,
            "rejected",
            output_refs=["failure:human_rejected"],
            failure_facts=failure,
        )],
    }


def _scoped_candidate(
    candidate: dict[str, Any], round_index: int
) -> dict[str, Any]:
    scoped = dict(candidate)
    experiment_id = str(scoped.get("experiment_id", "candidate")).strip()
    prefix = f"r{round_index}-"
    if not experiment_id.startswith(prefix):
        experiment_id = f"{prefix}{experiment_id}"
    scoped["experiment_id"] = experiment_id
    return scoped


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
