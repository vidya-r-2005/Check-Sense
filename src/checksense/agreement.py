"""Inter-rater reliability and Cohen's kappa evaluation module for CheckSense (Phase 3).

Computes unweighted and weighted Cohen's kappa (Cohen 1960, 1968) for pilot double-annotation
inter-rater agreement across binary gap presence, multi-class gap taxonomy, and ordinal severity.
Also provides dataset verification progress auditing.
"""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def interpret_kappa(kappa: float) -> str:
    """Interpret Cohen's kappa score using Landis & Koch (1977) scale."""
    if kappa < 0.0:
        return "Poor (< 0.00)"
    if kappa <= 0.20:
        return "Slight (0.00 - 0.20)"
    if kappa <= 0.40:
        return "Fair (0.21 - 0.40)"
    if kappa <= 0.60:
        return "Moderate (0.41 - 0.60)"
    if kappa <= 0.80:
        return "Substantial (0.61 - 0.80)"
    return "Almost Perfect (0.81 - 1.00)"


def compute_cohens_kappa(
    rater_a: list[Any],
    rater_b: list[Any],
    weights: str | None = None,
) -> dict[str, Any]:
    """Compute Cohen's kappa between two annotators' rating vectors.

    Args:
        rater_a: Annotator A rating list.
        rater_b: Annotator B rating list.
        weights: None (unweighted), 'linear', or 'quadratic'.

    Returns:
        Dictionary containing kappa, observed agreement, chance agreement,
        confusion matrix, and interpretation.
    """
    if len(rater_a) != len(rater_b):
        raise ValueError(
            f"Length mismatch between raters: rater_a={len(rater_a)}, rater_b={len(rater_b)}"
        )

    n = len(rater_a)
    if n == 0:
        return {
            "kappa": 1.0,
            "observed_agreement": 1.0,
            "chance_agreement": 1.0,
            "interpretation": "Perfect (empty set)",
            "n_items": 0,
            "confusion_matrix": {},
        }

    # Discover unique categories
    categories = sorted(set(rater_a) | set(rater_b), key=lambda x: str(x))
    k = len(categories)
    cat_to_idx = {c: i for i, c in enumerate(categories)}

    # Build confusion matrix counts
    matrix = [[0] * k for _ in range(k)]
    for a, b in zip(rater_a, rater_b, strict=False):
        matrix[cat_to_idx[a]][cat_to_idx[b]] += 1

    if weights in ("linear", "quadratic"):
        # Ordinal weighting
        w_matrix = [[0.0] * k for _ in range(k)]
        denom = float(k - 1) if k > 1 else 1.0
        for i in range(k):
            for j in range(k):
                diff = abs(i - j) / denom
                if weights == "linear":
                    w_matrix[i][j] = 1.0 - diff
                else:
                    w_matrix[i][j] = 1.0 - (diff**2)

        # Observed weighted agreement
        p_o = sum(
            w_matrix[i][j] * (matrix[i][j] / n)
            for i in range(k)
            for j in range(k)
        )

        # Marginal probabilities
        row_sums = [sum(matrix[i][j] for j in range(k)) / n for i in range(k)]
        col_sums = [sum(matrix[i][j] for i in range(k)) / n for j in range(k)]

        # Chance weighted agreement
        p_e = sum(
            w_matrix[i][j] * row_sums[i] * col_sums[j]
            for i in range(k)
            for j in range(k)
        )
    else:
        # Standard unweighted Cohen's kappa
        p_o = sum(matrix[i][i] for i in range(k)) / n
        row_sums = [sum(matrix[i][j] for j in range(k)) / n for i in range(k)]
        col_sums = [sum(matrix[i][j] for i in range(k)) / n for j in range(k)]
        p_e = sum(row_sums[i] * col_sums[i] for i in range(k))

    if abs(1.0 - p_e) < 1e-12:
        kappa = 1.0 if abs(p_o - 1.0) < 1e-12 else 0.0
    else:
        kappa = (p_o - p_e) / (1.0 - p_e)

    # Format human-readable confusion dict
    conf_dict: dict[str, dict[str, int]] = {}
    for i, cat_i in enumerate(categories):
        conf_dict[str(cat_i)] = {str(cat_j): matrix[i][j] for j, cat_j in enumerate(categories)}

    return {
        "kappa": round(kappa, 4),
        "observed_agreement": round(p_o, 4),
        "chance_agreement": round(p_e, 4),
        "interpretation": interpret_kappa(kappa),
        "n_items": n,
        "categories": [str(c) for c in categories],
        "confusion_matrix": conf_dict,
    }


