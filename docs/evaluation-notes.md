# Evaluation notes

## Overview

This document defines the retrieval and answer/brief evaluation approach for DER RegCheck.

It covers:

- Two-tier evaluation strategy: retrieval benchmarking and RAG quality evaluation
- Evaluation questions and expected source roles
- Retrieval labels, metrics, and configuration comparisons
- Evidence-block and chunk-level relevance assessment
- LLM answer and preliminary evidence-brief evaluation rubric
- Prompt variants and configuration-selection decisions
- Interpretation of source authority, currency, applicability, and uncertainty
- Empirical retrieval evaluation results (historical Tier 1 v1 and v2; authoritative production-aligned Tier 1 v3)

**Status:** Evaluation framework defined and implemented through the current
prototype stage. Raw extraction, deterministic normalisation, structural
chunking, embedding, and Tier 1 retrieval benchmarking are complete.
Historical file-based evaluations were completed on 2026-08-23 (v1 and v2).
The production-aligned PostgreSQL/pgvector retrieval and cached query-rewrite
evaluations were completed on 2026-09-05 (v3) and are the authoritative
retrieval results for the deployed retrieval path.

Answer-generation evaluation was completed on 2026-09-05 using 24 fixed
questions, three prompt configurations, deterministic citation validation, and
an LLM judge. `v3_few_shot_grounded_rag` was selected as the runtime prompt
because it was the only configuration to meet the 100% citation-validity
guardrail.

A separate 10-question Tier 2 set was created for realistic human RAG-quality
review. The Streamlit Review workflow, PostgreSQL manual-score storage, and
Monitoring coverage chart are implemented. Tier 2 review infrastructure is
therefore complete, but aggregate Tier 2 human-review results should not be
claimed until sufficient manual reviews have been recorded.

---

## Evaluation prerequisites

Evaluation must use normalised evidence outputs rather than raw extraction outputs.

```text
data/processed/extracted/
→ immutable raw extraction artifacts

data/processed/normalised/
→ deterministic evidence blocks for chunking and retrieval

data/processed/chunks/
→ 1,049 searchable chunks with citations and metadata

data/processed/embeddings/
→ 1,049 Nomic embeddings (768-dim vectors)

data/evaluation/
→ queries, qrels, cached rewrites, results, and summaries

future retrieved evidence
→ grounded answer and evidence-brief evaluation
```

Before retrieval evaluation begins:

- Normalised outputs must be reviewed. ✅ **Completed 2026-08-22**
- Primary sources must have acceptable heading-path or page-level provenance. ✅ **Completed**
- Each candidate evaluation question must identify expected primary sources. ✅ **Completed**
- Historical/draft sources must be explicitly labelled as acceptable context only where relevant. ✅ **Completed**
- Evaluation labels must distinguish required evidence from merely acceptable supporting material. ✅ **Completed**

Current normalisation and chunking review status:

| Source | Evaluation readiness |
|---|---|
| CPUC Rule 21 overview | ✅ Available as supporting context and source discovery |
| SCE Rule 21 tariff | ✅ Available as primary governing evidence |
| SCE Interconnection Handbook | ✅ Available as primary technical evidence |
| SCE Rule 21 web guidance | ✅ Available as supporting process evidence |
| SCE testing and certification instruction | ✅ Available as supporting implementation evidence |
| SIWG Phase 2 Recommendations | ✅ Available only as historical/draft context, excluded from default current-requirement retrieval |

---

## Two-tier evaluation strategy

DER RegCheck uses two complementary evaluation approaches:

### Tier 1: Retrieval benchmarking (automated, scalable)

**Purpose:** Compare retrieval configurations and select a retrieval pipeline using a fixed, reproducible query benchmark.

**Query set:** 100 LLM-generated queries, each tied to a specific gold chunk.

**Metrics:** nDCG@10, MRR, Recall@10, and a composite score (0.5·nDCG + 0.3·MRR + 0.2·Recall).

**Strengths:**
- Fast and reproducible
- Uses a fixed 100-query benchmark
- Supports comparative testing of retrievers, alpha values, metadata weightings, reranking, and cached query-rewrite techniques

**Limitations:**
- Single gold chunk per query; does not fully test multi-evidence retrieval
- Does not evaluate answer quality, only retrieval ranking
- Query quality depends on LLM generation
- Relevance is metadata-derived rather than independently human-labelled semantic relevance

**Location:** `data/evaluation/queries.jsonl` (100 queries), historical file-based result artifacts, and PostgreSQL production-aligned result artifacts.

### Tier 2: RAG quality evaluation (manual, realistic)

**Purpose:** Evaluate end-to-end RAG quality on realistic, open-ended questions that require evidence synthesis, source-hierarchy handling, clarification, uncertainty communication, and appropriate decision boundaries.

**Question set:** 10 curated Tier 2 questions stored in
`data/evaluation/tier2_questions.yaml`.

The set includes questions covering:

- Direct factual evidence lookup.
- Multi-chunk synthesis.
- Conditional or clarification-sensitive requests.
- Out-of-corpus handling.
- Historical or draft-source handling.
- High-stakes regulatory, engineering, or compliance boundaries.

Five Tier 2 questions are used as examples in the Streamlit Ask tab. All ten
questions are available in the Review tab.

**Human-review dimensions:**

- Groundedness.
- Relevance.
- Completeness.
- Citation quality.
- Appropriate uncertainty.

Each dimension is scored from 1 to 5. Reviewers may also record free-text
notes.

**Persistence:**

- `manual_scores` in PostgreSQL is the operational source of truth.
- `data/evaluation/tier2_manual_scores.jsonl` is retained as a portable
  secondary log.
- Each score is linked to a configuration-specific cached response through
  `query_cache.cache_id`.
- Multiple review events may be recorded for the same cached response.

**Strengths:**

- Evaluates realistic answers rather than retrieval ranking alone.
- Tests multi-evidence synthesis and source hierarchy reasoning.
- Captures answer-quality dimensions that retrieval metrics miss.
- Supports repeatable review through cached answer and evidence snapshots.

**Limitations:**

- Requires manual scoring.
- The question set is small.
- Human scores may vary between reviewers.
- Tier 2 aggregate results are not yet stable until sufficient reviews have
  been recorded.
