# DER RegCheck


> An evidence-first RAG application for converting fragmented public DER interconnection material into traceable research answers and preliminary market-entry evidence briefs.


> **Project status:** In active development. Ingestion and extraction are implemented; database, retrieval, generation, and interface are under development.


## Overview


DER RegCheck is an internal-tool-style prototype for researching distributed energy resource (DER) interconnection and market-entry requirements.


It accepts a structured project context and either:


1. A **focused evidence question**, such as: "What official source material covers telemetry requirements?"; or
2. A broader **market-entry research goal**, such as: "What should be validated before pursuing a DER communications and control opportunity in this market?"


For a focused question, DER RegCheck retrieves and explains the most relevant evidence directly. For a broader research goal, it creates a transparent retrieval plan, retrieves evidence across multiple research categories, and generates a structured preliminary market-entry evidence brief.


Version 1 focuses on the California Rule 21 / Southern California Edison (SCE) context. The corpus includes utility tariffs, technical guidance, web pages, testing instructions, and historical working-group material. These sources are intentionally not treated as equally authoritative.


The application makes the basis of an answer visible: users can inspect the source document, section, page range where available, authority level, retrieval tier, currency status, and supporting excerpt behind a result.


## Problem statement


Teams researching DER products, projects, or market opportunities must locate, read, compare, and interpret a large set of public but fragmented documents. Depending on the research context, relevant information may be distributed across a regulator's overview page, a utility tariff, an interconnection handbook, a testing/certification instruction sheet, utility web guidance, and historical standards or working-group reports.


This research is difficult for several reasons:


- **Document heterogeneity:** tariffs, handbooks, websites, tables, forms, and technical procedures use different structures and citation conventions.
- **Source hierarchy:** a web page may provide useful process guidance, while a formal tariff may control if the two conflict.
- **Conditional rules:** relevance can depend on the utility, DER type, exporting or non-exporting status, project size, interconnection stage, equipment category, or technical configuration.
- **Versioning:** documents may be revised, replaced, withdrawn, or silently updated at the same URL. A result is more useful when its source version and check date are visible.
- **Manual effort:** locating a relevant clause, preserving its thresholds and exceptions, following cross-references, and comparing sources takes time and can miss important context.


A general-purpose LLM alone is not an appropriate solution. It may generate uncited answers, confuse historical recommendations with current requirements, or overlook conditions located in another section. DER RegCheck uses retrieval-augmented generation (RAG) to ground outputs in retrieved, versioned source chunks and distinguish primary sources from supporting implementation or historical material.


## Scope


### In scope for v1


- Public California Rule 21 / SCE interconnection material.
- A downloadable, source-provenanced, and version-aware document corpus.
- Source-specific extraction and chunking for PDF and HTML documents.
- Metadata-aware retrieval over document authority, source type, currency, and retrieval tier.
- A structured project-context form and natural-language research request.
- Two interaction modes: focused evidence questions and market-entry evidence briefs.
- A controlled, template-based research-plan / query-decomposition step for broad requests.
- Multiple focused retrieval queries generated from selected project context and a broader research goal.
- Retrieved evidence with source links, heading paths, and page citations where available.
- Generated answers and briefs grounded in retrieved context.
- Preliminary evidence-based findings, source hierarchy, uncertainty flags, and validation actions.
- Evaluation of multiple retrieval and answer-generation configurations.
- User feedback capture and runtime monitoring.


### System boundaries for v1


DER RegCheck can generate preliminary research findings and structured validation actions from its configured public corpus. It may identify requirement areas that appear relevant to a selected context, surface primary and supporting sources, highlight uncertainty, and produce a preliminary market-entry evidence brief.


However, v1 does not make final legal, regulatory, engineering, compliance, commercial, or customer-approval decisions. It cannot determine that a specific product, project, device, or configuration meets a requirement unless the necessary evidence is available in the corpus and the conclusion is reviewed by an accountable human expert.


