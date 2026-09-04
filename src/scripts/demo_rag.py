"""Run end-to-end DER RegCheck retrieval-augmented generation.

This script demonstrates the complete RAG flow:
1. User asks a research question.
2. Query is expanded with technical terms.
3. Evidence is retrieved using the selected v3 configuration.
4. A structured, citation-grounded answer is generated.
5. Citations are validated deterministically.
6. Answer, evidence, and trace are displayed.

Usage:
    uv run python -m src.scripts.demo_rag \
      --question "What requirements apply to smart inverter reactive power?"
"""
from __future__ import annotations

import argparse
from typing import Any

from src.generation.answer_generator import AnswerGenerator, format_source_label


def format_rank(rank: int | None) -> str:
    """Format a first-stage rank for terminal output."""
    return str(rank) if rank is not None else "not retrieved"


def print_source(index: int, source: dict[str, Any]) -> None:
    """Print one source entry with retrieval trace and evidence preview."""
    print(f"\n{format_source_label(source, index)}")

    vector_similarity = source.get("vector_similarity")
    if vector_similarity is not None:
        print(f"Vector similarity: {float(vector_similarity):.6f}")

    reranker_score = source.get("reranker_score")
    if reranker_score is not None:
        print(f"Reranker score: {float(reranker_score):.6f}")

    vector_rank = source.get("vector_rank")
    if vector_rank is not None:
        print(f"Vector rank: {format_rank(vector_rank)}")

    print("Evidence preview:")
    print(source.get("evidence_text", "")[:600].strip())


def main() -> None:
    """Generate a grounded DER interconnection answer for one question."""
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "--question",
        required=True,
        help="DER interconnection question to answer from retrieved evidence.",
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=10,
        help="Number of reranked evidence chunks to provide. Default: 10.",
    )

    args = parser.parse_args()

    question = args.question.strip()

    if not question:
        parser.error("--question must not be blank.")

    if args.top_k <= 0:
        parser.error("--top-k must be positive.")

    print("Loading retrieval and generation services...")
    generator = AnswerGenerator()

    print(f"\n{'=' * 88}")
    print("QUESTION")
    print(f"{'=' * 88}")
    print(f"Original: {question}")

    result = generator.answer(
        question=question,
        top_k=args.top_k,
    )

    print(f"\nRetrieval query: {result.retrieval_query}")
    print(f"Rewrite status: {result.rewrite_status}")

    print(f"\n{'=' * 88}")
    print("ANSWER")
    print(f"{'=' * 88}")
    print(f"Status: {result.answer_status}")
    print()
    print(result.answer.direct_answer)

    if result.answer.clarifying_question:
        print(f"\nClarifying question: {result.answer.clarifying_question}")

    if result.answer.evidence_gaps:
        print("\nEvidence gaps:")
        for gap in result.answer.evidence_gaps:
            print(f"  - {gap}")

    if result.answer.research_next_steps:
        print("\nResearch next steps:")
        for step in result.answer.research_next_steps:
            print(f"  - {step}")

    print(f"\n{'=' * 88}")
    print("UNCERTAINTY STATEMENT")
    print(f"{'=' * 88}")
    print(result.answer.uncertainty_statement)

    if result.answer.claims:
        print(f"\n{'=' * 88}")
        print("CLAIMS WITH CITATIONS")
        print(f"{'=' * 88}")
        for idx, claim in enumerate(result.answer.claims, start=1):
            citations = ", ".join(claim.citation_labels)
            print(f"\n{idx}. {claim.text} [{citations}]")

    if not result.citation_validation.is_valid:
        print(f"\n{'=' * 88}")
        print("CITATION VALIDATION FAILED")
        print(f"{'=' * 88}")
        for error in result.citation_validation.errors:
            print(f"  - {error}")
        print("\nThis answer should not be displayed in production.")

    print(f"\n{'=' * 88}")
    print("RETRIEVED EVIDENCE")
    print(f"{'=' * 88}")

    if not result.sources:
        print("No retrieved sources.")
        return

    for index, source in enumerate(result.sources, start=1):
        print_source(index, source)


if __name__ == "__main__":
    main()