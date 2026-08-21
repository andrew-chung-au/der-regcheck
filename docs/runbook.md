# Runbook


## Overview


This runbook describes how to reproduce the DER RegCheck v1 environment, download the corpus, extract content, and run the application.


**Status:** Ingestion and extraction are implemented; database, retrieval, generation, and interface are under development.


---


## Prerequisites


- Python 3.11+
- `uv` for dependency management: https://github.com/astral-sh/uv
- (Optional) Docker and Docker Compose for future full-stack runtime


---


## Environment setup


### Create a virtual environment and install dependencies


```bash
cd der-regcheck
uv sync
```

This installs all dependencies from `pyproject.toml` and `uv.lock`.


### Add ingestion dependencies (if not already present)


```bash
uv add requests beautifulsoup4 pypdf
```


---


## Download the corpus


### Run the downloader


```bash
uv run python src/ingestion/download_california_rule21_docs.py
```

This will:
- Download all configured sources to `data/corpus/`.
- Validate PDF signatures.
- Retry failed PDFs with a simplified request.
- Record metadata in `data/corpus/corpus_metadata.json`.


### Handle blocked or unreliable downloads


If a source fails validation (e.g., returns HTML instead of PDF):

1. Manually download the file via browser or authenticated portal.
2. Save it to the configured path (e.g., `data/corpus/03_sce_interconnection_handbook.pdf`).
3. Mark it as manually replaced:

```bash
uv run python src/ingestion/download_california_rule21_docs.py \
  --mark-manual-replacement sce_interconnection_handbook_pdf \
  --reviewer your-name
```

This updates metadata to mark the file approved for extraction and default retrieval.


---


## Extract content


### Run the extractor


```bash
uv run python src/ingestion/extract_raw_content.py
```

This will:
- Read `data/corpus/corpus_metadata.json`.
- Only process sources with `eligible_for_extraction = true`.
- Extract page-preserving PDF text and main-content HTML.
- Write outputs to `data/processed/extracted/<document_id>.json`.
- Write a manifest to `data/processed/extraction_manifest.json`.


### Inspect outputs


```bash
cat data/processed/extraction_manifest.json
cat data/processed/extracted/sce_interconnection_handbook_pdf.json
```


---


## Database and knowledge base (planned)


### Start PostgreSQL with pgvector


*To be implemented:*

```bash
docker compose up -d db
```

### Create the knowledge base schema


*To be implemented:*

```bash
uv run python src/database/init_db.py
```

### Load chunks into the database


*To be implemented:*

```bash
uv run python src/ingestion/load_to_db.py
```


---


## Retrieval and generation (planned)


### Run retrieval experiments


*To be implemented:*

```bash
uv run python src/evaluation/run_retrieval_eval.py
```

### Generate answers and briefs


*To be implemented:*

```bash
uv run python src/generation/answer_question.py
uv run python src/generation/generate_brief.py
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
EMBEDDING_MODEL=<model_name>
```


### Run the Streamlit app


*To be implemented:*

```bash
uv run streamlit run app/main.py
```


---


## Run evaluation (planned)


### Run retrieval evaluation


*To be implemented:*

```bash
uv run python src/evaluation/evaluate_retrieval.py
```

### Run answer/brief evaluation


*To be implemented:*

```bash
uv run python src/evaluation/evaluate_answers.py
```


---


## Regenerate outputs


### Re-download the corpus


```bash
uv run python src/ingestion/download_california_rule21_docs.py
```

### Re-extract content


```bash
uv run python src/ingestion/extract_raw_content.py
```

### Re-load to database (planned)


```bash
uv run python src/ingestion/load_to_db.py
```


---


## Troubleshooting


### Download fails for a specific source


- Check the error message in the console output.
- Inspect `corpus_metadata.json` for the `failures` array.
- Try opening the URL in a browser to see if it requires authentication or shows an error.
- If blocked, manually download and use `--mark-manual-replacement`.


### Extraction fails for a source


- Check that the file exists at the configured `local_path`.
- Verify that `eligible_for_extraction = true` in metadata.
- For PDFs, ensure the file starts with `%PDF-` signature.
- Check the `failures` array in `extraction_manifest.json`.


### Database connection fails (planned)


- Ensure PostgreSQL is running: `docker compose ps`
- Verify `DATABASE_URL` in `.env` matches your database configuration.
- Check that the `pgvector` extension is installed and enabled.


---


## Next steps


- Implement PostgreSQL + pgvector knowledge base.
- Implement chunking logic for each source type.
- Implement retrieval (vector, lexical, hybrid, reranking).
- Implement answer and brief generation.
- Implement Streamlit interface.
- Implement evaluation scripts and record results.