- The Tier 2 set is not a substitute for the 24-question prompt-regression
  evaluation.

**Relationship:** Tier 1 evaluates retrieval ranking under a fixed benchmark.
The 24-question answer evaluation compares prompt configurations under a
citation-validity guardrail. Tier 2 evaluates realistic end-to-end RAG
usefulness through human review.

**Status:** Tier 2 infrastructure is implemented. The question set, Streamlit
Review workflow, PostgreSQL manual-score storage, JSONL secondary log, and
Monitoring coverage chart are available. Aggregate Tier 2 human-review results
remain pending until enough manual evaluations have been recorded.

---

## Evaluation observability and answer snapshots

The application separates generated-answer persistence from feedback and manual
evaluation.

A successful cache miss creates a `query_cache` record containing:

- Original question text.
- Prompt version.
- Retrieval configuration hash.
- Answer status.
- Direct answer.
- Uncertainty statement.
- Clarifying question, where applicable.
- Evidence gaps.
- Suggested research next steps.
- Evidence snapshot.
- Cache-miss generation latency.

The configuration hash is derived from the runtime configuration, including:

- Prompt version.
- Top-K retrieval value.
- Retrieval configuration identifier.

This prevents an answer generated under one prompt or retrieval configuration
from being reused as though it were generated under another.

Feedback and manual review are separate event types:

| Record | Purpose | Link |
|---|---|---|
| `query_cache` | Persist a configuration-specific answer and evidence snapshot | Primary response record |
| `answer_feedback` | Store Helpful / Not helpful feedback and optional comments | `cache_id` |
| `manual_scores` | Store structured human-review scores and notes | `cache_id` |

Cache hits are not treated as full generation runs. Generation latency is
recorded for cache misses only because a cache hit is a database lookup rather
than a complete embedding, retrieval, reranking, and LLM-generation path.

The Streamlit Monitoring tab reports:

- Cached-query volume.
- Answer-status distribution.
- Feedback distribution.
- Average manual-review scores.
- Cache-miss latency over time.
- Cache-miss latency by answer status.
- Tier 2 review coverage.

Charts use safe empty states when no valid records exist. The dashboard does
not create artificial observations for demonstration purposes.

---

## Tier 1: Retrieval benchmarking

### Query generation

**Query set:** 100 LLM-generated queries.

**Generation model:** `gemini-3.5-flash-lite`, configured through the project environment when the query set was generated.

**Query types:**
- `product_capability` (30 queries): Technical capabilities required
- `market_analysis` (25 queries): Market/regulatory requirements
- `evidence_governance` (15 queries): Which source governs, current vs historical
- `technical_deep_dive` (20 queries): Specific technical standard or requirement
- `broad_research` (10 queries): General research question requiring multiple sources

**Query record shape:**

```json
{
  "query_id": "q1a2b3c4d",
  "query_text": "What does SCE Rule 21 require regarding smart inverter reactive power?",
  "query_type": "product_capability",
  "gold_chunk_id": "sce_rule21_tariff_pdf:c0123",
  "gold_metadata": {
    "source_id": "sce_rule21_tariff_pdf",
    "document_id": "sce_rule21_tariff_pdf",
    "heading_path": ["P. Smart Inverter Requirements", "i. Reactive Power"],
    "citation": {...},
    "block_types": ["heading", "paragraph"],
    "source_policy": {
      "authority_tier": "primary_governing",
      "retrieval_tier": "default_current"
    }
  },
  "generated_at": "2026-08-23T...",
  "llm_model": "gemini-3.5-flash-lite"
}
```

**Location:** `data/evaluation/queries.jsonl` (100 queries)

### Label design

**Metadata-based relevance:** Evaluation uses metadata matching instead of manual relevance labelling:

- **Source match:** `retrieved.source_id == gold.source_id`
- **Section match:** Overlapping `section_ids`
- **Page proximity:** `abs(retrieved_page - gold_page) <= 2`
- **Block-type match:** Overlapping `block_types`
- **Authority-tier match:** Same `authority_tier`

**Composite metadata score:**

```python
metadata_score = (
    source_weight * source_match
    + section_weight * section_match
    + page_weight * page_proximity
    + block_type_weight * block_type_match
    + authority_weight * authority_match
)
```

**Weighting schemes tested:**

| Scheme | Source | Section | Page | Block type | Authority |
|---|---:|---:|---:|---:|---:|
| Equal | 0.20 | 0.20 | 0.20 | 0.20 | 0.20 |
| Source-heavy | 0.40 | 0.20 | 0.15 | 0.15 | 0.10 |
| Section-heavy | 0.15 | 0.40 | 0.20 | 0.15 | 0.10 |
| Page-heavy | 0.15 | 0.20 | 0.40 | 0.15 | 0.10 |
| Authority-heavy | 0.10 | 0.20 | 0.20 | 0.20 | 0.30 |

**Relevance threshold:** `metadata_score > 0.5` counts as relevant.

**Note on Recall@10:** Recall@10 uses all corpus chunks meeting the metadata relevance threshold as its denominator. It therefore measures coverage of the metadata-defined relevant set, not the percentage of real user questions answered successfully.

### Metrics

Retrieval benchmarking uses:

- **nDCG@10:** Ranking quality with graded relevance
- **MRR (Mean Reciprocal Rank):** How early the first relevant result appears
- **Recall@10:** Proportion of metadata-relevant chunks retrieved in the top 10 results
- **Composite score:** 0.5·nDCG@10 + 0.3·MRR + 0.2·Recall@10, used as a tie-breaker and overall quality indicator

**Computation:** Metadata-based relevance; no manual qrels are required for Tier 1.

---

## Historical file-based evaluation results

The v1 and v2 results below were generated using the earlier file-based, in-memory evaluator. That evaluator used locally loaded embeddings and a lightweight lexical-overlap baseline rather than the deployed PostgreSQL full-text and pgvector retrieval path.

The v1 and v2 results are retained as historical offline-baseline artifacts. They are useful for documenting development progress but must not be numerically compared directly with the production-aligned PostgreSQL results in v3 because multiple implementation details differ.

