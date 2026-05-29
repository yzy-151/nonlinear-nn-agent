from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


def collect_diagnostics(workspace: Path | str) -> dict[str, Any]:
    root = Path(workspace)
    benchmark_rows = _collect_benchmark_rows(root)
    run_rows, history_records, reflection_error_counts = _collect_run_rows(root)
    status_counts = Counter(str(record.get("run_status", "unknown")) for record in history_records)
    error_type_counts = Counter(
        str(record.get("error_type"))
        for record in history_records
        if record.get("error_type")
    )
    error_type_counts.update(reflection_error_counts)
    best_candidate = _best_candidate(history_records, benchmark_rows)
    totals = _aggregate_benchmark_totals(benchmark_rows)
    return {
        "benchmark_count": len(benchmark_rows),
        "run_count": len(run_rows),
        "totals": totals,
        "status_counts": dict(status_counts),
        "error_type_counts": dict(error_type_counts),
        "best_candidate": best_candidate,
        "benchmark_rows": benchmark_rows,
        "run_rows": run_rows,
    }


def render_diagnostics_markdown(diagnostics: dict[str, Any]) -> str:
    totals = diagnostics.get("totals", {})
    best = diagnostics.get("best_candidate", {})
    lines = [
        "# Agent Runtime Diagnostics Dashboard",
        "",
        "## Overview",
        "",
        f"- benchmark_runs: `{diagnostics.get('benchmark_count', 0)}`",
        f"- planner_loop_runs: `{diagnostics.get('run_count', 0)}`",
        "",
        "## Aggregate Metrics",
        "",
        "| metric | value |",
        "|---|---:|",
    ]
    for key in (
        "case_count",
        "target_hit_rate",
        "rejected_rate",
        "runtime_failure_rate",
        "average_experiments_used",
        "best_nmse_db",
    ):
        lines.append(f"| {key} | `{totals.get(key, '')}` |")
    lines.extend([
        "",
        "## Best Candidate",
        "",
        "| field | value |",
        "|---|---|",
        f"| id | `{best.get('id', '')}` |",
        f"| nmse_db | `{best.get('nmse_db', '')}` |",
        f"| parameter_count | `{best.get('parameter_count', '')}` |",
        f"| source | `{best.get('source', '')}` |",
        "",
        "## Run Status Distribution",
        "",
        "| status | count |",
        "|---|---:|",
    ])
    for status, count in sorted(diagnostics.get("status_counts", {}).items()):
        lines.append(f"| {status} | {count} |")
    lines.extend([
        "",
        "## Error Type Distribution",
        "",
        "| error_type | count |",
        "|---|---:|",
    ])
    for error_type, count in sorted(diagnostics.get("error_type_counts", {}).items()):
        lines.append(f"| {error_type} | {count} |")
    lines.extend([
        "",
        "## Benchmark Runs",
        "",
        "| source | cases | target_hit_rate | best_nmse_db |",
        "|---|---:|---:|---:|",
    ])
    for row in diagnostics.get("benchmark_rows", []):
        lines.append(
            f"| `{row.get('source', '')}` | {row.get('case_count', '')} | "
            f"{row.get('target_hit_rate', '')} | {row.get('best_nmse_db', '')} |"
        )
    lines.extend([
        "",
        "## Planner Loop Runs",
        "",
        "| source | status | rounds | history_count |",
        "|---|---|---:|---:|",
    ])
    for row in diagnostics.get("run_rows", []):
        lines.append(
            f"| `{row.get('source', '')}` | `{row.get('status', '')}` | "
            f"{row.get('rounds', '')} | {row.get('history_count', '')} |"
        )
    lines.extend([
        "",
        "## 面试解释",
        "",
        "这个 dashboard 的重点不是炫图，而是证明 Agent Harness 的改动可以被评估：target hit rate 说明目标命中能力，rejected/runtime failure rate 说明 guardrail 和 runtime 稳定性，error_type 分布说明失败是否被结构化诊断，best_nmse_db 和参数量说明算法实验结果。",
        "",
    ])
    return "\n".join(lines)


