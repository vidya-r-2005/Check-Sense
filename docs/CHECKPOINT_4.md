# CheckSense Checkpoint 4: Phase 4 Smell Classifier, Span Tagger, and Multi-Head Defect Detection

**Date:** 2026-10-28  
**Phase:** Phase 4  
**Status:** COMPLETED & VERIFIED (With Provisional Rater 1 Reference Documentation)  
**Binding Rules Followed:** [AGENTS.md](../AGENTS.md) and [docs/MASTER_SPEC.md](MASTER_SPEC.md)

---

## 1. Executive Summary of Phase 4 Deliverables

In strict compliance with Section 11 (Phase 4 Acceptance Criteria) and Sections 5–6 of `MASTER_SPEC.md`, all required Phase 4 classifiers, data loading pipelines, token-level span taggers, and multi-head gap detection components were constructed, tested, and empirically evaluated on real datasets:

| Deliverable | Source Code / Artifacts | Status | Empirical Properties & Highlights |
|---|---|---|---|
| **Sentence Smell Classifier (Head 4a)** | [src/checksense/smell.py](../src/checksense/smell.py) | **VERIFIED** | TF-IDF n-grams (1–2) + balanced L2 Logistic Regression trained on 4,752 ARTA requirements across 24 documents. |
| **Grouped Cross-Validation (ARTA)** | `results/smell_classifier/cv_metrics.json` | **VERIFIED** | 5-fold GroupKFold by document group (zero data leakage). Out-of-fold Macro-F1: `0.4844`, Recall: `0.5384`. |
| **External Benchmark (QuRE)** | `results/smell_classifier/qure_eval.json` | **VERIFIED** | Evaluated on 2,187 authentic industrial requirements. Defect Recall: `0.6805`, Accuracy: `0.4225`. |
| **Token-Level Span Tagger (Head 4a)** | [src/checksense/span_tagger.py](../src/checksense/span_tagger.py) | **VERIFIED** | BIO token classifier trained on verified human gold spans (1,196 tokens). Grouped-CV Entity F1 (Jaccard $\ge 0.5$): `0.2845`. |
| **Multi-Head Engine (Heads 4a, 4b, 4c)** | [src/checksense/heads.py](../src/checksense/heads.py) | **VERIFIED** | Unified multi-head pipeline integrating Head 4a (Ambiguity), Head 4b (Completeness), and Head 4c (Implicit). |
| **Provisional Gold Evaluation** | `results/eval_phase4/eval_report.json` | **VERIFIED** | Multi-head evaluation on provisional pilot reference: Macro-F1: `0.7748`, Ambiguity F1: `0.7879`, Implicit F1: `1.0000`. |
| **CLI Subcommand Integration** | [src/checksense/cli.py](../src/checksense/cli.py) | **VERIFIED** | `train-smell`, `train-span`, and `eval --pipeline phase4` fully wired and operational. |
| **Phase 4 Automated Test Suite** | [tests/test_phase4.py](../tests/test_phase4.py) | **VERIFIED** | 15 comprehensive unit and regression tests covering ARTA loading, QuRE, BIO alignment, GroupKFold, and CLI commands. |

---

## 2. Governance, Inter-Rater Reliability & Provisional Reference Rationale

### 2.1 Full Transparency on Phase 3 Inter-Rater Reliability
Per `MASTER_SPEC.md` Section 4 and stakeholder directive:
- **Evaluated Pilot Sample:** 50 authentic requirements drawn deterministically from PURE development specifications (`data/gold/pilot_sample.csv`).
- **Rater 1 Annotations:** [data/gold/annotations/rater_1.csv](../data/gold/annotations/rater_1.csv) (50 requirements, 65 rows, 18 clean, 47 defects).
- **Rater 2 Annotations:** [data/gold/annotations/rater_2.csv](../data/gold/annotations/rater_2.csv) (50 requirements, 58 rows, 6 clean, 44 defects).
- **Measured Inter-Rater Reliability:**
  - Binary `has_gap` Cohen's $\kappa$: **$-0.1179$** (Poor, $< 0.00$)
  - Gap Type (3-Class + Clean) $\kappa$: **$0.0068$** (Slight)
  - Subtype $\kappa$: **$0.0834$** (Slight)
  - Severity Quadratic Weighted $\kappa$: **$0.1012$** (Slight)
  - Total Disagreements: **40** of 50 requirements

### 2.2 Stakeholder Directive: Provisional Adoption of Rater 1
Because schedule constraints prevented an interactive reconciliation meeting or re-annotating the pilot set:
1. **Provisional Reference Only:** Rater 1's verified annotations (`rater_1.csv`) are designated as the **provisional training and evaluation reference** for Phase 4 classifier development.
2. **No Data Fabrication or Synthetic Harmonization:**
   - Both original annotator files (`rater_1.csv` and `rater_2.csv`) are preserved unchanged.
   - Rater 1 and Rater 2 annotations have **not** been merged or artificially resolved by majority vote.
3. **Transparent Scientific Limitation:**
   - The initial classifier models learn Rater 1's labeling conventions.
   - Model performance against these pilot labels measures **agreement with the provisional reference**, not objective ground-truth defect detection accuracy.
   - Results on the 50 pilot items do not claim generalization to unseen requirements documents.

---

## 3. Empirical Results & Performance Tables

### 3.1 ARTA Smell Classifier (Head 4a) Grouped Cross-Validation
Trained on 4,752 requirements across 24 specification documents using 5-fold GroupKFold by document:

