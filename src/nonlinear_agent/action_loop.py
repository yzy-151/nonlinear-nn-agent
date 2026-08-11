"""Action-level agent loop: decide one tool, execute it, observe, repeat."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from nonlinear_agent.actions import validate_agent_action
from nonlinear_agent.memory.ports import MemoryBackend, MemoryItem, MemoryKind
from nonlinear_agent.planner import AgentActionPlanner
from nonlinear_agent.runtime import HarnessRequest
from nonlinear_agent.tools import ToolRegistry


RuntimeFactory = Callable[[str], Any]


@dataclass(frozen=True)
class ActionLoopResult:
    status: str
    planner_call_count: int
    history: list[dict[str, Any]] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    artifacts: list[str] = field(default_factory=list)
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0


class ActionPlannerLoop:
    """Run one guarded planner action after every tool observation."""

    def __init__(
        self,
        planner: AgentActionPlanner,
        tool_registry: ToolRegistry,
        runtime_factory: RuntimeFactory,
        session_id: str,
        constraints: dict[str, Any] | None = None,
        memory_backend: MemoryBackend | None = None,
        memory_kind: MemoryKind = MemoryKind.EPISODIC,
        planner_context_builder: Any | None = None,
    ):
        self.planner = planner
        self.tool_registry = tool_registry
        self.runtime_factory = runtime_factory
        self.session_id = session_id
        self.constraints = constraints or {}
        self.memory_backend = memory_backend
        self.memory_kind = memory_kind
        self.planner_context_builder = planner_context_builder

    async def run(self, goal: str, max_actions: int = 12) -> ActionLoopResult:
        history: list[dict[str, Any]] = []
        metrics: dict[str, Any] = {}
        artifacts: list[str] = []
        unresolved_failure_event_id: str | None = None
        planner_call_count = 0

        for action_index in range(1, max_actions + 1):
            planner_call_count += 1
            planner_call_id = f"action-planner-{planner_call_count:03d}"
            action = self.planner.plan(
                goal=goal,
                history=history,
                constraints=self._planning_constraints(goal),
            )

            if action.is_stop:
                return self._result(
                    "stopped", planner_call_count, history, metrics, artifacts
                )

            try:
                call = validate_agent_action(action, self.tool_registry)
                if (
                    unresolved_failure_event_id is not None
                    and unresolved_failure_event_id not in action.caused_by_event_ids
                ):
                    raise ValueError(
                        "Next action must reference unresolved failure event "
                        f"{unresolved_failure_event_id}."
                    )
            except ValueError as exc:
                history.append({
                    "action_id": action.action_id,
                    "planner_call_id": planner_call_id,
                    "round": action_index,
                    "tool_name": action.tool_name,
                    "arguments": dict(action.arguments),
                    "caused_by_event_ids": list(action.caused_by_event_ids),
                    "event_id": f"{action.action_id}:rejected",
                    "run_status": "rejected",
                    "error": str(exc),
                    "observation": {"error": str(exc)},
                })
                continue

            if call is None:
                return self._result(
                    "stopped", planner_call_count, history, metrics, artifacts
                )

            runtime = self.runtime_factory(self.session_id)
            status = "succeeded"
            error: str | None = None
            observation: dict[str, Any] = {}
            request = HarnessRequest(
                session_id=self.session_id,
                goal=goal,
                steps=[call],
            )
            async for event in runtime.run(request):
                if event.event_type == "tool_end":
                    output = event.payload.get("output", {})
                    if isinstance(output, dict):
                        observation.update(output)
                elif event.event_type == "metric":
                    name = event.payload.get("name")
                    if name:
                        metrics[str(name)] = event.payload.get("value")
                elif event.event_type == "complete":
                    complete_metrics = event.payload.get("metrics", {})
                    if isinstance(complete_metrics, dict):
                        metrics.update(complete_metrics)
                    complete_artifacts = event.payload.get("artifacts", [])
                    if isinstance(complete_artifacts, list):
                        for artifact in complete_artifacts:
                            if str(artifact) not in artifacts:
                                artifacts.append(str(artifact))
                elif event.event_type == "error":
                    status = "failed"
                    error = event.error or "Tool execution failed."
                    observation["error"] = error
                    observation["error_type"] = event.error_type

            event_id = f"{action.action_id}:{status}"
            history.append({
                "action_id": action.action_id,
                "planner_call_id": planner_call_id,
                "round": action_index,
                "tool_name": action.tool_name,
                "arguments": dict(action.arguments),
                "caused_by_event_ids": list(action.caused_by_event_ids),
                "event_id": event_id,
                "run_status": status,
                "error": error,
                "observation": observation,
            })
            if self.memory_backend is not None:
                self._write_memory(
                    action_index=action_index,
                    planner_call_id=planner_call_id,
                    action=action,
                    status=status,
                    event_id=event_id,
                    observation=observation,
                )

            if status == "failed":
                unresolved_failure_event_id = event_id
            elif (
                unresolved_failure_event_id is not None
                and unresolved_failure_event_id in action.caused_by_event_ids
            ):
                unresolved_failure_event_id = None

        return self._result(
            "max_actions_reached",
            planner_call_count,
            history,
            metrics,
            artifacts,
        )

    def _planning_constraints(self, goal: str) -> dict[str, Any]:
        """Add only top-k, provenance-rich context to the planner request."""
        constraints = dict(self.constraints)
        if self.planner_context_builder is None:
            return constraints
        namespace = (
            str(constraints.get("domain", "nonlinear-modeling")),
            str(constraints.get("dataset_hash", "unknown")),
            str(constraints.get("model_family", "unknown")),
        )
        context = self.planner_context_builder.build(
            query=goal, namespace=namespace, top_k=3
        )
        knowledge = []
        for scored in context.knowledge:
            chunk = getattr(scored, "chunk", scored)
            knowledge.append(
                {
                    "citation": str(getattr(chunk, "citation", "")),
                    "text": str(getattr(chunk, "text", ""))[:800],
                    "score": getattr(scored, "score", None),
                }
            )
        memory = [
            {
                "memory_id": item.memory_id,
                "kind": item.kind.value,
                "fact": item.fact,
                "evidence_refs": list(item.evidence_refs),
                "run_id": item.run_id,
                "confidence": item.confidence,
            }
            for item in context.memory
        ]
        constraints["retrieved_context"] = {
            "knowledge": knowledge,
            "memory": memory,
        }
        return constraints

    def _write_memory(
        self,
        action_index: int,
        planner_call_id: str,
        action: Any,
        status: str,
        event_id: str,
        observation: dict[str, Any],
    ) -> None:
        """Write one provenance-rich episodic memory record per action."""
        constraints = self.constraints
        fact = (
            f"{action.tool_name} {status}: "
            f"{json.dumps(observation, ensure_ascii=False)[:240]}"
        )
        client = getattr(self.planner, "llm_client", None)
        item = MemoryItem(
            memory_id=f"{self.session_id}-{action_index:03d}",
            kind=self.memory_kind,
            namespace=(
                str(constraints.get("domain", "nonlinear-modeling")),
                str(constraints.get("dataset_hash", "unknown")),
                str(constraints.get("model_family", "unknown")),
            ),
            fact=fact,
            evidence_refs=(event_id,),
            run_id=self.session_id,
            action_id=action.action_id,
            config_hash=constraints.get("config_hash"),
            dataset_hash=str(constraints.get("dataset_hash", "unknown")),
            metrics={
                key: value
                for key, value in observation.items()
                if isinstance(value, (int, float))
            },
            created_by_role="action_loop",
            model=str(getattr(client, "model", "unknown")),
            prompt_hash=planner_call_id,
            created_at=time.time(),
            confidence=1.0 if status == "succeeded" else 0.4,
        )
        self.memory_backend.write(item)

    def _result(
        self,
        status: str,
        planner_call_count: int,
        history: list[dict[str, Any]],
        metrics: dict[str, Any],
        artifacts: list[str],
    ) -> ActionLoopResult:
        client = getattr(self.planner, "llm_client", None)
        return ActionLoopResult(
            status=status,
            planner_call_count=planner_call_count,
            history=history,
            metrics=metrics,
            artifacts=artifacts,
            total_prompt_tokens=getattr(client, "total_prompt_tokens", 0),
            total_completion_tokens=getattr(client, "total_completion_tokens", 0),
        )
