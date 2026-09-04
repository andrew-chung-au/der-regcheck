"""Evidence-bounded answer generation for DER RegCheck.

Runtime flow:
1. Retrieve evidence using the selected v3 production retrieval path.
2. Build an evidence pack with stable S1–S10 labels.
3. Generate a structured answer using Gemini with configurable prompt.
4. Validate every claim citation against the supplied evidence labels.
5. Fail closed when generated citations are invalid.

Note: Query expansion has been disabled for performance reasons.
The v3 evaluation showed expansion improved composite score by only 0.00285 (0.37%)
but added 32-36 seconds of latency per query. See docs/decisions.md for rationale.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.generation.citation_validator import (
    CitationValidationResult,
    validate_citations,
)
from src.generation.prompts import (
    DEFAULT_PROMPT_VERSION,
    PromptVersion,
    get_prompt_instructions,
)
from src.generation.schemas import StructuredAnswerOutput
from src.llm_client import generate_structured_answer, get_client
from src.retrieval.query_expansion import QueryExpansionResult
from src.retrieval.runtime_retriever import get_runtime_retriever


INSUFFICIENT_EVIDENCE_MESSAGE = (
    "I do not have enough retrieved evidence to answer that reliably. "
    "Please ask a more specific question or consult the cited source documents."
)


@dataclass(frozen=True)
class GeneratedAnswer:
    """Complete answer result with retrieval trace and validation details."""

    original_question: str
    retrieval_query: str
    rewrite_status: str
    answer_status: str
    answer: StructuredAnswerOutput
    sources: list[dict[str, Any]]
    citation_validation: CitationValidationResult
    usage: Any | None
    prompt_version: str | None = None


def _insufficient_answer(
    *,
    evidence_gap: str,
    next_steps: list[str],
) -> StructuredAnswerOutput:
    """Build the bounded response used for retrieval/generation failures."""
    return StructuredAnswerOutput(
        answer_status="insufficient_evidence",
        direct_answer=INSUFFICIENT_EVIDENCE_MESSAGE,
        claims=[],
        uncertainty_statement=(
            "This is research assistance only, not legal, engineering, "
            "regulatory, or compliance advice."
        ),
        clarifying_question=None,
        evidence_gaps=[evidence_gap],
        research_next_steps=next_steps,
    )


def format_source_label(chunk: dict[str, Any], index: int) -> str:
    """Build a trusted, human-readable source label for one evidence chunk."""
    citation = chunk.get("citation") or {}
    source_policy = chunk.get("source_policy") or {}
    heading_path = " > ".join(chunk.get("heading_path") or [])

    parts = [f"[S{index}] {chunk.get('source_id', 'Unknown source')}"]

    authority_tier = source_policy.get("authority_tier")
    if authority_tier:
        parts.append(f"Authority: {authority_tier.replace('_', ' ').title()}")

    currency_status = source_policy.get("currency_status")
    if currency_status:
        parts.append(f"Status: {currency_status.replace('_', ' ')}")

    if heading_path:
        parts.append(f"Heading: {heading_path}")

    section_ids = citation.get("section_ids")
    if section_ids:
        parts.append(f"Section: {'.'.join(str(item) for item in section_ids)}")

    pdf_page = citation.get("pdf_page_start")
    if pdf_page is not None:
        parts.append(f"PDF page: {pdf_page}")

    tariff_rule_sheet = citation.get("tariff_rule_sheet")
    if tariff_rule_sheet:
        parts.append(f"Rule sheet: {tariff_rule_sheet}")

    return " | ".join(parts)


def build_evidence_context(chunks: list[dict[str, Any]]) -> str:
    """Build the exact evidence pack supplied to the answer model."""
    sections: list[str] = []

    for index, chunk in enumerate(chunks, start=1):
        citation = chunk.get("citation") or {}
        source_policy = chunk.get("source_policy") or {}
        heading_path = " > ".join(chunk.get("heading_path") or [])
        section_ids = ".".join(
            str(item) for item in citation.get("section_ids") or []
        )

        sections.append(
            "\n".join(
                [
                    f"[S{index}]",
                    f"Source ID: {chunk.get('source_id', 'unknown')}",
                    f"Authority tier: {source_policy.get('authority_tier', 'unknown')}",
                    f"Currency status: {source_policy.get('currency_status', 'unknown')}",
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
    """Build the prompt containing the original question and evidence pack."""
    evidence_context = build_evidence_context(chunks)
    labels = ", ".join(f"S{index}" for index in range(1, len(chunks) + 1))

    return f"""Original user question:
{question.strip()}


Retrieved evidence:
{evidence_context}


