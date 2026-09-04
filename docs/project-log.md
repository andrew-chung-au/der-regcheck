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
| [2026-09-05](#2026-09-05---streamlit-interface) | Development | Streamlit interface | ✅ Complete |

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

## 2026-09-05 - Streamlit interface

### Goal
Build a Streamlit interface: a reviewer can use the actual app, inspect evidence, and understand limits.

### What I did
- Created `src/ui/streamlit_app.py` with:
  - Question input (text field + 5 example question buttons)
  - Answer status badge (Answered, Partial, Needs clarification, Insufficient evidence, High-stakes boundary)
  - Main answer with inline citation labels [S1], [S2], etc.
  - Expandable evidence cards showing:
    - Source title (heading path)
    - Source class (authority tier)
    - Page/section (section IDs, PDF page)
    - Excerpt (evidence text)
    - Retrieval rank
    - Score (rerank score)
  - Explicit disclaimer banner: "Not legal, engineering, regulatory, or compliance advice"
  - Feedback widgets (thumbs up/down + optional comment)
  - Feedback saved to `data/feedback/feedback.jsonl`
- Configured app to use v3 prompt (`v3_few_shot_grounded_rag`)
- Tested with example questions

### What I learned
- Streamlit provides rapid UI development with minimal code
- Evidence cards help users understand retrieval and verify citations
- Status badges communicate answer quality and uncertainty clearly
- Feedback capture is essential for future iteration

### Decision made
- Use Streamlit as the primary interface for demos and portfolio
- Keep UI simple: question → answer → evidence → feedback
- Explicitly communicate limitations and uncertainty

### Problems
- None major
- App runs successfully with `streamlit run src/ui/streamlit_app.py`

### Next step
- Test app with real users and collect feedback
- Add monitoring and analytics
- Consider multi-page app for different question types
- Update README with app usage instructions