"""Cross-encoder reranking for retrieved DER RegCheck chunks."""
from __future__ import annotations

from typing import Any

from sentence_transformers import CrossEncoder


class Reranker:
    """Cross-encoder reranker for two-stage retrieval."""

    def __init__(self, model_name: str = "BAAI/bge-reranker-base") -> None:
        """Load the cross-encoder model once."""
        self.model_name = model_name
        self.model = CrossEncoder(model_name)

    def rerank(
        self,
        query: str,
        chunks: list[dict[str, Any]],
        top_k: int = 10,
        candidate_limit: int = 50,
        max_tokens: int = 450,
        batch_size: int = 16,
    ) -> list[dict[str, Any]]:
        """Rerank first-stage candidates against the user query."""
        if not query.strip():
            raise ValueError("query must not be empty.")

        if top_k <= 0:
            raise ValueError("top_k must be positive.")

        if candidate_limit <= 0:
            raise ValueError("candidate_limit must be positive.")

        if max_tokens <= 0:
            raise ValueError("max_tokens must be positive.")

        if batch_size <= 0:
            raise ValueError("batch_size must be positive.")

        candidates = chunks[:candidate_limit]

        pairs: list[tuple[str, str]] = []

        for chunk in candidates:
            document_text = chunk.get(
                "embedding_text",
                chunk.get("evidence_text", ""),
            )
            pairs.append((query, document_text[:max_tokens]))

        if not pairs:
            return []

        scores = self.model.predict(
            pairs,
            batch_size=batch_size,
            show_progress_bar=False,
        )

        ranked = sorted(
            zip(candidates, scores, strict=True),
            key=lambda item: float(item[1]),
            reverse=True,
        )

        return [
            {
                **chunk,
                "reranker_score": float(score),
            }
            for chunk, score in ranked[:top_k]
        ]