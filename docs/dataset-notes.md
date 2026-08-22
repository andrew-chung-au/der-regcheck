# Dataset notes


## Corpus overview

**Market:** California, United States
**Regulator:** California Public Utilities Commission (CPUC)
**Primary utility:** Southern California Edison (SCE)
**Topic:** DER interconnection, technical requirements, communications/telemetry, testing, and certification
**Corpus role:** v1 research corpus for the DER RegCheck evidence-first RAG prototype
**Total sources:** 6 public documents: 5 PDF and 1 HTML


---


## Data lifecycle

DER RegCheck preserves separate, tracked representations of source content:

```text
data/corpus/
→ source downloads and manual replacements

data/processed/extracted/
→ raw deterministic extraction outputs

data/processed/normalised/
→ deterministic evidence-block derivatives for future chunking and retrieval
```

### Raw corpus files

Raw downloaded files in `data/corpus/` are ignored by Git.

Trust and eligibility are controlled by `data/corpus/corpus_metadata.json`, not by file location. Metadata records:

- Content hash
- Last-checked timestamp
- Automated validation status
- Manual review status
- Manual reviewer identity where applicable
- Extraction eligibility
- Default retrieval eligibility
- Acquisition method

### Raw extraction outputs

Raw extraction outputs in `data/processed/extracted/` are intentionally tracked.

They preserve source evidence without applying chunking, source authority policy, LLM enrichment, embeddings, retrieval ranking, or answer generation.

Raw extraction metadata includes:

- `schema_version`
- `extraction_method`
- Source ID
- Source content hash
- Source URL
- Extraction timestamp
- PDF physical pages or HTML blocks
- PDF page markers or HTML heading paths

### Normalised evidence outputs

Normalised outputs in `data/processed/normalised/` are intentionally tracked.

They are deterministic derivatives of raw extraction outputs and are the intended input to future structural chunking and retrieval stages.

Normalised blocks preserve:

- Source ID and source content hash
- Stable block order
- Block type
- Evidence text
- PDF physical page locator or HTML heading-path locator
- Source-specific citation metadata where available
- Normalisation flags for known review limitations

The normalisation stage does not alter raw extraction artifacts.


---


## Source list


### 1. CPUC Electric Rule 21 overview page

