"""NonlinearModelingDomain — RF nonlinear system modeling domain plugin.

Extracts ALL domain-specific knowledge that was previously hardcoded in
planner.py (prompt text), planner_validation.py (parameter estimation,
feature width, field validation), and loop.py (base config, constraints).

This domain covers:
- Nonlinear RF memory-polynomial (MPDPD) signal fitting
- Models: complex_lstsq, linear, tiny_mlp, spline_mlp, complex_cnn
- Features: complex_mp, legacy_abs
- Metric: NMSE in dB (lower is better)
"""

from __future__ import annotations

from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Any

from nonlinear_agent.experiment_tools import (
    build_experiment_tool_registry,
    generate_config_tool,
    run_training_tool,
    verify_artifacts_tool,
    write_report_tool,
)
from nonlinear_agent.tools import ToolRegistry, ToolSpec

if TYPE_CHECKING:
    pass


# ── Field aliases and blacklist ────────────────────────────────────
# These were previously in planner_validation.py

ALIAS_FIELDS: dict[str, str] = {
    "train_samples": "max_train_samples",
}

UNSUPPORTED_FIELDS: set[str] = {
    "rank", "parameter_count", "nmse_db", "status",
    "final_train_loss", "samples", "evaluation_samples",
}

# Model types that use neural training (need epochs >= 1)
NEURAL_MODEL_TYPES: set[str] = {"tiny_mlp", "spline_mlp", "linear", "complex_cnn"}

# Fields that must be positive integers
POSITIVE_INT_FIELDS: tuple[str, ...] = (
    "memory_depth", "mp_order_count", "hidden_units",
    "spline_knots", "batch_size", "max_train_samples",
)

# Fields that must be numbers
FLOAT_FIELDS: tuple[str, ...] = ("learning_rate", "scheduler_gamma", "train_ratio")

# ── Planner instructions (was hardcoded in planner.py _build_prompt) ──

PLANNER_INSTRUCTIONS = (
    "Executable design space:\n"
    "- model_type: complex_lstsq, linear, tiny_mlp, spline_mlp.\n"
    "- feature_mode: complex_mp is preferred for RF nonlinear memory "
    "polynomial structure; legacy_abs is a baseline.\n"
    "- complex_lstsq explores memory_depth and mp_order_count "
    "with closed-form fitting.\n"
    "- tiny_mlp explores hidden_units and activation in "
    "relu/tanh/silu/gelu.\n"
    "- spline_mlp is a physics-informed shallow nonlinear model: "
    "one nonlinear layer with a learnable 1D LUT activation, "
    "usually spline_knots=16 and first-order linear interpolation.\n"
    "- Good spline_mlp candidates under 4000 params: "
    "feature_mode=complex_mp, mp_order_count=1, "
    "memory_depth in [24, 48, 72], hidden_units in [16, 32], "
    "spline_knots=16.\n"
    "- Keep parameter_count_max from constraints; prefer fewer "
    "parameters when NMSE is similar.\n"
    "- Compare model performance from history before designing new experiments. "
    "If a model family consistently outperforms others with fewer parameters "
    "and less training time, prefer it.\n"
    "- spline_mlp/tiny_mlp require epochs >= 1. If you forget to set epochs "
    "the runtime will inject epochs=200.\n"
    "Use overrides for YAML config fields such as model_type, "
    "feature_mode, memory_depth, mp_order_count, epochs, "
    "learning_rate, optimizer, output_dir, hidden_units, "
    "activation, spline_knots, spline_range. "
    "Do not output shell commands. "
)

# ── Default constraints (was hardcoded in loop.py and server.py) ──

DEFAULT_PARAMETER_COUNT_MAX = 4000
DEFAULT_NMSE_THRESHOLD_DB = -35.0
DEFAULT_BASE_CONFIG = "configs/baselines/lstsq-complexmp-o12-m150.yaml"


