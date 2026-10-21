# CheckSense Checkpoint 1: Real Dataset Acquisition, Verification, and PURE Corpus Build

**Date:** 2026-10-21  
**Phase:** Phase 1  
**Status:** COMPLETED & VERIFIED (Halted for User Approval before Phase 2)  
**Binding Rules Followed:** [AGENTS.md](../AGENTS.md) and [docs/MASTER_SPEC.md](MASTER_SPEC.md)

---

## 1. What Was Done

### 1.1 Authentic Dataset Acquisition & Metadata Query via Zenodo REST API
Every dataset was queried directly through the official Zenodo REST API (`https://zenodo.org/api/records/<id>`) to retrieve verified metadata, versions, licenses, and host checksums prior to ingestion:
1. **PURE (Public REquirements Dataset):**
   - **Records:** Concept DOI `10.5281/zenodo.1414116`; Version 2.0 Record `7118517`; Version 1.0 Record `1414117`.
   - **Authors:** Alessio Ferrari, Giorgio Oronzo Spagnolo, Stefania Gnesi (CNR-ISTI, Italy; RE 2017).
   - **License:** CC-BY-4.0.
   - **Acquired Files:** `requirements-xml.zip` (378,737 bytes), `req_document.xsd` (5,355 bytes), and `requirements.zip` (33,623,628 bytes).
   - **Extraction:** 18 XML specification documents extracted from `requirements-xml.zip` into `data/raw/pure/extracted/requirements-xml/XMLZIPFile/`; 79 specifications extracted from `requirements.zip` into `data/raw/pure/extracted/requirements/`.
2. **ARTA (Automatic Requirements Testability Analysis Dataset):**
   - **Record:** Zenodo `4266727` (v1.0.0, 2020), Morteza Zakeri-Nasrabadi.
   - **Acquired File:** `ARTADataset_release1.zip` (1,312,856 bytes).
   - **Extraction:** 4 spreadsheets (`DS1.xlsx`, `DS2.xlsx`, `DS3.xlsx`, `DS4.xlsx`) containing 4,752 requirements, plus `SmellyWordsDictionary.xlsx` (1,000 words).
   - **Licensing Status:** Zenodo REST API returns `"license": null`. Logged in [docs/HUMAN_TODO.md](HUMAN_TODO.md) for human confirmation.
3. **QuRE (Industrial Requirements Quality Dataset):**
   - **Record:** Zenodo `16049822` / Concept DOI `10.5281/zenodo.15656471` (v1.0.1, 2025), Henning Femmer et al.
   - **License:** CC-BY-4.0.
   - **Acquired Files:** `QuRE.csv` (332,428 bytes, 2,111 requirements) and `description.md` (534 bytes).
4. **Investigation of Unverified Archives:**
   - **Zenodo Record 7118517:** Query confirmed this is the **official PURE v2.0 release** with identical checksums to PURE v1.0. License: CC-BY-4.0.
   - **Zenodo Record 7897601 (`Dataset.zip`):** Downloaded (11,864,852 bytes) and extracted. Examination of the 51 subdirectories confirmed this is the **Software Requirements Data Set** by David Šenkýř & Petr Kroha (May 2023). It is an aggregated benchmark containing 18 PURE documents (`P01`–`P18`), 7 coursework SRS (`C01`–`C07`), 4 healthcare specs (`H01`–`H04`), and 22 Dalpiaz user story sets (`g02`–`g28`). Verified and documented as an auxiliary benchmark.
5. **Investigation of PROMISE_exp:**
   - Searched the Zenodo RE Open Data community (`re-data`) and open repositories. No canonical, standalone Zenodo release with an open license exists.
   - Following `MASTER_SPEC.md` Section 3 ("If it cannot be located, skip the learned filter and keep the modal-verb rule; log it in HUMAN_TODO"), this branch was stopped and logged in [docs/HUMAN_TODO.md](HUMAN_TODO.md). CheckSense uses the deterministic modal-verb rule for candidate functional requirements.

---

### 1.2 Checksum Verification & Manifest Documentation
All downloaded raw archives were hashed locally (MD5 and SHA256) and verified against the host values. Complete records, DOI links, and file metrics were recorded in [data/MANIFEST.md](../data/MANIFEST.md):

| Dataset | File | Size (Bytes) | Host Zenodo MD5 | Local Computed MD5 | Verification |
|---|---|---|---|---|---|
| PURE | `requirements-xml.zip` | 378,737 | `c81235c40f88a2c947ae66e0eddad585` | `c81235c40f88a2c947ae66e0eddad585` | **MATCH (100%)** |
| PURE | `req_document.xsd` | 5,355 | `f44c255db9414afb7c39265697abcb33` | `f44c255db9414afb7c39265697abcb33` | **MATCH (100%)** |
| PURE | `requirements.zip` | 33,623,628 | `bc319fe28619f6290badff328ca159dd` | `bc319fe28619f6290badff328ca159dd` | **MATCH (100%)** |
| ARTA | `ARTADataset_release1.zip` | 1,312,856 | `92a09adc5e4b9cd96370e7f09fe466d2` | `92a09adc5e4b9cd96370e7f09fe466d2` | **MATCH (100%)** |
| QuRE | `QuRE.csv` | 332,428 | `80565e3b8996d8af1598813aafc87cb3` | `80565e3b8996d8af1598813aafc87cb3` | **MATCH (100%)** |
| QuRE | `description.md` | 534 | `e7b7a3526c0471fe6853daa13e5613d7` | `e7b7a3526c0471fe6853daa13e5613d7` | **MATCH (100%)** |
| 7897601 | `Dataset.zip` | 11,864,852 | `89f141ad7376afdbec1cf6db858f10c4` | `89f141ad7376afdbec1cf6db858f10c4` | **MATCH (100%)** |

