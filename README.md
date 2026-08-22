# DER RegCheck


> An evidence-first RAG prototype for converting fragmented public DER interconnection material into traceable research answers and preliminary market-entry evidence briefs.


> **Project status:** In active development. Corpus ingestion, raw extraction, deterministic evidence normalisation, quality reporting, and tariff regression tests are implemented. Chunking, database, retrieval, generation, evaluation experiments, interface, feedback capture, and monitoring are planned.


## Overview

DER RegCheck is a research-support prototype for investigating distributed energy resource (DER) interconnection and preliminary market-entry requirements.

It is intended to support two future interaction modes:

1. A **focused evidence question**, such as: “What official source material covers telemetry requirements?”; or
2. A broader **market-entry research goal**, such as: “What should be validated before pursuing a DER communications and control opportunity in this market?”

For focused questions, DER RegCheck will retrieve and explain the most relevant source evidence. For broader research goals, it will produce a structured, source-traceable preliminary evidence brief across relevant research categories.

Version 1 focuses on the California Rule 21 / Southern California Edison (SCE) context. The corpus includes a utility tariff, technical handbook, process web guidance, testing instructions, a regulatory overview page, and historical working-group material. These sources are intentionally not treated as equally authoritative.

The project is a research and decision-support tool only. It does not provide legal, regulatory, engineering, compliance, commercial, or customer-approval advice.


## Problem statement

Teams researching DER products, projects, or market opportunities must locate, read, compare, and interpret a fragmented set of public documents. Depending on the research context, relevant information may be distributed across a regulator's overview page, a utility tariff, an interconnection handbook, a testing/certification instruction sheet, utility web guidance, and historical standards or working-group reports.

This research is difficult for several reasons:

- **Document heterogeneity:** Tariffs, handbooks, web pages, tables, forms, and technical procedures use different structures and citation conventions.
- **Source hierarchy:** A web page may provide useful process guidance, while a formal tariff may control if the two conflict.
- **Conditional rules:** Relevance can depend on utility, DER type, exporting or non-exporting status, project size, interconnection stage, equipment category, voltage, or technical configuration.
- **Versioning and currency:** Documents may be revised, replaced, withdrawn, or silently updated at the same URL.
- **Manual effort:** Locating relevant provisions, preserving thresholds and exceptions, following cross-references, and comparing source authority takes time and can miss important context.
- **Historical contamination:** Historical or draft material can be useful for rationale but should not be represented as a current requirement.

A general-purpose LLM alone is not an appropriate solution. It may generate uncited answers, confuse historical recommendations with current requirements, or overlook conditions located in another section.

DER RegCheck is being built as a retrieval-augmented generation system that will ground outputs in retrieved, versioned source evidence and distinguish primary sources from supporting implementation or historical material.


## Scope


### In scope for v1

- Public California Rule 21 / SCE interconnection material.
- A source-provenanced and version-aware public corpus.
- Deterministic corpus download, validation, manual replacement, raw extraction, and evidence normalisation.
- Page-preserving PDF extraction and heading-path-preserving HTML extraction.
- Source-specific normalisation for regulatory and technical document structures.
- Future section-aware chunking over normalised evidence blocks.
- Future metadata-aware retrieval over authority, source type, currency, applicability, and retrieval tier.
- Future focused evidence questions and preliminary market-entry evidence briefs.
- Future retrieval and answer-generation evaluation.
- Future source-backed citations, uncertainty flags, and validation actions.
- Future feedback capture and runtime monitoring.


### System boundaries for v1

DER RegCheck can eventually generate preliminary research findings and structured validation actions from its configured public corpus. It may identify requirement areas that appear relevant to a selected context, surface primary and supporting sources, highlight uncertainty, and produce a preliminary market-entry evidence brief.

However, it will not make final legal, regulatory, engineering, compliance, commercial, customer-approval, or go/no-go decisions.

It cannot determine that a specific product, project, device, or configuration meets a requirement unless the necessary evidence is present in the corpus and the conclusion is reviewed by an accountable human expert.


### Out of scope for v1

