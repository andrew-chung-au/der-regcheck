"""Selected production retrieval flow for DER RegCheck.

This module provides the reusable retrieval primitive for the selected
v3 configuration:

    Expanded query
    → pgvector vector retrieval
    → BAAI/bge-reranker-base reranking
    → top 10 evidence chunks

Both the live application and the evaluation runner should use this
function rather than duplicating retrieval logic.
"""
from __future__ import annotations

from typing import Any

from src.database.db_connection import get_connection
from src.retrieval.rerank import Reranker
from src.retrieval.retrieve import Retriever


def retrieve_vector_reranked(
    *,
    query_text: str,
    query_embedding: list[float],
    reranker: Reranker,
    candidate_limit: int,
    final_k: int,
    rerank_max_tokens: int,
    rerank_batch_size: int,
) -> list[dict[str, Any]]:
    """Retrieve pgvector candidates and rerank with the selected cross-encoder.

    Args:
        query_text: The query string used for reranking (typically expanded).
        query_embedding: 768-dimensional Nomic embedding of the query.
        reranker: Initialized BAAI/bge-reranker-base cross-encoder.
        candidate_limit: Number of vector candidates to retrieve (typically 50).
        final_k: Number of final reranked chunks to return (typically 10).
        rerank_max_tokens: Maximum tokens per document for reranker input.
        rerank_batch_size: Batch size for cross-encoder inference.

    Returns:
        List of reranked chunk dictionaries, each containing at least:
        - chunk_id, document_id, source_id, heading_path
        - evidence_text, citation, source_policy
        - reranker_score
    """
    with get_connection() as conn:
        database_retriever = Retriever(conn)
        vector_candidates = database_retriever.search_vector(
            query_embedding=query_embedding,
            top_k=candidate_limit,
        )

    return reranker.rerank(
        query=query_text,
        chunks=vector_candidates,
        top_k=final_k,
        candidate_limit=candidate_limit,
        max_tokens=rerank_max_tokens,
        batch_size=rerank_batch_size,
    )