"""Shared 10-case benchmark definitions for CLI and Web UI.

The Web UI benchmark endpoint and the CLI `run_benchmark.py` both consume
this module so they always evaluate the same cases with the same metrics.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable

from nonlinear_agent.benchmark import BenchmarkCase
from nonlinear_agent.trace import TraceEvent


CASE_PLANS: dict[str, list[dict[str, Any]]] = {
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


CASE_METRICS: dict[str, dict[str, Any]] = {
    "strong-001": {"nmse_db": -36.0, "parameter_count": 128},
    "weak-001": {"nmse_db": -20.0, "parameter_count": 128, "error": "NMSE threshold failed"},
    "recovered-001": {"nmse_db": -36.5, "parameter_count": 128},
    "budget-001": {"nmse_db": -35.5, "parameter_count": 128},
    "edge-001": {"nmse_db": -35.8, "parameter_count": 128},
}


class FakeBenchmarkRuntime:
    """Offline runtime that returns deterministic metrics per experiment id."""

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
    """The canonical 10 benchmark cases (CLI and Web UI share this)."""
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


def build_fake_plans(case_id: str) -> list[str]:
    """Turn CASE_PLANS into the FakeLLM response queue."""
    # Variant case ids like "target-hit-v7" reuse the base template's plans.
    base_id = re.sub(r"-v\d+$", "", case_id)
    raw_plans = CASE_PLANS.get(base_id) or CASE_PLANS[case_id]
    if case_id == "json-tolerance":
        return [
            "Here is the plan JSON:\n"
            + json.dumps(raw_plans[0], ensure_ascii=False)
            + "\nHope this helps.",
            json.dumps(raw_plans[1], ensure_ascii=False),
        ]
    return [json.dumps(plan, ensure_ascii=False) for plan in raw_plans]


def build_extended_cases(count: int = 50) -> list[BenchmarkCase]:
    """Parameterized benchmark set: 10 canonical cases + threshold/budget variants.

    Variants sweep the target threshold and experiment budget so the comparison
    also covers behavior consistency across different operating points.
    """
    base = build_cases()
    cases = list(base)
    thresholds = [-34.0, -36.0, -37.0, -38.0, -40.0]
    idx = 0
    base_len = len(base)
    while len(cases) < count:
        for t in base:
            if len(cases) >= count:
                break
            # 每轮（base 全遍历一次）用同一个阈值，轮间轮换
            th = thresholds[(idx // base_len) % len(thresholds)]
            idx += 1
            rounds = min(t.max_rounds + (idx % 2), 4)
            cases.append(
                BenchmarkCase(
                    case_id=f"{t.case_id}-v{idx}",
                    goal=f"{t.goal} (variant threshold {th:.0f} dB)",
                    target_nmse_db=th,
                    max_rounds=rounds,
                    max_experiments=t.max_experiments,
                )
            )
    return cases[:count]


async def execute_case(
    case: BenchmarkCase,
    provider: str = "fake",
    workspace: Path | str | None = None,
    timeout_seconds: float = 36000.0,
    planner_retries: int = 0,
):
    """Execute one benchmark case.

    provider="fake" -> deterministic FakeLLM + FakeBenchmarkRuntime (offline).
    provider="deepseek" -> real LLM + real training through the domain runtime.
    """
    from nonlinear_agent.llm import FakeLLMClient
    from nonlinear_agent.loop import ExperimentPlannerLoop, PlannerLoopResult
    from nonlinear_agent.planner import ExperimentPlanner

    root = Path(workspace) if workspace is not None else Path.cwd()

    if provider == "deepseek":
        from nonlinear_agent.domains.nonlinear_modeling import NonlinearModelingDomain
        from nonlinear_agent.server import build_runtime

        domain = NonlinearModelingDomain()
        planner = ExperimentPlanner(_deepseek_client(), domain=domain)

        def runtime_factory(session_id):
            return build_runtime(
                root, session_id=session_id, domain=domain,
                timeout_seconds=timeout_seconds,
            )

    else:
        from nonlinear_agent.llm import FakeLLMClient

        domain = None
        planner = ExperimentPlanner(FakeLLMClient(responses=build_fake_plans(case.case_id)))
        runtime_factory = lambda session_id: FakeBenchmarkRuntime()

    loop = ExperimentPlannerLoop(
        planner=planner,
        workspace=root,
        runtime_factory=runtime_factory,
        artifact_dir=root / "runs" / f"benchmark-{case.case_id}",
        constraints={
            "parameter_count_max": 20000,
            "metric": "nmse_db",
            "nmse_threshold_db": case.target_nmse_db,
        },
        planner_retries=planner_retries,
        timeout_seconds=timeout_seconds,
    )
    try:
        return await loop.run(
            goal=case.goal,
            max_rounds=case.max_rounds,
            max_experiments=case.max_experiments,
        )
    except Exception as exc:
        return PlannerLoopResult(
            status="planner_error",
            rounds=0,
            history=[],
            summaries=[f"case aborted: {exc}"],
            total_prompt_tokens=getattr(planner.llm_client, "total_prompt_tokens", 0),
            total_completion_tokens=getattr(planner.llm_client, "total_completion_tokens", 0),
        )


def _deepseek_client():
    from nonlinear_agent.llm import OpenAICompatibleClient

    # 保持 v26 验证过的配置：flash 对复杂 planner prompt 需要 ~3k tokens
    # 思考量，max_tokens 限制会截断成空输出；json_mode + 低温度经 v26
    # 10-case 全量验证可用（单次 20-30s，10 case 约 36 分钟）。
    client = OpenAICompatibleClient.deepseek(timeout_seconds=45.0)
    # 网络黑洞时快速失败：正常 planner 调用 20-30s，45s 足够；
    # 减少重试累积时间（曾观察到单 case 因黑洞 + 90s×3 重试拖到 18 分钟）。
    client.max_retries = 2
    client.retry_backoff = 0.5
    return client
