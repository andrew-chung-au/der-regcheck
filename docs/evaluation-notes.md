# Evaluation notes


## Overview


This document tracks retrieval and answer/brief evaluation for DER RegCheck. It covers:
- Evaluation questions and expected sources.
- Retrieval metrics and baseline results.
- LLM answer and evidence-brief evaluation rubric.
- Prompt variants and configuration decisions.


**Status:** Evaluation framework defined; empirical results to be added as experiments are run.


---


## Evaluation questions


### Focused evidence questions


Each focused question targets specific evidence areas and source documents.


#### Q1. Interconnection process overview


**Question:**  
What official material should I review for interconnection, certification, and inadvertent-export requirements for a non-exporting battery system in SCE territory?


**Expected primary sources:**
- `sce_rule21_tariff_pdf` (interconnection and operating requirements)
- `sce_interconnection_handbook_pdf` (process and technical detail)
- `sce_testing_certification_instruction_pdf` (certification process)


**Expected supporting sources:**
- `sce_interconnection_web` (process summary and forms)
- `cpuc_rule21_overview` (regulatory context)


**Sources that should not rank prominently:**
- `siwg_phase2_recommendations_pdf` (historical/draft, not current requirements)


---


#### Q2. Communications and telemetry requirements


**Question:**  
What are the communications, telemetry, monitoring, and control requirements for DER in SCE under Rule 21?


**Expected primary sources:**
- `sce_interconnection_handbook_pdf` (telemetry and communications sections)
- `sce_rule21_tariff_pdf` (governing requirements)


**Expected supporting sources:**
- `siwg_phase2_recommendations_pdf` (historical rationale for communications functions)
- `sce_testing_certification_instruction_pdf` (testing of communications functions)


---


#### Q3. Testing and certification process


**Question:**  
What testing and certification steps are required for DER equipment to interconnect under SCE Rule 21?


**Expected primary sources:**
- `sce_testing_certification_instruction_pdf`
- `sce_interconnection_handbook_pdf` (testing sections)
- `sce_rule21_tariff_pdf` (governing requirements)


---


### Broad market-entry research requests


These requests evaluate the research-plan template and category coverage.


#### R1. Early market assessment for DER communications and control


**Request:**  
Market: California  
Utility: Southern California Edison  
Target customer type: Distribution utility  
Asset types: Solar PV and battery storage  
Capability focus: DER communications and control  
Decision stage: Early market assessment  

What current public sources should we review, which requirement areas appear relevant, and what needs validation before pursuing this opportunity?


**Expected research-plan categories:**
- Primary and technical sources
- Interconnection process
- Technical and operating requirements
- Communications, telemetry, monitoring, and control
- Equipment certification and testing
- Source currency, authority, applicability, and evidence gaps


**Expected primary sources:**
- `sce_rule21_tariff_pdf`
- `sce_interconnection_handbook_pdf`


**Expected supporting sources:**
- `sce_testing_certification_instruction_pdf`
- `sce_interconnection_web`
- `siwg_phase2_recommendations_pdf` (as historical context, not current requirements)


---


## Retrieval evaluation


### Metrics


For focused questions, retrieval will be evaluated using:


- **Document Recall@k:** Whether the required source documents appear in the top-k retrieved documents.
- **Section Recall@k:** Whether the required sections or chunks appear in the top-k retrieved chunks.
- **Mean Reciprocal Rank (MRR):** How early the first relevant chunk appears.
- **Primary-source Recall@k:** Whether primary sources (tariff, handbook) are retrieved in top-k.
- **Historical/draft contamination rate:** Proportion of retrieved chunks from historical/draft sources when the question concerns current requirements.
- **Retrieval latency:** Time to retrieve and rerank candidates.


### Retrieval configurations to compare


1. **Vector-only retrieval**
2. **Lexical/full-text retrieval**
3. **Hybrid retrieval (vector + lexical)**
4. **Hybrid retrieval with reranking**
5. **Hybrid retrieval with source-tier and currency-aware filtering** (planned)


### Baseline results


*To be added after running initial retrieval experiments.*


---


## LLM answer and brief evaluation


### Evaluation rubric


Each generated answer or preliminary evidence brief will be scored on:


#### Groundedness (0–2)
- **0:** Makes claims not supported by retrieved evidence.
- **1:** Mostly grounded but includes minor unsupported inferences.
- **2:** Strictly uses retrieved evidence; no unsupported claims.


#### Citation correctness (0–2)
- **0:** Citations do not support the stated claim or are missing.
- **1:** Most citations are correct but some are imprecise or incomplete.
- **2:** All citations correctly point to supporting evidence with appropriate section/page detail.


#### Source hierarchy (0–2)
- **0:** Treats supporting or historical sources as equivalent to primary requirements.
- **1:** Generally respects hierarchy but occasionally blurs distinctions.
- **2:** Clearly distinguishes primary tariff, primary technical, supporting, and historical sources.


#### Completeness (0–2)
- **0:** Misses material conditions, exceptions, or evidence gaps.
- **1:** Covers most key points but omits some conditions or uncertainty.
- **2:** Captures material conditions, exceptions, uncertainty, and evidence gaps.


#### Category coverage (0–2) — for broad requests only
- **0:** Misses major expected research categories.
- **1:** Covers most categories but omits one or more important areas.
- **2:** Covers all expected research categories appropriately.


#### Usefulness (0–2)
- **0:** Does not clearly direct the user to appropriate sources or actions.
- **1:** Somewhat useful but lacks clear validation actions or source pointers.
- **2:** Clearly directs the user to relevant sources, sections, and validation actions.


**Total score:** Sum of category scores (max 12 for focused questions, max 14 for broad requests).


### Prompt variants to test


*To be defined and tested:*
- Base answer-generation prompt with groundedness and citation instructions.
- Prompt variants emphasising source hierarchy and uncertainty flags.
- Prompt variants for preliminary evidence brief structure.


### Configuration-selection decisions


*To be added after experiments:*
- Selected retrieval configuration (e.g., hybrid + reranking with source-tier filtering).
- Selected LLM model and prompt variant.
- Trade-offs between groundedness, completeness, and usefulness.


---


## Next steps


- Define a small set of labelled evaluation questions with required sections/chunks.
- Run retrieval experiments across configurations and record metrics.
- Generate answers and briefs for each configuration and score using the rubric.
- Document results and configuration-selection decisions in this file.