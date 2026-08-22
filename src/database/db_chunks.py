"""Database operations for RAG chunks and embeddings."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from psycopg2.extras import execute_values, Json, RealDictCursor
from src.database.db_connection import get_connection


def load_chunks_from_json(chunks_dir: Path) -> list[dict[str, Any]]:
    """Load all chunks from JSON files for database import."""
    all_chunks: list[dict[str, Any]] = []

    for path in sorted(chunks_dir.glob("*.json")):
        if path.name in {"chunk_manifest.json", "chunk_quality_report.json"}:
            continue

        document = json.loads(path.read_text(encoding="utf-8"))
        all_chunks.extend(document["chunks"])

    return all_chunks


def load_embeddings_from_jsonl(embeddings_dir: Path) -> dict[str, list[float]]:
    """Load all embeddings from JSONL files for database import."""
    all_embeddings: dict[str, list[float]] = {}

    for path in sorted(embeddings_dir.glob("*.jsonl")):
        with path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    record = json.loads(line)
                    all_embeddings[record["chunk_id"]] = record["embedding"]

    return all_embeddings


def insert_chunks(chunks: list[dict[str, Any]]) -> None:
    """Insert multiple chunks into database."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            values = [
                (
                    chunk["chunk_id"],
                    chunk["document_id"],
                    chunk["source_id"],
                    chunk["chunk_ordinal"],
                    chunk["heading_path"],
                    chunk["evidence_text"],
                    chunk["embedding_text"],
                    Json(chunk["citation"]),
                    Json(chunk["source_policy"]),
                    chunk["block_ids"],
                    chunk["block_types"],
                    chunk["estimated_evidence_tokens"],
                )
                for chunk in chunks
            ]

            execute_values(
                cur,
                """
                INSERT INTO chunks (
                    chunk_id, document_id, source_id, chunk_ordinal,
                    heading_path, evidence_text, embedding_text,
                    citation, source_policy, block_ids, block_types,
                    estimated_tokens
                ) VALUES %s
                ON CONFLICT (chunk_id) DO NOTHING
                """,
                values,
            )
            conn.commit()

    print(f"Inserted {len(chunks)} chunks")


def insert_embeddings(embeddings: dict[str, list[float]], model_id: str = "nomic-ai/nomic-embed-text-v1.5") -> None:
    """Insert multiple embeddings into database."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            values = [
                (chunk_id, embedding, model_id)
                for chunk_id, embedding in embeddings.items()
            ]

            execute_values(
                cur,
                """
                INSERT INTO chunk_embeddings (chunk_id, embedding, model_id)
                VALUES %s
                ON CONFLICT (chunk_id) DO NOTHING
                """,
                values,
            )
            conn.commit()

    print(f"Inserted {len(embeddings)} embeddings")


def search_chunks(
    query_embedding: list[float],
    top_k: int = 10,
    source_filter: str | None = None,
) -> list[dict[str, Any]]:
    """
    Search for similar chunks using vector similarity.
    
    Args:
        query_embedding: 768-dimensional query vector
        top_k: Number of results to return
        source_filter: Optional source_id filter (e.g., "sce_rule21_tariff_pdf")
    
    Returns:
        List of chunks with similarity scores
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if source_filter:
                cur.execute("""
                    SELECT 
                        c.*,
                        e.embedding,
                        1 - (e.embedding <=> %s::vector) as similarity
                    FROM chunks c
                    JOIN chunk_embeddings e ON c.chunk_id = e.chunk_id
                    WHERE c.source_id = %s
                    ORDER BY e.embedding <=> %s::vector
                    LIMIT %s
                """, (query_embedding, source_filter, query_embedding, top_k))
            else:
                cur.execute("""
                    SELECT 
                        c.*,
                        e.embedding,
                        1 - (e.embedding <=> %s::vector) as similarity
                    FROM chunks c
                    JOIN chunk_embeddings e ON c.chunk_id = e.chunk_id
                    ORDER BY e.embedding <=> %s::vector
                    LIMIT %s
                """, (query_embedding, query_embedding, top_k))

            rows = cur.fetchall()
            return [dict(row) for row in rows]


def get_chunk_by_id(chunk_id: str) -> dict[str, Any] | None:
    """Get a single chunk by ID."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT c.*, e.embedding
                FROM chunks c
                JOIN chunk_embeddings e ON c.chunk_id = e.chunk_id
                WHERE c.chunk_id = %s
            """, (chunk_id,))
            row = cur.fetchone()
            return dict(row) if row else None


def get_chunk_count() -> int:
    """Get total number of chunks in database."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM chunks")
            return cur.fetchone()[0]


def get_embedding_count() -> int:
    """Get total number of embeddings in database."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM chunk_embeddings")
            return cur.fetchone()[0]