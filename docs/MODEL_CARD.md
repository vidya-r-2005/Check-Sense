# CheckSense: Model Card

**Standard:** Mitchell et al. (2019), *Model Cards for Model Reporting*, FAT* 2019.  
**Version:** 1.0.0  
**Date:** 2026-10-29  
**Specification Authority:** [docs/MASTER_SPEC.md](MASTER_SPEC.md) Sections 5, 6, 7, 8, 10, 11  
**Project Repository:** CheckSense (Python 3.12, PyTorch, spaCy, scikit-learn)  

---

## 1. Model Details

### 1.1 Overview
CheckSense is a neuro-symbolic Natural Language Processing (NLP) system designed to detect defect gaps in natural language software requirements specifications (SRS), explain each defect, formulate targeted clarification questions for stakeholders, and iteratively refine requirements using stakeholder answers while strictly preserving numeric constants.

### 1.2 Pipeline Architecture & Components

```
Software Requirement Sentence (5–60 tokens)
                  │
                  ▼
      [ Requirement Frame Parser ]
  (Actor, Modal, Action, Object, Condition, Quantity, Exception)
                  │
    ┌─────────────┼─────────────┐
    ▼             ▼             ▼
[ Head 4a ]   [ Head 4b ]   [ Head 4c ]
 Ambiguity     Complete       Implicit
- Lexicon     - Slot rules   - Ontology
- TF-IDF LR   - MLLM cues      checklist
- BIO Tagger
    │             │             │
    └─────────────┼─────────────┘
                  ▼
   [ Candidate-Level Fusion Scorer ]
   (MLP Scorer with 128 hidden units + Heuristic Fallback)
                  │
                  ▼
   [ Grounded Question & Explanation Engine ]
   (qwen2.5:7b via Ollama / Deterministic Per-Subtype Templates)
                  │
                  ▼
   [ Governed Requirement Refinement Engine ]
   (Strict Numeric Preservation Guardrail + Rule-Based Grammar Edits)
```

1. **Head 4a (Ambiguity):**
   - Lexicon regex detector (vague terms, quantifiers, anaphora, open lists).
   - Sentence smell classifier: TF-IDF word/char n-grams (1–2) + balanced L2 Logistic Regression.
   - Span tagger: Token-level BIO classifier extracting exact defect span substrings.
2. **Head 4b (Completeness):**
   - Frame-slot extraction rules over spaCy dependency parse (`en_core_web_sm`).
3. **Head 4c (Implicit Constraints):**
   - Domain ontology slot checklist (authentication, payment, deletion, upload, notification, input, search, audit).
4. **Phase 5 Fusion Scorer:**
   - Candidate-level Multi-Layer Perceptron (128-unit hidden layer, ReLU, Sigmoid output). Evaluates candidate gaps directly to compute calibrated defect probability and severity (1–3).
5. **Phase 6 Explanation & Question Generation:**
   - Local LLM (`qwen2.5:7b` via Ollama) with strict syntactic validation guardrails (parseable JSON, single '?', $\le 30$ words), with guaranteed fallback to deterministic per-subtype templates when offline.
6. **Refinement Engine:**
   - Rewrites requirements using stakeholder answers while enforcing strict numeric preservation (rejects rewrites that omit original numbers or invent unauthorized numbers).

---

## 2. Intended Use & Target Users

- **Intended Purpose:** Requirements analysis decision-support tool for systems engineers, requirements analysts, product managers, and safety auditors during specification authoring.
- **Out-of-Scope / Prohibited Uses:** Fully autonomous sign-off of safety-critical software requirements (e.g. ISO 26262, DO-178C) without human review; deploying to production specifications without domain-specific validation.

---

## 3. Training Data & Preprocessing

- **Smell Classifier:** Trained on 4,752 requirements across 24 documents from the ARTA benchmark (Femmer et al., Zenodo 4266727).
- **Span Tagger & Fusion Scorer:** Trained on 50 provisional pilot requirements (65 annotation rows) from PURE development documents (`data/gold/annotations/rater_1.csv`).
- **Feature Representations:** Lexical TF-IDF n-grams, POS tags, dependency relations, frame-slot boolean indicators, and candidate defect scores.

---

## 4. Empirical Evaluation & Quantitative Results

### 4.1 Genuine Out-of-Fold Cross-Validation vs. In-Sample Resubstitution

> [!IMPORTANT]
> **Scientific Integrity Notice:**  
> Performance scores on the provisional pilot set must be strictly distinguished between genuine out-of-fold cross-validation and in-sample resubstitution.

| Model Component | Evaluation Protocol | Metric Evaluated | Out-of-Fold Score | In-Sample Score | Scientific Interpretation |
|---|---|---|---|---|---|
| **Smell Classifier (ARTA)** | 5-fold GroupKFold by document | Macro-F1 | **`0.4844`** | `0.6512` | Genuine out-of-fold generalization across 24 unseen documents. |
| **Smell Classifier (QuRE)** | External Zero-Shot Test | Defect Recall | **`0.6805`** | N/A | Generalization on 2,187 industrial requirements without retraining. |
| **Span Tagger (Pilot)** | 5-fold GroupKFold by document | Entity F1 (Jaccard $\ge 0.5$) | **`0.2845`** | `0.8667` | Out-of-fold score (`0.2845`) measures true generalization; in-sample score reflects memorization. |
| **B2 Span Alone (Pilot)** | Resubstitution on training set | Macro-F1 | N/A | **`0.9037`** | In-sample resubstitution; model retrieves 100% of its own training entities ($FN=0$). |
| **Phase 5 Fusion (Pilot)** | 5-fold GroupKFold by document | Candidate Macro-F1 | **`0.6501`** | **`0.8850`** | Out-of-fold score is `0.6501`; in-sample resubstitution reaches `0.8850`. |
| **Fusion Calibration** | 5-fold GroupKFold by document | Expected Calibration Error | **`0.3830`** | **`0.0562`** | In-sample ECE is artificially low; out-of-fold ECE demonstrates need for external calibration. |

