# CheckSense Checkpoint 3: Sampling Protocol, Annotation Tooling, Guidelines, and Inter-Rater Reliability

**Date:** 2026-10-22  
**Phase:** Phase 3  
**Status:** COMPLETED & VERIFIED (**HALTED AT HUMAN ANNOTATION GATE**; Awaiting Human Labeling before Phase 4)  
**Binding Rules Followed:** [AGENTS.md](../AGENTS.md) and [docs/MASTER_SPEC.md](MASTER_SPEC.md)

---

## 1. Executive Summary of Phase 3 Deliverables

In strict compliance with Section 11 (Phase 3 Acceptance Criteria) of `MASTER_SPEC.md`, all required Phase 3 tooling, protocols, and documentation were constructed, tested, and validated. **Execution is formally halted at the Human Annotation Gate.** No model training has commenced and zero synthetic annotations or fabricated agreement metrics have been generated.

| Deliverable | Location | Status | Key Properties |
|---|---|---|---|
| **Multi-Format PURE Corpus** | [src/checksense/corpus.py](../src/checksense/corpus.py) | **VERIFIED** | 4,023 candidate requirements extracted across 26 authentic PURE documents (XML, HTML, PDF) |
| **Sampling & Partitioning Protocol** | [src/checksense/sample.py](../src/checksense/sample.py) | **VERIFIED** | Seed 42, 610 requirements sampled, 26 documents, held-out test set sequestered into separate artifact |
| **Streamlit Annotation Tool** | [app/annotate.py](../app/annotate.py) | **VERIFIED** | Multi-gap support, strict validation before verification, test split blocked from annotation |
| **Annotation Integrity & Validation** | [src/checksense/annotation.py](../src/checksense/annotation.py) | **VERIFIED** | Enforces substring spans, single terminal `?`, clean exclusivity, multi-row schema |
| **Annotation Guidelines** | [docs/annotation_guidelines.md](annotation_guidelines.md) | **VERIFIED** | 2–3 positive and negative examples per subtype across all 9 taxonomy categories; severity contract (1–3) |
| **Inter-Rater Reliability Engine** | [src/checksense/agreement.py](../src/checksense/agreement.py) | **VERIFIED** | Requires verified rows, matching complete ID sets, rejects partial intersections and draft rows |
| **CLI Subcommand Integration** | [src/checksense/cli.py](../src/checksense/cli.py) | **VERIFIED** | `sample`, `annotate-stats`, and `serve --app annotate` fully operational |
| **Phase 3 Test Suite** | [tests/test_phase3.py](../tests/test_phase3.py) | **VERIFIED** | 17 comprehensive unit/regression tests covering splits, kappa math, schema, and all 4 review fixes |

---

## 2. Sampling Protocol & Held-Out Test Set Sequestering

### 2.1 Multi-Format PURE Corpus Expansion
To fulfill the requirement of sampling across at least 20 PURE documents with a 25% document-level holdout, the corpus builder in `corpus.py` was extended to ingest both structured XML specifications (`requirements-xml/XMLZIPFile`) and authentic HTML/PDF specifications (`requirements/req`):
- **Total authentic PURE documents processed:** 26 specifications (0 dropped)
- **Total raw sentences extracted:** 13,394
- **Deduplication removals:** 1,987
- **Heading filter removals:** 393
- **Non-modal removals:** 6,790
- **Length filter removals:** 201 (> 60 tokens)
- **Total retained candidate requirements:** **4,023** (satisfying modal verb requirement, length [5, 60], non-heading, deduplicated)

### 2.2 Deterministic Document-Level Split (Seed 42)
To strictly prevent cross-requirement data contamination between development and testing, partitioning is conducted at the **document level**:
- **Held-out Test Documents (6 documents / 23.1% ~ 25%):**
  - `1999 - tcs`
  - `2001 - elsfork`
  - `2002 - evla back`
  - `2005 - phin`
  - `2007-eirene_fun_7-2`
  - `2010-blitdraft`
