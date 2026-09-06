# Runbook

## Overview

This runbook describes how to reproduce the DER RegCheck environment, run the application with the committed processed data, and optionally re-run the ingestion, evaluation, and answer-generation pipelines.

**Status:** Ingestion, raw extraction, deterministic evidence normalisation, quality reporting, tariff regression tests, structural chunking, embedding generation, database loading, production PostgreSQL/pgvector retrieval evaluation, cached query-rewrite evaluation, evaluator regression tests, summariser regression tests, answer-generation evaluation, the Streamlit interface, and the containerised deployment are implemented. Historical file-based evaluations (v1 and v2) are retained as offline-baseline artifacts. The production-aligned PostgreSQL evaluation completed on 2026-09-05 is authoritative for the deployed retrieval path. The runtime application uses original-query vector retrieval with reranking and the `v3_few_shot_grounded_rag` prompt.

The v1 corpus and all processed artifacts—extracted text, normalised blocks, chunks, and embeddings—are committed to the repository so the system can run without re-downloading source documents. The ingestion pipeline is provided for future corpus refreshes and advanced users; one source may require manual replacement because of intermittent automated-download blocking.

For project progress, implementation status, and planned next work, see [`docs/project-log.md`](project-log.md). For evaluation methodology and full results, including the RAG-impact evaluation, see [`docs/evaluation-notes.md`](evaluation-notes.md). For design rationale and configuration-selection decisions, see [`docs/decisions.md`](decisions.md).

---

## Prerequisites

