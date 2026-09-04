# Runbook

## Overview

This runbook describes how to reproduce the DER RegCheck v1 environment, download the corpus, extract raw source content, normalise evidence blocks, generate searchable chunks, create embeddings, load the database, run production-aligned retrieval evaluation, and prepare for answer generation.

**Status:** Ingestion, raw extraction, deterministic evidence normalisation, quality reporting, tariff regression tests, structural chunking, embedding generation, database loading, production PostgreSQL/pgvector retrieval evaluation, cached query-rewrite evaluation, evaluator regression tests, and summariser regression tests are implemented. Historical file-based evaluations (v1 and v2) are retained as offline-baseline artifacts. The production-aligned PostgreSQL evaluation completed on 2026-09-05 is authoritative for the deployed retrieval path. Answer generation, Tier 2 RAG quality evaluation, monitoring, and interface stages are under development.

---

## Prerequisites

- Python 3.11+
- `uv` for dependency management: [https://github.com/astral-sh/uv](https://github.com/astral-sh/uv)
- Docker and Docker Compose for PostgreSQL with pgvector
- A configured `.env` file containing the database and LLM settings required by the project

---

## Environment setup

### Create a virtual environment and install dependencies

```bash
cd der-regcheck
uv sync
```

This installs dependencies from `pyproject.toml` and `uv.lock`.

### Add dependencies if required

For a new or independently reproduced setup:

```bash
uv add requests beautifulsoup4 pypdf pyyaml \
  sentence-transformers pgvector psycopg2-binary
```

Current pipeline dependencies:

- `requests` for corpus download
- `beautifulsoup4` for HTML main-content extraction
- `pypdf` for page-preserving PDF text extraction
- `pyyaml` for source-specific normalisation configuration
- `sentence-transformers` for Nomic embedding generation and cross-encoder reranking
- `pgvector` for PostgreSQL vector similarity search
- `psycopg2-binary` for the PostgreSQL driver

### Configure environment variables

Create a local environment file if one does not already exist:

```bash
cp .env.example .env
```

Set the project-specific values in `.env`:

```dotenv
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/der_regcheck
LLM_PROVIDER=<provider>
LLM_API_KEY=<api_key>
LLM_MODEL=gemini-3.5-flash-lite
EMBEDDING_MODEL=nomic-ai/nomic-embed-text-v1.5
RERANKER_MODEL=BAAI/bge-reranker-base
```

Do not commit `.env` or API keys.

---

## Download the corpus

### Run the downloader

```bash
uv run python src/ingestion/download_california_rule21_docs.py
```

This will:

- Download configured sources to `data/corpus/`.
- Validate expected PDF responses using the `%PDF-` signature.
- Retry PDFs that fail validation using a simplified request.
- Record hashes, validation status, review status, and eligibility metadata in `data/corpus/corpus_metadata.json`.

### Handle blocked or unreliable downloads

If a source fails validation, for example because a PDF URL returns HTML, SharePoint content, or an authentication page:

1. Manually download the required file through a browser or authenticated portal.
2. Save it to the source's configured local path.
3. Mark the local file as an approved manual replacement.

Example:

```bash
uv run python src/ingestion/download_california_rule21_docs.py \
  --mark-manual-replacement sce_interconnection_handbook_pdf \
  --reviewer your-name
```

This validates the local replacement, updates its hash, records the manual-replacement method, records reviewer approval, and enables extraction and default retrieval according to corpus metadata.

### Inspect corpus metadata

```bash
cat data/corpus/corpus_metadata.json
```

Review source-level fields including:

- `content_hash`
- `last_checked`
- `automated_validation`
- `manual_review`
- `eligible_for_extraction`
- `eligible_for_default_retrieval`

---

## Extract raw content

### Run the extractor

```bash
uv run python src/ingestion/extract_raw_content.py
```

This will:

- Read `data/corpus/corpus_metadata.json`.
- Process only sources with `eligible_for_extraction = true`.
- Preserve raw PDF text by physical PDF page using `pypdf`.
- Extract HTML main content with heading-path preservation using BeautifulSoup.
- Write raw extraction outputs to `data/processed/extracted/<document_id>.json`.
- Write an extraction manifest to `data/processed/extraction_manifest.json`.
- Record `schema_version` and `extraction_method` metadata in raw outputs.

Raw extraction does not perform source-authority assignment, LLM enrichment, normalisation, chunking, embedding, retrieval, or answer generation.

### Inspect raw extraction outputs

```bash
cat data/processed/extraction_manifest.json
```

Example raw PDF output:

```bash
sed -n '1,180p' \
  data/processed/extracted/sce_interconnection_handbook_pdf.json
```

Example raw HTML output:

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

- 50: nested tariff hierarchy
- 100: Roman-numeral list items and parent-path restoration
- 150: frequency provision and tariff sheet metadata
- 233: Appendix B hierarchy reset

### Generate normalised outputs

```bash
rm -rf data/processed/normalised/*

uv run python src/processing/normalise_documents.py \
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
uv run python src/processing/quality_check_normalised.py \
  --normalised-dir data/processed/normalised \
  --output-json data/processed/normalised/quality_report.json \
  --output-md data/processed/normalised/quality_report.md
```

Review the Markdown report:

```bash
sed -n '1,280p' data/processed/normalised/quality_report.md
```

### Inspect normalised tariff output

```bash
uv run python - <<'PY'
import json
from pathlib import Path

document = json.loads(
    Path("data/processed/normalised/sce_rule21_tariff_pdf.json").read_text(
        encoding="utf-8"
    )
)

for page_number in (50, 100, 150, 233):
    print("\n" + "=" * 100)
    print(f"Physical PDF page {page_number}")

    for block in document["blocks"]:
        if block["citation"].get("pdf_page_start") != page_number:
            continue

        print("\nblock_type:", block["block_type"])
        print("text:", block["text"][:350])
        print("heading_path:", " > ".join(block["heading_path"]))
        print("section_ids:", block["citation"]["section_ids"])
        print("tariff_rule_sheet:", block["citation"]["tariff_rule_sheet"])
        print("tariff_cpuc_sheet:", block["citation"]["tariff_cpuc_sheet"])
        print("tariff_advice_letter:", block["citation"]["tariff_advice_letter"])
PY
```

Expected normalisation behaviour includes:

- Tariff administrative page text excluded from evidence blocks.
- Tariff Rule 21 sheet number, Cal. PUC sheet number, effective date, and advice letter retained as citation metadata.
- Lettered, numeric, lettered-subsection, selected Roman subheading, and appendix hierarchy preserved.
- Prose-style Roman entries retained as list items.
- Appendix B resetting the hierarchy rather than inheriting the preceding tariff section.

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

A review warning is not necessarily a pipeline failure. Supporting-source or historical front matter may remain review-flagged if physical PDF page provenance is retained and the material is not used as default current-requirement evidence.

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

uv run python src/processing/chunk_documents.py \
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
uv run python src/processing/quality_check_chunks.py \
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

print(f"Total chunks: {len(document['chunks'])}")
print(f"Oversized chunks: {sum(1 for c in document['chunks'] if c['oversized'])}")

chunk = document["chunks"]
print("\n" + "=" * 100)
print(f"Chunk {chunk['chunk_id']}")
print("Block types:", chunk["block_types"])
print("Evidence text (first 300 chars):", chunk["evidence_text"][:300])
print("Embedding text (first 300 chars):", chunk["embedding_text"][:300])
print("Citation:", chunk["citation"])
print("Source policy:", chunk["source_policy"])
print("Neighbours:", chunk["neighbour_chunk_ids"])
PY
```

Expected chunking behaviour includes:

- 1,049 total chunks across 6 sources.
- 5 oversized chunks, all handbook table-of-contents blocks of 1,033-1,561 tokens.
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

```bash
rm -rf data/processed/embeddings/*

uv run python src/processing/generate_embeddings.py \
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

with open("data/processed/embeddings/embeddings.jsonl", "r", encoding="utf-8") as file:
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

## Load database

### Start PostgreSQL with pgvector

```bash
docker compose up -d db
```

Wait for PostgreSQL to be ready:

```bash
docker compose logs db | grep "database system is ready"
```

### Create the knowledge-base schema

```bash
uv run python src/database/init_db.py
```

This creates:

- `chunks` table for chunk text and metadata
- `chunk_embeddings` table for 768-dimensional vectors
- pgvector indexes required by the configured database schema
- PostgreSQL full-text retrieval structures required by lexical retrieval

### Load chunks into the database

```bash
uv run python src/scripts/load_chunks_to_db.py \
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

Run this only when intentionally creating a new benchmark. Do not regenerate queries when reproducing the established v3 result.

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

```bash
uv run python -m src.retrieval.retrieve \
  --query "What does SCE Rule 21 require for smart inverter reactive power?" \
  --top-k 5
```

The deployed retrieval path can use:

- PostgreSQL full-text lexical retrieval
- pgvector vector retrieval
- PostgreSQL-backed hybrid retrieval
- Runtime query embedding using Nomic `search_query:`
- Cross-encoder reranking using `BAAI/bge-reranker-base`

The current selected production configuration is:

```text
Expanded query
→ pgvector vector retrieval
→ BAAI/bge-reranker-base cross-encoder reranking
→ top 10 evidence chunks
```

Inspect returned source metadata and citation locators before treating any result as evidence for a requirement.

---

## Run retrieval evaluation

### Evaluation conditions

The authoritative Tier 1 v3 evaluation uses:

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

The v3 retrieval grid contains:

```text
100 queries
× 3 alpha values
× 5 retrieval variants
× 5 metadata weighting schemes
= 7,500 evaluation records
```

### Run the production-aligned PostgreSQL retrieval grid

Ensure PostgreSQL is running and contains the current 1,049 chunks and embeddings before starting.

```bash
uv run python -m src.evaluation.evaluate_retrieval \
  --queries data/evaluation/queries.jsonl \
  --output data/evaluation/evaluation_results_postgres.jsonl \
  --alphas "0.3,0.5,0.7" \
  --rerank-weightings "equal,authority_heavy,page_heavy,section_heavy,source_heavy" \
  --resume
```

If the evaluator requires an explicit database argument in the current implementation, add it using the project’s configured database URL:

```bash
uv run python -m src.evaluation.evaluate_retrieval \
  --queries data/evaluation/queries.jsonl \
  --output data/evaluation/evaluation_results_postgres.jsonl \
  --database-url "$DATABASE_URL" \
  --alphas "0.3,0.5,0.7" \
  --rerank-weightings "equal,authority_heavy,page_heavy,section_heavy,source_heavy" \
  --resume
```

Use `--resume` to continue from JSONL checkpoints. Use `--overwrite` only when deliberately replacing the result artifact.

### Summarise PostgreSQL retrieval results

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

### Expected v3 retrieval highlights

| Configuration | nDCG@10 | MRR | Recall@10 | Composite |
|---|---:|---:|---:|---:|
| Vector rerank, equal weighting | 0.94627 | 0.92500 | 0.09625 | 0.76989 |
| Vector rerank, authority-heavy weighting | 0.94627 | 0.92500 | 0.09625 | 0.76989 |
| Hybrid rerank, equal weighting, alpha 0.50 | 0.94589 | 0.92500 | 0.09625 | 0.76969 |
| Hybrid rerank, section-heavy weighting, alpha 0.30 | 0.93240 | 0.60800 | 0.11019 | 0.67065 |
| Hybrid, equal weighting, alpha 0.50 | 0.76700 | 0.87293 | 0.08580 | 0.66253 |
| Vector, equal weighting | 0.76330 | 0.87293 | 0.08480 | 0.66049 |
| Lexical, equal weighting | 0.15420 | 0.15500 | 0.00690 | 0.12499 |

Interpret the results as follows:

- Reranking is the dominant observed retrieval-quality improvement.
- Vector reranking has the strongest observed nDCG@10, MRR, and composite score.
- Hybrid reranking is a near-tied alternative under equal weighting and alpha 0.50.
- Equal weighting is the selected default because it ties for the strongest vector-rerank score and is simplest to justify.
- Recall@10 is metadata-derived and must not be interpreted as the proportion of real user questions answered successfully.
- See `docs/evaluation-notes.md` and `docs/decisions.md` #12 for full interpretation and limitations.

---

## Run cached query-rewrite evaluation

### Evaluation conditions

The cached query-rewrite evaluation uses:

- 100 fixed benchmark queries
- Four cached rewrite techniques:
  - `original`
  - `expanded`
  - `hyde`
  - `hyde_expanded`
- Four retrieval variants
- Five metadata weighting schemes

The completed grid contains:

```text
100 queries
× 4 rewrite techniques
× 4 retrieval variants
× 5 metadata weighting schemes
= 8,000 query-rewrite evaluation records
```

### Generate or refresh cached rewrites

Only regenerate rewrites when intentionally revising the rewrite-generation method or benchmark. Otherwise, use the committed `data/evaluation/query_rewrites.jsonl` artifact.

Use the project’s implemented rewrite-generation command and configured `LLM_MODEL`. The resulting file must retain the original query ID and record the rewrite technique, generated text, timestamp, and model.

### Run the PostgreSQL rewrite evaluation

Use the project’s implemented query-rewrite evaluation entry point. The required inputs and outputs are:

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

The evaluation must use the same PostgreSQL corpus, metric implementation, weighting schemes, and reranking configuration as the main v3 retrieval evaluation.

### Expected rewrite highlights

| Configuration | nDCG@10 | MRR | Recall@10 | Composite |
|---|---:|---:|---:|---:|
| Expanded query + vector rerank, equal weighting | 0.94713 | 0.93583 | 0.09214 | 0.77274 |
| Original query + vector rerank, equal weighting | 0.94627 | 0.92500 | 0.09625 | 0.76989 |
| HyDE query + vector rerank, equal weighting | 0.89930 | 0.69980 | 0.08420 | 0.67643 |
| HyDE-expanded query + vector rerank, equal weighting | 0.88720 | 0.67200 | 0.08060 | 0.66131 |

Interpret the results as follows:

- Query expansion produced a modest increase in nDCG@10, MRR, and composite score.
- Query expansion slightly reduced metadata-derived Recall@10.
- HyDE and HyDE plus expansion reduced ranking quality on this benchmark.
- HyDE is not enabled as a default rewrite technique.
- The query-expansion advantage is small and requires paired statistical testing or manually judged relevance data before a strong superiority claim.

---

## Run evaluator regression tests

Run regression tests before a deliberate re-evaluation or after changing evaluator or summariser logic.

```bash
uv run python -m unittest \
  tests.test_evaluate_retrieval \
  tests.test_summarise_evaluation
```

These tests cover evaluator and summary behaviour, including grouping, unique-query counting, variability calculations, and composite-score ranking.

---

## Historical file-based evaluation

Historical v1 and v2 evaluation artifacts use a separate file-based, in-memory evaluator.

They remain useful for development history and offline experimentation, but they are not the authoritative production result and must not be numerically compared directly with v3.

Use the historical commands and artifacts only when reproducing those earlier experimental conditions:

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
```

---

## Regenerate pipeline outputs

### Full pipeline regeneration

A corpus refresh changes the evidence, chunks, embeddings, and database state. If the fixed query set remains valid, rerun the PostgreSQL v3 retrieval and rewrite evaluations after loading the refreshed corpus.

```bash
# 1. Re-download corpus
uv run python src/ingestion/download_california_rule21_docs.py

# 2. Re-extract raw content
uv run python src/ingestion/extract_raw_content.py

# 3. Re-run normalisation
rm -rf data/processed/normalised/*
uv run python src/processing/normalise_documents.py \
  --input-manifest data/processed/extraction_manifest.json \
  --config config/normalisation.yaml \
  --output-dir data/processed/normalised

# 4. Re-run normalisation quality checks
uv run python src/processing/quality_check_normalised.py \
  --normalised-dir data/processed/normalised \
  --output-json data/processed/normalised/quality_report.json \
  --output-md data/processed/normalised/quality_report.md

# 5. Re-run chunking
rm -rf data/processed/chunks/*
uv run python src/processing/chunk_documents.py \
  --normalised-dir data/processed/normalised \
  --config config/chunking.yaml \
  --output-dir data/processed/chunks

# 6. Re-run chunk quality checks
uv run python src/processing/quality_check_chunks.py \
  --chunks-dir data/processed/chunks \
  --output-json data/processed/chunks/quality_report.json \
  --output-md data/processed/chunks/quality_report.md

# 7. Re-run embeddings
rm -rf data/processed/embeddings/*
uv run python src/processing/generate_embeddings.py \
  --chunks-dir data/processed/chunks \
  --output-dir data/processed/embeddings \
  --model nomic-ai/nomic-embed-text-v1.5

# 8. Recreate and load the database
docker compose down
docker compose up -d db
uv run python src/database/init_db.py
uv run python src/scripts/load_chunks_to_db.py \
  --chunks-dir data/processed/chunks \
  --embeddings-file data/processed/embeddings/embeddings.jsonl

# 9. Run evaluator regression tests
uv run python -m unittest \
  tests.test_evaluate_retrieval \
  tests.test_summarise_evaluation

# 10. Re-run the production-aligned PostgreSQL retrieval grid
rm -f data/evaluation/evaluation_results_postgres.jsonl
rm -f data/evaluation/evaluation_summary_postgres.json

uv run python -m src.evaluation.evaluate_retrieval \
  --queries data/evaluation/queries.jsonl \
  --output data/evaluation/evaluation_results_postgres.jsonl \
  --alphas "0.3,0.5,0.7" \
  --rerank-weightings "equal,authority_heavy,page_heavy,section_heavy,source_heavy" \
  --overwrite

# 11. Summarise the production-aligned retrieval grid
uv run python -m src.evaluation.summarise_evaluation \
  --input data/evaluation/evaluation_results_postgres.jsonl \
  --output data/evaluation/evaluation_summary_postgres.json \
  --top-n 10 \
  --decimals 5

# 12. Re-run cached query-rewrite evaluation using the project's rewrite evaluator
# Keep the cached query-rewrite artifact fixed unless deliberately regenerating it.
```

Do not delete `data/evaluation/queries.jsonl` or `data/evaluation/query_rewrites.jsonl` during a routine rerun if the goal is comparable evaluation against the established benchmark.

If the query set, rewrite set, corpus, embedding model, chunking configuration, evaluator logic, or database retrieval logic changes, record a new dated evaluation condition rather than silently replacing the v3 result.

---

## Run the application

### Run the Streamlit app

*To be implemented:*

```bash
uv run streamlit run app/main.py
```

---

## Generate answers

### Generate grounded answers

*To be implemented:*

```bash
uv run python -m src.generation.answer_question \
  --query "What are the communications requirements for DER in SCE?" \
  --top-k 10 \
  --model gemini-3.5-flash-lite
```

### Generate evidence briefs

*To be implemented:*

```bash
uv run python -m src.generation.generate_brief \
  --request "Early market assessment for DER communications and control" \
  --top-k 15 \
  --model gemini-3.5-flash-lite
```

Answer generation must preserve source hierarchy, source currency, applicability conditions, uncertainty, and citation locators.

---

## Troubleshooting

### Download fails for a specific source

- Check the error printed by the downloader.
- Inspect the source entry in `data/corpus/corpus_metadata.json`.
- Open the source URL in a browser to determine whether it redirects, requires authentication, or serves unexpected content.
- For failed PDF validation, allow the simplified-request fallback to run.
- If the source remains blocked, manually download it and use `--mark-manual-replacement`.

### Raw extraction fails for a source

- Confirm the local file exists at its configured `local_path`.
- Confirm `eligible_for_extraction = true` in corpus metadata.
- For PDFs, confirm the source passed `%PDF-` signature validation.
- Inspect the `failures` array in `data/processed/extraction_manifest.json`.

### Normalisation fails for a source

- Confirm raw extraction completed successfully.
- Confirm the source JSON is listed as `success` in `data/processed/extraction_manifest.json`.
- Check `config/normalisation.yaml` for invalid YAML or malformed regular expressions.
- Run the unit tests before re-running the full normalisation pipeline.
- Inspect `data/processed/normalised/normalisation_manifest.json` for failures.

### Quality report contains review warnings

- Inspect warning blocks using the warning-block command in the normalisation section.
- Determine whether the block is:
  - cover, contents, disclaimer, page-header, or document-control material;
  - substantive text requiring a source-specific heading rule; or
  - accepted supporting or historical context with page-level provenance.
- Do not add broad generic heuristics solely to eliminate warnings.
- Record accepted limitations in `docs/decisions.md`, `docs/dataset-notes.md`, and the project log.

### Chunking produces oversized chunks

- Check `data/processed/chunks/quality_report.md` for oversized chunk details.
- Verify whether the chunks are acceptable, such as handbook table-of-contents blocks.
- If substantive content is oversized, consider adjusting `config/chunking.yaml` thresholds.
- Do not split citation-grade evidence mid-block; record accepted exceptions.

### Embedding generation fails

- Confirm `sentence-transformers` is installed.
- Verify internet connectivity for model download or use a cached model.
- Check that `data/processed/chunks/` exists and contains valid chunk JSON files.
- Confirm the model name is `nomic-ai/nomic-embed-text-v1.5`.

### Database connection fails

- Ensure PostgreSQL is running:

```bash
docker compose ps
```

- Verify `DATABASE_URL` in `.env`.
- Check that the pgvector extension is installed and enabled.
- Confirm the database schema has been created with `src/database/init_db.py`.

### PostgreSQL evaluation fails or resumes unexpectedly

- Confirm PostgreSQL is running and contains 1,049 chunks and 1,049 embeddings.
- Confirm `DATABASE_URL` is available to the evaluator.
- Inspect the existing JSONL output before choosing `--resume`, `--overwrite`, or a new dated output file.
- Use `--resume` only when continuing the same benchmark, corpus, evaluator implementation, and configuration grid.
- Use `--overwrite` only when deliberately replacing an incomplete or invalid artifact.
- Run evaluator regression tests after changing evaluation logic.

### Retrieval evaluation produces unexpected metrics

- Confirm `data/evaluation/queries.jsonl` contains the intended fixed benchmark.
- Confirm the database contains chunks and embeddings derived from the intended corpus version.
- Check metadata matching logic in `src/evaluation/evaluate_retrieval.py`.
- Confirm chunk metadata includes required fields such as `source_id`, `section_ids`, `block_types`, citation pages, and authority-tier metadata.
- Confirm the summariser groups by alpha and counts unique query IDs correctly.
- Distinguish historical file-based v1/v2 artifacts from the authoritative PostgreSQL v3 artifacts.
- Interpret Recall@10 as metadata-defined chunk coverage, not end-user answer success.
- Consult `docs/evaluation-notes.md` and `docs/decisions.md` #12 for the evaluation protocol and limitations.

---

## Next steps

- ✅ Commit the raw-extraction metadata and evidence-normalisation milestone. **Completed**
- ✅ Implement deterministic, section-aware chunk assembly over normalised blocks. **Completed**
- ✅ Preserve citation-grade evidence text separately from embedding-oriented context text. **Completed**
- ✅ Add source authority, retrieval tier, currency, and applicability metadata to chunks. **Completed**
- ✅ Implement PostgreSQL + pgvector knowledge base. **Completed**
- ✅ Implement historical lexical, vector, and hybrid retrieval evaluation (v1). **Completed**
- ✅ Implement historical file-based reranking, alpha sweeps, weighting schemes, and composite scoring (v2). **Completed**
- ✅ Implement production-aligned PostgreSQL full-text, pgvector, hybrid, runtime embedding, and reranking evaluation. **Completed 2026-09-05**
- ✅ Complete the PostgreSQL retrieval grid: 100 queries × 3 alphas × 5 retrieval variants × 5 weightings = 7,500 records. **Completed 2026-09-05**
- ✅ Complete the cached PostgreSQL query-rewrite evaluation: 8,000 records. **Completed 2026-09-05**
- ✅ Implement evaluator and summariser regression tests. **Completed**
- ✅ Select the production retrieval configuration: expanded query + vector rerank. **Completed**
- ⏳ Run paired statistical testing for original versus expanded query variants. **Pending**
- ⏳ Create a manually judged relevance set to supplement metadata-derived relevance labels. **Pending**
- ⏳ Implement source-aware filtering and tier-based retrieval constraints. **Pending**
- ⏳ Implement grounded answer and preliminary market-entry evidence-brief generation. **Pending**
- ⏳ Implement RAG quality evaluation (Tier 2) with 5-10 open-ended questions. **Pending**
- ⏳ Implement a Streamlit interface, feedback capture, and monitoring. **Pending**