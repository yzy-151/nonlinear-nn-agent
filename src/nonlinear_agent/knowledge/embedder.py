"""Local transformer embedder for hybrid retrieval (v3.6.1).

Uses HuggingFace ``transformers`` directly (already a project dependency via
torch ecosystem) with a locally-cached multilingual MiniLM model, so no
external ML service or additional vector-store dependency is required.
Loading fails loudly when the model is not cached locally.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Embedder(Protocol):
    def encode(self, texts: list[str]) -> "list[list[float]]": ...

    def dimension(self) -> int: ...


class LocalTransformerEmbedder:
    """Mean-pooled, L2-normalized embeddings from a local transformers model."""

    DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        max_length: int = 512,
        batch_size: int = 32,
        query_instruction: str = "为这个句子生成表示以用于检索相关文章：",
    ):
        try:
            from transformers import AutoModel, AutoTokenizer
        except ImportError as exc:
            raise ImportError(
                "LocalTransformerEmbedder requires transformers (pip install transformers)."
            ) from exc
        self._model_name = model_name
        self._max_length = max_length
        self._batch_size = max(1, batch_size)
        self._query_instruction = query_instruction
        try:
            self._tokenizer = AutoTokenizer.from_pretrained(
                model_name, local_files_only=True
            )
            self._model = AutoModel.from_pretrained(
                model_name, local_files_only=True
            )
        except Exception as exc:
            raise RuntimeError(
                f"Failed to load local embedding model '{model_name}'. "
                "Download it once (e.g. via huggingface_hub) or use a "
                "KnowledgeRetriever without an embedder (BM25-only)."
            ) from exc
        self._model.eval()

    def dimension(self) -> int:
        return int(self._model.config.hidden_size)

    def encode(
        self, texts: list[str], is_query: bool = False
    ) -> list[list[float]]:
        import torch

        if is_query and self._query_instruction:
            texts = [self._query_instruction + text for text in texts]
        all_embeddings: list[list[float]] = []
        for start in range(0, len(texts), self._batch_size):
            batch = texts[start : start + self._batch_size]
            inputs = self._tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=self._max_length,
                return_tensors="pt",
            )
            with torch.no_grad():
                outputs = self._model(**inputs)
            mask = inputs["attention_mask"].unsqueeze(-1).float()
            summed = (outputs.last_hidden_state * mask).sum(dim=1)
            lengths = mask.sum(dim=1).clamp(min=1e-9)
            embeddings = torch.nn.functional.normalize(
                summed / lengths, p=2, dim=1
            )
            all_embeddings.extend(embeddings.tolist())
        return all_embeddings
