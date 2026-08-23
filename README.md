# DER RegCheck

> An evidence-first RAG prototype for DER interconnection and market-entry research.

**Project status:** Ingestion, normalisation, chunking, embedding, database, and extended retrieval evaluation (including reranking and composite scoring) implemented. Answer generation, interface, and monitoring planned.

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

The v1 corpus contains six public sources from the California Public Utilities Commission (CPUC) and Southern California Edison (SCE):

| Source | Role | Authority level | Chunk count |
|---|---|---|---:|
| SCE Rule 21 tariff | Primary interconnection requirements | Governing source | 387 |
| SCE Interconnection Handbook | Technical implementation | Primary technical | 562 |
| SCE testing instruction | Equipment certification | Supporting guidance | 72 |
| SCE Rule 21 web guidance | Process guidance | Supporting process | 8 |
| CPUC Rule 21 overview | Regulatory context | Source discovery | 12 |
| SIWG Phase 2 Recommendations | Historical rationale | Historical/draft | 68 |
| **Total** | | | **1,049** |

For full source details, URLs, processing notes, and quality status, see [`docs/dataset-notes.md`](docs/dataset-notes.md).

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
Embedding generation (Nomic 768-dim vectors)
            |
            v
PostgreSQL + pgvector knowledge base (1,049 chunks + embeddings)
            |
            v
Lexical, vector, hybrid, and reranked retrieval evaluation ✅
            |
            v
Future grounded answer generation with citations
            |
            v
Future Streamlit interface, feedback capture, and monitoring
```

**Key design choices:**
- Raw extraction outputs remain immutable and auditable
- Normalisation creates deterministic evidence blocks without altering raw outputs
- Chunking preserves document hierarchy and citation metadata
- Embeddings use `search_document:` prefix for asymmetric retrieval
- Database uses pgvector with IVFFlat index for fast similarity search
- Evaluation includes reranking (cross-encoder) and composite scoring

For implementation details, see [`docs/runbook.md`](docs/runbook.md).

---

## Retrieval evaluation

### Extended evaluation (v2, 2026-08-23)

**Evaluation setup:**
- **100 queries** (LLM-generated, Gemini 3.5-flash-lite)
- **1,049 chunks** (structural chunking over normalised evidence)
- **1,049 embeddings** (Nomic nomic-embed-text-v1.5, 768-dim)
- **8,100 evaluation records** (multiple retrievers × alphas × weightings, including reranking)
- **Metrics:** nDCG@10, MRR, Recall@10, composite score (0.5·nDCG + 0.3·MRR + 0.2·Recall)

**Top configurations by composite score:**

| Rank | Configuration | nDCG@10 | MRR | Recall@10 | Composite |
|---|---|---:|---:|---:|---:|
| 1 | **hybrid_rerank__equal** (selected) | **0.95080** | **0.95361** | **1.00000** | **0.96148** |
| 2 | hybrid_rerank__authority_heavy | 0.95074 | 0.95361 | 1.00000 | 0.96145 |
| 3 | hybrid_rerank__source_heavy | 0.95021 | 0.95361 | 1.00000 | 0.96119 |
| 4 | vector_rerank__equal | 0.94542 | 0.93750 | 0.99000 | 0.95196 |
| 5 | vector_rerank__authority_heavy | 0.94542 | 0.93750 | 0.99000 | 0.95196 |
| 6 | vector_rerank__source_heavy | 0.94412 | 0.93750 | 0.99000 | 0.95131 |

**Non-reranked top configurations (for comparison):**

| Configuration | nDCG@10 | MRR | Recall@10 | Composite |
|---|---:|---:|---:|---:|
| vector__equal | 0.75740 | 0.89293 | 0.33081 | 0.71274 |
| hybrid__equal | 0.70484 | 0.88124 | 0.32452 | 0.68170 |
| bm25__equal | 0.64293 | 0.81559 | 0.30105 | 0.62635 |

**Key findings (v2):**
- Reranking dominates: best reranked nDCG@10 ≈ 0.951 vs best non-reranked ≈ 0.757.
- Recall@10 jumps from ~0.33–0.61 (non-reranked) to 0.95–1.00 (reranked).
- Among reranked configs, weighting has tiny effects (4th–5th decimal); equal weighting has a slight edge on composite.
- Hybrid + rerank slightly edges vector + rerank on composite (0.96148 vs 0.95196).
- Alpha (0.3–0.7) has modest impact relative to reranking; α = 0.5 chosen as default.

**Selected configuration (v2):** Hybrid retrieval with reranking and equal weighting (α = 0.5, RRF k = 1).

For full methodology, metadata matching approach, and future Tier 2 RAG quality evaluation, see [`docs/evaluation-notes.md`](docs/evaluation-notes.md) and [`docs/decisions.md`](docs/decisions.md) #11.

---

## How to run

### Prerequisites

- Python 3.11+
- `uv` for dependency management
- Docker and Docker Compose (for PostgreSQL with pgvector)

### Quick start

```bash
# Clone and setup
cd der-regcheck
uv sync

