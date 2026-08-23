"""Evaluate retrieval, reranking, and cached query-rewrite variants.

The evaluator supports resumable JSONL checkpoints. Retrieval results are
checkpointed after each completed (query_id, alpha, retriever, weighting) tuple;
cached query-rewrite results are checkpointed after each completed query.

Modes:
  --mode retrieval (default):
    Evaluate bm25, vector, hybrid, hybrid_rerank, vector_rerank with
    configurable alphas and rerank weightings.

  --mode rewrites-full:
    Evaluate cached query rewrites (original, hyde, expanded, hyde_expanded)
    across multiple retrievers (vector, hybrid, hybrid_rerank, vector_rerank)
    and weighting schemes.

Flags:
  --alphas: comma-separated BM25 weights for hybrid retrieval.
  --rerank-weightings: weightings to use for reranked retrievers and rewrites.
  --rerank-only: skip bm25/vector/hybrid, only evaluate reranked retrievers.
  --rewrite-retrievers: which retrievers to use in rewrites-full mode.
  --resume / --overwrite: checkpoint control.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import torch
from sentence_transformers import CrossEncoder
from transformers import AutoModel, AutoTokenizer

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "1.0"

DEFAULT_WEIGHTING_SCHEMES = {
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

VALID_WEIGHTINGS = {
    "equal",
    "authority_heavy",
    "page_heavy",
    "section_heavy",
    "source_heavy",
}

VALID_REWRITE_RETRIEVERS = {
    "vector",
    "hybrid",
    "hybrid_rerank",
    "vector_rerank",
}


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON object from disk."""
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load JSON Lines records from disk."""
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def absolute(path: Path) -> Path:
    """Resolve a project-relative path."""
    return path if path.is_absolute() else ROOT / path


def append_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    """Append checkpoint records immediately to a JSONL file."""
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("a", encoding="utf-8") as output:
        for record in records:
            output.write(json.dumps(record) + "\n")
        output.flush()


def completed_query_alpha_retriever_weighting(
    path: Path,
) -> set[tuple[str, float, str, str]]:
    """Return completed (query_id, alpha, retriever, weighting) tuples."""
    if not path.exists():
        return set()

    completed: set[tuple[str, float, str, str]] = set()

    for record in load_jsonl(path):
        query_id = record.get("query_id")
        alpha = record.get("alpha")
        retriever = record.get("retriever")
        weighting = record.get("weighting")

        if all(v is not None for v in (query_id, alpha, retriever, weighting)):
            completed.add((str(query_id), float(alpha), str(retriever), str(weighting)))

    return completed


def completed_rewrite_query_ids(path: Path) -> set[str]:
    """Return query IDs for which all expected rewrite variants are present."""
    if not path.exists():
        return set()

    expected_techniques = {"original", "hyde", "expanded", "hyde_expanded"}
    techniques_by_query: dict[str, set[str]] = {}

    for record in load_jsonl(path):
        query_id = record.get("query_id")
        technique = record.get("technique")

        if query_id is not None and technique is not None:
            techniques_by_query.setdefault(str(query_id), set()).add(str(technique))

    return {
        query_id
        for query_id, techniques in techniques_by_query.items()
        if expected_techniques.issubset(techniques)
    }


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    a_arr = np.asarray(a, dtype=np.float32)
    b_arr = np.asarray(b, dtype=np.float32)

    denominator = np.linalg.norm(a_arr) * np.linalg.norm(b_arr) + 1e-9
    return float(np.dot(a_arr, b_arr) / denominator)


def compute_metadata_score(
    retrieved: dict[str, Any],
    gold: dict[str, Any],
    weights: dict[str, float],
) -> float:
    """Score one result against its query's source-derived gold metadata."""
    source_match = float(retrieved["source_id"] == gold["source_id"])

    retrieved_sections = set(retrieved.get("citation", {}).get("section_ids", []))
    gold_sections = set(gold.get("citation", {}).get("section_ids", []))
    section_match = float(bool(retrieved_sections & gold_sections))

    retrieved_page = retrieved.get("citation", {}).get("pdf_page_start", 0)
    gold_page = gold.get("citation", {}).get("pdf_page_start", 0)
    page_proximity = float(abs(retrieved_page - gold_page) <= 2)

    retrieved_types = set(retrieved.get("block_types", []))
    gold_types = set(gold.get("block_types", []))
    block_type_match = float(bool(retrieved_types & gold_types))

    retrieved_tier = retrieved.get("source_policy", {}).get("authority_tier", "")
    gold_tier = gold.get("source_policy", {}).get("authority_tier", "")
    authority_match = float(retrieved_tier == gold_tier)

    return (
        weights["source"] * source_match
        + weights["section"] * section_match
        + weights["page"] * page_proximity
        + weights["block_type"] * block_type_match
        + weights["authority"] * authority_match
    )