- Formal legal or regulatory advice.
- Final compliance determination.
- Final market-entry, customer-approval, or go/no-go decision.
- Automated comparison against private product-capability, security, roadmap, OEM, contract, or customer-specific data.
- Direct regulatory filing, utility application submission, or control of DER equipment.
- Coverage of every Californian utility or every electricity market.
- A guarantee that every public source remains current.
- Replacement of official utility, regulator, engineering, legal, or compliance review.


## Intended users

The prototype is aimed at people who need a defensible starting point for public DER interconnection and market-entry research, for example:

- Product or strategy teams assessing a potential DER market.
- Industry or regulatory analysts mapping relevant public sources.
- Engineers identifying primary technical and interconnection material.
- Project developers researching public connection, testing, or certification material.
- Analysts who need source-backed answers and a visible record of uncertainty.

The tool supports human judgement. It does not replace regulatory specialists, utility guidance, legal review, engineering review, or official source documents.


## Data sources

The v1 corpus contains six public sources from the California Public Utilities Commission (CPUC) and Southern California Edison (SCE).

| Source | Corpus role | Default retrieval tier | Authority role |
|---|---|---|---|
| CPUC Electric Rule 21 overview page | Regulatory context and authoritative-source discovery | `source_discovery` | Regulatory overview; not controlling tariff text |
| SCE Rule 21 tariff | Primary interconnection requirements | `primary_requirements` | Primary tariff / governing source |
| SCE Interconnection Handbook | Technical implementation detail | `primary_technical` | Primary technical handbook |
| SCE Rule 21 interconnection web guidance | Process guidance, forms, and source discovery | `supporting_process` | Supporting process guidance |
| SIWG Phase 2 Recommendations | Historical context and standards rationale | `historical_context` | Historical/draft context |
| SCE testing and certification instruction | Equipment testing and certification implementation guidance | `supporting_implementation` | Supporting implementation guidance |


### Source hierarchy

Textual similarity is not sufficient evidence quality. Future chunks and retrieval results will carry source authority, retrieval tier, currency, and applicability metadata.

```text
Primary tariff / governing source
        ↓
Primary technical handbook
        ↓
Supporting testing or implementation guidance
        ↓
Supporting process guidance and source-discovery pages
        ↓
Historical or draft material
```

Historical or draft material is excluded from normal current-requirement retrieval unless the user explicitly requests historical context.

Supporting guidance can be retrieved where useful, but future generated outputs must not present it as equivalent to a controlling tariff.


## Current pipeline

The implemented pipeline preserves a clear boundary between raw source extraction and normalised evidence.

```text
Public CPUC and SCE documents
            |
            v
Download + validation + source metadata + content hashes
            |
            v
Raw PDF / HTML extraction
            |
            v
Deterministic evidence normalisation
            |
            v
Quality reporting + regression tests
            |
            v
Future structural chunking
            |
            v
Future PostgreSQL + pgvector knowledge base
            |
            v
Future lexical, vector, hybrid, and reranked retrieval
            |
            v
Future grounded answer or preliminary market-entry evidence brief
            |
            v
Future Streamlit interface, feedback capture, and monitoring
```


### Corpus download and metadata

Implemented downloader:

```text
src/ingestion/download_california_rule21_docs.py
```

The downloader:

- Downloads configured sources to `data/corpus/`.
- Validates expected PDF responses using the `%PDF-` signature.
- Uses a primary request with browser-style headers.
- Retries failed PDF validation with a simplified request:
  - Browser User-Agent only
  - No explicit `Accept` header
  - Default Requests redirect handling
- Tracks content hashes and last-checked timestamps.
- Records validation, manual review, extraction eligibility, and default retrieval eligibility.
- Supports manual replacement for sources that cannot be acquired reliably through automation.

The corpus metadata file is authoritative for source trust and eligibility:

```text
data/corpus/corpus_metadata.json
```


### Raw extraction

Implemented extractor:

```text
src/ingestion/extract_raw_content.py
```

Raw extraction is deterministic and does not perform chunking, LLM calls, authority assignment, embedding, retrieval, or answer generation.