def load_annotation_sheet(sheet_path: Path) -> dict[str, list[dict[str, str]]]:
    """Load an annotation CSV sheet into mapping of req_id -> list of gap rows."""
    if not sheet_path.exists():
        raise FileNotFoundError(f"Annotation file not found: {sheet_path}")

    req_map: dict[str, list[dict[str, str]]] = defaultdict(list)
    with open(sheet_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            req_id = row.get("req_id", "").strip()
            if req_id:
                req_map[req_id].append(row)

    return req_map


def compute_annotation_agreement(
    file_a: Path,
    file_b: Path,
) -> dict[str, Any]:
    """Calculate comprehensive inter-rater reliability across two pilot sheets.

    Evaluates:
    - has_gap agreement (clean vs gap)
    - gap_type agreement (ambiguity, incompleteness, implicit, clean)
    - subtype agreement
    - severity agreement (unweighted and quadratically weighted)
    """
    sheet_a = load_annotation_sheet(file_a)
    sheet_b = load_annotation_sheet(file_b)

    common_req_ids = sorted(set(sheet_a.keys()) & set(sheet_b.keys()))
    if not common_req_ids:
        raise ValueError(
            f"No overlapping req_ids between {file_a.name} ({len(sheet_a)} reqs) "
            f"and {file_b.name} ({len(sheet_b)} reqs)."
        )

    # 1. Binary has_gap alignment
    has_gap_a: list[int] = []
    has_gap_b: list[int] = []

    # 2. Primary gap_type alignment (take primary or clean)
    type_a: list[str] = []
    type_b: list[str] = []

    # 3. Subtype alignment
    sub_a: list[str] = []
    sub_b: list[str] = []

    # 4. Severity alignment (ordinal: 0=clean, 1, 2, 3)
    sev_a: list[int] = []
    sev_b: list[int] = []

    disagreements: list[dict[str, Any]] = []

    for req_id in common_req_ids:
        rows_a = sheet_a[req_id]
        rows_b = sheet_b[req_id]

        # Determine has_gap
        # has_gap is 1 if any row has has_gap == '1' or has gap_type
        is_gap_a = 1 if any(str(r.get("has_gap", "")).strip() in ("1", "true", "True") or r.get("gap_type") for r in rows_a) else 0
        is_gap_b = 1 if any(str(r.get("has_gap", "")).strip() in ("1", "true", "True") or r.get("gap_type") for r in rows_b) else 0

        has_gap_a.append(is_gap_a)
        has_gap_b.append(is_gap_b)

        # Primary gap type (or 'clean')
        gtype_a = rows_a[0].get("gap_type", "").strip().lower() if is_gap_a and rows_a[0].get("gap_type") else "clean"
        gtype_b = rows_b[0].get("gap_type", "").strip().lower() if is_gap_b and rows_b[0].get("gap_type") else "clean"
        type_a.append(gtype_a)
        type_b.append(gtype_b)

        # Subtype
        gsub_a = rows_a[0].get("subtype", "").strip().lower() if is_gap_a and rows_a[0].get("subtype") else "clean"
        gsub_b = rows_b[0].get("subtype", "").strip().lower() if is_gap_b and rows_b[0].get("subtype") else "clean"
        sub_a.append(gsub_a)
        sub_b.append(gsub_b)

        # Severity
        def parse_sev(r_list: list[dict[str, str]], is_gap: int) -> int:
            if not is_gap:
                return 0
            for r in r_list:
                s_str = str(r.get("severity", "")).strip()
                if s_str.isdigit():
                    return int(s_str)
            return 2  # Default moderate if unspecified

        s_a = parse_sev(rows_a, is_gap_a)
        s_b = parse_sev(rows_b, is_gap_b)
        sev_a.append(s_a)
        sev_b.append(s_b)

        if is_gap_a != is_gap_b or gtype_a != gtype_b or gsub_a != gsub_b:
            disagreements.append({
                "req_id": req_id,
                "text": rows_a[0].get("text", "")[:80] + "...",
                "rater_a": {"has_gap": is_gap_a, "gap_type": gtype_a, "subtype": gsub_a, "severity": s_a},
                "rater_b": {"has_gap": is_gap_b, "gap_type": gtype_b, "subtype": gsub_b, "severity": s_b},
            })

    kappa_has_gap = compute_cohens_kappa(has_gap_a, has_gap_b)
    kappa_type = compute_cohens_kappa(type_a, type_b)
    kappa_subtype = compute_cohens_kappa(sub_a, sub_b)
    kappa_severity_unweighted = compute_cohens_kappa(sev_a, sev_b)
    kappa_severity_quadratic = compute_cohens_kappa(sev_a, sev_b, weights="quadratic")

    return {
        "n_evaluated": len(common_req_ids),
        "file_a": str(file_a),
        "file_b": str(file_b),
        "has_gap_kappa": kappa_has_gap,
        "gap_type_kappa": kappa_type,
        "subtype_kappa": kappa_subtype,
        "severity_unweighted_kappa": kappa_severity_unweighted,
        "severity_quadratic_kappa": kappa_severity_quadratic,
        "n_disagreements": len(disagreements),
        "disagreements": disagreements,
    }


def compute_dataset_annotation_stats(gold_file: Path) -> dict[str, Any]:
    """Compute verification status and taxonomy breakdown from an annotation file."""
    if not gold_file.exists():
        raise FileNotFoundError(f"Annotation file not found: {gold_file}")

    req_map = load_annotation_sheet(gold_file)
    total_requirements = len(req_map)

    n_verified = 0
    n_draft = 0
    n_unreviewed = 0
    n_clean = 0
    total_gaps = 0

    class_counts: Counter[str] = Counter()
    subtype_counts: Counter[str] = Counter()
    severity_counts: Counter[str] = Counter()
    doc_counts: Counter[str] = Counter()

    for _req_id, rows in req_map.items():
        doc_id = rows[0].get("doc_id", "unknown")
        doc_counts[doc_id] += 1

        # Check overall requirement verification status
        statuses = [r.get("label_status", "").strip().lower() for r in rows]
        if all(s == "verified" for s in statuses if s):
            n_verified += 1
        elif any(s == "draft" for s in statuses):
            n_draft += 1
        else:
            n_unreviewed += 1

        # Check if clean
        is_clean = any(
            str(r.get("has_gap", "")).strip() in ("0", "false", "False")
            and not r.get("gap_type")
            for r in rows
        )
        if is_clean:
            n_clean += 1
        else:
            for r in rows:
                gtype = r.get("gap_type", "").strip().lower()
                gsub = r.get("subtype", "").strip().lower()
                gsev = str(r.get("severity", "")).strip()

                if gtype:
                    total_gaps += 1
                    class_counts[gtype] += 1
                if gsub:
                    subtype_counts[gsub] += 1
                if gsev:
                    severity_counts[gsev] += 1

    return {
        "gold_file": str(gold_file),
        "total_requirements": total_requirements,
        "verified_requirements": n_verified,
        "draft_requirements": n_draft,
        "unreviewed_requirements": n_unreviewed,
        "clean_requirements": n_clean,
        "total_gaps_annotated": total_gaps,
        "class_distribution": dict(class_counts),
        "subtype_distribution": dict(subtype_counts),
        "severity_distribution": dict(severity_counts),
        "per_document_counts": dict(doc_counts),
    }
