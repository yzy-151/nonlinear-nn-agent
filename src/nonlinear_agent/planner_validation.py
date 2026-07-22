from __future__ import annotations

from typing import Any

from nonlinear_agent.experiment import ExperimentConfig

ALIAS_FIELDS = {
    "train_samples": "max_train_samples",
}

UNSUPPORTED_FIELDS = {
    "rank",
    "parameter_count",
    "nmse_db",
    "status",
    "final_train_loss",
    "samples",
    "evaluation_samples",
}


def allowed_override_fields() -> set[str]:
    return set(ExperimentConfig.__dataclass_fields__)


def normalize_planner_overrides(overrides: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in overrides.items():
        normalized[ALIAS_FIELDS.get(key, key)] = value
    return normalized


def validate_planned_overrides(
    overrides: dict[str, Any],
    parameter_count_max: int | None = None,
) -> dict[str, Any]:
    normalized = normalize_planner_overrides(overrides)
    allowed = allowed_override_fields()
    unsupported = sorted((set(normalized) - allowed) | (set(overrides) & UNSUPPORTED_FIELDS))
    if unsupported:
        raise ValueError(f"Unsupported planner override fields: {', '.join(unsupported)}")
    if parameter_count_max is not None:
        parameter_count = estimate_parameter_count(normalized)
        if parameter_count is not None and parameter_count > parameter_count_max:
            raise ValueError(
                f"Estimated parameter count {parameter_count} exceeds parameter budget {parameter_count_max}."
            )
        if parameter_count is not None:
            normalized["estimated_parameter_count"] = parameter_count
    return {key: value for key, value in normalized.items() if key != "estimated_parameter_count"}


def estimate_parameter_count(overrides: dict[str, Any]) -> int | None:
    model_type = str(overrides.get("model_type", "complex_cnn"))
    feature_mode = str(overrides.get("feature_mode", "legacy_abs"))
    memory_depth = int(overrides.get("memory_depth", 5))
    mp_order_count = int(overrides.get("mp_order_count", 4))
    hidden_units = int(overrides.get("hidden_units", 64))
    spline_knots = int(overrides.get("spline_knots", 16))
    feature_width = _feature_width(feature_mode, memory_depth, mp_order_count)
    input_dim = 2 * feature_width

    if model_type == "complex_lstsq":
        return 2 * (feature_width + 1)
    if model_type == "linear":
        return input_dim * 2 + 2
    if model_type == "tiny_mlp":
        return input_dim * hidden_units + hidden_units + hidden_units * 2 + 2
    if model_type == "spline_mlp":
        return input_dim * hidden_units + hidden_units + hidden_units * spline_knots + hidden_units * 2 + 2
    if model_type == "complex_cnn":
        return None
    raise ValueError(f"Unsupported model_type: {model_type}")


def _feature_width(feature_mode: str, memory_depth: int, mp_order_count: int) -> int:
    if feature_mode == "complex_mp":
        return mp_order_count * (memory_depth + 1)
    if feature_mode == "legacy_abs":
        return 4 * (memory_depth + 1)
    raise ValueError(f"Unsupported feature_mode: {feature_mode}")