PDF extraction:

- Uses `pypdf`.
- Preserves one object per physical PDF page.
- Preserves page text and `--- PAGE N ---` markers.
- Records `schema_version` and `extraction_method`.

HTML extraction:

- Uses BeautifulSoup.
- Selects main page content where available.
- Preserves headings, paragraphs, list items, and tables.
- Preserves heading paths.
- Converts HTML tables to Markdown-style text.
- Removes selected page boilerplate such as navigation, headers, footers, scripts, and forms.

Raw outputs are tracked under:

```text
data/processed/extracted/
data/processed/extraction_manifest.json
```


### Evidence normalisation

Implemented normaliser:

```text
src/processing/normalise_documents.py
```

Implemented quality checker:

```text
src/processing/quality_check_normalised.py
```

Source-specific normalisation rules are configured in:

```text
config/normalisation.yaml
```

Normalisation produces deterministic evidence blocks under:

```text
data/processed/normalised/
```

Normalised blocks retain:

- Source ID
- Source content hash
- Stable block order
- Block type
- Evidence text
- PDF physical-page locators or HTML heading-path locators
- Source-specific citation metadata
- Normalisation flags for known review limitations

Raw extraction outputs remain unchanged and available for audit and parser-regression review.


### SCE Rule 21 tariff handling

The SCE Rule 21 tariff uses a dedicated deterministic normalisation path because it contains:

- Repeated California PUC administrative sheet headers.
- Rule 21 printed sheet numbers.
- Advice-letter and effective-date metadata.
- Lettered tariff sections.
- Numbered provisions.
- Lettered subsections.
- Roman-numeral entries that can function as either list items or subheadings.
- Appendices that reset prior heading hierarchy.

The tariff normaliser:

- Excludes Table of Contents pages from normalised evidence output.
- Removes recurring administrative sheet text from evidence blocks.
- Preserves Rule 21 sheet number, Cal. PUC sheet number, effective date, and advice letter as citation metadata.
- Treats prose-style Roman entries as list items.
- Treats short title-style Roman entries as level-four headings.
- Resets hierarchy at appendices, including `APPENDIX B`.

Regression fixtures currently validate raw tariff extraction pages 50, 100, 150, and 233.


### Current normalisation status

| Source | Normalisation status | Notes |
|---|---|---|
| CPUC Rule 21 overview | Pass | HTML heading paths and tables preserved |
| SCE Rule 21 tariff | Pass | Dedicated tariff parser and regression coverage |
| SCE Interconnection Handbook | Pass | Cover, contents, certificate, and repeated headers excluded |
| SCE Rule 21 web guidance | Pass | HTML headings, lists, and tables preserved |
| SCE testing instruction | Review | Limited early reference/acronym blocks lack heading paths |
| SIWG Phase 2 Recommendations | Review | Limited early substantive blocks lack heading paths; source remains historical/draft context |

A `review` status is not an extraction failure. It indicates that one or more blocks retain physical PDF page provenance but require manual interpretation or later source-specific parser refinement.


## Future application modes


### Focused evidence question

A future user may supply project context and a focused question:

```text
Utility / jurisdiction: Southern California Edison (SCE)
Asset type: Battery energy storage system
Export mode: Non-exporting
Project stage: Interconnection and certification research

Question:
What official material should I review for interconnection,
certification, and inadvertent-export requirements?
```

The planned flow is:

1. Normalise project context and user question.
2. Apply source, utility, authority, currency, and applicability filters.
3. Retrieve lexical and semantic candidates.
4. Combine and rerank evidence.
5. Prioritise current primary sources for current-requirement questions.
6. Generate a grounded answer from retrieved evidence.
7. Display source, locator, authority, retrieval-tier, currency, and uncertainty information.
8. Allow future user feedback capture.


### Preliminary market-entry evidence brief

A future user may submit a broader research request:

```text
Market: California
Utility / customer context: Southern California Edison
Target customer type: Distribution utility
Asset types: Solar PV and battery storage
Capability focus: DER communications and control
Decision stage: Early market assessment

Question:
What current public sources should we review, which requirement areas appear
relevant, and what needs validation before pursuing this opportunity?
```

