# DER RegCheck

> An evidence-first RAG prototype for DER interconnection and market-entry research.

**Project status:** Ingestion, normalisation, chunking, embedding, PostgreSQL/pgvector database loading, and production-aligned retrieval evaluation are implemented. The authoritative retrieval evaluation uses the deployed PostgreSQL retrieval path, including runtime query embedding, lexical/vector retrieval, cross-encoder reranking, and cached query-rewrite evaluation. Answer generation, interface, source-aware retrieval constraints, and monitoring remain planned.

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

1. **Focused questions:** “What does SCE Rule 21 require for smart inverter reactive power?”
2. **Market-entry research:** “What should we review before pursuing a DER communications opportunity in SCE territory?”

The system distinguishes primary tariff requirements from supporting guidance and historical material, with traceable citations to source documents.

**This is a research-support tool only.** It does not provide legal, regulatory, engineering, or compliance advice.

---

## Data sources

The v1 corpus contains six public sources from the California Public Utilities Commission (CPUC) and Southern California Edison (SCE):

| Source | Role | Authority level | Chunk count |
|---|---|---|---:|
| SCE Rule 21 tariff | Primary interconnection requirements | Governing source | 387 |
| SCE Interconnection Handbook | Technical implementation | Primary technical | 562 |
| SCE testing instruction | Equipment certification | Supporting guidance | 72 |
| SCE Rule 21 web guidance | Process guidance | Supporting process | 8 |
| CPUC Rule 21 overview | Regulatory context | Source discovery | 12 |
| SIWG Phase 2 Recommendations | Historical rationale | Historical/draft | 68 |
| **Total** |  |  | **1,049** |

For full source details, URLs, processing notes, source hierarchy, and quality status, see [`docs/dataset-notes.md`](docs/dataset-notes.md).

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
PostgreSQL lexical, pgvector vector, or hybrid retrieval
            |
            v
Cross-encoder reranking where selected
            |
            v
Future grounded answer generation with citations
            |
            v
Future Streamlit interface, feedback capture, and monitoring
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

For implementation details, setup, evaluation commands, and troubleshooting, see [`docs/runbook.md`](docs/runbook.md).

---

## Retrieval evaluation

### Authoritative evaluation: v3 (2026-09-05)

The authoritative retrieval evaluation runs through the deployed PostgreSQL/pgvector retrieval path. It uses the same fixed corpus and query benchmark as prior evaluations, but the historical file-based evaluator and the PostgreSQL evaluator are separate experimental conditions.

**Evaluation setup:**

- **100 queries:** LLM-generated using `gemini-3.5-flash-lite`.
- **1,049 chunks:** Structural chunks assembled from normalised evidence blocks.
- **1,049 embeddings:** Nomic `nomic-embed-text-v1.5`, 768-dimensional vectors.
- **Retrieval backend:** PostgreSQL full-text lexical retrieval and pgvector vector retrieval.
- **Reranker:** `BAAI/bge-reranker-base`.
- **Candidate limit:** Top 50 candidates before reranking.
- **Final result set:** Top 10 chunks.
- **Hybrid alpha sweep:** 0.3, 0.5, and 0.7.
- **Metadata weighting schemes:** Equal, source-heavy, section-heavy, page-heavy, and authority-heavy.
- **Metrics:** nDCG@10, MRR, Recall@10, and composite score:

```text
0.5 × nDCG@10 + 0.3 × MRR + 0.2 × Recall@10
```

**Completed retrieval grid:**

```text
100 queries
× 3 alpha values
× 5 retrieval variants
× 5 metadata weighting schemes
= 7,500 retrieval evaluation records
```

### Final retrieval results

| Configuration | nDCG@10 | MRR | Recall@10 | Composite |
|---|---:|---:|---:|---:|
| **Vector rerank, equal weighting** | **0.94627** | **0.92500** | 0.09625 | **0.76989** |
| Vector rerank, authority-heavy weighting | **0.94627** | **0.92500** | 0.09625 | **0.76989** |
| Hybrid rerank, equal weighting, alpha 0.50 | 0.94589 | **0.92500** | 0.09625 | 0.76969 |
| Hybrid rerank, section-heavy weighting, alpha 0.30 | 0.93240 | 0.60800 | **0.11019** | 0.67065 |
| Hybrid, equal weighting, alpha 0.50 | 0.76700 | 0.87293 | 0.08580 | 0.66253 |
| Vector, equal weighting | 0.76330 | 0.87293 | 0.08480 | 0.66049 |
| Lexical, equal weighting | 0.15420 | 0.15500 | 0.00690 | 0.12499 |

**Key findings:**

- **Cross-encoder reranking is the primary observed retrieval-quality improvement.** Vector reranking increases nDCG@10 from 0.76330 to 0.94627.
- **Vector reranking achieves the strongest observed ranking result** for nDCG@10, MRR, and composite score.
- **Hybrid reranking is a near-tied alternative** under equal weighting and alpha 0.50, but its composite score is marginally lower.
- **Equal and authority-heavy weighting tie** for the strongest vector-rerank result. Equal weighting is retained because it is easier to explain and maintain.
- **Hybrid alpha has limited practical impact after reranking.**
- **PostgreSQL lexical retrieval performs substantially worse** than vector retrieval on this benchmark.

### Query-rewrite evaluation

Cached query-rewrite variants were evaluated using the same PostgreSQL retrieval path:

