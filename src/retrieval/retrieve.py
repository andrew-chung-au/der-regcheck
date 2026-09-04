"""Database-backed lexical, vector, and hybrid retrieval for DER RegCheck."""
from __future__ import annotations

from typing import Any

from psycopg2.extensions import connection
from psycopg2.extras import RealDictCursor


RRF_OFFSET = 1


class Retriever:
    """Retrieve chunk candidates from PostgreSQL full-text search and pgvector."""

    def __init__(self, conn: connection) -> None:
        self.conn = conn

    def search_lexical(
        self,
        query: str,
        top_k: int = 50,
    ) -> list[dict[str, Any]]:
        """Retrieve candidates using weighted PostgreSQL full-text search."""
        if not query.strip():
            raise ValueError("query must not be empty.")

        if top_k <= 0:
            raise ValueError("top_k must be positive.")

        sql = """
            WITH query_terms AS (
                SELECT websearch_to_tsquery('english', %(query)s) AS tsquery
            )
            SELECT
                c.chunk_id,
                c.document_id,
                c.source_id,
                c.chunk_ordinal,
                c.heading_path,
                c.evidence_text,
                c.embedding_text,
                c.citation,
                c.source_policy,
                c.block_ids,
                c.block_types,
                c.estimated_tokens,
                ts_rank_cd(c.search_vector, query_terms.tsquery, 32)
                    AS lexical_score
            FROM chunks AS c
            CROSS JOIN query_terms
            WHERE c.search_vector @@ query_terms.tsquery
            ORDER BY lexical_score DESC, c.chunk_id ASC
            LIMIT %(top_k)s
        """

        with self.conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(sql, {"query": query, "top_k": top_k})
            rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def search_vector(
        self,
        query_embedding: list[float],
        top_k: int = 50,
    ) -> list[dict[str, Any]]:
        """Retrieve candidates using pgvector cosine-distance search."""
        if len(query_embedding) != 768:
            raise ValueError(
                "query_embedding must contain exactly 768 values; "
                f"received {len(query_embedding)}."
            )

        if top_k <= 0:
            raise ValueError("top_k must be positive.")

        sql = """
            SELECT
                c.chunk_id,
                c.document_id,
                c.source_id,
                c.chunk_ordinal,
                c.heading_path,
                c.evidence_text,
                c.embedding_text,
                c.citation,
                c.source_policy,
                c.block_ids,
                c.block_types,
                c.estimated_tokens,
                1 - (ce.embedding <=> %(query_embedding)s::vector)
                    AS vector_similarity
            FROM chunk_embeddings AS ce
            INNER JOIN chunks AS c
                ON c.chunk_id = ce.chunk_id
            ORDER BY
                ce.embedding <=> %(query_embedding)s::vector ASC,
                c.chunk_id ASC
            LIMIT %(top_k)s
        """

        vector_literal = "[" + ",".join(
            f"{value:.10f}" for value in query_embedding
        ) + "]"

        with self.conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                sql,
                {
                    "query_embedding": vector_literal,
                    "top_k": top_k,
                },
            )
            rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def search_hybrid(
        self,
        query: str,
        query_embedding: list[float],
        top_k: int = 50,
        alpha: float = 0.5,
        rrf_offset: int = RRF_OFFSET,
    ) -> list[dict[str, Any]]:
        """Fuse lexical and vector rankings with weighted RRF.

        Alpha is the lexical-search weight:
        - 0.0 uses only vector rank.
        - 1.0 uses only lexical rank.
        """
        if not 0.0 <= alpha <= 1.0:
            raise ValueError("alpha must be between 0.0 and 1.0.")

        if top_k <= 0:
            raise ValueError("top_k must be positive.")

        if rrf_offset < 0:
            raise ValueError("rrf_offset must be zero or greater.")

        lexical_results = self.search_lexical(query, top_k=top_k)
        vector_results = self.search_vector(
            query_embedding,
            top_k=top_k,
        )

        lexical_ranks = {
            result["chunk_id"]: rank
            for rank, result in enumerate(lexical_results, start=1)
        }

        vector_ranks = {
            result["chunk_id"]: rank
            for rank, result in enumerate(vector_results, start=1)
        }

        chunks_by_id: dict[str, dict[str, Any]] = {
            result["chunk_id"]: result
            for result in lexical_results + vector_results
        }

        fused_results: list[dict[str, Any]] = []

        for chunk_id in lexical_ranks.keys() | vector_ranks.keys():
            lexical_rank = lexical_ranks.get(chunk_id)
            vector_rank = vector_ranks.get(chunk_id)

            lexical_component = (
                alpha / (lexical_rank + rrf_offset)
                if lexical_rank is not None
                else 0.0
            )

            vector_component = (
                (1.0 - alpha) / (vector_rank + rrf_offset)
                if vector_rank is not None
                else 0.0
            )

            chunk = {
                **chunks_by_id[chunk_id],
                "lexical_rank": lexical_rank,
                "vector_rank": vector_rank,
                "rrf_score": lexical_component + vector_component,
            }

            fused_results.append(chunk)

        fused_results.sort(
            key=lambda chunk: (
                -float(chunk["rrf_score"]),
                str(chunk["chunk_id"]),
            )
        )

        return fused_results[:top_k]