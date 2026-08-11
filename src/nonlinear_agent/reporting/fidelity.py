"""Numeric fidelity checker (v3.9.0): report numbers must match source JSON."""

from __future__ import annotations

from typing import Any

from nonlinear_agent.reporting.report_spec import ReportSpec
from nonlinear_agent.reporting.task_report_spec import TaskReportSpec


_NUMERIC_FIELDS = (
    ("baseline_nmse_db", "baseline_nmse_db"),
    ("current_nmse_db", "nmse_db"),
    ("parameter_count", "parameter_count"),
    ("cost_usd", "cost_usd"),
)
_TOLERANCE = 1e-6


class FidelityChecker:
    """Returns a list of numeric mismatches; empty means the report is faithful."""

    def check(
        self, spec: ReportSpec, source: dict[str, Any]
    ) -> list[str]:
        mismatches: list[str] = []
        for spec_field, source_key in _NUMERIC_FIELDS:
            spec_value = getattr(spec, spec_field)
            source_value = _to_number(source.get(source_key))
            if spec_value is None and source_value is None:
                continue
            if spec_value is None or source_value is None:
                mismatches.append(
                    f"{spec_field}: report={spec_value} source={source_value}"
                )
                continue
            if abs(float(spec_value) - float(source_value)) > _TOLERANCE:
                mismatches.append(
                    f"{spec_field}: report={spec_value} source={source_value}"
                )
        return mismatches


def _to_number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class TaskFidelityChecker:
    """Verifies every run number in a TaskReportSpec against the source."""

    _TOLERANCE = 1e-6

    def check(
        self, spec: TaskReportSpec, source: dict[str, Any]
    ) -> list[str]:
        mismatches: list[str] = []
        source_runs = {
            str(item.get("run_id")): item
            for item in source.get("executions", [])
        }
        for run in spec.executions:
            src = source_runs.get(run.run_id)
            if src is None:
                mismatches.append(f"run {run.run_id}: missing in source")
                continue
            for field, key in (
                ("nmse_db", "nmse_db"),
                ("parameter_count", "parameter_count"),
                ("baseline_nmse_db", "baseline_nmse_db"),
                ("cost_usd", "cost_usd"),
            ):
                report_value = getattr(run, field)
                source_value = _to_number(src.get(key))
                if report_value is None and source_value is None:
                    continue
                if report_value is None or source_value is None:
                    mismatches.append(
                        f"{run.run_id}.{field}: report={report_value} source={source_value}"
                    )
                    continue
                if abs(float(report_value) - float(source_value)) > self._TOLERANCE:
                    mismatches.append(
                        f"{run.run_id}.{field}: report={report_value} source={source_value}"
                    )
        if spec.cost_usd is not None or source.get("cost_usd") is not None:
            if abs(
                float(spec.cost_usd or 0.0) - float(source.get("cost_usd") or 0.0)
            ) > self._TOLERANCE:
                mismatches.append(
                    f"cost_usd: report={spec.cost_usd} source={source.get('cost_usd')}"
                )
        return mismatches
