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

import hashlib
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
            "reg_strength": [1e-4, 0.001, 0.01, 0.1, 0.5, 1.0, 5.0, 10.0, 50.0, 100.0],
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
        elif float(reg) < 1e-4 or float(reg) > 100:
            errors.append("reg_strength must be in [1e-4, 100].")
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

    def dataset_fingerprint(self) -> str:
        """Deterministic fingerprint of the fixed synthetic data split."""
        payload = (
            "synthetic-regression|seed=42|true_degree=5|"
            "true_coeffs=0.5,-1.8,2.1,-0.9,0.3,-0.05|train_n=200|val_n=100"
        )
        return hashlib.sha256(payload.encode()).hexdigest()

    def historical_priors(self) -> list[Any]:
        """No historical priors exist for the synthetic demo domain."""
        return []
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


class SyntheticLargeDomain(SyntheticRegressionDomain):
    """Enlarged synthetic regression design space for strategy comparison.

    50-point space (5 degrees x 10 regs) is too small: with a 50-trial budget
    any dedup'd strategy nearly enumerates it, so strategy differences only
    show up in convergence speed. This domain grows the space to
    20 degrees x 20 log-spaced regs = 400 combinations, so a 50-trial budget
    covers only ~12% of the space and search quality actually matters.

    Validation stays range-based (like the parent): reg_strength is a
    continuous L2 penalty in [1e-4, 100], so a real LLM may propose any
    value in range; the design_space list drives the offline samplers.
    """

    name = "synthetic-large"

    def design_space(self) -> dict[str, list[object]]:
        import numpy as np

        return {
            "degree": list(range(1, 21)),
            "reg_strength": [float(x) for x in np.logspace(-4, 2, 20)],
        }

    def validate_candidate(
        self, overrides: dict[str, object], parameter_count_max: int = 100
    ) -> list[str]:
        errors: list[str] = []
        degree = overrides.get("degree", 1)
        if (
            not isinstance(degree, int)
            or isinstance(degree, bool)
            or degree < 1
            or degree > 20
        ):
            errors.append("degree must be an integer in [1, 20].")
        reg = overrides.get("reg_strength", 1e-3)
        if not isinstance(reg, (int, float)) or isinstance(reg, bool):
            errors.append("reg_strength must be a number.")
        elif float(reg) < 1e-4 or float(reg) > 100:
            errors.append("reg_strength must be in [1e-4, 100].")
        return errors

    def planner_instructions(self) -> str:
        return (
            "Design polynomial regression experiments for synthetic data.\n"
            "- degree: polynomial degree (1-20). The true function is "
            "degree-5; lower degrees underfit, very high degrees may overfit.\n"
            "- reg_strength: L2 regularization strength (1e-4 to 100). "
            "Small values are usually best; too-large values add bias.\n"
            "- Prefer simpler models (lower degree) when MSE is similar.\n"
            "Use overrides for: degree, reg_strength.\n"
        )

    def historical_priors(self) -> list[Any]:
        """Simulated historical best candidates (verified val_mse).

        The strategy-comparison protocol needs a knowledge source for
        llm_program_reflection: in the real business domain, priors come from
        previous experiment logs; here they stand in for "project history".
        Values are real evaluations (fit + evaluate on the same data split).
        """
        from nonlinear_agent.priors import HistoricalPrior

        return [
            HistoricalPrior(
                id="synthetic-prior-b",
                overrides={"degree": 5, "reg_strength": 0.01},
                known_nmse_db=0.043382,
                parameter_count=6,
                source="synthetic-history",
            ),
            HistoricalPrior(
                id="synthetic-prior-a",
                overrides={"degree": 5, "reg_strength": 1.0},
                known_nmse_db=0.047984,
                parameter_count=6,
                source="synthetic-history",
            ),
            HistoricalPrior(
                id="synthetic-prior-d",
                overrides={"degree": 6, "reg_strength": 0.1},
                known_nmse_db=0.112694,
                parameter_count=7,
                source="synthetic-history",
            ),
        ]


