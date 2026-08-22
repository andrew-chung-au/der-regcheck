from __future__ import annotations

import unittest

from src.processing.quality_check_normalised import check_document


class QualityCheckNormalisedTests(unittest.TestCase):
    def test_pdf_document_with_traceable_block_passes(self) -> None:
        document = {
            "schema_version": "1.0",
            "document_id": "example_pdf",
            "source_type": "pdf",
            "source": {"content_hash": "sha256:test"},
            "blocks": [
                {
                    "block_id": "example_pdf:p001:b0001",
                    "source_id": "example_pdf",
                    "block_type": "paragraph",
                    "text": "The applicant shall submit a complete request.",
                    "heading_path": ["Section 1"],
                    "citation": {"pdf_page_start": 1},
                    "is_substantive": True,
                    "normalisation_flags": [],
                }
            ],
        }

        result = check_document(document)

        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["errors"], [])

    def test_missing_pdf_page_locator_fails(self) -> None:
        document = {
            "schema_version": "1.0",
            "document_id": "example_pdf",
            "source_type": "pdf",
            "source": {"content_hash": "sha256:test"},
            "blocks": [
                {
                    "block_id": "example_pdf:b0001",
                    "source_id": "example_pdf",
                    "block_type": "paragraph",
                    "text": "The applicant shall submit a complete request.",
                    "heading_path": ["Section 1"],
                    "citation": {},
                    "is_substantive": True,
                    "normalisation_flags": [],
                }
            ],
        }

        result = check_document(document)

        self.assertEqual(result["status"], "fail")
        self.assertTrue(any("missing pdf_page_start" in error for error in result["errors"]))

    def test_html_document_requires_heading_path_citation(self) -> None:
        document = {
            "schema_version": "1.0",
            "document_id": "example_html",
            "source_type": "html",
            "source": {"content_hash": "sha256:test"},
            "blocks": [
                {
                    "block_id": "example_html:b0001",
                    "source_id": "example_html",
                    "block_type": "paragraph",
                    "text": "The applicant shall submit a complete request.",
                    "heading_path": ["Application"],
                    "citation": {},
                    "is_substantive": True,
                    "normalisation_flags": [],
                }
            ],
        }

        result = check_document(document)

        self.assertEqual(result["status"], "fail")
        self.assertTrue(
            any("missing heading-path citation" in error for error in result["errors"])
        )


if __name__ == "__main__":
    unittest.main()
