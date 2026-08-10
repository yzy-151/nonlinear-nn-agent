"""ReportSpec — structured, source-backed experiment report (v3.9.0)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ReportSpec:
    run_id: str
    goal: str
    baseline_nmse_db: float | None = None
    current_nmse_db: float | None = None
    parameter_count: int | None = None
    cost_usd: float | None = None
    psd_path: str | None = None
    trace_refs: tuple[str, ...] = ()
    reproduce_command: str = ""
    best_table: tuple[dict[str, Any], ...] = ()
    failure_cases: tuple[dict[str, Any], ...] = ()


class ReportSpecBuilder:
    """Builds a ReportSpec from a structured source dict (results/metrics JSON)."""

    def build(self, source: dict[str, Any]) -> ReportSpec:
        return ReportSpec(
            run_id=str(source.get("run_id", "unknown")),
            goal=str(source.get("goal", "")),
            baseline_nmse_db=_to_float(source.get("baseline_nmse_db")),
            current_nmse_db=_to_float(source.get("nmse_db")),
            parameter_count=_to_int(source.get("parameter_count")),
            cost_usd=_to_float(source.get("cost_usd")),
            psd_path=str(source["psd_path"]) if source.get("psd_path") else None,
            trace_refs=tuple(str(ref) for ref in source.get("trace_refs", [])),
            reproduce_command=str(source.get("reproduce_command", "")),
            best_table=tuple(
                dict(candidate) for candidate in source.get("best_candidates", [])
            ),
            failure_cases=tuple(
                dict(case) for case in source.get("failure_cases", [])
            ),
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
