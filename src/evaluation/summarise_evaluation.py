"""Summarise evaluation results across retrievers, weighting schemes, and RRF k.

Adds a composite score to break ties between configurations:
  composite = 0.5 * nDCG@10 + 0.3 * MRR + 0.2 * Recall@10

Handles retriever names like:
  - bm25, vector, hybrid, hybrid_rerank, vector_rerank
  - hybrid_rrf1, hybrid_rrf20, hybrid_rrf60, etc.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


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


def mean(values: list[float]) -> float:
    """Compute arithmetic mean."""
    return sum(values) / len(values)


def std_dev(values: list[float]) -> float:
    """Compute population standard deviation."""
    mu = mean(values)
    variance = sum((x - mu) ** 2 for x in values) / len(values)
    return math.sqrt(variance)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=ROOT / "data/evaluation/evaluation_results.jsonl",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data/evaluation/evaluation_summary.json",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=10,
        help="Number of top configurations to display in ranked tables.",
    )
    parser.add_argument(
        "--decimals",
        type=int,
        default=5,
        help="Number of decimal places to show in ranked tables.",
    )
    args = parser.parse_args()

    input_path = absolute(args.input)
    output_path = absolute(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    results = load_jsonl(input_path)
    print(f"Loaded {len(results)} evaluation results")

    grouped: dict[str, dict[str, list[float]]] = {}

    for result in results:
        key = f"{result['retriever']}__{result['weighting']}"
        if key not in grouped:
            grouped[key] = {"ndcg": [], "mrr": [], "recall": []}

        grouped[key]["ndcg"].append(result["ndcg_at_10"])
        grouped[key]["mrr"].append(result["mrr"])
        grouped[key]["recall"].append(result["recall_at_10"])

    # Infer counts from the data instead of hard-coding
    retrievers = {result["retriever"] for result in results}
    weightings = {result["weighting"] for result in results}

    num_retrievers = len(retrievers)
    num_weightings = len(weightings)
    approx_queries = len(results) // (num_retrievers * num_weightings) if (num_retrievers * num_weightings) > 0 else 0

    summary: dict[str, Any] = {
        "total_queries_evaluated": approx_queries,
        "retrievers_evaluated": num_retrievers,
        "weighting_schemes_evaluated": num_weightings,
        "per_configuration": {},
        "best_by_metric": {},
        "recommended_configuration": None,
    }

    for key, metrics in grouped.items():
        retriever, weighting = key.split("__", 1)
        ndcg_vals = metrics["ndcg"]
        mrr_vals = metrics["mrr"]
        recall_vals = metrics["recall"]

        ndcg_mean = mean(ndcg_vals)
        mrr_mean = mean(mrr_vals)
        recall_mean = mean(recall_vals)

        composite = 0.5 * ndcg_mean + 0.3 * mrr_mean + 0.2 * recall_mean

        summary["per_configuration"][key] = {
            "retriever": retriever,
            "weighting": weighting,
            "ndcg_at_10_mean": ndcg_mean,
            "ndcg_at_10_std": std_dev(ndcg_vals),
            "mrr_mean": mrr_mean,
            "recall_at_10_mean": recall_mean,
            "composite_score": composite,
        }

    # Best by individual metrics
    for metric in ["ndcg_at_10_mean", "mrr_mean", "recall_at_10_mean"]:
        best_key = max(
            summary["per_configuration"].keys(),
            key=lambda k: summary["per_configuration"][k][metric],
        )
        summary["best_by_metric"][metric] = {
            "configuration": best_key,
            "value": summary["per_configuration"][best_key][metric],
        }

    # Best by composite score
    best_composite_key = max(
        summary["per_configuration"].keys(),
        key=lambda k: summary["per_configuration"][k]["composite_score"],
    )
    summary["recommended_configuration"] = {
        "configuration": best_composite_key,
        "composite_score": summary["per_configuration"][best_composite_key]["composite_score"],
        "ndcg_at_10_mean": summary["per_configuration"][best_composite_key]["ndcg_at_10_mean"],
        "mrr_mean": summary["per_configuration"][best_composite_key]["mrr_mean"],
        "recall_at_10_mean": summary["per_configuration"][best_composite_key]["recall_at_10_mean"],
    }

    output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Summary -> {output_path}")

    print("\n=== Results ===\n")
    print(f"Queries evaluated: {summary['total_queries_evaluated']}")
    print(f"Retrievers: {summary['retrievers_evaluated']}")
    print(f"Weighting schemes: {summary['weighting_schemes_evaluated']}\n")

    top_n = args.top_n
    decimals = args.decimals

    def sorted_by_metric(metric: str):
        return sorted(
            summary["per_configuration"].items(),
            key=lambda item: item[1][metric],
            reverse=True,
        )

    for metric, label in [
        ("ndcg_at_10_mean", "nDCG@10"),
        ("mrr_mean", "MRR"),
        ("recall_at_10_mean", "Recall@10"),
        ("composite_score", "Composite (0.5·nDCG + 0.3·MRR + 0.2·Recall)"),
    ]:
        sorted_configs = sorted_by_metric(metric)
        print(f"=== Top {top_n} by {label} ===\n")
        print(f"{'Rank':>4} {'Configuration':<40} {'Mean':>{decimals + 3}}")
        header_width = 4 + 1 + 40 + 1 + decimals + 3
        print("-" * header_width)

        for rank, (key, cfg) in enumerate(sorted_configs[:top_n], start=1):
            retriever = cfg["retriever"]
            weighting = cfg["weighting"]
            config_str = f"{retriever}__{weighting}"
            mean_val = cfg[metric]
            print(f"{rank:>4} {config_str:<40} {mean_val:>{decimals + 3}.{decimals}f}")

        print()

    print("=== All configurations (alphabetical) ===\n")
    print(
        f"{'Retriever':<20} | {'Weighting':<16} | "
        f"nDCG@10          | MRR            | Recall@10      | Composite"
    )
    print("-" * 100)

    for key, config in sorted(summary["per_configuration"].items()):
        print(
            f"{config['retriever']:<20} | {config['weighting']:<16} | "
            f"{config['ndcg_at_10_mean']:>6.4f} ± {config['ndcg_at_10_std']:.4f} | "
            f"{config['mrr_mean']:>6.4f} | "
            f"{config['recall_at_10_mean']:>6.4f} | "
            f"{config['composite_score']:>9.5f}"
        )

    print("\n=== Best configurations ===\n")
    for metric, best in summary["best_by_metric"].items():
        print(f"{metric:16}: {best['configuration']} ({best['value']:.5f})")

    print("\n=== Recommended configuration (by composite score) ===\n")
    rec = summary["recommended_configuration"]
    print(f"Configuration     : {rec['configuration']}")
    print(f"Composite score   : {rec['composite_score']:.5f}")
    print(f"nDCG@10           : {rec['ndcg_at_10_mean']:.5f}")
    print(f"MRR               : {rec['mrr_mean']:.5f}")
    print(f"Recall@10         : {rec['recall_at_10_mean']:.5f}")


if __name__ == "__main__":
    main()