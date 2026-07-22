from __future__ import annotations

from collections import Counter
from copy import deepcopy
from typing import Any


class HistoryCompressor:
    def __init__(self, recent_window: int = 3, max_notable_errors: int = 3):
        if recent_window < 1:
            raise ValueError("recent_window must be >= 1.")
        self.recent_window = recent_window
        self.max_notable_errors = max_notable_errors

    def build_prompt_history(self, history: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if len(history) <= self.recent_window:
            return deepcopy(history)
        older = history[: -self.recent_window]
        recent = history[-self.recent_window :]
        return [summarize_history(older, max_notable_errors=self.max_notable_errors), *deepcopy(recent)]


def summarize_history(history: list[dict[str, Any]], max_notable_errors: int = 3) -> dict[str, Any]:
    status_counts = Counter(str(record.get("run_status", "unknown")) for record in history)
    best = _best_nmse_record(history)
    notable_errors = []
    for record in history:
        error = record.get("error")
        if error:
            notable_errors.append(f"{record.get('id', '')}: {error}")
        if len(notable_errors) >= max_notable_errors:
            break
    summary = {
        "id": "history-summary",
        "run_status": "summary",
        "covered_records": len(history),
        "status_counts": dict(status_counts),
        "best_experiment_id": str(best.get("id", "")) if best else "",
        "best_nmse_db": _to_float(best.get("nmse_db")) if best else None,
        "best_parameter_count": _to_int(best.get("parameter_count")) if best else None,
        "notable_errors": notable_errors,
    }
    summary["context_summary"] = _build_context_summary(summary)
    return summary


def _build_context_summary(summary: dict[str, Any]) -> str:
    return (
        f"Compressed {summary['covered_records']} older records. "
        f"Status counts: {summary['status_counts']}. "
        f"Best: {summary['best_experiment_id']} at {summary['best_nmse_db']} dB. "
        f"Notable errors: {summary['notable_errors']}."
    )


def _best_nmse_record(history: list[dict[str, Any]]) -> dict[str, Any] | None:
    records = [record for record in history if _to_float(record.get("nmse_db")) is not None]
    if not records:
        return None
    return min(records, key=lambda record: _to_float(record.get("nmse_db")) or 0.0)


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