---

### 1.3 Column Inspection & Proposed Label Mapping for ARTA
All 4 ARTA spreadsheets were inspected. Headers and value formats were extracted, and a comprehensive mapping to CheckSense's gap taxonomy was proposed in [docs/label_mapping.md](label_mapping.md):
- `Subjective Language`, `Ambiguous Adverbs & Adjectives`, `Uncertain Verbs`, `Non-verifiable/Open-ended`, `Polysemy` $\rightarrow$ `ambiguity / vague_term`
- `Superlatives`, `Comparatives` $\rightarrow$ `ambiguity / vague_quantifier`
- `Vague Pronouns` $\rightarrow$ `ambiguity / anaphora`
- `Loopholes` $\rightarrow$ `incompleteness / missing_condition`
- `Negative Statements` $\rightarrow$ Auxiliary sentence-level smell feature.

*Status: Awaiting human review and sign-off before model training in Phase 4.*

---

### 1.4 PURE Interim Corpus Build (`pure_requirements.jsonl`)
Implemented [src/checksense/corpus.py](file:///c:/Users/2005v/OneDrive/Desktop/CheckSense/src/checksense/corpus.py) and connected it to `python -m checksense.cli build-corpus`. The builder parses all 18 authentic PURE XML specifications without silently dropping any document, segments sentences, and applies the specification filters:

#### Real Filtering Statistics:
- **Total Documents Processed:** 18 (0 dropped)
- **Total Raw Sentences Extracted:** 7,273
- **Removed Duplicates (Within Document):** 408
- **Removed Headings / Titles:** 45
- **Removed Lacking Modal Verb (`shall/must/should/will`):** 3,749
- **Removed Too Short (< 5 tokens):** 0
- **Removed Too Long (> 60 tokens):** 143
- **Total Candidate Requirements Retained:** **2,928**
- **Output File:** `data/interim/pure_requirements.jsonl` (891,855 bytes, 2,928 lines)
- **Audit Log:** `data/interim/pure_filtering_stats.json` (balances exactly: $7,273 = 2,928 + 408 + 45 + 3,749 + 0 + 143$)

#### Per-Document Retention Breakdown:
| Document ID | Source File | Raw Sentences | Retained Requirements |
|---|---|---|---|
| `0000 - cctns` | `0000 - cctns.xml` | 201 | 128 |
| `0000 - gamma j` | `0000 - gamma j.xml` | 421 | 102 |
| `1995 - gemini` | `1995 - gemini.xml` | 1,096 | 366 |
| `1998 - themas` | `1998 - themas.xml` | 213 | 112 |
| `1999 - dii` | `1999 - dii.xml` | 206 | 35 |
| `1999 - tcs` | `1999 - tcs.xml` | 339 | 178 |
| `2003 - qheadache` | `2003 - qheadache.xml` | 159 | 24 |
| `2005 - microcare` | `2005 - microcare.xml` | 220 | 54 |
| `2005 - phin` | `2005 - phin.xml` | 196 | 45 |
| `2006 - eirene sys 15` | `2006 - eirene sys 15.xml` | 707 | 453 |
| `2007 - get real 0.2` | `2007 - get real 0.2.xml` | 101 | 51 |
| `2007-eirene_fun_7-2` | `2007-eirene_fun_7-2.xml` | 717 | 454 |
| `2007-ertms` | `2007-ertms.xml` | 391 | 147 |
| `2008 - keepass` | `2008 - keepass.xml` | 331 | 145 |
| `2008 - peering` | `2008 - peering.xml` | 240 | 79 |
| `2009 - peppol approved` | `2009 - peppol approved.xml` | 1,564 | 473 |
| `2009 - video search` | `2009 - video search.xml` | 104 | 46 |
| `2010-blitdraft` | `2010-blitdraft.xml` | 67 | 36 |
| **Total** | **18 XML Documents** | **7,273** | **2,928** |

---

### 1.5 Exploratory Data Analysis (EDA) Notebooks
Created 3 reproducible Jupyter notebooks in `notebooks/`:
1. `notebooks/01_pure_eda.ipynb`: PURE requirements analysis, length statistics, modal verb proportions, document distribution, and 20 sample rows.
2. `notebooks/02_arta_eda.ipynb`: ARTA spreadsheet exploration across DS1–DS4, smell frequency calculations, and 20 sample rows.
3. `notebooks/03_qure_eda.ipynb`: QuRE external dataset analysis, defect distribution (defect vs. ok), weak word distributions, and 20 sample rows.

---

### 1.6 CLI Subcommands Updated to Functional Status
- `download`: Now fully functional. Connects to `src/checksense/acquisition.py`, validates options, downloads from Zenodo, verifies checksums, and extracts.
- `build-corpus`: Now fully functional. Connects to `src/checksense/corpus.py`, parses XML, executes filters, writes `pure_requirements.jsonl`, and outputs audit stats.

---

## 2. Verifiable Evidence

### A. Unit Tests (`pytest tests -v`)
```text
============================= test session starts =============================
platform win32 -- Python 3.12.4, pytest-9.1.1, pluggy-1.7.0
rootdir: C:\Users\2005v\OneDrive\Desktop\CheckSense
configfile: pyproject.toml
collected 28 items

tests\test_cli.py ................                                       [ 57%]
tests\test_env.py ....                                                   [ 71%]
tests\test_phase1.py ........                                            [100%]

============================= 28 passed in 2.77s ==============================
```
**Exit Code:** `0` (28 passed, 0 failed across all suites).

### B. Linter Check (`ruff check .`)
```text
All checks passed!
```
**Exit Code:** `0`.

### C. Workspace Environment Check (`python scripts/check_env.py`)
```text
============================================================
CheckSense Environment & Workspace Verification
============================================================
[*] Python Runtime: 3.12.4 on Windows (AMD64)
    [+] Python version check passed (>= 3.11).
[*] Checking directory structure:
    [+] src/checksense/ exists.
    [+] docs/ exists.
    [+] data/raw/ exists.
    [+] data/interim/ exists.
    [+] data/processed/ exists.
    [+] data/gold/ exists.
    [+] notebooks/ exists.
    [+] reports/ exists.
    [+] results/ exists.
    [+] scripts/ exists.
    [+] tests/ exists.
    [+] .vscode/ exists.
[*] Checking Git repository:
    [+] Git repository initialized.
    [+] .gitignore present.
[*] Checking CheckSense package import:
    [+] Successfully imported 'checksense' v0.1.0
    [+] Subparsers loaded (12 commands): download, build-corpus, sample, annotate-stats, train-smell, train-span, train-fusion, eval, rate-make, rate-score, report, serve
[*] Checking installed dependencies:
    [+] pytest (9.1.1): Testing harness
    [+] ruff (unknown): Linter and formatter
    [?] torch is not yet installed: PyTorch deep learning framework
    [?] spacy is not yet installed: spaCy NLP parser
    [?] transformers is not yet installed: Hugging Face transformers
    [?] sklearn is not yet installed: scikit-learn machine learning
    [+] pandas (3.0.6): Data manipulation
    [?] streamlit is not yet installed: Interactive web UI
============================================================
[+] Environment and repository skeleton validation PASSED!
```
**Exit Code:** `0`.

### D. Git Cleanliness Check
```text
On branch master
Untracked files:
	data/interim/pure_filtering_stats.json
	data/interim/pure_requirements.jsonl
	docs/label_mapping.md
	notebooks/01_pure_eda.ipynb
	notebooks/02_arta_eda.ipynb
	notebooks/03_qure_eda.ipynb
	scripts/generate_eda_notebooks.py
	scripts/inspect_arta.py
	scripts/inspect_zenodo.py
	src/checksense/acquisition.py
	src/checksense/corpus.py
	tests/test_phase1.py
```
*Note:* Raw datasets in `data/raw/*` (`pure`, `arta`, `qure`, `unverified`) are safely ignored by `.gitignore` and are not committed to Git.

---

## 3. Unresolved Blockers & Items Requiring Human Review

1. **ARTA Research License:** Review [docs/HUMAN_TODO.md](HUMAN_TODO.md) to confirm academic fair use acceptance for ARTA benchmarking.
2. **ARTA Label Mapping Approval:** Review [docs/label_mapping.md](label_mapping.md) and confirm the mapping from ARTA smell columns to CheckSense taxonomy classes before Phase 4.
3. **PROMISE_exp Acknowledgment:** Confirm that skipping the learned NFR filter and retaining the modal-verb filter is acceptable.

---

## 4. Next Actions (Phase 2 Preview)

Upon user review and approval of Checkpoint 1:
1. **spaCy Dependency & Pipeline Setup:** Install spaCy and download `en_core_web_sm`.
2. **Requirement Frame Extractor:** Implement rule-based dependency extractor (`actor`, `modal`, `action`, `object`, `condition`, `quantity`, `exception`) handling passive voice and conditional clauses.
3. **Rule-Based Baseline Detector (B1):** Implement lexicon span detector and frame-slot heuristic candidate gap generator.
4. **Metrics & Evaluation Engine:** Implement macro-F1, token span Jaccard matching, and the strict gate that **refuses to evaluate on rows where `label_status != 'verified'`**.
5. **Phase 2 Test Suite & Checkpoint 2:** Unit tests for frame extractor and evaluation gating.

---

**Execution is halted.** No Phase 2 work has been started. I await your approval of Checkpoint 1.
