"""Numeric fidelity checker (v3.9.0): report numbers must match source JSON."""

from __future__ import annotations

from typing import Any

from nonlinear_agent.reporting.report_spec import ReportSpec


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
