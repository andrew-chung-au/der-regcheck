from __future__ import annotations

import os
import unittest

import psycopg2

from src.database.db_init import init_schema


@unittest.skipUnless(
    os.getenv("DATABASE_URL"),
    "DATABASE_URL is required for database schema integration tests.",
)
class DatabaseSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        init_schema()

    def test_chunks_has_trigger_managed_full_text_search_column(self) -> None:
        connection = psycopg2.connect(os.environ["DATABASE_URL"])

        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        column_name,
                        data_type,
                        is_generated
                    FROM information_schema.columns
                    WHERE table_name = 'chunks'
                      AND column_name = 'search_vector'
                    """
                )
                row = cursor.fetchone()
        finally:
            connection.close()

        self.assertIsNotNone(row)
        self.assertEqual(row[0], "search_vector")
        self.assertEqual(row[1], "tsvector")
        self.assertEqual(row[2], "NEVER")

    def test_chunks_has_gin_full_text_search_index(self) -> None:
        connection = psycopg2.connect(os.environ["DATABASE_URL"])

        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT indexdef
                    FROM pg_indexes
                    WHERE schemaname = 'public'
                      AND tablename = 'chunks'
                      AND indexname = 'idx_chunks_search_vector'
                    """
                )
                row = cursor.fetchone()
        finally:
            connection.close()

        self.assertIsNotNone(row)
        self.assertIn("using gin", row[0].lower())
        self.assertIn("search_vector", row[0])

    def test_chunks_has_search_vector_trigger(self) -> None:
        connection = psycopg2.connect(os.environ["DATABASE_URL"])

        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT tgname
                    FROM pg_trigger
                    WHERE tgrelid = 'chunks'::regclass
                      AND tgname = 'trg_chunks_search_vector'
                      AND NOT tgisinternal
                    """
                )
                row = cursor.fetchone()
        finally:
            connection.close()

        self.assertIsNotNone(row)
        self.assertEqual(row[0], "trg_chunks_search_vector")

    def test_trigger_assigns_heading_and_evidence_weights(self) -> None:
        connection = psycopg2.connect(os.environ["DATABASE_URL"])

        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO chunks (
                        chunk_id,
                        document_id,
                        source_id,
                        chunk_ordinal,
                        heading_path,
                        evidence_text,
                        embedding_text,
                        citation,
                        source_policy,
                        block_ids,
                        block_types,
                        estimated_tokens
                    )
                    VALUES (
                        'test:search-vector-weights',
                        'test-document',
                        'test-source',
                        1,
                        ARRAY['HeadingOnlyToken'],
                        'EvidenceOnlyToken',
                        'HeadingOnlyToken EvidenceOnlyToken',
                        '{}'::jsonb,
                        '{}'::jsonb,
                        ARRAY['test:block:1'],
                        ARRAY['paragraph'],
                        3
                    )
                    RETURNING search_vector::text
                    """
                )
                row = cursor.fetchone()
                connection.rollback()
        finally:
            connection.close()

        self.assertIsNotNone(row)
        search_vector = row[0]

        self.assertIn("'headingonlytoken':1A", search_vector)
        self.assertIn("'evidenceonlytoken':2B", search_vector)


if __name__ == "__main__":
    unittest.main()