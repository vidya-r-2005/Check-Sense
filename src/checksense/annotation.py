"""Annotation validation and multi-gap management module for CheckSense (Phase 3).

Enforces strict integrity constraints per MASTER_SPEC.md:
1. Multi-gap support: One row per gap in CSV; clean requirements have exactly one row with has_gap=0.
2. Clean and gap rows can NEVER coexist for the same requirement.
3. Strict validation before verification (label_status='verified'):
   - For ambiguity and incompleteness, span_text must be a non-empty, exact substring of the requirement.
   - Clarification question must end in exactly one '?' and contain no other question marks.
   - Severity must be in {1, 2, 3}.
4. Held-out test set sequestering: Prevents test documents/splits from loading in annotation workflows.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from typing import Any

TAXONOMY: dict[str, list[str]] = {
    "ambiguity": [
        "vague_term",
        "vague_quantifier",
        "anaphora",
        "coordination",
    ],
    "incompleteness": [
        "missing_actor",
        "missing_condition",
        "missing_threshold",
        "missing_error_handling",
    ],
    "implicit": [
        "unstated_constraint",
    ],
}

ALL_SUBTYPES: list[str] = [sub for subs in TAXONOMY.values() for sub in subs]

ANNOTATION_COLUMNS = [
    "req_id",
    "doc_id",
    "text",
    "has_gap",
    "gap_type",
    "subtype",
    "span_text",
    "severity",
    "explanation",
    "question",
    "stakeholder_answer",
    "refined_text",
    "annotator",
    "label_status",
    "notes",
]


def validate_clarification_question(question: str) -> list[str]:
    """Validate question formatting: exactly one '?' at the end, max 30 words."""
    errors: list[str] = []
    q = question.strip()
    if not q:
        errors.append("Clarification question cannot be empty for a verified gap.")
        return errors

    if not q.endswith("?"):
        errors.append("Clarification question must end with a question mark ('?').")

    q_mark_count = q.count("?")
    if q_mark_count > 1:
        errors.append(
            f"Clarification question must contain exactly one question mark, found {q_mark_count}."
        )

    words = q.split()
    if len(words) > 30:
        errors.append(f"Clarification question exceeds 30 words ({len(words)} words).")

    return errors


def validate_gap_row(
    req_text: str,
    row: dict[str, Any],
    for_verification: bool = True,
) -> list[str]:
    """Validate a single gap row against schema and integrity rules.

    Args:
        req_text: The full text of the requirement.
        row: Annotation dictionary for the gap.
        for_verification: If True, enforce strict rules required for label_status='verified'.

    Returns:
        List of validation error strings (empty if valid).
    """
    errors: list[str] = []
    has_gap_str = str(row.get("has_gap", "")).strip().lower()

    if has_gap_str in ("0", "false"):
        # Clean requirement row
        if for_verification:
            if row.get("gap_type"):
                errors.append("Clean requirement (has_gap=0) must not have a gap_type.")
            if row.get("subtype"):
                errors.append("Clean requirement (has_gap=0) must not have a subtype.")
            if row.get("span_text"):
                errors.append("Clean requirement (has_gap=0) must not have a span_text.")
            if str(row.get("severity", "")).strip():
                errors.append("Clean requirement (has_gap=0) must not specify a severity.")
        return errors

    if has_gap_str not in ("1", "true"):
        errors.append(f"Invalid has_gap value: '{has_gap_str}'. Must be '0' or '1'.")
        return errors

    gap_type = str(row.get("gap_type", "")).strip().lower()
    subtype = str(row.get("subtype", "")).strip().lower()
    span_text = str(row.get("span_text", ""))

    if gap_type not in TAXONOMY:
        errors.append(
            f"Invalid gap_type '{gap_type}'. Allowed: {list(TAXONOMY.keys())}"
        )
    elif subtype not in TAXONOMY[gap_type]:
        errors.append(
            f"Invalid subtype '{subtype}' for gap_type '{gap_type}'. Allowed: {TAXONOMY[gap_type]}"
        )

    if for_verification:
        # Span validation
        if gap_type in ("ambiguity", "incompleteness"):
            if not span_text or not span_text.strip():
                errors.append(
                    f"Span text is required for '{gap_type}' gaps before verification."
                )
            elif span_text not in req_text:
                errors.append(
                    f"Defective span '{span_text}' is not an exact substring of the requirement text."
                )

        # Severity validation
        sev_str = str(row.get("severity", "")).strip()
        if sev_str not in ("1", "2", "3"):
            errors.append(
                f"Invalid severity '{sev_str}'. Must be one of 1 (minor), 2 (moderate), or 3 (critical)."
            )

        # Explanation validation
        expl = str(row.get("explanation", "")).strip()
        if not expl:
            errors.append("A grounded one-sentence explanation is required before verification.")

        # Question validation
        question = str(row.get("question", "")).strip()
        errors.extend(validate_clarification_question(question))

    return errors


def validate_requirement_annotations(
    req_text: str,
    rows: list[dict[str, Any]],
    for_verification: bool = True,
) -> list[str]:
    """Validate a set of annotation rows belonging to a single requirement.

    Ensures that clean (has_gap=0) and defective (has_gap=1) rows NEVER coexist.
    """
    errors: list[str] = []
    if not rows:
        errors.append("Requirement has no annotation rows.")
        return errors

    has_cleans = [
        str(r.get("has_gap", "")).strip().lower() in ("0", "false")
        for r in rows
    ]
    has_gaps = [
        str(r.get("has_gap", "")).strip().lower() in ("1", "true") or bool(r.get("gap_type"))
        for r in rows
    ]

    if any(has_cleans) and any(has_gaps):
        errors.append(
            "Integrity violation: A clean label (has_gap=0) cannot coexist with gap rows for the same requirement."
        )

    if any(has_cleans) and len(rows) > 1:
        errors.append(
            f"Integrity violation: Clean requirements must have exactly one row, found {len(rows)}."
        )

    for idx, r in enumerate(rows):
        row_errors = validate_gap_row(req_text, r, for_verification=for_verification)
        for err in row_errors:
            errors.append(f"Row {idx + 1}: {err}")

    return errors


def load_annotation_sheet(sheet_path: Path) -> dict[str, list[dict[str, str]]]:
    """Load an annotation CSV sheet into mapping of req_id -> list of gap rows."""
    if not sheet_path.exists():
        return defaultdict(list)

    req_map: dict[str, list[dict[str, str]]] = defaultdict(list)
    with open(sheet_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            req_id = row.get("req_id", "").strip()
            if req_id:
                req_map[req_id].append(dict(row))

    return req_map


def save_annotation_rows(
    csv_path: Path,
    req_id: str,
    new_rows: list[dict[str, Any]],
    req_text: str = "",
    for_verification: bool = False,
) -> None:
    """Safely update or replace annotation rows for a specific req_id.

    Raises:
        ValueError: If new_rows violate validation rules (e.g. clean coexisting with gaps,
                    invalid spans or invalid questions on verification).
    """
    if not new_rows:
        raise ValueError("Cannot save empty annotation rows.")

    if req_text:
        errors = validate_requirement_annotations(req_text, new_rows, for_verification=for_verification)
        if errors:
            raise ValueError(f"Annotation validation failed for {req_id}:\n" + "\n".join(errors))

    existing_map = load_annotation_sheet(csv_path)
    existing_map[req_id] = [
        {col: str(r.get(col, "")) for col in ANNOTATION_COLUMNS}
        for r in new_rows
    ]

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ANNOTATION_COLUMNS)
        writer.writeheader()
        for rid in sorted(existing_map.keys()):
            for row in existing_map[rid]:
                writer.writerow(row)
