# CheckSense Checkpoint: SRS Document Upload & End-to-End Analysis Extension

**Date:** 2026-10-29  
**Phase / Milestone:** SRS Document Analysis Extension (Building upon Phase 9)  
**Status:** COMPLETED & VERIFIED (Document Ingestion Engine Operational; 5-Section Streamlit Studio Implemented; Dependency Inconsistencies Resolved; 164 Tests Passing; Held-Out Test Set Sealed)  
**Binding Rules Followed:** [AGENTS.md](../AGENTS.md) and [docs/MASTER_SPEC.md](MASTER_SPEC.md)

---

## 1. Executive Summary & Deliverables Checklist

In response to the requirements for a complete SRS document analysis application, the existing CheckSense neuro-symbolic NLP architecture has been extended from a single-requirement analyzer into a full document-scale requirements engineering suite:

| Requirement | Implementation Detail | Status |
|---|---|---|
| **Multi-Format Document Upload** | Ingestion for PDF (`.pdf`), Microsoft Word (`.docx`), and Plain Text (`.txt`) via [`src/checksense/document.py`](../src/checksense/document.py). | **PASSED:** Fully implemented and tested with metadata tracking (section, page, line, source file). |
| **Error Handling & Scanned Detection** | Graceful handling of empty files, malformed documents, unsupported extensions, and scanned/image-only PDFs (no OCR). | **PASSED:** Verified with automated unit tests (`tests/test_document.py`). |
| **Pre-Analysis Candidate Review** | Editable review interface allowing users to inspect extracted requirements, view uncertainty flags, and adjust text before analysis. | **PASSED:** Integrated into [`app/streamlit_app.py`](../app/streamlit_app.py). |
| **Batch Multi-Head Defect Detection** | Reuses existing Phase 4 detection heads (Heads 4a, 4b, 4c) and Phase 5 fusion scorer across all extracted requirements. | **PASSED:** Detects ambiguity, incompleteness, and implicit constraints with localized defect spans. |
| **Clarity & Quality Scoring** | Transparent, documented clarity penalty heuristic ($[0.0, 1.0]$) alongside ISO/IEC/IEEE 29148 conformance characteristics. | **PASSED:** Macro-averaged document metrics computed without double-counting requirements. |
| **Clarification Question Formulation** | Grounded clarification questions generated for every detected gap with deterministic offline template fallback. | **PASSED:** Contract verified ($\le 30$ words, 1 question mark, strict grounding). Status tracked as Open, Answered, or Unresolved. |
| **Governed Requirement Refinement** | Stakeholder answer capture, before/after diff preview, strict numeric preservation audit, and **mandatory explicit approval gating**. | **PASSED:** Revisions are never automatically approved; user must explicitly click "Accept & Commit Revision". |
| **Interactive Studio Dashboard** | 5-section Streamlit interface: Overview, Requirement Explorer, Clarification Workspace, Traceability Matrix, and Single-Requirement Mode. | **PASSED:** Operational via `python -m checksense.cli serve --app main`. |
| **Multi-Format Export Engine** | Exportable Markdown report (`.md`), CSV table (`.csv`), and complete JSON audit trail (`.json`). | **PASSED:** Generates comprehensive audit trails with unreviewed/unapproved disclosures. |
| **Dependency Resolution** | Resolved NumPy/PyArrow and SciPy version conflicts in [`pyproject.toml`](../pyproject.toml). | **PASSED:** Clean virtual environment confirmed; `pip check` reports zero broken requirements. |
| **Full Regression Suite** | 164 automated tests passing across all phases, document parsers, and end-to-end smoke tests. | **PASSED:** `pytest tests -v` passes 100% in 91.98s; Ruff linter reports `All checks passed!`. |
| **Test Pool Sequestering** | `data/gold/test_pool.jsonl` (150 requirements across 6 documents). | **MAINTAINED:** Zero held-out data accessed, trained on, tuned on, or evaluated. Sealed pending human adjudication. |

---

## 2. Architecture & Document Processing Lifecycle

