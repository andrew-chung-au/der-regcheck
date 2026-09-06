"""Run blinded, evidence-aware pairwise LLM judging for impact-evaluation answers.

Usage:
    uv run python -m src.evaluation.judge_impact_answers --overwrite
    uv run python -m src.evaluation.judge_impact_answers --resume
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from src.llm_client import generate_structured_answer, get_client, get_default_model

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "1.0"
DEFAULT_COMPARISONS = (
    ("naive_no_evidence", "zero_shot_rag"),
    ("zero_shot_rag", "full_v3_rag"),
    ("naive_no_evidence", "full_v3_rag"),
    ("naive_no_evidence", "v3_no_evidence"),
    ("v3_no_evidence", "full_v3_rag"),
)


class QualityScores(BaseModel):
    groundedness_score: int = Field(ge=1, le=5)
    relevance_score: int = Field(ge=1, le=5)
    completeness_score: int = Field(ge=1, le=5)
    citation_quality_score: int = Field(ge=1, le=5)
    appropriate_uncertainty_score: int = Field(ge=1, le=5)


class PairwiseJudgeOutput(BaseModel):
    candidate_a_scores: QualityScores
    candidate_b_scores: QualityScores
    winner: Literal["candidate_a", "candidate_b", "tie"]
    confidence_score: int = Field(ge=1, le=5)
    rationale: str


JUDGE_INSTRUCTIONS = """You are an independent evaluator of answers to Distributed Energy Resource
interconnection and market-entry research questions.

You will receive a question, optional reference evidence, expected-behaviour
notes, and two candidate answers. The candidates were produced by the same
underlying model under different hidden configurations. Do not infer or guess
which configuration produced either answer.

Score each candidate from 1 (poor) to 5 (excellent):

Groundedness:
- 1: Material claims conflict with the supplied reference evidence, go beyond
  it without qualification, or make unsupported source-specific assertions.
- 3: Most material claims are reasonable, but one or more claims stretch the
  evidence or lack adequate qualification.
- 5: Claims stay within the evidence and clearly distinguish evidence from
  uncertainty. If no evidence was available to the candidate, do not assume
  that unsupported factual statements are grounded.

Relevance:
- 1: Does not address the question.
- 3: Addresses it at a basic level.
- 5: Directly and appropriately addresses the research question.

Completeness:
- 1: Omits material supported points, necessary caveats, or a required refusal.
- 3: Covers most important points but misses a material condition or caveat.
- 5: Covers the material supported issues without irrelevant expansion.

Citation quality:
- 1: Citations are missing when evidence-supported claims are made, invalid,
  misleading, or clearly unrelated to claims.
- 3: Citations are mostly useful but incomplete, weakly linked, or unclear.
- 5: Citations are claim-linked, appropriate, and consistent with the supplied
  evidence and source hierarchy. An answer that received no evidence should not
  receive a high citation score merely because it avoided citations.

Appropriate uncertainty:
- 1: Overconfident, unsafe, or makes a project-specific approval, compliance,
  engineering, legal, or regulatory determination without adequate evidence.
- 3: Signals some uncertainty but misses important limits or clarification needs.
- 5: Clearly states uncertainty, evidence gaps, decision boundaries, and needed
  validation where appropriate.

Use the expected-behaviour notes as evaluation criteria, not as facts that an
answer may invent. Prefer the answer that is more reliable and useful for a
professional DER researcher. A safe abstention can be better than an unsupported
specific answer when the evidence is absent or insufficient.

Return valid JSON matching the PairwiseJudgeOutput schema. Give a concise,
specific rationale."""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def render_answer(answer: dict[str, Any] | None) -> str:
    if not answer:
        return "No answer was produced because generation failed."
    lines = [f"Status: {answer.get('answer_status', 'unknown')}", "", "Direct answer:", answer.get("direct_answer", "")]
    claims = answer.get("claims") or []
    if claims:
        lines.extend(["", "Claims:"])
        for claim in claims:
            labels = " ".join(f"[{label}]" for label in claim.get("citation_labels") or [])
            lines.append(f"- {claim.get('text', '')} {labels}".rstrip())
    if answer.get("uncertainty_statement"):
        lines.extend(["", f"Uncertainty: {answer['uncertainty_statement']}"])
    if answer.get("clarifying_question"):
        lines.extend(["", f"Clarifying question: {answer['clarifying_question']}"])
    if answer.get("evidence_gaps"):
        lines.extend(["", "Evidence gaps:"] + [f"- {value}" for value in answer["evidence_gaps"]])
    if answer.get("research_next_steps"):
        lines.extend(["", "Research next steps:"] + [f"- {value}" for value in answer["research_next_steps"]])
    return "\n".join(lines)


def comparison_id(left: str, right: str) -> str:
    return f"{left}__vs__{right}"


def blind_order(question_id: str, comparison: tuple[str, str], seed: int) -> tuple[str, str]:
    digest = hashlib.sha256(f"{seed}|{question_id}|{comparison_id(*comparison)}".encode()).hexdigest()
    ordered = list(comparison)
    random.Random(int(digest[:16], 16)).shuffle(ordered)
    return ordered[0], ordered[1]


def parse_comparisons(value: str) -> tuple[tuple[str, str], ...]:
    if not value:
        return DEFAULT_COMPARISONS
    pairs: list[tuple[str, str]] = []
    for item in value.split(","):
        left, separator, right = item.strip().partition(":")
        if not separator or not left or not right:
            raise ValueError("Comparisons must use comma-separated left:right pairs.")
        pairs.append((left, right))
    return tuple(pairs)


def build_judge_prompt(
    *,
    candidate_a: dict[str, Any],
    candidate_b: dict[str, Any],
    evidence_context: str,
) -> str:
    expected_behavior = candidate_a.get("expected_behavior") or candidate_b.get("expected_behavior") or {}
    expected_sources = candidate_a.get("expected_sources") or candidate_b.get("expected_sources") or []
    expected_topics = candidate_a.get("expected_topics") or candidate_b.get("expected_topics") or []
    return f"""Question:
{candidate_a['question_text']}

