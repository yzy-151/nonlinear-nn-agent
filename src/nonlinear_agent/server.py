"""
FastAPI SSE 服务层 ====================================================

整个项目的"交付面"。把 Agent Harness 的所有能力暴露为 HTTP 接口。

五个端点（3 个 POST + 2 个 GET）：
  GET  /                          — 浏览器首页（三 Tab 操作面板）
  GET  /health                    — 健康检查
  GET  /diagnostics/{name}       — 静态文件服务（dashboard HTML/MD）
  POST /runs/{session_id}/events — Fixed Workflow 执行（SSE 流）
  POST /agent/{session_id}/events — LLM Agent Planner Loop（SSE 流）
  POST /benchmark/events         — Benchmark 评估（SSE 流）

三个 POST 端点都返回 SSE（Server-Sent Events），浏览器可以实时看到：
  event: tool_start
  data: {"session_id":"exp001","event_type":"tool_start",...}

设计要点：
  - FastAPI + uvicorn 提供 HTTP 服务（可选依赖，核心测试不需要）
  - 所有端点返回 StreamingResponse（text/event-stream）
  - Agent 和 Benchmark 完成后自动刷新 dashboard
  - .env.local 自动加载，不需要手动 export DEEPSEEK_API_KEY

面试要点：
  这个文件展示了"把 Agent Runtime 包装成 Web 服务"的工程能力——
  CLI 和 Web UI 共用同一套 Planner + Runtime + Tools，只是交付面不同。
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Dict, Optional

# Per-session cancel events: set by POST /cancel/{session_id}, checked by streaming loops
_cancel_events: dict[str, asyncio.Event] = {}


# ============================================================
# .env.local 加载
# ============================================================
def _load_dotenv(workspace: Path) -> None:
    """把 .env.local 里的 key=value 加载到 os.environ。

    只加载 os.environ 中还不存在的 key（已设置的环境变量优先级更高）。
    支持 # 注释行和空行。

    为什么不用 python-dotenv 库？
      → 减少依赖。.env.local 格式很简单（KEY=VALUE），20 行代码搞定。
    """
    path = Path(workspace) / ".env.local"
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


from nonlinear_agent.artifact_paths import trial_config_path
from nonlinear_agent.experiment_tools import build_experiment_tool_registry
from nonlinear_agent.replay import write_replay_report
from nonlinear_agent.runtime import ExperimentHarnessRuntime, HarnessRequest
from nonlinear_agent.session import SessionStore
from nonlinear_agent.tools import ToolCall
from nonlinear_agent.trace import TraceEvent, TraceLogger
from nonlinear_agent.web_ui import WEB_ASSETS, read_web_asset, render_home_page


# ============================================================
# Fake Planner 的预设回复（Agent 模式离线用）
# ============================================================
BUILTIN_FAKE_PLANS = [
    # 第 1 轮：跑 complex_lstsq 最优候选
    (
        '{"summary":"Run the best lightweight complex MP least-squares candidate.","stop":false,'
        '"experiments":[{"id":"planner-demo-001","reason":"Validate the LLM-planned loop on the known best '
        'under-4000-parameter configuration.","overrides":{"output_dir":"reports/planner-demo-001",'
        '"model_type":"complex_lstsq","feature_mode":"complex_mp","memory_depth":150,'
        '"mp_order_count":12,"epochs":0}}]}'
    ),
    # 第 2 轮：主动停止
    '{"summary":"stop after demo run.","stop":true,"experiments":[]}',
]


# ============================================================
# HarnessRunSpec — Fixed Workflow 的请求参数
# ============================================================
@dataclass(frozen=True)
class HarnessRunSpec:
    """描述一次 Fixed Workflow 运行的所有参数。

    这些参数来自浏览器表单 → JSON body → 解包传入。
    字段含义和 Agent 表单里的基本一致，但这里是"直接执行"而非"让 LLM 规划"。
    """
    session_id: str
    goal: str = "Run nonlinear NN experiment through the Agent Harness streaming runtime."
    base_config: str = "configs/baselines/lstsq-complexmp-o12-m150.yaml"
    output_dir: str | None = None
    epochs: int = 0
    learning_rate: float = 0.0008
    optimizer: str = "adam"
    nmse_threshold_db: float = -35.0
    timeout_seconds: float = 300.0
    overrides: dict[str, Any] = field(default_factory=dict)


# ============================================================
# build_harness_request — Spec → HarnessRequest
# ============================================================
def build_harness_request(spec: HarnessRunSpec) -> HarnessRequest:
    """把 HarnessRunSpec 转成 Runtime 能执行的 HarnessRequest。

    硬编码了 4 步 Fixed Workflow 工具链：
      1. generate_config  — 根据 base + overrides 生成 YAML 配置
      2. run_training      — 调用 train.py 执行训练
      3. verify_artifacts  — 检查 NMSE 达标 + PSD 存在
      4. write_report      — 生成 Markdown 报告

    这是 Fixed Workflow 的唯一定义处——如果需要改工具链顺序，改这里就行。
    """
    output_dir = spec.output_dir or f"reports/{spec.session_id}"
    overrides = {
        "output_dir": output_dir,
        "epochs": spec.epochs,
        "learning_rate": spec.learning_rate,
        "optimizer": spec.optimizer,
    }
    overrides.update(spec.overrides)
    overrides["output_dir"] = output_dir  # 确保 output_dir 不被 overrides 覆盖

    return HarnessRequest(
        session_id=spec.session_id,
        goal=spec.goal,
        steps=[
            # Step 1: 生成配置文件
            ToolCall(
                name="generate_config",
                args={
                    "base_config_path": spec.base_config,
                    "experiment_id": spec.session_id,
                    "overrides": overrides,
                },
            ),
            # Step 2: 执行训练（timeout 比训练超时多 5 秒，给 subprocess 缓冲）
            ToolCall(
                name="run_training",
                args={
                    "config_path": str(trial_config_path(spec.session_id, spec.session_id)),
                    "timeout_seconds": spec.timeout_seconds,
                },
                timeout_seconds=spec.timeout_seconds + 5,
            ),
            # Step 3: 验证结果
            ToolCall(
                name="verify_artifacts",
                args={
                    "output_dir": output_dir,
                    "nmse_threshold_db": spec.nmse_threshold_db,
                },
            ),
            # Step 4: 写报告
            ToolCall(name="write_report", args={"session_id": spec.session_id}),
        ],
    )


# ============================================================
# SSE 编码
# ============================================================
# Per-session monotonic event ID counter for SSE id: field
_session_event_counters: dict[str, int] = {}

def _next_event_id(session_id: str) -> int:
    current = _session_event_counters.get(session_id, 0)
    _session_event_counters[session_id] = current + 1
    return current + 1

HEARTBEAT_SSE = ": heartbeat\n\n"


async def _heartbeat_producer(
    interval_seconds: float = 15.0,
) -> AsyncIterator[str]:
    """Yield SSE heartbeat comments at regular intervals.

    Used as a background task alongside the main event stream so
    the client knows the connection is still alive during long
    training runs.
    """
    while True:
        await asyncio.sleep(interval_seconds)
        yield HEARTBEAT_SSE


async def _merge_with_heartbeat(
    main_stream: AsyncIterator[str],
    interval_seconds: float = 15.0,
) -> AsyncIterator[str]:
    """Merge a main SSE stream with periodic heartbeats.

    Heartbeats are only sent when no main event has been yielded
    for `interval_seconds`. The heartbeat task is cancelled when
    the main stream ends.
    """
    import asyncio
    last_event_time = asyncio.get_event_loop().time()
    heartbeat_task: asyncio.Task | None = None

    async def heartbeat_loop(queue: asyncio.Queue) -> None:
        while True:
            await asyncio.sleep(interval_seconds)
            await queue.put(HEARTBEAT_SSE)

    queue: asyncio.Queue = asyncio.Queue()
    heartbeat_task = asyncio.ensure_future(heartbeat_loop(queue))

    try:
        async for chunk in main_stream:
            last_event_time = asyncio.get_event_loop().time()
            # Drain any pending heartbeats
            while not queue.empty():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
            yield chunk
        # Drain one final heartbeat if needed, then cancel
    finally:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass

def encode_sse_event(
    event: TraceEvent,
    event_id: int | None = None,
) -> str:
    """Encode a TraceEvent as SSE with optional id: field (v2.0)."""
    lines: list[str] = []
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event.event_type}")
    lines.append(f"data: {json.dumps(event.to_dict(), ensure_ascii=False, default=str)}")
    lines.append("")
    lines.append("")  # trailing blank line per SSE spec
    return "\n".join(lines)


def encode_replayed_sse_event(event: dict) -> str:
    """Encode a persisted {id, event, data} event as SSE for replay."""
    data = json.dumps(event.get("data", {}), ensure_ascii=False, default=str)
    return f"id: {event['id']}\nevent: {event['event']}\ndata: {data}\n\n\n"


async def stream_sse_events(
    runtime: ExperimentHarnessRuntime,
    request: HarnessRequest,
    last_event_id: int | None = None,
) -> AsyncIterator[str]:
    """把 Runtime 的事件流转为 SSE 字符串流，支持 Last-Event-ID 恢复。

    当客户端提供 last_event_id 时，先重放控制平面中已持久化的事件，
    再继续实时事件流，保证断线重连不丢失事件。
    """
    if last_event_id is not None and runtime.control_plane is not None:
        replayed = runtime.control_plane.get_events_since(
            request.session_id, last_event_id
        )
        for event in replayed:
            yield encode_replayed_sse_event(event)
            _session_event_counters[request.session_id] = max(
                _session_event_counters.get(request.session_id, 0),
                int(event["id"]),
            )
    async for event in runtime.run(request):
        yield encode_sse_event(event, event_id=_next_event_id(request.session_id))


# ============================================================
# build_runtime — 创建 Runtime 实例
# ============================================================
def build_runtime(
    workspace: Path | str,
    session_id: str,
    timeout_seconds: float = 300.0,
    domain: DomainPlugin | None = None,
    control_plane: Any = None,
) -> ExperimentHarnessRuntime:
    """装配一个完整的 Runtime 实例（ToolRegistry + SessionStore + TraceLogger）。

    每次 Agent Loop 的实验都会创建一个新的 Runtime 实例（新的 trace 文件），
    如果提供了 domain，使用 domain 的工具注册中心和显示指标名。
    """
    root = Path(workspace)
    if domain is not None:
        tool_registry = domain.build_tool_registry(root, default_timeout_seconds=timeout_seconds)
        display_names = domain.display_metric_names()
    else:
        tool_registry = build_experiment_tool_registry(root, default_timeout_seconds=timeout_seconds)
        display_names = None

    return ExperimentHarnessRuntime(
        tool_registry=tool_registry,
        session_store=SessionStore(root / "sessions"),
        trace_logger=TraceLogger(root / "traces" / f"{session_id}.jsonl"),
        display_metric_names=display_names,
        control_plane=control_plane,
    )


# ============================================================
# stream_agent_events — Agent Planner Loop 的 SSE 流
# ============================================================
async def stream_agent_events(
    workspace: Path | str,
    session_id: str,
    provider: str = "fake",
    goal: str = "",
    max_rounds: int = 2,
    max_experiments: int | None = None,
    base_config: str = "configs/baselines/lstsq-complexmp-o12-m150.yaml",
    parameter_count_max: int = 4000,
    nmse_threshold_db: float = -35.0,
    timeout_seconds: float = 300.0,
    artifact_dir: str | None = None,
    fake_plan: str | None = None,
    domain_name: str | None = None,
    enabled_fields: list[str] | None = None,
    allowed_models: list[str] | None = None,
    data_file: str | None = None,
):
    """Agent Planner Loop 的完整 SSE 流。

    流程：
      1. 根据 provider 创建 LLM（Fake 或 DeepSeek）
      2. 创建 ExperimentPlannerLoop
      3. 调用 run_streaming() 获取事件流
      4. 把 agent 事件转成 SSE TraceEvent（runtime_event 直接透传）
      5. 异常时 yield error event，不崩溃

    面试要点：
      这就是 plan → validate → execute → observe → reflect 在 Web 层的实现。
      前端看到的事件流就是从这里产出的。
    """
    from nonlinear_agent.llm import FakeLLMClient, OpenAICompatibleClient
    from nonlinear_agent.loop import ExperimentPlannerLoop
    from nonlinear_agent.planner import ExperimentPlanner

    root = Path(workspace)
    _load_dotenv(root)  # 加载 .env.local（DeepSeek API Key）

    # ── 注册 cancel event ──
    cancel_evt = asyncio.Event()
    _cancel_events[session_id] = cancel_evt
    cancelled = False
    try:
        # ── 创建 LLM Client ──
        if provider == "fake":
            responses: list[str] = []
            if fake_plan:
                responses.append(fake_plan)
            else:
                responses.extend(BUILTIN_FAKE_PLANS)
            llm = FakeLLMClient(responses=responses)
        elif provider == "deepseek":
            llm = OpenAICompatibleClient.deepseek(timeout_seconds=180.0)
        else:
            yield encode_sse_event(TraceEvent(
                session_id=session_id, event_type="error", status="failed",
                error=f"Unknown provider: {provider}",
            ))
            return

        # ── 加载 domain（空/未知 → 默认非线性建模，保证 prompt 契约）──
        domain = _load_domain(domain_name)
        if enabled_fields is not None or allowed_models is not None:
            from nonlinear_agent.domains.filtered import FilteredDomain

            selected_fields = (
                list(enabled_fields)
                if enabled_fields is not None
                else list(domain.design_space())
            )
            allowed_values = (
                {"model_type": list(allowed_models)}
                if allowed_models is not None
                else None
            )
            domain = FilteredDomain(
                domain,
                selected_fields,
                allowed_values=allowed_values,
            )

        # ── 创建 Agent Loop ──
        constraints = {"parameter_count_max": parameter_count_max}
        constraints.update(domain.default_constraints())
        constraints["parameter_count_max"] = parameter_count_max
        if data_file:
            constraints["data_file"] = data_file
        loop = ExperimentPlannerLoop(
            planner=ExperimentPlanner(llm_client=llm, domain=domain),
            workspace=root,
            base_config=domain.default_base_config(),
            constraints=constraints,
            timeout_seconds=timeout_seconds,
            artifact_dir=artifact_dir,
            domain=domain,
        )

        # ── 执行 + 流式输出事件 ──
        async for agent_event in loop.run_streaming(
            goal=goal, max_rounds=max_rounds, max_experiments=max_experiments,
        ):
            event_type = agent_event.get("type", "agent_event")

            if event_type == "runtime_event":
                inner = agent_event.get("event", {})
                trace_event = TraceEvent(
                    session_id=inner.get("session_id", session_id),
                    event_type=inner.get("event_type", "unknown"),
                    step=inner.get("step"),
                    tool=inner.get("tool"),
                    status=inner.get("status", "unknown"),
                    latency_ms=inner.get("latency_ms"),
                    payload=inner.get("payload"),
                    error=inner.get("error"),
                    error_type=inner.get("error_type"),
                )
                yield encode_sse_event(trace_event, event_id=_next_event_id(session_id))
            else:
                yield encode_sse_event(TraceEvent(
                    session_id=session_id,
                    event_type=event_type,
                    status="succeeded",
                    payload=agent_event,
                ), event_id=_next_event_id(session_id))

            # ── 检查取消 ──
            if cancel_evt.is_set():
                cancelled = True
                break

        if cancelled:
            yield encode_sse_event(TraceEvent(
                session_id=session_id, event_type="cancelled", status="cancelled",
                payload={"message": "Run cancelled by user."},
            ))

    except Exception as exc:
        yield encode_sse_event(TraceEvent(
            session_id=session_id, event_type="error", status="failed",
            error=f"Agent loop crashed: {exc}",
        ))
    finally:
        _cancel_events.pop(session_id, None)


async def stream_agent_task_benchmark_events(
    workspace: Path | str,
    output_dir: str = "benchmarks/agent-tasks-web",
    attempts: int = 1,
):
    """Run the 18-task scripted fixture and expose trace-backed case results."""
    from nonlinear_agent.agent_benchmark_fixtures import (
        run_scripted_agent_task_benchmark,
        write_agent_task_benchmark_artifacts,
    )

    root = Path(workspace)
    session_id = "agent-task-benchmark"
    yield encode_sse_event(TraceEvent(
        session_id=session_id,
        event_type="agent_task_benchmark_start",
        status="running",
        payload={
            "domain": "nonlinear-modeling",
            "evaluation_mode": "scripted_fixture",
            "attempts": attempts,
        },
    ), event_id=_next_event_id(session_id))

    report = await run_scripted_agent_task_benchmark(root, attempts=attempts)
    for row in report["results"]:
        yield encode_sse_event(TraceEvent(
            session_id=session_id,
            event_type="agent_task_case_end",
            status="succeeded" if row["passed"] else "failed",
            payload=row,
        ), event_id=_next_event_id(session_id))

    artifact_root = Path(output_dir)
    if not artifact_root.is_absolute():
        artifact_root = root / artifact_root
    artifacts = write_agent_task_benchmark_artifacts(artifact_root, report)
    yield encode_sse_event(TraceEvent(
        session_id=session_id,
        event_type="agent_task_benchmark_complete",
        status="succeeded" if report["pass_at_1"] == 1.0 else "failed",
        payload={
            "domain": report["domain"],
            "evaluation_mode": report["evaluation_mode"],
            "task_count": report["task_count"],
            "attempt_count": report["attempt_count"],
            "pass_at_1": report["pass_at_1"],
            f"pass_at_{attempts}": report[f"pass_at_{attempts}"],
            "artifacts": [str(path) for path in artifacts],
        },
    ), event_id=_next_event_id(session_id))


async def stream_multi_agent_events(
    graph: Any,
    session_id: str,
    goal: str,
) -> AsyncIterator[str]:
    """Stream LangGraph node updates as role-attributed SSE events."""
    queue: asyncio.Queue[tuple[str, Any] | None] = asyncio.Queue()
    loop = asyncio.get_running_loop()
    initial = {
        "run_id": session_id,
        "goal": goal,
        "status": "running",
        "cancelled": False,
        "replan_count": 0,
        "timeline": [],
        "failures": [],
    }

    def produce() -> None:
        last_event_at = time.perf_counter()
        try:
            for update in graph.stream(initial, stream_mode="updates"):
                for node, delta in update.items():
                    if not isinstance(delta, dict):
                        continue
                    for event in delta.get("timeline", []):
                        if event.get("role") == "terminal":
                            continue
                        event = dict(event)
                        now = time.perf_counter()
                        event.setdefault(
                            "latency_ms", round((now - last_event_at) * 1000.0, 3)
                        )
                        last_event_at = now
                        usage = event.get("model_usage") or []
                        event.setdefault(
                            "cost_usd",
                            round(
                                sum(
                                    float(item.get("cost_usd", 0.0) or 0.0)
                                    for item in usage
                                    if isinstance(item, dict)
                                ),
                                8,
                            ),
                        )
                        if event.get("role") == "execution" and delta.get(
                            "exploration_outcomes"
                        ):
                            event["experiments"] = [
                                _public_experiment_summary(item)
                                for item in delta["exploration_outcomes"]
                                if isinstance(item, dict)
                            ]
                        if event.get("role") == "coding" and delta.get("code_results"):
                            code_results = [
                                item for item in delta["code_results"]
                                if isinstance(item, dict)
                            ]
                            event["coding_summary"] = {
                                "candidate_count": len(code_results),
                                "passed_count": sum(
                                    bool(item.get("passed")) for item in code_results
                                ),
                                "failed_count": sum(
                                    not bool(item.get("passed")) for item in code_results
                                ),
                                "repair_attempts": sum(
                                    int(item.get("attempt_count", 0) or 0)
                                    for item in code_results
                                ),
                            }
                        if event.get("role") == "final_evaluation" and delta.get(
                            "final_evaluation"
                        ):
                            event["final_evaluation"] = _public_experiment_summary(
                                delta["final_evaluation"]
                            )
                        asyncio.run_coroutine_threadsafe(
                            queue.put(("role", event)), loop
                        ).result()
                    if delta.get("terminal"):
                        asyncio.run_coroutine_threadsafe(
                            queue.put(("terminal", delta["terminal"])), loop
                        ).result()
        except Exception as exc:
            asyncio.run_coroutine_threadsafe(
                queue.put(("error", str(exc))), loop
            ).result()
        finally:
            asyncio.run_coroutine_threadsafe(queue.put(None), loop).result()

    producer = asyncio.create_task(asyncio.to_thread(produce))
    while True:
        item = await queue.get()
        if item is None:
            break
        kind, payload = item
        if kind == "role":
            yield encode_sse_event(
                TraceEvent(
                    session_id=session_id,
                    event_type="multi_agent_role",
                    status=str(payload.get("status", "running")),
                    payload=payload,
                ),
                event_id=_next_event_id(session_id),
            )
        elif kind == "terminal":
            yield encode_sse_event(
                TraceEvent(
                    session_id=session_id,
                    event_type="multi_agent_terminal",
                    status=str(payload.get("status", "error")),
                    payload=payload,
                    error=str(payload.get("error") or "") or None,
                ),
                event_id=_next_event_id(session_id),
            )
        else:
            yield encode_sse_event(
                TraceEvent(
                    session_id=session_id,
                    event_type="error",
                    status="failed",
                    error=str(payload),
                ),
                event_id=_next_event_id(session_id),
            )
    await producer


def _public_experiment_summary(item: dict[str, Any]) -> dict[str, Any]:
    """Expose result evidence to the UI without candidate code or worker state."""
    import math

    candidate = dict(item.get("candidate") or {})
    metrics = {
        str(name): value
        for name, value in dict(item.get("metrics") or {}).items()
        if isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    }
    return {
        "experiment_id": str(
            item.get("experiment_id") or item.get("source_experiment_id") or "unknown"
        ),
        "evaluation_kind": str(item.get("evaluation_kind") or "search"),
        "model_type": str(
            item.get("candidate_name") or candidate.get("model_type") or "unknown"
        ),
        "status": str(item.get("status") or "unknown"),
        "metrics": metrics,
        "artifacts": [str(path) for path in item.get("artifacts", [])],
        "failure_count": len(item.get("failure_facts", [])),
    }


def _build_default_multi_agent_graph(
    workspace: Path,
    payload: dict[str, Any],
    cancel_check: Any | None = None,
    memory_backend: Any | None = None,
) -> Any:
    """Assemble the production DeepSeek multi-agent graph on demand."""
    provider = str(payload.get("provider", "deepseek"))
    if provider != "deepseek":
        raise ValueError(
            "Multi-Agent E2E currently supports provider=deepseek; "
            "offline fixtures are exposed only through injected test factories."
        )
    _load_dotenv(workspace)
    from nonlinear_agent.coding_agent import CodingAgent
    from nonlinear_agent.llm import create_llm_client
    from nonlinear_agent.model_router import ModelRouter
    from nonlinear_agent.multi_agent_runtime import MultiAgentRuntime
    from nonlinear_agent.knowledge import KnowledgeIngestor, KnowledgeRetriever
    from nonlinear_agent.memory.langgraph_store import LangGraphMemoryBackend
    from nonlinear_agent.memory.planner_context import PlannerContextBuilder
    from nonlinear_agent.supervisor_graph import build_multi_agent_graph
    from nonlinear_agent.writing_agent import WritingAgent
    from nonlinear_agent.priors import load_historical_priors

    default_model = str(payload.get("model", "deepseek-v4-flash"))
    roles = {
        role: {
            "provider": "deepseek",
            "model": str(payload.get(f"{role}_model", default_model)),
            "temperature": 0.1 if role == "writing" else 0.0,
        }
        for role in ("idea_plan", "coding", "writing")
    }
    timeout_seconds = float(payload.get("llm_timeout_seconds", 180.0))
    def client_factory(role: str, config: Any) -> Any:
        client = create_llm_client(
            model=config.model,
            timeout_seconds=timeout_seconds,
            role=role,
        )
        return _configure_multi_agent_client(
            client,
            role,
            temperature=float(config.temperature),
            payload=payload,
        )

    router = ModelRouter(roles=roles, client_factory=client_factory)
    router.set_budgets(
        cost_budget_usd=float(payload.get("cost_budget_usd", 1.0)),
        token_budget=int(payload.get("token_budget", 100_000)),
    )
    coding_temp_root = (
        Path.home() / "Desktop" / "codex" / "nonlinear-nn-agent" / "coding-worktrees"
    )
    coding = CodingAgent(
        repo_root=workspace,
        model_router=router,
        temp_root=coding_temp_root,
    )
    writing = WritingAgent(model_router=router)
    memory_backend = memory_backend or LangGraphMemoryBackend()
    context_enabled = bool(payload.get("knowledge_context_enabled", True))
    context_builder = None
    if context_enabled:
        knowledge_root = workspace / "docs" / "knowledge" / "nonlinear-modeling"
        chunks = KnowledgeIngestor(roots=[knowledge_root]).ingest()
        context_builder = PlannerContextBuilder(
            retriever=KnowledgeRetriever(chunks),
            memory_backend=memory_backend,
        )
    namespace = (
        str(payload.get("domain", "nonlinear-modeling")),
        str(payload.get("dataset_hash", "default")),
        str(payload.get("model_family", "mixed")),
    )
    runtime = MultiAgentRuntime(
        repo_root=workspace,
        model_router=router,
        coding_agent=coding,
        coding_agent_factory=lambda: CodingAgent(
            repo_root=workspace,
            model_router=router,
            temp_root=coding_temp_root,
        ),
        writing_agent=writing,
        nmse_threshold_db=float(payload.get("nmse_threshold_db", -35.0)),
        planner_context_builder=context_builder,
        planner_context_enabled=context_enabled,
        planner_namespace=namespace,
        planner_context_top_k=int(payload.get("knowledge_top_k", 3)),
        memory_backend=memory_backend,
        registered_anchor=_registered_anchor_from_payload(payload),
        registered_model_catalog=_registered_model_catalog(),
        candidate_parameter_count_max=int(
            payload.get("candidate_parameter_count_max", 4000)
        ),
        candidate_epochs_max=int(payload.get("candidate_epochs_max", 50)),
        candidate_timeout_seconds=float(
            payload.get("candidate_timeout_seconds", 300.0)
        ),
        coding_max_repairs=int(payload.get("coding_max_repairs", 3)),
        planner_max_repairs=int(payload.get("max_replans", 1)),
        screening_epochs_max=int(payload.get("screening_epochs_max", 300)),
        high_fidelity_rounds=tuple(
            int(value) for value in payload.get("high_fidelity_rounds", [])
        ),
        max_high_fidelity_candidates_per_round=int(
            payload.get("max_high_fidelity_candidates_per_round", 1)
        ),
        min_generated_candidates_per_round=int(
            payload.get("min_generated_candidates_per_round", 0)
        ),
        generated_candidate_epochs_max=int(
            payload.get(
                "generated_candidate_epochs_max",
                payload.get("candidate_epochs_max", 50),
            )
        ),
        historical_priors=[
            {
                "id": prior.id,
                "known_nmse_db": prior.known_nmse_db,
                "parameter_count": prior.parameter_count,
                "config": dict(prior.overrides),
                "source": prior.source,
            }
            for prior in load_historical_priors(
                workspace / "configs" / "priors" / "nonlinear-modeling.json",
                parameter_count_max=int(
                    payload.get("candidate_parameter_count_max", 4000)
                ),
            )
        ],
    )
    graph = build_multi_agent_graph(
        runtime.workers(),
        max_replans=int(payload.get("max_replans", 1)),
        model_router=router,
        cancel_check=cancel_check,
        rounds=int(payload.get("rounds", 1)),
        experiments_per_round=int(payload.get("experiments_per_round", 1)),
        final_evaluation=bool(payload.get("final_evaluation", False)),
        approval_gate=(
            payload["_approval_controller"].review
            if payload.get("_approval_controller") is not None
            else None
        ),
    )
    return graph


def _registered_model_catalog() -> dict[str, dict[str, Any]]:
    """Describe stable experiment tools that the Planner may select directly."""
    shared = [
        "feature_mode",
        "target_mode",
        "memory_depth",
        "mp_order_count",
        "train_ratio",
        "seed",
    ]
    training = [
        "epochs",
        "batch_size",
        "learning_rate",
        "optimizer",
        "scheduler_step_size",
        "scheduler_gamma",
    ]
    return {
        "tiny_mlp": {
            "implementation_source": "registered_model",
            "description": (
                "One hidden-layer real-valued MLP over explicit real/imaginary "
                "complex memory-polynomial features, with complex output."
            ),
            "config_fields": shared + training + ["hidden_units", "activation"],
            "allowed_values": {
                "feature_mode": ["complex_mp", "legacy_abs"],
                "target_mode": ["direct", "residual"],
                "activation": ["relu", "tanh", "silu", "gelu"],
                "optimizer": ["adam", "adamw", "sgd"],
            },
        },
        "spline_mlp": {
            "implementation_source": "registered_model",
            "description": (
                "Compact MLP with a learnable one-dimensional LUT/spline activation."
            ),
            "config_fields": shared
            + training
            + ["hidden_units", "activation", "spline_knots", "spline_range"],
        },
        "complex_lstsq": {
            "implementation_source": "registered_model",
            "description": (
                "Closed-form complex least-squares memory-polynomial baseline; "
                "use epochs=0."
            ),
            "config_fields": shared + ["epochs"],
        },
        "linear": {
            "implementation_source": "registered_model",
            "description": "Trainable complex-output linear baseline over selected features.",
            "config_fields": shared + training,
        },
        "complex_cnn": {
            "implementation_source": "registered_model",
            "description": "Compact convolutional baseline for causal memory features.",
            "config_fields": shared + training + ["kernel_size", "num_layers"],
        },
    }


def _registered_anchor_from_payload(
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    """Resolve a named, trace-backed model profile without accepting code paths."""
    profile = str(payload.get("registered_anchor_profile", "")).strip()
    if not profile:
        return None
    profiles = {
        "tiny-mem15-mp3-h80-40db": {
            "model_type": "tiny_mlp",
            "config": {
                "model_type": "tiny_mlp",
                "feature_mode": "complex_mp",
                "target_mode": "direct",
                "memory_depth": 15,
                "mp_order_count": 3,
                "hidden_units": 80,
                "activation": "relu",
                "epochs": 1500,
                "batch_size": 512,
                "learning_rate": 8.0e-4,
                "optimizer": "adam",
                "scheduler_step_size": 1000,
                "scheduler_gamma": 1.0,
                "seed": 42,
            },
            "parameter_count_max": 8000,
            "epochs_max": 1500,
            "timeout_seconds": 900.0,
            "evidence": "reports/tiny_mlp_relu_mem15_mp3_h80_epochs1500/metrics.json",
        },
        "tiny-mem20-mp3-h96-42db": {
            "model_type": "tiny_mlp",
            "config": {
                "model_type": "tiny_mlp",
                "feature_mode": "complex_mp",
                "target_mode": "direct",
                "memory_depth": 20,
                "mp_order_count": 3,
                "hidden_units": 96,
                "activation": "relu",
                "epochs": 10000,
                "batch_size": 512,
                "learning_rate": 8.0e-4,
                "optimizer": "adam",
                "scheduler_step_size": 1000,
                "scheduler_gamma": 1.0,
                "seed": 42,
            },
            "parameter_count_max": 13000,
            "epochs_max": 10000,
            "timeout_seconds": 1800.0,
            "evidence": "reports/tiny_mlp_md20_mp3_hu96_relu_ep10000/metrics.json",
        },
    }
    if profile not in profiles:
        raise ValueError(f"unsupported registered anchor profile: {profile}")
    return {"profile": profile, **profiles[profile]}


def _configure_multi_agent_client(
    client: Any,
    role: str,
    temperature: float,
    payload: dict[str, Any],
) -> Any:
    """Apply role-specific output and retry bounds to compatible clients."""
    default_tokens = {"idea_plan": 4000, "coding": 8000, "writing": 5000}
    if hasattr(client, "max_tokens"):
        client.max_tokens = int(
            payload.get(f"{role}_max_tokens", default_tokens.get(role, 4000))
        )
    if hasattr(client, "max_retries"):
        client.max_retries = int(payload.get("llm_max_retries", 1))
    if hasattr(client, "temperature"):
        client.temperature = float(temperature)
    return client

# ============================================================
# create_app — FastAPI 应用工厂（核心）
# ============================================================
def create_app(
    workspace: Path | str,
    multi_agent_graph_factory: Any | None = None,
):
    """创建 FastAPI 应用，注册所有路由。

    使用应用工厂模式（app factory）而不是全局 app 对象：
      → 可以创建多个独立的 app 实例（测试用不同的 workspace）
      → 依赖（如 workspace）通过闭包注入，不是全局变量

    返回的 app 可以用 uvicorn.run() 启动。
    """
    try:
        from fastapi import FastAPI, Header
        from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
    except ImportError as exc:
        raise RuntimeError(
            "FastAPI server dependencies are not installed. "
            "Install fastapi and uvicorn."
        ) from exc

    root = Path(workspace)
    app = FastAPI(title="Nonlinear Experiment Agent Harness", version="4.8.0")
    app.state.approval_controllers = {}

    # v3.6.0: process-local memory inspector backend (LangGraph InMemoryStore).
    # Action-loop runs write through the same MemoryBackend port; this
    # endpoint is read-only so the Web UI can inspect provenance.
    from nonlinear_agent.memory.langgraph_store import LangGraphMemoryBackend

    memory_backend = LangGraphMemoryBackend()

    # ── GET /health — 健康检查 ──────────────────────────
    @app.get("/health")
    async def health() -> dict[str, str]:
        """返回 {"status": "ok"}，用于监控和 readiness probe。"""
        return {"status": "ok"}

    @app.get("/memory")
    async def memory_inspector():
        """Read-only memory inspector: namespaces + all stored items."""
        namespaces = memory_backend.list_namespaces()
        items = []
        for namespace in namespaces:
            for item in memory_backend.query(namespace, top_k=100):
                items.append(
                    {
                        "memory_id": item.memory_id,
                        "kind": item.kind.value,
                        "namespace": list(item.namespace),
                        "fact": item.fact,
                        "evidence_refs": list(item.evidence_refs),
                        "run_id": item.run_id,
                        "action_id": item.action_id,
                        "config_hash": item.config_hash,
                        "created_by_role": item.created_by_role,
                        "confidence": item.confidence,
                        "invalidated_at": item.invalidated_at,
                    }
                )
        return {"namespaces": [list(ns) for ns in namespaces], "items": items}

    @app.get("/knowledge/sources")
    async def knowledge_sources():
        """Preview the fixed project-local knowledge allowlist."""
        from nonlinear_agent.knowledge import KnowledgeIngestor

        resolved_root = root.resolve()
        knowledge_root = resolved_root / "docs" / "knowledge" / "nonlinear-modeling"
        chunks = KnowledgeIngestor(roots=[knowledge_root]).ingest()
        sources: dict[str, dict[str, Any]] = {}
        for chunk in chunks:
            source = Path(chunk.source_path)
            key = source.name
            entry = sources.setdefault(
                key,
                {
                    "name": key,
                    "path": source.resolve().relative_to(resolved_root).as_posix(),
                    "chunk_count": 0,
                    "content_hashes": [],
                },
            )
            entry["chunk_count"] += 1
            entry["content_hashes"].append(chunk.content_hash)
        return {
            "root": knowledge_root.relative_to(resolved_root).as_posix() + "/",
            "sources": list(sources.values()),
        }

    @app.get("/domains/{domain_name}/fields")
    async def domain_fields(domain_name: str):
        """Return the optimizable fields (whitelist) for a domain, used by the
        Web UI to let users enable/disable tuning directions."""
        domain = _load_domain(domain_name)
        return {
            "name": domain.name,
            "fields": [
                {"name": key, "values": list(values)}
                for key, values in domain.design_space().items()
            ],
        }

    @app.get("/data/mat-files")
    async def mat_files():
        """Scan data/ and examples/*/data/ for .mat experiment datasets."""
        found: list[str] = []
        for base in (root / "data", root / "examples"):
            if base.is_dir():
                for p in sorted(base.rglob("*.mat")):
                    found.append(str(p.relative_to(root)).replace("\\", "/"))
        return {"files": found}

    # ── GET / — 浏览器首页 ──────────────────────────────
    @app.get("/", response_class=HTMLResponse)
    async def home():
        """返回 Agent Operations Console 首页。"""
        return render_home_page()

    @app.get("/ui/{asset_name}")
    async def web_asset(asset_name: str):
        """Serve the dependency-free UI bundle from an explicit allowlist."""
        from fastapi import HTTPException
        from fastapi.responses import Response

        if asset_name not in WEB_ASSETS:
            raise HTTPException(status_code=404, detail="UI asset not found.")
        return Response(
            content=read_web_asset(asset_name),
            media_type=WEB_ASSETS[asset_name],
            headers={"Cache-Control": "no-cache"},
        )

    # ── GET /diagnostics/{name} — 静态诊断文件 ──────────
    @app.get("/diagnostics/{name}")
    async def diagnostics_file(name: str):
        """服务 docs/diagnostics/ 下的文件（dashboard HTML 和 MD）。

        加了 Cache-Control: no-cache 头防止浏览器缓存旧版本 dashboard。
        """
        from fastapi import HTTPException

        diagnostics_root = (root / "docs" / "diagnostics").resolve()
        path = (diagnostics_root / name).resolve()
        if (
            not path.exists()
            or not path.is_file()
            or diagnostics_root not in path.parents
        ):
            raise HTTPException(status_code=404, detail="Diagnostics file not found.")
        from fastapi.responses import Response
        content = path.read_bytes()
        media = "text/html" if path.suffix == ".html" else "text/markdown"
        return Response(content=content, media_type=media, headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        })

    # ── GET /artifacts/{artifact_path} — 安全展示运行产物 ──
    @app.get("/artifacts/{artifact_path:path}")
    async def artifact_file(artifact_path: str):
        """服务运行产物图片/文本，供 Web UI 展示 PSD、summary、metrics。

        只允许访问项目内常见产物目录，且用 resolve() 防止 ../ 路径逃逸。
        """
        from fastapi import HTTPException

        allowed_roots = [
            (root / "reports").resolve(),
            (root / "runs").resolve(),
            (root / "benchmarks").resolve(),
            (root / "docs" / "assets").resolve(),
            (root / "docs" / "diagnostics").resolve(),
        ]
        candidate = (root / artifact_path).resolve()
        if not candidate.exists() or not candidate.is_file():
            raise HTTPException(status_code=404, detail="Artifact not found.")
        if not any(candidate == base or base in candidate.parents for base in allowed_roots):
            raise HTTPException(status_code=404, detail="Artifact not found.")
        return FileResponse(
            candidate,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )

    # ── POST /runs/{session_id}/events — Fixed Workflow ──
    @app.post("/runs/{session_id}/events")
    async def run_events(
        session_id: str,
        body: Optional[Dict[str, Any]] = None,
        x_last_event_id: Optional[str] = Header(default=None),
    ):
        """Fixed Workflow 模式：前端填参数 → 直接执行 4 步工具链。

        不需要 LLM，不需要 API Key，固定流程执行到底。
        body 里的字段直接映射到 HarnessRunSpec 的构造函数参数。
        客户端可通过 Last-Event-ID 头从断点恢复事件流。
        """
        payload = body or {}
        spec = HarnessRunSpec(session_id=session_id, **payload)

        # 加载 domain（如果指定）
        domain = None
        domain_name = payload.get("domain")
        if domain_name == "synthetic":
            from nonlinear_agent.domains.synthetic_regression import SyntheticRegressionDomain
            domain = SyntheticRegressionDomain()
        elif domain_name:
            from nonlinear_agent.domains.nonlinear_modeling import NonlinearModelingDomain
            domain = NonlinearModelingDomain()

        from nonlinear_agent.control_plane import RuntimeControlPlane

        control_plane = RuntimeControlPlane(root / "runtime.sqlite")
        runtime = build_runtime(
            root, session_id=session_id, timeout_seconds=spec.timeout_seconds,
            domain=domain, control_plane=control_plane,
        )
        if domain is not None:
            request = HarnessRequest(
                session_id=session_id,
                goal=spec.goal,
                steps=domain.build_harness_steps(spec, root),
            )
        else:
            request = build_harness_request(spec)
        trace_path = root / "traces" / f"{session_id}.jsonl"
        output_dir = spec.output_dir or f"reports/{session_id}"

        last_event_id = None
        if x_last_event_id is not None:
            try:
                last_event_id = int(x_last_event_id)
            except ValueError:
                last_event_id = None

        async def event_stream():
            try:
                async for chunk in stream_sse_events(
                    runtime, request, last_event_id=last_event_id
                ):
                    yield chunk
                # Workflow 完成后生成 replay report
                write_replay_report(trace_path, root / output_dir / "replay.md")
            finally:
                control_plane.close()

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    # ── POST /agent/{session_id}/events — Agent Planner ──
    @app.post("/agent/{session_id}/events")
    async def agent_events(session_id: str, body: Optional[Dict[str, Any]] = None):
        """Agent Planner 模式：前端填参数 → LLM 设计实验 → 多轮执行。

        provider="fake" → 离线 demo，用预设回复
        provider="deepseek" → 真实 DeepSeek API

        Agent Loop 完成后自动刷新 dashboard（MD + HTML）。
        """
        payload = body or {}
        provider = str(payload.get("provider", "deepseek"))
        goal = str(payload.get(
            "goal", "Find a low-NMSE nonlinear model under 4000 parameters."
        ))
        max_rounds = int(payload.get("max_rounds", 2))
        max_experiments_raw = payload.get("max_experiments")
        max_experiments = (
            int(max_experiments_raw) if max_experiments_raw is not None else None
        )
        base_config = str(payload.get(
            "base_config", "configs/baselines/lstsq-complexmp-o12-m150.yaml"
        ))
        parameter_count_max = int(payload.get("parameter_count_max", 4000))
        nmse_threshold_db = float(payload.get("nmse_threshold_db", -35.0))
        timeout_seconds = float(payload.get("timeout_seconds", 300.0))
        artifact_dir = payload.get("artifact_dir")
        fake_plan = payload.get("fake_plan")
        domain_name = payload.get("domain")
        enabled_fields = payload.get("enabled_fields")
        data_file = payload.get("data_file")

        async def agent_stream():
            async for chunk in stream_agent_events(
                root, session_id, provider=provider, goal=goal,
                max_rounds=max_rounds, max_experiments=max_experiments,
                base_config=base_config, parameter_count_max=parameter_count_max,
                nmse_threshold_db=nmse_threshold_db, timeout_seconds=timeout_seconds,
                artifact_dir=artifact_dir, fake_plan=fake_plan,
                domain_name=domain_name, enabled_fields=enabled_fields,
                data_file=data_file,
            ):
                yield chunk
            # Agent Loop 完成后自动刷新 Dashboard
            try:
                from nonlinear_agent.diagnostics import write_diagnostics_report
                from nonlinear_agent.dashboard import write_dashboard_html
                write_diagnostics_report(root)
                write_dashboard_html(root)
            except Exception:
                pass  # Dashboard 刷新失败不影响主流程

        return StreamingResponse(agent_stream(), media_type="text/event-stream")

    @app.post("/controlled-search/{session_id}/events")
    async def controlled_search_events(
        session_id: str,
        body: Optional[Dict[str, Any]] = None,
    ):
        """Run the proven model family with strict model/parameter allowlists."""
        payload = dict(body or {})
        domain_name = str(payload.get("domain", "nonlinear"))
        domain = _load_domain(domain_name)
        design_space = domain.design_space()
        valid_models = [str(item) for item in design_space.get("model_type", [])]
        requested_models = [str(item) for item in payload.get("allowed_models", valid_models)]
        invalid_models = sorted(set(requested_models) - set(valid_models))
        if invalid_models:
            from fastapi import HTTPException

            raise HTTPException(
                status_code=400,
                detail=f"Unknown allowed models: {invalid_models}",
            )
        allowed_models = [item for item in requested_models if item in valid_models]
        if not allowed_models:
            from fastapi import HTTPException

            raise HTTPException(status_code=400, detail="Select at least one allowed model.")

        requested_fields = [str(item) for item in payload.get("enabled_fields", [])]
        invalid_fields = sorted(set(requested_fields) - set(design_space))
        if invalid_fields:
            from fastapi import HTTPException

            raise HTTPException(
                status_code=400,
                detail=f"Unknown tunable fields: {invalid_fields}",
            )
        enabled_fields = list(dict.fromkeys(["model_type", *requested_fields]))

        async def controlled_stream():
            async for chunk in stream_agent_events(
                root,
                session_id,
                provider=str(payload.get("provider", "deepseek")),
                goal=str(payload.get(
                    "goal",
                    "Optimize a validated nonlinear model under the selected controls.",
                )),
                max_rounds=int(payload.get("max_rounds", 3)),
                max_experiments=int(payload.get("max_experiments", 9)),
                parameter_count_max=int(payload.get("parameter_count_max", 4000)),
                nmse_threshold_db=float(payload.get("nmse_threshold_db", -35.0)),
                timeout_seconds=float(payload.get("timeout_seconds", 300.0)),
                artifact_dir=payload.get("artifact_dir"),
                domain_name=domain_name,
                enabled_fields=enabled_fields,
                allowed_models=allowed_models,
                data_file=payload.get("data_file"),
            ):
                yield chunk

        return StreamingResponse(controlled_stream(), media_type="text/event-stream")

    @app.post("/multi-agent/{session_id}/events")
    async def multi_agent_events(
        session_id: str,
        body: Optional[Dict[str, Any]] = None,
    ):
        """Run the role-isolated Idea -> Code -> Execute -> Write graph."""
        payload = dict(body or {})
        goal = str(
            payload.get(
                "goal", "Design and evaluate a compact nonlinear model."
            )
        )
        cancel_evt = asyncio.Event()
        _cancel_events[session_id] = cancel_evt
        from nonlinear_agent.approval import ApprovalController

        approval = ApprovalController(
            session_id,
            mode=str(payload.get("approval_mode", "auto")),
            timeout_seconds=float(payload.get("approval_timeout_seconds", 3600.0)),
        )
        app.state.approval_controllers[session_id] = approval
        payload["_approval_controller"] = approval
        try:
            if multi_agent_graph_factory is not None:
                graph = multi_agent_graph_factory(payload)
            else:
                graph = _build_default_multi_agent_graph(
                    root,
                    payload,
                    cancel_check=cancel_evt.is_set,
                    memory_backend=memory_backend,
                )
        except Exception as exc:
            _cancel_events.pop(session_id, None)
            app.state.approval_controllers.pop(session_id, None)
            from fastapi import HTTPException

            raise HTTPException(status_code=400, detail=str(exc)) from exc
        async def multi_agent_stream():
            try:
                async for chunk in stream_multi_agent_events(
                    graph, session_id, goal
                ):
                    yield chunk
            finally:
                _cancel_events.pop(session_id, None)
                app.state.approval_controllers.pop(session_id, None)

        return StreamingResponse(
            multi_agent_stream(), media_type="text/event-stream"
        )

    @app.get("/approvals/{session_id}")
    async def pending_approvals(session_id: str):
        controller = app.state.approval_controllers.get(session_id)
        return {
            "session_id": session_id,
            "mode": controller.mode if controller is not None else "auto",
            "pending": controller.pending() if controller is not None else [],
        }

    @app.post("/approvals/{session_id}/{approval_id}/decision")
    async def decide_approval(
        session_id: str,
        approval_id: str,
        body: Optional[Dict[str, Any]] = None,
    ):
        from fastapi import HTTPException

        controller = app.state.approval_controllers.get(session_id)
        if controller is None:
            raise HTTPException(status_code=404, detail="run approval controller not found")
        decision = dict(body or {})
        try:
            return controller.decide(
                approval_id,
                approved=bool(decision.get("approved")),
                reason=str(decision.get("reason") or ""),
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    # ── POST /benchmark/events — Benchmark 评估 ──────────
    @app.post("/benchmark/events")
    async def benchmark_events(body: Optional[Dict[str, Any]] = None):
        """Benchmark 模式：跑固定测试 case，评估 Agent 质量。

        结果写入 benchmarks/web-<timestamp>/，完成后自动刷新 Dashboard。
        """
        payload = body or {}
        output_dir = str(
            payload.get("output_dir", f"benchmarks/web-{_short_ts()}")
        )
        timeout_seconds = float(payload.get("timeout_seconds", 300.0))
        nmse_threshold_db = float(payload.get("nmse_threshold_db", -35.0))

        async def bench_stream():
            async for chunk in stream_benchmark_events(
                root, output_dir=output_dir, timeout_seconds=timeout_seconds,
                nmse_threshold_db=nmse_threshold_db,
            ):
                yield chunk
            try:
                from nonlinear_agent.diagnostics import write_diagnostics_report
                from nonlinear_agent.dashboard import write_dashboard_html
                write_diagnostics_report(root)
                write_dashboard_html(root)
            except Exception:
                pass

        return StreamingResponse(bench_stream(), media_type="text/event-stream")

    @app.post("/agent-benchmark/events")
    async def agent_task_benchmark_events(
        body: Optional[Dict[str, Any]] = None,
    ):
        """Run independent Agent Task contract cases with explicit provenance."""
        payload = body or {}
        attempts = int(payload.get("attempts", 1))
        if attempts not in {1, 3}:
            attempts = 1
        output_dir = str(
            payload.get("output_dir", f"benchmarks/agent-tasks-{_short_ts()}")
        )
        return StreamingResponse(
            stream_agent_task_benchmark_events(
                root, output_dir=output_dir, attempts=attempts
            ),
            media_type="text/event-stream",
        )

    @app.post("/compare/events")
    async def compare_events(body: Optional[Dict[str, Any]] = None):
        """Strategy Comparison endpoint: runs 4 search methods side by side.

        Accepts custom parameters from the Web UI:
          - domain: "synthetic" or "nonlinear"
          - methods: list of method names
          - seeds: list of seed integers
          - trial_budget: trials per seed per method
          - parameter_count_max: param budget
          - nmse_threshold_db: target threshold
          - timeout_seconds: per-trial timeout
        """
        payload = body or {}
        ws = Path(str(payload.get("workspace", str(root))))
        domain_name = payload.get("domain", "synthetic")
        timeout_seconds = float(payload.get("timeout_seconds", 60.0))

        from nonlinear_agent.evaluation_protocol import EvaluationProtocol

        methods = payload.get("methods", ["random_search", "optuna_tpe", "llm_direct", "llm_program_reflection"])
        seeds = payload.get("seeds", [7, 17])
        trial_budget = int(payload.get("trial_budget", 3))
        param_count_max = int(payload.get("parameter_count_max", 15000))
        nmse_threshold = float(payload.get("nmse_threshold_db", -39.0))

        proto = EvaluationProtocol(
            methods=methods, seeds=seeds, trial_budget=trial_budget,
            parameter_count_max=param_count_max, nmse_threshold_db=nmse_threshold,
            llm_provider=str(payload.get("llm_provider", "deepseek")),
        )

        if domain_name == "synthetic":
            from nonlinear_agent.domains.synthetic_regression import SyntheticRegressionDomain
            domain = SyntheticRegressionDomain()
        else:
            from nonlinear_agent.domains.nonlinear_modeling import NonlinearModelingDomain
            domain = NonlinearModelingDomain()

        output_dir = root / "benchmarks" / f"compare-{_short_ts()}"
        from nonlinear_agent.compare_runner import stream_compare_events

        async def compare_stream():
            async for event in stream_compare_events(
                proto, domain, ws, output_dir=output_dir, timeout_seconds=timeout_seconds,
            ):
                etype = event.get("type", "compare_event")
                payload = dict(event)
                payload.pop("type", None)
                yield encode_sse_event(TraceEvent(
                    session_id="compare",
                    event_type=etype,
                    status="succeeded",
                    payload=payload,
                ), event_id=_next_event_id("compare"))
            # 完成后刷新 Dashboard
            try:
                from nonlinear_agent.diagnostics import write_diagnostics_report
                from nonlinear_agent.dashboard import write_dashboard_html
                write_diagnostics_report(root)
                write_dashboard_html(root)
            except Exception:
                pass

        return StreamingResponse(compare_stream(), media_type="text/event-stream")

    @app.get("/compare/summary")
    async def compare_summary():
        """Return the most recent comparison summary.json for loading saved results."""
        from fastapi.responses import Response
        import glob as _glob
        patterns = [
            "benchmarks/nonlinear-search-v1-v20000/summary.json",
            "benchmarks/nonlinear-search-v1/summary.json",
            "benchmarks/compare-*/summary.json",
            "benchmarks/search-smoke*/summary.json",
            "benchmarks/nonlinear-real-v*/summary.json",
        ]
        candidates = [
            Path(p)
            for pattern in patterns
            for p in _glob.glob(str(root / pattern))
            if Path(p).is_file()
        ]
        if candidates:
            # 按修改时间取最新结果，避免加载旧产物
            path = max(candidates, key=lambda p: p.stat().st_mtime)
            return Response(
                content=path.read_bytes(),
                media_type="application/json",
                headers={"Cache-Control": "no-cache"},
            )
        return {"error": "No comparison results found. Run compare-search first."}

    @app.get("/benchmark/summary")
    async def benchmark_summary():
        """Return the most recent saved benchmark results.json (10-case summary)."""
        from fastapi.responses import Response
        import glob as _glob

        candidates = [
            Path(p)
            for p in _glob.glob(str(root / "benchmarks" / "*" / "results.json"))
            if Path(p).is_file()
        ]
        if candidates:
            path = max(candidates, key=lambda p: p.stat().st_mtime)
            return Response(
                content=path.read_bytes(),
                media_type="application/json",
                headers={"Cache-Control": "no-cache"},
            )
        return {"error": "No benchmark results found. Run a benchmark first."}

    @app.post("/cancel/{session_id}")
    async def cancel_run(session_id: str):
        """Request cooperative cancellation for one owned session.

        Training subprocesses are not globally scanned or killed: doing so can
        terminate unrelated runs. Immediate process termination requires an
        explicit session-to-process ownership registry in the control plane.
        """
        evt = _cancel_events.get(session_id)
        if evt is not None:
            evt.set()
        return {"status": "cancelling", "session_id": session_id}

    return app


