from __future__ import annotations

from pathlib import Path, PurePosixPath


EXPERIMENT_OUTPUT_ROOT = "reports"
GENERATED_CONFIG_ROOT = "runs"


def trial_config_path(
    run_id: str, trial_id: str, workspace: Path | None = None
) -> Path:
    """Compute the canonical path for a generated trial config.

    Generated configs live under runs/<run_id>/configs/<trial_id>.yaml
    so they never pollute the hand-maintained configs/baselines/ directory.
    """
    relative = Path(GENERATED_CONFIG_ROOT) / run_id / "configs" / f"{trial_id}.yaml"
    if workspace is not None:
        return workspace / relative
    return relative


def normalize_experiment_output_dir(value: object) -> object:
    """Route bare experiment output names into the canonical reports/ folder."""
    if not isinstance(value, str) or not value.strip():
        return value

    normalized = value.replace("\\", "/").strip()
    path = PurePosixPath(normalized)
    if path.is_absolute() or path.parts[:1] == (EXPERIMENT_OUTPUT_ROOT,):
        return normalized

    first = path.parts[0] if path.parts else ""
    if first.lower().startswith(("exp", "experiment", "output", "result")):
        return f"{EXPERIMENT_OUTPUT_ROOT}/{normalized}"
    return normalized
