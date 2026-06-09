"""
Agent Runtime 诊断数据收集 ============================================

负责从磁盘上捞所有实验产物，聚合统计后喂给 Dashboard（HTML 和 Markdown 两种格式）。

数据来源（两个目录）：
  benchmarks/*/results.json  — Benchmark 的逐 case 结果
  runs/*/result.json         — Planner Loop 的逐轮结果

输出（两种格式）：
  Markdown dashboard  — docs/diagnostics/agent-runtime-dashboard.md
  HTML dashboard      — docs/diagnostics/agent-runtime-dashboard.html (由 dashboard.py 渲染)

面试要点：
  这个模块不是看一次实验的成败，而是看所有实验的"整体健康度"——
  改了 prompt / guard / runtime 之后，跑一堆实验，来 Dashboard 看指标有没有退化。
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


# ============================================================
# collect_diagnostics — 主入口，收集全部诊断数据
# ============================================================
def collect_diagnostics(workspace: Path | str) -> dict[str, Any]:
    """扫描整个项目目录，聚合所有实验数据。

    返回字典包含：
      benchmark_count  — 有多少份 benchmark 报告
      run_count        — 有多少份 planner loop 结果
      totals           — 聚合指标（target_hit_rate 等）
      status_counts    — 状态分布（succeeded / failed / rejected 各多少）
      error_type_counts — 错误类型分布（timeout / tool_error / metric_threshold 等）
      best_candidate   — 全局最优的实验候选
      benchmark_rows   — 每份 benchmark 的详细数据
      run_rows         — 每次 planner loop 的详细数据
    """
    root = Path(workspace)

    # 收集 benchmark 和 planner loop 的原始数据
    benchmark_rows = _collect_benchmark_rows(root)
    run_rows, history_records, reflection_error_counts = _collect_run_rows(root)

    # 统计状态分布
    status_counts = Counter(
        str(record.get("run_status", "unknown")) for record in history_records
    )

    # 统计错误类型分布
    error_type_counts = Counter(
        str(record.get("error_type"))
        for record in history_records
        if record.get("error_type")
    )
    # 补充 reflection 里的错误类型（那些没有被记录在 history error_type 里的）
    error_type_counts.update(reflection_error_counts)

    # 找全局最优候选
    best_candidate = _best_candidate(history_records, benchmark_rows)

    # 汇总指标（分两个来源）
    totals = _aggregate_all_totals(benchmark_rows, run_rows, history_records)
    benchmark_totals = _aggregate_benchmark_only(benchmark_rows)
    run_totals = _aggregate_run_only(run_rows, history_records)

    return {
        "benchmark_count": len(benchmark_rows),
        "run_count": len(run_rows),
        "totals": totals,
        "benchmark_totals": benchmark_totals,
        "run_totals": run_totals,
        "status_counts": dict(status_counts),
        "error_type_counts": dict(error_type_counts),
        "best_candidate": best_candidate,
        "benchmark_rows": benchmark_rows,
        "run_rows": run_rows,
    }


# ============================================================
# render_diagnostics_markdown — 生成 Markdown 报告
# ============================================================
def render_diagnostics_markdown(diagnostics: dict[str, Any]) -> str:
    """把诊断数据渲染为 GitHub 友好的 Markdown 格式。

    结构：
      - Overview（概览数字）
      - Aggregate Metrics（聚合指标表格）
      - Best Candidate（最佳候选详情）
      - Run Status Distribution（状态分布表）
      - Error Type Distribution（错误类型分布表）
      - Benchmark Runs（逐 benchmark 表格）
      - Planner Loop Runs（逐 run 表格）
      - 面试解释（一段中文注解）
    """
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
        "这个 dashboard 的重点不是炫图，而是证明 Agent Harness 的改动可以被评估："
        "target hit rate 说明目标命中能力，rejected/runtime failure rate 说明 "
        "guardrail 和 runtime 稳定性，error_type 分布说明失败是否被结构化诊断，"
        "best_nmse_db 和参数量说明算法实验结果。",
        "",
    ])

    return "\n".join(lines)


# ============================================================
# write_diagnostics_report — 落盘 Markdown 诊断报告
# ============================================================
def write_diagnostics_report(
    workspace: Path | str, output_path: Path | str | None = None
) -> Path:
    """收集诊断数据并写入 Markdown 文件。"""
    root = Path(workspace)
    target = (
        Path(output_path)
        if output_path
        else root / "docs" / "diagnostics" / "agent-runtime-dashboard.md"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        render_diagnostics_markdown(collect_diagnostics(root)), encoding="utf-8"
    )
    return target


# ============================================================
# 数据收集函数
# ============================================================

def _collect_benchmark_rows(root: Path) -> list[dict[str, Any]]:
    """扫描 benchmarks/*/results.json，提取每份 benchmark 的关键指标。

    每个 results.json 由 write_benchmark_artifacts() 写入，
    包含 summary（汇总）和 results（逐 case 详情）两部分。
    """
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
            "results": payload.get("results", []),  # 保留原始逐 case 结果
        })
    return rows


def _collect_run_rows(root: Path) -> tuple[
    list[dict[str, Any]], list[dict[str, Any]], Counter
]:
    """扫描 runs/*/result.json，提取每次 planner loop 的结果。

    返回三个值：
      rows                    — 每次 run 的摘要行
      history_records         — 所有实验记录的扁平列表（跨所有 run）
      reflection_error_counts — reflection 里的 error_type 统计

    按文件修改时间倒序排列（最新的在最前）。
    对于 history 里没有 error_type 字段的记录，
    从 reflection 中补充 error_type_counts。
    """
    rows = []
    history_records = []
    reflection_error_counts: Counter = Counter()

    # 按文件修改时间倒序，最新的 run 排前面
    for path in sorted(
        (root / "runs").glob("*/result.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    ):
        payload = _read_json(path)
        if not payload:
            continue

        history = payload.get("history", [])
        reflections = payload.get("reflections", [])

        # 如果 history 记录里没有 error_type，从 reflection 中补充
        # 这覆盖了"旧版本 Agent 没记录 error_type 但 reflection 有"的情况
        history_has_error_types = any(
            isinstance(record, dict) and record.get("error_type")
            for record in history
        )
        if not history_has_error_types:
            for reflection in reflections:
                reflection_error_counts.update(
                    reflection.get("error_type_counts", {})
                )

        # 把每条 history 记录打上 source 标签（来自哪个 run）
        for record in history:
            if isinstance(record, dict):
                record = dict(record)
                record["source"] = _relative(path, root)
                history_records.append(record)

        # 计算本次 run 的最佳 NMSE
        nmse_values = [
            _to_float(r.get("nmse_db"))
            for r in history
            if isinstance(r, dict) and r.get("nmse_db") is not None
        ]

        rows.append({
            "source": _relative(path, root),
            "status": payload.get("status", ""),
            "rounds": payload.get("rounds", ""),
            "history_count": len(history),
            "best_nmse_db": min(nmse_values) if nmse_values else None,
            "succeeded": sum(
                1 for r in history
                if isinstance(r, dict) and r.get("run_status") == "succeeded"
            ),
            "failed": sum(
                1 for r in history
                if isinstance(r, dict) and r.get("run_status") == "failed"
            ),
            "rejected": sum(
                1 for r in history
                if isinstance(r, dict) and r.get("run_status") == "rejected"
            ),
        })

    return rows, history_records, reflection_error_counts


# ============================================================
# 聚合计算函数
# ============================================================

def _aggregate_all_totals(
    benchmark_rows: list[dict[str, Any]],
    run_rows: list[dict[str, Any]],
    history_records: list[dict[str, Any]],
) -> dict[str, Any]:
    """从所有实验记录中计算聚合指标。

    这是 v1.6.1 修复的关键函数——之前只算 benchmark 数据，
    现在同时算 planner loop 的 history 数据。

    四个比率含义：
      target_hit_rate      — succeeded / (succeeded+failed+rejected)
                              达标比例。越高说明 Agent 越能找到好模型
      rejected_rate        — rejected / total
                              被 Guard 拦截的比例。过高说明 LLM 不理解约束
      runtime_failure_rate — failed / total
                              执行失败比例。过高说明工具链或阈值设置有问题
      best_nmse_db         — 全局最小 NMSE（越小越好）
    """
    succeeded = sum(1 for r in history_records if r.get("run_status") == "succeeded")
    failed = sum(1 for r in history_records if r.get("run_status") == "failed")
    rejected = sum(1 for r in history_records if r.get("run_status") == "rejected")
    total = succeeded + failed + rejected

    # 从 history_records 和 benchmark_rows 中收集所有 NMSE
    nmse_values = [
        _to_float(r.get("nmse_db"))
        for r in history_records
        if _to_float(r.get("nmse_db")) is not None
    ]
    for row in benchmark_rows:
        for result in row.get("results", []):
            n = _to_float(result.get("best_nmse_db"))
            if n is not None:
                nmse_values.append(n)

    return {
        "case_count": total,
        "target_hit_rate": succeeded / total if total else 0.0,
        "rejected_rate": rejected / total if total else 0.0,
        "runtime_failure_rate": failed / total if total else 0.0,
        "average_experiments_used": total / len(run_rows) if run_rows else 0.0,
        "best_nmse_db": min(nmse_values) if nmse_values else None,
    }


def _aggregate_benchmark_only(
    benchmark_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """只从 benchmark 数据计算指标。"""
    case_count = sum(int(row.get("case_count") or 0) for row in benchmark_rows)
    if not benchmark_rows:
        return {"case_count": 0, "target_hit_rate": 0.0, "rejected_rate": 0.0,
                 "runtime_failure_rate": 0.0, "average_experiments_used": 0.0, "best_nmse_db": None}
    return {
        "case_count": case_count,
        "target_hit_rate": _weighted_rate(benchmark_rows, "target_hit_rate"),
        "rejected_rate": _weighted_rate(benchmark_rows, "rejected_rate"),
        "runtime_failure_rate": _weighted_rate(benchmark_rows, "runtime_failure_rate"),
        "average_experiments_used": _mean([row.get("average_experiments_used") for row in benchmark_rows]),
        "best_nmse_db": min((float(row["best_nmse_db"]) for row in benchmark_rows if row.get("best_nmse_db") is not None), default=None),
    }


def _aggregate_run_only(
    run_rows: list[dict[str, Any]],
    history_records: list[dict[str, Any]],
) -> dict[str, Any]:
    """只从 planner loop 数据计算指标。"""
    succeeded = sum(1 for r in history_records if r.get("run_status") == "succeeded")
    failed = sum(1 for r in history_records if r.get("run_status") == "failed")
    rejected = sum(1 for r in history_records if r.get("run_status") == "rejected")
    total = succeeded + failed + rejected
    nmse_values = [_to_float(r.get("nmse_db")) for r in history_records if _to_float(r.get("nmse_db")) is not None]
    return {
        "case_count": total,
        "target_hit_rate": succeeded / total if total else 0.0,
        "rejected_rate": rejected / total if total else 0.0,
        "runtime_failure_rate": failed / total if total else 0.0,
        "average_experiments_used": total / len(run_rows) if run_rows else 0.0,
        "best_nmse_db": min(nmse_values) if nmse_values else None,
    }


def _best_candidate(
    history_records: list[dict[str, Any]],
    benchmark_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """从所有记录中找 NMSE 最优的实验候选。

    同时考虑了 planner loop history 和 benchmark results，
    按 NMSE 从小到大排序（越小越好），取最小值。
    """
    candidates = []

    # 从 planner loop 的记录中收集
    for record in history_records:
        nmse = _to_float(record.get("nmse_db"))
        if nmse is not None:
            candidates.append({
                "id": str(record.get("id", "")),
                "nmse_db": nmse,
                "parameter_count": record.get("parameter_count", ""),
                "source": record.get("source", ""),
            })

    # 从 benchmark 的结果中收集
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
    """加权平均（权重 = 每个 case 的 case_count），已废弃但保留兼容。"""
    total_cases = sum(int(row.get("case_count") or 0) for row in rows)
    if not total_cases:
        return 0.0
    return sum(
        float(row.get(field) or 0.0) * int(row.get("case_count") or 0)
        for row in rows
    ) / total_cases


def _mean(values: list[Any]) -> float:
    """安全求均值。"""
    numbers = [float(value) for value in values if value is not None]
    return sum(numbers) / len(numbers) if numbers else 0.0


# ============================================================
# 通用小工具
# ============================================================
def _to_float(value: Any) -> float | None:
    """安全转 float。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _read_json(path: Path) -> dict[str, Any]:
    """读 JSON 文件，失败返回空 dict。"""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _relative(path: Path, root: Path) -> str:
    """绝对路径 → 相对路径（相对 project root）。"""
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()
