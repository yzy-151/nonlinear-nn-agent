"""Top-k knowledge retrieval with citation, no external ML dependencies.

Uses a pure-Python BM25 over word tokens + character bigrams, so offline
tests and the Web inspector work without installing vector-search packages.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any

from nonlinear_agent.knowledge.ingest import KnowledgeChunk


@dataclass(frozen=True)
class ScoredChunk:
    chunk: KnowledgeChunk
    score: float


class KnowledgeRetriever:
    """BM25 retrieval over an in-memory chunk corpus."""

    _K1 = 1.5
    _B = 0.75
    _WORD = re.compile(r"[a-z0-9]+")

    def __init__(self, chunks: list[KnowledgeChunk]):
        self._chunks = chunks
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

    @staticmethod
    def _tokens(text: str) -> list[str]:
        lower = text.lower()
        words = KnowledgeRetriever._WORD.findall(lower)
        tokens = list(words)
        tokens += [w for w in words if len(w) > 2]
        # 单词 bigram 保留短语结构；字符 bigram 噪声太大已移除
        tokens += [f"{words[i]}_{words[i + 1]}" for i in range(max(0, len(words) - 1))]
        return tokens

    def retrieve(
        self,
        query: str,
        top_k: int = 3,
        namespace_filter: dict[str, Any] | None = None,
    ) -> list[ScoredChunk]:
        query_tokens = self._tokens(query)
        if not query_tokens:
            return []
        candidates = self._filtered_chunks(namespace_filter)
        scored: list[ScoredChunk] = []
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
            if score > 0:
                scored.append(ScoredChunk(chunk=chunk, score=score))
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:top_k]

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
