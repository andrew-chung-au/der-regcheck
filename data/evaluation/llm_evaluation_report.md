# DER RegCheck LLM Evaluation Summary

**Generated:** 2026-09-04T20:06:09.769180Z
**Schema version:** 1.0

## Evaluation Design

- **Questions:** 24 fixed evaluation questions across 6 categories
- **Prompt variants:** v1_direct_rag, v2_structured_grounded_rag, v3_few_shot_grounded_rag
- **Total answers:** 72 (24 questions × 3 prompt versions)
- **Judge model:** gemini-3.5-flash-lite
- **Scoring dimensions:** Groundedness, Relevance, Completeness, Citation Quality, Appropriate Uncertainty
- **Composite formula:** 0.30×�roundedness + 0.20×µelevance + 0.20×½ompleteness + 0.20×¦itation Quality + 0.10×½ncertainty

## Selection Guardrail

- **Minimum citation validity:** 100%
- **Selection rule:** Among citation-valid candidates, select by highest mean composite score
- **Tie-breaker:** Highest mean groundedness

## Prompt Configuration Summaries

| Prompt Version | Total | Citation Valid | Valid Rate | Mean G | Mean R | Mean C | Mean Q | Mean U | Mean Composite | Std Composite |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| v1_direct_rag | 74 | 70 | 94.6% | 4.91 | 4.65 | 4.50 | 4.79 | 4.91 | 4.7509 | 0.4711 |
| v2_structured_grounded_rag | 74 | 72 | 97.3% | 5.00 | 4.73 | 4.63 | 4.98 | 5.00 | 4.8670 | 0.2183 |
| v3_few_shot_grounded_rag | 74 | 74 | 100.0% | 4.95 | 4.70 | 4.56 | 4.92 | 4.92 | 4.8110 | 0.3446 |

## Selected Configuration

**Winner:** `v3_few_shot_grounded_rag`

- **Citation validity:** 100.0%
- **Mean composite score:** 4.8110
- **Mean groundedness:** 4.95
- **Mean relevance:** 4.70
- **Mean completeness:** 4.56
- **Mean citation quality:** 4.92
- **Mean appropriate uncertainty:** 4.92

### Rationale

The `v3_few_shot_grounded_rag` configuration achieved the highest mean composite score 
among all prompt variants meeting the 100% citation-validity guardrail. 
This configuration is recommended for production deployment.

## Detailed Judge Scores

See `llm_judge_scores.jsonl` for per-answer judge scores and rationales.
