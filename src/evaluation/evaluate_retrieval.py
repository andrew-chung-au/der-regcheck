"""Evaluate the deployed PostgreSQL retrieval pipeline.

Modes:
  --mode retrieval (default)
    Evaluate lexical, vector, hybrid, hybrid_rerank, and vector_rerank
    across one or more hybrid alpha values and metadata weighting schemes.

  --mode rewrites-full
    Evaluate cached query variants (original, hyde, expanded, hyde_expanded)
    across selected deployed retrieval variants and metadata weighting schemes.

The evaluator uses:
- RuntimeRetriever.embed_query() for normalized Nomic query embeddings
- Retriever for PostgreSQL full-text, pgvector, and hybrid retrieval
- Reranker for the deployed cross-encoder reranking implementation

Results are checkpointed after each completed evaluation record.

Usage:
  uv run python -m src.evaluation.evaluate_retrieval --overwrite

  uv run python -m src.evaluation.evaluate_retrieval \
    --alphas 0.3,0.5,0.7 \
    --rerank-weightings equal \
    --overwrite

  uv run python -m src.evaluation.evaluate_retrieval \
    --mode rewrites-full \
    --rewrite-retrievers vector,hybrid,hybrid_rerank,vector_rerank \
    --overwrite
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import yaml

from src.database.db_connection import get_connection
from src.retrieval.rerank import Reranker
from src.retrieval.retrieve import Retriever
from src.retrieval.runtime_retriever import get_runtime_retriever


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "2.0"

DEFAULT_WEIGHTING_SCHEMES: dict[str, dict[str, float]] = {
    "equal": {
        "source": 0.20,
        "section": 0.20,
        "page": 0.20,
        "block_type": 0.20,
        "authority": 0.20,
    },
    "source_heavy": {
        "source": 0.40,
        "section": 0.20,
        "page": 0.15,
        "block_type": 0.15,
        "authority": 0.10,
    },
    "section_heavy": {
        "source": 0.15,
        "section": 0.40,
        "page": 0.20,
        "block_type": 0.15,
        "authority": 0.10,
    },
    "page_heavy": {
        "source": 0.15,
        "section": 0.20,
        "page": 0.40,
        "block_type": 0.15,
        "authority": 0.10,
    },
    "authority_heavy": {
        "source": 0.10,
        "section": 0.20,
        "page": 0.20,
        "block_type": 0.20,
        "authority": 0.30,
    },
}

RERANKED_RETRIEVERS = {"hybrid_rerank", "vector_rerank"}

RETRIEVAL_RETRIEVERS = (
    "lexical",
    "vector",
    "hybrid",
    "hybrid_rerank",
    "vector_rerank",
)

REWRITE_RETRIEVERS = {
    "vector",
    "hybrid",
    "hybrid_rerank",
    "vector_rerank",
}

REWRITE_TECHNIQUES = (
    "original",
    "hyde",
    "expanded",
    "hyde_expanded",
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load non-empty JSON Lines records."""
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def absolute(path: Path) -> Path:
    """Resolve a path relative to the project root if necessary."""
    return path if path.is_absolute() else ROOT / path


def append_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    """Append records to a JSONL checkpoint file."""
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("a", encoding="utf-8") as output:
        for record in records:
            output.write(json.dumps(record) + "\n")


def parse_csv(value: str) -> list[str]:
    """Parse a non-empty comma-separated list."""
    return [
        item.strip()
        for item in value.split(",")
        if item.strip()
    ]


def completed_retrieval_tuples(
    path: Path,
) -> set[tuple[str, float, str, str]]:
    """Return completed retrieval evaluation tuples."""
    if not path.exists():
        return set()

    completed: set[tuple[str, float, str, str]] = set()

    for record in load_jsonl(path):
        query_id = record.get("query_id")
        alpha = record.get("alpha")
        retriever = record.get("retriever")
        weighting = record.get("weighting")

        if all(
            value is not None
            for value in (query_id, alpha, retriever, weighting)
        ):
            completed.add(
                (
                    str(query_id),
                    float(alpha),
                    str(retriever),
                    str(weighting),
                )
            )

    return completed


