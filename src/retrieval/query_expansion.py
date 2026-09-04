"""Live query expansion for DER RegCheck retrieval using structured output.

This module generates bounded technical expansion terms to improve
retrieval quality while avoiding semantic drift or overconfident rewriting.

The selected v3 configuration uses query expansion, which produced a
modest improvement in the production-aligned evaluation. HyDE is disabled
because it reduced retrieval quality. [cite:file:25]
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field


@dataclass(frozen=True)
class QueryExpansionResult:
    """Result of query expansion with fallback support."""

    original_question: str
    expansion_terms: list[str]
    retrieval_query: str
    status: str
    error_message: str | None = None


class ExpansionOutput(BaseModel):
    """Structured output schema for query expansion."""

    terms: list[str] = Field(
        description=(
            "Exactly 5 short technical search terms or synonyms relevant to "
            "DER interconnection research. Each term should be 1-3 words. "
            "Do not include explanations or full sentences."
        ),
        min_length=5,
        max_length=5,
    )


def expand_query(
    *,
    question: str,
    llm_client: Any,
    num_terms: int = 5,
    context: str = "DER interconnection requirements",
) -> QueryExpansionResult:
    """Generate bounded technical expansion terms for retrieval using structured output.

    Args:
        question: The original user question.
        llm_client: Gemini client instance.
        num_terms: Number of expansion terms to generate (default: 5).
        context: Domain context for the expansion prompt.

    Returns:
        QueryExpansionResult with original question, expansion terms,
        combined retrieval query, status, and optional error message.

    The expansion prompt is deliberately constrained:
    - Generates exactly 5 short technical terms via structured JSON.
    - Does not answer the question.
    - Does not state legal, regulatory, engineering, or compliance conclusions.
    - Does not cite sources or add explanatory prose.

    If expansion fails, the caller should fall back to the original question.
    """
    from src.llm_client import generate_structured_answer

    instructions = f"""You are generating search expansion terms for {context}.

Generate exactly {num_terms} short technical search terms or synonyms
relevant to DER interconnection research.

Each term should be 1-3 words. Do not include explanations, full sentences,
or answers to the user's question. Do not state legal, regulatory,
engineering, or compliance conclusions. Do not cite sources.

Return only the list of terms in valid JSON format."""

    user_prompt = f"""Given this search query: "{question}"

Generate exactly {num_terms} synonyms or related technical terms that would help
find relevant documents in utility tariffs and technical handbooks.

Return a JSON object with a "terms" field containing exactly {num_terms} short phrases.

Example output format:
{{"terms": ["term1", "term2", "term3", "term4", "term5"]}}"""

    try:
        output, _ = generate_structured_answer(
            instructions=instructions,
            user_prompt=user_prompt,
            output_type=ExpansionOutput,
            client=llm_client,
            verbose=False,
        )

        terms = [t.strip() for t in output.terms if t.strip()]

        if len(terms) != num_terms:
            return QueryExpansionResult(
                original_question=question,
                expansion_terms=[],
                retrieval_query=question,
                status="fallback_invalid_term_count",
                error_message=f"Expected {num_terms} terms, got {len(terms)}",
            )

        retrieval_query = f"{question} {' '.join(terms)}"

        return QueryExpansionResult(
            original_question=question,
            expansion_terms=terms,
            retrieval_query=retrieval_query,
            status="expanded",
        )

    except Exception as error:
        return QueryExpansionResult(
            original_question=question,
            expansion_terms=[],
            retrieval_query=question,
            status="fallback_error",
            error_message=f"{type(error).__name__}: {error}",
        )