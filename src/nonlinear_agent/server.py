from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Dict, Optional

from nonlinear_agent.experiment_tools import build_experiment_tool_registry
from nonlinear_agent.replay import write_replay_report
from nonlinear_agent.runtime import ExperimentHarnessRuntime, HarnessRequest
from nonlinear_agent.session import SessionStore
from nonlinear_agent.tools import ToolCall
from nonlinear_agent.trace import TraceEvent, TraceLogger
from nonlinear_agent.web_ui import render_home_page


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
        return FileResponse(path)

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

    return app


def app_factory(workspace: Path | str = "."):
    return create_app(workspace)


__all__ = [
    "HarnessRunSpec",
    "app_factory",
    "build_harness_request",
    "build_runtime",
    "create_app",
    "encode_sse_event",
    "stream_sse_events",
]