### Retrieval configurations compared (historical v2 evaluation)

1. **BM25:** Token-overlap similarity baseline
2. **Vector:** Cosine similarity with Nomic embeddings (768-dim)
3. **Hybrid:** Reciprocal Rank Fusion of BM25 + Vector (alpha ∈ {0.3, 0.5, 0.7}, RRF-style fusion)
4. **Hybrid + rerank:** Cross-encoder (`BAAI/bge-reranker-base`) on top of hybrid candidates
5. **Vector + rerank:** Cross-encoder on top of vector candidates

**Embedding model:** `nomic-ai/nomic-embed-text-v1.5`
- 768-dimensional vectors
- `search_document:` prefix on chunk embedding text
- `search_query:` prefix on query text

**Reranker:** `BAAI/bge-reranker-base`
- Candidate limit: 50
- Top-k after rerank: 10
- Max tokens per document: 450
- Batch size: 16

**Hybrid fusion:** RRF-style with configurable α and k.

### Baseline results (v1: historical file-based evaluation, 2026-08-23)

**Queries:** 100
**Chunks:** 1,049
**Results:** 1,500 (3 retrievers × 5 weightings)

| Retriever | Weighting | nDCG@10 | MRR | Recall@10 |
|---|---|---:|---:|---:|
| **Vector** | **Equal** | **0.826** | 0.893 | 0.594 |
| Vector | Authority-heavy | 0.826 | 0.893 | 0.594 |
| Vector | Source-heavy | 0.817 | 0.893 | 0.594 |
| Vector | Page-heavy | 0.793 | 0.751 | 0.650 |
| Vector | Section-heavy | 0.794 | 0.717 | 0.639 |
| **Hybrid** | **Equal** | 0.777 | **0.903** | 0.613 |
| Hybrid | Authority-heavy | 0.777 | 0.903 | 0.613 |
| Hybrid | Source-heavy | 0.766 | 0.903 | 0.613 |
| Hybrid | Page-heavy | 0.741 | 0.742 | 0.607 |
| Hybrid | Section-heavy | 0.740 | 0.713 | 0.623 |
| **BM25** | **Equal** | 0.745 | 0.815 | 0.563 |
| BM25 | Authority-heavy | 0.745 | 0.815 | 0.563 |
| BM25 | Source-heavy | 0.719 | 0.815 | 0.563 |
| BM25 | Page-heavy | 0.721 | 0.604 | 0.543 |
| BM25 | Section-heavy | 0.724 | 0.573 | 0.524 |

**Key findings (v1):**

1. **Vector retrieval outperforms hybrid and BM25**
   - Vector nDCG@10: 0.826
   - Hybrid nDCG@10: 0.777
   - BM25 nDCG@10: 0.745

2. **Weighting scheme has modest impact**
   - Vector range: 0.793–0.826
   - Equal weighting performs best for vector retrieval

3. **Hybrid has best MRR**
   - Hybrid MRR: 0.903
   - Vector MRR: 0.893

4. **Vector has best overall ranking quality**
   - Best nDCG@10: Vector with equal weighting (0.826)
   - Best MRR: Hybrid with equal weighting (0.903)
   - Best Recall@10: Vector with page-heavy weighting (0.650)

**Selected configuration (v1):** Vector retrieval with equal weighting.

### Extended results (v2: historical file-based evaluation, 2026-08-23)

> **Historical status:** v2 used the earlier file-based evaluator. It is retained as a development record, but its numerical scores are not directly comparable with v3 because v3 uses the deployed PostgreSQL retrieval path. Verify the stated historical v2 record total against the preserved result artifact before relying on it outside this document.

**Queries:** 100
**Chunks:** 1,049
**Results:** 8,100 retrieval records reported in the historical v2 artifact.

**Top configurations by composite score (0.5·nDCG + 0.3·MRR + 0.2·Recall):**

| Rank | Configuration | nDCG@10 | MRR | Recall@10 | Composite |
|---|---|---:|---:|---:|---:|
| 1 | hybrid_rerank__equal | 0.95080 | 0.95361 | 1.00000 | 0.96148 |
| 2 | hybrid_rerank__authority_heavy | 0.95074 | 0.95361 | 1.00000 | 0.96145 |
| 3 | hybrid_rerank__source_heavy | 0.95021 | 0.95361 | 1.00000 | 0.96119 |
| 4 | vector_rerank__equal | 0.94542 | 0.93750 | 0.99000 | 0.95196 |
| 5 | vector_rerank__authority_heavy | 0.94542 | 0.93750 | 0.99000 | 0.95196 |
| 6 | vector_rerank__source_heavy | 0.94412 | 0.93750 | 0.99000 | 0.95131 |
| 7 | hybrid_rerank__page_heavy | 0.93349 | 0.85840 | 0.98333 | 0.92092 |
| 8 | hybrid_rerank__section_heavy | 0.93721 | 0.85610 | 0.97333 | 0.92010 |
| 9 | vector_rerank__page_heavy | 0.92932 | 0.83450 | 0.95000 | 0.90501 |
| 10 | vector_rerank__section_heavy | 0.93221 | 0.82200 | 0.93000 | 0.89870 |

**Non-reranked top configurations (for comparison):**

| Configuration | nDCG@10 | MRR | Recall@10 | Composite |
|---|---:|---:|---:|---:|
| vector__equal | 0.75740 | 0.89293 | 0.33081 | 0.71274 |
| hybrid__equal | 0.70484 | 0.88124 | 0.32452 | 0.68170 |
| bm25__equal | 0.64293 | 0.81559 | 0.30105 | 0.62635 |

**Key findings (v2):**

1. **Reranking dominates**
   - Best reranked (`hybrid_rerank__equal`) nDCG@10 ≈ 0.951 versus best non-reranked (`vector__equal`) nDCG@10 ≈ 0.757.
   - Recall@10 increased substantially in the historical metadata-derived evaluation.

2. **Weighting matters little once reranking is used**
   - Among `hybrid_rerank` and `vector_rerank`, differences across leading weightings are small.
   - Equal weighting has a narrow composite-score edge and is simple to justify.

3. **Hybrid + rerank slightly edges vector + rerank**
   - `hybrid_rerank__equal` composite: 0.96148
   - `vector_rerank__equal` composite: 0.95196

