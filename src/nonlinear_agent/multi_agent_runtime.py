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
CodingAgentFactory = Callable[[], Any]


class MultiAgentRuntime:
    """Adapt existing role components to the supervisor's narrow worker ports."""

    def __init__(
        self,
        repo_root: Path | str,
        model_router: Any,
        coding_agent: Any,
        writing_agent: Any,
        coding_agent_factory: CodingAgentFactory | None = None,
        execution_agent_factory: ExecutionAgentFactory | None = None,
        report_writer: ReportWriter = write_task_report_tool,
        nmse_threshold_db: float = -35.0,
    ):
        self._root = Path(repo_root).resolve()
        self._router = model_router
        self._coding = coding_agent
        self._coding_factory = coding_agent_factory
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
        candidate_contract = {
            "experiment_id": "unique ID within this round",
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
            "exploration_role": "explore or exploit",
            "based_on_fact_refs": ["verified prior fact ID, empty only in round 1"],
            "expected_information_gain": 0.0,
        }
        contract = {
            "plan_id": "letters-digits-hyphens",
            "hypotheses": [
                {
                    "hypothesis": "testable claim",
                    "rationale": "physical or algorithmic basis",
                    "citation": "knowledge or memory evidence ID",
                }
            ],
            "decision_rationale": "why this round follows from available facts",
            "candidate_experiments": [
                {**candidate_contract, "experiment_id": f"candidate-{index}"}
                for index in range(1, 4)
            ],
            "experiment_dag": {
                "nodes": ["candidate-1", "candidate-2", "candidate-3"],
                "edges": [],
            },
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
            "Return one JSON object only, without Markdown. Design exactly three "
            "distinct compact candidates for this round; each must be implementable "
            "as a ModelPlugin. Every "
            "hypothesis and candidate needs a citation. Respect parameter, "
            "epoch and timeout budgets. In rounds after the first, explain the prior "
            "error or result and cite available_fact_refs in based_on_fact_refs before "
            "proposing the new plan. Use round_records only as verified observations; "
            "never request raw history, source secrets, or credentials.\nRequired contract:\n"
            + json.dumps(contract, ensure_ascii=False, sort_keys=True)
            + "\nRun request:\n"
            + json.dumps(request, ensure_ascii=False, sort_keys=True)
        )
        raw = str(self._router.complete("idea_plan", prompt)).strip()
        try:
            plan = _parse_json_object(raw, "idea_plan response")
        except ValueError as exc:
            repair_prompt = (
                prompt
                + "\nPrevious response failed validation: "
                + str(exc)
                + "\nRepair it now. Return exactly one complete JSON object and no prose."
            )
            repaired = str(self._router.complete("idea_plan", repair_prompt)).strip()
            plan = _parse_json_object(repaired, "idea_plan response")
        if not isinstance(plan, dict):
            raise ValueError("idea_plan response must be an object")
        return plan

    def _coding_worker(self, request: dict[str, Any]) -> dict[str, Any]:
        candidate = _requested_candidate(request)
        budget = dict(candidate.get("budget") or {})
        task_id = _child_run_id(request)
        prior_facts = list(request.get("prior_facts") or [])
        decision_rationale = str(request["plan"].get("decision_rationale", ""))
        candidate_rationale = str(candidate.get("rationale", ""))
        fact_text = json.dumps(prior_facts, ensure_ascii=False, sort_keys=True)
        objective_parts = [str(request["goal"]), candidate_rationale, decision_rationale]
        if prior_facts:
            objective_parts.append("Verified prior facts: " + fact_text)
        task = CodingTaskSpec(
            task_id=task_id,
            objective="\n".join(item for item in objective_parts if item),
            candidate_name=_candidate_plugin_name(
                candidate.get("model_type", "candidate")
            ),
            config=_candidate_config(candidate),
            parameter_count_max=int(budget.get("parameter_count_max", 4000)),
            smoke_timeout_seconds=float(budget.get("timeout_seconds", 120.0)),
            constraints=tuple(
                value
                for value in (
                    str(candidate.get("stop_condition", "")),
                    str(request["plan"].get("risk", "")),
                    "Repair or exploit these verified prior facts: " + fact_text
                    if prior_facts
                    else "",
                )
                if value
            ),
        )
        coding_agent = (
            self._coding_factory()
            if self._coding_factory is not None and request.get("candidate") is not None
            else self._coding
        )
        result = asdict(coding_agent.generate_candidate(task))
        trace_path = result.get("trace_path")
        if trace_path:
            published = self._publish_file(
                Path(result.get("worktree") or self._root),
                str(trace_path),
                task_id,
            )
            if published:
                result["trace_path"] = published
        return result

    def _execution_worker(self, request: dict[str, Any]) -> dict[str, Any]:
        candidate = _requested_candidate(request)
        code = dict(request.get("code_result") or {})
        workspace = Path(code.get("worktree") or self._root).resolve()
        manifest = code.get("manifest_path") or candidate.get("manifest_path")
        if not manifest:
            raise ValueError("execution requires a gated candidate manifest")
        budget = dict(candidate.get("budget") or {})
        child_run_id = _child_run_id(request)
        arguments = {
            "manifest_path": str(manifest),
            "run_id": child_run_id,
            "config": _candidate_config(candidate),
            "output_dir": f"reports/{child_run_id}/execution",
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
                    workspace, str(artifact), child_run_id
                )
            ]
        )
        return payload

    def _writing_worker(self, request: dict[str, Any]) -> dict[str, Any]:
        code = dict(request.get("code_result") or {})
        source = self._report_source(request)
        bundle = EvidenceBundle.from_task_source(source)
        narrative = self._writing.write(bundle)
        source["cost_usd"] = self._router.total_cost()
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
        if request.get("exploration_outcomes"):
            return self._batch_report_source(request)
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

    def _batch_report_source(self, request: dict[str, Any]) -> dict[str, Any]:
        plan = request["plan"]
        outcomes = list(request.get("exploration_outcomes", []))
        executions = [_outcome_report_record(item, self._threshold) for item in outcomes]
        final = _final_report_record(
            dict(request.get("final_evaluation") or {}), self._threshold
        )
        citations = sorted(
            {
                str(item["citation"])
                for item in list(plan.get("hypotheses", []))
                + list(plan.get("candidate_experiments", []))
                if isinstance(item, dict) and item.get("citation")
            }
        )
        code_changes = []
        trace_refs = []
        failures = []
        for outcome in outcomes:
            code = dict(outcome.get("code_result") or {})
            code_changes.extend(
                {"file": str(path), "change": "CodingAgent generated candidate plugin"}
                for path in code.get("applied_files", [])
            )
            if code.get("trace_path"):
                trace_refs.append(str(code["trace_path"]))
            if outcome.get("status") != "completed":
                failures.append(
                    {
                        "id": str(outcome.get("experiment_id", "unknown")),
                        "status": str(outcome.get("status", "failed")),
                        "error": "; ".join(
                            str(item) for item in outcome.get("failure_facts", [])
                        ) or "experiment failed",
                    }
                )
        parameter_limits = [
            int(dict(item.get("candidate") or {}).get("budget", {}).get("parameter_count_max", 4000))
            for item in outcomes
            if isinstance(item, dict)
        ]
        run_id = _identifier(request["run_id"])
        return {
            "task_id": run_id,
            "goal": request.get("goal", ""),
            "constraints": {
                "parameter_count_max": max(parameter_limits or [4000]),
                "nmse_threshold_db": self._threshold,
                "rounds": len(request.get("round_records", [])),
                "experiments": len(executions),
                "final_evaluations": 1 if final else 0,
            },
            "citations": citations,
            "plan": plan,
            "round_records": _sanitized_round_records(
                list(request.get("round_records", []))
            ),
            "code_changes": code_changes,
            "executions": executions,
            "final_evaluation": final,
            "failure_cases": failures,
            "cost_usd": self._router.total_cost(),
            "trace_refs": sorted(set(trace_refs)),
            "reproduce_command": (
                f"python agent.py multi-agent --run-id {run_id} --rounds 3 "
                "--experiments-per-round 3 --final-evaluation"
            ),
            "limits": (
                "Only the nonlinear-modeling domain and supplied verified evidence "
                "are covered; search and final-evaluation scores are reported separately."
            ),
        }


