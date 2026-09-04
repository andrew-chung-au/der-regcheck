"""Integration tests for database-backed retrieval paths."""
from __future__ import annotations

import os
import unittest
from typing import Any

from src.database.db_connection import get_connection
from src.retrieval.retrieve import Retriever
from src.retrieval.runtime_retriever import get_runtime_retriever


SAMPLE_QUERY = "smart inverter reactive power"


@unittest.skipUnless(
    os.getenv("DATABASE_URL"),
    "DATABASE_URL is required for retrieval integration tests.",
)
class RetrievalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runtime_retriever = get_runtime_retriever()
        cls.query_embedding = cls.runtime_retriever.embed_query(SAMPLE_QUERY)

    @staticmethod
    def has_domain_term(chunk: dict[str, Any]) -> bool:
        """Return whether a chunk includes a reactive-power domain term."""
        heading = " ".join(chunk.get("heading_path") or []).lower()
        evidence = (chunk.get("evidence_text") or "").lower()
        terms = (
            "reactive power",
            "reactive",
            "volt/var",
            "volt-var",
            "volt var",
        )
        return any(term in heading or term in evidence for term in terms)

    def test_lexical_search_returns_domain_matches(self) -> None:
        """Lexical full-text search should return matching regulatory chunks."""
        with get_connection() as conn:
            retriever = Retriever(conn)
            results = retriever.search_lexical(
                query=SAMPLE_QUERY,
                top_k=10,
            )

        self.assertGreater(
            len(results),
            0,
            "Lexical search returned no results.",
        )

        self.assertIn("lexical_score", results[0])

        self.assertTrue(
            any(self.has_domain_term(chunk) for chunk in results),
            "Lexical results did not contain expected reactive-power terms.",
        )

    def test_vector_search_returns_requested_candidate_count(self) -> None:
        """Vector search should return the requested number of candidates."""
        target_k = 10

        with get_connection() as conn:
            retriever = Retriever(conn)
            results = retriever.search_vector(
                query_embedding=self.query_embedding,
                top_k=target_k,
            )

        self.assertEqual(
            len(results),
            target_k,
            f"Expected {target_k} vector candidates, got {len(results)}.",
        )

        self.assertIn("vector_similarity", results[0])

        self.assertTrue(
            any(self.has_domain_term(chunk) for chunk in results),
            "Vector results did not contain expected reactive-power terms.",
        )

    def test_hybrid_search_returns_rrf_trace_fields(self) -> None:
        """Hybrid retrieval should return sorted RRF results with rank traces."""
        target_k = 10

        with get_connection() as conn:
            retriever = Retriever(conn)
            results = retriever.search_hybrid(
                query=SAMPLE_QUERY,
                query_embedding=self.query_embedding,
                top_k=target_k,
                alpha=0.5,
            )

        self.assertGreater(
            len(results),
            0,
            "Hybrid search returned no results.",
        )

        self.assertLessEqual(len(results), target_k)

        for chunk in results:
            self.assertIn("rrf_score", chunk)
            self.assertIsNotNone(chunk["rrf_score"])
            self.assertGreater(float(chunk["rrf_score"]), 0.0)

            self.assertIn("lexical_rank", chunk)
            self.assertIn("vector_rank", chunk)

            self.assertTrue(
                chunk["lexical_rank"] is not None
                or chunk["vector_rank"] is not None,
                "Every hybrid candidate must come from lexical or vector retrieval.",
            )

        rrf_scores = [float(chunk["rrf_score"]) for chunk in results]

        self.assertEqual(
            rrf_scores,
            sorted(rrf_scores, reverse=True),
            "Hybrid candidates are not ordered by descending RRF score.",
        )

        self.assertTrue(
            any(self.has_domain_term(chunk) for chunk in results[:3]),
            "Top hybrid candidates did not contain reactive-power terms.",
        )

        has_lexical_only = any(
            chunk["lexical_rank"] is not None
            and chunk["vector_rank"] is None
            for chunk in results
        )

        has_vector_only = any(
            chunk["lexical_rank"] is None
            and chunk["vector_rank"] is not None
            for chunk in results
        )

        self.assertTrue(
            has_lexical_only or has_vector_only,
            "Hybrid output did not preserve a candidate unique to one channel.",
        )


if __name__ == "__main__":
    unittest.main()