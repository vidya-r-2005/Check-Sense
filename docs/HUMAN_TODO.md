# CheckSense: Human To-Do & Blocked Items Log

Per **AGENTS.md** and **MASTER_SPEC.md** Rule 5:
> If a dataset cannot be downloaded, a column is ambiguous, a licence is unclear, or an annotation decision is needed, record it in `docs/HUMAN_TODO.md` and stop that branch. Do not substitute fake data.

---

## Active Blockers & Required Human Decisions

### 1. ARTA Dataset License & Reuse Authorization (BLOCKING Phase 4 Training)
- **Dataset:** ARTA (Automatic Requirements Testability Analysis Dataset, Zenodo record `4266727`, v1.0.0, Zakeri-Nasrabadi 2020)
- **Verified Facts:**
  - Official Zenodo REST API returns `"license": null` and `"access_right": "open"`.
  - Inspection of `ARTADataset_release1.zip` confirms there is **no** `LICENSE`, `README`, or terms-of-use document in the archive.
  - Paper: *Requirement testability measurement based on requirement smells*, Neural Computing and Applications (2024).
- **Rule Enforcement:** Academic fair use cannot be assumed without explicit terms. **Model training on ARTA in Phase 4 is BLOCKED** until the user/stakeholder explicitly establishes or confirms the reuse terms.
- **Action Required from Human Reviewer:**
  1. Determine if institutional/academic evaluation is authorized under the author's open deposit or obtain written clarification from the author (Morteza Zakeri-Nasrabadi).
  2. Confirm whether CheckSense may train classifiers on ARTA.

### 2. ARTA Proposed Label Mapping Approval (BLOCKING Phase 4 Training)
- **Status:** PROPOSED in [docs/label_mapping.md](label_mapping.md).
- **Rule Enforcement:** The mapping cannot be treated as approved or used in any code until explicitly confirmed by the human reviewer.
- **Action Required from Human Reviewer:**
  Review the proposed mapping from ARTA smell columns (`Subjective_lang.`, `Ambiguous_adv._adj.`, `Loophole`, `Superlative`, `Comparative`, `Negative`, `Vague_pron.`, `Uncertain_verb`, `Polysemy`) to CheckSense gap taxonomy (`ambiguity/vague_term`, `ambiguity/vague_quantifier`, `ambiguity/anaphora`, `incompleteness/missing_condition`).

### 3. PURE Rights & Web-Gathering Notice
- **Dataset:** PURE (Zenodo concept `10.5281/zenodo.1414116`, record `7118517`, CC-BY-4.0)
- **Curator Rights Notice:** Ferrari et al. gathered the original specifications from public web sources without formal licenses and maintain a takedown procedure.
- **Action Required from Human Reviewer:** Acknowledge this rights statement for research benchmarking purposes.

### 4. PROMISE_exp (Expanded PROMISE NFR) Skipped
- **Status:** Unverified open source host.
- **Resolution:** Skipped learned NFR filter in accordance with `MASTER_SPEC.md` Section 3; deterministic modal-verb rule retained.

---

## Resolved & Investigated Items

### 1. PURE XML Specification Count Discrepancy (18 vs. 19)
- **Investigation:** `requirements-xml.zip` from Ferrari et al. (Zenodo 7118517 / 1414117) contains exactly 18 XML files inside `XMLZIPFile/`. The description notes "a subset of 19 documents in XML format", which reflects the 19 entries including the parent directory (or the 19 entries in `__MACOSX/XMLZIPFile`).
- **Resolution:** All 18 authentic specification documents were parsed into `data/interim/pure_requirements.jsonl` (2,928 candidate requirements; 0 dropped). Verified.

### 2. Zenodo Unverified Archives (Records 7118517 and 7897601)
- **7118517:** Confirmed as official PURE v2.0 release (CC-BY-4.0).
- **7897601:** Confirmed as David Šenkýř & Petr Kroha (2023) composite dataset (`P01`–`P18` PURE, `C01`–`C07` coursework, `H01`–`H04` healthcare, `g02`–`g28` Dalpiaz). Documented as auxiliary benchmark.
