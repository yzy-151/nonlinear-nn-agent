"""
Agent Planner Loop — 主循环 ==========================================

整个项目最重要的文件。实现了 Agent 的核心闭环：

  ┌─────────────────────────────────────────┐
  │  for round in max_rounds:               │
  │    plan = LLM.plan(goal, history)        │  ← Planner 决策
  │    for exp in plan.experiments:          │
  │      Guard 校验 → Runtime 执行            │  ← 安全执行
  │      history 记录结果                     │  ← 反馈积累
  │    reflection = reflect(round, results)   │  ← 结构化复盘
  └─────────────────────────────────────────┘
两种运行模式：
  run()           — CLI 模式，收集结果一次性返回
  run_streaming() — Web UI 模式，实时 yield 事件给 SSE（代码几乎相同）

三个退出条件（按优先级）：
  1. LLM 主动停止：plan.stop=True 且 experiments 为空
  2. 实验配额用完：executed >= max_experiments
  3. 轮数配额用完：rounds >= max_rounds

面试必讲：
  这不是固定 workflow——LLM 每轮根据目标、历史错误和指标重新决定策略。
  Planner 和 Runtime 完全分离：Planner 出计划，Runtime 执行计划，Guard 在中间拦截。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Callable, TYPE_CHECKING

from nonlinear_agent.context_memory import HistoryCompressor
from nonlinear_agent.planner import ExperimentPlanner
from nonlinear_agent.planner_validation import validate_planned_overrides
from nonlinear_agent.reflection import ReflectionPolicy
from nonlinear_agent.run_artifacts import RunArtifactWriter, default_run_dir
from nonlinear_agent.runtime import HarnessRequest
from nonlinear_agent.server import HarnessRunSpec, build_harness_request, build_runtime

if TYPE_CHECKING:
    from nonlinear_agent.domains.base import DomainPlugin


# ============================================================
# PlannerLoopResult — 一次完整 Agent Loop 的最终结果
# ============================================================
@dataclass(frozen=True)
class PlannerLoopResult:
    """Agent Loop 结束后产出的结构化结果。

    status     — 退出原因：stopped / max_rounds_reached / max_experiments_reached / planner_error
    rounds     — 实际跑了几轮
    history    — 每轮每个实验的记录（含 rejected/failed/succeeded + NMSE 等）
    summaries  — 每轮 LLM 的策略概述
    reflections — 每轮的事实复盘记录（failure_causes / facts）

    这个对象会被 RunArtifactWriter 落盘为 result.json 和 leaderboard.csv。
    """
    status: str
    rounds: int
    history: list[dict[str, Any]] = field(default_factory=list)
    summaries: list[str] = field(default_factory=list)
    reflections: list[dict[str, Any]] = field(default_factory=list)


# runtime_factory 的类型：给定 session_id，返回一个 ExperimentHarnessRuntime
RuntimeFactory = Callable[[str], Any]

# ============================================================
# ExperimentPlannerLoop — 主循环（核心）
# ============================================================
class ExperimentPlannerLoop:
    """Agent 实验规划主循环。

    把 Planner、Guard、Runtime、History、Reflection、Artifacts 串在一起。

    依赖注入的组件：
      planner            — LLM 计划器（Fake 或 DeepSeek）
      runtime_factory    — 每次实验创建一个新的 Runtime 实例
      history_compressor — 历史压缩器（太多记录时压缩后再给 LLM）
      reflection_policy  — 每轮结束后的复盘策略
      artifact_writer    — 落盘 plans/、reflections/、result.json
    """

    def __init__(
        self,
        planner: ExperimentPlanner,
        workspace: Path | str,
        runtime_factory: RuntimeFactory | None = None,
        base_config: str | None = None,
        constraints: dict[str, Any] | None = None,
        timeout_seconds: float = 300.0,
        artifact_dir: Path | str | None = None,
        history_compressor: HistoryCompressor | None = None,
        reflection_policy: ReflectionPolicy | None = None,
        domain: DomainPlugin | None = None,
    ):
        self.planner = planner
        self.workspace = Path(workspace)
        self.domain = domain
        # 如果没有传 runtime_factory，默认用 build_runtime 创建
        self.runtime_factory = runtime_factory or (
            lambda session_id: build_runtime(
                self.workspace, session_id=session_id, timeout_seconds=timeout_seconds,
                domain=domain,
            )
        )
        self.base_config = base_config or (
            domain.default_base_config() if domain is not None
            else "configs/baselines/lstsq-complexmp-o12-m150.yaml"
        )
        self.constraints = constraints or (
            domain.default_constraints() if domain is not None
            else {"parameter_count_max": 4000, "metric": "nmse_db"}
        )
        self.timeout_seconds = timeout_seconds
        self.artifact_writer = RunArtifactWriter(
            artifact_dir or default_run_dir(self.workspace)
        )
        self.history_compressor = history_compressor or HistoryCompressor()
        self.reflection_policy = reflection_policy or ReflectionPolicy()

    # ================================================================
    # run() — CLI 模式（收集结果，一次性返回）
    # ================================================================
    async def run(
        self,
        goal: str,
        max_rounds: int = 3,
        max_experiments: int | None = None,
    ) -> PlannerLoopResult:
        """执行完整 Agent Loop，返回最终结果。

        用于 CLI（python agent.py run）和 Benchmark。
        如果需要实时事件流（Web UI），用 run_streaming()。
        """
        history: list[dict[str, Any]] = []    # 所有实验的完整记录
        summaries: list[str] = []              # 每轮 LLM 的策略概述
        reflections: list[dict[str, Any]] = [] # 每轮的复盘记录
        rounds = 0
        executed_experiments = 0              # 已执行的实验数（不含 rejected）

        for _ in range(max_rounds):
            rounds += 1
            round_records: list[dict[str, Any]] = []  # 本轮的所有记录

            # ── 第 1 步：LLM 出计划 ──
            # 给 LLM 的不是全量 history，而是压缩后的版本（summary + 最近 N 条）
            prompt_history = self.history_compressor.build_prompt_history(history)
            plan = self.planner.plan(
                goal=goal, history=prompt_history, constraints=self.constraints
            )
            summaries.append(plan.summary)
            self.artifact_writer.write_plan(rounds, plan)  # 落盘 plans/round-XXX.json

            # ── 退出条件 1：LLM 说停 ──
            if plan.stop and not plan.experiments:
                result = PlannerLoopResult(
                    status="stopped",
                    rounds=rounds,
                    history=history,
                    summaries=summaries,
                    reflections=reflections,
                )
                self.artifact_writer.write_result(result)
                return result

            # ── 第 2 步：逐个执行实验 ──
            for experiment in plan.experiments:
                # ── 退出条件 2：实验配额用完 ──
                if max_experiments is not None and executed_experiments >= max_experiments:
                    result = PlannerLoopResult(
                        status="max_experiments_reached",
                        rounds=rounds,
                        history=history,
                        summaries=summaries,
                        reflections=reflections,
                    )
                    self.artifact_writer.write_result(result)
                    return result

                # ── Guard 校验 ──
                # LLM 的输出不可信——先过 Schema Guard
                # 被拒 = 不消耗实验配额，直接记入 history
                try:
                    overrides = validate_planned_overrides(
                        experiment.overrides,
                        parameter_count_max=self.constraints.get("parameter_count_max"),
                        domain=getattr(self, "domain", None),
                    )
                except ValueError as exc:
                    history.append({
                        "id": experiment.experiment_id,
                        "reason": experiment.reason,
                        "run_status": "rejected",
                        "error": str(exc),
                    })
                    round_records.append(history[-1])
                    continue  # 跳过，下一个实验

                # ── 执行实验 ──
                # Guard 通过 → 交给 Runtime 执行完整的工具链
                metrics = await self._run_experiment(
                    experiment.experiment_id, overrides
                )
                executed_experiments += 1
                record = {
                    "id": experiment.experiment_id,
                    "reason": experiment.reason,
                    **metrics,  # 包含 run_status / nmse_db / error 等
                }
                history.append(record)
                round_records.append(record)

            # ── 第 3 步：复盘 ──
            # 本轮至少有一个实验被处理过（rejected 也算），生成 reflection
            if round_records:
                reflection = self.reflection_policy.reflect(
                    round_index=rounds, round_records=round_records,
                    primary_metric=self.domain.primary_metric() if self.domain else "nmse_db",
                    lower_is_better=self.domain.display_metric_lower_is_better() if self.domain else True,
                )
                reflections.append(reflection)
                history.append(_build_reflection_history_record(reflection))
                self.artifact_writer.write_reflection(reflection)

        # ── 退出条件 3：轮数用完 ──
        result = PlannerLoopResult(
            status="max_rounds_reached",
            rounds=rounds,
            history=history,
            summaries=summaries,
            reflections=reflections,
        )
        self.artifact_writer.write_result(result)
        return result

    # ================================================================
    # run_streaming() — Web UI 模式（实时 yield 事件给 SSE）
    # ================================================================
    async def run_streaming(
        self,
        goal: str,
        max_rounds: int = 3,
        max_experiments: int | None = None,
    ) -> "AsyncIterator[dict[str, Any]]":
        """和 run() 逻辑完全相同，但每步实时 yield 事件。

        事件类型：
          agent_start       — Agent Loop 启动
          round_start       — 新的一轮开始
          plan_generated    — LLM 出计划了
          experiment_start  — 开始执行一个实验
          runtime_event     — Runtime 的工具执行事件（透传）
          experiment_end    — 实验执行完毕
          experiment_rejected — Guard 拦截
          reflection        — 本轮复盘
          loop_complete     — Agent Loop 结束
        """
        history: list[dict[str, Any]] = []
        reflections: list[dict[str, Any]] = []
        rounds = 0
        executed = 0

        domain_config: dict[str, Any] = {}
        if self.domain is not None:
            domain_config = {
                "display_metric_unit": self.domain.display_metric_unit(),
                "display_metric_lower_is_better": self.domain.display_metric_lower_is_better(),
                "artifact_preview_patterns": self.domain.artifact_preview_patterns(),
                "display_metric_names": list(self.domain.display_metric_names()),
                "primary_metric": self.domain.primary_metric(),
            }

        yield {
            "type": "agent_start",
            "goal": goal,
            "max_rounds": max_rounds,
            "max_experiments": max_experiments or "unlimited",
            **domain_config,
        }

        for _ in range(max_rounds):
            rounds += 1
            round_records: list[dict[str, Any]] = []

            yield {"type": "round_start", "round": rounds}

            # ── LLM 出计划（带异常保护：LLM 挂了也能优雅退出）──
            prompt_history = self.history_compressor.build_prompt_history(history)
            try:
                plan = self.planner.plan(
                    goal=goal, history=prompt_history, constraints=self.constraints
                )
            except Exception as exc:
                # LLM 调用失败 → 保存已有结果，优雅退出
                yield {"type": "error", "message": f"LLM planner failed: {exc}"}
                result = PlannerLoopResult(
                    status="planner_error",
                    rounds=rounds,
                    history=history,
                    reflections=reflections,
                )
                self.artifact_writer.write_result(result)
                yield {
                    "type": "loop_complete",
                    "status": "planner_error",
                    "rounds": rounds,
                    "history_count": len(history),
                    "error": str(exc),
                }
                return

            self.artifact_writer.write_plan(rounds, plan)

            # 把计划告诉前端
            yield {
                "type": "plan_generated",
                "round": rounds,
                "summary": plan.summary,
                "stop": plan.stop,
                "experiment_count": len(plan.experiments),
                "previous_reflection_facts": _latest_reflection_facts(history),
                "previous_reflection_failure_causes": _latest_reflection_failure_causes(history),
                "experiments": [
                    {"id": e.experiment_id, "reason": e.reason}
                    for e in plan.experiments
                ],
            }

            # 退出条件 1：LLM 说停
            if plan.stop and not plan.experiments:
                result = PlannerLoopResult(
                    status="stopped",
                    rounds=rounds,
                    history=history,
                    reflections=reflections,
                )
                self.artifact_writer.write_result(result)
                yield {
                    "type": "loop_complete",
                    "status": "stopped",
                    "rounds": rounds,
                    "history_count": len(history),
                }
                return

            # ── 逐个执行实验 ──
            for experiment in plan.experiments:
                # 退出条件 2：配额用完
                if max_experiments is not None and executed >= max_experiments:
                    result = PlannerLoopResult(
                        status="max_experiments_reached",
                        rounds=rounds,
                        history=history,
                        reflections=reflections,
                    )
                    self.artifact_writer.write_result(result)
                    yield {
                        "type": "loop_complete",
                        "status": "max_experiments",
                        "rounds": rounds,
                        "history_count": len(history),
                    }
                    return

                yield {
                    "type": "experiment_start",
                    "id": experiment.experiment_id,
                    "reason": experiment.reason,
                }

                # Guard 校验
                try:
                    overrides = validate_planned_overrides(
                        experiment.overrides,
                        parameter_count_max=self.constraints.get("parameter_count_max"),
                        domain=getattr(self, "domain", None),
                    )
                except ValueError as exc:
                    record = {
                        "id": experiment.experiment_id,
                        "reason": experiment.reason,
                        "run_status": "rejected",
                        "error": str(exc),
                    }
                    history.append(record)
                    round_records.append(record)
                    yield {
                        "type": "experiment_rejected",
                        "id": experiment.experiment_id,
                        "error": str(exc),
                    }
                    continue

                # ── 执行实验（实时透传 Runtime 事件）──
                metrics: dict[str, Any] = {"run_status": "succeeded"}
                output_dir = str(
                    overrides.get("output_dir", f"reports/{experiment.experiment_id}")
                )
                if self.domain is not None:
                    spec = self.domain.build_harness_spec(
                        session_id=experiment.experiment_id,
                        base_config=self.base_config,
                        overrides=overrides,
                        constraints=self.constraints,
                        timeout_seconds=self.timeout_seconds,
                    )
                    request = HarnessRequest(
                        session_id=experiment.experiment_id,
                        goal=f"Run experiment {experiment.experiment_id}",
                        steps=self.domain.build_harness_steps(spec, self.workspace),
                    )
                else:
                    spec = HarnessRunSpec(
                        session_id=experiment.experiment_id,
                        base_config=self.base_config,
                        output_dir=output_dir,
                        epochs=int(overrides.get("epochs", 0)),
                        learning_rate=float(overrides.get("learning_rate", 0.0008)),
                        optimizer=str(overrides.get("optimizer", "adam")),
                        nmse_threshold_db=float(
                            overrides.get(
                                "nmse_threshold_db",
                                self.constraints.get("nmse_threshold_db", -35.0),
                            )
                        ),
                        timeout_seconds=self.timeout_seconds,
                        overrides=overrides,
                    )
                    request = build_harness_request(spec)
                runtime = self.runtime_factory(experiment.experiment_id)

                # 把 Runtime 的每个事件直接推给前端
                async for event in runtime.run(request):
                    yield {"type": "runtime_event", "event": event.to_dict()}
                    if event.event_type == "metric":
                        name = event.payload.get("name")
                        if name:
                            metrics[str(name)] = event.payload.get("value")
                    elif event.event_type == "error":
                        metrics["run_status"] = "failed"
                        metrics["error"] = event.error
                        metrics["error_type"] = event.error_type

                executed += 1
                record = {
                    "id": experiment.experiment_id,
                    "reason": experiment.reason,
                    **metrics,
                }
                history.append(record)
                round_records.append(record)
                yield {
                    "type": "experiment_end",
                    "id": experiment.experiment_id,
                    "metrics": metrics,
                }

            # ── 复盘 ──
            if round_records:
                reflection = self.reflection_policy.reflect(
                    round_index=rounds, round_records=round_records,
                    primary_metric=self.domain.primary_metric() if self.domain else "nmse_db",
                    lower_is_better=self.domain.display_metric_lower_is_better() if self.domain else True,
                )
                reflections.append(reflection)
                history.append(_build_reflection_history_record(reflection))
                self.artifact_writer.write_reflection(reflection)
                yield {
                    "type": "reflection",
                    "round": rounds,
                    "reflection": reflection,
                }

        # 退出条件 3：轮数用完
        result = PlannerLoopResult(
            status="max_rounds_reached",
            rounds=rounds,
            history=history,
            reflections=reflections,
        )
        self.artifact_writer.write_result(result)
        yield {
            "type": "loop_complete",
            "status": "max_rounds",
            "rounds": rounds,
            "history_count": len(history),
            "summary": result.__dict__,
        }

    # ================================================================
    # _run_experiment — 执行单个实验（run() 专用）
    # ================================================================
    async def _run_experiment(
        self, experiment_id: str, overrides: dict[str, Any]
    ) -> dict[str, Any]:
        """构造 HarnessRequest → 调 Runtime → 收集指标。

        run() 用这个方法，run_streaming() 内联了相同的逻辑
        （因为 streaming 需要 yield 中间事件，不能直接 return）。
        """
        output_dir = str(overrides.get("output_dir", f"reports/{experiment_id}"))
        if self.domain is not None:
            spec = self.domain.build_harness_spec(
                session_id=experiment_id,
                base_config=self.base_config,
                overrides=overrides,
                constraints=self.constraints,
                timeout_seconds=self.timeout_seconds,
            )
            request = HarnessRequest(
                session_id=experiment_id,
                goal=f"Run experiment {experiment_id}",
                steps=self.domain.build_harness_steps(spec, self.workspace),
            )
        else:
            spec = HarnessRunSpec(
                session_id=experiment_id,
                base_config=self.base_config,
                output_dir=output_dir,
                epochs=int(overrides.get("epochs", 0)),
                learning_rate=float(overrides.get("learning_rate", 0.0008)),
                optimizer=str(overrides.get("optimizer", "adam")),
                nmse_threshold_db=float(
                    overrides.get(
                        "nmse_threshold_db",
                        self.constraints.get("nmse_threshold_db", -35.0),
                    )
                ),
                timeout_seconds=self.timeout_seconds,
                overrides=overrides,
            )
            request = build_harness_request(spec)
        runtime = self.runtime_factory(experiment_id)

        metrics: dict[str, Any] = {"run_status": "succeeded"}
        async for event in runtime.run(request):
            if event.event_type == "metric":
                name = event.payload.get("name")
                if name:
                    metrics[str(name)] = event.payload.get("value")
            elif event.event_type == "error":
                metrics["run_status"] = "failed"
                metrics["error"] = event.error
                metrics["error_type"] = event.error_type

        return metrics


def _build_reflection_history_record(reflection: dict[str, Any]) -> dict[str, Any]:
    round_index = int(reflection.get("round", 0))
    # Find the dynamic best_* key (e.g. best_nmse_db, best_val_mse)
    best_value = None
    for key in reflection:
        if key.startswith("best_") and key not in ("best_experiment_id",):
            best_value = reflection.get(key)
            break

    return {
        "id": f"reflection-round-{round_index:03d}",
        "run_status": "reflection",
        "round": round_index,
        "status_counts": reflection.get("status_counts", {}),
        "failure_causes": reflection.get("failure_causes", []),
        "facts": reflection.get("facts", []),
        "best_experiment_id": reflection.get("best_experiment_id", ""),
        "best_nmse_db": best_value,  # kept for backward compat; key is dynamic in reflection
        "context_summary": (
            f"Reflection round {round_index}: "
            f"facts={reflection.get('facts', [])}; "
            f"failure_causes={reflection.get('failure_causes', [])}"
        ),
    }


def _latest_reflection_facts(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for record in reversed(history):
        if record.get("run_status") == "reflection":
            facts = record.get("facts", [])
            return facts if isinstance(facts, list) else []
    return []


def _latest_reflection_failure_causes(history: list[dict[str, Any]]) -> list[str]:
    for record in reversed(history):
        if record.get("run_status") == "reflection":
            causes = record.get("failure_causes", [])
            return [str(cause) for cause in causes] if isinstance(causes, list) else []
    return []
