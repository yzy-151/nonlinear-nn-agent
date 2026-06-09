from __future__ import annotations

from pathlib import PurePosixPath


EXPERIMENT_OUTPUT_ROOT = "reports"


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
