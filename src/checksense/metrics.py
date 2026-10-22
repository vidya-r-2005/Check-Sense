"""Evaluation metrics and matching protocol for CheckSense.

Implements the evaluation specification from MASTER_SPEC.md (Section 7):
- Matching: ambiguity & incompleteness match on gap_type equality and span overlap
  (token Jaccard >= 0.5 or containment). Implicit gaps match at requirement level.
- Primary metric: gap-level macro-F1 over the 3 taxonomy classes (ambiguity, incompleteness, implicit).
- Secondary: per-class P/R/F1, micro-F1, micro-F2.
- Requirement-level: has_gap PR-AUC, Accuracy, False-Alarm Rate on clean requirements (has_gap=0).
- Severity & Ranking: Spearman rho and nDCG@3 against annotator severity.
- Reliability & Calibration: Expected Calibration Error (ECE) and Brier score.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
from scipy.stats import spearmanr
from sklearn.metrics import auc, precision_recall_curve

TAXONOMY_CLASSES = ["ambiguity", "incompleteness", "implicit"]


@dataclass
class ClassMetrics:
    """Precision, Recall, and F1 metrics for a single gap class."""

    class_name: str
    tp: int
    fp: int
    fn: int
    precision: float
    recall: float
    f1: float
    f2: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvaluationReport:
    """Comprehensive evaluation metrics report."""

    n_requirements: int
    n_clean_requirements: int
    n_gold_gaps: int
    n_pred_gaps: int
    req_level: bool

    # Primary gap metrics
    macro_f1: float
    micro_f1: float
    micro_f2: float
    per_class: dict[str, ClassMetrics]

    # Requirement-level metrics
    has_gap_accuracy: float
    has_gap_precision: float
    has_gap_recall: float
    has_gap_f1: float
    has_gap_pr_auc: float
    false_alarm_rate_clean: float

    # Ranking & Severity metrics
    spearman_rho: float
    ndcg_at_3: float

    # Calibration & Reliability
    ece: float
    brier_score: float

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["per_class"] = {k: v.to_dict() for k, v in self.per_class.items()}
        return d


def compute_token_jaccard(span_a: str, span_b: str) -> float:
    """Compute token-level Jaccard similarity between two spans."""
    tokens_a = set(span_a.lower().split())
    tokens_b = set(span_b.lower().split())
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a.intersection(tokens_b)
    union = tokens_a.union(tokens_b)
    return len(intersection) / len(union)


def is_span_match(span_a: str, span_b: str, jaccard_threshold: float = 0.5) -> bool:
    """Determine if two spans match by token Jaccard or containment."""
    a = span_a.strip().lower()
    b = span_b.strip().lower()
    if not a or not b:
        return False
    # Containment: one span contains the other
    if a in b or b in a:
        return True
    # Token Jaccard threshold
    return compute_token_jaccard(a, b) >= jaccard_threshold


def match_requirement_gaps(
    pred_gaps: list[dict[str, Any]],
    gold_gaps: list[dict[str, Any]],
    req_level: bool = False,
) -> tuple[list[tuple[int, int]], list[int], list[int]]:
    """Match predicted gaps against gold gaps for a single requirement.

    Args:
        pred_gaps: List of predicted gap dicts with 'gap_type', 'span_text'.
        gold_gaps: List of gold gap dicts with 'gap_type', 'span_text', 'has_gap'.
        req_level: If True, matches purely at requirement level.

    Returns:
        tuple of (matched_pairs, unmatched_preds, unmatched_golds)
    """
    # Filter gold gaps to active gaps (has_gap == 1)
    active_gold = [
        (i, g) for i, g in enumerate(gold_gaps)
        if int(g.get("has_gap", 1)) == 1
    ]

    matched_pairs: list[tuple[int, int]] = []
    used_gold_indices: set[int] = set()
    used_pred_indices: set[int] = set()

    for p_idx, pred in enumerate(pred_gaps):
        p_type = pred.get("gap_type")
        p_span = str(pred.get("span_text", ""))

        for g_idx, gold in active_gold:
            if g_idx in used_gold_indices:
                continue

            g_type = gold.get("gap_type")
            g_span = str(gold.get("span_text", ""))

            # Types must match
            if p_type != g_type:
                continue

            # Matching criteria
            is_match = False
            if req_level or p_type == "implicit":
                is_match = True
            else:
                is_match = is_span_match(p_span, g_span)

            if is_match:
                matched_pairs.append((p_idx, g_idx))
                used_gold_indices.add(g_idx)
                used_pred_indices.add(p_idx)
                break

    unmatched_preds = [i for i in range(len(pred_gaps)) if i not in used_pred_indices]
    unmatched_golds = [g_idx for g_idx, _ in active_gold if g_idx not in used_gold_indices]

    return matched_pairs, unmatched_preds, unmatched_golds


def compute_f_scores(tp: int, fp: int, fn: int) -> tuple[float, float, float, float]:
    """Compute precision, recall, f1, and f2 from counts."""
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    beta_sq = 4.0  # beta = 2
    f2 = ((1 + beta_sq) * precision * recall) / (beta_sq * precision + recall) if (beta_sq * precision + recall) > 0 else 0.0
    return precision, recall, f1, f2


def compute_pr_auc(y_true: list[int], y_scores: list[float]) -> float:
    """Compute Area Under Precision-Recall Curve."""
    if len(set(y_true)) < 2:
        return 0.0
    precision, recall, _ = precision_recall_curve(y_true, y_scores)
    return float(auc(recall, precision))


def compute_spearman_rho(y_pred: list[float], y_true: list[float]) -> float:
    """Compute Spearman rank correlation between predictions and gold."""
    if len(y_pred) < 2 or len(set(y_pred)) < 2 or len(set(y_true)) < 2:
        return 0.0
    rho, _ = spearmanr(y_pred, y_true)
    return 0.0 if math.isnan(rho) else float(rho)


def compute_ndcg_at_k(y_true: list[float], y_pred: list[float], k: int = 3) -> float:
    """Compute Normalized Discounted Cumulative Gain at rank k."""
    if not y_true or not y_pred:
        return 0.0

    order = np.argsort(y_pred)[::-1][:k]
    dcg = sum(
        (2 ** y_true[idx] - 1) / math.log2(rank + 2)
        for rank, idx in enumerate(order)
    )

    ideal_order = np.argsort(y_true)[::-1][:k]
    idcg = sum(
        (2 ** y_true[idx] - 1) / math.log2(rank + 2)
        for rank, idx in enumerate(ideal_order)
    )

    if idcg <= 0.0:
        return 1.0 if dcg <= 0.0 else 0.0
    return float(dcg / idcg)


def compute_ece(y_true: list[int], y_prob: list[float], n_bins: int = 10) -> float:
    """Compute Expected Calibration Error."""
    if not y_true or not y_prob:
        return 0.0

    probs = np.clip(np.array(y_prob, dtype=float), 0.0, 1.0)
    labels = np.array(y_true, dtype=int)
    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    n = len(labels)

    for i in range(n_bins):
        bin_mask = (probs >= bin_edges[i]) & (probs < bin_edges[i + 1])
        if i == n_bins - 1:
            bin_mask = bin_mask | (probs == bin_edges[i + 1])
        bin_count = np.sum(bin_mask)
        if bin_count > 0:
            bin_acc = np.mean(labels[bin_mask])
            bin_conf = np.mean(probs[bin_mask])
            ece += (bin_count / n) * abs(bin_acc - bin_conf)

    return float(ece)


def compute_brier_score(y_true: list[int], y_prob: list[float]) -> float:
    """Compute Brier Score (Mean Squared Error of predicted probabilities)."""
    if not y_true or not y_prob:
        return 0.0
    labels = np.array(y_true, dtype=float)
    probs = np.clip(np.array(y_prob, dtype=float), 0.0, 1.0)
    return float(np.mean((probs - labels) ** 2))


def evaluate_predictions(
    req_predictions: dict[str, list[dict[str, Any]]],
    req_gold: dict[str, list[dict[str, Any]]],
    req_level: bool = False,
) -> EvaluationReport:
    """Run full evaluation across all requirements and produce structured report.

    Args:
        req_predictions: Map of req_id to list of predicted gap dictionaries.
        req_gold: Map of req_id to list of gold gap dictionaries.
        req_level: Whether to evaluate gap matching at requirement level.

    Returns:
        Populated EvaluationReport.
    """
    class_counts = {c: {"tp": 0, "fp": 0, "fn": 0} for c in TAXONOMY_CLASSES}

    all_req_ids = sorted(set(req_predictions.keys()).union(req_gold.keys()))
    n_clean = 0
    clean_false_alarms = 0

    req_y_true: list[int] = []
    req_y_pred_prob: list[float] = []

    sev_pred: list[float] = []
    sev_gold: list[float] = []

    calib_y_true: list[int] = []
    calib_y_prob: list[float] = []

    total_pred_gaps = 0
    total_gold_gaps = 0

    for req_id in all_req_ids:
        preds = req_predictions.get(req_id, [])
        golds = req_gold.get(req_id, [])

        active_golds = [g for g in golds if int(g.get("has_gap", 1)) == 1]
        total_pred_gaps += len(preds)
        total_gold_gaps += len(active_golds)

        # Requirement-level has_gap metrics
        gold_has_gap = 1 if len(active_golds) > 0 else 0
        pred_has_gap = 1 if len(preds) > 0 else 0
        max_prob = max((float(p.get("probability", 0.5)) for p in preds), default=0.0)

        req_y_true.append(gold_has_gap)
        req_y_pred_prob.append(max_prob)

        if gold_has_gap == 0:
            n_clean += 1
            if pred_has_gap == 1:
                clean_false_alarms += 1

        # Match gaps
        matched, un_preds, un_golds = match_requirement_gaps(preds, golds, req_level=req_level)

        for p_idx, g_idx in matched:
            pred = preds[p_idx]
            gold = golds[g_idx]
            gtype = pred.get("gap_type", "ambiguity")
            if gtype in class_counts:
                class_counts[gtype]["tp"] += 1

            # Paired severity
            sev_pred.append(float(pred.get("severity", 2)))
            sev_gold.append(float(gold.get("severity", 2)))

            # Calibration for matched predictions (true positive = 1)
            calib_y_true.append(1)
            calib_y_prob.append(float(pred.get("probability", 0.8)))

        for p_idx in un_preds:
            pred = preds[p_idx]
            gtype = pred.get("gap_type", "ambiguity")
            if gtype in class_counts:
                class_counts[gtype]["fp"] += 1

            # Calibration for false positive prediction (true positive = 0)
            calib_y_true.append(0)
            calib_y_prob.append(float(pred.get("probability", 0.8)))

        for g_idx in un_golds:
            gold = golds[g_idx]
            gtype = gold.get("gap_type", "ambiguity")
            if gtype in class_counts:
                class_counts[gtype]["fn"] += 1

    # Compute per-class and macro metrics
    per_class_metrics: dict[str, ClassMetrics] = {}
    f1_list: list[float] = []
    total_tp = 0
    total_fp = 0
    total_fn = 0

    for c in TAXONOMY_CLASSES:
        counts = class_counts[c]
        p, r, f1, f2 = compute_f_scores(counts["tp"], counts["fp"], counts["fn"])
        per_class_metrics[c] = ClassMetrics(
            class_name=c,
            tp=counts["tp"],
            fp=counts["fp"],
            fn=counts["fn"],
            precision=p,
            recall=r,
            f1=f1,
            f2=f2,
        )
        f1_list.append(f1)
        total_tp += counts["tp"]
        total_fp += counts["fp"]
        total_fn += counts["fn"]

    macro_f1 = float(np.mean(f1_list)) if f1_list else 0.0
    _, _, micro_f1, micro_f2 = compute_f_scores(total_tp, total_fp, total_fn)

    # Requirement-level metrics
    req_tp = sum(1 for y, p in zip(req_y_true, req_y_pred_prob, strict=True) if y == 1 and p >= 0.5)
    req_fp = sum(1 for y, p in zip(req_y_true, req_y_pred_prob, strict=True) if y == 0 and p >= 0.5)
    req_fn = sum(1 for y, p in zip(req_y_true, req_y_pred_prob, strict=True) if y == 1 and p < 0.5)
    req_tn = sum(1 for y, p in zip(req_y_true, req_y_pred_prob, strict=True) if y == 0 and p < 0.5)

    req_prec, req_rec, req_f1, _ = compute_f_scores(req_tp, req_fp, req_fn)
    req_acc = (req_tp + req_tn) / len(req_y_true) if req_y_true else 0.0
    pr_auc = compute_pr_auc(req_y_true, req_y_pred_prob)
    far_clean = clean_false_alarms / n_clean if n_clean > 0 else 0.0

    # Severity ranking
    rho = compute_spearman_rho(sev_pred, sev_gold)
    ndcg = compute_ndcg_at_k(sev_gold, sev_pred, k=3)

    # Calibration
    ece = compute_ece(calib_y_true, calib_y_prob)
    brier = compute_brier_score(calib_y_true, calib_y_prob)

    return EvaluationReport(
        n_requirements=len(all_req_ids),
        n_clean_requirements=n_clean,
        n_gold_gaps=total_gold_gaps,
        n_pred_gaps=total_pred_gaps,
        req_level=req_level,
        macro_f1=macro_f1,
        micro_f1=micro_f1,
        micro_f2=micro_f2,
        per_class=per_class_metrics,
        has_gap_accuracy=req_acc,
        has_gap_precision=req_prec,
        has_gap_recall=req_rec,
        has_gap_f1=req_f1,
        has_gap_pr_auc=pr_auc,
        false_alarm_rate_clean=far_clean,
        spearman_rho=rho,
        ndcg_at_3=ndcg,
        ece=ece,
        brier_score=brier,
    )
