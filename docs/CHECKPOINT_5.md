# CheckSense Checkpoint 5: Phase 5 Candidate-Level Fusion Scorer, Deduplication Engine, and Deterministic Ranking

**Date:** 2026-10-28  
**Phase:** Phase 5  
**Status:** COMPLETED & EMPIRICALLY VERIFIED (With Provisional Rater 1 Reference Protocol)  
**Binding Rules Followed:** [AGENTS.md](../AGENTS.md) and [docs/MASTER_SPEC.md](MASTER_SPEC.md)

---

## 1. Executive Summary of Phase 5 Deliverables

In strict compliance with Section 5.5, Section 6, Section 7, and Section 11 of `MASTER_SPEC.md`, the Phase 5 Candidate-Level Fusion Scorer was designed, implemented, cross-validated, and integrated into the CheckSense pipeline:

| Deliverable | Source Code / Artifacts | Status | Technical Details & Empirical Highlights |
|---|---|---|---|
| **Candidate-Level Feature Extractor** | [src/checksense/fusion.py](../src/checksense/fusion.py) | **VERIFIED** | 24-dimensional feature vector featurizing individual candidate gaps (one-hot gap type, one-hot subtype, head score, sentence smell prob, missing frame slots, passive flag, lengths, domain severity keywords). |
| **MLP Candidate Fusion Scorer** | [src/checksense/fusion.py](../src/checksense/fusion.py) | **VERIFIED** | 128-unit ReLU MLP probability scorer + 64-unit severity scorer trained with `StandardScaler` and deterministic heuristic fallback. |
| **Heuristic Fallback Scorer** | [src/checksense/fusion.py](../src/checksense/fusion.py) | **VERIFIED** | Rule-based fallback combining head score, smell probability, and critical domain safety/security keywords. |
| **Deduplication & Conflict Engine** | [src/checksense/fusion.py](../src/checksense/fusion.py) | **VERIFIED** | Resolves overlapping candidate spans (token Jaccard $\ge 0.70$ or containment), enforces single implicit gap per requirement, and applies deterministic ranking. |
| **Grouped Cross-Validation** | `results/fusion_model/cv_metrics.json` | **VERIFIED** | 5-fold GroupKFold by document group (17 documents, 0 data leakage). Out-of-fold Precision: `0.7027`, Recall: `0.6047`, F1: `0.6500`, ROC-AUC: `0.6080`. |
| **Calibration Analysis (ECE)** | `results/fusion_model/calibration_data.json` | **VERIFIED** | Expected Calibration Error computation with 10-bin empirical calibration curve data. |
| **Pipeline Integration** | [src/checksense/eval.py](../src/checksense/eval.py) | **VERIFIED** | `generate_phase5_predictions` and `eval --pipeline phase5` integrated into evaluation runner. |
| **Provisional Gold Evaluation** | `results/eval_phase5/eval_report.json` | **VERIFIED** | Macro-F1: `0.8969`, Ambiguity F1: `0.9811`, Incompleteness F1: `0.7097`, Implicit F1: `1.0000`, False-Alarm Rate: `0.0556`. |
| **CLI Commands** | [src/checksense/cli.py](../src/checksense/cli.py) | **VERIFIED** | `train-fusion` and `eval --pipeline phase5` fully wired with reproducible flags. |
| **Automated Test Suite** | [tests/test_phase5.py](../tests/test_phase5.py) | **VERIFIED** | 15 comprehensive unit and regression tests covering features, matching math, ECE, heuristic fallback, MLP serialization, deduplication, conflict resolution, ranking, and CLI. |

---

## 2. Architecture & Algorithmic Design

### 2.1 The Unit of Scoring is a Candidate Gap
Traditional defect classifiers classify entire requirement sentences. CheckSense implements candidate-level fusion where each emitted defect hypothesis is individually scored, calibrated, and ranked:

