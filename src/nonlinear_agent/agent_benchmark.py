"""Outcome-based scoring for independent action-level agent tasks."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Awaitable, Callable

from nonlinear_agent.action_loop import ActionLoopResult
from nonlinear_agent.agent_benchmark_cases import AgentTaskCase


@dataclass(frozen=True)
class AgentTaskScore:
    case_id: str
    passed: bool
    passed_checks: tuple[str, ...]
    failed_checks: tuple[str, ...]


def score_agent_task(
    case: AgentTaskCase, result: ActionLoopResult
) -> AgentTaskScore:
    checks: dict[str, bool] = {}
    history = result.history
    tools = [
        str(record.get("tool_name"))
        for record in history
        if record.get("tool_name")
        and record.get("run_status") != "rejected"
    ]

    checks["terminal_status"] = result.status in case.expected_statuses
    checks["action_budget"] = len(history) <= case.max_actions
    checks["required_tools"] = all(tool in tools for tool in case.required_tools)
    checks["forbidden_tools"] = not any(tool in tools for tool in case.forbidden_tools)
    if case.require_tool_order:
        checks["tool_order"] = _is_subsequence(case.required_tools, tools)
    if case.require_rejection:
        checks["guard_rejection"] = any(
            record.get("run_status") == "rejected" for record in history
        )
    if case.require_causal_recovery:
        checks["causal_recovery"] = _has_causal_recovery(history)
    if case.required_metric:
        checks["required_metric"] = case.required_metric in result.metrics
    if case.required_artifact_suffix:
        checks["required_artifact"] = any(
            str(artifact).endswith(case.required_artifact_suffix)
            for artifact in result.artifacts
        )

    passed_checks = tuple(name for name, passed in checks.items() if passed)
    failed_checks = tuple(name for name, passed in checks.items() if not passed)
    return AgentTaskScore(
        case_id=case.case_id,
        passed=not failed_checks,
        passed_checks=passed_checks,
        failed_checks=failed_checks,
    )


AgentTaskExecutor = Callable[[AgentTaskCase], Awaitable[ActionLoopResult]]


async def run_agent_task_benchmark(
    cases: list[AgentTaskCase],
    execute_case: AgentTaskExecutor,
    attempts: int = 1,
) -> dict[str, Any]:
    if attempts < 1:
        raise ValueError("attempts must be at least 1")

    rows: list[dict[str, Any]] = []
    pass_at_1_count = 0
    pass_at_k_count = 0
    for case in cases:
        scores = []
        for attempt_index in range(1, attempts + 1):
            result = await execute_case(case)
            score = score_agent_task(case, result)
            scores.append(score)
            rows.append({
                "case_id": case.case_id,
                "attempt": attempt_index,
                **asdict(score),
                "status": result.status,
                "planner_call_count": result.planner_call_count,
                "history": result.history,
                "metrics": result.metrics,
                "artifacts": result.artifacts,
                "total_prompt_tokens": result.total_prompt_tokens,
                "total_completion_tokens": result.total_completion_tokens,
            })
        if scores[0].passed:
            pass_at_1_count += 1
        if any(score.passed for score in scores):
            pass_at_k_count += 1

    task_count = len(cases)
    return {
        "domain": "nonlinear-modeling",
        "task_count": task_count,
        "attempt_count": task_count * attempts,
        "pass_at_1": pass_at_1_count / task_count if task_count else 0.0,
        f"pass_at_{attempts}": (
            pass_at_k_count / task_count if task_count else 0.0
        ),
        "results": rows,
    }


def _is_subsequence(expected: tuple[str, ...], actual: list[str]) -> bool:
    position = 0
    for item in actual:
        if position < len(expected) and item == expected[position]:
            position += 1
    return position == len(expected)


def _has_causal_recovery(history: list[dict[str, Any]]) -> bool:
    failures = {
        str(record.get("event_id")): record
        for record in history
        if record.get("run_status") in {"failed", "rejected"}
        and record.get("event_id")
    }
    for record in history:
        if record.get("run_status") != "succeeded":
            continue
        caused_by = record.get("caused_by_event_ids", [])
        if not isinstance(caused_by, list):
            continue
        for event_id in caused_by:
            source = failures.get(str(event_id))
            if source is None:
                continue
            if source.get("planner_call_id") != record.get("planner_call_id"):
                return True
    return False