```text
100 queries
× 4 rewrite techniques
× 4 retrieval variants
× 5 metadata weighting schemes
= 8,000 query-rewrite evaluation records
```

| Configuration | nDCG@10 | MRR | Recall@10 | Composite |
|---|---:|---:|---:|---:|
| **Expanded query + vector rerank, equal weighting** | **0.94713** | **0.93583** | 0.09214 | **0.77274** |
| Original query + vector rerank, equal weighting | 0.94627 | 0.92500 | 0.09625 | 0.76989 |
| HyDE query + vector rerank, equal weighting | 0.89930 | 0.69980 | 0.08420 | 0.67643 |
| HyDE-expanded query + vector rerank, equal weighting | 0.88720 | 0.67200 | 0.08060 | 0.66131 |

**Query-rewrite findings:**

- Query expansion produces a modest increase in nDCG@10, MRR, and composite score.
- Query expansion slightly reduces metadata-derived Recall@10.
- HyDE and HyDE plus expansion reduce ranking quality on this corpus.
- The observed expansion advantage is small; it requires paired statistical testing or a manually judged relevance set before a strong superiority claim.

### Selected configuration

```text
Expanded query
→ pgvector vector retrieval
→ BAAI/bge-reranker-base cross-encoder reranking
→ top 10 evidence chunks
```

**Why this configuration:**

- Highest observed composite score: 0.77274.
- Highest observed nDCG@10: 0.94713.
- Highest observed MRR: 0.93583.
- Simpler than hybrid retrieval because it does not depend on the weaker lexical baseline.
- HyDE is disabled because it reduces benchmark performance.

### Historical results

The earlier v1 and v2 results were produced by a file-based, in-memory evaluator using locally loaded embeddings and a lightweight lexical-overlap baseline.

They are retained as historical offline-baseline artifacts, but they are **not directly comparable** with v3 because the evaluator and retrieval implementation changed. The v3 PostgreSQL/pgvector evaluation is the basis for current production retrieval claims.

For full methodology, relevance scoring, historical results, result artifacts, and Tier 2 RAG-quality evaluation plans, see [`docs/evaluation-notes.md`](docs/evaluation-notes.md) and [`docs/decisions.md`](docs/decisions.md) #12.

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
  tests.test_summarise_evaluation

# Run the production-aligned PostgreSQL retrieval grid
uv run python -m src.evaluation.evaluate_retrieval \
  --queries data/evaluation/queries.jsonl \
  --output data/evaluation/evaluation_results_postgres.jsonl \
  --alphas "0.3,0.5,0.7" \
  --rerank-weightings "equal,authority_heavy,page_heavy,section_heavy,source_heavy" \
  --resume

# Summarise the results
uv run python -m src.evaluation.summarise_evaluation \
  --input data/evaluation/evaluation_results_postgres.jsonl \
  --output data/evaluation/evaluation_summary_postgres.json \
  --top-n 10 \
  --decimals 5
```

For complete setup instructions, database checks, query-rewrite evaluation, troubleshooting, and safe regeneration guidance, see [`docs/runbook.md`](docs/runbook.md).

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
| Source-aware filtering | ⏳ Planned |
| Answer generation | ⏳ Planned |
| Tier 2 RAG quality evaluation | ⏳ Planned |
| Streamlit interface | ⏳ Planned |
| Feedback capture and monitoring | ⏳ Planned |

For detailed progress and next steps, see [`docs/project-log.md`](docs/project-log.md).

---

## Key decisions

- **Structural chunking** instead of fixed-size splitting, to preserve document hierarchy and citation context.
- **PostgreSQL + pgvector** as the production retrieval backend.
- **Expanded query + vector retrieval + cross-encoder reranking** as the current selected retrieval configuration.
- **Equal metadata weighting** as the default evaluation setting because it ties for the top vector-rerank score and is simple to justify.
- **HyDE disabled by default** because it reduced retrieval quality in the production-aligned benchmark.
- **Historical file-based v1/v2 evaluations retained** as offline-baseline artifacts, not as final production results.
- **Two-tier evaluation:** fixed-benchmark retrieval evaluation plus future manual RAG answer-quality evaluation.
- **Source hierarchy metadata** retained in chunks to distinguish governing, technical, supporting, and historical material.

For rationale, alternatives, and trade-offs, see [`docs/decisions.md`](docs/decisions.md), especially Decision 12.

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
- Source-aware filtering, answer generation, citation validation, and Tier 2 RAG answer-quality evaluation are not yet implemented.

See [`docs/dataset-notes.md`](docs/dataset-notes.md) and [`docs/evaluation-notes.md`](docs/evaluation-notes.md) for detailed source, evaluation, and responsible-use limitations.

---

## Documentation

- [`docs/project-log.md`](docs/project-log.md) — Working journal and stage-by-stage progress
- [`docs/decisions.md`](docs/decisions.md) — Design choices and trade-offs, including Decision 12
- [`docs/dataset-notes.md`](docs/dataset-notes.md) — Corpus details, source hierarchy, processing, and quality notes
- [`docs/evaluation-notes.md`](docs/evaluation-notes.md) — Retrieval protocol, historical v1/v2 context, authoritative v3 results, and Tier 2 plan
- [`docs/runbook.md`](docs/runbook.md) — Setup, reproduction, evaluation, and troubleshooting

---

## License

MIT License. Public source documents remain subject to their original publishers’ terms.