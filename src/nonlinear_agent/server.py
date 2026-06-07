from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Dict, Optional


def _load_dotenv(workspace: Path) -> None:
    """Load .env.local into os.environ so DeepSeek client can read the API key."""
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

from nonlinear_agent.experiment_tools import build_experiment_tool_registry
from nonlinear_agent.replay import write_replay_report
from nonlinear_agent.runtime import ExperimentHarnessRuntime, HarnessRequest
from nonlinear_agent.session import SessionStore
from nonlinear_agent.tools import ToolCall
from nonlinear_agent.trace import TraceEvent, TraceLogger
from nonlinear_agent.web_ui import render_home_page

BUILTIN_FAKE_PLANS = [
    (
        '{"summary":"Run the best lightweight complex MP least-squares candidate.","stop":false,'
        '"experiments":[{"id":"planner-demo-001","reason":"Validate the LLM-planned loop on the known best '
        'under-4000-parameter configuration.","overrides":{"output_dir":"reports/planner-demo-001",'
        '"model_type":"complex_lstsq","feature_mode":"complex_mp","memory_depth":150,'
        '"mp_order_count":12,"epochs":0}}]}'
    ),
    '{"summary":"stop after demo run.","stop":true,"experiments":[]}',
]


@dataclass(frozen=True)
class HarnessRunSpec:
    session_id: str
    goal: str = "Run nonlinear NN experiment through the Agent Harness streaming runtime."
    base_config: str = "configs/model-search/lstsq-complexmp-o12-m150.yaml"
    output_dir: str | None = None
    epochs: int = 0
    learning_rate: float = 0.0008
    optimizer: str = "adam"
    nmse_threshold_db: float = -35.0
    timeout_seconds: float = 300.0
    overrides: dict[str, Any] = field(default_factory=dict)


def build_harness_request(spec: HarnessRunSpec) -> HarnessRequest:
    output_dir = spec.output_dir or f"reports/{spec.session_id}"
    overrides = {
        "output_dir": output_dir,
        "epochs": spec.epochs,
        "learning_rate": spec.learning_rate,
        "optimizer": spec.optimizer,
    }
    overrides.update(spec.overrides)
    overrides["output_dir"] = output_dir
    return HarnessRequest(
        session_id=spec.session_id,
        goal=spec.goal,
        steps=[
            ToolCall(
                name="generate_config",
                args={
                    "base_config_path": spec.base_config,
                    "experiment_id": spec.session_id,
                    "overrides": overrides,
                },
            ),
            ToolCall(
                name="run_training",
                args={"config_path": f"configs/{spec.session_id}.yaml", "timeout_seconds": spec.timeout_seconds},
                timeout_seconds=spec.timeout_seconds + 5,
            ),
            ToolCall(
                name="verify_artifacts",
                args={"output_dir": output_dir, "nmse_threshold_db": spec.nmse_threshold_db},
            ),
            ToolCall(name="write_report", args={"session_id": spec.session_id}),
        ],
    )


def encode_sse_event(event: TraceEvent) -> str:
    return "event: {event_type}\ndata: {payload}\n\n".format(
        event_type=event.event_type,
        payload=json.dumps(event.to_dict(), ensure_ascii=False, default=str),
    )


async def stream_sse_events(runtime: ExperimentHarnessRuntime, request: HarnessRequest) -> AsyncIterator[str]:
    async for event in runtime.run(request):
        yield encode_sse_event(event)


def build_runtime(workspace: Path | str, session_id: str, timeout_seconds: float = 300.0) -> ExperimentHarnessRuntime:
    root = Path(workspace)
    return ExperimentHarnessRuntime(
        tool_registry=build_experiment_tool_registry(root, default_timeout_seconds=timeout_seconds),
        session_store=SessionStore(root / "sessions"),
        trace_logger=TraceLogger(root / "traces" / f"{session_id}.jsonl"),
    )


