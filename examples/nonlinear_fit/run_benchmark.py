from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nonlinear_agent.benchmark import (  # noqa: E402
    BenchmarkCase,
    run_benchmark_cases,
    write_benchmark_artifacts,
)
from nonlinear_agent.llm import FakeLLMClient  # noqa: E402
from nonlinear_agent.loop import ExperimentPlannerLoop  # noqa: E402
from nonlinear_agent.planner import ExperimentPlanner  # noqa: E402
from nonlinear_agent.trace import TraceEvent  # noqa: E402


CASE_PLANS = {
    "target-hit": [
        {
            "summary": "run strong candidate",
            "stop": False,
            "experiments": [
                {
                    "id": "strong-001",
                    "reason": "known good candidate",
                    "overrides": {"model_type": "complex_lstsq", "epochs": 0},
                }
            ],
        },
        {"summary": "target reached", "stop": True, "experiments": []},
    ],
    "invalid-plan": [
        {
            "summary": "bad planner output",
            "stop": False,
            "experiments": [
                {
                    "id": "bad-rank",
                    "reason": "invalid field should be rejected",
                    "overrides": {"model_type": "complex_lstsq", "rank": 100, "epochs": 0},
                }
            ],
        }
    ],
    "runtime-failure": [
        {
            "summary": "run weak candidate",
            "stop": False,
            "experiments": [
                {
                    "id": "weak-001",
                    "reason": "expected metric failure",
                    "overrides": {"model_type": "complex_lstsq", "epochs": 0},
                }
            ],
        }
    ],
    "reflection-recovery": [
        {
            "summary": "bad first plan",
            "stop": False,
            "experiments": [
                {
                    "id": "bad-spline-range",
                    "reason": "schema failure should become reflection input",
                    "overrides": {
                        "model_type": "spline_mlp",
                        "feature_mode": "complex_mp",
                        "memory_depth": 24,
                        "mp_order_count": 1,
                        "hidden_units": 16,
                        "spline_knots": 16,
                        "spline_range": None,
                        "epochs": 50,
                    },
                }
            ],
        },
        {
            "summary": "recover with safe closed-form model",
            "stop": False,
            "experiments": [
                {
                    "id": "recovered-001",
                    "reason": "safe candidate after reflection",
                    "overrides": {"model_type": "complex_lstsq", "epochs": 0},
                }
            ],
        },
    ],
    "budget-stop": [
        {
            "summary": "two candidates but budget allows one",
            "stop": False,
            "experiments": [
                {
                    "id": "budget-001",
                    "reason": "first candidate consumes the only experiment slot",
                    "overrides": {"model_type": "complex_lstsq", "epochs": 0},
                },
                {
                    "id": "budget-002",
                    "reason": "should not run after budget is exhausted",
                    "overrides": {"model_type": "complex_lstsq", "epochs": 0},
                },
            ],
        }
    ],
    "json-tolerance": [
        {
            "summary": "run strong candidate",
            "stop": False,
            "experiments": [
                {
                    "id": "strong-001",
                    "reason": "valid plan inside noisy LLM text",
                    "overrides": {"model_type": "complex_lstsq", "epochs": 0},
                }
            ],
        },
        {"summary": "target reached", "stop": True, "experiments": []},
    ],
    "parameter-budget-edge": [
        {
            "summary": "candidate at the parameter budget edge",
            "stop": False,
            "experiments": [
                {
                    "id": "edge-001",
                    "reason": "within parameter budget",
                    "overrides": {"model_type": "complex_lstsq", "epochs": 0},
                }
            ],
        },
        {"summary": "done", "stop": True, "experiments": []},
    ],
    "unknown-tool": [
        {
            "summary": "planner requests unsupported tool",
            "stop": False,
            "experiments": [
                {
                    "id": "bad-tool",
                    "reason": "unknown tool should be rejected by guard",
                    "overrides": {"model_type": "complex_lstsq", "rank": 1, "epochs": 0},
                }
            ],
        }
    ],
    "long-history-compression": [
        {
            "summary": "first strong candidate",
            "stop": False,
            "experiments": [
                {"id": f"strong-00{i}", "reason": "grow history", "overrides": {"model_type": "complex_lstsq", "epochs": 0}}
                for i in range(1, 4)
            ],
        },
        {
            "summary": "second strong candidate",
            "stop": False,
            "experiments": [
                {"id": f"strong-01{i}", "reason": "grow history further", "overrides": {"model_type": "complex_lstsq", "epochs": 0}}
                for i in range(1, 4)
            ],
        },
        {"summary": "stop after compressed history", "stop": True, "experiments": []},
    ],
    "multi-round-self-correction": [
        {
            "summary": "bad first plan",
            "stop": False,
            "experiments": [
                {
                    "id": "bad-rank",
                    "reason": "should be rejected",
                    "overrides": {"model_type": "complex_lstsq", "rank": 1, "epochs": 0},
                }
            ],
        },
        {
            "summary": "recover with strong candidate",
            "stop": False,
            "experiments": [
                {
                    "id": "strong-001",
                    "reason": "correction after rejection",
                    "overrides": {"model_type": "complex_lstsq", "epochs": 0},
                }
            ],
        },
        {
            "summary": "weak candidate to create a second correction",
            "stop": False,
            "experiments": [
                {
                    "id": "weak-001",
                    "reason": "expected metric failure",
                    "overrides": {"model_type": "complex_lstsq", "epochs": 0},
                }
            ],
        },
        {
            "summary": "correct again",
            "stop": False,
            "experiments": [
                {
                    "id": "strong-001",
                    "reason": "second correction",
                    "overrides": {"model_type": "complex_lstsq", "epochs": 0},
                }
            ],
        },
        {"summary": "done", "stop": True, "experiments": []},
    ],
}

