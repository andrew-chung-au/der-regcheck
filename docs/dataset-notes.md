# Dataset notes

## Corpus overview

**Market:** California, United States
**Regulator:** California Public Utilities Commission (CPUC)
**Primary utility:** Southern California Edison (SCE)
**Topic:** DER interconnection, technical requirements, communications/telemetry, testing, and certification
**Corpus role:** v1 research corpus for the DER RegCheck evidence-first RAG prototype
**Total sources:** 6 public documents: 5 PDF and 1 HTML
**Total chunks:** 1,049 searchable chunks (2026-08-23)
**Embeddings:** 1,049 Nomic vectors (768-dim)
**Authoritative retrieval evaluation:** Production-aligned PostgreSQL/pgvector evaluation completed 2026-09-05

---

## Data lifecycle

DER RegCheck preserves separate, tracked representations of source content:

```text
data/corpus/
→ source downloads and manual replacements

data/processed/extracted/
→ raw deterministic extraction outputs

data/processed/normalised/
→ deterministic evidence-block derivatives for chunking

data/processed/chunks/
→ 1,049 searchable chunks with citations and metadata

data/processed/embeddings/
→ 1,049 Nomic embeddings (768-dim vectors)

data/evaluation/
→ 100 retrieval benchmarking queries
→ historical file-based v1/v2 retrieval artifacts
→ authoritative PostgreSQL/pgvector v3 retrieval and query-rewrite artifacts
```

### Raw corpus files

Raw downloaded files in `data/corpus/` are ignored by Git.

Trust and eligibility are controlled by `data/corpus/corpus_metadata.json`, not by file location. Metadata records:

- Content hash
- Last-checked timestamp
- Automated validation status
- Manual review status
- Manual reviewer identity where applicable
- Extraction eligibility
- Default retrieval eligibility
- Acquisition method

### Raw extraction outputs

Raw extraction outputs in `data/processed/extracted/` are intentionally tracked.

They preserve source evidence without applying chunking, source authority policy, LLM enrichment, embeddings, retrieval ranking, or answer generation.

Raw extraction metadata includes:

- `schema_version`
- `extraction_method`
- Source ID
- Source content hash
- Source URL
- Extraction timestamp
- PDF physical pages or HTML blocks
- PDF page markers or HTML heading paths

### Normalised evidence outputs

Normalised outputs in `data/processed/normalised/` are intentionally tracked.

They are deterministic derivatives of raw extraction outputs and are the input to structural chunking.

Normalised blocks preserve:

- Source ID and source content hash
- Stable block order
- Block type
- Evidence text
- PDF physical page locator or HTML heading-path locator
- Source-specific citation metadata where available
- Normalisation flags for known review limitations

The normalisation stage does not alter raw extraction artifacts.

### Chunk outputs

Chunk outputs in `data/processed/chunks/` are intentionally tracked.

They are deterministic derivatives of normalised evidence blocks, designed for retrieval and embedding.

Chunk metadata includes:

- `chunk_id` (stable, source-scoped identifier)
- `source_id` and `document_id`
- `source_content_hash` (provenance)
- `block_ids` (constituent normalised blocks)
- `block_types` (heading, paragraph, list_item, table, etc.)
- `evidence_text` (unchanged from normalised blocks, citation-grade)
- `embedding_text` (evidence text with heading context prepended)
- `heading_path` (for HTML and tariff sources)
- `citation` (PDF pages, tariff sheets, Cal. PUC sheets, section IDs)
- `source_policy` (authority tier, retrieval tier)
- `neighbour_chunk_ids` (previous/next for navigation)
- `oversized` flag (for blocks exceeding hard token limit)

Chunking configuration (2026-08-23):

- Soft max: 500 tokens
- Hard max: 750 tokens
- Overlap: 90 tokens (for oversized chunks only)
- 1,049 chunks generated across 6 sources
- 5 oversized chunks (all handbook TOC blocks, accepted as documented exceptions)

### Embedding outputs

Embedding outputs in `data/processed/embeddings/` are intentionally tracked.

They are 768-dimensional vectors generated from chunk `embedding_text` using Nomic `nomic-embed-text-v1.5`.

