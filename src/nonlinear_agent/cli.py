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
    run.add_argument("--base-config", default="configs/baselines/lstsq-complexmp-o12-m150.yaml")
    run.add_argument("--parameter-count-max", type=int, default=4000)
    run.add_argument("--nmse-threshold-db", type=float, default=-35.0)
    run.add_argument("--max-rounds", type=int, default=2)
    run.add_argument("--max-experiments", type=int)
    run.add_argument("--timeout-seconds", type=float, default=300.0)
    run.add_argument("--artifact-dir")
    run.add_argument("--fake-plan")
    run.add_argument("--llm-kind", choices=["compat", "sdk"], default="compat",
        help="LLM client: compat (hand-written HTTP, default) or sdk (official OpenAI SDK).")

    benchmark = subparsers.add_parser("benchmark", help="Run the built-in Agent benchmark cases.")
    benchmark.add_argument("--workspace", default=str(PROJECT_ROOT))
    benchmark.add_argument("--output-dir", default="benchmarks/fake-v15")

    diagnostics = subparsers.add_parser("diagnostics", help="Write the Markdown diagnostics report.")
    diagnostics.add_argument("--workspace", default=str(PROJECT_ROOT))
    diagnostics.add_argument("--output")

    dashboard = subparsers.add_parser("dashboard", help="Write a standalone HTML diagnostics dashboard.")
    dashboard.add_argument("--workspace", default=str(PROJECT_ROOT))
    dashboard.add_argument("--output")

    compare = subparsers.add_parser("compare-search", help="Run multi-strategy search comparison.")
    compare.add_argument("--workspace", default=str(PROJECT_ROOT))
    compare.add_argument("--methods", default="random_search,optuna_tpe,llm_direct,llm_program_reflection")
    compare.add_argument("--seeds", default="7,17,29,43,61")
    compare.add_argument("--trial-budget", type=int, default=10)
    compare.add_argument("--parameter-count-max", type=int, default=15000)
    compare.add_argument("--nmse-threshold-db", type=float, default=-39.0)
    compare.add_argument("--output-dir", default="benchmarks/nonlinear-search-v1")
    compare.add_argument("--protocol",
        help="JSON protocol file (methods/seeds/trial_budget). Takes precedence over --methods/--seeds/--trial-budget.")
    compare.add_argument("--domain", choices=["nonlinear", "synthetic", "synthetic-large", "synthetic-hard"], default="nonlinear",
        help="Which DomainPlugin to execute (default: nonlinear).")
    compare.add_argument("--llm-provider", choices=["simulated", "deepseek"], default="simulated",
        help="LLM strategy backend: simulated (offline neighborhood sampling) or deepseek (real chat API).")
    compare.add_argument("--timeout-seconds", type=float, default=300.0,
        help="Per-trial training timeout (default 300s).")
    compare.add_argument("--smoke", action="store_true", help="Use reduced smoke budget (2 seeds x 3 trials)")
    compare.add_argument("--dry-run", action="store_true", help="Print protocol and exit without running")

    stress = subparsers.add_parser("stress-runtime", help="Reliability stress test for the runtime control plane.")
    stress.add_argument("--workspace", default=str(PROJECT_ROOT))
    stress.add_argument("--concurrency", type=int, default=8)
    stress.add_argument("--requests", type=int, default=100)
    stress.add_argument("--failure-rate", type=float, default=0.1)
    stress.add_argument("--output-dir", default="benchmarks/runtime-v2")

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
    if args.command == "compare-search":
        return _run_compare_search(args)
    if args.command == "diagnostics":
        return _write_diagnostics(args)
    if args.command == "dashboard":
        return _write_dashboard(args)
    if args.command == "stress-runtime":
        return _run_stress(args)
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
        from nonlinear_agent.llm import create_llm_client

        llm = create_llm_client(kind=args.llm_kind)
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


