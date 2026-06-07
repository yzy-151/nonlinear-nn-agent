"""
Planner Schema Guard — 计划校验与参数预算 =================================

LLM 输出不可信，必须过安检。本文件是 Agent 的"安全检查站"。

三道检查（按执行顺序）：
  1. 字段白名单检查   — LLM 不能输出不存在的字段（如 rank、nmse_db）
  2. 字段值类型检查   — LLM 不能把数字写成字符串、把 list 写成 None
  3. 参数预算检查     — LLM 不能设计超出参数上限的模型

被拒的计划不会进入 Runtime，而是记入 history：
  {"run_status": "rejected", "error": "Unsupported fields: rank"}
  → 下一轮 LLM 看到后应自觉修正

面试要点（为什么需要 Guard）：
  schema guard 不是"不相信 LLM"，而是"把不可靠的 LLM 输出变成可审计的结构化拒绝记录"。
  被拒并不可怕——可怕的是 LLM 输出了一个没被检查的计划，到训练时才崩溃，
  浪费了 GPU 时间还没留下可追溯的记录。
"""

from __future__ import annotations

from typing import Any

from nonlinear_agent.experiment import ExperimentConfig


# ============================================================
# 字段别名和黑名单
# ============================================================

ALIAS_FIELDS = {
    "train_samples": "max_train_samples",
    # LLM 有时写旧字段名 → 自动映射到新字段名
    # 加新别名：直接在字典里加一行，不用改代码逻辑
}

# LLM 绝对不能设置的字段（这些都是"结果字段"，不是"配置字段"）
UNSUPPORTED_FIELDS = {
    "rank",              # 矩阵秩 → 训练结果，不是输入
    "parameter_count",   # 参数量 → 也是结果
    "nmse_db",           # NMSE 指标 → 训练结果
    "status",            # 实验状态 → 运行时决定的
    "final_train_loss",  # 最终损失 → 训练结果
    "samples",           # 样本数 → 数据集的属性
    "evaluation_samples",# 评估样本数 → 同上
}
# 为什么有这份黑名单？
# DeepSeek 真实运行中曾输出 fields like "rank" 和 "nmse_db"，
# 但这些是训练脚本产出的结果，不是可覆写的配置。
# 如果不拦截，会传入 generate_config 导致 YAML 写入无效字段，
# 虽然不会崩溃，但会污染配置文件和日志。


# ============================================================
# allowed_override_fields — LLM 可以设置哪些字段
# ============================================================
def allowed_override_fields() -> set[str]:
    """从 ExperimentConfig 的字段定义中提取所有允许覆写的字段名。

    白名单策略：
      只有 ExperimentConfig dataclass 里定义的字段才能被 LLM 覆写。
      LLM 输出不在白名单的字段 → 拒绝。

    为什么不从黑名单反推？
      白名单比黑名单更安全——新增配置字段后自动允许，不需要改 Guard 代码。
      ExperimentConfig 是唯一真相来源（single source of truth）。
    """
    return set(ExperimentConfig.__dataclass_fields__)


# ============================================================
# normalize_planner_overrides — 字段别名映射
# ============================================================
def normalize_planner_overrides(overrides: dict[str, Any]) -> dict[str, Any]:
    """把 LLM 的字段名标准化。

    例如：LLM 写了 train_samples → 映射为 max_train_samples
    不匹配别名 → 保持原样。
    """
    normalized: dict[str, Any] = {}
    for key, value in overrides.items():
        normalized[ALIAS_FIELDS.get(key, key)] = value
    return normalized


# ============================================================
# validate_planned_overrides — 核心校验函数
# ============================================================
def validate_planned_overrides(
    overrides: dict[str, Any],
    parameter_count_max: int | None = None,
) -> dict[str, Any]:
    """对 LLM 输出的 overrides 做完整校验。

    执行顺序：
      1. normalize — 字段别名映射
      2. 白名单检查 — 拒绝不在 ExperimentConfig 里的字段
      3. 黑名单检查 — 拒绝 UNSUPPORTED_FIELDS（结果字段）
      4. 值类型检查 — spline_range 必须是数字；正整数检查
      5. 参数预算检查 — 估计参数量，超预算拒绝

    返回值：
      正常的 overrides（不含 estimated_parameter_count 内部字段）

    异常：
      ValueError — 检查不通过，rejected 记录会写入 history
    """
    # 第 1 步：字段别名映射
    normalized = normalize_planner_overrides(overrides)

    # 第 2 + 3 步：白名单 + 黑名单检查
    allowed = allowed_override_fields()
    unsupported = sorted(
        (set(normalized) - allowed)           # 不在白名单的
        | (set(overrides) & UNSUPPORTED_FIELDS)  # 在黑名单的
    )
    if unsupported:
        raise ValueError(
            f"Unsupported planner override fields: {', '.join(unsupported)}"
        )

    # 第 4 步：值类型/范围检查
    _validate_field_values(normalized)

    # 第 5 步：参数预算检查
    if parameter_count_max is not None:
        parameter_count = estimate_parameter_count(normalized)
        if parameter_count is not None and parameter_count > parameter_count_max:
            raise ValueError(
                f"Estimated parameter count {parameter_count} "
                f"exceeds parameter budget {parameter_count_max}."
            )
        # 把预估值附带到结果里（供日志/调试用，最终返回前会移除）
        if parameter_count is not None:
            normalized["estimated_parameter_count"] = parameter_count

    # 移除非配置字段（estimated_parameter_count 是 Guard 内部使用的）
    return {
        key: value
        for key, value in normalized.items()
        if key != "estimated_parameter_count"
    }


