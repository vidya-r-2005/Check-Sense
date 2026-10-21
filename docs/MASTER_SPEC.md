# CheckSense: Master Build Specification

## 0. Rules of engagement (binding)

1. **Real data only.** Training data, gold labels and reported results must come from real datasets or real human annotation. It is forbidden to generate synthetic requirements, synthetic labels or made-up metrics and present them as real. Synthetic gap injection is allowed *only* for optional pre-training, must be tagged `source=silver`, and must never appear in validation or test data.
2. **Verify every download.** Read the dataset's metadata first, compare the checksum, count files, and write an entry in `data/MANIFEST.md` (source URL, DOI/record id, version, license text, download date, file sizes, checksum, intended role).
3. **No fabricated numbers.** Every number in a report or README must come from a logged run in `results/` (config, seed, git commit, date stored beside it). Reports are generated from `results/*.csv` by code, never typed by hand.
4. **Human labels gate evaluation.** Gold rows carry `label_status` in {`draft`, `verified`}. Evaluation code must refuse to run on any row that is not `verified`. LLM-drafted labels are `draft` until a human accepts or edits them. Test-set reference questions are written by humans only.
5. **Stop and ask.** If a dataset cannot be downloaded, a column is ambiguous, a licence is unclear, or an annotation decision is needed, record it in `docs/HUMAN_TODO.md` and stop that branch.
6. **Honest status.** Every module is marked in `README.md` as `working`, `untested on real data` or `todo`. Never claim a model was trained or evaluated unless a log proves it.
7. **Reproducible.** Fixed seeds, pinned dependencies, config files, deterministic data splits (hash of document id).
8. **Small and safe.** Do not commit raw datasets, model weights, `.env` or API keys. Respect licences; cite every dataset.

## 1. Goal and scope

- **Input:** a software requirements specification (SRS) or a single functional requirement in English.
- **Output per requirement:** a ranked list of gaps. Each gap has type, subtype, exact span, severity (1–3), probability, a one-sentence explanation, and one clarification question. After a stakeholder answers, a refined requirement.
- **In scope:** functional requirements, sentences of 5–60 tokens containing shall/must/should/will, English.
- **Out of scope:** non-functional-requirement classification as a goal (only used as a filter), cross-requirement consistency checking, multilingual text, user stories.
- **Novel contributions to demonstrate:** (1) a candidate-level fusion and severity scorer over three gap heads; (2) gap-conditioned explanation and question generation.

## 2. Gap taxonomy and severity (the labelling contract)

| Class | Subtypes |
|---|---|
| ambiguity | vague_term, vague_quantifier, anaphora, coordination |
| incompleteness | missing_actor, missing_condition, missing_threshold, missing_error_handling |
| implicit | unstated_constraint |

Rule 0: do not flag information that is defined elsewhere in the same SRS.
Severity: 3 = developer likely builds wrong behaviour or there is a security/safety/legal impact; 2 = likely rework; 1 = minor.
Write the full guideline with 2–3 examples per subtype in `docs/annotation_guidelines.md`.

## 3. Datasets (all real; verify before use)

