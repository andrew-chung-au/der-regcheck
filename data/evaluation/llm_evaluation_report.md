# DER RegCheck LLM Evaluation Summary

**Generated:** 2026-11-19T03:16:46.292769Z
**Schema version:** 1.1

## Evaluation Design

- **Questions:** 24 fixed evaluation questions across 6 categories
- **Prompt variants:** v1_direct_rag, v2_structured_grounded_rag, v3_few_shot_grounded_rag
- **Total answers:** 72 unique (24 questions × 3 prompt versions); repeated records are counted once and judge scores are averaged per question
- **Judge model:** gemini-3.5-flash-lite
- **Scoring dimensions:** Groundedness, Relevance, Completeness, Citation Quality, Appropriate Uncertainty
- **Composite formula:** 0.30×Groundedness + 0.20×Relevance + 0.20×Completeness + 0.20×Citation Quality + 0.10×Uncertainty

## Selection Guardrail

- **Minimum citation validity:** 100%
- **Selection rule:** Among citation-valid candidates, select by highest mean composite score
- **Tie-breaker:** Highest mean groundedness

## Prompt Configuration Summaries

| Prompt Version | Total | Citation Valid | Valid Rate | Mean G | Mean R | Mean C | Mean Q | Mean U | Mean Composite | Std Composite |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| v1_direct_rag | 24 | 21 | 87.5% | 4.96 | 4.82 | 4.69 | 4.89 | 4.96 | 4.8640 | 0.3425 |
| v2_structured_grounded_rag | 24 | 22 | 91.7% | 5.00 | 4.80 | 4.74 | 4.99 | 5.00 | 4.9062 | 0.1707 |
| v3_few_shot_grounded_rag | 24 | 24 | 100.0% | 4.98 | 4.80 | 4.70 | 4.96 | 4.96 | 4.8812 | 0.2466 |

## Selected Configuration

**Winner:** `v3_few_shot_grounded_rag`

- **Citation validity:** 100.0%
- **Mean composite score:** 4.8812
- **Mean groundedness:** 4.98
- **Mean relevance:** 4.80
- **Mean completeness:** 4.70
- **Mean citation quality:** 4.96
- **Mean appropriate uncertainty:** 4.96

### Rationale

The `v3_few_shot_grounded_rag` configuration achieved the highest mean composite score 
among all prompt variants meeting the 100% citation-validity guardrail. 
This configuration is recommended for production deployment.

## Detailed Judge Scores

See `llm_judge_scores.jsonl` for per-answer judge scores and rationales.
