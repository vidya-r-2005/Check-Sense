# CheckSense: Datasheet for Datasets

**Standard:** Gebru et al. (2021), *Datasheets for Datasets*, Communications of the ACM.  
**Version:** 1.0.0  
**Date:** 2026-10-29  
**Specification Authority:** [docs/MASTER_SPEC.md](MASTER_SPEC.md) Sections 2, 3, 4, 10  
**Project:** CheckSense Requirements Defect Analysis Engine  

---

## 1. Motivation

- **For what purpose was the dataset created?**  
  The CheckSense data collection was created to support research and development of NLP systems that detect semantic, syntactic, and structural defect gaps in natural language Software Requirements Specifications (SRS). Specifically, it targets three defect classes: *ambiguity*, *incompleteness*, and *implicit unstated constraints*.
- **Who created the dataset and on behalf of which entity?**  
  Compiled and curated by the CheckSense research team from peer-reviewed public requirements engineering benchmarks (PURE, ARTA, QuRE) and structured human annotations.
- **Who funded the creation of the dataset?**  
  Academic research and open-source software engineering community benchmarking.

---

## 2. Composition

### 2.1 Component Datasets & Sources

| Dataset Component | Source & Provenance | Size & Records | Role in CheckSense | License & Permitted Uses |
|---|---|---|---|---|
| **PURE (Public Requirements Dataset)** | Zenodo record `7118517` / `1414116` (Ferrari et al., RE 2017) | 79 specifications (18 XML parsed; 13,394 raw sentences; 4,023 retained requirements) | Base corpus for sampling candidate requirements | CC-BY-4.0. Note: Curators gathered original PDFs/XML from web sources without formal licenses and maintain a takedown notice. Permitted for academic benchmarking. |
| **ARTA Smell Dataset** | Zenodo record `4266727` (v1.0.0, Femmer et al.) | 4 spreadsheets; 4,752 requirements across 24 specification documents | Training and grouped cross-validation of Head 4a sentence-level smell classifier | Open academic research fair use deposit. |
| **QuRE (Industrial Requirements Quality)** | Zenodo record `15656471` (RE Open Data community) | 2,187 real-world industrial requirements | External zero-shot benchmark for smell and defect classification | Creative Commons Attribution 4.0 International. |
| **Pilot Annotation Sample** | Deterministically sampled from PURE development documents (seed 42) | 50 requirements (65 annotation rows in Rater 1; 58 in Rater 2) | Training span tagger, candidate fusion scorer, question templates | Verified human pilot annotations. |
| **Held-Out Test Pool (`data/gold/test_pool.jsonl`)** | Deterministically sampled from 6 held-out PURE documents (seed 42) | 150 requirements (0 annotations currently) | Final held-out evaluation benchmark | **Sequestered & Sealed.** Pending human double-annotation and reconciliation. |

---

### 2.2 Document-Level Partitioning & Contamination Audit

To eliminate data leakage, requirements are strictly partitioned at the **specification document level** (hash of document ID, seed 42):

- **Total Specifications Analyzed:** 26 PURE documents (610 requirements sampled).
- **Development Partition:** 20 documents (460 requirements; 76.9% effective share).
  - Documents: `0000 - cctns`, `0000 - gamma j`, `1995 - gemini`, `1998 - themas`, `1999 - dii`, `1999 - multi-mahjong`, `2001 - beyond`, `2001 - ctc network`, `2001 - esa`, `2001 - hats`, `2003 - qheadache`, `2005 - microcare`, `2005 - nenios`, `2006 - eirene sys 15`, `2007 - get real 0.2`, `2007-ertms`, `2008 - keepass`, `2008 - peering`, `2009 - peppol approved`, `2009 - video search`.
- **Held-Out Test Partition:** 6 documents (150 requirements; 23.1% effective share).
  - Documents: `1999 - tcs`, `2001 - elsfork`, `2002 - evla back`, `2005 - phin`, `2007-eirene_fun_7-2`, `2010-blitdraft`.
- **Contamination Check:** **0 document overlap** between development pool and held-out test pool (`sample_manifest.json` verified).

---

## 3. Preprocessing, Exclusions & Filtering

Raw sentences from PURE were parsed and filtered via [`src/checksense/corpus.py`](../src/checksense/corpus.py):
1. **Sentence Segmentation:** Deterministic spaCy sentence tokenizer (`en_core_web_sm`).
2. **Duplicate Removal:** Removed 1,987 identical sentences.
3. **Heading / Fragment Removal:** Removed 393 section titles, table fragments, and non-prose items.
4. **Modal Verb Requirement Filter:** Retained only sentences containing normative/modal auxiliaries (`shall`, `must`, `should`, `will`). Removed 6,790 non-functional/descriptive sentences.
5. **Length Constraints:** Kept sentences with token length between 5 and 60 tokens (removed 201 sentences with $>60$ tokens; 0 sentences with $<5$ tokens).
6. **Retained Corpus:** Exactly 4,023 functional requirements extracted across 26 documents. Zero documents silently dropped.

