"""
Reflection Facts — 实验事实提取 ==================================

每轮 Agent 实验结束后，只提取"这一轮发生了什么"。

解决的问题：
  日志是"发生了什么"（描述性）
  Reflection Facts 是"把发生过的事实清洗成 LLM 容易读的结构化上下文"

输出关键字段：
  facts           — 干净的实验事实列表，供下一轮 Planner LLM 自己推理
  failure_causes  — 本轮失败的原因（具体是哪个实验、什么错误）

设计决策（面试可能问）：
  为什么不在 reflection 里生成 recovery_actions？
    → LLM 比几个 if 规则更擅长根据干净 history 推理下一步
    → deterministic reflection 只负责事实提取，避免把工程师规则当成智能策略
    → planner prompt 会拿到 facts，由 LLM 负责判断错误原因和新实验计划
"""

from __future__ import annotations

from collections import Counter
from typing import Any


# ============================================================
# ReflectionPolicy — 复盘策略
# ============================================================
class ReflectionPolicy:
    """分析一轮实验的结果，生成结构化事实。

    输入：round_records（本轮所有实验记录）
    输出：{round, status_counts, best_nmse, failure_causes, facts}

    使用方式（在 ExperimentPlannerLoop 中）：
      reflection = self.reflection_policy.reflect(round_index=1, round_records=records)
      → 写入 reflections/round-001.json
      → 下一轮 planner prompt 里引用 reflection 结果
    """

    def reflect(
        self,
        round_index: int,
        round_records: list[dict[str, Any]],
        primary_metric: str = "nmse_db",
        lower_is_better: bool = True,
    ) -> dict[str, Any]:
        """对本轮所有实验记录做复盘分析。

        round_records 示例：
          [{"id": "exp001", "run_status": "succeeded", "nmse_db": -37.42},
           {"id": "exp002", "run_status": "rejected",  "error": "Unsupported: rank"},
           {"id": "exp003", "run_status": "failed",    "error": "NMSE threshold", "error_type": "metric_threshold_error"}]
        """

        # ── 统计本轮状态分布 ──
        status_counts = Counter(
            str(record.get("run_status", "unknown")) for record in round_records
        )

        # ── 统计错误类型分布 ──
        # 例如 {"metric_threshold_error": 3, "validation_error": 1}
        error_type_counts = Counter(
            str(record.get("error_type"))
            for record in round_records
            if record.get("error_type")
        )

        # ── 提取失败原因和干净事实 ──
        failure_causes = _failure_causes(round_records)

        return {
            "round": round_index,
            "record_count": len(round_records),
            "status_counts": dict(status_counts),
            "error_type_counts": dict(error_type_counts),
            "best_experiment_id": _best_experiment_id(round_records, primary_metric, lower_is_better),
            f"best_{primary_metric}": _best_metric(round_records, primary_metric, lower_is_better),
            "failure_causes": failure_causes,
            "facts": _facts(round_records, primary_metric),
        }


# ============================================================
# 失败原因提取
# ============================================================
def _failure_causes(records: list[dict[str, Any]]) -> list[str]:
    """从记录中提取所有失败原因。

    两类失败：
      - rejected：Schema Guard 在运行前拦截（非法字段、类型错误）
        → "Schema/preflight rejection in exp26: Unsupported fields: rank"
      - failed：Runtime 执行失败（训练崩溃、NMSE 不达标）
        → "Runtime/tool failure in exp23: NMSE -27 dB did not meet threshold"

    成功的记录（succeeded）不出现在这里——只记录"出了什么问题"。
    """
    causes = []
    for record in records:
        status = record.get("run_status")
        error = str(record.get("error", ""))
        if status == "rejected":
            causes.append(
                f"Schema/preflight rejection in {record.get('id', '')}: {error}"
            )
        elif status == "failed":
            causes.append(
                f"Runtime/tool failure in {record.get('id', '')}: {error}"
            )
    return causes


# ============================================================
# 恢复策略生成（规则匹配）
# ============================================================
def _facts(records: list[dict[str, Any]], primary_metric: str = "nmse_db") -> list[dict[str, Any]]:
    """从实验记录中提取给 LLM 的干净事实，不输出策略。"""
    facts: list[dict[str, Any]] = []
    base_fields = ["id", "reason", "run_status", "error", "error_type", primary_metric]
    extra_fields = [
        "parameter_count", "model_type", "feature_mode", "target_mode",
        "memory_depth", "mp_order_count", "epochs", "optimizer", "learning_rate",
        "baseline_nmse_db", "nmse_improvement_db", "train_mse",
    ]
    fields = base_fields + [f for f in extra_fields if any(f in r for r in records)]
    for record in records:
        fact: dict[str, Any] = {}
        for field in fields:
            if field in record and record.get(field) is not None:
                key = "status" if field == "run_status" else field
                fact[key] = record.get(field)
        if fact:
            facts.append(fact)
    return facts


# ============================================================
# 辅助函数
# ============================================================
def _best_experiment_id(records: list[dict[str, Any]], metric: str = "nmse_db", lower_is_better: bool = True) -> str:
    """本轮最优实验 ID。"""
    best = _best_record(records, metric, lower_is_better)
    return str(best.get("id", "")) if best else ""


def _best_metric(records: list[dict[str, Any]], metric: str = "nmse_db", lower_is_better: bool = True) -> float | None:
    """本轮最优 metric 值。"""
    best = _best_record(records, metric, lower_is_better)
    return _to_float(best.get(metric)) if best else None


def _best_record(records: list[dict[str, Any]], metric: str = "nmse_db", lower_is_better: bool = True) -> dict[str, Any] | None:
    """从记录中找到 metric 最优的那条。"""
    candidates = [
        record
        for record in records
        if _to_float(record.get(metric)) is not None
    ]
    if not candidates:
        return None
    if lower_is_better:
        return min(candidates, key=lambda r: _to_float(r.get(metric)) or float("inf"))
    return max(candidates, key=lambda r: _to_float(r.get(metric)) or float("-inf"))


def _to_float(value: Any) -> float | None:
    """安全转 float，失败返回 None。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