```
[ Upload SRS Document (.pdf / .docx / .txt) ]
                     │
                     ▼
[ Safe Parsing & Segmentation (src/checksense/document.py) ]
  ├── PDF: Page tracking via pypdf; scanned PDF detection (<50 chars)
  ├── DOCX: Paragraphs, heading styles & requirements tables via python-docx
  └── TXT: Section header recognition, explicit ID preservation, bullet grouping
                     │
                     ▼
[ Candidate Review & Editing Gate (app/streamlit_app.py) ]
  ├── User reviews candidate requirements
  ├── Uncertain candidates (lacking modal verbs) flagged for confirmation
  └── Action: "🚀 Analyze SRS Document"
                     │
                     ▼
[ Batch Multi-Head Defect Detection & Fusion ]
  ├── Dependency Frame Parsing (Actor, Modal, Action, Condition, Object)
  ├── Head 4a (Ambiguity): Lexicon, TF-IDF Smell Classifier, BIO Span Tagger
  ├── Head 4b (Incompleteness): Missing slots, passive voice, missing conditions/thresholds
  ├── Head 4c (Implicit Constraints): Domain checklist ontology (security, privacy, payments)
  └── Phase 5 Candidate Fusion: Overlap deduplication, MLP scoring, probability calibration
                     │
                     ▼
[ Clarity & ISO 29148 Assessment ]
  ├── ISO 29148 Characteristics: Singularity, Normative, Unambiguous, Complete
  ├── Transparent Clarity Heuristic: Base 1.00 - Severity Penalties - Smell Penalty - Modal Penalty
  └── Document-Level Metrics: Clean Ratio (non-double-counted), Macro-Avg ISO, Macro-Avg Clarity
                     │
                     ▼
[ Interactive Studio Dashboard (5 Sections) ]
  ├── Section A: Document Overview (Metrics cards, defect category distribution)
  ├── Section B: Requirement Explorer (Search, filter by category/severity, sort, highlighted HTML spans)
  ├── Section C: Clarification Workspace (Grounded questions, stakeholder answer input, before/after preview)
  ├── Section D: Summary & Traceability Matrix (Full traceability table, unresolved alerts, export buttons)
  └── Section E: Single-Requirement Analysis (Preserved individual requirement mode)
                     │
                     ▼
[ Governed Refinement & Approval Gate ]
  ├── Propose Refinement using Stakeholder Answer
  ├── Strict Numeric Preservation Guardrail (Zero dropped numbers, zero invented numbers)
  ├── ISO 29148 Before vs After Delta
  └── Explicit Stakeholder Approval Gate ("Accept & Commit Revision")
                     │
                     ▼
[ Multi-Format Report Exports ]
  ├── 📥 Markdown Monograph Report (checksense_srs_report.md)
  ├── 📥 CSV Requirements Table (checksense_requirements.csv)
  └── 📥 Complete JSON Audit Trail (checksense_audit_trail.json)
```

---

## 3. Dependency Compatibility & Environment Resolution

### Identified Issues
- Previously, NumPy 2.5.4 was installed while SciPy 1.13.1 required `numpy<2.3.0` (raising `UserWarning: A NumPy version >=1.22.4 and <2.3.0 is required for this version of SciPy`).
- PyArrow 26.0.0 required NumPy 2.0+, causing an `ImportError` when paired with NumPy 1.x.

### Resolution
- Updated `pyproject.toml` with strictly bounded, mutually compatible dependency specifications:
  - `numpy>=1.26.0,<2.0.0` (resolved to NumPy `1.26.4`)
  - `scipy>=1.12.0,<1.14.0` (resolved to SciPy `1.13.1`)
  - `pyarrow>=15.0.0,<19.0.0` (resolved to PyArrow `18.1.0`)
  - `python-docx>=1.1.0` (installed Python-docx `1.2.0` with `lxml`)
  - `pypdf>=4.0.0` (installed `pypdf 6.21.2`)
- Executed `pip check`: confirmed **"No broken requirements found."**
- Tested all runtime imports (`numpy`, `scipy.stats`, `pyarrow`, `pandas`, `docx`, `pypdf`, `streamlit`): verified **zero warnings and zero import errors**.

---

## 4. Verification Evidence & Test Execution