# Download corpus
uv run python src/ingestion/download_california_rule21_docs.py

# Extract, normalise, chunk
uv run python src/ingestion/extract_raw_content.py
uv run python src/processing/normalise_documents.py
uv run python src/processing/chunk_documents.py

# Generate embeddings
uv run python src/processing/generate_embeddings.py \
  --model nomic-ai/nomic-embed-text-v1.5

# Load database
docker compose up -d db
uv run python src/database/init_db.py
uv run python src/scripts/load_chunks_to_db.py

# Run retrieval evaluation (v2: extended with reranking and multiple alphas)
uv run python -m src.evaluation.generate_synthetic_queries \
  --chunks-dir data/processed/chunks \
  --output-file data/evaluation/queries.jsonl \
  --num-queries 100 \
  --model gemini-3.5-flash-lite
uv run python -m src.evaluation.evaluate_retrieval \
  --queries data/evaluation/queries.jsonl \
  --chunks-dir data/processed/chunks \
  --output data/evaluation/evaluation_results.jsonl \
  --alphas "0.3,0.5,0.7" \
  --rerank-weightings "equal,authority_heavy,page_heavy,section_heavy,source_heavy" \
  --resume
```

For complete setup instructions, troubleshooting, and output regeneration, see [`docs/runbook.md`](docs/runbook.md).

---

## Project structure

```text
der-regcheck/
├── compose.yaml          # Docker Compose runtime
├── config/               # Normalisation and chunking rules
├── data/                 # Processed corpus and evaluation
├── docs/                 # Documentation
├── src/                  # Python source code
├── tests/                # Regression tests
├── pyproject.toml        # Project metadata
├── README.md             # This file
└── uv.lock               # Locked dependencies
```

See [`docs/runbook.md`](docs/runbook.md) for the full directory structure.

---

## Implementation status

| Component | Status |
|---|---|
| Corpus ingestion | ✅ Implemented |
| Raw extraction | ✅ Implemented |
| Evidence normalisation | ✅ Implemented |
| Structural chunking | ✅ Implemented |
| Embedding generation | ✅ Implemented |
| PostgreSQL + pgvector | ✅ Implemented |
| Retrieval evaluation | ✅ Implemented (BM25, vector, hybrid, reranked; multiple alphas and weightings) |
| Answer generation | ⏳ Planned |
| Streamlit interface | ⏳ Planned |
| Monitoring dashboard | ⏳ Planned |
| Source-aware filtering | ⏳ Planned |
| RRF k sweep (course-aligned) | ⏳ Planned |

For detailed progress and next steps, see [`docs/project-log.md`](docs/project-log.md).

---

## Key decisions

- **Structural chunking** over fixed-size splitting to preserve document hierarchy
- **Hybrid + rerank retrieval** selected for best composite score (0.96148) and near-perfect Recall@10
- **Equal weighting** selected for simplicity and marginal edge among near-tied reranked configs
- **Two-tier evaluation:** automated retrieval benchmarking (100 queries, 8,100 results) + manual RAG quality evaluation (planned 5-10 questions)
- **Source hierarchy metadata** embedded in chunks for authority-aware retrieval

For rationale and alternatives considered, see [`docs/decisions.md`](docs/decisions.md).

---

## Limitations

- Only covers California Rule 21 / SCE (not multi-utility or multi-market)
- Cannot guarantee source currency (documents may be updated at source URLs)
- Some PDF extraction artifacts remain in evidence text (layout issues from pypdf)
- Review warnings exist for 2 sources (heading-path limitations in front matter)
- Answer generation not yet implemented
- RRF k sweep and source-aware filtering not yet implemented

See "Limitations and responsible use" in [`docs/dataset-notes.md`](docs/dataset-notes.md) for full details.

---

## Documentation

- [`docs/project-log.md`](docs/project-log.md) — Working journal and stage-by-stage progress
- [`docs/decisions.md`](docs/decisions.md) — Key design choices and trade-offs (including #11: retrieval evaluation v2)
- [`docs/dataset-notes.md`](docs/dataset-notes.md) — Corpus details, source hierarchy, and quality notes
- [`docs/evaluation-notes.md`](docs/evaluation-notes.md) — Retrieval evaluation framework and results (v1 and v2)
- [`docs/runbook.md`](docs/runbook.md) — Setup, reproduction, and troubleshooting

---

## License

MIT License. Public source documents remain subject to their original publishers' terms.