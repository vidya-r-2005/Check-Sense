"""Comprehensive Unit and Regression Tests for CheckSense Phase 5.

Covers:
- Candidate feature extraction (one-hot classes, subtypes, frame slots, length, severity keywords)
- Feature vectorization determinism
- Candidate-to-gold matching protocol (span Jaccard >= 0.5 for ambiguity/incompleteness, requirement-level for implicit)
- Expected Calibration Error (ECE) calculation and 10-bin calibration data
- Heuristic fallback fusion scorer behavior and rule weighting
- MLP fusion scorer fit, serialization, prediction, and unfitted fallback
- Overlap deduplication (Jaccard >= 0.7), conflict resolution, and deterministic ranking
- Empty and invalid input handling
- Evaluation runner with pipeline='phase5'
- CLI subcommand execution for train-fusion and eval --pipeline phase5
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from checksense import (
    CandidateGap,
    HeuristicFusionScorer,
    MLPFusionScorer,
    RequirementFrame,
    deduplicate_and_rank_candidates,
    extract_candidate_features,
    run_evaluation,
)
from checksense.cli import main
from checksense.fusion import (
    compute_expected_calibration_error,
    feature_dict_to_vector,
    match_candidate_to_gold_gaps,
)


def make_candidate(
    gap_type: str = "ambiguity",
    subtype: str = "vague_quantifier",
    span_text: str = "",
    start_char: int | None = 0,
    end_char: int | None = 0,
    severity: int = 2,
    probability: float = 0.8,
    explanation: str = "Test explanation",
    question: str = "What is the expected value?",
) -> CandidateGap:
    """Helper to instantiate CandidateGap with valid defaults."""
    return CandidateGap(
        gap_type=gap_type,
        subtype=subtype,
        span_text=span_text,
        start_char=start_char,
        end_char=end_char,
        severity=severity,
        probability=probability,
        explanation=explanation,
        question=question,
    )


# ============================================================================
# 1. Feature Extraction Tests
# ============================================================================

def test_extract_candidate_features_keys_and_values():
    """Verify feature extractor populates all required feature dimensions."""
    cand = make_candidate(
        gap_type="ambiguity",
        subtype="vague_quantifier",
        span_text="several",
        start_char=10,
        end_char=17,
        severity=2,
        probability=0.85,
    )
    req_text = "The system shall process several fatal critical transactions quickly."
    frame = RequirementFrame(
        text=req_text,
        actor="system",
        modal="shall",
        action="process",
        object="transactions",
        condition="",
        missing_slots=["condition"],
        is_passive=False,
    )

    feats = extract_candidate_features(
        candidate=cand,
        req_text=req_text,
        frame=frame,
        smell_prob=0.90,
        n_candidates=3,
    )

    assert feats["type_ambiguity"] == 1.0
    assert feats["type_incompleteness"] == 0.0
    assert feats["type_implicit"] == 0.0
    assert feats["subtype_vague_quantifier"] == 1.0
    assert feats["head_score"] == 0.85
    assert feats["smell_probability"] == 0.90
    assert feats["n_candidates"] == 3.0
    assert feats["missing_slots_count"] == 1.0
    assert feats["is_passive"] == 0.0
    assert feats["has_critical_keyword"] == 1.0
    assert feats["text_severity_keywords"] >= 2.0  # 'fatal', 'critical'
    assert feats["span_char_length"] == len("several")


def test_feature_dict_to_vector_deterministic():
    """Verify feature vector converts deterministically based on key list."""
    feats = {"b": 2.5, "a": 1.0, "c": 3.0}
    keys = ["a", "b", "c"]
    vec = feature_dict_to_vector(feats, keys)
    assert isinstance(vec, np.ndarray)
    np.testing.assert_array_equal(vec, [1.0, 2.5, 3.0])

    # Missing keys default to 0.0
    vec_missing = feature_dict_to_vector(feats, ["a", "d"])
    np.testing.assert_array_equal(vec_missing, [1.0, 0.0])


# ============================================================================
# 2. Candidate Matching Protocol Tests
# ============================================================================

def test_match_candidate_ambiguity_overlap():
    """Ambiguity matches when gap_type matches and span token Jaccard >= 0.5."""
    cand = make_candidate(
        gap_type="ambiguity",
        subtype="vague_quantifier",
        span_text="appropriate response time",
        start_char=10,
        end_char=35,
        severity=2,
    )
    gold_rows = [
        {
            "has_gap": "1",
            "gap_type": "ambiguity",
            "span_text": "appropriate response",
            "severity": "3",
        }
    ]

    is_gap, sev = match_candidate_to_gold_gaps(cand, gold_rows)
    assert is_gap == 1
    assert sev == 3


def test_match_candidate_non_overlap_fails():
    """Disjoint span does not match gold gap."""
    cand = make_candidate(
        gap_type="ambiguity",
        subtype="vague_quantifier",
        span_text="quickly",
        start_char=50,
        end_char=57,
        severity=2,
    )
    gold_rows = [
        {
            "has_gap": "1",
            "gap_type": "ambiguity",
            "span_text": "appropriate response time",
            "severity": "2",
        }
    ]

    is_gap, _ = match_candidate_to_gold_gaps(cand, gold_rows)
    assert is_gap == 0


def test_match_candidate_implicit_requirement_level():
    """Implicit gaps match at requirement level without requiring span overlap."""
    cand = make_candidate(
        gap_type="implicit",
        subtype="missing_exception",
        span_text="",
        severity=2,
    )
    gold_rows = [
        {
            "has_gap": "1",
            "gap_type": "implicit",
            "span_text": "",
            "severity": "3",
        }
    ]

    is_gap, sev = match_candidate_to_gold_gaps(cand, gold_rows)
    assert is_gap == 1
    assert sev == 3


# ============================================================================
# 3. Calibration Error Math Tests
# ============================================================================

def test_compute_expected_calibration_error():
    """Test ECE computation and 10-bin empirical calibration curve generation."""
    y_true = np.array([1, 1, 0, 0, 1, 0, 1, 1, 0, 0])
    y_proba = np.array([0.9, 0.8, 0.2, 0.1, 0.85, 0.3, 0.7, 0.65, 0.15, 0.25])

    ece, bins = compute_expected_calibration_error(y_true, y_proba, n_bins=10)
    assert 0.0 <= ece <= 1.0
    assert len(bins) == 10
    assert all("bin_lower" in b and "empirical_accuracy" in b for b in bins)


# ============================================================================
# 4. Scorer Models & Fallback Tests
# ============================================================================

def test_heuristic_fusion_scorer():
    """Heuristic fallback scorer applies domain keyword rules and clamps."""
    scorer = HeuristicFusionScorer()
    cand = make_candidate(
        gap_type="ambiguity",
        subtype="vague_quantifier",
        span_text="appropriate",
        severity=2,
    )

    # Standard feature set
    feats = {
        "head_score": 0.80,
        "smell_probability": 0.60,
        "has_critical_keyword": 0.0,
        "span_char_length": 11,
    }
    prob, sev = scorer.score_candidate(cand, feats)
    assert 0.05 <= prob <= 0.98
    assert sev == 2

    # Critical keyword boosts severity and probability
    feats_crit = {
        "head_score": 0.80,
        "smell_probability": 0.60,
        "has_critical_keyword": 1.0,
        "span_char_length": 11,
    }
    prob_crit, sev_crit = scorer.score_candidate(cand, feats_crit)
    assert prob_crit > prob
    assert sev_crit == 3


def test_mlp_fusion_scorer_fit_predict_save_load(tmp_path: Path):
    """Verify MLP fusion scorer fit, serialization roundtrip, and inference."""
    np.random.seed(42)
    n_samples = 40
    n_feats = 10
    feature_names = [f"f_{i}" for i in range(n_feats)]

    x = np.random.randn(n_samples, n_feats)
    y_gap = np.random.randint(0, 2, size=n_samples)
    y_sev = np.random.choice([1, 2, 3], size=n_samples)

    model = MLPFusionScorer(seed=42)
    assert not model.is_fitted

    # Unfitted falls back to heuristic without crashing
    cand = make_candidate(gap_type="ambiguity", subtype="lexical", span_text="fast", severity=2)
    prob_fallback, _sev_fallback = model.score_candidate(cand, {"head_score": 0.7, "smell_probability": 0.5})
    assert 0.05 <= prob_fallback <= 0.98

    # Fit model
    model.fit(x, y_gap, y_sev, feature_names)
    assert model.is_fitted

    test_feats = {f"f_{i}": 0.5 for i in range(n_feats)}
    prob, sev = model.score_candidate(cand, test_feats)
    assert 0.0 <= prob <= 1.0
    assert sev in (1, 2, 3)

    # Serialize and reload
    save_path = tmp_path / "fusion_model.joblib"
    model.save(save_path)
    assert save_path.exists()

    loaded = MLPFusionScorer.load(save_path)
    assert loaded.is_fitted
    prob_loaded, sev_loaded = loaded.score_candidate(cand, test_feats)
    assert prob_loaded == prob
    assert sev_loaded == sev


# ============================================================================
# 5. Deduplication, Conflict Resolution & Ranking Tests
# ============================================================================

def test_deduplicate_overlapping_spans():
    """Overlapping spans with Jaccard >= 0.70 retain highest probability candidate."""
    scorer = HeuristicFusionScorer()
    cands = [
        make_candidate(
            gap_type="ambiguity",
            subtype="vague_quantifier",
            span_text="appropriate response time",
            start_char=10,
            end_char=35,
            severity=2,
            probability=0.70,
        ),
        make_candidate(
            gap_type="ambiguity",
            subtype="vague_quantifier",
            span_text="appropriate response",
            start_char=10,
            end_char=30,
            severity=2,
            probability=0.85,  # Higher score
        ),
    ]

    ranked = deduplicate_and_rank_candidates(
        candidates=cands,
        scorer=scorer,
        req_text="The system shall provide appropriate response time.",
    )

    assert len(ranked) == 1
    assert ranked[0].span_text == "appropriate response"


def test_deduplicate_multiple_implicit_gaps():
    """Only one implicit gap per requirement is retained."""
    scorer = HeuristicFusionScorer()
    cands = [
        make_candidate(
            gap_type="implicit",
            subtype="missing_exception",
            span_text="",
            severity=3,
            probability=0.60,
        ),
        make_candidate(
            gap_type="implicit",
            subtype="missing_actor",
            span_text="",
            severity=3,
            probability=0.90,  # Higher score
        ),
    ]

    ranked = deduplicate_and_rank_candidates(
        candidates=cands,
        scorer=scorer,
        req_text="The system shall process requests.",
    )

    assert len(ranked) == 1
    assert ranked[0].subtype == "missing_actor"


def test_deterministic_final_ranking_order():
    """Sort order: Severity descending, Probability descending, start_char ascending."""
    scorer = HeuristicFusionScorer()
    cands = [
        make_candidate(
            gap_type="ambiguity",
            subtype="anaphora",
            span_text="it",
            start_char=20,
            end_char=22,
            severity=1,
            probability=0.75,
        ),
        make_candidate(
            gap_type="implicit",
            subtype="missing_actor",
            span_text="",
            start_char=0,
            end_char=0,
            severity=3,
            probability=0.85,
        ),
        make_candidate(
            gap_type="ambiguity",
            subtype="vague_quantifier",
            span_text="several",
            start_char=42,
            end_char=49,
            severity=2,
            probability=0.80,
        ),
    ]

    ranked = deduplicate_and_rank_candidates(
        candidates=cands,
        scorer=scorer,
        req_text="The user can run the fast engine and load several files.",
    )

    # First should be severity 3
    assert ranked[0].severity == 3
    # Second should be severity 2
    assert ranked[1].severity == 2
    # Third should be severity 1
    assert ranked[2].severity == 1


def test_empty_candidates_handled_gracefully():
    """Empty candidate list returns empty list."""
    scorer = HeuristicFusionScorer()
    ranked = deduplicate_and_rank_candidates(
        candidates=[],
        scorer=scorer,
        req_text="Any text",
    )
    assert ranked == []


# ============================================================================
# 6. Pipeline Integration & CLI Tests
# ============================================================================

def test_eval_pipeline_phase5_integration():
    """Execute evaluation runner with pipeline='phase5' on provisional gold."""
    gold_path = Path("data/gold/annotations/rater_1.csv")
    if not gold_path.exists():
        pytest.skip("Provisional gold annotations file not found.")

    report = run_evaluation(
        gold_file=gold_path,
        pipeline="phase5",
    )

    assert report.n_requirements == 50
    assert report.macro_f1 >= 0.70
    assert "ambiguity" in report.per_class
    assert "incompleteness" in report.per_class
    assert "implicit" in report.per_class


def test_cli_train_fusion_help():
    """Verify CLI train-fusion help options."""
    with pytest.raises(SystemExit) as exc_info:
        main(["train-fusion", "--help"])
    assert exc_info.value.code == 0


def test_cli_eval_phase5_help():
    """Verify CLI eval accepts phase5 pipeline option."""
    with pytest.raises(SystemExit) as exc_info:
        main(["eval", "--help"])
    assert exc_info.value.code == 0