Return a structured answer to the original user question. For every factual
claim, set citation_labels only from this supplied-label set: {labels}.
Do not invent labels, source locations, page numbers, or document status."""


class AnswerGenerator:
    """Retrieve evidence and generate a citation-grounded structured answer.

    The prompt version can be configured at initialization time. The default
    is v2_structured_grounded_rag, which is the current production prompt.
    """

    def __init__(
        self,
        retriever: Any | None = None,
        llm_client: Any | None = None,
        prompt_version: PromptVersion | str = DEFAULT_PROMPT_VERSION,
    ) -> None:
        self.retriever = retriever or get_runtime_retriever()
        self.llm_client = llm_client or get_client()
        self.prompt_version = prompt_version

    def answer(
        self,
        question: str,
        top_k: int = 10,
    ) -> GeneratedAnswer:
        """Answer one question using the selected retrieval path and supplied evidence.

        Query expansion is disabled for performance reasons. The v3 evaluation
        showed expansion improved composite score by only 0.00285 (0.37%) but
        added 32-36 seconds of latency per query.

        Args:
            question: User's research question.
            top_k: Number of evidence chunks to retrieve (default: 10).

        Returns:
            GeneratedAnswer with structured output and citation validation.
        """
        cleaned_question = question.strip()

        if not cleaned_question:
            raise ValueError("question must not be empty.")
        if top_k <= 0:
            raise ValueError("top_k must be positive.")

        # Query expansion disabled for performance. See docs/decisions.md.
        expansion = QueryExpansionResult(
            original_question=cleaned_question,
            expansion_terms=[],
            retrieval_query=cleaned_question,
            status="disabled_for_performance",
        )

        sources = self.retriever.retrieve(
            question=expansion.retrieval_query,
            final_k=top_k,
        )

        supplied_labels = {f"S{index}" for index in range(1, len(sources) + 1)}

        if not sources:
            answer = _insufficient_answer(
                evidence_gap="No relevant evidence was retrieved from the knowledge base.",
                next_steps=[
                    "Rephrase the question with more specific technical terms.",
                    "Consult the source documents directly.",
                ],
            )
            return GeneratedAnswer(
                original_question=cleaned_question,
                retrieval_query=expansion.retrieval_query,
                rewrite_status=expansion.status,
                answer_status=answer.answer_status,
                answer=answer,
                sources=[],
                citation_validation=CitationValidationResult(
                    is_valid=True,
                    supplied_labels=set(),
                    used_labels=set(),
                    unknown_labels=set(),
                    uncited_claim_indexes=[],
                    errors=[],
                ),
                usage=None,
                prompt_version=self.prompt_version,
            )

        # Get prompt instructions for this configuration
        instructions = get_prompt_instructions(self.prompt_version)

        # Build user prompt with evidence
        user_prompt = build_user_prompt(cleaned_question, sources)

        try:
            structured_output, usage = generate_structured_answer(
                instructions=instructions,
                user_prompt=user_prompt,
                output_type=StructuredAnswerOutput,
                client=self.llm_client,
                verbose=False,
            )
        except Exception as error:
            answer = _insufficient_answer(
                evidence_gap=(
                    "The answer-generation service failed before it could produce "
                    "a validated answer."
                ),
                next_steps=["Retry the question."],
            )
            validation = CitationValidationResult(
                is_valid=False,
                supplied_labels=supplied_labels,
                used_labels=set(),
                unknown_labels=set(),
                uncited_claim_indexes=[],
                errors=[f"Generation failed: {type(error).__name__}: {error}"],
            )
            return GeneratedAnswer(
                original_question=cleaned_question,
                retrieval_query=expansion.retrieval_query,
                rewrite_status=expansion.status,
                answer_status=answer.answer_status,
                answer=answer,
                sources=sources,
                citation_validation=validation,
                usage=None,
                prompt_version=self.prompt_version,
            )

        validation = validate_citations(
            answer=structured_output,
            supplied_evidence_labels=supplied_labels,
        )

        if not validation.is_valid:
            answer = _insufficient_answer(
                evidence_gap=(
                    "The generated response contained citations that could not be "
                    "validated against the supplied evidence."
                ),
                next_steps=["Retry the question."],
            )
            return GeneratedAnswer(
                original_question=cleaned_question,
                retrieval_query=expansion.retrieval_query,
                rewrite_status=expansion.status,
                answer_status=answer.answer_status,
                answer=answer,
                sources=sources,
                citation_validation=validation,
                usage=usage,
                prompt_version=self.prompt_version,
            )

        return GeneratedAnswer(
            original_question=cleaned_question,
            retrieval_query=expansion.retrieval_query,
            rewrite_status=expansion.status,
            answer_status=structured_output.answer_status,
            answer=structured_output,
            sources=sources,
            citation_validation=validation,
            usage=usage,
            prompt_version=self.prompt_version,
        )