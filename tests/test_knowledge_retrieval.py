"""TDD tests for v3.6.0 Knowledge Base ingestion + retrieval."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from nonlinear_agent.knowledge.ingest import KnowledgeChunk, KnowledgeIngestor
from nonlinear_agent.knowledge.retriever import KnowledgeRetriever


_LABELED_QUERIES = [
    ("reflection facts failure causes", "kb-reflect-1"),
    ("schema guard planner validation", "kb-guard-1"),
    ("runtime control plane sqlite lease", "kb-runtime-1"),
    ("sse last event id replay", "kb-sse-1"),
    ("historical priors known best candidates", "kb-priors-1"),
    ("search strategy random optuna llm", "kb-search-1"),
    ("benchmark target hit rate rejected", "kb-bench-1"),
    ("domain plugin design space", "kb-domain-1"),
    ("tool registry tool spec schema", "kb-tools-1"),
    ("action loop observation planner", "kb-action-1"),
    ("memory episodic semantic procedural", "kb-memory-1"),
    ("knowledge ingestion chunk hash citation", "kb-ingest-1"),
    ("model router role provider budget", "kb-router-1"),
    ("supervisor worker isolation", "kb-supervisor-1"),
    ("experiment dag budget early stop", "kb-plan-1"),
    ("coding agent worktree patch test", "kb-coding-1"),
    ("execution agent tool registry shell", "kb-exec-1"),
    ("writing agent report pdf fidelity", "kb-writing-1"),
    ("trace span id attempt token cost", "kb-trace-1"),
    ("control plane dedup atomic claim", "kb-claim-1"),
    ("reflection recovery rejection history", "kb-recover-1"),
    ("parameter budget estimate", "kb-budget-1"),
    ("output dir normalize reports", "kb-artifacts-1"),
    ("benchmark case templates variants", "kb-variants-1"),
    ("stress concurrency failure recovery", "kb-stress-1"),
    ("mcp tools list bridge", "kb-mcp-1"),
    ("web ui dark theme metrics", "kb-web-1"),
    ("fake llm offline regression", "kb-fake-1"),
    ("deepseek json schema compliance", "kb-deepseek-1"),
    ("session trace logging persistence", "kb-session-1"),
]


def _build_kb_chunks(tmp: Path) -> list[KnowledgeChunk]:
    docs = {
        "kb-reflect-1": "reflection extracts facts and failure causes after each round",
        "kb-guard-1": "schema guard validates planner output and rejects unsupported fields",
        "kb-runtime-1": "runtime control plane uses sqlite with lease expiry and atomic claim",
        "kb-sse-1": "sse replay uses last event id to resume after disconnect",
        "kb-priors-1": "historical priors list known best candidates from project history",
        "kb-search-1": "search strategies include random search optuna tpe and llm planner",
        "kb-bench-1": "benchmark reports target hit rate rejected rate and runtime failure rate",
        "kb-domain-1": "domain plugin defines design space validation and tool registry",
        "kb-tools-1": "tool registry exposes tool spec with required arguments and schema",
        "kb-action-1": "action loop executes one action then returns observation to planner",
        "kb-memory-1": "memory is typed semantic episodic procedural with namespace isolation",
        "kb-ingest-1": "knowledge ingestion chunks documents with content hash and citation",
        "kb-router-1": "model router maps roles to provider model and token budget",
        "kb-supervisor-1": "supervisor routes state and isolates worker context",
        "kb-plan-1": "idea plan spec includes experiment dag budget and early stop",
        "kb-coding-1": "coding agent edits isolated worktree and must pass tests",
        "kb-exec-1": "execution agent only calls registered tools no free shell",
        "kb-writing-1": "writing agent produces report spec and pdf fidelity check",
        "kb-trace-1": "trace records span id attempt model and token cost",
        "kb-claim-1": "control plane deduplicates requests with atomic claim",
        "kb-recover-1": "rejection history feeds next round planner recovery",
        "kb-budget-1": "parameter budget estimate rejects over budget candidates",
        "kb-artifacts-1": "output dir normalization moves experiments under reports",
        "kb-variants-1": "benchmark case variants sweep thresholds and rounds",
        "kb-stress-1": "stress test injects failures and checks recovery",
        "kb-mcp-1": "mcp bridge exposes tools list to external clients",
        "kb-web-1": "web ui renders metrics with dark console theme",
        "kb-fake-1": "fake llm client returns scripted responses for offline regression",
        "kb-deepseek-1": "deepseek planner must follow json schema to pass guard",
        "kb-session-1": "session store persists trace events for replay",
    }
    chunks = []
    for chunk_id, text in docs.items():
        src = tmp / "kb" / f"{chunk_id}.md"
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text(f"# {chunk_id}\n\n{text}\n", encoding="utf-8")
        chunks.append(
            KnowledgeChunk(
                chunk_id=chunk_id,
                source_path=str(src),
                content_hash="",
                version="test",
                created_at=1.0,
                text=f"{chunk_id} {text}",
                citation=f"{chunk_id}.md#section",
            )
        )
    return chunks


class TestKnowledgeIngestion(unittest.TestCase):
    def test_ingest_only_whitelisted_directories(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "docs").mkdir()
            (root / "secret").mkdir()
            (root / "docs" / "a.md").write_text("# A\n\nplanner validation\n", encoding="utf-8")
            (root / "secret" / "b.md").write_text("secret", encoding="utf-8")
            ingestor = KnowledgeIngestor(roots=[root / "docs"])
            chunks = ingestor.ingest()
            self.assertTrue(all(chunk.source_path.startswith(str(root / "docs")) for chunk in chunks))
            self.assertFalse(any("secret" in chunk.source_path for chunk in chunks))

    def test_chunk_has_provenance(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "docs").mkdir()
            (root / "docs" / "a.md").write_text("# Head\n\nschema guard content\n", encoding="utf-8")
            chunks = KnowledgeIngestor(roots=[root / "docs"]).ingest()
            self.assertTrue(chunks)
            chunk = chunks[0]
            self.assertTrue(chunk.source_path.endswith("a.md"))
            self.assertEqual(len(chunk.content_hash), 64)
            self.assertEqual(chunk.version, "main")
            self.assertGreater(chunk.created_at, 0)
            self.assertIn("schema guard", chunk.text)


class TestKnowledgeRetrieval(unittest.TestCase):
    def setUp(self):
        with tempfile.TemporaryDirectory() as td:
            chunks = _build_kb_chunks(Path(td))
        self.retriever = KnowledgeRetriever(chunks=chunks)

    def test_retrieve_returns_top_k_with_citation(self):
        results = self.retriever.retrieve("schema guard planner validation", top_k=3)
        self.assertEqual(len(results), 3)
        self.assertTrue(all(r.chunk.citation for r in results))

    def test_recall_at_3_on_30_labeled_queries(self):
        hits = 0
        for query, expected in _LABELED_QUERIES:
            results = self.retriever.retrieve(query, top_k=3)
            ids = {r.chunk.chunk_id for r in results}
            if expected in ids:
                hits += 1
        recall = hits / len(_LABELED_QUERIES)
        self.assertGreaterEqual(recall, 0.90, f"Recall@3={recall:.2f}")

    def test_citation_precision_at_3(self):
        """Citation precision = top-1 citation is the labeled source."""
        correct = 0
        for query, expected in _LABELED_QUERIES:
            results = self.retriever.retrieve(query, top_k=3)
            if results and results[0].chunk.chunk_id == expected:
                correct += 1
        precision = correct / len(_LABELED_QUERIES)
        self.assertGreaterEqual(
            precision, 0.95, f"top-1 citation precision={precision:.2f}"
        )

    def test_cross_dataset_leakage_zero(self):
        ds_a = [
            KnowledgeChunk(
                chunk_id=f"a-{i}", source_path=f"/kb/a-{i}.md", content_hash="", version="t",
                created_at=1.0, text=f"dataset alpha metric {i}", citation=f"a-{i}.md",
                namespace=("dataset", "alpha"),
            )
            for i in range(10)
        ]
        ds_b = [
            KnowledgeChunk(
                chunk_id=f"b-{i}", source_path=f"/kb/b-{i}.md", content_hash="", version="t",
                created_at=1.0, text=f"dataset beta metric {i}", citation=f"b-{i}.md",
                namespace=("dataset", "beta"),
            )
            for i in range(10)
        ]
        retriever = KnowledgeRetriever(chunks=ds_a + ds_b)
        results = retriever.retrieve("dataset alpha metric 3", top_k=3, namespace_filter={"dataset": "alpha"})
        self.assertTrue(results)
        self.assertTrue(all(r.chunk.chunk_id.startswith("a-") for r in results))


if __name__ == "__main__":
    unittest.main()
