# CheckSense Checkpoint 8: Phase 8 Full Evaluation Suite, Human Rating Tools, and Paper-Style Monograph Report

**Date:** 2026-10-28  
**Phase:** Phase 8  
**Status:** COMPLETED & VERIFIED (Report Generated Strictly from Results; Limitations Documented; Sequestered Test Pool Sealed)  
**Binding Rules Followed:** [AGENTS.md](../AGENTS.md) and [docs/MASTER_SPEC.md](MASTER_SPEC.md)

---

## 1. Executive Summary & Acceptance Criteria Verification

In strict compliance with Section 11 (Phase 8 Acceptance Criteria), Section 7, Section 8, and Section 9 of `docs/MASTER_SPEC.md`:

| Requirement | Prescribed Criterion | Result / Verification Status |
|---|---|---|
| **Phase 8 Acceptance Criterion** | *"Report generated from results/ only; limitations section written"* | **PASSED:** [`reports/final_report.md`](../reports/final_report.md) generated strictly from artifacts in `results/`, containing comprehensive Limitations and Ethics sections. |
| **Error Analysis Report** | *"reports/error_analysis.md: Slices by token length and domain, confusion matrix, failure cases"* | **PASSED:** [`reports/error_analysis.md`](../reports/error_analysis.md) generated with class confusion matrices, length slices, domain slices, and detailed failure case catalogues. |
| **rate-make CLI Tool** | Randomized, blinded human-rating sheets with reference questions mixed in | **PASSED:** Generates blinded sheets ([`results/ratings/blinded_rating_sheet.csv`](../results/ratings/blinded_rating_sheet.csv)) and unblinding keys ([`results/ratings/blinding_key.json`](../results/ratings/blinding_key.json)). |
| **rate-score CLI Tool** | Multi-rater agreement (quadratic-weighted $\kappa$) and paired bootstrap non-inferiority test ($\Delta = 0.5$) | **PASSED:** Fully implemented and verified in [`src/checksense/rating.py`](../src/checksense/rating.py); evaluates completed rating sheets from 2+ raters. |
| **Cluster Bootstrap Engine** | 1,000-sample bootstrap confidence intervals resampling requirements | **PASSED:** [`results/bootstrap_metrics.json`](../results/bootstrap_metrics.json) records empirical 95% CIs and standard errors across all metrics. |
| **Refinement Assessment Engine** | Gap-closure rate, newly introduced defect rate, and ISO/IEC/IEEE 29148 characteristics | **PASSED:** [`results/refinement_metrics.json`](../results/refinement_metrics.json) evaluates singularity, completeness, ambiguity, and strict numeric preservation. |
| **Test Pool Sequestering Safeguard** | `data/gold/test_pool.jsonl` (150 requirements from 6 documents) | **MAINTAINED:** Zero held-out test data accessed, trained on, tuned on, or synthesized. Test set remains 100% sealed pending human double-annotation and reconciliation. |

---

## 2. Quantitative Results & Statistical Rigor

### 2.1 1,000-Sample Cluster Bootstrap Confidence Intervals ([`results/bootstrap_metrics.json`](../results/bootstrap_metrics.json))

Cluster resampling of requirements ($B = 1000$ iterations, seed 42) for Phase 5 Candidate Fusion on the provisional pilot set:

| Evaluation Metric | Point Estimate | Bootstrap Mean | Standard Error | 95% Bootstrap Confidence Interval |
|---|---|---|---|---|
| **Macro-F1** | `0.9032` | `0.8540` | `0.1219` | `[0.5402, 0.9573]` |
| **Micro-F1** | `0.8966` | `0.8962` | `0.0350` | `[0.8247, 0.9583]` |
| **Micro-F2** | `0.8553` | `0.8563` | `0.0479` | `[0.7655, 0.9404]` |
| **Has-Gap Accuracy** | `0.9400` | `0.9403` | `0.0336` | `[0.8795, 1.0000]` |
| **Has-Gap PR-AUC** | `0.9816` | `0.9816` | `0.0115` | `[0.9561, 1.0000]` |
| **Clean False-Alarm Rate** | `0.0556` | `0.0562` | `0.0546` | `[0.0000, 0.1820]` |
| **Expected Calibration Error (ECE)** | `0.0309` | `0.0310` | `0.0113` | `[0.0120, 0.0555]` |
| **Brier Score** | `0.0058` | `0.0059` | `0.0032` | `[0.0006, 0.0129]` |

