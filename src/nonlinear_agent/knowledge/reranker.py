"""Local cross-encoder reranker for precise knowledge retrieval (v3.6.1)."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from nonlinear_agent.knowledge.ingest import KnowledgeChunk


@runtime_checkable
class Reranker(Protocol):
    def rerank(
        self, query: str, candidates: list[Any], top_k: int = 3
    ) -> list[Any]: ...


class LocalCrossEncoderReranker:
    """Cross-encoder relevance scoring from a locally-cached model."""

    DEFAULT_MODEL = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        max_length: int = 256,
        batch_size: int = 16,
    ):
        try:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except ImportError as exc:
            raise ImportError(
                "LocalCrossEncoderReranker requires transformers."
            ) from exc
        try:
            self._tokenizer = AutoTokenizer.from_pretrained(
                model_name, local_files_only=True
            )
            self._model = AutoModelForSequenceClassification.from_pretrained(
                model_name, local_files_only=True
            )
        except Exception as exc:
            raise RuntimeError(
                f"Failed to load local reranker '{model_name}'. "
                "Use a retriever without a reranker to skip reranking."
            ) from exc
        self._max_length = max_length
        self._batch_size = max(1, batch_size)
        self._model.eval()

    def rerank(
        self, query: str, candidates: list[Any], top_k: int = 3
    ) -> list[Any]:
        import torch

        from nonlinear_agent.knowledge.retriever import ScoredChunk

        if not candidates:
            return []
        scored: list[ScoredChunk] = []
        for start in range(0, len(candidates), self._batch_size):
            batch = candidates[start : start + self._batch_size]
            pairs = [
                (query, item.chunk.text[: self._max_length * 2])
                for item in batch
            ]
            inputs = self._tokenizer(
                pairs,
                padding=True,
                truncation=True,
                max_length=self._max_length,
                return_tensors="pt",
            )
            with torch.no_grad():
                logits = self._model(**inputs).logits
            for item, logit in zip(batch, logits[:, 0].tolist()):
                scored.append(
                    ScoredChunk(chunk=item.chunk, score=float(logit))
                )
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:top_k]
