"""Configuration-aware query cache for DER RegCheck.


Provides:
- get_cached_answer(question_text, config_hash) -> dict | None
- save_answer_to_cache(question_text, config_hash, gen_answer, latency_ms) -> cache_id
- list_recent_queries(limit) -> list[dict]
- get_cached_answer_by_id(cache_id) -> dict | None


The cache is keyed by (question_text, config_hash) to ensure answers are only
reused when generated with the same prompt and retrieval configuration.
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from src.database.db_connection import get_connection
from src.generation.answer_generator import GeneratedAnswer
from src.generation.schemas import StructuredAnswerOutput


def compute_config_hash(
    prompt_version: str,
    top_k: int,
    retrieval_config_id: str = "default",
) -> str:
    """
    Compute a stable hash for a given retrieval + generation configuration.

    This ensures cached answers are only reused when the configuration matches.
    """
    payload = {
        "prompt_version": prompt_version,
        "top_k": top_k,
        "retrieval_config_id": retrieval_config_id,
    }
    text = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _build_evidence_snapshot(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Build a lightweight evidence snapshot for caching.

    Stores only the fields needed to reconstruct evidence cards in the UI.
    """
    snapshot = []
    for rank, chunk in enumerate(sources, start=1):
        citation = chunk.get("citation") or {}
        source_policy = chunk.get("source_policy") or {}

        snapshot.append(
            {
                "chunk_id": chunk.get("chunk_id"),
                "source_id": chunk.get("source_id"),
                "retrieval_rank": rank,
                "score": chunk.get("_rerank_score"),
                "heading_path": chunk.get("heading_path"),
                "citation": {
                    "pdf_page_start": citation.get("pdf_page_start"),
                    "section_ids": citation.get("section_ids"),
                },
                "source_policy": {
                    "authority_tier": source_policy.get("authority_tier"),
                    "currency_status": source_policy.get("currency_status"),
                },
                "evidence_text": chunk.get("evidence_text"),
            }
        )
    return snapshot


def get_cached_answer(
    question_text: str,
    config_hash: str,
) -> dict[str, Any] | None:
    """
    Look up a cached answer for (question_text, config_hash).

    Returns:
        A dict with keys:
          - cache_id
          - answer_status
          - direct_answer
          - claims
          - uncertainty_statement
          - clarifying_question
          - evidence_gaps
          - research_next_steps
          - evidence_snapshot
        or None if no cache hit.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    cache_id,
                    answer_status,
                    direct_answer,
                    claims,
                    uncertainty_statement,
                    clarifying_question,
                    evidence_gaps,
                    research_next_steps,
                    evidence_snapshot
                FROM query_cache
                WHERE question_text = %s
                  AND config_hash = %s
                LIMIT 1
                """,
                (question_text, config_hash),
            )
            row = cur.fetchone()
            if not row:
                return None

            cache_id, answer_status, direct_answer, claims, uncertainty_statement, clarifying_question, evidence_gaps, research_next_steps, evidence_snapshot = row

            return {
                "cache_id": cache_id,
                "answer_status": answer_status,
                "direct_answer": direct_answer,
                "claims": claims,
                "uncertainty_statement": uncertainty_statement,
                "clarifying_question": clarifying_question,
                "evidence_gaps": evidence_gaps,
                "research_next_steps": research_next_steps,
                "evidence_snapshot": evidence_snapshot,
            }


def save_answer_to_cache(
    question_text: str,
    config_hash: str,
    gen_answer: GeneratedAnswer,
    latency_ms: int,
) -> str:
    """
    Save a generated answer to the query cache.

    Returns:
        The cache_id of the inserted row.
    """
    structured: StructuredAnswerOutput = gen_answer.answer

    claims_payload = [
        {
            "text": claim.text,
            "citation_labels": claim.citation_labels,
        }
        for claim in structured.claims
    ]

    evidence_snapshot = _build_evidence_snapshot(gen_answer.sources or [])

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO query_cache (
                    question_text,
                    config_hash,
                    answer_status,
                    direct_answer,
                    claims,
                    uncertainty_statement,
                    clarifying_question,
                    evidence_gaps,
                    research_next_steps,
                    evidence_snapshot,
                    latency_ms
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (question_text, config_hash) DO UPDATE
                SET
                    answer_status = EXCLUDED.answer_status,
                    direct_answer = EXCLUDED.direct_answer,
                    claims = EXCLUDED.claims,
                    uncertainty_statement = EXCLUDED.uncertainty_statement,
                    clarifying_question = EXCLUDED.clarifying_question,
                    evidence_gaps = EXCLUDED.evidence_gaps,
                    research_next_steps = EXCLUDED.research_next_steps,
                    evidence_snapshot = EXCLUDED.evidence_snapshot,
                    latency_ms = EXCLUDED.latency_ms,
                    created_at = NOW()
                RETURNING cache_id
                """,
                (
                    question_text,
                    config_hash,
                    structured.answer_status,
                    structured.direct_answer,
                    json.dumps(claims_payload),
                    structured.uncertainty_statement,
                    structured.clarifying_question,
                    json.dumps(structured.evidence_gaps),
                    json.dumps(structured.research_next_steps),
                    json.dumps(evidence_snapshot),
                    latency_ms,
                ),
            )
            cache_id = cur.fetchone()[0]
        conn.commit()

    return cache_id


def list_recent_queries(limit: int = 20) -> list[dict[str, Any]]:
    """
    List recent cached queries for the sidebar selector.

    Returns a list of dicts with keys:
      - cache_id
      - question_text
      - answer_status
      - created_at
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT cache_id, question_text, answer_status, created_at
                FROM query_cache
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
            return [
                {
                    "cache_id": r[0],
                    "question_text": r[1],
                    "answer_status": r[2],
                    "created_at": r[3],
                }
                for r in rows
            ]


def get_cached_answer_by_id(cache_id: str) -> dict[str, Any] | None:
    """
    Load a full cached answer row by cache_id.

    Returns the same dict shape as get_cached_answer, plus:
      - question_text
      - config_hash
      - latency_ms
      - created_at
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    cache_id,
                    question_text,
                    config_hash,
                    answer_status,
                    direct_answer,
                    claims,
                    uncertainty_statement,
                    clarifying_question,
                    evidence_gaps,
                    research_next_steps,
                    evidence_snapshot,
                    latency_ms,
                    created_at
                FROM query_cache
                WHERE cache_id = %s
                """,
                (cache_id,),
            )
            row = cur.fetchone()
            if not row:
                return None

            (
                cache_id,
                question_text,
                config_hash,
                answer_status,
                direct_answer,
                claims,
                uncertainty_statement,
                clarifying_question,
                evidence_gaps,
                research_next_steps,
                evidence_snapshot,
                latency_ms,
                created_at,
            ) = row

            return {
                "cache_id": cache_id,
                "question_text": question_text,
                "config_hash": config_hash,
                "answer_status": answer_status,
                "direct_answer": direct_answer,
                "claims": claims,
                "uncertainty_statement": uncertainty_statement,
                "clarifying_question": clarifying_question,
                "evidence_gaps": evidence_gaps,
                "research_next_steps": research_next_steps,
                "evidence_snapshot": evidence_snapshot,
                "latency_ms": latency_ms,
                "created_at": created_at,
            }