For v1, DER RegCheck is intended to use a controlled research-plan template rather than an open-ended autonomous agent.

```text
Research plan

1. Identify current primary and technical sources
2. Review interconnection process and application pathways
3. Review technical and operating requirements
4. Review communications, telemetry, monitoring, and control
5. Review equipment certification and testing
6. Identify source authority, currency risks, applicability issues, and gaps
```

Each category will become a focused retrieval query. The system will aggregate, deduplicate, and rank evidence before generating a preliminary evidence brief.


## Planned chunking, retrieval, and generation


### Structural chunking

Chunking is not implemented yet.

The next pipeline stage will consume normalised blocks rather than raw extraction outputs.

Planned chunking principles:

- Preserve canonical citation-grade evidence text.
- Create separate embedding-oriented context text where required.
- Preserve source page, sheet, section, heading path, authority, currency, and applicability metadata.
- Group headings, introductory clauses, associated lists, and trailing context into coherent semantic units.
- Avoid splitting conditions from their exceptions, thresholds, or applicability statements.
- Use fixed-size token windows only as a fallback for oversized structurally cohesive blocks.
- Keep adjacent chunk references for context expansion.


### Retrieval

Planned retrieval configurations:

1. Lexical/full-text retrieval.
2. Vector-only retrieval.
3. Hybrid lexical plus vector retrieval.
4. Hybrid retrieval with reranking.
5. Hybrid retrieval with source-tier, currency, and applicability-aware filtering.
6. Hybrid retrieval with neighbouring-chunk context expansion.

The initial vector baseline will use exact pgvector nearest-neighbour search before approximate indexing is considered.

Hybrid retrieval debug output should preserve:

- Lexical rank
- Vector rank
- Combined score
- Reranker score where applicable
- Source ID
- Authority tier
- Retrieval tier
- Currency status
- Applicability metadata


### Grounded generation

Future answer-generation prompts will instruct the model to:

- Use only retrieved context.
- Cite the underlying document and available section/page metadata.
- State when evidence is insufficient.
- Distinguish primary requirements from supporting guidance.
- Separate historical/draft context from current requirements.
- Identify open questions and validation actions when evidence is incomplete.
- Avoid unsupported legal, compliance, engineering, or commercial conclusions.


## Preliminary evidence brief

The planned broad-request output is a structured research artifact, not a final decision.

```text
DER RegCheck — Preliminary Market-entry Evidence Brief

1. Research scope
   - Market, utility/customer context, asset types, capability focus
   - Research question and corpus last-checked date

2. Source map
   - Primary governing sources
   - Primary technical sources
   - Supporting implementation/process guidance
   - Historical or draft sources excluded from current conclusions

3. Evidence areas
   - Interconnection process
   - Technical and operating requirements
   - Communications and telemetry
   - Certification and testing
   - Source currency and applicability conditions

4. Preliminary findings and validation actions
   - What retrieved evidence indicates
   - Questions for Product, Engineering, Industry, Security, or external SMEs
   - Missing evidence, ambiguous applicability, or version risks

5. Evidence appendix
   - Retrieved excerpts
   - Source URLs
   - Version/effective-date information
   - Section and page citations
   - Authority and retrieval-tier labels
```


## Evaluation

Evaluation design is documented in [`docs/evaluation-notes.md`](docs/evaluation-notes.md).

Planned evaluation areas:

- Retrieval document recall.
- Evidence or chunk recall.
- Primary-source recall.
- Mean Reciprocal Rank (MRR).
- nDCG where graded relevance labels exist.
- Historical/draft contamination rate.
- Authority-weighted retrieval quality.
- Citation-locator coverage.
- Retrieval latency.
- Groundedness of generated answers.
- Citation correctness.
- Source hierarchy representation.
- Currency and applicability handling.
- Completeness, uncertainty, and evidence-gap handling.
- Category coverage for broad market-entry research requests.
- Usefulness and validation-action quality.

