# Project log


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