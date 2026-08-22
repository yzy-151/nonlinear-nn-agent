"""Parent-side candidate execution tool and evidence validation."""

from __future__ import annotations

import json
import math
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from nonlinear_agent.model_plugins.contracts import (
    ModelDescriptor,
    TrainingRequest,
    TrainingResult,
    descriptor_hash,
    validate_descriptor,
)


_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SECRET_MARKERS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL")


def validate_candidate_model_tool(
    workspace: Path | str,
    manifest_path: Path | str,
    config: dict[str, Any],
    parameter_count_max: int,
) -> dict[str, Any]:
    root = Path(workspace).resolve()
    run_id = f"validate-{uuid.uuid4().hex[:12]}"
    request = TrainingRequest(
        run_id=run_id,
        workspace=str(root),
        config=dict(config),
        output_dir=f"runs/candidate-agent/{run_id}/validation",
    )
    payload, elapsed, process = _invoke_candidate_runner(
        root=root,
        manifest_path=manifest_path,
        request=request,
        parameter_count_max=parameter_count_max,
        timeout_seconds=60.0,
        action="validate",
    )
    descriptor, validated_hash, parameter_count = _validation_from_payload(payload)
    return {
        "descriptor": descriptor.to_dict(),
        "descriptor_hash": validated_hash,
        "parameter_count": parameter_count,
        "elapsed_seconds": elapsed,
        "runner_returncode": process.returncode,
        "context_summary": (
            f"Candidate {descriptor.name} satisfies the plugin contract "
            f"with {parameter_count} parameters."
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
    request = TrainingRequest(
        run_id=run_id,
        workspace=str(root),
        config=dict(config),
        output_dir=output_relative,
        train_ratio=float(config.get("train_ratio", 0.8)),
        seed=int(config.get("seed", seed)),
    )
    payload, elapsed, process = _invoke_candidate_runner(
        root=root,
        manifest_path=manifest_path,
        request=request,
        parameter_count_max=parameter_count_max,
        timeout_seconds=timeout_seconds,
        action="train",
    )
    descriptor, validated_hash, parameter_count = _validation_from_payload(payload)
    result = TrainingResult.from_dict(dict(payload.get("result") or {}))
    _validate_result(root, result, validated_hash, parameter_count)
    return {
        "metrics": dict(result.metrics),
        "artifacts": list(result.artifacts),
        "descriptor": descriptor.to_dict(),
        "descriptor_hash": validated_hash,
        "elapsed_seconds": elapsed,
        "runner_returncode": process.returncode,
        "stdout_tail": process.stdout[-1000:],
        "stderr_tail": process.stderr[-1000:],
        "context_summary": (
            f"Candidate {descriptor.name} completed in {elapsed:.2f}s "
            f"with NMSE {result.metrics['nmse_db']:.4f} dB."
        ),
    }


def _invoke_candidate_runner(
    root: Path,
    manifest_path: Path | str,
    request: TrainingRequest,
    parameter_count_max: int,
    timeout_seconds: float,
    action: str,
) -> tuple[dict[str, Any], float, subprocess.CompletedProcess[str]]:
    control_dir = root / "runs" / "candidate-agent" / request.run_id
    control_dir.mkdir(parents=True, exist_ok=True)
    request_file = control_dir / "request.json"
    result_file = control_dir / f"{action}-result.json"
    request_payload = request.to_dict()
    request_payload["parameter_count_max"] = int(parameter_count_max)
    request_file.write_text(
        json.dumps(request_payload, ensure_ascii=False), encoding="utf-8"
    )
    result_file.unlink(missing_ok=True)
    command = [
        sys.executable,
        "-m",
        "nonlinear_agent.model_plugins.runner",
        "--workspace",
        str(root),
        "--manifest",
        _relative_inside(root, manifest_path, "manifest_path"),
        "--request",
        request_file.relative_to(root).as_posix(),
        "--result",
        result_file.relative_to(root).as_posix(),
        "--action",
        action,
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
    return payload, elapsed, process


def _validation_from_payload(
    payload: dict[str, Any],
) -> tuple[ModelDescriptor, str, int]:
    raw = dict(payload.get("validation") or {})
    descriptor = ModelDescriptor.from_dict(dict(raw.get("descriptor") or {}))
    validate_descriptor(descriptor)
    actual_hash = descriptor_hash(descriptor)
    reported_hash = str(raw.get("descriptor_hash", ""))
    if actual_hash != reported_hash:
        raise ValueError("runner validation descriptor hash is inconsistent")
    parameter_count = raw.get("parameter_count")
    if (
        not isinstance(parameter_count, int)
        or isinstance(parameter_count, bool)
        or parameter_count < 0
    ):
        raise ValueError("runner validation parameter_count is invalid")
    return descriptor, actual_hash, parameter_count


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
    resolved_artifacts: dict[str, Path] = {}
    for artifact in result.artifacts:
        relative = _relative_inside(root, artifact, "artifact")
        path = root / relative
        if not path.is_file():
            raise FileNotFoundError(f"candidate artifact does not exist: {artifact}")
        resolved_artifacts[path.name] = path
    for required_artifact in ("metrics.json", "psd.png"):
        if required_artifact not in resolved_artifacts:
            raise FileNotFoundError(
                f"candidate result is missing required artifact: {required_artifact}"
            )
    artifact_metrics = json.loads(
        resolved_artifacts["metrics.json"].read_text(encoding="utf-8")
    )
    for name, value in result.metrics.items():
        if name not in artifact_metrics or float(artifact_metrics[name]) != float(value):
            raise ValueError(
                f"metrics artifact disagrees with result for metric {name}"
            )
    if resolved_artifacts["psd.png"].read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("psd.png artifact is not a valid PNG file")


def _scrubbed_environment() -> dict[str, str]:
    return {
        key: value
        for key, value in os.environ.items()
        if not any(marker in key.upper() for marker in _SECRET_MARKERS)
    }
