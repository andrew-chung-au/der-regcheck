"""Run database-backed hybrid retrieval and print source-traceable results.

Usage:
    uv run python -m src.scripts.demo_retrieval \
      --question "What requirements apply to smart inverter reactive power?"
"""
from __future__ import annotations

import argparse
from typing import Any

from src.retrieval.runtime_retriever import get_runtime_retriever


def format_citation(citation: dict[str, Any]) -> str:
    """Format available source-location metadata into one short string."""
    parts: list[str] = []

    section_ids = citation.get("section_ids")
    if section_ids:
        parts.append(f"Section: {'.'.join(str(item) for item in section_ids)}")

    pdf_page = citation.get("pdf_page_start")
    if pdf_page is not None:
        parts.append(f"PDF page: {pdf_page}")

    printed_page = citation.get("printed_page_start")
    if printed_page:
        parts.append(f"Printed page: {printed_page}")

    tariff_rule_sheet = citation.get("tariff_rule_sheet")
    if tariff_rule_sheet:
        parts.append(f"Rule sheet: {tariff_rule_sheet}")

    tariff_cpuc_sheet = citation.get("tariff_cpuc_sheet")
    if tariff_cpuc_sheet:
        parts.append(f"CPUC sheet: {tariff_cpuc_sheet}")

    tariff_advice_letter = citation.get("tariff_advice_letter")
    if tariff_advice_letter:
        parts.append(f"Advice letter: {tariff_advice_letter}")

    heading_path = citation.get("heading_path")
    if heading_path:
        parts.append(
            "Citation heading: "
            + " > ".join(str(item) for item in heading_path)
        )

    return " | ".join(parts) if parts else "No citation locator available"


def print_result(index: int, chunk: dict[str, Any]) -> None:
    """Print one retrieved chunk with retrieval trace and source metadata."""
    heading_path = " > ".join(chunk.get("heading_path") or [])
    citation = format_citation(chunk.get("citation") or {})

    lexical_rank = chunk.get("lexical_rank")
    vector_rank = chunk.get("vector_rank")

    print(f"\n{'=' * 88}")
    print(f"Result {index}")
    print(f"{'=' * 88}")
    print(f"Chunk ID       : {chunk['chunk_id']}")
    print(f"Source ID      : {chunk['source_id']}")
    print(f"Document ID    : {chunk['document_id']}")
    print(f"Heading path   : {heading_path or 'No heading path'}")
    print(f"Reranker score : {float(chunk['reranker_score']):.6f}")
    print(f"RRF score      : {float(chunk['rrf_score']):.6f}")
    print(
        "First-stage ranks: "
        f"lexical={lexical_rank if lexical_rank is not None else 'not in top candidates'}, "
        f"vector={vector_rank if vector_rank is not None else 'not in top candidates'}"
    )
    print(f"Citation       : {citation}")
    print("\nEvidence preview:")
    print(chunk.get("evidence_text", "")[:800].strip())


def main() -> None:
    """Run a hybrid retrieval demonstration for one question."""
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "--question",
        required=True,
        help="Regulatory or technical DER interconnection question to retrieve against.",
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of reranked results to display. Default: 5.",
    )

    args = parser.parse_args()

    if args.top_k <= 0:
        parser.error("--top-k must be positive.")

    question = args.question.strip()

    if not question:
        parser.error("--question must not be blank.")

    print("Loading retrieval models...")
    retriever = get_runtime_retriever()

    print(f"Question: {question}")
    print("Pipeline: PostgreSQL full-text + pgvector -> weighted RRF -> cross-encoder")

    results = retriever.retrieve(
        question=question,
        final_k=args.top_k,
    )

    if not results:
        print("\nNo matching chunks were found.")
        return

    print(f"\nRetrieved {len(results)} reranked chunk(s).")

    for index, chunk in enumerate(results, start=1):
        print_result(index, chunk)


if __name__ == "__main__":
    main()