from __future__ import annotations

import json
import unittest
from pathlib import Path

from src.processing.normalise_documents import (
    normalise_html_document,
    normalise_pdf_document,
    normalise_sce_rule21_tariff,
)


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "normalisation"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


class NormaliseDocumentsTests(unittest.TestCase):
    def test_html_converts_heading_path_and_suppresses_adjacent_duplicate(self) -> None:
        document = {
            "document_id": "example_html",
            "source_type": "html",
            "source": {"id": "example_html", "content_hash": "sha256:test"},
            "blocks": [
                {
                    "block_type": "heading",
                    "heading_level": 2,
                    "heading": "Application",
                    "heading_path": "Application",
                    "text": "Application",
                },
                {
                    "block_type": "paragraph",
                    "heading_path": "Application",
                    "text": "Submit a complete request.",
                },
                {
                    "block_type": "paragraph",
                    "heading_path": "Application",
                    "text": "Submit a complete request.",
                },
            ],
        }

        normalised = normalise_html_document(document, {})

        self.assertEqual(normalised["normalisation_summary"]["output_blocks"], 2)
        self.assertEqual(
            normalised["normalisation_summary"]["adjacent_duplicates_suppressed"], 1
        )
        self.assertEqual(normalised["blocks"][1]["heading_path"], ["Application"])
        self.assertEqual(
            normalised["blocks"][1]["citation"]["heading_path"], ["Application"]
        )

    def test_pdf_removes_configured_boilerplate_and_preserves_page_locator(self) -> None:
        document = {
            "document_id": "example_pdf",
            "source_type": "pdf",
            "source": {"id": "example_pdf", "content_hash": "sha256:test"},
            "pages": [
                {
                    "page_number": 15,
                    "text": "\n".join(
                        [
                            "System Planning & Engineering",
                            "Part 1 | Page 1",
                            "SECTION 3 PROTECTION REQUIREMENTS",
                            "3.2.1 The Producer shall provide adequate protective devices",
                            "The Producer shall provide protection for the facility.",
                            "Docusign Envelope ID: example",
                        ]
                    ),
                }
            ],
        }
        config = {
            "repeated_line_patterns": [
                "^System Planning & Engineering$",
                "^Docusign Envelope ID:.*$",
            ],
            "part_patterns": ["^PART\\s+(\\d+)$"],
            "section_patterns": ["^SECTION\\s+(\\d+)\\s+(.+)$"],
            "clause_patterns": ["^(\\d+(?:\\.\\d+){1,4})\\s+(.+)$"],
        }

        normalised = normalise_pdf_document(document, config)
        all_text = "\n".join(block["text"] for block in normalised["blocks"])
        paragraph = next(
            block
            for block in normalised["blocks"]
            if block["block_type"] == "paragraph"
        )

        self.assertNotIn("Docusign Envelope ID", all_text)
        self.assertNotIn("System Planning & Engineering", all_text)
        self.assertEqual(paragraph["citation"]["pdf_page_start"], 15)
        self.assertEqual(paragraph["citation"]["printed_page_start"], "Part 1 | Page 1")
        self.assertIn("SECTION 3 PROTECTION REQUIREMENTS", paragraph["heading_path"])
        self.assertIn(
            "3.2.1 The Producer shall provide adequate protective devices",
            paragraph["heading_path"],
        )

    def test_tariff_page_50_creates_four_level_heading_path(self) -> None:
        normalised = normalise_sce_rule21_tariff(load_fixture("tariff_page_50.json"), {})

        special_circumstances = next(
            block
            for block in normalised["blocks"]
            if block["block_type"] == "heading"
            and block["text"].startswith("iv) Special Circumstances")
        )

        self.assertEqual(
            special_circumstances["citation"]["section_ids"],
            ["E", "3", "a", "iv"],
        )
        self.assertEqual(len(special_circumstances["heading_path"]), 4)
        self.assertTrue(
            special_circumstances["heading_path"][0].startswith(
                "E. INTERCONNECTION REQUEST"
            )
        )

    def test_tariff_page_100_keeps_roman_enumerations_as_list_items(self) -> None:
        normalised = normalise_sce_rule21_tariff(load_fixture("tariff_page_100.json"), {})

        list_items = [
            block
            for block in normalised["blocks"]
            if block["block_type"] == "list_item"
        ]

        self.assertEqual(len(list_items), 3)
        self.assertTrue(list_items[0]["text"].startswith("i)"))
        self.assertTrue(list_items[1]["text"].startswith("ii)"))
        self.assertTrue(list_items[2]["text"].startswith("iii)"))
        for item in list_items:
            self.assertEqual(item["citation"]["section_ids"], ["F", "4", "a"])

    def test_tariff_page_100_restores_parent_path_after_list(self) -> None:
        normalised = normalise_sce_rule21_tariff(load_fixture("tariff_page_100.json"), {})

        post_list_paragraph = next(
            block
            for block in normalised["blocks"]
            if block["block_type"] == "paragraph"
            and block["text"].startswith("Interconnection Financial Security instruments")
        )

        self.assertEqual(post_list_paragraph["citation"]["section_ids"], ["F", "4", "a"])
        self.assertNotIn("iii", post_list_paragraph["citation"]["section_ids"])
        self.assertEqual(post_list_paragraph["citation"]["tariff_cpuc_sheet"], "59686-E")
        self.assertEqual(post_list_paragraph["citation"]["tariff_advice_letter"], "3429-E")

    def test_tariff_page_150_preserves_frequency_path_and_sheet_metadata(self) -> None:
        normalised = normalise_sce_rule21_tariff(load_fixture("tariff_page_150.json"), {})

        frequency_paragraph = next(
            block
            for block in normalised["blocks"]
            if block["block_type"] == "paragraph"
            and block["text"].startswith("Distribution Provider controls system frequency")
        )

        citation = frequency_paragraph["citation"]
        self.assertEqual(citation["section_ids"], ["H", "2", "f"])
        self.assertEqual(citation["tariff_rule_sheet"], "150")
        self.assertEqual(citation["tariff_cpuc_sheet"], "59991-E")
        self.assertEqual(citation["tariff_advice_letter"], "3458-E")

    def test_tariff_page_233_resets_hierarchy_at_appendix(self) -> None:
        normalised = normalise_sce_rule21_tariff(load_fixture("tariff_page_233.json"), {})

        appendix = normalised["blocks"][0]
        self.assertEqual(appendix["block_type"], "heading")
        self.assertEqual(appendix["text"], "APPENDIX B")
        self.assertEqual(appendix["heading_path"], ["APPENDIX B"])
        self.assertEqual(appendix["citation"]["section_ids"], ["appendix_B"])

        for block in normalised["blocks"][1:]:
            self.assertEqual(block["citation"]["section_ids"], ["appendix_B"])
            self.assertEqual(block["heading_path"], ["APPENDIX B"])
            self.assertEqual(block["citation"]["tariff_rule_sheet"], "233")
            self.assertEqual(block["citation"]["tariff_advice_letter"], "3647-E")


if __name__ == "__main__":
    unittest.main()