### Out of scope for v1


- Formal legal or regulatory advice.
- A final compliance determination.
- A final market-entry, customer-approval, or go/no-go decision.
- Automated comparison against private product-capability, security, roadmap, OEM, contract, or customer-specific data.
- Direct regulatory filing, utility application submission, or control of DER equipment.
- Coverage of every Californian utility or every electricity market.
- A guarantee that every public source remains current.


## Intended users


The prototype is aimed at people who need a defensible starting point for public DER interconnection and market-entry research, for example:


- Product or strategy teams assessing a potential DER market.
- Industry or regulatory analysts mapping relevant public sources.
- Engineers identifying primary technical and interconnection material.
- Project developers researching public connection, testing, or certification material.
- Analysts who need source-backed answers and a visible record of uncertainty.


The tool supports human judgement. It does not replace regulatory specialists, utility guidance, legal review, engineering review, or the official source documents.


## Application modes


### Focused evidence question


A user supplies project context and one evidence question:


```text
Utility / jurisdiction: Southern California Edison (SCE)
Asset type: Battery energy storage system
Export mode: Non-exporting
Project stage: Interconnection and certification research


Question:
What official material should I review for interconnection,
certification, and inadvertent-export requirements?
```


DER RegCheck then:


1. Normalises the project context and question.
2. Retrieves relevant source chunks using metadata, lexical search, and semantic search.
3. Prioritises current primary sources where the question concerns requirements.
4. Reranks the evidence and generates a concise grounded answer.
5. Shows supporting evidence with authority, retrieval-tier, and currency labels.
6. Allows the user to rate the answer and optionally leave feedback.


### Market-entry evidence brief


A user can also submit a broader research request:


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


For v1, DER RegCheck uses a controlled, transparent research-plan template rather than an open-ended autonomous agent.


```text
Research plan


1. Identify current primary and technical sources
2. Review interconnection process and application pathways
3. Review technical and operating requirements
4. Review communications, telemetry, monitoring, and control
5. Review equipment certification and testing
6. Identify source authority, currency risks, applicability issues, and gaps
```


Each category becomes a focused retrieval query. The system retrieves evidence for each category, merges and deduplicates the evidence, applies source-authority checks, and generates a preliminary evidence brief.


## Data sources


The v1 corpus is composed of public documents from the California Public Utilities Commission (CPUC) and Southern California Edison (SCE). The downloader records source URLs, content hashes, last-checked timestamps, and version/currency cues where available.


| Source | Corpus role | Default retrieval tier |
|---|---|---|
| CPUC Electric Rule 21 overview page | Regulatory context and discovery of authoritative sources | `source_discovery` |
| SCE Rule 21 tariff | Primary interconnection requirements | `primary_requirements` |
| SCE Interconnection Handbook | Technical implementation detail | `primary_technical` |
| SCE Rule 21 interconnection web guidance | Process guidance, forms, and source discovery | `supporting_process` |
| Smart Inverter Working Group Phase 2 Recommendations | Historical context and standards rationale | `historical_context` |
| SCE testing and certification instruction | Equipment testing and certification implementation guidance | `supporting_implementation` |


### Source hierarchy


Textual similarity is not sufficient evidence quality. Each chunk carries an authority level and retrieval tier.


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


Historical or draft material is excluded from normal current-requirement retrieval unless a user asks a specifically historical question. Supporting guidance can be retrieved, but the generated output must not present it as equivalent to a controlling source.


## Architecture


```text
Public CPUC and SCE documents
            |
            v
Download + source metadata + content hashes
            |
            v
PDF / HTML text extraction
            |
            v
Document-specific normalisation and chunking
            |
            v
PostgreSQL + pgvector knowledge base
            |
            v
Project context + user research request
            |
            v
Research-plan generation
(focused query or multi-category evidence-brief plan)
            |
            v
Metadata-aware hybrid retrieval + reranking
(per focused retrieval question)
            |
            v
Evidence aggregation, deduplication, and authority checks
            |
            v
Grounded answer or preliminary market-entry evidence brief
            |
            v
Streamlit interface, feedback, and monitoring dashboard
```


