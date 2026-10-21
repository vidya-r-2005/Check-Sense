# CheckSense Checkpoint 0: Repository, Environment, CLI Skeleton, and Test Harness

**Date:** 2026-10-21  
**Phase:** Phase 0  
**Status:** COMPLETED & VERIFIED (Pending User Approval to Begin Phase 1)

---

## 1. What Was Done

1. **Repository Setup & Git Ignore Rules:**
   - Initialized Git repository.
   - Configured `.gitignore` enforcing non-negotiable rules from `MASTER_SPEC.md`: raw datasets (`data/raw/*`), model weights (`models/*`), secret tokens (`.env`), virtual environments (`.venv/`), and caches are strictly excluded.
   - Structured standard directories:
     - `src/checksense/` (package code)
     - `docs/` (binding specifications, guidelines, plans, and checkpoints)
     - `data/` (`raw/`, `interim/`, `processed/`, `gold/`)
     - `notebooks/` (exploratory data analysis notebooks)
     - `reports/` (paper-style generated reports)
     - `results/` (experimental logs, configs, metric CSVs)
     - `scripts/` (utility and validation scripts)
     - `tests/` and `tests/fixtures/` (unit tests and test fixtures)
     - `app/` (Streamlit apps for annotation and interactive analysis)
     - `.vscode/` (editor settings, launch configurations, tasks, and extensions)
     - `models/` (model weights directory)

2. **Binding Contract & Documentation Deliverables:**
   - Saved [AGENTS.md](../AGENTS.md) to workspace root.
   - Saved [docs/MASTER_SPEC.md](MASTER_SPEC.md) with full 12-section project specification.
   - Created [README.md](../README.md) with honest module status table (`working`, `untested on real data`, `todo`), quick start commands, and architecture workflow.
   - Initialized [data/MANIFEST.md](../data/MANIFEST.md) for checksums and dataset metadata.
   - Initialized [docs/HUMAN_TODO.md](HUMAN_TODO.md) for blocking items.
   - Outlined detailed execution plan in [docs/PLAN_PHASE_0_1.md](PLAN_PHASE_0_1.md).

3. **Python Environment & Packaging:**
   - Configured Python 3.12 virtual environment at `.venv/`.
   - Authored `pyproject.toml` with project metadata, build configuration, scripts entry point `checksense = "checksense.cli:main"`, and ruff/pytest configurations.
   - Authored pinned `requirements.txt` for Python 3.12 / Windows compatibility.
   - Installed `pytest`, `ruff`, and `checksense` in editable mode (`pip install -e . --no-deps`).

4. **Windows-Friendly CLI Skeleton (`src/checksense/cli.py`):**
   - Implemented top-level CLI parser and all 12 required subcommands:
     1. `download`
     2. `build-corpus`
     3. `sample`
     4. `annotate-stats`
     5. `train-smell`
     6. `train-span`
     7. `train-fusion`
     8. `eval` (with `--req-level` and strict `label_status` enforcement placeholder)
     9. `rate-make`
     10. `rate-score`
     11. `report`
     12. `serve`

5. **VS Code Workspace Integration (`.vscode/`):**
   - `.vscode/settings.json`: Configured interpreter path (`${workspaceFolder}/.venv/Scripts/python.exe`), format-on-save with ruff, pytest integration.
   - `.vscode/launch.json`: Pre-configured debug targets for CLI Help, CLI Download, Streamlit apps, and Pytest.
   - `.vscode/tasks.json`: Quick shell tasks for running check_env, pytest, and ruff linting.
   - `.vscode/extensions.json`: Recommended extensions for Python, Pylance, Ruff, and TOML.

6. **Environment Check Script (`scripts/check_env.py`):**
   - Implemented automated verification of Python version (>= 3.11), required directories, Git initialization, package importability, and dependency statuses.

7. **Test Harness (`tests/`):**
   - `tests/test_cli.py`: 16 test cases verifying CLI help, parser structure, and execution of all 12 subcommands.
   - `tests/test_env.py`: 4 test cases verifying Python runtime, directory layout, `.gitignore` rules, and binding specification presence.

---

## 2. Evidence of Completion