4. **Alpha (0.3–0.7) has modest impact relative to reranking**
   - Reranking had a much larger observed impact than alpha selection.
   - α = 0.5 was retained as a sensible historical default.

**Selected configuration (v2):** Hybrid retrieval with reranking and equal weighting (α = 0.5, RRF k = 1).

**Reference:** Full historical configuration rationale and decision record are in `docs/decisions.md` #11, which supersedes #09 for the file-based evaluation stage.

---

## Production-aligned PostgreSQL evaluation (v3: 2026-09-05)

### Purpose

v3 re-ran the fixed retrieval benchmark using the deployed PostgreSQL/pgvector retrieval path rather than the earlier file-based, in-memory evaluator.

This is the authoritative retrieval evaluation for the current DER RegCheck runtime system.

v1 and v2 remain historical offline-baseline artifacts. They are not directly comparable with v3 because the evaluator implementation, lexical retrieval mechanism, vector retrieval mechanism, and retrieval execution path changed together.

### Runtime retrieval path

```text
Query text
→ runtime query embedding using Nomic `search_query:` prefix
→ PostgreSQL full-text lexical retrieval and/or pgvector vector retrieval
→ PostgreSQL-backed hybrid retrieval where selected
→ BAAI/bge-reranker-base cross-encoder reranking where selected
→ top 10 chunks evaluated using metadata-derived relevance
```

### Evaluation configuration

| Component | Configuration |
|---|---|
| Corpus | 1,049 indexed chunks |
| Query benchmark | 100 fixed LLM-generated queries |
| Retrieval backend | PostgreSQL full-text search and pgvector |
| Embedding model | `nomic-ai/nomic-embed-text-v1.5` |
| Embedding dimension | 768 |
| Document embedding prefix | `search_document:` |
| Query embedding prefix | `search_query:` |
| Reranker | `BAAI/bge-reranker-base` |
| Reranker candidate limit | 50 |
| Reranked output size | 10 |
| Reranker max document tokens | 450 |
| Reranker batch size | 16 |
| Hybrid alpha values | 0.3, 0.5, 0.7 |
| Metadata weightings | Equal, source-heavy, section-heavy, page-heavy, authority-heavy |
| Checkpointing | JSONL checkpointing for resumable evaluation |
| Query rewrites | Cached original, expanded, HyDE, and HyDE-expanded variants |

### Retrieval configurations compared

1. **Lexical:** PostgreSQL full-text lexical retrieval
2. **Vector:** pgvector vector retrieval
3. **Hybrid:** PostgreSQL-backed hybrid lexical/vector retrieval
4. **Hybrid + rerank:** Hybrid candidates reranked using `BAAI/bge-reranker-base`
5. **Vector + rerank:** Vector candidates reranked using `BAAI/bge-reranker-base`

### Full PostgreSQL retrieval grid

The completed PostgreSQL retrieval grid contains:

```text
100 queries
× 3 alpha values
× 5 retrieval variants
× 5 metadata weighting schemes
= 7,500 retrieval evaluation records
```

### Final PostgreSQL retrieval results

| Configuration | nDCG@10 | MRR | Recall@10 | Composite |
|---|---:|---:|---:|---:|
| Vector rerank, equal weighting | **0.94627** | **0.92500** | 0.09625 | **0.76989** |
| Vector rerank, authority-heavy weighting | **0.94627** | **0.92500** | 0.09625 | **0.76989** |
| Hybrid rerank, equal weighting, alpha 0.50 | 0.94589 | **0.92500** | 0.09625 | 0.76969 |
| Hybrid rerank, section-heavy weighting, alpha 0.30 | 0.93240 | 0.60800 | **0.11019** | 0.67065 |
| Hybrid, equal weighting, alpha 0.50 | 0.76700 | 0.87293 | 0.08580 | 0.66253 |
| Vector, equal weighting | 0.76330 | 0.87293 | 0.08480 | 0.66049 |
| Lexical, equal weighting | 0.15420 | 0.15500 | 0.00690 | 0.12499 |

### Key findings (v3)

1. **Cross-encoder reranking produced the main ranking-quality improvement**
   - Vector reranking increased nDCG@10 from 0.76330 for vector retrieval to 0.94627.
   - Reranking was the dominant observed design choice in the deployed retrieval path.

2. **Vector + rerank achieved the strongest observed ranking performance**
   - Best nDCG@10: 0.94627
   - Best MRR: 0.92500
   - Best composite score: 0.76989

3. **Hybrid + rerank was effectively tied on leading ranking metrics**
   - Hybrid rerank with equal weighting and α = 0.50 achieved nDCG@10 of 0.94589 and the same MRR of 0.92500.
   - Its composite score was marginally lower than vector rerank.

4. **Section-heavy hybrid reranking achieved the highest observed Recall@10**
   - Hybrid rerank with section-heavy weighting and α = 0.30 achieved Recall@10 of 0.11019.
   - It did not lead on nDCG@10, MRR, or composite score.

5. **Metadata weighting had little effect among the strongest reranked configurations**
   - Equal and authority-heavy weighting tied for the strongest vector-rerank result.
   - Equal weighting remains the simplest default to justify.

6. **Alpha had modest practical effect after reranking**
   - α = 0.50 was marginally strongest for equal-weight hybrid reranking.
   - The observed alpha differences were much smaller than the reranking effect.

7. **PostgreSQL lexical retrieval was substantially weaker than vector retrieval**
   - Lexical equal-weight retrieval achieved nDCG@10 of 0.15420.
   - Vector equal-weight retrieval achieved nDCG@10 of 0.76330.

### Cached query-rewrite evaluation

The completed PostgreSQL cached query-rewrite grid contains:

```text
100 queries
× 4 rewrite techniques
× 4 retrieval variants
× 5 metadata weighting schemes
= 8,000 query-rewrite evaluation records
```

**Rewrite techniques:**
- `original`
- `expanded`
- `hyde`
- `hyde_expanded`

### Query-rewrite results

