"""
上下文压缩 =========================================================

问题：Agent 跑了 20 轮实验，history 有 50 条记录。全塞进 LLM prompt？
  → token 爆炸（烧钱）+ LLM 注意力分散（信息过载）

解决方案：压缩旧记录，只给 LLM 看"摘要 + 最近几条"。

类比：
  你写周报时不需要把周一每封邮件抄一遍——你写"本周完成了 X，遇到了 Y 问题"。
  HistoryCompressor 就是在给 LLM 写"实验周报"。

具体做法：
  输入：[exp1, exp2, exp3, exp4, exp5, exp6, exp7]  （7 条记录）
  输出：[summary(前 4 条), exp5, exp6, exp7]        （摘要 + 最近 3 条）

面试要点：
  - 完整 history 仍在 artifacts 里保留（可审计）
  - Prompt 里只注入压缩版本（省 token）
  - 摘要保留"状态统计 + 最优指标 + 代表性错误"（足够 LLM 决策）
"""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from typing import Any


# ============================================================
# HistoryCompressor — 历史压缩器
# ============================================================
class HistoryCompressor:
    """把长的实验历史压缩为"summary + 最近 N 条"。

    参数：
      recent_window      — 保留最近多少条原始记录（至少 1）
      max_notable_errors  — 摘要里最多收录几条代表性错误

    使用方式（在 ExperimentPlannerLoop 中）：
      compressor = HistoryCompressor(recent_window=3)
      prompt_history = compressor.build_prompt_history(history)
      # prompt_history 现在是 [summary_dict, record4, record5, record6]
    """

    def __init__(self, recent_window: int = 3, max_notable_errors: int = 3):
        if recent_window < 1:
            raise ValueError("recent_window must be >= 1.")
        self.recent_window = recent_window
        self.max_notable_errors = max_notable_errors

    def build_prompt_history(
        self, history: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """把历史压缩后返回给 Planner prompt 使用的列表。

        如果历史很短（<= recent_window），直接返回全部（不做压缩）。
        如果历史很长，前面的压缩成一条 summary，后面的原样保留。

        示例：
          history = [r1, r2, r3, r4, r5, r6, r7], window=3
          → [summary(压缩了 r1-r4), r5, r6, r7]

        为什么保留最近 N 条原始记录？
          LLM 需要看到最近的具体失败原因和指标来决策下一轮。
          很久之前的记录只需要"大致知道结果"就够了。
        """
        if len(history) <= self.recent_window:
            # 历史不长 → 不做压缩，直接返回（deepcopy 防篡改）
            return deepcopy(history)

        # 切分：前面的压缩，后面的保留
        older = history[: -self.recent_window]       # 需要压缩的旧记录
        recent = history[-self.recent_window :]       # 保留原样的新记录

        # 构造压缩摘要
        summary = summarize_history(
            older, max_notable_errors=self.max_notable_errors
        )

        # 返回：摘要放在第一条（LLM 先看到概览），然后是最新记录
        return [summary, *deepcopy(recent)]


# ============================================================
# summarize_history — 把若干条记录压缩成一条摘要
# ============================================================
def summarize_history(
    history: list[dict[str, Any]], max_notable_errors: int = 3
) -> dict[str, Any]:
    """把一组实验记录压缩成一条结构化摘要。

    摘要保留了 LLM 决策需要的三个关键信息：
      1. 状态统计 — 多少成功 / 多少失败 / 多少被拒
      2. 最优候选 — 到目前为止 NMSE 最低的是哪个实验
      3. 代表性错误 — 出现了哪些错误（最多 max_notable_errors 条）

    返回的 dict 长得像一条正常的 history 记录（有 id、run_status、nmse_db 等字段），
    这样 LLM 可以统一解析，不需要区分"摘要"和"原始记录"。

    为什么只取前 N 条错误而不是全部？
      LLM 不需要看所有 20 个失败原因——前 3 个就足够判断"当前策略有问题"。
    """
    # 统计状态分布
    status_counts = Counter(
        str(record.get("run_status", "unknown")) for record in history
    )

    # 找最佳实验
    best = _best_nmse_record(history)

    # 收集代表性错误（取前 N 条，不是全部）
    notable_errors = []
    for record in history:
        error = record.get("error")
        if error:
            notable_errors.append(f"{record.get('id', '')}: {error}")
        if len(notable_errors) >= max_notable_errors:
            break

    summary = {
        "id": "history-summary",           # 特殊 ID，LLM 能一眼认出这是摘要
        "run_status": "summary",
        "covered_records": len(history),   # 告诉 LLM"这个摘要覆盖了多少条记录"
        "status_counts": dict(status_counts),
        "best_experiment_id": str(best.get("id", "")) if best else "",
        "best_nmse_db": _to_float(best.get("nmse_db")) if best else None,
        "best_parameter_count": _to_int(best.get("parameter_count")) if best else None,
        "notable_errors": notable_errors,
    }

    # 追加一段自然语言总结（方便 LLM 快速理解）
    summary["context_summary"] = _build_context_summary(summary)
    return summary


def _build_context_summary(summary: dict[str, Any]) -> str:
    """生成一段可读的摘要文本，追加在压缩记录的 context_summary 字段里。"""
    return (
        f"Compressed {summary['covered_records']} older records. "
        f"Status counts: {summary['status_counts']}. "
        f"Best: {summary['best_experiment_id']} at {summary['best_nmse_db']} dB. "
        f"Notable errors: {summary['notable_errors']}."
    )


# ============================================================
# 辅助函数
# ============================================================
def _best_nmse_record(history: list[dict[str, Any]]) -> dict[str, Any] | None:
    """从历史记录中找到 NMSE 最小的那条。

    NMSE 越小越好（-40 比 -35 好），所以用 min()。
    """
    records = [
        record for record in history if _to_float(record.get("nmse_db")) is not None
    ]
    if not records:
        return None
    return min(records, key=lambda record: _to_float(record.get("nmse_db")) or 0.0)


def _to_float(value: Any) -> float | None:
    """安全转 float，失败返回 None。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    """安全转 int，失败返回 None。"""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
