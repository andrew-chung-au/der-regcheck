# Evaluation notes


## Overview

This document defines the planned retrieval and answer/brief evaluation approach for DER RegCheck.

It covers:

- Evaluation questions and expected source roles
- Retrieval labels, metrics, and configuration comparisons
- Evidence-block and future chunk-level relevance assessment
- LLM answer and preliminary evidence-brief evaluation rubric
- Prompt variants and configuration-selection decisions
- Interpretation of source authority, currency, applicability, and uncertainty

**Status:** Evaluation framework defined. Raw extraction and deterministic normalisation are implemented. Retrieval, chunk-level labels, empirical retrieval results, answer generation, and evidence-brief evaluation results remain to be implemented.


---


## Evaluation prerequisites

Evaluation must use normalised evidence outputs rather than raw extraction outputs.

```text
data/processed/extracted/
→ immutable raw extraction artifacts

data/processed/normalised/
→ deterministic evidence blocks for future chunking and retrieval

future chunk outputs
→ labelled retrieval candidates

future retrieved evidence
→ grounded answer and evidence-brief evaluation
```

Before retrieval evaluation begins:

- Normalised outputs must be reviewed.
- Primary sources must have acceptable heading-path or page-level provenance.
- Each candidate evaluation question must identify expected primary sources.
- Historical/draft sources must be explicitly labelled as acceptable context only where relevant.
- Evaluation labels must distinguish required evidence from merely acceptable supporting material.

Current normalisation review status:

| Source | Evaluation readiness |
|---|---|
| CPUC Rule 21 overview | Available as supporting context and source discovery |
| SCE Rule 21 tariff | Available as primary governing evidence |
| SCE Interconnection Handbook | Available as primary technical evidence |
| SCE Rule 21 web guidance | Available as supporting process evidence |
| SCE testing and certification instruction | Available as supporting implementation evidence, with limited early-page heading-path review flags |
| SIWG Phase 2 Recommendations | Available only as historical/draft context, excluded from default current-requirement retrieval |


---


## Evaluation questions


### Focused evidence questions

Each focused question should target a bounded evidence need. Labels should identify required primary sources, acceptable supporting sources, expected evidence locators, and sources that should not rank prominently.

Future labelled records should be committed under:

```text
data/evaluation/
  retrieval_queries.jsonl
  retrieval_qrels.jsonl
```

Suggested query record shape:

```json
{
  "query_id": "Q1",
  "question": "What official material should I review for interconnection, certification, and inadvertent-export requirements for a non-exporting battery system in SCE territory?",
  "query_type": "focused_evidence",
  "current_requirement_query": true,
  "required_source_ids": [
    "sce_rule21_tariff_pdf",
    "sce_interconnection_handbook_pdf"
  ],
  "acceptable_supporting_source_ids": [
    "sce_testing_certification_instruction_pdf",
    "sce_interconnection_web",
    "cpuc_rule21_overview"
  ],
  "excluded_default_source_ids": [
    "siwg_phase2_recommendations_pdf"
  ]
}
```


#### Q1. Interconnection, certification, and inadvertent export

**Question:**

What official material should I review for interconnection, certification, and inadvertent-export requirements for a non-exporting battery system in SCE territory?

**Question type:** Focused evidence question

**Current-requirement query:** Yes

**Expected primary sources:**

- `sce_rule21_tariff_pdf`
  - Governing interconnection, operating, and metering requirements
  - Inadvertent-export provisions
  - Equipment certification and applicable tariff requirements
- `sce_interconnection_handbook_pdf`
  - Technical implementation detail
  - Protection, operating, metering, and telemetry context

**Expected supporting sources:**

- `sce_testing_certification_instruction_pdf`
  - Testing and certification implementation guidance
- `sce_interconnection_web`
  - Process guidance, forms, and non-export application context
- `cpuc_rule21_overview`
  - Regulatory context and source discovery

**Sources that should not rank prominently:**

- `siwg_phase2_recommendations_pdf`
  - Historical/draft context rather than current requirements

**Expected answer properties:**

- Distinguish governing tariff requirements from supporting process guidance.
- Identify whether project-specific facts are required before a definitive conclusion.
- Direct the user to the tariff, handbook, and testing/certification material.
- State that this is preliminary research support, not legal, engineering, regulatory, or compliance advice.


---


#### Q2. Communications, telemetry, monitoring, and control

**Question:**