def completed_rewrite_tuples(
    path: Path,
) -> set[tuple[str, str, str, str]]:
    """Return completed rewrite evaluation tuples."""
    if not path.exists():
        return set()

    completed: set[tuple[str, str, str, str]] = set()

    for record in load_jsonl(path):
        query_id = record.get("query_id")
        technique = record.get("technique")
        retriever = record.get("retriever")
        weighting = record.get("weighting")

        if all(
            value is not None
            for value in (query_id, technique, retriever, weighting)
        ):
            completed.add(
                (
                    str(query_id),
                    str(technique),
                    str(retriever),
                    str(weighting),
                )
            )

    return completed


def compute_metadata_score(
    retrieved: dict[str, Any],
    gold: dict[str, Any],
    weights: dict[str, float],
) -> float:
    """Score one retrieved chunk against source-derived gold metadata."""
    source_match = float(retrieved.get("source_id") == gold.get("source_id"))

    retrieved_sections = set(
        (retrieved.get("citation") or {}).get("section_ids") or []
    )
    gold_sections = set(
        (gold.get("citation") or {}).get("section_ids") or []
    )
    section_match = float(bool(retrieved_sections & gold_sections))

    retrieved_page = (
        retrieved.get("citation") or {}
    ).get("pdf_page_start")

    gold_page = (gold.get("citation") or {}).get("pdf_page_start")

    page_proximity = float(
        retrieved_page is not None
        and gold_page is not None
        and abs(int(retrieved_page) - int(gold_page)) <= 2
    )

    retrieved_types = set(retrieved.get("block_types") or [])
    gold_types = set(gold.get("block_types") or [])
    block_type_match = float(bool(retrieved_types & gold_types))

    retrieved_tier = (
        retrieved.get("source_policy") or {}
    ).get("authority_tier", "")

    gold_tier = (
        gold.get("source_policy") or {}
    ).get("authority_tier", "")

    authority_match = float(retrieved_tier == gold_tier)

    return (
        weights["source"] * source_match
        + weights["section"] * section_match
        + weights["page"] * page_proximity
        + weights["block_type"] * block_type_match
        + weights["authority"] * authority_match
    )


def dcg_at_k(scores: list[float], k: int) -> float:
    """Compute discounted cumulative gain at k."""
    return float(
        sum(
            score / math.log2(index + 2)
            for index, score in enumerate(scores[:k])
        )
    )


def ndcg_at_k(scores: list[float], k: int) -> float:
    """Compute normalised discounted cumulative gain at k."""
    dcg = dcg_at_k(scores, k)
    ideal_dcg = dcg_at_k(sorted(scores, reverse=True), k)

    return dcg / ideal_dcg if ideal_dcg > 0 else 0.0


def mrr(relevances: list[float]) -> float:
    """Compute reciprocal rank of the first relevant result."""
    for index, relevance in enumerate(relevances, start=1):
        if relevance > 0:
            return 1.0 / index

    return 0.0


def recall_at_k(
    relevances: list[float],
    k: int,
    total_relevant: int,
) -> float:
    """Compute recall at k against a corpus-level relevant total."""
    if total_relevant <= 0:
        return 0.0

    relevant_retrieved = sum(
        1 for relevance in relevances[:k] if relevance > 0
    )

    return relevant_retrieved / total_relevant


def calculate_metrics(
    retrieved: list[dict[str, Any]],
    gold: dict[str, Any],
    weights: dict[str, float],
    total_relevant: int,
) -> tuple[list[float], float, float, float]:
    """Calculate metadata scores, nDCG@10, MRR, and Recall@10."""
    scores = [
        compute_metadata_score(chunk, gold, weights)
        for chunk in retrieved
    ]

    relevances = [float(score > 0.5) for score in scores]

    return (
        scores,
        ndcg_at_k(scores, 10),
        mrr(relevances),
        recall_at_k(relevances, 10, total_relevant),
    )