def dcg_at_k(scores: list[float], k: int) -> float:
    """Compute discounted cumulative gain."""
    return float(
        sum(score / math.log2(index + 2) for index, score in enumerate(scores[:k]))
    )


def ndcg_at_k(scores: list[float], k: int) -> float:
    """Compute normalised discounted cumulative gain."""
    dcg = dcg_at_k(scores, k)
    idcg = dcg_at_k(sorted(scores, reverse=True), k)
    return dcg / idcg if idcg > 0 else 0.0


def mrr(relevances: list[float]) -> float:
    """Compute mean reciprocal rank for a single query."""
    for index, relevance in enumerate(relevances):
        if relevance > 0:
            return 1.0 / (index + 1)
    return 0.0


def recall_at_k(relevances: list[float], k: int, total_relevant: int) -> float:
    """Compute recall at k for a single query."""
    if total_relevant == 0:
        return 0.0

    relevant_in_top_k = sum(1 for relevance in relevances[:k] if relevance > 0)
    return relevant_in_top_k / total_relevant


def load_retrieval_config() -> dict[str, Any]:
    """Load retrieval settings from config/retrieval.yaml."""
    config_path = ROOT / "config" / "retrieval.yaml"

    default_config: dict[str, Any] = {
        "hybrid_alpha": 0.5,
        "weighting_schemes": DEFAULT_WEIGHTING_SCHEMES,
        "reranking": {
            "candidate_limit": 50,
            "top_k": 10,
            "max_tokens": 450,
            "batch_size": 16,
        },
    }

    if not config_path.exists():
        return default_config

    import yaml

    loaded = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    weighting_schemes = loaded.get(
        "weighting_schemes",
        DEFAULT_WEIGHTING_SCHEMES,
    )

    expected_keys = set(DEFAULT_WEIGHTING_SCHEMES["equal"])

    for name, weights in weighting_schemes.items():
        missing_keys = expected_keys - set(weights)
        if missing_keys:
            raise ValueError(
                f"Weighting scheme '{name}' is missing keys: {sorted(missing_keys)}"
            )

        total = sum(weights[key] for key in expected_keys)
        if not math.isclose(total, 1.0, rel_tol=1e-9, abs_tol=1e-9):
            raise ValueError(
                f"Weighting scheme '{name}' must sum to 1.0; found {total}."
            )

    reranking = {
        **default_config["reranking"],
        **loaded.get("reranking", {}),
    }

    return {
        "hybrid_alpha": loaded.get("hybrid_alpha", default_config["hybrid_alpha"]),
        "weighting_schemes": weighting_schemes,
        "reranking": reranking,
    }


def bm25_retrieve(
    query: str,
    chunks: list[dict[str, Any]],
    k: int = 20,
) -> list[dict[str, Any]]:
    """Retrieve via a lightweight lexical-overlap baseline."""
    query_tokens = set(query.lower().split())
    scored: list[tuple[dict[str, Any], float]] = []

    for chunk in chunks:
        tokens = set(chunk["evidence_text"].lower().split())
        overlap = len(query_tokens & tokens)
        score = overlap / (len(query_tokens) + len(tokens) + 1)
        scored.append((chunk, score))

    scored.sort(key=lambda item: item[1], reverse=True)
    return [chunk for chunk, _ in scored[:k]]