### A. Environment Check Script (`scripts/check_env.py`)
```text
============================================================
CheckSense Environment & Workspace Verification
============================================================
[*] Python Runtime: 3.12.4 on Windows (AMD64)
    [+] Python version check passed (>= 3.11).
[*] Checking directory structure:
    [+] src/checksense/ exists.
    [+] docs/ exists.
    [+] data/raw/ exists.
    [+] data/interim/ exists.
    [+] data/processed/ exists.
    [+] data/gold/ exists.
    [+] notebooks/ exists.
    [+] reports/ exists.
    [+] results/ exists.
    [+] scripts/ exists.
    [+] tests/ exists.
    [+] .vscode/ exists.
[*] Checking Git repository:
    [+] Git repository initialized.
    [+] .gitignore present.
[*] Checking CheckSense package import:
    [+] Successfully imported 'checksense' v0.1.0
    [+] Subparsers loaded (12 commands): download, build-corpus, sample, annotate-stats, train-smell, train-span, train-fusion, eval, rate-make, rate-score, report, serve
[*] Checking installed dependencies:
    [+] pytest (9.1.1): Testing harness
    [+] ruff (unknown): Linter and formatter
    [?] torch is not yet installed: PyTorch deep learning framework
    [?] spacy is not yet installed: spaCy NLP parser
    [?] transformers is not yet installed: Hugging Face transformers
    [?] sklearn is not yet installed: scikit-learn machine learning
    [?] pandas is not yet installed: Data manipulation
    [?] streamlit is not yet installed: Interactive web UI
============================================================
[+] Environment and repository skeleton validation PASSED!
```
*Result: Exit Code 0.*

### B. Unit Tests (`pytest tests -v`)
```text
============================= test session starts =============================
platform win32 -- Python 3.12.4, pytest-9.1.1, pluggy-1.7.0
rootdir: C:\Users\2005v\OneDrive\Desktop\CheckSense
configfile: pyproject.toml
collected 20 items

tests\test_cli.py ................                                       [ 80%]
tests\test_env.py ....                                                   [100%]

============================= 20 passed in 0.16s ==============================
```
*Result: 20 passed, 0 failed in 0.16s. Exit Code 0.*

### C. Linter & Style Check (`ruff check .`)
```text
All checks passed!
```
*Result: Exit Code 0.*

### D. CLI Command Line Output
```text
PS C:\Users\2005v\OneDrive\Desktop\CheckSense> .\.venv\Scripts\python.exe -m checksense.cli --help
usage: python -m checksense.cli [-h] [--version]
                                {download,build-corpus,sample,annotate-stats,train-smell,train-span,train-fusion,eval,rate-make,rate-score,report,serve}
                                ...

CheckSense: NLP system for detecting gaps in software requirements.

options:
  -h, --help            show this help message and exit
  --version             show program's version number and exit

subcommands:
  Valid CheckSense operations

  {download,build-corpus,sample,annotate-stats,train-smell,train-span,train-fusion,eval,rate-make,rate-score,report,serve}
    download            Download and verify real datasets from Zenodo / open repositories.
    build-corpus        Parse raw PURE requirements into data/interim/pure_requirements.jsonl.
    sample              Sample requirements for human annotation and partition held-out documents.
    annotate-stats      Compute annotation statistics, verification progress, and inter-rater agreement.
    train-smell         Train and cross-validate sentence-level smell classifier on ARTA.
    train-span          Train and fine-tune token-level SpanBERT span tagger on human gold spans.
    train-fusion        Train the candidate-level fusion and severity scorer (MLP / fallback).
    eval                Evaluate gap detection pipeline on gold test set (refuses unverified rows).
    rate-make           Generate blinded human rating sheets with reference questions mixed in.
    rate-score          Score human rating sheets with agreement (kappa) and bootstrap non-inferiority.
    report              Compile paper-ready tables and summary report strictly from results/*.csv.
    serve               Launch CheckSense Streamlit application (analysis app or annotation app).
```
*Result: Exit Code 0.*

---

## 3. What Must Be Done Next (Phase 1)

Upon user approval of Checkpoint 0, Phase 1 will execute:
1. **Zenodo REST API Queries:**
   - Query metadata for PURE (Zenodo 1414116 & 1414117, v2.0).
   - Query metadata for ARTA smell dataset (Zenodo 4266727, v1.0.0).
   - Query metadata for QuRE industrial requirements quality dataset (DOI 10.5281/zenodo.15656471).
   - Query metadata for unverified archives (Zenodo 7118517 & 7897601) to identify their contents without assumptions.
   - Locate PROMISE_exp via RE Open Data community.
2. **Download & Checksum Verification:**
   - Download raw archives into `data/raw/<dataset>/`.
   - Calculate and verify MD5/SHA256 checksums against the host's published values.
   - Record all metadata, file sizes, licenses, and checksums in `data/MANIFEST.md`.
   - If any download or network access is blocked, record the exact manual steps in `docs/HUMAN_TODO.md` and halt that branch.
3. **Exploratory Data Analysis (EDA):**
   - Create and run EDA notebooks (`notebooks/01_pure_eda.ipynb`, `notebooks/02_arta_eda.ipynb`, etc.) detailing sentence counts, token length distributions, modal verb proportions, and 20 sample rows.
4. **PURE Corpus Construction:**
   - Parse real PURE XML/PDF documents into `data/interim/pure_requirements.jsonl` with schema `req_id, doc_id, text, source_file, sent_idx`.
   - Apply candidate requirement filters (modal verb, 5–60 tokens, non-heading), deduplicate, and report removal stats per filter.
5. **Phase 1 Checkpoint & Gate:**
   - Write `docs/CHECKPOINT_1.md` with evidence and await user approval before proceeding to Phase 2.
