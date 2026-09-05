# DER RegCheck

> An evidence-first RAG prototype for DER interconnection and market-entry research.

**Project status:** Ingestion, normalisation, chunking, embedding, PostgreSQL/pgvector database loading, production-aligned retrieval evaluation, answer-generation evaluation, and Streamlit interface are implemented. The authoritative retrieval evaluation uses the deployed PostgreSQL retrieval path with runtime query embedding, vector retrieval, and cross-encoder reranking. The runtime application disables query expansion for latency reasons and uses the `v3_few_shot_grounded_rag` prompt configuration selected under a 100% deterministic citation-validity guardrail. A PostgreSQL-backed answer cache, feedback capture, manual-review workflow, and seven-chart Monitoring dashboard are implemented; aggregate Tier 2 human-review results remain pending.

---

## Problem statement

Teams researching distributed energy resource (DER) products, projects, or market opportunities must locate, read, compare, and interpret a fragmented set of public documents. Depending on the research context, relevant information may be distributed across a regulator's overview page, a utility tariff, an interconnection handbook, a testing/certification instruction sheet, utility web guidance, and historical standards or working-group reports.

This research is difficult for several reasons:

- **Document heterogeneity:** Tariffs, handbooks, web pages, tables, forms, and technical procedures use different structures and citation conventions.
- **Source hierarchy:** A web page may provide useful process guidance, while a formal tariff may control if the two conflict.
- **Conditional rules:** Relevance can depend on utility, DER type, exporting or non-exporting status, project size, interconnection stage, equipment category, voltage, or technical configuration.
- **Versioning and currency:** Documents may be revised, replaced, withdrawn, or silently updated at the same URL.
- **Historical contamination:** Historical or draft material can be useful for rationale but should not be represented as a current requirement.
- **Manual effort:** Locating relevant provisions, preserving thresholds and exceptions, following cross-references, and comparing source authority takes time and can miss important context.

A general-purpose LLM alone is not an appropriate solution. It may generate uncited answers, confuse historical recommendations with current requirements, or overlook conditions located in another section.

**DER RegCheck addresses this problem** by building a retrieval-augmented generation system that grounds outputs in retrieved, versioned source evidence and distinguishes primary sources from supporting implementation or historical material.

---

## Overview

DER RegCheck helps teams research DER interconnection requirements by retrieving and explaining relevant provisions from public regulatory and utility documents.

It supports two modes:

1. **Focused questions:** "What does SCE Rule 21 require for smart inverter reactive power?"
2. **Market-entry research:** "What should we review before pursuing a DER communications opportunity in SCE territory?"

The system distinguishes primary tariff requirements from supporting guidance and historical material, with traceable citations to source documents.

**This is a research-support tool only.** It does not provide legal, regulatory, engineering, or compliance advice.

---

## Data sources

The v1 corpus contains six public sources from the California Public Utilities Commission (CPUC) and Southern California Edison (SCE). For full source details, URLs, processing notes, chunk counts, authority levels, and quality status, please see [`docs/dataset-notes.md`](docs/dataset-notes.md).

---

## Retrieval flow

The implemented pipeline preserves a clear boundary between raw source extraction, normalised evidence, searchable chunks, embeddings, and database storage:

```text
Public CPUC and SCE documents
            |
            v
Download + validation + source metadata + content hashes
            |
            v
Raw PDF / HTML extraction (pypdf, BeautifulSoup)
            |
            v
Deterministic evidence normalisation (source-specific rules)
            |
            v
Quality reporting + regression tests
            |
            v
Structural chunking (1,049 chunks, citation-preserving)
            |
            v
Embedding generation (Nomic 768-dimensional vectors)
            |
            v
PostgreSQL + pgvector knowledge base (1,049 chunks + embeddings)
            |
            v
Runtime query embedding
            |
            v
pgvector vector retrieval
            |
            v
Cross-encoder reranking
            |
            v
Grounded answer generation with citations (v3_few_shot_grounded_rag)
            |
            v
Configuration-aware answer cache (PostgreSQL)
            |
            v
Streamlit interface, feedback capture, manual review, and monitoring
```

