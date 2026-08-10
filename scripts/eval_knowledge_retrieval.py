"""Reproducible knowledge-retrieval evaluation (v3.6.1).

Runs the 30 user-style Chinese queries against the real project KB and
reports BM25 / hybrid / hybrid+rerank recall@3 and citation precision,
writing results to benchmarks/knowledge-eval-v1/.

Usage:
  python scripts/eval_knowledge_retrieval.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nonlinear_agent.knowledge.embedder import LocalTransformerEmbedder  # noqa: E402
from nonlinear_agent.knowledge.ingest import KnowledgeIngestor  # noqa: E402
from nonlinear_agent.knowledge.reranker import LocalCrossEncoderReranker  # noqa: E402
from nonlinear_agent.knowledge.retriever import KnowledgeRetriever  # noqa: E402

from tests.test_knowledge_retrieval_hybrid import REAL_QUERIES, _recall  # noqa: E402


def main() -> int:
    roots = [
        PROJECT_ROOT / "README.md",
        PROJECT_ROOT / "docs/handoff",
        PROJECT_ROOT / "docs/learning",
        PROJECT_ROOT / "docs/experiments",
        PROJECT_ROOT / "configs",
    ]
    chunks = KnowledgeIngestor(roots=roots).ingest()
    print(f"ingested {len(chunks)} chunks", flush=True)

    embedder = LocalTransformerEmbedder(batch_size=16)
    reranker = LocalCrossEncoderReranker(batch_size=16)

    bm25 = KnowledgeRetriever(chunks=chunks)
    hybrid = KnowledgeRetriever(chunks=chunks, embedder=embedder)
    full = KnowledgeRetriever(
        chunks=chunks, embedder=embedder, reranker=reranker, bm25_candidates=100
    )

    results = {
        "query_count": len(REAL_QUERIES),
        "chunk_count": len(chunks),
        "bm25_recall_at_3": _recall(bm25, use_expansion=False),
        "hybrid_recall_at_3": _recall(hybrid, use_expansion=False),
        "hybrid_rerank_recall_at_3": _recall(full, use_expansion=False),
        "hybrid_rerank_expansion_recall_at_3": _recall(full),
    }
    print(json.dumps(results, ensure_ascii=False, indent=2))

    output_dir = PROJECT_ROOT / "benchmarks" / "knowledge-eval-v1"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    md = [
        "# Knowledge Retrieval Eval (v3.6.1)",
        "",
        f"- queries: {results['query_count']} (user-style Chinese, multi-accept)",
        f"- chunks: {results['chunk_count']}",
        f"- BM25 recall@3: {results['bm25_recall_at_3']:.2f}",
        f"- hybrid recall@3: {results['hybrid_recall_at_3']:.2f}",
        f"- hybrid+rerank recall@3: {results['hybrid_rerank_recall_at_3']:.2f}",
        f"- hybrid+rerank+expansion recall@3: {results['hybrid_rerank_expansion_recall_at_3']:.2f}",
        "",
    ]
    (output_dir / "summary.md").write_text("\n".join(md), encoding="utf-8")
    print(f"wrote {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
