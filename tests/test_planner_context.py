"""TDD tests for planner context assembly: stale memory filtering + citations."""

from __future__ import annotations

import unittest

from nonlinear_agent.knowledge.ingest import KnowledgeChunk
from nonlinear_agent.memory.langgraph_store import LangGraphMemoryBackend
from nonlinear_agent.memory.ports import MemoryItem, MemoryKind


def _chunk(chunk_id: str, citation: str) -> KnowledgeChunk:
    return KnowledgeChunk(
        chunk_id=chunk_id,
        source_path=f"/kb/{chunk_id}.md",
        content_hash="",
        version="test",
        created_at=1.0,
        text=f"{chunk_id} content",
        citation=citation,
    )


def _memory(
    memory_id: str,
    fact: str,
    namespace: tuple[str, str, str] = ("nonlinear-modeling", "ds-1", "tiny_mlp"),
    invalidated_at: float | None = None,
) -> MemoryItem:
    return MemoryItem(
        memory_id=memory_id,
        kind=MemoryKind.EPISODIC,
        namespace=namespace,
        fact=fact,
        evidence_refs=(f"{memory_id}:evt",),
        run_id="run-1",
        created_by_role="execution",
        created_at=1.0,
        invalidated_at=invalidated_at,
    )


class _StubRetriever:
    def __init__(self, chunks: list[KnowledgeChunk]):
        self._chunks = chunks

    def retrieve(self, query: str, top_k: int = 3, **kwargs):
        return [
            type("Scored", (), {"chunk": chunk, "score": float(i)})
            for i, chunk in enumerate(self._chunks[:top_k])
        ]


class TestPlannerContextBuilder(unittest.TestCase):
    def test_stale_memory_never_enters_planner_context(self):
        from nonlinear_agent.memory.planner_context import PlannerContextBuilder

        backend = LangGraphMemoryBackend()
        namespace = ("nonlinear-modeling", "ds-1", "tiny_mlp")
        backend.write(_memory("mem-stale-1", "old fact", invalidated_at=5.0))
        backend.write(_memory("mem-stale-2", "old fact 2", invalidated_at=6.0))
        backend.write(_memory("mem-good-1", "valid fact 1"))
        backend.write(_memory("mem-good-2", "valid fact 2"))
        backend.write(_memory("mem-good-3", "valid fact 3"))
        backend.write(_memory("mem-good-4", "valid fact 4"))

        builder = PlannerContextBuilder(
            retriever=_StubRetriever([_chunk("kb-1", "docs/a.md#topic")]),
            memory_backend=backend,
        )
        context = builder.build(query="q", namespace=namespace, top_k=3)
        self.assertEqual(len(context.memory), 3)
        self.assertTrue(all(m.invalidated_at is None for m in context.memory))
        self.assertNotIn("mem-stale-1", [m.memory_id for m in context.memory])
        backend.close()

    def test_memory_cross_dataset_isolation(self):
        from nonlinear_agent.memory.planner_context import PlannerContextBuilder

        backend = LangGraphMemoryBackend()
        backend.write(_memory("mem-ds1", "ds1 fact", namespace=("nonlinear-modeling", "ds-1", "tiny_mlp")))
        backend.write(_memory("mem-ds2", "ds2 fact", namespace=("nonlinear-modeling", "ds-2", "tiny_mlp")))
        builder = PlannerContextBuilder(
            retriever=_StubRetriever([]),
            memory_backend=backend,
        )
        context = builder.build(
            query="q", namespace=("nonlinear-modeling", "ds-1", "tiny_mlp"), top_k=5
        )
        self.assertEqual([m.memory_id for m in context.memory], ["mem-ds1"])
        backend.close()

    def test_knowledge_top_k_with_citation(self):
        from nonlinear_agent.memory.planner_context import PlannerContextBuilder

        chunks = [
            _chunk("kb-1", "docs/a.md#reflection"),
            _chunk("kb-2", "docs/b.md#guard"),
            _chunk("kb-3", "docs/c.md#runtime"),
        ]
        builder = PlannerContextBuilder(
            retriever=_StubRetriever(chunks),
            memory_backend=LangGraphMemoryBackend(),
        )
        context = builder.build(
            query="q", namespace=("nonlinear-modeling", "ds-1", "tiny_mlp"), top_k=3
        )
        self.assertEqual(len(context.knowledge), 3)
        self.assertTrue(all(c.chunk.citation for c in context.knowledge))


if __name__ == "__main__":
    unittest.main()
