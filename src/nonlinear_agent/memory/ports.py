"""Memory ports — business code depends on these abstractions, not a vendor SDK.

v3.6.0: typed memory (semantic / episodic / procedural) with full provenance
(run/action/config/dataset hash, evidence refs, model, prompt hash, confidence)
and namespace isolation (domain, dataset hash, model family).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, runtime_checkable


class MemoryKind(str, Enum):
    SEMANTIC = "semantic"
    EPISODIC = "episodic"
    PROCEDURAL = "procedural"


@dataclass(frozen=True)
class MemoryItem:
    """One immutable, fully-provenanced memory record."""

    memory_id: str
    kind: MemoryKind
    # (domain, dataset_hash, model_family)
    namespace: tuple[str, str, str]
    fact: str
    evidence_refs: tuple[str, ...] = ()
    run_id: str = ""
    action_id: str | None = None
    config_hash: str | None = None
    dataset_hash: str = ""
    metrics: dict[str, float] = field(default_factory=dict)
    created_by_role: str = "system"
    model: str = ""
    prompt_hash: str | None = None
    created_at: float = 0.0
    confidence: float = 1.0
    valid_from: float | None = None
    supersedes: str | None = None
    invalidated_at: float | None = None

    def is_stale(self, now: float | None = None) -> bool:
        return self.invalidated_at is not None


@runtime_checkable
class MemoryBackend(Protocol):
    """Storage port. Implementations: LangGraph Store (InMemory/Postgres)."""

    def write(self, item: MemoryItem) -> str: ...

    def get(self, memory_id: str) -> MemoryItem | None: ...

    def query(
        self,
        namespace: tuple[str, str, str],
        kind: MemoryKind | None = None,
        top_k: int = 5,
    ) -> list[MemoryItem]: ...

    def invalidate(self, memory_id: str, invalidated_at: float | None = None) -> None: ...

    def list_by_run(self, run_id: str) -> list[MemoryItem]: ...

    def delete_run(self, run_id: str) -> list[str]: ...

    def close(self) -> None: ...
