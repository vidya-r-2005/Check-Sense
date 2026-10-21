# CheckSense: Human To-Do & Blocked Items Log

Per **AGENTS.md** and **MASTER_SPEC.md** Rule 5:
> If a dataset cannot be downloaded, a column is ambiguous, a licence is unclear, or an annotation decision is needed, record it in `docs/HUMAN_TODO.md` and stop that branch. Do not substitute fake data.

---

## Open Items

### 1. ARTA Dataset License Confirmation & Label Mapping Approval
- **Dataset:** ARTA (Zenodo record 4266727, v1.0.0, Zakeri-Nasrabadi 2020)
- **Status:** Downloaded and checksum verified (`92a09adc5e4b9cd96370e7f09fe466d2`). However, the Zenodo metadata API returns `"license": null`.
- **Reference Paper:** Zakeri-Nasrabadi et al., *"Requirement testability measurement based on requirement smells"*, Neural Computing and Applications (2024).
- **Required Action:**
  1. Confirm academic fair use / license acceptance for research benchmarking.
  2. Review and approve the proposed label mapping in [docs/label_mapping.md](label_mapping.md) before training the smell classifier in Phase 4.

### 2. PROMISE_exp (Expanded PROMISE NFR) Availability
- **Dataset:** PROMISE_exp
- **Investigation:** Searched the Zenodo RE Open Data community (`re-data`) and public repositories. PROMISE_exp exists in several third-party GitHub forks (e.g., `se-requirements-classification`) and derivative papers without a canonical, standalone, license-verified Zenodo or institutional host.
- **Spec Instruction (MASTER_SPEC.md Section 3):**
  > If it cannot be located, skip the learned filter and keep the modal-verb rule; log it in HUMAN_TODO.
- **Action Taken:** The learned NFR filter branch is skipped. CheckSense uses the deterministic modal-verb rule (`shall`, `must`, `should`, `will`) for functional requirement filtering. No fake data was substituted.

---

## Resolved / Investigated Items

### 1. Zenodo Unverified Archives (Records 7118517 and 7897601)
- **Zenodo Record 7118517 (`requirements.zip`):**
  - **Investigation:** Querying Zenodo REST API revealed this is the **official PURE v2.0 release** by Ferrari, Spagnolo, and Gnesi (concept DOI: `10.5281/zenodo.1414116`, DOI: `10.5281/zenodo.7118517`). Checksums for `requirements-xml.zip` and `requirements.zip` match PURE v1.0 exactly. License: CC-BY-4.0.
  - **Resolution:** Confirmed as authentic PURE v2.0.
- **Zenodo Record 7897601 (`Dataset.zip`):**
  - **Investigation:** Querying Zenodo REST API and examining the 203 extracted folders confirmed this is the **Software Requirements Data Set** by David Šenkýř and Petr Kroha (May 2023, DOI: `10.5281/zenodo.7897601`). It is an aggregated benchmark combining 18 PURE documents (`P01`–`P18`), 7 coursework SRS (`C01`–`C07`), 4 healthcare specs (`H01`–`H04`), and 22 Dalpiaz user story sets (`g02`–`g28`). License: CC-BY-4.0.
  - **Resolution:** Documented and verified as an auxiliary benchmark. Not used as the primary base PURE corpus to avoid conflating original PURE with other domains.