| Configuration | nDCG@10 | MRR | Recall@10 | Composite |
|---|---:|---:|---:|---:|
| Expanded query + vector rerank, equal weighting | **0.94713** | **0.93583** | 0.09214 | **0.77274** |
| Original query + vector rerank, equal weighting | 0.94627 | 0.92500 | 0.09625 | 0.76989 |
| HyDE query + vector rerank, equal weighting | 0.89930 | 0.69980 | 0.08420 | 0.67643 |
| HyDE-expanded query + vector rerank, equal weighting | 0.88720 | 0.67200 | 0.08060 | 0.66131 |

### Query-rewrite findings

1. **Query expansion produced a modest ranking improvement**
   - nDCG@10 increased by 0.00086.
   - MRR increased by 0.01083.
   - Composite score increased by 0.00285.

2. **Query expansion slightly reduced Recall@10**
   - Recall@10 declined from 0.09625 to 0.09214 under equal weighting.

3. **HyDE was not selected**
   - Both HyDE and HyDE-expanded queries reduced ranking quality relative to the original and expanded query variants.
   - HyDE is therefore not enabled as the default query-rewrite technique.

4. **The expansion gain is small**
   - The observed gain supports expansion as a possible refinement.
   - A paired statistical test and manually judged relevance data would be needed before making a strong superiority claim.

### Evaluation-best configuration

The highest-scoring PostgreSQL evaluation configuration was:

```text
Expanded query
→ pgvector vector retrieval
→ BAAI/bge-reranker-base cross-encoder reranking
→ top 10 evidence chunks
```

This was the best evaluation configuration under the documented benchmark,
metadata-derived relevance labels, and composite score.

### Runtime configuration

The deployed application does not use query expansion by default:

```text
Original user query
→ pgvector vector retrieval
→ BAAI/bge-reranker-base cross-encoder reranking
→ top 10 evidence chunks
→ v3_few_shot_grounded_rag answer generation
```

Query expansion was disabled as a runtime latency trade-off. The expanded-query
configuration remains the evaluation winner, while the original-query
configuration is the current application configuration.

This distinction prevents the evaluation result from being misreported as the
actual runtime behavior.

### Runtime configuration: disable query expansion for latency

**Date:** 2026-09-05

**Decision:**

The PostgreSQL evaluation identified expanded-query vector reranking as the
highest-scoring retrieval variant. The runtime application nevertheless uses
the original user query with vector retrieval and cross-encoder reranking
because query expansion added approximately 36 seconds of latency in live
testing.

This is an engineering distinction:

- Expanded query + vector rerank is the evaluation-best configuration.
- Original query + vector rerank is the deployed runtime configuration.

**Impact:**

- The runtime uses the original user question rather than an expanded query.
- The expected retrieval-quality difference is small under the benchmark:
  approximately 0.00086 nDCG@10 and 0.00285 composite-score difference.
- The latency improvement is approximately 36 seconds per query, or roughly 75%
  in the observed live test.
- Configuration-aware answer caching reduces repeated generation for identical
  questions and runtime configuration.

**Future work:**

- Consider re-enabling expansion if API latency can be reduced through caching, faster models, or batch processing.
- The expansion logic remains available in the codebase for future optimization.

### v3 interpretation and limitations

- v3 is authoritative because it evaluates the deployed PostgreSQL/pgvector retrieval path.
- v1 and v2 are historical offline evaluations and are not directly comparable numerical baselines.
- Migrating from the file-based evaluator to PostgreSQL changed multiple implementation details simultaneously; the evaluation cannot support a controlled causal claim that PostgreSQL alone caused any performance difference.
- Relevance is metadata-derived rather than independently human-labelled semantic relevance.
- Synthetic queries provide scalable, controlled coverage but may not represent the distribution of real user questions.
- Recall@10 measures recovery of metadata-defined related chunks and should not be interpreted as end-user answer success.
- Retrieval metrics do not demonstrate answer groundedness, citation correctness, completeness, or regulatory applicability.
- The completed prompt-comparison evaluation supports selection of the runtime prompt, but it does not establish full end-to-end RAG quality. A manually reviewed Tier 2 evaluation remains future work for a later version.

---

## Tier 2: RAG quality evaluation

### Open-ended evaluation questions

These questions evaluate research-plan structure, source hierarchy, category coverage, uncertainty communication, and usefulness for preliminary market-entry research.

**Status:** To be regenerated or manually reviewed using a stronger model such as Gemini 2.5 Pro or equivalent for realistic RAG evaluation.

**Original example questions (for reference):**

#### Q1. Interconnection, certification, and inadvertent export

**Question:**

What official material should I review for interconnection, certification, and inadvertent-export requirements for a non-exporting battery system in SCE territory?

**Question type:** Focused evidence question

**Current-requirement query:** Yes

**Expected primary sources:**

- `sce_rule21_tariff_pdf`
  - Governing interconnection, operating, and metering requirements
  - Inadvertent-export provisions
  - Equipment certification and applicable tariff requirements
- `sce_interconnection_handbook_pdf`
  - Technical implementation detail
  - Protection, operating, metering, and telemetry context

**Expected supporting sources:**

- `sce_testing_certification_instruction_pdf`
  - Testing and certification implementation guidance
- `sce_interconnection_web`
  - Process guidance, forms, and non-export application context
- `cpuc_rule21_overview`
  - Regulatory context and source discovery

**Sources that should not rank prominently:**

- `siwg_phase2_recommendations_pdf`
  - Historical/draft context rather than current requirements

**Expected answer properties:**

- Distinguish governing tariff requirements from supporting process guidance.
- Identify whether project-specific facts are required before a definitive conclusion.
- Direct the user to the tariff, handbook, and testing/certification material.
- State that this is preliminary research support, not legal, engineering, regulatory, or compliance advice.

#### Q2. Communications, telemetry, monitoring, and control

**Question:**

What are the communications, telemetry, monitoring, and control requirements for DER in SCE under Rule 21?

**Question type:** Focused evidence question

**Current-requirement query:** Yes

**Expected primary sources:**

- `sce_rule21_tariff_pdf`
  - Governing Rule 21 requirements
  - Applicable smart inverter, communications, monitoring, and telemetry provisions
- `sce_interconnection_handbook_pdf`
  - Technical telecommunications, telemetry, RTU, SCADA, and operating requirements

