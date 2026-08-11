"""Task-level Chinese report spec (v3.9.x).

A task report covers the full multi-agent loop (plan -> code -> executions)
for one experiment task, not a single run: multiple executions, ablations,
citations, failure cases, aggregate cost and limits.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RunResult:
    run_id: str
    model_type: str
    nmse_db: float | None = None
    parameter_count: int | None = None
    baseline_nmse_db: float | None = None
    psd_path: str | None = None
    target_hit: bool = False
    cost_usd: float | None = None


@dataclass(frozen=True)
class TaskReportSpec:
    task_id: str
    goal: str
    constraints: dict[str, Any] = field(default_factory=dict)
    citations: tuple[str, ...] = ()
    plan: dict[str, Any] = field(default_factory=dict)
    code_changes: tuple[dict[str, Any], ...] = ()
    executions: tuple[RunResult, ...] = ()
    round_records: tuple[dict[str, Any], ...] = ()
    final_evaluation: RunResult | None = None
    ablations: tuple[dict[str, Any], ...] = ()
    failure_cases: tuple[dict[str, Any], ...] = ()
    cost_usd: float | None = None
    trace_refs: tuple[str, ...] = ()
    reproduce_command: str = ""
    limits: str = ""

    def best(self) -> RunResult | None:
        """Best execution: highest NMSE with target hit, else lowest NMSE."""
        hits = [r for r in self.executions if r.target_hit]
        pool = hits or list(self.executions)
        return (
            min(
                pool,
                key=lambda r: (
                    not r.target_hit,
                    r.nmse_db if r.nmse_db is not None else float("inf"),
                ),
            )
            if pool
            else None
        )

    def selected(self) -> RunResult | None:
        """Final evaluation when supplied, otherwise the best search execution."""
        return self.final_evaluation or self.best()


class TaskReportBuilder:
    """Builds a TaskReportSpec from a task-level source dict."""

    def build(self, source: dict[str, Any]) -> TaskReportSpec:
        executions = tuple(
            RunResult(
                run_id=str(item.get("run_id", "")),
                model_type=str(item.get("model_type", "")),
                nmse_db=_to_float(item.get("nmse_db")),
                parameter_count=_to_int(item.get("parameter_count")),
                baseline_nmse_db=_to_float(item.get("baseline_nmse_db")),
                psd_path=str(item["psd_path"]) if item.get("psd_path") else None,
                target_hit=bool(item.get("target_hit", False)),
                cost_usd=_to_float(item.get("cost_usd")),
            )
            for item in source.get("executions", [])
        )
        final_source = source.get("final_evaluation")
        final_evaluation = None
        if isinstance(final_source, dict) and final_source:
            final_evaluation = RunResult(
                run_id=str(final_source.get("run_id", "final-evaluation")),
                model_type=str(final_source.get("model_type", "")),
                nmse_db=_to_float(final_source.get("nmse_db")),
                parameter_count=_to_int(final_source.get("parameter_count")),
                baseline_nmse_db=_to_float(final_source.get("baseline_nmse_db")),
                psd_path=(
                    str(final_source["psd_path"])
                    if final_source.get("psd_path")
                    else None
                ),
                target_hit=bool(final_source.get("target_hit", False)),
                cost_usd=_to_float(final_source.get("cost_usd")),
            )
        return TaskReportSpec(
            task_id=str(source.get("task_id", "unknown")),
            goal=str(source.get("goal", "")),
            constraints=dict(source.get("constraints", {})),
            citations=tuple(str(c) for c in source.get("citations", [])),
            plan=dict(source.get("plan", {})),
            code_changes=tuple(
                dict(c) for c in source.get("code_changes", [])
            ),
            executions=executions,
            round_records=tuple(
                dict(item) for item in source.get("round_records", [])
            ),
            final_evaluation=final_evaluation,
            ablations=tuple(dict(a) for a in source.get("ablations", [])),
            failure_cases=tuple(
                dict(f) for f in source.get("failure_cases", [])
            ),
            cost_usd=_to_float(source.get("cost_usd")),
            trace_refs=tuple(str(r) for r in source.get("trace_refs", [])),
            reproduce_command=str(source.get("reproduce_command", "")),
            limits=str(source.get("limits", "")),
        )


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
