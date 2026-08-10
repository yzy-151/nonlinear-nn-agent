"""Independent nonlinear-modeling tasks for action-level agent evaluation."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class AgentTaskCase:
    case_id: str
    goal: str
    category: str
    domain: str = "nonlinear-modeling"
    max_actions: int = 12
    required_tools: tuple[str, ...] = ()
    forbidden_tools: tuple[str, ...] = ()
    expected_statuses: tuple[str, ...] = ("stopped",)
    require_tool_order: bool = False
    require_rejection: bool = False
    require_causal_recovery: bool = False
    required_metric: str | None = None
    required_artifact_suffix: str | None = None
    fault: str | None = None


def build_nonlinear_agent_task_cases() -> list[AgentTaskCase]:
    """Return 18 semantically distinct tasks for one real project domain."""
    cases = [
        AgentTaskCase(
            "complete-experiment",
            "Complete one nonlinear-modeling experiment and produce verified evidence.",
            "workflow",
            required_tools=("generate_config", "run_training", "verify_artifacts", "write_report"),
            require_tool_order=True,
            required_metric="nmse_db",
            required_artifact_suffix="agent-harness-report.md",
        ),
        AgentTaskCase(
            "generate-config-only",
            "Generate a valid constrained experiment config, then stop before training.",
            "workflow",
            required_tools=("generate_config",),
            forbidden_tools=("run_training",),
        ),
        AgentTaskCase(
            "unknown-tool-rejection",
            "Reject an unavailable shell tool and recover with a registered experiment tool.",
            "contract",
            required_tools=("generate_config",),
            require_rejection=True,
            fault="unknown_tool",
        ),
        AgentTaskCase(
            "missing-required-argument",
            "Repair a generate_config action that omits experiment_id.",
            "contract",
            required_tools=("generate_config",),
            require_rejection=True,
            fault="missing_required_argument",
        ),
        AgentTaskCase(
            "unexpected-argument",
            "Remove an argument not allowed by the selected ToolSpec and retry.",
            "contract",
            required_tools=("run_training",),
            require_rejection=True,
            fault="unexpected_argument",
        ),
        AgentTaskCase(
            "wrong-argument-type",
            "Correct a nested object passed where config_path must be a string.",
            "contract",
            required_tools=("run_training",),
            require_rejection=True,
            fault="wrong_argument_type",
        ),
        AgentTaskCase(
            "training-failure-recovery",
            "Recover from a training runtime failure using its event id.",
            "recovery",
            required_tools=("run_training", "generate_config"),
            require_causal_recovery=True,
            fault="training_error",
        ),
        AgentTaskCase(
            "threshold-failure-switch-candidate",
            "After NMSE threshold failure, change the candidate before training again.",
            "recovery",
            required_tools=("verify_artifacts", "generate_config", "run_training"),
            require_causal_recovery=True,
            fault="metric_threshold_error",
        ),
        AgentTaskCase(
            "timeout-reduce-training-budget",
            "After training timeout, reduce the training budget and retry once.",
            "recovery",
            required_tools=("run_training",),
            require_causal_recovery=True,
            fault="timeout_error",
        ),
        AgentTaskCase(
            "missing-artifact-reverify",
            "Recover when PSD verification reports a missing artifact.",
            "artifact",
            required_tools=("verify_artifacts", "run_training"),
            require_causal_recovery=True,
            required_metric="nmse_db",
            fault="missing_psd",
        ),
        AgentTaskCase(
            "verify-before-report",
            "Do not write the report until metrics and PSD have been verified.",
            "workflow",
            required_tools=("verify_artifacts", "write_report"),
            require_tool_order=True,
            required_artifact_suffix="agent-harness-report.md",
        ),
        AgentTaskCase(
            "stop-after-target-hit",
            "Stop immediately after a verified NMSE target hit.",
            "control",
            required_tools=("verify_artifacts",),
            forbidden_tools=("generate_config",),
            max_actions=3,
            required_metric="nmse_db",
        ),
        AgentTaskCase(
            "hard-action-budget-stop",
            "Respect a one-action hard budget even if the experiment is incomplete.",
            "control",
            max_actions=1,
            required_tools=("generate_config",),
            expected_statuses=("max_actions_reached",),
        ),
        AgentTaskCase(
            "avoid-duplicate-candidate",
            "Use the observed config hash to avoid repeating the previous candidate.",
            "history",
            required_tools=("generate_config",),
            fault="duplicate_candidate",
        ),
        AgentTaskCase(
            "reuse-history-best",
            "Use the best previous experiment as evidence for the next candidate.",
            "history",
            required_tools=("generate_config",),
            required_metric="nmse_db",
            fault="historical_best_available",
        ),
        AgentTaskCase(
            "consume-reflection-facts",
            "Use reflection facts from a failed experiment in the next action.",
            "reflection",
            required_tools=("generate_config",),
            require_causal_recovery=True,
            fault="reflection_fact_available",
        ),
        AgentTaskCase(
            "resolve-conflicting-history",
            "Prefer newer trace-backed evidence when historical candidates conflict.",
            "history",
            required_tools=("generate_config",),
            fault="conflicting_history",
        ),
        AgentTaskCase(
            "compressed-context-constraint",
            "Preserve parameter budget and failure facts after history compression.",
            "context",
            required_tools=("generate_config",),
            fault="compressed_history",
        ),
    ]
    validate_agent_task_catalog(cases)
    return cases


def validate_agent_task_catalog(cases: list[AgentTaskCase]) -> None:
    ids: set[str] = set()
    semantics: set[str] = set()
    for case in cases:
        if case.case_id in ids:
            raise ValueError(f"Duplicate task id: {case.case_id}")
        ids.add(case.case_id)
        payload = asdict(case)
        payload.pop("case_id")
        signature = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        if signature in semantics:
            raise ValueError(f"Duplicate task semantics: {case.case_id}")
        semantics.add(signature)
