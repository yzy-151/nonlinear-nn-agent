"""SearchStrategy Protocol and SearchContext dataclass.

All search strategies (Random, Optuna TPE, LLM) implement this protocol
so the EvaluationProtocol can drive them uniformly through the same
suggest/observe loop.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from nonlinear_agent.domains.base import DomainPlugin


@dataclass(frozen=True)
class SearchContext:
    """Immutable context passed to every search strategy."""

    domain: DomainPlugin
    seed: int
    trial_budget: int
    parameter_count_max: int = 4000
    llm_provider: str = "simulated"


@runtime_checkable
class SearchStrategy(Protocol):
    """A pluggable search strategy for experiment candidate selection.

    Implementations:
      - RandomSearch: uniform sampling from domain.design_space()
      - OptunaTPESearch: tree-structured Parzen estimator
      - LLMDirectSearch: LLM planner without reflection injection
      - LLMProgramReflectionSearch: LLM planner with reflection
    """

    name: str

    def suggest(
        self, history: list[dict], trial_index: int
    ) -> dict:
        """Propose the next candidate as an overrides dict."""
        ...

    def observe(self, candidate: dict, result: dict) -> None:
        """Record the outcome of a suggested candidate (for learning strategies)."""
        ...