- Python 3.13 or later.
- `uv` for dependency management: [https://github.com/astral.sh/uv](https://github.com/astral-sh/uv).
- Docker and Docker Compose.
- A local `.env` file containing the database and LLM settings required by the project.
- Sufficient local disk space for the application image, model caches, and PostgreSQL volume.

---

## Environment setup

### Create a virtual environment and install dependencies

For local development or local application execution:

```bash
cd der-regcheck
uv sync
```

This installs dependencies from `pyproject.toml` and `uv.lock`.

### Configure environment variables

Create a local environment file:

```bash
cp .env.example .env
```

Set the project-specific values in `.env`:

```dotenv
# PostgreSQL / pgvector
POSTGRES_DB=der-regcheck
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_PORT=5432
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/der-regcheck

# Google AI
GOOGLE_API_KEY=your_api_key_here
MODEL_ID=gemini-3.5-flash-lite

# Streamlit
STREAMLIT_PORT=8501
```

Do not commit `.env` or API keys.

When the application runs inside Docker Compose, the app container uses the service hostname `db` rather than `localhost`. The Compose configuration supplies the container-network database URL automatically:

```text
postgresql://postgres:postgres@db:5432/der-regcheck
```

### Current pipeline dependencies

The project declares its dependencies in `pyproject.toml`. The main runtime and pipeline dependencies include:

- `requests` for corpus download.
- `beautifulsoup4` for HTML main-content extraction.
- `pypdf` for page-preserving PDF text extraction.
- `pyyaml` for source-specific normalisation configuration.
- `sentence-transformers` for Nomic embedding generation and cross-encoder reranking.
- `psycopg2-binary` for the PostgreSQL driver.
- `streamlit` for the user interface.
- `google-genai` for Gemini API access.
- `pydantic` for structured answer and evaluation data.
- `pandas` for evaluation and monitoring support.

---

## Run with Docker Compose

### Container architecture

The containerised deployment consists of:

```text
Docker Compose
├── app
│   ├── Streamlit interface
│   ├── Retrieval and reranking pipeline
│   ├── Answer generation
│   ├── Feedback and review workflow
│   └── Committed processed data
└── db
    └── pgvector/pgvector:pg16
```

The application image is built from the repository `Dockerfile`. The database uses `pgvector/pgvector:pg16`.

Raw source files in `data/corpus/` are not required for normal application startup. The app uses the committed processed artifacts in `data/processed/`.

### Build the application image

From the repository root:

```bash
make docker-build
```

This is required after changing application code, dependencies, configuration, or the Dockerfile.

### Start the database and application

```bash
cp .env.example .env
# Edit .env and set GOOGLE_API_KEY.

make docker-up
```

This starts:

- PostgreSQL with pgvector.
- The Streamlit application.
- The persistent PostgreSQL volume.

Check service status:

```bash
docker compose ps
```

Follow application and database logs:

```bash
make docker-logs
```

The Streamlit interface is available at:

```text
http://localhost:8501
```

### Initialise the database schema

The database schema must be created before chunks and embeddings are loaded.

Run initialisation inside the application container:

```bash
docker compose exec app python -m src.database.db_init
```

This creates:

- The `chunks` table for chunk text and metadata.
- The `chunk_embeddings` table for 768-dimensional vectors.
- pgvector indexes required by the database schema.
- PostgreSQL full-text retrieval structures.
- The `query_cache` table for configuration-aware answer and evidence snapshots.
- The `answer_feedback` table for helpful/not-helpful feedback events.
- The `manual_scores` table for structured human-review scores.

### Load committed chunks and embeddings

Run the loader inside the application container:

```bash
docker compose exec app python -m src.scripts.load_chunks_to_db \
  --chunks-dir /app/data/processed/chunks \
  --embeddings-file /app/data/processed/embeddings/embeddings.jsonl
```

Expected output:

```text
Loaded 1,049 chunks into database
Loaded 1,049 embeddings into database
```

The loader is safe to run again when the database schema supports replacement or upsert behaviour. If you need a clean reload, stop the stack and remove the database volume only when you intentionally want to delete the existing database state:

```bash
docker compose down -v
docker compose up -d
```

Then repeat schema initialisation and data loading.

### Verify the database

Open a PostgreSQL shell inside the database container:

```bash
docker compose exec db psql \
  -U "${POSTGRES_USER:-postgres}" \
  -d "${POSTGRES_DB:-der-regcheck}"
```

Run:

```sql
SELECT COUNT(*) FROM chunks;
SELECT COUNT(*) FROM chunk_embeddings;
SELECT extname FROM pg_extension WHERE extname = 'vector';
\q
```

Expected counts for the committed corpus are:

```text
chunks: 1049
chunk_embeddings: 1049
```

The `vector` extension should be present.

### Run tests in the application container

Run the full test suite:

```bash
docker compose exec app python -m unittest discover -s tests
```

Run the evaluator and answer-generation regression tests:

```bash
docker compose exec app python -m unittest \
  tests.test_evaluate_retrieval \
  tests.test_summarise_evaluation \
  tests.test_answer_generator
```

### Stop the services

Stop containers without deleting the database volume:

```bash
make docker-down
```

Restart the services:

```bash
make docker-restart
```

Follow logs:

```bash
make docker-logs
```

Remove containers, the PostgreSQL volume, and the local application image:

```bash
make docker-clean
```

Use `docker-clean` carefully. Removing the volume deletes the local PostgreSQL database and any cached answers, feedback, and manual-review scores stored there.

---

## Run locally with PostgreSQL in Docker

This option runs only PostgreSQL in Docker while running the Python application directly on the host.

### Start PostgreSQL

```bash
docker compose up -d db
```

Wait for the database to become healthy:

```bash
docker compose ps
```

The host-side `.env` should use `localhost`:

```dotenv
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/der-regcheck
```

### Initialise the schema

```bash
uv run python -m src.database.db_init
```

### Load chunks and embeddings

```bash
uv run python -m src.scripts.load_chunks_to_db \
  --chunks-dir data/processed/chunks \
  --embeddings-file data/processed/embeddings/embeddings.jsonl
```

### Run the Streamlit application

```bash
uv run streamlit run src/ui/streamlit_app.py
```

Open:

```text
http://localhost:8501
```

### Stop PostgreSQL

```bash
docker compose stop db
```

To remove the PostgreSQL volume as well:

```bash
docker compose down -v
```

---

## Application behaviour

The application provides:

- About, Ask, Evidence, Review, and Monitoring tabs.
- Question input with Tier 2 example questions.
- Answer status badges:
  - Answered.
  - Partial.
  - Needs clarification.
  - Insufficient evidence.
  - High-stakes boundary.
- Main answers with inline citation labels.
- Expandable evidence cards with source class, page or section locators, and retrieval rank.
- An explicit research-support disclaimer.
- Helpful/not-helpful feedback with optional comments.
- Manual review for Tier 2 and custom questions.
- Five 1–5 review dimensions:
  - Groundedness.
  - Relevance.
  - Completeness.
  - Citation quality.
  - Appropriate uncertainty.
- Monitoring charts with safe empty states.

The runtime retrieval path is:

```text
Original user query
→ pgvector vector retrieval
→ BAAI/bge-reranker-base cross-encoder reranking
→ top 10 evidence chunks
→ v3_few_shot_grounded_rag answer generation
→ deterministic citation validation
```

Query expansion is disabled at runtime because its observed quality improvement was small relative to its latency cost. The query-expansion implementation remains available for future evaluation.

---

## Optional corpus refresh

The v1 corpus and processed artifacts are already committed, so downloading the source documents is not required for normal application startup.

Use the ingestion workflow only when intentionally refreshing the corpus or reproducing the complete processing pipeline from source documents.

### Download the corpus

```bash
uv run python src/ingestion/download_california_rule21_docs.py
```

The downloader:

- Downloads configured sources to `data/corpus/`.
- Validates expected PDF responses using the `%PDF-` signature.
- Retries PDFs that fail validation using a simplified request.
- Records content hashes, validation status, review status, and eligibility metadata in `data/corpus/corpus_metadata.json`.

Raw source files in `data/corpus/` are ignored by Git.

### Handle blocked or unreliable downloads

If a source URL returns HTML, SharePoint content, an authentication page, or another invalid response:

1. Download the required file manually through a browser or authenticated portal.
2. Save it to the source's configured local path.
3. Mark it as an approved manual replacement.

For example:

```bash
uv run python src/ingestion/download_california_rule21_docs.py \
  --mark-manual-replacement sce_interconnection_handbook_pdf \
  --reviewer your-name
```

This should validate the local replacement, update its content hash, record the manual-replacement method, record reviewer approval, and enable extraction and default retrieval according to corpus metadata.

### Inspect corpus metadata

```bash
cat data/corpus/corpus_metadata.json
```

Review source-level fields including:

- `content_hash`.
- `last_checked`.
- `automated_validation`.
- `manual_review`.
- `eligible_for_extraction`.
- `eligible_for_default_retrieval`.
- `acquisition_method`.

---

## Extract raw content

### Run the extractor

```bash
uv run python src/ingestion/extract_raw_content.py
```

The extractor:

- Reads `data/corpus/corpus_metadata.json`.
- Processes only sources with `eligible_for_extraction = true`.
- Preserves raw PDF text by physical PDF page using `pypdf`.
- Extracts HTML main content with heading-path preservation using BeautifulSoup.
- Writes raw extraction outputs to `data/processed/extracted/<document_id>.json`.
- Writes an extraction manifest to `data/processed/extraction_manifest.json`.
- Records `schema_version` and `extraction_method` metadata in raw outputs.

Raw extraction does not perform source-authority assignment, LLM enrichment, normalisation, chunking, embedding, retrieval, or answer generation.

### Inspect extraction outputs

```bash
cat data/processed/extraction_manifest.json
```

Example PDF output:

```bash
sed -n '1,180p' \
  data/processed/extracted/sce_interconnection_handbook_pdf.json
```

Example HTML output:

```bash
sed -n '1,180p' \
  data/processed/extracted/sce_interconnection_web.json
```

---

## Normalise evidence blocks

### Purpose

Raw extraction outputs remain preserved as auditable source artifacts. Normalisation creates separate deterministic evidence blocks for later chunking and retrieval.

The normalisation stage:

- Does not alter raw extraction files.
- Does not download sources.
- Does not call an LLM.
- Does not create embedding vectors or retrieval indexes.
- Preserves PDF physical-page locators and HTML heading-path locators.
- Applies source-specific rules from `config/normalisation.yaml`.
- Uses dedicated logic for the SCE Rule 21 tariff.

### Run regression tests

```bash
uv run python -m unittest \
  tests.test_normalise_documents \
  tests.test_quality_check_normalised
```

Current tariff fixtures cover physical PDF pages:

- Page 50: nested tariff hierarchy.
- Page 100: Roman-numeral list items and parent-path restoration.
- Page 150: frequency provision and tariff sheet metadata.
- Page 233: Appendix B hierarchy reset.

### Generate normalised outputs

```bash
rm -rf data/processed/normalised/*

uv run python -m src.processing.normalise_documents \
  --input-manifest data/processed/extraction_manifest.json \
  --config config/normalisation.yaml \
  --output-dir data/processed/normalised
```

This writes:

```text
data/processed/normalised/<document_id>.json
data/processed/normalised/normalisation_manifest.json
```

### Generate quality reports

```bash
uv run python -m src.processing.quality_check_normalised \
  --normalised-dir data/processed/normalised \
  --output-json data/processed/normalised/quality_report.json \
  --output-md data/processed/normalised/quality_report.md
```

Review the Markdown report:

```bash
sed -n '1,280p' data/processed/normalised/quality_report.md
```

### Inspect warning blocks

```bash
uv run python - <<'PY'
import json
from pathlib import Path

names = [
    "sce_interconnection_handbook_pdf",
    "sce_testing_certification_instruction_pdf",
    "siwg_phase2_recommendations_pdf",
]

for name in names:
    path = Path(f"data/processed/normalised/{name}.json")
    document = json.loads(path.read_text(encoding="utf-8"))

    flagged = [
        block
        for block in document["blocks"]
        if "no_detected_heading_path" in block["normalisation_flags"]
    ]

    print("\n" + "=" * 100)
    print(name)
    print(f"Flagged blocks: {len(flagged)}")

    for block in flagged:
        print("\nblock_id:", block["block_id"])
        print("page:", block["citation"].get("pdf_page_start"))
        print("text:", block["text"][:700])
PY
```

A review warning is not necessarily a pipeline failure. Supporting-source or historical front matter may remain review-flagged if physical PDF provenance is retained and the material is not used as default current-requirement evidence.

---

## Generate searchable chunks

### Purpose

Chunking transforms normalised evidence blocks into searchable units for retrieval and embedding.

The chunking stage:

- Preserves `evidence_text` unchanged from normalised blocks.
- Prepends heading context to `embedding_text`.
- Merges citation metadata, including PDF pages, tariff sheets, and section IDs.
- Links neighbour chunks for navigation.
- Flags oversized blocks without splitting evidence mid-block.

### Run chunking

```bash
rm -rf data/processed/chunks/*

uv run python -m src.processing.chunk_documents \
  --normalised-dir data/processed/normalised \
  --config config/chunking.yaml \
  --output-dir data/processed/chunks
```

This writes:

```text
data/processed/chunks/<document_id>.json
data/processed/chunks/chunking_manifest.json
```

### Generate chunk quality reports

```bash
uv run python -m src.processing.quality_check_chunks \
  --chunks-dir data/processed/chunks \
  --output-json data/processed/chunks/quality_report.json \
  --output-md data/processed/chunks/quality_report.md
```

Review the Markdown report:

```bash
cat data/processed/chunks/quality_report.md
```

### Inspect chunk outputs

```bash
uv run python - <<'PY'
import json
from pathlib import Path

document = json.loads(
    Path("data/processed/chunks/sce_rule21_tariff_pdf.json").read_text(
        encoding="utf-8"
    )
)

chunks = document["chunks"]

print(f"Total chunks: {len(chunks)}")
print(f"Oversized chunks: {sum(1 for chunk in chunks if chunk['oversized'])}")

if chunks:
    chunk = chunks
    print("\n" + "=" * 100)
    print(f"Chunk {chunk['chunk_id']}")
    print("Block types:", chunk["block_types"])
    print("Evidence text:", chunk["evidence_text"][:300])
    print("Embedding text:", chunk["embedding_text"][:300])
    print("Citation:", chunk["citation"])
    print("Source policy:", chunk["source_policy"])
    print("Neighbours:", chunk["neighbour_chunk_ids"])
PY
```

Expected chunking behaviour:

- 1,049 total chunks across six sources.
- Five oversized chunks, all handbook table-of-contents blocks of approximately 1,033–1,561 tokens.
- `evidence_text` remains unchanged from normalised blocks.
- `embedding_text` includes heading context.
- Neighbour links enable navigation.

---

## Generate embeddings

### Purpose

Embeddings enable vector similarity search for retrieval.

The embedding stage:

- Uses Nomic `nomic-embed-text-v1.5`.
- Applies the `search_document:` prefix to chunk `embedding_text`.
- Produces 768-dimensional vectors.
- Preserves chunk metadata for traceability.

### Run embedding generation

Use the embedding module implemented in the repository:

```bash
rm -rf data/processed/embeddings/*

uv run python -m src.processing.embed_chunks \
  --chunks-dir data/processed/chunks \
  --output-dir data/processed/embeddings \
  --model nomic-ai/nomic-embed-text-v1.5
```

This writes:

```text
data/processed/embeddings/embeddings.jsonl
data/processed/embeddings/embedding_manifest.json
```

### Inspect embedding outputs

```bash
uv run python - <<'PY'
import json

with open(
    "data/processed/embeddings/embeddings.jsonl",
    "r",
    encoding="utf-8",
) as file:
    for index, line in enumerate(file):
        if index >= 5:
            break

        embedding = json.loads(line)
        print(f"\nChunk {embedding['chunk_id']}")
        print(f"Vector dimension: {len(embedding['vector'])}")
        print(f"Model: {embedding['embedding_model']}")
        print(f"Prefix: {embedding['embedding_prefix']}")
PY
```

Expected embedding outputs:

- 1,049 embeddings, one per chunk.
- 768-dimensional vectors.
- `search_document:` prefix applied to document embedding input.

---

## Load the database

Use this section when loading a newly generated or refreshed set of processed artifacts.

### Start PostgreSQL

```bash
docker compose up -d db
```

Wait for PostgreSQL to become healthy:

```bash
docker compose ps
```

### Create the knowledge-base schema

```bash
uv run python -m src.database.db_init
```

### Load chunks and embeddings

```bash
uv run python -m src.scripts.load_chunks_to_db \
  --chunks-dir data/processed/chunks \
  --embeddings-file data/processed/embeddings/embeddings.jsonl
```

Expected output:

```text
Loaded 1,049 chunks into database
Loaded 1,049 embeddings into database
```

### Verify database contents

```bash
uv run python - <<'PY'
import os
import psycopg2

database_url = os.environ["DATABASE_URL"]

conn = psycopg2.connect(database_url)
cur = conn.cursor()

cur.execute("SELECT COUNT(*) FROM chunks")
print(f"Chunks: {cur.fetchone()}")

cur.execute("SELECT COUNT(*) FROM chunk_embeddings")
print(f"Embeddings: {cur.fetchone()}")

cur.close()
conn.close()
PY
```

Do not use an all-zero dummy embedding to validate relevance or ranking quality. Use the retrieval command below so the project generates a real query embedding.

---

## Generate evaluation queries

### Generate the fixed benchmark

Run this only when intentionally creating a new benchmark. Do not regenerate queries when reproducing the established production-aligned result.

```bash
uv run python -m src.evaluation.generate_synthetic_queries \
  --chunks-dir data/processed/chunks \
  --output-file data/evaluation/queries.jsonl \
  --num-queries 100 \
  --model gemini-3.5-flash-lite
```

Expected output:

- 100 LLM-generated queries.
- Gold chunk IDs and metadata.
- Query source and generation metadata.

The current production-aligned benchmark is `data/evaluation/queries.jsonl`. Treat it as fixed for direct configuration comparisons.

---

## Run production retrieval

### Test the deployed retrieval path

The exact command-line interface may vary with the current retrieval module. The runtime application is the canonical integration path:

```bash
uv run streamlit run src/ui/streamlit_app.py
```

The deployed retrieval path can use:

- PostgreSQL full-text lexical retrieval.
- pgvector vector retrieval.
- PostgreSQL-backed hybrid retrieval.
- Runtime query embedding using the Nomic `search_query:` prefix.
- Cross-encoder reranking using `BAAI/bge-reranker-base`.

The runtime application uses:

```text
Original user query
→ pgvector vector retrieval
→ BAAI/bge-reranker-base cross-encoder reranking
→ top 10 evidence chunks
```

Inspect returned source metadata and citation locators before treating any result as evidence for a requirement.

---

## Run retrieval evaluation

### Evaluation conditions

The authoritative Tier 1 evaluation uses:

| Component | Configuration |
|---|---|
| Query benchmark | 100 fixed synthetic queries |
| Corpus | 1,049 indexed chunks |
| Retrieval backend | PostgreSQL full-text search and pgvector |
| Retrieval variants | Lexical, vector, hybrid, hybrid rerank, vector rerank |
| Hybrid alpha values | 0.3, 0.5, 0.7 |
| Metadata weightings | Equal, source-heavy, section-heavy, page-heavy, authority-heavy |
| Embedding model | `nomic-ai/nomic-embed-text-v1.5` |
| Reranker | `BAAI/bge-reranker-base` |
| Reranker candidates | Top 50 |
| Reranked output | Top 10 |
| Metrics | nDCG@10, MRR, Recall@10, composite score |
| Checkpointing | JSONL checkpointing and resume support |

The retrieval grid contains:

```text
100 queries
× 3 alpha values
× 5 retrieval variants
× 5 metadata weighting schemes
= 7,500 evaluation records
```

### Run the PostgreSQL retrieval grid

Ensure PostgreSQL is running and contains the current 1,049 chunks and embeddings before starting.

Use the evaluator's current command-line help to confirm supported options:

```bash
uv run python -m src.evaluation.evaluate_retrieval --help
```

The intended evaluation inputs and outputs are:

```text
Input:
data/evaluation/queries.jsonl

Output:
data/evaluation/evaluation_results_postgres.jsonl
```

When supported by the current evaluator interface, use:

```bash
uv run python -m src.evaluation.evaluate_retrieval \
  --queries data/evaluation/queries.jsonl \
  --output data/evaluation/evaluation_results_postgres.jsonl \
  --alphas "0.3,0.5,0.7" \
  --rerank-weightings "equal,authority_heavy,page_heavy,section_heavy,source_heavy" \
  --resume
```

If the evaluator exposes an explicit database URL option, use:

```bash
uv run python -m src.evaluation.evaluate_retrieval \
  --queries data/evaluation/queries.jsonl \
  --output data/evaluation/evaluation_results_postgres.jsonl \
  --database-url "$DATABASE_URL" \
  --alphas "0.3,0.5,0.7" \
  --rerank-weightings "equal,authority_heavy,page_heavy,section_heavy,source_heavy" \
  --resume
```

Use `--resume` only when continuing the same benchmark, corpus, evaluator implementation, and configuration grid. Use `--overwrite` only when deliberately replacing an existing result artifact.

### Summarise PostgreSQL retrieval results

Confirm supported options first:

```bash
uv run python -m src.evaluation.summarise_evaluation --help
```

The intended summary output is:

```text
data/evaluation/evaluation_summary_postgres.json
```

When supported by the current summariser interface, use:

```bash
uv run python -m src.evaluation.summarise_evaluation \
  --input data/evaluation/evaluation_results_postgres.jsonl \
  --output data/evaluation/evaluation_summary_postgres.json \
  --top-n 10 \
  --decimals 5
```

The summariser must:

- Group records by configuration and alpha.
- Count unique query IDs correctly.
- Calculate variability across queries.
- Calculate the composite score:

```text
0.5 × nDCG@10 + 0.3 × MRR + 0.2 × Recall@10
```

- Rank configurations by composite score.

### Expected retrieval result

For the documented v3 retrieval highlights, metric interpretations, and limitation caveats, refer to [`docs/evaluation-notes.md`](evaluation-notes.md).

---

## Run cached query-rewrite evaluation

### Evaluation conditions

The cached query-rewrite evaluation uses:

- 100 fixed benchmark queries.
- Four cached rewrite techniques:
  - `original`.
  - `expanded`.
  - `hyde`.
  - `hyde_expanded`.
- Four retrieval variants.
- Five metadata weighting schemes.

The completed grid contains:

```text
100 queries
× 4 rewrite techniques
× 4 retrieval variants
× 5 metadata weighting schemes
= 8,000 query-rewrite evaluation records
```

### Use the committed rewrite artifact

Do not regenerate rewrites when reproducing the established evaluation.

The committed artifact is:

```text
data/evaluation/query_rewrites.jsonl
```

It records the original query ID, rewrite technique, generated text, timestamp, and model metadata.

### Refresh cached rewrites

Only regenerate rewrites when intentionally revising the rewrite-generation method or benchmark. Inspect the current command interface first:

```bash
uv run python -m src.evaluation.generate_query_rewrites --help
```

Keep the original query IDs stable if the goal is a comparable evaluation.

### Run the PostgreSQL rewrite evaluation

Use the implemented query-rewrite evaluation entry point and confirm its options before running:

```bash
uv run python -m src.evaluation.evaluate_retrieval --help
```

The intended inputs and outputs are:

```text
Input queries:
data/evaluation/queries.jsonl

Cached rewrites:
data/evaluation/query_rewrites.jsonl

Output results:
data/evaluation/query_rewrite_results_postgres.jsonl

Output summary:
data/evaluation/query_rewrite_summary_postgres.json
```

The evaluation must use the same PostgreSQL corpus, metric implementation, weighting schemes, and reranking configuration as the main production-aligned retrieval evaluation.

### Expected rewrite result

For rewrite highlights, metric breakdowns, and interpretations of query expansion, refer to [`docs/evaluation-notes.md`](evaluation-notes.md).

---

## Answer-generation evaluations

Two complementary answer-evaluation studies are documented. For detailed protocol, results, and interpretation, see [`docs/evaluation-notes.md`](evaluation-notes.md).

### Prompt-regression evaluation (24 questions, 3 prompts)

The prompt-regression evaluation uses:

- 24 fixed questions across six categories:
  - `direct_factual`.
  - `multi_chunk_synthesis`.
  - `ambiguous_needs_clarification`.
  - `out_of_corpus`.
  - `high_stakes_boundary`.
  - `historical_source_handling`.
- Three prompt configurations:
  - `v1_direct_rag`.
  - `v2_structured_grounded_rag`.
  - `v3_few_shot_grounded_rag`.
- Deterministic citation validation for every generated answer.
- An LLM judge scoring five dimensions:
  - Groundedness.
  - Relevance.
  - Completeness.
  - Citation quality.
  - Appropriate uncertainty.

The composite score is:

```text
0.30 × Groundedness
+ 0.20 × Relevance
+ 0.20 × Completeness
+ 0.20 × Citation quality
+ 0.10 × Appropriate uncertainty
```

The evaluation design contains:

```text
24 unique questions
× 3 prompt configurations
= 72 intended unique answer evaluations
```

Generated JSONL artifacts may contain repeated or checkpointed records, so raw record counts may exceed the intended number of unique question/configuration pairs.

### RAG-impact evaluation (10 questions, 4 conditions)

The RAG-impact evaluation uses:

- 10 Tier 2 realistic open-ended questions from `data/evaluation/tier2_questions.yaml`.
- Four answer conditions per question:
  - Naive model-only (no evidence, general-knowledge prompt).
  - No-evidence v3 prompt (`v3_few_shot_grounded_rag` without retrieved evidence).
  - Zero-shot RAG (`v1_direct_rag` with shared top-10 evidence).
  - Full v3 RAG (`v3_few_shot_grounded_rag` with shared top-10 evidence).
- Shared top-10 evidence pack for the two evidence-backed conditions.
- Blinded pairwise LLM judging with the same five dimensions.
- Generation metrics, citation-label validation, and answer-status tracking.

---

## Run prompt-regression evaluation

Inspect the current evaluator interface first:

```bash
uv run python -m src.evaluation.evaluate_llm_answers --help
```

The intended artifacts are:

```text
data/evaluation/llm_answers.jsonl
data/evaluation/llm_judge_scores.jsonl
data/evaluation/llm_evaluation_summary.json
data/evaluation/llm_evaluation_report.md
```

When supported by the current evaluator interface, generate answers with:

```bash
uv run python -m src.evaluation.evaluate_llm_answers \
  --mode generate \
  --questions data/evaluation/llm_evaluation_questions.yaml \
  --output data/evaluation/llm_answers.jsonl \
  --prompt-versions "v1_direct_rag,v2_structured_grounded_rag,v3_few_shot_grounded_rag" \
  --overwrite
```

### Judge generated answers

```bash
uv run python -m src.evaluation.evaluate_llm_answers \
  --mode judge \
  --answers data/evaluation/llm_answers.jsonl \
  --judge-output data/evaluation/llm_judge_scores.jsonl
```

### Summarise answer-generation results

```bash
uv run python -m src.evaluation.summarise_llm_evaluation \
  --answers data/evaluation/llm_answers.jsonl \
  --judge-scores data/evaluation/llm_judge_scores.jsonl \
  --output data/evaluation/llm_evaluation_summary.json \
  --report data/evaluation/llm_evaluation_report.md
```

### Expected answer-generation result

For prompt-version comparisons, the judge rubric, and interpretation of the selected prompt configuration, refer to [`docs/evaluation-notes.md`](evaluation-notes.md).

---

## Run RAG-impact evaluation

### Purpose

The RAG-impact evaluation estimates the contribution of retrieval and evidence grounding to answer quality on realistic DER research questions. It is not a business-impact or user-satisfaction study.

### Evaluation conditions

The impact evaluation uses:

- 10 Tier 2 questions from `data/evaluation/tier2_questions.yaml`.
- Four answer conditions per question:
  - Naive model-only (no evidence, general-knowledge prompt).
  - No-evidence v3 prompt (`v3_few_shot_grounded_rag` without retrieved evidence).
  - Zero-shot RAG (`v1_direct_rag` with shared top-10 evidence).
  - Full v3 RAG (`v3_few_shot_grounded_rag` with shared top-10 evidence).
- Blinded pairwise LLM judging for five comparison types per question.
- Generation metrics, citation-label validation, and answer-status distributions.

### Run impact answer generation

Inspect the current evaluator interface:

```bash
uv run python -m src.evaluation.generate_impact_answers --help
```

The intended artifacts are:

```text
data/evaluation/impact_answers.jsonl
data/evaluation/impact_judge_scores.jsonl
data/evaluation/impact_summary.json
data/evaluation/impact_report.md
```

Generate answers:

```bash
uv run python -m src.evaluation.generate_impact_answers \
  --output data/evaluation/impact_answers.jsonl \
  --overwrite
```

Resume an interrupted generation run:

```bash
uv run python -m src.evaluation.generate_impact_answers \
  --output data/evaluation/impact_answers.jsonl \
  --resume
```

### Judge impact answers

```bash
uv run python -m src.evaluation.judge_impact_answers \
  --answers data/evaluation/impact_answers.jsonl \
  --judge-output data/evaluation/impact_judge_scores.jsonl \
  --overwrite
```

Run only the three core retrieval-impact comparisons:

```bash
uv run python -m src.evaluation.judge_impact_answers \
  --answers data/evaluation/impact_answers.jsonl \
  --judge-output data/evaluation/impact_judge_scores.jsonl \
  --comparisons naive_no_evidence:zero_shot_rag,zero_shot_rag:full_v3_rag,naive_no_evidence:full_v3_rag \
  --overwrite
```

### Summarise impact results

```bash
uv run python -m src.evaluation.summarise_impact_evaluation \
  --answers data/evaluation/impact_answers.jsonl \
  --judge-scores data/evaluation/impact_judge_scores.jsonl \
  --output data/evaluation/impact_summary.json \
  --report data/evaluation/impact_report.md
```

### Expected impact result

For detailed findings, pairwise preferences, pooled judge scores, and interpretation, see [`docs/evaluation-notes.md`](evaluation-notes.md).

---

## Run regression tests

Run the full test suite:

```bash
make test
```

Equivalent direct command:

```bash
uv run python -m unittest discover -s tests
```

Run evaluator and answer-generation regression tests:

```bash
uv run python -m unittest \
  tests.test_evaluate_retrieval \
  tests.test_summarise_evaluation \
  tests.test_answer_generator
```

Run normalisation and quality tests:

```bash
uv run python -m unittest \
  tests.test_normalise_documents \
  tests.test_quality_check_normalised \
  tests.test_quality_check_chunks
```

Regression tests cover pipeline behaviour, evaluator and summariser behaviour, unique-query counting, variability calculations, composite-score ranking, and answer-generation citation validation.

---

## Historical file-based evaluation

Historical v1 and v2 evaluation artifacts use a separate file-based, in-memory evaluator.

They remain useful for development history and offline experimentation, but they are not the authoritative production result and must not be compared numerically directly with the PostgreSQL-aligned v3 result.

Historical artifacts include:

```text
data/evaluation/evaluation_results.jsonl
data/evaluation/evaluation_summary.json
data/evaluation/query_rewrite_results.jsonl
```

For current production conclusions, use:

```text
data/evaluation/evaluation_results_postgres.jsonl
data/evaluation/evaluation_summary_postgres.json
data/evaluation/query_rewrite_results_postgres.jsonl
data/evaluation/query_rewrite_summary_postgres.json
data/evaluation/llm_answers.jsonl
data/evaluation/llm_judge_scores.jsonl
data/evaluation/llm_evaluation_summary.json
data/evaluation/llm_evaluation_report.md
```

---

## Regenerate pipeline outputs

### Full pipeline regeneration

A corpus refresh changes the evidence, chunks, embeddings, and database state. If the fixed query set remains valid, rerun the PostgreSQL retrieval and query-rewrite evaluations after loading the refreshed corpus.

The following workflow intentionally regenerates derived artifacts:

```bash
# 1. Refresh source downloads.
uv run python src/ingestion/download_california_rule21_docs.py

# 2. Re-extract raw content.
uv run python src/ingestion/extract_raw_content.py

# 3. Re-run normalisation.
rm -rf data/processed/normalised/*
uv run python -m src.processing.normalise_documents \
  --input-manifest data/processed/extraction_manifest.json \
  --config config/normalisation.yaml \
  --output-dir data/processed/normalised

# 4. Re-run normalisation quality checks.
uv run python -m src.processing.quality_check_normalised \
  --normalised-dir data/processed/normalised \
  --output-json data/processed/normalised/quality_report.json \
  --output-md data/processed/normalised/quality_report.md

# 5. Re-run chunking.
rm -rf data/processed/chunks/*
uv run python -m src.processing.chunk_documents \
  --normalised-dir data/processed/normalised \
  --config config/chunking.yaml \
  --output-dir data/processed/chunks

# 6. Re-run chunk quality checks.
uv run python -m src.processing.quality_check_chunks \
  --chunks-dir data/processed/chunks \
  --output-json data/processed/chunks/quality_report.json \
  --output-md data/processed/chunks/quality_report.md

# 7. Re-run embeddings.
rm -rf data/processed/embeddings/*
uv run python -m src.processing.embed_chunks \
  --chunks-dir data/processed/chunks \
  --output-dir data/processed/embeddings \
  --model nomic-ai/nomic-embed-text-v1.5

# 8. Recreate the local database only if a clean reload is required.
docker compose down -v
docker compose up -d db

# 9. Initialise the database schema.
uv run python -m src.database.db_init

# 10. Load refreshed chunks and embeddings.
uv run python -m src.scripts.load_chunks_to_db \
  --chunks-dir data/processed/chunks \
  --embeddings-file data/processed/embeddings/embeddings.jsonl

# 11. Run regression tests.
make test

# 12. Re-run the PostgreSQL retrieval evaluation after confirming
# the current evaluator command-line options.
uv run python -m src.evaluation.evaluate_retrieval --help

# 13. Summarise the refreshed retrieval evaluation after confirming
# the current summariser command-line options.
uv run python -m src.evaluation.summarise_evaluation --help
```

Do not delete `data/evaluation/queries.jsonl` or `data/evaluation/query_rewrites.jsonl` during a routine rerun if the goal is comparable evaluation against the established benchmark.

If the query set, rewrite set, corpus, embedding model, chunking configuration, evaluator logic, database retrieval logic, or answer-generation prompt changes, record a new dated evaluation condition rather than silently replacing the established result.

A source refresh that changes source content, normalised evidence, chunks, or embeddings requires:

1. Re-extraction.
2. Normalisation.
3. Chunking.
4. Embedding generation.
5. Database reload.
6. Regression tests.
7. A new dated retrieval evaluation before the previous evaluation is treated as applicable to the refreshed corpus.

---

## Run the application directly

### Run the Streamlit app

```bash
uv run streamlit run src/ui/streamlit_app.py
```

The app provides:

- Five connected tabs: About, Ask, Evidence, Review, and Monitoring.
- Question input with Tier 2 example questions.
- Answer status badges.
- Main answers with inline citation labels.
- Expandable evidence cards with source class, page or section locators, and retrieval rank.
- An explicit disclaimer banner.
- Feedback widgets.
- Manual review with five 1–5 scoring dimensions.
- Monitoring charts with safe empty states.

The app uses:

- The `v3_few_shot_grounded_rag` prompt configuration.
- The original user query.
- PostgreSQL/pgvector vector retrieval.
- Cross-encoder reranking.
- Deterministic citation validation.
- PostgreSQL-backed answer, feedback, and manual-review storage.

### Run the demonstration scripts

Run the RAG demonstration:

```bash
make demo-rag
```

Run the retrieval demonstration:

```bash
make demo-retrieval
```

Inspect the scripts' current options:

```bash
uv run python -m src.scripts.demo_rag --help
uv run python -m src.scripts.demo_retrieval --help
```

---

## Data distribution and reproducibility

The repository separates raw source acquisition from processed application data.

### Raw source files

Raw downloads and manual replacements are stored locally in:

```text
data/corpus/
```

This directory is ignored by Git.

The corpus metadata file records:

- Source IDs.
- URLs.
- Content hashes.
- Last-checked timestamps.
- Automated validation status.
- Manual review status.
- Extraction eligibility.
- Default retrieval eligibility.
- Acquisition method.

### Committed processed artifacts

The following directories are intentionally committed:

```text
data/processed/extracted/
data/processed/normalised/
data/processed/chunks/
data/processed/embeddings/
```

These artifacts are sufficient to:

- Initialise the database.
- Load the searchable chunks and embeddings.
- Run retrieval.
- Run the Streamlit application.
- Reproduce the documented evaluation workflow.

### Copyright and source distribution

The source documents remain the property of their respective publishers. The repository distributes processed, machine-readable derivatives for research and educational reproducibility without distributing the original PDF and HTML source files.

When source documents are refreshed, content hashes and downstream artifacts must be updated consistently.

---

## Troubleshooting

### Docker services do not start

Check Docker status:

```bash
docker compose ps
```

View logs:

```bash
docker compose logs db
docker compose logs app
```

Rebuild the application image:

```bash
make docker-build
```

Restart the services:

```bash
make docker-restart
```

If the database volume is corrupted or you intentionally need a clean database:

```bash
docker compose down -v
docker compose up -d
```

Then repeat schema initialisation and data loading.

### Database connection fails

- Confirm PostgreSQL is running:

```bash
docker compose ps
```

- Confirm the host-side `DATABASE_URL` uses `localhost`.
- Confirm the app-container `DATABASE_URL` uses the Compose service name `db`.
- Confirm the configured database name, user, password, and port match `.env`.
- Confirm the `vector` extension is installed.
- Confirm the schema has been created with `src.database.db_init`.
- Confirm the application container can resolve the `db` hostname.

### The application container cannot reach PostgreSQL

Inside the app container, the database host must be `db`, not `localhost`.

Check the environment visible to the container:

```bash
docker compose exec app env | grep -E 'DATABASE_URL|POSTGRES_'
```

The internal URL should resemble:

```text
postgresql://postgres:postgres@db:5432/der-regcheck
```

### Download fails for a source

- Check the error printed by the downloader.
- Inspect the source entry in `data/corpus/corpus_metadata.json`.
- Open the source URL in a browser to determine whether it redirects, requires authentication, or serves unexpected content.
- For failed PDF validation, allow the simplified-request fallback to run.
- If the source remains blocked, manually download it and use `--mark-manual-replacement`.

### Raw extraction fails

- Confirm the local file exists at its configured `local_path`.
- Confirm `eligible_for_extraction = true` in corpus metadata.
- For PDFs, confirm the source passed `%PDF-` signature validation.
- Inspect the `failures` array in `data/processed/extraction_manifest.json`.

### Normalisation fails

- Confirm raw extraction completed successfully.
- Confirm the source JSON is listed as successful in `data/processed/extraction_manifest.json`.
- Check `config/normalisation.yaml` for invalid YAML or malformed regular expressions.
- Run the normalisation unit tests before rerunning the pipeline.
- Inspect `data/processed/normalised/normalisation_manifest.json` for failures.

### Quality reports contain review warnings

- Inspect warning blocks using the warning-block command in the normalisation section.
- Determine whether the block is:
  - Cover, contents, disclaimer, page-header, or document-control material.
  - Substantive text requiring a source-specific heading rule.
  - Accepted supporting or historical context with page-level provenance.
- Do not add broad generic heuristics solely to eliminate warnings.
- Record accepted limitations in `docs/decisions.md`, `docs/dataset-notes.md`, and the project log.

### Chunking produces oversized chunks

- Check `data/processed/chunks/quality_report.md`.
- Verify whether the chunks are accepted exceptions, such as handbook table-of-contents blocks.
- If substantive content is oversized, consider adjusting `config/chunking.yaml`.
- Do not split citation-grade evidence mid-block without recording the change and its implications.

### Embedding generation fails

- Confirm `sentence-transformers` is installed.
- Verify internet connectivity for model download or use a cached model.
- Check that `data/processed/chunks/` exists and contains valid chunk JSON files.
- Confirm the model is `nomic-ai/nomic-embed-text-v1.5`.
- Check available memory, particularly when running inside Docker.

### PostgreSQL loading fails

- Confirm the database schema exists.
- Confirm `data/processed/chunks/` contains chunk files.
- Confirm `data/processed/embeddings/embeddings.jsonl` exists.
- Confirm the number of embeddings matches the number of chunks.
- Confirm embedding vectors have dimension 768.
- Confirm `DATABASE_URL` points to the intended database.
- Review the loader error before rerunning it.

### Retrieval evaluation fails or resumes unexpectedly

- Confirm PostgreSQL contains the intended chunks and embeddings.
- Confirm `DATABASE_URL` is available to the evaluator.
- Inspect the existing JSONL output before choosing `--resume`, `--overwrite`, or a new dated output file.
- Use `--resume` only when continuing the same benchmark and configuration.
- Use `--overwrite` only when deliberately replacing an incomplete or invalid artifact.
- Run evaluator regression tests after changing evaluation logic.
- Confirm the database and evaluator use the same corpus version.

### Retrieval evaluation produces unexpected metrics

- Confirm `data/evaluation/queries.jsonl` contains the intended fixed benchmark.
- Confirm the database contains chunks and embeddings derived from the intended corpus version.
- Check metadata matching logic in `src/evaluation/evaluate_retrieval.py`.
- Confirm chunk metadata includes fields such as:
  - `source_id`.
  - `section_ids`.
  - `block_types`.
  - Citation pages.
  - Authority-tier metadata.
- Confirm the summariser groups by alpha and counts unique query IDs correctly.
- Distinguish historical file-based v1/v2 artifacts from authoritative PostgreSQL v3 artifacts.
- Interpret Recall@10 as metadata-defined chunk coverage, not end-user answer success.
- Consult `docs/evaluation-notes.md` and Decision 12 in `docs/decisions.md`.

### Answer-generation evaluation produces unexpected results

- Confirm `data/evaluation/llm_evaluation_questions.yaml` contains the intended 24 fixed questions.
- Confirm the retrieval path returns evidence for each question.
- Check deterministic citation validation in `src/generation/citation_validator.py`.
- Confirm the LLM judge scores all five dimensions.
- Distinguish the fixed prompt-regression benchmark from future manual RAG-quality assessment.
- Consult `docs/evaluation-notes.md` and Decision 14 in `docs/decisions.md`.

### Streamlit import errors

- Run Streamlit from the repository root.
- Confirm the project environment is active or use `uv run`.
- Confirm `src/` is available to the application.
- Check the Streamlit configuration in `.streamlit/config.toml`.
- Review the application-container logs if running through Docker Compose.

### API calls fail

- Confirm `GOOGLE_API_KEY` is set in `.env`.
- Confirm the key is passed into the application container.
- Confirm `MODEL_ID` names an available model.
- Check provider rate limits and network access.
- Do not commit API keys or include them in Docker images.

### Monitoring charts are empty

Empty charts are expected when no corresponding records exist.

- Run a query to create a cached answer.
- Submit feedback to populate feedback charts.
- Submit manual-review scores to populate quality and Tier 2 coverage charts.
- Generate cache misses if you need cache-miss latency observations.
- Do not create artificial runtime records solely to populate charts.

### Manual scores are not visible

- Confirm the answer was persisted in `query_cache`.
- Confirm the review was submitted successfully.
- Confirm the `manual_scores` table exists.
- Check the Streamlit and database logs.
- Remember that PostgreSQL is the operational source of truth; JSONL logs are secondary portable artifacts.

---

## Safe regeneration rules

Before regenerating artifacts:

1. Confirm the source corpus version and content hashes.
2. Confirm whether the fixed evaluation benchmark must remain unchanged.
3. Run relevant regression tests.
4. Preserve existing evaluation artifacts unless intentionally replacing them.
5. Record changes to corpus, configuration, evaluator logic, retrieval logic, or prompt configuration.
6. Generate a new dated evaluation when changes affect evidence, retrieval, or answer generation.
7. Do not treat old evaluation results as applicable to a refreshed corpus without re-evaluation.

Avoid deleting the following files during routine work:

```text
data/evaluation/queries.jsonl
data/evaluation/query_rewrites.jsonl
data/evaluation/evaluation_results_postgres.jsonl
data/evaluation/evaluation_summary_postgres.json
data/evaluation/query_rewrite_results_postgres.jsonl
data/evaluation/query_rewrite_summary_postgres.json
data/evaluation/llm_answers.jsonl
data/evaluation/llm_judge_scores.jsonl
data/evaluation/llm_evaluation_summary.json
data/evaluation/llm_evaluation_report.md
```

Use a new dated output path when an experiment is not directly comparable with the established evaluation.

---

## Documentation map

- [`README.md`](../README.md) — Project overview, setup, architecture, and high-level results.
- [`docs/project-log.md`](project-log.md) — Working journal and stage-by-stage progress.
- [`docs/decisions.md`](decisions.md) — Design choices, alternatives, trade-offs, and implementation decisions.
- [`docs/dataset-notes.md`](dataset-notes.md) — Corpus details, source hierarchy, processing, distribution, and quality notes.
- [`docs/evaluation-notes.md`](evaluation-notes.md) — Retrieval protocol, historical v1/v2 context, authoritative v3 results, prompt evaluation, Tier 2 review, and RAG-impact evaluation.
- [`docs/runbook.md`](runbook.md) — This setup, reproduction, evaluation, and troubleshooting guide.

---

## Limitations and responsible use

DER RegCheck is a research-support prototype.

It does not provide:

- Legal advice.
- Regulatory advice.
- Engineering advice.
- Compliance certification.
- A substitute for reviewing the controlling tariff, handbook, utility instructions, or regulator materials.

Users should verify important conclusions against the current authoritative source, check applicability conditions, distinguish historical material from current requirements, and consult qualified professionals where appropriate.