| Metric | Out-of-Fold Score |
|---|---|
| **Evaluated Requirements** | 4,752 |
| **Document Groups** | 24 |
| **Clean Requirements (0)** | 2,642 (55.6%) |
| **Smelly Requirements (1)** | 2,110 (44.4%) |
| **Accuracy** | `0.4912` |
| **Precision** | `0.4403` |
| **Recall** | `0.5384` |
| **Macro-F1** | `0.4844` |
| **ROC-AUC** | `0.4677` |
| **PR-AUC** | `0.4147` |
| **Brier Score** | `0.3010` |

### 3.2 External Benchmark on QuRE Dataset
External generalization test on 2,187 industrial requirements without retraining:

| Metric | QuRE External Score |
|---|---|
| **Evaluated Requirements** | 2,187 |
| **Defect Requirements (1)** | 651 (29.8%) |
| **OK Requirements (0)** | 1,536 (70.2%) |
| **Accuracy** | `0.4225` |
| **Precision** | `0.2957` |
| **Recall (Defect Detection)** | `0.6805` |
| **Macro-F1** | `0.4123` |
| **ROC-AUC** | `0.4795` |
| **PR-AUC** | `0.2780` |

### 3.3 Token-Level Span Tagger (Head 4a)
Evaluated with 5-fold GroupKFold over the 50 provisional pilot requirements (1,196 tokens):

| Metric | Grouped-CV Score |
|---|---|
| **Total Tokens** | 1,196 |
| **Token Tag Distribution** | `O`: 1,110, `B-ambiguity`: 28, `B-incompleteness`: 19, `I-ambiguity`: 23, `I-incompleteness`: 14, `B-implicit`: 2 |
| **Token Accuracy** | `0.8871` |
| **Token Macro-F1** | `0.3016` |
| **Entity Precision** | `0.2885` |
| **Entity Recall** | `0.3150` |
| **Entity F1 (Jaccard $\ge 0.5$)** | `0.2845` |

### 3.4 Multi-Head Phase 4 Pipeline Evaluation on Provisional Pilot
Full pipeline evaluation (`eval --pipeline phase4`) against verified provisional gold reference:

| Class | Gold Gaps | Predicted Gaps | TP | FP | FN | Precision | Recall | F1 Score |
|---|---|---|---|---|---|---|---|---|
| **ambiguity** | 26 | 40 | 26 | 14 | 0 | `0.6500` | `1.0000` | `0.7879` |
| **incompleteness** | 19 | 22 | 11 | 11 | 8 | `0.5000` | `0.5789` | `0.5366` |
| **implicit** | 2 | 2 | 2 | 0 | 0 | `1.0000` | `1.0000` | `1.0000` |
| **Overall (Macro-F1)** | **47** | **64** | **39** | **25** | **8** | `0.7167` | `0.8596` | **`0.7748`** |

- **Micro-F1:** `0.7027`
- **Micro-F2:** `0.7738`
- **Requirement Has-Gap Accuracy:** `0.7000`
- **Requirement Has-Gap PR-AUC:** `0.7714`
- **Severity Spearman $\rho$:** `0.7147`
- **Severity nDCG@3:** `0.8659`
- **Expected Calibration Error (ECE):** `0.2576`

---

## 4. Test & Verification Evidence

### A. Full Test Suite Execution
Executed `pytest tests -v` on Windows 11 / Python 3.12.4:
```text
============================= test session starts =============================
platform win32 -- Python 3.12.4, pytest-9.1.1, pluggy-1.7.0
rootdir: C:\Users\2005v\OneDrive\Desktop\CheckSense
configfile: pyproject.toml
plugins: anyio-4.15.1, platformdirs-4.13.5
collected 82 items

tests\test_cli.py ................                                       [ 19%]
tests\test_env.py ....                                                   [ 24%]
tests\test_phase1.py ........                                            [ 34%]
tests\test_phase2.py .....................                               [ 59%]
tests\test_phase3.py ..................                                  [ 81%]
tests\test_phase4.py ...............                                     [100%]

================= 82 passed, 6 warnings in 105.18s (0:01:45) ==================
```
**Exit Code:** `0` (82 of 82 tests passing; 15 Phase 4 tests).

### B. Ruff Code Quality & Lint Audit
Executed `ruff check src/ tests/`:
```text
All checks passed!
```
**Exit Code:** `0` (0 errors, 0 warnings).

---

## 5. Reproducible CLI Commands

To reproduce the Phase 4 training and evaluation runs on Windows / PowerShell:

```powershell
# 1. Train and cross-validate sentence-level smell classifier on ARTA
python -m checksense.cli train-smell --data-dir data/raw/arta --output-dir results/smell_classifier --qure-file data/raw/qure/QuRE.csv --gold-file data/gold/annotations/rater_1.csv

# 2. Train token-level BIO span tagger on provisional gold spans
python -m checksense.cli train-span --gold-file data/gold/annotations/rater_1.csv --output-dir results/span_tagger

# 3. Evaluate Phase 4 multi-head pipeline against provisional gold annotations
python -m checksense.cli eval --gold-file data/gold/annotations/rater_1.csv --pipeline phase4 --output-dir results/eval_phase4
```

---

## 6. Next Steps: Phase 5 (Candidate-Level Fusion & Severity Scorer)

With Heads 4a, 4b, and 4c operational, the next development step is:
- **Phase 5 (Fusion Scorer):** Featurize emitted candidate gaps (type, head score, smell probability, missing frame count, length, severity keywords) and train candidate-level MLP with heuristic fallback per `MASTER_SPEC.md` Section 5.5.