async def stream_agent_events(
    workspace: Path | str,
    session_id: str,
    provider: str = "fake",
    goal: str = "",
    max_rounds: int = 2,
    max_experiments: int | None = None,
    base_config: str = "configs/model-search/lstsq-complexmp-o12-m150.yaml",
    parameter_count_max: int = 4000,
    nmse_threshold_db: float = -35.0,
    timeout_seconds: float = 300.0,
    artifact_dir: str | None = None,
    fake_plan: str | None = None,
):
    from nonlinear_agent.llm import FakeLLMClient, OpenAICompatibleClient
    from nonlinear_agent.loop import ExperimentPlannerLoop
    from nonlinear_agent.planner import ExperimentPlanner

    root = Path(workspace)
    _load_dotenv(root)
    try:
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

        loop = ExperimentPlannerLoop(
            planner=ExperimentPlanner(llm_client=llm),
            workspace=root,
            base_config=base_config,
            constraints={
                "parameter_count_max": parameter_count_max,
                "metric": "nmse_db",
                "nmse_threshold_db": nmse_threshold_db,
            },
            timeout_seconds=timeout_seconds,
            artifact_dir=artifact_dir,
        )

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
                yield encode_sse_event(trace_event)
            else:
                yield encode_sse_event(TraceEvent(
                    session_id=session_id,
                    event_type=event_type,
                    status="succeeded",
                    payload=agent_event,
                ))
    except Exception as exc:
        yield encode_sse_event(TraceEvent(
            session_id=session_id, event_type="error", status="failed",
            error=f"Agent loop crashed: {exc}",
        ))


def create_app(workspace: Path | str):
    try:
        from fastapi import FastAPI
        from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
    except ImportError as exc:  # pragma: no cover - depends on optional server deps
        raise RuntimeError("FastAPI server dependencies are not installed. Install fastapi and uvicorn.") from exc

    root = Path(workspace)
    app = FastAPI(title="Nonlinear Experiment Agent Harness", version="0.3")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    async def home():
        return render_home_page()

    @app.get("/diagnostics/{name}")
    async def diagnostics_file(name: str):
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

    @app.post("/runs/{session_id}/events")
    async def run_events(session_id: str, body: Optional[Dict[str, Any]] = None):
        payload = body or {}
        spec = HarnessRunSpec(session_id=session_id, **payload)
        runtime = build_runtime(root, session_id=session_id, timeout_seconds=spec.timeout_seconds)
        request = build_harness_request(spec)
        trace_path = root / "traces" / f"{session_id}.jsonl"
        output_dir = spec.output_dir or f"reports/{session_id}"

        async def event_stream():
            async for chunk in stream_sse_events(runtime, request):
                yield chunk
            write_replay_report(trace_path, root / output_dir / "replay.md")

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    @app.post("/agent/{session_id}/events")
    async def agent_events(session_id: str, body: Optional[Dict[str, Any]] = None):
        payload = body or {}
        provider = str(payload.get("provider", "fake"))
        goal = str(payload.get("goal", "Find a low-NMSE nonlinear model under 4000 parameters."))
        max_rounds = int(payload.get("max_rounds", 2))
        max_experiments_raw = payload.get("max_experiments")
        max_experiments = int(max_experiments_raw) if max_experiments_raw is not None else None
        base_config = str(payload.get("base_config", "configs/model-search/lstsq-complexmp-o12-m150.yaml"))
        parameter_count_max = int(payload.get("parameter_count_max", 4000))
        nmse_threshold_db = float(payload.get("nmse_threshold_db", -35.0))
        timeout_seconds = float(payload.get("timeout_seconds", 300.0))
        artifact_dir = payload.get("artifact_dir")
        fake_plan = payload.get("fake_plan")

        async def agent_stream():
            async for chunk in stream_agent_events(
                root, session_id, provider=provider, goal=goal,
                max_rounds=max_rounds, max_experiments=max_experiments,
                base_config=base_config, parameter_count_max=parameter_count_max,
                nmse_threshold_db=nmse_threshold_db, timeout_seconds=timeout_seconds,
                artifact_dir=artifact_dir, fake_plan=fake_plan,
            ):
                yield chunk
            # Auto-regenerate dashboards after agent loop finishes
            try:
                from nonlinear_agent.diagnostics import write_diagnostics_report
                from nonlinear_agent.dashboard import write_dashboard_html
                write_diagnostics_report(root)
                write_dashboard_html(root)
            except Exception:
                pass

        return StreamingResponse(agent_stream(), media_type="text/event-stream")

    @app.post("/benchmark/events")
    async def benchmark_events(body: Optional[Dict[str, Any]] = None):
        payload = body or {}
        output_dir = str(payload.get("output_dir", f"benchmarks/web-{_short_ts()}"))
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

    return app