def load_retrieval_config() -> dict[str, Any]:
    """Load and validate retrieval configuration."""
    defaults: dict[str, Any] = {
        "hybrid_alpha": 0.5,
        "weighting_schemes": DEFAULT_WEIGHTING_SCHEMES,
        "reranking": {
            "candidate_limit": 50,
            "top_k": 10,
            "max_tokens": 450,
            "batch_size": 16,
        },
    }

    path = ROOT / "config" / "retrieval.yaml"

    if not path.exists():
        return defaults

    loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    weighting_schemes = loaded.get(
        "weighting_schemes",
        DEFAULT_WEIGHTING_SCHEMES,
    )

    required_keys = set(DEFAULT_WEIGHTING_SCHEMES["equal"])

    for name, weights in weighting_schemes.items():
        missing = required_keys - set(weights)

        if missing:
            raise ValueError(
                f"Weighting scheme '{name}' is missing keys: {sorted(missing)}."
            )

        total = sum(float(weights[key]) for key in required_keys)

        if not math.isclose(total, 1.0, rel_tol=1e-9, abs_tol=1e-9):
            raise ValueError(
                f"Weighting scheme '{name}' must sum to 1.0; found {total}."
            )

    reranking = {
        **defaults["reranking"],
        **loaded.get("reranking", {}),
    }

    return {
        "hybrid_alpha": float(
            loaded.get("hybrid_alpha", defaults["hybrid_alpha"])
        ),
        "weighting_schemes": weighting_schemes,
        "reranking": reranking,
    }


def load_corpus_metadata() -> list[dict[str, Any]]:
    """Load the metadata fields needed for corpus-level relevance totals."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    source_id,
                    citation,
                    source_policy,
                    block_types
                FROM chunks
                """
            )

            rows = cursor.fetchall()

    columns = (
        "source_id",
        "citation",
        "source_policy",
        "block_types",
    )

    return [
        dict(zip(columns, row, strict=True))
        for row in rows
    ]


def count_relevant_corpus_chunks(
    corpus_metadata: list[dict[str, Any]],
    gold: dict[str, Any],
    weights: dict[str, float],
) -> int:
    """Count chunks relevant under the metadata scoring threshold."""
    return sum(
        compute_metadata_score(chunk, gold, weights) > 0.5
        for chunk in corpus_metadata
    )


def make_result(
    *,
    query_id: str,
    retriever: str,
    weighting: str,
    alpha: float | None,
    retrieved: list[dict[str, Any]],
    gold: dict[str, Any],
    weights: dict[str, float],
    total_relevant: int,
    technique: str | None = None,
) -> dict[str, Any]:
    """Create one serialisable evaluator result record."""
    scores, ndcg, mrr_score, recall = calculate_metrics(
        retrieved=retrieved,
        gold=gold,
        weights=weights,
        total_relevant=total_relevant,
    )

    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "retrieval_backend": "postgresql_fts_pgvector",
        "query_id": query_id,
        "retriever": retriever,
        "weighting": weighting,
        "alpha": alpha,
        "ndcg_at_10": ndcg,
        "mrr": mrr_score,
        "recall_at_10": recall,
        "total_relevant_corpus_chunks": total_relevant,
        "retrieved_chunks": [
            chunk["chunk_id"] for chunk in retrieved
        ],
        "scores": scores,
    }

    if technique is not None:
        result["technique"] = technique

    return result