What are the communications, telemetry, monitoring, and control requirements for DER in SCE under Rule 21?

**Question type:** Focused evidence question

**Current-requirement query:** Yes

**Expected primary sources:**

- `sce_rule21_tariff_pdf`
  - Governing Rule 21 requirements
  - Applicable smart inverter, communications, monitoring, and telemetry provisions
- `sce_interconnection_handbook_pdf`
  - Technical telecommunications, telemetry, RTU, SCADA, and operating requirements

**Expected supporting sources:**

- `sce_interconnection_web`
  - Customer-Owned Telemetry and process guidance
- `sce_testing_certification_instruction_pdf`
  - Testing and certification implementation context

**Historical source handling:**

- `siwg_phase2_recommendations_pdf` may be retrieved only if the question requests historical rationale, communications evolution, or draft-era context.
- It should not be used as the basis for a current-requirement conclusion.

**Expected answer properties:**

- Separate Rule 21 distribution-level requirements from possible CAISO, WDAT, transmission, or project-specific requirements.
- Distinguish governing requirements from supporting handbook detail.
- Preserve conditions such as generation size, voltage, project type, export status, and interconnection pathway where the source makes them relevant.


---


#### Q3. Testing and certification process

**Question:**

What testing and certification steps are required for DER equipment to interconnect under SCE Rule 21?

**Question type:** Focused evidence question

**Current-requirement query:** Yes

**Expected primary sources:**

- `sce_rule21_tariff_pdf`
  - Governing certification and testing criteria
- `sce_interconnection_handbook_pdf`
  - Technical requirements and implementation context

**Expected supporting source:**

- `sce_testing_certification_instruction_pdf`
  - Testing and certification process guidance

**Expected answer properties:**

- State that the tariff governs where sources conflict.
- Identify whether the instruction sheet is guidance rather than a controlling tariff.
- Preserve equipment type, applicable standards, certification status, and project-specific conditions.
- Flag the need to verify current tariff, utility, and certification-list status before action.


---


#### Q4. Fast Track and Detailed Study path

**Question:**

What Rule 21 review and study paths may apply to an SCE interconnection request, and what evidence should a project team review before selecting a path?

**Question type:** Focused evidence question

**Current-requirement query:** Yes

**Expected primary sources:**

- `sce_rule21_tariff_pdf`
  - Review process and governing procedures
- `sce_interconnection_handbook_pdf`
  - Technical and project-specific implementation context

**Expected supporting source:**

- `sce_interconnection_web`
  - Process explanation, forms, application guidance, and published utility process information

**Expected answer properties:**

- Prioritise tariff evidence over web-page summaries.
- Distinguish Fast Track, supplemental review, and detailed study concepts where supported.
- Avoid asserting project eligibility without project-specific facts and current utility review.


---


### Broad market-entry research requests

These requests evaluate research-plan structure, source hierarchy, category coverage, uncertainty communication, and usefulness for preliminary market-entry research.


#### R1. Early market assessment for DER communications and control

**Request:**

Market: California  
Utility: Southern California Edison  
Target customer type: Distribution utility  
Asset types: Solar PV and battery storage  
Capability focus: DER communications and control  
Decision stage: Early market assessment  

What current public sources should we review, which requirement areas appear relevant, and what needs validation before pursuing this opportunity?

**Request type:** Broad preliminary market-entry research request

**Expected research-plan categories:**

- Primary governing and technical sources
- Interconnection process and applicable pathway
- Technical operating requirements
- Communications, telemetry, monitoring, and control
- Equipment certification and testing
- Source authority, currency, and applicability
- Evidence gaps and project-specific validation needs
- Explicit historical/draft-context handling

**Expected primary sources:**

- `sce_rule21_tariff_pdf`
- `sce_interconnection_handbook_pdf`

**Expected supporting sources:**

- `sce_testing_certification_instruction_pdf`
- `sce_interconnection_web`
- `cpuc_rule21_overview`

**Historical-context source:**

- `siwg_phase2_recommendations_pdf`
  - May support historical rationale only
  - Must not be represented as a current requirement

**Expected answer properties:**

- Present an evidence plan rather than a definitive market-entry conclusion.
- State which conclusions depend on project characteristics, current tariff status, utility review, and applicable interconnection pathway.
- Separate known public evidence from unresolved questions.
- Avoid treating source discovery pages or historical material as equivalent to the tariff.


---


## Retrieval evaluation


### Label design