- **Development Documents (20 documents / 76.9%):**
  - `0000 - cctns`, `0000 - gamma j`, `1995 - gemini`, `1998 - themas`, `1999 - dii`, `1999 - multi-mahjong`, `2001 - beyond`, `2001 - ctc network`, `2001 - esa`, `2001 - hats`, `2003 - qheadache`, `2005 - microcare`, `2005 - nenios`, `2006 - eirene sys 15`, `2007 - get real 0.2`, `2007-ertms`, `2008 - keepass`, `2008 - peering`, `2009 - peppol approved`, `2009 - video search`
- **Contamination Audit:** `set(dev_docs) & set(test_docs) == set()` (**PASSED; 0 shared documents**).

### 2.3 Sample Pool & Sequestered Test Artifacts
- **Total Sampled Requirements:** **610** ($\ge 600$)
  - **Development Set (`data/gold/dev_pool.jsonl`):** **460** requirements across 20 documents.
  - **Held-Out Test Set (`data/gold/test_pool.jsonl`):** **150** requirements across 6 documents.
- **Test Set Isolation:** `test_pool.jsonl` is completely segregated. In `sample.py`, `load_annotation_workflow_pool` strictly raises `PermissionError` if an annotator or script attempts to load `test_pool.jsonl`, and automatically filters out any requirement from the held-out split. The ordinary annotation UI only offers the pilot sample and the development pool.
- **Pilot Double-Annotation Set:** **50** requirements drawn deterministically from the development split into `data/gold/pilot_sample.csv`.
- **Annotation Template:** `data/gold/annotations_template.csv` matching the canonical schema:
  `req_id, doc_id, text, has_gap, gap_type, subtype, span_text, severity, explanation, question, stakeholder_answer, refined_text, annotator, label_status, notes`

---

## 3. Tooling: Streamlit Annotation Application (`app/annotate.py`)

The annotation tool enforces all Phase 3 governance rules and integrity protections:
1. **Zero Auto-Verification:** Any suggestions imported from automated tools (e.g., Baseline B1 or LLM drafts) display a prominent visual banner `[DRAFT - AI SUGGESTION]` and are persisted with `label_status='draft'`.
2. **Strict Validation Before Verification:** When an annotator clicks `Confirm & VERIFY Requirement`:
   - For any gap with `gap_type` in `('ambiguity', 'incompleteness')`, `span_text` must be a non-empty, exact substring of the requirement text.
   - Clarification questions must contain **exactly one question mark**, located at the end (`count('?') == 1` and `endswith('?')`). Additional or misplaced question marks are rejected.
   - Severity must be in `{1, 2, 3}` and explanation cannot be empty.
   - Validation failure blocks the save and displays an error banner in the UI.
3. **Multi-Gap Support (One-Row-Per-Gap Schema):** Annotators can record multiple defects for a single requirement (`➕ Add Another Gap`). All gaps are saved without replacing or overwriting previously added gaps.
4. **Clean Requirement Exclusivity:** Annotators can confirm a requirement has no defects via `Confirm & VERIFY Clean Requirement`, saving `has_gap=0` and `label_status='verified'`. If clean is confirmed, any existing gap rows for that requirement are removed so clean and defect rows never coexist.
5. **Launch Command:**
   ```powershell
   python -m checksense.cli serve --app annotate
   # Or directly:
   streamlit run app/annotate.py
   ```

---

## 4. Annotation Guidelines (`docs/annotation_guidelines.md`)

Authored comprehensive guidelines containing 2–3 positive and negative examples per subtype across the taxonomy:
- **Ambiguity:** `vague_term`, `vague_quantifier`, `anaphora`, `coordination`
- **Incompleteness:** `missing_actor`, `missing_condition`, `missing_threshold`, `missing_error_handling`
- **Implicit:** `unstated_constraint`
- **Severity Criteria:**
  - Severity 3: Wrong behavior, security compromise, safety hazard, or legal violation.
  - Severity 2: Likely rework during development or acceptance testing.
  - Severity 1: Minor stylistic or harmless omission where intent is obvious.
- **Rule 0:** Explicitly instructs annotators not to flag information that is defined elsewhere in the same specification.

---

## 5. Inter-Rater Reliability & Agreement Engine (`src/checksense/agreement.py`)