class NonlinearModelingDomain:
    """Domain plugin for RF nonlinear-system modeling experiments."""

    name = "nonlinear-modeling"

    # ── Planner interface ──────────────────────────────────────
    def planner_instructions(self) -> str:
        return PLANNER_INSTRUCTIONS

    def design_space(self) -> dict[str, list[object]]:
        return {
            "model_type": ["complex_lstsq", "linear", "tiny_mlp", "spline_mlp"],
            "feature_mode": ["complex_mp", "legacy_abs"],
            "activation": ["relu", "tanh", "silu", "gelu"],
            "optimizer": ["adam", "sgd", "adamw"],
            "memory_depth": [5, 8, 12, 24, 32, 48, 72, 100, 150, 220],
            "mp_order_count": [1, 2, 3, 4, 6, 8, 9, 12],
            "hidden_units": [16, 32, 48, 64],
            "spline_knots": [8, 12, 16, 24, 32],
            "epochs": [0, 50, 100, 200, 400, 600],
        }

    def validate_candidate(
        self, overrides: dict[str, object], parameter_count_max: int = 4000
    ) -> list[str]:
        errors: list[str] = []

        model_type = str(overrides.get("model_type", "complex_cnn"))
        feature_mode = str(overrides.get("feature_mode", "legacy_abs"))
        memory_depth = int(overrides.get("memory_depth", 5))
        mp_order_count = int(overrides.get("mp_order_count", 4))
        hidden_units = int(overrides.get("hidden_units", 64))
        spline_knots = int(overrides.get("spline_knots", 16))

        # spline_range must be a number
        if "spline_range" in overrides and not _is_number(overrides["spline_range"]):
            errors.append("spline_range must be a number.")

        # Positive-int fields
        for field in POSITIVE_INT_FIELDS:
            if field in overrides and not _is_positive_int(overrides[field]):
                errors.append(f"{field} must be a positive integer.")

        # epochs
        if "epochs" in overrides:
            val = overrides["epochs"]
            if (
                not isinstance(val, int)
                or isinstance(val, bool)
                or val < 0
            ):
                errors.append("epochs must be a non-negative integer.")
            elif model_type in NEURAL_MODEL_TYPES and val < 1:
                errors.append(f"epochs must be >= 1 for neural model {model_type}.")

        # Float fields
        for field in FLOAT_FIELDS:
            if field in overrides and not _is_number(overrides[field]):
                errors.append(f"{field} must be a number.")

        # Parameter budget
        param_count = _estimate_parameter_count(
            model_type, feature_mode, memory_depth,
            mp_order_count, hidden_units, spline_knots,
        )
        if param_count is not None and param_count > parameter_count_max:
            errors.append(
                f"Estimated parameter count {param_count} "
                f"exceeds parameter budget {parameter_count_max}."
            )

        return errors

    # ── Tool registry ─────────────────────────────────────────
    def build_tool_registry(
        self, workspace: Path, default_timeout_seconds: float = 300.0
    ) -> ToolRegistry:
        return build_experiment_tool_registry(workspace, default_timeout_seconds)

    # ── Metric semantics ───────────────────────────────────────
    def primary_metric(self) -> str:
        return "nmse_db"

    def is_better(self, candidate: dict, incumbent: dict) -> bool:
        return float(candidate.get("nmse_db", 0)) < float(incumbent.get("nmse_db", 0))

    # ── Defaults ──────────────────────────────────────────────
    def default_base_config(self) -> str:
        return DEFAULT_BASE_CONFIG

    def default_constraints(self) -> dict:
        return {
            "parameter_count_max": DEFAULT_PARAMETER_COUNT_MAX,
            "metric": "nmse_db",
            "nmse_threshold_db": DEFAULT_NMSE_THRESHOLD_DB,
        }

    def default_epochs(self) -> int:
        return 200

    def default_learning_rate(self) -> float:
        return 0.0008

    def default_optimizer(self) -> str:
        return "adam"

    # ── v2.1: Execution workflow ────────────────────────────────
    def build_harness_spec(
        self, session_id: str, base_config: str, overrides: dict,
        constraints: dict, timeout_seconds: float,
    ):
        from nonlinear_agent.server import HarnessRunSpec
        output_dir = str(overrides.get("output_dir", f"reports/{session_id}"))
        return HarnessRunSpec(
            session_id=session_id,
            base_config=base_config,
            output_dir=output_dir,
            epochs=int(overrides.get("epochs", self.default_epochs())),
            learning_rate=float(overrides.get("learning_rate", self.default_learning_rate())),
            optimizer=str(overrides.get("optimizer", self.default_optimizer())),
            nmse_threshold_db=float(overrides.get(
                "nmse_threshold_db",
                constraints.get("nmse_threshold_db", DEFAULT_NMSE_THRESHOLD_DB),
            )),
            timeout_seconds=timeout_seconds,
            overrides=overrides,
        )

    def build_harness_steps(self, spec, workspace):
        from pathlib import Path as _Path
        from nonlinear_agent.tools import ToolCall
        from nonlinear_agent.artifact_paths import trial_config_path
        root = _Path(workspace) if not isinstance(workspace, _Path) else workspace
        output_dir = spec.output_dir or f"reports/{spec.session_id}"
        merged_overrides = {
            "output_dir": output_dir,
            "epochs": spec.epochs,
            "learning_rate": spec.learning_rate,
            "optimizer": spec.optimizer,
        }
        merged_overrides.update(spec.overrides)
        merged_overrides["output_dir"] = output_dir
        return [
            ToolCall(name="generate_config", args={
                "base_config_path": spec.base_config,
                "experiment_id": spec.session_id,
                "overrides": merged_overrides,
            }),
            ToolCall(name="run_training", args={
                "config_path": str(trial_config_path(spec.session_id, spec.session_id)),
                "timeout_seconds": spec.timeout_seconds,
            }, timeout_seconds=spec.timeout_seconds + 5),
            ToolCall(name="verify_artifacts", args={
                "output_dir": output_dir,
                "nmse_threshold_db": spec.nmse_threshold_db,
            }),
            ToolCall(name="write_report", args={"session_id": spec.session_id}),
        ]

    # ── v2.1: Display configuration ─────────────────────────────
    def display_metric_names(self) -> set[str]:
        return {"nmse_db", "baseline_nmse_db", "nmse_improvement_db", "parameter_count", "final_train_loss"}

    def display_metric_unit(self) -> str:
        return "dB"

    def display_metric_lower_is_better(self) -> bool:
        return True

    def artifact_preview_patterns(self) -> list[str]:
        return ["psd.png"]

    # ── v2.1: Guard / Planner config ────────────────────────────
    def allowed_override_fields(self) -> set[str]:
        from nonlinear_agent.experiment import ExperimentConfig
        return set(ExperimentConfig.__dataclass_fields__)

    def planner_allowed_tools(self) -> list[str]:
        return ["generate_config", "run_training", "verify_artifacts", "write_report"]


