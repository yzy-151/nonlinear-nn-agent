from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from nonlinear_agent.context_memory import HistoryCompressor
from nonlinear_agent.planner import ExperimentPlanner
from nonlinear_agent.planner_validation import validate_planned_overrides
from nonlinear_agent.run_artifacts import RunArtifactWriter, default_run_dir
from nonlinear_agent.server import HarnessRunSpec, build_harness_request, build_runtime


@dataclass(frozen=True)
class PlannerLoopResult:
    status: str
    rounds: int
    history: list[dict[str, Any]] = field(default_factory=list)
    summaries: list[str] = field(default_factory=list)


RuntimeFactory = Callable[[str], Any]


class ExperimentPlannerLoop:
    def __init__(
        self,
        planner: ExperimentPlanner,
        workspace: Path | str,
        runtime_factory: RuntimeFactory | None = None,
        base_config: str = "configs/model-search/lstsq-complexmp-o12-m150.yaml",
        constraints: dict[str, Any] | None = None,
        timeout_seconds: float = 300.0,
        artifact_dir: Path | str | None = None,
        history_compressor: HistoryCompressor | None = None,
    ):
        self.planner = planner
        self.workspace = Path(workspace)
        self.runtime_factory = runtime_factory or (
            lambda session_id: build_runtime(self.workspace, session_id=session_id, timeout_seconds=timeout_seconds)
        )
        self.base_config = base_config
        self.constraints = constraints or {"parameter_count_max": 4000, "metric": "nmse_db"}
        self.timeout_seconds = timeout_seconds
        self.artifact_writer = RunArtifactWriter(artifact_dir or default_run_dir(self.workspace))
        self.history_compressor = history_compressor or HistoryCompressor()

    async def run(self, goal: str, max_rounds: int = 3, max_experiments: int | None = None) -> PlannerLoopResult:
        history: list[dict[str, Any]] = []
        summaries: list[str] = []
        rounds = 0
        executed_experiments = 0
        for _ in range(max_rounds):
            rounds += 1
            prompt_history = self.history_compressor.build_prompt_history(history)
            plan = self.planner.plan(goal=goal, history=prompt_history, constraints=self.constraints)
            summaries.append(plan.summary)
            self.artifact_writer.write_plan(rounds, plan)
            if plan.stop and not plan.experiments:
                result = PlannerLoopResult(status="stopped", rounds=rounds, history=history, summaries=summaries)
                self.artifact_writer.write_result(result)
                return result
            for experiment in plan.experiments:
                if max_experiments is not None and executed_experiments >= max_experiments:
                    result = PlannerLoopResult(
                        status="max_experiments_reached",
                        rounds=rounds,
                        history=history,
                        summaries=summaries,
                    )
                    self.artifact_writer.write_result(result)
                    return result
                try:
                    overrides = validate_planned_overrides(
                        experiment.overrides,
                        parameter_count_max=self.constraints.get("parameter_count_max"),
                    )
                except ValueError as exc:
                    history.append({
                        "id": experiment.experiment_id,
                        "reason": experiment.reason,
                        "run_status": "rejected",
                        "error": str(exc),
                    })
                    continue
                metrics = await self._run_experiment(experiment.experiment_id, overrides)
                executed_experiments += 1
                record = {"id": experiment.experiment_id, "reason": experiment.reason, **metrics}
                history.append(record)
        result = PlannerLoopResult(status="max_rounds_reached", rounds=rounds, history=history, summaries=summaries)
        self.artifact_writer.write_result(result)
        return result

    async def _run_experiment(self, experiment_id: str, overrides: dict[str, Any]) -> dict[str, Any]:
        output_dir = str(overrides.get("output_dir", f"reports/{experiment_id}"))
        spec = HarnessRunSpec(
            session_id=experiment_id,
            base_config=self.base_config,
            output_dir=output_dir,
            epochs=int(overrides.get("epochs", 0)),
            learning_rate=float(overrides.get("learning_rate", 0.0008)),
            optimizer=str(overrides.get("optimizer", "adam")),
            nmse_threshold_db=float(overrides.get("nmse_threshold_db", self.constraints.get("nmse_threshold_db", -35.0))),
            timeout_seconds=self.timeout_seconds,
            overrides=overrides,
        )
        request = build_harness_request(spec)
        runtime = self.runtime_factory(experiment_id)
        metrics: dict[str, Any] = {"run_status": "succeeded"}
        async for event in runtime.run(request):
            if event.event_type == "metric":
                name = event.payload.get("name")
                if name:
                    metrics[str(name)] = event.payload.get("value")
            elif event.event_type == "error":
                metrics["run_status"] = "failed"
                metrics["error"] = event.error
        return metrics