def _first_candidate(plan: dict[str, Any]) -> dict[str, Any]:
    candidates = plan.get("candidate_experiments") or []
    if not candidates or not isinstance(candidates[0], dict):
        raise ValueError("plan must contain one candidate experiment")
    return dict(candidates[0])


def _requested_candidate(request: dict[str, Any]) -> dict[str, Any]:
    candidate = request.get("candidate")
    return dict(candidate) if isinstance(candidate, dict) else _first_candidate(request["plan"])


def _child_run_id(request: dict[str, Any]) -> str:
    experiment_id = str(request.get("experiment_id") or "candidate")
    if request.get("evaluation_kind") == "final" and not experiment_id.endswith("-final"):
        experiment_id = f"{experiment_id}-final"
    return _identifier(f"{request['run_id']}-{experiment_id}")


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


def _outcome_report_record(
    outcome: dict[str, Any], threshold: float
) -> dict[str, Any]:
    candidate = dict(outcome.get("candidate") or {})
    code = dict(outcome.get("code_result") or {})
    execution = dict(outcome.get("execution_result") or {})
    metrics = dict(outcome.get("metrics") or execution.get("metrics") or {})
    artifacts = [str(item) for item in outcome.get("artifacts", execution.get("artifacts", []))]
    nmse = metrics.get("nmse_db")
    descriptor = dict(execution.get("output") or {}).get("descriptor") or dict(
        code.get("validation") or {}
    ).get("descriptor")
    return {
        "run_id": str(outcome.get("experiment_id", "unknown")),
        "model_type": str(outcome.get("candidate_name") or candidate.get("model_type", "unknown")),
        "nmse_db": nmse,
        "parameter_count": metrics.get("parameter_count"),
        "baseline_nmse_db": candidate.get("baseline_nmse_db"),
        "psd_path": next((item for item in artifacts if Path(item).name.lower() == "psd.png"), None),
        "target_hit": nmse is not None and float(nmse) <= threshold,
        "model_descriptor": descriptor,
        "config": _candidate_config(candidate),
        "evaluation_kind": "search",
    }


