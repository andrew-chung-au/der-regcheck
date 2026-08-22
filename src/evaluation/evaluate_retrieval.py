"""Evaluate multiple retrievers under multiple metadata weighting schemes, load queries from JSONL."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from transformers import AutoTokenizer, AutoModel
import torch

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "1.0"

WEIGHTING_SCHEMES = {
    "equal": {"source": 0.20, "section": 0.20, "page": 0.20, "block_type": 0.20, "authority": 0.20},
    "source_heavy": {"source": 0.40, "section": 0.20, "page": 0.15, "block_type": 0.15, "authority": 0.10},
    "section_heavy": {"source": 0.15, "section": 0.40, "page": 0.20, "block_type": 0.15, "authority": 0.10},
    "page_heavy": {"source": 0.15, "section": 0.20, "page": 0.40, "block_type": 0.15, "authority": 0.10},
    "authority_heavy": {"source": 0.10, "section": 0.20, "page": 0.20, "block_type": 0.20, "authority": 0.30},
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def absolute(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def cosine_similarity(a: list[float], b: list[float]) -> float:
    a_arr = np.array(a)
    b_arr = np.array(b)
    return float(np.dot(a_arr, b_arr) / (np.linalg.norm(a_arr) * np.linalg.norm(b_arr) + 1e-9))


def compute_metadata_score(retrieved: dict[str, Any], gold: dict[str, Any], weights: dict[str, float]) -> float:
    source_match = float(retrieved["source_id"] == gold["source_id"])

    retrieved_sections = set(retrieved.get("citation", {}).get("section_ids", []))
    gold_sections = set(gold["citation"].get("section_ids", []))
    section_match = float(bool(retrieved_sections & gold_sections))

    retrieved_page = retrieved.get("citation", {}).get("pdf_page_start", 0)
    gold_page = gold["citation"].get("pdf_page_start", 0)
    page_proximity = float(abs(retrieved_page - gold_page) <= 2)

    retrieved_types = set(retrieved.get("block_types", []))
    gold_types = set(gold.get("block_types", []))
    block_type_match = float(bool(retrieved_types & gold_types))

    retrieved_tier = retrieved.get("source_policy", {}).get("authority_tier", "")
    gold_tier = gold.get("source_policy", {}).get("authority_tier", "")
    authority_match = float(retrieved_tier == gold_tier)

    return (
        weights["source"] * source_match +
        weights["section"] * section_match +
        weights["page"] * page_proximity +
        weights["block_type"] * block_type_match +
        weights["authority"] * authority_match
    )


def dcg_at_k(scores: list[float], k: int) -> float:
    scores = scores[:k]
    return float(sum(s / math.log2(i + 2) for i, s in enumerate(scores)))


def ndcg_at_k(scores: list[float], k: int) -> float:
    ideal = sorted(scores, reverse=True)
    dcg = dcg_at_k(scores, k)
    idcg = dcg_at_k(ideal, k)
    return dcg / idcg if idcg > 0 else 0.0


def mrr(relevances: list[float]) -> float:
    for i, rel in enumerate(relevances):
        if rel > 0:
            return 1.0 / (i + 1)
    return 0.0


def recall_at_k(relevances: list[float], k: int, total_relevant: int) -> float:
    if total_relevant == 0:
        return 0.0
    relevant_in_top_k = sum(1 for rel in relevances[:k] if rel > 0)
    return relevant_in_top_k / total_relevant


def bm25_retrieve(
    query: str,
    chunks: list[dict[str, Any]],
    k: int = 20,
) -> list[dict[str, Any]]:
    """Simple BM25-like retrieval using token overlap."""
    query_tokens = set(query.lower().split())
    scored: list[tuple[dict[str, Any], float]] = []

    for chunk in chunks:
        text = chunk["evidence_text"].lower()
        tokens = set(text.split())
        overlap = len(query_tokens & tokens)
        score = overlap / (len(query_tokens) + len(tokens) + 1)
        scored.append((chunk, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return [chunk for chunk, _ in scored[:k]]


def vector_retrieve(
    query: str,
    query_embedding: list[float],
    chunks: list[dict[str, Any]],
    chunk_embeddings: list[list[float]],
    k: int = 20,
) -> list[dict[str, Any]]:
    """Retrieve by cosine similarity to query embedding."""
    scores = [cosine_similarity(query_embedding, emb) for emb in chunk_embeddings]
    indices = np.argsort(scores)[::-1][:k]
    return [chunks[i] for i in indices]


def hybrid_retrieve(
    query: str,
    query_embedding: list[float],
    chunks: list[dict[str, Any]],
    chunk_embeddings: list[list[float]],
    k: int = 20,
    alpha: float = 0.5,
) -> list[dict[str, Any]]:
    """Reciprocal Rank Fusion of BM25 and vector retrieval."""
    bm25_results = bm25_retrieve(query, chunks, k=50)
    vector_results = vector_retrieve(query, query_embedding, chunks, chunk_embeddings, k=50)

    bm25_ranks = {chunk["chunk_id"]: i + 1 for i, chunk in enumerate(bm25_results)}
    vector_ranks = {chunk["chunk_id"]: i + 1 for i, chunk in enumerate(vector_results)}

    all_chunks = {chunk["chunk_id"]: chunk for chunk in chunks}
    fusion_scores: list[tuple[str, float]] = []

    for chunk_id in set(bm25_ranks.keys()) | set(vector_ranks.keys()):
        bm25_rank = bm25_ranks.get(chunk_id, 60)
        vector_rank = vector_ranks.get(chunk_id, 60)
        score = alpha / (bm25_rank + 1) + (1 - alpha) / (vector_rank + 1)
        fusion_scores.append((chunk_id, score))

    fusion_scores.sort(key=lambda x: x[1], reverse=True)
    return [all_chunks[chunk_id] for chunk_id, _ in fusion_scores[:k]]


def load_all_chunks(chunks_dir: Path) -> tuple[list[dict[str, Any]], list[list[float]]]:
    """Load all chunks and their embeddings."""
    all_chunks: list[dict[str, Any]] = []
    all_embeddings: list[list[float]] = []

    for path in sorted(chunks_dir.glob("*.json")):
        if path.name in {"chunk_manifest.json", "chunk_quality_report.json"}:
            continue

        document = load_json(path)
        source_id = path.stem

        embeddings_file = Path(chunks_dir).parent / "embeddings" / f"{source_id}.jsonl"
        if not embeddings_file.exists():
            continue

        embeddings_data = load_jsonl(embeddings_file)
        chunk_map = {rec["chunk_id"]: rec["embedding"] for rec in embeddings_data}

        for chunk in document["chunks"]:
            if chunk["chunk_id"] in chunk_map:
                all_chunks.append(chunk)
                all_embeddings.append(chunk_map[chunk["chunk_id"]])

    return all_chunks, all_embeddings


def encode_query(query: str, model: AutoModel, tokenizer: AutoTokenizer, device: str) -> list[float]:
    """Encode a query with search_query: prefix."""
    prefixed = "search_query: " + query
    encoded = tokenizer(
        prefixed,
        padding=True,
        truncation=True,
        max_length=8192,
        return_tensors="pt",
    ).to(device)

    with torch.no_grad():
        outputs = model(**encoded)

    embedding = outputs.last_hidden_state[:, 0, :].cpu().tolist()[0]
    return embedding


def evaluate_query(
    query_record: dict[str, Any],
    chunks: list[dict[str, Any]],
    chunk_embeddings: list[list[float]],
    query_embedding: list[float],
) -> list[dict[str, Any]]:
    """Evaluate all retrievers and weightings for a single query."""
    query_text = query_record["query_text"]
    gold = query_record["gold_metadata"]

    results: list[dict[str, Any]] = []

    retrievers = {
        "bm25": lambda: bm25_retrieve(query_text, chunks, k=20),
        "vector": lambda: vector_retrieve(query_text, query_embedding, chunks, chunk_embeddings, k=20),
        "hybrid": lambda: hybrid_retrieve(query_text, query_embedding, chunks, chunk_embeddings, k=20),
    }

    for retriever_name, retrieve_fn in retrievers.items():
        retrieved = retrieve_fn()

        for weighting_name, weights in WEIGHTING_SCHEMES.items():
            scores = [compute_metadata_score(chunk, gold, weights) for chunk in retrieved]
            relevances = [float(s > 0.5) for s in scores]

            total_relevant = sum(1 for s in scores if s > 0.5)

            ndcg = ndcg_at_k(scores, 10)
            mrr_score = mrr(relevances)
            recall = recall_at_k(relevances, 10, total_relevant)

            results.append(
                {
                    "query_id": query_record["query_id"],
                    "retriever": retriever_name,
                    "weighting": weighting_name,
                    "ndcg_at_10": ndcg,
                    "mrr": mrr_score,
                    "recall_at_10": recall,
                    "retrieved_chunks": [chunk["chunk_id"] for chunk in retrieved],
                    "scores": scores,
                }
            )

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
    args = parser.parse_args()

    queries_path = absolute(args.queries)
    chunks_dir = absolute(args.chunks_dir)
    output_path = absolute(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Loading queries from {queries_path}...")
    queries = load_jsonl(queries_path)
    print(f"Loaded {len(queries)} queries")

    if not queries:
        print("No queries found. Run generate_synthetic_queries.py first.")
        return

    print("Loading chunks and embeddings...")
    chunks, chunk_embeddings = load_all_chunks(chunks_dir)
    print(f"Loaded {len(chunks)} chunks with embeddings")

    print("Loading Nomic model for query encoding...")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model_id = "nomic-ai/nomic-embed-text-v1.5"
    revision = "e9b6763023c676ca8431644204f50c2b100d9aab"

    tokenizer = AutoTokenizer.from_pretrained(model_id, revision=revision, trust_remote_code=True)
    model = AutoModel.from_pretrained(model_id, revision=revision, trust_remote_code=True).to(device)
    model.eval()

    print(f"Evaluating {len(queries)} queries...")

    all_results: list[dict[str, Any]] = []

    for i, query_record in enumerate(queries, 1):
        print(f"Query {i}/{len(queries)}: {query_record['query_id']}")

        try:
            query_embedding = encode_query(query_record["query_text"], model, tokenizer, device)
            results = evaluate_query(
                query_record,
                chunks,
                chunk_embeddings,
                query_embedding,
            )
            all_results.extend(results)

        except Exception as error:
            print(f"Failed to evaluate {query_record['query_id']}: {error}")

    print(f"Saving {len(all_results)} evaluation results to {output_path}...")
    with output_path.open("w", encoding="utf-8") as f:
        for result in all_results:
            f.write(json.dumps(result) + "\n")

    print(f"Evaluation complete: results saved to JSONL")


if __name__ == "__main__":
    main()