### Ingestion and chunking


The corpus is structurally heterogeneous, so DER RegCheck does not apply one fixed-size text splitter to every source.


- **Utility tariff:** hierarchy-aware clause chunking. Each chunk retains its section path, conditions, thresholds, exceptions, tables, and page/sheet citations where available.
- **Interconnection handbook:** hierarchy-aware technical chunking with table and cross-reference preservation.
- **Testing instruction:** section/subsection chunks preserving equipment-specific checklists, tables, and associated footnotes.
- **Web guidance:** HTML heading- and accordion-aware chunking. Navigation, cookie banners, headers, footers, and unrelated boilerplate are removed; hyperlinks are preserved.
- **Working-group report:** section-based contextual chunks labelled as draft/historical material where applicable.


## Retrieval and generation flow


### Focused evidence question


```text
Project context + focused user question
            ↓
Query normalisation / optional query rewriting
            ↓
Metadata filters
(utility, source tier, current/draft status, asset type when available)
            ↓
Candidate retrieval
(vector + lexical / full-text search)
            ↓
Hybrid rank fusion + document reranking
            ↓
Top evidence chunks
            ↓
Grounded answer-generation prompt
            ↓
Answer + citations + uncertainty / review note
```


### Market-entry evidence brief


```text
Project context + broad research goal
            ↓
Controlled research-plan template
            ↓
Focused retrieval questions by category
            ↓
Metadata-aware hybrid retrieval and reranking for each category
            ↓
Evidence aggregation, deduplication, and authority checks
            ↓
Grounded preliminary evidence brief
```


The answer-generation prompt will instruct the LLM to:


- Use only retrieved context.
- Cite the underlying document and section/page metadata.
- State when evidence is insufficient.
- Distinguish primary requirements from supporting guidance.
- Identify open questions and validation actions when evidence is incomplete.
- Avoid unsupported legal, compliance, engineering, or commercial conclusions.


## Preliminary evidence brief


The broad-request output is a structured research artefact, not a final decision.


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
   - What the retrieved evidence indicates
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


### Research-plan evaluation


For broad market-entry requests, DER RegCheck is evaluated on whether its controlled research plan covers the expected evidence categories.


Expected categories may include:


- Primary and technical sources.
- Interconnection process.
- Technical and operating requirements.
- Communications and telemetry.
- Testing and certification.
- Currency, authority, applicability, and evidence gaps.


The v1 plan is deliberately template-based. Evaluation checks that the appropriate categories are selected for a given request and that resulting focused retrieval queries are correctly scoped.


### Focused retrieval evaluation


A manually curated evaluation set will contain representative, scoped DER questions. Each query will identify:


- Required source document IDs.
- Required section or chunk IDs.
- Acceptable supporting source IDs.
- Sources that should not rank prominently.
- Expected source-authority tier.


The evaluation will compare multiple retrieval approaches:


1. Vector-only retrieval.
2. Lexical/full-text retrieval.
3. Hybrid retrieval.
4. Hybrid retrieval with reranking.
5. **Planned:** Hybrid retrieval with source-tier and currency-aware filtering.


Planned metrics include:


- Document Recall@k.
- Section Recall@k.
- Mean Reciprocal Rank (MRR).
- Primary-source Recall@k.
- Historical/draft contamination rate.
- Retrieval latency.


### LLM answer and brief evaluation


Focused answers and preliminary evidence briefs will be evaluated across multiple prompt or model configurations using labelled test sets.


The evaluation rubric will score:


- **Groundedness:** Does the output stay within retrieved evidence?
- **Citation correctness:** Do citations support the stated claim?
- **Source hierarchy:** Are primary and supporting sources represented correctly?
- **Completeness:** Are material conditions, exceptions, uncertainty, and evidence gaps noted?
- **Category coverage:** For broad requests, does the brief cover the planned research areas?
- **Usefulness:** Does the output clearly direct a human to the appropriate source material and validation action?


Results and configuration-selection decisions will be published in [`docs/evaluation-notes.md`](docs/evaluation-notes.md).


## Interface


**Planned:** A Streamlit interface will provide:


- A choice between **Focused evidence question** and **Market-entry evidence brief** modes.
- Project-context controls: utility, asset type, export status, project stage, target customer type, and capability focus.
- Natural-language question input.
- A visible research-plan panel for broad requests.
- Generated evidence-grounded answers or briefs.
- Expandable category-level source evidence cards.
- Source authority, retrieval tier, version, check date, section path, and page citations.
- Thumbs-up/down feedback and optional comments.
- A separate runtime monitoring dashboard.


![Placeholder for DER RegCheck query interface](docs/images/query-interface-placeholder.png)


Replace this placeholder with a screenshot once the interface is available.


## Monitoring and feedback


**Planned:** Runtime telemetry and optional user feedback will be persisted to PostgreSQL.


The monitoring dashboard is intended to include at least five charts:


1. Query volume over time.
2. Retrieval latency distribution.
3. Retrieved source/document frequency.
4. Authority-tier distribution of retrieved evidence.
5. User feedback ratio and feedback volume over time.
6. Optional: documents with changed hashes, currency warnings, or review flags.


## Repository structure


```text
der-regcheck/
├── app/                         # Streamlit application and dashboard
├── config/                      # Chunking, research-plan, and retrieval policies
├── data/
│   ├── corpus/                  # Downloaded source documents and metadata
│   ├── processed/               # Extracted text and chunks
│   ├── evaluation/              # Public evaluation queries, plans, and labels
│   └── source_manifest.json     # Source provenance and retrieval metadata
├── docs/
│   ├── project-log.md           # Working journal and stage-by-stage progress
│   ├── decisions.md             # Key design choices and trade-offs
│   ├── dataset-notes.md         # Corpus source details and extraction issues
│   ├── evaluation-notes.md      # Retrieval and answer/brief evaluation
│   └── runbook.md               # Setup, reproduction, and troubleshooting
├── src/
│   ├── database/                # PostgreSQL and pgvector access
│   ├── evaluation/              # Plan, retrieval, and answer evaluation
│   ├── generation/              # LLM prompts and answer/brief orchestration
│   ├── ingestion/               # Download, extract, normalise, and chunk
│   ├── monitoring/              # Telemetry and feedback persistence
│   ├── planning/                # Research-plan templates and query decomposition
│   └── retrieval/               # Vector, lexical, hybrid, and reranking logic
├── compose.yaml                 # Planned full-stack Docker Compose runtime
├── pyproject.toml               # Python dependencies managed with uv
├── uv.lock                      # Locked dependency versions
└── README.md
```


## Technology stack


| Component | Technology | Status |
|---|---|---|
| Language and dependency management | Python + uv | Implemented |
| Knowledge base | PostgreSQL + pgvector | Planned |
| Embeddings | To be selected and evaluated | Planned |
| Research planning | Template-based query decomposition | Planned |
| Retrieval | Vector, lexical, hybrid, reranking | Planned |
| LLM | Configurable provider/model | Planned |
| Interface | Streamlit | Planned |
| Monitoring | PostgreSQL + Streamlit dashboard | Planned |
| Runtime | Docker Compose | Planned |


## Local setup


### Prerequisites


- Python 3.11+
- `uv` for dependency management: https://github.com/astral-sh/uv


### Install dependencies


```bash
cd der-regcheck
uv sync
```

Add ingestion dependencies if not already present:

```bash
uv add requests beautifulsoup4 pypdf
```