Evaluation queries and relevance labels will be committed under:

```text
data/evaluation/
```


## Planned interface

A future Streamlit interface is intended to provide:

- A choice between **Focused evidence question** and **Market-entry evidence brief** modes.
- Project-context controls:
  - Utility
  - Asset type
  - Export status
  - Project stage
  - Target customer type
  - Capability focus
- Natural-language question input.
- A visible research-plan panel for broad requests.
- Generated evidence-grounded answers or briefs.
- Expandable source evidence cards.
- Source authority, retrieval tier, version, check date, section path, and page citations.
- Future thumbs-up/down feedback and optional comments.
- A separate future runtime-monitoring dashboard.


## Planned monitoring and feedback

Runtime telemetry and optional user feedback are planned for persistence in PostgreSQL.

The future monitoring dashboard is intended to include:

1. Query volume over time.
2. Retrieval latency distribution.
3. Retrieved source/document frequency.
4. Authority-tier distribution of retrieved evidence.
5. User feedback ratio and feedback volume over time.
6. Optional source freshness, changed hash, currency-warning, and review-flag views.


## Repository structure

```text
der-regcheck/
├── config/
│   └── normalisation.yaml              # Implemented source-specific normalisation rules
├── data/
│   ├── corpus/                         # Ignored raw source files and corpus metadata
│   ├── processed/
│   │   ├── extracted/                  # Tracked raw extraction artifacts
│   │   └── normalised/                 # Tracked normalised evidence blocks and quality reports
│   └── evaluation/                     # Planned labelled evaluation artifacts
├── docs/
│   ├── project-log.md                  # Working journal and stage-by-stage progress
│   ├── decisions.md                    # Key design choices and trade-offs
│   ├── dataset-notes.md                # Corpus, normalisation, and source-quality details
│   ├── evaluation-notes.md             # Retrieval and answer/brief evaluation framework
│   └── runbook.md                      # Setup, reproduction, and troubleshooting
├── src/
│   ├── ingestion/
│   │   ├── download_california_rule21_docs.py
│   │   └── extract_raw_content.py
│   └── processing/
│       ├── normalise_documents.py
│       └── quality_check_normalised.py
├── tests/
│   ├── fixtures/
│   │   └── normalisation/              # Raw tariff regression fixtures
│   ├── test_normalise_documents.py
│   └── test_quality_check_normalised.py
├── pyproject.toml                       # Python project configuration
├── uv.lock                              # Locked dependency versions
└── README.md
```


## Technology stack

| Component | Technology | Status |
|---|---|---|
| Language and dependency management | Python + uv | Implemented |
| Corpus download | Requests | Implemented |
| PDF extraction | pypdf | Implemented |
| HTML extraction | BeautifulSoup | Implemented |
| Evidence normalisation | Python + PyYAML | Implemented |
| Quality reporting | Python | Implemented |
| Regression testing | Python `unittest` | Implemented |
| Structural chunking | Deterministic section-aware assembly | Planned |
| Knowledge base | PostgreSQL + pgvector | Planned |
| Embeddings | Model to be selected and evaluated | Planned |
| Retrieval | Lexical, vector, hybrid, and reranking | Planned |
| LLM | Configurable provider/model | Planned |
| Interface | Streamlit | Planned |
| Monitoring | PostgreSQL + Streamlit dashboard | Planned |
| Runtime | Docker Compose | Planned |


## Local setup


### Prerequisites

