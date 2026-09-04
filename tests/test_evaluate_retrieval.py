"""Unit tests for PostgreSQL retrieval evaluation metrics."""
from __future__ import annotations

import unittest

from src.evaluation.evaluate_retrieval import (
    compute_metadata_score,
    mrr,
    ndcg_at_k,
    recall_at_k,
)


class RetrievalEvaluationMetricTests(unittest.TestCase):
    def test_metadata_score_is_one_for_exact_metadata_match(self) -> None:
        weights = {
            "source": 0.20,
            "section": 0.20,
            "page": 0.20,
            "block_type": 0.20,
            "authority": 0.20,
        }

        chunk = {
            "source_id": "sce_rule21_tariff_pdf",
            "citation": {
                "section_ids": ["H", "2", "w"],
                "pdf_page_start": 174,
            },
            "block_types": ["paragraph"],
            "source_policy": {
                "authority_tier": "primary_governing",
            },
        }

        score = compute_metadata_score(
            retrieved=chunk,
            gold=chunk,
            weights=weights,
        )

        self.assertEqual(score, 1.0)

    def test_ndcg_is_one_for_ideal_ranking(self) -> None:
        self.assertEqual(
            ndcg_at_k([1.0, 0.8, 0.4], k=10),
            1.0,
        )

    def test_mrr_uses_first_relevant_result(self) -> None:
        self.assertEqual(
            mrr([0.0, 0.0, 1.0, 1.0]),
            1 / 3,
        )

    def test_recall_uses_corpus_relevant_total(self) -> None:
        self.assertEqual(
            recall_at_k(
                relevances=[1.0, 0.0, 1.0],
                k=10,
                total_relevant=4,
            ),
            0.5,
        )

    def test_recall_is_zero_without_relevant_corpus_chunks(self) -> None:
        self.assertEqual(
            recall_at_k(
                relevances=[1.0],
                k=10,
                total_relevant=0,
            ),
            0.0,
        )


if __name__ == "__main__":
    unittest.main()