def vector_retrieve(
    query_embedding: list[float],
    chunks: list[dict[str, Any]],
    chunk_embeddings: list[list[float]],
    k: int = 20,
) -> list[dict[str, Any]]:
    """Retrieve chunks by cosine similarity."""
    scores = [
        cosine_similarity(query_embedding, chunk_embedding)
        for chunk_embedding in chunk_embeddings
    ]
    indices = np.argsort(scores)[::-1][:k]
    return [chunks[index] for index in indices]


def hybrid_retrieve(
    query: str,
    query_embedding: list[float],
    chunks: list[dict[str, Any]],
    chunk_embeddings: list[list[float]],
    k: int = 20,
    alpha: float = 0.5,
    candidate_limit: int = 50,
) -> list[dict[str, Any]]:
    """Use weighted reciprocal-rank fusion of lexical and vector results.

    Alpha is the lexical/BM25 weight. An alpha of 0.0 gives only vector
    contribution, while 1.0 gives only lexical contribution.
    """
    bm25_results = bm25_retrieve(query, chunks, k=candidate_limit)
    vector_results = vector_retrieve(
        query_embedding,
        chunks,
        chunk_embeddings,
        k=candidate_limit,
    )

    bm25_ranks = {
        chunk["chunk_id"]: index + 1
        for index, chunk in enumerate(bm25_results)
    }
    vector_ranks = {
        chunk["chunk_id"]: index + 1
        for index, chunk in enumerate(vector_results)
    }
    all_chunks = {chunk["chunk_id"]: chunk for chunk in chunks}

    fusion_scores: list[tuple[str, float]] = []

    for chunk_id in set(bm25_ranks) | set(vector_ranks):
        bm25_rank = bm25_ranks.get(chunk_id, 60)
        vector_rank = vector_ranks.get(chunk_id, 60)

        score = (
            alpha / (bm25_rank + 1)
            + (1.0 - alpha) / (vector_rank + 1)
        )
        fusion_scores.append((chunk_id, score))

    fusion_scores.sort(key=lambda item: item[1], reverse=True)
    return [all_chunks[chunk_id] for chunk_id, _ in fusion_scores[:k]]


def rerank_candidates(
    query: str,
    candidates: list[dict[str, Any]],
    reranker: CrossEncoder,
    top_k: int = 10,
    candidate_limit: int = 50,
    max_tokens: int = 450,
    batch_size: int = 16,
) -> list[dict[str, Any]]:
    """Rerank candidate chunks with a shared loaded cross-encoder."""
    selected_candidates = candidates[:candidate_limit]

    pairs: list[tuple[str, str]] = []
    for chunk in selected_candidates:
        document_text = chunk.get(
            "embedding_text",
            chunk.get("evidence_text", ""),
        )
        pairs.append((query, document_text[:max_tokens]))

    if not pairs:
        return []

    scores = reranker.predict(
        pairs,
        batch_size=batch_size,
        show_progress_bar=False,
    )

    ranked = sorted(
        zip(selected_candidates, scores),
        key=lambda item: float(item[1]),
        reverse=True,
    )

    return [
        {**chunk, "reranker_score": float(score)}
        for chunk, score in ranked[:top_k]
    ]


def load_all_chunks(
    chunks_dir: Path,
) -> tuple[list[dict[str, Any]], list[list[float]]]:
    """Load all chunk records and stored embeddings."""
    all_chunks: list[dict[str, Any]] = []
    all_embeddings: list[list[float]] = []

    excluded_files = {
        "chunk_manifest.json",
        "chunking_manifest.json",
        "chunk_quality_report.json",
        "quality_report.json",
    }

    for path in sorted(chunks_dir.glob("*.json")):
        if path.name in excluded_files:
            continue

        document = load_json(path)
        source_id = path.stem
        embeddings_file = chunks_dir.parent / "embeddings" / f"{source_id}.jsonl"

        if not embeddings_file.exists():
            continue

        embeddings_data = load_jsonl(embeddings_file)
        chunk_to_embedding = {
            record["chunk_id"]: record["embedding"]
            for record in embeddings_data
        }

        for chunk in document["chunks"]:
            embedding = chunk_to_embedding.get(chunk["chunk_id"])
            if embedding is not None:
                all_chunks.append(chunk)
                all_embeddings.append(embedding)

    return all_chunks, all_embeddings