**Key design choices:**

- Raw extraction outputs remain immutable and auditable.
- Normalisation creates deterministic evidence blocks without altering raw outputs.
- Chunking preserves document hierarchy and citation metadata.
- Embeddings use `search_document:` and `search_query:` prefixes for asymmetric retrieval.
- PostgreSQL provides lexical retrieval and pgvector provides vector similarity search.
- Reranking uses `BAAI/bge-reranker-base` on a candidate set before returning final evidence chunks.
- Historical/draft SIWG material is excluded from default current-requirement retrieval.
- Retrieval evaluation uses a fixed 100-query benchmark and metadata-derived relevance labels.
- Answer-generation evaluation uses 24 fixed questions and an LLM judge under a 100% citation-validity guardrail.
- Answers are cached by question text and configuration hash to avoid repeated generation for identical queries.
- Feedback and manual-review scores are stored as separate events linked to cached answers.

For implementation details, setup, evaluation commands, and troubleshooting, see [`docs/runbook.md`](docs/runbook.md).

---

## Retrieval evaluation

### Authoritative evaluation: v3 (2026-09-05)

The authoritative retrieval evaluation runs through the deployed PostgreSQL/pgvector retrieval path. The top-performing configuration (Vector rerank, equal weighting) achieved an nDCG@10 of **0.94627** and a composite score of **0.76989**.

For the comprehensive 7,500-record retrieval grid breakdown, query-rewrite evaluation findings, historical baseline comparisons, and full metric interpretation, please refer to the definitive results in [`docs/evaluation-notes.md`](docs/evaluation-notes.md).

### Evaluation-best vs runtime retrieval configuration

The evaluation-best configuration used an expanded query:

```text
Expanded query
→ pgvector vector retrieval
→ BAAI/bge-reranker-base cross-encoder reranking
→ top 10 evidence chunks
```

The deployed runtime application uses the original user query:

```text
Original user query
→ pgvector vector retrieval
→ BAAI/bge-reranker-base cross-encoder reranking
→ top 10 evidence chunks
```

**Why this configuration:**

- Query expansion improved composite score by only 0.00285 (approximately 0.37%).
- Live expansion latency: approximately 32–36 seconds.
- Total answer latency with expansion: approximately 50 seconds.
- Total answer latency without expansion: approximately 14 seconds.
- The retrieval-quality gain does not justify the latency penalty for the intended use case.

This is a data-driven engineering decision. The expansion implementation remains available for future re-assessment if caching, model choice, or infrastructure changes the latency trade-off.

---

## Answer-generation evaluation

### Evaluation setup (2026-09-05)

- **24 fixed questions** across six categories:
  - `direct_factual`
  - `multi_chunk_synthesis`
  - `ambiguous_needs_clarification`
  - `out_of_corpus`
  - `high_stakes_boundary`
  - `historical_source_handling`
- **Three prompt configurations:**
  - `v1_direct_rag`: direct RAG prompt
  - `v2_structured_grounded_rag`: structured prompt with explicit grounding instructions
  - `v3_few_shot_grounded_rag`: few-shot grounded prompt with examples
- **Deterministic citation validation** for every generated answer
- **LLM judge** (`gemini-3.5-flash-lite`) scoring on five dimensions:
  - Groundedness
  - Relevance
  - Completeness
  - Citation quality
  - Appropriate uncertainty
- **Composite score:**

```text
0.30 × Groundedness
+ 0.20 × Relevance
+ 0.20 × Completeness
+ 0.20 × Citation quality
+ 0.10 × Appropriate uncertainty
```

### Results

