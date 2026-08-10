"""Structured handoff from IdeaPlanSpec to execution (v3.7.0).

Only gate-passed plans reach this converter. Each candidate experiment is
projected to an execution step with an explicit config hash, budget and
stop condition, so downstream workers never re-derive intent.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ExecutionStep:
    step_id: str
    config_hash: str
    overrides: dict[str, Any]
    budget: dict[str, Any]
    stop_condition: str
    rationale: str
    citations: tuple[str, ...] = ()


class PlanHandoff:
    """Converts a validated IdeaPlanSpec into executable steps."""

    def to_execution(self, plan: dict[str, Any]) -> list[ExecutionStep]:
        steps: list[ExecutionStep] = []
        for index, candidate in enumerate(plan.get("candidate_experiments", [])):
            overrides = {
                key: value
                for key, value in candidate.items()
                if key
                not in {
                    "params_estimate",
                    "budget",
                    "stop_condition",
                    "rationale",
                    "citation",
                    "config_hash",
                }
            }
            config_hash = str(
                candidate.get("config_hash")
                or hashlib.sha256(
                    json.dumps(overrides, sort_keys=True, default=str).encode()
                ).hexdigest()
            )
            steps.append(
                ExecutionStep(
                    step_id=f"{plan.get('plan_id', 'plan')}-step-{index + 1:03d}",
                    config_hash=config_hash,
                    overrides=overrides,
                    budget=dict(candidate.get("budget", {})),
                    stop_condition=str(candidate.get("stop_condition", "")),
                    rationale=str(candidate.get("rationale", "")),
                    citations=(
                        (str(candidate["citation"]),)
                        if candidate.get("citation")
                        else ()
                    ),
                )
            )
        return steps
