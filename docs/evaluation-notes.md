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
- Empirical retrieval evaluation results (Tier 1 v1 and v2)

**Status:** Evaluation framework defined. Raw extraction and deterministic normalisation implemented. **Chunking, embedding, and retrieval benchmarking completed (2026-08-23, with extended evaluation including reranking and composite scoring).** Answer generation and RAG quality evaluation remain to be implemented.

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
→ queries, qrels, and results

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

**Purpose:** Compare retrieval configurations (BM25, vector, hybrid, hybrid + rerank, vector + rerank) and tune chunking/embedding parameters.

**Query set:** 100 LLM-generated queries (Gemini 3.5-flash-lite), each tied to a specific gold chunk.

**Metrics:** nDCG@10, MRR, Recall@10, and a composite score (0.5·nDCG + 0.3·MRR + 0.2·Recall).

**Strengths:**
- Fast, reproducible, no manual labelling required
- Statistically powerful (100 queries)
- Good for relative comparison of retrievers and weighting schemes

**Limitations:**
- Single gold chunk per query (doesn't test multi-evidence retrieval)
- Doesn't evaluate answer quality, only retrieval ranking
- Query quality depends on LLM generation

**Location:** `data/evaluation/queries.jsonl` (100 queries), `data/evaluation/evaluation_results.jsonl` (8,100 retrieval results in v2 evaluation)

### Tier 2: RAG quality evaluation (manual, realistic)

**Purpose:** Evaluate end-to-end RAG quality on realistic, open-ended questions that require multi-evidence synthesis.

**Query set:** 5-10 open-ended questions (originally LLM-generated with Gemini 2.5 Pro or similar), each with multiple relevant chunks across sources.

**Metrics:** Human-scored rubric (groundedness, citation correctness, source hierarchy, completeness, usefulness, etc.)

**Strengths:**
- Realistic RAG evaluation (answers, not just retrieval)
- Tests multi-evidence synthesis and source hierarchy reasoning
- Captures answer quality dimensions retrieval metrics miss

**Limitations:**
- Requires manual scoring (slower, less scalable)
- Smaller query set (5-10 questions)
- Subject to human judgment variability

**Location:** `data/evaluation/rag_eval_cases.jsonl` (to be created), `data/evaluation/answer_results/` (to be created)

**Relationship:** Tier 1 tells you which retriever is best. Tier 2 tells you whether the best retriever produces good answers.

---

## Tier 1: Retrieval benchmarking

### Query generation

**Query set:** 100 LLM-generated queries (Gemini 3.5-flash-lite, 2026-08-23).

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

**Metadata-based relevance:** Evaluation uses metadata matching instead of manual labelling:

- **Source match:** `retrieved.source_id == gold.source_id`
- **Section match:** Overlapping `section_ids`
- **Page proximity:** `abs(retrieved_page - gold_page) <= 2`
- **Block-type match:** Overlapping `block_types`
- **Authority-tier match:** Same `authority_tier`

**Composite metadata score:**

```python
metadata_score = (
    0.20 * source_match +
    0.20 * section_match +
    0.20 * page_proximity +
    0.20 * block_type_match +
    0.20 * authority_match
)
```

**Five weighting schemes tested:**
1. **Equal:** All weights = 0.20
2. **Source-heavy:** Source = 0.40, others = 0.15
3. **Section-heavy:** Section = 0.40, others = 0.15
4. **Page-heavy:** Page = 0.40, others = 0.15
5. **Authority-heavy:** Authority = 0.30, others = 0.175

**Relevance threshold:** `metadata_score >= 0.5` counts as relevant

**Location:** `data/evaluation/evaluation_results.jsonl` (8,100 retrieval records in v2: multiple retrievers × alphas × weightings)

### Metrics

Retrieval benchmarking uses:

- **nDCG@10:** Ranking quality with graded relevance
- **MRR (Mean Reciprocal Rank):** How early the first relevant result appears
- **Recall@10:** Proportion of relevant chunks in top-10 results
- **Composite score:** 0.5·nDCG@10 + 0.3·MRR + 0.2·Recall@10 (used as a tie-breaker and overall quality indicator)

**Computation:** Metadata-based relevance (no manual labelling required)

### Retrieval configurations compared (v2 evaluation)

1. **BM25:** Token overlap similarity (lexical baseline)
2. **Vector:** Cosine similarity with Nomic embeddings (768-dim)
3. **Hybrid:** Reciprocal Rank Fusion of BM25 + Vector (alpha ∈ {0.3, 0.5, 0.7}, RRF-style fusion)
4. **Hybrid + rerank:** Cross-encoder (BAAI/bge-reranker-base) on top of hybrid candidates
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

**Hybrid fusion:** RRF-style with configurable α and k (current default: α = 0.5, k = 1; course-aligned k sweep planned).

### Baseline results (v1: 2026-08-23)

**Queries:** 100 (LLM-generated with Gemini 3.5-flash-lite)  
**Chunks:** 1,049 (embedded with Nomic)  
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
   - Vector range: 0.793–0.826 (4% difference)
   - Equal weighting performs best for vector retrieval

3. **Hybrid has best MRR**
   - Hybrid MRR: 0.903 (better at getting #1 result right)
   - Vector MRR: 0.893

4. **Vector has best overall ranking quality**
   - Best nDCG@10: Vector with equal weighting (0.826)
   - Best MRR: Hybrid with equal weighting (0.903)
   - Best Recall@10: Vector with page-heavy (0.650)

**Selected configuration (v1):** Vector retrieval with equal weighting

### Extended results (v2: 2026-08-23, with reranking and composite score)

**Queries:** 100  
**Chunks:** 1,049  
**Results:** 8,100 retrieval records (multiple retrievers × alphas × weightings)

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
   - Best reranked (hybrid_rerank__equal) nDCG@10 ≈ 0.951 vs best non-reranked (vector__equal) ≈ 0.757.
   - Recall@10 jumps from ~0.33–0.61 (non-reranked) to 0.95–1.00 (reranked).
2. **Weighting matters little once reranking is used**
   - Among `hybrid_rerank` and `vector_rerank`, differences across weightings are in the 4th–5th decimal for nDCG and composite.
   - Equal weighting has a tiny edge on composite and is simplest to justify.
3. **Hybrid + rerank slightly edges vector + rerank**
   - hybrid_rerank__equal composite: 0.96148
   - vector_rerank__equal composite: 0.95196
   - Difference is small but consistent across metrics.
4. **Alpha (0.3–0.7) has modest impact relative to reranking**
   - All alphas tested with reranking yield similar top-line performance.
   - α = 0.5 chosen as a sensible default.
5. **RRF k sweep planned**
   - Current default behaves like RRF k = 1.
   - Course-aligned sweep over k ∈ {1, 20, 60, 100} planned to fine-tune hybrid behaviour.

**Selected configuration (v2):** Hybrid retrieval with reranking and equal weighting (α = 0.5, RRF k = 1).

**Reference:** Full configuration rationale and decision record are in `docs/decisions.md` #11 (Embedding and retrieval evaluation v2), which supersedes #09.

---

## Tier 2: RAG quality evaluation

### Open-ended evaluation questions

These questions evaluate research-plan structure, source hierarchy, category coverage, uncertainty communication, and usefulness for preliminary market-entry research.

**Status:** To be regenerated with a stronger model (Gemini 2.5 Pro or equivalent) for higher-quality, realistic RAG evaluation.

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
- Avoid treating source discovery pages or historical material as equivalent to the tariff.

### Preconditions

Generated-answer evaluation must not begin until:

- ✅ Tier 1 retrieval baseline exists. **Completed 2026-08-23 (v1 and v2)**
- ✅ Retrieved evidence retains source and locator metadata. **Completed**
- ⏳ The answer generator can cite retrieved evidence blocks or chunks. **Pending**
- ⏳ The generation prompt distinguishes source authority, currency, applicability, uncertainty, and historical context. **Pending**
- ⏳ The system can state when evidence is insufficient rather than infer unsupported requirements. **Pending**

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

- **0:** Ignores source currency, project conditions, jurisdiction, utility, or interconnection-pathway applicability.
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

*To be defined after retrieval is implemented.*

Candidate variants:

- Base grounded-answer prompt with mandatory citations.
- Prompt with explicit source-hierarchy instructions.
- Prompt with explicit current-versus-historical source handling.
- Prompt requiring an applicability and uncertainty section.
- Prompt requiring an evidence-gap and validation-actions section.
- Preliminary market-entry evidence-brief template.
- Concise evidence-answer template for focused questions.

---

## Configuration-selection decisions

**Selected configuration (v1, 2026-08-23):**

| Component | Selection | Rationale |
|---|---|---|
| **Chunking** | Structural block assembly | Preserves citations, keeps headings with content |
| **Embedding model** | Nomic nomic-embed-text-v1.5 | 768-dim, asymmetric retrieval (`search_document:`/`search_query:`) |
| **Retrieval** | Vector (cosine similarity) | Best nDCG@10 (0.826) |
| **Weighting scheme** | Equal (all metadata = 0.20) | Best performance for vector retrieval |
| **Hybrid method** | Reciprocal Rank Fusion (alpha=0.5) | Good MRR (0.903) but lower nDCG than vector |
| **Reranking** | Not yet implemented | Pending cross-encoder evaluation |
| **Source filtering** | Not yet implemented | Pending source-tier and currency rules |
| **Answer generation** | Pending | Gemini 3.5-flash-lite or stronger planned |
| **Prompt variant** | Pending | Base grounded-answer prompt with citations planned |

**Selected configuration (v2, 2026-08-23):**

| Component | Selection | Rationale |
|---|---|---|
| **Chunking** | Structural block assembly | Preserves citations, keeps headings with content |
| **Embedding model** | Nomic nomic-embed-text-v1.5 | 768-dim, asymmetric retrieval (`search_document:`/`search_query:`) |
| **Retrieval** | Hybrid + rerank (BAAI/bge-reranker-base) | Best composite score (0.961), nDCG@10 ≈ 0.951, Recall@10 = 1.000 |
| **Hybrid α** | 0.5 | Balanced BM25 + vector contribution; modest sensitivity across 0.3–0.7 |
| **RRF k** | 1 (default; course-aligned sweep planned) | Current implementation; k ∈ {1, 20, 60, 100} planned |
| **Weighting scheme** | Equal (all metadata = 0.20) | Tiny edge on composite; simplest to justify among near-tied reranked configs |
| **Reranking** | Implemented (cross-encoder on top-50 candidates → top-10) | Large quality gain vs non-reranked; dominates design choice |
| **Source filtering** | Not yet implemented | Pending source-tier and currency rules |
| **Answer generation** | Pending | Gemini 3.5-flash-lite or stronger planned |
| **Prompt variant** | Pending | Base grounded-answer prompt with citations planned |

**Trade-offs:**

- Reranking adds latency and a model dependency (BAAI/bge-reranker-base) but yields large quality gains (nDCG@10 ~ 0.95 vs ~ 0.76).
- Equal weighting is simpler to justify and implement, at the cost of ignoring small, uncertain gains from tuned weightings.
- File-based evaluation is reproducible and peer-review friendly, but requires separate database logic for production.
- Synthetic queries are scalable and systematic, but may not capture all real-world query patterns; manual queries can be added later.
- Two-tier evaluation balances scalable retrieval benchmarking (Tier 1) with realistic RAG quality evaluation (Tier 2).

---

## Evaluation artifacts

**Committed evaluation artifacts:**

```text
data/evaluation/
  queries.jsonl                  # 100 LLM-generated queries for Tier 1 (retrieval benchmarking)
  evaluation_results.jsonl       # 8,100 retrieval results (v2: multiple retrievers × alphas × weightings)
  evaluation_summary.json        # Aggregated metrics (per configuration, best by metric, recommended by composite)
  query_rewrites.jsonl           # Cached query-rewrite variants (original, hyde, expanded, hyde_expanded)
  query_rewrite_results.jsonl    # Rewrite evaluation results (technique × retriever × weighting)
  rag_eval_cases.jsonl           # 5-10 open-ended questions for Tier 2 (to be created)
  answer_results/                # Generated answers and human scores (to be created)

docs/
  evaluation-notes.md            # This document
  decisions.md                   # Decision records, including #11 (Embedding and retrieval evaluation v2)
```

Evaluation records should be reproducible without requiring raw corpus downloads, runtime feedback data, or external API credentials where feasible.

---

## Next steps

- ✅ Review and accept the normalised evidence outputs. **Completed 2026-08-22**
- ✅ Implement deterministic, section-aware chunk assembly over normalised blocks. **Completed 2026-08-23**
- ✅ Preserve citation-grade evidence text separately from embedding-oriented context text. **Completed**
- ✅ Add source authority, retrieval tier, currency, and applicability metadata to future chunks. **Completed**
- ✅ Create Tier 1 query set (100 LLM-generated queries). **Completed 2026-08-23**
- ✅ Establish lexical, vector-only, and hybrid retrieval baselines (v1). **Completed**
- ✅ Extend evaluation to include reranking, multiple alphas, all weightings, and composite scoring (v2). **Completed**
- ✅ Select retrieval configuration (hybrid + rerank, equal weighting, α = 0.5). **Completed**
- ⏳ Run RRF k sweep (k ∈ {1, 20, 60, 100}) to align with course experiments. **Pending**
- ⏳ Create Tier 2 query set (5-10 open-ended questions, stronger model). **Pending**
- ⏳ Implement answer generation with citation support. **Pending**
- ⏳ Generate answers for Tier 2 questions. **Pending**
- ⏳ Score answers using rubric (groundedness, citation correctness, etc.). **Pending**
- ⏳ Record empirical RAG-quality results and configuration-selection decisions in this document. **Pending**