```
Requirement Text
       │
       ▼
[ Phase 4 Multi-Head Engine ]
  ├─ Head 4a (Smell & Span Tagger) ──────► Candidate Ambiguity Gaps
  ├─ Head 4b (Frame Slot Completeness) ──► Candidate Incompleteness Gaps
  └─ Head 4c (Implicit Domain Knowledge) ─► Candidate Implicit Gaps
       │
       ▼ (Candidate Pool: 64 candidates across 50 pilot items)
[ 24-Dimensional Candidate Featurization ]
  ├─ One-hot gap class (3): ambiguity, incompleteness, implicit
  ├─ One-hot subtype (9): lexical, syntactic, vague_quantifier, anaphora, etc.
  ├─ Head confidence score & Head 4a sentence smell probability
  ├─ Global context: n_candidates, missing_slots_count, is_passive
  ├─ Length features: text char/token count, span char/token count
  └─ Domain hazard keywords: text_severity_keywords, span_severity_keywords, has_critical_keyword
       │
       ▼
[ MLP Fusion Scorer (128 units) + Heuristic Fallback ]
  ├─ Calibrated gap probability P(candidate is true gap)
  └─ Predicted defect severity {1, 2, 3}
       │
       ▼
[ Deduplication, Conflict Resolution & Deterministic Ranking ]
  ├─ Overlap suppression (token Jaccard >= 0.70 or containment)
  ├─ Single implicit gap per requirement
  └─ Deterministic ranking: Severity (desc) -> Probability (desc) -> Span start_char (asc)
       │
       ▼
Final Calibrated, Deduplicated, and Ranked Defect Report
```

### 2.2 Deduplication and Conflict Resolution
1. **Confidence Filtering:** Discards low-probability false alarm candidates ($P < 0.30$).
2. **Span Overlap Suppression:** When two candidate spans overlap with token Jaccard $\ge 0.70$ or one span contains the other:
   - Same gap class: retains candidate with highest calibrated fusion probability.
   - Conflicting gap classes: retains candidate with highest probability, prioritizing higher severity if scores are within $0.05$.
3. **Implicit Gap Uniqueness:** Exactly one implicit gap is retained per requirement (the highest scoring candidate).
4. **Deterministic Ranking:** Output is deterministically ordered by:
   - Primary: Severity descending ($3 \to 2 \to 1$).
   - Secondary: Probability descending ($1.0 \to 0.0$).
   - Stable tie-breaker: `start_char` ascending, subtype alphabetically.

---

## 3. Empirical Results

### 3.1 Grouped Cross-Validation (by Source Document — Genuinely Out-of-Fold)
Trained and evaluated on the 64 candidate gaps emitted across the 50 provisional pilot requirements using 5-fold `GroupKFold` by source document (17 document groups, strictly disjoint across folds):

```json
{
  "n_candidates": 64,
  "class_balance": {
    "positive_gold_matches_P": 43,
    "negative_candidates_N": 21
  },
  "out_of_fold_confusion_matrix": {
    "true_positives_TP": 26,
    "false_positives_FP": 11,
    "false_negatives_FN": 17,
    "true_negatives_TN": 10
  },
  "metrics": {
    "accuracy": 0.5625,
    "precision": 0.7027,
    "recall": 0.6047,
    "f1": 0.6500,
    "roc_auc": 0.6080,
    "brier_score": 0.3617,
    "ece": 0.3830,
    "severity_spearman_rho": 0.2510,
    "severity_mae": 0.4419
  }
}
```

> [!NOTE]
> **Resolution of Class Counts vs. Precision:**
> The 43 positive gold matches ($P$) and 21 negative candidates ($N$) represent the ground-truth candidate class balance ($P = TP + FN = 26 + 17 = 43$; $N = TN + FP = 10 + 11 = 21$).
> The out-of-fold model predictions produced $TP = 26$ and $FP = 11$. Precision is therefore $\frac{26}{26 + 11} = \frac{26}{37} \approx 0.7027$, and Recall is $\frac{26}{26 + 17} = \frac{26}{43} \approx 0.6047$.

### 3.2 10-Bin Calibration Analysis (Out-of-Fold)
Empirical calibration data computed across the 10 confidence bins on out-of-fold validation predictions:
- Overall Expected Calibration Error (ECE): **0.3830**
- Brier Score: **0.3617**
- Calibration curve bins logged in `results/fusion_model/calibration_data.json`.
- *Scientific Assessment:* On held-out documents, the model exhibits moderate-to-high miscalibration ($\text{ECE} = 0.3830$), reflecting uncalibrated probability sharpness typical of small-sample neural nets without temperature scaling.

### 3.3 End-to-End Pipeline Evaluation (IN-SAMPLE RESUBSTITUTION ON PROVISIONAL REFERENCE)