| Prompt version | Citation-valid rate | Mean composite |
|---|---:|---:|
| `v1_direct_rag` | 94.6% | 4.7509 |
| `v2_structured_grounded_rag` | 97.3% | **4.8670** |
| `v3_few_shot_grounded_rag` | **100.0%** | 4.8110 |

### Selected configuration

`v3_few_shot_grounded_rag` is selected as the runtime prompt because it is the only configuration meeting the 100% deterministic citation-validity guardrail. The selected v3 mean composite of 4.8110 is 96.2% of the maximum possible score of 5.0.

For full methodology, judge rubric, limitations, and artifacts, see [`docs/evaluation-notes.md`](docs/evaluation-notes.md) and [`docs/decisions.md`](docs/decisions.md) #14.

---

## How to run

### Prerequisites

- Python 3.11+
- `uv` for dependency management
- Docker and Docker Compose for PostgreSQL with pgvector
- A local `.env` file containing required database and LLM settings

### Quick start

```bash
# Clone and install dependencies
cd der-regcheck
uv sync

# Create local environment configuration
cp .env.example .env

# Download corpus
uv run python src/ingestion/download_california_rule21_docs.py

# Extract, normalise, and chunk evidence
uv run python src/ingestion/extract_raw_content.py
uv run python src/processing/normalise_documents.py
uv run python src/processing/chunk_documents.py

# Generate embeddings
uv run python src/processing/generate_embeddings.py \
  --model nomic-ai/nomic-embed-text-v1.5

# Start and initialise PostgreSQL
docker compose up -d db
uv run python src/database/init_db.py

# Load chunks and embeddings
uv run python src/scripts/load_chunks_to_db.py \
  --chunks-dir data/processed/chunks \
  --embeddings-file data/processed/embeddings/embeddings.jsonl

# Run evaluator regression tests
uv run python -m unittest \
  tests.test_evaluate_retrieval \
  tests.test_summarise_evaluation \
  tests.test_answer_generator

# Run the Streamlit app
uv run streamlit run src/ui/streamlit_app.py
```

For complete setup instructions, database checks, retrieval evaluation, answer-generation evaluation, troubleshooting, and safe regeneration guidance, see [`docs/runbook.md`](docs/runbook.md).

---

## Project structure

```text
der-regcheck/
├── compose.yaml          # Docker Compose runtime
├── config/               # Normalisation and chunking rules
├── data/                 # Corpus, processed outputs, and evaluation artifacts
├── docs/                 # Documentation
├── src/                  # Python source code
├── tests/                # Regression tests
├── pyproject.toml        # Project metadata
├── README.md             # This file
└── uv.lock               # Locked dependencies
```

See [`docs/runbook.md`](docs/runbook.md) for the complete directory structure and artifact descriptions.

---

## Implementation status

| Component | Status |
|---|---|
| Corpus ingestion | ✅ Implemented |
| Raw extraction | ✅ Implemented |
| Evidence normalisation | ✅ Implemented |
| Structural chunking | ✅ Implemented |
| Embedding generation | ✅ Implemented |
| PostgreSQL + pgvector knowledge base | ✅ Implemented |
| PostgreSQL lexical retrieval | ✅ Implemented |
| pgvector vector retrieval | ✅ Implemented |
| Hybrid retrieval | ✅ Implemented |
| Cross-encoder reranking | ✅ Implemented |
| Production-aligned retrieval evaluation | ✅ Completed 2026-09-05 |
| Cached query-rewrite evaluation | ✅ Completed 2026-09-05 |
| Evaluator and summariser regression tests | ✅ Implemented |
| Answer-generation evaluation | ✅ Completed 2026-09-05 |
| Streamlit interface | ✅ Implemented 2026-09-05 |
| PostgreSQL-backed answer cache | ✅ Implemented 2026-09-05 |
| Feedback capture | ✅ Implemented 2026-09-05 |
| Manual-review workflow (Tier 2) | ✅ Implemented 2026-09-05 |
| Monitoring dashboard (seven charts) | ✅ Implemented 2026-09-05 |
| Source-aware filtering | ⏳ Planned |
| Tier 2 aggregate human-review results | ⏳ Pending sufficient reviews |
| Paired statistical testing (query expansion) | ⏳ Planned |