### 4.1 Full Regression Test Suite
Executed across all 12 test modules:
```
============================= test session starts =============================
platform win32 -- Python 3.12.4, pytest-9.1.1, pluggy-1.7.0
rootdir: C:\Users\2005v\OneDrive\Desktop\CheckSense
configfile: pyproject.toml
plugins: anyio-4.15.1, platformdirs-4.13.5
collected 164 items

tests\test_cli.py ................                                       [  9%]
tests\test_document.py .........                                         [ 15%]
tests\test_e2e_document_flow.py ..                                       [ 16%]
tests\test_env.py ....                                                   [ 18%]
tests\test_phase1.py ........                                            [ 23%]
tests\test_phase2.py .....................                               [ 36%]
tests\test_phase3.py ..................                                  [ 47%]
tests\test_phase4.py ...............                                     [ 56%]
tests\test_phase5.py ...............                                     [ 65%]
tests\test_phase6.py ........................                            [ 80%]
tests\test_phase7.py ..............                                      [ 89%]
tests\test_phase8.py ..........                                          [ 95%]
tests\test_phase9.py ........                                            [100%]

================= 164 passed, 20 warnings in 91.98s (0:01:31) =================
```

### 4.2 Verified End-to-End Smoke Test (`tests/test_e2e_document_flow.py`)
- Programmatically synthesized an SRS Word document with multiple requirement sections and defect types.
- Executed: Ingestion $\to$ Extraction $\to$ Batch Multi-Head Detection $\to$ Question Generation $\to$ Stakeholder Clarification $\to$ Refinement $\to$ Numeric Preservation Audit $\to$ Explicit Stakeholder Commit $\to$ Multi-Format Report Export.
- Verified all assertions: **2/2 passed in 8.30s**.

### 4.3 Code Quality & Environment Check
- **Ruff Linter:** `ruff check src/ tests/ app/` $\to$ **All checks passed!**
- **Environment Verification:** `python scripts/check_env.py` $\to$ **Passed** (All 12 subcommands registered, directory skeleton and ML packages verified).

---

## 5. Modified & Created Files

1. **`src/checksense/document.py`** (New): Core document extraction, segmentation, batch analysis, clarity heuristic, approval workflow, and report generators.
2. **`app/streamlit_app.py`** (Updated): Full interactive SRS Document Analysis Studio with 5 views, candidate review table, highlighted defect span visualizer, clarification workspace, and report download buttons.
3. **`pyproject.toml`** (Updated): Added `python-docx`, bounded `pyarrow`, `scipy`, `numpy`, and `pypdf` versions to resolve compatibility warnings.
4. **`src/checksense/__init__.py`** (Updated): Exported document models, analysis engines, and report generation functions.
5. **`tests/test_document.py`** (New): 9 unit tests covering TXT, DOCX, and PDF parsing, headings, tables, bullets, clarity heuristic, and batch analysis.
6. **`tests/test_e2e_document_flow.py`** (New): 2 end-to-end integration smoke tests verifying full document workflow from upload to export.
7. **`README.md`** (Updated): Added document workflow diagrams, supported formats, launch instructions, and updated test suite counts.
8. **`docs/CHECKPOINT_EXTENSION_SRS_DOC.md`** (New): Checkpoint documenting implementation details, test results, and scientific status.

---

## 6. How to Launch & Use the Application

To launch the CheckSense SRS Analysis Studio:
```powershell
python -m checksense.cli serve --app main --port 8501
```
Or directly via Streamlit:
```powershell
streamlit run app/streamlit_app.py
```

### User Steps
1. Navigate to the **"📑 SRS Document Analysis"** tab.
2. Upload an SRS file (`.pdf`, `.docx`, or `.txt`).
3. Review the candidate requirements in the review table.
4. Click **"🚀 Analyze SRS Document"**.
5. Explore results across the **Document Overview**, **Requirement Explorer**, **Clarification Workspace**, and **Traceability Matrix**.
6. Provide stakeholder answers to clarification questions, inspect proposed revisions, and click **"✅ Accept & Commit Revision"**.
7. Download reports via the Markdown, CSV, and JSON download buttons.

---

## 7. Limitations & Governance Disclosure

1. **Scanned PDF Limitation:** Text-based PDFs are parsed directly with page tracking. Scanned or image-only PDFs containing zero extractable characters are detected and flagged with an informative warning requiring OCR preprocessing.
2. **Document-Level Aggregation:** The "Clean Ratio" reflects the percentage of unique requirements with zero detected defects, preventing artificial deflation from requirements containing multiple gaps.
3. **Heuristic vs. Validated Scores:** The "Clarity Heuristic" is a transparent penalty index ($[0.0, 1.0]$) clearly distinguished from the ISO/IEC/IEEE 29148 4-characteristic conformance index.
4. **Sequestered Test Pool:** `data/gold/test_pool.jsonl` (150 requirements across 6 documents) remains safely sealed and untouched until independent human double-annotation and adjudication are performed.

