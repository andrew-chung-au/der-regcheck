from __future__ import annotations

import json
import unittest
from pathlib import Path

from src.processing.chunk_documents import chunk_document
from src.processing.quality_check_chunks import check_document


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
        }
    },
}


def load_fixture() -> dict:
    path = FIXTURES_DIR / "tariff_structural_blocks.json"
    return json.loads(path.read_text(encoding="utf-8"))


class QualityCheckChunksTests(unittest.TestCase):
    def test_valid_chunk_document_passes_quality_check(self) -> None:
        document = chunk_document(load_fixture(), CONFIG)

        result = check_document(document, hard_max=750)

        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["errors"], [])

    def test_invalid_neighbor_link_fails_quality_check(self) -> None:
        config = json.loads(json.dumps(CONFIG))
        config["chunking"]["soft_max_tokens"] = 15
        config["chunking"]["hard_max_tokens"] = 30
        document = chunk_document(load_fixture(), config)
        document["chunks"][1]["previous_chunk_id"] = "invalid:chunk"

        result = check_document(document, hard_max=30)

        self.assertEqual(result["status"], "fail")
        self.assertTrue(
            any("invalid previous_chunk_id" in error for error in result["errors"])
        )

    def test_over_hard_limit_chunk_is_review_not_failure(self) -> None:
        document = chunk_document(load_fixture(), CONFIG)
        document["chunks"][0]["estimated_evidence_tokens"] = 751

        result = check_document(document, hard_max=750)

        self.assertEqual(result["status"], "review")
        self.assertTrue(any("exceeds hard token target" in warning for warning in result["warnings"]))


if __name__ == "__main__":
    unittest.main()
