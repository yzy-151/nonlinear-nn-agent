"""
Agent Benchmark 评估系统 ==============================================

解决一个面试高频问题："你怎么证明 Agent 改动后真的更好了？"

答案不是"跑一次 demo 看看效果"，而是用固定测试集做定量评估。
就像模型的回归测试——改了 prompt / guard / runtime 之后跑一遍 benchmark，
看 target_hit_rate / rejected_rate / runtime_failure_rate 有没有退化。

三个内置 Benchmark Case：

  case 1: target-under-budget
    目标：在 4000 参数约束下找到 NMSE <= -35 dB
    测试：Agent 能否在预算内找到达标模型

  case 2: invalid-plan-recovery
    目标：LLM 出非法计划时，Guard 能否拦截 + Planner 能否修正
    测试：Fake LLM 第一轮输出非法字段 → 应被 rejected → 第二轮修正

  case 3: runtime-failure-handling
    目标：工具执行失败时，Agent 能否优雅处理
    测试：设一个不可能达成的 NMSE 阈值（-60 dB），观察 Agent 如何处理失败

评价指标（不止看 NMSE）：
  target_hit_rate      — 达标率（越高越好）
  rejected_rate        — 非法计划拦截率（反映了 Guard 的有效性）
  runtime_failure_rate — 运行时失败率（反映了工具链的稳定性）
  average_experiments_used — 平均用了几个实验才达标（效率指标）
  best_nmse_db         — 全局最优 NMSE

面试要点：
  这些指标能解释 prompt 改动、guardrail 改动、runtime 改动的效果。
  面试官不会只看"你跑了个 demo 成功了"，而是看"你有体系地评估 Agent 的行为质量"。
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

from nonlinear_agent.loop import PlannerLoopResult


# ============================================================
# BenchmarkCase — 一个测试用例（输入）
# ============================================================
@dataclass(frozen=True)
class BenchmarkCase:
    """定义一个 Benchmark 测试用例。

    每个 case 是一套"让 Agent 完成某任务"的设定：
      - 如果 Agent 在限制内达成目标 → target_hit = True
      - 如果 Guard 正确拦截了非法计划 → rejected 记录
      - 如果工具执行失败但没崩溃 → failed 记录（不是系统 crash）

    target_nmse_db 是达标线（NMSE <= target → hit）。
    """
    case_id: str                          # 用例 ID，如 "target-under-budget"
    goal: str                             # Agent 要达成的目标
    constraints: dict[str, Any] = field(default_factory=dict)  # 约束条件
    max_rounds: int = 3                   # 最多几轮
    max_experiments: int | None = None    # 最多几个实验
    target_nmse_db: float | None = None   # 达标阈值，None 表示不检查


# ============================================================
# BenchmarkCaseResult — 一个测试用例的结果（输出）
# ============================================================
@dataclass
class BenchmarkCaseResult:
    """单个 Benchmark Case 执行后的统计结果。

    这个对象从 PlannerLoopResult 中提取关键指标，
    用于汇总和横向对比（同一个 case 跑多次，对比不同 prompt/guard/runtime 的表现）。
    """
    case_id: str
    status: str = ""                     # Agent Loop 的退出原因
    rounds: int = 0                      # 实际跑了几轮
    history_count: int = 0               # 总共有多少条实验记录（含 rejected）
    best_experiment_id: str = ""         # NMSE 最优的实验 ID
    best_nmse_db: float | None = None    # 最优 NMSE
    best_parameter_count: int | None = None  # 最优实验的参数量
    target_hit: bool = False             # 是否达标
    rejected_count: int = 0              # Guard 拦截次数
    failed_count: int = 0                # 执行失败次数
    succeeded_count: int = 0             # 执行成功次数
    experiments_used: int = 0            # 实际消耗的实验配额（failed + succeeded，不含 rejected）


# execute_case 的类型：接受 BenchmarkCase，返回 PlannerLoopResult
BenchmarkExecutor = Callable[[BenchmarkCase], Awaitable[PlannerLoopResult]]


# ============================================================
# run_benchmark_cases — 跑 Benchmark
# ============================================================
async def run_benchmark_cases(
    cases: list[BenchmarkCase],
    execute_case: BenchmarkExecutor,
) -> tuple[list[BenchmarkCaseResult], dict[str, Any]]:
    """依次执行所有 Benchmark Case，返回逐 case 结果 + 汇总。

    execute_case 是一个回调函数，接受 BenchmarkCase，返回 PlannerLoopResult。
    调用方（server.py 或 run_benchmark.py）负责创建 FakeLLM + ExperimentPlannerLoop，
    然后传给这里执行。
    """
    results = []
    for case in cases:
        loop_result = await execute_case(case)
        results.append(summarize_loop_result(case, loop_result))
    return results, build_benchmark_summary(results)


# ============================================================
# summarize_loop_result — 从 PlannerLoopResult 提取统计
# ============================================================
def summarize_loop_result(
    case: BenchmarkCase, loop_result: PlannerLoopResult
) -> BenchmarkCaseResult:
    """把一次 Agent Loop 的完整结果压缩为 Benchmark 所需的关键指标。

    核心逻辑：
      - 从 history 里统计 rejected / failed / succeeded 数量
      - 从 history 里找 NMSE 最优的实验
      - 判断是否 hit 目标阈值
      - experiments_used = failed + succeeded（不含 rejected，因为 rejected 不消耗训练资源）
    """
    history = loop_result.history
    best = _best_nmse_record(history)

    rejected_count = _count_status(history, "rejected")
    failed_count = _count_status(history, "failed")
    succeeded_count = _count_status(history, "succeeded")

    best_nmse = _to_float(best.get("nmse_db")) if best else None

    # 判断是否达标：最优 NMSE <= 目标阈值
    target_hit = bool(
        case.target_nmse_db is not None
        and best_nmse is not None
        and best_nmse <= case.target_nmse_db  # NMSE 越小越好
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


# ============================================================
# build_benchmark_summary — 所有 case 汇总
# ============================================================
def build_benchmark_summary(results: list[BenchmarkCaseResult]) -> dict[str, Any]:
    """把所有 case 的结果汇总成一份总评。

    四个关键比率：
      target_hit_rate      = 命中目标的 case 数 / 总 case 数
      rejected_rate        = 被 Guard 拦截的记录数 / 总记录数
      runtime_failure_rate = 执行失败的记录数 / 总记录数
      average_experiments_used = 实际消耗的实验数 / case 数

    全部比率都乘以 case_count 做加权平均（权重 = 每个 case 的记录数）。
    """
    case_count = len(results)
    total_records = sum(
        result.rejected_count + result.failed_count + result.succeeded_count
        for result in results
    )
    total_experiments = sum(result.experiments_used for result in results)

    return {
        "case_count": case_count,
        "target_hit_rate": _rate(
            sum(1 for result in results if result.target_hit), case_count
        ),
        "rejected_rate": _rate(
            sum(result.rejected_count for result in results), total_records
        ),
        "runtime_failure_rate": _rate(
            sum(result.failed_count for result in results), total_records
        ),
        "average_experiments_used": (
            (total_experiments / case_count) if case_count else 0.0
        ),
        "best_nmse_db": min(
            (
                result.best_nmse_db
                for result in results
                if result.best_nmse_db is not None
            ),
            default=None,
        ),
    }


# ============================================================
# write_benchmark_artifacts — 落盘
# ============================================================
def write_benchmark_artifacts(
    output_dir: Path | str,
    results: list[BenchmarkCaseResult],
    summary: dict[str, Any],
) -> None:
    """把 Benchmark 结果写入磁盘。

    输出三个文件：
      benchmarks/<dir>/results.json    — 完整结构化结果（给 Dashboard 读）
      benchmarks/<dir>/leaderboard.csv — 按 NMSE 排序的排行榜（给 Excel 看）
      benchmarks/<dir>/summary.md      — Markdown 摘要（给人类读）
    """
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    # JSON：包含 summary + 每个 case 的完整结果
    result_rows = [asdict(result) for result in results]
    (output / "results.json").write_text(
        json.dumps(
            {"summary": summary, "results": result_rows},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    _write_leaderboard(output / "leaderboard.csv", results)
    _write_summary(output / "summary.md", summary, results)


def _write_leaderboard(path: Path, results: list[BenchmarkCaseResult]) -> None:
    """输出 CSV 排行榜，按 NMSE 从优到差排序。"""
    columns = [
        "case_id", "target_hit", "best_nmse_db", "best_experiment_id",
        "best_parameter_count", "status", "rounds", "experiments_used",
        "rejected_count", "failed_count", "succeeded_count",
    ]
    # 排序：有 NMSE 的在前（从小到大），None 的排最后
    sorted_results = sorted(
        results,
        key=lambda result: (result.best_nmse_db is None, result.best_nmse_db or 0.0),
    )
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for result in sorted_results:
            row = asdict(result)
            writer.writerow({column: row.get(column, "") for column in columns})


def _write_summary(
    path: Path, summary: dict[str, Any], results: list[BenchmarkCaseResult]
) -> None:
    """输出 Markdown 摘要报告。"""
    lines = [
        "# Agent Benchmark Summary", "",
        f"- case_count: `{summary['case_count']}`",
        f"- target_hit_rate: `{summary['target_hit_rate']}`",
        f"- rejected_rate: `{summary['rejected_rate']}`",
        f"- runtime_failure_rate: `{summary['runtime_failure_rate']}`",
        f"- average_experiments_used: `{summary['average_experiments_used']}`",
        f"- best_nmse_db: `{summary['best_nmse_db']}`",
        "", "## Cases", "",
    ]
    for result in results:
        lines.append(
            f"- `{result.case_id}`: hit={result.target_hit}, "
            f"best_nmse={result.best_nmse_db}, "
            f"rejected={result.rejected_count}, "
            f"failed={result.failed_count}, "
            f"succeeded={result.succeeded_count}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ============================================================
# 辅助函数
# ============================================================
def _best_nmse_record(history: list[dict[str, Any]]) -> dict[str, Any] | None:
    """从 history 中找 NMSE 最优的记录。"""
    records = [
        record for record in history if _to_float(record.get("nmse_db")) is not None
    ]
    if not records:
        return None
    return min(records, key=lambda r: _to_float(r.get("nmse_db")) or 0.0)


def _count_status(history: list[dict[str, Any]], status: str) -> int:
    """统计 history 中某状态的记录数。"""
    return sum(1 for record in history if record.get("run_status") == status)


def _rate(numerator: int, denominator: int) -> float:
    """安全除法，分母为 0 时返回 0.0。"""
    return numerator / denominator if denominator else 0.0


def _to_float(value: Any) -> float | None:
    """安全转 float。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    """安全转 int。"""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