class SyntheticHardDomain(SyntheticLargeDomain):
    """Harder strategy-comparison domain: 2500 combos, single-point optimum.

    50 degrees x 50 log-spaced regs = 2500 combinations. The optimum region
    (degree=5 + small reg) is ~0.7% of the space and the exact optimum is a
    single point, so a 50-trial budget gives random/TPE almost no chance of
    hitting it — search quality becomes the deciding factor, not luck.
    default_constraints() sets a val_mse_threshold just above the exact
    optimum so target_hit_rate measures precise single-point hits.
    """

    name = "synthetic-hard"

    def design_space(self) -> dict[str, list[object]]:
        import numpy as np

        return {
            "degree": list(range(1, 51)),
            "reg_strength": [float(x) for x in np.logspace(-4, 2, 50)],
        }

    def validate_candidate(
        self, overrides: dict[str, object], parameter_count_max: int = 100
    ) -> list[str]:
        errors: list[str] = []
        degree = overrides.get("degree", 1)
        if (
            not isinstance(degree, int)
            or isinstance(degree, bool)
            or degree < 1
            or degree > 50
        ):
            errors.append("degree must be an integer in [1, 50].")
        reg = overrides.get("reg_strength", 1e-3)
        if not isinstance(reg, (int, float)) or isinstance(reg, bool):
            errors.append("reg_strength must be a number.")
        elif float(reg) < 1e-4 or float(reg) > 100:
            errors.append("reg_strength must be in [1e-4, 100].")
        return errors

    def default_constraints(self) -> dict:
        return {
            "parameter_count_max": 100,
            "metric": "val_mse",
            "val_mse_threshold": 0.0433716,  # 全局最优 0.0433606 + 1.1e-5 容差
        }


# ── Tool implementations ────────────────────────────────────────────

_GLOBAL_MODEL: dict[str, Any] = {}  # Simple in-memory store for demo


def _generate_data(seed: int = 42):
    """Generate consistent train+val data from a seed."""
    rng = np.random.default_rng(seed)
    # True function: degree-5 polynomial with decaying coefficients
    # degree=5 → perfect; degree<5 → underfit; reg too high → bias
    TRUE_COEFFS = np.array([0.5, -1.8, 2.1, -0.9, 0.3, -0.05])  # degree 5

    # Train set
    x_train = np.linspace(-3, 3, 200)
    y_true_train = np.polyval(TRUE_COEFFS[::-1], x_train)
    y_train = y_true_train + rng.normal(0, 0.8, 200)

    # Validation set — different noise, wider range (tests extrapolation)
    x_val = np.linspace(-3.5, 3.5, 100)
    y_true_val = np.polyval(TRUE_COEFFS[::-1], x_val)
    y_val = y_true_val + rng.normal(0, 0.8, 100)

    return x_train, y_train, x_val, y_val


def _fit_candidate_tool(
    degree: int, reg_strength: float = 1e-3, **_kw: Any
) -> dict[str, Any]:
    """Fit a polynomial of given degree with L2 regularization."""
    x, y, _, _ = _generate_data()

    A = np.vander(x, degree + 1, increasing=True)
    # Regularize all coefficients (including bias for simplicity)
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
    """Evaluate the fitted model on validation data against the true function.

    Falls back to _GLOBAL_MODEL when model_state is empty or missing keys,
    so build_harness_steps can call this with {} after fit_candidate.

    Uses the true degree-5 polynomial (no noise) to compute generalization MSE,
    so underfitted models (degree < 5) get clearly worse scores.
    """
    if not model_state or "coeffs" not in model_state:
        model_state = _GLOBAL_MODEL
    TRUE_COEFFS = np.array([0.5, -1.8, 2.1, -0.9, 0.3, -0.05])
    _, _, x_val, _ = _generate_data()
    y_true = np.polyval(TRUE_COEFFS[::-1], x_val)

    coeffs = np.array(model_state["coeffs"])
    y_pred = np.polyval(coeffs[::-1], x_val)
    val_mse = float(np.mean((y_true - y_pred) ** 2))

    return {
        "val_mse": val_mse,
        "metrics": {"val_mse": val_mse},
        "context_summary": f"Evaluated model: val_mse={val_mse:.6f}",
    }