def encode_query(
    query: str,
    model: AutoModel,
    tokenizer: AutoTokenizer,
    device: str,
) -> list[float]:
    """Encode a query using Nomic's asymmetric query prefix."""
    encoded = tokenizer(
        f"search_query: {query}",
        padding=True,
        truncation=True,
        max_length=8192,
        return_tensors="pt",
    ).to(device)

    with torch.no_grad():
        outputs = model(**encoded)

    return outputs.last_hidden_state[:, 0, :].cpu().tolist()[0]


def calculate_metrics(
    retrieved: list[dict[str, Any]],
    gold: dict[str, Any],
    weights: dict[str, float],
) -> tuple[list[float], float, float, float]:
    """Calculate scores, nDCG@10, MRR, and Recall@10."""
    scores = [
        compute_metadata_score(chunk, gold, weights)
        for chunk in retrieved
    ]
    relevances = [float(score > 0.5) for score in scores]
    total_relevant = sum(1 for relevance in relevances if relevance > 0)

    return (
        scores,
        ndcg_at_k(scores, 10),
        mrr(relevances),
        recall_at_k(relevances, 10, total_relevant),
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
) -> dict[str, Any]:
    """Create one serialisable evaluation record."""
    scores, ndcg, mrr_score, recall = calculate_metrics(
        retrieved,
        gold,
        weights,
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "query_id": query_id,
        "retriever": retriever,
        "weighting": weighting,
        "alpha": alpha,
        "ndcg_at_10": ndcg,
        "mrr": mrr_score,
        "recall_at_10": recall,
        "retrieved_chunks": [chunk["chunk_id"] for chunk in retrieved],
        "scores": scores,
    }


def evaluate_query(
    query_record: dict[str, Any],
    chunks: list[dict[str, Any]],
    chunk_embeddings: list[list[float]],
    query_embedding: list[float],
    config: dict[str, Any],
    reranker: CrossEncoder,
) -> list[dict[str, Any]]:
    """Evaluate lexical, vector, hybrid, and reranked retrievers for one query."""
    query_id = query_record["query_id"]
    query_text = query_record["query_text"]
    gold = query_record["gold_metadata"]

    alpha = float(config["hybrid_alpha"])
    weighting_schemes = config["weighting_schemes"]
    rerank_config = config["reranking"]
    rerank_weightings = config.get("rerank_weightings", ["equal"])
    rerank_only = bool(config.get("rerank_only", False))

    candidate_limit = int(rerank_config["candidate_limit"])
    first_stage_k = max(20, candidate_limit)

    bm25_results = bm25_retrieve(query_text, chunks, k=first_stage_k)

    vector_results = vector_retrieve(
        query_embedding,
        chunks,
        chunk_embeddings,
        k=first_stage_k,
    )

    hybrid_results = hybrid_retrieve(
        query_text,
        query_embedding,
        chunks,
        chunk_embeddings,
        k=first_stage_k,
        alpha=alpha,
        candidate_limit=candidate_limit,
    )

    results: list[dict[str, Any]] = []

    if not rerank_only:
        for retriever_name, retrieved in {
            "bm25": bm25_results,
            "vector": vector_results,
            "hybrid": hybrid_results,
        }.items():
            for weighting_name, weights in weighting_schemes.items():
                results.append(
                    make_result(
                        query_id=query_id,
                        retriever=retriever_name,
                        weighting=weighting_name,
                        alpha=alpha,
                        retrieved=retrieved,
                        gold=gold,
                        weights=weights,
                    )
                )

    equal_weights = weighting_schemes["equal"]

    hybrid_reranked = rerank_candidates(
        query_text,
        hybrid_results,
        reranker,
        top_k=int(rerank_config["top_k"]),
        candidate_limit=candidate_limit,
        max_tokens=int(rerank_config["max_tokens"]),
        batch_size=int(rerank_config["batch_size"]),
    )

    for weighting_name in rerank_weightings:
        weights = weighting_schemes[weighting_name]
        results.append(
            make_result(
                query_id=query_id,
                retriever="hybrid_rerank",
                weighting=weighting_name,
                alpha=alpha,
                retrieved=hybrid_reranked,
                gold=gold,
                weights=weights,
            )
        )

    vector_reranked = rerank_candidates(
        query_text,
        vector_results,
        reranker,
        top_k=int(rerank_config["top_k"]),
        candidate_limit=candidate_limit,
        max_tokens=int(rerank_config["max_tokens"]),
        batch_size=int(rerank_config["batch_size"]),
    )

    for weighting_name in rerank_weightings:
        weights = weighting_schemes[weighting_name]
        results.append(
            make_result(
                query_id=query_id,
                retriever="vector_rerank",
                weighting=weighting_name,
                alpha=alpha,
                retrieved=vector_reranked,
                gold=gold,
                weights=weights,
            )
        )

    return results


