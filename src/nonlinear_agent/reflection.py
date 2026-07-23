from __future__ import annotations

from collections import Counter
from typing import Any


class ReflectionPolicy:
    def reflect(self, round_index: int, round_records: list[dict[str, Any]]) -> dict[str, Any]:
        status_counts = Counter(str(record.get("run_status", "unknown")) for record in round_records)
        error_type_counts = Counter(
            str(record.get("error_type"))
            for record in round_records
            if record.get("error_type")
        )
        failure_causes = _failure_causes(round_records)
        return {
            "round": round_index,
            "record_count": len(round_records),
            "status_counts": dict(status_counts),
            "error_type_counts": dict(error_type_counts),
            "best_experiment_id": _best_experiment_id(round_records),
            "best_nmse_db": _best_nmse(round_records),
            "failure_causes": failure_causes,
            "recovery_actions": _recovery_actions(failure_causes),
            "avoid_next": _avoid_next(failure_causes),
        }


def _failure_causes(records: list[dict[str, Any]]) -> list[str]:
    causes = []
    for record in records:
        status = record.get("run_status")
        error = str(record.get("error", ""))
        if status == "rejected":
            causes.append(f"Schema/preflight rejection in {record.get('id', '')}: {error}")
        elif status == "failed":
            causes.append(f"Runtime/tool failure in {record.get('id', '')}: {error}")
    return causes


def _recovery_actions(causes: list[str]) -> list[str]:
    actions = []
    text = " ".join(causes).lower()
    if "unsupported" in text or "schema" in text or "preflight" in text:
        actions.append("Remove unsupported fields and keep planner overrides within the declared tool/config schema.")
    if "nmse" in text or "threshold" in text:
        actions.append("Prefer stronger baseline variants or revise the target/feature family after repeated NMSE threshold failures.")
    if "timeout" in text:
        actions.append("Increase the tool timeout only for expensive steps or split the run into smaller resumable steps.")
    if not actions:
        actions.append("Continue with the best observed configuration and explore one controlled variable at a time.")
    return actions


def _avoid_next(causes: list[str]) -> list[str]:
    avoid = []
    text = " ".join(causes).lower()
    if "unsupported" in text or "schema" in text:
        avoid.append("Avoid planner fields not listed in ExperimentConfig or ToolSpec input_schema.")
    if "threshold" in text or "nmse" in text:
        avoid.append("Avoid repeating weak model families without changing feature design or training budget.")
    if not avoid:
        avoid.append("Avoid changing multiple variables at once when the previous round did not isolate a cause.")
    return avoid


def _best_experiment_id(records: list[dict[str, Any]]) -> str:
    best = _best_record(records)
    return str(best.get("id", "")) if best else ""


def _best_nmse(records: list[dict[str, Any]]) -> float | None:
    best = _best_record(records)
    return _to_float(best.get("nmse_db")) if best else None


def _best_record(records: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates = [record for record in records if _to_float(record.get("nmse_db")) is not None]
    if not candidates:
        return None
    return min(candidates, key=lambda record: _to_float(record.get("nmse_db")) or 0.0)


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
