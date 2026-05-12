from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

from nonlinear_agent.loop import PlannerLoopResult


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    goal: str
    constraints: dict[str, Any] = field(default_factory=dict)
    max_rounds: int = 3
    max_experiments: int | None = None
    target_nmse_db: float | None = None


@dataclass
class BenchmarkCaseResult:
    case_id: str
    status: str = ""
    rounds: int = 0
    history_count: int = 0
    best_experiment_id: str = ""
    best_nmse_db: float | None = None
    best_parameter_count: int | None = None
    target_hit: bool = False
    rejected_count: int = 0
    failed_count: int = 0
    succeeded_count: int = 0
    experiments_used: int = 0


BenchmarkExecutor = Callable[[BenchmarkCase], Awaitable[PlannerLoopResult]]


async def run_benchmark_cases(
    cases: list[BenchmarkCase],
    execute_case: BenchmarkExecutor,
) -> tuple[list[BenchmarkCaseResult], dict[str, Any]]:
    results = []
    for case in cases:
        loop_result = await execute_case(case)
        results.append(summarize_loop_result(case, loop_result))
    return results, build_benchmark_summary(results)


def summarize_loop_result(case: BenchmarkCase, loop_result: PlannerLoopResult) -> BenchmarkCaseResult:
    history = loop_result.history
    best = _best_nmse_record(history)
    rejected_count = _count_status(history, "rejected")
    failed_count = _count_status(history, "failed")
    succeeded_count = _count_status(history, "succeeded")
    best_nmse = _to_float(best.get("nmse_db")) if best else None
    target_hit = bool(
        case.target_nmse_db is not None
        and best_nmse is not None
        and best_nmse <= case.target_nmse_db
    )
    return BenchmarkCaseResult(
        case_id=case.case_id,
        status=loop_result.status,
        rounds=loop_result.rounds,
        history_count=len(history),
        best_experiment_id=str(best.get("id", "")) if best else "",
        best_nmse_db=best_nmse,
        best_parameter_count=_to_int(best.get("parameter_count")) if best else None,
        target_hit=target_hit,
        rejected_count=rejected_count,
        failed_count=failed_count,
        succeeded_count=succeeded_count,
        experiments_used=failed_count + succeeded_count,
    )


def build_benchmark_summary(results: list[BenchmarkCaseResult]) -> dict[str, Any]:
    case_count = len(results)
    total_records = sum(result.rejected_count + result.failed_count + result.succeeded_count for result in results)
    total_experiments = sum(result.experiments_used for result in results)
    return {
        "case_count": case_count,
        "target_hit_rate": _rate(sum(1 for result in results if result.target_hit), case_count),
        "rejected_rate": _rate(sum(result.rejected_count for result in results), total_records),
        "runtime_failure_rate": _rate(sum(result.failed_count for result in results), total_records),
        "average_experiments_used": (total_experiments / case_count) if case_count else 0.0,
        "best_nmse_db": min(
            (result.best_nmse_db for result in results if result.best_nmse_db is not None),
            default=None,
        ),
    }


def write_benchmark_artifacts(
    output_dir: Path | str,
    results: list[BenchmarkCaseResult],
    summary: dict[str, Any],
) -> None:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    result_rows = [asdict(result) for result in results]
    (output / "results.json").write_text(
        json.dumps({"summary": summary, "results": result_rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_leaderboard(output / "leaderboard.csv", results)
    _write_summary(output / "summary.md", summary, results)


def _write_leaderboard(path: Path, results: list[BenchmarkCaseResult]) -> None:
    columns = [
        "case_id",
        "target_hit",
        "best_nmse_db",
        "best_experiment_id",
        "best_parameter_count",
        "status",
        "rounds",
        "experiments_used",
        "rejected_count",
        "failed_count",
        "succeeded_count",
    ]
    sorted_results = sorted(results, key=lambda result: (result.best_nmse_db is None, result.best_nmse_db or 0.0))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for result in sorted_results:
            row = asdict(result)
            writer.writerow({column: row.get(column, "") for column in columns})


def _write_summary(path: Path, summary: dict[str, Any], results: list[BenchmarkCaseResult]) -> None:
    lines = [
        "# Agent Benchmark Summary",
        "",
        f"- case_count: `{summary['case_count']}`",
        f"- target_hit_rate: `{summary['target_hit_rate']}`",
        f"- rejected_rate: `{summary['rejected_rate']}`",
        f"- runtime_failure_rate: `{summary['runtime_failure_rate']}`",
        f"- average_experiments_used: `{summary['average_experiments_used']}`",
        f"- best_nmse_db: `{summary['best_nmse_db']}`",
        "",
        "## Cases",
        "",
    ]
    for result in results:
        lines.append(
            f"- `{result.case_id}`: hit={result.target_hit}, best_nmse={result.best_nmse_db}, "
            f"rejected={result.rejected_count}, failed={result.failed_count}, succeeded={result.succeeded_count}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _best_nmse_record(history: list[dict[str, Any]]) -> dict[str, Any] | None:
    records = [record for record in history if _to_float(record.get("nmse_db")) is not None]
    if not records:
        return None
    return min(records, key=lambda record: _to_float(record.get("nmse_db")) or 0.0)


def _count_status(history: list[dict[str, Any]], status: str) -> int:
    return sum(1 for record in history if record.get("run_status") == status)


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


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
