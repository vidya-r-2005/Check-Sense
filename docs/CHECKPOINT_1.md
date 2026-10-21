# CheckSense Checkpoint 1: Real Dataset Acquisition, Verification, and PURE Corpus Build

**Date:** 2026-10-21  
**Phase:** Phase 1  
**Status:** COMPLETED & VERIFIED (Halted for User Approval before Phase 2)  
**Binding Rules Followed:** [AGENTS.md](../AGENTS.md) and [docs/MASTER_SPEC.md](MASTER_SPEC.md)

---

## 1. What Was Done in Phase 1

### 1.1 Authentic Dataset Acquisition & Metadata Ingestion
Every dataset was acquired through the official host API/repository and verified before use:
1. **PURE (Public REquirements Dataset, Ferrari et al. 2017):**
   - **Records:** Concept DOI `10.5281/zenodo.1414116`; Version 2.0 Record `7118517` (`10.5281/zenodo.7118517`).
   - **Curators:** Alessio Ferrari, Giorgio Oronzo Spagnolo, Stefania Gnesi (CNR-ISTI, Italy; RE 2017).
   - **Files Acquired & Verified:**
     - `requirements-xml.zip` (378,737 bytes; MD5: `c81235c40f88a2c947ae66e0eddad585`)
     - `req_document.xsd` (5,355 bytes; MD5: `f44c255db9414afb7c39265697abcb33`)
     - `requirements.zip` (33,623,628 bytes; MD5: `bc319fe28619f6290badff328ca159dd`)
   - **Document Count Resolution:** The curator's Zenodo summary description informally states *"a subset of 19 documents in XML format"*. However, byte-level inspection of the verified `requirements-xml.zip` archive confirms that it contains **exactly 18 XML files** inside `XMLZIPFile/`, plus the directory `XMLZIPFile` itself (totaling 19 zip entries; and 19 resource-fork entries in `__MACOSX`). There is no missing XML document: all 18 specification documents present in the official archive were parsed, processed, and accounted for in `data/interim/pure_requirements.jsonl` (0 dropped).
   - **Rights Statement (Verbatim from Zenodo metadata):**
     > *"The dataset has been created by gathering data from web sources and we are not aware of license agreements or intellectual property rights on the requirements. The curator took utmost diligence in minimizing the risks of copyright infringement by using non-recent data that is less likely to be critical, by sampling a subset of the original requirements collection, and by qualitatively analyzing the requirements. In case of copyright infringement, please contact the dataset curator (Alessio Ferrari, alessio.ferrari@cnr.it, alessio.ferrari@ucd.ie) to discuss the possibility of removal of that dataset [see Zenodo's policies]."*
     The record itself is deposited under Creative Commons Attribution 4.0 International (`CC-BY-4.0`).
2. **ARTA (Automatic Requirements Testability Analysis Dataset, Zakeri-Nasrabadi 2020):**
   - **Record:** Zenodo `4266727` (v1.0.0, 2020-11-10).
   - **File Acquired & Verified:** `ARTADataset_release1.zip` (1,312,856 bytes; MD5: `92a09adc5e4b9cd96370e7f09fe466d2`).
   - **Licensing Status:** Zenodo REST API reports `"access_right": "open"`, `"license": null`. Archive inspection confirms there is no `LICENSE` or `README` file inside the zip.
   - **Mandatory Enforcement:** Per user instructions, academic use is **not** assumed. **Model training on ARTA in Phase 4 is strictly BLOCKED** until the user/stakeholder explicitly establishes or confirms reuse terms.
3. **QuRE (Industrial Requirements Quality Dataset, Femmer et al. 2025):**
   - **Concept DOI:** `10.5281/zenodo.15656471`
   - **Version-Specific Record ID:** Zenodo `16049822`
   - **Version-Specific DOI:** `10.5281/zenodo.16049822` (Version 1.0.1, published 2025-07-17)
   - **License:** `CC-BY-4.0`
   - **Files Acquired & Verified:**
     - `QuRE.csv` (332,428 bytes; MD5: `80565e3b8996d8af1598813aafc87cb3`)
     - `description.md` (534 bytes; MD5: `e7b7a3526c0471fe6853daa13e5613d7`)
   - **Content:** 2,111 unique industrial requirements labeled for defects (`defect` vs. `ok`) and associated weak words.
