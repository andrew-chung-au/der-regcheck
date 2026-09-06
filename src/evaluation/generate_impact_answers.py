"""Generate four-case RAG impact-evaluation answers on Tier 2 questions.

Cases:
- naive_no_evidence: general-knowledge structured-answer baseline, no evidence
- v3_no_evidence: v3 evidence-bounded prompt, intentionally no evidence
- zero_shot_rag: v1 direct RAG prompt over retrieved evidence
- full_v3_rag: v3 few-shot prompt over the same retrieved evidence

Usage:
    uv run python -m src.evaluation.generate_impact_answers --overwrite
    uv run python -m src.evaluation.generate_impact_answers --resume
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from src.generation.answer_generator import build_evidence_context, build_user_prompt
from src.generation.citation_validator import validate_citations
from src.generation.prompts import get_prompt_instructions
from src.generation.schemas import StructuredAnswerOutput
from src.llm_client import generate_structured_answer, get_client, get_default_model
from src.retrieval.runtime_retriever import get_runtime_retriever

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "1.0"
CASES = (
    "naive_no_evidence",
    "v3_no_evidence",
    "zero_shot_rag",
    "full_v3_rag",
)
NAIVE_INSTRUCTIONS = """You are a careful research assistant for Distributed Energy Resource
interconnection and market-entry questions.

Answer the user's question using your general knowledge. Do not claim to have
reviewed source documents or retrieved evidence. Do not invent tariff clauses,
section numbers, page numbers, rule-sheet numbers, URLs, deadlines, numerical
thresholds, or citations. If the answer depends on current, source-specific, or
project-specific information, state that uncertainty and recommend verification.
Do not make legal, regulatory, engineering, compliance, approval, or
project-specific eligibility determinations.

