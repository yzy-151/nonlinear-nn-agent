"""Planner context assembly (v3.6.x gap closure).

The planner only receives top-k knowledge chunks (with citations) and top-k
*valid* memories: invalidated (stale) items are filtered out before they can
influence the planner, and memory stays isolated by namespace.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from nonlinear_agent.memory.ports import MemoryBackend, MemoryItem


@dataclass(frozen=True)
class PlannerContext:
    knowledge: tuple[Any, ...] = ()  # top-k scored chunks with citation
    memory: tuple[MemoryItem, ...] = ()  # top-k valid memories


class PlannerContextBuilder:
    """Builds the exact context the planner may see (no full-corpus injection)."""

    def __init__(self, retriever: Any, memory_backend: MemoryBackend):
        self._retriever = retriever
        self._memory_backend = memory_backend

    def build(
        self,
        query: str,
        namespace: tuple[str, str, str],
        top_k: int = 3,
    ) -> PlannerContext:
        knowledge = tuple(
            self._retriever.retrieve(query, top_k=top_k) or []
        )
        memory = self._memory_backend.query(namespace, top_k=top_k * 3)
        valid = [item for item in memory if item.invalidated_at is None]
        return PlannerContext(
            knowledge=knowledge[:top_k],
            memory=tuple(valid[:top_k]),
        )
