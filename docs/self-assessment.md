# Self-assessment — DER RegCheck

This document maps the current DER RegCheck project state to the peer-review evaluation criteria. It is intended to provide an honest, easy-to-check evidence trail for reviewers and to identify remaining improvement areas.

For the project overview, architecture, and rubric evidence map, see the [README](../README.md).
For complete local reproduction and Docker Compose commands, see the [runbook](runbook.md).
For retrieval and answer-generation results, see the [evaluation notes](evaluation-notes.md).

---

## Live application

The application runs locally via Docker Compose and is temporarily deployed on AWS EC2 for peer-review demonstration. Reviewers can access the live Streamlit application at **[http://100.30.163.97:8501/](http://100.30.163.97:8501/)**. The deployment will be decommissioned after the review period.

**Local runtime (Docker Compose):**

- PostgreSQL with pgvector for the knowledge base and observability tables
- Streamlit application running the selected v3 RAG path:
  - Original-query vector retrieval plus local cross-encoder reranking
  - `v3_few_shot_grounded_rag` prompt with deterministic citation validation
  - Configuration-aware answer cache, feedback capture, manual-review workflow, and seven-chart Monitoring dashboard

The local Docker Compose stack is the authoritative runtime for reviewer reproduction. The EC2 deployment uses the same Compose configuration for demonstration purposes only.

**Important:** This project is a research-support prototype. It does not provide legal, regulatory, engineering, or compliance advice. The EC2 deployment is a temporary demonstration environment and is not hardened for production use.

---

## Reviewer quick check

A reviewer can verify the main implemented capabilities through the live deployment or by reproducing the local Docker Compose stack.

### Live review path

1. Open the **[live DER RegCheck application](http://100.30.163.97:8501/)**.
2. Select **Ask**.
3. Choose a Tier 2 example question or paste a DER interconnection or market-entry research question.
4. Inspect the returned structured answer, answer status, uncertainty statement, and retrieved evidence cards with source class, heading path, and page/section locators.
5. Open **Evidence** to inspect the preserved evidence excerpts, source hierarchy, final retrieval ranks, and locators.
6. Open **Review** to inspect the Tier 2 manual-review workflow and five 1–5 scoring dimensions.
7. Open **Monitoring** to inspect PostgreSQL-backed telemetry, including answer-status distribution, feedback events, manual-review coverage, cache-miss generation latency, and Tier 2 coverage.
8. Use the [README assessment evidence map](../README.md#assessment-evidence) and [decisions.md](decisions.md) to locate implementation and evaluation evidence for each criterion.

### Local reproduction path

For full local reproduction, start the Docker Compose stack as described in the [runbook](runbook.md), then open:

```text
http://localhost:8501
```

The local Docker Compose stack remains the authoritative reproducibility path. The EC2 deployment is a temporary reviewer-facing demonstration of the same application architecture.

---

## Score summary

**Self-assessed core score: 18/18**

**Implemented bonus features:**

- Hybrid search evaluation — +1
- Document reranking — +1
- User query rewriting — +1
- Cloud deployment — +2 (temporary EC2 deployment for peer-review demonstration)

**Total self-assessed score:** 21/23

**Extra Bonus Points:** (Up to 3)
- Two-tier evaluation (100-query retrieval benchmark + 10-question Tier 2 RAG-quality set) with production-aligned PostgreSQL/pgvector results and explicit old-vs-new separation.
- Deterministic 100% citation-validity guardrail for prompt selection; higher-scoring prompts with any invalid citations are rejected.
- Comprehensive evaluation grid (7,500 retrieval + 8,000 query-rewrite records) with JSONL checkpointing, resumable runs, and regression tests.
- RAG-impact evaluation: four-condition impact study on the 10-question Tier 2 set quantifying retrieval and evidence grounding contribution.
- Source hierarchy and currency awareness in chunks; historical/draft material excluded from default current-requirement retrieval.
- Fail-closed citation validation against the evidence pack; unknown/invalid citations cause the answer to be rejected rather than hallucinated.
- Content-hash tracking, manual-replacement workflow for blocked sources, and safe regeneration rules that preserve evaluation comparability.
- Observability beyond "five charts": seven monitoring charts with safe empty states, truthful cache-miss latency, and multiple feedback/review events per cached answer.
- Regression tests across normalisation, chunking, quality checks, retrieval evaluation, summarisation, and answer-generation citation validation.
- Clean documentation separation (README, project log, decisions, dataset notes, evaluation notes, runbook) with 21 decision records and explicit trade-offs.

See the [Extra Bonus Points (case for additional marks)](#extra-bonus-points-case-for-additional-marks) section below for more details.

| Criterion | Self-assessed score | Summary |
|---|---:|---|
| Problem description | 2/2 | Clear problem, users, scope, and retrieval rationale |
| Retrieval flow | 2/2 | DER knowledge base plus grounded LLM answer generation |
| Retrieval evaluation | 2/2 | Lexical, vector, hybrid, reranked, and query-rewrite retrieval evaluated; best backend selected |
| LLM evaluation | 2/2 | Multiple prompt configurations evaluated with deterministic citation validation and LLM judge; best prompt selected |
| Interface | 2/2 | Streamlit UI deployed for reviewer access (local Docker Compose) |
| Ingestion pipeline | 2/2 | Fully automated scripted ingestion via Docker Compose (no dedicated orchestrator required) |
| Monitoring | 2/2 | PostgreSQL-backed user feedback plus seven live telemetry charts and safe empty states |
| Containerization | 2/2 | Database and application services run through Docker Compose |
| Reproducibility | 2/2 | Accessible processed data, pinned dependencies, runbook, corpus snapshot, and Docker runtime |
| Hybrid search | +1 | Implemented and evaluated |
| Document reranking | +1 | Implemented, evaluated, and selected as default retrieval |
| User query rewriting | +1 | Implemented and evaluated; retained as experimental due to latency |
| Cloud deployment | +2 | Temporary EC2 deployment for peer-review demonstration |

---

## Criterion definitions

### Problem description

- **0 points:** The problem is not described.
- **1 point:** The problem is described but briefly or unclearly.
- **2 points:** The problem is well-described and it is clear what problem the project solves.

### Retrieval flow

- **0 points:** No knowledge base or LLM is used.
- **1 point:** No knowledge base is used, and the LLM is queried directly.
- **2 points:** Both a knowledge base and an LLM are used in the flow.

### Retrieval evaluation

- **0 points:** No evaluation of retrieval is provided.
- **1 point:** Only one retrieval approach is evaluated.
- **2 points:** Multiple retrieval approaches are evaluated, and the best one is used.

### LLM evaluation

- **0 points:** No evaluation of final LLM output is provided.
- **1 point:** Only one approach, such as one prompt, is evaluated.
- **2 points:** Multiple approaches are evaluated, and the best one is used.

### Interface

- **0 points:** No way to interact with the application at all.
- **1 point:** Command line interface, a script, or a Jupyter notebook.
- **2 points:** A UI, web application, or API is available.

### Ingestion pipeline

- **0 points:** No ingestion.
- **1 point:** Semi-automated ingestion of the dataset into the knowledge base, such as with scripts or a notebook.
- **2 points:** Automated ingestion with a dedicated orchestration tool, such as Kestra, dlt, Airflow, or Prefect.
  *Course guidance: a fully automated scripted pipeline (e.g., via Docker Compose) satisfies the 2/2 requirement.*

### Monitoring

- **0 points:** No monitoring.
- **1 point:** User feedback is collected or a monitoring dashboard exists.
- **2 points:** User feedback is collected and a dashboard contains at least five charts.

### Containerization

- **0 points:** No containerization.
- **1 point:** A Dockerfile is provided for the main application, or Docker Compose is used only for dependencies.
- **2 points:** The complete runtime is defined in Docker Compose.

### Reproducibility

- **0 points:** No instructions are provided, data is missing, or access is unclear.
- **1 point:** Instructions are incomplete, or code works but data is missing.
- **2 points:** Instructions are clear, the dataset is accessible, the project is easy to run, and dependency versions are specified.

---

## Problem description — 2/2

The project addresses a clear problem: teams researching distributed energy resource (DER) products, projects, or market opportunities must locate, read, compare, and interpret a fragmented set of public documents. Depending on the research context, relevant information may be distributed across a regulator's overview page, a utility tariff, an interconnection handbook, a testing/certification instruction sheet, utility web guidance, and historical standards or working-group reports.

DER RegCheck provides a retrieval-augmented assistant over a curated California Rule 21 / SCE corpus. Rather than relying on general LLM advice alone, it retrieves relevant tariff, handbook, and supporting material and generates answers grounded in that material, explicitly surfacing uncertainty, source hierarchy, and evidence for analyst review.

**Evidence:**

- [README problem statement](../README.md#problem-statement)
- [README overview](../README.md#overview)
- [Dataset notes](dataset-notes.md)
- [Architecture decisions](decisions.md)

---

## Retrieval flow — 2/2

The project uses both a knowledge base and an LLM-supported answer flow.

Public CPUC and SCE documents are downloaded, extracted, normalised, chunked, and embedded into PostgreSQL with pgvector. The selected UI path retrieves evidence using vector retrieval plus local cross-encoder reranking, then generates a structured answer from the top reranked chunks using the `v3_few_shot_grounded_rag` prompt with deterministic citation validation.

The LLM is also used in supporting evaluation stages, including synthetic query generation, answer generation, and LLM-as-judge scoring.

**Evidence:**

- `data/processed/chunks/`
- `data/processed/embeddings/`
- `src/ingestion/download_california_rule21_docs.py`
- `src/ingestion/extract_raw_content.py`
- `src/processing/normalise_documents.py`
- `src/processing/chunk_documents.py`
- `src/processing/embed_chunks.py`
- `src/database/db_init.py`
- `src/scripts/load_chunks_to_db.py`
- `src/retrieval/retrieve.py`
- `src/retrieval/rerank.py`
- `src/generation/answer_generator.py`
- `src/llm_client.py`
- `src/ui/streamlit_app.py`

---

## Retrieval evaluation — 2/2

Retrieval quality is evaluated across multiple approaches using a fixed 100-query synthetic benchmark:

- PostgreSQL lexical (full-text) retrieval
- pgvector vector retrieval
- PostgreSQL-backed hybrid retrieval (lexical + vector)
- Vector retrieval plus local cross-encoder reranking
- Query rewriting (original, expanded, HyDE, HyDE-expanded) plus vector retrieval and reranking

The benchmark is built from LLM-generated queries over sampled chunks, with metadata-derived relevance labels. Retrieval evaluation reports metrics including nDCG@10, MRR, Recall@10, and a composite score.

Vector-plus-reranking performed best on the current benchmark and is therefore used as the default downstream retrieval path in the UI and answer-generation workflow. Query expansion improved metrics slightly but introduced unacceptable latency for interactive use and is retained as an evaluated experimental capability.

**Evidence:**

- `src/evaluation/evaluate_retrieval.py`
- `src/evaluation/summarise_evaluation.py`
- `src/evaluation/generate_query_rewrites.py`
- `data/evaluation/queries.jsonl`
- `data/evaluation/evaluation_results_postgres.jsonl`
- `data/evaluation/evaluation_summary_postgres.json`
- `data/evaluation/query_rewrite_results_postgres.jsonl`
- `data/evaluation/query_rewrite_summary_postgres.json`
- [Evaluation notes](evaluation-notes.md)
- [README retrieval and evaluation](../README.md#retrieval-evaluation)

---

## LLM evaluation — 2/2

The project compares multiple answer-generation prompt configurations using a fixed 24-question set and a consistent LLM-as-judge setup with deterministic citation validation.

The evaluated answer artefacts include:

- `data/evaluation/llm_answers.jsonl`
- `data/evaluation/llm_judge_scores.jsonl`
- `data/evaluation/llm_evaluation_summary.json`
- `data/evaluation/llm_evaluation_report.md`

The evaluation compared:

- `v1_direct_rag`
- `v2_structured_grounded_rag`
- `v3_few_shot_grounded_rag`

All 72 intended unique answer evaluations (24 questions × 3 prompts) were checked for deterministic citation validity and scored by an LLM judge on five dimensions. `v3_few_shot_grounded_rag` achieved 100% citation validity (the only configuration to meet the guardrail) and is selected as the default answer-generation prompt.

This satisfies "multiple approaches are evaluated, and the best one is used" under the criterion.

**Evidence:**

- `src/evaluation/evaluate_llm_answers.py`
- `src/evaluation/summarise_llm_evaluation.py`
- `data/evaluation/llm_evaluation_questions.yaml`
- `data/evaluation/llm_answers.jsonl`
- `data/evaluation/llm_judge_scores.jsonl`
- `data/evaluation/llm_evaluation_summary.json`
- `data/evaluation/llm_evaluation_report.md`
- [Evaluation notes](evaluation-notes.md)
- [Decision 14](decisions.md#14-llm-answer-evaluation-and-prompt-configuration-selection)

---

## Interface — 2/2

The project provides both command-line workflows and a deployed Streamlit UI.

The Streamlit application in `src/ui/streamlit_app.py` provides:

- **About** — project overview, data sources, and responsible-use boundary
- **Ask** — DER research question input, vector-plus-rerank retrieval, structured answer generation, evidence inspection, and feedback capture
- **Evidence** — expandable evidence cards with source class, heading path, and page/section locators
- **Review** — Tier 2 realistic RAG-quality manual-review workflow with 1–5 scoring on five dimensions
- **Monitoring** — PostgreSQL-backed runtime telemetry dashboard with seven operational views

The application is accessible locally via Docker Compose and temporarily through the **[live EC2 demonstration deployment](http://100.30.163.97:8501/)** for peer review.

**Evidence:**

- **[Live EC2 demonstration deployment](http://100.30.163.97:8501/)**
- `src/ui/streamlit_app.py`
- `.streamlit/config.toml`
- [Runbook](runbook.md)

---

## Ingestion pipeline — 2/2

The ingestion pipeline is fully automated and reproducible through scripted tools and Docker Compose:

1. A downloader fetches public CPUC and SCE documents and records provenance in `corpus_metadata.json`.
2. An extractor produces page-preserving PDF text and main-content HTML as JSON.
3. A normaliser derives deterministic evidence blocks with source-specific rules.
4. A chunker transforms evidence blocks into searchable chunks with citation metadata.
5. An embedder generates 768-dimensional Nomic vectors.
6. Scripts create PostgreSQL schema, load chunk records, and load embeddings.
7. Docker Compose provides an automated runtime for the database and application.

This satisfies the course guidance that a fully automated scripted pipeline (e.g., via Docker Compose) qualifies for 2/2, even without a dedicated orchestration tool.

**Evidence:**

- `data/corpus/corpus_metadata.json`
- `src/ingestion/download_california_rule21_docs.py`
- `src/ingestion/extract_raw_content.py`
- `src/processing/normalise_documents.py`
- `src/processing/chunk_documents.py`
- `src/processing/embed_chunks.py`
- `src/database/db_init.py`
- `src/scripts/load_chunks_to_db.py`
- `compose.yaml`
- [Dataset notes](dataset-notes.md)
- [Runbook](runbook.md)

---

## Monitoring — 2/2

The Streamlit application includes user-feedback collection and a PostgreSQL-backed runtime telemetry dashboard.

After a successful answer generation, the Ask workflow writes a `query_cache` record to PostgreSQL. This record stores the question text, configuration hash, generated answer status and structured fields, claims and evidence gaps, evidence snapshot, and cache-miss generation latency. Logging occurs independently of whether the user submits feedback.

When a user selects **Helpful** or **Not helpful**, the application writes the optional rating to the `answer_feedback` table, linked to the original query through `cache_id`.

The Monitoring tab queries live telemetry and provides seven charts:

1. **Answer-status distribution**
2. **Helpful versus not-helpful feedback distribution**
3. **Average manual-review scores by quality dimension**
4. **Cache-miss generation latency over time**
5. **Average cache-miss generation latency by answer status**
6. **Cached query volume over time**
7. **Tier 2 manual-review coverage**

All charts have safe empty states for fresh databases.

**Evidence:**

- `src/database/db_init.py`
- `src/observability/query_cache.py`
- `src/ui/streamlit_app.py`
- PostgreSQL tables: `query_cache`, `answer_feedback`, `manual_scores`
- [Runbook](runbook.md)

---

## Containerization — 2/2

The complete application runtime is defined through Docker Compose.

The Compose configuration includes:

- `db` — PostgreSQL with pgvector
- `app` — Streamlit application service

The repository also includes a `Dockerfile` for the application image, named volumes for PostgreSQL, health checks, and Docker ignore rules.

**Evidence:**

- `Dockerfile`
- `compose.yaml`
- `.dockerignore`
- [Runbook Docker and deployment instructions](runbook.md)

---

## Reproducibility — 2/2

The project provides clear reproduction paths from a clean checkout.

Reproducibility support includes:

- Public CPUC and SCE source URLs defined in `data/corpus/corpus_metadata.json`
- A reviewed processed-artifact snapshot (`data/processed/`) for strict baseline reproduction
- A fresh source-download and extraction path for corpus refresh
- Pinned Python dependencies in `pyproject.toml` and `uv.lock`
- Documented `uv` commands for the local workflow
- A Docker Compose runtime for the database and application
- A committed Streamlit configuration
- Step-by-step setup, evaluation, reset, and troubleshooting instructions

A reviewer can follow the runbook to reproduce the corpus, index, retrieval evaluation, and local UI runtime.

**Evidence:**

- [README setup](../README.md#how-to-run)
- [README usage](../README.md#running-the-system)
- [Runbook](runbook.md)
- `pyproject.toml`
- `uv.lock`
- `Dockerfile`
- `compose.yaml`
- `data/corpus/corpus_metadata.json`
- `data/processed/`

---

## Bonus implementation categories

### Hybrid search — implemented and evaluated

Hybrid retrieval combines lexical (PostgreSQL full-text) and vector (pgvector) results through reciprocal rank fusion. It was evaluated against the same benchmark as the other retrieval backends.

Hybrid retrieval improved slightly over lexical-only retrieval on some metrics but did not outperform vector-plus-reranking. It is retained as an evaluated alternative and debugging aid rather than being selected as the default.

**Evidence:**

- `src/retrieval/retrieve.py` (hybrid variant)
- `src/evaluation/evaluate_retrieval.py`
- `data/evaluation/evaluation_results_postgres.jsonl`
- [Evaluation notes](evaluation-notes.md)

### Document reranking — implemented and selected

The project implements chunk reranking through `src/retrieval/rerank.py`.

Vector-plus-reranking outperformed lexical, plain vector, and hybrid alternatives on the current benchmark. It is therefore the selected default retrieval backend for the Streamlit UI and current answer-generation path.

**Evidence:**

- `src/retrieval/rerank.py`
- `src/evaluation/evaluate_retrieval.py`
- `src/ui/streamlit_app.py`
- [Evaluation notes](evaluation-notes.md)

### User query rewriting — implemented and evaluated

Query rewriting is implemented through `src/retrieval/query_expansion.py` and was evaluated across original-query and expanded-query configurations with vector-plus-reranking.

Query expansion improved retrieval metrics slightly but introduced unacceptable latency for interactive use. It was not adopted as the default but remains available for experimentation and future re-evaluation.

Not selecting expansion as the production default reflects the evaluation result; the capability is still implemented and evaluated.

**Evidence:**

- `src/retrieval/query_expansion.py`
- `src/evaluation/generate_query_rewrites.py`
- `src/evaluation/evaluate_retrieval.py`
- `data/evaluation/query_rewrite_results_postgres.jsonl`
- `data/evaluation/query_rewrite_summary_postgres.json`
- [Evaluation notes](evaluation-notes.md)
- [Decision 13](decisions.md#13-runtime-configuration-disable-query-expansion-for-latency)

### Cloud deployment — implemented and live (+2)

The application has been deployed to a lightweight Ubuntu-based AWS EC2 instance for reviewer demonstration during the peer-review period.

The instance runs the same Docker Compose stack used for local reproduction:

- `db` — PostgreSQL with pgvector
- `app` — Streamlit application service

The deployment is a temporary demonstration environment. It does not include HTTPS, a custom domain, or managed secrets. It is intended for reviewer access and portfolio demonstration only, and will be decommissioned after the review period.

**Evidence:**

- **[Live DER RegCheck application on AWS EC2](http://100.30.163.97:8501/)**
- `Dockerfile`
- `compose.yaml`
- [Runbook](runbook.md)
- [README live demo](../README.md#live-demo)

---

## Extra Bonus Points (case for additional marks)

Beyond the standard and bonus criteria, the project includes several elements that go beyond the rubric's expectations. These are presented as a coherent case for discretionary recognition rather than as a self-scored checklist.

### Evaluation depth and methodological care

- **Two-tier evaluation strategy:**  
  A fixed 100-query retrieval benchmark plus a separate 10-question Tier 2 realistic RAG-quality set. This separates configuration selection from human-judged answer quality, which is more rigorous than a single benchmark.
- **Production-aligned evaluation:**  
  The authoritative retrieval evaluation uses the deployed PostgreSQL/pgvector path (runtime embeddings, vector retrieval, and reranking), not a separate in-memory evaluator. Historical file-based results are retained as baselines but explicitly not compared numerically with the production-aligned results.
- **Deterministic citation guardrail:**  
  Answer-generation selection uses a hard 100% citation-validity guardrail. A prompt with higher composite score but any invalid citations is rejected on safety grounds. This is a stricter selection rule than "best average score".
- **Comprehensive configuration grid:**  
  7,500 retrieval records (100 queries × 3 alphas × 5 variants × 5 weightings) plus 8,000 query-rewrite records, with JSONL checkpointing, resumable runs, and regression tests for the evaluators and summarisers.
- **RAG-impact evaluation:**  
  A separate four-condition impact study (naive model-only, no-evidence v3, zero-shot RAG, and full v3 RAG) on the 10-question Tier 2 set quantifies the contribution of retrieval and evidence grounding to answer quality. Blinded pairwise judging shows both evidence-backed RAG configurations strongly outperforming the no-evidence baseline.

### Safety, governance, and responsible use

- **Source hierarchy and currency awareness:**  
  Chunks encode authority tier (governing tariff vs technical handbook vs supporting guidance vs historical/draft) and retrieval tier. Historical SIWG material is excluded from default current-requirement retrieval and only surfaced when explicitly requested.
- **Fail-closed citation behaviour:**  
  The generation pipeline validates every citation against the supplied evidence pack. Unknown or invalid citation labels cause the answer to fail closed rather than hallucinate sources.

### Reproducibility and data governance

- **Content-hash tracking and manual replacement workflow:**  
  Every source has content hashes, last-checked timestamps, automated validation status, and manual-review status. A blocked handbook PDF is handled via a documented manual-replacement workflow with explicit reviewer approval.
- **Safe regeneration rules:**  
  The runbook defines how to refresh the corpus without breaking comparability of evaluation results, including when to create a new dated evaluation rather than silently replacing artifacts.

### Engineering quality and operational discipline

- **Observability beyond "five charts":**  
  Seven monitoring charts with safe empty states, truthful cache-miss latency interpretation, and explicit separation of cache hits vs full RAG path latency. Multiple feedback and manual-review events can be linked to a single cached answer.
- **Regression tests across the pipeline:**  
  Tests cover normalisation, chunking, quality checks, retrieval evaluation, summarisation, and answer-generation citation validation. This is more than "it runs"; it supports iterative change with confidence.

### Documentation quality

- **Clear separation of concerns across docs:**  
  `README.md` (public story), `project-log.md` (working journal), `decisions.md` (design rationale), `dataset-notes.md` (corpus and processing), `evaluation-notes.md` (methods and results), and `runbook.md` (reproduction and operations).
- **Decision records with alternatives and trade-offs:**  
  Twenty documented decisions, including why PostgreSQL results are authoritative, why query expansion is disabled at runtime, why v3 prompt was selected, and why processed artifacts are committed while raw sources are not.

---

## Strengths

The strongest parts of the project are currently:

- A clearly scoped and well-documented problem
- A real knowledge-base-plus-LLM RAG flow rather than direct prompting
- Comparative retrieval evaluation across multiple backends and query-rewrite variants
- Deterministic citation validation plus LLM-judge scoring for prompt selection
- Selected defaults based on recorded benchmark results
- A deployed Streamlit interface with inspectable evidence and explicit source hierarchy
- PostgreSQL-backed query telemetry, linked user-feedback capture, seven live telemetry charts, and safe empty states
- Full Docker Compose runtime coverage
- Reproducible local deployment documentation
- Explicit separation of raw source acquisition from committed processed artifacts

---

## Remaining gaps

The main remaining limitations are:

- The benchmark is synthetic and relatively small, so results should not be interpreted as broad real-world performance claims.
- Query expansion is implemented but not part of the default interactive path due to latency.
- Tier 2 aggregate human-review results are not yet stable until sufficient manual scores have been collected.
- Source-aware filtering by authority tier and currency is not yet implemented in the runtime retrieval path.
- The local deployment is a research prototype without production hardening (HTTPS, custom domain, managed secrets, backups, or high availability).

---

## Next steps

Potential next improvements are:

- Expand evaluation with more diverse or human-authored questions while preserving a held-out test set.
- Collect sufficient Tier 2 manual reviews to produce stable aggregate human-review results.
- Investigate source-aware filtering and tier-based retrieval constraints only when evaluated against the existing benchmark.
- Maintain clear Docker documentation for first-time bootstrap, normal restart, and full-reset workflows.
- If the project evolves beyond a portfolio demonstration, consider production hardening: HTTPS termination, restricted security-group rules, managed secrets, backups, and operational monitoring.

This document should be updated when the implementation or evidence changes. The criterion definitions should remain stable so changes in project maturity are easy to track.