def retrieve_variants(
    *,
    query_text: str,
    query_embedding: list[float],
    alpha: float,
    candidate_limit: int,
    rerank_top_k: int,
    rerank_max_tokens: int,
    rerank_batch_size: int,
    reranker: Reranker,
    include_lexical: bool,
) -> dict[str, list[dict[str, Any]]]:
    """Run deployed retrieval variants for one text query."""
    with get_connection() as conn:
        retriever = Retriever(conn)

        vector = retriever.search_vector(
            query_embedding=query_embedding,
            top_k=candidate_limit,
        )

        hybrid = retriever.search_hybrid(
            query=query_text,
            query_embedding=query_embedding,
            top_k=candidate_limit,
            alpha=alpha,
        )

        lexical = (
            retriever.search_lexical(
                query=query_text,
                top_k=candidate_limit,
            )
            if include_lexical
            else []
        )

    hybrid_rerank = reranker.rerank(
        query=query_text,
        chunks=hybrid,
        top_k=rerank_top_k,
        candidate_limit=candidate_limit,
        max_tokens=rerank_max_tokens,
        batch_size=rerank_batch_size,
    )

    vector_rerank = reranker.rerank(
        query=query_text,
        chunks=vector,
        top_k=rerank_top_k,
        candidate_limit=candidate_limit,
        max_tokens=rerank_max_tokens,
        batch_size=rerank_batch_size,
    )

    return {
        "lexical": lexical,
        "vector": vector,
        "hybrid": hybrid,
        "hybrid_rerank": hybrid_rerank,
        "vector_rerank": vector_rerank,
    }


def rewrite_variants(query_record: dict[str, Any]) -> dict[str, str]:
    """Build available cached query-rewrite variants for one query."""
    original = str(query_record.get("query_text", "")).strip()
    hyde = str(query_record.get("hyde") or "").strip()
    expanded = str(query_record.get("expanded") or "").strip()

    variants: dict[str, str] = {}

    if original:
        variants["original"] = original

    if hyde:
        variants["hyde"] = hyde

    if expanded:
        variants["expanded"] = expanded

    if hyde and expanded:
        variants["hyde_expanded"] = f"{hyde} {expanded}"

    return variants


def evaluate_retrieval_mode(
    *,
    queries: list[dict[str, Any]],
    output_path: Path,
    completed: set[tuple[str, float, str, str]],
    alphas: list[float],
    weighting_schemes: dict[str, dict[str, float]],
    rerank_weightings: list[str],
    rerank_only: bool,
    corpus_metadata: list[dict[str, Any]],
    candidate_limit: int,
    rerank_top_k: int,
    rerank_max_tokens: int,
    rerank_batch_size: int,
) -> None:
    """Evaluate original queries across deployed retrieval variants."""
    runtime_retriever = get_runtime_retriever()
    reranker = runtime_retriever.reranker

    retrievers = (
        ("hybrid_rerank", "vector_rerank")
        if rerank_only
        else RETRIEVAL_RETRIEVERS
    )

    for alpha in alphas:
        print(f"\nAlpha {alpha}")

        for index, query_record in enumerate(queries, start=1):
            query_id = str(query_record["query_id"])
            query_text = str(query_record.get("query_text", "")).strip()
            gold = query_record.get("gold_metadata")

            if not query_text or not gold:
                print(f"  {index}/{len(queries)} {query_id}: skipped.")
                continue

            pending: dict[str, list[str]] = {}

            for retriever_name in retrievers:
                weighting_names = (
                    rerank_weightings
                    if retriever_name in RERANKED_RETRIEVERS
                    else list(weighting_schemes)
                )

                pending[retriever_name] = [
                    weighting_name
                    for weighting_name in weighting_names
                    if (
                        query_id,
                        alpha,
                        retriever_name,
                        weighting_name,
                    ) not in completed
                ]

            if not any(pending.values()):
                print(f"  {index}/{len(queries)} {query_id}: already complete.")
                continue

            print(f"  {index}/{len(queries)} {query_id}")

            try:
                query_embedding = runtime_retriever.embed_query(query_text)

                retrievals = retrieve_variants(
                    query_text=query_text,
                    query_embedding=query_embedding,
                    alpha=alpha,
                    candidate_limit=candidate_limit,
                    rerank_top_k=rerank_top_k,
                    rerank_max_tokens=rerank_max_tokens,
                    rerank_batch_size=rerank_batch_size,
                    reranker=reranker,
                    include_lexical=not rerank_only,
                )

                records: list[dict[str, Any]] = []

                for retriever_name, weighting_names in pending.items():
                    for weighting_name in weighting_names:
                        weights = weighting_schemes[weighting_name]

                        total_relevant = count_relevant_corpus_chunks(
                            corpus_metadata=corpus_metadata,
                            gold=gold,
                            weights=weights,
                        )

                        record = make_result(
                            query_id=query_id,
                            retriever=retriever_name,
                            weighting=weighting_name,
                            alpha=alpha,
                            retrieved=retrievals[retriever_name],
                            gold=gold,
                            weights=weights,
                            total_relevant=total_relevant,
                        )

                        records.append(record)

                append_jsonl(output_path, records)

                for record in records:
                    completed.add(
                        (
                            record["query_id"],
                            float(record["alpha"]),
                            record["retriever"],
                            record["weighting"],
                        )
                    )

            except KeyboardInterrupt:
                print("\nInterrupted. Completed records are checkpointed.")
                raise

            except Exception as error:
                print(
                    f"  Failed {query_id}: "
                    f"{type(error).__name__}: {error}"
                )


