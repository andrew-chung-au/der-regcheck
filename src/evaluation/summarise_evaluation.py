"""Summarise DER RegCheck retrieval-evaluation results.

Creates a JSON summary containing:
- mean and population-standard-deviation metrics per configuration;
- a composite ranking score;
- best configuration by nDCG@10, MRR, Recall@10, and composite score.

Composite score:
    0.5 * nDCG@10 + 0.3 * MRR + 0.2 * Recall@10

Supports both historical in-memory results and current PostgreSQL results.
For PostgreSQL retrieval evaluation, alpha is included in each configuration
because hybrid RRF behaviour changes with the lexical/vector balance.

Usage:
    uv run python -m src.evaluation.summarise_evaluation \
      --input data/evaluation/evaluation_results_postgres.jsonl \
      --output data/evaluation/evaluation_summary_postgres.json

    uv run python -m src.evaluation.summarise_evaluation \
      --input data/evaluation/query_rewrite_results_postgres.jsonl \
      --output data/evaluation/query_rewrite_summary_postgres.json
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]

COMPOSITE_WEIGHTS = {
    "ndcg_at_10": 0.5,
    "mrr": 0.3,
    "recall_at_10": 0.2,
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load non-empty JSON Lines records."""
    if not path.exists():
        raise FileNotFoundError(f"Evaluation results were not found: {path}")

    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def absolute(path: Path) -> Path:
    """Resolve a project-relative path."""
    return path if path.is_absolute() else ROOT / path


def mean(values: list[float]) -> float:
    """Compute an arithmetic mean."""
    if not values:
        raise ValueError("Cannot calculate a mean for an empty list.")

    return sum(values) / len(values)


def std_dev(values: list[float]) -> float:
    """Compute population standard deviation."""
    if not values:
        raise ValueError(
            "Cannot calculate standard deviation for an empty list."
        )

    average = mean(values)

    variance = sum(
        (value - average) ** 2
        for value in values
    ) / len(values)

    return math.sqrt(variance)


def display_alpha(alpha: float | None) -> str:
    """Format an optional RRF alpha for configuration labels."""
    return "n/a" if alpha is None else f"{float(alpha):.2f}"


def configuration_key(result: dict[str, Any]) -> str:
    """Build an alpha-aware grouping key for one result record."""
    technique = result.get("technique")
    retriever = str(result["retriever"])
    weighting = str(result["weighting"])
    alpha = result.get("alpha")

    parts: list[str] = []

    if technique:
        parts.append(f"technique={technique}")

    parts.extend(
        [
            f"retriever={retriever}",
            f"alpha={display_alpha(alpha)}",
            f"weighting={weighting}",
        ]
    )

    return " | ".join(parts)


def composite_score(
    ndcg_at_10: float,
    mrr_score: float,
    recall_at_10: float,
) -> float:
    """Calculate the documented composite configuration score."""
    return (
        COMPOSITE_WEIGHTS["ndcg_at_10"] * ndcg_at_10
        + COMPOSITE_WEIGHTS["mrr"] * mrr_score
        + COMPOSITE_WEIGHTS["recall_at_10"] * recall_at_10
    )


def validate_results(results: list[dict[str, Any]]) -> None:
    """Validate the minimum evaluator fields needed for aggregation."""
    if not results:
        raise ValueError("No evaluation records were found.")

    required_fields = {
        "query_id",
        "retriever",
        "weighting",
        "ndcg_at_10",
        "mrr",
        "recall_at_10",
    }

    available_fields = set().union(
        *(result.keys() for result in results)
    )

    missing_fields = required_fields - available_fields

    if missing_fields:
        raise ValueError(
            "Evaluation results are missing required fields: "
            f"{sorted(missing_fields)}"
        )


