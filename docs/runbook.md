# Runbook

## Overview

This runbook describes how to reproduce the DER RegCheck v1 environment, download the corpus, extract raw source content, normalise evidence blocks, generate searchable chunks, create embeddings, load the database, run retrieval evaluation (Tier 1 v1 and v2), and prepare for answer generation.

**Status:** Ingestion, raw extraction, deterministic evidence normalisation, quality reporting, tariff regression tests, structural chunking, embedding generation, database loading, and extended retrieval evaluation (including reranking and composite scoring) are implemented. Answer generation, RAG quality evaluation (Tier 2), monitoring, and interface stages are under development.

---

## Prerequisites

- Python 3.11+
- `uv` for dependency management: [https://github.com/astral-sh/uv](https://github.com/astral-sh/uv)
- Docker and Docker Compose for PostgreSQL with pgvector

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
- `sentence-transformers` for Nomic embedding generation
- `pgvector` for PostgreSQL vector similarity search
- `psycopg2-binary` for PostgreSQL database driver

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

This validates the local replacement, updates its hash, records the manual replacement method, records reviewer approval, and enables extraction and default retrieval according to corpus metadata.

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

- Preserves `evidence_text` unchanged from normalised blocks (citation-grade).
- Prepends heading context to `embedding_text` (for retrieval quality).
- Merges citation metadata (PDF pages, tariff sheets, section IDs).
- Links neighbour chunks (previous/next for navigation).
- Flags oversized blocks without splitting mid-evidence.

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

# Inspect a sample chunk
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
- 5 oversized chunks (all handbook TOC blocks, 1,033-1,561 tokens).
- `evidence_text` unchanged from normalised blocks.
- `embedding_text` has heading context prepended.
- Neighbour links enable navigation.

---

## Generate embeddings

### Purpose

Embeddings enable vector similarity search for retrieval.

The embedding stage:

- Uses Nomic nomic-embed-text-v1.5 (768-dim vectors).
- Applies `search_document:` prefix to chunk `embedding_text`.
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
from pathlib import Path

# Load first 5 embeddings
with open("data/processed/embeddings/embeddings.jsonl", "r") as f:
    for i, line in enumerate(f):
        if i >= 5:
            break
        emb = json.loads(line)
        print(f"\nChunk {emb['chunk_id']}")
        print(f"Vector dimension: {len(emb['vector'])}")
        print(f"Model: {emb['embedding_model']}")
        print(f"Prefix: {emb['embedding_prefix']}")
PY
```

Expected embedding outputs:

- 1,049 embeddings (one per chunk).
- 768-dimensional vectors.
- `search_document:` prefix applied.

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

### Create the knowledge base schema

```bash
uv run python src/database/init_db.py
```

This creates:

- `chunks` table (full chunk metadata)
- `chunk_embeddings` table (768-dim vectors with pgvector)
- IVFFlat index for fast similarity search

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
import psycopg2

conn = psycopg2.connect(
    "postgresql://postgres:postgres@localhost:5432/der_regcheck"
)
cur = conn.cursor()

# Count chunks
cur.execute("SELECT COUNT(*) FROM chunks")
print(f"Chunks: {cur.fetchone()}")

# Count embeddings
cur.execute("SELECT COUNT(*) FROM chunk_embeddings")
print(f"Embeddings: {cur.fetchone()}")

# Sample similarity search (dummy vector shown; replace with a real 768-dim query embedding)
dummy_vector = [0.0] * 768
vector_str = "[" + ",".join(str(x) for x in dummy_vector) + "]"

cur.execute(f"""
    SELECT chunk_id, source_id, 
           1 - (embedding <=> '{vector_str}'::vector) AS similarity
    FROM chunk_embeddings
    ORDER BY similarity DESC
    LIMIT 5
""")
print("\nTop 5 similar chunks (dummy query):")
for row in cur.fetchall():
    print(f"  {row} | {row} | similarity: {row:.4f}")

cur.close()
conn.close()
PY
```

---

## Run retrieval evaluation (Tier 1)

### Generate evaluation queries

```bash
uv run python -m src.evaluation.generate_synthetic_queries \
  --chunks-dir data/processed/chunks \
  --output-file data/evaluation/queries.jsonl \
  --num-queries 100 \
  --model gemini-3.5-flash-lite
```

Expected output:

- 100 LLM-generated queries with gold chunk metadata.

### Run retrieval evaluation (v1-style: BM25, vector, hybrid; no rerank)

```bash
uv run python -m src.evaluation.evaluate_retrieval \
  --queries data/evaluation/queries.jsonl \
  --chunks-dir data/processed/chunks \
  --output data/evaluation/evaluation_results_v1.jsonl \
  --alphas "0.5" \
  --rerank-weightings "equal" \
  --rerank-only \
  --overwrite
```

Then, if you want a pure v1-style set without reranking, you can restrict analysis to the non-reranked rows in the summary step, or run a separate evaluation script variant. The current unified script supports both v1 and v2 configurations; the key is how you interpret the results.

### Run retrieval evaluation (v2: extended with reranking and multiple alphas)

```bash
uv run python -m src.evaluation.evaluate_retrieval \
  --queries data/evaluation/queries.jsonl \
  --chunks-dir data/processed/chunks \
  --output data/evaluation/evaluation_results.jsonl \
  --alphas "0.3,0.5,0.7" \
  --rerank-weightings "equal,authority_heavy,page_heavy,section_heavy,source_heavy" \
  --resume
```

Expected output:

- 8,100 retrieval records (multiple retrievers × alphas × weightings, including reranking).
- Metrics: nDCG@10, MRR, Recall@10, and composite score (0.5·nDCG + 0.3·MRR + 0.2·Recall).

### Review evaluation results

```bash
uv run python -m src.evaluation.summarise_evaluation \
  --input data/evaluation/evaluation_results.jsonl \
  --output data/evaluation/evaluation_summary.json \
  --top-n 10 \
  --decimals 5
```

Expected highlights (v2):

- Top configuration by composite: `hybrid_rerank__equal` (composite ≈ 0.96148).
- Reranked configurations dominate non-reranked on all metrics.
- Weighting differences among reranked configs are in the 4th–5th decimal.

See `docs/evaluation-notes.md` and `docs/decisions.md` #11 for interpretation and the selected production configuration (hybrid + rerank, equal weighting, α = 0.5).

---

## Run retrieval (production)

### Test production retrieval

```bash
uv run python -m src.retrieval.retrieve \
  --query "What does SCE Rule 21 require for smart inverter reactive power?" \
  --top-k 5
```

Expected output:

- Top 5 retrieved chunks with metadata and citations, using the production configuration (hybrid + rerank, equal weighting).

---

## Regenerate pipeline outputs

### Full pipeline regeneration

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

# 4. Re-run chunking
rm -rf data/processed/chunks/*
uv run python src/processing/chunk_documents.py \
  --normalised-dir data/processed/normalised \
  --config config/chunking.yaml \
  --output-dir data/processed/chunks

# 5. Re-run embedding
rm -rf data/processed/embeddings/*
uv run python src/processing/generate_embeddings.py \
  --chunks-dir data/processed/chunks \
  --output-dir data/processed/embeddings \
  --model nomic-ai/nomic-embed-text-v1.5

# 6. Re-load database
docker compose down db
docker compose up -d db
uv run python src/database/init_db.py
uv run python src/scripts/load_chunks_to_db.py \
  --chunks-dir data/processed/chunks \
  --embeddings-file data/processed/embeddings/embeddings.jsonl

# 7. Re-run evaluation (v2: extended with reranking and multiple alphas)
rm -rf data/evaluation/*
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

---

## Run the application (planned)

### Set environment variables

```bash
cp .env.example .env
```

Edit `.env` to set:

```dotenv
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/der_regcheck
LLM_PROVIDER=<provider>
LLM_API_KEY=<api_key>
EMBEDDING_MODEL=nomic-ai/nomic-embed-text-v1.5
```

### Run the Streamlit app

*To be implemented:*

```bash
uv run streamlit run app/main.py
```

---

## Generate answers (planned)

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
  - accepted supporting/historical context with page-level provenance.
- Do not add broad generic heuristics solely to eliminate warnings.
- Record accepted limitations in `docs/decisions.md` and `docs/project-log.md`.

### Chunking produces oversized chunks

- Check `data/processed/chunks/quality_report.md` for oversized chunk details.
- Verify these are acceptable (e.g., handbook TOC blocks).
- If substantive content is oversized, consider adjusting `config/chunking.yaml` thresholds.
- Do not split mid-evidence; accept documented exceptions.

### Embedding generation fails

- Confirm `sentence-transformers` is installed.
- Verify internet connectivity for model download (or use cached model).
- Check `data/processed/chunks/` exists and contains valid chunk JSON files.

### Database connection fails

- Ensure PostgreSQL is running:

```bash
docker compose ps
```

- Verify `DATABASE_URL` in `.env`.
- Check that the `pgvector` extension is installed and enabled.

### Retrieval evaluation produces unexpected metrics

- Verify queries are diverse and well-formed: `head data/evaluation/queries.jsonl`
- Check metadata matching logic in `src/evaluation/evaluate_retrieval.py`.
- Confirm chunk metadata includes all required fields (source_id, section_ids, etc.).
- Compare against `docs/evaluation-notes.md` and `docs/decisions.md` #11 to ensure you're interpreting v1 vs v2 results correctly.

---

## Next steps

- ✅ Commit the raw-extraction metadata and evidence-normalisation milestone. **Completed**
- ✅ Implement deterministic, section-aware chunk assembly over normalised blocks. **Completed**
- ✅ Preserve citation-grade evidence text separately from embedding-oriented context text. **Completed**
- ✅ Add source authority, retrieval tier, currency, and applicability metadata to chunks. **Completed**
- ✅ Implement PostgreSQL + pgvector knowledge base. **Completed**
- ✅ Implement lexical, vector, hybrid retrieval and evaluation (v1). **Completed**
- ✅ Extend evaluation to include reranking, multiple alphas, all weightings, and composite scoring (v2). **Completed**
- ✅ Create a labelled retrieval evaluation set (100 queries). **Completed**
- ⏳ Run RRF k sweep (k ∈ {1, 20, 60, 100}) to align with course experiments. **Pending**
- ⏳ Implement source-aware filtering and tier-based retrieval constraints. **Pending**
- ⏳ Implement grounded answer and preliminary market-entry evidence-brief generation. **Pending**
- ⏳ Implement RAG quality evaluation (Tier 2) with 5-10 open-ended questions. **Pending**
- ⏳ Implement a Streamlit interface, feedback capture, and monitoring. **Pending**