CASE_METRICS = {
    "strong-001": {"nmse_db": -36.0, "parameter_count": 128},
    "weak-001": {"nmse_db": -20.0, "parameter_count": 128, "error": "NMSE threshold failed"},
    "recovered-001": {"nmse_db": -36.5, "parameter_count": 128},
    "budget-001": {"nmse_db": -35.5, "parameter_count": 128},
    "edge-001": {"nmse_db": -35.8, "parameter_count": 128},
}


def _load_env(workspace: Path) -> None:
    """Load .env.local keys (e.g. DEEPSEEK_API_KEY) without overriding existing env."""
    env_path = workspace / ".env.local"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


class FakeBenchmarkRuntime:
    async def run(self, request):
        metrics = CASE_METRICS.get(request.session_id)
        if metrics is None and request.session_id.startswith("strong-"):
            metrics = {"nmse_db": -36.0, "parameter_count": 128}
        metrics = metrics or {}
        if "nmse_db" in metrics:
            yield TraceEvent(
                session_id=request.session_id,
                event_type="metric",
                status="succeeded",
                payload={"name": "nmse_db", "value": metrics["nmse_db"]},
            )
        if "parameter_count" in metrics:
            yield TraceEvent(
                session_id=request.session_id,
                event_type="metric",
                status="succeeded",
                payload={"name": "parameter_count", "value": metrics["parameter_count"]},
            )
        if "error" in metrics:
            yield TraceEvent(session_id=request.session_id, event_type="error", error=metrics["error"])