Embedding metadata includes:

- `chunk_id` (matches chunk output)
- `vector` (768-dim array)
- `embedding_model` (`nomic-ai/nomic-embed-text-v1.5`)
- `embedding_prefix` (`search_document:`)
- `embedding_timestamp`

Embedding configuration (2026-08-23):

- Model: `nomic-ai/nomic-embed-text-v1.5`
- Dimension: 768
- Prefix: `search_document:` on chunk text, `search_query:` on query text
- 1,049 embeddings generated (one per chunk)

### Evaluation artifacts

Evaluation artifacts in `data/evaluation/` are intentionally tracked.

They preserve both historical file-based experiments and the authoritative production-aligned PostgreSQL evaluation.

**Tier 1 query benchmark:**

- `queries.jsonl`: 100 LLM-generated queries (`gemini-3.5-flash-lite`, 2026-08-23)
- `query_rewrites.jsonl`: Cached query-rewrite variants (`original`, `expanded`, `hyde`, `hyde_expanded`)

**Historical file-based retrieval evaluation artifacts (v1 and v2):**

- `evaluation_results.jsonl`:
  - v1: 1,500 retrieval results (100 queries × 3 retrievers × 5 weightings)
  - v2: historical file-based retrieval results, including reranking, alpha sweeps, weighting schemes, and composite scoring
- `evaluation_summary.json`: Historical aggregated metrics
- `query_rewrite_results.jsonl`: Historical cached query-rewrite evaluation results
- Historical v1 and v2 results are retained as offline-baseline artifacts and must not be directly compared numerically with v3.

**Authoritative production-aligned PostgreSQL evaluation artifacts (v3, 2026-09-05):**

- `evaluation_results_postgres.jsonl`:
  - 7,500 retrieval evaluation records
  - 100 queries × 3 alpha values × 5 retrieval variants × 5 metadata weighting schemes
- `evaluation_summary_postgres.json`:
  - Aggregated nDCG@10, MRR, Recall@10, variability, composite score, and ranked configurations
- `query_rewrite_results_postgres.jsonl`:
  - 8,000 cached query-rewrite evaluation records
  - 100 queries × 4 rewrite techniques × 4 retrieval variants × 5 metadata weighting schemes
- `query_rewrite_summary_postgres.json`:
  - Aggregated rewrite-evaluation metrics and ranked configurations

**Tier 2: RAG quality evaluation** (pending)

- `rag_eval_cases.jsonl`: 5-10 open-ended questions (to be created)
- `answer_results/`: Generated answers and human scores (to be created)

---

## Source list

### 1. CPUC Electric Rule 21 overview page