# ── Migrated from planner_validation.py ────────────────────────────

def _estimate_parameter_count(
    model_type: str,
    feature_mode: str,
    memory_depth: int,
    mp_order_count: int,
    hidden_units: int = 64,
    spline_knots: int = 16,
) -> int | None:
    """Estimate parameter count for a given model configuration."""
    feature_width = _feature_width(feature_mode, memory_depth, mp_order_count)
    input_dim = 2 * feature_width

    if model_type == "complex_lstsq":
        return 2 * (feature_width + 1)
    if model_type == "linear":
        return input_dim * 2 + 2
    if model_type == "tiny_mlp":
        return input_dim * hidden_units + hidden_units + hidden_units * 2 + 2
    if model_type == "spline_mlp":
        return (
            input_dim * hidden_units
            + hidden_units
            + hidden_units * spline_knots
            + hidden_units * 2
            + 2
        )
    if model_type == "complex_cnn":
        return None
    raise ValueError(f"Unsupported model_type: {model_type}")


def _feature_width(
    feature_mode: str, memory_depth: int, mp_order_count: int
) -> int:
    if feature_mode == "complex_mp":
        return mp_order_count * (memory_depth + 1)
    if feature_mode == "legacy_abs":
        return 4 * (memory_depth + 1)
    raise ValueError(f"Unsupported feature_mode: {feature_mode}")


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0
