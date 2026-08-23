# src/evaluation/generate_query_rewrites.py
"""Generate and cache query rewrites (HyDE and expansion)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.llm_client import generate_text_answer, get_client
from src.evaluation.evaluate_retrieval import load_jsonl

ROOT = Path(__file__).resolve().parents[2]


def generate_hyde(llm_client, query_text: str, context: str = "DER interconnection requirements", max_tokens: int = 150) -> str:
    """Generate hypothetical document for HyDE."""
    prompt = f"""You are researching: {context}

User question: {query_text}

Write a hypothetical document paragraph that would answer this question. 
Be specific and technical, as if from a utility tariff or technical handbook.
Keep it under {max_tokens} words.

Hypothetical document:"""

    response, _ = generate_text_answer(
        instructions="Generate a technical document paragraph.",
        user_prompt=prompt,
        client=llm_client,
        verbose=False,
    )
    return response.strip()


def generate_expansion(llm_client, query_text: str, num_terms: int = 5) -> str:
    """Generate query expansion terms."""
    prompt = f"""Given this search query: "{query_text}"

Generate {num_terms} synonyms or related technical terms that would help find relevant documents in utility tariffs and technical handbooks.
Return only the terms, comma-separated, no explanation.

Related terms:"""

    response, _ = generate_text_answer(
        instructions="Generate comma-separated technical terms.",
        user_prompt=prompt,
        client=llm_client,
        verbose=False,
    )
    terms = [t.strip() for t in response.split(",")]
    return f"{query_text} {' '.join(terms)}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--queries",
        type=Path,
        default=ROOT / "data/evaluation/queries.jsonl",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data/evaluation/query_rewrites.jsonl",
    )
    args = parser.parse_args()

    # Initialize LLM client
    llm_client = get_client()

    # Load queries
    queries = load_jsonl(args.queries)
    print(f"Generating rewrites for {len(queries)} queries...")

    # Generate and cache
    results = []
    for i, query in enumerate(queries, 1):
        print(f"Query {i}/{len(queries)}: {query['query_id']}")

        try:
            hyde = generate_hyde(llm_client, query["query_text"], context="DER interconnection requirements")
        except Exception as e:
            print(f"  HyDE failed: {e}")
            hyde = None

        try:
            expanded = generate_expansion(llm_client, query["query_text"], num_terms=5)
        except Exception as e:
            print(f"  Expansion failed: {e}")
            expanded = None

        # Copy all fields from original query including gold_metadata
        results.append({
            **query,  # This includes query_id, query_text, gold_metadata, etc.
            "hyde": hyde,
            "expanded": expanded,
        })

    # Save
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        for r in results:
            json.dump(r, f, ensure_ascii=False)
            f.write("\n")

    print(f"Saved {len(results)} rewrites to {args.output}")


if __name__ == "__main__":
    main()