**Expected supporting sources:**

- `sce_interconnection_web`
  - Customer-Owned Telemetry and process guidance
- `sce_testing_certification_instruction_pdf`
  - Testing and certification implementation context

**Historical source handling:**

- `siwg_phase2_recommendations_pdf` may be retrieved only if the question requests historical rationale, communications evolution, or draft-era context.
- It should not be used as the basis for a current-requirement conclusion.

**Expected answer properties:**

- Separate Rule 21 distribution-level requirements from possible CAISO, WDAT, transmission, or project-specific requirements.
- Distinguish governing requirements from supporting handbook detail.
- Preserve conditions such as generation size, voltage, project type, export status, and interconnection pathway where the source makes them relevant.

#### Q3. Testing and certification process

**Question:**

What testing and certification steps are required for DER equipment to interconnect under SCE Rule 21?

**Question type:** Focused evidence question

**Current-requirement query:** Yes

**Expected primary sources:**

- `sce_rule21_tariff_pdf`
  - Governing certification and testing criteria
- `sce_interconnection_handbook_pdf`
  - Technical requirements and implementation context

**Expected supporting source:**

- `sce_testing_certification_instruction_pdf`
  - Testing and certification process guidance

**Expected answer properties:**

- State that the tariff governs where sources conflict.
- Identify whether the instruction sheet is guidance rather than a controlling tariff.
- Preserve equipment type, applicable standards, certification status, and project-specific conditions.
- Flag the need to verify current tariff, utility, and certification-list status before action.

#### Q4. Fast Track and Detailed Study path

**Question:**

What Rule 21 review and study paths may apply to an SCE interconnection request, and what evidence should a project team review before selecting a path?

**Question type:** Focused evidence question

**Current-requirement query:** Yes

**Expected primary sources:**

- `sce_rule21_tariff_pdf`
  - Review process and governing procedures
- `sce_interconnection_handbook_pdf`
  - Technical and project-specific implementation context

**Expected supporting source:**

- `sce_interconnection_web`
  - Process explanation, forms, application guidance, and published utility process information

**Expected answer properties:**

- Prioritise tariff evidence over web-page summaries.
- Distinguish Fast Track, supplemental review, and detailed study concepts where supported.
- Avoid asserting project eligibility without project-specific facts and current utility review.

#### R1. Early market assessment for DER communications and control

**Request:**

Market: California
Utility: Southern California Edison
Target customer type: Distribution utility
Asset types: Solar PV and battery storage
Capability focus: DER communications and control
Decision stage: Early market assessment

What current public sources should we review, which requirement areas appear relevant, and what needs validation before pursuing this opportunity?

**Request type:** Broad preliminary market-entry research request

**Expected research-plan categories:**

- Primary governing and technical sources
- Interconnection process and applicable pathway
- Technical operating requirements
- Communications, telemetry, monitoring, and control
- Equipment certification and testing
- Source authority, currency, and applicability
- Evidence gaps and project-specific validation needs
- Explicit historical/draft-context handling

**Expected primary sources:**

- `sce_rule21_tariff_pdf`
- `sce_interconnection_handbook_pdf`

**Expected supporting sources:**

- `sce_testing_certification_instruction_pdf`
- `sce_interconnection_web`
- `cpuc_rule21_overview`

**Historical-context source:**

- `siwg_phase2_recommendations_pdf`
  - May support historical rationale only
  - Must not be represented as a current requirement

**Expected answer properties:**

- Present an evidence plan rather than a definitive market-entry conclusion.
- State which conclusions depend on project characteristics, current tariff status, utility review, and applicable interconnection pathway.
- Separate known public evidence from unresolved questions.
- Avoid treating source-discovery pages or historical material as equivalent to the tariff.

### Preconditions

Generated-answer evaluation must not begin until:

- ✅ Tier 1 retrieval baseline exists. **Completed**
- ✅ Retrieved evidence retains source and locator metadata. **Completed**
- ✅ The answer generator can cite retrieved evidence blocks or chunks. **Completed 2026-09-05**
- ✅ The generation prompt distinguishes source authority, currency, applicability, uncertainty, and historical context. **Completed 2026-09-05**
- ✅ The system can state when evidence is insufficient rather than infer unsupported requirements. **Completed 2026-09-05**

### Evaluation rubric

Each generated focused answer or preliminary evidence brief should be scored using the following rubric.

#### Groundedness (0–2)

- **0:** Makes material claims not supported by retrieved evidence.
- **1:** Mostly grounded but includes minor unsupported inference, overstatement, or incomplete qualification.
- **2:** Strictly uses retrieved evidence and clearly labels uncertainty or gaps.

#### Citation correctness (0–2)

- **0:** Citations are missing, incorrect, or do not support stated claims.
- **1:** Most citations are correct but one or more are imprecise, incomplete, or attached to weak support.
- **2:** All material claims cite supporting evidence with appropriate source and locator detail.

#### Source hierarchy and authority (0–2)

- **0:** Treats supporting or historical sources as equivalent to primary governing requirements.
- **1:** Generally respects hierarchy but occasionally blurs governing, technical, supporting, or historical roles.
- **2:** Clearly distinguishes tariff, handbook, supporting guidance, source-discovery material, and historical/draft context.

#### Currency and applicability (0–2)

- **0:** Ignoes source currency, project conditions, jurisdiction, utility, or interconnection-pathway applicability.
- **1:** Identifies some applicability limits but omits relevant project-specific conditions or source-currency caveats.
- **2:** Clearly states applicable source scope, current-status caveats, and project facts that require validation.

#### Completeness (0–2)

- **0:** Misses material conditions, exceptions, source conflicts, or evidence gaps.
- **1:** Covers most major points but omits one or more material conditions, exceptions, or validation needs.
- **2:** Captures material conditions, exceptions, uncertainty, and evidence gaps within the requested scope.

#### Category coverage (0–2) — broad requests only

- **0:** Misses major expected research categories.
- **1:** Covers most categories but omits one or more important areas.
- **2:** Covers expected categories appropriately and does not inflate scope with unsupported detail.

#### Usefulness (0–2)

