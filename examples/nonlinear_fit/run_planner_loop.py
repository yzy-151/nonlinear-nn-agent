from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nonlinear_agent.llm import FakeLLMClient, OpenAICompatibleClient
from nonlinear_agent.loop import ExperimentPlannerLoop
from nonlinear_agent.planner import ExperimentPlanner


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


def build_llm(provider: str, fake_plan: str | None = None):
    if provider == "fake":
        return FakeLLMClient(responses=[fake_plan or DEFAULT_FAKE_PLAN, '{"summary":"stop after demo", "stop": true, "experiments": []}'])
    if provider == "deepseek":
        return OpenAICompatibleClient.deepseek()
    raise ValueError(f"Unsupported provider: {provider}")


async def run(args) -> None:
    llm = build_llm(args.provider, fake_plan=args.fake_plan)
    planner = ExperimentPlanner(llm_client=llm)
    loop = ExperimentPlannerLoop(
        planner=planner,
        workspace=PROJECT_ROOT,
        base_config=args.base_config,
        constraints={"parameter_count_max": args.parameter_count_max, "metric": "nmse_db", "nmse_threshold_db": args.nmse_threshold_db},
        timeout_seconds=args.timeout_seconds,
    )
    result = await loop.run(goal=args.goal, max_rounds=args.max_rounds, max_experiments=args.max_experiments)
    print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=["fake", "deepseek"], default="fake")
    parser.add_argument("--goal", default="Find a low-NMSE nonlinear model under 4000 parameters and produce PSD evidence.")
    parser.add_argument("--base-config", default="configs/model-search/lstsq-complexmp-o12-m150.yaml")
    parser.add_argument("--parameter-count-max", type=int, default=4000)
    parser.add_argument("--nmse-threshold-db", type=float, default=-35.0)
    parser.add_argument("--max-rounds", type=int, default=2)
    parser.add_argument("--max-experiments", type=int)
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    parser.add_argument("--fake-plan")
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
