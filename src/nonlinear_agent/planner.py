from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from nonlinear_agent.llm import LLMClient
from nonlinear_agent.planner_validation import normalize_planner_overrides


@dataclass(frozen=True)
class PlannedExperiment:
    experiment_id: str
    reason: str
    overrides: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExperimentPlan:
    summary: str
    experiments: list[PlannedExperiment]
    stop: bool = False


class ExperimentPlanner:
    def __init__(self, llm_client: LLMClient, allowed_tools: list[str] | None = None):
        self.llm_client = llm_client
        self.allowed_tools = allowed_tools or ["generate_config", "run_training", "verify_artifacts", "write_report"]

    def plan(
        self,
        goal: str,
        history: list[dict[str, Any]] | None = None,
        constraints: dict[str, Any] | None = None,
    ) -> ExperimentPlan:
        prompt = self._build_prompt(goal=goal, history=history or [], constraints=constraints or {})
        raw = self.llm_client.complete(prompt)
        payload = _parse_json_object(raw)
        return self._parse_plan(payload)

    def _build_prompt(self, goal: str, history: list[dict[str, Any]], constraints: dict[str, Any]) -> str:
        return (
            "Design the next nonlinear-system modeling experiments.\n"
            f"Goal: {goal}\n"
            f"Constraints: {json.dumps(constraints, ensure_ascii=False)}\n"
            f"History: {json.dumps(history, ensure_ascii=False)}\n\n"
            "Return JSON only with schema:\n"
            "{\"summary\": str, \"stop\": bool, \"experiments\": ["
            "{\"id\": str, \"reason\": str, \"overrides\": object}]}\n"
            "Executable design space:\n"
            "- model_type: complex_lstsq, linear, tiny_mlp, spline_mlp.\n"
            "- feature_mode: complex_mp is preferred for RF nonlinear memory polynomial structure; legacy_abs is a baseline.\n"
            "- complex_lstsq explores memory_depth and mp_order_count with closed-form fitting.\n"
            "- tiny_mlp explores hidden_units and activation in relu/tanh/silu/gelu.\n"
            "- spline_mlp is a physics-informed shallow nonlinear model: one nonlinear layer with a learnable 1D LUT activation, usually spline_knots=16 and first-order linear interpolation.\n"
            "- Good spline_mlp candidates under 4000 params: feature_mode=complex_mp, mp_order_count=1, memory_depth in [24, 48, 72], hidden_units in [16, 32], spline_knots=16.\n"
            "- Keep parameter_count_max from constraints; prefer fewer parameters when NMSE is similar.\n"
            "Use overrides for YAML config fields such as model_type, feature_mode, memory_depth, mp_order_count, epochs, learning_rate, optimizer, output_dir, hidden_units, activation, spline_knots, spline_range. Do not output shell commands. "
            f"The runtime will only use these tools: {', '.join(self.allowed_tools)}."
        )

    def _parse_plan(self, payload: dict[str, Any]) -> ExperimentPlan:
        experiments = []
        for item in payload.get("experiments", []):
            experiment_id = str(item.get("id", "")).strip()
            if not experiment_id:
                raise ValueError("Planned experiment is missing id.")
            overrides = item.get("overrides", {})
            if not isinstance(overrides, dict):
                raise ValueError(f"Experiment {experiment_id} overrides must be an object.")
            overrides = normalize_planner_overrides(overrides)
            experiments.append(
                PlannedExperiment(
                    experiment_id=experiment_id,
                    reason=str(item.get("reason", "")),
                    overrides=overrides,
                )
            )
        return ExperimentPlan(
            summary=str(payload.get("summary", "")),
            stop=bool(payload.get("stop", False)),
            experiments=experiments,
        )


def _parse_json_object(text: str) -> dict[str, Any]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise
        payload = json.loads(text[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("Planner response must be a JSON object.")
    return payload



