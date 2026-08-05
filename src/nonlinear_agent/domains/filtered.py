"""FilteredDomain — whitelist control for which hyperparameters are optimizable.

Wraps any DomainPlugin and restricts `design_space` / `allowed_override_fields`
to a user-selected subset. Disabled fields are no longer suggested to the LLM
and are rejected by the guard, so the search only tunes the enabled directions.

Used by the Web UI "optimizable directions" toggles to update the whitelist
without touching the underlying domain.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


class FilteredDomain:
    """Delegate wrapper that limits the optimizable field whitelist."""

    def __init__(self, domain: Any, enabled_fields: list[str] | set[str]):
        self._domain = domain
        self._enabled = set(enabled_fields)

    # ── Delegated identity ─────────────────────────────────────
    @property
    def name(self) -> str:
        return self._domain.name

    # ── Planner interface (filtered) ───────────────────────────
    def planner_instructions(self) -> str:
        return self._domain.planner_instructions()

    def design_space(self) -> dict[str, list[object]]:
        return {
            key: value
            for key, value in self._domain.design_space().items()
            if key in self._enabled
        }

    def planner_allowed_tools(self) -> list[str]:
        return self._domain.planner_allowed_tools()

    # ── Guard interface (filtered) ─────────────────────────────
    def validate_candidate(
        self, overrides: dict[str, object], parameter_count_max: int | None = None
    ) -> list[str]:
        # Fields outside the enabled whitelist are rejected outright
        unsupported = sorted(set(overrides) - self._enabled)
        errors = [f"field not enabled for tuning: {f}" for f in unsupported]
        allowed_overrides = {k: v for k, v in overrides.items() if k in self._enabled}
        errors.extend(self._domain.validate_candidate(allowed_overrides, parameter_count_max))
        return errors

    def allowed_override_fields(self) -> set[str]:
        return self._enabled & self._domain.allowed_override_fields()

    # ── Everything else is delegated ───────────────────────────
    def build_tool_registry(self, workspace: Path, default_timeout_seconds: float = 300.0):
        return self._domain.build_tool_registry(workspace, default_timeout_seconds)

    def build_harness_spec(self, session_id, base_config, overrides, constraints, timeout_seconds):
        return self._domain.build_harness_spec(
            session_id, base_config, overrides, constraints, timeout_seconds
        )

    def build_harness_steps(self, spec, workspace):
        return self._domain.build_harness_steps(spec, workspace)

    def primary_metric(self) -> str:
        return self._domain.primary_metric()

    def is_better(self, candidate: dict, incumbent: dict) -> bool:
        return self._domain.is_better(candidate, incumbent)

    def display_metric_names(self) -> set[str]:
        return self._domain.display_metric_names()

    def display_metric_unit(self) -> str:
        return self._domain.display_metric_unit()

    def display_metric_lower_is_better(self) -> bool:
        return self._domain.display_metric_lower_is_better()

    def artifact_preview_patterns(self) -> list[str]:
        return self._domain.artifact_preview_patterns()

    def default_base_config(self) -> str:
        return self._domain.default_base_config()

    def default_constraints(self) -> dict:
        return self._domain.default_constraints()

    def dataset_fingerprint(self) -> str:
        return self._domain.dataset_fingerprint()

    def historical_priors(self) -> list[Any]:
        return self._domain.historical_priors()