| Dataset | Where | Role | Notes |
|---|---|---|---|
| **PURE** (79 public requirements documents, ~34k sentences) | Zenodo records 1414116 and 1414117 (v2.0). All documents are PDF, 19 also as XML. Project page: nlreqdataset.isti.cnr.it | Base corpus | Start with the 19 XML documents; add PDFs for more domains. Cite Ferrari et al., RE 2017. No known licence restrictions: copy the licence text into MANIFEST. |
| **ARTA smell dataset** | Zenodo record 4266727 (v1.0.0) | Train/validate the sentence-level smell classifier and the rule baseline lexicon | Four spreadsheets with nine smell types. Inspect the real columns, then propose a label mapping in `docs/label_mapping.md` for human approval. |
| **QuRE** (industrial requirements quality dataset) | DOI 10.5281/zenodo.15656471 (RE Open Data community: zenodo.org/communities/re-data) | External test set for the smell/ambiguity head | Inspect columns and licence first. |
| **PROMISE_exp** (expanded PROMISE NFR) | Locate through the RE Open Data community or the authors' repository; verify host and licence | Train the functional-requirement filter | If it cannot be located, skip the learned filter and keep the modal-verb rule; log it in HUMAN_TODO. |
| **Dalpiaz user-story sets** (optional) | Mendeley Data, DOI 10.17632/7zbk8zsd8y | Optional out-of-domain robustness check only | Skip if time is short. |
| **Unverified archives** | Zenodo records 7118517 (`requirements.zip`) and 7897601 (`Dataset.zip`) were used in an earlier draft | Unknown | Query each record's metadata and document what it is before using it. Do not assume either is PURE. |
| **ConceptNet** (optional) | Official ConceptNet download | Candidate concepts for the implicit head | Optional; the hand-built checklist ontology must work without it. |

**Acquisition protocol (for each dataset):** (1) call the Zenodo REST API (`https://zenodo.org/api/records/<id>`) or the host's metadata page and log title, version, licence and file list; (2) download to `data/raw/<name>/`; (3) verify the checksum given by the host; (4) extract; (5) write the exploratory notebook `notebooks/01_<name>_eda.ipynb` with counts, length distribution, modal-verb share and 20 random samples; (6) update `data/MANIFEST.md`. If the network or a login blocks any step, write precise manual instructions in `docs/HUMAN_TODO.md`.

**Corpus build:** parse PURE into `data/interim/pure_requirements.jsonl` with fields `req_id, doc_id, text, source_file, sent_idx`. Split sentences, keep candidate requirements (modal verb, 5–60 tokens, not a heading), deduplicate, and report how many sentences each filter removed. Never silently drop documents.

## 4. Gold annotation (humans do the labelling; you build the tooling)

- **Sampling:** at least 600 requirements from at least 20 PURE documents (about 30 per document), seed 42. Hold out about 25% of the **documents** as the final test set (about 150 requirements), never touched during development.
- **Record schema (one row per gap; clean requirements have one row with `has_gap=0`):** `req_id, doc_id, text, has_gap, gap_type, subtype, span_text, severity, explanation, question, stakeholder_answer, refined_text, annotator, label_status, notes`.
- **Tooling to build:** a Streamlit annotation app (`app/annotate.py`) that shows a requirement, optional LLM-drafted suggestions (labelled draft), and lets an annotator accept, edit, reject or add gaps, set severity, and write the question, answer and refined text. It writes CSV, records the annotator id, and sets `label_status=verified` only on human confirmation.
- **Process:** a double-annotated pilot of 50–60 requirements; compute Cohen's kappa on `has_gap` and `gap_type` (script provided); revise the guidelines until kappa is about 0.6 or higher; then annotate the rest. The test set is double-annotated and disagreements are resolved by discussion. Reference questions for the test set are human-written.
- **You must not** label data yourself and mark it verified.

## 5. Architecture (stages 1 to 9)

1. **Acquisition** of PURE requirements (section 3).
2. **Preprocessing:** sentence split, tokenisation, POS and dependency parse with spaCy (`en_core_web_sm`), deterministic and versioned.
3. **Requirement frame:** actor, modal, action, object, condition, quantity, exception. Rule-based over the dependency parse; handle passives and leading conditional clauses. A missing slot becomes a candidate gap and a fusion feature.
4. **Heads** (each emits candidate gaps with a score):
   - **4a Ambiguity:** lexicon span detector (vague terms, quantifiers, pronouns, open lists), a sentence-level smell classifier (TF-IDF + logistic regression and a SpanBERT-embedding + logistic regression variant), and a SpanBERT token tagger trained on human span labels.
   - **4b Completeness:** frame-slot rules plus a masked-LM slot predictor (internal: predicted terms found elsewhere in the same SRS; external: general knowledge).
   - **4c Implicit:** hand-built slot-checklist ontology (authentication, payment, deletion, upload, notification, input, search, report, and more) plus optional ConceptNet neighbours; an LLM verification step rescales confidence. A concept already covered anywhere in the same SRS is not flagged.
