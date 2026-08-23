"""Cross-encoder reranking for retrieved chunks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sentence_transformers import CrossEncoder

if TYPE_CHECKING:
    from psycopg2.extensions import connection


class Reranker:
    """Cross-encoder reranker for production-like two-stage retrieval."""

    def __init__(self, model_name: str = "BAAI/bge-reranker-base") -> None:
        """Initialize the cross-encoder reranker.

        Args:
            model_name: HuggingFace model name for cross-encoder.
        """
        self.model = CrossEncoder(model_name)
        self.model_name = model_name

    def rerank(
        self,
        query: str,
        chunks: list[dict],
        top_k: int = 10,
        candidate_limit: int = 50,
        max_tokens: int = 450,
    ) -> list[dict]:
        """Rerank retrieved chunks using cross-encoder.

        Args:
            query: User query string.
            chunks: List of retrieved chunks with metadata.
            top_k: Number of chunks to return after reranking.
            candidate_limit: Number of candidates to rerank from initial retrieval.
            max_tokens: Maximum tokens to use from each chunk for reranking.

        Returns:
            List of chunks sorted by reranker score, limited to top_k.
        """
        # Limit candidates for reranking (performance)
        candidates = chunks[:candidate_limit]

        # Prepare query-document pairs for cross-encoder
        # Use embedding_text (has heading context) or truncate evidence_text
        pairs = []
        for chunk in candidates:
            # Prefer embedding_text as it has heading context prepended
            doc_text = chunk.get("embedding_text", chunk.get("evidence_text", ""))
            # Truncate to fit model token limit (leave room for query)
            doc_text = doc_text[:max_tokens]
            pairs.append((query, doc_text))

        # Compute reranker scores
        scores = self.model.compute_score(pairs)

        # Sort by score (descending)
        ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)

        # Return top_k chunks with scores
        return [
            {**chunk, "reranker_score": score}
            for chunk, score in ranked[:top_k]
        ]

    def rerank_from_db(
        self,
        query: str,
        conn: connection,
        top_k: int = 10,
        candidate_limit: int = 50,
    ) -> list[dict]:
        """Rerank results from database retrieval.

        Args:
            query: User query string.
            conn: PostgreSQL database connection.
            top_k: Number of chunks to return after reranking.
            candidate_limit: Number of candidates to retrieve and rerank.

        Returns:
            List of chunks sorted by reranker score.
        """
        from src.retrieval.retrieve import Retriever

        # First-stage retrieval (vector search)
        retriever = Retriever(conn)
        candidates = retriever.search(query, top_k=candidate_limit)

        # Second-stage reranking
        return self.rerank(query, candidates, top_k=top_k)