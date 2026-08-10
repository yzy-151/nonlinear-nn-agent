"""Top-k knowledge retrieval with citation.

Hybrid retrieval: pure-Python BM25 recalls a candidate pool, then an optional
local transformer embedder re-ranks by cosine similarity. Without an embedder
the retriever degrades gracefully to BM25-only, keeping offline tests and the
Web inspector dependency-free.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any

from nonlinear_agent.knowledge.embedder import Embedder
from nonlinear_agent.knowledge.ingest import KnowledgeChunk
from nonlinear_agent.knowledge.reranker import Reranker


@dataclass(frozen=True)
class ScoredChunk:
    chunk: KnowledgeChunk
    score: float


class KnowledgeRetriever:
    """BM25 retrieval over an in-memory chunk corpus."""

    _K1 = 1.5
    _B = 0.75
    _WORD = re.compile(r"[a-z0-9]+")

    def __init__(
        self,
        chunks: list[KnowledgeChunk],
        embedder: Embedder | None = None,
        reranker: Reranker | None = None,
        bm25_candidates: int = 50,
    ):
        self._chunks = chunks
        self._embedder = embedder
        self._reranker = reranker
        self._bm25_candidates = max(3, bm25_candidates)
        self._tokenized = [self._tokens(chunk.text) for chunk in chunks]
        self._doc_lens = [len(tokens) for tokens in self._tokenized]
        self._avg_len = (
            sum(self._doc_lens) / len(self._doc_lens) if self._doc_lens else 0.0
        )
        self._idf: dict[str, float] = {}
        doc_count = len(chunks)
        df: dict[str, int] = {}
        for tokens in self._tokenized:
            for token in set(tokens):
                df[token] = df.get(token, 0) + 1
        for token, count in df.items():
            self._idf[token] = math.log(
                1.0 + (doc_count - count + 0.5) / (count + 0.5)
            )
        # 预计算全库 embedding：查询时只 encode query，全库点积排序
        self._chunk_embeddings: list[list[float]] | None = None
        if embedder is not None:
            self._chunk_embeddings = embedder.encode(
                [chunk.text for chunk in self._chunks]
            )

    @staticmethod
    def _tokens(text: str) -> list[str]:
        lower = text.lower()
        words = KnowledgeRetriever._WORD.findall(lower)
        tokens = list(words)
        tokens += [w for w in words if len(w) > 2]
        # 单词 bigram 保留短语结构；字符 bigram 噪声太大已移除
        tokens += [f"{words[i]}_{words[i + 1]}" for i in range(max(0, len(words) - 1))]
        # 中文：每个汉字作为字符 token，保证纯中文查询也有词法信号
        tokens += [ch for ch in lower if "\u4e00" <= ch <= "\u9fff"]
        return tokens

    def retrieve(
        self,
        query: str,
        top_k: int = 3,
        namespace_filter: dict[str, Any] | None = None,
        hybrid: bool = True,
    ) -> list[ScoredChunk]:
        query_tokens = self._tokens(query)
        use_embedder = self._embedder is not None and hybrid and self._chunk_embeddings is not None
        if not query_tokens and not use_embedder:
            return []
        candidates = self._filtered_chunks(namespace_filter)
        if not candidates:
            return []
        bm25_scores = self._bm25_scores(candidates, query_tokens)

        pool: list[ScoredChunk] = []
        if use_embedder:
            pool = self._hybrid_rank(
                query, candidates, bm25_scores, self._bm25_candidates
            )
        else:
            chunk_by_id = {chunk.chunk_id: chunk for chunk in candidates}
            pool = sorted(
                (
                    ScoredChunk(chunk=chunk_by_id[chunk_id], score=score)
                    for chunk_id, score in bm25_scores.items()
                    if score > 0
                ),
                key=lambda item: item.score,
                reverse=True,
            )[: self._bm25_candidates]
        if self._reranker is not None:
            return self._reranker.rerank(query, pool, top_k=top_k)
        return pool[:top_k]

    def retrieve_many(
        self,
        queries: list[str],
        top_k: int = 3,
        namespace_filter: dict[str, Any] | None = None,
    ) -> list[ScoredChunk]:
        """Fuse results from multiple query phrasings (query expansion).

        Each phrasing retrieves 3x top_k candidates; reciprocal-rank fusion
        merges them so a term-rich expansion can rescue a user-style query.
        """
        per_query = [
            self.retrieve(
                query, top_k=top_k * 3, namespace_filter=namespace_filter
            )
            for query in queries
        ]
        rrf_scores: dict[str, float] = {}
        chunk_by_id = {chunk.chunk_id: chunk for chunk in self._chunks}
        for results in per_query:
            for rank, item in enumerate(results):
                rrf_scores[item.chunk.chunk_id] = rrf_scores.get(
                    item.chunk.chunk_id, 0.0
                ) + 1.0 / (60.0 + rank)
        merged = sorted(
            (
                ScoredChunk(chunk=chunk_by_id[chunk_id], score=score)
                for chunk_id, score in rrf_scores.items()
                if chunk_id in chunk_by_id
            ),
            key=lambda item: item.score,
            reverse=True,
        )
        return merged[:top_k]

    def _bm25_scores(
        self, candidates: list[KnowledgeChunk], query_tokens: list[str]
    ) -> dict[str, float]:
        scores: dict[str, float] = {}
        for chunk in candidates:
            tokens = self._tokens(chunk.text)
            doc_len = len(tokens)
            freq: dict[str, int] = {}
            for token in tokens:
                freq[token] = freq.get(token, 0) + 1
            score = 0.0
            for token in set(query_tokens):
                tf = freq.get(token, 0)
                if tf == 0 or token not in self._idf:
                    continue
                denominator = tf + self._K1 * (
                    1.0 - self._B + self._B * doc_len / max(self._avg_len, 1e-9)
                )
                score += self._idf[token] * (tf * (self._K1 + 1.0)) / denominator
            scores[chunk.chunk_id] = score
        return scores

    def _hybrid_rank(
        self,
        query: str,
        candidates: list[KnowledgeChunk],
        bm25_scores: dict[str, float],
        pool_size: int,
    ) -> list[ScoredChunk]:
        """Union of BM25-top and semantic-top candidates for downstream rerank.

        RRF fusion can drop a relevant chunk that ranks mid-list in both
        signals; taking the union of both top-N lists maximizes recall of the
        reranker pool (precision is delegated to the cross-encoder).
        """
        query_vec = self._embedder.encode([query], is_query=True)[0]
        chunk_index = {chunk.chunk_id: i for i, chunk in enumerate(self._chunks)}
        semantic_scores: dict[str, float] = {}
        for chunk in candidates:
            vec = self._chunk_embeddings[chunk_index[chunk.chunk_id]]
            semantic_scores[chunk.chunk_id] = sum(
                a * b for a, b in zip(query_vec, vec)
            )

        bm25_top = sorted(
            bm25_scores, key=bm25_scores.get, reverse=True
        )[:pool_size]
        sem_top = sorted(
            semantic_scores, key=semantic_scores.get, reverse=True
        )[:pool_size]
        union_ids = list(dict.fromkeys([*bm25_top, *sem_top]))
        chunk_by_id = {chunk.chunk_id: chunk for chunk in self._chunks}
        pool = [
            ScoredChunk(
                chunk=chunk_by_id[chunk_id],
                score=bm25_scores.get(chunk_id, 0.0),
            )
            for chunk_id in union_ids
            if chunk_id in chunk_by_id
        ]
        return pool

    def _filtered_chunks(
        self, namespace_filter: dict[str, Any] | None
    ) -> list[KnowledgeChunk]:
        if not namespace_filter:
            return self._chunks

        def matches(chunk: KnowledgeChunk) -> bool:
            ns = chunk.namespace
            for key, value in namespace_filter.items():
                # namespace 是偶数长度 key-value 对
                pairs = {
                    ns[i]: ns[i + 1] for i in range(0, len(ns) - 1, 2)
                }
                if pairs.get(key) != value:
                    return False
            return True

        return [chunk for chunk in self._chunks if matches(chunk)]