- **0:** Does not direct the user to relevant sources, evidence, or validation actions.
- **1:** Provides useful information but lacks clear evidence priorities, source pointers, or next validation actions.
- **2:** Clearly directs the user to relevant sources, evidence locations, priorities, and project-specific validation actions.

### Total score

| Response type | Applicable categories | Maximum score |
|---|---|---:|
| Focused evidence answer | Groundedness, citation correctness, source hierarchy, currency/applicability, completeness, usefulness | 12 |
| Broad evidence brief | All categories | 14 |

### Critical failure conditions

Regardless of numerical score, mark an answer as failed if it:

- Presents historical/draft SIWG material as a current controlling requirement.
- Contradicts primary tariff evidence without explicitly identifying and explaining the conflict.
- Gives a definitive compliance, legal, regulatory, engineering, or market-entry conclusion without sufficient evidence.
- Omits citations for material factual claims.
- Fails to identify missing project facts where those facts determine applicability.
- Claims that a source is current without checking or disclosing currency limitations.

### Prompt variants to test

---

## Completed answer-generation evaluation (2026-09-05)

### Evaluation set

- The evaluation design targeted 72 unique answer evaluations
  (24 questions × 3 prompts).
- The persisted artifacts contain repeated or checkpointed records, so raw
  JSONL line counts must not be interpreted as unique-question coverage.
- Unique-question coverage is 24 questions per prompt version after
  deduplication by question ID and prompt version.

Three prompt configurations tested:

- `v1_direct_rag`: direct RAG prompt
- `v2_structured_grounded_rag`: structured prompt with explicit grounding instructions
- `v3_few_shot_grounded_rag`: few-shot grounded prompt with examples

Each prompt variant received the same retrieved evidence pack for a question.

### Deterministic validation

Every generated answer was checked independently of the LLM judge. Validation verified that:

- Citation labels refer only to supplied evidence labels.
- Material claims are not left uncited under the answer schema.
- Unknown citation labels fail closed.
- Empty retrieval results produce an insufficient-evidence response rather than an inferred answer.

### LLM judge rubric

The judge model was `gemini-3.5-flash-lite`. It scored each answer from 1 to 5 on:

- **Groundedness:** whether claims remain supported by supplied evidence and source-status limits.
- **Relevance:** whether the answer addresses the actual question.
- **Completeness:** whether it covers material supported points and caveats.
- **Citation quality:** whether citations are valid, claim-linked, and authority-aware.
- **Appropriate uncertainty:** whether it communicates limits, clarification needs, and decision boundaries.

The per-answer composite was:

```text
0.30 × Groundedness
+ 0.20 × Relevance
+ 0.20 × Completeness
+ 0.20 × Citation quality
+ 0.10 × Appropriate uncertainty
```

The composite has a maximum of `5.0`. It is an aggregate answer-quality indicator, not a probability of correctness.

### Selection guardrail

A prompt configuration was eligible for production selection only if its deterministic citation-validity rate was 100%.

Among eligible configurations, the highest mean composite score was selected. Mean groundedness was the tie-breaker.

### Results

| Prompt version | Unique questions | Persisted records | Citation-valid rate | Mean composite |
|---|---:|---:|---:|---:|
| `v1_direct_rag` | 24 | 74 | 94.6% | 4.7509 |
| `v2_structured_grounded_rag` | 24 | 74 | 97.3% | **4.8670** |
| `v3_few_shot_grounded_rag` | 24 | 74 | **100.0%** | 4.8110 |

**Record-count note:** The evaluation design targeted 24 unique questions per prompt version, or 72 intended unique answer evaluations in total. The aggregate artifacts contain 74 answer records per prompt version because of repeated or checkpointed records. The 74 records should not be interpreted as 74 distinct questions; unique-question coverage is 24 questions per prompt version when deduplicated by question ID and prompt version.

### Selection

`v3_few_shot_grounded_rag` is selected as the runtime prompt because it is the only configuration meeting the 100% citation-validity guardrail. Although v2 achieved the highest mean composite score, it did not meet the citation guardrail.

The selected v3 mean composite of `4.8110` is `96.2%` of the maximum possible score of `5.0`.

This selection does not establish that v3 is universally the best prompt. It establishes that v3 is the best eligible configuration under the documented guardrail, question set, judge rubric, and recorded evaluation run.

### Evaluation artifacts

- `data/evaluation/llm_evaluation_questions.yaml`: 24 fixed evaluation questions.
- `data/evaluation/llm_answers.jsonl`: Generated answer records and deterministic validation results.
- `data/evaluation/llm_judge_scores.jsonl`: Per-answer judge scores and rationales.
- `data/evaluation/llm_evaluation_summary.json`: Prompt-level aggregates and selected configuration.
- `data/evaluation/llm_evaluation_report.md`: Human-readable answer-evaluation report.
- `src/evaluation/evaluate_llm_answers.py`: Answer generation and judging harness.
- `src/evaluation/summarise_llm_evaluation.py`: Aggregation, selection, and report generation.
- `src/generation/answer_generator.py`, `src/generation/citation_validator.py`, `src/generation/prompts.py`: Generation components.
- `tests/test_answer_generator.py`: Citation/schema/unit tests.

---

## Configuration-selection decisions

For detailed explanations on *why* specific configurations—such as chunking approaches, embedding models, query expansion, and reranking parameters—were selected over alternatives, please refer to the rationale documented in [`docs/decisions.md`](decisions.md).

**Selected configuration (v1, historical file-based evaluation, 2026-08-23):**

| Component | Selection |
|---|---|
| **Chunking** | Structural block assembly |
| **Embedding model** | Nomic `nomic-embed-text-v1.5` |
| **Retrieval** | Vector (cosine similarity) |
| **Weighting scheme** | Equal (all metadata = 0.20) |
| **Hybrid method** | Reciprocal Rank Fusion (alpha=0.5) |
| **Reranking** | Not yet implemented in v1 |
| **Source filtering** | Not yet implemented  |
| **Answer generation** | Not yet implemented in v1  |
| **Prompt variant** | Not yet implemented in v1  |

**Selected configuration (v2, historical file-based evaluation, 2026-08-23):**

