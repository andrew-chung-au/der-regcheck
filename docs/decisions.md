# Decisions

## Decision index

| # | Decision | Status | Superseded |
|---|----------|--------|------------|
| [01](#01-project-scope) | Project scope | Active | No |
| [02](#02-corpus-selection) | Corpus selection | Active | No |
| [03](#03-ingestion-and-download-strategy) | Ingestion and download strategy | Active | No |
| [04](#04-extraction-and-chunking-approach) | Extraction and chunking approach | Active | No |
| [05](#05-source-hierarchy-and-authority) | Source hierarchy and authority | Active | No |
| [06](#06-evaluation-strategy) | Evaluation strategy | Active | No |
| [07](#07-raw-extraction-and-evidence-normalisation) | Raw extraction and evidence normalisation | Active | No |
| [08](#08-structural-chunking-and-citation-preservation) | Structural chunking and citation preservation | Active | No |
| [09](#09-embedding-and-retrieval-evaluation) | Embedding and retrieval evaluation | Superseded | Yes (by [11](#11-embedding-and-retrieval-evaluation-v2)) |
| [10](#10-production-database-and-retrieval) | Production database and retrieval | Active | No |
| [11](#11-embedding-and-retrieval-evaluation-v2) | Embedding and retrieval evaluation v2 | Superseded | Yes (by [12](#12-production-aligned-postgresql-retrieval-evaluation)) |
| [12](#12-production-aligned-postgresql-retrieval-evaluation) | Production-aligned PostgreSQL retrieval evaluation | Active | No |
| [13](#13-runtime-configuration-disable-query-expansion-for-latency) | Runtime configuration: disable query expansion for latency | Active | No |
| [14](#14-llm-answer-evaluation-and-prompt-configuration-selection) | LLM answer evaluation and prompt configuration selection | Active | No |
| [15](#15-streamlit-interface-adapter-and-tabbed-reviewer-workflow) | Streamlit interface adapter and tabbed reviewer workflow | Active | No |
| [16](#16-postgresql-backed-configuration-aware-answer-cache) | PostgreSQL-backed configuration-aware answer cache | Active | No |
| [17](#17-feedback-and-manual-review-event-model) | Feedback and manual-review event model | Active | No |
| [18](#18-tier-2-manual-evaluation-separation-from-prompt-regression) | Tier 2 manual evaluation separation from prompt regression | Active | No |
| [19](#19-monitoring-dashboard-and-cache-miss-latency-interpretation) | Monitoring dashboard and cache-miss latency interpretation | Active | No |
| [20](#20-processed-data-distribution-and-optional-ingestion) | Processed-data distribution and optional ingestion | Active | No |
| [21](#21-rag-impact-evaluation-and-retrieval-contribution) | RAG impact evaluation and retrieval contribution | Active | No |

---

## 01. Project scope

**Decision:**
Build a RAG prototype for DER interconnection and market-entry research, starting with California Rule 21 / Southern California Edison (SCE) public material.

**Reason:**
- DER market-entry research requires locating, reading, and comparing multiple heterogeneous public documents (tariffs, handbooks, web guidance, testing instructions, working-group reports).
- The California Rule 21 / SCE context provides a well-defined, public, and sufficiently complex corpus to justify RAG.
- A focused initial scope allows end-to-end pipeline development (ingestion, retrieval, generation, evaluation, interface) without overextending.

**Alternatives considered:**
- Starting with a different market (e.g., ERCOT, NYISO, AEMO).
- Using generic AI policy or guidance documents (e.g., ACSC AI guidance hub).
- Building a broader multi-utility corpus from the start.

**Trade-offs:**
- California Rule 21 is complex but may not generalise directly to other markets.
- A narrow initial corpus limits immediate applicability but accelerates iteration.
- Generic AI guidance is easier to obtain but less compelling as a RAG use case.

---

## 02. Corpus selection

**Decision:**
Use six core public sources from CPUC and SCE for v1:
- CPUC Electric Rule 21 overview page (regulatory context and source discovery)
- SCE Rule 21 tariff (primary interconnection requirements)
- SCE Interconnection Handbook (primary technical implementation)
- SCE Rule 21 interconnection web guidance (supporting process guidance)
- Smart Inverter Working Group Phase 2 Recommendations (historical/draft context)
- SCE testing and certification instruction sheet (supporting implementation guidance)

**Reason:**
- These sources collectively cover interconnection process, technical requirements, communications/telemetry, testing/certification, and historical rationale.
- All are public and directly relevant to DER market-entry research in the SCE context.
- The set is small enough to manage manually but diverse enough to test metadata-aware retrieval and source hierarchy.

**Alternatives considered:**
- Including additional utilities (e.g., PG&E, SDG&E) in v1.
- Including more historical working-group material or older tariff versions.
- Starting with a larger set of web pages and forms.

**Trade-offs:**
- A minimal corpus reduces coverage but improves traceability and debugging.
- Historical material adds context but complicates currency and authority reasoning.
- Multi-utility coverage would improve generality but delay core pipeline development.

---

## 03. Ingestion and download strategy

**Decision:**
- Store all latest downloaded source responses in `data/corpus/` regardless of validation status.
- Use `corpus_metadata.json` as the authoritative record for:
  - Content hashes and last-checked timestamps
  - Validation status (passed/failed)
  - Manual review status (pending/approved/rejected)
  - Extraction eligibility and default retrieval eligibility
- Implement a two-tier download strategy:
  - Primary request with browser-style headers and explicit Accept header
  - For PDFs that fail signature validation, retry with a simplified request (browser User-Agent only, no explicit Accept header, default redirect handling)
- Provide a manual-replacement helper for sources that cannot be obtained via automated download.

**Reason:**
- Keeping all latest files together simplifies the model: physical location does not imply trust; metadata does.
- A simplified-request fallback preserves the original working download behaviour when a more complex request fails.
- Manual replacement is necessary when servers block automated access or require authentication.
- Explicit metadata control allows downstream pipelines to skip non-eligible sources cleanly.

**Alternatives considered:**
- Separate folders for valid, failed, and review files (e.g., `current/`, `review/`, `archive/`).
- Only saving files that pass validation.
- No fallback logic; treat any failed download as a hard error.

**Trade-offs:**
- A single folder requires strict metadata discipline but is conceptually simpler.
- Saving failed downloads enables auditability and manual review but requires clear eligibility flags.
- Fallback logic adds complexity but improves robustness against server-side blocks.

---

## 04. Extraction and chunking approach

**Decision:**
- Do not apply a single fixed-size text splitter to all sources.
- Implement source-specific extraction:
  - PDFs: page-preserving text extraction with page markers
  - HTML: main-content extraction with heading-path preservation, table-to-markdown conversion, and removal of boilerplate
- Defer fine-grained chunking logic to a later stage; v1 extraction produces document-level structured text and block/page lists.

**Reason:**
- Tariffs, handbooks, web pages, and reports have different structures and citation conventions.
- Preserving page numbers and heading paths is critical for traceable citations.
- A uniform chunker would lose document-specific structure (e.g., tariff sections, HTML accordions, tables).

**Alternatives considered:**
- Immediate fine-grained chunking with a generic text splitter.
- Treating all sources as plain text without structure preservation.
- Using a PDF-to-markdown converter for all PDFs.

**Trade-offs:**
- Source-specific extraction requires more code but yields higher-quality context for RAG.
- Deferring chunking delays some retrieval experiments but allows focused iteration on extraction quality first.

---

## 05. Source hierarchy and authority

**Decision:**
Assign each source an authority level and retrieval tier:
- Primary tariff / governing source
- Primary technical handbook
- Supporting testing or implementation guidance
- Supporting process guidance and source-discovery pages
- Historical or draft material (excluded from normal current-requirement retrieval)

**Reason:**
- Textual similarity alone is insufficient for evidence quality.
- A web page may provide useful process guidance while a tariff controls if the two conflict.
- Historical or draft material should not be presented as current requirements unless explicitly requested.

**Alternatives considered:**
- Treating all sources as equally authoritative.
- Using only primary sources and ignoring supporting material.
- Relying solely on URL domain (e.g., `.gov` vs `.com`) for authority.

**Trade-offs:**
- Manual authority assignment requires judgement but improves answer quality.
- Excluding historical material from default retrieval reduces contamination but requires explicit handling for historical queries.

---

## 06. Evaluation strategy

**Decision:**
- Build a small, manually curated set of representative DER questions.
- For each question, identify:
  - Required source document IDs
  - Required section or chunk IDs
  - Acceptable supporting sources
  - Sources that should not rank prominently
- Compare multiple retrieval approaches:
  - Vector-only
  - Lexical/full-text only
  - Hybrid (vector + lexical)
  - Hybrid with reranking
  - Hybrid with source-tier and currency-aware filtering (planned)
- Evaluate LLM answers and preliminary evidence briefs on:
  - Groundedness
  - Citation correctness
  - Source hierarchy representation
  - Completeness (conditions, exceptions, uncertainty, gaps)
  - Category coverage (for broad requests)
  - Usefulness (directs human to appropriate source and validation action)

**Reason:**
- A small, high-quality evaluation set is more actionable than a large, noisy one.
- Retrieval and generation errors have different causes and should be measured separately.
- Source hierarchy and currency are central to the value proposition; they must be evaluated explicitly.

**Alternatives considered:**
- Relying solely on automated metrics (e.g., nDCG, MRR) without human judgement.
- Using synthetic questions generated by an LLM.
- Evaluating only end-to-end answer quality without isolating retrieval.

**Trade-offs:**
- Manual curation is time-consuming but yields clearer signals.
- Automated metrics are scalable but may not reflect real-world usefulness.

---

## 07. Raw extraction and evidence normalisation

**Decision:**
- Preserve `data/processed/extracted/` as immutable, page-preserving raw extraction artifacts.
- Add extraction schema and method metadata to each extracted document and the extraction manifest.
- Generate separately tracked, deterministic normalised evidence outputs in `data/processed/normalised/`.
- Keep PDF physical-page locators and HTML heading-path locators in every normalised block.
- Use document-specific normalisation where structure requires it, including a dedicated SCE Rule 21 tariff parser.
- Preserve tariff Rule 21 sheet number, Cal. PUC sheet number, effective date, and advice letter as citation metadata.
- Treat tariff Roman-numeral entries as list items by default, except short title-like entries that are deterministic level-four subheadings.
- Exclude non-substantive cover, approval, contents, certificate, page-header, and repeated document-control material from normalised evidence outputs.
- Keep SIWG Phase 2 in the corpus as historical/draft context, excluded from normal current-requirement retrieval.

**Reason:**
- Raw PDF and HTML extraction provides reproducible evidence, but outputs have incompatible structures: PDF pages, HTML blocks, tables, repeated headers, document-control notices, and tariff sheet metadata.
- Citation-grade RAG requires a consistent evidence-block representation without changing or discarding the raw extracted source material.
- The SCE Rule 21 tariff has a distinct legal hierarchy and recurring Cal. PUC sheet structure that cannot be handled reliably by the generic PDF normaliser.
- Normalisation must remain deterministic and auditable before later chunking, embedding, retrieval, or generated-answer stages.
- Regression fixtures derived from raw tariff pages protect critical parsing behaviour for nested headings, Roman entries, tariff sheet metadata, and appendices.

**Alternatives considered:**
- Replacing raw PDF extraction with a structural parser such as `pdfplumber` or `unstructured`.
- Applying one generic PDF normalisation strategy to every source.
- Chunking raw page text directly.
- Using an LLM to repair PDF layout or infer headings during normalisation.
- Treating source headers, tariff sheet metadata, and document-control text as retrievable evidence.

**Trade-offs:**
- Document-specific normalisation adds code and tests, but retains traceability and avoids applying unreliable generic heuristics to legal and technical sources.
- Some supporting-source blocks remain flagged with `no_detected_heading_path`; these are review limitations, not extraction failures.
- Raw `pypdf` layout artefacts remain in evidence text. Any future readability cleanup must be separated from citation text and must not overwrite raw extraction outputs.
- Chunking, embedding, and retrieval are deferred until normalised output quality is reviewed and accepted.

---

## 08. Structural chunking and citation preservation

**Decision:**
- Transform normalised evidence blocks into searchable chunks while preserving citations and source metadata.
- Use structural block assembly that keeps headings with their substantive descendants.
- Preserve evidence text unchanged from normalised blocks.
- Prepend heading context to embedding text only (not evidence text).
- Merge citation metadata (PDF pages, tariff sheets, Cal. PUC sheets, section IDs).
- Link neighbour chunks (previous_chunk_id, next_chunk_id).
- Flag oversized blocks without mutating text.
- Configure chunking with soft max (500 tokens), hard max (750 tokens), and overlap (90 tokens).
- Accept limited oversized blocks (5 handbook TOC blocks) as documented exceptions.

**Reason:**
- Must keep parent headings with nested child headings to avoid orphan chunks.
- Tables should stay with preceding context when under hard limit.
- Evidence text must never be mutated (breaks citation integrity).
- Heading context improves retrieval when in embedding text.
- Neighbour links enable navigation and context expansion.
- Five handbook TOC blocks exceed 750 tokens (1,033-1,561 tokens) but are dense list-of-lists, not substantive requirements.

**Alternatives considered:**
- Fixed-size chunking with overlap (would split tables and sections arbitrarily).
- LLM-based chunking (non-deterministic, expensive, loses citation structure).
- Splitting oversized blocks mid-evidence (would break citation integrity).

**Trade-offs:**
- Structural chunking requires more logic but preserves document hierarchy.
- Accepting some oversized blocks reduces chunk count but keeps evidence intact.
- Heading context in embedding text increases token count but improves retrieval.

---

## 09. Embedding and retrieval evaluation

**Decision:**
- Embed 1,049 chunks with Nomic nomic-embed-text-v1.5 (768-dim vectors, `search_document:` prefix).
- Generate 100 synthetic queries with Gemini 3.5-flash-lite (LLM-generated from sampled chunks).
- Evaluate three retrieval approaches: BM25 (token overlap), vector (cosine similarity), hybrid (reciprocal rank fusion).
- Test five metadata weighting schemes: equal, source-heavy, section-heavy, page-heavy, authority-heavy.
- Compute metrics: nDCG@10, MRR, Recall@10.
- Save results to JSONL (1,500 records, reproducible without database).
- Use vector retrieval with equal weighting for production.

**Reason:**
- Vector retrieval outperforms hybrid and BM25 on primary ranking metrics.
- Weighting scheme has a modest impact, with equal weighting performing best for vector retrieval.
- Hybrid has the best MRR, but vector was chosen for overall nDCG@10.
- File-based evaluation is reproducible (no DB needed for reviewers).
- *For full evaluation metrics and tables, please see [`docs/evaluation-notes.md`](evaluation-notes.md).*

**Alternatives considered:**
- Manual query curation (more accurate but time-consuming).
- Using only BM25 or only vector (would miss comparative insights).
- Storing evaluation results in database (less reproducible for peer review).

**Trade-offs:**
- Synthetic queries are scalable but may not capture all real-world query patterns.
- File-based evaluation is reproducible but requires separate database for production.
- Vector retrieval is best overall but hybrid has better MRR (depends on use case).

---

## 10. Production database and retrieval

**Decision:**
- Use PostgreSQL with pgvector for production RAG retrieval.
- Load 1,049 chunks and embeddings into database (chunks + chunk_embeddings tables).
- Use IVFFlat index for fast similarity search (cosine distance).
- Build `src/retrieval/retrieve.py` for production retrieval with metadata filtering.
- Keep evaluation file-based (JSONL) for reproducibility.
- Separate concerns: database for production ops, files for evaluation.

**Reason:**
- pgvector enables efficient similarity search at scale.
- Database is better for production than loading all embeddings into memory.
- Metadata filtering (by source_id) is essential for targeted retrieval.
- Evaluation must remain file-based for peer review (no DB setup required).
- Production and evaluation can coexist with different storage backends.

**Alternatives considered:**
- Keep everything in JSON files (simpler but not scalable).
- Use dedicated vector database (e.g., Qdrant, Weaviate) - adds complexity.
- Store evaluation results in database (less reproducible).

**Trade-offs:**
- PostgreSQL with pgvector adds operational complexity but scales better.
- Separate storage for eval and production requires sync but maintains reproducibility.
- IVFFlat index is faster but approximate (acceptable for RAG retrieval).

---

## 11. Embedding and retrieval evaluation v2

**Decision:**
- Embed 1,049 chunks with Nomic nomic-embed-text-v1.5 (768-dim vectors, `search_document:` prefix).
- Generate 100 synthetic queries with Gemini 3.5-flash-lite (LLM-generated from sampled chunks).
- Evaluate multiple retrieval approaches:
  - BM25 (token overlap)
  - Vector (cosine similarity)
  - Hybrid (reciprocal-rank fusion of BM25 + vector with configurable α and RRF k)
  - Hybrid + reranking (cross-encoder on top of hybrid candidates)
  - Vector + reranking (cross-encoder on top of vector candidates)
- Test five metadata weighting schemes: equal, source-heavy, section-heavy, page-heavy, authority-heavy.
- Sweep hybrid α ∈ {0.3, 0.5, 0.7} and plan RRF k ∈ {1, 20, 60, 100} (course-aligned).
- Compute metrics: nDCG@10, MRR, Recall@10, and a composite score.
- Save results to JSONL (8,100 records for retrieval, plus rewrite variants), reproducible without database.
- Use hybrid retrieval with reranking and equal weighting (α = 0.5, RRF k = 1) for production.

**Reason:**
- Reranked retrievers clearly dominate on all metrics compared to non-reranked baseline methods.
- Among reranked configurations, weighting scheme has tiny effects; equal weighting is chosen for simplicity and a marginal edge on the composite score.
- Hybrid α has modest impact relative to the reranking effect; 0.5 is a sensible default.
- RRF k sweep is planned to align with course experiments.
- *For full evaluation metrics, grids, and historical tables, please see [`docs/evaluation-notes.md`](evaluation-notes.md).*

**Alternatives considered:**
- Using only vector or only BM25 (would miss large gains from reranking).
- Choosing a more complex weighting scheme (e.g. authority-heavy) for production.
- Selecting vector_rerank instead of hybrid_rerank (slightly lower composite, but similar profile).
- Running only a single α or a single weighting scheme (would under-explore the design space).

**Trade-offs:**
- Reranking adds latency and a model dependency (BAAI/bge-reranker-base) but yields large quality gains.
- Equal weighting is simpler to justify and implement, at the cost of ignoring small, uncertain gains from tuned weightings.
- File-based evaluation is reproducible and peer-review friendly, but requires separate database logic for production.
- Synthetic queries are scalable and systematic, but may not capture all real-world query patterns; manual queries can be added later.

**Supersedes:**
- [Decision 09](#09-embedding-and-retrieval-evaluation) as the historical file-based evaluation decision.

**Superseded by:**
- [Decision 12](#12-production-aligned-postgresql-retrieval-evaluation) as the authoritative production retrieval-evaluation and selection decision.

---

## 12. Production-aligned PostgreSQL retrieval evaluation

**Decision:**
- Treat the PostgreSQL/pgvector retrieval evaluation completed on 2026-09-05 as the authoritative final retrieval evaluation for DER RegCheck.
- Retain Decisions 09 and 11 and their file-based results as historical offline-baseline artifacts rather than directly comparable production results.
- Evaluate the fixed benchmark of 100 synthetic queries against the 1,049-chunk production corpus using the deployed retrieval path:
  - PostgreSQL full-text lexical retrieval
  - pgvector vector retrieval
  - PostgreSQL-backed hybrid retrieval
  - Runtime Nomic query embedding
  - `BAAI/bge-reranker-base` cross-encoder reranking
- Retain the five metadata weighting schemes:
  - Equal
  - Source-heavy
  - Section-heavy
  - Page-heavy
  - Authority-heavy
- Sweep hybrid alpha values of 0.3, 0.5, and 0.7.
- Use JSONL checkpointing and persisted summaries for reproducible, resumable evaluation.
- Evaluate cached query-rewrite variants:
  - Original query
  - Expanded query
  - HyDE query
  - HyDE-expanded query
- Compute nDCG@10, MRR, Recall@10, and the documented composite score.
- Select expanded-query vector retrieval with cross-encoder reranking as the current default retrieval configuration.
- Use equal metadata weighting as the default evaluation configuration.
- Keep hybrid alpha at 0.5 if hybrid retrieval is used.
- Disable HyDE as a default query-rewrite technique.

**Reason:**
- The deployed runtime uses PostgreSQL full-text retrieval, pgvector vector retrieval, runtime query embeddings, and cross-encoder reranking. Final retrieval claims should therefore be based on that runtime path rather than a separate file-based evaluator.
- The historical evaluator used locally loaded embeddings and a lightweight lexical-overlap baseline. It tested a different experimental condition even though it used the same query benchmark and corpus.
- Reranking was the dominant observed performance improvement in the deployed retrieval evaluation.
- Vector reranking achieved the strongest observed ranking result.
- Hybrid reranking was effectively tied on leading ranking metrics but was marginally lower on composite score.
- The expanded-query vector-rerank configuration achieved the highest observed query-rewrite composite score.
- Query expansion improved ranking metrics only modestly relative to the original vector-rerank query.
- HyDE and HyDE-expanded variants reduced ranking quality on this corpus.
- Equal and authority-heavy weighting tied for the strongest vector-rerank score. Equal weighting is selected because it is simpler to explain and maintain.
- PostgreSQL lexical retrieval was substantially weaker than vector retrieval in this benchmark.
- *For exact commands, models, exact metrics, full grids, and the old-vs-new caveat, please refer to [`docs/evaluation-notes.md`](evaluation-notes.md).*

**Alternatives considered:**
- Retaining the historical file-based v2 hybrid-rerank result as the final production selection.
- Selecting hybrid reranking instead of vector reranking.
- Using the original query rather than query expansion.
- Enabling HyDE or HyDE plus query expansion.
- Selecting authority-heavy weighting rather than equal weighting.
- Replacing PostgreSQL/pgvector with a dedicated vector database.
- Removing historical file-based results from project documentation.

**Trade-offs:**
- Reranking adds latency and dependency on `BAAI/bge-reranker-base`, but it produced the main observed ranking-quality improvement.
- Query expansion slightly improved nDCG@10, MRR, and composite score, but reduced Recall@10 and has not yet been validated with a paired statistical test.
- Vector reranking is simpler than hybrid reranking because it does not depend on the weak lexical baseline, though hybrid reranking remains a viable near-tied alternative.
- Equal weighting is transparent and simple, but metadata weighting itself is an evaluation mechanism rather than a demonstrated runtime relevance policy.
- The 100 queries are synthetic and generated from the indexed corpus. They provide controlled comparative coverage but may not represent real user-query distributions.
- Relevance is metadata-derived rather than manually judged semantic relevance.
- Recall@10 measures recovery of chunks that satisfy the metadata relevance threshold. It must not be interpreted as the share of real user questions answered successfully.
- Migrating from the file-based evaluator to the PostgreSQL evaluator changed multiple implementation details simultaneously. The comparison does not establish that PostgreSQL alone changed performance.
- Tier 1 retrieval metrics do not demonstrate end-to-end groundedness, citation correctness, source-hierarchy handling, completeness, or regulatory applicability. Tier 2 RAG quality evaluation remains required.
- Historical file-based evaluation artifacts remain valuable for reproducibility and development history, but keeping both evaluators increases documentation and maintenance overhead.

**Evidence and artifacts:**
- `data/evaluation/queries.jsonl`
- `data/evaluation/query_rewrites.jsonl`
- `data/evaluation/evaluation_results_postgres.jsonl`
- `data/evaluation/evaluation_summary_postgres.json`
- `data/evaluation/query_rewrite_results_postgres.jsonl`
- `data/evaluation/query_rewrite_summary_postgres.json`
- `src/evaluation/evaluate_retrieval.py`
- `src/evaluation/summarise_evaluation.py`
- `tests/test_evaluate_retrieval.py`
- `tests/test_summarise_evaluation.py`
- `docs/evaluation-notes.md`

**Supersedes:**
- [Decision 11](#11-embedding-and-retrieval-evaluation-v2) as the final production retrieval-selection decision.
- Decision 11 remains valid as the historical file-based v2 evaluation record.

---

## 13. Runtime configuration: disable query expansion for latency

**Decision:**
- Disable query expansion in the runtime application.
- Use the original user query (not expanded) with vector retrieval and cross-encoder reranking.
- Accept the negligible retrieval-quality trade-off for a substantial latency reduction.

**Reason:**
- v3 evaluation showed query expansion improved composite score only marginally.
- Live API latency for expansion is significant, pushing total answer latency to unacceptable levels for a demo.
- The retrieval-quality gain does not justify the latency penalty for a demo/portfolio system.

**Alternatives considered:**
- Keep query expansion enabled and accept the latency penalty.
- Implement caching for repeated queries.
- Use a faster model for query expansion.
- Batch expansion requests for multiple users.

**Trade-offs:**
- Minor nDCG@10 reduction.
- Latency improvement is significant (approximately 75% reduction).
- User experience is significantly improved for demo and portfolio purposes.
- Expansion logic remains available in the codebase for future optimization.

**Evidence and artifacts:**
- `docs/evaluation-notes.md` — Query-rewrite evaluation results and interpretation.
- `data/evaluation/query_rewrite_summary_postgres.json` — Aggregated query-rewrite metrics.
- Runtime latency measurements from live API testing (2026-09-05).

**Impact:**
- Production retrieval configuration:

```text
Original query (no expansion)
→ pgvector vector retrieval
→ BAAI/bge-reranker-base cross-encoder reranking
→ top 10 evidence chunks
```

- User-facing latency is drastically reduced per query.
- Retrieval quality remains excellent despite disabling expansion.

**Future work:**
- Consider re-enabling expansion if API latency can be reduced through caching, faster models, or batch processing.
- Monitor user feedback to determine if the retrieval-quality difference is perceptible in practice.

**Supersedes:**
- None (this is a runtime optimization decision that complements Decision 12).

---

## 14. LLM answer evaluation and prompt configuration selection

**Decision:**
- Treat the LLM answer evaluation completed on 2026-09-05 as the authoritative answer-quality evaluation for DER RegCheck.
- Evaluate three prompt configurations on 24 fixed evaluation questions:
  - `v1_direct_rag`: Direct RAG prompt without explicit structure
  - `v2_structured_grounded_rag`: Structured prompt with explicit grounding instructions
  - `v3_few_shot_grounded_rag`: Few-shot prompt with grounding examples
- Use an LLM judge (`gemini-3.5-flash-lite`) to score each answer on five dimensions:
  - Groundedness (1-5)
  - Relevance (1-5)
  - Completeness (1-5)
  - Citation quality (1-5)
  - Appropriate uncertainty (1-5)
- Compute a composite score for each answer.
- Apply a citation-validity guardrail: only configurations with 100% valid citations are eligible for selection.
- Select `v3_few_shot_grounded_rag` as the production prompt configuration.
- Use the selected prompt configuration in the Streamlit interface and future API deployments.

**Reason:**
- The v3 prompt configuration achieved 100% citation validity, the only configuration to meet the guardrail.
- v3 achieved a high mean composite score, indicating strong answer quality.
- v2 had a slightly higher composite score but failed to meet the citation validity guardrail.
- Citation validity is a critical safety property for a regulatory research tool; invalid citations undermine trust and traceability.
- The few-shot examples in v3 appear to improve citation discipline without sacrificing answer quality.
- *For detailed judge scores and metrics, please see [`docs/evaluation-notes.md`](evaluation-notes.md).*

**Alternatives considered:**
- Selecting v2 based on highest composite score despite citation failures.
- Relaxing the citation-validity guardrail to 95% or 90%.
- Using a different composite formula (e.g., equal weights, or higher weight on groundedness).
- Manual review of the answers with citation issues to assess severity.
- Iterating on v2 or v1 prompts to fix citation issues before selection.

**Trade-offs:**
- The 100% citation-validity guardrail may exclude configurations with higher overall quality but occasional citation errors.
- Few-shot prompts are longer and may increase token costs slightly.
- The LLM judge is itself an LLM and may have scoring biases; manual review of a sample would increase confidence.
- The 24 evaluation questions cover important scenarios but are not exhaustive; future iterations should expand the question set.
- The judge's composite formula weights groundedness most heavily; alternative weightings could change the ranking.

**Evidence and artifacts:**
- `data/evaluation/llm_evaluation_questions.yaml`
- `data/evaluation/llm_answers.jsonl`
- `data/evaluation/llm_judge_scores.jsonl`
- `data/evaluation/llm_evaluation_summary.json`
- `data/evaluation/llm_evaluation_report.md`
- `src/evaluation/evaluate_llm_answers.py`
- `src/evaluation/summarise_llm_evaluation.py`

**Supersedes:**
- None (this is the first answer-quality evaluation decision).

**Future work:**
- Expand the evaluation question set to 50-100 questions covering more edge cases.
- Add manual review of a sample of judge scores to validate the LLM judge's reliability.
- Test additional prompt variants (e.g., v4 with stronger uncertainty language, v5 with source-hierarchy emphasis).
- Integrate citation-validity checking into the CI pipeline to prevent regressions.
- Re-run evaluation when the corpus is updated or new sources are added.

---

## 15. Streamlit interface adapter and tabbed reviewer workflow

**Decision:**
- Use Streamlit as the primary reviewer-facing interface and portfolio demo.
- Implement `src/ui/streamlit_app.py` as an interface adapter over the existing
  production retrieval and answer-generation pipeline.
- Provide five connected tabs: About, Ask, Evidence, Review, and Monitoring.
- Use a shared selected cached response as the state boundary between tabs.
- Use a sidebar for recent-query navigation rather than a dense static
  information panel.

**Reason:**
- A tabbed interface separates concerns:
  - Ask focuses on interaction and answer consumption.
  - Evidence focuses on provenance inspection.
  - Review focuses on human evaluation.
  - Monitoring focuses on system and evaluation signals.
- A shared selected-query model avoids disconnects between answer, evidence,
  and review tabs.
- Streamlit provides rapid UI development with minimal code and integrates
  cleanly with the existing Python pipeline.
- A sidebar for recent-query navigation is more useful than a large static
  About panel for day-to-day review work.

**Alternatives considered:**
- Building a React or Vue frontend with a separate backend API.
- Keeping a single long page with all information in one tab.
- Using a different Python UI framework (e.g., Gradio, Dash).
- Placing all project information in the sidebar instead of an About tab.

**Trade-offs:**
- Streamlit is simpler than a full frontend framework but less customizable.
- A tabbed UI requires more navigation but improves clarity and focus.
- A shared selected-query model requires careful state management but avoids
  confusion between tabs.
- A sidebar for navigation is less visible than a top-level menu but keeps
  focus on the main content area.

**Impact:**
- Reviewers interact with the system through a single Streamlit application.
- The UI does not duplicate retrieval or answer-generation logic; it calls
  `AnswerGenerator` and existing retrieval components.
- Evidence cards, status badges, and feedback widgets are standardized across
  tabs.
- The About tab centralizes static project information, runtime configuration,
  project links, and responsible-use boundary.

**Supersedes:**
- None (this is the first interface-architecture decision).

**Future work:**
- Consider a separate frontend framework if more complex interactions are
  required in future iterations.
- Add multi-page navigation if the app grows beyond five tabs.
- Improve responsive design for mobile and small-screen reviewers.

---

## 16. PostgreSQL-backed configuration-aware answer cache

**Decision:**
- Add a `query_cache` table to PostgreSQL to store configuration-specific
  question/answer/evidence snapshots.
- Compute a configuration hash from:
  - Prompt version.
  - Top-K value.
  - Retrieval configuration identifier.
- Use (question text, configuration hash) as the cache key.
- Persist query/answer records immediately after successful generation; do not
  require a feedback event before storing the response.
- Load existing cached responses on cache hit instead of repeating retrieval,
  reranking, and LLM generation.
- Record cache-miss generation latency for each cached response.

**Reason:**
- Repeated questions, especially Tier 2 examples, should not re-run the full
  RAG pipeline on every UI interaction.
- A configuration-aware cache prevents reusing an answer created under a
  different prompt or retrieval setup.
- Persisting responses immediately simplifies observability and enables
  feedback and manual review without re-generation.
- Cache-miss latency is a useful operational metric for the end-to-end RAG
  path.

**Alternatives considered:**
- Caching only in memory (would not survive restarts).
- Caching only question text without configuration hash (would mix answers from
  different prompt or retrieval setups).
- Requiring a feedback event before storing a response (would lose unreviewed
  answers).
- Storing only question and answer text without evidence snapshot (would limit
  review and debugging).

**Trade-offs:**
- Configuration-aware caching increases cache misses slightly but improves
  answer-quality control.
- Persisting all responses increases storage but enables comprehensive
  observability and review.
- Recording latency only on cache misses complicates analysis but provides a
  truthful measure of the full RAG path.

**Impact:**
- Repeated questions with the same configuration load the existing response.
- New questions are persisted immediately after successful generation.
- Feedback and manual-review events are linked to a stable cached answer.
- Monitoring can report cached query volume and cache-miss latency.

**Evidence and artifacts:**
- `src/database/db_init.py` — observability schema and `query_cache` table.
- `src/observability/query_cache.py` — cache lookup and save functions.
- `src/ui/streamlit_app.py` — cache integration in Ask and Review tabs.

**Supersedes:**
- None (this is the first caching decision).

**Future work:**
- Add cache invalidation when the corpus or retrieval configuration changes.
- Consider TTL-based expiration for very old cached responses.
- Add cache statistics (hit rate, miss rate, average latency) to monitoring.

---

## 17. Feedback and manual-review event model

**Decision:**
- Add `answer_feedback` and `manual_scores` tables to PostgreSQL.
- Link both tables to `query_cache.cache_id`.
- Store helpful/not-helpful feedback events in `answer_feedback`.
- Store structured human evaluation events in `manual_scores` with:
  - Groundedness (1–5).
  - Relevance (1–5).
  - Completeness (1–5).
  - Citation quality (1–5).
  - Appropriate uncertainty (1–5).
  - Optional free-text notes.
- Permit multiple feedback and manual-review events for a single cached answer.
- Retain JSONL copies in:
  - `data/feedback/feedback.jsonl`
  - `data/evaluation/tier2_manual_scores.jsonl`
- Treat PostgreSQL as the operational source of truth; JSONL records are
  secondary portable artifacts.

**Reason:**
- Feedback and manual evaluations serve different purposes and should be stored
  separately.
- Linking to `cache_id` ensures scores and feedback are associated with a
  specific persisted answer and evidence set.
- Multiple events per cached answer support repeated review and multiple
  reviewers.
- JSONL copies provide simple portability during the prototype stage.

**Alternatives considered:**
- Storing only JSONL feedback and scores (would limit monitoring and
  aggregation).
- Using a single table for both feedback and scores (would mix different
  event types).
- Requiring exactly one feedback or score per cached answer (would prevent
  repeated review).
- Dropping JSONL entirely (would lose simple portable artifacts).

**Trade-offs:**
- Separate tables increase schema complexity but improve clarity and query
  patterns.
- Multiple events per answer increase storage but support richer evaluation.
- Maintaining both PostgreSQL and JSONL increases write overhead but provides
  redundancy and portability.

**Impact:**
- Reviewers can submit feedback and scores independently.
- Monitoring can aggregate feedback counts and average scores.
- Tier 2 evaluation is supported through structured manual scores.
- Feedback and scores are linked to a stable cached answer for traceability.

**Evidence and artifacts:**
- `src/database/db_init.py` — `answer_feedback` and `manual_scores` tables.
- `src/ui/streamlit_app.py` — feedback and score submission in Ask and Review.
- `data/feedback/feedback.jsonl` — JSONL feedback log.
- `data/evaluation/tier2_manual_scores.jsonl` — JSONL manual-score log.

**Supersedes:**
- None (this is the first feedback and review-model decision).

**Future work:**
- Add reviewer identity and role fields to support multi-reviewer workflows.
- Add inter-rater reliability metrics when multiple reviewers score the same
  answer.
- Consider removing JSONL logs once PostgreSQL is fully trusted and backed up.

---

## 18. Tier 2 manual evaluation separation from prompt regression

**Decision:**
- Maintain two separate evaluation question sets:
  - A 24-question set for prompt-regression evaluation (v1/v2/v3 comparison).
  - A 10-question Tier 2 set for realistic manual RAG-quality evaluation.
- Use the 24-question set to compare prompt configurations under deterministic
  citation validation.
- Use the Tier 2 set for human review of end-to-end RAG usefulness.
- Use five Tier 2 questions as examples in the Ask tab.
- Expose all Tier 2 questions in the Review tab.

**Reason:**
- The 24-question set includes adversarial and edge-case questions that are
  valuable for prompt comparison but not representative of typical user
  queries.
- Tier 2 questions are designed to be realistic, open-ended DER research
  questions suitable for human review.
- Separating the sets avoids conflating prompt-regression results with
  real-world RAG usefulness.
- Using a subset of Tier 2 questions as examples keeps the Ask tab focused
  while still exposing reviewers to realistic questions.

**Alternatives considered:**
- Using a single question set for both prompt regression and manual review.
- Using only synthetic questions for both evaluation types.
- Using only manual questions for both evaluation types.
- Exposing all Tier 2 questions as examples in Ask.

**Trade-offs:**
- Maintaining two sets increases documentation and maintenance overhead.
- The 24-question set may not represent typical user queries but is valuable
  for stress-testing prompts.
- Tier 2 questions are more realistic but require human review effort.
- Using a subset of Tier 2 examples keeps Ask focused but may hide some
  interesting questions from casual reviewers.

**Impact:**
- Prompt-regression evaluation remains focused on v1/v2/v3 comparison.
- Tier 2 evaluation supports realistic human assessment of RAG quality.
- The Ask tab provides a small, reviewer-friendly set of examples.
- The Review tab provides access to the full Tier 2 set for comprehensive
  evaluation.

**Evidence and artifacts:**
- `data/evaluation/llm_evaluation_questions.yaml` — 24-question prompt-regression set.
- `data/evaluation/tier2_questions.yaml` — 10-question Tier 2 set.
- `src/evaluation/evaluate_llm_answers.py` — prompt-regression evaluation.
- `src/ui/streamlit_app.py` — Tier 2 question selection and scoring in Review.

**Supersedes:**
- None (this is the first Tier 2 separation decision).

**Future work:**
- Expand the Tier 2 set to 20–30 questions covering more scenarios.
- Add manual review of a sample of 24-question answers to validate the LLM
  judge's reliability.
- Consider merging the sets if future evaluation shows they overlap significantly.

---

## 19. Monitoring dashboard and cache-miss latency interpretation

**Decision:**
- Implement a seven-chart monitoring dashboard in the Monitoring tab:
  1. Answer-status distribution.
  2. Helpful versus not-helpful feedback distribution.
  3. Average manual-review scores by quality dimension.
  4. Cache-miss generation latency over time.
  5. Average cache-miss generation latency by answer status.
  6. Cached query volume over time.
  7. Tier 2 manual-review coverage.
- Use Altair for chart layout control, including horizontal categorical bars,
  horizontal category labels, responsive chart width, explicit chart height,
  readable answer-status labels, and calendar-date formatting for
  query-volume charts.
- Use compact stable labels such as `T2-001` for Tier 2 coverage; keep full
  question text accessible in the Review tab.
- Provide safe empty states for all charts when no valid observations exist.
- Distinguish cache hits from cache misses:
  - Cache hits are fast database lookups.
  - Cache-miss latency represents the end-to-end RAG path.
  - Cache hits are not treated as full retrieval and answer-generation timing
    observations.
- Do not create artificial runtime records simply to populate charts.

**Reason:**
- A small set of focused charts provides actionable signals about answer
  behavior, feedback, quality, and latency.
- Altair provides explicit control over orientation, label placement, date
  formatting, chart height, and responsive width, which simple Streamlit
  charts do not.
- Compact Tier 2 labels improve chart readability; full question text remains
  available in Review.
- Safe empty states prevent misleading zeros and clarify how reviewers can
  populate each chart.
- Distinguishing cache hits from cache misses provides a truthful measure of
  the full RAG path and avoids conflating database lookups with generation
  latency.

**Alternatives considered:**
- Using simple Streamlit bar charts for all monitoring charts.
- Showing raw reranker scores in evidence cards and monitoring.
- Creating artificial runtime records to populate charts for demo purposes.
- Using a single composite chart instead of multiple focused charts.

**Trade-offs:**
- Altair requires more configuration but provides better control and
  readability.
- Compact Tier 2 labels improve chart clarity but require navigation to Review
  for full question text.
- Safe empty states may leave some charts blank initially but avoid misleading
  interpretations.
- Distinguishing cache hits from cache misses complicates analysis but provides
  a truthful measure of the full RAG path.

**Impact:**
- Reviewers can inspect answer behavior, feedback, quality, and latency in one
  place.
- Charts remain truthful and interpretable even with sparse data.
- Cache-miss latency is a reliable indicator of end-to-end RAG performance.
- Tier 2 coverage is visible at a glance while full question text remains
  accessible in Review.

**Evidence and artifacts:**
- `src/ui/streamlit_app.py` — Monitoring tab and seven-chart dashboard.
- `src/database/db_init.py` — observability schema and tables.
- `src/observability/query_cache.py` — cache lookup and save functions.
- `data/feedback/feedback.jsonl` — JSONL feedback log.
- `data/evaluation/tier2_manual_scores.jsonl` — JSONL manual-score log.

**Supersedes:**
- None (this is the first monitoring-dashboard decision).

**Future work:**
- Add cache-hit rate and average cache-hit latency charts.
- Add inter-rater reliability metrics when multiple reviewers score the same
  answer.
- Consider adding time-series charts for feedback and scores over time.
- Add drill-down views for individual cached answers from chart clicks.

---

## 20. Processed-data distribution and optional ingestion

**Decision:**

- Do not commit raw corpus PDFs or HTML files from `data/corpus/` to the public repository.
- Commit the processed, machine-readable artifacts required to run the application:
  - `data/processed/extracted/`
  - `data/processed/normalised/`
  - `data/processed/chunks/`
  - `data/processed/embeddings/`
- Treat the ingestion and source-download pipeline as optional for normal Milestone 5 application startup.
- Use the committed processed artifacts as the default input for database initialisation and application startup.
- Retain the source downloader and ingestion scripts for future corpus refreshes and advanced reproduction.
- Require corpus metadata validation and, where necessary, manual replacement when a source cannot be downloaded reliably.

**Reason:**

- One source, the SCE Interconnection Handbook, intermittently returns HTML,
  SharePoint content, or authentication material instead of the expected PDF.
- Requiring every user or evaluator to download the source before running the
  application would make the “one command” containerised workflow unreliable.
- The processed artifacts are sufficient to initialise the knowledge base,
  run retrieval, use the Streamlit application, and reproduce the documented
  evaluation workflow.
- Excluding raw PDF and HTML files reduces repository size and avoids
  unnecessarily redistributing source documents whose rights remain with their
  respective publishers.
- Content hashes, source URLs, extraction metadata, and provenance fields
  preserve traceability without requiring the raw source files to be present in
  the public repository.

**Alternatives considered:**

- Commit the raw PDFs and HTML files directly to Git.
- Require users to download and validate the entire corpus before starting the application.
- Host a separate corpus archive through a GitHub Release or external dataset store.
- Commit only embeddings and omit extracted, normalised, and chunked artifacts.
- Re-run the complete ingestion pipeline automatically every time Docker Compose starts.

**Trade-offs:**

- Committing processed artifacts increases repository size compared with a
  code-only repository.
- A clean-clone user can run the application without independently reproducing
  the raw-download step.
- Reproducing the entire corpus from source URLs still requires the downloader,
  source access, and possible manual replacement.
- Processed artifacts are derived data and do not provide the same archival
  guarantee as retaining the original source files.
- The application and evaluation workflow are reproducible from committed
  processed data, while full source acquisition remains a separate refresh
  workflow.
- Future corpus refreshes must regenerate downstream artifacts and trigger a
  new retrieval evaluation before existing results are treated as applicable
  to the refreshed corpus.

**Impact:**

- `data/corpus/` remains a local acquisition directory and is ignored by Git.
- `data/corpus/corpus_metadata.json` remains the source of truth for download
  validation, content hashes, manual review, and extraction eligibility.
- `data/processed/` is the default reproducibility boundary for Milestone 5.
- The standard startup path is:
  - Start PostgreSQL with Docker Compose.
  - Initialise the database schema.
  - Load committed chunks and embeddings.
  - Start the Streamlit application.
- The source download and ingestion pipeline is documented as optional for
  normal application startup.
- A source refresh that changes content hashes requires re-extraction,
  normalisation, chunking, embedding generation, database reload, and a new
  dated retrieval evaluation.
- README, dataset notes, and runbook documentation must distinguish:
  - committed processed artifacts;
  - uncommitted raw source files; and
  - optional corpus-refresh commands.

**Evidence and artifacts:**

- `README.md` — Data and copyright note and committed-processed-data startup path.
- `docs/dataset-notes.md` — Data lifecycle, distribution, copyright, and source notes.
- `docs/runbook.md` — Recommended Milestone 5 startup path and optional ingestion workflow.
- `src/ingestion/download_california_rule21_docs.py` — Source acquisition and validation.
- `src/ingestion/extract_raw_content.py` — Raw extraction.
- `data/corpus/corpus_metadata.json` — Source hashes and eligibility metadata.
- `data/processed/extracted/` — Tracked raw-extraction derivatives.
- `data/processed/normalised/` — Tracked normalised evidence blocks.
- `data/processed/chunks/` — Tracked searchable chunks.
- `data/processed/embeddings/` — Tracked embedding artifacts.

**Supersedes:**

- No previous decision is fully superseded.
- This decision clarifies and operationalises the distribution implications of
  [Decision 03](#03-ingestion-and-download-strategy) for Milestone 5.

**Future work:**

- Consider publishing a versioned corpus manifest or processed-data release
  artifact separately from the source repository.
- Add automated checks that verify committed processed-artifact counts and
  content hashes before application startup.
- Consider a data-version identifier in the database schema and cache key.
- Revisit raw-source distribution if publisher terms, repository size, or
  deployment requirements change.

---

## 21. RAG impact evaluation and retrieval contribution

**Decision:**

- Add a separate RAG impact evaluation focused on the contribution of retrieval and evidence grounding to answer quality.
- Keep this evaluation separate from:
  - the 100-query retrieval benchmark; and
  - the 24-question prompt-regression and production-prompt selection study.
- Use the 10-question Tier 2 set in `data/evaluation/tier2_questions.yaml`.
- Compare four answer-generation conditions:
  - **A — Naive model-only baseline:** no retrieved evidence and a general-knowledge prompt.
  - **B — V3 without evidence:** the evidence-bounded v3 prompt with no retrieved evidence.
  - **C — Zero-shot RAG:** `v1_direct_rag` with production-retrieved evidence.
  - **D — Full v3 RAG:** `v3_few_shot_grounded_rag` with the same retrieved evidence used for C.
- Reuse one shared top-10 production evidence pack for Cases C and D for each question.
- Evaluate outputs using:
  - deterministic citation-label validation;
  - answer-status and expected-behaviour checks; and
  - blinded pairwise LLM judging with `gemini-3.5-flash-lite`.
- Treat retrieval contribution as the primary impact question. Treat additional prompt optimisation as a secondary future-work question.

**Reason:**

- The existing 24-question evaluation was designed primarily to compare prompt configurations under a strict citation-validity guardrail.
- The Tier 2 set contains 10 more realistic questions covering:
  - direct factual lookup;
  - multi-chunk synthesis;
  - clarification-sensitive questions;
  - out-of-corpus handling;
  - high-stakes decision boundaries; and
  - historical-source treatment.
- Comparing a no-evidence model against evidence-backed RAG provides a direct test of whether the retrieval layer improves answers over a plain LLM baseline.
- Reusing the same retrieved evidence for Cases C and D controls retrieval variation when comparing zero-shot RAG with the full v3 prompt.
- A separate impact evaluation avoids overstating the meaning of the prompt-selection benchmark.
- The experiment is appropriate for a portfolio project where no real users or attached business workflow are available.

**Alternatives considered:**

- Measuring business outcomes such as conversion, revenue, or research productivity.
- Running a real-user satisfaction or task-completion study.
- Using only the 24-question prompt-regression set.
- Comparing only the full RAG system with a naive LLM baseline.
- Relying solely on LLM-judge scores without deterministic validation.
- Treating the selected v3 prompt as the only possible source of improvement.

**Trade-offs:**

- The 10-question set is realistic and manageable but too small for a conclusive general performance claim.
- LLM judging provides scalable comparative evidence but is not independent human evaluation.
- The same Gemini model family is used for answer generation and judging, which may introduce model-specific preferences.
- Case B is primarily a safety-control condition rather than a substantive answer-quality competitor because it receives no evidence.
- Deterministic citation-label validation confirms label validity and claim-citation presence, but not semantic entailment between claims and evidence.
- The experiment measures comparative answer quality, not business impact, user satisfaction, or time saved.
- Additional prompt optimisation was not the main focus of this experiment; further improvements may require more systematic prompt iteration and independent human review.

**Impact:**

- Retrieval produced the clearest observed improvement:
  - Zero-shot RAG was preferred to the naive no-evidence baseline in 8 of 10 blinded comparisons.
  - Full v3 RAG was preferred to the naive no-evidence baseline in 8 of 10 blinded comparisons.
  - Full v3 RAG was preferred to the v3 no-evidence condition in 9 of 10 comparisons.
- The full v3 configuration achieved slightly higher pooled judge scores than zero-shot RAG across groundedness, relevance, completeness, citation quality, and appropriate uncertainty.
- The zero-shot RAG versus full v3 pairwise result was mixed:
  - Zero-shot RAG was preferred in 5 of 10 comparisons.
  - Full v3 RAG was preferred in 3 of 10 comparisons.
  - The remaining 2 comparisons were ties.
- The result supports retrieval and evidence grounding as the primary quality improvement demonstrated by this experiment.
- The result does not establish that v3 prompt engineering consistently outperforms zero-shot RAG on realistic Tier 2 questions.
- Additional prompt optimisation remains a worthwhile future direction, especially for:
  - few-shot example selection;
  - clarification and abstention behaviour;
  - source-hierarchy instructions; and
  - concise answers that preserve uncertainty and evidence boundaries.

**Evidence and artifacts:**

- `data/evaluation/tier2_questions.yaml` — 10-question Tier 2 evaluation set.
- `src/evaluation/generate_impact_answers.py` — Four-case answer generation.
- `src/evaluation/judge_impact_answers.py` — Blinded pairwise LLM judging.
- `src/evaluation/summarise_impact_evaluation.py` — Aggregation and reporting.
- `data/evaluation/impact_answers.jsonl` — Generated answer records.
- `data/evaluation/impact_judge_scores.jsonl` — Pairwise judge records.
- `data/evaluation/impact_summary.json` — Machine-readable summary.
- `data/evaluation/impact_report.md` — Human-readable impact report.
- `src/generation/citation_validator.py` — Deterministic citation-label validation.
- `docs/evaluation-notes.md` — Detailed protocol, metrics, results, and limitations.

**Supersedes:**

- No previous decision is superseded.
- This decision complements:
  - [Decision 06](#06-evaluation-strategy), which separates retrieval and answer-quality evaluation.
  - [Decision 14](#14-llm-answer-evaluation-and-prompt-configuration-selection), which selects the production prompt under the citation-validity guardrail.
  - [Decision 18](#18-tier-2-manual-evaluation-separation-from-prompt-regression), which separates the Tier 2 question set from the 24-question prompt-regression set.

**Future work:**

- Repeat the evaluation after deliberate prompt optimisation rather than treating the current prompt comparison as final.
- Expand the Tier 2 set and preserve a dated evaluation version for comparability.
- Add independent human scoring for a sample of the same A–D comparisons.
- Compare judge preferences with human-review agreement.
- Add semantic citation-entailment assessment rather than relying only on citation-label validity.
- Evaluate whether retrieval improvements persist across a larger and more diverse question set.
- Preserve each future run as a dated artifact rather than overwriting the current results.