### Download the corpus


```bash
uv run python src/ingestion/download_california_rule21_docs.py
```

This downloads all configured sources to `data/corpus/` and writes metadata to `data/corpus/corpus_metadata.json`.


### Handle blocked downloads


If a source fails validation (e.g., returns HTML instead of PDF):

1. Manually download the file via browser or authenticated portal.
2. Save it to the configured path (e.g., `data/corpus/03_sce_interconnection_handbook.pdf`).
3. Mark it as manually replaced:

```bash
uv run python src/ingestion/download_california_rule21_docs.py \
  --mark-manual-replacement sce_interconnection_handbook_pdf \
  --reviewer your-name
```


### Extract content


```bash
uv run python src/ingestion/extract_raw_content.py
```

This extracts page-preserving PDF text and main-content HTML to `data/processed/extracted/` and writes a manifest to `data/processed/extraction_manifest.json`.


### Run the application (planned)


```bash
cp .env.example .env
# Edit .env to set DATABASE_URL, LLM_PROVIDER, LLM_API_KEY, etc.
uv run streamlit run app/main.py
```


## Course project rubric mapping


This repository is being built as an end-to-end project for the DataTalks.Club LLM Zoomcamp.


| Criterion | Evidence / planned evidence |
|---|---|
| Problem description | This README: [Problem statement](#problem-statement), [Scope](#scope), and [Data sources](#data-sources) |
| Knowledge base and LLM retrieval flow | [Architecture](#architecture) and [Retrieval and generation flow](#retrieval-and-generation-flow) |
| Retrieval evaluation | [`docs/evaluation-notes.md`](docs/evaluation-notes.md) — planned comparison of vector, lexical, hybrid, and reranked retrieval |
| LLM evaluation | [`docs/evaluation-notes.md`](docs/evaluation-notes.md) — planned answer and evidence-brief evaluation |
| Interface | Streamlit application — planned |
| Ingestion pipeline | `src/ingestion/` — implemented download, validation, manual replacement, and extraction |
| Monitoring | PostgreSQL telemetry, feedback, and dashboard — planned |
| Containerization | `compose.yaml` — planned |
| Reproducibility | `uv.lock`, `.env.example`, this README, and `docs/runbook.md` |
| Hybrid search | Vector + lexical retrieval evaluation — planned |
| Document reranking | Retrieval-reranking experiment — planned |
| Query rewriting | Query-rewriting experiment — planned |


## Limitations and responsible use


- DER RegCheck is a research and decision-support prototype, not a legal, regulatory, engineering, or compliance-authority system.
- It can only retrieve and reason over documents included in its corpus.
- A retrieved document may no longer be current; the system records source checks and version cues but does not guarantee source currency.
- Generated outputs may be incomplete or incorrect. Users must inspect original documents and seek qualified human review where appropriate.
- Supporting web guidance, testing instructions, and historical reports are not equivalent to a controlling utility tariff.
- The initial corpus is deliberately narrow and does not represent every utility, technology, project type, or market.
- A preliminary evidence brief is not a final compliance, product-readiness, or market-entry decision.


## Documentation


- [`docs/project-log.md`](docs/project-log.md) — Working journal and stage-by-stage progress.
- [`docs/decisions.md`](docs/decisions.md) — Key design choices and trade-offs.
- [`docs/dataset-notes.md`](docs/dataset-notes.md) — Corpus source details, extraction issues, and version notes.
- [`docs/evaluation-notes.md`](docs/evaluation-notes.md) — Retrieval and answer/brief evaluation framework and results.
- [`docs/runbook.md`](docs/runbook.md) — Setup, reproduction, and troubleshooting instructions.


## License


This project is released under the [MIT License](LICENSE), unless source-material terms require otherwise.


Public source documents remain subject to their original publishers' copyright, licence, and terms of use. The project records source provenance and does not claim ownership of regulatory or utility source content.