def write_diagnostics_report(workspace: Path | str, output_path: Path | str | None = None) -> Path:
    root = Path(workspace)
    target = Path(output_path) if output_path else root / "docs" / "diagnostics" / "agent-runtime-dashboard.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_diagnostics_markdown(collect_diagnostics(root)), encoding="utf-8")
    return target


def _collect_benchmark_rows(root: Path) -> list[dict[str, Any]]:
    rows = []
    for path in sorted((root / "benchmarks").glob("*/results.json")):
        payload = _read_json(path)
        if not payload:
            continue
        summary = payload.get("summary", {})
        rows.append({
            "source": _relative(path, root),
            "case_count": summary.get("case_count", 0),
            "target_hit_rate": summary.get("target_hit_rate", 0.0),
            "rejected_rate": summary.get("rejected_rate", 0.0),
            "runtime_failure_rate": summary.get("runtime_failure_rate", 0.0),
            "average_experiments_used": summary.get("average_experiments_used", 0.0),
            "best_nmse_db": summary.get("best_nmse_db"),
            "results": payload.get("results", []),
        })
    return rows


def _collect_run_rows(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], Counter]:
    rows = []
    history_records = []
    reflection_error_counts: Counter = Counter()
    for path in sorted((root / "runs").glob("*/result.json")):
        payload = _read_json(path)
        if not payload:
            continue
        history = payload.get("history", [])
        reflections = payload.get("reflections", [])
        history_has_error_types = any(isinstance(record, dict) and record.get("error_type") for record in history)
        if not history_has_error_types:
            for reflection in reflections:
                reflection_error_counts.update(reflection.get("error_type_counts", {}))
        for record in history:
            if isinstance(record, dict):
                record = dict(record)
                record["source"] = _relative(path, root)
                history_records.append(record)
        rows.append({
            "source": _relative(path, root),
            "status": payload.get("status", ""),
            "rounds": payload.get("rounds", ""),
            "history_count": len(history),
        })
    return rows, history_records, reflection_error_counts


def _aggregate_benchmark_totals(rows: list[dict[str, Any]]) -> dict[str, Any]:
    case_count = sum(int(row.get("case_count") or 0) for row in rows)
    if not rows:
        return {
            "case_count": 0,
            "target_hit_rate": 0.0,
            "rejected_rate": 0.0,
            "runtime_failure_rate": 0.0,
            "average_experiments_used": 0.0,
            "best_nmse_db": None,
        }
    return {
        "case_count": case_count,
        "target_hit_rate": _weighted_rate(rows, "target_hit_rate"),
        "rejected_rate": _weighted_rate(rows, "rejected_rate"),
        "runtime_failure_rate": _weighted_rate(rows, "runtime_failure_rate"),
        "average_experiments_used": _mean([row.get("average_experiments_used") for row in rows]),
        "best_nmse_db": min(
            (float(row["best_nmse_db"]) for row in rows if row.get("best_nmse_db") is not None),
            default=None,
        ),
    }


def _best_candidate(history_records: list[dict[str, Any]], benchmark_rows: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = []
    for record in history_records:
        nmse = _to_float(record.get("nmse_db"))
        if nmse is not None:
            candidates.append({
                "id": str(record.get("id", "")),
                "nmse_db": nmse,
                "parameter_count": record.get("parameter_count", ""),
                "source": record.get("source", ""),
            })
    for row in benchmark_rows:
        for result in row.get("results", []):
            nmse = _to_float(result.get("best_nmse_db"))
            if nmse is not None:
                candidates.append({
                    "id": str(result.get("best_experiment_id", "")),
                    "nmse_db": nmse,
                    "parameter_count": result.get("best_parameter_count", ""),
                    "source": row.get("source", ""),
                })
    if not candidates:
        return {"id": "", "nmse_db": None, "parameter_count": "", "source": ""}
    return min(candidates, key=lambda item: item["nmse_db"])


def _weighted_rate(rows: list[dict[str, Any]], field: str) -> float:
    total_cases = sum(int(row.get("case_count") or 0) for row in rows)
    if not total_cases:
        return 0.0
    return sum(float(row.get(field) or 0.0) * int(row.get("case_count") or 0) for row in rows) / total_cases


def _mean(values: list[Any]) -> float:
    numbers = [float(value) for value in values if value is not None]
    return sum(numbers) / len(numbers) if numbers else 0.0


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()
