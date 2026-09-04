"""Evidence-bounded answer generation for DER RegCheck."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.llm_client import generate_text_answer, get_client
from src.retrieval.runtime_retriever import RuntimeRetriever, get_runtime_retriever


INSUFFICIENT_EVIDENCE_MESSAGE = (
    "I do not have enough retrieved evidence to answer that reliably. "
    "Please ask a more specific question or consult the cited source documents."
)

SYSTEM_INSTRUCTIONS = """You are DER RegCheck, an evidence-first assistant for
Distributed Energy Resource interconnection requirements.

Answer only from the supplied retrieved evidence. Do not use outside knowledge.
Do not invent requirements, deadlines, standards, numerical values, source
details, or citations.

Every factual claim must include one or more inline evidence citations in square
brackets, such as [1] or [1][2]. Use only citation numbers supplied in the
evidence. If the evidence does not support a reliable answer, respond exactly:

I do not have enough retrieved evidence to answer that reliably. Please ask a
more specific question or consult the cited source documents.

Use clear, concise language. Distinguish binding tariff requirements from
supporting guidance or historical material when the source metadata indicates it.
"""


@dataclass(frozen=True)
class GeneratedAnswer:
    """Answer text, retrieved evidence, and optional Gemini usage metadata."""

    answer: str
    sources: list[dict[str, Any]]
    usage: Any | None


def format_source_label(chunk: dict[str, Any], index: int) -> str:
    """Build a concise human-readable citation label for one chunk."""
    citation = chunk.get("citation") or {}
    parts = [f"[{index}] {chunk.get('source_id', 'Unknown source')}"]

    section_ids = citation.get("section_ids")
    if section_ids:
        parts.append(f"Section {'.'.join(str(item) for item in section_ids)}")

    pdf_page = citation.get("pdf_page_start")
    if pdf_page is not None:
        parts.append(f"PDF page {pdf_page}")

    tariff_rule_sheet = citation.get("tariff_rule_sheet")
    if tariff_rule_sheet:
        parts.append(f"Rule sheet {tariff_rule_sheet}")

    return " | ".join(parts)


def build_evidence_context(chunks: list[dict[str, Any]]) -> str:
    """Convert retrieved chunks into a numbered prompt context."""
    sections: list[str] = []

    for index, chunk in enumerate(chunks, start=1):
        citation = chunk.get("citation") or {}
        heading_path = " > ".join(chunk.get("heading_path") or [])
        section_ids = ".".join(
            str(item) for item in citation.get("section_ids") or []
        )
        authority_tier = (
            chunk.get("source_policy") or {}
        ).get("authority_tier", "unknown")

        sections.append(
            "\n".join(
                [
                    f"[{index}]",
                    f"Source ID: {chunk.get('source_id', 'unknown')}",
                    f"Authority tier: {authority_tier}",
                    f"Heading: {heading_path or 'Not available'}",
                    f"Section IDs: {section_ids or 'Not available'}",
                    f"PDF page: {citation.get('pdf_page_start', 'Not available')}",
                    "Evidence:",
                    chunk.get("evidence_text", "").strip(),
                ]
            )
        )

    return "\n\n---\n\n".join(sections)


def build_user_prompt(question: str, chunks: list[dict[str, Any]]) -> str:
    """Build the user prompt containing a question and retrieved evidence."""
    evidence_context = build_evidence_context(chunks)

    return f"""Question:
{question.strip()}

Retrieved evidence:
{evidence_context}

Write an evidence-bounded answer to the question. Cite every factual statement
using only the bracketed source numbers provided above."""


class AnswerGenerator:
    """Retrieve evidence and generate a citation-grounded answer."""

    def __init__(
        self,
        retriever: RuntimeRetriever | None = None,
        llm_client: Any | None = None,
    ) -> None:
        self.retriever = retriever or get_runtime_retriever()
        self.llm_client = llm_client or get_client()

    def answer(
        self,
        question: str,
        top_k: int = 5,
    ) -> GeneratedAnswer:
        """Retrieve evidence and generate a grounded answer."""
        cleaned_question = question.strip()

        if not cleaned_question:
            raise ValueError("question must not be empty.")

        if top_k <= 0:
            raise ValueError("top_k must be positive.")

        sources = self.retriever.retrieve(
            question=cleaned_question,
            final_k=top_k,
        )

        if not sources:
            return GeneratedAnswer(
                answer=INSUFFICIENT_EVIDENCE_MESSAGE,
                sources=[],
                usage=None,
            )

        answer, usage = generate_text_answer(
            instructions=SYSTEM_INSTRUCTIONS,
            user_prompt=build_user_prompt(cleaned_question, sources),
            client=self.llm_client,
            verbose=False,
        )

        cleaned_answer = answer.strip()

        if not cleaned_answer:
            cleaned_answer = INSUFFICIENT_EVIDENCE_MESSAGE

        return GeneratedAnswer(
            answer=cleaned_answer,
            sources=sources,
            usage=usage,
        )