*Note on In-Sample Resubstitution:* The point estimate reflects the end-to-end model evaluated on its pilot training set; out-of-fold Grouped-CV estimates are detailed in Checkpoint 5.

---

### 2.2 Requirement Refinement Quality & ISO/IEC/IEEE 29148 Assessment ([`results/refinement_metrics.json`](../results/refinement_metrics.json))

| Quality Dimension | Measured Score | Evaluation Notes |
|---|---|---|
| **Numeric Preservation Rate** | **`100.0%`** | Exactly zero original numbers dropped and zero unauthorized numbers invented. |
| **Newly Introduced Defect Rate** | **`0.0000` gaps/req** | Zero new syntactic or lexical defects introduced during rewrite. |
| **ISO 29148 Conformance Score** | **`0.7500`** | Enforces singular normative action, unstated ambiguity elimination, and frame completion. |

---

## 3. Human Rating Tooling Workflow (`rate-make` & `rate-score`)

```
   Candidate System Questions (CheckSense / Baselines)
                          │
                          ▼
             [ Human Reference Questions ]
                          │
                          ▼
       python -m checksense.cli rate-make --output-sheet ...
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
     [ Blinded Rater Sheet ]    [ Unblinding Key ]
    (Randomized Q0001..Q0094)   (results/ratings/blinding_key.json)
              │
              ├───────────────────────┐
              ▼                       ▼
     [ Human Rater 1 Sheet ]    [ Human Rater 2 Sheet ]
    (Clarity, Relevance, Info, (Clarity, Relevance, Info,
     Answerable, Hallucinated)  Answerable, Hallucinated)
              │                       │
              └───────────┬───────────┘
                          │
                          ▼
       python -m checksense.cli rate-score --sheet-a ... --sheet-b ...
                          │
                          ▼
       [ Inter-Rater Reliability (Quadratic Weighted Kappa) ]
       [ Paired Non-Inferiority Bootstrap Test (Delta = 0.5) ]
       [ results/ratings/rating_scores.json ]
```

---

## 4. Scientific Limitations & Threats to Validity

In accordance with `MASTER_SPEC.md` Section 10 and Section 11, the following limitations are formally documented in [`reports/final_report.md`](../reports/final_report.md):

1. **Provisional Development Reference:** The initial multi-head detectors and fusion scorer were trained on Rater 1's pilot annotations (`rater_1.csv`) under a stakeholder directive to proceed without re-annotation. Inter-rater reliability on the pilot was low (Cohen's $\kappa = -0.1179$). Performance metrics on this sample measure agreement with Rater 1 rather than independently validated ground truth.
2. **In-Sample Evaluation on Pilot:** Baselines B2 and the Phase 5 fusion model evaluated on `rater_1.csv` were trained on those same 50 requirements, yielding in-sample resubstitution scores (e.g. 100% recall in B2). Genuinely out-of-fold GroupKFold cross-validation metrics are documented separately in Checkpoints 4 and 5.
3. **Local LLM Availability:** Full execution of Baselines B3 and B4 requires an active Ollama instance (`localhost:11434`). CheckSense gracefully handles headless offline execution via deterministic templates without fabricating outputs.
4. **Sequestered Held-Out Test Set:** `data/gold/test_pool.jsonl` (150 requirements from 6 documents) remains unannotated by humans and completely sealed. In accordance with Section 0.4 and Section 4, agents are strictly forbidden from self-certifying synthetic test labels. Full test-set evaluation will occur only after human double-annotation and reconciliation.

---

## 5. Reproducible Execution Commands

All Phase 8 outputs can be reproduced via one-line CLI commands:

```powershell
# 1. Compile summary tables, bootstrap CIs, refinement metrics, error analysis, and final monograph
python -m checksense.cli report

# 2. Generate blinded human-rating sheet for questions
python -m checksense.cli rate-make `
  --output-sheet results/ratings/blinded_rating_sheet.csv `
  --key-file results/ratings/blinding_key.json

# 3. Score completed human rating sheets from two raters
python -m checksense.cli rate-score `
  --sheet-a results/ratings/sheet_rater1.csv `
  --sheet-b results/ratings/sheet_rater2.csv `
  --key-file results/ratings/blinding_key.json `
  --output-dir results/ratings

# 4. Run full test suite across all phases (Phases 0-8)
pytest tests -v
```
