"""Parent-side candidate execution tool and evidence validation."""

from __future__ import annotations

import json
import math
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from nonlinear_agent.model_plugins.contracts import TrainingRequest, TrainingResult
from nonlinear_agent.model_plugins.registry import CandidateRegistry


_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SECRET_MARKERS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL")


def validate_candidate_model_tool(
    workspace: Path | str,
    manifest_path: Path | str,
    config: dict[str, Any],
    parameter_count_max: int,
) -> dict[str, Any]:
    validation = CandidateRegistry(workspace).validate_candidate(
        manifest_path,
        dict(config),
        int(parameter_count_max),
    )
    return {
        "descriptor": validation.descriptor.to_dict(),
        "descriptor_hash": validation.descriptor_hash,
        "parameter_count": validation.parameter_count,
        "context_summary": (
            f"Candidate {validation.descriptor.name} satisfies the plugin contract "
            f"with {validation.parameter_count} parameters."
        ),
    }


def run_candidate_model_tool(
    workspace: Path | str,
    manifest_path: Path | str,
    run_id: str,
    config: dict[str, Any],
    output_dir: Path | str,
    parameter_count_max: int,
    seed: int = 42,
    timeout_seconds: float = 300.0,
) -> dict[str, Any]:
    root = Path(workspace).resolve()
    if not _RUN_ID.fullmatch(run_id):
        raise ValueError("run_id contains unsupported characters")
    output_relative = _relative_inside(root, output_dir, "output_dir")
    registry = CandidateRegistry(root)
    validation = registry.validate_candidate(
        manifest_path, dict(config), int(parameter_count_max)
    )

    control_dir = root / "runs" / "candidate-agent" / run_id
    control_dir.mkdir(parents=True, exist_ok=True)
    request_file = control_dir / "request.json"
    result_file = control_dir / "result.json"
    request = TrainingRequest(
        run_id=run_id,
        workspace=str(root),
        config=dict(config),
        output_dir=output_relative,
        seed=int(seed),
    )
    request_payload = request.to_dict()
    request_payload["parameter_count_max"] = int(parameter_count_max)
    request_file.write_text(
        json.dumps(request_payload, ensure_ascii=False), encoding="utf-8"
    )
    result_file.unlink(missing_ok=True)

    manifest_relative = _relative_inside(root, manifest_path, "manifest_path")
    request_relative = request_file.relative_to(root).as_posix()
    result_relative = result_file.relative_to(root).as_posix()
    command = [
        sys.executable,
        "-m",
        "nonlinear_agent.model_plugins.runner",
        "--workspace",
        str(root),
        "--manifest",
        manifest_relative,
        "--request",
        request_relative,
        "--result",
        result_relative,
    ]
    environment = _scrubbed_environment()
    source_root = str(Path(__file__).resolve().parents[2])
    environment["PYTHONPATH"] = os.pathsep.join(
        item
        for item in (source_root, environment.get("PYTHONPATH", ""))
        if item
    )
    started = time.perf_counter()
    process = subprocess.run(
        command,
        cwd=root,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
        timeout=float(timeout_seconds),
    )
    elapsed = time.perf_counter() - started
    if not result_file.is_file():
        raise RuntimeError(
            "candidate runner did not produce a result; "
            f"returncode={process.returncode}, stderr={process.stderr[-1000:]}"
        )
    payload = json.loads(result_file.read_text(encoding="utf-8"))
    if process.returncode != 0 or not payload.get("ok"):
        raise RuntimeError(
            "candidate runner failed: "
            f"{payload.get('error_type', 'error')}: {payload.get('error', '')}"
        )
    result = TrainingResult.from_dict(dict(payload.get("result") or {}))
    _validate_result(root, result, validation.descriptor_hash, validation.parameter_count)
    return {
        "metrics": dict(result.metrics),
        "artifacts": list(result.artifacts),
        "descriptor": validation.descriptor.to_dict(),
        "descriptor_hash": validation.descriptor_hash,
        "elapsed_seconds": elapsed,
        "runner_returncode": process.returncode,
        "stdout_tail": process.stdout[-1000:],
        "stderr_tail": process.stderr[-1000:],
        "context_summary": (
            f"Candidate {validation.descriptor.name} completed in {elapsed:.2f}s "
            f"with NMSE {result.metrics['nmse_db']:.4f} dB."
        ),
    }


def _relative_inside(root: Path, value: Path | str, label: str) -> str:
    path = Path(value)
    if path.is_absolute():
        try:
            return path.resolve().relative_to(root).as_posix()
        except ValueError as exc:
            raise ValueError(f"{label} must remain inside workspace") from exc
    resolved = (root / path).resolve()
    try:
        return resolved.relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError(f"{label} must remain inside workspace") from exc


def _validate_result(
    root: Path,
    result: TrainingResult,
    expected_hash: str,
    expected_parameter_count: int,
) -> None:
    if result.status != "completed":
        raise RuntimeError(f"candidate terminal status is {result.status!r}")
    if result.descriptor_hash != expected_hash:
        raise ValueError("candidate descriptor hash does not match validated plugin")
    for name, value in result.metrics.items():
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(f"metric {name} must be numeric")
        if not math.isfinite(float(value)):
            raise ValueError(f"metric {name} must be finite")
    for required in ("nmse_db", "parameter_count"):
        if required not in result.metrics:
            raise ValueError(f"candidate metrics missing {required}")
    if int(result.metrics["parameter_count"]) != expected_parameter_count:
        raise ValueError("reported parameter_count does not match validated estimate")
    if not result.artifacts:
        raise FileNotFoundError("candidate result has no artifacts")
    for artifact in result.artifacts:
        relative = _relative_inside(root, artifact, "artifact")
        path = root / relative
        if not path.is_file():
            raise FileNotFoundError(f"candidate artifact does not exist: {artifact}")


def _scrubbed_environment() -> dict[str, str]:
    return {
        key: value
        for key, value in os.environ.items()
        if not any(marker in key.upper() for marker in _SECRET_MARKERS)
    }
