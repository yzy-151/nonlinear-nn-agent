from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncIterator

from nonlinear_agent.hooks import HookManager
from nonlinear_agent.run_control import RunController
from nonlinear_agent.runtime_errors import ErrorType
from nonlinear_agent.session import SessionStore
from nonlinear_agent.tools import ToolCall, ToolRegistry
from nonlinear_agent.trace import TraceEvent, TraceLogger


@dataclass(frozen=True)
class HarnessRequest:
    session_id: str
    goal: str
    steps: list[ToolCall]
    resume_from_step: int = 1


class ExperimentHarnessRuntime:
    def __init__(
        self,
        tool_registry: ToolRegistry,
        session_store: SessionStore,
        trace_logger: TraceLogger,
        hooks: HookManager | None = None,
        controller: RunController | None = None,
    ):
        self.tool_registry = tool_registry
        self.session_store = session_store
        self.trace_logger = trace_logger
        self.hooks = hooks or HookManager()
        self.controller = controller or RunController()

    async def run(self, request: HarnessRequest) -> AsyncIterator[TraceEvent]:
        session = self.session_store.load_or_create(goal=request.goal, session_id=request.session_id)
        session.status = "running"
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
        self._record(session, start_event)
        yield start_event

        for index, call in enumerate(request.steps, start=1):
            if index < request.resume_from_step:
                continue
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
                return
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
            await self.hooks.emit("before_tool", before)
            self._record(session, before)
            yield before

            result = await self.tool_registry.run(call)
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
                return

            end_event = TraceEvent(
                session_id=request.session_id,
                event_type="tool_end",
                step=step_name,
                tool=call.name,
                status="succeeded",
                latency_ms=result.latency_ms,
                payload={"attempts": result.attempts, "output": result.output},
            )
            self._apply_tool_output(session, result.output)
            if index not in session.completed_steps:
                session.completed_steps.append(index)
            await self.hooks.emit("after_tool", end_event)
            self._record(session, end_event)
            self.session_store.save(session)
            yield end_event

            for metric_name, metric_value in result.output.get("metrics", {}).items():
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

        session.status = "succeeded"
        complete = TraceEvent(
            session_id=request.session_id,
            event_type="complete",
            status="succeeded",
            payload={"metrics": session.metrics, "artifacts": session.artifacts},
        )
        self._record(session, complete)
        self.session_store.save(session)
        yield complete

    def _record(self, session, event: TraceEvent) -> None:
        event_dict = event.to_dict()
        session.history.append(event_dict)
        self.trace_logger.log(event)

    def _apply_tool_output(self, session, output: dict) -> None:
        metrics = output.get("metrics", {})
        if isinstance(metrics, dict):
            session.metrics.update(metrics)
        artifacts = output.get("artifacts", [])
        if isinstance(artifacts, list):
            for artifact in artifacts:
                if artifact not in session.artifacts:
                    session.artifacts.append(str(artifact))
        context_summary = output.get("context_summary")
        if context_summary:
            session.context_summary = str(context_summary)