- **Source ID:** `cpuc_rule21_overview`
- **URL:** [https://www.cpuc.ca.gov/Rule21/](https://www.cpuc.ca.gov/Rule21/)
- **Type:** HTML
- **Corpus role:** Regulatory context and discovery of authoritative sources
- **Default retrieval tier:** `source_discovery`
- **Authority level:** Regulatory overview; not controlling tariff text
- **Filename:** `01_cpuc_rule21_overview.html`
- **Local path:** `data/corpus/01_cpuc_rule21_overview.html`
- **Raw extraction method:** `beautifulsoup_main_content_blocks`
- **Normalisation status:** Pass
- **Extraction issues:** None identified in the current review.
- **Normalisation notes:** Preserves HTML heading paths, paragraphs, list items, and tables. The table-of-contents heading path is excluded from normalised evidence output.
- **Notes:** Provides links to tariff, handbooks, and related CPUC pages. Useful for context and source discovery, not treated as a primary requirements source.


---


### 2. SCE Rule 21 tariff (PDF)

- **Source ID:** `sce_rule21_tariff_pdf`
- **URL:** [https://www.sce.com/sites/default/files/custom-files/PDF_Files/ELECTRIC_RULES_21.pdf](https://www.sce.com/sites/default/files/custom-files/PDF_Files/ELECTRIC_RULES_21.pdf)
- **Type:** PDF
- **Corpus role:** Primary interconnection requirements
- **Default retrieval tier:** `primary_requirements`
- **Authority level:** Primary tariff / governing source
- **Filename:** `02_sce_rule21_tariff.pdf`
- **Local path:** `data/corpus/02_sce_rule21_tariff.pdf`
- **Raw extraction method:** `pypdf_page_text`
- **Normalisation status:** Pass
- **Extraction issues:** PDF signature validation passes.
- **Normalisation notes:**
  - Uses a dedicated deterministic SCE Rule 21 tariff parser.
  - Removes recurring administrative Cal. PUC sheet material from normalised evidence blocks.
  - Excludes Table of Contents pages from normalised evidence blocks.
  - Preserves tariff hierarchy across lettered sections, numbered provisions, lettered subsections, selected Roman-numeral subheadings, and appendices.
  - Retains prose-style Roman-numeral entries as list items.
  - Resets hierarchy at appendices, including `APPENDIX B`.
  - Preserves Rule 21 sheet number, Cal. PUC sheet number, effective date, and advice letter as citation metadata.
- **Known limitation:** Raw `pypdf` layout artifacts can preserve spaces inside words. These are retained in citation-grade evidence text rather than automatically repaired.
- **Notes:** Controlling document for interconnection, operating, and metering requirements. Contains sheet-level supersession cues such as `Cancelling Revised Cal. PUC Sheet No.`.


---


### 3. SCE Interconnection Handbook (PDF)

- **Source ID:** `sce_interconnection_handbook_pdf`
- **URL:** [https://on.sce.com/InterconnectionHandbook](https://on.sce.com/InterconnectionHandbook)
- **Type:** PDF
- **Corpus role:** Technical implementation detail
- **Default retrieval tier:** `primary_technical`
- **Authority level:** Primary technical handbook; secondary to the tariff in the event of conflict
- **Filename:** `03_sce_interconnection_handbook.pdf`
- **Local path:** `data/corpus/03_sce_interconnection_handbook.pdf`
- **Raw extraction method:** `pypdf_page_text`
- **Normalisation status:** Pass
- **Extraction issues:**
  - Automated download intermittently returns HTML or SharePoint authentication material instead of a PDF.
  - Repeated automated requests triggered what appeared to be a temporary block.
  - The source was manually replaced and approved through corpus metadata.
- **Normalisation notes:**
  - Excludes cover, approval, table-of-contents, and DocuSign certificate pages.
  - Removes repeated document-control notices, version headers, effective-date headers, DocuSign envelope IDs, and `Requirement | Page N` page-header text.
  - Preserves PDF physical page locators and detected Part, Section, and clause hierarchy.
- **Notes:** Covers interconnection process details, protection requirements, telemetry, inverter performance, communications, metering, and testing-related requirements. Critical for technical research questions.


---


### 4. SCE Rule 21 interconnection web guidance

- **Source ID:** `sce_interconnection_web`
- **URL:** [https://www.sce.com/business/smart-energy-solar/solar-for-business/grid-interconnections/interconnecting-generation-under-rule-21](https://www.sce.com/business/smart-energy-solar/solar-for-business/grid-interconnections/interconnecting-generation-under-rule-21)
- **Type:** HTML
- **Corpus role:** Process guidance, forms, and source discovery
- **Default retrieval tier:** `supporting_process`
- **Authority level:** Supporting process guidance; not controlling
- **Filename:** `04_sce_interconnection_web.html`
- **Local path:** `data/corpus/04_sce_interconnection_web.html`
- **Raw extraction method:** `beautifulsoup_main_content_blocks`
- **Normalisation status:** Pass
- **Extraction issues:** None identified in the current review.
- **Normalisation notes:** Preserves HTML heading paths, paragraphs, list items, and tables.
- **Notes:** Summarises Rule 21 process, links to forms, testing information, pre-application information, study tracks, and Customer-Owned Telemetry procedures. Useful for process questions but not treated as a primary requirements source.


---


### 5. Smart Inverter Working Group Phase 2 Recommendations (PDF)

- **Source ID:** `siwg_phase2_recommendations_pdf`
- **URL:** [https://www.cpuc.ca.gov/-/media/cpuc-website/divisions/energy-division/documents/rule21/smart-inverter-working-group/siwg_phase_2.pdf](https://www.cpuc.ca.gov/-/media/cpuc-website/divisions/energy-division/documents/rule21/smart-inverter-working-group/siwg_phase_2.pdf)
- **Type:** PDF
- **Corpus role:** Historical context and standards rationale
- **Default retrieval tier:** `historical_context`
- **Authority level:** Historical/draft material; excluded from default current-requirement retrieval
- **Filename:** `05_siwg_phase2_recommendations.pdf`
- **Local path:** `data/corpus/05_siwg_phase2_recommendations.pdf`
- **Raw extraction method:** `pypdf_page_text`
- **Normalisation status:** Review
- **Extraction issues:** PDF signature validation passes.
- **Normalisation notes:**
  - Excludes cover and contents pages.
  - Retains physical PDF page provenance.
  - Six early substantive blocks remain flagged with `no_detected_heading_path`.
- **Notes:** Provides historical rationale for smart inverter functions, communications, and data categories. It must not be presented as a current controlling requirement unless a user explicitly requests historical or draft context.


---


### 6. SCE testing and certification instruction sheet (PDF)

- **Source ID:** `sce_testing_certification_instruction_pdf`
- **URL:** [https://www.sce.com/sites/default/files/custom-files/PDF_Files/Rule_21_Testing_and_Certification_Instruction_Sheet_Final_2025-06-05.pdf](https://www.sce.com/sites/default/files/custom-files/PDF_Files/Rule_21_Testing_and_Certification_Instruction_Sheet_Final_2025-06-05.pdf)
- **Type:** PDF
- **Corpus role:** Equipment testing and certification implementation guidance
- **Default retrieval tier:** `supporting_implementation`
- **Authority level:** Supporting implementation guidance
- **Filename:** `06_sce_testing_certification.pdf`
- **Local path:** `data/corpus/06_sce_testing_certification.pdf`
- **Raw extraction method:** `pypdf_page_text`
- **Normalisation status:** Review
- **Extraction issues:** PDF signature validation passes.
- **Normalisation notes:**
  - Excludes cover/disclaimer and contents pages.
  - Removes recurring `Instruction Sheet - Version 6/5/2025` page headers.
  - Detects numbered `Section N.` headings.
  - Seven blocks in early references and acronym material remain flagged with `no_detected_heading_path`.
- **Notes:** Describes testing and certification procedures for equipment compliance. Supports tariff and handbook requirements but is not itself controlling.


---


## Source hierarchy summary

| Authority level | Sources |
|---|---|
| Primary tariff / governing source | SCE Rule 21 tariff |
| Primary technical handbook | SCE Interconnection Handbook |
| Supporting implementation guidance | SCE testing and certification instruction |
| Supporting process guidance | SCE Rule 21 interconnection web guidance |
| Source discovery / regulatory context | CPUC Rule 21 overview page |
| Historical/draft material | SIWG Phase 2 Recommendations |


---


## Version and currency notes

- All sources are tracked by content hash in `data/corpus/corpus_metadata.json`.
- Raw extraction outputs retain the source content hash used for extraction.
- Normalised blocks retain the source content hash used for evidence provenance.
- Tariff normalisation preserves Rule 21 sheet number, Cal. PUC sheet number, effective date, and advice letter as citation metadata.
- Tariff PDF includes explicit supersession cues such as `Cancelling Revised Cal. PUC Sheet No.`.
- Web sources may change without explicit version markers; last-checked timestamps and hash changes are the primary currency signals.
- The handbook required manual replacement due to automated download blocking; metadata records the reviewer, approval status, hash, and retrieval eligibility.
- Normalised output quality must be reviewed after source refreshes, parser changes, or normalisation configuration changes.


---


## Quality and review notes

The current normalisation review result is:

| Source category | Result |
|---|---|
| Primary/current tariff and handbook sources | Pass |
| HTML overview and process guidance sources | Pass |
| Supporting testing instruction | Review; limited early-page heading-path warnings |
| Historical SIWG source | Review; limited early-page heading-path warnings |

Interpretation rules:

- `pass` means no quality-report errors or review warnings were detected by the current checks.
- `review` means the output remains usable and traceable, but one or more blocks require manual interpretation or source-specific parser refinement before high-confidence reliance.
- `fail` means a quality-report error was detected and the source must not proceed to downstream chunking or retrieval without correction.
- A `no_detected_heading_path` warning is not a loss of physical PDF page provenance.
- Review warnings should not be removed by broad heuristics solely to make the quality report green.


---


## Duplicates and exclusions

**Duplicates:** No adjacent duplicate normalised blocks were detected in the current quality report.

**Exclusions:**

- PG&E, SDG&E, and other California utilities are out of scope for v1.
- Older tariff versions and historical handbooks are not included in the v1 corpus.
- Additional working-group reports and draft material beyond SIWG Phase 2 are not included in v1.
- Handbook cover, approval, contents, certificate, repeated document-control, and page-header material are excluded from normalised evidence blocks.
- Testing instruction cover/disclaimer and contents pages are excluded from normalised evidence blocks.
- SIWG cover and contents pages are excluded from normalised evidence blocks.
- SIWG Phase 2 is excluded from normal current-requirement retrieval because it is historical/draft context.


---


## Future corpus extensions

Potential additions for later versions:

- Additional California utilities, including PG&E and SDG&E.
- Older tariff and handbook versions for version-comparison retrieval.
- More working-group reports and CPUC decisions related to DER interconnection and smart inverters.
- SCE forms, application instructions, and supporting process materials where their authority and currency can be recorded.
- Other markets, including ERCOT, NYISO, and AEMO, for cross-market comparison.