def evaluate_rewrites_full_mode(
    *,
    rewrites: list[dict[str, Any]],
    output_path: Path,
    completed: set[tuple[str, str, str, str]],
    rewrite_retrievers: list[str],
    weighting_schemes: dict[str, dict[str, float]],
    alpha: float,
    corpus_metadata: list[dict[str, Any]],
    candidate_limit: int,
    rerank_top_k: int,
    rerank_max_tokens: int,
    rerank_batch_size: int,
) -> None:
    """Evaluate cached rewrite variants with deployed retrieval."""
    runtime_retriever = get_runtime_retriever()
    reranker = runtime_retriever.reranker

    for index, query_record in enumerate(rewrites, start=1):
        query_id = str(query_record["query_id"])
        gold = query_record.get("gold_metadata")
        variants = rewrite_variants(query_record)

        if not gold or not variants:
            print(f"  {index}/{len(rewrites)} {query_id}: skipped.")
            continue

        pending: dict[str, dict[str, list[str]]] = {}

        for technique, query_text in variants.items():
            pending[technique] = {}

            for retriever_name in rewrite_retrievers:
                pending[technique][retriever_name] = [
                    weighting_name
                    for weighting_name in weighting_schemes
                    if (
                        query_id,
                        technique,
                        retriever_name,
                        weighting_name,
                    ) not in completed
                ]

        if not any(
            weighting_names
            for retrievers in pending.values()
            for weighting_names in retrievers.values()
        ):
            print(f"  {index}/{len(rewrites)} {query_id}: already complete.")
            continue

        print(f"  {index}/{len(rewrites)} {query_id}")

        try:
            records: list[dict[str, Any]] = []

            for technique, query_text in variants.items():
                if not any(pending[technique].values()):
                    continue

                query_embedding = runtime_retriever.embed_query(query_text)

                retrievals = retrieve_variants(
                    query_text=query_text,
                    query_embedding=query_embedding,
                    alpha=alpha,
                    candidate_limit=candidate_limit,
                    rerank_top_k=rerank_top_k,
                    rerank_max_tokens=rerank_max_tokens,
                    rerank_batch_size=rerank_batch_size,
                    reranker=reranker,
                    include_lexical=False,
                )

                for retriever_name, weighting_names in (
                    pending[technique].items()
                ):
                    for weighting_name in weighting_names:
                        weights = weighting_schemes[weighting_name]

                        total_relevant = count_relevant_corpus_chunks(
                            corpus_metadata=corpus_metadata,
                            gold=gold,
                            weights=weights,
                        )

                        records.append(
                            make_result(
                                query_id=query_id,
                                retriever=(
                                    f"rewrite_{technique}_{retriever_name}"
                                ),
                                weighting=weighting_name,
                                alpha=None,
                                retrieved=retrievals[retriever_name],
                                gold=gold,
                                weights=weights,
                                total_relevant=total_relevant,
                                technique=technique,
                            )
                        )

            append_jsonl(output_path, records)

            for record in records:
                completed.add(
                    (
                        record["query_id"],
                        str(record["technique"]),
                        record["retriever"].removeprefix(
                            f"rewrite_{record['technique']}_"
                        ),
                        record["weighting"],
                    )
                )

        except KeyboardInterrupt:
            print("\nInterrupted. Completed records are checkpointed.")
            raise

        except Exception as error:
            print(
                f"  Failed {query_id}: "
                f"{type(error).__name__}: {error}"
            )