- Python 3.11+
- `uv` for dependency management: [https://github.com/astral-sh/uv](https://github.com/astral-sh/uv)


### Install dependencies

```bash
cd der-regcheck
uv sync
```

For an independently reproduced environment:

```bash
uv add requests beautifulsoup4 pypdf pyyaml
```


### Download the corpus

```bash
uv run python src/ingestion/download_california_rule21_docs.py
```

This downloads configured sources to `data/corpus/` and writes source metadata to:

```text
data/corpus/corpus_metadata.json
```


### Handle blocked downloads

If a source fails validation, for example because a PDF URL returns HTML rather than a PDF:

1. Manually download the source through a browser or authenticated portal.
2. Save it to the configured local path.
3. Register the file as a manually reviewed replacement.

Example:

```bash
uv run python src/ingestion/download_california_rule21_docs.py \
  --mark-manual-replacement sce_interconnection_handbook_pdf \
  --reviewer your-name
```


### Extract raw content

```bash
uv run python src/ingestion/extract_raw_content.py
```

This writes raw extraction outputs to:

```text
data/processed/extracted/
data/processed/extraction_manifest.json
```


### Run normalisation tests

```bash
uv run python -m unittest \
  tests.test_normalise_documents \
  tests.test_quality_check_normalised
```


### Generate normalised evidence outputs

```bash
rm -rf data/processed/normalised/*

uv run python src/processing/normalise_documents.py \
  --input-manifest data/processed/extraction_manifest.json \
  --config config/normalisation.yaml \
  --output-dir data/processed/normalised
```


### Generate quality reports

```bash
uv run python src/processing/quality_check_normalised.py \
  --normalised-dir data/processed/normalised \
  --output-json data/processed/normalised/quality_report.json \
  --output-md data/processed/normalised/quality_report.md
```

Review the report:

```bash
sed -n '1,280p' data/processed/normalised/quality_report.md
```


## Course project rubric mapping

This repository is being built as an end-to-end project for the DataTalks.Club LLM Zoomcamp.

| Criterion | Current or planned evidence |
|---|---|
| Problem description | This README: [Problem statement](#problem-statement), [Scope](#scope), and [Data sources](#data-sources) |
| Ingestion pipeline | Implemented downloader, metadata validation, manual replacement, raw extraction, normalisation, and quality reporting |
| Knowledge base and LLM retrieval flow | Planned architecture and retrieval flow |
| Retrieval evaluation | [`docs/evaluation-notes.md`](docs/evaluation-notes.md) — framework defined; experiments planned |
| LLM evaluation | [`docs/evaluation-notes.md`](docs/evaluation-notes.md) — rubric defined; experiments planned |
| Interface | Streamlit application planned |
| Monitoring | Telemetry, feedback persistence, and dashboard planned |
| Containerization | Docker Compose runtime planned |
| Reproducibility | `uv.lock`, tracked processed artifacts, regression fixtures, this README, and `docs/runbook.md` |
| Hybrid search | Planned lexical plus vector retrieval evaluation |
| Document reranking | Planned retrieval-reranking experiment |
| Query rewriting | Planned query-rewriting experiment |


## Limitations and responsible use

- DER RegCheck is a research and decision-support prototype, not a legal, regulatory, engineering, or compliance-authority system.
- It can only retrieve and reason over documents included in its configured corpus.
- A retrieved source may no longer be current; the system records source checks and version cues but does not guarantee source currency.
- Generated outputs may be incomplete or incorrect. Users must inspect original documents and seek qualified human review where appropriate.
- Supporting web guidance, testing instructions, and historical reports are not equivalent to a controlling utility tariff.
- Some raw PDF text contains layout artifacts from page-level extraction.
- The initial corpus is deliberately narrow and does not represent every utility, technology, project type, or market.
- A preliminary evidence brief is not a final compliance, product-readiness, or market-entry decision.


## Documentation

- [`docs/project-log.md`](docs/project-log.md) — Working journal and stage-by-stage progress.
- [`docs/decisions.md`](docs/decisions.md) — Key design choices and trade-offs.
- [`docs/dataset-notes.md`](docs/dataset-notes.md) — Corpus source details, source hierarchy, extraction, normalisation, and review notes.
- [`docs/evaluation-notes.md`](docs/evaluation-notes.md) — Retrieval and answer/brief evaluation framework and future results.
- [`docs/runbook.md`](docs/runbook.md) — Setup, reproduction, output regeneration, and troubleshooting instructions.


## License

This project is released under the [MIT License](LICENSE), unless source-material terms require otherwise.

Public source documents remain subject to their original publishers' copyright, licence, and terms of use. The project records source provenance and does not claim ownership of regulatory or utility source content.