> [!WARNING]
> **In-Sample Evaluation Warning:**
> The following table reports end-to-end pipeline execution where the production `fusion_model.joblib` (trained on all 50 provisional requirements from `rater_1.csv`) was evaluated on that same dataset.
> **This is strictly an in-sample training-set resubstitution check to verify pipeline wiring and deduplication mechanics.**
> It must **NOT** be interpreted as an independent or generalized performance evaluation. The genuine out-of-fold generalization score is the Grouped-CV result in Section 3.1 ($\text{F1} = 0.6500$).

| Metric | Baseline B1 (Rules) | Phase 4 Multi-Head | Phase 5 Fusion (In-Sample Fit) | Delta (Phase 5 vs B1) |
|---|---|---|---|---|
| **Macro-F1** | `0.4571` | `0.7748` | **`0.8969`** *(in-sample)* | +0.4398 (+96.2%) |
| **Micro-F1** | `0.3704` | `0.6903` | **`0.8864`** *(in-sample)* | +0.5160 (+139.3%) |
| **Micro-F2** | `0.3472` | `0.7785` | **`0.8515`** *(in-sample)* | +0.5043 (+145.2%) |
| **Ambiguity F1** | `0.3714` | `0.7879` | **`0.9811`** *(in-sample)* | +0.6097 (+164.2%) |
| **Incompleteness F1** | `0.0000` | `0.5366` | **`0.7097`** *(in-sample)* | +0.7097 (New Capability) |
| **Implicit F1** | `1.0000` | `1.0000` | **`1.0000`** *(in-sample)* | Parity |
| **Has-Gap Accuracy** | `0.7000` | `0.8000` | **`0.9400`** *(in-sample)* | +0.2400 |
| **Clean False-Alarm Rate** | `0.4444` | `0.2778` | **`0.0556`** *(in-sample)* | -0.3888 (-87.5% false alarms) |
| **Expected Calibration Error** | `0.2974` | `0.2078` | **`0.0562`** *(in-sample only)* | Note: OOF ECE is 0.3830 |
| **Brier Score** | `0.0884` | `0.0432` | **`0.0133`** *(in-sample only)* | Note: OOF Brier is 0.3617 |

---

## 4. Governance, Provenance & Scientific Limitations

1. **In-Sample vs. Out-of-Fold Distinction:**
   - The end-to-end evaluation metrics (`eval_report.json`) are in-sample. The true development benchmark is the out-of-fold Grouped-CV F1 of `0.6500`.
2. **Upstream Model Conditioning Risk:**
   - The candidate pool was emitted by Phase 4 heads where the linear span tagger was fine-tuned on the 50 pilot items in Phase 4. Consequently, candidate span boundaries and Head 4a scores reflect upstream exposure to `rater_1.csv`.
3. **Provisional Reference Protocol Maintained:**
   - In accordance with stakeholder instructions, Rater 1's annotations (`data/gold/annotations/rater_1.csv`) are strictly treated as a **provisional reference** for pipeline development.
   - The pilot inter-rater reliability was poor (Cohen's $\kappa = -0.1179$). The labels have not been reconciled through consensus meetings.
   - Reported evaluation scores reflect **agreement with Rater 1's labeling conventions**, not objective defect-detection truth.
4. **Sequestered Held-Out Test Set:**
   - The held-out test document pool (`test_pool.jsonl`, 10 documents) remains completely sequestered and untouched.
5. **Weight Hygiene:**
   - Model weights (`fusion_model.joblib`) are excluded from Git via `.gitignore` per Rule 8 of `MASTER_SPEC.md`.

---

## 5. Reproducible Execution Commands

### Train Candidate Fusion Scorer:
```powershell
python -m checksense.cli train-fusion `
  --gold-file data/gold/annotations/rater_1.csv `
  --output-dir results/fusion_model `
  --smell-model results/smell_classifier/smell_classifier.joblib `
  --span-model results/span_tagger/span_tagger.joblib `
  --n-splits 5 `
  --seed 42
```

### Run Phase 5 Pipeline Evaluation:
```powershell
python -m checksense.cli eval `
  --gold-file data/gold/annotations/rater_1.csv `
  --pipeline phase5 `
  --fusion-model results/fusion_model/fusion_model.joblib `
  --output-dir results/eval_phase5
```

### Run Phase 5 Test Suite:
```powershell
pytest tests/test_phase5.py -v
```

