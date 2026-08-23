"""Generate synthetic queries from sampled chunks using LLM, save to JSONL."""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

# Add src/ to path so we can import llm_client
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from llm_client import generate_structured_answer, RateLimiter  # noqa: E402

SCHEMA_VERSION = "1.0"


class QueryGenerationOutput(BaseModel):
    """Schema for LLM-generated query."""
    query: str = Field(description="A specific question that this chunk directly answers.")
    query_type: str = Field(description="One of: product_capability, market_analysis, evidence_governance, technical_deep_dive, broad_research")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def absolute(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def sample_chunks(
    chunks_dir: Path,
    n_per_source: dict[str, int],
    seed: int = 42,
) -> list[dict[str, Any]]:
    """Sample chunks from each source document."""
    random.seed(seed)
    sampled: list[dict[str, Any]] = []

    for source_id, n in n_per_source.items():
        source_file = chunks_dir / f"{source_id}.json"
        if not source_file.exists():
            print(f"Warning: {source_file} not found, skipping")
            continue

        document = load_json(source_file)
        chunks = document["chunks"]

        if len(chunks) <= n:
            sampled.extend(chunks)
        else:
            sampled.extend(random.sample(chunks, n))

    return sampled


def generate_query_from_chunk_llm(
    chunk: dict[str, Any],
    rate_limiter: RateLimiter | None = None,
) -> dict[str, Any] | None:
    """Generate a synthetic query from a chunk using LLM."""
    evidence = chunk["evidence_text"][:800]
    heading = " > ".join(chunk["heading_path"])
    source_id = chunk["source_id"]

    source_type_map = {
        "tariff": "SCE Rule 21 tariff (primary governing document)",
        "handbook": "SCE Interconnection Handbook (implementation guidance)",
        "cpuc": "CPUC Rule 21 overview (regulatory context)",
        "web": "SCE interconnection web content (public guidance)",
        "testing": "SCE testing and certification instructions",
        "siwg": "SIWG recommendations (historical working group material)",
    }

    source_description = next(
        (desc for key, desc in source_type_map.items() if key in source_id),
        "DER regulatory document"
    )

    instructions = """
    You are generating evaluation queries for a DER (Distributed Energy Resources) 
    regulatory retrieval system. Given a chunk from a regulatory document, generate 
    ONE specific question that this chunk directly answers.
    
    The question should be realistic for a product manager, regulatory analyst, or 
    solutions engineer researching interconnection requirements in a new market.
    
    Focus on practical questions about:
    - Technical capabilities needed (smart inverters, telemetry, cybersecurity)
    - Interconnection processes and requirements
    - Evidence and governance (which source governs, current vs historical)
    - Standards compliance (IEEE 1547, UL 1741)
    
    Classify the query type as one of:
    - product_capability: What technical capabilities are required?
    - market_analysis: What are the market/regulatory requirements?
    - evidence_governance: Which source governs, current vs historical?
    - technical_deep_dive: Specific technical standard or requirement
    - broad_research: General research question requiring multiple sources
    """

    user_prompt = f"""
    Source type: {source_description}
    
    Heading path: {heading}
    
    Chunk text:
    {evidence}
    
    Generate ONE specific question that this chunk answers.
    Classify the query type appropriately.
    """

    try:
        output, usage = generate_structured_answer(
            instructions=instructions,
            user_prompt=user_prompt,
            output_type=QueryGenerationOutput,
            model="gemini-3.5-flash-lite",
            rate_limiter=rate_limiter,
            verbose=False,
        )

        query_id = f"q{hashlib.sha256((chunk['chunk_id'] + output.query).encode()).hexdigest()[:8]}"

        return {
            "query_id": query_id,
            "query_text": output.query,
            "query_type": output.query_type,
            "gold_chunk_id": chunk["chunk_id"],
            "gold_metadata": {
                "source_id": chunk["source_id"],
                "document_id": chunk["document_id"],
                "heading_path": chunk["heading_path"],
                "citation": chunk["citation"],
                "block_types": chunk["block_types"],
                "source_policy": chunk["source_policy"],
            },
            "generated_at": now_iso(),
            "llm_model": "gemini-3.5-flash-lite",
        }

    except Exception as error:
        print(f"Failed to generate query for {chunk['chunk_id']}: {error}")
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--chunks-dir",
        type=Path,
        default=ROOT / "data/processed/chunks",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data/evaluation/queries.jsonl",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
    )
    parser.add_argument(
        "--rate-limit-calls",
        type=int,
        default=10,
        help="Max LLM calls per window",
    )
    parser.add_argument(
        "--rate-limit-window",
        type=float,
        default=60.0,
        help="Rate limit window in seconds",
    )
    args = parser.parse_args()

    chunks_dir = absolute(args.chunks_dir)
    output_path = absolute(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    n_per_source = {
        "sce_rule21_tariff_pdf": 30,
        "sce_interconnection_handbook_pdf": 25,
        "cpuc_rule21_overview": 15,
        "sce_interconnection_web": 10,
        "sce_testing_certification_instruction_pdf": 10,
        "siwg_phase2_recommendations_pdf": 10,
    }

    sampled = sample_chunks(chunks_dir, n_per_source, seed=args.seed)
    print(f"Sampled {len(sampled)} chunks")

    rate_limiter = RateLimiter(
        max_calls=args.rate_limit_calls,
        window_seconds=args.rate_limit_window,
    )

    queries: list[dict[str, Any]] = []
    for i, chunk in enumerate(sampled, 1):
        print(f"Generating query {i}/{len(sampled)}: {chunk['chunk_id']}")

        query_record = generate_query_from_chunk_llm(chunk, rate_limiter)
        if query_record:
            queries.append(query_record)

            if i % 10 == 0:
                with output_path.open("a", encoding="utf-8") as f:
                    for query in queries[-10:]:
                        f.write(json.dumps(query) + "\n")
                print(f"Saved {len(queries)} queries so far...")

    # Rewrite full file to ensure consistency
    with output_path.open("w", encoding="utf-8") as f:
        for query in queries:
            f.write(json.dumps(query) + "\n")

    print(f"Generated {len(queries)} queries -> {output_path}")


if __name__ == "__main__":
    main()