Return valid JSON matching the StructuredAnswerOutput schema. Because no
evidence has been supplied, leave every claim.citation_labels list empty."""


@dataclass(frozen=True)
class EvaluationQuestion:
    id: str
    category: str
    question: str
    expected_sources: list[str]
    expected_topics: list[str]
    expected_behavior: dict[str, Any]
    notes: str


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def get_git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=ROOT,
            check=False,
        )
        return result.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def load_questions(path: Path) -> list[EvaluationQuestion]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return [
        EvaluationQuestion(
            id=item["id"],
            category=item["category"],
            question=item["question"],
            expected_sources=item.get("expected_sources", []),
            expected_topics=item.get("expected_topics", []),
            expected_behavior=item.get("expected_behavior", {}),
            notes=item.get("notes", ""),
        )
        for item in data.get("questions", [])
    ]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def serialise_validation(validation: Any) -> dict[str, Any]:
    return {
        "is_valid": validation.is_valid,
        "supplied_labels": sorted(validation.supplied_labels),
        "used_labels": sorted(validation.used_labels),
        "unknown_labels": sorted(validation.unknown_labels),
        "uncited_claim_indexes": validation.uncited_claim_indexes,
        "errors": validation.errors,
    }


def insufficient_answer(evidence_gap: str) -> StructuredAnswerOutput:
    return StructuredAnswerOutput(
        answer_status="insufficient_evidence",
        direct_answer=(
            "I do not have enough retrieved evidence to answer that reliably. "
            "Please ask a more specific question or consult the cited source documents."
        ),
        claims=[],
        uncertainty_statement=(
            "This is research assistance only, not legal, engineering, regulatory, "
            "or compliance advice."
        ),
        clarifying_question=None,
        evidence_gaps=[evidence_gap],
        research_next_steps=["Retry the question or consult the source documents directly."],
    )


def case_configuration(case_id: str) -> tuple[str, str, bool, bool]:
    if case_id == "naive_no_evidence":
        return NAIVE_INSTRUCTIONS, "naive_general_knowledge", False, False
    if case_id == "v3_no_evidence":
        return get_prompt_instructions("v3_few_shot_grounded_rag"), "v3_few_shot_grounded_rag", True, False
    if case_id == "zero_shot_rag":
        return get_prompt_instructions("v1_direct_rag"), "v1_direct_rag", True, False
    if case_id == "full_v3_rag":
        return get_prompt_instructions("v3_few_shot_grounded_rag"), "v3_few_shot_grounded_rag", True, True
    raise ValueError(f"Unknown case_id: {case_id}")


def generate_case(
    *,
    case_id: str,
    question: EvaluationQuestion,
    sources: list[dict[str, Any]],
    evidence_context: str,
    llm_client: Any,
) -> dict[str, Any]:
    instructions, prompt_id, validation_applicable, fail_closed = case_configuration(case_id)
    case_sources = [] if case_id in {"naive_no_evidence", "v3_no_evidence"} else sources
    user_prompt = (
        f"Original user question:\n{question.question.strip()}"
        if case_id == "naive_no_evidence"
        else build_user_prompt(question.question, case_sources)
    )
    supplied_labels = {f"S{i}" for i in range(1, len(case_sources) + 1)}
    started = time.perf_counter()
    try:
        output, usage = generate_structured_answer(
            instructions=instructions,
            user_prompt=user_prompt,
            output_type=StructuredAnswerOutput,
            client=llm_client,
            verbose=False,
        )
        generation_error = ""
    except Exception as error:
        output = None
        usage = None
        generation_error = f"{type(error).__name__}: {error}"
    latency_ms = int((time.perf_counter() - started) * 1000)

    if output is None:
        delivered = insufficient_answer("The answer-generation service failed before producing an answer.")
        validation = None
        raw_answer = None
        fail_closed_triggered = False
    else:
        raw_answer = output.model_dump()
        validation = validate_citations(answer=output, supplied_evidence_labels=supplied_labels) if validation_applicable else None
        fail_closed_triggered = bool(fail_closed and validation is not None and not validation.is_valid)
        delivered = insufficient_answer(
            "The generated response contained citations that could not be validated against the supplied evidence."
        ) if fail_closed_triggered else output

    return {
        "schema_version": SCHEMA_VERSION,
        "question_id": question.id,
        "category": question.category,
        "question_text": question.question,
        "expected_sources": question.expected_sources,
        "expected_topics": question.expected_topics,
        "expected_behavior": question.expected_behavior,
        "notes": question.notes,
        "case_id": case_id,
        "prompt_id": prompt_id,
        "retrieval_enabled": bool(case_sources),
        "retrieval_config_id": "vector_rerank_top10" if case_sources else None,
        "retrieved_chunk_ids": [source["chunk_id"] for source in case_sources],
        "evidence_labels": {f"S{i}": source["chunk_id"] for i, source in enumerate(case_sources, start=1)},
        "evidence_context": evidence_context if case_sources else "",
        "model_provider": "google_gemini",
        "model_name": get_default_model(),
        "generation_parameters": {},
        "generation_latency_ms": latency_ms,
        "token_usage": usage.model_dump() if usage else None,
        "generation_error": generation_error,
        "raw_parsed_answer": raw_answer,
        "displayed_answer": delivered.model_dump(),
        "citation_validation_applicable": validation_applicable,
        "citation_validation": serialise_validation(validation) if validation else None,
        "fail_closed_triggered": fail_closed_triggered,
        "generated_at_utc": now_iso(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", type=Path, default=ROOT / "data/evaluation/tier2_questions.yaml")
    parser.add_argument("--output", type=Path, default=ROOT / "data/evaluation/impact_answers.jsonl")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.overwrite and args.resume:
        parser.error("Use only one of --overwrite or --resume.")

    questions_path = args.questions if args.questions.is_absolute() else ROOT / args.questions
    output_path = args.output if args.output.is_absolute() else ROOT / args.output
    if output_path.exists() and not args.overwrite and not args.resume:
        parser.error(f"{output_path} exists. Use --overwrite to replace it or --resume to continue it.")
    if args.overwrite:
        output_path.unlink(missing_ok=True)

    completed = {
        (row.get("question_id"), row.get("case_id"))
        for row in load_jsonl(output_path)
    } if args.resume else set()
    questions = load_questions(questions_path)
    if not questions:
        raise ValueError("No Tier 2 questions found.")

    run_id = f"impact_generate_{now_iso().replace(':', '-').replace('.', '-')}"
    git_commit = get_git_commit()
    retriever = get_runtime_retriever()
    llm_client = get_client()
    print(f"Generating impact answers: {len(questions)} questions × {len(CASES)} cases")

    for index, question in enumerate(questions, start=1):
        needed = [case for case in CASES if (question.id, case) not in completed]
        if not needed:
            print(f"[{index}/{len(questions)}] {question.id}: already complete")
            continue
        print(f"[{index}/{len(questions)}] {question.id}: retrieving shared evidence")
        retrieval_started = time.perf_counter()
        sources = retriever.retrieve(question=question.question, final_k=10)
        retrieval_latency_ms = int((time.perf_counter() - retrieval_started) * 1000)
        evidence_context = build_evidence_context(sources)

        for case_id in needed:
            print(f"  generating {case_id}")
            record = generate_case(
                case_id=case_id,
                question=question,
                sources=sources,
                evidence_context=evidence_context,
                llm_client=llm_client,
            )
            record.update(
                {
                    "run_id": run_id,
                    "git_commit": git_commit,
                    "shared_retrieval_latency_ms": retrieval_latency_ms,
                    "shared_retrieved_chunk_count": len(sources),
                }
            )
            append_jsonl(output_path, record)
    print(f"Impact-answer generation complete: {output_path}")


if __name__ == "__main__":
    main()
