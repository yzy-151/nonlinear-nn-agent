"""
Agent Harness Runtime — 工具链执行引擎 ==================================

整个项目的"心脏"。负责：接到一个任务 → 逐个执行工具 → 产出事件流。

核心方法只有 30 行逻辑，但它封装了生产级 Agent Runtime 的所有关键行为：

  1. 加载/创建 session（支持断点续跑）
  2. 逐步执行工具链
  3. 每步产出 TraceEvent（start → tool_start → tool_end → metric → complete）
  4. 失败时写 error event 并终止
  5. 支持取消/中断
  6. Hook 机制（执行前后的可扩展回调）
  7. 工具输出自动合并到 session

设计边界：
  - Runtime 不知道工具怎么实现的，只调 ToolRegistry.run(call)
  - Runtime 不知道 planner 怎么决策的，只管执行
  - LLM 和 Runtime 完全解耦——Planner 出计划，Runtime 执行计划
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncIterator

from nonlinear_agent.control_plane import RuntimeControlPlane
from nonlinear_agent.hooks import HookManager
from nonlinear_agent.run_control import RunController
from nonlinear_agent.runtime_errors import ErrorType
from nonlinear_agent.session import SessionStore
from nonlinear_agent.tools import ToolCall, ToolRegistry
from nonlinear_agent.trace import TraceEvent, TraceLogger


DISPLAY_METRIC_NAMES = {
    "nmse_db",
    "baseline_nmse_db",
    "nmse_improvement_db",
    "parameter_count",
    "final_train_loss",
}


# ============================================================
# HarnessRequest — 一次执行请求（输入）
# ============================================================
@dataclass(frozen=True)
class HarnessRequest:
    """告诉 Runtime：跑什么、用哪个 session、从哪步开始。

    类比：给工厂的"生产工单"——产品编号、目标、工序清单、是否续做
    """

    session_id: str       # 会话 ID，用于加载/保存 session
    goal: str             # 实验目标描述，会写入 start event
    steps: list[ToolCall] # 要执行的工具列表，按顺序执行
    resume_from_step: int = 1  # 从第几步开始（1-based），大于 1 表示断点续跑


# ============================================================
# ExperimentHarnessRuntime — 运行时引擎（核心）
# ============================================================
class ExperimentHarnessRuntime:
    """工具链执行引擎。

    初始化时注入四个依赖（依赖注入，不是内部创建）：
      tool_registry  — 知道有哪些工具、怎么执行
      session_store  — 会话的读写
      trace_logger   — 事件日志的写入
      hooks          — 可选的扩展回调（before/after/error/metric）
      controller     — 取消/中断控制

    面试要点：
      这个设计体现了 "Runtime 是薄薄一层调度器" 的理念。
      它不做决策、不实现工具、不管理 prompt——只负责"按顺序安全执行工具并记录一切"。
    """

    def __init__(
        self,
        tool_registry: ToolRegistry,
        session_store: SessionStore,
        trace_logger: TraceLogger,
        hooks: HookManager | None = None,
        controller: RunController | None = None,
        control_plane: RuntimeControlPlane | None = None,
    ):
        self.tool_registry = tool_registry
        self.session_store = session_store
        self.trace_logger = trace_logger
        self.hooks = hooks or HookManager()
        self.controller = controller or RunController()
        self.control_plane = control_plane

    # ── 核心执行方法 ──────────────────────────────────────
    async def run(self, request: HarnessRequest) -> AsyncIterator[TraceEvent]:
        """执行工具链并流式产出事件。

        这是一个 async generator（异步生成器）：
          - 用 async for 消费事件 → 可以流式推送给 SSE / WebSocket
          - 用 async for + break → 可以在中途停止消费（但工具会继续执行完当前步骤）

        返回的 TraceEvent 类型顺序：
          start → tool_start → tool_end → (metrics...) → tool_start → ... → complete
          如果失败：start → tool_start → error（终止，不再执行后续步骤）
          如果取消：start → cancelled

        关键设计决策：
          - 每个 event 同时写入 session.history（内存）和 trace JSONL（磁盘）
          - 每个工具成功后立刻 save session（崩溃时最多丢失当前步骤）
          - 工具失败后立即终止，不执行后续步骤（fast-fail 策略）
        """

        # ── 第 1 步：加载或创建 session ──
        # 如果 session_id 对应的 JSON 文件已存在 → 加载（支持断点续跑）
        # 如果不存在 → 新建
        session = self.session_store.load_or_create(
            goal=request.goal, session_id=request.session_id
        )
        session.status = "running"

        # ── 第 2 步：发出 start event ──
        start_event = TraceEvent(
            session_id=request.session_id,
            event_type="start",
            status="running",
            payload={
                "goal": request.goal,
                "step_count": len(request.steps),
                "resume_from_step": request.resume_from_step,
            },
        )
        self._record(session, start_event)  # 同时写 session 和 trace
        yield start_event                   # 把事件推送给消费者（SSE / 调用方）

        # ── 第 3 步：逐个执行工具 ──
        for index, call in enumerate(request.steps, start=1):
            # 3a. 跳过已完成的步骤（断点续跑支持）
            if index < request.resume_from_step:
                continue

            # 3b. 检查是否被取消
            if self.controller.cancelled:
                cancelled_event = TraceEvent(
                    session_id=request.session_id,
                    event_type="cancelled",
                    step=f"step_{index}",
                    status="cancelled",
                    error=self.controller.reason,
                    error_type=ErrorType.CANCELLED.value,
                )
                session.status = "cancelled"
                session.errors.append(self.controller.reason)
                session.error_types.append(ErrorType.CANCELLED.value)
                self._record(session, cancelled_event)
                self.session_store.save(session)
                yield cancelled_event
                return  # 终止执行

            # 3c. 发出 tool_start event
            session.current_step = call.name
            step_name = f"step_{index}"
            before = TraceEvent(
                session_id=request.session_id,
                event_type="tool_start",
                step=step_name,
                tool=call.name,
                status="running",
                payload={"args": call.args},
            )
            await self.hooks.emit("before_tool", before)  # 执行前钩子
            self._record(session, before)
            yield before

            # 3d. 执行工具（核心）
            result = await self.tool_registry.run(call)

            # 3e. 工具执行失败 → 发出 error event → 终止后续步骤
            if result.status == "failed":
                error_event = TraceEvent(
                    session_id=request.session_id,
                    event_type="error",
                    step=step_name,
                    tool=call.name,
                    status="failed",
                    latency_ms=result.latency_ms,
                    payload={"attempts": result.attempts},
                    error=result.error,
                    error_type=result.error_type,
                )
                session.status = "failed"
                if result.error:
                    session.errors.append(result.error)
                if result.error_type:
                    session.error_types.append(result.error_type)
                await self.hooks.emit("on_error", error_event)
                self._record(session, error_event)
                self.session_store.save(session)
                yield error_event
                return  # fast-fail：一个工具失败，后续全不执行

            # 3f. 工具执行成功 → 发出 tool_end event
            end_event = TraceEvent(
                session_id=request.session_id,
                event_type="tool_end",
                step=step_name,
                tool=call.name,
                status="succeeded",
                latency_ms=result.latency_ms,
                payload={"attempts": result.attempts, "output": result.output},
            )
            # 把工具输出合并到 session（metrics、artifacts、context_summary）
            self._apply_tool_output(session, result.output)
            if index not in session.completed_steps:
                session.completed_steps.append(index)
            await self.hooks.emit("after_tool", end_event)
            self._record(session, end_event)
            self.session_store.save(session)
            yield end_event

            # 3g. 如果工具输出里有 metrics，只把关键指标单独发成 metric event。
            # 完整 metrics 仍保留在 tool_end.output 和 complete.metrics 中，前端可完整展示；
            # 这里过滤是为了避免 status/samples/model_type 等描述字段刷屏。
            for metric_name, metric_value in result.output.get("metrics", {}).items():
                if metric_name not in DISPLAY_METRIC_NAMES:
                    continue
                metric_event = TraceEvent(
                    session_id=request.session_id,
                    event_type="metric",
                    step=step_name,
                    tool=call.name,
                    status="succeeded",
                    payload={"name": metric_name, "value": metric_value},
                )
                await self.hooks.emit("on_metric", metric_event)
                self._record(session, metric_event)
                yield metric_event

        # ── 第 4 步：所有工具成功 → 发出 complete event ──
        session.status = "succeeded"
        complete = TraceEvent(
            session_id=request.session_id,
            event_type="complete",
            status="succeeded",
            payload={
                "metrics": session.metrics,     # 所有步骤累积的指标
                "artifacts": session.artifacts,  # 所有步骤产出的文件
            },
        )
        self._record(session, complete)
        self.session_store.save(session)
        yield complete

    # ── 内部方法 ─────────────────────────────────────────

    def _record(self, session, event: TraceEvent) -> None:
        """把事件同时写入三处：
          1. session.history（内存中，当前会话内快速查阅）
          2. trace JSONL 文件（磁盘上，永久归档和审计）
          3. control_plane events 表（SQLite，用于 SSE replay）
        """
        event_dict = event.to_dict()
        session.history.append(event_dict)
        self.trace_logger.log(event)
        if self.control_plane is not None:
            import json as _json
            self.control_plane.record_event(
                event.session_id,
                event.event_type,
                _json.dumps(event_dict, ensure_ascii=False, default=str),
            )

    def _apply_tool_output(self, session, output: dict) -> None:
        """把工具输出合并到 session。

        三种合并逻辑：
          metrics         → 合并到 session.metrics（字典更新，后来的覆盖先来的）
          artifacts       → 追加到 session.artifacts（去重）
          context_summary → 覆盖 session.context_summary（保留最新的一句话总结）
        """
        # 合并指标
        metrics = output.get("metrics", {})
        if isinstance(metrics, dict):
            session.metrics.update(metrics)

        # 追加产物文件路径（去重）
        artifacts = output.get("artifacts", [])
        if isinstance(artifacts, list):
            for artifact in artifacts:
                if artifact not in session.artifacts:
                    session.artifacts.append(str(artifact))

        # 更新上下文摘要
        context_summary = output.get("context_summary")
        if context_summary:
            session.context_summary = str(context_summary)
