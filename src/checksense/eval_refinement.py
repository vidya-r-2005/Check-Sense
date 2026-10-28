"""Requirement refinement quality assessment and ISO/IEC/IEEE 29148 conformity engine.

Implements MASTER_SPEC.md (Section 7 and Section 8):
- Gap-closure rate (re-running the detector on refined requirements)
- Newly introduced gap rate
- ISO/IEC/IEEE 29148 requirements characteristics before and after
- Strict numeric preservation verification
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .baseline import CandidateGap, detect_rule_gaps
from .heads import Phase4Pipeline
from .refinement import extract_numbers

NORMATIVE_MODALS = {"shall", "must"}
NON_NORMATIVE_MODALS = {"should", "will", "may", "can"}


@dataclass
class ISO29148Characteristics:
    """ISO/IEC/IEEE 29148 requirement quality characteristics."""

    is_singular: bool
    is_normative: bool
    is_unambiguous: bool
    is_complete: bool

    def score(self) -> float:
        """Normalized score [0.0, 1.0] across the 4 characteristics."""
        items = [self.is_singular, self.is_normative, self.is_unambiguous, self.is_complete]
        return sum(1.0 for x in items if x) / len(items)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["conformance_score"] = round(self.score(), 4)
        return d


def evaluate_iso_29148(text: str, detected_gaps: list[CandidateGap] | None = None) -> ISO29148Characteristics:
    """Evaluate ISO/IEC/IEEE 29148 characteristics on a requirement sentence.

    Characteristics:
    1. Singularity: Sentence contains exactly one main normative clause (not multiple conjoined shall/must).
    2. Normative: Sentence contains 'shall' or 'must'.
    3. Unambiguous: Zero detected ambiguity gaps.
    4. Complete: Zero detected incompleteness gaps.
    """
    words = [w.lower().strip(".,;:?!") for w in text.split()]

    # Normative check
    has_normative = any(w in NORMATIVE_MODALS for w in words)

    # Singularity: exactly 1 normative modal verb
    normative_count = sum(1 for w in words if w in NORMATIVE_MODALS)
    is_singular = (normative_count == 1)

    if detected_gaps is None:
        detected_gaps = detect_rule_gaps(text)

    has_ambiguity = any(g.gap_type == "ambiguity" for g in detected_gaps)
    has_incompleteness = any(g.gap_type == "incompleteness" for g in detected_gaps)

    return ISO29148Characteristics(
        is_singular=is_singular,
        is_normative=has_normative,
        is_unambiguous=not has_ambiguity,
        is_complete=not has_incompleteness,
    )


def evaluate_refinement_suite(
    refined_records: list[dict[str, Any]],
    pipeline: Phase4Pipeline | None = None,
) -> dict[str, Any]:
    """Assess refinement quality over a set of requirement rewrites.

    Each record in refined_records must have:
    - 'req_id': ID
    - 'original_text': Original sentence
    - 'stakeholder_answer': Stakeholder response
    - 'refined_text': Refined sentence
    - 'target_gap_type': Optional target gap type
    - 'target_subtype': Optional target subtype
    """
    if not refined_records:
        return {
            "n_records": 0,
            "gap_closure_rate": 0.0,
            "new_gap_rate": 0.0,
            "numeric_preservation_rate": 1.0,
            "iso_29148_before": {},
            "iso_29148_after": {},
        }

    total_orig_gaps = 0
    closed_gaps = 0
    new_gaps_total = 0
    numeric_violations = 0

    scores_before: list[float] = []
    scores_after: list[float] = []

    detect_fn = pipeline.detect_all_gaps if pipeline else detect_rule_gaps

    for rec in refined_records:
        orig_text = rec.get("original_text", "")
        refined_text = rec.get("refined_text", "")
        answer = rec.get("stakeholder_answer", "")

        # 1. Gap detection before and after
        gaps_orig = detect_fn(orig_text)
        gaps_ref = detect_fn(refined_text)

        total_orig_gaps += len(gaps_orig)

        # Matched / closed original gaps
        # An original gap is considered closed if no gap of the same type/subtype exists in refined
        orig_types = {(g.gap_type, g.subtype) for g in gaps_orig}
        ref_types = {(g.gap_type, g.subtype) for g in gaps_ref}

        closed_types = orig_types - ref_types
        closed_gaps += len(closed_types)

        # Newly introduced gap types
        new_introduced = ref_types - orig_types
        new_gaps_total += len(new_introduced)

        # 2. Strict numeric preservation check
        orig_nums = set(extract_numbers(orig_text))
        ans_nums = set(extract_numbers(answer))
        ref_nums = set(extract_numbers(refined_text))

        dropped_nums = orig_nums - ref_nums
        invented_nums = ref_nums - (orig_nums | ans_nums)
        if dropped_nums or invented_nums:
            numeric_violations += 1

        # 3. ISO 29148 characteristics
        iso_b = evaluate_iso_29148(orig_text, detected_gaps=gaps_orig)
        iso_a = evaluate_iso_29148(refined_text, detected_gaps=gaps_ref)
        scores_before.append(iso_b.score())
        scores_after.append(iso_a.score())

    n = len(refined_records)
    gap_closure_rate = float(closed_gaps / total_orig_gaps) if total_orig_gaps > 0 else 1.0
    new_gap_rate = float(new_gaps_total / n) if n > 0 else 0.0
    num_pres_rate = float((n - numeric_violations) / n) if n > 0 else 1.0

    mean_iso_before = float(sum(scores_before) / len(scores_before)) if scores_before else 0.0
    mean_iso_after = float(sum(scores_after) / len(scores_after)) if scores_after else 0.0

    return {
        "n_records": n,
        "total_original_gaps": total_orig_gaps,
        "total_closed_gaps": closed_gaps,
        "gap_closure_rate": round(gap_closure_rate, 4),
        "total_new_gaps_introduced": new_gaps_total,
        "new_gap_rate_per_req": round(new_gap_rate, 4),
        "numeric_preservation_rate": round(num_pres_rate, 4),
        "iso_29148_mean_conformance_before": round(mean_iso_before, 4),
        "iso_29148_mean_conformance_after": round(mean_iso_after, 4),
        "iso_29148_relative_gain": round(mean_iso_after - mean_iso_before, 4),
    }
