"""Summarise evaluation results across retrievers and weighting schemes."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def absolute(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


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

    summary: dict[str, Any] = {
        "total_queries_evaluated": len(results) // (3 * 5),
        "retrievers_evaluated": 3,
        "weighting_schemes_evaluated": 5,
        "per_configuration": {},
        "best_by_metric": {},
    }

    for key, metrics in grouped.items():
        retriever, weighting = key.split("__")
        summary["per_configuration"][key] = {
            "retriever": retriever,
            "weighting": weighting,
            "ndcg_at_10_mean": sum(metrics["ndcg"]) / len(metrics["ndcg"]),
            "ndcg_at_10_std": (sum((x - sum(metrics["ndcg"]) / len(metrics["ndcg"])) ** 2 for x in metrics["ndcg"]) / len(metrics["ndcg"])) ** 0.5,
            "mrr_mean": sum(metrics["mrr"]) / len(metrics["mrr"]),
            "recall_at_10_mean": sum(metrics["recall"]) / len(metrics["recall"]),
        }

    for metric in ["ndcg_at_10_mean", "mrr_mean", "recall_at_10_mean"]:
        best_key = max(summary["per_configuration"].keys(), key=lambda k: summary["per_configuration"][k][metric])
        summary["best_by_metric"][metric] = {
            "configuration": best_key,
            "value": summary["per_configuration"][best_key][metric],
        }

    output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Summary -> {output_path}")

    print("\n=== Results ===\n")
    print(f"Queries evaluated: {summary['total_queries_evaluated']}")
    print(f"Retrievers: {summary['retrievers_evaluated']}")
    print(f"Weighting schemes: {summary['weighting_schemes_evaluated']}\n")

    print("Per-configuration metrics:\n")
    for key, config in sorted(summary["per_configuration"].items()):
        print(f"{config['retriever']:8} | {config['weighting']:16} | "
              f"nDCG@10: {config['ndcg_at_10_mean']:.3f} ± {config['ndcg_at_10_std']:.3f} | "
              f"MRR: {config['mrr_mean']:.3f} | "
              f"Recall@10: {config['recall_at_10_mean']:.3f}")

    print("\n=== Best configurations ===\n")
    for metric, best in summary["best_by_metric"].items():
        print(f"{metric:16}: {best['configuration']} ({best['value']:.3f})")


if __name__ == "__main__":
    main()