---

### 4.2 Comparative Baseline & Ablation Summary ([`results/summary.csv`](../results/summary.csv))

| System | System Type | Macro-F1 | Micro-F1 | Ambiguity F1 | Incompleteness F1 | Implicit F1 | Has-Gap Acc | Clean FAR | Status |
|---|---|---|---|---|---|---|---|---|---|
| **B1_rules** | Baseline | **0.7006** | 0.5714 | 0.5652 | 0.5366 | 1.0000 | 0.6600 | 0.5000 | evaluated |
| **B2_span_alone** | Baseline | **0.9037** | 0.8624 | 0.8667 | 0.8444 | 1.0000 | 0.8800 | 0.3333 | `in_sample_resubstitution` |
| **B3_zeroshot_llm** | Baseline | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.3600 | 0.0000 | `offline_llm` |
| **B4_multi_llm** | Baseline | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.3600 | 0.0000 | `offline_llm` |
| **Phase4_multi_head** | Architecture | **0.7748** | 0.7027 | 0.7879 | 0.5366 | 1.0000 | 0.7000 | 0.5000 | evaluated |
| **Phase5_fusion** | Architecture | **0.8850** | 0.8667 | 0.9455 | 0.7097 | 1.0000 | 0.9000 | 0.0000 | `in_sample_resubstitution` |
| **Ablation_no_4a** | Ablation | **0.5122** | 0.3662 | 0.0000 | 0.5366 | 1.0000 | 0.5600 | 0.3889 | evaluated |
| **Ablation_no_4b** | Ablation | **0.5960** | 0.6292 | 0.7879 | 0.0000 | 1.0000 | 0.7000 | 0.1667 | evaluated |
| **Ablation_no_4c** | Ablation | **0.4415** | 0.6789 | 0.7879 | 0.5366 | 0.0000 | 0.6800 | 0.5000 | evaluated |
| **Ablation_plain_union** | Ablation | **0.7748** | 0.7027 | 0.7879 | 0.5366 | 1.0000 | 0.7000 | 0.5000 | evaluated |

---

### 4.3 Cluster Bootstrap Confidence Intervals (1,000 Iterations)

From [`results/bootstrap_metrics.json`](../results/bootstrap_metrics.json) (seed 42, $N=50$ requirements):
- **Macro-F1:** Point Estimate = `0.9032`, Bootstrap Mean = `0.8540`, 95% CI = `[0.5402, 0.9573]`
- **Micro-F1:** Point Estimate = `0.8966`, Bootstrap Mean = `0.8962`, 95% CI = `[0.8247, 0.9583]`
- **Has-Gap Accuracy:** Point Estimate = `0.9400`, Bootstrap Mean = `0.9403`, 95% CI = `[0.8795, 1.0000]`
- **Clean FAR:** Point Estimate = `0.0556`, Bootstrap Mean = `0.0562`, 95% CI = `[0.0000, 0.1820]`

---

## 5. Failure Modes & Limitations

1. **Lack of Global SRS Context:** Detectors operate on individual sentence units. Domain terminology defined in a specification's glossary or architecture overview may be falsely flagged as a `vague_term` or `missing_condition`.
2. **Provisional Pilot Reference:** Trained on Rater 1's pilot annotations (pilot inter-rater Cohen's $\kappa = -0.1179$). Classifiers reflect Rater 1's labeling threshold.
3. **Implicit Head Lexical Dependency:** Head 4c relies on ontology keywords. Novel domain operations not in the checklist ontology may elude implicit omission detection.
4. **Local LLM Availability:** Baselines B3 and B4 require a running Ollama daemon. When offline, deterministic fallback templates guarantee 100% operational availability without synthetic outputs.

---

## 6. Safeguards & Hallucination Mitigations

- **Strict Numeric Preservation:** Refinement engine rejects any rewrite that drops numbers or invents unauthorized numbers not present in the requirement or stakeholder answer.
- **Syntactic Question Validation:** Enforces exactly one question mark `'?'`, maximum 30 words, and parseable JSON.
- **Deterministic Fallbacks:** Immediate fallback to rule-based grammar edits and per-subtype templates whenever validation fails or models are unreachable.

---

## 7. Held-Out Test Set Governance

`data/gold/test_pool.jsonl` (150 requirements from 6 documents) remains **strictly sealed and untouched**. No model training, tuning, feature fitting, or evaluation has accessed or will access this pool until human double-annotation and reconciliation are complete.

---

## 8. Reproducibility & Model Artifacts

All models and reports are reproducible via standard CLI invocations:

```powershell
# Retrain smell classifier
python -m checksense.cli train-smell

# Retrain span tagger
python -m checksense.cli train-span

# Retrain fusion scorer
python -m checksense.cli train-fusion

# Reproduce summary benchmark, bootstrap CIs, and paper-style monograph
python -m checksense.cli report
```

