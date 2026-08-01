"""SimpleDomain — minimal domain adapter for new experiment types.

Instead of implementing the full DomainPlugin protocol (9+ methods), a new
experiment only needs to provide:
  - a design space (dict of field -> list of allowed values)
  - one callable that runs a candidate and returns a metric dict
  - the primary metric name and whether lower is better

Example for a grid/scan-style experiment:

    from nonlinear_agent.domains.simple import SimpleDomain

    def run_candidate(threshold=0.5, kernel="rbf", **kw):
        acc = _train_and_evaluate(threshold, kernel)   # returns accuracy
        return {"acc": acc, "threshold": threshold, "kernel": kernel}

    scan = SimpleDomain(
        name="grid-scan",
        design_space={"threshold": [0.1, 0.2, 0.5], "kernel": ["rbf", "linear"]},
        run_candidate=run_candidate,
        primary_metric="acc",
        lower_is_better=False,
    )

Everything else (prompt, guard, tool registry, harness steps, metric
semantics) is derived automatically.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from nonlinear_agent.tools import ToolRegistry, ToolSpec


@dataclass(frozen=True)
class _SimpleSpec:
    session_id: str
    overrides: dict[str, Any]
    timeout_seconds: float


class SimpleDomain:
    """Adapter that turns a design space + one runner into a DomainPlugin."""

    def __init__(
        self,
        name: str,
        design_space: dict[str, list[object]],
        run_candidate: Callable[..., dict[str, Any]],
        primary_metric: str,
        lower_is_better: bool = True,
        parameter_count_max: int = 100,
        instructions: str | None = None,
        metric_unit: str = "",
    ):
        self.name = name
        self._design_space = design_space
        self._run = run_candidate
        self._metric = primary_metric
        self._lower = lower_is_better
        self._budget = parameter_count_max
        self._unit = metric_unit
        self._instructions = instructions or self._default_instructions()

    # ── Planner interface ──────────────────────────────────────
    def planner_instructions(self) -> str:
        return self._instructions

    def design_space(self) -> dict[str, list[object]]:
        return self._design_space

    def planner_allowed_tools(self) -> list[str]:
        return ["run_candidate"]

    # ── Guard interface ────────────────────────────────────────
    def validate_candidate(
        self, overrides: dict[str, object], parameter_count_max: int | None = None
    ) -> list[str]:
        errors: list[str] = []
        for field, choices in self._design_space.items():
            if field not in overrides:
                continue
            value = overrides[field]
            if value not in choices:
                errors.append(f"{field} must be one of {choices}.")
        return errors

    def allowed_override_fields(self) -> set[str]:
        return set(self._design_space.keys())

    # ── Execution interface ────────────────────────────────────
    def build_tool_registry(
        self, workspace: Path, default_timeout_seconds: float = 300.0
    ) -> ToolRegistry:
        registry = ToolRegistry(default_timeout_seconds=default_timeout_seconds)
        registry.register(
            "run_candidate",
            self._run,
            spec=ToolSpec(
                name="run_candidate",
                description=f"Run one candidate and return {self._metric}.",
                input_schema={"type": "object", "required": sorted(self._design_space.keys())},
                category="experiment",
                error_policy="return_error",
            ),
        )
        return registry

    def build_harness_spec(
        self, session_id: str, base_config: str, overrides: dict[str, Any],
        constraints: dict[str, Any], timeout_seconds: float,
    ) -> Any:
        return _SimpleSpec(
            session_id=session_id,
            overrides=dict(overrides),
            timeout_seconds=timeout_seconds,
        )

    def build_harness_steps(self, spec: Any, workspace: Path) -> list[Any]:
        from nonlinear_agent.tools import ToolCall

        return [ToolCall(name="run_candidate", args=dict(spec.overrides))]

    # ── Metric semantics ───────────────────────────────────────
    def primary_metric(self) -> str:
        return self._metric

    def is_better(self, candidate: dict, incumbent: dict) -> bool:
        c = float(candidate.get(self._metric, float("inf")))
        i = float(incumbent.get(self._metric, float("inf")))
        return c < i if self._lower else c > i

    def display_metric_names(self) -> set[str]:
        return {self._metric, *self._design_space.keys()}

    def display_metric_unit(self) -> str:
        return self._unit

    def display_metric_lower_is_better(self) -> bool:
        return self._lower

    def artifact_preview_patterns(self) -> list[str]:
        return []

    # ── Defaults / provenance ──────────────────────────────────
    def default_base_config(self) -> str:
        return ""

    def default_constraints(self) -> dict:
        return {"parameter_count_max": self._budget, "metric": self._metric}

    def dataset_fingerprint(self) -> str:
        return "unknown"

    def historical_priors(self) -> list[Any]:
        return []

    def _default_instructions(self) -> str:
        fields = ", ".join(
            f"{field} in {choices}" for field, choices in self._design_space.items()
        )
        return (
            f"Design experiments for the '{self.name}' task. "
            f"Each candidate is defined by overrides with {fields}. "
            f"Return overrides using exactly these field names; "
            f"any other field will be rejected by the guard.\n"
        )
