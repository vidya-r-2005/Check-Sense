# CheckSense Execution Plan: Phase 0 & Phase 1

This plan defines the step-by-step implementation for **Phase 0** and **Phase 1** strictly in accordance with [AGENTS.md](../AGENTS.md) and [docs/MASTER_SPEC.md](MASTER_SPEC.md).

---

## Strict Rules & Principles
1. **Real Data Only:** Absolutely zero synthetic requirements, synthetic labels, or made-up metrics.
2. **Every Download Verified:** Metadata fetched first, checksum verified, file counts verified, logged in `data/MANIFEST.md`.
3. **If Blocked, Document in `docs/HUMAN_TODO.md`:** Stop that branch, do not substitute fake data.
4. **Honest Status:** Modules marked as `working`, `untested on real data`, or `todo`.
5. **Phase-by-Phase Gates:** Stop at the end of each phase, generate `docs/CHECKPOINT_<n>.md`, and await user approval before proceeding.

---

## Phase 0: Repository, Environment, CLI Skeleton, and Test Harness

### Objectives & Deliverables
- **Git Repository & Ignore Rules:** Initialize git repository, configure `.gitignore` ensuring raw data (`data/raw/`), large weights (`models/`), caches, and secrets (`.env`) are never committed.
- **Python Environment (3.11+ / 3.12):**
  - Create Python 3.12 virtual environment `.venv`.
  - Provide `pyproject.toml` and `requirements.txt` with pinned dependencies (spaCy, transformers, torch, scikit-learn, streamlit, requests, pytest, ruff, rich, typer/argparse, etc.).
- **Windows-Friendly CLI Skeleton (`src/checksense/cli.py`):**
  - Package structure: `src/checksense/` (`__init__.py`, `cli.py`, `version.py`).
  - Implement all 12 specified subcommands with CLI entry points, descriptive help messages, and argument parsers:
    1. `download`
    2. `build-corpus`
    3. `sample`
    4. `annotate-stats`
    5. `train-smell`
    6. `train-span`
    7. `train-fusion`
    8. `eval`
    9. `rate-make`
    10. `rate-score`
    11. `report`
    12. `serve`
- **VS Code Configuration (`.vscode/`):**
  - `settings.json`: Windows paths, python interpreter pointing to `.venv`, ruff as default formatter/linter, pytest enabled.
  - `launch.json`: Configurations for running CLI commands and Streamlit apps under debugging.
  - `tasks.json`: Quick tasks for running tests, environment checks, and linting.
  - `extensions.json`: Recommended VS Code extensions.
- **Environment Verification Script (`scripts/check_env.py`):**
  - Validates Python version (>=3.11), required directories, platform compatibility, installed core tools, and Git status.
- **Documentation (`README.md` & `docs/HUMAN_TODO.md`):**
  - `README.md` with honest module status table (`working`, `untested on real data`, `todo`), quick start commands, and architecture workflow.
  - `docs/HUMAN_TODO.md` initialized.
- **Test Harness (`tests/`):**
  - `tests/test_cli.py`: Verifies all subcommands respond correctly to `--help` and CLI entry point functions.
  - `tests/test_env.py`: Verifies environment constants, paths, and package metadata.
  - Verify that `pytest` passes with 100% green tests.
- **Phase 0 Acceptance Gate:**
  - `pytest` passes cleanly.
  - `python scripts/check_env.py` exits 0 on Windows.
  - Produce `docs/CHECKPOINT_0.md` and pause for user approval.

---

## Phase 1 Preview: Real Dataset Acquisition, Verification, & Corpus Build (to be started only after Phase 0 approval)

### Objectives & Deliverables
1. **Zenodo Metadata Query & Real Acquisition:**
   - Call Zenodo REST APIs (`https://zenodo.org/api/records/<id>`) for:
     - **PURE:** Zenodo records 1414116 & 1414117 (v2.0).
     - **ARTA:** Zenodo record 4266727 (v1.0.0).
     - **QuRE:** Zenodo DOI 10.5281/zenodo.15656471.
     - **PROMISE_exp:** Locate through RE Open Data community or authors' repository.
     - **Unverified archives:** Zenodo 7118517 & 7897601 (query and log metadata, document nature).
2. **Checksum Verification & Logging in `data/MANIFEST.md`:**
   - Record source URL, DOI/record ID, version, license, download timestamp, file sizes, MD5/SHA256 checksums, and intended role.
3. **Exploratory Data Analysis (EDA):**
   - Provide exploratory notebooks/scripts for downloaded datasets (`notebooks/01_pure_eda.ipynb`, `notebooks/02_arta_eda.ipynb`, etc.) detailing sentence counts, length distribution, modal verb share, and random samples.
4. **PURE Corpus Construction:**
   - Parse real PURE XML/PDF into `data/interim/pure_requirements.jsonl` with schema `req_id, doc_id, text, source_file, sent_idx`.
   - Apply filters (modal verb, 5–60 tokens, non-heading), deduplicate, log exact removal stats per filter without dropping documents silently.
5. **Phase 1 Acceptance Gate:**
   - Every dataset verified or logged in `docs/HUMAN_TODO.md` with precise manual instructions.
   - PURE corpus stats generated and verified from real data.
   - Produce `docs/CHECKPOINT_1.md` and pause for user approval.
