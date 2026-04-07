from __future__ import annotations

import json
import subprocess
import sys
import time
from functools import partial
from pathlib import Path
from typing import Any

import yaml

from nonlinear_agent.agent_workflow import parse_metrics_stdout
from nonlinear_agent.tools import ToolRegistry


def _resolve(workspace: Path | str, path: Path | str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return Path(workspace) / candidate


def _relative(path: Path, workspace: Path | str) -> str:
    root = Path(workspace)
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def generate_config_tool(
    workspace: Path | str,
    base_config_path: Path | str,
    experiment_id: str,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = Path(workspace)
    base_path = _resolve(root, base_config_path)
    config = yaml.safe_load(base_path.read_text(encoding="utf-8")) or {}
    config.update(overrides or {})
    config_dir = root / "configs"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / f"{experiment_id}.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return {
        "config_path": _relative(config_path, root),
        "artifacts": [_relative(config_path, root)],
        "context_summary": f"Generated config for {experiment_id}: {_relative(config_path, root)}",
    }


def run_training_tool(
    workspace: Path | str,
    config_path: Path | str,
    command: list[str] | None = None,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    root = Path(workspace)
    resolved_config = _resolve(root, config_path)
    command_to_run = command or [
        sys.executable,
        "examples/nonlinear_fit/train.py",
        "--config",
        _relative(resolved_config, root),
    ]
    started = time.perf_counter()
    result = subprocess.run(
        command_to_run,
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout_seconds,
    )
    elapsed = time.perf_counter() - started
    if result.returncode != 0:
        raise RuntimeError(
            "Training command failed "
            f"with return code {result.returncode}.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    config = yaml.safe_load(resolved_config.read_text(encoding="utf-8")) or {}
    output_dir = str(config.get("output_dir", ""))
    metrics = _load_metrics(root, output_dir, result.stdout)
    artifacts = _collect_artifacts(root, output_dir)
    return {
        "metrics": metrics,
        "artifacts": artifacts,
        "returncode": result.returncode,
        "stdout_tail": result.stdout[-2000:],
        "stderr_tail": result.stderr[-2000:],
        "elapsed_seconds": elapsed,
        "context_summary": (
            f"Training finished in {elapsed:.2f}s with NMSE "
            f"{metrics.get('nmse_db', 'unknown')} dB."
        ),
    }


def verify_artifacts_tool(
    workspace: Path | str,
    output_dir: Path | str,
    nmse_threshold_db: float,
) -> dict[str, Any]:
    root = Path(workspace)
    resolved_output = _resolve(root, output_dir)
    metrics_path = resolved_output / "metrics.json"
    psd_path = resolved_output / "psd.png"
    if not metrics_path.exists():
        raise FileNotFoundError(f"Missing metrics file: {metrics_path}")
    if not psd_path.exists():
        raise FileNotFoundError(f"Missing PSD image: {psd_path}")
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    if "nmse_db" not in metrics:
        raise RuntimeError("metrics.json does not contain nmse_db.")
    nmse = float(metrics["nmse_db"])
    if nmse > nmse_threshold_db:
        raise RuntimeError(f"NMSE {nmse:.4f} dB did not meet threshold {nmse_threshold_db:.4f} dB.")
    artifacts = [_relative(metrics_path, root), _relative(psd_path, root)]
    return {
        "metrics": {"nmse_db": nmse},
        "artifacts": artifacts,
        "context_summary": f"NMSE {nmse:.4f} dB meets threshold {nmse_threshold_db:.4f} dB; PSD exists.",
    }


def write_report_tool(
    workspace: Path | str,
    session_id: str,
    metrics: dict[str, Any] | None = None,
    artifacts: list[str] | None = None,
) -> dict[str, Any]:
    root = Path(workspace)
    if not metrics or not artifacts:
        session_path = root / "sessions" / f"{session_id}.json"
        if session_path.exists():
            session_payload = json.loads(session_path.read_text(encoding="utf-8"))
            metrics = metrics or session_payload.get("metrics", {})
            artifacts = artifacts or session_payload.get("artifacts", [])
    metrics = metrics or {}
    artifacts = artifacts or []
    report_dir = root / "reports" / session_id
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "agent-harness-report.md"
    nmse = metrics.get("nmse_db")
    nmse_line = f"{float(nmse):.4f} dB" if nmse is not None else "unknown"
    artifact_lines = "\n".join(f"- `{artifact}`" for artifact in artifacts) or "- No artifacts recorded"
    report_path.write_text(
        "# Agent Harness Report\n\n"
        "## Result\n\n"
        f"- Session: `{session_id}`\n"
        f"- NMSE: {nmse_line}\n\n"
        "## Artifacts\n\n"
        f"{artifact_lines}\n\n"
        "## Runtime Evidence\n\n"
        "This report is generated by the Agent Harness tool chain. The important hiring evidence is not only the final NMSE, but the trace-backed execution path: config generation, training command execution, artifact verification, metric capture, and report generation.\n",
        encoding="utf-8",
    )
    return {
        "artifacts": [_relative(report_path, root)],
        "context_summary": f"Wrote Agent Harness report: {_relative(report_path, root)}",
    }


def build_experiment_tool_registry(workspace: Path | str, default_timeout_seconds: float = 300.0) -> ToolRegistry:
    root = Path(workspace)
    registry = ToolRegistry(default_timeout_seconds=default_timeout_seconds)
    registry.register("generate_config", partial(generate_config_tool, workspace=root))
    registry.register("run_training", partial(run_training_tool, workspace=root))
    registry.register("verify_artifacts", partial(verify_artifacts_tool, workspace=root))
    registry.register("write_report", partial(write_report_tool, workspace=root))
    return registry


def _load_metrics(workspace: Path, output_dir: str, stdout: str) -> dict[str, Any]:
    if output_dir:
        metrics_path = _resolve(workspace, output_dir) / "metrics.json"
        if metrics_path.exists():
            return json.loads(metrics_path.read_text(encoding="utf-8"))
    return parse_metrics_stdout(stdout)


def _collect_artifacts(workspace: Path, output_dir: str) -> list[str]:
    if not output_dir:
        return []
    output_path = _resolve(workspace, output_dir)
    artifacts = []
    for name in ("metrics.json", "psd.png", "summary.md", "resolved_config.yaml"):
        path = output_path / name
        if path.exists():
            artifacts.append(_relative(path, workspace))
    return artifacts

