from __future__ import annotations

import json
import unittest
from pathlib import Path

from src.processing.chunk_documents import chunk_document, tokens


ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "chunking"


CONFIG = {
    "chunking": {
        "soft_max_tokens": 500,
        "hard_max_tokens": 750,
        "oversized_overlap_tokens": 90,
        "minimum_chunk_tokens": 50,
        "prepend_heading_path_to_embedding_text": True,
    },
    "source_policy": {
        "sce_rule21_tariff_pdf": {
            "authority_tier": "primary_governing",
            "retrieval_tier": "default_current",
            "currency_status": "current_candidate",
        },
        "siwg_phase2_recommendations_pdf": {
            "authority_tier": "historical_draft",
            "retrieval_tier": "historical_only",
            "currency_status": "historical",
        },
    },
}


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


class ChunkDocumentsTests(unittest.TestCase):
    def test_tariff_chunk_preserves_evidence_and_citation_metadata(self) -> None:
        document = load_fixture("tariff_structural_blocks.json")

        chunked = chunk_document(document, CONFIG)
        first_chunk = chunked["chunks"][0]

        self.assertEqual(first_chunk["source_id"], "sce_rule21_tariff_pdf")
        self.assertEqual(
            first_chunk["source_policy"]["authority_tier"],
            "primary_governing",
        )
        self.assertEqual(first_chunk["citation"]["tariff_rule_sheet"], "51")
        self.assertEqual(first_chunk["citation"]["tariff_cpuc_sheet"], "85469-E")
        self.assertIn(
            "An Applicant is responsible for interconnection fees",
            first_chunk["evidence_text"],
        )
        self.assertIn("Section:", first_chunk["embedding_text"])
        self.assertIn(
            "E. INTERCONNECTION REQUEST SUBMISSION PROCESS",
            first_chunk["embedding_text"],
        )

    def test_evidence_text_does_not_gain_embedding_heading_prefix(self) -> None:
        document = load_fixture("tariff_structural_blocks.json")

        chunked = chunk_document(document, CONFIG)
        evidence = "\n".join(chunk["evidence_text"] for chunk in chunked["chunks"])

        self.assertNotIn("Section:", evidence)
        self.assertNotIn("title: SCE Rule 21 tariff | text:", evidence)

    def test_table_is_preserved_with_preceding_context_when_within_hard_limit(self) -> None:
        document = load_fixture("tariff_structural_blocks.json")

        chunked = chunk_document(document, CONFIG)
        chunk_with_table = next(
            chunk
            for chunk in chunked["chunks"]
            if "sce_rule21_tariff_pdf:p050:b0005" in chunk["block_ids"]
        )

        self.assertIn("Table E.1", chunk_with_table["evidence_text"])
        self.assertIn(
            "An Applicant is responsible for interconnection fees",
            chunk_with_table["evidence_text"],
        )

    def test_neighbor_links_are_bidirectional(self) -> None:
        document = load_fixture("tariff_structural_blocks.json")
        config = json.loads(json.dumps(CONFIG))
        config["chunking"]["soft_max_tokens"] = 15
        config["chunking"]["hard_max_tokens"] = 30

        chunked = chunk_document(document, config)
        chunks = chunked["chunks"]

        self.assertGreater(len(chunks), 1)
        self.assertIsNone(chunks[0]["previous_chunk_id"])
        self.assertEqual(chunks[0]["next_chunk_id"], chunks[1]["chunk_id"])
        self.assertEqual(chunks[-1]["previous_chunk_id"], chunks[-2]["chunk_id"])
        self.assertIsNone(chunks[-1]["next_chunk_id"])

    def test_oversized_single_block_is_flagged_without_text_mutation(self) -> None:
        long_text = " ".join(f"word{index}" for index in range(900))
        document = {
            "document_id": "sce_rule21_tariff_pdf",
            "source": {
                "id": "sce_rule21_tariff_pdf",
                "title": "SCE Rule 21 tariff",
                "content_hash": "sha256:test",
            },
            "blocks": [
                {
                    "block_id": "sce_rule21_tariff_pdf:p001:b0001",
                    "block_type": "paragraph",
                    "text": long_text,
                    "heading_path": ["E. Example"],
                    "citation": {"pdf_page_start": 1, "section_ids": ["E"]},
                    "is_substantive": True,
                }
            ],
        }

        chunked = chunk_document(document, CONFIG)
        chunk = chunked["chunks"][0]

        self.assertEqual(chunk["evidence_text"], long_text)
        self.assertGreater(chunk["estimated_evidence_tokens"], 750)
        self.assertIn("single_block_exceeds_hard_limit", chunk["chunking_flags"])

    def test_historical_policy_is_preserved(self) -> None:
        document = load_fixture("tariff_structural_blocks.json")
        document["document_id"] = "siwg_phase2_recommendations_pdf"
        document["source"]["id"] = "siwg_phase2_recommendations_pdf"

        chunked = chunk_document(document, CONFIG)

        self.assertTrue(chunked["chunking_summary"]["historical_only"])
        self.assertEqual(
            chunked["source_policy"]["retrieval_tier"],
            "historical_only",
        )

    def test_token_estimator_is_deterministic(self) -> None:
        self.assertEqual(tokens("One, two, three."), tokens("One, two, three."))
        self.assertGreater(tokens("One, two, three."), 0)


if __name__ == "__main__":
    unittest.main()