For detailed progress and next steps, see [`docs/project-log.md`](docs/project-log.md).

---

## Key decisions

- **Structural chunking** instead of fixed-size splitting, to preserve document hierarchy and citation context.
- **PostgreSQL + pgvector** as the production retrieval backend.
- **Original query + vector retrieval + cross-encoder reranking** as the runtime retrieval configuration (query expansion disabled for latency).
- **Equal metadata weighting** as the default evaluation setting because it ties for the top vector-rerank score and is simple to justify.
- **HyDE disabled by default** because it reduced retrieval quality in the production-aligned benchmark.
- **Historical file-based v1/v2 evaluations retained** as offline-baseline artifacts, not as final production results.
- **Two-tier evaluation:** fixed-benchmark retrieval evaluation plus future manual RAG answer-quality evaluation.
- **Source hierarchy metadata** retained in chunks to distinguish governing, technical, supporting, and historical material.
- **`v3_few_shot_grounded_rag` prompt** selected under a 100% deterministic citation-validity guardrail.
- **Configuration-aware answer cache** to avoid repeated generation for identical questions and to anchor feedback and manual scores to stable answer snapshots.
- **Separate feedback and manual-review event tables** to support multiple reviews per cached answer.
- **Seven-chart Monitoring dashboard** with safe empty states and truthful cache-miss latency interpretation.

For rationale, alternatives, and trade-offs, see [`docs/decisions.md`](docs/decisions.md), especially Decisions 12, 13, 14, 15, 16, 17, 18, and 19.

---

## Limitations

- The v1 corpus covers California Rule 21 and SCE only; it is not yet multi-utility or multi-market.
- Sources can change at their original URLs; corpus hashes and review procedures mitigate but do not eliminate currency risk.
- Some PDF extraction artifacts remain in citation-grade evidence text.
- Review warnings remain for two supporting or historical sources with limited heading-path detection.
- Relevance metrics are metadata-derived rather than manually judged semantic relevance.
- The benchmark queries are synthetic and may not represent real user-query distributions.
- Recall@10 measures recovery of metadata-defined related chunks, not the share of real user questions successfully answered.
- Moving from the historical file-based evaluator to PostgreSQL changed multiple implementation details; the comparison cannot show that PostgreSQL alone changed performance.
- Query expansion has only a small observed gain and needs paired statistical testing or manual relevance judgments.
- The answer-generation evaluation uses an LLM judge, which may contain systematic scoring bias.
- The 24-question prompt-evaluation set is useful for regression testing but is not exhaustive.
- Tier 2 aggregate human-review results are not yet stable until sufficient manual scores have been collected.
- Source-aware filtering is not yet implemented.

See [`docs/dataset-notes.md`](docs/dataset-notes.md), [`docs/evaluation-notes.md`](docs/evaluation-notes.md), and [`docs/decisions.md`](docs/decisions.md) for detailed source, evaluation, and responsible-use limitations.

---

## Documentation

- [`docs/project-log.md`](docs/project-log.md) — Working journal and stage-by-stage progress
- [`docs/decisions.md`](docs/decisions.md) — Design choices and trade-offs, including Decisions 12–19
- [`docs/dataset-notes.md`](docs/dataset-notes.md) — Corpus details, source hierarchy, processing, and quality notes
- [`docs/evaluation-notes.md`](docs/evaluation-notes.md) — Retrieval protocol, historical v1/v2 context, authoritative v3 results, answer-generation evaluation, and Tier 2 plan
- [`docs/runbook.md`](docs/runbook.md) — Setup, reproduction, evaluation, and troubleshooting

---

## License

MIT License. Public source documents remain subject to their original publishers' terms.