| Component | Selection |
|---|---|
| **Chunking** | Structural block assembly |
| **Embedding model** | Nomic `nomic-embed-text-v1.5` |
| **Retrieval** | Hybrid + rerank (`BAAI/bge-reranker-base`) |
| **Hybrid α** | 0.5 |
| **RRF k** | 1 |
| **Weighting scheme** | Equal (all metadata = 0.20) |
| **Reranking** | Implemented (cross-encoder on top-50 candidates → top-10) |
| **Source filtering** | Not yet implemented |
| **Answer generation** | Not yet implemented in v2 |
| **Prompt variant** | Not yet implemented in v2 |

**Selected configuration (v3, production-aligned PostgreSQL evaluation, 2026-09-05):**

| Component | Evaluation selection | Runtime status |
|---|---|---|
| **Evaluation backend** | PostgreSQL full-text search and pgvector | Used |
| **Chunking** | Structural block assembly | Used |
| **Embedding model** | Nomic `nomic-embed-text-v1.5` | Used |
| **Evaluation-best query treatment** | Expanded query | Evaluated, not enabled by default |
| **Runtime query treatment** | Original user query | Used |
| **Retrieval** | Vector retrieval | Used |
| **Reranking** | `BAAI/bge-reranker-base` | Used |
| **Candidate limit** | 50 | Used |
| **Final output** | Top 10 chunks | Used |
| **Weighting scheme** | Equal | Used |
| **Hybrid alpha** | 0.5 if hybrid is used | Conditional |
| **HyDE** | Disabled | Disabled |
| **Source filtering** | Not yet implemented | Not implemented |
| **Answer generation** | Implemented | Used |
| **Prompt variant** | `v3_few_shot_grounded_rag` | Used |
| **Answer cache** | PostgreSQL configuration-aware cache | Used |
| **Manual review storage** | PostgreSQL `manual_scores` plus JSONL secondary log | Used |

---

## Evaluation artifacts

**Committed or planned evaluation artifacts:**

```text
data/evaluation/
  queries.jsonl
    # 100 LLM-generated queries for Tier 1 retrieval benchmarking

  evaluation_results.jsonl
    # Historical file-based evaluation results, if retained

  evaluation_summary.json
    # Historical file-based evaluation summary, if retained

  query_rewrites.jsonl
    # Cached query-rewrite variants:
    # original, expanded, hyde, hyde_expanded

  query_rewrite_results.jsonl
    # Historical file-based rewrite evaluation results, if retained

  evaluation_results_postgres.jsonl
    # Authoritative v3 PostgreSQL retrieval grid:
    # 7,500 records

  evaluation_summary_postgres.json
    # Authoritative v3 PostgreSQL aggregated metrics and rankings

  query_rewrite_results_postgres.jsonl
    # Authoritative v3 PostgreSQL query-rewrite evaluation:
    # 8,000 records

  query_rewrite_summary_postgres.json
    # Authoritative v3 PostgreSQL rewrite summary

  tier2_questions.yaml
    # 10 realistic open-ended questions for manual Tier 2 review

  tier2_manual_scores.jsonl
    # Secondary portable manual-review event log

  llm_evaluation_questions.yaml
    # 24 fixed questions for prompt comparison

  llm_answers.jsonl
    # Generated prompt-comparison answers and validation results

  llm_judge_scores.jsonl
    # LLM-judge scores for prompt comparison

  llm_evaluation_summary.json
    # Prompt-level aggregates and selected prompt

  llm_evaluation_report.md
    # Human-readable prompt-evaluation report

docs/
  evaluation-notes.md
    # This document

  decisions.md
    # Decision records

  runbook.md
    # Reproducible operational instructions
```

The authoritative operational records for cached answers, feedback, and manual
scores are stored in PostgreSQL:

- `query_cache`
- `answer_feedback`
- `manual_scores`

Evaluation records should be reproducible without requiring raw corpus downloads, runtime feedback data, or external API credentials where feasible.

---

## Next steps

- ✅ Review and accept the normalised evidence outputs. **Completed 2026-08-22**
- ✅ Implement deterministic, section-aware chunk assembly over normalised blocks. **Completed 2026-08-23**
- ✅ Preserve citation-grade evidence text separately from embedding-oriented context text. **Completed**
- ✅ Add source authority, retrieval tier, currency, and applicability metadata to future chunks. **Completed**
- ✅ Create Tier 1 query set (100 LLM-generated queries). **Completed 2026-08-23**
- ✅ Establish historical lexical, vector-only, and hybrid retrieval baselines (v1). **Completed 2026-08-23**
- ✅ Extend the historical file-based evaluation with reranking, multiple alphas, weightings, and composite scoring (v2). **Completed 2026-08-23**
- ✅ Run the full production-aligned PostgreSQL retrieval grid: 100 queries × 3 alphas × 5 variants × 5 weightings = 7,500 records. **Completed 2026-09-05**
- ✅ Run the production-aligned PostgreSQL cached query-rewrite evaluation: 100 queries × 4 rewrite techniques × 4 retrieval variants × 5 weightings = 8,000 records. **Completed 2026-09-05**
- ✅ Select a production retrieval configuration from the PostgreSQL evaluation. **Completed: expanded query + vector rerank**
- ✅ Add evaluator and summariser regression tests. **Completed**
- ✅ Create Tier 2 question set with 10 realistic open-ended questions. **Completed 2026-09-05**
- ✅ Implement answer generation with citation support. **Completed 2026-09-05**
- ✅ Complete the 24-question prompt-comparison evaluation with deterministic citation validation and an LLM judge. **Completed 2026-09-05**
- ✅ Implement Streamlit Review workflow for Tier 2 manual evaluation. **Completed 2026-09-05**
- ✅ Persist manual-review scores in PostgreSQL and JSONL. **Completed 2026-09-05**
- ✅ Add Tier 2 coverage and manual-score monitoring. **Completed 2026-09-05**
- ⏳ Collect sufficient manual reviews for stable Tier 2 aggregate results. **Pending**
- ⏳ Run paired statistical testing for original versus expanded query variants. **Pending**
- ⏳ Create a manually judged relevance set to complement metadata-derived labels. **Pending**
- ⏳ Validate a sample of LLM-judge scores against human reviewers. **Pending**