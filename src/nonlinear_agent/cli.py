from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
from pathlib import Path
from typing import Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_FAKE_PLAN = json.dumps(
    {
        "summary": "Run the current best lightweight complex MP least-squares candidate.",
        "stop": False,
        "experiments": [
            {
                "id": "planner-demo-001",
                "reason": "Validate the LLM-planned loop on the known best under-4000-parameter configuration.",
                "overrides": {
                    "output_dir": "reports/planner-demo-001",
                    "model_type": "complex_lstsq",
                    "feature_mode": "complex_mp",
                    "memory_depth": 150,
                    "mp_order_count": 12,
                    "epochs": 0,
                },
            }
        ],
    },
    ensure_ascii=False,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nonlinear-agent", description="Unified CLI for the nonlinear Agent Harness.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="Run an LLM-planned experiment loop.")
    run.add_argument("--workspace", default=str(PROJECT_ROOT))
    run.add_argument("--provider", choices=["fake", "deepseek"], default="fake")
    run.add_argument("--goal", default="Find a low-NMSE nonlinear model under 4000 parameters and produce PSD evidence.")
    run.add_argument("--base-config", default="configs/model-search/lstsq-complexmp-o12-m150.yaml")
    run.add_argument("--parameter-count-max", type=int, default=4000)
    run.add_argument("--nmse-threshold-db", type=float, default=-35.0)
    run.add_argument("--max-rounds", type=int, default=2)
    run.add_argument("--max-experiments", type=int)
    run.add_argument("--timeout-seconds", type=float, default=300.0)
    run.add_argument("--artifact-dir")
    run.add_argument("--fake-plan")

    benchmark = subparsers.add_parser("benchmark", help="Run the built-in Agent benchmark cases.")
    benchmark.add_argument("--workspace", default=str(PROJECT_ROOT))
    benchmark.add_argument("--output-dir", default="benchmarks/fake-v15")

    diagnostics = subparsers.add_parser("diagnostics", help="Write the Markdown diagnostics report.")
    diagnostics.add_argument("--workspace", default=str(PROJECT_ROOT))
    diagnostics.add_argument("--output")

    dashboard = subparsers.add_parser("dashboard", help="Write a standalone HTML diagnostics dashboard.")
    dashboard.add_argument("--workspace", default=str(PROJECT_ROOT))
    dashboard.add_argument("--output")

    serve = subparsers.add_parser("serve", help="Serve the SSE harness API.")
    serve.add_argument("--workspace", default=str(PROJECT_ROOT))
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "run":
        return asyncio.run(_run_planner(args))
    if args.command == "benchmark":
        return _run_benchmark(args)
    if args.command == "diagnostics":
        return _write_diagnostics(args)
    if args.command == "dashboard":
        return _write_dashboard(args)
    if args.command == "serve":
        return _serve(args)
    raise ValueError(f"Unsupported command: {args.command}")


async def _run_planner(args: argparse.Namespace) -> int:
    from nonlinear_agent.llm import FakeLLMClient, OpenAICompatibleClient
    from nonlinear_agent.loop import ExperimentPlannerLoop
    from nonlinear_agent.planner import ExperimentPlanner

    if args.provider == "fake":
        llm = FakeLLMClient(
            responses=[
                args.fake_plan or DEFAULT_FAKE_PLAN,
                '{"summary":"stop after demo", "stop": true, "experiments": []}',
            ]
        )
    elif args.provider == "deepseek":
        llm = OpenAICompatibleClient.deepseek()
    else:
        raise ValueError(f"Unsupported provider: {args.provider}")

    workspace = Path(args.workspace)
    loop = ExperimentPlannerLoop(
        planner=ExperimentPlanner(llm_client=llm),
        workspace=workspace,
        base_config=args.base_config,
        constraints={
            "parameter_count_max": args.parameter_count_max,
            "metric": "nmse_db",
            "nmse_threshold_db": args.nmse_threshold_db,
        },
        timeout_seconds=args.timeout_seconds,
        artifact_dir=args.artifact_dir,
    )
    result = await loop.run(goal=args.goal, max_rounds=args.max_rounds, max_experiments=args.max_experiments)
    print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))
    return 0


def _run_benchmark(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace)
    script = workspace / "examples" / "nonlinear_fit" / "run_benchmark.py"
    output_dir = args.output_dir
    result = subprocess.run(
        [sys.executable, str(script), "--output-dir", output_dir],
        cwd=workspace,
        text=True,
        check=False,
    )
    return int(result.returncode)


def _write_diagnostics(args: argparse.Namespace) -> int:
    from nonlinear_agent.diagnostics import write_diagnostics_report

    output = write_diagnostics_report(args.workspace, args.output)
    print(output)
    return 0


def _write_dashboard(args: argparse.Namespace) -> int:
    from nonlinear_agent.dashboard import write_dashboard_html

    output = write_dashboard_html(args.workspace, args.output)
    print(output)
    return 0


def _serve(args: argparse.Namespace) -> int:
    try:
        import uvicorn
    except ImportError as exc:
        raise SystemExit("Install server dependencies first: pip install fastapi uvicorn") from exc
    from nonlinear_agent.server import create_app

    uvicorn.run(create_app(args.workspace), host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