4. **Investigation of Unverified Zenodo Archives:**
   - **Zenodo 7118517:** Query confirmed this is the **official PURE v2.0 release** with checksums matching PURE v1.0. License: CC-BY-4.0.
   - **Zenodo 7897601 (`Dataset.zip`, 11,864,852 bytes):** Verified and extracted. Inspection of the 51 subdirectories confirmed this is the **Software Requirements Data Set** by David Šenkýř & Petr Kroha (May 2023). It is an aggregated benchmark containing 18 PURE documents (`P01`–`P18`), 7 coursework SRS (`C01`–`C07`), 4 healthcare specs (`H01`–`H04`), and 22 Dalpiaz user story sets (`g02`–`g28`). Verified and documented as an auxiliary benchmark.
5. **Investigation of PROMISE_exp:**
   - No canonical, standalone Zenodo or institutional repository with an open license exists.
   - Per `MASTER_SPEC.md` Section 3 ("If it cannot be located, skip the learned filter and keep the modal-verb rule; log it in HUMAN_TODO"), this branch was stopped and logged in [docs/HUMAN_TODO.md](HUMAN_TODO.md). CheckSense uses the deterministic modal-verb rule for candidate functional requirements.

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
All 4 ARTA spreadsheets (`DS1.xlsx`–`DS4.xlsx`) were inspected (4,752 requirements total). A mapping to CheckSense's gap taxonomy was formulated in [docs/label_mapping.md](label_mapping.md):
- `Subjective Language`, `Ambiguous Adverbs & Adjectives`, `Uncertain Verbs`, `Non-verifiable/Open-ended`, `Polysemy` $\rightarrow$ `ambiguity/vague_term`
- `Superlatives`, `Comparatives` $\rightarrow$ `ambiguity/vague_quantifier`
- `Vague Pronouns` $\rightarrow$ `ambiguity/anaphora`
- `Loopholes` $\rightarrow$ `incompleteness/missing_condition`
- `Negative Statements` $\rightarrow$ Auxiliary sentence-level smell feature.

**Status:** Strictly marked as **PROPOSED (Awaiting Human Approval)**. It is not approved, no model has been trained on it, and it will not be used in code until explicit approval is received.

---

