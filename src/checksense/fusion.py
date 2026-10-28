"""Phase 5 Candidate-Level Fusion and Severity Scorer for CheckSense.

Implements the novel candidate-level fusion scorer specified in MASTER_SPEC.md
Section 5.5, 6, and 11.

Key Architecture:
- Unit of scoring is a CANDIDATE GAP, not a requirement.
- Features: gap type (one-hot), subtype (one-hot), head score, sentence smell probability,
  number of candidates, frame missing slots count, passive voice flag, text length,
  span length, and domain severity keywords.
- Model: MLP with a 128-unit hidden layer producing calibrated gap probability
  and severity (1-3), with a deterministic heuristic fallback.
- Conflict & Deduplication Engine: merges overlapping spans, resolves conflicting
  gap types by fusion score, and applies deterministic output ranking.
- Strictly grouped cross-validation by source document (prevents data leakage).
"""

from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from scipy.stats import spearmanr
from sklearn.metrics import (
    accuracy_score,
    brier_score_loss,
    f1_score,
    mean_absolute_error,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GroupKFold
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler

from .annotation import ALL_SUBTYPES
from .baseline import CandidateGap
from .frame import RequirementFrame, extract_requirement_frame
from .heads import Phase4Pipeline
from .span_tagger import token_jaccard

# High-severity domain keywords indicating potential safety, security, or legal hazards
SEVERITY_KEYWORDS = {
    "security",
    "safety",
    "loss",
    "crash",
    "fatal",
    "delete",
    "erase",
    "wipe",
    "critical",
    "kill",
    "hazard",
    "unauthorized",
    "fail",
    "failure",
    "damage",
    "corrupt",
    "corruption",
    "tamper",
    "leak",
    "breach",
    "malfunction",
    "emergency",
    "catastrophic",
    "terminate",
    "abort",
}

GAP_CLASSES = ["ambiguity", "incompleteness", "implicit"]
SUBTYPE_LIST = sorted(ALL_SUBTYPES)


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
# Feature Extraction
# ============================================================================

def extract_candidate_features(
    candidate: CandidateGap,
    req_text: str,
    frame: RequirementFrame | None = None,
    smell_prob: float = 0.5,
    n_candidates: int = 1,
) -> dict[str, float]:
    """Extract candidate-level feature vector.

    Args:
        candidate: CandidateGap to featurize.
        req_text: Requirement text string.
        frame: Optional pre-computed RequirementFrame.
        smell_prob: Sentence-level smell probability from Head 4a.
        n_candidates: Total number of candidate gaps emitted for this requirement.

    Returns:
        Dictionary of feature name -> float value.
    """
    if frame is None:
        frame = extract_requirement_frame(req_text)

    features: dict[str, float] = {}

    # 1. One-hot gap class (3 classes)
    for cname in GAP_CLASSES:
        features[f"type_{cname}"] = 1.0 if candidate.gap_type.lower() == cname else 0.0

    # 2. One-hot subtype (9 subtypes)
    for stype in SUBTYPE_LIST:
        features[f"subtype_{stype}"] = 1.0 if candidate.subtype.lower() == stype else 0.0

    # 3. Head score and sentence smell score
    features["head_score"] = float(candidate.probability)
    features["smell_probability"] = float(smell_prob)

    # 4. Global requirement context features
    features["n_candidates"] = float(n_candidates)
    features["missing_slots_count"] = float(len(frame.missing_slots))
    features["is_passive"] = 1.0 if frame.is_passive else 0.0
    features["req_char_length"] = float(len(req_text))
    features["req_token_count"] = float(len(req_text.split()))

    # 5. Span length features
    span_str = candidate.span_text or ""
    features["span_char_length"] = float(len(span_str))
    features["span_token_count"] = float(len(span_str.split()))

    # 6. Severity keyword indicators
    text_words = set(re.findall(r"\b\w+\b", req_text.lower()))
    span_words = set(re.findall(r"\b\w+\b", span_str.lower()))

    n_text_keywords = len(text_words & SEVERITY_KEYWORDS)
    n_span_keywords = len(span_words & SEVERITY_KEYWORDS)

    features["text_severity_keywords"] = float(n_text_keywords)
    features["span_severity_keywords"] = float(n_span_keywords)
    features["has_critical_keyword"] = 1.0 if (n_text_keywords > 0 or n_span_keywords > 0) else 0.0

    return features


def feature_dict_to_vector(features: dict[str, float], feature_names: list[str]) -> np.ndarray:
    """Convert feature dictionary to a deterministic numpy vector."""
    return np.array([features.get(k, 0.0) for k in feature_names], dtype=float)


# ============================================================================
# Candidate Matching to Gold Labels
# ============================================================================

def match_candidate_to_gold_gaps(
    candidate: CandidateGap,
    gold_rows: list[dict[str, Any]],
) -> tuple[int, int]:
    """Determine whether candidate gap matches verified gold gaps.

    Per MASTER_SPEC.md Section 7:
    - Ambiguity and Incompleteness match when gap_type is equal AND spans overlap
      (token Jaccard >= 0.5 or containment).
    - Implicit gaps match at requirement level.

    Returns:
        (is_gap_label, gold_severity):
        - is_gap_label: 1 if candidate is a true positive, 0 if false positive.
        - gold_severity: annotator severity in {1, 2, 3} if matched, else 1.
    """
    for g in gold_rows:
        if str(g.get("has_gap", "0")) != "1":
            continue

        gold_type = str(g.get("gap_type", "")).strip().lower()
        if candidate.gap_type.lower() != gold_type:
            continue

        gold_span = str(g.get("span_text", "")).strip()
        gold_sev = int(g.get("severity", 1)) if str(g.get("severity", "")).isdigit() else 1

        if gold_type == "implicit":
            # Implicit gaps match at requirement level
            return 1, gold_sev

        # Ambiguity and incompleteness require span overlap (Jaccard >= 0.5 or containment)
        jacc = token_jaccard(candidate.span_text, gold_span)
        if jacc >= 0.5 or candidate.span_text.lower() in gold_span.lower() or gold_span.lower() in candidate.span_text.lower():
            return 1, gold_sev

    return 0, 1


# ============================================================================
# Calibration Math & Metrics
# ============================================================================

def compute_expected_calibration_error(
    y_true: np.ndarray,
    y_proba: np.ndarray,
    n_bins: int = 10,
) -> tuple[float, list[dict[str, Any]]]:
    """Compute Expected Calibration Error (ECE) and bin calibration data.

    Returns:
        (ece_score, calibration_bins):
        - ece_score: Float in [0.0, 1.0].
        - calibration_bins: List of dicts with bin boundaries, mean confidence, and empirical accuracy.
    """
    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    bins_data: list[dict[str, Any]] = []

    for i in range(n_bins):
        bin_lower = bin_edges[i]
        bin_upper = bin_edges[i + 1]

        if i == n_bins - 1:
            in_bin = (y_proba >= bin_lower) & (y_proba <= bin_upper)
        else:
            in_bin = (y_proba >= bin_lower) & (y_proba < bin_upper)

        n_in_bin = int(np.sum(in_bin))
        if n_in_bin > 0:
            bin_acc = float(np.mean(y_true[in_bin]))
            bin_conf = float(np.mean(y_proba[in_bin]))
            ece += (n_in_bin / len(y_true)) * abs(bin_acc - bin_conf)
        else:
            bin_acc = 0.0
            bin_conf = float((bin_lower + bin_upper) / 2.0)

        bins_data.append({
            "bin_index": i,
            "bin_lower": round(float(bin_lower), 2),
            "bin_upper": round(float(bin_upper), 2),
            "count": n_in_bin,
            "mean_confidence": round(bin_conf, 4),
            "empirical_accuracy": round(bin_acc, 4),
        })

    return round(float(ece), 4), bins_data


# ============================================================================
# Candidate Fusion Scorer Models
# ============================================================================

class HeuristicFusionScorer:
    """Deterministic heuristic fallback fusion scorer.

    Used when models are uncalibrated or for tiny datasets. Combines head scores,
    sentence smell probability, and domain keyword rules.
    """

    def score_candidate(self, candidate: CandidateGap, features: dict[str, float]) -> tuple[float, int]:
        """Compute calibrated probability and severity 1-3.

        Returns:
            (probability, severity)
        """
        head_score = features.get("head_score", 0.5)
        smell_prob = features.get("smell_probability", 0.5)
        has_critical = features.get("has_critical_keyword", 0.0)

        # Base calibrated probability: convex combination of head score and smell probability
        prob = 0.55 * head_score + 0.35 * smell_prob + 0.10 * has_critical
        prob = min(max(prob, 0.05), 0.98)

        # Calibrate severity:
        # 3: Critical domain action, security keyword, or explicit severity 3 flag
        # 2: Default defect severity
        # 1: Minor stylistic ambiguity
        if has_critical > 0 or candidate.gap_type == "implicit":
            severity = 3
        elif candidate.subtype in ("vague_quantifier", "anaphora") and features.get("span_char_length", 0) <= 3:
            severity = 1
        else:
            severity = max(1, min(3, candidate.severity))

        return round(float(prob), 4), int(severity)


class MLPFusionScorer:
    """MLP Candidate-Level Fusion and Severity Scorer per Section 5.5.

    Architecture:
    - Standardized feature scaler.
    - Probability Scorer: 128-unit MLPClassifier producing P(candidate is true gap).
    - Severity Scorer: 64-unit MLPClassifier predicting severity in {1, 2, 3}.
    - Heuristic fallback if unfitted or on inference failure.
    """

    def __init__(self, seed: int = 42):
        self.seed = seed
        self.scaler = StandardScaler()
        self.prob_mlp = MLPClassifier(
            hidden_layer_sizes=(128,),
            activation="relu",
            solver="adam",
            alpha=0.001,
            max_iter=1000,
            random_state=self.seed,
        )
        self.sev_mlp = MLPClassifier(
            hidden_layer_sizes=(64,),
            activation="relu",
            solver="adam",
            alpha=0.001,
            max_iter=1000,
            random_state=self.seed,
        )
        self.feature_names: list[str] = []
        self.is_fitted = False
        self.fallback = HeuristicFusionScorer()

    def fit(
        self,
        x: np.ndarray,
        y_gap: np.ndarray,
        y_sev: np.ndarray,
        feature_names: list[str],
    ) -> MLPFusionScorer:
        """Fit probability and severity MLPs on candidate feature matrix."""
        self.feature_names = list(feature_names)
        x_scaled = self.scaler.fit_transform(x)

        # Fit probability scorer (binary: 0 or 1)
        self.prob_mlp.fit(x_scaled, y_gap)

        # Fit severity scorer on positive candidates only
        pos_mask = (y_gap == 1)
        if np.sum(pos_mask) >= 5 and len(np.unique(y_sev[pos_mask])) > 1:
            self.sev_mlp.fit(x_scaled[pos_mask], y_sev[pos_mask])
        else:
            # Fit on full data if positive slice is too sparse
            self.sev_mlp.fit(x_scaled, y_sev)

        self.is_fitted = True
        return self

    def score_candidate(self, candidate: CandidateGap, features: dict[str, float]) -> tuple[float, int]:
        """Score candidate using fitted MLP or heuristic fallback."""
        if not self.is_fitted:
            return self.fallback.score_candidate(candidate, features)

        try:
            vec = feature_dict_to_vector(features, self.feature_names).reshape(1, -1)
            vec_scaled = self.scaler.transform(vec)

            # Probability: P(gap = 1)
            if hasattr(self.prob_mlp, "predict_proba"):
                probas = self.prob_mlp.predict_proba(vec_scaled)[0]
                classes = list(self.prob_mlp.classes_)
                prob = float(probas[classes.index(1)]) if 1 in classes else float(probas[0])
            else:
                prob = float(self.prob_mlp.predict(vec_scaled)[0])

            # Severity: 1, 2, or 3
            pred_sev = int(self.sev_mlp.predict(vec_scaled)[0])
            pred_sev = max(1, min(3, pred_sev))

            return round(prob, 4), pred_sev
        except Exception:
            return self.fallback.score_candidate(candidate, features)

    def save(self, filepath: Path) -> None:
        """Serialize model to disk."""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({
            "scaler": self.scaler,
            "prob_mlp": self.prob_mlp,
            "sev_mlp": self.sev_mlp,
            "feature_names": self.feature_names,
            "is_fitted": self.is_fitted,
            "seed": self.seed,
        }, filepath)

    @classmethod
    def load(cls, filepath: Path) -> MLPFusionScorer:
        """Load serialized model from disk."""
        data = joblib.load(filepath)
        instance = cls(seed=data.get("seed", 42))
        instance.scaler = data["scaler"]
        instance.prob_mlp = data["prob_mlp"]
        instance.sev_mlp = data["sev_mlp"]
        instance.feature_names = data["feature_names"]
        instance.is_fitted = data["is_fitted"]
        return instance


# ============================================================================
# Deduplication, Conflict Resolution & Deterministic Ranking
# ============================================================================

def deduplicate_and_rank_candidates(
    candidates: list[CandidateGap],
    scorer: MLPFusionScorer | HeuristicFusionScorer,
    req_text: str,
    frame: RequirementFrame | None = None,
    smell_prob: float = 0.5,
    confidence_threshold: float = 0.30,
) -> list[CandidateGap]:
    """Fuse scores, resolve duplicates/conflicts, and deterministically rank candidate gaps.

    Rules applied:
    1. Confidence filtering: Discard candidates below confidence_threshold.
    2. Overlap deduplication: If two candidates cover overlapping spans (Jaccard >= 0.7
       or one containment), resolve conflict:
       - If same gap_type: retain the candidate with highest fusion probability.
       - If different gap_type: retain the candidate with highest fusion probability,
         favoring higher severity if scores are within 0.05.
    3. Deterministic output ranking: Sort by severity descending, probability descending,
       with stable tie-breaker (start_char, end_char, subtype).

    Returns:
        Deduplicated, calibrated, and ranked list of CandidateGap objects.
    """
    if not candidates:
        return []

    if frame is None:
        frame = extract_requirement_frame(req_text)

    n_cands = len(candidates)
    scored_candidates: list[tuple[CandidateGap, float, int]] = []

    # 1. Score each candidate
    for cand in candidates:
        feats = extract_candidate_features(
            candidate=cand,
            req_text=req_text,
            frame=frame,
            smell_prob=smell_prob,
            n_candidates=n_cands,
        )
        prob, sev = scorer.score_candidate(cand, feats)

        # Create updated candidate copy with calibrated scores
        calibrated_cand = CandidateGap(
            gap_type=cand.gap_type,
            subtype=cand.subtype,
            span_text=cand.span_text,
            start_char=cand.start_char,
            end_char=cand.end_char,
            severity=sev,
            probability=prob,
            explanation=cand.explanation,
            question=cand.question,
        )

        if prob >= confidence_threshold:
            scored_candidates.append((calibrated_cand, prob, sev))

    if not scored_candidates:
        return []

    # 2. Conflict resolution and duplicate elimination
    # Sort initially by probability descending
    scored_candidates.sort(key=lambda item: (item[2], item[1]), reverse=True)
    retained: list[CandidateGap] = []

    for cand, _prob, _sev in scored_candidates:
        # Check against already retained candidates for span conflict
        conflict = False
        for r_cand in retained:
            if cand.gap_type == "implicit" and r_cand.gap_type == "implicit":
                # Only keep one implicit gap per requirement
                conflict = True
                break

            if cand.span_text and r_cand.span_text:
                jacc = token_jaccard(cand.span_text, r_cand.span_text)
                overlap = (
                    jacc >= 0.70
                    or cand.span_text.lower() in r_cand.span_text.lower()
                    or r_cand.span_text.lower() in cand.span_text.lower()
                )
                if overlap:
                    conflict = True
                    break

        if not conflict:
            retained.append(cand)

    # 3. Deterministic Final Ranking
    # Primary: Severity descending (3, 2, 1)
    # Secondary: Probability descending (1.0 to 0.0)
    # Stable Tie-Breaker: start_char ascending, subtype alphabetically
    retained.sort(
        key=lambda c: (
            -c.severity,
            -c.probability,
            c.start_char if c.start_char is not None else 0,
            c.subtype,
        )
    )

    return retained


# ============================================================================
# Phase 5 Training & Grouped-CV Execution
# ============================================================================

def build_candidate_dataset_from_gold(
    gold_path: Path,
    pipeline: Phase4Pipeline,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, list[str]]:
    """Generate candidate pool from Phase 4 heads and match against verified gold.

    Returns:
        (X, y_gap, y_sev, doc_groups, feature_names)
    """
    if not gold_path.exists():
        raise FileNotFoundError(f"Gold annotations not found: {gold_path.resolve()}")

    with gold_path.open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Verification gate
    unverified = [r.get("req_id", "") for r in rows if r.get("label_status") != "verified"]
    if unverified:
        raise ValueError(f"Fusion training refused: {len(unverified)} rows are not verified.")

    grouped_gold: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        grouped_gold.setdefault(r["req_id"], []).append(r)

    candidate_records: list[dict[str, Any]] = []

    for req_id, req_rows in grouped_gold.items():
        first = req_rows[0]
        text = str(first.get("text", "")).strip()
        doc_id = str(first.get("doc_id", "unknown_doc"))

        if not text:
            continue

        frame = extract_requirement_frame(text)

        # Get smell probability from pipeline
        smell_prob = 0.5
        if pipeline.smell_model:
            try:
                smell_prob = float(pipeline.smell_model.predict_smell_probability([text])[0])
            except Exception:
                smell_prob = 0.5

        # Detect candidate gaps using Phase 4 multi-head engine
        candidates = pipeline.detect_all_gaps(text, frame=frame)
        n_cands = len(candidates)

        for cand in candidates:
            feats = extract_candidate_features(
                candidate=cand,
                req_text=text,
                frame=frame,
                smell_prob=smell_prob,
                n_candidates=n_cands,
            )
            is_gap, gold_sev = match_candidate_to_gold_gaps(cand, req_rows)

            candidate_records.append({
                "req_id": req_id,
                "doc_id": doc_id,
                "features": feats,
                "is_gap": is_gap,
                "severity": gold_sev,
            })

    if not candidate_records:
        raise ValueError(f"No candidate gaps generated from gold requirements in {gold_path}")

    # Standardize feature names
    sample_feats = candidate_records[0]["features"]
    feature_names = sorted(sample_feats.keys())

    x = np.array([
        feature_dict_to_vector(r["features"], feature_names)
        for r in candidate_records
    ], dtype=float)
    y_gap = np.array([r["is_gap"] for r in candidate_records], dtype=int)
    y_sev = np.array([r["severity"] for r in candidate_records], dtype=int)
    doc_groups = np.array([r["doc_id"] for r in candidate_records], dtype=str)

    return x, y_gap, y_sev, doc_groups, feature_names


def train_and_cross_validate_fusion_scorer(
    gold_file: Path,
    output_dir: Path,
    smell_model_path: Path | None = None,
    span_model_path: Path | None = None,
    seed: int = 42,
    n_splits: int = 5,
) -> dict[str, Any]:
    """Train and evaluate candidate-level fusion scorer with grouped cross-validation.

    Performs:
    1. Candidate generation over provisional gold requirements using Phase 4 heads.
    2. Candidate-level feature extraction and gold label assignment.
    3. 5-fold Grouped Cross-Validation by document (GroupKFold).
    4. Computes Accuracy, F1, ROC-AUC, Brier score, ECE, and calibration data.
    5. Saves model artifact, config, metrics, and calibration data.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    start_time = datetime.now(UTC)

    print("[*] Initializing Phase 4 pipeline for candidate generation...")
    pipeline = Phase4Pipeline(smell_model_path=smell_model_path, span_model_path=span_model_path)

    print(f"[*] Extracting candidate pool from: {gold_file.resolve()}...")
    x, y_gap, y_sev, doc_groups, feature_names = build_candidate_dataset_from_gold(gold_file, pipeline)

    n_samples = len(x)
    n_pos = int(np.sum(y_gap == 1))
    n_neg = int(np.sum(y_gap == 0))
    unique_docs = len(set(doc_groups))

    print(f"    [+] Total Candidate Gaps: {n_samples}")
    print(f"    [+] Positive (True Gaps):  {n_pos} ({n_pos / n_samples:.1%})")
    print(f"    [+] Negative (False Gaps): {n_neg} ({n_neg / n_samples:.1%})")
    print(f"    [+] Document Groups:       {unique_docs}")
    print(f"    [+] Feature Dimensions:    {len(feature_names)}")

    # Grouped Cross-Validation
    effective_splits = min(n_splits, unique_docs)
    print(f"\n[*] Running {effective_splits}-fold Grouped Cross-Validation (by source document)...")
    gkf = GroupKFold(n_splits=effective_splits)

    oof_preds = np.zeros(n_samples, dtype=int)
    oof_probas = np.zeros(n_samples, dtype=float)
    oof_sev_preds = np.zeros(n_samples, dtype=int)
    fold_metrics = []

    for fold_idx, (train_idx, val_idx) in enumerate(gkf.split(x, y_gap, groups=doc_groups), start=1):
        # Strict document isolation check
        train_docs = set(doc_groups[train_idx])
        val_docs = set(doc_groups[val_idx])
        assert len(train_docs & val_docs) == 0, f"Fold {fold_idx}: Document contamination detected!"

        model = MLPFusionScorer(seed=seed + fold_idx)
        model.fit(x[train_idx], y_gap[train_idx], y_sev[train_idx], feature_names)

        # Predict validation candidates
        val_x = x[val_idx]
        val_scaled = model.scaler.transform(val_x)

        if hasattr(model.prob_mlp, "predict_proba"):
            p_val = model.prob_mlp.predict_proba(val_scaled)[:, 1]
        else:
            p_val = model.prob_mlp.predict(val_scaled)

        y_pred = (p_val >= 0.50).astype(int)
        sev_pred = model.sev_mlp.predict(val_scaled)

        oof_preds[val_idx] = y_pred
        oof_probas[val_idx] = p_val
        oof_sev_preds[val_idx] = sev_pred

        acc = float(accuracy_score(y_gap[val_idx], y_pred))
        f1 = float(f1_score(y_gap[val_idx], y_pred, zero_division=0))
        fold_metrics.append({
            "fold": fold_idx,
            "n_val": len(val_idx),
            "accuracy": round(acc, 4),
            "f1": round(f1, 4),
        })

    # Overall CV metrics
    cv_acc = float(accuracy_score(y_gap, oof_preds))
    cv_prec = float(precision_score(y_gap, oof_preds, zero_division=0))
    cv_rec = float(recall_score(y_gap, oof_preds, zero_division=0))
    cv_f1 = float(f1_score(y_gap, oof_preds, zero_division=0))

    try:
        cv_roc_auc = float(roc_auc_score(y_gap, oof_probas))
    except Exception:
        cv_roc_auc = 0.5

    cv_brier = float(brier_score_loss(y_gap, oof_probas))
    cv_ece, calibration_bins = compute_expected_calibration_error(y_gap, oof_probas, n_bins=10)

    # Severity correlation on true gaps
    pos_mask = (y_gap == 1)
    if np.sum(pos_mask) >= 5:
        spearman_res = spearmanr(y_sev[pos_mask], oof_sev_preds[pos_mask])
        rho = float(spearman_res.correlation) if not np.isnan(spearman_res.correlation) else 0.0
        sev_mae = float(mean_absolute_error(y_sev[pos_mask], oof_sev_preds[pos_mask]))
    else:
        rho = 0.0
        sev_mae = 0.0

    cv_overall = {
        "n_candidates": n_samples,
        "n_positive_gold_matches": n_pos,
        "n_negative_candidates": n_neg,
        "accuracy": round(cv_acc, 4),
        "precision": round(cv_prec, 4),
        "recall": round(cv_rec, 4),
        "f1": round(cv_f1, 4),
        "roc_auc": round(cv_roc_auc, 4),
        "brier_score": round(cv_brier, 4),
        "ece": round(cv_ece, 4),
        "severity_spearman_rho": round(rho, 4),
        "severity_mae": round(sev_mae, 4),
    }

    print("\n" + "=" * 60)
    print("Candidate-Level Fusion Scorer Grouped-CV Performance:")
    print("=" * 60)
    print(f"  Candidate Accuracy:    {cv_overall['accuracy']:.4f}")
    print(f"  Candidate Precision:   {cv_overall['precision']:.4f}")
    print(f"  Candidate Recall:      {cv_overall['recall']:.4f}")
    print(f"  Candidate F1 Score:    {cv_overall['f1']:.4f}")
    print(f"  Candidate ROC-AUC:     {cv_overall['roc_auc']:.4f}")
    print(f"  Brier Score:           {cv_overall['brier_score']:.4f}")
    print(f"  Expected Calib Error:  {cv_overall['ece']:.4f}")
    print(f"  Severity Spearman Rho: {cv_overall['severity_spearman_rho']:.4f}")
    print("=" * 60)

    # Train Final Production Model on All Candidate Data
    print("\n[*] Training final production MLP Fusion Scorer...")
    final_model = MLPFusionScorer(seed=seed)
    final_model.fit(x, y_gap, y_sev, feature_names)

    model_path = output_dir / "fusion_model.joblib"
    final_model.save(model_path)
    print(f"    [+] Serialized model artifact to: {model_path}")

    # Provenance Configuration
    run_provenance = {
        "timestamp": start_time.isoformat(),
        "git_commit": get_git_commit(),
        "python_version": sys.version.split()[0],
        "seed": seed,
        "n_splits": effective_splits,
        "gold_file": str(gold_file),
        "n_candidates": n_samples,
        "n_positive": n_pos,
        "n_negative": n_neg,
        "feature_count": len(feature_names),
        "feature_names": feature_names,
        "architecture": "MLP (128 units, ReLU, Adam) + Heuristic Fallback",
        "provisional_reference": "Rater 1 (Provisional Reference per Stakeholder Directive)",
    }

    with (output_dir / "config.json").open("w", encoding="utf-8") as f:
        json.dump(run_provenance, f, indent=2)

    with (output_dir / "cv_metrics.json").open("w", encoding="utf-8") as f:
        json.dump({"overall": cv_overall, "folds": fold_metrics}, f, indent=2)

    with (output_dir / "calibration_data.json").open("w", encoding="utf-8") as f:
        json.dump({"ece": cv_ece, "bins": calibration_bins}, f, indent=2)

    return {
        "cv_overall": cv_overall,
        "fold_metrics": fold_metrics,
        "calibration_bins": calibration_bins,
        "model_path": str(model_path),
        "output_dir": str(output_dir),
    }
