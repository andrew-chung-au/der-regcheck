"""Database schema initialisation for the DER RegCheck RAG corpus.


Initialises:
- chunks: evidence chunks, metadata, and weighted PostgreSQL full-text vectors
- chunk_embeddings: pgvector embeddings for cosine similarity search
- query_cache: configuration-aware cache of question → answer
- manual_scores: human evaluation scores linked to cached answers
- answer_feedback: thumbs up/down feedback linked to cached answers


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



def init_observability_schema() -> None:
    """
    Initialise or upgrade the observability schema for DER RegCheck.


    Creates:
    - query_cache: configuration-aware cache of question → answer.
    - manual_scores: human evaluation scores linked to cached answers.
    - answer_feedback: thumbs up/down feedback linked to cached answers.


    These tables support:
    - Reuse of previously generated answers (performance + cost).
    - Stable answer snapshots for Tier 2 manual evaluation.
    - Future monitoring and analytics in the Streamlit app.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Ensure uuid extension
            cur.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\"")


            # query_cache table
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS query_cache (
                    cache_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    question_text TEXT NOT NULL,
                    config_hash TEXT NOT NULL,
                    answer_status TEXT NOT NULL,
                    direct_answer TEXT NOT NULL,
                    claims JSONB NOT NULL,
                    uncertainty_statement TEXT NOT NULL,
                    clarifying_question TEXT,
                    evidence_gaps JSONB NOT NULL,
                    research_next_steps JSONB NOT NULL,
                    evidence_snapshot JSONB NOT NULL,
                    latency_ms INTEGER NOT NULL,
                    UNIQUE (question_text, config_hash)
                )
                """
            )


            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_query_cache_config
                ON query_cache (config_hash)
                """
            )


            # manual_scores table
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS manual_scores (
                    score_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    cache_id UUID NOT NULL REFERENCES query_cache(cache_id),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    question_id TEXT,
                    is_tier2 BOOLEAN NOT NULL DEFAULT FALSE,
                    groundedness INTEGER CHECK (groundedness BETWEEN 1 AND 5),
                    relevance INTEGER CHECK (relevance BETWEEN 1 AND 5),
                    completeness INTEGER CHECK (completeness BETWEEN 1 AND 5),
                    citation_quality INTEGER CHECK (citation_quality BETWEEN 1 AND 5),
                    appropriate_uncertainty INTEGER CHECK (appropriate_uncertainty BETWEEN 1 AND 5),
                    notes TEXT
                )
                """
            )


            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_manual_scores_cache
                ON manual_scores (cache_id)
                """
            )


            # answer_feedback table
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS answer_feedback (
                    feedback_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    cache_id UUID NOT NULL REFERENCES query_cache(cache_id),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    rating TEXT NOT NULL CHECK (rating IN ('helpful', 'not_helpful')),
                    comment TEXT
                )
                """
            )


            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_answer_feedback_cache
                ON answer_feedback (cache_id)
                """
            )


        conn.commit()


    print("Observability schema initialised (query_cache, manual_scores, answer_feedback)")



if __name__ == "__main__":
    # For one-off local initialisation:
    #   uv run python -m src.database.db_init
    # will now initialise both RAG and observability schemas.
    init_schema()
    init_observability_schema()
    print("Full schema (RAG + observability) initialisation complete")