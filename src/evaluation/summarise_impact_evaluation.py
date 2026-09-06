"""Summarise four-case RAG impact-evaluation generation and judge artifacts.

Usage:
    uv run python -m src.evaluation.summarise_impact_evaluation \
      --answers data/evaluation/impact_answers.jsonl \
      --judge-scores data/evaluation/impact_judge_scores.jsonl \
      --output data/evaluation/impact_summary.json \
      --report data/evaluation/impact_report.md
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "1.0"
CASE_ORDER = ("naive_no_evidence", "v3_no_evidence", "zero_shot_rag", "full_v3_rag")
CASE_LABELS = {
    "naive_no_evidence": "A — Naive LLM, no evidence",
    "v3_no_evidence": "B — V3 prompt, no evidence",
    "zero_shot_rag": "C — Zero-shot RAG",
    "full_v3_rag": "D — Full V3 RAG",
}
SCORE_FIELDS = (
    "groundedness_score",
    "relevance_score",
    "completeness_score",
    "citation_quality_score",
    "appropriate_uncertainty_score",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 4) if values else None


def median(values: list[float]) -> float | None:
    return round(statistics.median(values), 4) if values else None


def percentage(numerator: int, denominator: int) -> float | None:
    return round(100 * numerator / denominator, 2) if denominator else None


def answer_summary(records: list[dict[str, Any]], case_id: str) -> dict[str, Any]:
    rows = [record for record in records if record.get("case_id") == case_id]
    successful = [record for record in rows if not record.get("generation_error")]
    statuses = Counter(
        (record.get("displayed_answer") or {}).get("answer_status", "generation_failed")
        for record in rows
    )
    latencies = [float(record["generation_latency_ms"]) for record in successful]
    claims = [len((record.get("displayed_answer") or {}).get("claims") or []) for record in successful]
    applicable = [record for record in successful if record.get("citation_validation_applicable")]
    valid = [record for record in applicable if (record.get("citation_validation") or {}).get("is_valid")]
    unknown_labels = sum(len((record.get("citation_validation") or {}).get("unknown_labels") or []) for record in applicable)
    uncited_claims = sum(len((record.get("citation_validation") or {}).get("uncited_claim_indexes") or []) for record in applicable)
    supplied = sum(len(record.get("evidence_labels") or {}) for record in successful)
    used = sum(len((record.get("citation_validation") or {}).get("used_labels") or []) for record in applicable)
    fail_closed = sum(bool(record.get("fail_closed_triggered")) for record in successful)

    behavior: dict[str, Any] = {}
    for record in successful:
        expected = record.get("expected_behavior") or {}
        answer = record.get("displayed_answer") or {}
        if expected.get("should_ask_clarification"):
            behavior.setdefault("clarification_required", []).append(
                answer.get("answer_status") == "needs_clarification" and bool(answer.get("clarifying_question"))
            )
        if expected.get("should_state_insufficient_evidence"):
            behavior.setdefault("insufficient_evidence_required", []).append(
                answer.get("answer_status") == "insufficient_evidence" and not answer.get("claims")
            )
    behavior_summary = {
        name: {
            "passed": sum(values),
            "total": len(values),
            "rate_percent": percentage(sum(values), len(values)),
        }
        for name, values in behavior.items()
    }

    return {
        "case_id": case_id,
        "case_label": CASE_LABELS[case_id],
        "total_records": len(rows),
        "generation_success_count": len(successful),
        "generation_success_rate_percent": percentage(len(successful), len(rows)),
        "answer_status_counts": dict(sorted(statuses.items())),
        "mean_generation_latency_ms": mean(latencies),
        "median_generation_latency_ms": median(latencies),
        "mean_claim_count": mean([float(value) for value in claims]),
        "citation_validation_applicable_count": len(applicable),
        "citation_label_valid_count": len(valid),
        "citation_label_valid_rate_percent": percentage(len(valid), len(applicable)),
        "unknown_label_count": unknown_labels,
        "uncited_claim_count": uncited_claims,
        "evidence_labels_supplied_count": supplied,
        "evidence_labels_used_count": used,
        "evidence_label_utilisation_percent": percentage(used, supplied),
        "fail_closed_triggered_count": fail_closed,
        "expected_behavior_status_compliance": behavior_summary,
    }


def judge_summary(judge_records: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, dict[str, list[float]]]]:
    by_comparison: dict[str, list[dict[str, Any]]] = defaultdict(list)
    scores_by_case: dict[str, dict[str, list[float]]] = {
        case: {field: [] for field in SCORE_FIELDS} for case in CASE_ORDER
    }
    for record in judge_records:
        if record.get("judgement"):
            by_comparison[record["comparison_id"]].append(record)
            judgement = record["judgement"]
            for position, case_key in (("candidate_a_scores", "candidate_a_case_id"), ("candidate_b_scores", "candidate_b_case_id")):
                case_id = record[case_key]
                for field in SCORE_FIELDS:
                    scores_by_case[case_id][field].append(float(judgement[position][field]))

    summaries: dict[str, Any] = {}
    for comparison_id, records in sorted(by_comparison.items()):
        left, right = records[0]["comparison_cases"]
        wins = Counter()
        confidences: list[float] = []
        for record in records:
            judgement = record["judgement"]
            winner = judgement["winner"]
            if winner == "candidate_a":
                wins[record["candidate_a_case_id"]] += 1
            elif winner == "candidate_b":
                wins[record["candidate_b_case_id"]] += 1
            else:
                wins["tie"] += 1
            confidences.append(float(judgement["confidence_score"]))
        total = len(records)
        summaries[comparison_id] = {
            "left_case_id": left,
            "right_case_id": right,
            "total_judgements": total,
            "left_wins": wins[left],
            "right_wins": wins[right],
            "ties": wins["tie"],
            "left_win_rate_percent": percentage(wins[left], total),
            "right_win_rate_percent": percentage(wins[right], total),
            "tie_rate_percent": percentage(wins["tie"], total),
            "mean_judge_confidence": mean(confidences),
        }
    return summaries, scores_by_case


def markdown_report(answer_summaries: list[dict[str, Any]], pairwise: dict[str, Any], scores: dict[str, dict[str, list[float]]]) -> str:
    lines = ["# DER RegCheck RAG Impact Evaluation", "", f"**Generated:** {now_iso()}", ""]
    lines += [
        "## Purpose", "",
        "This evaluation compares four answer-generation conditions on the 10-question Tier 2 realistic DER research set. It estimates the contribution of retrieval, evidence-bounded prompting, and the selected v3 few-shot RAG configuration. It is an LLM-as-judge evaluation, not a human-user study or independent factual verification.", "",
        "## Conditions", "",
        "| Case | Evidence | Prompt | Role |",
        "|---|---|---|---|",
        "| A | None | Naive general-knowledge prompt | Model-only baseline |",
        "| B | None | v3 few-shot evidence-bounded prompt | No-evidence safety-control condition |",
        "| C | Shared top-10 production evidence pack | v1 direct RAG | Zero-shot RAG baseline |",
        "| D | Same shared top-10 evidence pack as C | v3 few-shot grounded RAG | Full selected RAG configuration |",
        "",
        "## Generation and validation", "",
        "| Case | Success | Mean latency (ms) | Median latency (ms) | Mean claims | Citation-label validity | Unknown labels | Uncited claims | Evidence-label utilisation | Fail-closed events |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for summary in answer_summaries:
        validity = "N/A" if not summary["citation_validation_applicable_count"] else f"{summary['citation_label_valid_rate_percent']:.1f}%"
        utilisation = "N/A" if not summary["evidence_labels_supplied_count"] else f"{summary['evidence_label_utilisation_percent']:.1f}%"
        lines.append(
            f"| {summary['case_label']} | {summary['generation_success_count']}/{summary['total_records']} | "
            f"{summary['mean_generation_latency_ms'] or 0:.1f} | {summary['median_generation_latency_ms'] or 0:.1f} | "
            f"{summary['mean_claim_count'] or 0:.2f} | {validity} | {summary['unknown_label_count']} | "
            f"{summary['uncited_claim_count']} | {utilisation} | {summary['fail_closed_triggered_count']} |"
        )
    lines += ["", "## Answer status", ""]
    for summary in answer_summaries:
        statuses = ", ".join(f"{key}: {value}" for key, value in summary["answer_status_counts"].items()) or "None"
        lines.append(f"- **{summary['case_label']}:** {statuses}")
    lines += ["", "## Expected-behaviour status checks", "", "These limited deterministic checks apply only where the Tier 2 YAML explicitly requires clarification or insufficient evidence. Other safety behaviours require review of answer content and judge rationales.", ""]
    for summary in answer_summaries:
        for name, value in summary["expected_behavior_status_compliance"].items():
            lines.append(f"- **{summary['case_label']} — {name}:** {value['passed']}/{value['total']} ({value['rate_percent']:.1f}%)")
    lines += ["", "## Blinded pairwise judging", "", "| Comparison | Left wins | Right wins | Ties | Mean confidence |", "|---|---:|---:|---:|---:|"]
    for item in pairwise.values():
        lines.append(
            f"| {CASE_LABELS[item['left_case_id']]} vs {CASE_LABELS[item['right_case_id']]} | "
            f"{item['left_wins']}/{item['total_judgements']} ({item['left_win_rate_percent']:.1f}%) | "
            f"{item['right_wins']}/{item['total_judgements']} ({item['right_win_rate_percent']:.1f}%) | "
            f"{item['ties']}/{item['total_judgements']} ({item['tie_rate_percent']:.1f}%) | {item['mean_judge_confidence']:.2f} |"
        )
    lines += ["", "## Pairwise candidate scores", "", "Scores are pooled across the blinded pairwise comparisons in which each case appeared.", "", "| Case | Groundedness | Relevance | Completeness | Citation quality | Appropriate uncertainty |", "|---|---:|---:|---:|---:|---:|"]
    for case_id in CASE_ORDER:
        values = scores[case_id]
        lines.append("| " + CASE_LABELS[case_id] + " | " + " | ".join(f"{mean(values[field]) or 0:.2f}" for field in SCORE_FIELDS) + " |")
    lines += [
        "", "## Interpretation boundaries", "",
        "- Citation-label validity verifies that claim labels are drawn from the evidence labels supplied to the model and that structured claims are not uncited. It does not independently prove that a cited chunk semantically entails a claim.",
        "- The judge receives the retrieved evidence for evidence-backed comparisons so it can inspect apparent grounding and citation alignment. The judge does not receive the hidden configuration labels.",
        "- Cases C and D use the same evidence pack per question; their comparison is designed to isolate the v3 prompt and few-shot examples from retrieval variation.",
        "- Cases A and B have no evidence. Case B is primarily a safe-abstention control, not a substantive answer-quality competitor.",
        "- Results use the same Gemini model as judge and generator family, so they should be interpreted as a reproducible automated signal rather than independent human validation.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--answers", type=Path, required=True)
    parser.add_argument("--judge-scores", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "data/evaluation/impact_summary.json")
    parser.add_argument("--report", type=Path, default=ROOT / "data/evaluation/impact_report.md")
    args = parser.parse_args()
    answers_path = args.answers if args.answers.is_absolute() else ROOT / args.answers
    judges_path = args.judge_scores if args.judge_scores.is_absolute() else ROOT / args.judge_scores
    output_path = args.output if args.output.is_absolute() else ROOT / args.output
    report_path = args.report if args.report.is_absolute() else ROOT / args.report
    answers = load_jsonl(answers_path)
    judges = load_jsonl(judges_path)
    summaries = [answer_summary(answers, case_id) for case_id in CASE_ORDER]
    pairwise, scores = judge_summary(judges)
    score_means = {case: {field: mean(values) for field, values in fields.items()} for case, fields in scores.items()}
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_iso(),
        "answers_file": str(answers_path),
        "judge_scores_file": str(judges_path),
        "question_count": len({record.get("question_id") for record in answers}),
        "answer_record_count": len(answers),
        "judge_record_count": len(judges),
        "case_summaries": summaries,
        "pairwise_summaries": pairwise,
        "pooled_pairwise_score_means": score_means,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(markdown_report(summaries, pairwise, scores), encoding="utf-8")
    print(f"Summary written to: {output_path}")
    print(f"Report written to: {report_path}")


if __name__ == "__main__":
    main()
