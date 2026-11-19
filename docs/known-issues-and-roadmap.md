# Known issues and roadmap

Read this first when returning to the project. It records what is working, what was found broken or inconsistent, and what to do next.

Last reviewed: 2026-11-19. The review was mostly documentation. Code or data changes were limited to findings 1, 2, 9, 10, 12, 13 and 14 and the prompt-comparison summary (marked below). Other issues are still present. Each finding comes from reading the repository; the method is given where something was run.

## Current state

- The pipeline, database schema, retrieval, answer generation, evaluation scripts and Streamlit app are implemented. Processed data (1,049 chunks and embeddings) and evaluation artefacts are committed.
- Last commit: 2026-09-07. Work took place between 2026-08-21 and 2026-09-07.
- Unit tests: 36 passed, 7 skipped, 1 error on Python 3.11 without a database or Hugging Face access (see the [runbook](runbook.md#run-regression-tests)).
- Docker path verified by the author on 2026-11-19 (see below).

## Verification status

### Verified (author's machine, 2026-11-19)

- `docker compose up --build` builds the image on Python 3.13 (about 14 minutes the first time, with a 5.63 GB build context) and starts both containers. `docker compose ps` shows `app` and `db` as `healthy`. This also exercises the `pyproject.toml` metadata change (`license = "MIT"`) and the `data/feedback/.gitkeep` `COPY`.
- `make load-chunks-docker`, run twice against a database that already held the data, completes both times with `Chunks: 1049` and `Embeddings: 1049`. The schema initialisation inside it also re-runs cleanly. A direct `SELECT count(*)` returned 1049 for `chunks` and 1049 for `chunk_embeddings`.

### Not verified

The database already existed before these runs, so a load into a truly empty volume has not been checked. The second loader run used identical data, so the upsert's replacement of changed rows has not been checked either. The review environment had no Docker daemon, no PostgreSQL, no Gemini key and no Hugging Face access (Python 3.11 rather than 3.13).

- The effect of the new `.dockerignore` on build context size and on the build itself.
- A question answered end to end in the Streamlit app (needs `GOOGLE_API_KEY` and the model downloads).
- `make load-chunks` on the host, `make db-init-docker` on its own, and the other `make docker-*` targets.
- The 7 database-dependent tests and `tests/test_embed_chunks.py`.
- Every evaluation script (they need the database and Gemini).
- `uv sync` from `uv.lock`. The Docker build uses `uv pip install -e .`, which does not read the lock file.
- The earlier temporary AWS EC2 demo. Its link was removed from the README, and its current status is unknown.

## Findings

### Defects in tooling

| # | Finding | Evidence | Suggested fix |
|---|---|---|---|
| 1 | **Fixed.** `make load-chunks` passed `--embeddings-file`, which the loader rejects. It now passes `--embeddings-dir data/processed/embeddings`. The equivalent `make load-chunks-docker` target was run successfully; the host target itself was not. | `Makefile` | None. |
| 2 | **Fixed.** Re-running the loader against PostgreSQL 16 with pgvector succeeded and left the counts unchanged (see Verification status); replacement of changed rows was not tested. `insert_chunks` and `insert_embeddings` now upsert (`ON CONFLICT ... DO UPDATE`). Chunks deleted from the source files are still not removed from the database; that needs a clean reload. The full-text column updates through the existing trigger. | `src/database/db_chunks.py` | Optionally delete rows missing from the loaded set. |
| 3 | Tests cannot run in the app container because the Dockerfile does not copy `tests/` and installs without the dev group. | `Dockerfile` | Run tests on the host, or add a test stage. |
| 4 | Compose does not initialise the database. A fresh volume needs `make db-init-docker` and `make load-chunks-docker` before the app works. Earlier docs described this as automated ingestion; it is not. | `compose.yaml` has no init or loader service | Add an init service or an entrypoint step. |
| 5 | The `db` healthcheck is written as `CMD-SHELL` followed by several list items. Docker runs only the first command string (`pg_isready`) and ignores the user and database flags. `docker compose ps` reported the database as `healthy` on 2026-11-19, so it works, but it is unclear whether the user and database flags are applied. | `compose.yaml` | Use `CMD` form or a single shell string. |
| 6 | Hugging Face models are downloaded at runtime with no cache volume in Compose. A recreated container downloads them again. The Nomic model is loaded with `trust_remote_code=True` (revision pinned in `config/embedding.yaml`). | `compose.yaml`, `src/retrieval/runtime_retriever.py`, `src/processing/embed_chunks.py` | Mount a cache volume or pre-download in the image. |
| 7 | PostgreSQL is published on host port 5432 with default credentials `postgres`/`postgres`. Fine on a laptop, not elsewhere. | `compose.yaml`, `.env.example` | Bind to `127.0.0.1` and require a real password outside local use. |
| 8 | The Streamlit app has no authentication. | `src/ui/streamlit_app.py` | Needed before any public deployment. |

### Inconsistencies in code comments and metadata

| # | Finding | Where |
|---|---|---|
| 9 | **Fixed.** Docstrings in `runtime_retriever.py`, `production_pipeline.py` and `demo_rag.py` described query expansion as part of the default flow. They now describe the original-query path. | `src/retrieval/`, `src/scripts/demo_rag.py` |
| 10 | **Partly fixed.** The template description was replaced and MIT licence and author metadata added. The project name is still `der` (renaming would affect `uv.lock`). The pyproject change was not exercised with `uv sync` or the Docker build. | `pyproject.toml` |
| 11 | `src/database/db_monitoring.py`, `src/ingestion/analyse_structure.py` and `src/monitoring/` are empty. | `src/` |
| 12 | **Fixed.** Summary JSON files contained absolute paths from the author's machine (`/home/andrew/...`). Both summarisers now write repository-relative paths, and the paths in the two existing files were edited by hand (no other content changed). | `src/evaluation/summarise_*_evaluation.py`, `data/evaluation/` |
| 13 | **Fixed.** `data/feedback/feedback.jsonl` (3 events) and `data/evaluation/tier2_manual_scores.jsonl` (2 scores) were development test entries and have been removed. The app creates both files on first use. `data/feedback/.gitkeep` keeps the directory so the Dockerfile `COPY` still works. Real runtime logs written there would be committed by accident; consider adding them to `.gitignore`. | `data/feedback/`, `data/evaluation/` |
| 14 | **Partly fixed.** An MIT `LICENSE` was added. There is still no CI configuration or contributing guide. | repository root |
| 15 | The initial `Decision 12` text says expanded-query retrieval was "selected as the current default". Decision 13 overrides this for runtime. Both are accurate but easy to misread. | `docs/decisions.md` |

### Evaluation caveats

- **Retrieval labels.** Each of the 100 queries has a single gold chunk and relevance is derived from chunk metadata. Recall@10 sits near 0.10 for every configuration, so only nDCG@10 and MRR are informative.
- **Duplicate records in the prompt-comparison inputs (summary fixed, raw files unchanged).** `llm_answers.jsonl` has 222 lines but only 72 distinct (question, prompt) pairs. The other 150 lines are byte-identical copies, and `llm_judge_scores.jsonl` has 2,752 rows because the judge ran over the copies. The summariser now deduplicates by (question, prompt) and averages judge scores per question, and the committed summary and report were regenerated (2026-11-19). Corrected figures: citation-valid v1 21/24, v2 22/24, v3 24/24; mean composite v1 4.864, v2 4.906, v3 4.881 (previously 94.6%/97.3%/100% and 4.751/4.867/4.811). The v3 selection still holds. The pre-correction summary and report are in git history (commit `86b1006` and earlier). The repeated lines in the raw files have not been removed, and the judge scores for repeated copies differ (16 question/prompt pairs have varying composites), which is extra judge noise worth knowing about.
- **Same-family judge.** Gemini generates and judges answers. No human validation of judge scores has been done.
- **Small samples.** The prompt comparison uses 24 questions and the impact study 10. The v3 prompt did not clearly beat zero-shot RAG in the impact study (3 wins, 5 losses, 2 ties).
- **Structural citation check only.** Labels are validated, not whether the passage supports the claim.
- **v1/v2 retrieval results** came from an earlier file-based evaluator whose code is no longer in the repository. They cannot be reproduced and are not comparable with v3.
- **No aggregate human review.** Only the 2 test-like manual scores exist.

## Roadmap

Ordered by value to the project, not by commitment. Nothing here is in progress.

1. **Fix the remaining small defects** (findings 10 and 14: CI, project name). Each is small.
2. **Finish verifying the Docker path** on a clean volume with a real question answered, and add a model-cache volume (finding 6). A `.dockerignore` has been added to shrink the 5.63 GB build context and keep `.env` out of the builder layer; rebuild and confirm the context size drops and both services still reach `healthy`.
3. **Add CI** that runs the unit tests (the 7 database tests can run against a pgvector service container) and checks the committed chunk and embedding counts.
4. **Improve evaluation validity**
   - Re-run the prompt comparison cleanly (one answer per question and prompt, one judge pass, possibly several judge samples to measure judge noise) instead of relying on the repeated records.
   - Build a small human-labelled retrieval set with more than one relevant chunk per query.
   - Spot-check a sample of judge scores against human review.
   - Add a semantic citation-entailment check on top of the structural check.
   - Expand the Tier 2 question set and keep a held-out part.
5. **Use the source metadata in retrieval.** Authority and currency tiers are stored but only shown to the model. Test filtering or boosting against the existing benchmark before adopting it.
6. **Revisit query expansion** if latency can be cut (cheaper model, caching, or batching). It scored slightly higher on the benchmark.
7. **Split `streamlit_app.py`** (about 1,600 lines) and add tests for `query_cache.py`.
8. **Corpus currency.** Detect changed sources by content hash on a schedule, and add a data-version identifier to the cache key (also noted in Decision 20).
9. **Hardening, only if it is ever deployed:** authentication, HTTPS, secrets management, restricted database exposure, backups.

When any of these change retrieval, prompts or the corpus, record a new dated evaluation instead of overwriting the existing results (see "Safe regeneration rules" in the [runbook](runbook.md)).
