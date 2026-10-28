# CheckSense Error Analysis & Failure Modes Report

**Date:** 2026-10-28  
**Evaluation Basis:** Development / Pilot Annotations (`rater_1.csv` Provisional Reference)  
**Governing Protocol:** [docs/MASTER_SPEC.md](docs/MASTER_SPEC.md) Section 7

---

## 1. Executive Summary

- **Evaluated Requirements:** 50
- **Clean Requirements:** 18
- **Total Gold Gaps:** 47
- **Total Predicted Gaps:** 40
- **Overall Macro-F1:** `0.9032` | **Micro-F1:** `0.8966`
- **Requirement-Level Accuracy:** `0.9400`
- **Clean False-Alarm Rate:** `0.0556`

---

## 2. Confusion & Performance by Defect Class

| Defect Class | TP | FP | FN | Precision | Recall | F1 Score | F2 Score |
|---|---|---|---|---|---|---|---|
| **ambiguity** | 26 | 0 | 0 | `1.0000` | `1.0000` | `1.0000` | `1.0000` |
| **incompleteness** | 11 | 1 | 8 | `0.9167` | `0.5789` | `0.7097` | `0.6250` |
| **implicit** | 2 | 0 | 0 | `1.0000` | `1.0000` | `1.0000` | `1.0000` |

---

## 3. Slice Analysis by Requirement Token Length

Performance sliced across requirement length distributions:

| Length Slice | Requirements | Macro-F1 | Micro-F1 | Has-Gap Accuracy | Clean FAR |
|---|---|---|---|---|---|
| **short (<15 tokens)** | 14 | `0.9167` | `0.9167` | `0.9286` | `0.3333` |
| **medium (15-30 tokens)** | 30 | `0.8772` | `0.8627` | `0.9333` | `0.0000` |
| **long (>30 tokens)** | 6 | `0.6667` | `1.0000` | `1.0000` | `0.0000` |

---

## 4. Slice Analysis by Specification Domain / Document

| Specification Document | Requirements | Macro-F1 | Micro-F1 | Has-Gap Accuracy |
|---|---|---|---|---|
| **0000 - cctns** | 5 | `0.6667` | `1.0000` | `1.0000` |
| **0000 - gamma j** | 3 | `0.3333` | `0.6667` | `1.0000` |
| **1995 - gemini** | 3 | `0.3333` | `0.8000` | `1.0000` |
| **1998 - themas** | 2 | `0.3333` | `1.0000` | `1.0000` |
| **1999 - dii** | 6 | `0.5556` | `0.8000` | `0.8333` |
| **1999 - multi-mahjong** | 3 | `0.0000` | `0.0000` | `1.0000` |
| **2001 - beyond** | 2 | `0.5000` | `0.7500` | `1.0000` |
| **2001 - ctc network** | 2 | `0.3333` | `1.0000` | `1.0000` |
| **2001 - esa** | 2 | `0.3333` | `1.0000` | `1.0000` |
| **2001 - hats** | 1 | `0.0000` | `0.0000` | `1.0000` |
| **2003 - qheadache** | 1 | `0.0000` | `0.0000` | `1.0000` |
| **2005 - microcare** | 1 | `0.0000` | `0.0000` | `0.0000` |
| **2005 - nenios** | 4 | `0.5556` | `0.8000` | `0.7500` |
| **2006 - eirene sys 15** | 2 | `0.6667` | `1.0000` | `1.0000` |
| **2007 - get real 0.2** | 1 | `0.3333` | `1.0000` | `1.0000` |
| **2007-ertms** | 3 | `0.3333` | `0.8000` | `1.0000` |
| **2008 - keepass** | 4 | `1.0000` | `1.0000` | `1.0000` |
| **2009 - peppol approved** | 3 | `0.6667` | `1.0000` | `1.0000` |
| **2009 - video search** | 2 | `0.3333` | `1.0000` | `1.0000` |

---

## 5. Catalogue of Failure Cases

### 5.1 False Alarm Samples (Clean Requirements Flagged)
#### Sample FP-1: Requirement `0000 - gamma j_sent_0372` (0000 - gamma j)
- **Requirement Text:** *"Sales Person must be logged-in on the system."*
- **Spurious Detections:** incompleteness/missing_actor ('logged')
- **Diagnosis:** Clean requirement false alarm

### 5.2 False Negative Samples (Unflagged Defect Gaps)
#### Sample FN-1: Requirement `1999 - dii_sent_0169` (1999 - dii)
- **Requirement Text:** *"The COE Chief Engineer will reserve ultimate authority to mediate any unresolved disputes within all COIs."*
- **Omitted Gold Gaps:** incompleteness/missing_condition ('unresolved')
- **Diagnosis:** Defect entirely undetected (false negative)

#### Sample FN-2: Requirement `2005 - microcare_sent_0167` (2005 - microcare)
- **Requirement Text:** *"In the transaction part no of forms should match with No of Available Forms"*
- **Omitted Gold Gaps:** incompleteness/missing_error_handling ('should match')
- **Diagnosis:** Defect entirely undetected (false negative)

#### Sample FN-3: Requirement `2005 - nenios_sent_0037` (2005 - nenios)
- **Requirement Text:** *"The departure time will be used to keep track of late pick ups so the parent can be billed accordingly."*
- **Omitted Gold Gaps:** incompleteness/missing_condition ('late pick ups')
- **Diagnosis:** Defect entirely undetected (false negative)

---

## 6. Diagnostic Insights & Mitigation Roadmap

1. **Lexical False Positives:** Ambiguity detectors can over-trigger on technical domain adjectives (e.g. 'direct', 'normal', 'real-time') when evaluated out-of-context without SRS global definitions.
2. **Implicit Domain Constraints:** Implicit gaps require ontological checklist matching; non-standard actions or uncommon terminology not in ConceptNet/ontology may elude detection.
3. **Length Sensitivity:** Longer requirements (>30 tokens) exhibit higher coordination ambiguity and multiple clauses, demanding advanced syntactic clause segmentation.
