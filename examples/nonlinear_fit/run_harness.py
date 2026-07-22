from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nonlinear_agent.experiment_tools import build_experiment_tool_registry
from nonlinear_agent.replay import write_replay_report
from nonlinear_agent.runtime import ExperimentHarnessRuntime, HarnessRequest
from nonlinear_agent.session import SessionStore
from nonlinear_agent.tools import ToolCall
from nonlinear_agent.trace import TraceLogger


async def run_harness(args) -> list[dict]:
    workspace = PROJECT_ROOT
    registry = build_experiment_tool_registry(workspace=workspace, default_timeout_seconds=args.timeout_seconds)
    trace_path = workspace / "traces" / f"{args.experiment_id}.jsonl"
    runtime = ExperimentHarnessRuntime(
        tool_registry=registry,
        session_store=SessionStore(workspace / "sessions"),
        trace_logger=TraceLogger(trace_path),
    )
    output_dir = args.output_dir or f"reports/{args.experiment_id}"
    steps = [
        ToolCall(
            name="generate_config",
            args={
                "base_config_path": args.base_config,
                "experiment_id": args.experiment_id,
                "overrides": {
                    "output_dir": output_dir,
                    "epochs": args.epochs,
                    "learning_rate": args.learning_rate,
                    "optimizer": args.optimizer,
                },
            },
        ),
        ToolCall(
            name="run_training",
            args={"config_path": f"configs/{args.experiment_id}.yaml", "timeout_seconds": args.timeout_seconds},
            timeout_seconds=args.timeout_seconds + 5,
        ),
        ToolCall(
            name="verify_artifacts",
            args={"output_dir": output_dir, "nmse_threshold_db": args.nmse_threshold_db},
        ),
        ToolCall(
            name="write_report",
            args={"session_id": args.experiment_id},
        ),
    ]
    events = []
    async for event in runtime.run(HarnessRequest(session_id=args.experiment_id, goal=args.goal, steps=steps)):
        payload = event.to_dict()
        events.append(payload)
        print(json.dumps(payload, ensure_ascii=False))
    write_replay_report(trace_path, workspace / output_dir / "replay.md")
    return events


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--goal", default="Run nonlinear NN experiment through the Agent Harness runtime.")
    parser.add_argument("--base-config", default="configs/model-search/lstsq-complexmp-o12-m150.yaml")
    parser.add_argument("--output-dir")
    parser.add_argument("--epochs", type=int, default=0)
    parser.add_argument("--learning-rate", type=float, default=0.0008)
    parser.add_argument("--optimizer", default="adam")
    parser.add_argument("--nmse-threshold-db", type=float, default=-35.0)
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    args = parser.parse_args()
    asyncio.run(run_harness(args))


if __name__ == "__main__":
    main()

