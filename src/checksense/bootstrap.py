"""Bootstrap statistical significance and confidence interval engine for CheckSense.

Implements MASTER_SPEC.md (Section 7):
- 1,000-sample bootstrap confidence intervals resampling requirements
- Paired bootstrap hypothesis tests for system comparisons
"""

from __future__ import annotations

from typing import Any

import numpy as np

from .metrics import evaluate_predictions


def compute_bootstrap_confidence_intervals(
    req_predictions: dict[str, list[dict[str, Any]]],
    req_gold: dict[str, list[dict[str, Any]]],
    n_bootstrap: int = 1000,
    confidence_level: float = 0.95,
    seed: int = 42,
    req_level: bool = False,
) -> dict[str, Any]:
    """Compute cluster bootstrap confidence intervals resampling requirements.

    Args:
        req_predictions: Mapping of req_id to list of predicted gap dicts.
        req_gold: Mapping of req_id to list of gold gap dicts.
        n_bootstrap: Number of bootstrap iterations (default: 1000).
        confidence_level: Confidence level (default: 0.95 for 95% CI).
        seed: Random seed.
        req_level: Whether to evaluate matching at requirement level.

    Returns:
        Dictionary of point estimates, standard errors, and percentile CIs.
    """
    req_ids = sorted(set(req_predictions.keys()).union(req_gold.keys()))
    n_reqs = len(req_ids)
    if n_reqs == 0:
        return {}

    # Point estimate on full dataset
    point_report = evaluate_predictions(req_predictions, req_gold, req_level=req_level)
    point_dict = point_report.to_dict()

    metric_keys = [
        "macro_f1",
        "micro_f1",
        "micro_f2",
        "has_gap_accuracy",
        "has_gap_pr_auc",
        "false_alarm_rate_clean",
        "ece",
        "brier_score",
    ]

    boot_metrics: dict[str, list[float]] = {k: [] for k in metric_keys}
    alpha = (1.0 - confidence_level) / 2.0
    low_pct = alpha * 100.0
    high_pct = (1.0 - alpha) * 100.0

    rng = np.random.default_rng(seed)

    for _ in range(n_bootstrap):
        # Cluster resample requirements with replacement
        sampled_indices = rng.choice(n_reqs, size=n_reqs, replace=True)
        sample_preds: dict[str, list[dict[str, Any]]] = {}
        sample_gold: dict[str, list[dict[str, Any]]] = {}

        for synthetic_idx, orig_idx in enumerate(sampled_indices):
            orig_rid = req_ids[orig_idx]
            synthetic_rid = f"BOOT_{synthetic_idx}_{orig_rid}"
            sample_preds[synthetic_rid] = req_predictions.get(orig_rid, [])
            sample_gold[synthetic_rid] = req_gold.get(orig_rid, [])

        report = evaluate_predictions(sample_preds, sample_gold, req_level=req_level)
        rep_dict = report.to_dict()

        for k in metric_keys:
            boot_metrics[k].append(rep_dict.get(k, 0.0))

    results: dict[str, Any] = {
        "n_requirements": n_reqs,
        "n_bootstrap": n_bootstrap,
        "confidence_level": confidence_level,
        "metrics": {},
    }

    for k in metric_keys:
        vals = boot_metrics[k]
        pe = point_dict.get(k, 0.0)
        mean_b = float(np.mean(vals))
        std_b = float(np.std(vals))
        ci_l = float(np.percentile(vals, low_pct))
        ci_h = float(np.percentile(vals, high_pct))

        results["metrics"][k] = {
            "point_estimate": round(pe, 4),
            "bootstrap_mean": round(mean_b, 4),
            "std_error": round(std_b, 4),
            "ci_lower": round(ci_l, 4),
            "ci_upper": round(ci_h, 4),
        }

    return results


def run_paired_bootstrap_test(
    preds_a: dict[str, list[dict[str, Any]]],
    preds_b: dict[str, list[dict[str, Any]]],
    req_gold: dict[str, list[dict[str, Any]]],
    metric: str = "macro_f1",
    n_bootstrap: int = 1000,
    seed: int = 42,
    req_level: bool = False,
) -> dict[str, Any]:
    """Execute paired bootstrap hypothesis test between two systems on the same requirements.

    H0: Metric(System A) == Metric(System B)
    H1: Metric(System A) != Metric(System B)
    """
    req_ids = sorted(set(preds_a.keys()).union(preds_b.keys()).union(req_gold.keys()))
    n_reqs = len(req_ids)
    if n_reqs == 0:
        return {}

    # Observed difference
    rep_a = evaluate_predictions(preds_a, req_gold, req_level=req_level)
    rep_b = evaluate_predictions(preds_b, req_gold, req_level=req_level)

    val_a = rep_a.to_dict().get(metric, 0.0)
    val_b = rep_b.to_dict().get(metric, 0.0)
    obs_diff = val_a - val_b

    rng = np.random.default_rng(seed)
    diffs: list[float] = []

    for _ in range(n_bootstrap):
        sampled_indices = rng.choice(n_reqs, size=n_reqs, replace=True)
        samp_preds_a: dict[str, list[dict[str, Any]]] = {}
        samp_preds_b: dict[str, list[dict[str, Any]]] = {}
        samp_gold: dict[str, list[dict[str, Any]]] = {}

        for synthetic_idx, orig_idx in enumerate(sampled_indices):
            orig_rid = req_ids[orig_idx]
            s_rid = f"BOOT_{synthetic_idx}_{orig_rid}"
            samp_preds_a[s_rid] = preds_a.get(orig_rid, [])
            samp_preds_b[s_rid] = preds_b.get(orig_rid, [])
            samp_gold[s_rid] = req_gold.get(orig_rid, [])

        boot_rep_a = evaluate_predictions(samp_preds_a, samp_gold, req_level=req_level)
        boot_rep_b = evaluate_predictions(samp_preds_b, samp_gold, req_level=req_level)

        b_val_a = boot_rep_a.to_dict().get(metric, 0.0)
        b_val_b = boot_rep_b.to_dict().get(metric, 0.0)
        diffs.append(b_val_a - b_val_b)

    ci_l = float(np.percentile(diffs, 2.5))
    ci_h = float(np.percentile(diffs, 97.5))

    # Empirical two-sided p-value against zero difference
    p_le = np.mean([d <= 0.0 for d in diffs])
    p_ge = np.mean([d >= 0.0 for d in diffs])
    p_val = float(2.0 * min(p_le, p_ge))
    p_val = min(max(p_val, 1.0 / n_bootstrap), 1.0)

    return {
        "metric": metric,
        "n_requirements": n_reqs,
        "n_bootstrap": n_bootstrap,
        "score_a": round(val_a, 4),
        "score_b": round(val_b, 4),
        "observed_diff_a_minus_b": round(obs_diff, 4),
        "ci_95": [round(ci_l, 4), round(ci_h, 4)],
        "p_value": round(p_val, 4),
        "statistically_significant": bool(p_val < 0.05),
    }