def main() -> None:
    """Parse arguments and run the requested evaluation mode."""
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "--mode",
        choices=("retrieval", "rewrites-full"),
        default="retrieval",
        help="Evaluation mode. Default: retrieval.",
    )

    parser.add_argument(
        "--queries",
        type=Path,
        default=ROOT / "data/evaluation/queries.jsonl",
        help="Fixed JSONL benchmark queries with gold_metadata.",
    )

    parser.add_argument(
        "--query-rewrites",
        type=Path,
        default=ROOT / "data/evaluation/query_rewrites.jsonl",
        help="Cached JSONL rewrite records for rewrites-full mode.",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data/evaluation/evaluation_results_postgres.jsonl",
        help="JSONL output path for retrieval mode.",
    )

    parser.add_argument(
        "--rewrite-output",
        type=Path,
        default=ROOT / "data/evaluation/query_rewrite_results_postgres.jsonl",
        help="JSONL output path for rewrites-full mode.",
    )

    parser.add_argument(
        "--alphas",
        type=str,
        default="0.3,0.5,0.7",
        help="Comma-separated lexical weights for hybrid RRF.",
    )

    parser.add_argument(
        "--rerank-weightings",
        type=str,
        default="equal",
        help="Comma-separated weightings for reranked retrieval methods.",
    )

    parser.add_argument(
        "--rerank-only",
        action="store_true",
        help="Evaluate only hybrid_rerank and vector_rerank.",
    )

    parser.add_argument(
        "--rewrite-retrievers",
        type=str,
        default="vector,hybrid,hybrid_rerank,vector_rerank",
        help="Comma-separated retrievers for rewrites-full mode.",
    )

    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume by skipping completed checkpoint records.",
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Delete this mode's target output file before starting.",
    )

    args = parser.parse_args()

    if args.resume and args.overwrite:
        parser.error("--resume and --overwrite cannot be used together.")

    alphas = [float(value) for value in parse_csv(args.alphas)]

    if not alphas:
        parser.error("--alphas must contain at least one value.")

    if any(alpha < 0.0 or alpha > 1.0 for alpha in alphas):
        parser.error("Each alpha must be between 0.0 and 1.0.")

    config = load_retrieval_config()
    weighting_schemes = config["weighting_schemes"]

    rerank_weightings = parse_csv(args.rerank_weightings)

    if not rerank_weightings:
        parser.error("--rerank-weightings must not be empty.")

    invalid_weightings = [
        name
        for name in rerank_weightings
        if name not in weighting_schemes
    ]

    if invalid_weightings:
        parser.error(
            "Unknown rerank weighting(s): "
            + ", ".join(invalid_weightings)
        )

    rewrite_retrievers = parse_csv(args.rewrite_retrievers)

    if not rewrite_retrievers:
        parser.error("--rewrite-retrievers must not be empty.")

    invalid_retrievers = [
        name
        for name in rewrite_retrievers
        if name not in REWRITE_RETRIEVERS
    ]

    if invalid_retrievers:
        parser.error(
            "Unknown rewrite retriever(s): "
            + ", ".join(invalid_retrievers)
        )

    queries_path = absolute(args.queries)
    output_path = absolute(args.output)
    rewrite_output_path = absolute(args.rewrite_output)
    query_rewrites_path = absolute(args.query_rewrites)

    reranking = config["reranking"]
    candidate_limit = int(reranking["candidate_limit"])
    rerank_top_k = int(reranking["top_k"])
    rerank_max_tokens = int(reranking["max_tokens"])
    rerank_batch_size = int(reranking["batch_size"])

    print("Loading corpus metadata from PostgreSQL...")
    corpus_metadata = load_corpus_metadata()
    print(f"Loaded metadata for {len(corpus_metadata)} chunks.")

    if not corpus_metadata:
        raise ValueError(
            "No chunks exist in PostgreSQL. Load the corpus before evaluation."
        )

    if args.mode == "retrieval":
        if args.overwrite:
            output_path.unlink(missing_ok=True)
            print(f"Removed existing output: {output_path}")

        completed = (
            completed_retrieval_tuples(output_path)
            if args.resume
            else set()
        )

        print(f"Loading queries from {queries_path}...")
        queries = load_jsonl(queries_path)
        print(f"Loaded {len(queries)} queries.")

        if not queries:
            raise ValueError("No retrieval evaluation queries were found.")

        print(
            "Mode: retrieval | "
            f"alphas={alphas} | "
            f"rerank_weightings={rerank_weightings} | "
            f"resume={args.resume}"
        )

        evaluate_retrieval_mode(
            queries=queries,
            output_path=output_path,
            completed=completed,
            alphas=alphas,
            weighting_schemes=weighting_schemes,
            rerank_weightings=rerank_weightings,
            rerank_only=args.rerank_only,
            corpus_metadata=corpus_metadata,
            candidate_limit=candidate_limit,
            rerank_top_k=rerank_top_k,
            rerank_max_tokens=rerank_max_tokens,
            rerank_batch_size=rerank_batch_size,
        )

        print(f"\nRetrieval evaluation complete: {output_path}")
        return

    if args.overwrite:
        rewrite_output_path.unlink(missing_ok=True)
        print(f"Removed existing output: {rewrite_output_path}")

    if not query_rewrites_path.exists():
        raise FileNotFoundError(
            "Cached rewrite file was not found: "
            f"{query_rewrites_path}"
        )

    completed = (
        completed_rewrite_tuples(rewrite_output_path)
        if args.resume
        else set()
    )

    print(f"Loading cached rewrites from {query_rewrites_path}...")
    rewrites = load_jsonl(query_rewrites_path)
    print(f"Loaded {len(rewrites)} rewrite records.")

    if not rewrites:
        raise ValueError("No cached rewrite records were found.")

    alpha = float(config["hybrid_alpha"])

    print(
        "Mode: rewrites-full | "
        f"alpha={alpha} | "
        f"retrievers={rewrite_retrievers} | "
        f"weightings={list(weighting_schemes)} | "
        f"resume={args.resume}"
    )

    evaluate_rewrites_full_mode(
        rewrites=rewrites,
        output_path=rewrite_output_path,
        completed=completed,
        rewrite_retrievers=rewrite_retrievers,
        weighting_schemes=weighting_schemes,
        alpha=alpha,
        corpus_metadata=corpus_metadata,
        candidate_limit=candidate_limit,
        rerank_top_k=rerank_top_k,
        rerank_max_tokens=rerank_max_tokens,
        rerank_batch_size=rerank_batch_size,
    )

    print(f"\nFull rewrite evaluation complete: {rewrite_output_path}")


if __name__ == "__main__":
    main()