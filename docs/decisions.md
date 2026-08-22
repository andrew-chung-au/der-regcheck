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
| [09](#09-embedding-and-retrieval-evaluation) | Embedding and retrieval evaluation | Active | No |
| [10](#10-production-database-and-retrieval) | Production database and retrieval | Active | No |

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
- Use vector retrieval with equal weighting for production (nDCG@10: 0.826).

**Reason:**
- Vector retrieval outperforms hybrid and BM25 (nDCG@10: 0.826 vs 0.777 vs 0.745).
- Weighting scheme has modest impact (4% difference across schemes).
- Hybrid has best MRR (0.903 vs 0.893 for vector) - better at getting #1 result.
- Equal weighting works best for vector retrieval.
- File-based evaluation is reproducible (no DB needed for reviewers).

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