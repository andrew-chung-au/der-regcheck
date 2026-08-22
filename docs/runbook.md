# Runbook


## Overview

This runbook describes how to reproduce the DER RegCheck v1 environment, download the corpus, extract raw source content, normalise evidence blocks, review output quality, and run future application stages.

**Status:** Ingestion, raw extraction, deterministic evidence normalisation, quality reporting, and tariff regression tests are implemented. Chunking, database, retrieval, generation, evaluation, monitoring, and interface stages are under development.


---


## Prerequisites

- Python 3.11+
- `uv` for dependency management: [https://github.com/astral-sh/uv](https://github.com/astral-sh/uv)
- (Optional) Docker and Docker Compose for the future database and full-stack runtime


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
uv add requests beautifulsoup4 pypdf pyyaml
```

Current pipeline dependencies:

- `requests` for corpus download
- `beautifulsoup4` for HTML main-content extraction
- `pypdf` for page-preserving PDF text extraction
- `pyyaml` for source-specific normalisation configuration


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


## Regenerate pipeline outputs


### Re-download the corpus

```bash
uv run python src/ingestion/download_california_rule21_docs.py
```


### Re-extract raw content

```bash
uv run python src/ingestion/extract_raw_content.py
```


### Re-run normalisation and quality checks

```bash
rm -rf data/processed/normalised/*

uv run python -m unittest \
  tests.test_normalise_documents \
  tests.test_quality_check_normalised

uv run python src/processing/normalise_documents.py \
  --input-manifest data/processed/extraction_manifest.json \
  --config config/normalisation.yaml \
  --output-dir data/processed/normalised

uv run python src/processing/quality_check_normalised.py \
  --normalised-dir data/processed/normalised \
  --output-json data/processed/normalised/quality_report.json \
  --output-md data/processed/normalised/quality_report.md
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


### Load normalised chunks into the database

*To be implemented after structural chunking:*

```bash
uv run python src/database/load_chunks.py
```


---


## Retrieval and generation (planned)


### Run retrieval experiments

*To be implemented:*

```bash
uv run python src/evaluation/run_retrieval_eval.py
```


### Generate grounded answers and evidence briefs

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


### Run answer and evidence-brief evaluation

*To be implemented:*

```bash
uv run python src/evaluation/evaluate_answers.py
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


### Database connection fails (planned)

- Ensure PostgreSQL is running:

```bash
docker compose ps
```

- Verify `DATABASE_URL` in `.env`.
- Check that the `pgvector` extension is installed and enabled.


---


## Next steps

- Commit the raw-extraction metadata and evidence-normalisation milestone.
- Implement deterministic, section-aware chunk assembly over normalised blocks.
- Preserve citation-grade evidence text separately from future embedding-oriented context text.
- Add source authority, retrieval tier, currency, and applicability metadata to chunks.
- Implement PostgreSQL + pgvector knowledge base.
- Implement lexical, vector, hybrid, and reranked retrieval.
- Create a small labelled retrieval evaluation set.
- Implement grounded answer and preliminary market-entry evidence-brief generation.
- Implement a Streamlit interface, feedback capture, and monitoring.