"""Summarise LLM evaluation results and select the best prompt configuration.

This script aggregates judge scores by prompt version, applies the citation-validity
guardrail, and produces a markdown report with tables and rationale.

Usage:
    uv run python -m src.evaluation.summarise_llm_evaluation \
      --answers data/evaluation/llm_answers.jsonl \
      --judge-scores data/evaluation/llm_judge_scores.jsonl \
      --output data/evaluation/llm_evaluation_summary.json

    uv run python -m src.evaluation.summarise_llm_evaluation \
      --answers data/evaluation/llm_answers.jsonl \
      --judge-scores data/evaluation/llm_judge_scores.jsonl \
      --output data/evaluation/llm_evaluation_summary.json \
      --report data/evaluation/llm_evaluation_report.md
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "1.0"


@dataclass
class PromptSummary:
    """Aggregated metrics for one prompt version."""

    prompt_version: str
    total_answers: int
    citation_valid_count: int
    citation_valid_rate: float
    mean_groundedness: float
    mean_relevance: float
    mean_completeness: float
    mean_citation_quality: float
    mean_uncertainty: float
    mean_composite: float
    std_composite: float
    best_composite: float
    worst_composite: float


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load non-empty JSON Lines records."""
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def now_iso() -> str:
    """Return current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def mean(values: list[float]) -> float:
    """Compute arithmetic mean."""
    if not values:
        return 0.0
    return sum(values) / len(values)


def std_dev(values: list[float]) -> float:
    """Compute population standard deviation."""
    if len(values) < 2:
        return 0.0
    avg = mean(values)
    variance = sum((v - avg) ** 2 for v in values) / len(values)
    return variance ** 0.5


def compute_summary(
    answers: list[dict[str, Any]],
    judge_scores: list[dict[str, Any]],
    prompt_version: str,
) -> PromptSummary:
    """Compute aggregated metrics for one prompt version."""
    # Filter answers for this prompt version
    prompt_answers = [a for a in answers if a["prompt_version"] == prompt_version]
    total_answers = len(prompt_answers)

    # Citation validity
    citation_valid_count = sum(
        1 for a in prompt_answers
        if a.get("citation_validation", {}).get("is_valid", False)
    )
    citation_valid_rate = citation_valid_count / total_answers if total_answers > 0 else 0.0

    # Join with judge scores
    answer_run_ids = {a["run_id"] for a in prompt_answers}
    prompt_judges = [
        j for j in judge_scores
        if j["prompt_version"] == prompt_version and j["answer_record_run_id"] in answer_run_ids
    ]

    if not prompt_judges:
        return PromptSummary(
            prompt_version=prompt_version,
            total_answers=total_answers,
            citation_valid_count=citation_valid_count,
            citation_valid_rate=citation_valid_rate,
            mean_groundedness=0.0,
            mean_relevance=0.0,
            mean_completeness=0.0,
            mean_citation_quality=0.0,
            mean_uncertainty=0.0,
            mean_composite=0.0,
            std_composite=0.0,
            best_composite=0.0,
            worst_composite=0.0,
        )

    # Extract scores
    groundedness = [j["groundedness_score"] for j in prompt_judges]
    relevance = [j["relevance_score"] for j in prompt_judges]
    completeness = [j["completeness_score"] for j in prompt_judges]
    citation_quality = [j["citation_quality_score"] for j in prompt_judges]
    uncertainty = [j["appropriate_uncertainty_score"] for j in prompt_judges]
    composite = [j["composite_score"] for j in prompt_judges]

    return PromptSummary(
        prompt_version=prompt_version,
        total_answers=total_answers,
        citation_valid_count=citation_valid_count,
        citation_valid_rate=citation_valid_rate,
        mean_groundedness=mean(groundedness),
        mean_relevance=mean(relevance),
        mean_completeness=mean(completeness),
        mean_citation_quality=mean(citation_quality),
        mean_uncertainty=mean(uncertainty),
        mean_composite=mean(composite),
        std_composite=std_dev(composite),
        best_composite=max(composite),
        worst_composite=min(composite),
    )


def select_best_prompt(
    summaries: list[PromptSummary],
    min_citation_validity: float = 1.0,
) -> PromptSummary | None:
    """Select the best prompt configuration according to guardrails.

    Guardrails:
    - Citation validity must be >= min_citation_validity (default 100%)
    - Among valid candidates, select by highest mean composite score
    - Tie-breaker: highest mean groundedness
    """
    # Filter by citation validity guardrail
    valid_candidates = [
        s for s in summaries
        if s.citation_valid_rate >= min_citation_validity
    ]

    if not valid_candidates:
        return None

    # Sort by composite score (desc), then groundedness (desc)
    valid_candidates.sort(
        key=lambda s: (s.mean_composite, s.mean_groundedness),
        reverse=True,
    )

    return valid_candidates[0]


def generate_markdown_report(
    summaries: list[PromptSummary],
    best_prompt: PromptSummary | None,
    min_citation_validity: float = 1.0,
) -> str:
    """Generate a markdown report with tables and rationale."""
    lines: list[str] = []

    lines.append("# DER RegCheck LLM Evaluation Summary")
    lines.append("")
    lines.append(f"**Generated:** {now_iso()}")
    lines.append(f"**Schema version:** {SCHEMA_VERSION}")
    lines.append("")

    lines.append("## Evaluation Design")
    lines.append("")
    lines.append("- **Questions:** 24 fixed evaluation questions across 6 categories")
    lines.append("- **Prompt variants:** v1_direct_rag, v2_structured_grounded_rag, v3_few_shot_grounded_rag")
    lines.append("- **Total answers:** 72 (24 questions × 3 prompt versions)")
    lines.append("- **Judge model:** gemini-3.5-flash-lite")
    lines.append("- **Scoring dimensions:** Groundedness, Relevance, Completeness, Citation Quality, Appropriate Uncertainty")
    lines.append("- **Composite formula:** 0.30×�roundedness + 0.20×µelevance + 0.20×½ompleteness + 0.20×¦itation Quality + 0.10×½ncertainty")
    lines.append("")

    lines.append("## Selection Guardrail")
    lines.append("")
    lines.append(f"- **Minimum citation validity:** {min_citation_validity * 100:.0f}%")
    lines.append("- **Selection rule:** Among citation-valid candidates, select by highest mean composite score")
    lines.append("- **Tie-breaker:** Highest mean groundedness")
    lines.append("")

    lines.append("## Prompt Configuration Summaries")
    lines.append("")
    lines.append("| Prompt Version | Total | Citation Valid | Valid Rate | Mean G | Mean R | Mean C | Mean Q | Mean U | Mean Composite | Std Composite |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")

    for s in summaries:
        lines.append(
            f"| {s.prompt_version} | {s.total_answers} | {s.citation_valid_count} | {s.citation_valid_rate * 100:.1f}% | "
            f"{s.mean_groundedness:.2f} | {s.mean_relevance:.2f} | {s.mean_completeness:.2f} | "
            f"{s.mean_citation_quality:.2f} | {s.mean_uncertainty:.2f} | {s.mean_composite:.4f} | {s.std_composite:.4f} |"
        )

    lines.append("")

    if best_prompt:
        lines.append("## Selected Configuration")
        lines.append("")
        lines.append(f"**Winner:** `{best_prompt.prompt_version}`")
        lines.append("")
        lines.append(f"- **Citation validity:** {best_prompt.citation_valid_rate * 100:.1f}%")
        lines.append(f"- **Mean composite score:** {best_prompt.mean_composite:.4f}")
        lines.append(f"- **Mean groundedness:** {best_prompt.mean_groundedness:.2f}")
        lines.append(f"- **Mean relevance:** {best_prompt.mean_relevance:.2f}")
        lines.append(f"- **Mean completeness:** {best_prompt.mean_completeness:.2f}")
        lines.append(f"- **Mean citation quality:** {best_prompt.mean_citation_quality:.2f}")
        lines.append(f"- **Mean appropriate uncertainty:** {best_prompt.mean_uncertainty:.2f}")
        lines.append("")
        lines.append("### Rationale")
        lines.append("")
        lines.append(f"The `{best_prompt.prompt_version}` configuration achieved the highest mean composite score ")
        lines.append(f"among all prompt variants meeting the {min_citation_validity * 100:.0f}% citation-validity guardrail. ")
        lines.append("This configuration is recommended for production deployment.")
        lines.append("")
    else:
        lines.append("## No Configuration Selected")
        lines.append("")
        lines.append(f"No prompt variant met the {min_citation_validity * 100:.0f}% citation-validity guardrail. ")
        lines.append("Review individual answer failures and consider prompt engineering improvements before deployment.")
        lines.append("")

    lines.append("## Detailed Judge Scores")
    lines.append("")
    lines.append("See `llm_judge_scores.jsonl` for per-answer judge scores and rationales.")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    """Parse arguments and generate summary report."""
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "--answers",
        type=Path,
        required=True,
        help="JSONL file with generated answers.",
    )

    parser.add_argument(
        "--judge-scores",
        type=Path,
        required=True,
        help="JSONL file with judge scores.",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data/evaluation/llm_evaluation_summary.json",
        help="JSON output path for summary.",
    )

    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Optional markdown report output path.",
    )

    parser.add_argument(
        "--min-citation-validity",
        type=float,
        default=1.0,
        help="Minimum citation validity rate (0.0-1.0) for selection. Default: 1.0 (100%).",
    )

    args = parser.parse_args()

    answers_path = args.answers if args.answers.is_absolute() else ROOT / args.answers
    judge_scores_path = (
        args.judge_scores if args.judge_scores.is_absolute() else ROOT / args.judge_scores
    )
    output_path = args.output if args.output.is_absolute() else ROOT / args.output

    print(f"Loading answers from {answers_path}...")
    answers = load_jsonl(answers_path)
    print(f"Loaded {len(answers)} answer records.")

    print(f"Loading judge scores from {judge_scores_path}...")
    judge_scores = load_jsonl(judge_scores_path)
    print(f"Loaded {len(judge_scores)} judge records.")

    # Compute summaries for each prompt version
    prompt_versions = ["v1_direct_rag", "v2_structured_grounded_rag", "v3_few_shot_grounded_rag"]
    summaries: list[PromptSummary] = []

    for pv in prompt_versions:
        summary = compute_summary(answers, judge_scores, pv)
        summaries.append(summary)
        print(
            f"{pv}: {summary.total_answers} answers, "
            f"{summary.citation_valid_rate * 100:.1f}% valid, "
            f"composite={summary.mean_composite:.4f}"
        )

    # Select best prompt
    best_prompt = select_best_prompt(summaries, min_citation_validity=args.min_citation_validity)

    if best_prompt:
        print(f"\nSelected configuration: {best_prompt.prompt_version}")
        print(f"Mean composite score: {best_prompt.mean_composite:.4f}")
    else:
        print(f"\nNo configuration met the {args.min_citation_validity * 100:.0f}% citation-validity guardrail.")

    # Build summary JSON
    summary_json = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_iso(),
        "answers_file": str(answers_path),
        "judge_scores_file": str(judge_scores_path),
        "total_answers": len(answers),
        "total_judge_scores": len(judge_scores),
        "prompt_versions_evaluated": prompt_versions,
        "min_citation_validity_threshold": args.min_citation_validity,
        "summaries": [
            {
                "prompt_version": s.prompt_version,
                "total_answers": s.total_answers,
                "citation_valid_count": s.citation_valid_count,
                "citation_valid_rate": s.citation_valid_rate,
                "mean_groundedness": round(s.mean_groundedness, 4),
                "mean_relevance": round(s.mean_relevance, 4),
                "mean_completeness": round(s.mean_completeness, 4),
                "mean_citation_quality": round(s.mean_citation_quality, 4),
                "mean_uncertainty": round(s.mean_uncertainty, 4),
                "mean_composite": round(s.mean_composite, 4),
                "std_composite": round(s.std_composite, 4),
                "best_composite": round(s.best_composite, 4),
                "worst_composite": round(s.worst_composite, 4),
            }
            for s in summaries
        ],
        "selected_configuration": {
            "prompt_version": best_prompt.prompt_version,
            "mean_composite": round(best_prompt.mean_composite, 4),
            "mean_groundedness": round(best_prompt.mean_groundedness, 4),
            "citation_valid_rate": best_prompt.citation_valid_rate,
        } if best_prompt else None,
    }

    # Write JSON summary
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary_json, indent=2), encoding="utf-8")
    print(f"\nSummary written to: {output_path}")

    # Generate markdown report if requested
    if args.report:
        report_path = args.report if args.report.is_absolute() else ROOT / args.report
        report_md = generate_markdown_report(summaries, best_prompt, args.min_citation_validity)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report_md, encoding="utf-8")
        print(f"Markdown report written to: {report_path}")


if __name__ == "__main__":
    main()