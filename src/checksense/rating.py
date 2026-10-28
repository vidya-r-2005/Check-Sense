"""Blinded human-rating sheet generation and scoring engine for CheckSense questions.

Implements MASTER_SPEC.md (Section 7 and Section 8):
- rate-make: Generates randomized, blinded human-rating sheets with reference
  questions mixed in.
- rate-score: Evaluates completed sheets from at least two human raters,
  computing quadratic-weighted Cohen's kappa for inter-rater agreement,
  paired bootstrap tests, and non-inferiority against human reference questions
  (margin Delta = 0.5).
"""

from __future__ import annotations

import csv
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics import cohen_kappa_score

RATING_DIMENSIONS = [
    ("clarity_1_to_5", "clarity", True),
    ("relevance_1_to_5", "relevance", True),
    ("informativeness_1_to_5", "informativeness", True),
    ("answerable_0_1", "answerable", False),
    ("hallucinated_0_1", "hallucinated", False),
]


@dataclass
class RatingItem:
    """A single blinded question rating item."""

    blinded_id: str
    req_id: str
    text: str
    question: str
    system_origin: str


# ============================================================================
# rate-make: Blinded Sheet Generation
# ============================================================================

def generate_blinded_rating_sheet(
    candidate_items: list[dict[str, Any]],
    output_sheet_path: Path,
    key_output_path: Path | None = None,
    seed: int = 42,
) -> tuple[Path, Path]:
    """Generate randomized, blinded human rating sheet.

    Args:
        candidate_items: List of dicts containing:
            - 'req_id': requirement identifier
            - 'text': requirement sentence text
            - 'question': question to be evaluated
            - 'system_origin': origin label ('human_reference', 'checksense', etc.)
        output_sheet_path: Path to output CSV for human raters.
        key_output_path: Path to evaluator blinding key JSON.
        seed: Random seed for deterministic shuffling.

    Returns:
        tuple of (output_sheet_path, key_output_path)
    """
    if not candidate_items:
        raise ValueError("candidate_items cannot be empty.")

    rng = random.Random(seed)
    shuffled_items = list(candidate_items)
    rng.shuffle(shuffled_items)

    blinding_key: dict[str, dict[str, Any]] = {}
    sheet_rows: list[dict[str, Any]] = []

    for idx, item in enumerate(shuffled_items, start=1):
        blinded_id = f"Q{idx:04d}"
        req_id = str(item.get("req_id", f"REQ_{idx}"))
        text = str(item.get("text", "")).strip()
        question = str(item.get("question", "")).strip()
        origin = str(item.get("system_origin", "unknown"))

        blinding_key[blinded_id] = {
            "req_id": req_id,
            "system_origin": origin,
            "original_question": question,
        }

        sheet_rows.append(
            {
                "blinded_id": blinded_id,
                "req_id": req_id,
                "requirement_text": text,
                "clarification_question": question,
                "clarity_1_to_5": "",
                "relevance_1_to_5": "",
                "informativeness_1_to_5": "",
                "answerable_0_1": "",
                "hallucinated_0_1": "",
                "rater_id": "",
                "notes": "",
            }
        )

    output_sheet_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "blinded_id",
        "req_id",
        "requirement_text",
        "clarification_question",
        "clarity_1_to_5",
        "relevance_1_to_5",
        "informativeness_1_to_5",
        "answerable_0_1",
        "hallucinated_0_1",
        "rater_id",
        "notes",
    ]

    with output_sheet_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sheet_rows)

    if key_output_path is None:
        key_output_path = output_sheet_path.parent / "blinding_key.json"

    key_output_path.parent.mkdir(parents=True, exist_ok=True)
    with key_output_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "seed": seed,
                "total_items": len(blinding_key),
                "key": blinding_key,
            },
            f,
            indent=2,
        )

    return output_sheet_path, key_output_path


# ============================================================================
# rate-score: Inter-Rater Agreement & Statistical Comparisons
# ============================================================================

def _parse_rating_sheet(sheet_path: Path) -> dict[str, dict[str, Any]]:
    """Parse a completed rating sheet CSV indexed by blinded_id."""
    if not sheet_path.exists():
        raise FileNotFoundError(f"Rating sheet not found: {sheet_path}")

    ratings: dict[str, dict[str, Any]] = {}
    with sheet_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            bid = row.get("blinded_id", "").strip()
            if not bid:
                continue
            ratings[bid] = row

    return ratings