Expected behaviour metadata:
{json.dumps(expected_behavior, ensure_ascii=False)}

Expected source IDs:
{json.dumps(expected_sources, ensure_ascii=False)}

Expected topics:
{json.dumps(expected_topics, ensure_ascii=False)}

Reference evidence for the evaluator:
{evidence_context if evidence_context else 'No retrieved evidence was available for this comparison.'}

Candidate A:
{render_answer(candidate_a.get('displayed_answer'))}

Candidate B:
{render_answer(candidate_b.get('displayed_answer'))}

Evaluate both candidates. Return valid JSON."""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--answers", type=Path, default=ROOT / "data/evaluation/impact_answers.jsonl")
    parser.add_argument("--output", type=Path, default=ROOT / "data/evaluation/impact_judge_scores.jsonl")
    parser.add_argument("--comparisons", type=str, default="")
    parser.add_argument("--seed", type=int, default=20260906)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.overwrite and args.resume:
        parser.error("Use only one of --overwrite or --resume.")

    answers_path = args.answers if args.answers.is_absolute() else ROOT / args.answers
    output_path = args.output if args.output.is_absolute() else ROOT / args.output
    if output_path.exists() and not args.overwrite and not args.resume:
        parser.error(f"{output_path} exists. Use --overwrite to replace it or --resume to continue it.")
    if args.overwrite:
        output_path.unlink(missing_ok=True)

    answers = load_jsonl(answers_path)
    by_question: dict[str, dict[str, dict[str, Any]]] = {}
    for answer in answers:
        if not answer.get("generation_error"):
            by_question.setdefault(answer["question_id"], {})[answer["case_id"]] = answer
    comparisons = parse_comparisons(args.comparisons)
    completed = {
        (record.get("question_id"), record.get("comparison_id"))
        for record in load_jsonl(output_path)
    } if args.resume else set()
    llm_client = get_client()
    run_id = f"impact_judge_{now_iso().replace(':', '-').replace('.', '-')}"

    for question_id in sorted(by_question):
        cases = by_question[question_id]
        for comparison in comparisons:
            comparison_key = comparison_id(*comparison)
            if (question_id, comparison_key) in completed:
                continue
            if comparison[0] not in cases or comparison[1] not in cases:
                print(f"Skipping {question_id} {comparison_key}: missing answer case")
                continue
            case_a, case_b = blind_order(question_id, comparison, args.seed)
            candidate_a, candidate_b = cases[case_a], cases[case_b]
            evidence_context = candidate_a.get("evidence_context") or candidate_b.get("evidence_context") or ""
            print(f"Judging {question_id}: {comparison_key}")
            started = time.perf_counter()
            try:
                judgement, usage = generate_structured_answer(
                    instructions=JUDGE_INSTRUCTIONS,
                    user_prompt=build_judge_prompt(
                        candidate_a=candidate_a,
                        candidate_b=candidate_b,
                        evidence_context=evidence_context,
                    ),
                    output_type=PairwiseJudgeOutput,
                    client=llm_client,
                    verbose=False,
                )
                error = ""
            except Exception as exc:
                judgement = None
                usage = None
                error = f"{type(exc).__name__}: {exc}"
            record = {
                "schema_version": SCHEMA_VERSION,
                "run_id": run_id,
                "question_id": question_id,
                "category": candidate_a["category"],
                "comparison_id": comparison_key,
                "comparison_cases": list(comparison),
                "candidate_a_case_id": case_a,
                "candidate_b_case_id": case_b,
                "judge_model_provider": "google_gemini",
                "judge_model_name": get_default_model(),
                "judge_latency_ms": int((time.perf_counter() - started) * 1000),
                "judge_token_usage": usage.model_dump() if usage else None,
                "judge_error": error,
                "judgement": judgement.model_dump() if judgement else None,
                "judged_at_utc": now_iso(),
            }
            append_jsonl(output_path, record)
    print(f"Impact judging complete: {output_path}")


if __name__ == "__main__":
    main()
