"""Tests for command-line RAG demo formatting."""
from __future__ import annotations

import unittest
from io import StringIO
from unittest.mock import patch

from src.scripts.demo_rag import print_source


class DemoRagTests(unittest.TestCase):
    def test_print_source_displays_citation_label_once(self) -> None:
        source = {
            "source_id": "sce_rule21_tariff_pdf",
            "heading_path": ["H.2.w", "Constant Reactive Power Mode"],
            "citation": {
                "section_ids": ["H", "2", "w"],
                "pdf_page_start": 174,
                "tariff_rule_sheet": "174",
            },
            "source_policy": {
                "authority_tier": "primary_governing",
            },
            "reranker_score": 0.998204,
            "rrf_score": 0.25,
            "lexical_rank": None,
            "vector_rank": 1,
            "evidence_text": "The Smart Inverter shall maintain constant reactive power.",
        }

        output = StringIO()

        with patch("sys.stdout", output):
            print_source(1, source)

        rendered = output.getvalue()

        self.assertIn("[S1] sce_rule21_tariff_pdf", rendered)
        self.assertNotIn("[S1] [S1]", rendered)
        self.assertIn("Reranker score: 0.998204", rendered)
        self.assertIn("Vector rank: 1", rendered)


if __name__ == "__main__":
    unittest.main()