def compute_inter_rater_agreement(
    ratings_a: dict[str, dict[str, Any]],
    ratings_b: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Compute Cohen's kappa (quadratic weighted for 1-5 scales) between 2 raters."""
    common_ids = sorted(set(ratings_a.keys()).intersection(ratings_b.keys()))
    if not common_ids:
        return {"n_items": 0, "error": "No overlapping item IDs between sheets"}

    agreement_metrics: dict[str, Any] = {"n_items": len(common_ids)}

    for col_name, dim_name, is_ordinal in RATING_DIMENSIONS:
        scores_a: list[int] = []
        scores_b: list[int] = []

        for bid in common_ids:
            val_a_str = ratings_a[bid].get(col_name, "").strip()
            val_b_str = ratings_b[bid].get(col_name, "").strip()
            if val_a_str and val_b_str:
                try:
                    scores_a.append(int(float(val_a_str)))
                    scores_b.append(int(float(val_b_str)))
                except ValueError:
                    continue

        if len(scores_a) < 2:
            agreement_metrics[dim_name] = {
                "n_rated": len(scores_a),
                "kappa": None,
                "exact_agreement": 0.0,
            }
            continue

        arr_a = np.array(scores_a)
        arr_b = np.array(scores_b)
        exact_match = float(np.mean(arr_a == arr_b))

        weights = "quadratic" if is_ordinal else None
        try:
            kappa = float(cohen_kappa_score(arr_a, arr_b, weights=weights))
        except Exception:
            kappa = 0.0

        dim_res: dict[str, Any] = {
            "n_rated": len(scores_a),
            "exact_agreement": round(exact_match, 4),
            "kappa": round(kappa, 4),
            "weights": weights or "unweighted",
        }
        if is_ordinal:
            within_one = float(np.mean(np.abs(arr_a - arr_b) <= 1))
            dim_res["within_1_agreement"] = round(within_one, 4)

        agreement_metrics[dim_name] = dim_res

    return agreement_metrics


def evaluate_question_ratings(
    sheet_paths: list[Path],
    blinding_key_path: Path,
    margin: float = 0.5,
    n_bootstrap: int = 1000,
    seed: int = 42,
) -> dict[str, Any]:
    """Score completed rating sheets and run paired non-inferiority bootstrap tests.

    Args:
        sheet_paths: Paths to 1 or more completed rating sheets.
        blinding_key_path: Path to blinding_key.json.
        margin: Non-inferiority margin Delta (default: 0.5 per MASTER_SPEC.md).
        n_bootstrap: Number of bootstrap iterations.
        seed: Random seed.

    Returns:
        Structured dictionary of rating scores and statistical comparisons.
    """
    if not sheet_paths:
        raise ValueError("At least one rating sheet path is required.")

    if not blinding_key_path.exists():
        raise FileNotFoundError(f"Blinding key file not found: {blinding_key_path}")

    with blinding_key_path.open("r", encoding="utf-8") as f:
        key_data = json.load(f)
    key_mapping = key_data.get("key", {})

    parsed_sheets = [_parse_rating_sheet(p) for p in sheet_paths]

    # Inter-rater agreement if >= 2 sheets
    agreement_res: dict[str, Any] | None = None
    if len(parsed_sheets) >= 2:
        agreement_res = compute_inter_rater_agreement(parsed_sheets[0], parsed_sheets[1])

    # Unblind and aggregate ratings per item across raters
    items_by_system: dict[str, list[dict[str, float]]] = {}

    all_blinded_ids = sorted(key_mapping.keys())
    for bid in all_blinded_ids:
        sys_origin = key_mapping[bid].get("system_origin", "unknown")
        if sys_origin not in items_by_system:
            items_by_system[sys_origin] = []

        item_scores: dict[str, float] = {}
        for col_name, dim_name, _ in RATING_DIMENSIONS:
            vals: list[float] = []
            for sheet in parsed_sheets:
                if bid in sheet:
                    raw_val = sheet[bid].get(col_name, "").strip()
                    if raw_val:
                        try:
                            vals.append(float(raw_val))
                        except ValueError:
                            pass
            if vals:
                item_scores[dim_name] = float(np.mean(vals))

        if item_scores:
            items_by_system[sys_origin].append(item_scores)

    # Compute descriptive statistics per system
    system_summaries: dict[str, Any] = {}
    for sys_name, records in items_by_system.items():
        summary: dict[str, Any] = {"n_items": len(records)}
        for _, dim_name, _ in RATING_DIMENSIONS:
            dim_vals = [r[dim_name] for r in records if dim_name in r]
            if dim_vals:
                summary[dim_name] = {
                    "mean": round(float(np.mean(dim_vals)), 4),
                    "std": round(float(np.std(dim_vals)), 4),
                    "n_rated": len(dim_vals),
                }
            else:
                summary[dim_name] = {"mean": None, "std": None, "n_rated": 0}
        system_summaries[sys_name] = summary

    # Paired non-inferiority check against human reference if available
    comparisons: dict[str, Any] = {}
    human_records = items_by_system.get("human_reference", [])
    rng = np.random.default_rng(seed)

    for sys_name, sys_records in items_by_system.items():
        if sys_name == "human_reference":
            continue

        sys_comp: dict[str, Any] = {}
        for _, dim_name, is_ordinal in RATING_DIMENSIONS:
            if not is_ordinal:
                continue

            h_vals = [r[dim_name] for r in human_records if dim_name in r]
            s_vals = [r[dim_name] for r in sys_records if dim_name in r]

            if not h_vals or not s_vals:
                continue

            mean_h = float(np.mean(h_vals))
            mean_s = float(np.mean(s_vals))
            obs_diff = mean_h - mean_s

            # Bootstrap difference in means
            boot_diffs = []
            for _ in range(n_bootstrap):
                boot_h = rng.choice(h_vals, size=len(h_vals), replace=True)
                boot_s = rng.choice(s_vals, size=len(s_vals), replace=True)
                boot_diffs.append(float(np.mean(boot_h) - np.mean(boot_s)))

            ci_low = float(np.percentile(boot_diffs, 2.5))
            ci_high = float(np.percentile(boot_diffs, 97.5))

            # Non-inferiority: System is non-inferior if upper CI of (Human - System) < margin
            non_inferior = bool(ci_high < margin)

            sys_comp[dim_name] = {
                "human_mean": round(mean_h, 4),
                "system_mean": round(mean_s, 4),
                "mean_diff_human_minus_sys": round(obs_diff, 4),
                "ci_95": [round(ci_low, 4), round(ci_high, 4)],
                "margin": margin,
                "non_inferior": non_inferior,
            }

        comparisons[sys_name] = sys_comp

    return {
        "n_sheets": len(sheet_paths),
        "inter_rater_agreement": agreement_res,
        "system_summaries": system_summaries,
        "non_inferiority_comparisons": comparisons,
    }
