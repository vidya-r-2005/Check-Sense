"""Unit tests for Phase 2: Frame Extraction, Rule Baseline (B1), and Evaluation Gating."""

from __future__ import annotations

from pathlib import Path

import pytest

from checksense.baseline import detect_rule_gaps
from checksense.cli import main as cli_main
from checksense.eval import UnverifiedEvaluationError, load_and_verify_gold_data, run_evaluation
from checksense.frame import extract_requirement_frame
from checksense.metrics import (
    compute_brier_score,
    compute_ece,
    compute_ndcg_at_k,
    compute_pr_auc,
    compute_spearman_rho,
    compute_token_jaccard,
    is_span_match,
    match_requirement_gaps,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ============================================================================
# 1. Requirement Frame Extractor Tests
# ============================================================================

def test_frame_extractor_active_voice() -> None:
    text = "The system shall display the report within 5 seconds when the user logs in, unless network is unavailable."
    frame = extract_requirement_frame(text)

    assert frame.actor == "The system"
    assert frame.modal == "shall"
    assert frame.action == "display"
    assert frame.object == "the report"
    assert frame.quantity == "5 seconds"
    assert frame.condition == "when the user logs in"
    assert frame.exception == "unless network is unavailable"
    assert not frame.is_passive
    assert frame.missing_slots == []


def test_frame_extractor_passive_with_agent() -> None:
    text = "The configuration file shall be updated by the administrator."
    frame = extract_requirement_frame(text)

    assert frame.is_passive
    assert frame.actor == "the administrator"
    assert frame.object == "The configuration file"
    assert frame.modal == "shall"
    assert frame.action == "updated"


def test_frame_extractor_passive_missing_actor() -> None:
    text = "The password shall be encrypted."
    frame = extract_requirement_frame(text)

    assert frame.is_passive
    assert frame.actor is None
    assert "actor" in frame.missing_slots
    assert frame.object == "The password"


def test_frame_extractor_leading_condition() -> None:
    text = "If the temperature exceeds 100 degrees, the valve shall open."
    frame = extract_requirement_frame(text)

    assert frame.condition == "If the temperature exceeds 100 degrees"
    assert frame.actor == "the valve"
    assert frame.action == "open"


# ============================================================================
# 2. Rule-Based Baseline Detector (B1) Tests
# ============================================================================

def test_detect_vague_terms() -> None:
    text = "The search feature shall return results fast and be user-friendly."
    gaps = detect_rule_gaps(text)

    subtypes = [g.subtype for g in gaps]
    assert "vague_term" in subtypes
    vague_spans = [g.span_text.lower() for g in gaps if g.subtype == "vague_term"]
    assert "fast" in vague_spans
    assert "user-friendly" in vague_spans

    for g in gaps:
        assert g.gap_type == "ambiguity"
        assert g.severity in {1, 2, 3}
        assert g.question.endswith("?")


def test_detect_vague_quantifiers_and_anaphora() -> None:
    text = "The server shall process several requests and archive them etc."
    gaps = detect_rule_gaps(text)

    subtypes = [g.subtype for g in gaps]
    assert "vague_quantifier" in subtypes
    assert "anaphora" in subtypes


def test_detect_coordination_and_loopholes() -> None:
    text = "The administrator shall grant access and/or assign roles if applicable."
    gaps = detect_rule_gaps(text)

    subtypes = [g.subtype for g in gaps]
    assert "coordination" in subtypes
    assert "missing_condition" in subtypes


def test_detect_missing_error_handling() -> None:
    text = "The system shall delete all user accounts."
    gaps = detect_rule_gaps(text)

    subtypes = [g.subtype for g in gaps]
    assert "missing_error_handling" in subtypes
    err_gap = next(g for g in gaps if g.subtype == "missing_error_handling")
    assert err_gap.severity == 3


def test_detect_implicit_constraints() -> None:
    text = "The client shall transmit the user password to the authentication server."
    gaps = detect_rule_gaps(text)

    implicit_gaps = [g for g in gaps if g.gap_type == "implicit"]
    assert len(implicit_gaps) >= 1
    assert implicit_gaps[0].subtype == "unstated_constraint"
    assert implicit_gaps[0].severity == 3


# ============================================================================
# 3. Matching Protocol Tests
# ============================================================================

def test_token_jaccard_and_containment() -> None:
    # Containment
    assert is_span_match("quickly", "quickly process")
    assert is_span_match("within 5 seconds", "5 seconds")

    # High overlap (Jaccard >= 0.5)
    assert compute_token_jaccard("user access control", "access control policy") == 2 / 4  # 0.5
    assert is_span_match("user access control", "access control policy")

    # Disjoint
    assert not is_span_match("immediately", "later today")


def test_match_requirement_gaps() -> None:
    preds = [
        {"gap_type": "ambiguity", "span_text": "quickly"},
        {"gap_type": "incompleteness", "span_text": "missing agent"},
    ]
    golds = [
        {"has_gap": 1, "gap_type": "ambiguity", "span_text": "quickly"},
        {"has_gap": 1, "gap_type": "implicit", "span_text": "password"},
    ]

    matched, un_preds, un_golds = match_requirement_gaps(preds, golds)
    assert len(matched) == 1
    assert matched[0] == (0, 0)
    assert un_preds == [1]
    assert un_golds == [1]


# ============================================================================
# 4. Metrics Calculations Tests
# ============================================================================

def test_metrics_computations() -> None:
    # Spearman Rho
    y_pred = [1.0, 2.0, 3.0, 4.0]
    y_true = [1.0, 2.0, 3.0, 4.0]
    assert pytest.approx(compute_spearman_rho(y_pred, y_true), 0.01) == 1.0

    # NDCG@3
    assert pytest.approx(compute_ndcg_at_k(y_true, y_pred, k=3), 0.01) == 1.0

    # PR-AUC
    y_true_bin = [0, 1, 1, 0]
    y_scores = [0.1, 0.9, 0.8, 0.2]
    pr_auc = compute_pr_auc(y_true_bin, y_scores)
    assert 0.0 <= pr_auc <= 1.0

    # ECE & Brier
    ece = compute_ece([1, 0], [0.9, 0.1])
    assert 0.0 <= ece <= 1.0
    brier = compute_brier_score([1, 0], [0.9, 0.1])
    assert 0.0 <= brier <= 1.0


# ============================================================================
# 5. Strict Evaluation Gate Tests (Binding Enforcement)
# ============================================================================

def test_evaluation_strictly_refuses_unverified_labels() -> None:
    unverified_fixture = FIXTURES_DIR / "unverified_annotations.csv"
    assert unverified_fixture.exists()

    # Must raise UnverifiedEvaluationError
    with pytest.raises(UnverifiedEvaluationError) as exc_info:
        load_and_verify_gold_data(unverified_fixture)

    assert "Evaluation REJECTED" in str(exc_info.value)
    assert "label_status='draft'" in str(exc_info.value)
    assert "Rule 4" in str(exc_info.value)


def test_evaluation_strictly_refuses_in_runner() -> None:
    unverified_fixture = FIXTURES_DIR / "unverified_annotations.csv"

    with pytest.raises(UnverifiedEvaluationError):
        run_evaluation(gold_file=unverified_fixture)


def test_evaluation_accepts_verified_labels(tmp_path: Path) -> None:
    verified_fixture = FIXTURES_DIR / "verified_annotations.csv"
    assert verified_fixture.exists()

    report = run_evaluation(
        gold_file=verified_fixture,
        output_dir=tmp_path / "eval_out",
    )

    assert report.n_requirements == 4
    assert report.n_clean_requirements == 1
    assert 0.0 <= report.macro_f1 <= 1.0
    assert (tmp_path / "eval_out" / "eval_report.json").exists()
    assert (tmp_path / "eval_out" / "eval_summary.csv").exists()
    assert (tmp_path / "eval_out" / "config.json").exists()


# ============================================================================
# 6. CLI Eval Subcommand Tests
# ============================================================================

def test_cli_eval_refuses_unverified_fixture() -> None:
    unverified_fixture = FIXTURES_DIR / "unverified_annotations.csv"
    exit_code = cli_main(["eval", "--gold-file", str(unverified_fixture)])
    # Strict gate refusal returns exit code 2
    assert exit_code == 2


def test_cli_eval_succeeds_on_verified_fixture(tmp_path: Path) -> None:
    verified_fixture = FIXTURES_DIR / "verified_annotations.csv"
    out_dir = tmp_path / "cli_eval_results"

    exit_code = cli_main([
        "eval",
        "--gold-file", str(verified_fixture),
        "--output-dir", str(out_dir),
    ])

    assert exit_code == 0
    assert (out_dir / "eval_report.json").exists()
    assert (out_dir / "eval_summary.csv").exists()