### 1.4 PURE Interim Corpus Build & Filter Integrity Verification
Implemented [src/checksense/corpus.py](file:///c:/Users/2005v/OneDrive/Desktop/CheckSense/src/checksense/corpus.py) and functional CLI command `python -m checksense.cli build-corpus`. Parsed all 18 authentic PURE XML specifications into `data/interim/pure_requirements.jsonl` with schema `req_id, doc_id, text, source_file, sent_idx, token_count`:

#### Actual CLI Invocation Output:
```text
PS C:\Users\2005v\OneDrive\Desktop\CheckSense> .\.venv\Scripts\python.exe -m checksense.cli build-corpus
[CheckSense CLI] 'build-corpus' subcommand invoked.
Input: C:\Users\2005v\OneDrive\Desktop\CheckSense\data\raw\pure -> Output: C:\Users\2005v\OneDrive\Desktop\CheckSense\data\interim\pure_requirements.jsonl

============================================================
PURE Corpus Build Complete
============================================================
Total documents processed: 18 (0 dropped)
Total raw sentences:        7273
Removed duplicates:         408
Removed headings:           45
Removed no modal verb:      3749
Removed < 5 tokens:         0
Removed > 60 tokens:        143
Retained requirements:      2928
Output JSONL (Local Only):  data\interim\pure_requirements.jsonl (891,855 bytes)
Filtering Audit Log:        data\interim\pure_filtering_stats.json
============================================================
```

> **Redistribution Rights Assessment & Repository Governance:**  
> Because the PURE specifications were gathered from public web sources without explicit copyright transfer for third-party redistribution, the extracted full-text requirement corpus (`data/interim/pure_requirements.jsonl`) is maintained strictly as a **local generated artifact** and is excluded from Git tracking via `.gitignore`. It is generated deterministically and reproducibly on demand using `python -m checksense.cli build-corpus` from the verified official Zenodo archive. The aggregate filtering audit statistics (`data/interim/pure_filtering_stats.json`), which contain only numerical counts and schema metadata without raw requirement text, remain tracked in Git for auditability.

#### Non-Overlapping Filter Pipeline Verification:
The filtering stages in `src/checksense/corpus.py` are executed sequentially with immediate `continue` on failure, guaranteeing non-overlapping stages:
1. **Deduplication within Document:** Identical sentence text (case-normalized) already seen in the current document is dropped ($Removed_{dup} = 408$).
2. **Heading Filter:** Sentences matching document titles or short header heuristics ($Removed_{heading} = 45$).
3. **Modal Verb Filter:** Sentences lacking `shall|must|should|will` ($Removed_{no\_modal} = 3,749$).
4. **Token Length Bounds:** Tokens $< 5$ ($Removed_{short} = 0$) or $> 60$ ($Removed_{long} = 143$).
5. **Retained Requirements:** Sentences passing all checks ($Retained = 2,928$).

**Exact Balance Proof:**
$$\text{Total Raw Sentences} = Removed_{dup} + Removed_{heading} + Removed_{no\_modal} + Removed_{short} + Removed_{long} + Retained$$
$$7,273 = 408 + 45 + 3,749 + 0 + 143 + 2,928 \quad \checkmark$$

#### Per-Document Retention Breakdown:
| Document ID | Source File | Raw Sentences | Retained Requirements |
|---|---|---|---|
| `0000 - cctns` | `0000 - cctns.xml` | 201 | 128 |
| `0000 - gamma j` | `0000 - gamma j.xml` | 421 | 102 |
| `1995 - gemini` | `1995 - gemini.xml` | 1,096 | 366 |
| `1998 - themas` | `1998 - themas.xml` | 213 | 112 |
| `1999 - dii` | `1999 - dii.xml` | 206 | 35 |
| `1999 - tcs` | `1999 - tcs.xml` | 339 | 178 |
| `2003 - qheadache` | `2003 - qheadache.xml` | 159 | 10 |
| `2005 - microcare` | `2005 - microcare.xml` | 220 | 111 |
| `2005 - phin` | `2005 - phin.xml` | 196 | 139 |
| `2006 - eirene sys 15` | `2006 - eirene sys 15.xml` | 707 | 361 |
| `2007 - get real 0.2` | `2007 - get real 0.2.xml` | 101 | 13 |
| `2007-eirene_fun_7-2` | `2007-eirene_fun_7-2.xml` | 717 | 508 |
| `2007-ertms` | `2007-ertms.xml` | 391 | 203 |
| `2008 - keepass` | `2008 - keepass.xml` | 331 | 41 |
| `2008 - peering` | `2008 - peering.xml` | 240 | 12 |
| `2009 - peppol approved` | `2009 - peppol approved.xml` | 1,564 | 470 |
| `2009 - video search` | `2009 - video search.xml` | 104 | 74 |
| `2010-blitdraft` | `2010-blitdraft.xml` | 67 | 65 |
| **Total** | **18 XML Documents** | **7,273** | **2,928** |

---

### 1.5 Execution of Exploratory Data Analysis (EDA) Notebooks
All 3 notebooks were executed in-place via `nbconvert --execute --inplace` using the project's Python 3.12 kernel:
- `notebooks/01_pure_eda.ipynb` (25.3 KB with executed output cells): Evaluates the 2,928 candidate requirements. Modal verb occurrences across candidate requirements: `shall` (1,293 / 44.16%), `will` (732 / 25.00%), `should` (526 / 17.96%), `must` (488 / 16.67%). Mean token length: 23.02 tokens (std: 10.56, min: 5, max: 60). Includes 20 seeded sample requirements.
- `notebooks/02_arta_eda.ipynb` (12.6 KB with executed output cells): Evaluates DS1–DS4. Top smells in DS1: `Polysemy` (436 occurrences), `Subjective_lang.` (259 occurrences), `Uncertain_verb` (188 occurrences), `Nonverifiable_term` (165 occurrences). Includes 20 seeded sample rows.
- `notebooks/03_qure_eda.ipynb` (16.9 KB with executed output cells): Evaluates 2,187 labeled rows (2,111 unique industrial requirements). Labels: `ok` (70.23%, 1,536 rows), `defect` (29.77%, 651 rows). Top weak words: `adequate` (223), `support` (172), `easy` (143), `effective` (114), `fast` (104). Includes 20 seeded sample rows.

---

## 2. Verifiable Evidence

### A. Unit Tests (`pytest tests -v`)
```text
============================= test session starts =============================
platform win32 -- Python 3.12.4, pytest-9.1.1, pluggy-1.7.0
rootdir: C:\Users\2005v\OneDrive\Desktop\CheckSense
configfile: pyproject.toml
plugins: platformdirs-4.13.5
collected 28 items

tests\test_cli.py ................                                       [ 57%]
tests\test_env.py ....                                                   [ 71%]
tests\test_phase1.py ........                                            [100%]

============================= 28 passed in 5.55s ==============================
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

### D. Git Repository & Remote Synchronization Status
- **Local Branch:** `main`
- **Remote Repository:** `https://github.com/vidya-r-2005/Check-Sense.git`
- **Remote Tracking Branch:** `origin/main`
- **Push Status:** **SYNCHRONIZED (Up-to-date with `origin/main`)**
- **Recent Commit Chain:**
  - `cd29d5f`: `feat(phase-0): initialize repo, environment, cli skeleton, vscode config, test harness, and checkpoint 0`
  - `e20234e`: `feat(phase-1): acquire and verify datasets, build PURE corpus, eda notebooks, and checkpoint 1`
  - `c5c3639`: `docs(phase-1): synchronize per-document counts, QuRE row counts, and verification evidence`
  - `789d734`: `merge: safely reconcile remote origin/main into CheckSense`
- **Protection of Excluded Artifacts (Excluded from Public Git via `.gitignore`):**
  - `data/raw/*`: Raw Zenodo dataset downloads (only `data/raw/.gitkeep` tracked).
  - `data/interim/*.jsonl`: Derived full-text requirement corpora including `data/interim/pure_requirements.jsonl` (only `data/interim/.gitkeep` and aggregate statistics `data/interim/pure_filtering_stats.json` tracked).
  - `data/processed/*`: Processed requirement datasets (only `data/processed/.gitkeep` tracked).
  - `models/*`: Trained model weights and checkpoints (only `models/.gitkeep` tracked).
  - `.env`: Environment variables, tokens, and secrets.
  - `.venv/`: Python virtual environment and site-packages.
- **Tracked Reproducibility Assets in Public Repository:**
  - Code & Pipelines: `src/checksense/acquisition.py`, `src/checksense/corpus.py`, `src/checksense/cli.py`.
  - Test Harness: `tests/test_cli.py`, `tests/test_env.py`, `tests/test_phase1.py` (28 unit tests).
  - EDA Notebooks: `notebooks/01_pure_eda.ipynb`, `notebooks/02_arta_eda.ipynb`, `notebooks/03_qure_eda.ipynb`.
  - Verification & Audit: `data/MANIFEST.md`, `data/interim/pure_filtering_stats.json` (aggregate counts without raw text).
  - Specifications & Gates: `docs/CHECKPOINT_1.md`, `docs/HUMAN_TODO.md`, `docs/label_mapping.md`.

---

## 3. Summary of Discrepancies Resolved & Remaining Blockers

1. **Discrepancy Resolved (PURE XML Document Count):** The official Ferrari et al. Zenodo archive `requirements-xml.zip` contains **18 XML files**, not 19. All 18 documents were parsed and retained; zero documents dropped.
2. **Discrepancy Resolved (QuRE Provenance):** Fully distinguished Concept DOI (`10.5281/zenodo.15656471`) from Version Record ID (`16049822` / DOI `10.5281/zenodo.16049822`, v1.0.1, CC-BY-4.0).
3. **Discrepancy Resolved (PURE Rights Statement):** Recorded verbatim curator rights notice and takedown policy in MANIFEST and checkpoint.
4. **Discrepancy Resolved (PURE Derived Text Redistribution Governance):** Evaluated third-party copyright and redistribution rights on extracted PURE requirement text. Established that public redistribution of extracted requirement text on GitHub is not authorized by the original specification owners. Removed `data/interim/pure_requirements.jsonl` from Git tracking and added `.gitignore` rules (`data/interim/*.jsonl`, `data/processed/*`). Preserved local file on disk for pipeline execution and retained publicly tracked audit statistics (`pure_filtering_stats.json`).
5. **Active Blocker (ARTA Licensing):** Official Zenodo record returns `"license": null`. Archive contains no license text. **ARTA model training in Phase 4 is BLOCKED** until the human reviewer establishes applicable reuse terms.
6. **Active Blocker (ARTA Label Mapping):** Marked strictly as **PROPOSED (Awaiting Human Approval)** in `docs/label_mapping.md`.

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
