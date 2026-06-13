"""DomainPlugin Protocol — the contract that decouples the Agent Harness from
any specific experiment domain.

Every domain (nonlinear modeling, synthetic regression, etc.) implements this
protocol so the Planner, Guard, Loop, and Runtime stay generic.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from nonlinear_agent.tools import ToolRegistry


@runtime_checkable
class DomainPlugin(Protocol):
    """A pluggable experiment domain.

    Implementations supply:
    - Planner instructions and design space (for LLM prompts)
    - Candidate validation rules (for the schema guard)
    - A ToolRegistry with domain-specific tools
    - Primary metric and comparison semantics
    - Default base config and constraints
    """

    name: str

    def planner_instructions(self) -> str:
        """Return domain-specific guidance text appended to the planner prompt."""
        ...

    def design_space(self) -> dict[str, list[object]]:
        """Return a structured mapping of field -> allowed values for search."""
        ...

    def validate_candidate(self, overrides: dict[str, object]) -> list[str]:
        """Validate a candidate override dict. Returns a list of error messages (empty = valid)."""
        ...

    def build_tool_registry(self, workspace: Path) -> "ToolRegistry":
        """Build a ToolRegistry populated with domain-specific tools."""
        ...

    def primary_metric(self) -> str:
        """Return the name of the primary evaluation metric (e.g. 'nmse_db')."""
        ...

    def is_better(self, candidate: dict, incumbent: dict) -> bool:
        """Return True if candidate outperforms incumbent on the primary metric."""
        ...

    def default_base_config(self) -> str:
        """Return the default base config path for this domain."""
        ...

    def default_constraints(self) -> dict:
        """Return default constraints (parameter_count_max, metric, thresholds)."""
        ...