# ============================================================
# estimate_parameter_count — 参数预算估算
# ============================================================
def estimate_parameter_count(overrides: dict[str, Any]) -> int | None:
    """根据模型类型和超参，估计参数量。

    为什么是"估计"而不是精确计算？
      实际参数量取决于训练脚本的具体实现（偏置项、归一化层等），
      Guard 的估计不需要 100% 精确——只要在预算边界附近足够判断是否超限。

    返回 None 的情况：
      complex_cnn 的参数量无法简单估计（取决于 dataset 和网络结构）

    各模型的估计公式（考虑复数特征 = 2× 实数维度）：
      complex_lstsq  — 2 × (feature_width + 1)           闭式解，参数 = 特征数
      linear         — input_dim×2 + 2                    线性层 → 2 输出
      tiny_mlp       — input_dim×hidden + hidden + hidden×2 + 2  MLP → 2 输出
      spline_mlp     — 同上 + hidden×knots                        多了 spline LUT
    """
    model_type = str(overrides.get("model_type", "complex_cnn"))
    feature_mode = str(overrides.get("feature_mode", "legacy_abs"))
    memory_depth = int(overrides.get("memory_depth", 5))
    mp_order_count = int(overrides.get("mp_order_count", 4))
    hidden_units = int(overrides.get("hidden_units", 64))
    spline_knots = int(overrides.get("spline_knots", 16))

    feature_width = _feature_width(feature_mode, memory_depth, mp_order_count)
    input_dim = 2 * feature_width  # 复数 → 实部+虚部，维度翻倍

    if model_type == "complex_lstsq":
        # 闭式最小二乘：每个特征一个系数 + 一个偏置，复数=2×
        return 2 * (feature_width + 1)

    if model_type == "linear":
        # 单层线性：input_dim → 2（实部+虚部输出）
        return input_dim * 2 + 2

    if model_type == "tiny_mlp":
        # 单隐藏层 MLP：input → hidden → 2
        return input_dim * hidden_units + hidden_units + hidden_units * 2 + 2

    if model_type == "spline_mlp":
        # 单隐藏层 + learnable LUT activation：
        # input → hidden + LUT (hidden × knots) → 2
        return (
            input_dim * hidden_units
            + hidden_units
            + hidden_units * spline_knots
            + hidden_units * 2
            + 2
        )

    if model_type == "complex_cnn":
        return None  # CNN 参数不可简单估计

    raise ValueError(f"Unsupported model_type: {model_type}")


# ============================================================
# 字段值校验
# ============================================================
def _validate_field_values(overrides: dict[str, Any]) -> None:
    """逐字段做类型和值域检查。

    这些检查是从真实 DeepSeek 运行事故中总结出来的：
      - spline_range 曾被 LLM 设为 None 或 list → 训练脚本 float(None) 崩溃
      - epochs 曾被 LLM 设为 0 但用的是神经模型 → 不训练直接输出随机值
      - learning_rate 曾被设为字符串 "0.001" → YAML 解析不报错但行为异常

    每个检查后面都有一个真实的 bug。
    """
    model_type = str(overrides.get("model_type", ""))

    # spline_range 必须是数字（曾出现 None 和 list）
    if "spline_range" in overrides and not _is_number(overrides["spline_range"]):
        raise ValueError("spline_range must be a number.")

    # 正整数字段（显然不能为负数或零）
    for field in (
        "memory_depth", "mp_order_count", "hidden_units",
        "spline_knots", "batch_size", "max_train_samples",
    ):
        if field in overrides and not _is_positive_int(overrides[field]):
            raise ValueError(f"{field} must be a positive integer.")

    # epochs 特殊处理：complex_lstsq 允许 0（闭式解不需要训练），
    # 但神经模型必须 >= 1
    if "epochs" in overrides:
        if (
            not isinstance(overrides["epochs"], int)
            or isinstance(overrides["epochs"], bool)
            or overrides["epochs"] < 0
        ):
            raise ValueError("epochs must be a non-negative integer.")
        if (
            model_type in {"tiny_mlp", "spline_mlp", "linear", "complex_cnn"}
            and overrides["epochs"] < 1
        ):
            raise ValueError(
                f"epochs must be >= 1 for neural model {model_type}."
            )

    # 浮点数字段
    for field in ("learning_rate", "scheduler_gamma", "train_ratio"):
        if field in overrides and not _is_number(overrides[field]):
            raise ValueError(f"{field} must be a number.")


# ============================================================
# 类型检查小工具
# ============================================================
def _is_number(value: Any) -> bool:
    """值是不是真正的数字（排除 bool——Python 里 bool 是 int 的子类）。"""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_positive_int(value: Any) -> bool:
    """值是不是正整数（同样排除 bool）。"""
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _feature_width(feature_mode: str, memory_depth: int, mp_order_count: int) -> int:
    """计算特征向量的宽度。

    complex_mp: mp_order_count 个多项式阶数，每阶 (memory_depth+1) 个延迟抽头
      例如 mp=12, mem=150 → width = 12 × 151 = 1812

    legacy_abs: 4 路特征（I/Q 各自幅度+相位），每路 (memory_depth+1) 个延迟
      例如 mem=150 → width = 4 × 151 = 604
    """
    if feature_mode == "complex_mp":
        return mp_order_count * (memory_depth + 1)
    if feature_mode == "legacy_abs":
        return 4 * (memory_depth + 1)
    raise ValueError(f"Unsupported feature_mode: {feature_mode}")