def _short_ts() -> str:
    """生成简短时间戳，用于 benchmark 产物目录名。"""
    from datetime import datetime
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _load_domain(domain_name: str | None):
    """Resolve the DomainPlugin for a request.

    Blank/unknown names fall back to the default nonlinear-modeling domain so
    the planner always receives the full prompt contract (known bests,
    JSON template, allowed fields, model_type whitelist). Otherwise the LLM
    free-forms plans and the guard rejects most of them.
    """
    if domain_name == "synthetic":
        from nonlinear_agent.domains.synthetic_regression import SyntheticRegressionDomain

        return SyntheticRegressionDomain()
    if domain_name == "pim-cancellation":
        from nonlinear_agent.domains.pim_cancellation import PIMCancellationDomain

        return PIMCancellationDomain()
    if domain_name == "register-config":
        from nonlinear_agent.domains.register_config import RegisterConfigDomain

        return RegisterConfigDomain()
    from nonlinear_agent.domains.nonlinear_modeling import NonlinearModelingDomain

    return NonlinearModelingDomain()


# ============================================================
# stream_benchmark_events — Benchmark 的 SSE 流
# ============================================================
async def stream_benchmark_events(
    workspace: Path | str,
    output_dir: str = "",
    timeout_seconds: float = 300.0,
    nmse_threshold_db: float = -35.0,
):
    """10-case Agent Benchmark streamed as SSE events with extended metrics.

    Case definitions are shared with the CLI (nonlinear_agent.benchmark_cases)
    so the Web UI and the CLI always evaluate the same cases. Each case
    yields start/end events; the final event carries the full summary
    (target_hit_rate, planner_success_rate, self_correction_count, tokens,
    estimated cost, ...).
    """
    from nonlinear_agent.benchmark import (
        BenchmarkCaseResult, build_benchmark_summary,
        summarize_loop_result, write_benchmark_artifacts,
    )
    from nonlinear_agent.benchmark_cases import build_cases, execute_case

    root = Path(workspace)
    cases = build_cases()
    results: list[BenchmarkCaseResult] = []
    for i, case in enumerate(cases):
        # 通知前端：开始一个 case
        yield encode_sse_event(TraceEvent(
            session_id="benchmark",
            event_type="benchmark_case_start",
            status="running",
            payload={
                "case_id": case.case_id,
                "case_index": i + 1,
                "total_cases": len(cases),
                "goal": case.goal,
            },
        ), event_id=_next_event_id("benchmark"))

        try:
            loop_result = await execute_case(
                case, provider="fake", workspace=root,
                timeout_seconds=timeout_seconds,
            )
            result = summarize_loop_result(case, loop_result)
        except Exception as exc:
            # Benchmark case 内部异常 → 记录为 error，继续下一个 case
            result = BenchmarkCaseResult(
                case_id=case.case_id, status=f"error: {exc}"
            )
        results.append(result)

        # 通知前端：case 完成
        yield encode_sse_event(TraceEvent(
            session_id="benchmark",
            event_type="benchmark_case_end",
            status="succeeded",
            payload={
                "case_id": result.case_id,
                "status": result.status,
                "target_hit": result.target_hit,
                "best_nmse_db": result.best_nmse_db,
                "best_parameter_count": result.best_parameter_count,
                "rejected": result.rejected_count,
                "failed": result.failed_count,
                "succeeded": result.succeeded_count,
                "planner_success_rate": result.planner_success_rate,
                "self_correction_count": result.self_correction_count,
                "rounds": result.rounds,
                "total_prompt_tokens": result.total_prompt_tokens,
                "total_completion_tokens": result.total_completion_tokens,
                "estimated_cost_usd": result.estimated_cost_usd,
            },
        ), event_id=_next_event_id("benchmark"))

    # 汇总 + 落盘
    summary = build_benchmark_summary(results)
    write_benchmark_artifacts(root / output_dir, results, summary)

    # 通知前端：全部完成
    yield encode_sse_event(TraceEvent(
        session_id="benchmark",
        event_type="benchmark_complete",
        status="succeeded",
        payload={"summary": summary, "output_dir": output_dir},
    ), event_id=_next_event_id("benchmark"))


def app_factory(workspace: Path | str = "."):
    """应用工厂的公共入口。等价于 create_app(workspace)。"""
    return create_app(workspace)


__all__ = [
    "HarnessRunSpec",
    "app_factory",
    "build_harness_request",
    "build_runtime",
    "create_app",
    "encode_sse_event",
    "stream_agent_events",
    "stream_agent_task_benchmark_events",
    "stream_benchmark_events",
    "stream_sse_events",
]
