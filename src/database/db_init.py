"""Database schema initialisation for the DER RegCheck RAG corpus.

Initialises:
- chunks: evidence chunks, metadata, and weighted PostgreSQL full-text vectors
- chunk_embeddings: pgvector embeddings for cosine similarity search

Evaluation queries remain file-based under data/evaluation for reproducibility.
"""
from __future__ import annotations

from src.database.db_connection import get_connection


def init_schema() -> None:
    """Initialise or upgrade the RAG corpus schema."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")

            cur.execute(
                """
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
                """
            )

            cur.execute(
                """
                DROP INDEX IF EXISTS idx_chunks_search_vector
                """
            )

            cur.execute(
                """
                ALTER TABLE chunks
                DROP COLUMN IF EXISTS search_vector
                """
            )

            cur.execute(
                """
                ALTER TABLE chunks
                ADD COLUMN search_vector tsvector NOT NULL DEFAULT ''::tsvector
                """
            )

            cur.execute(
                """
                CREATE OR REPLACE FUNCTION update_chunks_search_vector()
                RETURNS trigger
                AS $$
                BEGIN
                    NEW.search_vector :=
                        setweight(
                            to_tsvector(
                                'pg_catalog.english',
                                coalesce(array_to_string(NEW.heading_path, ' '), '')
                            ),
                            'A'
                        )
                        ||
                        setweight(
                            to_tsvector(
                                'pg_catalog.english',
                                coalesce(NEW.evidence_text, '')
                            ),
                            'B'
                        );

                    RETURN NEW;
                END;
                $$
                LANGUAGE plpgsql
                """
            )

            cur.execute(
                """
                DROP TRIGGER IF EXISTS trg_chunks_search_vector
                ON chunks
                """
            )

            cur.execute(
                """
                CREATE TRIGGER trg_chunks_search_vector
                BEFORE INSERT OR UPDATE OF heading_path, evidence_text
                ON chunks
                FOR EACH ROW
                EXECUTE FUNCTION update_chunks_search_vector()
                """
            )

            cur.execute(
                """
                UPDATE chunks
                SET heading_path = heading_path
                """
            )

            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chunks_search_vector
                ON chunks
                USING GIN (search_vector)
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS chunk_embeddings (
                    chunk_id TEXT PRIMARY KEY REFERENCES chunks(chunk_id),
                    embedding vector(768) NOT NULL,
                    model_id TEXT NOT NULL,
                    embedded_at TIMESTAMPTZ DEFAULT NOW()
                )
                """
            )

            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_vector
                ON chunk_embeddings
                USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100)
                """
            )

            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chunks_source
                ON chunks(source_id)
                """
            )

            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_chunks_document
                ON chunks(document_id)
                """
            )

            cur.execute("ANALYZE chunks")
            cur.execute("ANALYZE chunk_embeddings")

        conn.commit()

    print(
        "Database schema initialised "
        "(weighted full-text search + pgvector embeddings)"
    )


if __name__ == "__main__":
    init_schema()
    print("Schema initialisation complete")