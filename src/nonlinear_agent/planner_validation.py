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
    _validate_field_values(normalized)
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


def _validate_field_values(overrides: dict[str, Any]) -> None:
    model_type = str(overrides.get("model_type", ""))
    if "spline_range" in overrides and not _is_number(overrides["spline_range"]):
        raise ValueError("spline_range must be a number.")
    for field in ("memory_depth", "mp_order_count", "hidden_units", "spline_knots", "batch_size", "max_train_samples"):
        if field in overrides and not _is_positive_int(overrides[field]):
            raise ValueError(f"{field} must be a positive integer.")
    if "epochs" in overrides:
        if not isinstance(overrides["epochs"], int) or isinstance(overrides["epochs"], bool) or overrides["epochs"] < 0:
            raise ValueError("epochs must be a non-negative integer.")
        if model_type in {"tiny_mlp", "spline_mlp", "linear", "complex_cnn"} and overrides["epochs"] < 1:
            raise ValueError(f"epochs must be >= 1 for neural model {model_type}.")
    for field in ("learning_rate", "scheduler_gamma", "train_ratio"):
        if field in overrides and not _is_number(overrides[field]):
            raise ValueError(f"{field} must be a number.")


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _feature_width(feature_mode: str, memory_depth: int, mp_order_count: int) -> int:
    if feature_mode == "complex_mp":
        return mp_order_count * (memory_depth + 1)
    if feature_mode == "legacy_abs":
        return 4 * (memory_depth + 1)
    raise ValueError(f"Unsupported feature_mode: {feature_mode}")
