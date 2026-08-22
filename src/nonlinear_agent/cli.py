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
    run.add_argument("--provider", choices=["fake", "deepseek"], default="deepseek")
    run.add_argument(
        "--mode", choices=["fixed", "action"], default="fixed",
        help="fixed plans an experiment batch; action chooses one tool after each observation.",
    )
    run.add_argument("--goal", default="Find a low-NMSE nonlinear model under 4000 parameters and produce PSD evidence.")
    run.add_argument("--base-config", default="configs/baselines/lstsq-complexmp-o12-m150.yaml")
    run.add_argument("--parameter-count-max", type=int, default=4000)
    run.add_argument("--nmse-threshold-db", type=float, default=-35.0)
    run.add_argument("--max-rounds", type=int, default=2)
    run.add_argument("--max-experiments", type=int)
    run.add_argument("--timeout-seconds", type=float, default=300.0)
    run.add_argument("--artifact-dir")
    run.add_argument("--fake-plan")
    run.add_argument("--fake-action")
    run.add_argument("--max-actions", type=int, default=12)
    run.add_argument(
        "--planner-context",
        choices=["on", "off"],
        default="on",
        help="Inject top-k project knowledge and valid typed memory into action planning.",
    )
    run.add_argument("--llm-kind", choices=["compat", "sdk"], default="compat",
        help="LLM client: compat (hand-written HTTP, default) or sdk (official OpenAI SDK).")

    multi_agent = subparsers.add_parser(
        "multi-agent",
        help="Run the role-isolated batch Supervisor with final evaluation.",
    )
    multi_agent.add_argument("--workspace", default=str(PROJECT_ROOT))
    multi_agent.add_argument("--provider", choices=["deepseek"], default="deepseek")
    multi_agent.add_argument(
        "--goal",
        default=(
            "Design and evaluate compact nonlinear models under 4000 parameters. "
            "Use NMSE as the selection metric and produce verified PSD evidence."
        ),
    )
    multi_agent.add_argument("--run-id")
    multi_agent.add_argument("--rounds", type=int, default=3)
    multi_agent.add_argument("--experiments-per-round", type=int, default=3)
    multi_agent.add_argument(
        "--final-evaluation",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    multi_agent.add_argument("--model", default="deepseek-v4-flash")
    multi_agent.add_argument("--idea-plan-model")
    multi_agent.add_argument("--coding-model")
    multi_agent.add_argument("--writing-model")
    multi_agent.add_argument("--nmse-threshold-db", type=float, default=-35.0)
    multi_agent.add_argument("--llm-timeout-seconds", type=float, default=180.0)
    multi_agent.add_argument("--token-budget", type=int, default=200_000)
    multi_agent.add_argument("--cost-budget-usd", type=float, default=2.0)
    multi_agent.add_argument(
        "--planner-context",
        choices=["on", "off"],
        default="on",
        help="Inject top-k whitelisted knowledge and typed memory into Idea/Plan.",
    )
    multi_agent.add_argument("--knowledge-top-k", type=int, default=3)
    multi_agent.add_argument("--domain", default="nonlinear-modeling")
    multi_agent.add_argument("--dataset-hash", default="default")
    multi_agent.add_argument("--model-family", default="mixed")

    benchmark = subparsers.add_parser("benchmark", help="Run the built-in Agent benchmark cases.")
    benchmark.add_argument("--workspace", default=str(PROJECT_ROOT))
    benchmark.add_argument("--output-dir", default="benchmarks/fake-v15")

    agent_benchmark = subparsers.add_parser(
        "agent-benchmark",
        help="Run independent nonlinear-modeling Agent Task cases.",
    )
    agent_benchmark.add_argument("--workspace", default=str(PROJECT_ROOT))
    agent_benchmark.add_argument(
        "--provider",
        choices=["scripted", "deepseek"],
        default="scripted",
        help="scripted validates harness contracts; deepseek measures real planner decisions on fixed faults.",
    )
    agent_benchmark.add_argument("--model", default="deepseek-v4-flash")
    agent_benchmark.add_argument("--llm-timeout-seconds", type=float, default=90.0)
    agent_benchmark.add_argument(
        "--cases",
        help="Comma-separated task ids for an incremental protocol rerun.",
    )
    agent_benchmark.add_argument("--attempts", type=int, choices=[1, 3], default=1)
    agent_benchmark.add_argument(
        "--output-dir", default="benchmarks/agent-tasks-v1"
    )

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
    compare.add_argument("--llm-provider", choices=["simulated", "deepseek"], default="deepseek",
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

    evidence = subparsers.add_parser(
        "evidence-pack", help="Aggregate behavior, search, and reliability artifacts."
    )
    evidence.add_argument("--workspace", default=str(PROJECT_ROOT))
    evidence.add_argument("--scripted-results", required=True)
    evidence.add_argument("--online-results")
    evidence.add_argument("--online-before")
    evidence.add_argument(
        "--online-correction",
        help="Optional incremental rerun whose case rows replace invalid scored rows.",
    )
    evidence.add_argument("--search-dir", required=True)
    evidence.add_argument("--stress-results", required=True)
    evidence.add_argument("--before-results")
    evidence.add_argument("--after-results")
    evidence.add_argument("--output-dir", default="docs/assets/evidence/v1")

    serve = subparsers.add_parser("serve", help="Serve the SSE harness API.")
    serve.add_argument("--workspace", default=str(PROJECT_ROOT))
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "run":
        return asyncio.run(_run_planner(args))
    if args.command == "multi-agent":
        return _run_multi_agent(args)
    if args.command == "benchmark":
        return _run_benchmark(args)
    if args.command == "agent-benchmark":
        return _run_agent_benchmark(args)
    if args.command == "compare-search":
        return _run_compare_search(args)
    if args.command == "diagnostics":
        return _write_diagnostics(args)
    if args.command == "dashboard":
        return _write_dashboard(args)
    if args.command == "stress-runtime":
        return _run_stress(args)
    if args.command == "evidence-pack":
        return _run_evidence_pack(args)
    if args.command == "serve":
        return _serve(args)
    raise ValueError(f"Unsupported command: {args.command}")


def _run_multi_agent(args: argparse.Namespace) -> int:
    from datetime import datetime

    from nonlinear_agent.server import _build_default_multi_agent_graph
    from nonlinear_agent.supervisor_graph import run_multi_agent_graph

    workspace = Path(args.workspace).resolve()
    run_id = args.run_id or datetime.now().strftime("deepseek-3x3-%Y%m%d-%H%M%S")
    payload = {
        "provider": args.provider,
        "model": args.model,
        "idea_plan_model": args.idea_plan_model or args.model,
        "coding_model": args.coding_model or args.model,
        "writing_model": args.writing_model or args.model,
        "nmse_threshold_db": args.nmse_threshold_db,
        "llm_timeout_seconds": args.llm_timeout_seconds,
        "token_budget": args.token_budget,
        "cost_budget_usd": args.cost_budget_usd,
        "rounds": args.rounds,
        "experiments_per_round": args.experiments_per_round,
        "final_evaluation": args.final_evaluation,
        "knowledge_context_enabled": args.planner_context == "on",
        "knowledge_top_k": args.knowledge_top_k,
        "domain": args.domain,
        "dataset_hash": args.dataset_hash,
        "model_family": args.model_family,
    }
    graph = _build_default_multi_agent_graph(workspace, payload)
    result = run_multi_agent_graph(
        graph,
        goal=args.goal,
        run_id=run_id,
    )
    run_dir = workspace / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    result_path = run_dir / "supervisor-result.json"
    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    summary = {
        "run_id": run_id,
        "status": result.get("status"),
        "rounds": len(result.get("round_records", [])),
        "exploration_count": len(result.get("exploration_outcomes", [])),
        "final_evaluation_count": 1 if result.get("final_evaluation") else 0,
        "result_path": result_path.relative_to(workspace).as_posix(),
        "terminal": result.get("terminal", {}),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if result.get("status") == "completed" else 1


async def _run_planner(args: argparse.Namespace) -> int:
    from nonlinear_agent.llm import FakeLLMClient, OpenAICompatibleClient
    from nonlinear_agent.loop import ExperimentPlannerLoop
    from nonlinear_agent.planner import ExperimentPlanner

    if args.provider == "fake" and args.mode == "action":
        llm = FakeLLMClient(
            responses=[
                args.fake_action
                or '{"type":"stop","action_id":"fake-stop",'
                '"reason":"No fake action supplied.","caused_by_event_ids":[]}'
            ]
        )
    elif args.provider == "fake":
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
    if args.mode == "action":
        from dataclasses import asdict

        from nonlinear_agent.action_loop import ActionPlannerLoop
        from nonlinear_agent.domains.nonlinear_modeling import NonlinearModelingDomain
        from nonlinear_agent.planner import AgentActionPlanner
        from nonlinear_agent.server import build_runtime

        domain = NonlinearModelingDomain()
        tool_registry = domain.build_tool_registry(
            workspace, default_timeout_seconds=args.timeout_seconds
        )
        memory_backend = None
        context_builder = None
        if args.planner_context == "on":
            from nonlinear_agent.knowledge.ingest import KnowledgeIngestor
            from nonlinear_agent.knowledge.retriever import KnowledgeRetriever
            from nonlinear_agent.memory.langgraph_store import LangGraphMemoryBackend
            from nonlinear_agent.memory.planner_context import PlannerContextBuilder

            roots = [path for path in (workspace / "docs", workspace / "configs") if path.is_dir()]
            chunks = KnowledgeIngestor(roots=roots).ingest()
            memory_backend = LangGraphMemoryBackend()
            context_builder = PlannerContextBuilder(
                retriever=KnowledgeRetriever(chunks=chunks),
                memory_backend=memory_backend,
            )
        loop = ActionPlannerLoop(
            planner=AgentActionPlanner(llm, tool_registry),
            tool_registry=tool_registry,
            runtime_factory=lambda session_id: build_runtime(
                workspace,
                session_id=session_id,
                timeout_seconds=args.timeout_seconds,
                domain=domain,
            ),
            session_id="action-cli",
            constraints={
                "parameter_count_max": args.parameter_count_max,
                "metric": "nmse_db",
                "nmse_threshold_db": args.nmse_threshold_db,
                "domain": "nonlinear-modeling",
                "dataset_hash": "cli-default",
                "model_family": "mixed",
            },
            memory_backend=memory_backend,
            planner_context_builder=context_builder,
        )
        try:
            result = await loop.run(goal=args.goal, max_actions=args.max_actions)
        finally:
            if memory_backend is not None:
                memory_backend.close()
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
        return 0

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


def _run_agent_benchmark(args: argparse.Namespace) -> int:
    from nonlinear_agent.agent_benchmark_fixtures import (
        run_llm_agent_task_benchmark,
        run_scripted_agent_task_benchmark,
        write_agent_task_benchmark_artifacts,
    )

    workspace = Path(args.workspace)
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = workspace / output_dir
    cases = None
    if args.cases:
        from nonlinear_agent.agent_benchmark_cases import build_nonlinear_agent_task_cases

        catalog = {case.case_id: case for case in build_nonlinear_agent_task_cases()}
        requested = [item.strip() for item in args.cases.split(",") if item.strip()]
        unknown = sorted(set(requested) - set(catalog))
        if unknown:
            raise ValueError(f"Unknown agent benchmark cases: {', '.join(unknown)}")
        cases = [catalog[case_id] for case_id in requested]
    if args.provider == "deepseek":
        report = asyncio.run(run_llm_agent_task_benchmark(
            workspace,
            attempts=args.attempts,
            cases=cases,
            model=args.model,
            timeout_seconds=args.llm_timeout_seconds,
        ))
    else:
        report = asyncio.run(
            run_scripted_agent_task_benchmark(
                workspace, attempts=args.attempts, cases=cases
            )
        )
    paths = write_agent_task_benchmark_artifacts(output_dir, report)
    print(json.dumps({
        "evaluation_mode": report["evaluation_mode"],
        "task_count": report["task_count"],
        "pass_at_1": report["pass_at_1"],
        f"pass_at_{args.attempts}": report[f"pass_at_{args.attempts}"],
        "artifacts": [str(path) for path in paths],
    }, ensure_ascii=False, indent=2))
    return 0 if report["pass_at_1"] == 1.0 else 1


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


def _run_evidence_pack(args: argparse.Namespace) -> int:
    from nonlinear_agent.evidence_pack import write_evidence_pack

    workspace = Path(args.workspace)

    def resolve(value: str | None) -> Path | None:
        if not value:
            return None
        path = Path(value)
        return path if path.is_absolute() else workspace / path

    def read_json(value: str | None) -> dict | None:
        path = resolve(value)
        if path is None:
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    scripted = read_json(args.scripted_results) or {}
    online = read_json(args.online_results)
    online_before = read_json(args.online_before)
    online_correction = read_json(args.online_correction)
    if online and online_correction:
        from nonlinear_agent.evidence_pack import merge_agent_benchmark_reports

        online = merge_agent_benchmark_reports(online, online_correction)
    stress = read_json(args.stress_results)
    before_payload = read_json(args.before_results)
    after_payload = read_json(args.after_results)
    before = (before_payload or {}).get("summary", before_payload)
    after = (after_payload or {}).get("summary", after_payload)
    search_dir = resolve(args.search_dir)
    if search_dir is None:
        raise ValueError("search-dir is required")
    search_summary = json.loads(
        (search_dir / "summary.json").read_text(encoding="utf-8")
    )
    trials = [
        json.loads(line)
        for line in (search_dir / "trials.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    output_dir = resolve(args.output_dir)
    if output_dir is None:
        raise ValueError("output-dir is required")
    paths = write_evidence_pack(
        output_dir,
        scripted,
        online,
        search_summary,
        trials,
        stress,
        online_before=online_before,
        before=before,
        after=after,
    )
    print(json.dumps({"artifacts": [str(path) for path in paths]}, ensure_ascii=False, indent=2))
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