- **Source ID:** `cpuc_rule21_overview`
- **URL:** [https://www.cpuc.ca.gov/Rule21/](https://www.cpuc.ca.gov/Rule21/)
- **Type:** HTML
- **Corpus role:** Regulatory context and discovery of authoritative sources
- **Default retrieval tier:** `source_discovery`
- **Authority level:** Regulatory overview; not controlling tariff text
- **Filename:** `01_cpuc_rule21_overview.html`
- **Local path:** `data/corpus/01_cpuc_rule21_overview.html`
- **Raw extraction method:** `beautifulsoup_main_content_blocks`
- **Normalisation status:** Pass
- **Chunk count:** 12 chunks
- **Extraction issues:** None identified in the current review.
- **Normalisation notes:** Preserves HTML heading paths, paragraphs, list items, and tables. The table-of-contents heading path is excluded from normalised evidence output.
- **Notes:** Provides links to tariff, handbooks, and related CPUC pages. Useful for context and source discovery, not treated as a primary requirements source.

---

### 2. SCE Rule 21 tariff (PDF)

- **Source ID:** `sce_rule21_tariff_pdf`
- **URL:** [https://www.sce.com/sites/default/files/custom-files/PDF_Files/ELECTRIC_RULES_21.pdf](https://www.sce.com/sites/default/files/custom-files/PDF_Files/ELECTRIC_RULES_21.pdf)
- **Type:** PDF
- **Corpus role:** Primary interconnection requirements
- **Default retrieval tier:** `primary_requirements`
- **Authority level:** Primary tariff / governing source
- **Filename:** `02_sce_rule21_tariff.pdf`
- **Local path:** `data/corpus/02_sce_rule21_tariff.pdf`
- **Raw extraction method:** `pypdf_page_text`
- **Normalisation status:** Pass
- **Chunk count:** 387 chunks
- **Extraction issues:** PDF signature validation passes.
- **Normalisation notes:**
  - Uses a dedicated deterministic SCE Rule 21 tariff parser.
  - Removes recurring administrative Cal. PUC sheet material from normalised evidence blocks.
  - Excludes Table of Contents pages from normalised evidence blocks.
  - Preserves tariff hierarchy across lettered sections, numbered provisions, lettered subsections, selected Roman-numeral subheadings, and appendices.
  - Retains prose-style Roman-numeral entries as list items.
  - Resets hierarchy at appendices, including `APPENDIX B`.
  - Preserves Rule 21 sheet number, Cal. PUC sheet number, effective date, and advice letter as citation metadata.
- **Known limitation:** Raw `pypdf` layout artifacts can preserve spaces inside words. These are retained in citation-grade evidence text rather than automatically repaired.
- **Notes:** Controlling document for interconnection, operating, and metering requirements. Contains sheet-level supersession cues such as `Cancelling Revised Cal. PUC Sheet No.`.

---

### 3. SCE Interconnection Handbook (PDF)

- **Source ID:** `sce_interconnection_handbook_pdf`
- **URL:** [https://on.sce.com/InterconnectionHandbook](https://on.sce.com/InterconnectionHandbook)
- **Type:** PDF
- **Corpus role:** Technical implementation detail
- **Default retrieval tier:** `primary_technical`
- **Authority level:** Primary technical handbook; secondary to the tariff in the event of conflict
- **Filename:** `03_sce_interconnection_handbook.pdf`
- **Local path:** `data/corpus/03_sce_interconnection_handbook.pdf`
- **Raw extraction method:** `pypdf_page_text`
- **Normalisation status:** Pass
- **Chunk count:** 562 chunks
- **Extraction issues:**
  - Automated download intermittently returns HTML or SharePoint authentication material instead of a PDF.
  - Repeated automated requests triggered what appeared to be a temporary block.
  - The source was manually replaced and approved through corpus metadata.
- **Normalisation notes:**
  - Excludes cover, approval, table-of-contents, and DocuSign certificate pages.
  - Removes repeated document-control notices, version headers, effective-date headers, DocuSign envelope IDs, and `Requirement | Page N` page-header text.
  - Preserves PDF physical page locators and detected Part, Section, and clause hierarchy.
- **Chunking notes:**
  - 5 oversized chunks (1,033-1,561 tokens) are handbook TOC blocks.
  - These are dense list-of-lists blocks, not substantive requirements.
  - Accepted as documented exceptions without splitting mid-evidence.
- **Notes:** Covers interconnection process details, protection requirements, telemetry, inverter performance, communications, metering, and testing-related requirements. Critical for technical research questions.

---

### 4. SCE Rule 21 interconnection web guidance

- **Source ID:** `sce_interconnection_web`
- **URL:** [https://www.sce.com/business/smart-energy-solar/solar-for-business/grid-interconnections/interconnecting-generation-under-rule-21](https://www.sce.com/business/smart-energy-solar/solar-for-business/grid-interconnections/interconnecting-generation-under-rule-21)
- **Type:** HTML
- **Corpus role:** Process guidance, forms, and source discovery
- **Default retrieval tier:** `supporting_process`
- **Authority level:** Supporting process guidance; not controlling
- **Filename:** `04_sce_interconnection_web.html`
- **Local path:** `data/corpus/04_sce_interconnection_web.html`
- **Raw extraction method:** `beautifulsoup_main_content_blocks`
- **Normalisation status:** Pass
- **Chunk count:** 8 chunks
- **Extraction issues:** None identified in the current review.
- **Normalisation notes:** Preserves HTML heading paths, paragraphs, list items, and tables.
- **Notes:** Summarises Rule 21 process, links to forms, testing information, pre-application information, study tracks, and Customer-Owned Telemetry procedures. Useful for process questions but not treated as a primary requirements source.

---

### 5. Smart Inverter Working Group Phase 2 Recommendations (PDF)

- **Source ID:** `siwg_phase2_recommendations_pdf`
- **URL:** [https://www.cpuc.ca.gov/-/media/cpuc-website/divisions/energy-division/documents/rule21/smart-inverter-working-group/siwg_phase_2.pdf](https://www.cpuc.ca.gov/-/media/cpuc-website/divisions/energy-division/documents/rule21/smart-inverter-working-group/siwg_phase_2.pdf)
- **Type:** PDF
- **Corpus role:** Historical context and standards rationale
- **Default retrieval tier:** `historical_context`
- **Authority level:** Historical/draft material; excluded from default current-requirement retrieval
- **Filename:** `05_siwg_phase2_recommendations.pdf`
- **Local path:** `data/corpus/05_siwg_phase2_recommendations.pdf`
- **Raw extraction method:** `pypdf_page_text`
- **Normalisation status:** Review
- **Chunk count:** 68 chunks
- **Extraction issues:** PDF signature validation passes.
- **Normalisation notes:**
  - Excludes cover and contents pages.
  - Retains physical PDF page provenance.
  - Six early substantive blocks remain flagged with `no_detected_heading_path`.
- **Notes:** Provides historical rationale for smart inverter functions, communications, and data categories. It must not be presented as a current controlling requirement unless a user explicitly requests historical or draft context.

---

### 6. SCE testing and certification instruction sheet (PDF)

- **Source ID:** `sce_testing_certification_instruction_pdf`
- **URL:** [https://www.sce.com/sites/default/files/custom-files/PDF_Files/Rule_21_Testing_and_Certification_Instruction_Sheet_Final_2025-06-05.pdf](https://www.sce.com/sites/default/files/custom-files/PDF_Files/Rule_21_Testing_and_Certification_Instruction_Sheet_Final_2025-06-05.pdf)
- **Type:** PDF
- **Corpus role:** Equipment testing and certification implementation guidance
- **Default retrieval tier:** `supporting_implementation`
- **Authority level:** Supporting implementation guidance
- **Filename:** `06_sce_testing_certification.pdf`
- **Local path:** `data/corpus/06_sce_testing_certification.pdf`
- **Raw extraction method:** `pypdf_page_text`
- **Normalisation status:** Review
- **Chunk count:** 72 chunks
- **Extraction issues:** PDF signature validation passes.
- **Normalisation notes:**
  - Excludes cover/disclaimer and contents pages.
  - Removes recurring `Instruction Sheet - Version 6/5/2025` page headers.
  - Detects numbered `Section N.` headings.
  - Seven blocks in early references and acronym material remain flagged with `no_detected_heading_path`.
- **Notes:** Describes testing and certification procedures for equipment compliance. Supports tariff and handbook requirements but is not itself controlling.

---

## Source hierarchy summary

| Authority level | Sources | Chunk count |
|---|---|---:|
| Primary tariff / governing source | SCE Rule 21 tariff | 387 |
| Primary technical handbook | SCE Interconnection Handbook | 562 |
| Supporting implementation guidance | SCE testing and certification instruction | 72 |
| Supporting process guidance | SCE Rule 21 interconnection web guidance | 8 |
| Source discovery / regulatory context | CPUC Rule 21 overview page | 12 |
| Historical/draft material | SIWG Phase 2 Recommendations | 68 |
| **Total** | **6 sources** | **1,049** |

---

## Version and currency notes

- All sources are tracked by content hash in `data/corpus/corpus_metadata.json`.
- Raw extraction outputs retain the source content hash used for extraction.
- Normalised blocks retain the source content hash used for evidence provenance.
- Chunks retain the source content hash used for chunking.
- Embeddings are derived from chunk `embedding_text` rather than `evidence_text`.
- Tariff normalisation preserves Rule 21 sheet number, Cal. PUC sheet number, effective date, and advice letter as citation metadata.
- Tariff PDF includes explicit supersession cues such as `Cancelling Revised Cal. PUC Sheet No.`.
- Web sources may change without explicit version markers; last-checked timestamps and hash changes are the primary currency signals.
- The handbook required manual replacement due to automated download blocking; metadata records the reviewer, approval status, hash, and retrieval eligibility.
- Normalised output quality must be reviewed after source refreshes, parser changes, or normalisation configuration changes.
- Chunk output quality must be reviewed after chunking configuration changes.
- A source refresh that changes source content, normalised evidence, chunks, or embeddings requires a new dated retrieval evaluation before the current v3 result is treated as applicable to the refreshed corpus.

---

## Quality and review notes

The current normalisation and chunking review result is:

| Source category | Normalisation result | Chunk count | Chunking notes |
|---|---|---:|---|
| Primary/current tariff and handbook sources | Pass | 949 | Handbook has 5 oversized TOC chunks (accepted) |
| HTML overview and process guidance sources | Pass | 20 | No issues |
| Supporting testing instruction | Review | 72 | Limited early-page heading-path warnings |
| Historical SIWG source | Review | 68 | Limited early-page heading-path warnings |

Interpretation rules:

- `pass` means no quality-report errors or review warnings were detected by the current checks.
- `review` means the output remains usable and traceable, but one or more blocks require manual interpretation or source-specific parser refinement before high-confidence reliance.
- `fail` means a quality-report error was detected and the source must not proceed to downstream chunking or retrieval without correction.
- A `no_detected_heading_path` warning is not a loss of physical PDF page provenance.
- Review warnings should not be removed by broad heuristics solely to make the quality report green.
- Oversized chunks (>750 tokens) are flagged but not split mid-evidence; handbook TOC blocks are accepted exceptions.

---

## Duplicates and exclusions

**Duplicates:** No adjacent duplicate normalised blocks or chunks were detected in the current quality reports.

**Exclusions:**

- PG&E, SDG&E, and other California utilities are out of scope for v1.
- Older tariff versions and historical handbooks are not included in the v1 corpus.
- Additional working-group reports and draft material beyond SIWG Phase 2 are not included in v1.
- Handbook cover, approval, contents, certificate, repeated document-control, and page-header material are excluded from normalised evidence blocks.
- Testing instruction cover/disclaimer and contents pages are excluded from normalised evidence blocks.
- SIWG cover and contents pages are excluded from normalised evidence blocks.
- SIWG Phase 2 is excluded from normal current-requirement retrieval because it is historical/draft context.
- Handbook TOC blocks exceeding 750 tokens are retained as documented exceptions (5 chunks).

---

## Retrieval evaluation summary

### Historical v1 evaluation (file-based, 2026-08-23)

**Queries:** 100 LLM-generated (`gemini-3.5-flash-lite`)
**Chunks:** 1,049
**Embeddings:** 1,049 (Nomic `nomic-embed-text-v1.5`, 768-dim)
**Results:** 1,500 (100 queries × 3 retrievers × 5 weightings)

**Selected configuration (v1):** Vector retrieval with equal weighting.

| Retriever | Weighting | nDCG@10 | MRR | Recall@10 |
|---|---|---:|---:|---:|
| Vector | Equal | 0.826 | 0.893 | 0.594 |
| Hybrid | Equal | 0.777 | 0.903 | 0.613 |
| BM25 | Equal | 0.745 | 0.815 | 0.563 |

**Key findings (v1):**

- Vector retrieval outperforms hybrid and BM25 on nDCG@10.
- Hybrid has best MRR.
- Weighting scheme has modest impact.
- Equal weighting performs best for vector retrieval.

**Historical status:** v1 used the earlier file-based, in-memory evaluator. It is retained as an offline baseline and is not directly comparable numerically with v3.

### Historical v2 evaluation (file-based, 2026-08-23)

**Queries:** 100
**Chunks:** 1,049
**Embeddings:** 1,049
**Results:** Historical file-based evaluation with reranking, multiple alphas, metadata weightings, composite scoring, and cached query-rewrite variants.

**Top configurations by composite score (0.5·nDCG + 0.3·MRR + 0.2·Recall):**

| Rank | Configuration | nDCG@10 | MRR | Recall@10 | Composite |
|---|---|---:|---:|---:|---:|
| 1 | hybrid_rerank__equal | 0.95080 | 0.95361 | 1.00000 | 0.96148 |
| 2 | hybrid_rerank__authority_heavy | 0.95074 | 0.95361 | 1.00000 | 0.96145 |
| 3 | hybrid_rerank__source_heavy | 0.95021 | 0.95361 | 1.00000 | 0.96119 |
| 4 | vector_rerank__equal | 0.94542 | 0.93750 | 0.99000 | 0.95196 |
| 5 | vector_rerank__authority_heavy | 0.94542 | 0.93750 | 0.99000 | 0.95196 |
| 6 | vector_rerank__source_heavy | 0.94412 | 0.93750 | 0.99000 | 0.95131 |

**Non-reranked top configurations (for comparison):**

| Configuration | nDCG@10 | MRR | Recall@10 | Composite |
|---|---:|---:|---:|---:|
| vector__equal | 0.75740 | 0.89293 | 0.33081 | 0.71274 |
| hybrid__equal | 0.70484 | 0.88124 | 0.32452 | 0.68170 |
| bm25__equal | 0.64293 | 0.81559 | 0.30105 | 0.62635 |

**Key findings (v2):**

- Reranking dominated the historical file-based evaluation.
- Hybrid plus reranking slightly exceeded vector plus reranking under the historical composite score.
- Weighting had small effects among the leading reranked configurations.
- Alpha had a smaller observed effect than reranking.

**Selected configuration (v2):** Hybrid retrieval with reranking and equal weighting (α = 0.5, RRF k = 1).

**Historical status:** v2 used the earlier file-based, in-memory evaluator. Its results are retained for development history but are not directly comparable with the deployed PostgreSQL evaluation.

### Authoritative v3 evaluation (production-aligned PostgreSQL/pgvector, 2026-09-05)

**Purpose:** Evaluate the deployed retrieval path rather than the earlier file-based evaluator.

**Queries:** 100 fixed LLM-generated benchmark queries
**Chunks:** 1,049
**Embeddings:** Runtime Nomic query embeddings and pgvector document retrieval
**Retrieval backend:** PostgreSQL full-text retrieval and pgvector vector retrieval
**Reranker:** `BAAI/bge-reranker-base`
**Candidate limit:** 50
**Final output size:** Top 10 chunks
**Hybrid alpha values:** 0.3, 0.5, 0.7
**Metadata weightings:** Equal, source-heavy, section-heavy, page-heavy, authority-heavy

**Completed retrieval grid:**

```text
100 queries
× 3 alpha values
× 5 retrieval variants
× 5 metadata weighting schemes
= 7,500 retrieval evaluation records
```

**Retrieval variants:**

- PostgreSQL lexical retrieval
- pgvector vector retrieval
- PostgreSQL-backed hybrid retrieval
- Hybrid retrieval with cross-encoder reranking
- Vector retrieval with cross-encoder reranking

**Final retrieval results:**

| Configuration | nDCG@10 | MRR | Recall@10 | Composite |
|---|---:|---:|---:|---:|
| Vector rerank, equal weighting | **0.94627** | **0.92500** | 0.09625 | **0.76989** |
| Vector rerank, authority-heavy weighting | **0.94627** | **0.92500** | 0.09625 | **0.76989** |
| Hybrid rerank, equal weighting, alpha 0.50 | 0.94589 | **0.92500** | 0.09625 | 0.76969 |
| Hybrid rerank, section-heavy weighting, alpha 0.30 | 0.93240 | 0.60800 | **0.11019** | 0.67065 |
| Hybrid, equal weighting, alpha 0.50 | 0.76700 | 0.87293 | 0.08580 | 0.66253 |
| Vector, equal weighting | 0.76330 | 0.87293 | 0.08480 | 0.66049 |
| Lexical, equal weighting | 0.15420 | 0.15500 | 0.00690 | 0.12499 |

**Key findings (v3):**

- Cross-encoder reranking produced the main observed ranking-quality improvement.
- Vector reranking achieved the highest observed nDCG@10, MRR, and composite score.
- Hybrid reranking was effectively tied on leading ranking metrics, but had a marginally lower composite score.
- Equal and authority-heavy weighting tied for the strongest vector-rerank result; equal weighting is the simpler default.
- Hybrid reranking with section-heavy weighting achieved the highest Recall@10 but did not lead on nDCG@10, MRR, or composite score.
- Alpha had little practical effect after reranking.
- PostgreSQL lexical retrieval was substantially weaker than vector retrieval on this benchmark.

### v3 cached query-rewrite evaluation

**Completed query-rewrite grid:**

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

**Leading rewrite results:**

| Configuration | nDCG@10 | MRR | Recall@10 | Composite |
|---|---:|---:|---:|---:|
| Expanded query + vector rerank, equal weighting | **0.94713** | **0.93583** | 0.09214 | **0.77274** |
| Original query + vector rerank, equal weighting | 0.94627 | 0.92500 | 0.09625 | 0.76989 |
| HyDE query + vector rerank, equal weighting | 0.89930 | 0.69980 | 0.08420 | 0.67643 |
| HyDE-expanded query + vector rerank, equal weighting | 0.88720 | 0.67200 | 0.08060 | 0.66131 |

**Query-rewrite findings:**

- Query expansion produced a modest improvement in nDCG@10, MRR, and composite score compared with the original query.
- Query expansion reduced Recall@10 slightly.
- HyDE and HyDE plus expansion reduced ranking quality on this corpus.
- The observed expansion improvement is small and requires paired statistical testing or manually judged relevance data before a strong superiority claim.

### Current selected retrieval configuration

```text
Expanded query
→ pgvector vector retrieval
→ BAAI/bge-reranker-base cross-encoder reranking
→ top 10 evidence chunks
```

**Selection rationale:**

- Highest observed production-aligned composite score: 0.77274.
- Highest observed production-aligned nDCG@10: 0.94713.
- Highest observed production-aligned MRR: 0.93583.
- Simpler than hybrid retrieval because it does not depend on the relatively weak lexical baseline.
- HyDE is disabled because it reduced retrieval quality in the benchmark.
- The production-aligned evaluation is authoritative because it measures the deployed PostgreSQL/pgvector retrieval path.

### Evaluation limitations

- The historical file-based v1 and v2 scores are separate experimental conditions and are not directly comparable with v3.
- Migrating the evaluator changed multiple implementation details, so the evaluation cannot show that PostgreSQL alone caused any observed difference.
- Relevance is metadata-derived rather than independently human-labelled semantic relevance.
- Recall@10 measures retrieval of the metadata-defined relevant set, not the proportion of user questions answered successfully.
- The benchmark queries are synthetic and generated from the corpus; they may not represent real user-query distributions.
- Tier 1 retrieval scores do not establish answer groundedness, citation correctness, completeness, source hierarchy handling, or regulatory applicability.
- Tier 2 answer-quality evaluation is required before making end-to-end RAG-quality claims.

**Reference:** See `docs/evaluation-notes.md` for the complete evaluation protocol, interpretation, limitations, and Tier 2 RAG-evaluation plan. See `docs/decisions.md` #12 for the authoritative production-aligned retrieval-selection decision.

---

## Future corpus extensions

Potential additions for later versions:

- Additional California utilities, including PG&E and SDG&E.
- Older tariff and handbook versions for version-comparison retrieval.
- More working-group reports and CPUC decisions related to DER interconnection and smart inverters.
- SCE forms, application instructions, and supporting process materials where their authority and currency can be recorded.
- Other markets, including ERCOT, NYISO, and AEMO, for cross-market comparison.
- Tier 2 RAG evaluation queries (5-10 open-ended questions with stronger model).
- Manual answer quality scores for Tier 2 evaluation.
- Paired statistical testing of original versus expanded query variants.
- A manually judged relevance set to complement metadata-derived relevance labels.
- Source refresh and re-evaluation procedures as the corpus evolves.