def build_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate evaluation records into configuration-level statistics."""
    validate_results(results)

    grouped: dict[str, dict[str, Any]] = {}

    for result in results:
        key = configuration_key(result)

        if key not in grouped:
            grouped[key] = {
                "query_ids": set(),
                "retriever": str(result["retriever"]),
                "technique": result.get("technique"),
                "alpha": result.get("alpha"),
                "weighting": str(result["weighting"]),
                "ndcg": [],
                "mrr": [],
                "recall": [],
            }

        grouped[key]["query_ids"].add(str(result["query_id"]))
        grouped[key]["ndcg"].append(float(result["ndcg_at_10"]))
        grouped[key]["mrr"].append(float(result["mrr"]))
        grouped[key]["recall"].append(float(result["recall_at_10"]))

    configurations: dict[str, dict[str, Any]] = {}

    for key, values in grouped.items():
        ndcg_mean = mean(values["ndcg"])
        mrr_mean = mean(values["mrr"])
        recall_mean = mean(values["recall"])

        configurations[key] = {
            "retriever": values["retriever"],
            "technique": values["technique"],
            "alpha": values["alpha"],
            "weighting": values["weighting"],
            "queries_evaluated": len(values["query_ids"]),
            "records_aggregated": len(values["ndcg"]),
            "ndcg_at_10_mean": ndcg_mean,
            "ndcg_at_10_std": std_dev(values["ndcg"]),
            "mrr_mean": mrr_mean,
            "mrr_std": std_dev(values["mrr"]),
            "recall_at_10_mean": recall_mean,
            "recall_at_10_std": std_dev(values["recall"]),
            "composite_score": composite_score(
                ndcg_at_10=ndcg_mean,
                mrr_score=mrr_mean,
                recall_at_10=recall_mean,
            ),
        }

    unique_query_ids = {
        str(result["query_id"])
        for result in results
    }

    return {
        "summary_schema_version": "2.0",
        "total_records": len(results),
        "total_unique_queries": len(unique_query_ids),
        "retrievers_evaluated": sorted(
            {str(result["retriever"]) for result in results}
        ),
        "weighting_schemes_evaluated": sorted(
            {str(result["weighting"]) for result in results}
        ),
        "alphas_evaluated": sorted(
            {
                float(result["alpha"])
                for result in results
                if result.get("alpha") is not None
            }
        ),
        "per_configuration": configurations,
        "best_by_metric": {},
        "recommended_configuration": None,
    }


def best_configuration(
    configurations: dict[str, dict[str, Any]],
    metric: str,
) -> tuple[str, dict[str, Any]]:
    """Return the best configuration with deterministic tie-breaking."""
    return max(
        configurations.items(),
        key=lambda item: (
            float(item[1][metric]),
            float(item[1]["ndcg_at_10_mean"]),
            float(item[1]["mrr_mean"]),
            item[0],
        ),
    )


def add_rankings(summary: dict[str, Any]) -> None:
    """Add best-by-metric and composite recommendation fields."""
    configurations = summary["per_configuration"]

    if not configurations:
        return

    metric_names = (
        "ndcg_at_10_mean",
        "mrr_mean",
        "recall_at_10_mean",
        "composite_score",
    )

    for metric in metric_names:
        key, values = best_configuration(configurations, metric)

        summary["best_by_metric"][metric] = {
            "configuration": key,
            "value": float(values[metric]),
        }

    best_key, best_values = best_configuration(
        configurations,
        "composite_score",
    )

    summary["recommended_configuration"] = {
        "configuration": best_key,
        "composite_score": float(best_values["composite_score"]),
        "ndcg_at_10_mean": float(best_values["ndcg_at_10_mean"]),
        "mrr_mean": float(best_values["mrr_mean"]),
        "recall_at_10_mean": float(
            best_values["recall_at_10_mean"]
        ),
    }


def sorted_configurations(
    summary: dict[str, Any],
    metric: str,
) -> list[tuple[str, dict[str, Any]]]:
    """Return configurations ordered by one metric."""
    return sorted(
        summary["per_configuration"].items(),
        key=lambda item: (
            -float(item[1][metric]),
            -float(item[1]["ndcg_at_10_mean"]),
            -float(item[1]["mrr_mean"]),
            item[0],
        ),
    )


def print_ranked_table(
    summary: dict[str, Any],
    metric: str,
    label: str,
    top_n: int,
    decimals: int,
) -> None:
    """Print a compact ranking table."""
    print(f"=== Top {top_n} by {label} ===\n")
    print(f"{'Rank':>4}  {'Configuration':<86}  {'Mean':>{decimals + 3}}")
    print("-" * (100 + decimals))

    for rank, (key, values) in enumerate(
        sorted_configurations(summary, metric)[:top_n],
        start=1,
    ):
        print(
            f"{rank:>4}  "
            f"{key:<86}  "
            f"{float(values[metric]):>{decimals + 3}.{decimals}f}"
        )

    print()


def print_all_configurations(summary: dict[str, Any]) -> None:
    """Print complete configuration metrics in alphabetical order."""
    print("=== All configurations (alphabetical) ===\n")

    print(
        f"{'Retriever':<34} | "
        f"{'Technique':<15} | "
        f"{'Alpha':<5} | "
        f"{'Weighting':<16} | "
        f"{'nDCG@10':<15} | "
        f"{'MRR':<15} | "
        f"{'Recall@10':<15} | "
        f"{'Composite':<9}"
    )

    print("-" * 165)

    for _, values in sorted(
        summary["per_configuration"].items()
    ):
        technique = values["technique"] or "n/a"

        print(
            f"{values['retriever']:<34} | "
            f"{technique:<15} | "
            f"{display_alpha(values['alpha']):<5} | "
            f"{values['weighting']:<16} | "
            f"{values['ndcg_at_10_mean']:.4f} +/- "
            f"{values['ndcg_at_10_std']:.4f} | "
            f"{values['mrr_mean']:.4f} +/- "
            f"{values['mrr_std']:.4f} | "
            f"{values['recall_at_10_mean']:.4f} +/- "
            f"{values['recall_at_10_std']:.4f} | "
            f"{values['composite_score']:.5f}"
        )

    print()


def print_summary(
    summary: dict[str, Any],
    top_n: int,
    decimals: int,
) -> None:
    """Print evaluation metadata, rankings, and recommendation."""
    print("\n=== Results ===\n")
    print(f"Unique queries evaluated: {summary['total_unique_queries']}")
    print(f"Evaluation records: {summary['total_records']}")
    print(
        "Retrievers: "
        + ", ".join(summary["retrievers_evaluated"])
    )
    print(
        "Weighting schemes: "
        + ", ".join(summary["weighting_schemes_evaluated"])
    )

    alphas = summary["alphas_evaluated"]

    if alphas:
        print(
            "Alphas: "
            + ", ".join(f"{alpha:.2f}" for alpha in alphas)
        )

    print()

    ranked_metrics = (
        ("ndcg_at_10_mean", "nDCG@10"),
        ("mrr_mean", "MRR"),
        ("recall_at_10_mean", "Recall@10"),
        (
            "composite_score",
            "Composite (0.5*nDCG + 0.3*MRR + 0.2*Recall)",
        ),
    )

    for metric, label in ranked_metrics:
        print_ranked_table(
            summary=summary,
            metric=metric,
            label=label,
            top_n=top_n,
            decimals=decimals,
        )

    print_all_configurations(summary)

    print("=== Best configurations ===\n")

    for metric, best in summary["best_by_metric"].items():
        print(
            f"{metric:<20}: "
            f"{best['configuration']} "
            f"({best['value']:.5f})"
        )

    recommendation = summary["recommended_configuration"]

    if recommendation is not None:
        print("\n=== Recommended configuration (composite score) ===\n")
        print(f"Configuration   : {recommendation['configuration']}")
        print(
            f"Composite score : "
            f"{recommendation['composite_score']:.5f}"
        )
        print(
            f"nDCG@10         : "
            f"{recommendation['ndcg_at_10_mean']:.5f}"
        )
        print(
            f"MRR             : "
            f"{recommendation['mrr_mean']:.5f}"
        )
        print(
            f"Recall@10       : "
            f"{recommendation['recall_at_10_mean']:.5f}"
        )


def main() -> None:
    """Load results, aggregate configurations, and write a JSON summary."""
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "--input",
        type=Path,
        default=ROOT / "data/evaluation/evaluation_results_postgres.jsonl",
        help="Input JSONL evaluator result file.",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data/evaluation/evaluation_summary_postgres.json",
        help="Output JSON summary file.",
    )

    parser.add_argument(
        "--top-n",
        type=int,
        default=10,
        help="Number of top configurations to show per metric.",
    )

    parser.add_argument(
        "--decimals",
        type=int,
        default=5,
        help="Number of decimal places in ranked tables.",
    )

    args = parser.parse_args()

    if args.top_n <= 0:
        parser.error("--top-n must be positive.")

    if args.decimals < 0:
        parser.error("--decimals must be zero or greater.")

    input_path = absolute(args.input)
    output_path = absolute(args.output)

    results = load_jsonl(input_path)
    summary = build_summary(results)
    add_rankings(summary)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )

    print(f"Loaded {len(results)} evaluation records.")
    print(f"Summary written to: {output_path}")

    print_summary(
        summary=summary,
        top_n=args.top_n,
        decimals=args.decimals,
    )


if __name__ == "__main__":
    main()