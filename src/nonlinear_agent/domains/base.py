"""DomainPlugin Protocol — the contract that decouples the Agent Harness from
any specific experiment domain.

Every domain (nonlinear modeling, synthetic regression, etc.) implements this
protocol so the Planner, Guard, Loop, and Runtime stay generic.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from nonlinear_agent.tools import ToolCall, ToolRegistry


@runtime_checkable
class DomainPlugin(Protocol):
    """A pluggable experiment domain.

    Implementations supply:
    - Planner instructions and design space (for LLM prompts)
    - Candidate validation rules (for the schema guard)
    - A ToolRegistry with domain-specific tools
    - Primary metric and comparison semantics
    - Default base config and constraints
    - Execution workflow (spec + steps)
    - Display configuration (metric names, units, preview patterns)
    """

    name: str

    # ── Planner interface ──────────────────────────────────────
    def planner_instructions(self) -> str: ...
    def design_space(self) -> dict[str, list[object]]: ...
    def planner_allowed_tools(self) -> list[str]: ...

    # ── Guard interface ────────────────────────────────────────
    def validate_candidate(self, overrides: dict[str, object]) -> list[str]: ...
    def allowed_override_fields(self) -> set[str]: ...

    # ── Execution interface ────────────────────────────────────
    def build_tool_registry(self, workspace: Path) -> "ToolRegistry": ...
    def build_harness_spec(
        self, session_id: str, base_config: str, overrides: dict[str, Any],
        constraints: dict[str, Any], timeout_seconds: float,
    ) -> Any: ...
    def build_harness_steps(self, spec: Any, workspace: Path) -> list["ToolCall"]: ...

    # ── Metric semantics ───────────────────────────────────────
    def primary_metric(self) -> str: ...
    def is_better(self, candidate: dict, incumbent: dict) -> bool: ...
    def display_metric_names(self) -> set[str]: ...
    def display_metric_unit(self) -> str: ...
    def display_metric_lower_is_better(self) -> bool: ...
    def artifact_preview_patterns(self) -> list[str]: ...

    # ── Defaults ──────────────────────────────────────────────
    def default_base_config(self) -> str: ...
    def default_constraints(self) -> dict: ...
