"""SyntheticRegressionDomain — lightweight second domain plugin.

A minimal domain that proves the Agent Harness is transferable to new
experiment types. Uses NumPy to generate synthetic regression data.

Tools: fit_candidate (fits a polynomial model), evaluate_candidate (computes MSE).
Metric: val_mse (lower is better).

This domain does NOT use PyTorch — it exists solely to demonstrate that
the Planner / Guard / Loop / Runtime / Tool chain works for a different
domain without changing any harness code.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from nonlinear_agent.tools import ToolRegistry, ToolSpec


SYNTHETIC_PLANNER_INSTRUCTIONS = (
    "Design polynomial regression experiments for synthetic data.\n"
    "- degree: polynomial degree (1-5). Higher degrees can overfit.\n"
    "- reg_strength: L2 regularization strength (1e-4 to 1e-1).\n"
    "- Prefer simpler models (lower degree) when MSE is similar.\n"
    "Use overrides for: degree, reg_strength.\n"
)


class SyntheticRegressionDomain:
    """Minimal domain for synthetic polynomial regression."""

    name = "synthetic-regression"

    def planner_instructions(self) -> str:
        return SYNTHETIC_PLANNER_INSTRUCTIONS

    def design_space(self) -> dict[str, list[object]]:
        return {
            "degree": [1, 2, 3, 4, 5],
            "reg_strength": [1e-4, 1e-3, 1e-2, 1e-1],
        }

    def validate_candidate(
        self, overrides: dict[str, object], parameter_count_max: int = 100
    ) -> list[str]:
        errors: list[str] = []
        degree = overrides.get("degree", 1)
        if not isinstance(degree, int) or isinstance(degree, bool) or degree < 1 or degree > 5:
            errors.append("degree must be an integer in [1, 5].")
        reg = overrides.get("reg_strength", 1e-3)
        if not isinstance(reg, (int, float)) or isinstance(reg, bool):
            errors.append("reg_strength must be a number.")
        elif float(reg) < 1e-4 or float(reg) > 1e-1:
            errors.append("reg_strength must be in [1e-4, 1e-1].")
        return errors

    def build_tool_registry(
        self, workspace: Path, default_timeout_seconds: float = 300.0
    ) -> ToolRegistry:
        registry = ToolRegistry(default_timeout_seconds=default_timeout_seconds)

        registry.register(
            "fit_candidate",
            _fit_candidate_tool,
            spec=ToolSpec(
                name="fit_candidate",
                description="Fit a polynomial regression model to synthetic data.",
                input_schema={"type": "object", "required": ["degree", "reg_strength"]},
                category="experiment",
                error_policy="return_error",
            ),
        )

        registry.register(
            "evaluate_candidate",
            _evaluate_candidate_tool,
            spec=ToolSpec(
                name="evaluate_candidate",
                description="Evaluate a fitted model on the validation set. Returns val_mse.",
                input_schema={"type": "object", "required": ["model_state"]},
                category="experiment",
                error_policy="return_error",
            ),
        )

        return registry

    def primary_metric(self) -> str:
        return "val_mse"

    def is_better(self, candidate: dict, incumbent: dict) -> bool:
        return float(candidate.get("val_mse", float("inf"))) < float(
            incumbent.get("val_mse", float("inf"))
        )

    def default_base_config(self) -> str:
        return "configs/examples/synthetic-regression.yaml"

    def default_constraints(self) -> dict:
        return {"parameter_count_max": 100, "metric": "val_mse"}

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
            epochs=0, learning_rate=0.0, optimizer="",
            nmse_threshold_db=0.0,
            timeout_seconds=timeout_seconds,
            overrides=overrides,
        )

    def build_harness_steps(self, spec, workspace):
        from nonlinear_agent.tools import ToolCall
        output_dir = spec.output_dir or f"reports/{spec.session_id}"
        overrides = {"output_dir": output_dir, **spec.overrides}
        return [
            ToolCall(name="fit_candidate", args={
                "degree": int(overrides.get("degree", 2)),
                "reg_strength": float(overrides.get("reg_strength", 0.001)),
            }),
            ToolCall(name="evaluate_candidate", args={}),
        ]

    # ── v2.1: Display configuration ─────────────────────────────
    def display_metric_names(self) -> set[str]:
        return {"val_mse", "train_mse", "degree", "reg_strength"}

    def display_metric_unit(self) -> str:
        return ""

    def display_metric_lower_is_better(self) -> bool:
        return True

    def artifact_preview_patterns(self) -> list[str]:
        return []

    # ── v2.1: Guard / Planner config ────────────────────────────
    def allowed_override_fields(self) -> set[str]:
        return {"degree", "reg_strength", "output_dir"}

    def planner_allowed_tools(self) -> list[str]:
        return ["fit_candidate", "evaluate_candidate"]


# ── Tool implementations ────────────────────────────────────────────

_GLOBAL_MODEL: dict[str, Any] = {}  # Simple in-memory store for demo


def _fit_candidate_tool(
    degree: int, reg_strength: float = 1e-3, **_kw: Any
) -> dict[str, Any]:
    """Fit a polynomial of given degree with L2 regularization."""
    rng = np.random.default_rng(42)
    n_samples = 200
    x = np.linspace(-3, 3, n_samples)
    true_coeffs = np.array([0.5, -1.5, 0.8, 0.0, 0.0, 0.0][: degree + 1])
    y_true = np.polyval(true_coeffs[::-1], x)
    y = y_true + rng.normal(0, 0.5, n_samples)

    A = np.vander(x, degree + 1, increasing=True)
    I = np.eye(degree + 1)
    I[0, 0] = 0  # Don't regularize the bias
    coeffs = np.linalg.solve(A.T @ A + reg_strength * I, A.T @ y)

    _GLOBAL_MODEL["coeffs"] = coeffs.tolist()
    _GLOBAL_MODEL["degree"] = degree
    train_pred = A @ coeffs
    train_mse = float(np.mean((y - train_pred) ** 2))

    return {
        "model_state": {"coeffs": coeffs.tolist(), "degree": degree},
        "train_mse": train_mse,
        "context_summary": f"Fitted polynomial degree={degree} with reg={reg_strength}, train_mse={train_mse:.6f}",
    }


def _evaluate_candidate_tool(
    model_state: dict[str, Any] | None = None, **_kw: Any
) -> dict[str, Any]:
    """Evaluate the fitted model on validation data.

    Falls back to _GLOBAL_MODEL when model_state is empty or missing keys,
    so build_harness_steps can call this with {} after fit_candidate.
    """
    if not model_state or "coeffs" not in model_state:
        model_state = _GLOBAL_MODEL
    rng = np.random.default_rng(99)
    n_samples = 100
    x_val = np.linspace(-3.5, 3.5, n_samples)
    true_coeffs = np.array([0.5, -1.5, 0.8, 0.0, 0.0, 0.0][: model_state["degree"] + 1])
    y_true = np.polyval(true_coeffs[::-1], x_val)
    y_val = y_true + rng.normal(0, 0.5, n_samples)

    coeffs = np.array(model_state["coeffs"])
    y_pred = np.polyval(coeffs[::-1], x_val)
    val_mse = float(np.mean((y_val - y_pred) ** 2))

    return {
        "val_mse": val_mse,
        "metrics": {"val_mse": val_mse},
        "context_summary": f"Evaluated model: val_mse={val_mse:.6f}",
    }
