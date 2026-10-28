# CheckSense: Human To-Do & Blocked Items Log

Per **AGENTS.md** and **MASTER_SPEC.md** Rule 5:
> If a dataset cannot be downloaded, a column is ambiguous, a licence is unclear, or an annotation decision is needed, record it in `docs/HUMAN_TODO.md` and stop that branch. Do not substitute fake data.

---

## Active Blockers & Required Human Decisions

### 1. Inter-Rater Agreement & Re-Annotation Status (Phase 3 Audit Finding)
- **Status:** Cohen's $\kappa = -0.1179$ (binary `has_gap`), $\kappa = 0.0834$ (subtype).
- **Provisional Resolution (2026-10-28):** Per stakeholder directive, re-annotation and reconciliation meetings were skipped to avoid schedule delay.
- **Protocol Enforced:**
  1. `data/gold/annotations/rater_1.csv` is designated as the **provisional reference** for Phase 4 classifier development.
  2. Both `rater_1.csv` and `rater_2.csv` are strictly preserved unchanged.
  3. No artificial majority voting or synthetic harmonization is applied.
  4. Limitations are transparently documented: evaluated metrics measure agreement with Rater 1's labeling conventions on 50 pilot items, not objective defect detection.
- **Future Action Required:** Before camera-ready paper submission or final Phase 8 benchmarking on held-out test documents, conduct a reconciliation meeting to calibrate annotation guidelines.

### 2. PURE Rights & Web-Gathering Notice
- **Dataset:** PURE (Zenodo concept `10.5281/zenodo.1414116`, record `7118517`, CC-BY-4.0)
- **Curator Rights Notice:** Ferrari et al. gathered the original specifications from public web sources without formal licenses and maintain a takedown procedure.
- **Action Required from Human Reviewer:** Acknowledge this rights statement for research benchmarking purposes.

### 3. PROMISE_exp (Expanded PROMISE NFR) Skipped
- **Status:** Unverified open source host.
- **Resolution:** Skipped learned NFR filter in accordance with `MASTER_SPEC.md` Section 3; deterministic modal-verb rule retained.

---

## Resolved & Authorized Items

### 1. ARTA Dataset License & Reuse Authorization
- **Status:** Authorized for academic evaluation and classifier training per stakeholder directive (2026-10-28).
- **Resolution:** Model training proceeded under academic research fair use on Zenodo deposit record `4266727`.

### 2. ARTA Label Mapping Approval
- **Status:** Approved and provisionally adopted in [docs/label_mapping.md](label_mapping.md).
- **Resolution:** All 9 ARTA smell types mapped to CheckSense classes/subtypes. Implemented in `src/checksense/smell.py`.

### 3. PURE XML Specification Count Discrepancy (18 vs. 19)
- **Resolution:** All 18 authentic specification documents were parsed into `data/interim/pure_requirements.jsonl` (2,928 candidate requirements; 0 dropped). Verified.

### 4. Zenodo Unverified Archives (Records 7118517 and 7897601)
- **7118517:** Confirmed as official PURE v2.0 release (CC-BY-4.0).
- **7897601:** Confirmed as David Šenkýř & Petr Kroha (2023) composite dataset (`P01`–`P18` PURE, `C01`–`C07` coursework, `H01`–`H04` healthcare, `g02`–`g28` Dalpiaz). Documented as auxiliary benchmark.
