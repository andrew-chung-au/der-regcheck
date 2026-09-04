"""Unit tests for evidence-bounded answer generation."""
from __future__ import annotations

import unittest
from typing import Any

from src.generation.answer_generator import (
    INSUFFICIENT_EVIDENCE_MESSAGE,
    AnswerGenerator,
    build_evidence_context,
)


class FakeRetriever:
    """Return predetermined chunks without loading retrieval models."""

    def __init__(self, sources: list[dict[str, Any]]) -> None:
        self.sources = sources
        self.received_question: str | None = None
        self.received_top_k: int | None = None

    def retrieve(
        self,
        question: str,
        final_k: int = 5,
    ) -> list[dict[str, Any]]:
        self.received_question = question
        self.received_top_k = final_k
        return self.sources


class FakeLlmClient:
    """Minimal fake Gemini client compatible with generate_text_answer()."""

    class Models:
        def __init__(self, answer: str) -> None:
            self.answer = answer
            self.calls: list[dict[str, Any]] = []

        def generate_content(
            self,
            *,
            model: str,
            contents: str,
        ) -> Any:
            self.calls.append(
                {
                    "model": model,
                    "contents": contents,
                }
            )

            response = type("Response", (), {})()
            response.text = self.answer
            response.usage_metadata = {"test_usage": True}
            return response

    def __init__(self, answer: str) -> None:
        self.models = self.Models(answer)


def make_source() -> dict[str, Any]:
    """Create one realistic retrieved chunk for deterministic tests."""
    return {
        "chunk_id": "sce_rule21_tariff_pdf:c0360",
        "source_id": "sce_rule21_tariff_pdf",
        "document_id": "sce_rule21_tariff_pdf",
        "heading_path": [
            "H. GENERATING FACILITY DESIGN AND OPERATING REQUIREMENTS",
            "2. Prevention of Interference",
            "w. Constant Reactive Power Mode",
        ],
        "evidence_text": (
            "When in this mode, the Smart Inverter shall maintain a constant "
            "reactive power. The target reactive power level and mode shall be "
            "specified by the Distribution Provider."
        ),
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
    }


class AnswerGeneratorTests(unittest.TestCase):
    def test_build_evidence_context_contains_numbered_source_metadata(self) -> None:
        context = build_evidence_context([make_source()])

        self.assertIn("[1]", context)
        self.assertIn("sce_rule21_tariff_pdf", context)
        self.assertIn("primary_governing", context)
        self.assertIn("Constant Reactive Power Mode", context)
        self.assertIn("PDF page: 174", context)

    def test_answer_returns_insufficient_evidence_when_retrieval_is_empty(self) -> None:
        retriever = FakeRetriever([])
        llm_client = FakeLlmClient("This response should not be used.")

        generator = AnswerGenerator(
            retriever=retriever,
            llm_client=llm_client,
        )

        result = generator.answer(
            "What is the constant reactive power requirement?",
            top_k=3,
        )

        self.assertEqual(result.answer, INSUFFICIENT_EVIDENCE_MESSAGE)
        self.assertEqual(result.sources, [])
        self.assertIsNone(result.usage)
        self.assertEqual(llm_client.models.calls, [])

    def test_answer_sends_retrieved_evidence_to_llm_client(self) -> None:
        source = make_source()
        retriever = FakeRetriever([source])
        llm_client = FakeLlmClient(
            "The Smart Inverter shall maintain constant reactive power [1]."
        )

        generator = AnswerGenerator(
            retriever=retriever,
            llm_client=llm_client,
        )

        result = generator.answer(
            "What is the constant reactive power requirement?",
            top_k=1,
        )

        self.assertEqual(
            result.answer,
            "The Smart Inverter shall maintain constant reactive power [1].",
        )
        self.assertEqual(result.sources, [source])
        self.assertEqual(retriever.received_top_k, 1)
        self.assertEqual(len(llm_client.models.calls), 1)

        prompt = llm_client.models.calls[0]["contents"]
        self.assertIn("Constant Reactive Power Mode", prompt)
        self.assertIn("shall maintain a constant reactive power", prompt)
        self.assertIn("[1]", prompt)


if __name__ == "__main__":
    unittest.main()