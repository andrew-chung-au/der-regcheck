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