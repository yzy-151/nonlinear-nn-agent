from __future__ import annotations

import argparse
import asyncio
import json
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
}

CASE_METRICS = {
    "strong-001": {"nmse_db": -36.0, "parameter_count": 128},
    "weak-001": {"nmse_db": -20.0, "parameter_count": 128, "error": "NMSE threshold failed"},
}


class FakeBenchmarkRuntime:
    async def run(self, request):
        metrics = CASE_METRICS.get(request.session_id, {})
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
    ]


async def execute_case(case: BenchmarkCase):
    plans = [json.dumps(plan, ensure_ascii=False) for plan in CASE_PLANS[case.case_id]]
    planner = ExperimentPlanner(FakeLLMClient(responses=plans))
    loop = ExperimentPlannerLoop(
        planner=planner,
        workspace=PROJECT_ROOT,
        runtime_factory=lambda session_id: FakeBenchmarkRuntime(),
        artifact_dir=PROJECT_ROOT / "runs" / f"benchmark-{case.case_id}",
        constraints={"parameter_count_max": 4000, "metric": "nmse_db", "nmse_threshold_db": case.target_nmse_db},
    )
    return await loop.run(goal=case.goal, max_rounds=case.max_rounds, max_experiments=case.max_experiments)


async def run(args) -> None:
    cases = build_cases()
    results, summary = await run_benchmark_cases(cases, execute_case)
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = PROJECT_ROOT / output_dir
    write_benchmark_artifacts(output_dir, results, summary)
    print(json.dumps({"summary": summary, "output_dir": str(output_dir)}, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="benchmarks/fake-v08")
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
