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
**Runtime retrieval configuration:** Original user query → pgvector vector retrieval → `BAAI/bge-reranker-base` reranking → top 10 evidence chunks
**Answer-generation evaluation:** 24-question prompt comparison completed 2026-09-05; `v3_few_shot_grounded_rag` selected under the deterministic citation-validity guardrail
**Tier 2 RAG-quality evaluation:** 10 realistic open-ended questions created 2026-09-05; Streamlit Review workflow, PostgreSQL manual-score storage, and Monitoring coverage chart implemented; aggregate human-review results remain pending
**RAG-impact evaluation:** Four-condition automated evaluation completed 2026-09-06 using the 10-question Tier 2 set; it compares no-evidence and evidence-backed answer conditions. Detailed protocol, results, interpretation, and limitations are recorded in [`docs/evaluation-notes.md`](evaluation-notes.md).

---

## Data lifecycle

DER RegCheck preserves separate, tracked representations of source content:

```text
data/corpus/
→ source downloads and manual replacements (not committed to Git)

data/processed/extracted/
→ raw deterministic extraction outputs (committed)

data/processed/normalised/
→ deterministic evidence-block derivatives for chunking (committed)

data/processed/chunks/
→ 1,049 searchable chunks with citations and metadata (committed)

data/processed/embeddings/
→ 1,049 Nomic embeddings (768-dim vectors) (committed)

data/evaluation/
→ 100 retrieval benchmarking queries
→ historical file-based v1/v2 retrieval artifacts
→ authoritative PostgreSQL/pgvector v3 retrieval and query-rewrite artifacts
→ 24 fixed answer-evaluation questions
→ generated answers, citation-validation results, LLM judge scores, and prompt-selection reports
→ 10 Tier 2 realistic RAG-quality questions
→ manual-review scores (PostgreSQL authoritative; JSONL secondary log)
→ RAG-impact answer, judge, summary, and report artifacts
```

### Distribution and copyright

The v1 corpus consists of public regulatory and utility documents (CPUC and SCE). The code in this repository is provided under the MIT License.

The source documents remain the property of their respective owners and are included here for research and educational purposes only. To avoid redistributing raw PDF/HTML files, the repository commits processed, machine-readable derivatives (extracted text, normalised blocks, chunks, and embeddings). The ingestion scripts are provided for future corpus refreshes; one source may require manual replacement due to intermittent automated-download blocking.

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

**Answer-generation prompt evaluation (completed 2026-09-05):**

- `llm_evaluation_questions.yaml`:
  - 24 fixed questions across six categories:
    - `direct_factual`
    - `multi_chunk_synthesis`
    - `ambiguous_needs_clarification`
    - `out_of_corpus`
    - `high_stakes_boundary`
    - `historical_source_handling`
- `llm_answers.jsonl`:
  - Generated answer records for `v1_direct_rag`, `v2_structured_grounded_rag`, and `v3_few_shot_grounded_rag`
  - Includes retrieved chunk IDs, evidence labels, model output, parsed answer data, and deterministic citation-validation results
- `llm_judge_scores.jsonl`:
  - LLM-judge scores for groundedness, relevance, completeness, citation quality, and appropriate uncertainty
- `llm_evaluation_summary.json`:
  - Prompt-level aggregate metrics and the selected configuration
- `llm_evaluation_report.md`:
  - Human-readable prompt-comparison report
- Selected prompt:
  - `v3_few_shot_grounded_rag`
  - Selected because it was the only evaluated configuration with 100% deterministic citation validity

**Tier 2 realistic RAG-quality evaluation (infrastructure complete 2026-09-05):**

- `tier2_questions.yaml`:
  - 10 realistic open-ended questions for manual RAG-quality review
  - Categories: direct factual, multi-chunk synthesis, clarification-sensitive, out-of-corpus, historical-source handling, high-stakes boundary
  - Five questions are used as examples in the Streamlit Ask tab; all ten are available in the Review tab
- `tier2_manual_scores.jsonl`:
  - Secondary portable manual-review event log
  - PostgreSQL `manual_scores` table is the operational source of truth
  - Each score is linked to a configuration-specific cached response through `query_cache.cache_id`
  - Multiple review events may be recorded for the same cached response

**RAG-impact evaluation (completed 2026-09-06):**

- `impact_answers.jsonl`:
  - 40 generated answers across 10 Tier 2 questions and four answer conditions
  - Conditions: naive model-only, no-evidence v3, zero-shot RAG, and full v3 RAG
  - Includes retrieved chunk IDs, evidence labels, parsed outputs, generation metrics, and deterministic citation-label validation
- `impact_judge_scores.jsonl`:
  - Blinded pairwise judge results for the five configured comparison types per question
  - Includes dimension scores, pairwise preferences, confidence ratings, and rationales
- `impact_summary.json`:
  - Machine-readable aggregate results, pairwise preferences, pooled judge scores, generation metrics, and answer-status distributions
- `impact_report.md`:
  - Human-readable impact-evaluation report with interpretation and limitations

Detailed findings are intentionally maintained in [`docs/evaluation-notes.md`](evaluation-notes.md), rather than duplicated here.

**Future manually reviewed RAG-quality evaluation:**

- Additional manual reviews to populate stable Tier 2 aggregate results
- Independent or human answer-quality scoring to complement the completed LLM-judge prompt comparison
- Paired statistical testing of original versus expanded query variants
- A manually judged relevance set to complement metadata-derived relevance labels

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

All historical (v1/v2) and authoritative production-aligned (v3) retrieval evaluation metrics, configuration comparisons, runtime configuration details, and query-rewrite findings have been consolidated. Please refer directly to [`docs/evaluation-notes.md`](docs/evaluation-notes.md) for the definitive evaluation artifacts, result tables, limitations, and composite scores.

---

## Future corpus extensions

Potential additions for later versions:

- Additional California utilities, including PG&E and SDG&E.
- Older tariff and handbook versions for version-comparison retrieval.
- More working-group reports and CPUC decisions related to DER interconnection and smart inverters.
- SCE forms, application instructions, and supporting process materials where their authority and currency can be recorded.
- Other markets, including ERCOT, NYISO, and AEMO, for cross-market comparison.
- Additional manual reviews to populate stable Tier 2 aggregate results.
- Independent or human answer-quality scoring to complement the completed LLM-judge prompt comparison.
- Additional prompt configurations if future evidence indicates a better citation-validity and quality trade-off.
- Paired statistical testing of original versus expanded query variants.
- A manually judged relevance set to complement metadata-derived relevance labels.
- Repeat the RAG-impact evaluation after deliberate prompt optimisation, preserving the current run as a dated baseline.
- Expand the Tier 2 set and rerun impact evaluation using a versioned question set.
- Add semantic citation-entailment assessment to complement structural citation-label validation.
- Source refresh and re-evaluation procedures as the corpus evolves.