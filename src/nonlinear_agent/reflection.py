"""
Reflection / Recovery Policy — 实验复盘 ==================================

每轮 Agent 实验结束后，结构化分析"这一轮发生了什么、下轮该怎么做"。

解决的问题：
  日志是"发生了什么"（描述性）
  Reflection 是"下一步怎么修"（处方性）

输出三个关键字段：
  failure_causes  — 本轮失败的原因（具体是哪个实验、什么错误）
  recovery_actions — 下一轮应该怎么改（修改策略、换模型、调整阈值）
  avoid_next       — 下一轮应该避免什么（不要重复犯同样的错）

设计决策（面试可能问）：
  为什么不调 LLM 做 reflection，而是用规则匹配？
    → 确定性：规则匹配不需要 API 调用、不烧钱、结果可复现
    → 速度：几毫秒完成，不影响 Agent Loop 节奏
    → 可审计：同一个错误永远触发同一个建议，方便调试
    → 如果需要更智能的 reflection，可以在下一轮把 reflection 结果
      注入 planner prompt，让 LLM 自己解读并修正——而不是让 LLM 写 reflection
"""

from __future__ import annotations

from collections import Counter
from typing import Any


# ============================================================
# ReflectionPolicy — 复盘策略
# ============================================================
class ReflectionPolicy:
    """分析一轮实验的结果，生成结构化复盘。

    输入：round_records（本轮所有实验记录）
    输出：{round, status_counts, best_nmse, failure_causes, recovery_actions, avoid_next}

    使用方式（在 ExperimentPlannerLoop 中）：
      reflection = self.reflection_policy.reflect(round_index=1, round_records=records)
      → 写入 reflections/round-001.json
      → 下一轮 planner prompt 里引用 reflection 结果
    """

    def reflect(
        self,
        round_index: int,
        round_records: list[dict[str, Any]],
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

        # ── 提取失败原因 ──
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
def _recovery_actions(causes: list[str]) -> list[str]:
    """根据失败原因的关键词，生成修正策略。

    规则匹配逻辑（简单但有效）：
      - 出现 "unsupported"/"schema"/"preflight" → 让 LLM 检查字段合法性
      - 出现 "nmse"/"threshold" → 建议换模型族或特征设计
      - 出现 "timeout" → 建议增加超时或拆分步骤
      - 其他 → 保持当前方向，一次只改一个变量

    面试要点：
      这些规则不是 AI 生成的，是工程师根据真实运行经验写的。
      每次新增一种失败模式，就往这里加一条规则——积累形成团队的容错知识库。
    """
    actions = []
    text = " ".join(causes).lower()

    if "unsupported" in text or "schema" in text or "preflight" in text:
        actions.append(
            "Remove unsupported fields and keep planner overrides "
            "within the declared tool/config schema."
        )

    if "nmse" in text or "threshold" in text:
        actions.append(
            "Prefer stronger baseline variants or revise the target/feature family "
            "after repeated NMSE threshold failures."
        )

    if "timeout" in text:
        actions.append(
            "Increase the tool timeout only for expensive steps "
            "or split the run into smaller resumable steps."
        )

    # 兜底：没有匹配到任何规则 → 给一个通用建议
    if not actions:
        actions.append(
            "Continue with the best observed configuration "
            "and explore one controlled variable at a time."
        )

    return actions


def _avoid_next(causes: list[str]) -> list[str]:
    """根据失败原因生成"下一轮避免事项"。

    和 recovery_actions 的区别：
      recovery_actions = "应该做什么"（positive, actionable）
      avoid_next       = "不应该做什么"（negative, preventive）

    例如：
      recovery: "换模型族"
      avoid:    "不要再用表现差的模型族重复尝试"
    """
    avoid = []
    text = " ".join(causes).lower()

    if "unsupported" in text or "schema" in text:
        avoid.append(
            "Avoid planner fields not listed in ExperimentConfig "
            "or ToolSpec input_schema."
        )

    if "threshold" in text or "nmse" in text:
        avoid.append(
            "Avoid repeating weak model families "
            "without changing feature design or training budget."
        )

    if not avoid:
        avoid.append(
            "Avoid changing multiple variables at once "
            "when the previous round did not isolate a cause."
        )

    return avoid


# ============================================================
# 辅助函数
# ============================================================
def _best_experiment_id(records: list[dict[str, Any]]) -> str:
    """本轮 NMSE 最优的实验 ID。"""
    best = _best_record(records)
    return str(best.get("id", "")) if best else ""


def _best_nmse(records: list[dict[str, Any]]) -> float | None:
    """本轮最优 NMSE 值。"""
    best = _best_record(records)
    return _to_float(best.get("nmse_db")) if best else None


def _best_record(records: list[dict[str, Any]]) -> dict[str, Any] | None:
    """从记录中找到 NMSE 最小的那条（NMSE 越小越好）。"""
    candidates = [
        record
        for record in records
        if _to_float(record.get("nmse_db")) is not None
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda r: _to_float(r.get("nmse_db")) or 0.0)


def _to_float(value: Any) -> float | None:
    """安全转 float，失败返回 None。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
