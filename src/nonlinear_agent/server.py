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
from nonlinear_agent.web_ui import render_home_page


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


async def stream_sse_events(
    runtime: ExperimentHarnessRuntime, request: HarnessRequest
) -> AsyncIterator[str]:
    """把 Runtime 的事件流转为 SSE 字符串流。

    这是一个简单的适配器：TraceEvent → encode_sse_event → yield string
    """
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

        # ── 加载 domain（如果指定）──
        domain = None
        if domain_name == "synthetic":
            from nonlinear_agent.domains.synthetic_regression import SyntheticRegressionDomain
            domain = SyntheticRegressionDomain()
        elif domain_name:
            from nonlinear_agent.domains.nonlinear_modeling import NonlinearModelingDomain
            domain = NonlinearModelingDomain()

        # ── 创建 Agent Loop ──
        constraints = {"parameter_count_max": parameter_count_max}
        if domain is not None:
            constraints.update(domain.default_constraints())
            constraints["parameter_count_max"] = parameter_count_max
        else:
            constraints.update({
                "metric": "nmse_db",
                "nmse_threshold_db": nmse_threshold_db,
            })
        loop = ExperimentPlannerLoop(
            planner=ExperimentPlanner(llm_client=llm, domain=domain),
            workspace=root,
            base_config=base_config if base_config and not domain else (
                domain.default_base_config() if domain else base_config
            ),
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


# ============================================================
# create_app — FastAPI 应用工厂（核心）
# ============================================================
def create_app(workspace: Path | str):
    """创建 FastAPI 应用，注册所有路由。

    使用应用工厂模式（app factory）而不是全局 app 对象：
      → 可以创建多个独立的 app 实例（测试用不同的 workspace）
      → 依赖（如 workspace）通过闭包注入，不是全局变量

    返回的 app 可以用 uvicorn.run() 启动。
    """
    try:
        from fastapi import FastAPI
        from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
    except ImportError as exc:
        raise RuntimeError(
            "FastAPI server dependencies are not installed. "
            "Install fastapi and uvicorn."
        ) from exc

    root = Path(workspace)
    app = FastAPI(title="Nonlinear Experiment Agent Harness", version="0.3")

    # ── GET /health — 健康检查 ──────────────────────────
    @app.get("/health")
    async def health() -> dict[str, str]:
        """返回 {"status": "ok"}，用于监控和 readiness probe。"""
        return {"status": "ok"}

    # ── GET / — 浏览器首页 ──────────────────────────────
    @app.get("/", response_class=HTMLResponse)
    async def home():
        """返回三 Tab 操作面板 HTML（由 web_ui.py 渲染）。"""
        return render_home_page()

    # ── GET /diagnostics/{name} — 静态诊断文件 ──────────
    @app.get("/diagnostics/{name}")
    async def diagnostics_file(name: str):
        """服务 docs/diagnostics/ 下的文件（dashboard HTML 和 MD）。

        加了 Cache-Control: no-cache 头防止浏览器缓存旧版本 dashboard。
        """
        path = root / "docs" / "diagnostics" / name
        if not path.exists():
            from fastapi import HTTPException
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
    async def run_events(session_id: str, body: Optional[Dict[str, Any]] = None):
        """Fixed Workflow 模式：前端填参数 → 直接执行 4 步工具链。

        不需要 LLM，不需要 API Key，固定流程执行到底。
        body 里的字段直接映射到 HarnessRunSpec 的构造函数参数。
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

        runtime = build_runtime(
            root, session_id=session_id, timeout_seconds=spec.timeout_seconds,
            domain=domain,
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

        async def event_stream():
            async for chunk in stream_sse_events(runtime, request):
                yield chunk
            # Workflow 完成后生成 replay report
            write_replay_report(trace_path, root / output_dir / "replay.md")

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
        provider = str(payload.get("provider", "fake"))
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

        async def agent_stream():
            async for chunk in stream_agent_events(
                root, session_id, provider=provider, goal=goal,
                max_rounds=max_rounds, max_experiments=max_experiments,
                base_config=base_config, parameter_count_max=parameter_count_max,
                nmse_threshold_db=nmse_threshold_db, timeout_seconds=timeout_seconds,
                artifact_dir=artifact_dir, fake_plan=fake_plan,
                domain_name=domain_name,
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

    @app.post("/compare/events")
    async def compare_events(body: Optional[Dict[str, Any]] = None):
        """Strategy Comparison endpoint: runs 4 search methods side by side.

        Uses the EvaluationProtocol to drive Random/TPE/LLM searches and
        REAL execution through the domain's tool chain. Results are streamed
        as SSE events and written to benchmarks/compare-<ts>/.
        """
        payload = body or {}
        protocol_name = str(payload.get("protocol", "smoke"))
        ws = Path(str(payload.get("workspace", str(root))))
        domain_name = payload.get("domain", "synthetic")
        timeout_seconds = float(payload.get("timeout_seconds", 60.0))

        from nonlinear_agent.evaluation_protocol import build_full_protocol, build_smoke_protocol
        proto = build_smoke_protocol() if protocol_name == "smoke" else build_full_protocol()

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

    @app.post("/cancel/{session_id}")
    async def cancel_run(session_id: str):
        """Cancel a running session — set cancel flag + kill train.py subprocess."""
        evt = _cancel_events.get(session_id)
        if evt is not None:
            evt.set()
        # Kill train.py subprocess so cancel works even during long training
        import subprocess as sp
        try:
            sp.run('wmic process where "commandline like \'%train.py%\' and not commandline like \'%wmic%\'" call terminate',
                   shell=True, capture_output=True, timeout=10)
        except Exception:
            pass
        return {"status": "cancelling", "session_id": session_id}

    return app


def _short_ts() -> str:
    """生成简短时间戳，用于 benchmark 产物目录名。"""
    from datetime import datetime
    return datetime.now().strftime("%Y%m%d-%H%M%S")


# ============================================================
# stream_benchmark_events — Benchmark 的 SSE 流
# ============================================================
async def stream_benchmark_events(
    workspace: Path | str,
    output_dir: str = "",
    timeout_seconds: float = 300.0,
    nmse_threshold_db: float = -35.0,
):
    """依次执行 Benchmark Case，每个 case 的事件通过 SSE 流式输出。

    这些 case 的 Fake Plans 是精心设计的：
      case 1：正常跑 → target hit（complex_lstsq 能达标）
      case 2：先输出非法字段(rank=200) → rejected → 再输出合法 → 观察 recovery
      case 3：用 linear 模型 + -60 dB 的不可能阈值 → target miss → 观察失败处理
      case 4：先触发 schema reflection，再用安全候选恢复
      case 5：一次只允许一个实验，观察预算耗尽停止
    """
    from nonlinear_agent.benchmark import (
        BenchmarkCase, BenchmarkCaseResult, build_benchmark_summary,
        run_benchmark_cases, summarize_loop_result, write_benchmark_artifacts,
    )
    from nonlinear_agent.llm import FakeLLMClient
    from nonlinear_agent.loop import ExperimentPlannerLoop, PlannerLoopResult
    from nonlinear_agent.planner import ExperimentPlanner

    root = Path(workspace)

    cases = [
        BenchmarkCase(
            case_id="target-under-budget",
            goal="Find NMSE <= -35 dB under 4000 params.",
            constraints={"parameter_count_max": 4000},
            max_rounds=2, max_experiments=3,
            target_nmse_db=-35.0,
        ),
        BenchmarkCase(
            case_id="invalid-plan-recovery",
            goal="Recover from invalid planner output.",
            constraints={"parameter_count_max": 4000},
            max_rounds=2, max_experiments=2,
            target_nmse_db=-35.0,
        ),
        BenchmarkCase(
            case_id="runtime-failure-handling",
            goal="Handle runtime tool failure gracefully.",
            constraints={"parameter_count_max": 4000},
            max_rounds=2, max_experiments=2,
            target_nmse_db=-60.0,  # 不可能达标 → 测试失败处理
        ),
        BenchmarkCase(
            case_id="reflection-recovery",
            goal="Recover after rejected planner output using reflection.",
            constraints={"parameter_count_max": 4000},
            max_rounds=2, max_experiments=2,
            target_nmse_db=-35.0,
        ),
        BenchmarkCase(
            case_id="budget-stop",
            goal="Stop cleanly when experiment budget is exhausted.",
            constraints={"parameter_count_max": 4000},
            max_rounds=1, max_experiments=1,
            target_nmse_db=-35.0,
        ),
    ]

    plan_map = {
        "target-under-budget": [
            '{"summary":"Run complex_lstsq baseline.","stop":false,'
            '"experiments":[{"id":"bm001","reason":"complex_lstsq base.",'
            '"overrides":{"model_type":"complex_lstsq","feature_mode":"complex_mp",'
            '"memory_depth":150,"mp_order_count":12,"epochs":0}}]}',
            '{"summary":"Stop after demo.","stop":true,"experiments":[]}',
        ],
        "invalid-plan-recovery": [
            '{"summary":"Run invalid then valid.","stop":false,'
            '"experiments":[{"id":"bm002","reason":"bad plan.",'
            '"overrides":{"model_type":"complex_lstsq","rank":200}},'
            '{"id":"bm003","reason":"valid plan.",'
            '"overrides":{"model_type":"complex_lstsq","feature_mode":"complex_mp",'
            '"memory_depth":150,"mp_order_count":12,"epochs":0}}]}',
            '{"summary":"Stop.","stop":true,"experiments":[]}',
        ],
        "runtime-failure-handling": [
            '{"summary":"Test runtime failure.","stop":false,'
            '"experiments":[{"id":"bm004","reason":"push threshold.",'
            '"overrides":{"model_type":"linear","epochs":0}}]}',
            '{"summary":"Stop.","stop":true,"experiments":[]}',
        ],
        "reflection-recovery": [
            '{"summary":"Trigger schema reflection.","stop":false,'
            '"experiments":[{"id":"bm005","reason":"bad spline range.",'
            '"overrides":{"model_type":"spline_mlp","feature_mode":"complex_mp",'
            '"memory_depth":24,"mp_order_count":1,"hidden_units":16,'
            '"spline_knots":16,"spline_range":null,"epochs":50}}]}',
            '{"summary":"Recover after reflection.","stop":false,'
            '"experiments":[{"id":"bm006","reason":"safe closed-form candidate.",'
            '"overrides":{"model_type":"complex_lstsq","feature_mode":"complex_mp",'
            '"memory_depth":150,"mp_order_count":12,"epochs":0}}]}',
        ],
        "budget-stop": [
            '{"summary":"Two candidates but one-slot budget.","stop":false,'
            '"experiments":[{"id":"bm007","reason":"first candidate.",'
            '"overrides":{"model_type":"complex_lstsq","feature_mode":"complex_mp",'
            '"memory_depth":150,"mp_order_count":12,"epochs":0}},'
            '{"id":"bm008","reason":"should not run after budget.",'
            '"overrides":{"model_type":"complex_lstsq","feature_mode":"complex_mp",'
            '"memory_depth":120,"mp_order_count":10,"epochs":0}}]}',
        ],
    }

    async def _run_one(case: BenchmarkCase) -> PlannerLoopResult:
        """对每个 case 创建独立的 FakeLLM + Loop 实例。"""
        llm = FakeLLMClient(responses=list(plan_map[case.case_id]))
        loop = ExperimentPlannerLoop(
            planner=ExperimentPlanner(llm_client=llm),
            workspace=root,
            base_config="configs/baselines/lstsq-complexmp-o12-m150.yaml",
            constraints={
                "parameter_count_max": case.constraints.get("parameter_count_max", 4000),
                "metric": "nmse_db",
                "nmse_threshold_db": case.target_nmse_db or nmse_threshold_db,
            },
            timeout_seconds=timeout_seconds,
        )
        return await loop.run(
            goal=case.goal,
            max_rounds=case.max_rounds,
            max_experiments=case.max_experiments,
        )

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
            loop_result = await _run_one(case)
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
    "stream_benchmark_events",
    "stream_sse_events",
]
