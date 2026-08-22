"""Database schema initialisation for RAG corpus.

Initialises tables for:
- chunks: RAG corpus with metadata
- chunk_embeddings: pgvector embeddings for similarity search

Evaluation queries are file-based (data/evaluation/queries.jsonl) for reproducibility.
"""
from __future__ import annotations

from src.database.db_connection import get_connection


def init_schema() -> None:
    """Initialise database schema for RAG corpus."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Enable pgvector extension
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")

            # Chunks table (RAG corpus)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chunks (
                    chunk_id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    chunk_ordinal INTEGER NOT NULL,
                    heading_path TEXT[] NOT NULL,
                    evidence_text TEXT NOT NULL,
                    embedding_text TEXT NOT NULL,
                    citation JSONB NOT NULL,
                    source_policy JSONB NOT NULL,
                    block_ids TEXT[] NOT NULL,
                    block_types TEXT[] NOT NULL,
                    estimated_tokens INTEGER NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)

            # Embeddings table with pgvector
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chunk_embeddings (
                    chunk_id TEXT PRIMARY KEY REFERENCES chunks(chunk_id),
                    embedding vector(768) NOT NULL,
                    model_id TEXT NOT NULL,
                    embedded_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)

            # Index for vector similarity search
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_vector
                ON chunk_embeddings USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100)
            """)

            # Indexes for metadata filtering
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_chunks_source
                ON chunks(source_id)
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_chunks_document
                ON chunks(document_id)
            """)

            conn.commit()

    print("Database schema initialised (chunks + embeddings)")


if __name__ == "__main__":
    init_schema()
    print("Schema initialisation complete")