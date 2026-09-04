"""Structured answer schemas for DER RegCheck.

These schemas define the contract between the LLM and the application.
They enable deterministic citation validation, answer-status routing,
structured evidence gaps, and monitoring aggregation.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AnswerClaim(BaseModel):
    """One evidence-grounded factual claim with citations."""

    text: str = Field(
        description=(
            "One concise evidence-grounded claim. Do not include citation "
            "brackets in the text."
        )
    )
    citation_labels: list[str] = Field(
        default_factory=list,
        description=(
            "Evidence labels supporting this claim, such as S1 or S3. "
            "Use only labels from the supplied evidence pack."
        ),
    )


class StructuredAnswerOutput(BaseModel):
    """Structured output schema for DER RegCheck answer generation.

    The application renders this into user-facing text and validates
    citations deterministically before showing the answer.
    """

    answer_status: Literal[
        "answered",
        "partial",
        "needs_clarification",
        "insufficient_evidence",
        "high_stakes_boundary",
    ]
    direct_answer: str = Field(
        description=(
            "A concise direct answer to the user's question, grounded only "
            "in the supplied evidence. May include general uncertainty wording."
        )
    )
    claims: list[AnswerClaim] = Field(
        default_factory=list,
        description=(
            "Structured factual claims with explicit citation labels. "
            "Each claim should be a single factual statement supported by evidence."
        )
    )
    uncertainty_statement: str = Field(
        description=(
            "Required uncertainty and boundary statement. Must clarify that "
            "this is research assistance, not legal, engineering, regulatory, "
            "or compliance advice."
        )
    )
    clarifying_question: str | None = Field(
        default=None,
        description=(
            "Optional clarifying question if the answer status is "
            "'needs_clarification' or if additional project facts would "
            "significantly change the applicable requirements."
        )
    )
    evidence_gaps: list[str] = Field(
        default_factory=list,
        description=(
            "List of material information gaps or limitations in the supplied "
            "evidence that prevent a more complete answer."
        )
    )
    research_next_steps: list[str] = Field(
        default_factory=list,
        description=(
            "Concrete next research or validation actions the user should take, "
            "such as verifying current tariff revision, confirming project-specific "
            "requirements with the utility, or consulting qualified professionals."
        )
    )