def _final_report_record(
    final: dict[str, Any], threshold: float
) -> dict[str, Any]:
    if not final:
        return {}
    candidate = dict(final.get("candidate") or {})
    code = dict(final.get("code_result") or {})
    metrics = dict(final.get("metrics") or {})
    artifacts = [str(item) for item in final.get("artifacts", [])]
    nmse = metrics.get("nmse_db")
    descriptor = dict(final.get("output") or {}).get("descriptor") or dict(
        code.get("validation") or {}
    ).get("descriptor")
    source_id = str(final.get("source_experiment_id", "unknown"))
    return {
        "run_id": f"{source_id}-final",
        "source_experiment_id": source_id,
        "evaluation_kind": "final",
        "status": str(final.get("status", "failed")),
        "model_type": str(candidate.get("model_type", "unknown")),
        "nmse_db": nmse,
        "parameter_count": metrics.get("parameter_count"),
        "baseline_nmse_db": candidate.get("baseline_nmse_db"),
        "psd_path": next((item for item in artifacts if Path(item).name.lower() == "psd.png"), None),
        "target_hit": nmse is not None and float(nmse) <= threshold,
        "model_descriptor": descriptor,
        "config": _candidate_config(candidate),
    }


def _sanitized_round_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sanitized = []
    for record in records:
        outcomes = []
        for outcome in record.get("outcomes", []):
            outcomes.append(
                {
                    "experiment_id": str(outcome.get("experiment_id", "")),
                    "candidate_name": str(outcome.get("candidate_name", "")),
                    "status": str(outcome.get("status", "")),
                    "metrics": dict(outcome.get("metrics") or {}),
                    "failure_facts": list(outcome.get("failure_facts", [])),
                    "evidence_refs": [f"metric:{outcome.get('experiment_id', 'unknown')}"],
                }
            )
        sanitized.append(
            {
                key: value
                for key, value in record.items()
                if key != "outcomes"
            }
            | {"outcomes": outcomes}
        )
    return sanitized


def _identifier(value: Any) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", str(value)).strip("-_")
    if not cleaned or not cleaned[0].isalpha():
        cleaned = f"run-{cleaned or 'unknown'}"
    return cleaned[:64]


def _candidate_plugin_name(value: Any) -> str:
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(value))
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_").lower()
    if not cleaned or not cleaned[0].isalpha():
        cleaned = f"candidate_{cleaned or 'unknown'}"
    return cleaned[:64]


def _parse_json_object(value: str, label: str) -> dict[str, Any]:
    start = value.find("{")
    if start < 0:
        raise ValueError(f"{label} must contain one JSON object")
    try:
        payload, _ = json.JSONDecoder().raw_decode(value[start:])
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} is invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be one JSON object")
    return payload
