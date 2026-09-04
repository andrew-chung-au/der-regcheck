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