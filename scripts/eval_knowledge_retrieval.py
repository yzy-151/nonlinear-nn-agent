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


def _top1_precision(retriever, use_expansion: bool = True) -> float:
    """Fraction of queries whose top-1 citation is an accepted target."""
    correct = 0
    for query, accepted, extra in REAL_QUERIES:
        if use_expansion:
            results = retriever.retrieve_many([query, extra], top_k=1)
        else:
            results = retriever.retrieve(query, top_k=1)
        if results and any(
            accepted_fragment in results[0].chunk.citation
            for accepted_fragment in accepted
        ):
            correct += 1
    return correct / len(REAL_QUERIES)


def _recall_progress(retriever, use_expansion: bool = True) -> float:
    """Like tests._recall but prints per-batch progress."""
    hits = 0
    for i, (query, accepted, extra) in enumerate(REAL_QUERIES, start=1):
        if use_expansion:
            results = retriever.retrieve_many([query, extra], top_k=3)
        else:
            results = retriever.retrieve(query, top_k=3)
        if any(
            any(exp in r.chunk.citation for exp in accepted)
            for r in results
        ):
            hits += 1
        if i % 5 == 0:
            print(f"  recall progress {i}/{len(REAL_QUERIES)}", flush=True)
    return hits / len(REAL_QUERIES)


def _precision_progress(retriever) -> float:
    correct = 0
    for i, (query, accepted, extra) in enumerate(REAL_QUERIES, start=1):
        results = retriever.retrieve_many([query, extra], top_k=1)
        if results and any(
            exp in results[0].chunk.citation for exp in accepted
        ):
            correct += 1
        if i % 5 == 0:
            print(f"  precision progress {i}/{len(REAL_QUERIES)}", flush=True)
    return correct / len(REAL_QUERIES)


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

    embedder = LocalTransformerEmbedder(batch_size=32)
    reranker = LocalCrossEncoderReranker(batch_size=32)

    bm25 = KnowledgeRetriever(chunks=chunks)
    hybrid = KnowledgeRetriever(chunks=chunks, embedder=embedder)
    full = KnowledgeRetriever(
        chunks=chunks, embedder=embedder, reranker=reranker, bm25_candidates=150
    )

    print("evaluating BM25 baseline...", flush=True)
    bm25_recall = _recall_progress(bm25, use_expansion=False)
    print("evaluating hybrid...", flush=True)
    hybrid_recall = _recall_progress(hybrid, use_expansion=False)
    print("evaluating hybrid+rerank...", flush=True)
    rerank_recall = _recall_progress(full, use_expansion=False)
    print("evaluating hybrid+rerank+expansion (recall + precision)...", flush=True)
    expansion_recall = _recall_progress(full)
    precision_top1 = _precision_progress(full)

    results = {
        "query_count": len(REAL_QUERIES),
        "chunk_count": len(chunks),
        "bm25_recall_at_3": bm25_recall,
        "hybrid_recall_at_3": hybrid_recall,
        "hybrid_rerank_recall_at_3": rerank_recall,
        "hybrid_rerank_expansion_recall_at_3": expansion_recall,
        "hybrid_rerank_expansion_citation_precision_top1": precision_top1,
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
        f"- hybrid+rerank+expansion citation precision@1: {results['hybrid_rerank_expansion_citation_precision_top1']:.2f}",
        "",
    ]
    (output_dir / "summary.md").write_text("\n".join(md), encoding="utf-8")
    print(f"wrote {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
