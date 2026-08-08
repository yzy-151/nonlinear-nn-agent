"""Unified evaluation protocol for fair comparison of search strategies.

Defines fixed budgets, seeds, and methods. All strategies share the same
data split, candidate space, trial budget, and termination conditions.

Protocol variants:
  - smoke: 4 methods x 2 seeds x 3 trials = 24 effective training trials
  - full:  4 methods x 5 seeds x 10 trials = 200 effective training trials
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


METHODS = ["random_search", "optuna_tpe", "llm_direct", "llm_program_reflection"]
SEEDS_FULL = [7, 17, 29, 43, 61]
SEEDS_SMOKE = [7, 17]


@dataclass
class EvaluationProtocol:
    """Fixed evaluation protocol for search strategy comparison."""

    methods: list[str] = field(default_factory=lambda: list(METHODS))
    seeds: list[int] = field(default_factory=lambda: list(SEEDS_FULL))
    trial_budget: int = 10
    parameter_count_max: int = 4000
    nmse_threshold_db: float = -35.0
    llm_provider: str = "simulated"

    def estimate_total_trials(self) -> int:
        return len(self.methods) * len(self.seeds) * self.trial_budget

    def to_dict(self) -> dict[str, Any]:
        return {
            "methods": self.methods,
            "seeds": self.seeds,
            "trial_budget": self.trial_budget,
            "parameter_count_max": self.parameter_count_max,
            "nmse_threshold_db": self.nmse_threshold_db,
            "llm_provider": self.llm_provider,
            "estimated_total_trials": self.estimate_total_trials(),
        }


def build_full_protocol() -> EvaluationProtocol:
    return EvaluationProtocol(
        methods=list(METHODS),
        seeds=list(SEEDS_FULL),
        trial_budget=10,
    )


def build_smoke_protocol() -> EvaluationProtocol:
    return EvaluationProtocol(
        methods=list(METHODS),
        seeds=list(SEEDS_SMOKE),
        trial_budget=3,
    )


TRIAL_RECORD_FIELDS = [
    "run_id",
    "method",
    "seed",
    "trial_index",
    "config_hash",
    "dataset_hash",
    "git_commit",
    "model_type",
    "parameter_count",
    "nmse_db",
    "target_hit",
    "training_seconds",
    "planner_latency_ms",
    "prompt_tokens",
    "completion_tokens",
    "estimated_cost_usd",
    "rejected",
    "runtime_failed",
    "reflection_used",
]


def build_trial_record(
    run_id: str,
    method: str,
    seed: int,
    trial_index: int,
    config_hash: str = "unknown",
    dataset_hash: str = "unknown",
    git_commit: str = "unknown",
    model_type: str = "unknown",
    parameter_count: int = 0,
    nmse_db: float = 0.0,
    target_hit: bool = False,
    training_seconds: float = 0.0,
    planner_latency_ms: float = 0.0,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    estimated_cost_usd: float = 0.0,
    rejected: bool = False,
    runtime_failed: bool = False,
    reflection_used: bool = False,
    metric_name: str = "nmse_db",
    metric_value: float | None = None,
) -> dict[str, Any]:
    """Build a trial record.

    For non-NMSE domains, pass metric_name + metric_value (e.g.
    metric_name="val_mse", metric_value=0.19). The metric value is also
    stored under the dynamic key {metric_name} for statistics functions.
    """
    record = {
        "run_id": run_id,
        "method": method,
        "seed": seed,
        "trial_index": trial_index,
        "config_hash": config_hash,
        "dataset_hash": dataset_hash,
        "git_commit": git_commit,
        "model_type": model_type,
        "parameter_count": parameter_count,
        "nmse_db": nmse_db,
        "target_hit": target_hit,
        "training_seconds": training_seconds,
        "planner_latency_ms": planner_latency_ms,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "estimated_cost_usd": estimated_cost_usd,
        "rejected": rejected,
        "runtime_failed": runtime_failed,
        "reflection_used": reflection_used,
        "metric_name": metric_name,
    }
    if metric_value is not None:
        record[metric_name] = metric_value
        record["metric_value"] = metric_value
        if metric_name == "nmse_db":
            record["nmse_db"] = metric_value
    return record