Each future relevance judgment should distinguish:

- **Required primary evidence:** Evidence that should be retrieved for a complete current-requirement answer.
- **Required technical evidence:** Technical evidence needed to explain or qualify a governing requirement.
- **Acceptable supporting evidence:** Process, implementation, or context material that may help answer the question.
- **Historical context:** Material that may be relevant only when historical rationale is requested.
- **Excluded default evidence:** Historical/draft material that should not rank prominently for current-requirement questions.
- **Not relevant:** Material unrelated to the question.

Suggested future qrel record shape:

```json
{
  "query_id": "Q1",
  "source_id": "sce_rule21_tariff_pdf",
  "locator": {
    "section_ids": ["M"],
    "pdf_page_start": null,
    "pdf_page_end": null
  },
  "relevance_grade": 3,
  "evidence_role": "required_primary",
  "notes": "Required governing source for inadvertent-export requirements."
}
```

Suggested relevance grades:

| Grade | Meaning |
|---:|---|
| 3 | Required evidence for a complete answer |
| 2 | Strong supporting evidence |
| 1 | Helpful context or secondary support |
| 0 | Not relevant |
| -1 | Historical/draft material that should not rank for current-requirement questions |


### Metrics

For focused questions, retrieval should be evaluated using:

- **Document Recall@k:** Whether required source documents appear in the top-k retrieved documents.
- **Evidence Recall@k:** Whether required normalised blocks or future chunks appear in the top-k results.
- **Primary-source Recall@k:** Whether required primary tariff and handbook sources appear in the top-k.
- **Mean Reciprocal Rank (MRR):** How early the first required evidence item appears.
- **nDCG@k:** Ranking quality where graded relevance labels are available.
- **Historical/draft contamination rate:** Proportion of retrieved historical/draft material for current-requirement questions.
- **Authority-weighted Recall@k:** Whether required primary governing evidence appears before merely supporting evidence.
- **Citation-locator coverage:** Proportion of retrieved substantive blocks with usable PDF page or HTML heading-path locators.
- **Retrieval latency:** Time required to retrieve, combine, and rerank candidates.

For broad requests, evaluation should also consider:

- **Source-category coverage:** Whether primary, technical, supporting, and historical categories are appropriately represented.
- **Authority ordering:** Whether governing sources rank above supporting process material.
- **Evidence-gap identification:** Whether retrieval surfaces missing facts or unresolved applicability conditions.


### Retrieval configurations to compare

1. **Lexical/full-text retrieval**
2. **Vector-only retrieval**
3. **Hybrid retrieval**
   - Combined lexical and vector retrieval
   - Preserve component ranks for debugging
4. **Hybrid retrieval with reranking**
5. **Hybrid retrieval with source-tier, currency, and applicability filtering**
6. **Hybrid retrieval with neighbouring-block context expansion**

For early vector experiments:

- Start with exact pgvector nearest-neighbour search.
- Do not add approximate nearest-neighbour indexes until baseline retrieval quality and corpus scale justify them.
- Retain lexical rank, vector rank, combined score, and source metadata in debug output.


### Baseline results

*To be added after chunking, indexing, and initial retrieval experiments.*

Suggested results table:

| Run ID | Corpus version | Chunking version | Retrieval configuration | Query set | Recall@5 | MRR | nDCG@10 | Primary Recall@5 | Historical contamination | Notes |
|---|---|---|---|---|---:|---:|---:|---:|---:|---|
| `TBD` | `TBD` | `TBD` | `TBD` | `TBD` | `TBD` | `TBD` | `TBD` | `TBD` | `TBD` | `TBD` |


---


## LLM answer and evidence-brief evaluation


### Preconditions

Generated-answer evaluation must not begin until:

- A retrieval baseline exists.
- Retrieved evidence retains source and locator metadata.
- The answer generator can cite retrieved evidence blocks or chunks.
- The generation prompt distinguishes source authority, currency, applicability, uncertainty, and historical context.
- The system can state when evidence is insufficient rather than infer unsupported requirements.


### Evaluation rubric

Each generated focused answer or preliminary evidence brief should be scored using the following rubric.


#### Groundedness (0–2)

- **0:** Makes material claims not supported by retrieved evidence.
- **1:** Mostly grounded but includes minor unsupported inference, overstatement, or incomplete qualification.
- **2:** Strictly uses retrieved evidence and clearly labels uncertainty or gaps.


#### Citation correctness (0–2)