def evaluate_query_rewrite(
    query_record: dict[str, Any],
    chunks: list[dict[str, Any]],
    chunk_embeddings: list[list[float]],
    model: AutoModel,
    tokenizer: AutoTokenizer,
    device: str,
    equal_weights: dict[str, float],
) -> list[dict[str, Any]]:
    """Evaluate cached original, HyDE, expansion, and combined vector variants."""
    gold = query_record.get("gold_metadata")
    if gold is None:
        return []

    query_id = query_record["query_id"]
    original = query_record.get("query_text", "")
    hyde = query_record.get("hyde")
    expanded = query_record.get("expanded")

    variants: dict[str, str] = {"original": original}

    if hyde:
        variants["hyde"] = hyde

    if expanded:
        variants["expanded"] = expanded

    if hyde and expanded:
        variants["hyde_expanded"] = f"{hyde} {expanded}"

    results: list[dict[str, Any]] = []

    for technique, text in variants.items():
        embedding = encode_query(text, model, tokenizer, device)

        retrieved = vector_retrieve(
            embedding,
            chunks,
            chunk_embeddings,
            k=10,
        )

        result = make_result(
            query_id=query_id,
            retriever=f"rewrite_{technique}",
            weighting="equal",
            alpha=None,
            retrieved=retrieved,
            gold=gold,
            weights=equal_weights,
        )
        result["technique"] = technique
        results.append(result)

    return results


