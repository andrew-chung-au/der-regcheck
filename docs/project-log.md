# Project log

## Log index

| Date | Stage | Topic | Status |
|---|---|---|---|
| [2026-08-21](#2026-08-21---california-rule-21-corpus-selection-and-ingestion) | Ingestion | Corpus selection and download pipeline | ✅ Complete |
| [2026-08-22](#2026-08-22---raw-extraction-metadata-and-evidence-normalisation) | Processing | Raw extraction and evidence normalisation | ✅ Complete |
| [2026-08-23](#2026-08-23---structural-chunking-and-citation-preservation) | Processing | Structural chunking | ✅ Complete |
| [2026-08-23](#2026-08-23---embedding-and-retrieval-evaluation-initial) | Evaluation | Initial retrieval evaluation (v1) | ✅ Complete |
| [2026-08-23](#2026-08-23---production-database-and-retrieval) | Infrastructure | PostgreSQL/pgvector setup | ✅ Complete |
| [2026-08-23](#2026-08-23---comprehensive-retrieval-evaluation-with-reranking-and-query-rewrites) | Evaluation | Extended retrieval evaluation (v2) | ✅ Complete |
| [2026-09-05](#2026-09-05---production-aligned-postgresql-retrieval-re-evaluation) | Evaluation | PostgreSQL-aligned evaluation (v3) | ✅ Complete |
| [2026-09-05](#2026-09-05---application-core-rag-pipeline-and-cli) | Development | Application core: RAG pipeline and CLI | ✅ Complete |
| [2026-09-05](#2026-09-05---llm-answer-evaluation-and-prompt-selection) | Evaluation | LLM answer evaluation and prompt selection | ✅ Complete |
| [2026-09-05](#2026-09-05---streamlit-interface-observability-and-manual-review) | Development | Streamlit interface, cache, manual review, and monitoring | ✅ Complete |
| [2026-09-06](#2026-09-06---containerisation-and-processed-data-distribution) | Infrastructure | Containerisation and processed-data distribution | ✅ Complete |
| [2026-09-06](#2026-09-06---rag-impact-evaluation) | Evaluation | RAG impact evaluation | ✅ Complete |

---

## 2026-08-21 - California Rule 21 corpus selection and ingestion

### Goal
Establish a minimal, public, source-provenanced corpus for DER interconnection research in the California Rule 21 / SCE context, and build a reproducible ingestion pipeline that handles blocked or unreliable downloads.

### What I did
- Selected six core public sources from CPUC and SCE:
  - CPUC Electric Rule 21 overview page
  - SCE Rule 21 tariff (PDF)
  - SCE Interconnection Handbook (PDF)
  - SCE Rule 21 interconnection web guidance
  - Smart Inverter Working Group Phase 2 Recommendations (PDF, draft/historical)
  - SCE testing and certification instruction sheet (PDF)
- Built `src/ingestion/download_california_rule21_docs.py` with:
  - Primary request with browser-style headers
  - PDF signature validation
  - Simplified-request fallback for blocked PDFs
  - Manual-replacement helper for cases where automated download is impossible
  - Metadata tracking of validation status, manual review, and extraction eligibility
- Built `src/ingestion/extract_raw_content.py` with:
  - Page-preserving PDF text extraction
  - Main-content HTML extraction with heading-path preservation
  - Filtering by `eligible_for_extraction` to avoid processing failed or pending-review sources
  - Extraction manifest with success, failure, and skipped categories
- Manually replaced the SCE Interconnection Handbook after automated download was blocked and marked it approved in metadata.

### What I learned
- SCE's handbook URL (`https://on.sce.com/InterconnectionHandbook`) is sensitive to repeated automated requests and can return HTML/SharePoint responses instead of PDF.
- A simplified request (browser User-Agent only, no explicit Accept header, default redirect handling) matches the original working downloader behaviour and can recover PDFs when a more complex request fails.
- Manual replacement with explicit metadata approval is a practical fallback when a source is intermittently blocked.
- Keeping all latest downloaded files in one `data/corpus/` directory, with metadata controlling trust and eligibility, is simpler than splitting into multiple folders.

### Decision made
- Use a two-tier download strategy: primary request with validation, then simplified-request fallback for PDFs that fail signature validation.
- Store all latest source responses in `data/corpus/` regardless of validation status.
- Use `corpus_metadata.json` as the source of truth for:
  - Which files are eligible for extraction
  - Which files are eligible for default retrieval
  - Manual review status and reviewer identity
- Only extract sources with `eligible_for_extraction = true`.

### Problems
- Initial attempts to add SharePoint URL parsing and alternate candidate downloads complicated the acquisition logic and broke the working behaviour.
- Repeated automated requests to the handbook URL triggered what appears to be a temporary block, requiring manual replacement.
- Documentation had not been written alongside development, making it harder to recall exact design choices.

### Next step
- Write project documentation: `docs/project-log.md`, `docs/decisions.md`, `docs/dataset-notes.md`, `docs/evaluation-notes.md`, and `docs/runbook.md`.
- Update `README.md` to reflect implemented behaviour rather than planned features.
- Review raw extraction output quality before implementing chunking, retrieval, or database stages.

## 2026-08-22 - Raw extraction metadata and evidence normalisation

### Goal
Create a deterministic, reviewable evidence-normalisation stage between raw extraction and future chunking, embedding, retrieval, and answer-generation stages.

### What I did
- Updated `src/ingestion/extract_raw_content.py` to add:
  - `schema_version` to raw extracted document outputs and the extraction manifest
  - `extraction_method` metadata for PDF and HTML outputs
- Kept raw extraction unchanged in its core behaviour:
  - PDFs remain page-preserving `pypdf` extraction outputs
  - HTML remains main-content extraction with heading-path preservation
  - No LLM calls, chunking, authority assignment, or retrieval logic were added to extraction
- Added `src/processing/normalise_documents.py` to generate deterministic normalised evidence blocks in `data/processed/normalised/`.
- Added `src/processing/quality_check_normalised.py` to generate JSON and Markdown quality reports.
- Added `config/normalisation.yaml` for source-specific page exclusions, boilerplate removal, and heading-detection rules.
- Added document-specific SCE Rule 21 tariff normalisation that:
  - Removes recurring administrative Cal. PUC sheet text from evidence blocks
  - Preserves Rule 21 sheet number, Cal. PUC sheet number, effective date, and advice-letter metadata in citations
  - Recognises lettered tariff sections, numbered provisions, lettered subsections, selected Roman-numeral subheadings, and appendices
  - Preserves prose-style Roman-numeral entries as list items
  - Resets the hierarchy correctly at `APPENDIX B`
- Added raw-tariff regression fixtures for physical PDF pages 50, 100, 150, and 233.
- Added regression tests for:
  - Tariff hierarchy through `E > 3 > a > iv`
  - Roman-numeral list-item handling
  - Parent-heading restoration after enumerated lists
  - Tariff sheet and Cal. PUC sheet metadata
  - Appendix B hierarchy reset
- Generated normalised outputs and quality reports for all six corpus sources.

### What I learned
- Raw extraction and evidence normalisation should be separate stages:
  - Raw extraction preserves source evidence and reproducibility
  - Normalisation derives consistent, reviewable evidence blocks for downstream use
- The SCE Rule 21 tariff requires source-specific parsing because it combines:
  - Repeated California PUC administrative sheet headers
  - Rule 21 printed sheet numbers
  - Advice letters and effective dates
  - Multi-level legal hierarchy
  - Enumerated list items that can resemble subheadings
  - Appendices that reset prior section hierarchy
- A generic PDF parser is insufficient for all source types without source-specific rules and regression tests.
- Some `pypdf` layout artefacts remain in extracted evidence text, such as spaces inside words. These should not be automatically repaired in citation-grade evidence text.
- Quality reports are useful for distinguishing hard failures from accepted review limitations.

### Decision made
- Preserve `data/processed/extracted/` as immutable, page-preserving raw extraction artifacts.
- Use `data/processed/normalised/` for tracked deterministic derivatives of raw extraction outputs.
- Require normalised blocks to retain:
  - Source ID and content hash
  - Stable block order
  - PDF physical-page locators or HTML heading-path locators
  - Source-specific citation metadata where available
  - Normalisation flags for review limitations
- Use a dedicated tariff parser rather than applying generic PDF rules to the SCE Rule 21 tariff.
- Treat Roman-numeral tariff entries as list items by default, except short title-like entries that are deterministic level-four subheadings.
- Exclude handbook cover, approval, contents, certificate, page-header, and document-control material from normalised evidence blocks.
- Keep the SIWG Phase 2 Recommendations source as historical/draft context, excluded from normal current-requirement retrieval.
- Accept limited `no_detected_heading_path` review flags in supporting testing-instruction content and historical SIWG material where page-level provenance remains available.

### Problems
- The first generic tariff parser incorrectly classified all Roman-numeral entries as headings.
- Initial tariff metadata regexes captured trailing hyphens instead of full values such as `4963-E` and `85469-E`.
- Appendix B initially inherited the preceding Section O hierarchy rather than resetting to its own top-level structure.
- The handbook normaliser initially retained a non-substantive `Requirement | Page 1` page-header block.
- Supporting testing-instruction and historical SIWG front matter still has limited heading-path coverage.

### Next step
- Update project documentation to describe the raw-extraction and normalisation boundary.
- Commit the normalisation milestone, including source-specific configuration, processing scripts, regression tests, fixtures, quality reports, and normalised outputs.
- Review normalised source outputs before designing structural chunk assembly.
- Implement deterministic, section-aware chunking as the next pipeline stage.
- Preserve canonical evidence text separately from any future embedding-oriented context text.

## 2026-08-23 - Structural chunking and citation preservation

### Goal
Transform normalised evidence blocks into searchable chunks while preserving citations and source metadata.

### What I did
- Built `src/processing/chunk_documents.py` with:
  - Structural block assembly (keeps headings with their content)
  - Evidence text preservation (unchanged from normalised blocks)
  - Embedding text with heading context prepended
  - Citation metadata merging (PDF pages, tariff sheets, Cal. PUC sheets, sections)
  - Neighbour chunk linking (previous/next chunk IDs)
  - Oversized block flagging (without text mutation)
- Built `src/processing/quality_check_chunks.py` with:
  - Neighbour link validation
  - Token limit checking
  - JSON and Markdown quality reports
- Added `config/chunking.yaml` with:
  - Soft max: 500 tokens, Hard max: 750 tokens
  - Overlap: 90 tokens for oversized chunks
  - Source policy (authority tiers, retrieval tiers)
- Generated 1,049 chunks across 6 sources
- Added regression tests for chunking (20 tests total)

### What I learned
- Must keep parent headings with nested child headings (avoid orphan chunks)
- Tables should stay with preceding context when under hard limit
- Evidence text must never be mutated (breaks citation integrity)
- Heading context belongs in embedding text, not evidence text
- 5 handbook TOC blocks exceed hard limit (accepted as documented exceptions)

### Decision made
- Use structural chunking with citation preservation
- Flag oversized blocks rather than splitting mid-evidence
- Keep heading context in embedding_text only
- Preserve source policy metadata (authority tier, retrieval tier)

### Problems
- Initial implementation created orphan heading chunks (fixed by keeping headings with descendants)
- Five handbook TOC blocks exceed 750 tokens (1,033-1,561 tokens)
- These are dense list-of-lists blocks, not substantive requirements

### Next step
- Embed chunks with Nomic nomic-embed-text-v1.5
- Generate evaluation queries
- Compare BM25, vector, and hybrid retrieval

## 2026-08-23 - Embedding and retrieval evaluation (initial)

### Goal
Evaluate retrieval approaches (BM25, vector, hybrid) with multiple metadata weighting schemes.

### What I did
- Embedded 1,049 chunks with Nomic nomic-embed-text-v1.5:
  - 768-dimensional vectors
  - `search_document:` prefix on embedding text
  - Batched inference with retry logic
- Generated 100 synthetic queries with Gemini 2.5 Flash Lite:
  - LLM-generated from sampled chunks
  - Query types: product_capability, market_analysis, evidence_governance, technical_deep_dive, broad_research
  - Gold metadata preserved for each query
- Built evaluation pipeline:
  - BM25 (token overlap)
  - Vector (cosine similarity)
  - Hybrid (reciprocal rank fusion)
  - 5 metadata weighting schemes (equal, source-heavy, section-heavy, page-heavy, authority-heavy)
- Computed metrics: nDCG@10, MRR, Recall@10
- Saved results to JSONL (1,500 records, reproducible)

### What I learned
- Vector retrieval outperforms hybrid and BM25 on primary ranking metrics.
- Weighting scheme has modest impact across schemes.
- Hybrid has best MRR compared to standard vector.
- Equal weighting works best for vector retrieval.
- Section-heavy helps hybrid slightly.
- *Note: Exact metrics are cataloged in `docs/evaluation-notes.md`.*

### Decision made
- Use vector retrieval with equal weighting for production
- Keep evaluation file-based (reproducible, no DB needed for reviewers)
- Add PostgreSQL/pgvector for production deployment (separate from evaluation)

### Problems
- None major
- All 100 queries generated successfully
- All 1,500 evaluation results computed

### Next step
- Load chunks into PostgreSQL/pgvector
- Build production retrieval layer
- Add RAG generation with Gemini

## 2026-08-23 - Production database and retrieval

### Goal
Build production-ready RAG infrastructure with PostgreSQL/pgvector.

### What I did
- Set up PostgreSQL with pgvector (Docker: `pgvector/pgvector:pg16`)
- Built `src/database/` module:
  - `db_connection.py`: Connection pooling
  - `db_init.py`: Schema (chunks + chunk_embeddings with pgvector)
  - `db_chunks.py`: CRUD operations (insert, search, filter)
- Built `src/scripts/load_chunks_to_db.py`:
  - Loads 1,049 chunks from JSON files
  - Loads 1,049 embeddings from JSONL files
  - Validates counts match
- Built `src/retrieval/retrieve.py`:
  - Query encoding with Nomic (`search_query:` prefix)
  - pgvector similarity search (cosine distance)
  - Metadata filtering (by source_id)
  - Formatted results for RAG context
- Database stats:
  - 1,049 chunks with full metadata
  - 1,049 embeddings (768-dim vectors)
  - IVFFlat index for fast similarity search

### What I learned
- pgvector enables efficient similarity search at scale
- Database is better for production than loading all embeddings into memory
- Keep evaluation file-based for reproducibility
- Production and evaluation can coexist (different storage backends)

### Decision made
- Use PostgreSQL/pgvector for production RAG
- Keep evaluation file-based (JSONL)
- Separate concerns: DB for ops, files for eval

### Problems
- Needed pgvector Docker image (not standard PostgreSQL)
- Had to fix script pathing (use `src/scripts/` and run as modules)

### Next step
- Build RAG generation pipeline with Gemini
- Add reranking (cross-encoder)
- Add query rewriting
- Build API or Streamlit interface

## 2026-08-23 - Comprehensive retrieval evaluation with reranking and query rewrites

### Goal
Run a thorough, methodologically consistent evaluation of retrieval strategies, including:
- Multiple retrievers (BM25, vector, hybrid, hybrid+rerank, vector+rerank)
- Multiple metadata weighting schemes
- Multiple hybrid alpha values
- Query rewrite techniques (original, HyDE, expansion, combined)
- Composite scoring to select a single recommended configuration

### What I did
- Extended `src/evaluation/evaluate_retrieval.py` to:
  - Evaluate all combinations of:
    - 5 retrievers: `bm25`, `vector`, `hybrid`, `hybrid_rerank`, `vector_rerank`
    - 5 weightings: `equal`, `authority_heavy`, `page_heavy`, `section_heavy`, `source_heavy`
    - 3 alphas: 0.3, 0.5, 0.7 (for hybrid)
  - Use BAAI/bge-reranker-base for reranking top-50 candidates to 10
  - Checkpoint results at `(query_id, alpha, retriever, weighting)` granularity for resumable runs
  - Add `--mode rewrites-full` to evaluate query rewrites across all retrievers and weightings
- Generated 15,500 evaluation records across two result files:
  - 100 queries × 3 alphas × 5 retrievers × 5 weightings = 7,500 retrieval rows
  - 4 rewrite techniques × 4 retrievers × 5 weightings × 100 queries = 8,000 rewrite rows
- Updated `src/evaluation/summarise_evaluation.py` to:
  - Compute composite score formula
  - Show ranked tables by each metric and by composite score
  - Recommend a single configuration by composite score
- Key findings:
  - Reranking dominates: all top configurations are `hybrid_rerank` or `vector_rerank`
  - Best configuration: `hybrid_rerank__equal` (see `docs/evaluation-notes.md` for exact metrics)
  - Other reranked weightings performed similarly, appearing effectively tied.
  - Non-reranked methods are clearly behind.
  - Query rewrites show small gains, but original query is already near-optimal.

### What I learned
- Reranking provides the largest single ranking improvement.
- Weighting scheme matters much less once you rerank
- Hybrid + rerank slightly edges vector + rerank on composite score
- Query rewrites are not worth the complexity for this corpus (original query is already near-optimal)
- Fine-grained checkpointing (`query_id, alpha, retriever, weighting`) makes iterative evaluation practical

### Decision made
- Use `hybrid_rerank__equal` with alpha = 0.5 for production retrieval (see `docs/decisions.md` for final superseding rationale)
- Keep reranker settings: `candidate_limit=50`, `top_k=10`, `max_tokens=450`, `batch_size=16`
- Do not use query rewrites in production (original query is sufficient)
- Document evaluation as complete and methodologically consistent across retrievers, weightings, and alphas

### Problems
- Initial checkpointing was too coarse (`query_id, alpha` only), causing rerun issues when adding weightings
- Fixed by tracking `(query_id, alpha, retriever, weighting)` tuples
- Some reranked weightings appeared tied at 3 decimals; increased to 5 decimals to show small differences

### Next step
- Finalise documentation: `README.md`, `docs/decisions.md`, `docs/evaluation-notes.md`, `docs/runbook.md`
- Optionally add RRF k sweep (e.g. k ∈ {1, 20, 60, 100}) in a future iteration
- Build RAG generation pipeline with Gemini using the selected retrieval configuration

## 2026-09-05 - Production-aligned PostgreSQL retrieval re-evaluation

### Goal
Re-evaluate retrieval and cached query-rewrite variants using the deployed PostgreSQL/pgvector retrieval path rather than the earlier file-based, in-memory evaluator.

### What I did
- Migrated evaluation retrieval to the deployed production components:
  - PostgreSQL full-text lexical retrieval
  - pgvector vector retrieval
  - PostgreSQL-backed hybrid retrieval
  - Runtime query embedding
  - Cross-encoder reranking
- Preserved the fixed benchmark of 100 evaluation queries and 1,049 indexed chunks.
- Retained retrieval variants, alpha sweeps, metadata weighting schemes, JSONL checkpointing, and cached query-rewrite evaluation.
- Updated `src/evaluation/summarise_evaluation.py` to group results by alpha, count unique queries correctly, calculate variability, and rank configurations by the documented composite score.
- Added and passed evaluator and summariser regression tests.
- Completed the full PostgreSQL retrieval grid and rewrite evaluation; detailed commands, metrics, results, and limitations are recorded in `docs/evaluation-notes.md`.

### What I learned
- The earlier file-based evaluator and the deployed PostgreSQL evaluator are separate experimental conditions, despite using the same query benchmark and corpus.
- Final claims should use the PostgreSQL results because they measure the runtime retrieval path.
- Reranking produced the main ranking-quality improvement; query expansion was evaluated as a possible refinement, while HyDE was not selected for default use.

### Decision made
- Treat the PostgreSQL/pgvector results as the authoritative final retrieval evaluation.
- Preserve earlier file-based results as historical offline-baseline artifacts, not directly comparable final results.
- Record the selected production configuration and its supporting metrics in `docs/evaluation-notes.md` and `docs/decisions.md`.

### Problems
- The original evaluator used locally loaded embeddings and a lightweight lexical-overlap baseline rather than the deployed retrieval path.
- Migrating evaluators changed multiple implementation details simultaneously, preventing a controlled causal claim that PostgreSQL alone changed performance.

### Next step
- Finalise `docs/evaluation-notes.md` with the evaluation protocol, final result tables, interpretation, and limitations.
- Update `docs/decisions.md`, `docs/runbook.md`, and `README.md`.

---

## 2026-09-05 - Application core: RAG pipeline and CLI

### Goal
Build the production application core: a command-line user can ask a DER research question and receive a source-grounded, validated, uncertainty-aware response.

### What I did
- Introduced domain models and service boundary in `src/generation/`:
  - `schemas.py`: `StructuredAnswerOutput` Pydantic model
  - `prompts.py`: Prompt instruction templates for v1, v2, v3 configurations
  - `citation_validator.py`: Deterministic citation validation against supplied evidence labels
  - `answer_generator.py`: Answer generation with citation validation and fail-closed behavior
- Wired existing retrieval pipeline into production service:
  - `src/retrieval/runtime_retriever.py`: Production retrieval with query expansion capability (disabled for latency per Decision 13)
  - Evidence packet building with source-authority policy
- Added real LLM provider adapter:
  - `src/llm_client.py`: Gemini client with structured output generation
- Implemented **v2_structured_grounded_rag** as provisional runtime prompt
- Added CLI `ask` command in `src/scripts/demo_rag.py`
- Stored traces and added observability module `src/observability/`
- Added comprehensive tests:
  - Citation/schema/unit tests in `tests/test_answer_generator.py`
  - All 7 tests passing
- Added `pytest.ini` for test configuration

### What I learned
- Citation validation must be deterministic and fail-closed to prevent hallucinated sources
- Structured output schemas (Pydantic) improve reliability and testability
- Prompt versioning allows systematic comparison without code changes
- Query expansion adds significant latency (~36 seconds) with marginal retrieval benefit

### Decision made
- Use fail-closed citation validation: answers with invalid citations are rejected
- Store traces for debugging and future evaluation
- Use Pydantic schemas for all structured outputs
- Disable query expansion in runtime (see Decision 13)

### Problems
- Initial implementation allowed uncited claims to pass validation
- Fixed by implementing strict fail-closed validation in tests
- Query expansion latency made the system unusable for demos (~50 seconds total)
- Resolved by disabling expansion (Decision 13)

### Next step
- Build LLM evaluation harness to compare prompt configurations
- Select production prompt based on empirical evidence
- Build Streamlit interface

---

## 2026-09-05 - LLM answer evaluation and prompt selection

### Goal
Add systematic answer-quality evaluation: prove why the production prompt configuration is selected using empirical evidence from 24 fixed evaluation questions.

### What I did
- Created `src/evaluation/evaluate_llm_answers.py`:
  - Loads 24 fixed evaluation questions from `data/evaluation/llm_evaluation_questions.yaml`
  - Retrieves evidence once per question using production retrieval path
  - Generates answers for v1, v2, v3 prompt configurations using same evidence pack
  - Records all answer artifacts with full traceability
  - Runs deterministic citation validation for every generated answer
  - Judges each answer using LLM judge (`gemini-3.5-flash-lite`) on 5 dimensions
  - Computes composite scores
- Created `src/evaluation/summarise_llm_evaluation.py`:
  - Aggregates judge scores by prompt version
  - Applies citation-validity guardrail (100% required)
  - Selects best prompt configuration
  - Produces JSON summary and markdown report
- Generated evaluation artifacts:
  - `data/evaluation/llm_answers.jsonl`
  - `data/evaluation/llm_judge_scores.jsonl`
  - `data/evaluation/llm_evaluation_summary.json`
  - `data/evaluation/llm_evaluation_report.md`

### What I learned
- v3 (few-shot grounded RAG) achieved 100% citation validity (only configuration to meet guardrail)
- v2 had the highest composite score but failed the citation validity guardrail.
- v1 had the lowest scores on both dimensions.
- Citation validity is a critical safety property for regulatory research tools
- Few-shot examples improve citation discipline without sacrificing quality

### Decision made
- Select `v3_few_shot_grounded_rag` as production prompt configuration (Decision 14)
- Apply 100% citation-validity guardrail for all future prompt selections
- Use LLM judge for systematic answer-quality evaluation
- Store evaluation artifacts for reproducibility and future iteration

### Problems
- v2 had 2 answers with citation issues
- Manually reviewed and confirmed these were real citation failures
- Decision: reject v2 despite higher composite score (safety first)

### Next step
- Update production service default prompt to v3
- Build Streamlit interface
- Add feedback capture and monitoring
- Update README with evaluation results

---

## 2026-09-05 - Streamlit interface, observability, and manual review

### Goal

Complete a reviewer-facing Streamlit interface adapter for the DER RegCheck
evidence-first RAG pipeline and add lightweight operational monitoring,
feedback capture, query caching, and Tier 2 human-evaluation support.

### What I did

- Implemented `src/ui/streamlit_app.py` as the Streamlit interface adapter
  over the existing production retrieval and answer-generation pipeline.
- Kept Streamlit as a presentation and interaction layer only:
  - The UI calls `AnswerGenerator`.
  - Retrieval, reranking, prompt selection, Gemini generation, and
    deterministic citation validation remain in the existing pipeline.
  - The UI does not duplicate retrieval or answer-generation logic.

- Added a wide, responsive Streamlit layout:
  - `layout="wide"` adapts to available browser and monitor width.
  - Sidebar provides recent-query navigation rather than a dense static
    information panel.
  - Static project information, runtime configuration, project links, and
    responsible-use boundary are located in the About tab.

- Added five connected interface tabs:
  - `About`
  - `Ask`
  - `Evidence`
  - `Review`
  - `Monitoring`

- Added the Ask workflow:
  - Free-text DER research question input.
  - Five selectable example questions drawn from the Tier 2 question set.
  - Human-readable Tier 2 labels in the select box, such as
    `T2-003 — For a DER project in SCE territory...`.
  - Configuration-aware cache lookup before a new RAG generation.
  - Visible cache-hit and cache-miss messages.
  - Cached answer rendering with status badge, uncertainty statement,
    clarifying question, evidence gaps, and suggested next steps.
  - Optional helpful/not-helpful feedback with optional free-text comment.

- Added reviewer-facing answer status labels:
  - `Answered`
  - `Partial`
  - `Needs clarification`
  - `Insufficient evidence`
  - `High-stakes boundary`

- Added the Evidence workflow:
  - All tabs operate on a shared selected cached response.
  - Users can select a recent question from the sidebar and inspect the same
    answer in Ask, evidence in Evidence, and scores in Review.
  - Expandable evidence cards display:
    - Stable source label such as `S1`.
    - Source ID.
    - Source class, combining authority tier and currency status.
    - Heading path and available PDF page or section locator.
    - Final retrieval rank.
    - Preserved evidence excerpt.
  - Raw reranker scores are not displayed in the default reviewer view because
    the runtime retrieval path does not yet persist a consistent reranker score
    for every cached evidence record.

- Added PostgreSQL-backed response caching:
  - Extended `src/database/db_init.py` with an observability schema.
  - Added `query_cache` table containing:
    - Question text.
    - Configuration hash.
    - Generated answer status and structured answer fields.
    - Claims and evidence gaps.
    - Evidence snapshot.
    - Cache-miss generation latency.
  - Added `src/observability/query_cache.py`.
  - Cache identity is based on:
    - Question text.
    - Prompt version.
    - Top-K value.
    - Retrieval configuration identifier.
  - Repeated questions with the same configuration load the existing response
    instead of repeating retrieval, reranking, and LLM generation.
  - New questions are persisted immediately after successful generation,
    independent of whether feedback is submitted.

- Added persistent feedback and manual-review event storage:
  - `answer_feedback` table stores helpful/not-helpful feedback events linked
    to `query_cache.cache_id`.
  - `manual_scores` table stores human evaluation events linked to
    `query_cache.cache_id`.
  - Multiple feedback submissions can be associated with one cached response.
  - Multiple manual-review records can be associated with one cached response,
    supporting future repeated review or multiple reviewers.
  - JSONL copies are also written to:
    - `data/feedback/feedback.jsonl`
    - `data/evaluation/tier2_manual_scores.jsonl`
  - PostgreSQL is the operational source of truth; JSONL records are retained
    as simple portable artifacts during this prototype stage.

- Added a Tier 2 realistic RAG-quality evaluation workflow:
  - Created `data/evaluation/tier2_questions.yaml`.
  - Added 10 realistic, open-ended DER research questions.
  - Kept the existing 24-question set separate as the prompt-regression suite.
  - Tier 2 questions cover:
    - Direct factual research.
    - Multi-chunk synthesis.
    - Conditional and clarification-sensitive questions.
    - Out-of-corpus handling.
    - High-stakes decision boundaries.
    - Historical-source treatment.
  - Five Tier 2 questions are used as example questions in Ask.
  - The full Tier 2 set is selectable in Review.

- Added the Review workflow:
  - A reviewer can select:
    - The currently selected recent query.
    - A Tier 2 evaluation question.
    - A custom question.
  - Tier 2 question selection uses readable labels while preserving stable
    identifiers such as `tier2_003` in the database.
  - Reviewers can load a cached response or generate one on cache miss.
  - Reviewers score each response from 1 to 5 on:
    - Groundedness.
    - Relevance.
    - Completeness.
    - Citation quality.
    - Appropriate uncertainty.
  - Reviewers can add free-text notes.
  - Tier 2 expected behavior can be inspected from the Review tab.

- Added a Monitoring workflow and dashboard:
  - Uses real runtime data from PostgreSQL.
  - Includes summary metrics for:
    - Cached queries.
    - Feedback events.
    - Manual reviews.
    - Tier 2 reviews.
    - Tier 2 question coverage.
  - Includes seven monitoring charts:
    1. Answer-status distribution.
    2. Helpful versus not-helpful feedback distribution.
    3. Average manual-review scores by quality dimension.
    4. Cache-miss generation latency over time.
    5. Average cache-miss generation latency by answer status.
    6. Cached query volume over time.
    7. Tier 2 manual-review coverage.
  - Uses Altair for chart layout control, including:
    - Horizontal categorical bars.
    - Horizontal category labels.
    - Responsive chart width.
    - Explicit chart height.
    - Readable answer-status labels.
    - Calendar-date formatting for query-volume charts.
  - Tier 2 coverage uses compact stable labels such as `T2-001` rather than
    long question text, because the full question remains accessible in Review.
  - Every chart has a safe empty state for fresh databases, new machines, and
    new Docker volumes.
  - The dashboard does not create artificial runtime records simply to populate
    charts.

- Added local developer command support:
  - Created a Makefile with targets for the Streamlit UI, database
    initialization, tests, demo scripts, chunk loading, and Docker workflows.
  - The primary local UI command is:
    ```bash
    make ui
    ```
  - Database schema initialization, including observability tables, is:
    ```bash
    make db-init
    ```

- Addressed local Streamlit development issues:
  - Added repository-root path handling in `streamlit_app.py` so imports such
    as `from src...` work when Streamlit executes the UI file directly.
  - Used a project-level Streamlit configuration appropriate for WSL.
  - Identified that optional `torchvision` warnings arise from Streamlit file
    watching combined with optional Hugging Face Transformers image/video
    modules, rather than from DER RegCheck RAG logic.

### What I learned

- A tabbed UI provides a clearer review workflow than placing all information
  on one long scrolling page:
  - Ask is focused on interaction and answer consumption.
  - Evidence is focused on provenance inspection.
  - Review is focused on human evaluation.
  - Monitoring is focused on system and evaluation signals.

- A sidebar is more useful as persistent query navigation than as a large static
  About panel. The shared selected-query model avoids disconnects between
  answer, evidence, and review tabs.

- Query caching is both a performance feature and an evaluation-control feature:
  - It reduces repeated LLM and reranking cost for identical questions.
  - It provides a stable answer snapshot for a specific runtime configuration.
  - It ensures manual feedback and reviewer scores are linked to a specific
    persisted answer and evidence set.

- Feedback, cache records, and manual evaluations have different purposes:
  - `query_cache` stores one configuration-specific response snapshot.
  - `answer_feedback` stores lightweight user-sentiment events.
  - `manual_scores` stores structured human-quality evaluations.
  - A single cached response can legitimately have multiple feedback and review
    events.

- The 24-question answer-generation set and Tier 2 set should remain separate:
  - The 24-question set evaluates v1/v2/v3 prompt behavior, including
    adversarial and edge-case questions.
  - Tier 2 evaluates realistic end-to-end RAG usefulness through human review.
  - UI examples are a small, reviewer-friendly subset of Tier 2.

- Monitoring must distinguish cache hits from cache misses:
  - Cache hits are fast database lookups.
  - Cache-miss latency represents the end-to-end RAG path.
  - Cache hits should not be treated as full retrieval and answer-generation
    timing observations.

- Monitoring dashboards need truthful empty states:
  - Fresh databases should not show fabricated data.
  - A chart with no valid observations should provide a specific explanation
    of how a reviewer can populate it.
  - Zero must not be used to represent missing manual-review scores.

- Raw internal scores are not automatically helpful to reviewers:
  - Final retrieval rank is consistently available and understandable.
  - Reranker scores should only be shown when the runtime captures and
    persists their semantics consistently.

### Decision made

- Use Streamlit as the primary reviewer-facing interface and portfolio demo.
- Keep `src/ui/streamlit_app.py` under `src/ui/`; use the Makefile and Docker
  commands as the reviewer-friendly launch surface rather than moving the app
  entry point to the repository root.
- Use a shared `selected_cache_id` as the state boundary between Ask, Evidence,
  Review, and sidebar navigation.
- Use PostgreSQL as the authoritative operational store for:
  - Cached question/answer/evidence snapshots.
  - User feedback events.
  - Manual-review scores.
  - Monitoring queries and dashboard aggregation.
- Retain JSONL feedback and manual-score artifacts as secondary portable logs
  during the prototype stage.
- Cache responses using question text plus a configuration hash to avoid
  reusing an answer created under a different prompt or retrieval setup.
- Persist query/answer records immediately after successful generation; do not
  require a feedback event before storing the response.
- Permit multiple feedback and manual-review events for a single cached answer.
- Use the existing 24-question set as the prompt-regression suite.
- Use the new 10-question Tier 2 set for realistic manual RAG-quality review.
- Use five Tier 2 questions as the Ask-tab examples and expose all Tier 2
  questions in the Review tab.
- Use seven charts in Monitoring, exceeding the five-chart course requirement:
  - Answer status distribution.
  - Feedback distribution.
  - Average manual-review scores.
  - Generation latency over time.
  - Generation latency by answer status.
  - Cached query volume over time.
  - Tier 2 manual-review coverage.
- Use Altair for monitoring charts where explicit orientation, label placement,
  date formatting, chart height, and responsive width are needed.
- Show final retrieval rank in evidence cards; defer reviewer-facing reranker
  scores until consistent score persistence is implemented.

### Problems

- Streamlit runs an app file as a standalone script, which initially caused
  `ModuleNotFoundError: No module named 'src'`.
- Running the app through `python -m` resolved imports but did not create a
  proper Streamlit browser session. The final approach keeps `streamlit run`
  and explicitly adds the repository root to `sys.path`.
- Iterative UI edits temporarily introduced indentation errors in the Ask and
  Review action blocks.
- Early sidebar behavior made it appear that questions were only stored after
  feedback. The actual issue was UI refresh/state flow; query cache inserts now
  occur immediately after generation and the selected cached response drives
  navigation.
- The initial example-question selector displayed raw Tier 2 identifiers rather
  than descriptive labels. Select boxes now display readable labels while
  retaining stable IDs internally.
- Streamlit's file watcher inspected optional Transformers image/video modules
  and produced noisy `torchvision` import warnings under the local WSL setup.
  This was unrelated to the RAG functionality.
- Simple Streamlit bar charts produced cramped or vertical category labels and
  partially obscured axes for long values. The monitoring dashboard now uses
  Altair with explicit horizontal chart configuration.
- Initial date encoding in the query-volume chart displayed epoch-millisecond
  values rather than human-readable dates. The chart now declares the field as
  temporal and formats dates explicitly.
- Existing cached evidence records do not contain reranker scores because the
  current runtime does not persist that value; displaying `N/A` repeatedly was
  not useful. The default evidence view now emphasizes final retrieval rank.

### Follow-up

- Collect enough manual Tier 2 reviews to produce stable aggregate human-review results.
- Add focused tests for query-cache lookup, configuration separation, feedback insertion, manual-score insertion, monitoring aggregation, and Tier 2 question-label mapping.
- Revisit reviewer-facing reranker scores only if the runtime persists a consistent score definition for every cached evidence record.
- Keep containerisation, processed-data distribution, and source-refresh procedures documented in the later infrastructure entry and `docs/runbook.md`.

---

## 2026-09-06 - Containerisation and processed-data distribution

### Goal
Ship a reproducible, containerised deployment of DER RegCheck that can run from committed processed artifacts without re-downloading sources, and document the data-distribution strategy.

### What I did
- Implemented a multi-stage Dockerfile using `uv` to build a stateless application image.
- Defined `compose.yaml` with:
  - `db` service using `pgvector/pgvector:pg16`.
  - `app` service running the Streamlit app and depending on `db`.
- Added Makefile targets:
  - `docker-build`, `docker-up`, `docker-down`, `docker-logs`, `docker-restart`, `docker-clean`.
  - `db-init-docker` and `load-chunks-docker` for one-time schema and data load in the container.
- Finalised the “processed-data distribution” strategy:
  - Raw source files in `data/corpus/` remain local and are ignored by Git.
  - Processed artifacts (`data/processed/extracted/`, `normalised/`, `chunks/`, `embeddings/`) are committed.
  - The app can run from committed processed data; ingestion scripts are optional and intended for future corpus refreshes.
- Updated `README.md`, `docs/runbook.md`, and `docs/decisions.md` to reflect:
  - Container-first setup.
  - Processed-data distribution and copyright notes.
  - New Decision 20 on processed-data distribution and optional ingestion.

### What I learned
- Venvs created by `uv` on the host can embed host-specific symlinks that break in containers; switching to `--system` installs in the builder and copying site-packages into the runtime image avoids this.
- Keeping raw source acquisition separate from processed artifacts simplifies both licensing and reproducibility.
- A small set of Makefile wrappers around `docker compose` makes the workflow much easier to document and use.

### Decision made
- Use a stateless application image + separate PostgreSQL container.
- Commit processed artifacts and treat them as the reproducibility boundary.
- Keep ingestion and source download as optional, advanced workflows for corpus refresh.

### Problems
- Initial Dockerfile used a venv with host-specific symlinks, causing `streamlit` to fail with “no such file or directory”.
- Resolved by:
  - Installing with `uv pip install --system` in the builder.
  - Copying site-packages and `streamlit` into the runtime image.
  - Removing reliance on a venv in the runtime container.

### Current follow-up

- Add optional CI checks that verify committed processed-artifact counts and basic database-schema integrity.
- Consider adding a data-version identifier to the database schema or answer-cache configuration hash when the corpus is refreshed.
- Keep source refreshes, downstream regeneration, and re-evaluation documented through the existing dataset, evaluation, decision, and runbook documents.

---

## 2026-09-06 - RAG impact evaluation

### Goal

Measure the observable contribution of the retrieval layer on realistic DER research questions, while separately examining whether the selected v3 prompt configuration adds value beyond a simpler retrieval-grounded prompt.

This evaluation was intended as a portfolio-quality system-impact study rather than a business-impact or real-user study.

### What I did

- Used the 10-question Tier 2 evaluation set in `data/evaluation/tier2_questions.yaml`.
- Kept the existing 24-question prompt-regression evaluation separate.
- Generated four answer conditions for each Tier 2 question:
  - Naive model-only answer with no retrieved evidence.
  - v3 evidence-bounded prompt with no retrieved evidence.
  - Zero-shot RAG using `v1_direct_rag`.
  - Full RAG using `v3_few_shot_grounded_rag`.
- Retrieved one shared top-10 evidence pack per question and reused it for the two evidence-backed conditions.
- Added deterministic citation-label validation for the evidence-backed conditions.
- Used blinded pairwise LLM judging with `gemini-3.5-flash-lite`.
- Compared:
  - Naive model-only answers against zero-shot RAG.
  - Zero-shot RAG against the full v3 RAG configuration.
  - Naive model-only answers against the full v3 RAG configuration.
  - The no-evidence v3 condition against the full v3 RAG configuration.
- Recorded generation outputs, retrieval references, validation results, judge results, and summary reports as JSONL, JSON, and Markdown artefacts.

### What I learned

- The main observed impact came from adding retrieval and evidence grounding:
  - Zero-shot RAG was preferred to the naive no-evidence baseline in 8 of 10 comparisons.
  - The full v3 RAG configuration was preferred to the naive baseline in 8 of 10 comparisons.
  - The full v3 configuration was preferred to the v3 no-evidence condition in 9 of 10 comparisons.
- The full v3 configuration achieved slightly higher pooled judge scores than zero-shot RAG across groundedness, relevance, completeness, citation quality, and appropriate uncertainty.
- The pairwise zero-shot RAG versus full v3 comparison was mixed: zero-shot RAG was preferred in 5 cases, full v3 in 3 cases, with 2 ties.
- This suggests that the retrieval layer produced the clearest quality improvement in this experiment, while additional prompt engineering produced a smaller and less consistent incremental benefit on the 10-question set.
- Further prompt optimisation remains a worthwhile future direction, particularly for:
  - Few-shot example selection.
  - Clarification and abstention behaviour.
  - Source-hierarchy instructions.
  - Concise answers that retain appropriate uncertainty.
- All evidence-backed outputs passed deterministic citation-label validation. This confirms label validity and claim-citation presence, but does not independently establish semantic citation entailment.
- The v3 no-evidence condition returned `insufficient_evidence` for all 10 questions, demonstrating safe abstention when no evidence pack was supplied.

### Decision made

- Treat the retrieval-impact result as the primary finding from this experiment.
- Describe the full v3 prompt as the selected production configuration because it satisfies the existing citation-validity guardrail and performed strongly on the established prompt-regression evaluation.
- Do not claim that v3 prompt engineering definitively outperformed zero-shot RAG on realistic Tier 2 questions.
- Retain the impact experiment as a separate evaluation from the 24-question prompt-selection study.
- Describe the new results as an automated LLM-as-judge comparison, not as human-user impact, business impact, or independent factual validation.
- Preserve the generated impact artefacts for later inspection and future comparison.

### Problems

- The Tier 2 set contains only 10 questions, so the results should be treated as indicative rather than conclusive.
- The same Gemini model family was used for answer generation and judging, so judge results may contain model-specific preferences.
- The pairwise comparison between zero-shot RAG and full v3 RAG was not decisive.
- Some expected-behaviour checks for clarification and insufficient-evidence handling did not align perfectly with the structured output statuses and require interpretation at the answer-content level.
- No real users or business workflow were available, so this experiment does not measure adoption, task completion time, business value, or user satisfaction.

### Next step

- Record the detailed protocol, metrics, tables, results, and limitations in `docs/evaluation-notes.md`.
- Add one concise headline result and limitation to `README.md`.
- Consider future prompt optimisation using a larger and independently human-reviewed evaluation set.
- Avoid overwriting this evaluation when testing prompt changes; record future runs as new dated conditions.