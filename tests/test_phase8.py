"""Unit and regression tests for CheckSense Phase 8.

Tests:
- Blinded rating sheet generation and unblinding key consistency (`rate-make`)
- Inter-rater agreement with quadratic-weighted Cohen's kappa and non-inferiority (`rate-score`)
- Cluster bootstrap confidence intervals (1,000 samples) and paired bootstrap tests
- Requirement refinement quality, gap closure, and ISO/IEC/IEEE 29148 evaluation
- Error analysis generation with length and domain slices
- Paper-style final monograph report generation from results artifacts
- CLI subcommand invocations
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from checksense import (
    CandidateGap,
    compute_bootstrap_confidence_intervals,
    compute_inter_rater_agreement,
    evaluate_iso_29148,
    evaluate_question_ratings,
    evaluate_refinement_suite,
    generate_blinded_rating_sheet,
    generate_error_analysis,
    generate_final_report,
    run_paired_bootstrap_test,
)
from checksense.cli import main

# ============================================================================
# 1. Blinded Human-Rating Sheet Generation (rate-make)
# ============================================================================

def test_generate_blinded_rating_sheet(tmp_path: Path):
    """Verify randomized blinding, rater columns, and key mapping."""
    candidate_items = [
        {"req_id": "R1", "text": "The system shall run fast.", "question": "What is the speed?", "system_origin": "checksense"},
        {"req_id": "R2", "text": "The engine shall halt.", "question": "Under what condition?", "system_origin": "human_reference"},
        {"req_id": "R3", "text": "Records shall be kept.", "question": "For how many days?", "system_origin": "template_strategy"},
    ]

    out_sheet = tmp_path / "sheet.csv"
    out_key = tmp_path / "key.json"

    sheet_p, key_p = generate_blinded_rating_sheet(
        candidate_items=candidate_items,
        output_sheet_path=out_sheet,
        key_output_path=out_key,
        seed=123,
    )

    assert sheet_p.exists()
    assert key_p.exists()

    with sheet_p.open("r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
        assert len(reader) == 3
        blinded_ids = [r["blinded_id"] for r in reader]
        assert set(blinded_ids) == {"Q0001", "Q0002", "Q0003"}
        for r in reader:
            assert "clarity_1_to_5" in r
            assert "relevance_1_to_5" in r
            assert "informativeness_1_to_5" in r
            assert "answerable_0_1" in r
            assert "hallucinated_0_1" in r
            assert "notes" in r

    with key_p.open("r", encoding="utf-8") as f:
        key_data = json.load(f)
        assert key_data["total_items"] == 3
        assert "Q0001" in key_data["key"]
        origins = {v["system_origin"] for v in key_data["key"].values()}
        assert origins == {"checksense", "human_reference", "template_strategy"}


# ============================================================================
# 2. Inter-Rater Agreement & Scoring (rate-score)
# ============================================================================

def test_compute_inter_rater_agreement():
    """Verify quadratic weighted kappa and exact agreement computation."""
    ratings_a = {
        "Q0001": {"clarity_1_to_5": "5", "relevance_1_to_5": "4", "answerable_0_1": "1"},
        "Q0002": {"clarity_1_to_5": "3", "relevance_1_to_5": "2", "answerable_0_1": "0"},
        "Q0003": {"clarity_1_to_5": "4", "relevance_1_to_5": "4", "answerable_0_1": "1"},
    }
    ratings_b = {
        "Q0001": {"clarity_1_to_5": "5", "relevance_1_to_5": "4", "answerable_0_1": "1"},
        "Q0002": {"clarity_1_to_5": "3", "relevance_1_to_5": "3", "answerable_0_1": "0"},
        "Q0003": {"clarity_1_to_5": "4", "relevance_1_to_5": "4", "answerable_0_1": "1"},
    }

    res = compute_inter_rater_agreement(ratings_a, ratings_b)
    assert res["n_items"] == 3
    assert res["clarity"]["exact_agreement"] == 1.0
    assert res["clarity"]["kappa"] == 1.0
    assert res["relevance"]["within_1_agreement"] == 1.0
    assert res["answerable"]["kappa"] == 1.0


def test_evaluate_question_ratings(tmp_path: Path):
    """Verify end-to-end question scoring and non-inferiority bootstrap test."""
    key_file = tmp_path / "blinding_key.json"
    key_data = {
        "total_items": 4,
        "key": {
            "Q0001": {"system_origin": "human_reference", "req_id": "R1"},
            "Q0002": {"system_origin": "checksense", "req_id": "R1"},
            "Q0003": {"system_origin": "human_reference", "req_id": "R2"},
            "Q0004": {"system_origin": "checksense", "req_id": "R2"},
        },
    }
    with key_file.open("w", encoding="utf-8") as f:
        json.dump(key_data, f)

    sheet_a = tmp_path / "sheet_a.csv"
    sheet_b = tmp_path / "sheet_b.csv"

    rows_a = [
        {"blinded_id": "Q0001", "clarity_1_to_5": "5", "relevance_1_to_5": "5", "informativeness_1_to_5": "5", "answerable_0_1": "1", "hallucinated_0_1": "0"},
        {"blinded_id": "Q0002", "clarity_1_to_5": "4", "relevance_1_to_5": "5", "informativeness_1_to_5": "4", "answerable_0_1": "1", "hallucinated_0_1": "0"},
        {"blinded_id": "Q0003", "clarity_1_to_5": "5", "relevance_1_to_5": "4", "informativeness_1_to_5": "5", "answerable_0_1": "1", "hallucinated_0_1": "0"},
        {"blinded_id": "Q0004", "clarity_1_to_5": "5", "relevance_1_to_5": "4", "informativeness_1_to_5": "5", "answerable_0_1": "1", "hallucinated_0_1": "0"},
    ]

    fieldnames = list(rows_a[0].keys())
    with sheet_a.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_a)

    with sheet_b.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_a)

    eval_res = evaluate_question_ratings(
        sheet_paths=[sheet_a, sheet_b],
        blinding_key_path=key_file,
        margin=0.5,
        n_bootstrap=100,
    )

    assert "system_summaries" in eval_res
    assert "human_reference" in eval_res["system_summaries"]
    assert "checksense" in eval_res["system_summaries"]
    assert "non_inferiority_comparisons" in eval_res
    assert "checksense" in eval_res["non_inferiority_comparisons"]
    clarity_comp = eval_res["non_inferiority_comparisons"]["checksense"]["clarity"]
    assert "non_inferior" in clarity_comp


# ============================================================================
# 3. Bootstrap Confidence Intervals & Significance
# ============================================================================

def test_bootstrap_confidence_intervals():
    """Verify cluster bootstrap confidence intervals resampling requirements."""
    gold = {
        "R1": [{"has_gap": 1, "gap_type": "ambiguity", "span_text": "quickly"}],
        "R2": [{"has_gap": 0, "gap_type": "none", "span_text": ""}],
        "R3": [{"has_gap": 1, "gap_type": "incompleteness", "span_text": ""}],
    }
    preds = {
        "R1": [{"gap_type": "ambiguity", "span_text": "quickly", "severity": 2, "probability": 0.9}],
        "R2": [],
        "R3": [{"gap_type": "incompleteness", "span_text": "", "severity": 2, "probability": 0.8}],
    }

    ci_res = compute_bootstrap_confidence_intervals(
        req_predictions=preds,
        req_gold=gold,
        n_bootstrap=50,
        seed=42,
    )

    assert ci_res["n_requirements"] == 3
    assert "macro_f1" in ci_res["metrics"]
    mf1_stat = ci_res["metrics"]["macro_f1"]
    assert "point_estimate" in mf1_stat
    assert "ci_lower" in mf1_stat
    assert "ci_upper" in mf1_stat
    assert mf1_stat["ci_lower"] <= mf1_stat["ci_upper"]


def test_paired_bootstrap_test():
    """Verify paired bootstrap hypothesis testing between two systems."""
    gold = {
        "R1": [{"has_gap": 1, "gap_type": "ambiguity", "span_text": "fast"}],
        "R2": [{"has_gap": 1, "gap_type": "incompleteness", "span_text": ""}],
    }
    preds_a = {
        "R1": [{"gap_type": "ambiguity", "span_text": "fast", "severity": 2, "probability": 0.9}],
        "R2": [{"gap_type": "incompleteness", "span_text": "", "severity": 2, "probability": 0.9}],
    }
    preds_b = {
        "R1": [],
        "R2": [],
    }

    comp = run_paired_bootstrap_test(
        preds_a=preds_a,
        preds_b=preds_b,
        req_gold=gold,
        metric="macro_f1",
        n_bootstrap=50,
        seed=42,
    )

    assert comp["score_a"] > comp["score_b"]
    assert comp["observed_diff_a_minus_b"] > 0
    assert "ci_95" in comp
    assert "p_value" in comp


# ============================================================================
# 4. Refinement Quality & ISO 29148 Assessment
# ============================================================================

def test_evaluate_iso_29148():
    """Verify ISO/IEC/IEEE 29148 characteristics evaluation."""
    singular_normative = "The system shall transmit 100 packets."
    iso_res = evaluate_iso_29148(singular_normative, detected_gaps=[])
    assert iso_res.is_singular is True
    assert iso_res.is_normative is True
    assert iso_res.is_unambiguous is True
    assert iso_res.is_complete is True
    assert iso_res.score() == 1.0

    ambiguous_compound = "The system shall process records quickly and the operator must confirm."
    gaps = [
        CandidateGap(
            gap_type="ambiguity",
            subtype="vague_term",
            span_text="quickly",
            start_char=33,
            end_char=40,
            severity=2,
            probability=0.8,
            explanation="Vague adverb without quantitative metric.",
            question="What is the required processing time in milliseconds?",
        )
    ]
    iso_bad = evaluate_iso_29148(ambiguous_compound, detected_gaps=gaps)
    assert iso_bad.is_singular is False  # two normative modals ('shall', 'must')
    assert iso_bad.is_unambiguous is False  # has ambiguity gap
    assert iso_bad.score() < 1.0


def test_evaluate_refinement_suite():
    """Verify gap closure and numeric preservation assessment."""
    records = [
        {
            "req_id": "R1",
            "original_text": "The engine shall process records quickly within 5 seconds.",
            "stakeholder_answer": "within 100 milliseconds",
            "refined_text": "The engine shall process records within 100 milliseconds within 5 seconds.",
        }
    ]

    res = evaluate_refinement_suite(records)
    assert res["n_records"] == 1
    assert "gap_closure_rate" in res
    assert "numeric_preservation_rate" in res
    assert res["numeric_preservation_rate"] == 1.0


# ============================================================================
# 5. Error Analysis & Final Report Generation
# ============================================================================

def test_generate_error_analysis(tmp_path: Path):
    """Verify reports/error_analysis.md generation with length/domain slices."""
    gold = {
        "R1": [{"has_gap": 1, "gap_type": "ambiguity", "span_text": "fast", "text": "The fast car shall stop.", "doc_id": "DOC1"}],
        "R2": [{"has_gap": 0, "gap_type": "none", "span_text": "", "text": "The sensor shall report 10 units.", "doc_id": "DOC2"}],
    }
    preds = {
        "R1": [{"gap_type": "ambiguity", "span_text": "fast", "severity": 2, "probability": 0.9}],
        "R2": [{"gap_type": "ambiguity", "span_text": "10", "severity": 2, "probability": 0.8}],  # false alarm
    }

    err_path = tmp_path / "error_analysis.md"
    generate_error_analysis(preds, gold, output_path=err_path)

    assert err_path.exists()
    content = err_path.read_text(encoding="utf-8")
    assert "Error Analysis & Failure Modes Report" in content
    assert "Slice Analysis by Requirement Token Length" in content
    assert "Slice Analysis by Specification Domain / Document" in content
    assert "Sample FP-1" in content


def test_generate_final_report(tmp_path: Path):
    """Verify reports/final_report.md populated from results artifacts."""
    summary_csv = tmp_path / "summary.csv"
    with summary_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["system", "type", "macro_f1", "micro_f1", "ambiguity_f1", "incompleteness_f1", "implicit_f1", "has_gap_accuracy", "clean_false_alarm_rate", "n_predicted_gaps", "status"])
        writer.writeheader()
        writer.writerow({
            "system": "B1_rules", "type": "baseline", "macro_f1": "0.7006", "micro_f1": "0.5714",
            "ambiguity_f1": "0.5652", "incompleteness_f1": "0.5366", "implicit_f1": "1.0",
            "has_gap_accuracy": "0.66", "clean_false_alarm_rate": "0.5", "n_predicted_gaps": "44", "status": "evaluated"
        })

    comp_json = tmp_path / "comparative_metrics.json"
    comp_json.write_text("{}", encoding="utf-8")

    out_rep = tmp_path / "final_report.md"
    generate_final_report(
        summary_csv_path=summary_csv,
        comparative_metrics_path=comp_json,
        output_path=out_rep,
    )

    assert out_rep.exists()
    content = out_rep.read_text(encoding="utf-8")
    assert "CheckSense: Multi-Head Defect Detection" in content
    assert "B1_rules" in content
    assert "Held-Out Test Set Status" in content
    assert "data/gold/test_pool.jsonl" in content


# ============================================================================
# 6. CLI Invocations (rate-make, rate-score, report)
# ============================================================================

def test_cli_rate_make_and_rate_score(tmp_path: Path):
    """Verify rate-make and rate-score CLI subcommands."""
    gold_path = Path("data/gold/annotations/rater_1.csv")
    if not gold_path.exists():
        return

    sheet_out = tmp_path / "ratings" / "sheet.csv"
    key_out = tmp_path / "ratings" / "key.json"

    # 1. rate-make CLI
    ret_make = main(["rate-make", "--gold-file", str(gold_path), "--output-sheet", str(sheet_out), "--key-file", str(key_out)])
    assert ret_make == 0
    assert sheet_out.exists()
    assert key_out.exists()

    # Fill sample rating in sheet for rater A and B
    with sheet_out.open("r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    for r in rows:
        r["clarity_1_to_5"] = "4"
        r["relevance_1_to_5"] = "5"
        r["informativeness_1_to_5"] = "4"
        r["answerable_0_1"] = "1"
        r["hallucinated_0_1"] = "0"

    sheet_a = tmp_path / "ratings" / "sheet_a.csv"
    sheet_b = tmp_path / "ratings" / "sheet_b.csv"
    fieldnames = list(rows[0].keys())

    with sheet_a.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    with sheet_b.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    # 2. rate-score CLI
    out_scores = tmp_path / "ratings_scored"
    ret_score = main(["rate-score", "--sheet-a", str(sheet_a), "--sheet-b", str(sheet_b), "--key-file", str(key_out), "--output-dir", str(out_scores)])
    assert ret_score == 0
    assert (out_scores / "rating_scores.json").exists()