def _run_compare_search(args: argparse.Namespace) -> int:
    import json as _json
    from pathlib import Path

    from nonlinear_agent.compare_runner import run_compare_protocol
    from nonlinear_agent.evaluation_protocol import EvaluationProtocol

    if args.protocol:
        with Path(args.protocol).open("r", encoding="utf-8") as fh:
            data = _json.load(fh)
        protocol = EvaluationProtocol(
            methods=data["methods"],
            seeds=[int(s) for s in data["seeds"]],
            trial_budget=int(data["trial_budget"]),
            parameter_count_max=int(data.get("parameter_count_max", 4000)),
            nmse_threshold_db=float(data.get("nmse_threshold_db", -35.0)),
            llm_provider=str(data.get("llm_provider", "simulated")),
        )
    else:
        methods = [m.strip() for m in args.methods.split(",")]
        seeds = [int(s.strip()) for s in args.seeds.split(",")]
        if args.smoke:
            seeds = seeds[:2]
            args.trial_budget = 3
        protocol = EvaluationProtocol(
            methods=methods,
            seeds=seeds,
            trial_budget=args.trial_budget,
            parameter_count_max=args.parameter_count_max,
            nmse_threshold_db=args.nmse_threshold_db,
            llm_provider=args.llm_provider,
        )

    if args.dry_run:
        print(_json.dumps(protocol.to_dict(), indent=2, ensure_ascii=False))
        print(f"Output directory: {args.output_dir}")
        return 0

    if args.domain == "synthetic":
        from nonlinear_agent.domains.synthetic_regression import SyntheticRegressionDomain

        domain = SyntheticRegressionDomain()
    elif args.domain == "synthetic-large":
        from nonlinear_agent.domains.synthetic_regression import SyntheticLargeDomain

        domain = SyntheticLargeDomain()
    elif args.domain == "synthetic-hard":
        from nonlinear_agent.domains.synthetic_regression import SyntheticHardDomain

        domain = SyntheticHardDomain()
    else:
        from nonlinear_agent.domains.nonlinear_modeling import NonlinearModelingDomain

        domain = NonlinearModelingDomain()

    print(f"Protocol: {protocol.estimate_total_trials()} total trials "
          f"({len(protocol.methods)} methods x {len(protocol.seeds)} seeds x "
          f"{protocol.trial_budget} trials)")
    print(f"Domain: {domain.name} | Output: {args.output_dir}")

    out_dir = Path(args.output_dir)
    rows, summary, _ = asyncio.run(run_compare_protocol(
        protocol,
        domain,
        Path(args.workspace),
        output_dir=out_dir,
        timeout_seconds=args.timeout_seconds,
    ))

    print(f"\nWrote {len(rows)} trials to {out_dir / 'trials.jsonl'}")
    metric = domain.primary_metric()
    for m in protocol.methods:
        stats = summary["per_method"].get(m, {})
        best = stats.get(f"best_{metric}_mean", "N/A")
        hit = stats.get("target_hit_rate_mean", 0)
        if isinstance(best, float):
            print(f"  {m}: best={best:.1f}, hit_rate={float(hit) * 100:.0f}%")

    paired = summary.get("paired_comparisons", {})
    for name, delta in paired.items():
        n = delta.get("paired_seed_count", 0)
        d = delta.get("nmse_delta_mean_db") or delta.get(f"{metric}_delta_mean")
        sig = "significant" if delta.get("significant") else "not significant"
        if isinstance(d, float):
            print(f"  {name}: delta={d:.2f} across {n} seeds ({sig})")

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


def _run_stress(args: argparse.Namespace) -> int:
    """Run the concurrent reliability stress test on the RuntimeControlPlane."""
    from pathlib import Path
    from nonlinear_agent.stress import run_stress_test

    out_dir = Path(args.output_dir)
    report = run_stress_test(
        concurrency=args.concurrency,
        requests=args.requests,
        failure_rate=args.failure_rate,
        output_dir=out_dir,
    )

    print(f"Stress test: {report['requests']} requests, "
          f"concurrency={report['concurrency']}")
    print(f"  Duplicate execution rate: {report['duplicate_execution_rate']:.3f}")
    print(f"  Event loss rate: {report['event_loss_rate']:.3f}")
    print(f"  Terminal consistency: {report['terminal_consistency']:.3f}")
    print(f"  Recovery rate (injected {report['injected_failures']} failures): "
          f"{report['recovery_rate']:.3f}")
    print(f"  Report: {out_dir / 'stress.json'}")
    print(f"  {'PASS' if report['pass'] else 'FAIL'}")
    return 0 if report["pass"] else 1


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
