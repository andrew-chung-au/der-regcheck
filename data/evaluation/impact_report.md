# DER RegCheck RAG Impact Evaluation

**Generated:** 2026-09-06T11:22:18.506427Z

## Purpose

This evaluation compares four answer-generation conditions on the 10-question Tier 2 realistic DER research set. It estimates the contribution of retrieval, evidence-bounded prompting, and the selected v3 few-shot RAG configuration. It is an LLM-as-judge evaluation, not a human-user study or independent factual verification.

## Conditions

| Case | Evidence | Prompt | Role |
|---|---|---|---|
| A | None | Naive general-knowledge prompt | Model-only baseline |
| B | None | v3 few-shot evidence-bounded prompt | No-evidence safety-control condition |
| C | Shared top-10 production evidence pack | v1 direct RAG | Zero-shot RAG baseline |
| D | Same shared top-10 evidence pack as C | v3 few-shot grounded RAG | Full selected RAG configuration |

## Generation and validation

| Case | Success | Mean latency (ms) | Median latency (ms) | Mean claims | Citation-label validity | Unknown labels | Uncited claims | Evidence-label utilisation | Fail-closed events |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A — Naive LLM, no evidence | 10/10 | 7839.4 | 2201.0 | 1.50 | N/A | 0 | 0 | N/A | 0 |
| B — V3 prompt, no evidence | 10/10 | 1628.6 | 1612.5 | 0.00 | 100.0% | 0 | 0 | N/A | 0 |
| C — Zero-shot RAG | 10/10 | 2559.1 | 2733.5 | 3.50 | 100.0% | 0 | 0 | 34.0% | 0 |
| D — Full V3 RAG | 10/10 | 2366.8 | 2389.5 | 3.40 | 100.0% | 0 | 0 | 36.0% | 0 |

## Answer status

- **A — Naive LLM, no evidence:** insufficient_evidence: 7, needs_clarification: 1, partial: 2
- **B — V3 prompt, no evidence:** insufficient_evidence: 10
- **C — Zero-shot RAG:** answered: 5, insufficient_evidence: 2, partial: 3
- **D — Full V3 RAG:** answered: 7, high_stakes_boundary: 1, insufficient_evidence: 1, needs_clarification: 1

## Expected-behaviour status checks

These limited deterministic checks apply only where the Tier 2 YAML explicitly requires clarification or insufficient evidence. Other safety behaviours require review of answer content and judge rationales.

- **A — Naive LLM, no evidence — clarification_required:** 1/1 (100.0%)
- **A — Naive LLM, no evidence — insufficient_evidence_required:** 1/1 (100.0%)
- **B — V3 prompt, no evidence — clarification_required:** 0/1 (0.0%)
- **B — V3 prompt, no evidence — insufficient_evidence_required:** 1/1 (100.0%)
- **C — Zero-shot RAG — clarification_required:** 0/1 (0.0%)
- **C — Zero-shot RAG — insufficient_evidence_required:** 0/1 (0.0%)
- **D — Full V3 RAG — clarification_required:** 0/1 (0.0%)
- **D — Full V3 RAG — insufficient_evidence_required:** 0/1 (0.0%)

## Blinded pairwise judging

| Comparison | Left wins | Right wins | Ties | Mean confidence |
|---|---:|---:|---:|---:|
| A — Naive LLM, no evidence vs D — Full V3 RAG | 1/10 (10.0%) | 8/10 (80.0%) | 1/10 (10.0%) | 4.80 |
| A — Naive LLM, no evidence vs B — V3 prompt, no evidence | 8/10 (80.0%) | 2/10 (20.0%) | 0/10 (0.0%) | 4.60 |
| A — Naive LLM, no evidence vs C — Zero-shot RAG | 2/10 (20.0%) | 8/10 (80.0%) | 0/10 (0.0%) | 4.90 |
| B — V3 prompt, no evidence vs D — Full V3 RAG | 0/10 (0.0%) | 9/10 (90.0%) | 1/10 (10.0%) | 5.00 |
| C — Zero-shot RAG vs D — Full V3 RAG | 5/10 (50.0%) | 3/10 (30.0%) | 2/10 (20.0%) | 4.60 |

## Pairwise candidate scores

Scores are pooled across the blinded pairwise comparisons in which each case appeared.

| Case | Groundedness | Relevance | Completeness | Citation quality | Appropriate uncertainty |
|---|---:|---:|---:|---:|---:|
| A — Naive LLM, no evidence | 3.77 | 3.67 | 3.33 | 2.03 | 4.30 |
| B — V3 prompt, no evidence | 3.30 | 2.40 | 2.20 | 2.30 | 3.70 |
| C — Zero-shot RAG | 4.85 | 4.60 | 4.30 | 4.45 | 4.80 |
| D — Full V3 RAG | 4.93 | 4.87 | 4.43 | 4.83 | 4.87 |

## Interpretation boundaries

- Citation-label validity verifies that claim labels are drawn from the evidence labels supplied to the model and that structured claims are not uncited. It does not independently prove that a cited chunk semantically entails a claim.
- The judge receives the retrieved evidence for evidence-backed comparisons so it can inspect apparent grounding and citation alignment. The judge does not receive the hidden configuration labels.
- Cases C and D use the same evidence pack per question; their comparison is designed to isolate the v3 prompt and few-shot examples from retrieval variation.
- Cases A and B have no evidence. Case B is primarily a safe-abstention control, not a substantive answer-quality competitor.
- Results use the same Gemini model as judge and generator family, so they should be interpreted as a reproducible automated signal rather than independent human validation.
