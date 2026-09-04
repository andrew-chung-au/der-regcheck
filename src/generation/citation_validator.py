"""Deterministic citation validation for DER RegCheck answers.

This module validates that all citations in a generated answer map to
supplied evidence labels. It enforces the evidence-first principle:
the LLM may only cite evidence that was actually provided.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from src.generation.schemas import StructuredAnswerOutput


@dataclass(frozen=True)
class CitationValidationResult:
    """Result of citation validation."""

    is_valid: bool
    supplied_labels: set[str]
    used_labels: set[str]
    unknown_labels: set[str]
    uncited_claim_indexes: list[int]
    errors: list[str]


def validate_citations(
    *,
    answer: "StructuredAnswerOutput",
    supplied_evidence_labels: Iterable[str],
) -> CitationValidationResult:
    """Validate that all citations map to supplied evidence labels.

    Args:
        answer: Structured answer output from the LLM.
        supplied_evidence_labels: Iterable of evidence labels provided to the LLM
            (e.g., ["S1", "S2", ..., "S10"]).

    Returns:
        CitationValidationResult with validation status and details.

    Validation rules:
    - Every label in claim.citation_labels must exist in supplied evidence.
    - Every 'answered' claim must have at least one citation.
    - 'insufficient_evidence' must contain no factual claims.
    - Citation label syntax must match 'S' followed by a positive integer.
    - No model-generated page/section/reference text is trusted as provenance.
    """
    supplied_set = set(supplied_evidence_labels)
    used_labels: set[str] = set()
    uncited_claim_indexes: list[int] = []
    errors: list[str] = []

    label_pattern = re.compile(r"^S\d+$")

    for idx, claim in enumerate(answer.claims):
        if not claim.citation_labels:
            uncited_claim_indexes.append(idx)
            errors.append(f"Claim {idx} has no citations")

        for label in claim.citation_labels:
            used_labels.add(label)

            if label not in supplied_set:
                errors.append(f"Unknown citation label: {label}")

            if not label_pattern.match(label):
                errors.append(f"Invalid citation label syntax: {label}")

    if answer.answer_status == "insufficient_evidence" and answer.claims:
        errors.append(
            "Answer status is 'insufficient_evidence' but contains factual claims"
        )

    unknown_labels = used_labels - supplied_set
    is_valid = len(errors) == 0

    return CitationValidationResult(
        is_valid=is_valid,
        supplied_labels=supplied_set,
        used_labels=used_labels,
        unknown_labels=unknown_labels,
        uncited_claim_indexes=uncited_claim_indexes,
        errors=errors,
    )