"""Run end-to-end DER RegCheck retrieval-augmented generation.

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
    heading_path = " > ".join(source.get("heading_path") or [])
    authority_tier = (
        source.get("source_policy") or {}
    ).get("authority_tier", "unknown")

    print(f"\n{format_source_label(source, index)}")
    print(f"Heading: {heading_path or 'Not available'}")
    print(f"Authority tier: {authority_tier}")
    print(f"Reranker score: {float(source['reranker_score']):.6f}")
    print(f"RRF score: {float(source['rrf_score']):.6f}")
    print(
        "First-stage ranks: "
        f"lexical={format_rank(source.get('lexical_rank'))}, "
        f"vector={format_rank(source.get('vector_rank'))}"
    )
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
        default=5,
        help="Number of reranked evidence chunks to provide. Default: 5.",
    )

    args = parser.parse_args()

    question = args.question.strip()

    if not question:
        parser.error("--question must not be blank.")

    if args.top_k <= 0:
        parser.error("--top-k must be positive.")

    print("Loading retrieval and generation services...")
    generator = AnswerGenerator()

    print(f"\nQuestion: {question}")

    result = generator.answer(
        question=question,
        top_k=args.top_k,
    )

    print("\n" + "=" * 88)
    print("ANSWER")
    print("=" * 88)
    print(result.answer)

    print("\n" + "=" * 88)
    print("RETRIEVED SOURCES")
    print("=" * 88)

    if not result.sources:
        print("No retrieved sources.")
        return

    for index, source in enumerate(result.sources, start=1):
        print_source(index, source)


if __name__ == "__main__":
    main()