def _short_ts() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y%m%d-%H%M%S")


async def stream_benchmark_events(
    workspace: Path | str,
    output_dir: str = "",
    timeout_seconds: float = 300.0,
    nmse_threshold_db: float = -35.0,
):
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
            max_rounds=2,
            max_experiments=3,
            target_nmse_db=-35.0,
        ),
        BenchmarkCase(
            case_id="invalid-plan-recovery",
            goal="Recover from invalid planner output.",
            constraints={"parameter_count_max": 4000},
            max_rounds=2,
            max_experiments=2,
            target_nmse_db=-35.0,
        ),
        BenchmarkCase(
            case_id="runtime-failure-handling",
            goal="Handle runtime tool failure gracefully.",
            constraints={"parameter_count_max": 4000},
            max_rounds=2,
            max_experiments=2,
            target_nmse_db=-60.0,
        ),
    ]

    fake_plans = [
        '{"summary":"Run complex_lstsq baseline.","stop":false,"experiments":[{"id":"bm001","reason":"complex_lstsq base.","overrides":{"model_type":"complex_lstsq","feature_mode":"complex_mp","memory_depth":150,"mp_order_count":12,"epochs":0}}]}',
        '{"summary":"Stop after demo.","stop":true,"experiments":[]}',
        '{"summary":"Run invalid then valid.","stop":false,"experiments":[{"id":"bm002","reason":"bad plan.","overrides":{"model_type":"complex_lstsq","rank":200}},{"id":"bm003","reason":"valid plan.","overrides":{"model_type":"complex_lstsq","feature_mode":"complex_mp","memory_depth":150,"mp_order_count":12,"epochs":0}}]}',
        '{"summary":"Stop.","stop":true,"experiments":[]}',
        '{"summary":"Test runtime failure.","stop":false,"experiments":[{"id":"bm004","reason":"push threshold.","overrides":{"model_type":"linear","epochs":0}}]}',
        '{"summary":"Stop.","stop":true,"experiments":[]}',
    ]

    async def _run_one(case: BenchmarkCase) -> PlannerLoopResult:
        llm = FakeLLMClient(responses=list(fake_plans))
        loop = ExperimentPlannerLoop(
            planner=ExperimentPlanner(llm_client=llm),
            workspace=root,
            base_config="configs/model-search/lstsq-complexmp-o12-m150.yaml",
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
        yield encode_sse_event(TraceEvent(
            session_id="benchmark", event_type="benchmark_case_start", status="running",
            payload={"case_id": case.case_id, "case_index": i + 1, "total_cases": len(cases),
                      "goal": case.goal},
        ))
        try:
            loop_result = await _run_one(case)
            result = summarize_loop_result(case, loop_result)
        except Exception as exc:
            result = BenchmarkCaseResult(case_id=case.case_id, status=f"error: {exc}")
        results.append(result)
        yield encode_sse_event(TraceEvent(
            session_id="benchmark", event_type="benchmark_case_end", status="succeeded",
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
        ))

    summary = build_benchmark_summary(results)
    write_benchmark_artifacts(root / output_dir, results, summary)
    yield encode_sse_event(TraceEvent(
        session_id="benchmark", event_type="benchmark_complete", status="succeeded",
        payload={"summary": summary, "output_dir": output_dir},
    ))


def app_factory(workspace: Path | str = "."):
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


