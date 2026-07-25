"""LLM-based search strategy adapters.

Wraps the ExperimentPlannerLoop into the SearchStrategy interface.
Two variants:
  - LLMDirectSearch: planner without reflection injection into next round
  - LLMProgramReflectionSearch: planner with full reflection feedback loop
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nonlinear_agent.domains.base import DomainPlugin
from nonlinear_agent.llm import FakeLLMClient
from nonlinear_agent.loop import ExperimentPlannerLoop
from nonlinear_agent.planner import ExperimentPlanner
from nonlinear_agent.search.base import SearchContext


class LLMDirectSearch:
    """LLM planner without reflection context injected into subsequent rounds.

    The ReflectionPolicy still computes facts (for observability) but they
    are NOT passed back to the planner as context for the next round.
    """

    name = "llm_direct"

    def __init__(self, context: SearchContext, workspace: Path | str):
        self._ctx = context
        self._workspace = Path(workspace)
        self._history: list[dict] = []
        self._trial_index = 0
        self._pending_candidate: dict[str, Any] | None = None

    def suggest(
        self, history: list[dict], trial_index: int
    ) -> dict[str, Any]:
        # In the actual evaluation protocol, LLM search runs as a full
        # ExperimentPlannerLoop per seed. The suggest/observe interface is
        # used for the other strategies; for LLM we use run_llm_strategy()
        # directly. This suggest returns a placeholder.
        return {}

    def observe(self, candidate: dict, result: dict) -> None:
        pass


class LLMProgramReflectionSearch:
    """LLM planner with full reflection feedback injected into each round."""

    name = "llm_program_reflection"

    def __init__(self, context: SearchContext, workspace: Path | str):
        self._ctx = context
        self._workspace = Path(workspace)

    def suggest(
        self, history: list[dict], trial_index: int
    ) -> dict[str, Any]:
        return {}

    def observe(self, candidate: dict, result: dict) -> None:
        pass