- **0:** Citations are missing, incorrect, or do not support stated claims.
- **1:** Most citations are correct but one or more are imprecise, incomplete, or attached to weak support.
- **2:** All material claims cite supporting evidence with appropriate source and locator detail.


#### Source hierarchy and authority (0–2)

- **0:** Treats supporting or historical sources as equivalent to primary governing requirements.
- **1:** Generally respects hierarchy but occasionally blurs governing, technical, supporting, or historical roles.
- **2:** Clearly distinguishes tariff, handbook, supporting guidance, source-discovery material, and historical/draft context.


#### Currency and applicability (0–2)

- **0:** Ignores source currency, project conditions, jurisdiction, utility, or interconnection-pathway applicability.
- **1:** Identifies some applicability limits but omits relevant project-specific conditions or source-currency caveats.
- **2:** Clearly states applicable source scope, current-status caveats, and project facts that require validation.


#### Completeness (0–2)

- **0:** Misses material conditions, exceptions, source conflicts, or evidence gaps.
- **1:** Covers most major points but omits one or more material conditions, exceptions, or validation needs.
- **2:** Captures material conditions, exceptions, uncertainty, and evidence gaps within the requested scope.


#### Category coverage (0–2) — broad requests only

- **0:** Misses major expected research categories.
- **1:** Covers most categories but omits one or more important areas.
- **2:** Covers expected categories appropriately and does not inflate scope with unsupported detail.


#### Usefulness (0–2)

- **0:** Does not direct the user to relevant sources, evidence, or validation actions.
- **1:** Provides useful information but lacks clear evidence priorities, source pointers, or next validation actions.
- **2:** Clearly directs the user to relevant sources, evidence locations, priorities, and project-specific validation actions.


### Total score

| Response type | Applicable categories | Maximum score |
|---|---|---:|
| Focused evidence answer | Groundedness, citation correctness, source hierarchy, currency/applicability, completeness, usefulness | 12 |
| Broad evidence brief | All categories | 14 |


### Critical failure conditions

Regardless of numerical score, mark an answer as failed if it:

- Presents historical/draft SIWG material as a current controlling requirement.
- Contradicts primary tariff evidence without explicitly identifying and explaining the conflict.
- Gives a definitive compliance, legal, regulatory, engineering, or market-entry conclusion without sufficient evidence.
- Omits citations for material factual claims.
- Fails to identify missing project facts where those facts determine applicability.
- Claims that a source is current without checking or disclosing currency limitations.


### Prompt variants to test

*To be defined after retrieval is implemented.*

Candidate variants:

- Base grounded-answer prompt with mandatory citations.
- Prompt with explicit source-hierarchy instructions.
- Prompt with explicit current-versus-historical source handling.
- Prompt requiring an applicability and uncertainty section.
- Prompt requiring an evidence-gap and validation-actions section.
- Preliminary market-entry evidence-brief template.
- Concise evidence-answer template for focused questions.


### Configuration-selection decisions

*To be added after experiments.*

Record:

- Selected chunking configuration
- Selected embedding model and dimension
- Selected lexical retrieval configuration
- Selected hybrid retrieval method and score fusion approach
- Whether reranking is used
- Source-tier, currency, and applicability filtering rules
- Selected answer-generation model
- Selected prompt variant
- Trade-offs between groundedness, completeness, latency, cost, and usefulness


---


## Evaluation artifacts

Future committed evaluation artifacts should include:

```text
data/evaluation/
  retrieval_queries.jsonl
  retrieval_qrels.jsonl
  answer_eval_cases.jsonl
  retrieval_results/
  answer_results/

docs/
  evaluation-notes.md
```

Evaluation records should be reproducible without requiring raw corpus downloads, runtime feedback data, or external API credentials where feasible.


---


## Next steps

- Review and accept the normalised evidence outputs.
- Implement deterministic, section-aware chunk assembly over normalised blocks.
- Preserve citation-grade evidence text separately from embedding-oriented context text.
- Add source authority, retrieval tier, currency, and applicability metadata to future chunks.
- Create the initial labelled query and relevance set.
- Implement PostgreSQL with pgvector.
- Establish lexical, vector-only, and hybrid retrieval baselines.
- Add reranking and source-aware filtering only after baseline evaluation.
- Generate grounded answers and preliminary evidence briefs.
- Score answers and briefs using this rubric.
- Record empirical results and configuration-selection decisions in this document.