Implemented Cohen's $\kappa$ (Cohen 1960, 1968) supporting both unweighted multi-class agreement and quadratically weighted ordinal agreement for severity ratings:
- **Strict Verification Gate:** Requires human-confirmed `label_status='verified'` for all evaluated rows; raises `ValueError` if any draft or unverified rows are present.
- **Complete ID Matching:** Rejects partial intersections or missing IDs between raters. Both annotators must have annotated the exact same set of requirement IDs.
- **Integrity Validation:** Prohibits duplicate clean records and clean/gap coexistence.
- Interprets scores against the Landis & Koch (1977) benchmark.
- Produces paired confusion matrices and isolates specific requirement disagreements to streamline reconciliation meetings.
- Audits annotation queue progress via CLI:
  ```powershell
  python -m checksense.cli annotate-stats --gold-file data/gold/pilot_sample.csv
  ```
  Current audit on pilot queue confirms zero fabricated metrics:
  ```text
  Total Requirements:           50
  Verified (Human Confirmed):   0
  Draft (Awaiting Verification):50
  Unreviewed:                   0
  Clean Requirements:           0
  Total Gaps Identified:        0
  ```

---

## 6. Verification & Test Evidence

### A. Full Test Suite Execution
Executed `pytest tests -v` on Windows 11 / Python 3.12.4:
```text
============================= test session starts =============================
platform win32 -- Python 3.12.4, pytest-9.1.1, pluggy-1.7.0
rootdir: C:\Users\2005v\OneDrive\Desktop\CheckSense
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.15.1, platformdirs-4.13.5
collected 66 items

tests\test_cli.py ................                                       [ 24%]
tests\test_env.py ....                                                   [ 30%]
tests\test_phase1.py ........                                            [ 42%]
tests\test_phase2.py .....................                               [ 74%]
tests\test_phase3.py .................                                   [100%]

============================= 66 passed in 40.39s =============================
```
**Exit Code:** `0` (66 of 66 tests passing; 17 Phase 3 tests).

### B. Ruff Code Quality & Lint Audit
Executed `ruff check .`:
```text
All checks passed!
```
**Exit Code:** `0` (0 errors, 0 warnings).

### C. Environment Check Script
Executed `python scripts/check_env.py`:
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
    [+] spacy (3.8.16): spaCy NLP parser
    [?] transformers is not yet installed: Hugging Face transformers
    [+] sklearn (1.5.0): scikit-learn machine learning
    [+] pandas (3.0.6): Data manipulation
    [+] streamlit (1.66.1): Interactive web UI
============================================================
[+] Environment and repository skeleton validation PASSED!
```
**Exit Code:** `0`.

---

## 7. Governance, Invariants & Human Gate

1. **Human Labeling Gate (Active):**
   - No Phase 4 work or model training has been started.
   - Zero synthetic or fabricated annotations have been produced.
   - All 50 pilot requirements are initialized as `draft`.
2. **Licensing & Repository Hygiene:**
   - Raw datasets (`data/raw/*`), derived requirement lines (`data/interim/*.jsonl`), and gold annotation text sheets (`data/gold/*.csv`, `data/gold/*.jsonl`) remain strictly excluded from git tracking via `.gitignore`.
   - Only non-text metadata (`sample_manifest.json`, `annotations_template.csv`) is tracked.
3. **ARTA Block Maintained:**
   - Zero model training executed on ARTA.
   - Label mapping in `docs/label_mapping.md` remains strictly `PROPOSED (Awaiting Human Approval)`.

---

## 8. Remaining Human Decisions & Next Actions

Before Phase 4 can begin, human raters must complete the following actions:
1. **Annotate Pilot Sample:** Two human raters independently annotate `data/gold/pilot_sample.csv` (using `app/annotate.py`).
2. **Compute Inter-Rater Reliability:** Run `python -m checksense.cli annotate-stats --pilot-file-a rater_1.csv --pilot-file-b rater_2.csv`.
3. **Reconcile Disagreements:** Review disagreement rows and refine guidelines if $\kappa < 0.60$.
4. **Approve ARTA Label Mapping:** Review and formally approve `docs/label_mapping.md`.

---

**Execution is halted at the Human Annotation Gate.** Checkpoint 3 is submitted for human review.