5. **Fusion and severity scorer (novelty):** the unit is a **candidate gap**, not a requirement. Features: type, head score, smell probability, number of candidates, frame-missing count, length, severity keywords, optional span embedding. Model: MLP with a 128-unit hidden layer producing gap probability and severity 1–3. Provide a heuristic fallback until trained.
6. **Explanation and question generation (novelty):** local LLM through an `LLMClient` interface (Ollama default, `qwen2.5:7b`; provider adapters configurable by environment variable). JSON output with `explanation` and `question`. Validation: exactly one question mark, at most 30 words, parseable JSON; otherwise fall back to a deterministic per-subtype template. Never invent facts or propose answers.
7. **Stakeholder answer:** human-in-the-loop in the Streamlit app.
8. **Refinement:** rewrite the requirement using only information from the requirement and the answer; reject outputs that drop or add numbers; fall back to a rule-based edit.
9. **Evaluation and output:** metrics, report, refined SRS export.

## 6. Training specification

- **Encoders:** `SpanBERT/spanbert-base-cased` with the `bert-base-cased` tokenizer (also try `roberta-base`); max length 128.
- **Smell classifier:** train on ARTA after the approved label mapping; evaluate with grouped cross-validation; test on QuRE.
- **Span tagger:** BIO tags over words, trained on **human gold spans**; optional warm start on lexicon-labelled `silver` data, then fine-tune on gold; select by entity-level F1 on gold dev data only.
- **Optional:** continued masked-LM pretraining of BERT on PURE sentences (unlabelled) to adapt the completeness head.
- **Fusion:** candidate-level labels derived from gold (candidate matches a gold gap by type and span overlap); grouped 5-fold cross-validation by document.
- **Hardware:** assume CPU only by default (`--device auto`); use CUDA and mixed precision when present; provide `notebooks/colab_train.ipynb` that mirrors the training CLI for people without a GPU. Log wall time per run.
- **Seeds and configs:** every run saves `config.json`, seed, library versions and git commit next to its outputs.

## 7. Evaluation protocol

- **Matching:** ambiguity and incompleteness gaps match when the type is equal and spans overlap (token Jaccard at least 0.5 or containment); implicit gaps match at requirement level. Provide a lenient `--req-level` mode.
- **Primary:** gap-level macro-F1 over the three classes. Also report per-class P/R/F1, micro F1 and F2, requirement-level has-gap PR-AUC, false-alarm rate on clean requirements.
- **Severity and ranking:** Spearman rho and nDCG@3 against annotator severity.
- **Reliability:** ECE and Brier score of the gap probability.
- **Question quality (human):** blinded rating sheet with the human reference mixed in; clarity, relevance and informativeness on a 1–5 scale, plus answerable and hallucinated (0/1); at least two raters; weighted kappa for agreement; paired bootstrap and a non-inferiority check against the human reference (margin 0.5).
- **Refinement:** gap-closure rate, ISO/IEC/IEEE 29148 characteristic ratings before and after, rate of newly introduced gaps (re-run the detector plus human check).
- **Efficiency:** seconds per requirement and LLM calls per requirement versus B4.
- **Baselines:** B1 rules only; B2 span tagger alone; B3 single zero-shot LLM; B4 multi-LLM majority vote with local models (`qwen2.5:7b`, `llama3.1:8b`, `mistral:7b`). LLM gaps whose span is not in the requirement are discarded.
- **Ablations:** remove each head; plain union of heads instead of the fusion scorer; template-only versus LLM questions; generic versus gap-conditioned prompts.
- **Statistics:** grouped cross-validation on development documents plus the fixed held-out test documents; 1,000-sample bootstrap CIs resampling requirements; paired bootstrap for system comparisons; three seeds for trained models.
- **Error analysis:** confusion by gap type, slices by length and domain, and a catalogue of failure cases saved in `reports/error_analysis.md`.

