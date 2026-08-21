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
- Write project documentation: `docs/project-log.md`, `docs/decisions.md`, `docs/dataset-notes.md`, `docs/evaluation-notes.md`, `docs/runbook.md`.
- Update `README.md` to reflect implemented behaviour rather than planned features.
- Implement PostgreSQL + pgvector knowledge base and chunking logic.
- Build initial retrieval and answer-generation prototypes.