def build_cases() -> list[BenchmarkCase]:
    return [
        BenchmarkCase(case_id="target-hit", goal="Reach NMSE <= -35 dB", target_nmse_db=-35.0, max_rounds=2, max_experiments=2),
        BenchmarkCase(case_id="invalid-plan", goal="Reject unsupported planner fields", target_nmse_db=-35.0, max_rounds=1, max_experiments=1),
        BenchmarkCase(case_id="runtime-failure", goal="Record runtime metric failure", target_nmse_db=-35.0, max_rounds=1, max_experiments=1),
        BenchmarkCase(case_id="reflection-recovery", goal="Recover after rejected planner output", target_nmse_db=-35.0, max_rounds=2, max_experiments=2),
        BenchmarkCase(case_id="budget-stop", goal="Stop cleanly when experiment budget is exhausted", target_nmse_db=-35.0, max_rounds=1, max_experiments=1),
        BenchmarkCase(case_id="json-tolerance", goal="Tolerate noisy LLM JSON output", target_nmse_db=-35.0, max_rounds=2, max_experiments=2),
        BenchmarkCase(case_id="parameter-budget-edge", goal="Allow candidates at the parameter budget edge", target_nmse_db=-35.0, max_rounds=2, max_experiments=2),
        BenchmarkCase(case_id="unknown-tool", goal="Reject unsupported tool usage", target_nmse_db=-35.0, max_rounds=1, max_experiments=1),
        BenchmarkCase(case_id="long-history-compression", goal="Keep deciding after long history", target_nmse_db=-35.0, max_rounds=3, max_experiments=9),
        BenchmarkCase(case_id="multi-round-self-correction", goal="Correct multiple times across rounds", target_nmse_db=-35.0, max_rounds=4, max_experiments=4),
    ]


async def execute_case(case: BenchmarkCase, provider: str = "fake"):
    if provider == "deepseek":
        from nonlinear_agent.llm import OpenAICompatibleClient

        planner = ExperimentPlanner(OpenAICompatibleClient.deepseek())
    else:
        raw_plans = CASE_PLANS[case.case_id]
        if case.case_id == "json-tolerance":
            plans = [
                "Here is the plan JSON:\n"
                + json.dumps(raw_plans[0], ensure_ascii=False)
                + "\nHope this helps.",
                json.dumps(raw_plans[1], ensure_ascii=False),
            ]
        else:
            plans = [json.dumps(plan, ensure_ascii=False) for plan in raw_plans]
        planner = ExperimentPlanner(FakeLLMClient(responses=plans))

    if provider == "deepseek":
        from nonlinear_agent.domains.nonlinear_modeling import NonlinearModelingDomain
        from nonlinear_agent.server import build_runtime

        domain = NonlinearModelingDomain()

        def runtime_factory(session_id):
            return build_runtime(PROJECT_ROOT, session_id=session_id, domain=domain)

    else:
        runtime_factory = lambda session_id: FakeBenchmarkRuntime()

    loop = ExperimentPlannerLoop(
        planner=planner,
        workspace=PROJECT_ROOT,
        runtime_factory=runtime_factory,
        artifact_dir=PROJECT_ROOT / "runs" / f"benchmark-{case.case_id}",
        constraints={"parameter_count_max": 20000, "metric": "nmse_db", "nmse_threshold_db": case.target_nmse_db},
    )
    try:
        return await loop.run(
            goal=case.goal,
            max_rounds=case.max_rounds,
            max_experiments=case.max_experiments,
        )
    except Exception as exc:  # planner/runtime failure must not abort the suite
        from nonlinear_agent.loop import PlannerLoopResult

        return PlannerLoopResult(
            status="planner_error",
            rounds=0,
            history=[],
            summaries=[f"case aborted: {exc}"],
            total_prompt_tokens=getattr(planner.llm_client, "total_prompt_tokens", 0),
            total_completion_tokens=getattr(planner.llm_client, "total_completion_tokens", 0),
        )


async def run(args) -> None:
    cases = build_cases()
    results, summary = await run_benchmark_cases(
        cases, lambda case: execute_case(case, provider=args.provider)
    )
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = PROJECT_ROOT / output_dir
    write_benchmark_artifacts(output_dir, results, summary)
    summary["provider"] = args.provider
    print(json.dumps({"summary": summary, "output_dir": str(output_dir)}, ensure_ascii=False, indent=2))


def main() -> None:
    _load_env(PROJECT_ROOT)
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="benchmarks/fake-v08")
    parser.add_argument("--provider", choices=["fake", "deepseek"], default="fake",
                        help="LLM provider: fake (offline) or deepseek (real LLM + real training)")
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