## 8. Software requirements

- Python 3.11 or newer, `src/checksense` package layout, type hints, `ruff`, `pytest`, pinned `requirements.txt` (or `pyproject.toml` with a lock file).
- One Windows-friendly CLI: `python -m checksense.cli <command>` with subcommands `download`, `build-corpus`, `sample`, `annotate-stats`, `train-smell`, `train-span`, `train-fusion`, `eval`, `rate-make`, `rate-score`, `report`, `serve`.
- A `.vscode/` folder with settings, launch configurations, tasks and recommended extensions; everything must be runnable from VS Code on Windows.
- Streamlit apps: `app/streamlit_app.py` (analysis, answer, refinement, download) and `app/annotate.py` (annotation).
- Tests for: sentence filter, frame extraction, each head, fusion featurisation, generation validation, refinement validation, metrics, matching, split determinism, and a test that evaluation refuses non-verified labels. Tests may use tiny hand-written fixtures; fixtures must be clearly named `fixtures/` and never used to report results.
- Continuous integration (GitHub Actions) running `ruff` and `pytest` is optional.

## 9. Documentation deliverables

`README.md` (status table, quick start, workflow), `docs/annotation_guidelines.md`, `docs/DATASHEET.md` (dataset documentation), `docs/MODEL_CARD.md`, `docs/label_mapping.md`, `docs/HUMAN_TODO.md`, `data/MANIFEST.md`, a generated results report in `reports/`, and a paper-style report skeleton (abstract, introduction, related work, method, experiments, results, discussion, limitations, ethics, conclusion) whose tables are filled by code from `results/`.

## 10. Ethics and risks to document

Hallucinated questions (mitigated by validation, grounding and human review), bias across domains and writing styles, licences and attribution for datasets, privacy if proprietary SRS documents are ever used, over-reliance on automation, and the limitation that the gold set is small and from public documents.

## 11. Phases, acceptance criteria and checkpoints

Stop after each phase, write `docs/CHECKPOINT_<n>.md`, and wait for approval.

| Phase | Work | Acceptance criteria |
|---|---|---|
| 0 | Repo, environment, CLI skeleton, `.vscode/`, README, AGENTS.md, test harness | `pytest` passes; environment check script runs on Windows |
| 1 | Real dataset acquisition, verification, MANIFEST, EDA notebooks, PURE corpus build | Every dataset in section 3 either downloaded and verified or listed in HUMAN_TODO with exact manual steps; corpus stats printed; no fabricated data |
| 2 | Preprocessing, frame extraction, B1 rule baseline, metrics module, eval runner that enforces `label_status` | Unit tests pass; the eval runner refuses unverified labels |
| 3 | Annotation tooling, sampling, guidelines, kappa script, pilot sheet. **Then stop for human annotation.** | Pilot sheet generated from real PURE sentences; annotation app works |
| 4 | Heads 4a, 4b, 4c; smell classifier on ARTA; span tagger on human gold spans | Grouped-CV results saved with configs; QuRE external result saved |
| 5 | Fusion and severity scorer on candidate-level labels | CV results, calibration plot data and ECE saved |
| 6 | Generation, validation, refinement, local LLM client | Validation tests pass; works with templates when no LLM is installed |
| 7 | Baselines B2 to B4 and all ablations | One command reproduces `results/summary.csv` |
| 8 | Full evaluation on the held-out test documents, human rating tools, report generation | Report generated from `results/` only; limitations section written |
| 9 | App polish, documentation, datasheet, model card, final clean install test | Fresh clone plus documented steps reproduces results |

## 12. Forbidden shortcuts

Generating example "requirements" to fill a dataset; inventing labels, metrics or screenshots; marking LLM drafts as verified; evaluating on training documents; tuning on the held-out test documents; silently skipping a failing dataset step; hard-coding results into reports; committing raw data or secrets; claiming a model was trained without a log.
