"""Unit tests for evaluation-result aggregation."""
from __future__ import annotations

import unittest

from src.evaluation.summarise_evaluation import (
    add_rankings,
    build_summary,
)


class SummariseEvaluationTests(unittest.TestCase):
    def test_summary_keeps_alpha_configurations_separate(self) -> None:
        results = [
            {
                "query_id": "q1",
                "retriever": "hybrid",
                "weighting": "equal",
                "alpha": 0.3,
                "ndcg_at_10": 0.6,
                "mrr": 0.5,
                "recall_at_10": 0.7,
            },
            {
                "query_id": "q1",
                "retriever": "hybrid",
                "weighting": "equal",
                "alpha": 0.7,
                "ndcg_at_10": 0.8,
                "mrr": 1.0,
                "recall_at_10": 0.9,
            },
        ]

        summary = build_summary(results)

        self.assertEqual(len(summary["per_configuration"]), 2)

        keys = set(summary["per_configuration"])

        self.assertTrue(
            any("alpha=0.30" in key for key in keys)
        )
        self.assertTrue(
            any("alpha=0.70" in key for key in keys)
        )

    def test_summary_uses_distinct_query_ids_not_record_estimation(self) -> None:
        results = [
            {
                "query_id": "q1",
                "retriever": "vector",
                "weighting": "equal",
                "alpha": 0.5,
                "ndcg_at_10": 1.0,
                "mrr": 1.0,
                "recall_at_10": 1.0,
            },
            {
                "query_id": "q1",
                "retriever": "vector",
                "weighting": "source_heavy",
                "alpha": 0.5,
                "ndcg_at_10": 0.8,
                "mrr": 1.0,
                "recall_at_10": 0.8,
            },
            {
                "query_id": "q2",
                "retriever": "vector",
                "weighting": "equal",
                "alpha": 0.5,
                "ndcg_at_10": 0.6,
                "mrr": 0.5,
                "recall_at_10": 0.4,
            },
        ]

        summary = build_summary(results)

        self.assertEqual(summary["total_unique_queries"], 2)
        self.assertEqual(summary["total_records"], 3)

    def test_recommendation_uses_documented_composite_score(self) -> None:
        results = [
            {
                "query_id": "q1",
                "retriever": "vector",
                "weighting": "equal",
                "alpha": 0.5,
                "ndcg_at_10": 0.6,
                "mrr": 0.6,
                "recall_at_10": 0.6,
            },
            {
                "query_id": "q1",
                "retriever": "hybrid",
                "weighting": "equal",
                "alpha": 0.5,
                "ndcg_at_10": 0.8,
                "mrr": 0.7,
                "recall_at_10": 0.7,
            },
        ]

        summary = build_summary(results)
        add_rankings(summary)

        recommendation = summary["recommended_configuration"]

        self.assertIsNotNone(recommendation)
        self.assertIn("retriever=hybrid", recommendation["configuration"])
        self.assertAlmostEqual(
            recommendation["composite_score"],
            0.5 * 0.8 + 0.3 * 0.7 + 0.2 * 0.7,
        )


if __name__ == "__main__":
    unittest.main()