---

## 4. Label Taxonomy & Pilot Annotation Audit

### 4.1 Gap Taxonomy Contract

CheckSense defines 3 gap classes and 9 subtypes (`docs/annotation_guidelines.md`):

| Class | Subtype | Scope |
|---|---|---|
| **Ambiguity** | `vague_term` | Adjectives/adverbs without quantitative criteria (e.g. "fast", "user-friendly"). |
| | `vague_quantifier` | Non-specific quantifiers (e.g. "several", "a few", "almost"). |
| | `anaphora` | Pronoun with ambiguous grammatical antecedent (e.g. "it", "they", "this"). |
| | `coordination` | Conjunction ambiguity ("and"/"or") with unclear operator precedence. |
| **Incompleteness** | `missing_actor` | Passive voice or missing subject responsible for action. |
| | `missing_condition` | Action lacks triggering condition or state prerequisite. |
| | `missing_threshold` | Performance criteria without minimum/maximum boundary. |
| | `missing_error_handling` | Failure modes without specified recovery behavior. |
| **Implicit** | `unstated_constraint` | Omitted security, authentication, deletion, or privacy constraint. |

---

### 4.2 Inter-Rater Reliability Audit (Phase 3 Pilot)

A double-annotated pilot of 50 requirements was executed by two independent raters using [`app/annotate.py`](../app/annotate.py):
- **Evaluated Pilot Sample:** 50 requirements from PURE development documents (`data/gold/pilot_sample.csv`).
- **Rater 1 Annotations:** [`data/gold/annotations/rater_1.csv`](../data/gold/annotations/rater_1.csv) (65 rows; 18 clean requirements, 47 defect gaps).
- **Rater 2 Annotations:** [`data/gold/annotations/rater_2.csv`](../data/gold/annotations/rater_2.csv) (58 rows; 6 clean requirements, 44 defect gaps).
- **Inter-Rater Agreement Metrics:**
  - Binary `has_gap` Cohen's $\kappa$: **$-0.1179$** (Poor, $< 0.00$)
  - Gap Type (3-Class + Clean) $\kappa$: **$0.0068$** (Slight)
  - Subtype $\kappa$: **$0.0834$** (Slight)
  - Severity Quadratic Weighted $\kappa$: **$0.1012$** (Slight)
  - Disagreement Rate: **40 out of 50 requirements** exhibited disagreements on gap boundaries or presence.

### 4.3 Provisional Reference Rationale & Limitations
- Schedule constraints in Phase 3 prevented an interactive reconciliation meeting.
- Per stakeholder directive, **Rater 1's verified annotations (`rater_1.csv`) were adopted as a provisional development reference**.
- **Crucial Limitation:** Model performance on the 50 pilot items measures agreement with Rater 1's individual interpretations rather than objective, consensus ground truth.
- Both original annotation files (`rater_1.csv` and `rater_2.csv`) are strictly preserved unchanged. No artificial majority voting or synthetic harmonization was performed.

---

## 5. Held-Out Test Set Governance Status

> [!IMPORTANT]
> **Sequestered Status:**  
> The 150 requirements in `data/gold/test_pool.jsonl` remain **strictly sealed, unannotated, and un-evaluated**.
>
> In accordance with `docs/MASTER_SPEC.md` Section 0.4 and Section 4:
> - Agents are strictly forbidden from labeling data or synthesizing ground-truth annotations.
> - Evaluation code strictly refuses to run on any row where `label_status != 'verified'`.
> - Final held-out benchmarking can only be conducted after verified human double-annotation and reconciliation are completed by human experts.

---

## 6. Permitted Uses & Ethical Considerations

- **Permitted Uses:** Academic research, requirements engineering benchmarking, educational demonstration, and NLP tool development.
- **Inappropriate Uses:** Fully automated requirement signing or safety certification without human review; deploying classifiers to production systems without domain-specific re-annotation.
- **Attribution & Citation:**
  - Ferrari et al., *PURE: A Dataset of Public Requirements Documents*, RE 2017.
  - Femmer et al., *Rapid Quality Defect Detection in Requirements*, Zenodo record 4266727.
  - RE Open Data Community, *QuRE Industrial Quality Dataset*, Zenodo record 15656471.

