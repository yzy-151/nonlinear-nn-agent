from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Any

import yaml


@dataclass
class AgentRequest:
    experiment_id: str
    goal: str
    base_config_path: Path
    epochs: int
    learning_rate: float
    optimizer: str
    output_dir: str
    nmse_threshold_db: float = -35.0


@dataclass
class AgentState:
    request: AgentRequest
    status: str = "initialized"
    plan_path: Path | None = None
    config_path: Path | None = None
    summary_path: Path | None = None
    resume_log_path: Path | None = None
    metrics: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


Runner = Callable[[Path], dict[str, Any]]


def parse_metrics_stdout(stdout: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    for index, char in enumerate(stdout):
        if char != "{":
            continue
        try:
            payload, _ = decoder.raw_decode(stdout[index:])
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            continue
    raise RuntimeError("Could not parse metrics JSON from experiment stdout.")


def _relative(path: Path, workspace: Path) -> str:
    try:
        return path.relative_to(workspace).as_posix()
    except ValueError:
        return path.as_posix()


def build_resume_change_log(
    experiment_id: str,
    nmse_db: float,
    plan_path: Path,
    config_path: Path,
    summary_path: Path,
) -> str:
    return (
        f"# Resume Change Log: {experiment_id}\n\n"
        "## Resume Angle\n\n"
        "Built an Agentic Experiment Runner for nonlinear neural-network MPDPD fitting. "
        "The workflow turns an experiment request into a tracked plan, reproducible YAML "
        "configuration, executable run, metric verification, PSD artifact check, and "
        "resume-ready Markdown summary.\n\n"
        "## Evidence\n\n"
        f"- NMSE: {nmse_db:.2f} dB\n"
        f"- Plan: {plan_path.as_posix()}\n"
        f"- Config: {config_path.as_posix()}\n"
        f"- Summary: {summary_path.as_posix()}\n\n"
        "## Resume Bullet Draft\n\n"
        "- Designed an Agentic Experiment Runner for neural-network nonlinear fitting, "
        "automating experiment planning, YAML configuration generation, training execution, "
        "NMSE parsing, PSD artifact verification, and Markdown result summarization.\n"
    )


class ExperimentAgent:
    def __init__(self, workspace: Path | str, runner: Runner | None = None):
        self.workspace = Path(workspace)
        self.runner = runner or self._subprocess_runner

    def run(self, request: AgentRequest) -> AgentState:
        state = AgentState(request=request)
        try:
            self._write_plan(state)
            self._write_config(state)
            self._run_experiment(state)
            self._verify_outputs(state)
            self._write_summary(state)
            self._write_resume_log(state)
            state.status = "succeeded"
        except Exception as exc:
            state.status = "failed"
            state.errors.append(str(exc))
            self._write_failure_summary(state)
        return state

    def _write_plan(self, state: AgentState) -> None:
        request = state.request
        plan_dir = self.workspace / "plans"
        plan_dir.mkdir(parents=True, exist_ok=True)
        state.plan_path = plan_dir / f"{request.experiment_id}.md"
        content = (
            f"# {request.experiment_id} Experiment Plan\n\n"
            f"## Goal\n\n{request.goal}\n\n"
            "## Agent Steps\n\n"
            "1. Read the baseline YAML configuration.\n"
            "2. Write a reproducible experiment configuration.\n"
            "3. Run the nonlinear NN training command.\n"
            "4. Parse `metrics.json` and verify NMSE.\n"
            "5. Check that PSD output exists for visual inspection.\n"
            "6. Write a resume-ready change log.\n\n"
            "## Success Criteria\n\n"
            f"- NMSE must be <= {request.nmse_threshold_db:.2f} dB.\n"
            "- `metrics.json` must exist.\n"
            "- `psd.png` must exist.\n"
            "- Summary must include config, metrics, and resume angle.\n"
        )
        state.plan_path.write_text(content, encoding="utf-8")

    def _write_config(self, state: AgentState) -> None:
        request = state.request
        config_dir = self.workspace / "configs"
        config_dir.mkdir(parents=True, exist_ok=True)
        state.config_path = config_dir / f"{request.experiment_id}.yaml"
        base_path = request.base_config_path
        if not base_path.is_absolute():
            base_path = self.workspace / base_path
        config = yaml.safe_load(base_path.read_text(encoding="utf-8")) or {}
        config.update(
            {
                "output_dir": request.output_dir,
                "epochs": request.epochs,
                "learning_rate": request.learning_rate,
                "optimizer": request.optimizer,
            }
        )
        state.config_path.write_text(
            yaml.safe_dump(config, sort_keys=False),
            encoding="utf-8",
        )

    def _run_experiment(self, state: AgentState) -> None:
        if state.config_path is None:
            raise RuntimeError("Config was not created.")
        state.metrics = self.runner(state.config_path)

    def _verify_outputs(self, state: AgentState) -> None:
        request = state.request
        metrics = state.metrics
        if metrics.get("status") != "succeeded":
            raise RuntimeError(f"Experiment did not succeed: {metrics}")
        if "nmse_db" not in metrics:
            raise RuntimeError("metrics.json does not contain nmse_db.")
        if float(metrics["nmse_db"]) > request.nmse_threshold_db:
            raise RuntimeError(
                f"NMSE {metrics['nmse_db']:.2f} dB did not meet "
                f"threshold {request.nmse_threshold_db:.2f} dB."
            )
        output_dir = self.workspace / request.output_dir
        metrics_path = output_dir / "metrics.json"
        psd_path = output_dir / "psd.png"
        if not metrics_path.exists():
            raise RuntimeError(f"Missing metrics file: {metrics_path}")
        if not psd_path.exists():
            raise RuntimeError(f"Missing PSD image: {psd_path}")

    def _write_summary(self, state: AgentState) -> None:
        request = state.request
        output_dir = self.workspace / request.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        state.summary_path = output_dir / "agent-summary.md"
        content = (
            f"# Agent Summary: {request.experiment_id}\n\n"
            "## Result\n\n"
            f"- Status: {state.metrics['status']}\n"
            f"- NMSE: {state.metrics['nmse_db']:.4f} dB\n"
            f"- Epochs: {state.metrics['epochs']}\n"
            f"- Samples: {state.metrics['samples']}\n\n"
            "## Reproducibility\n\n"
            f"- Plan: {_relative(state.plan_path, self.workspace)}\n"
            f"- Config: {_relative(state.config_path, self.workspace)}\n"
            f"- Metrics: {_relative(output_dir / 'metrics.json', self.workspace)}\n"
            f"- PSD: {_relative(output_dir / 'psd.png', self.workspace)}\n\n"
            "## Resume Value\n\n"
            "This run demonstrates an agent-style experiment loop: plan generation, "
            "config generation, command execution, metric parsing, artifact verification, "
            "and a job-search-ready change record.\n"
        )
        state.summary_path.write_text(content, encoding="utf-8")

    def _write_resume_log(self, state: AgentState) -> None:
        if state.plan_path is None or state.config_path is None or state.summary_path is None:
            raise RuntimeError("Cannot write resume log before plan/config/summary exist.")
        log_dir = self.workspace / "docs" / "resume-change-logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        state.resume_log_path = log_dir / f"{state.request.experiment_id}.md"
        state.resume_log_path.write_text(
            build_resume_change_log(
                experiment_id=state.request.experiment_id,
                nmse_db=float(state.metrics["nmse_db"]),
                plan_path=state.plan_path,
                config_path=state.config_path,
                summary_path=state.summary_path,
            ),
            encoding="utf-8",
        )

    def _write_failure_summary(self, state: AgentState) -> None:
        request = state.request
        output_dir = self.workspace / request.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        state.summary_path = output_dir / "agent-summary.md"
        state.summary_path.write_text(
            "# Agent Summary\n\n"
            "- Status: failed\n"
            f"- Errors: {'; '.join(state.errors)}\n",
            encoding="utf-8",
        )

    def _subprocess_runner(self, config_path: Path) -> dict[str, Any]:
        command = [
            sys.executable,
            "examples/nonlinear_fit/train.py",
            "--config",
            _relative(config_path, self.workspace),
        ]
        result = subprocess.run(
            command,
            cwd=self.workspace,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                "Experiment command failed:\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            )
        output = result.stdout.strip()
        if not output:
            raise RuntimeError("Experiment command did not print metrics JSON.")
        return parse_metrics_stdout(output)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--goal", required=True)
    parser.add_argument("--base-config", default="examples/nonlinear_fit/config_good_adam.yaml")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--epochs", type=int, required=True)
    parser.add_argument("--learning-rate", type=float, required=True)
    parser.add_argument("--optimizer", default="adam")
    parser.add_argument("--nmse-threshold-db", type=float, default=-35.0)
    args = parser.parse_args()

    workspace = Path.cwd()
    agent = ExperimentAgent(workspace=workspace)
    state = agent.run(
        AgentRequest(
            experiment_id=args.experiment_id,
            goal=args.goal,
            base_config_path=Path(args.base_config),
            epochs=args.epochs,
            learning_rate=args.learning_rate,
            optimizer=args.optimizer,
            output_dir=args.output_dir,
            nmse_threshold_db=args.nmse_threshold_db,
        )
    )
    print(
        json.dumps(
            {
                "status": state.status,
                "metrics": state.metrics,
                "plan_path": str(state.plan_path) if state.plan_path else None,
                "config_path": str(state.config_path) if state.config_path else None,
                "summary_path": str(state.summary_path) if state.summary_path else None,
                "resume_log_path": str(state.resume_log_path) if state.resume_log_path else None,
                "errors": state.errors,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if state.status != "succeeded":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
