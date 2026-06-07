"""
LLM 实验计划器 ======================================================

整个 Agent Loop 的"大脑"。负责：

  输入：实验目标 + 历史结果 + 约束条件
  处理：构造 prompt → 发给 LLM → 解析返回的 JSON
  输出：ExperimentPlan（包含本轮要跑哪些实验、是否停止）

设计边界（面试重点）：
  Planner 只输出结构化 JSON plan，不能直接调工具、执行命令或访问文件。
  这就是 Agent 和"让 LLM 写脚本直接跑"的核心区别——
  LLM 负责规划，Runtime 负责执行，两者完全解耦。
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any

from nonlinear_agent.llm import LLMClient
from nonlinear_agent.planner_validation import normalize_planner_overrides


# ============================================================
# PlannedExperiment — 一个待执行的实验
# ============================================================
@dataclass(frozen=True)
class PlannedExperiment:
    """LLM 设计的一个实验候选。

    字段含义：
      experiment_id  — 实验编号，如 "exp001"、"exp_016"
      reason         — LLM 解释"为什么设计这个实验"，用于日志审计和人类理解
      overrides      — 要覆写的配置字段，如 {"model_type":"complex_lstsq","memory_depth":220}

    注意：overrides 里写的只是"相对于 base config 的改动"。
    比如 base 是 lstsq-complexmp-o12-m150，overrides 写 {"memory_depth": 220}，
    generate_config 工具会把两个合并，产生 mem=220 的配置。
    """
    experiment_id: str
    reason: str
    overrides: dict[str, Any] = field(default_factory=dict)


# ============================================================
# ExperimentPlan — 一轮实验计划
# ============================================================
@dataclass(frozen=True)
class ExperimentPlan:
    """LLM 返回的一整轮计划。

    summary     — 本轮策略的一句话概括，会写入日志和 history
    experiments — 本轮要跑的实验列表，可能为空（表示"停止"）
    stop        — True 表示 LLM 认为目标已达成或无法继续，Agent Loop 应停止

    最小有效计划：stop=True, experiments=[] → Agent 停止
    正常计划：    stop=False, experiments=[...] → Agent 继续执行
    """
    summary: str
    experiments: list[PlannedExperiment]
    stop: bool = False


# ============================================================
# ExperimentPlanner — 计划器（核心）
# ============================================================
class ExperimentPlanner:
    """把目标、历史、约束打包发给 LLM，解析返回的 JSON。

    依赖注入：
      llm_client — FakeLLMClient 或 OpenAICompatibleClient（不清楚调的是哪个）
      → Planner 不知道也不关心 LLM 是怎么工作的，只管"发 prompt，收 JSON"

    调用链：
      ExperimentPlannerLoop.run() 每轮调 plan()
        → plan() 构造 prompt → llm.complete(prompt) → 解析 JSON → ExperimentPlan
    """

    def __init__(self, llm_client: LLMClient, allowed_tools: list[str] | None = None):
        """allowed_tools 会嵌入 prompt，告诉 LLM 它能用哪些工具。"""
        self.llm_client = llm_client
        self.allowed_tools = allowed_tools or [
            "generate_config", "run_training", "verify_artifacts", "write_report",
        ]

    # ── 公共入口 ──────────────────────────────────────────
    def plan(
        self,
        goal: str,
        history: list[dict[str, Any]] | None = None,
        constraints: dict[str, Any] | None = None,
    ) -> ExperimentPlan:
        """策划下一轮实验。

        三步：
          1. 构造 prompt（目标 + 历史 + 约束 + 设计空间 + 工具列表）
          2. 发给 LLM
          3. 解析 JSON → ExperimentPlan

        参数：
          goal        — 实验目标，如 "Find NMSE <= -35 dB under 4000 params"
          history     — 之前所有实验的结果（已压缩过的）
          constraints — 约束条件，如 {"parameter_count_max": 4000}
        """
        prompt = self._build_prompt(
            goal=goal,
            history=history or [],
            constraints=constraints or {},
        )
        raw = self.llm_client.complete(prompt)     # 发 prompt，拿 JSON 字符串
        payload = _parse_json_object(raw)           #
        
         解析 JSON（容错：处理 LLM 多输出文字的情况）
        return self._parse_plan(payload)            # 转成结构化的 ExperimentPlan

    # ── Prompt 构造 ──────────────────────────────────────
    def _build_prompt(
        self,
        goal: str,
        history: list[dict[str, Any]],
        constraints: dict[str, Any],
    ) -> str:
        """构造发给 LLM 的完整 prompt。

        Prompt 结构（面试常考点——怎么让 LLM 输出可靠的结构化计划）：
          1. 任务描述："Design the next nonlinear-system modeling experiments."
          2. 目标："Goal: Find NMSE <= -35 dB under 4000 params"
          3. 约束：{"parameter_count_max": 4000, "metric": "nmse_db"}
          4. 历史：上一轮的结果（含 NMSE、错误、被拒原因等）
          5. JSON 格式要求：必须返回这个 schema
          6. 设计空间说明：有哪些模型、特征、参数可以选
          7. 可用工具列表：Agent 能调哪些工具

        面试要点：
          Prompt 里显式列出设计空间和参数约束，
          不是为了"调参"，而是为了"让 LLM 在不写代码不调 shell 的情况下
          做出可执行的实验决策"。
        """
        return (
            "Design the next nonlinear-system modeling experiments.\n"
            f"Goal: {goal}\n"
            f"Constraints: {json.dumps(constraints, ensure_ascii=False)}\n"
            f"History: {json.dumps(history, ensure_ascii=False)}\n\n"
            "Return JSON only with schema:\n"
            '{"summary": str, "stop": bool, "experiments": ['
            '{"id": str, "reason": str, "overrides": object}]}\n'
            # ── 领域知识注入 ──
            # 下面这块是物理/算法先验，不是通用能力
            "Executable design space:\n"
            "- model_type: complex_lstsq, linear, tiny_mlp, spline_mlp.\n"
            "- feature_mode: complex_mp is preferred for RF nonlinear memory "
            "polynomial structure; legacy_abs is a baseline.\n"
            "- complex_lstsq explores memory_depth and mp_order_count "
            "with closed-form fitting.\n"
            "- tiny_mlp explores hidden_units and activation in "
            "relu/tanh/silu/gelu.\n"
            "- spline_mlp is a physics-informed shallow nonlinear model: "
            "one nonlinear layer with a learnable 1D LUT activation, "
            "usually spline_knots=16 and first-order linear interpolation.\n"
            "- Good spline_mlp candidates under 4000 params: "
            "feature_mode=complex_mp, mp_order_count=1, "
            "memory_depth in [24, 48, 72], hidden_units in [16, 32], "
            "spline_knots=16.\n"
            "- Keep parameter_count_max from constraints; prefer fewer "
            "parameters when NMSE is similar.\n"
            "Use overrides for YAML config fields such as model_type, "
            "feature_mode, memory_depth, mp_order_count, epochs, "
            "learning_rate, optimizer, output_dir, hidden_units, "
            "activation, spline_knots, spline_range. "
            "Do not output shell commands. "
            # ── 安全边界：告诉 LLM 能调哪些工具 ──
            f"The runtime will only use these tools: "
            f"{_format_allowed_tools(self.allowed_tools)}."
        )

    # ── 解析 LLM 返回 ────────────────────────────────────
    def _parse_plan(self, payload: dict[str, Any]) -> ExperimentPlan:
        """把 LLM 返回的 JSON 字典转成 ExperimentPlan 对象。

        做三件事：
          1. 校验每个实验必须有 id
          2. 校验 overrides 必须是字典（不是字符串、数组）
          3. 对 overrides 做 normalize（字段别名映射，如 train_samples → max_train_samples）
        """
        experiments = []
        for item in payload.get("experiments", []):
            experiment_id = str(item.get("id", "")).strip()
            if not experiment_id:
                raise ValueError("Planned experiment is missing id.")
            overrides = item.get("overrides", {})
            if not isinstance(overrides, dict):
                raise ValueError(
                    f"Experiment {experiment_id} overrides must be an object."
                )
            # normalize：字段别名映射 + 类型规范化
            overrides = normalize_planner_overrides(overrides)
            experiments.append(
                PlannedExperiment(
                    experiment_id=experiment_id,
                    reason=str(item.get("reason", "")),
                    overrides=overrides,
                )
            )
        return ExperimentPlan(
            summary=str(payload.get("summary", "")),
            stop=bool(payload.get("stop", False)),
            experiments=experiments,
        )


# ============================================================
# JSON 解析（容错）
# ============================================================
def _parse_json_object(text: str) -> dict[str, Any]:
    """解析 LLM 返回的 JSON 字符串，带容错处理。

    容错策略：
      LLM 偶尔在 JSON 前后加上自然语言（如 "Here is the plan:\n{...}\nHope this helps"）。
      先用 json.loads() 直接解析；如果失败，找第一个 { 和最后一个 }，只解析中间那部分。

    面试要点：
      这不是 hack，是生产 Agent 的常见需求——LLM 输出不能 100% 保证纯 JSON。
    """
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        # LLM 多说了话 → 只取第一个 { 到最后一个 } 之间的部分
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise  # 实在找不到 JSON → 抛出原始错误，外层 Planner 捕获
        payload = json.loads(text[start : end + 1])

    if not isinstance(payload, dict):
        raise ValueError("Planner response must be a JSON object.")
    return payload


def _format_allowed_tools(allowed_tools: list[Any]) -> str:
    """把工具列表格式化成 prompt 里可读的字符串。

    支持三种格式：
      - 字符串：直接使用
      - dataclass 实例（如 ToolSpec）：用 asdict() 转成 dict → JSON
      - 字典：直接 JSON

    输出示例："generate_config; run_training; verify_artifacts; write_report"
    """
    formatted = []
    for tool in allowed_tools:
        if isinstance(tool, str):
            formatted.append(tool)
        elif is_dataclass(tool):
            formatted.append(json.dumps(asdict(tool), ensure_ascii=False))
        elif isinstance(tool, dict):
            formatted.append(json.dumps(tool, ensure_ascii=False))
        else:
            formatted.append(str(tool))
    return "; ".join(formatted)
