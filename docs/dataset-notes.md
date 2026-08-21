# Dataset notes


## Corpus overview


**Market:** California, United States  
**Regulator:** California Public Utilities Commission (CPUC)  
**Primary utility:** Southern California Edison (SCE)  
**Topic:** DER interconnection, technical requirements, communications/telemetry, testing and certification  
**Corpus role:** v1 research corpus for DER RegCheck RAG prototype  
**Total sources:** 6 public documents (5 PDF, 1 HTML)  


---


## Source list


### 1. CPUC Electric Rule 21 overview page


- **Source ID:** `cpuc_rule21_overview`
- **URL:** https://www.cpuc.ca.gov/Rule21/
- **Type:** HTML
- **Corpus role:** Regulatory context and discovery of authoritative sources
- **Default retrieval tier:** `source_discovery`
- **Authority level:** Regulatory overview (not controlling tariff text)
- **Filename:** `01_cpuc_rule21_overview.html`
- **Local path:** `data/corpus/01_cpuc_rule21_overview.html`
- **Extraction issues:** None; straightforward HTML with main content region.
- **Notes:** Provides links to tariff, handbooks, and related CPUC pages. Useful for context and source discovery, not treated as primary requirements.


---


### 2. SCE Rule 21 tariff (PDF)


- **Source ID:** `sce_rule21_tariff_pdf`
- **URL:** https://www.sce.com/sites/default/files/custom-files/PDF_Files/ELECTRIC_RULES_21.pdf
- **Type:** PDF
- **Corpus role:** Primary interconnection requirements
- **Default retrieval tier:** `primary_requirements`
- **Authority level:** Primary tariff / governing source
- **Filename:** `02_sce_rule21_tariff.pdf`
- **Local path:** `data/corpus/02_sce_rule21_tariff.pdf`
- **Extraction issues:** None; PDF signature validation passes.
- **Notes:** Controlling document for interconnection, operating, and metering requirements. Contains "Cancelling Revised Cal. PUC Sheet No." supersession cues that can be extracted for version tracking.


---


### 3. SCE Interconnection Handbook (PDF)


- **Source ID:** `sce_interconnection_handbook_pdf`
- **URL:** https://on.sce.com/InterconnectionHandbook
- **Type:** PDF
- **Corpus role:** Technical implementation detail
- **Default retrieval tier:** `primary_technical`
- **Authority level:** Primary technical handbook (secondary to tariff in conflicts)
- **Filename:** `03_sce_interconnection_handbook.pdf`
- **Local path:** `data/corpus/03_sce_interconnection_handbook.pdf`
- **Extraction issues:** 
  - Automated download intermittently returns HTML/SharePoint authentication response instead of PDF.
  - Triggered what appears to be a temporary block after repeated requests.
  - Manually replaced and marked approved in metadata.
- **Notes:** Covers interconnection process details, protection requirements, telemetry, inverter performance, and testing procedures. Critical for technical research questions.


---


### 4. SCE Rule 21 interconnection web guidance


- **Source ID:** `sce_interconnection_web`
- **URL:** https://www.sce.com/business/smart-energy-solar/solar-for-business/grid-interconnections/interconnecting-generation-under-rule-21
- **Type:** HTML
- **Corpus role:** Process guidance, forms, and source discovery
- **Default retrieval tier:** `supporting_process`
- **Authority level:** Supporting process guidance (not controlling)
- **Filename:** `04_sce_interconnection_web.html`
- **Local path:** `data/corpus/04_sce_interconnection_web.html`
- **Extraction issues:** None; standard utility web page with main content region.
- **Notes:** Summarises Rule 21 process, links to forms, testing information, and COT procedures. Useful for process questions but not treated as primary requirements.


---


### 5. Smart Inverter Working Group Phase 2 Recommendations (PDF)


- **Source ID:** `siwg_phase2_recommendations_pdf`
- **URL:** https://www.cpuc.ca.gov/-/media/cpuc-website/divisions/energy-division/documents/rule21/smart-inverter-working-group/siwg_phase_2.pdf
- **Type:** PDF
- **Corpus role:** Historical context and standards rationale
- **Default retrieval tier:** `historical_context`
- **Authority level:** Historical/draft material (excluded from default current-requirement retrieval)
- **Filename:** `05_siwg_phase2_recommendations.pdf`
- **Local path:** `data/corpus/05_siwg_phase2_recommendations.pdf`
- **Extraction issues:** None; PDF signature validation passes.
- **Notes:** Provides rationale for smart inverter functions, communications, and data categories. Important for historical context but not treated as current controlling requirements.


---


### 6. SCE testing and certification instruction sheet (PDF)


- **Source ID:** `sce_testing_certification_instruction_pdf`
- **URL:** https://www.sce.com/sites/default/files/custom-files/PDF_Files/Rule_21_Testing_and_Certification_Instruction_Sheet_Final_2025-06-05.pdf
- **Type:** PDF
- **Corpus role:** Equipment testing and certification implementation guidance
- **Default retrieval tier:** `supporting_implementation`
- **Authority level:** Supporting implementation guidance
- **Filename:** `06_sce_testing_certification.pdf`
- **Local path:** `data/corpus/06_sce_testing_certification.pdf`
- **Extraction issues:** None; PDF signature validation passes.
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


- All sources are tracked by content hash in `corpus_metadata.json`.
- Tariff PDF includes explicit supersession cues ("Cancelling Revised Cal. PUC Sheet No.") that can be extracted for version tracking.
- Web sources may change without explicit version markers; last-checked timestamps and hash changes are the primary currency signals.
- The handbook required manual replacement due to automated download block; its metadata records the reviewer and approval status.


---


## Duplicates and exclusions


**Duplicates:** None identified in v1 corpus.  

**Exclusions:**
- PG&E, SDG&E, and other California utilities (out of scope for v1).
- Older tariff versions and historical handbooks (may be added later for version-comparison experiments).
- Additional working-group reports and draft material beyond SIWG Phase 2 (may be added for historical-context experiments).


---


## Future corpus extensions


Potential additions for later versions:
- Additional California utilities (PG&E, SDG&E).
- Older tariff and handbook versions for version-comparison retrieval.
- More working-group reports and CPUC decisions related to DER and smart inverters.
- Other markets (e.g., ERCOT, NYISO, AEMO) for cross-market comparison.