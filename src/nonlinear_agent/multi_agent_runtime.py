"""Composition root for the real multi-agent experiment workers."""

from __future__ import annotations

import asyncio
import json
import re
import shutil
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from nonlinear_agent.coding_agent import CodingTaskSpec
from nonlinear_agent.execution_agent import ExecutionAgent
from nonlinear_agent.experiment_tools import build_experiment_tool_registry
from nonlinear_agent.reporting.tool import write_task_report_tool
from nonlinear_agent.supervisor_graph import MultiAgentWorkers
from nonlinear_agent.writing_agent import EvidenceBundle


ExecutionAgentFactory = Callable[[Path], Any]
ReportWriter = Callable[..., dict[str, Any]]


class MultiAgentRuntime:
    """Adapt existing role components to the supervisor's narrow worker ports."""

    def __init__(
        self,
        repo_root: Path | str,
        model_router: Any,
        coding_agent: Any,
        writing_agent: Any,
        execution_agent_factory: ExecutionAgentFactory | None = None,
        report_writer: ReportWriter = write_task_report_tool,
        nmse_threshold_db: float = -35.0,
    ):
        self._root = Path(repo_root).resolve()
        self._router = model_router
        self._coding = coding_agent
        self._writing = writing_agent
        self._execution_factory = execution_agent_factory or (
            lambda workspace: ExecutionAgent(
                build_experiment_tool_registry(workspace)
            )
        )
        self._report_writer = report_writer
        self._threshold = float(nmse_threshold_db)

    def workers(self) -> MultiAgentWorkers:
        return MultiAgentWorkers(
            idea_plan=self._idea_plan,
            coding=self._coding_worker,
            execution=self._execution_worker,
            writing=self._writing_worker,
        )

    def _idea_plan(self, request: dict[str, Any]) -> dict[str, Any]:
        contract = {
            "plan_id": "letters-digits-hyphens",
            "hypotheses": [
                {
                    "hypothesis": "testable claim",
                    "rationale": "physical or algorithmic basis",
                    "citation": "knowledge or memory evidence ID",
                }
            ],
            "candidate_experiments": [
                {
                    "model_type": "new candidate plugin name",
                    "config": {"candidate-specific field": "value"},
                    "params_estimate": 1,
                    "budget": {
                        "parameter_count_max": 4000,
                        "epochs_max": 50,
                        "timeout_seconds": 300,
                    },
                    "stop_condition": f"nmse_db <= {self._threshold}",
                    "rationale": "why this experiment is informative",
                    "citation": "knowledge or memory evidence ID",
                }
            ],
            "experiment_dag": {"nodes": ["candidate-1"], "edges": []},
            "expected_information_gain": 0.0,
            "risk": "bounded implementation or training risk",
            "fallback": ["one concrete fallback"],
            "required_code_changes": [
                "models/candidates/<candidate>/plugin.py",
                "models/candidates/<candidate>/manifest.json",
            ],
        }
        prompt = (
            "You are the Idea/Plan Agent for nonlinear model experiments. "
            "Return one JSON object only, without Markdown. Design one compact "
            "candidate that can be implemented as a ModelPlugin. Every "
            "hypothesis and candidate needs a citation. Respect parameter, "
            "epoch and timeout budgets. On replanning, use only failure_facts "
            "as observations and change the causal design; never request raw "
            "history or secrets.\nRequired contract:\n"
            + json.dumps(contract, ensure_ascii=False, sort_keys=True)
            + "\nRun request:\n"
            + json.dumps(request, ensure_ascii=False, sort_keys=True)
        )
        raw = str(self._router.complete("idea_plan", prompt)).strip()
        if not raw.startswith("{") or not raw.endswith("}"):
            raise ValueError("idea_plan response must be one JSON object")
        plan = json.loads(raw)
        if not isinstance(plan, dict):
            raise ValueError("idea_plan response must be an object")
        return plan

    def _coding_worker(self, request: dict[str, Any]) -> dict[str, Any]:
        candidate = _first_candidate(request["plan"])
        budget = dict(candidate.get("budget") or {})
        task = CodingTaskSpec(
            task_id=_identifier(request["run_id"]),
            objective=str(request["goal"]),
            candidate_name=_identifier(candidate.get("model_type", "candidate")),
            config=_candidate_config(candidate),
            parameter_count_max=int(budget.get("parameter_count_max", 4000)),
            smoke_timeout_seconds=float(budget.get("timeout_seconds", 120.0)),
            constraints=tuple(
                value
                for value in (
                    str(candidate.get("stop_condition", "")),
                    str(request["plan"].get("risk", "")),
                )
                if value
            ),
        )
        result = asdict(self._coding.generate_candidate(task))
        trace_path = result.get("trace_path")
        if trace_path:
            published = self._publish_file(
                Path(result.get("worktree") or self._root),
                str(trace_path),
                _identifier(request["run_id"]),
            )
            if published:
                result["trace_path"] = published
        return result

    def _execution_worker(self, request: dict[str, Any]) -> dict[str, Any]:
        candidate = _first_candidate(request["plan"])
        code = dict(request.get("code_result") or {})
        workspace = Path(code.get("worktree") or self._root).resolve()
        manifest = code.get("manifest_path") or candidate.get("manifest_path")
        if not manifest:
            raise ValueError("execution requires a gated candidate manifest")
        budget = dict(candidate.get("budget") or {})
        arguments = {
            "manifest_path": str(manifest),
            "run_id": _identifier(request["run_id"]),
            "config": _candidate_config(candidate),
            "output_dir": f"reports/{_identifier(request['run_id'])}/execution",
            "parameter_count_max": int(budget.get("parameter_count_max", 4000)),
            "timeout_seconds": float(budget.get("timeout_seconds", 300.0)),
        }
        agent = self._execution_factory(workspace)
        result = asyncio.run(agent.execute("run_candidate_model", arguments))
        payload = asdict(result)
        payload["artifacts"] = tuple(
            published or artifact
            for artifact in payload.get("artifacts", ())
            for published in [
                self._publish_file(
                    workspace, str(artifact), _identifier(request["run_id"])
                )
            ]
        )
        return payload

    def _writing_worker(self, request: dict[str, Any]) -> dict[str, Any]:
        code = dict(request.get("code_result") or {})
        source = self._report_source(request)
        bundle = EvidenceBundle.from_task_source(source)
        narrative = self._writing.write(bundle)
        return self._report_writer(
            workspace=self._root,
            task_source=source,
            output_dir=f"reports/{_identifier(request['run_id'])}/task-report",
            narrative=narrative.to_dict(),
        )

    def _publish_file(
        self,
        source_workspace: Path,
        value: str,
        run_id: str,
    ) -> str | None:
        source_root = source_workspace.resolve()
        source = Path(value)
        source = source.resolve() if source.is_absolute() else (source_root / source).resolve()
        try:
            source.relative_to(source_root)
        except ValueError as exc:
            raise ValueError("worker artifact must remain inside its workspace") from exc
        if not source.is_file():
            return None
        destination = self._root / "reports" / run_id / "evidence" / source.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source != destination.resolve():
            shutil.copy2(source, destination)
        return destination.relative_to(self._root).as_posix()

    def _report_source(self, request: dict[str, Any]) -> dict[str, Any]:
        plan = request["plan"]
        candidate = _first_candidate(plan)
        execution = request["execution_result"]
        output = dict(execution.get("output") or {})
        metrics = dict(execution.get("metrics") or {})
        artifacts = [str(item) for item in execution.get("artifacts", [])]
        psd_path = next(
            (item for item in artifacts if Path(item).name.lower() == "psd.png"),
            None,
        )
        nmse = metrics.get("nmse_db")
        run_id = _identifier(request["run_id"])
        citations = [
            str(item["citation"])
            for item in list(plan.get("hypotheses", []))
            + list(plan.get("candidate_experiments", []))
            if isinstance(item, dict) and item.get("citation")
        ]
        code = dict(request.get("code_result") or {})
        descriptor = output.get("descriptor") or dict(
            code.get("validation") or {}
        ).get("descriptor")
        return {
            "task_id": run_id,
            "goal": request.get("goal", ""),
            "constraints": {
                "parameter_count_max": int(
                    dict(candidate.get("budget") or {}).get("parameter_count_max", 4000)
                ),
                "nmse_threshold_db": self._threshold,
            },
            "citations": citations,
            "plan": plan,
            "code_changes": [
                {"file": path, "change": "CodingAgent generated candidate plugin"}
                for path in code.get("applied_files", [])
            ],
            "executions": [
                {
                    "run_id": run_id,
                    "model_type": str(candidate.get("model_type", "unknown")),
                    "nmse_db": nmse,
                    "parameter_count": metrics.get("parameter_count"),
                    "baseline_nmse_db": candidate.get("baseline_nmse_db"),
                    "psd_path": psd_path,
                    "target_hit": nmse is not None and float(nmse) <= self._threshold,
                    "model_descriptor": descriptor,
                    "config": _candidate_config(candidate),
                }
            ],
            "failure_cases": list(request.get("failures", [])),
            "cost_usd": self._router.total_cost(),
            "trace_refs": [code["trace_path"]] if code.get("trace_path") else [],
            "reproduce_command": f"python agent.py multi-agent --run-id {run_id}",
            "limits": "Only the nonlinear-modeling domain and supplied evidence are covered.",
        }


def _first_candidate(plan: dict[str, Any]) -> dict[str, Any]:
    candidates = plan.get("candidate_experiments") or []
    if not candidates or not isinstance(candidates[0], dict):
        raise ValueError("plan must contain one candidate experiment")
    return dict(candidates[0])


def _candidate_config(candidate: dict[str, Any]) -> dict[str, Any]:
    if isinstance(candidate.get("config"), dict):
        return dict(candidate["config"])
    excluded = {
        "model_type",
        "params_estimate",
        "budget",
        "stop_condition",
        "rationale",
        "citation",
        "config_hash",
        "manifest_path",
        "baseline_nmse_db",
    }
    return {key: value for key, value in candidate.items() if key not in excluded}


def _identifier(value: Any) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", str(value)).strip("-_")
    if not cleaned or not cleaned[0].isalpha():
        cleaned = f"run-{cleaned or 'unknown'}"
    return cleaned[:64]
