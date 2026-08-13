"""Deterministic fault fixtures for the single-domain Agent Task benchmark."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from nonlinear_agent.action_loop import ActionPlannerLoop
from nonlinear_agent.agent_benchmark import run_agent_task_benchmark
from nonlinear_agent.agent_benchmark_cases import (
    AgentTaskCase,
    build_nonlinear_agent_task_cases,
)
from nonlinear_agent.experiment_tools import build_experiment_tool_registry
from nonlinear_agent.llm import FakeLLMClient
from nonlinear_agent.planner import AgentActionPlanner
from nonlinear_agent.runtime import ExperimentHarnessRuntime
from nonlinear_agent.session import SessionStore
from nonlinear_agent.tools import ToolRegistry
from nonlinear_agent.trace import TraceLogger


def build_initial_fault_history(case: AgentTaskCase) -> list[dict[str, Any]]:
    """Expose a deterministic failure as an observation for online recovery eval."""
    if case.case_id == "stop-after-target-hit":
        return [{
            "action_id": "fixture-target-hit",
            "planner_call_id": "benchmark-fixture",
            "round": 0,
            "tool_name": "verify_artifacts",
            "arguments": {},
            "caused_by_event_ids": [],
            "event_id": "fixture-target-hit:succeeded",
            "run_status": "succeeded",
            "error": None,
            "observation": {
                "metrics": {"nmse_db": -42.26, "parameter_count": 3626},
                "artifacts": ["reports/fixture-best/psd.png"],
                "context_summary": "Verified target hit.",
            },
            "source": "deterministic_fault_fixture",
        }]
    if not case.fault:
        return []
    event_id = f"fixture-{case.fault}:failed"
    messages = {
        "training_error": "Training failed with a numerical divergence.",
        "metric_threshold_error": "Verified NMSE -34.0 dB missed the -35.0 dB target.",
        "timeout_error": "Training exceeded the allowed timeout.",
        "missing_psd": "PSD artifact is missing after training.",
        "duplicate_candidate": "Candidate config hash duplicates the previous trial.",
        "historical_best_available": "Trace-backed best candidate reached -42.26 dB.",
        "reflection_fact_available": "Failure fact: the previous model diverged during training.",
        "conflicting_history": "Older evidence says -38 dB; newer verified trace says -42 dB.",
        "compressed_history": "Compressed context retains parameter_count_max=4000 and timeout failure.",
        "unknown_tool": "Guard rejected unavailable tool 'shell'.",
        "missing_required_argument": "Guard rejected generate_config because experiment_id was missing.",
        "unexpected_argument": "Guard rejected run_training because argument 'shell' is not allowed.",
        "wrong_argument_type": "Guard rejected run_training because config_path must be a string.",
    }
    message = messages.get(case.fault, f"Injected benchmark fact: {case.fault}")
    observation: dict[str, Any] = {"error": message, "error_type": case.fault}
    if case.fault == "historical_best_available":
        observation.update({
            "metrics": {"nmse_db": -42.26, "parameter_count": 3626},
            "evidence_id": "fixture-history-best-verified",
            "config_hash": "fixture-best-config",
        })
    return [{
        "action_id": f"fixture-{case.fault}",
        "planner_call_id": "benchmark-fixture",
        "round": 0,
        "tool_name": None,
        "arguments": {},
        "caused_by_event_ids": [],
        "event_id": event_id,
        "run_status": "rejected" if case.fault in {
            "unknown_tool", "missing_required_argument",
            "unexpected_argument", "wrong_argument_type",
        } else "failed",
        "error": message,
        "error_type": case.fault,
        "observation": observation,
        "source": "deterministic_fault_fixture",
    }]


def _tool_action(
    action_id: str,
    tool: str,
    arguments: dict[str, Any],
    caused_by: list[str] | None = None,
) -> str:
    return json.dumps(
        {
            "type": "tool_call",
            "action_id": action_id,
            "reason": "scripted benchmark action",
            "tool": tool,
            "arguments": arguments,
            "caused_by_event_ids": caused_by or [],
        },
        ensure_ascii=False,
    )


def _stop_action(action_id: str = "stop") -> str:
    return json.dumps(
        {
            "type": "stop",
            "action_id": action_id,
            "reason": "task terminal state reached",
            "caused_by_event_ids": [],
        }
    )


def _valid_arguments(case: AgentTaskCase, tool: str) -> dict[str, Any]:
    experiment_id = case.case_id
    if tool == "generate_config":
        return {
            "base_config_path": "configs/baselines/fixture.yaml",
            "experiment_id": experiment_id,
            "overrides": {"output_dir": f"reports/{experiment_id}"},
        }
    if tool == "run_training":
        return {
            "config_path": f"runs/{experiment_id}/configs/{experiment_id}.yaml",
            "timeout_seconds": 1.0,
        }
    if tool == "verify_artifacts":
        return {
            "output_dir": f"reports/{experiment_id}",
            "nmse_threshold_db": -35.0,
        }
    if tool == "write_report":
        return {"session_id": experiment_id}
    raise ValueError(f"No fixture arguments for tool: {tool}")


def build_scripted_actions(case: AgentTaskCase) -> list[str]:
    """Return a deterministic action trace that exercises each task predicate."""
    action = lambda index, tool, caused=None: _tool_action(
        f"a{index}", tool, _valid_arguments(case, tool), caused
    )
    scripts: dict[str, list[str]] = {
        "complete-experiment": [
            action(1, "generate_config"),
            action(2, "run_training"),
            action(3, "verify_artifacts"),
            action(4, "write_report"),
        ],
        "generate-config-only": [action(1, "generate_config")],
        "training-failure-recovery": [
            action(1, "run_training"),
            action(2, "generate_config", ["a1:failed"]),
        ],
        "threshold-failure-switch-candidate": [
            action(1, "verify_artifacts"),
            action(2, "generate_config", ["a1:failed"]),
            action(3, "run_training"),
        ],
        "timeout-reduce-training-budget": [
            action(1, "run_training"),
            action(2, "run_training", ["a1:failed"]),
        ],
        "missing-artifact-reverify": [
            action(1, "verify_artifacts"),
            action(2, "run_training", ["a1:failed"]),
            action(3, "verify_artifacts"),
        ],
        "verify-before-report": [
            action(1, "verify_artifacts"),
            action(2, "write_report"),
        ],
        "stop-after-target-hit": [action(1, "verify_artifacts")],
        "hard-action-budget-stop": [action(1, "generate_config")],
        "avoid-duplicate-candidate": [action(1, "generate_config")],
        "reuse-history-best": [
            action(1, "verify_artifacts"),
            action(2, "generate_config"),
        ],
        "consume-reflection-facts": [
            action(1, "run_training"),
            action(2, "generate_config", ["a1:failed"]),
        ],
        "resolve-conflicting-history": [action(1, "generate_config")],
        "compressed-context-constraint": [action(1, "generate_config")],
    }

    if case.case_id == "unknown-tool-rejection":
        actions = [
            _tool_action("a1", "shell", {"command": "echo unsafe"}),
            action(2, "generate_config", ["a1:rejected"]),
        ]
    elif case.case_id == "missing-required-argument":
        invalid = _valid_arguments(case, "generate_config")
        invalid.pop("experiment_id")
        actions = [
            _tool_action("a1", "generate_config", invalid),
            action(2, "generate_config", ["a1:rejected"]),
        ]
    elif case.case_id == "unexpected-argument":
        invalid = _valid_arguments(case, "run_training")
        invalid["shell"] = "echo unsafe"
        actions = [
            _tool_action("a1", "run_training", invalid),
            action(2, "run_training", ["a1:rejected"]),
        ]
    elif case.case_id == "wrong-argument-type":
        invalid = _valid_arguments(case, "run_training")
        invalid["config_path"] = {"nested": "bad"}
        actions = [
            _tool_action("a1", "run_training", invalid),
            action(2, "run_training", ["a1:rejected"]),
        ]
    else:
        actions = scripts[case.case_id]

    if case.expected_statuses != ("max_actions_reached",):
        actions.append(_stop_action(f"a{len(actions) + 1}"))
    return actions


def build_fixture_tool_registry(case: AgentTaskCase) -> ToolRegistry:
    """Use production ToolSpecs with deterministic in-memory tool behavior."""
    production = build_experiment_tool_registry(Path("."))
    registry = ToolRegistry(default_timeout_seconds=1.0)
    calls: dict[str, int] = {}

    def count(name: str) -> int:
        calls[name] = calls.get(name, 0) + 1
        return calls[name]

    def generate_config(**_kwargs: Any) -> dict[str, Any]:
        count("generate_config")
        return {
            "config_path": f"runs/{case.case_id}/configs/{case.case_id}.yaml",
            "artifacts": [f"runs/{case.case_id}/configs/{case.case_id}.yaml"],
            "context_summary": "fixture config generated",
        }

    def run_training(**_kwargs: Any) -> dict[str, Any]:
        invocation = count("run_training")
        if invocation == 1 and case.fault in {
            "training_error", "reflection_fact_available"
        }:
            raise RuntimeError("Injected training error")
        if invocation == 1 and case.fault == "timeout_error":
            raise asyncio.TimeoutError("Injected training timeout")
        return {
            "metrics": {"nmse_db": -36.0, "parameter_count": 3626},
            "artifacts": [f"reports/{case.case_id}/psd.png"],
            "context_summary": "fixture training completed",
        }

    def verify_artifacts(**_kwargs: Any) -> dict[str, Any]:
        invocation = count("verify_artifacts")
        if invocation == 1 and case.fault == "metric_threshold_error":
            raise RuntimeError("NMSE -34.0 exceeds threshold -35.0")
        if invocation == 1 and case.fault == "missing_psd":
            raise FileNotFoundError("Injected missing PSD artifact")
        return {
            "metrics": {"nmse_db": -36.0, "parameter_count": 3626},
            "artifacts": [f"reports/{case.case_id}/psd.png"],
            "context_summary": "fixture artifacts verified",
        }

    def write_report(**_kwargs: Any) -> dict[str, Any]:
        count("write_report")
        return {
            "artifacts": [
                f"reports/{case.case_id}/agent-harness-report.md"
            ],
            "context_summary": "fixture report written",
        }

    functions = {
        "generate_config": generate_config,
        "run_training": run_training,
        "verify_artifacts": verify_artifacts,
        "write_report": write_report,
    }
    for name, function in functions.items():
        registry.register(name, function, production.get_tool_spec(name))
    return registry


async def run_scripted_agent_task_benchmark(
    workspace: Path | str,
    attempts: int = 1,
    cases: list[AgentTaskCase] | None = None,
) -> dict[str, Any]:
    root = Path(workspace)
    selected_cases = cases or build_nonlinear_agent_task_cases()
    attempt_counts: dict[str, int] = {}

    async def execute_case(case: AgentTaskCase):
        attempt_counts[case.case_id] = attempt_counts.get(case.case_id, 0) + 1
        attempt = attempt_counts[case.case_id]
        session_id = f"agent-task-{case.case_id}-a{attempt}"
        registry = build_fixture_tool_registry(case)
        planner = AgentActionPlanner(
            FakeLLMClient(responses=build_scripted_actions(case)), registry
        )
        loop = ActionPlannerLoop(
            planner=planner,
            tool_registry=registry,
            runtime_factory=lambda current_session_id: ExperimentHarnessRuntime(
                tool_registry=registry,
                session_store=SessionStore(root / "sessions"),
                trace_logger=TraceLogger(
                    root / "traces" / f"{current_session_id}.jsonl"
                ),
            ),
            session_id=session_id,
            constraints={"parameter_count_max": 4000, "domain": case.domain},
        )
        return await loop.run(case.goal, max_actions=case.max_actions)

    report = await run_agent_task_benchmark(
        selected_cases, execute_case, attempts=attempts
    )
    report["evaluation_mode"] = "scripted_fixture"
    report["provenance"] = {
        "planner": "FakeLLMClient scripted actions",
        "tool_schemas": "production ToolSpec",
        "tool_outputs": "deterministic fault fixture",
    }
    return report


async def run_llm_agent_task_benchmark(
    workspace: Path | str,
    attempts: int = 3,
    cases: list[AgentTaskCase] | None = None,
    client_factory: Any | None = None,
    model: str = "deepseek-v4-flash",
    timeout_seconds: float = 90.0,
) -> dict[str, Any]:
    """Evaluate a real planner against production schemas and fixed fault facts."""
    root = Path(workspace)
    selected_cases = cases or build_nonlinear_agent_task_cases()
    attempt_counts: dict[str, int] = {}

    if client_factory is None:
        from nonlinear_agent.server import _load_dotenv
        from nonlinear_agent.llm import OpenAICompatibleClient

        _load_dotenv(root)
        client_factory = lambda: OpenAICompatibleClient.deepseek(
            model=model, timeout_seconds=timeout_seconds, role="planner"
        )

    async def execute_case(case: AgentTaskCase):
        attempt_counts[case.case_id] = attempt_counts.get(case.case_id, 0) + 1
        attempt = attempt_counts[case.case_id]
        session_id = f"agent-task-online-{case.case_id}-a{attempt}"
        registry = build_fixture_tool_registry(case)
        client = client_factory()
        planner = AgentActionPlanner(client, registry)
        loop = ActionPlannerLoop(
            planner=planner,
            tool_registry=registry,
            runtime_factory=lambda current_session_id: ExperimentHarnessRuntime(
                tool_registry=registry,
                session_store=SessionStore(root / "sessions"),
                trace_logger=TraceLogger(
                    root / "traces" / f"{current_session_id}.jsonl"
                ),
            ),
            session_id=session_id,
            constraints={
                "parameter_count_max": 4000,
                "nmse_threshold_db": -35.0,
                "domain": case.domain,
                "benchmark_case_id": case.case_id,
                "benchmark_fault": case.fault,
            },
        )
        return await loop.run(
            case.goal,
            max_actions=case.max_actions,
            initial_history=build_initial_fault_history(case),
        )

    report = await run_agent_task_benchmark(
        selected_cases, execute_case, attempts=attempts
    )
    report["evaluation_mode"] = "real_llm_fault_fixture"
    report["provenance"] = {
        "planner": f"DeepSeek {model}",
        "tool_schemas": "production ToolSpec",
        "tool_outputs": "deterministic fault fixture",
        "claim_scope": "LLM action selection and recovery, not model-training quality",
    }
    return report


def write_agent_task_benchmark_artifacts(
    output_dir: Path | str, report: dict[str, Any]
) -> list[Path]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / "results.json"
    markdown_path = root / "summary.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = [
        "# Agent Task Benchmark",
        "",
        f"- Domain: `{report.get('domain', 'unknown')}`",
        f"- Evaluation mode: `{report.get('evaluation_mode', 'unknown')}`",
        f"- Tasks: {report.get('task_count', 0)}",
        f"- Attempts: {report.get('attempt_count', 0)}",
        f"- pass@1: {float(report.get('pass_at_1', 0.0)):.3f}",
        "",
        "| Case | Attempt | Passed | Passed checks | Failed checks |",
        "| --- | ---: | --- | --- | --- |",
    ]
    for row in report.get("results", []):
        passed_checks = ", ".join(row.get("passed_checks", [])) or "-"
        failed_checks = ", ".join(row.get("failed_checks", [])) or "-"
        lines.append(
            f"| `{row.get('case_id', '')}` | {row.get('attempt', '')} | "
            f"{row.get('passed', False)} | {passed_checks} | {failed_checks} |"
        )
    lines.extend([
        "",
        "Scripted fixture results prove harness contract regression only. "
        "They do not measure autonomous LLM reasoning quality.",
        "",
    ])
    markdown_path.write_text("\n".join(lines), encoding="utf-8")
    return [json_path, markdown_path]
