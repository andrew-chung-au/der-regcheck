"""Unit tests for evidence-bounded answer generation."""
from __future__ import annotations

import json
import unittest
from typing import Any

from google.genai import types

from src.generation.answer_generator import (
    INSUFFICIENT_EVIDENCE_MESSAGE,
    AnswerGenerator,
    build_evidence_context,
)
from src.generation.schemas import AnswerClaim, StructuredAnswerOutput


class FakeRetriever:
    """Return predetermined chunks without loading retrieval models."""

    def __init__(self, sources: list[dict[str, Any]]) -> None:
        self.sources = sources
        self.received_question: str | None = None
        self.received_top_k: int | None = None

    def retrieve(
        self,
        question: str,
        final_k: int = 10,
    ) -> list[dict[str, Any]]:
        self.received_question = question
        self.received_top_k = final_k
        return self.sources


class FakeLlmClient:
    """Minimal fake Gemini client compatible with structured generation."""

    class Models:
        def __init__(self, answer: StructuredAnswerOutput) -> None:
            self.answer = answer
            self.calls: list[dict[str, Any]] = []

        def generate_content(
            self,
            *,
            model: str,
            contents: str,
            config: types.GenerateContentConfig | None = None,
        ) -> Any:
            self.calls.append(
                {
                    "model": model,
                    "contents": contents,
                    "config": config,
                }
            )
            response = type("Response", (), {})()
            response.text = json.dumps(self.answer.model_dump())
            response.usage_metadata = {"test_usage": True}
            return response

    def __init__(self, answer: StructuredAnswerOutput) -> None:
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
            "retrieval_tier": "default_current",
            "currency_status": "current_candidate",
        },
        "reranker_score": 0.998204,
        "vector_rank": 1,
    }


def valid_answer() -> StructuredAnswerOutput:
    """Return a valid answer for the one-source evidence fixture."""
    return StructuredAnswerOutput(
        answer_status="answered",
        direct_answer=(
            "The supplied tariff evidence states that the Smart Inverter shall "
            "maintain constant reactive power in this mode."
        ),
        claims=[
            AnswerClaim(
                text=(
                    "In constant reactive power mode, the Smart Inverter shall "
                    "maintain constant reactive power."
                ),
                citation_labels=["S1"],
            )
        ],
        uncertainty_statement="This is research assistance only.",
        clarifying_question=None,
        evidence_gaps=[],
        research_next_steps=[],
    )


class AnswerGeneratorTests(unittest.TestCase):
    def make_generator(
        self,
        *,
        sources: list[dict[str, Any]],
        answer: StructuredAnswerOutput | None = None,
        prompt_version: str = "v2_structured_grounded_rag",
    ) -> tuple[AnswerGenerator, FakeRetriever, FakeLlmClient]:
        retriever = FakeRetriever(sources)
        llm_client = FakeLlmClient(answer or valid_answer())
        generator = AnswerGenerator(
            retriever=retriever,
            llm_client=llm_client,
            prompt_version=prompt_version,
        )
        return generator, retriever, llm_client

    def test_build_evidence_context_contains_numbered_source_metadata(self) -> None:
        context = build_evidence_context([make_source()])

        self.assertIn("[S1]", context)
        self.assertIn("sce_rule21_tariff_pdf", context)
        self.assertIn("primary_governing", context)
        self.assertIn("Constant Reactive Power Mode", context)
        self.assertIn("PDF page: 174", context)

    def test_answer_returns_insufficient_evidence_when_retrieval_is_empty(self) -> None:
        generator, retriever, llm_client = self.make_generator(sources=[])

        result = generator.answer("What is the constant reactive power requirement?")

        self.assertEqual(result.answer_status, "insufficient_evidence")
        self.assertEqual(result.answer.direct_answer, INSUFFICIENT_EVIDENCE_MESSAGE)
        self.assertEqual(result.sources, [])
        self.assertIsNone(result.usage)
        self.assertEqual(retriever.received_top_k, 10)
        self.assertEqual(llm_client.models.calls, [])

    def test_answer_sends_retrieved_evidence_to_llm_client(self) -> None:
        generator, retriever, llm_client = self.make_generator(
            sources=[make_source()]
        )

        result = generator.answer(
            "What is the constant reactive power requirement?",
            top_k=1,
        )

        self.assertEqual(result.answer_status, "answered")
        self.assertEqual(retriever.received_top_k, 1)
        self.assertEqual(len(llm_client.models.calls), 1)

        prompt = llm_client.models.calls[0]["contents"]
        self.assertIn("Constant Reactive Power Mode", prompt)
        self.assertIn("shall maintain a constant reactive power", prompt)
        self.assertIn("[S1]", prompt)

    def test_default_top_k_is_ten(self) -> None:
        generator, retriever, _ = self.make_generator(sources=[make_source()])

        generator.answer("Test question?")

        self.assertEqual(retriever.received_top_k, 10)

    def test_valid_citation_mapping(self) -> None:
        generator, _, _ = self.make_generator(sources=[make_source()])

        result = generator.answer("Test question?")

        self.assertTrue(result.citation_validation.is_valid)
        self.assertEqual(result.citation_validation.unknown_labels, set())

    def test_unknown_citation_fails_closed(self) -> None:
        invalid_output = StructuredAnswerOutput(
            answer_status="answered",
            direct_answer="Unsupported answer.",
            claims=[
                AnswerClaim(
                    text="Unsupported claim.",
                    citation_labels=["S99"],
                )
            ],
            uncertainty_statement="Test.",
        )
        generator, _, _ = self.make_generator(
            sources=[make_source()],
            answer=invalid_output,
        )

        result = generator.answer("Test question?")

        self.assertFalse(result.citation_validation.is_valid)
        self.assertIn("S99", result.citation_validation.unknown_labels)
        self.assertEqual(result.answer_status, "insufficient_evidence")

    def test_uncited_claim_fails_closed(self) -> None:
        invalid_output = StructuredAnswerOutput(
            answer_status="answered",
            direct_answer="Unsupported answer.",
            claims=[AnswerClaim(text="An uncited factual claim.")],
            uncertainty_statement="Test.",
        )
        generator, _, _ = self.make_generator(
            sources=[make_source()],
            answer=invalid_output,
        )

        result = generator.answer("Test question?")

        self.assertFalse(result.citation_validation.is_valid)
        self.assertEqual(result.citation_validation.uncited_claim_indexes, [0])
        self.assertEqual(result.answer_status, "insufficient_evidence")


if __name__ == "__main__":
    unittest.main()