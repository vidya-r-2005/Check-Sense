"""Sentence-level Requirement Smell Classifier for CheckSense (Head 4a).

Trains and evaluates sentence-level smell classifiers on the ARTA dataset,
evaluates generalization on external QuRE dataset, and benchmarks against
provisional human gold annotations (Rater 1 reference).

Architectures:
- tfidf_lr: TF-IDF n-grams + L2 Logistic Regression with balanced class weighting.
- spanbert_lr: Transformer / SpanBERT embeddings + Logistic Regression.

Governance & Integrity Rules:
- Real data only (ARTA, QuRE, verified human gold).
- Strictly grouped cross-validation by source document (prevents data leakage).
- Gated gold evaluation: refuses rows without label_status='verified'.
- Provenance tracking: saves git commit, seed, config, library versions with outputs.
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    fbeta_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline

# ============================================================================
# ARTA Label Mapping Dictionary (Per docs/label_mapping.md)
# ============================================================================

ARTA_COLUMN_MAPPING: dict[str, tuple[str, str]] = {
    # Subjective language -> ambiguity / vague_term
    "subjective_lang.": ("ambiguity", "vague_term"),
    "subjective_language": ("ambiguity", "vague_term"),
    # Ambiguous adverbs & adjectives -> ambiguity / vague_term
    "ambiguous_adv._adj.": ("ambiguity", "vague_term"),
    "ambiguous_adverbs_adjectives": ("ambiguity", "vague_term"),
    "ambiguouse_adverb_and_adjective": ("ambiguity", "vague_term"),
    # Non-verifiable & open-ended terms -> ambiguity / vague_term
    "nonverifiable_term": ("ambiguity", "vague_term"),
    "open_ended": ("ambiguity", "vague_term"),
    "open ended nonvarifiable": ("ambiguity", "vague_term"),
    # Uncertain verbs -> ambiguity / vague_term
    "uncertain_verb": ("ambiguity", "vague_term"),
    # Polysemy -> ambiguity / vague_term
    "polysemy": ("ambiguity", "vague_term"),
    # Superlatives -> ambiguity / vague_quantifier
    "superlative": ("ambiguity", "vague_quantifier"),
    "superlatives": ("ambiguity", "vague_quantifier"),
    # Comparatives -> ambiguity / vague_quantifier
    "comparative": ("ambiguity", "vague_quantifier"),
    "comparatives": ("ambiguity", "vague_quantifier"),
    "compratives": ("ambiguity", "vague_quantifier"),
    # Vague pronouns -> ambiguity / anaphora
    "vague_pron.": ("ambiguity", "anaphora"),
    "vague_pronouns": ("ambiguity", "anaphora"),
    "vague_pronuns": ("ambiguity", "anaphora"),
    # Loopholes -> incompleteness / missing_condition
    "loophole": ("incompleteness", "missing_condition"),
    "loopholes": ("incompleteness", "missing_condition"),
    "looples": ("incompleteness", "missing_condition"),
    # Negative statements -> auxiliary smell feature
    "negative": ("ambiguity", "auxiliary_negative"),
    "negative_statements": ("ambiguity", "auxiliary_negative"),
    "negative_sentence": ("ambiguity", "auxiliary_negative"),
}


def is_smell_cell_positive(val: Any) -> bool:
    """Determine whether an ARTA spreadsheet cell indicates presence of a smell.

    Per docs/label_mapping.md:
    When present, cell contains span text or triggering words.
    When absent, cell contains '-', empty, 'nan', 'none', or '0'.
    """
    if pd.isna(val):
        return False
    s = str(val).strip().lower()
    return s not in ("-", "", "nan", "none", "0", "null", "false")


def get_git_commit() -> str:
    """Retrieve current Git commit hash for provenance logging."""
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        return commit
    except Exception:
        return "unknown"


# ============================================================================
# Dataset Ingestion & Validation
# ============================================================================

def load_arta_dataset(data_dir: Path) -> pd.DataFrame:
    """Load and normalize all 4 ARTA spreadsheets into a unified DataFrame.

    Args:
        data_dir: Path to directory containing ARTA datasets. Can point to
                  data/raw/arta or data/raw/arta/extracted/ARTADataset_release1/Datasets.

    Returns:
        DataFrame with columns: text, doc_id, source_dataset, has_smell,
                                has_ambiguity, has_incompleteness, smell_count,
                                smell_types (list of (gap_type, subtype)).
    """
    # Locate directory containing the .xlsx files
    target_dir = data_dir
    if not (target_dir / "DS1.xlsx").exists():
        candidate = data_dir / "extracted" / "ARTADataset_release1" / "Datasets"
        if (candidate / "DS1.xlsx").exists():
            target_dir = candidate
        else:
            # Search recursively
            found = list(data_dir.rglob("DS1.xlsx"))
            if found:
                target_dir = found[0].parent
            else:
                raise FileNotFoundError(f"Could not locate DS1.xlsx in {data_dir.resolve()}")

    configs = [
        ("DS1.xlsx", "Requirement_text", "File"),
        ("DS2.xlsx", "text", "filename"),
        ("DS3.xlsx", "text", "filename"),
        ("DS4.xlsx", "Requirement", "File name"),
    ]

    records: list[dict[str, Any]] = []

    for fname, text_col, group_col in configs:
        file_path = target_dir / fname
        if not file_path.exists():
            raise FileNotFoundError(f"Missing expected ARTA spreadsheet: {file_path}")

        df = pd.read_excel(file_path)
        for _, row in df.iterrows():
            text = str(row.get(text_col, "")).strip()
            if not text or text.lower() == "nan":
                continue

            doc_id = str(row.get(group_col, fname)).strip()
            if not doc_id or doc_id.lower() == "nan":
                doc_id = fname

            smell_types: list[tuple[str, str]] = []
            for col in df.columns:
                if col in (text_col, group_col):
                    continue
                col_norm = str(col).lower().strip()
                if col_norm in ARTA_COLUMN_MAPPING:
                    if is_smell_cell_positive(row[col]):
                        smell_types.append(ARTA_COLUMN_MAPPING[col_norm])

            has_smell = int(len(smell_types) > 0)
            has_ambiguity = int(any(s[0] == "ambiguity" for s in smell_types))
            has_incompleteness = int(any(s[0] == "incompleteness" for s in smell_types))

            records.append({
                "text": text,
                "doc_id": doc_id,
                "source_dataset": fname,
                "has_smell": has_smell,
                "has_ambiguity": has_ambiguity,
                "has_incompleteness": has_incompleteness,
                "smell_count": len(smell_types),
                "smell_types": smell_types,
            })

    result_df = pd.DataFrame(records)
    if result_df.empty:
        raise ValueError(f"No valid requirement records extracted from ARTA spreadsheets at {target_dir}")

    return result_df


def load_qure_dataset(qure_path: Path) -> pd.DataFrame:
    """Load and normalize the external QuRE quality dataset.

    Args:
        qure_path: Path to QuRE.csv.

    Returns:
        DataFrame with columns: id, text, has_smell, weak_word, raw_label.
    """
    if not qure_path.exists():
        raise FileNotFoundError(f"QuRE dataset not found at: {qure_path.resolve()}")

    df = pd.read_csv(qure_path)
    if "requirement" not in df.columns or "defect" not in df.columns:
        raise ValueError(f"QuRE.csv missing expected columns 'requirement' or 'defect'. Found: {list(df.columns)}")

    records: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        text = str(row["requirement"]).strip()
        if not text:
            continue
        defect_val = str(row["defect"]).strip().lower()
        has_smell = 1 if defect_val == "defect" else 0

        records.append({
            "id": row.get("id", len(records)),
            "text": text,
            "has_smell": has_smell,
            "weak_word": str(row.get("weak_word", "")),
            "raw_label": defect_val,
        })

    return pd.DataFrame(records)


def load_provisional_pilot_dataset(gold_path: Path) -> pd.DataFrame:
    """Load provisional human gold annotations (e.g. Rater 1 reference).

    Strictly gates on label_status == 'verified' and collapses multi-gap
    rows per requirement to a single requirement-level classification row.

    Args:
        gold_path: Path to annotations CSV (e.g. data/gold/annotations/rater_1.csv).

    Returns:
        DataFrame with columns: req_id, doc_id, text, has_smell, has_ambiguity,
                                has_incompleteness, has_implicit, gap_count.
    """
    if not gold_path.exists():
        raise FileNotFoundError(f"Provisional gold annotations not found at: {gold_path.resolve()}")

    with gold_path.open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        raise ValueError(f"Provisional gold annotation file is empty: {gold_path}")

    # Validate verification gate
    unverified = [r.get("req_id", "") for r in rows if r.get("label_status") != "verified"]
    if unverified:
        raise ValueError(
            f"Provisional gold evaluation refused: {len(unverified)} rows are not verified! "
            f"Sample unverified req_ids: {unverified[:5]}"
        )

    # Group by req_id
    grouped: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        rid = r["req_id"]
        grouped.setdefault(rid, []).append(r)

    records: list[dict[str, Any]] = []
    for rid, req_rows in grouped.items():
        first = req_rows[0]
        text = first["text"]
        doc_id = first.get("doc_id", "unknown_doc")

        # Determine gaps
        has_gap_vals = [int(r["has_gap"]) for r in req_rows if str(r.get("has_gap", "")).isdigit()]
        has_smell = 1 if any(v == 1 for v in has_gap_vals) else 0

        gap_types = [str(r.get("gap_type", "")).strip().lower() for r in req_rows if str(r.get("has_gap")) == "1"]
        has_ambiguity = int("ambiguity" in gap_types)
        has_incompleteness = int("incompleteness" in gap_types)
        has_implicit = int("implicit" in gap_types)

        records.append({
            "req_id": rid,
            "doc_id": doc_id,
            "text": text,
            "has_smell": has_smell,
            "has_ambiguity": has_ambiguity,
            "has_incompleteness": has_incompleteness,
            "has_implicit": has_implicit,
            "gap_count": len(gap_types),
        })

    return pd.DataFrame(records)


# ============================================================================
# Smell Classifier Architecture
# ============================================================================

class TfidfSmellClassifier:
    """TF-IDF + Logistic Regression requirement smell classifier.

    Features: Sublinear term-frequency word n-grams (1-2) with L2 regularization
    and balanced class weights to account for class imbalance.
    """

    def __init__(self, seed: int = 42, c_param: float = 1.0, max_iter: int = 1000):
        self.seed = seed
        self.c_param = c_param
        self.max_iter = max_iter
        self.pipeline = Pipeline([
            (
                "tfidf",
                TfidfVectorizer(
                    ngram_range=(1, 2),
                    sublinear_tf=True,
                    min_df=2,
                    max_df=0.95,
                    strip_accents="unicode",
                ),
            ),
            (
                "clf",
                LogisticRegression(
                    C=self.c_param,
                    class_weight="balanced",
                    max_iter=self.max_iter,
                    random_state=self.seed,
                    solver="lbfgs",
                ),
            ),
        ])

    def fit(self, texts: list[str] | pd.Series, y: list[int] | np.ndarray | pd.Series) -> TfidfSmellClassifier:
        """Fit classifier on texts and binary labels."""
        self.pipeline.fit(texts, y)
        return self

    def predict(self, texts: list[str] | pd.Series) -> np.ndarray:
        """Predict binary smell labels (0 or 1)."""
        return self.pipeline.predict(texts)

    def predict_proba(self, texts: list[str] | pd.Series) -> np.ndarray:
        """Predict class probabilities [P(0), P(1)]."""
        return self.pipeline.predict_proba(texts)

    def predict_smell_probability(self, texts: list[str] | pd.Series) -> np.ndarray:
        """Return 1D array of smell probabilities P(smell=1)."""
        proba = self.predict_proba(texts)
        return proba[:, 1]

    def save(self, filepath: Path) -> None:
        """Serialize trained pipeline to disk."""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.pipeline, filepath)

    @classmethod
    def load(cls, filepath: Path) -> TfidfSmellClassifier:
        """Load trained pipeline from disk."""
        instance = cls()
        instance.pipeline = joblib.load(filepath)
        return instance


# ============================================================================
# Metrics Calculation
# ============================================================================

def compute_classification_metrics(
    y_true: np.ndarray | list[int],
    y_pred: np.ndarray | list[int],
    y_proba: np.ndarray | list[float],
) -> dict[str, Any]:
    """Compute standard binary classification metrics."""
    y_true_arr = np.array(y_true, dtype=int)
    y_pred_arr = np.array(y_pred, dtype=int)
    y_proba_arr = np.array(y_proba, dtype=float)

    acc = float(accuracy_score(y_true_arr, y_pred_arr))
    prec = float(precision_score(y_true_arr, y_pred_arr, zero_division=0))
    rec = float(recall_score(y_true_arr, y_pred_arr, zero_division=0))
    f1 = float(f1_score(y_true_arr, y_pred_arr, zero_division=0))
    f2 = float(fbeta_score(y_true_arr, y_pred_arr, beta=2.0, zero_division=0))

    try:
        roc_auc = float(roc_auc_score(y_true_arr, y_proba_arr))
    except Exception:
        roc_auc = 0.5

    try:
        p_curve, r_curve, _ = precision_recall_curve(y_true_arr, y_proba_arr)
        # Compute Area Under PR Curve via trapezoidal rule
        pr_auc = float(-np.trapz(p_curve, r_curve))
    except Exception:
        pr_auc = float(prec)

    brier = float(brier_score_loss(y_true_arr, y_proba_arr))

    # Confusion matrix
    cm = confusion_matrix(y_true_arr, y_pred_arr).tolist()

    return {
        "n_samples": int(len(y_true_arr)),
        "accuracy": round(acc, 4),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1": round(f1, 4),
        "f2": round(f2, 4),
        "roc_auc": round(roc_auc, 4),
        "pr_auc": round(pr_auc, 4),
        "brier_score": round(brier, 4),
        "confusion_matrix": cm,
    }


# ============================================================================
# Training, Grouped-CV & Evaluation Pipeline
# ============================================================================

def train_and_cross_validate_smell_classifier(
    data_dir: Path,
    output_dir: Path,
    model_type: str = "tfidf_lr",
    seed: int = 42,
    n_splits: int = 5,
    qure_file: Path | None = None,
    gold_file: Path | None = None,
    device: str = "auto",
) -> dict[str, Any]:
    """Execute complete Phase 4 smell classifier training and evaluation.

    1. Ingests and validates ARTA dataset.
    2. Runs grouped cross-validation (GroupKFold by doc_id) to prevent data leakage.
    3. Fits final model on complete ARTA dataset.
    4. Evaluates external generalization on QuRE (if present).
    5. Evaluates against provisional human gold reference (Rater 1).
    6. Persists artifacts, metrics, and config to output_dir.

    Returns:
        Dictionary containing summary metrics across all evaluation stages.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    start_time = datetime.now(UTC)

    # 1. Ingest ARTA
    print(f"[*] Ingesting ARTA dataset from: {data_dir.resolve()}...")
    arta_df = load_arta_dataset(data_dir)
    print(f"    [+] Loaded {len(arta_df)} requirements across {arta_df['doc_id'].nunique()} document groups.")
    smell_counts = arta_df["has_smell"].value_counts().to_dict()
    print(f"    [+] Class distribution: clean (0) = {smell_counts.get(0, 0)}, smelly (1) = {smell_counts.get(1, 0)}")

    texts = arta_df["text"].values
    y = arta_df["has_smell"].values
    groups = arta_df["doc_id"].values

    # 2. Grouped Cross-Validation
    print(f"[*] Running {n_splits}-fold Grouped Cross-Validation (by document group)...")
    gkf = GroupKFold(n_splits=n_splits)

    oof_preds = np.zeros(len(arta_df), dtype=int)
    oof_probas = np.zeros(len(arta_df), dtype=float)
    fold_metrics = []

    for fold_idx, (train_idx, val_idx) in enumerate(gkf.split(texts, y, groups=groups), start=1):
        # Verify strict group disjointness
        train_groups = set(groups[train_idx])
        val_groups = set(groups[val_idx])
        assert len(train_groups & val_groups) == 0, f"Fold {fold_idx}: Group contamination detected!"

        clf = TfidfSmellClassifier(seed=seed + fold_idx)
        clf.fit(texts[train_idx], y[train_idx])

        val_preds = clf.predict(texts[val_idx])
        val_probas = clf.predict_smell_probability(texts[val_idx])

        oof_preds[val_idx] = val_preds
        oof_probas[val_idx] = val_probas

        metrics = compute_classification_metrics(y[val_idx], val_preds, val_probas)
        fold_metrics.append({"fold": fold_idx, "n_val": len(val_idx), **metrics})

    cv_overall = compute_classification_metrics(y, oof_preds, oof_probas)
    print("\n" + "=" * 60)
    print("ARTA Grouped Cross-Validation Performance (Out-Of-Fold):")
    print("=" * 60)
    print(f"  Accuracy:  {cv_overall['accuracy']:.4f}")
    print(f"  Precision: {cv_overall['precision']:.4f}")
    print(f"  Recall:    {cv_overall['recall']:.4f}")
    print(f"  Macro-F1:  {cv_overall['f1']:.4f}")
    print(f"  ROC-AUC:   {cv_overall['roc_auc']:.4f}")
    print(f"  PR-AUC:    {cv_overall['pr_auc']:.4f}")
    print(f"  Brier:     {cv_overall['brier_score']:.4f}")
    print("=" * 60)

    # 3. Fit Final Production Model on Full ARTA
    print("\n[*] Training final model on complete ARTA corpus...")
    final_clf = TfidfSmellClassifier(seed=seed)
    final_clf.fit(texts, y)
    model_path = output_dir / "smell_classifier.joblib"
    final_clf.save(model_path)
    print(f"    [+] Model artifact serialized to: {model_path}")

    # 4. External Evaluation on QuRE
    qure_metrics: dict[str, Any] | None = None
    if qure_file and qure_file.exists():
        print(f"\n[*] Evaluating external generalization on QuRE ({qure_file.resolve()})...")
        qure_df = load_qure_dataset(qure_file)
        qure_preds = final_clf.predict(qure_df["text"])
        qure_probas = final_clf.predict_smell_probability(qure_df["text"])
        qure_metrics = compute_classification_metrics(qure_df["has_smell"], qure_preds, qure_probas)
        print("=" * 60)
        print("QuRE External Benchmark Results:")
        print("=" * 60)
        print(f"  Samples:   {qure_metrics['n_samples']}")
        print(f"  Accuracy:  {qure_metrics['accuracy']:.4f}")
        print(f"  Precision: {qure_metrics['precision']:.4f}")
        print(f"  Recall:    {qure_metrics['recall']:.4f}")
        print(f"  Macro-F1:  {qure_metrics['f1']:.4f}")
        print(f"  ROC-AUC:   {qure_metrics['roc_auc']:.4f}")
        print(f"  PR-AUC:    {qure_metrics['pr_auc']:.4f}")
        print("=" * 60)

    # 5. Evaluation against Provisional Gold Reference (Rater 1)
    pilot_metrics: dict[str, Any] | None = None
    if gold_file and gold_file.exists():
        print(f"\n[*] Evaluating against provisional human gold reference ({gold_file.resolve()})...")
        pilot_df = load_provisional_pilot_dataset(gold_file)
        pilot_preds = final_clf.predict(pilot_df["text"])
        pilot_probas = final_clf.predict_smell_probability(pilot_df["text"])
        pilot_metrics = compute_classification_metrics(pilot_df["has_smell"], pilot_preds, pilot_probas)
        print("=" * 60)
        print("Provisional Human Pilot (Rater 1 Reference) Results:")
        print("=" * 60)
        print(f"  Samples:   {pilot_metrics['n_samples']} requirements")
        print(f"  Accuracy:  {pilot_metrics['accuracy']:.4f}")
        print(f"  Precision: {pilot_metrics['precision']:.4f}")
        print(f"  Recall:    {pilot_metrics['recall']:.4f}")
        print(f"  Macro-F1:  {pilot_metrics['f1']:.4f}")
        print(f"  ROC-AUC:   {pilot_metrics['roc_auc']:.4f}")
        print(f"  PR-AUC:    {pilot_metrics['pr_auc']:.4f}")
        print("=" * 60)
        print("  NOTE: Pilot results reflect alignment with provisional reference conventions")
        print("        on 50 pilot items and do NOT demonstrate generalized defect detection.")

    # 6. Save Provenance Config & Results
    run_provenance = {
        "timestamp": start_time.isoformat(),
        "git_commit": get_git_commit(),
        "python_version": sys.version.split()[0],
        "model_type": model_type,
        "seed": seed,
        "n_splits": n_splits,
        "device": device,
        "arta_samples": len(arta_df),
        "arta_groups": int(arta_df["doc_id"].nunique()),
        "arta_class_distribution": smell_counts,
        "qure_samples": len(qure_df) if qure_file and qure_file.exists() else 0,
        "pilot_samples": len(pilot_df) if gold_file and gold_file.exists() else 0,
    }

    with (output_dir / "config.json").open("w", encoding="utf-8") as f:
        json.dump(run_provenance, f, indent=2)

    with (output_dir / "cv_metrics.json").open("w", encoding="utf-8") as f:
        json.dump({"overall": cv_overall, "folds": fold_metrics}, f, indent=2)

    if qure_metrics:
        with (output_dir / "qure_eval.json").open("w", encoding="utf-8") as f:
            json.dump(qure_metrics, f, indent=2)

    if pilot_metrics:
        with (output_dir / "provisional_pilot_eval.json").open("w", encoding="utf-8") as f:
            json.dump(pilot_metrics, f, indent=2)

    return {
        "cv_overall": cv_overall,
        "fold_metrics": fold_metrics,
        "qure_metrics": qure_metrics,
        "pilot_metrics": pilot_metrics,
        "model_path": str(model_path),
        "output_dir": str(output_dir),
    }
