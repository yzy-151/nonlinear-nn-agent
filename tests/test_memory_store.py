"""TDD tests for v3.6.0 Memory Backend (ports + LangGraph Store adapter)."""

from __future__ import annotations

import unittest

from nonlinear_agent.memory.ports import MemoryItem, MemoryKind


def _item(
    memory_id: str = "mem-001",
    kind: MemoryKind = MemoryKind.EPISODIC,
    namespace: tuple[str, str, str] = ("nonlinear-modeling", "hash-ds-a", "tiny_mlp"),
    fact: str = "degree=5 reg=1e-4 reached val_mse=0.04336",
    run_id: str = "run-001",
    action_id: str = "act-001",
    config_hash: str = "cfg-001",
    dataset_hash: str = "hash-ds-a",
    confidence: float = 0.9,
    created_at: float = 1000.0,
    supersedes: str | None = None,
) -> MemoryItem:
    return MemoryItem(
        memory_id=memory_id,
        kind=kind,
        namespace=namespace,
        fact=fact,
        evidence_refs=("evt-001",),
        run_id=run_id,
        action_id=action_id,
        config_hash=config_hash,
        dataset_hash=dataset_hash,
        metrics={"val_mse": 0.04336},
        created_by_role="execution",
        model="fake",
        prompt_hash="prompt-001",
        created_at=created_at,
        confidence=confidence,
        valid_from=1000.0,
        supersedes=supersedes,
        invalidated_at=None,
    )


class TestMemoryBackendContract(unittest.TestCase):
    """MemoryBackend 端口：业务代码只依赖端口，不依赖厂商 SDK。"""

    def test_langgraph_backend_implements_protocol(self):
        from nonlinear_agent.memory.langgraph_store import LangGraphMemoryBackend
        from nonlinear_agent.memory.ports import MemoryBackend

        self.assertTrue(issubclass(LangGraphMemoryBackend, MemoryBackend))

    def test_write_and_get_roundtrip(self):
        from nonlinear_agent.memory.langgraph_store import LangGraphMemoryBackend

        backend = LangGraphMemoryBackend()
        item = _item()
        memory_id = backend.write(item)
        self.assertEqual(memory_id, item.memory_id)
        got = backend.get(memory_id)
        self.assertIsNotNone(got)
        self.assertEqual(got.fact, item.fact)
        self.assertEqual(got.namespace, item.namespace)
        backend.close()

    def test_query_filters_by_kind_and_top_k(self):
        from nonlinear_agent.memory.langgraph_store import LangGraphMemoryBackend

        backend = LangGraphMemoryBackend()
        for i in range(6):
            kind = MemoryKind.EPISODIC if i < 4 else MemoryKind.SEMANTIC
            backend.write(_item(memory_id=f"mem-{i:03d}", kind=kind))
        episodic = backend.query(
            ("nonlinear-modeling", "hash-ds-a", "tiny_mlp"),
            kind=MemoryKind.EPISODIC,
            top_k=3,
        )
        self.assertEqual(len(episodic), 3)
        self.assertTrue(all(m.kind == MemoryKind.EPISODIC for m in episodic))
        backend.close()

    def test_namespace_isolation(self):
        from nonlinear_agent.memory.langgraph_store import LangGraphMemoryBackend

        backend = LangGraphMemoryBackend()
        backend.write(_item(memory_id="mem-a", namespace=("d1", "h1", "m1")))
        backend.write(_item(memory_id="mem-b", namespace=("d2", "h1", "m1")))
        backend.write(_item(memory_id="mem-c", namespace=("d1", "h2", "m1")))
        # 跨 domain 或跨 dataset 都不应被检索到
        found = backend.query(("d1", "h1", "m1"), top_k=10)
        self.assertEqual([m.memory_id for m in found], ["mem-a"])
        backend.close()

    def test_stale_memory_does_not_override_new_evidence(self):
        from nonlinear_agent.memory.langgraph_store import LangGraphMemoryBackend

        backend = LangGraphMemoryBackend()
        old = _item(memory_id="mem-old", confidence=0.5, created_at=1.0)
        new = _item(memory_id="mem-new", confidence=0.95, created_at=2.0, supersedes="mem-old")
        backend.write(old)
        backend.write(new)
        # 旧记录仍可读取（审计链），且被新记录 supersede
        self.assertIsNotNone(backend.get("mem-old"))
        self.assertEqual(backend.get("mem-new").supersedes, "mem-old")
        backend.close()

    def test_invalidate_marks_tombstone_without_removing_audit_chain(self):
        from nonlinear_agent.memory.langgraph_store import LangGraphMemoryBackend

        backend = LangGraphMemoryBackend()
        item = _item()
        backend.write(item)
        backend.invalidate(item.memory_id, invalidated_at=2000.0)
        got = backend.get(item.memory_id)
        self.assertIsNotNone(got)
        self.assertEqual(got.invalidated_at, 2000.0)
        backend.close()

    def test_delete_run_returns_all_derived_memory_ids(self):
        from nonlinear_agent.memory.langgraph_store import LangGraphMemoryBackend

        backend = LangGraphMemoryBackend()
        backend.write(_item(memory_id="mem-1", run_id="run-X"))
        backend.write(_item(memory_id="mem-2", run_id="run-X"))
        backend.write(_item(memory_id="mem-3", run_id="run-Y"))
        removed = backend.delete_run("run-X")
        self.assertEqual(sorted(removed), ["mem-1", "mem-2"])
        self.assertIsNone(backend.get("mem-1"))
        self.assertIsNotNone(backend.get("mem-3"))
        backend.close()

    def test_list_namespaces_returns_only_nonempty_namespaces(self):
        from nonlinear_agent.memory.langgraph_store import LangGraphMemoryBackend

        backend = LangGraphMemoryBackend()
        backend.write(_item(memory_id="mem-a", namespace=("d1", "h1", "m1")))
        namespaces = backend.list_namespaces()
        self.assertEqual(namespaces, [("d1", "h1", "m1")])
        backend.close()

    def test_item_carries_full_provenance(self):
        item = _item()
        self.assertEqual(item.evidence_refs, ("evt-001",))
        self.assertEqual(item.config_hash, "cfg-001")
        self.assertEqual(item.dataset_hash, "hash-ds-a")
        self.assertEqual(item.created_by_role, "execution")
        self.assertEqual(item.model, "fake")
        self.assertEqual(item.prompt_hash, "prompt-001")
        self.assertEqual(item.confidence, 0.9)


class TestPostgresProfileDependency(unittest.TestCase):
    def test_postgres_backend_raises_clear_error_when_driver_missing(self):
        from nonlinear_agent.memory.langgraph_store import PostgresMemoryBackend

        with self.assertRaises(ImportError) as ctx:
            PostgresMemoryBackend(connection_string="postgresql://localhost/nn")
        self.assertIn("psycopg", str(ctx.exception).lower())


if __name__ == "__main__":
    unittest.main()