def evaluate_query_rewrite_full(
    query_record: dict[str, Any],
    chunks: list[dict[str, Any]],
    chunk_embeddings: list[list[float]],
    model: AutoModel,
    tokenizer: AutoTokenizer,
    device: str,
    config: dict[str, Any],
    reranker: CrossEncoder,
) -> list[dict[str, Any]]:
    """Evaluate cached rewrite variants across multiple retrievers and weightings."""
    gold = query_record.get("gold_metadata")
    if gold is None:
        return []

    query_id = query_record["query_id"]
    original = query_record.get("query_text", "")
    hyde = query_record.get("hyde")
    expanded = query_record.get("expanded")

    variants: dict[str, str] = {"original": original}

    if hyde:
        variants["hyde"] = hyde

    if expanded:
        variants["expanded"] = expanded

    if hyde and expanded:
        variants["hyde_expanded"] = f"{hyde} {expanded}"

    weighting_schemes = config["weighting_schemes"]
    rerank_config = config["reranking"]
    rewrite_retrievers = config.get("rewrite_retrievers", ["vector"])
    candidate_limit = int(rerank_config["candidate_limit"])
    first_stage_k = max(20, candidate_limit)
    alpha = float(config["hybrid_alpha"])

    results: list[dict[str, Any]] = []

    for technique, text in variants.items():
        embedding = encode_query(text, model, tokenizer, device)

        # Pre-compute retrievals that can be reused across weightings
        vector_results = vector_retrieve(
            embedding,
            chunks,
            chunk_embeddings,
            k=first_stage_k,
        )

        hybrid_results = hybrid_retrieve(
            text,
            embedding,
            chunks,
            chunk_embeddings,
            k=first_stage_k,
            alpha=alpha,
            candidate_limit=candidate_limit,
        )

        hybrid_reranked = rerank_candidates(
            text,
            hybrid_results,
            reranker,
            top_k=int(rerank_config["top_k"]),
            candidate_limit=candidate_limit,
            max_tokens=int(rerank_config["max_tokens"]),
            batch_size=int(rerank_config["batch_size"]),
        )

        vector_reranked = rerank_candidates(
            text,
            vector_results,
            reranker,
            top_k=int(rerank_config["top_k"]),
            candidate_limit=candidate_limit,
            max_tokens=int(rerank_config["max_tokens"]),
            batch_size=int(rerank_config["batch_size"]),
        )

        retrieval_map = {
            "vector": vector_results,
            "hybrid": hybrid_results,
            "hybrid_rerank": hybrid_reranked,
            "vector_rerank": vector_reranked,
        }

        for retriever in rewrite_retrievers:
            retrieved = retrieval_map[retriever]

            for weighting_name, weights in weighting_schemes.items():
                result = make_result(
                    query_id=query_id,
                    retriever=f"rewrite_{technique}_{retriever}",
                    weighting=weighting_name,
                    alpha=None,
                    retrieved=retrieved,
                    gold=gold,
                    weights=weights,
                )
                result["technique"] = technique
                results.append(result)

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "--queries",
        type=Path,
        default=ROOT / "data/evaluation/queries.jsonl",
    )
    parser.add_argument(
        "--chunks-dir",
        type=Path,
        default=ROOT / "data/processed/chunks",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data/evaluation/evaluation_results.jsonl",
    )
    parser.add_argument(
        "--alphas",
        type=str,
        default="0.3,0.5,0.7",
        help="Comma-separated BM25 weights for hybrid retrieval.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from JSONL checkpoints, skipping completed queries.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Delete existing result files before starting.",
    )
    parser.add_argument(
        "--rerank-weightings",
        type=str,
        default="equal",
        help=(
            "Comma-separated weighting schemes to evaluate for reranked retrievers "
            "and for rewrites-full mode. "
            f"Options: {', '.join(sorted(VALID_WEIGHTINGS))}. Default: equal"
        ),
    )
    parser.add_argument(
        "--rerank-only",
        action="store_true",
        help=(
            "Skip non-reranked retrievers (bm25, vector, hybrid) and only evaluate "
            "hybrid_rerank and vector_rerank for the specified --rerank-weightings."
        ),
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="retrieval",
        choices=["retrieval", "rewrites-full"],
        help=(
            "Which evaluation to run: "
            "'retrieval' (default) or 'rewrites-full' (full rewrite × retriever × weighting)."
        ),
    )
    parser.add_argument(
        "--rewrite-retrievers",
        type=str,
        default="vector,hybrid,hybrid_rerank,vector_rerank",
        help=(
            "Comma-separated retrievers to evaluate for rewrites in rewrites-full mode. "
            f"Options: {', '.join(sorted(VALID_REWRITE_RETRIEVERS))}. "
            "Default: all four."
        ),
    )

    args = parser.parse_args()

    if args.resume and args.overwrite:
        parser.error("--resume and --overwrite cannot be used together.")

    queries_path = absolute(args.queries)
    chunks_dir = absolute(args.chunks_dir)
    output_path = absolute(args.output)
    rewrite_output_path = output_path.parent / "query_rewrite_results.jsonl"

    alphas = [float(value.strip()) for value in args.alphas.split(",")]

    if any(alpha < 0.0 or alpha > 1.0 for alpha in alphas):
        raise ValueError("Each alpha must be between 0.0 and 1.0.")

    rerank_weightings = [
        w.strip() for w in args.rerank_weightings.split(",")
    ]

    if any(w not in VALID_WEIGHTINGS for w in rerank_weightings):
        parser.error(
            f"--rerank-weightings must be a comma-separated subset of "
            f"{sorted(VALID_WEIGHTINGS)}; got {rerank_weightings}"
        )

    rewrite_retrievers = [
        r.strip() for r in args.rewrite_retrievers.split(",")
    ]

    if any(r not in VALID_REWRITE_RETRIEVERS for r in rewrite_retrievers):
        parser.error(
            f"--rewrite-retrievers must be a comma-separated subset of "
            f"{sorted(VALID_REWRITE_RETRIEVERS)}; got {rewrite_retrievers}"
        )

    if args.overwrite:
        output_path.unlink(missing_ok=True)
        rewrite_output_path.unlink(missing_ok=True)
        print("Removed existing evaluation result files.")

    # Use fine-grained checkpointing: (query_id, alpha, retriever, weighting)
    if args.resume:
        completed_tuples = completed_query_alpha_retriever_weighting(output_path)
        completed_rewrites = completed_rewrite_query_ids(rewrite_output_path)
    else:
        completed_tuples = set()
        completed_rewrites = set()

    print(f"Loading queries from {queries_path}...")
    queries = load_jsonl(queries_path)
    print(f"Loaded {len(queries)} queries")

    if not queries:
        raise ValueError(
            "No queries found. Run generate_synthetic_queries.py first."
        )

    print("Loading chunks and embeddings...")
    chunks, chunk_embeddings = load_all_chunks(chunks_dir)
    print(f"Loaded {len(chunks)} chunks with embeddings")

    if not chunks:
        raise ValueError("No chunks with embeddings were loaded.")

    print("Loading Nomic model for query encoding...")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model_id = "nomic-ai/nomic-embed-text-v1.5"
    revision = "e9b6763023c676ca8431644204f50c2b100d9aab"

    tokenizer = AutoTokenizer.from_pretrained(
        model_id,
        revision=revision,
        trust_remote_code=True,
    )
    model = AutoModel.from_pretrained(
        model_id,
        revision=revision,
        trust_remote_code=True,
    ).to(device)
    model.eval()

    print("Loading cross-encoder reranker once...")
    reranker = CrossEncoder("BAAI/bge-reranker-base")

    config = load_retrieval_config()
    config["rerank_weightings"] = rerank_weightings
    config["rerank_only"] = args.rerank_only
    config["mode"] = args.mode
    config["rewrite_retrievers"] = rewrite_retrievers

    if args.mode == "rewrites-full":
        print(
            f"Mode: rewrites-full. "
            f"Queries: {len(queries)}. "
            f"Rewrite retrievers: {rewrite_retrievers}. "
            f"Weightings: {rerank_weightings}."
        )

        query_rewrites_path = ROOT / "data/evaluation/query_rewrites.jsonl"

        if not query_rewrites_path.exists():
            print("No cached query-rewrite file found; skipping rewrite evaluation.")
            return

        print(f"\nLoading cached rewrites from {query_rewrites_path}...")
        rewrites = load_jsonl(query_rewrites_path)

        print(
            f"Full rewrite evaluation: "
            f"{len(rewrites)} queries × {len(rewrite_retrievers)} retrievers × "
            f"{len(rerank_weightings)} weightings."
        )

        for index, rewrite in enumerate(rewrites, start=1):
            query_id = rewrite["query_id"]
            print(f"Rewrite {index}/{len(rewrites)}: {query_id}")

            try:
                results = evaluate_query_rewrite_full(
                    rewrite,
                    chunks,
                    chunk_embeddings,
                    model,
                    tokenizer,
                    device,
                    config,
                    reranker,
                )

                append_jsonl(rewrite_output_path, results)

            except KeyboardInterrupt:
                print("\nInterrupted. Completed rewrite results are checkpointed.")
                raise

            except Exception as error:
                print(
                    f"Failed to evaluate rewrite {query_id}: "
                    f"{type(error).__name__}: {error}"
                )

        print("Full query-rewrite evaluation complete.")
        return

    # Default mode: retrieval evaluation
    print(
        f"Mode: retrieval. "
        f"Resume: {args.resume}. "
        f"Completed (query, alpha, retriever, weighting) tuples: {len(completed_tuples)}. "
        f"Rerank weightings: {rerank_weightings}. "
        f"Rerank-only: {args.rerank_only}."
    )

    # Build the set of tuples we expect to produce for each (query_id, alpha)
    all_retrievers = (
        ["hybrid_rerank", "vector_rerank"]
        if args.rerank_only
        else ["bm25", "vector", "hybrid", "hybrid_rerank", "vector_rerank"]
    )

    for alpha in alphas:
        config["hybrid_alpha"] = alpha

        pending_work: list[dict[str, Any]] = []

        for query_record in queries:
            query_id = query_record["query_id"]

            for retriever in all_retrievers:
                if retriever in {"hybrid_rerank", "vector_rerank"}:
                    weightings_to_check = rerank_weightings
                else:
                    weightings_to_check = list(config["weighting_schemes"].keys())

                for weighting in weightings_to_check:
                    tup = (query_id, alpha, retriever, weighting)
                    if tup not in completed_tuples:
                        pending_work.append(
                            {
                                "query": query_record,
                                "retriever": retriever,
                                "weighting": weighting,
                            }
                        )

        if not pending_work:
            print(
                f"\nAlpha {alpha}: all retriever/weighting combinations already complete."
            )
            continue

        # Group pending work by query to avoid re-encoding and re-retrieving
        pending_by_query: dict[str, dict[str, Any]] = {}
        for item in pending_work:
            qid = item["query"]["query_id"]
            if qid not in pending_by_query:
                pending_by_query[qid] = {
                    "query": item["query"],
                    "needed_retrievers": set(),
                    "needed_weightings_for_retriever": {},
                }
            pending_by_query[qid]["needed_retrievers"].add(item["retriever"])
            pending_by_query[qid]["needed_weightings_for_retriever"].setdefault(
                item["retriever"], set()
            ).add(item["weighting"])

        print("\n" + "=" * 80)
        print(
            f"Alpha {alpha}: {len(pending_by_query)} queries with pending work."
        )
        print("=" * 80)

        for index, (query_id, pending_item) in enumerate(pending_by_query.items(), start=1):
            query_record = pending_item["query"]
            needed_retrievers = pending_item["needed_retrievers"]

            print(
                f"Alpha {alpha} | query {index}/{len(pending_by_query)} | {query_id} | "
                f"needed: {sorted(needed_retrievers)}"
            )

            try:
                query_embedding = encode_query(
                    query_record["query_text"],
                    model,
                    tokenizer,
                    device,
                )

                results = evaluate_query(
                    query_record,
                    chunks,
                    chunk_embeddings,
                    query_embedding,
                    config,
                    reranker,
                )

                # Filter results to only those tuples that were actually pending
                filtered_results = []
                for res in results:
                    tup = (
                        res["query_id"],
                        alpha,
                        res["retriever"],
                        res["weighting"],
                    )
                    if tup not in completed_tuples:
                        filtered_results.append(res)
                        completed_tuples.add(tup)

                if filtered_results:
                    append_jsonl(output_path, filtered_results)

            except KeyboardInterrupt:
                print("\nInterrupted. Completed results are already checkpointed.")
                raise

            except Exception as error:
                print(
                    f"Failed to evaluate {query_id}: "
                    f"{type(error).__name__}: {error}"
                )

    print("\nRetrieval evaluation complete.")

    # Optional narrow rewrite evaluation (kept for backward compatibility)
    query_rewrites_path = ROOT / "data/evaluation/query_rewrites.jsonl"

    if not query_rewrites_path.exists():
        print("No cached query-rewrite file found; skipping rewrite evaluation.")
        return

    print(f"\nLoading cached rewrites from {query_rewrites_path}...")
    rewrites = load_jsonl(query_rewrites_path)
    equal_weights = config["weighting_schemes"]["equal"]

    pending_rewrites = [
        rewrite
        for rewrite in rewrites
        if rewrite["query_id"] not in completed_rewrites
    ]

    print(
        f"Rewrite evaluation: {len(pending_rewrites)} pending; "
        f"{len(rewrites) - len(pending_rewrites)} already complete."
    )

    for index, rewrite in enumerate(pending_rewrites, start=1):
        query_id = rewrite["query_id"]

        print(f"Rewrite {index}/{len(pending_rewrites)}: {query_id}")

        try:
            results = evaluate_query_rewrite(
                rewrite,
                chunks,
                chunk_embeddings,
                model,
                tokenizer,
                device,
                equal_weights,
            )

            append_jsonl(rewrite_output_path, results)
            completed_rewrites.add(query_id)

        except KeyboardInterrupt:
            print("\nInterrupted. Completed rewrite results are checkpointed.")
            raise

        except Exception as error:
            print(
                f"Failed to evaluate rewrite {query_id}: "
                f"{type(error).__name__}: {error}"
            )

    print("Query-rewrite evaluation complete.")


if __name__ == "__main__":
    main()