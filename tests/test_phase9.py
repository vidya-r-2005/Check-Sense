"""Unit and regression tests for CheckSense Phase 9.

Tests:
- Streamlit application module import and sample configuration
- Graceful handling of missing model artifacts (heuristic fallback)
- End-to-end integration workflow (Frame -> Multi-Head -> Fusion -> Question -> Refine -> ISO 29148)
- Offline LLM operation without Ollama (deterministic templates & rule edit)
- Invalid and edge-case input handling
- CLI parser consistency and subcommand registration
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

from checksense import (
    CandidateGap,
    HeuristicFusionScorer,
    Phase4Pipeline,
    StakeholderAnswer,
    deduplicate_and_rank_candidates,
    evaluate_iso_29148,
    extract_requirement_frame,
    get_template_explanation_and_question,
    refine_requirement,
    validate_numeric_preservation,
)
from checksense.cli import create_parser, main

# Ensure repo root is in sys.path for app module imports
REPO_ROOT = str(Path(__file__).resolve().parents[1])
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# ============================================================================
# 1. Streamlit Application Module & Sample Validation
# ============================================================================

def test_streamlit_app_import_and_samples():
    """Verify app/streamlit_app.py imports cleanly and samples are valid."""
    app_mod = importlib.import_module("app.streamlit_app")
    assert hasattr(app_mod, "main")
    assert hasattr(app_mod, "SAMPLE_REQUIREMENTS")
    assert len(app_mod.SAMPLE_REQUIREMENTS) >= 4

    for name, text in app_mod.SAMPLE_REQUIREMENTS:
        assert isinstance(name, str) and len(name) > 0
        assert isinstance(text, str) and len(text.split()) >= 3


def test_streamlit_app_highlight_spans():
    """Verify HTML span highlighting logic."""
    app_mod = importlib.import_module("app.streamlit_app")
    highlight_fn = app_mod.highlight_spans

    text = "The system shall process records quickly."
    gaps = [
        CandidateGap(
            gap_type="ambiguity",
            subtype="vague_term",
            span_text="quickly",
            start_char=33,
            end_char=40,
            severity=2,
            probability=0.9,
            explanation="Vague term",
            question="How quickly?",
        )
    ]

    html_out = highlight_fn(text, gaps)
    assert '<span style="' in html_out
    assert "quickly</span>" in html_out


# ============================================================================
# 2. Missing Artifacts & Graceful Fallback
# ============================================================================

def test_missing_model_artifacts_graceful_fallback(tmp_path: Path):
    """Pipeline operates reliably using heuristic fallbacks when models are absent."""
    non_existent_smell = tmp_path / "missing_smell.joblib"
    non_existent_span = tmp_path / "missing_span.joblib"

    pipeline = Phase4Pipeline(
        smell_model_path=non_existent_smell,
        span_model_path=non_existent_span,
    )
    assert pipeline.smell_model is None
    assert pipeline.span_tagger is None

    # Should run rule heuristics without crashing
    text = "The system shall process data quickly upon user login."
    candidates = pipeline.detect_all_gaps(text)
    assert len(candidates) >= 1

    # Heuristic fusion scorer
    scorer = HeuristicFusionScorer()
    fused = deduplicate_and_rank_candidates(
        candidates=candidates,
        scorer=scorer,
        req_text=text,
    )
    assert len(fused) >= 1
    assert fused[0].probability >= 0.0


# ============================================================================
# 3. End-to-End Pipeline Integration Workflow
# ============================================================================

def test_end_to_end_user_workflow_integration():
    """Verify full workflow: Frame -> Heads -> Fusion -> Question -> Refinement -> ISO 29148."""
    req_text = "The telemetry engine shall transmit diagnostic reports quickly."

    # 1. Frame extraction
    frame = extract_requirement_frame(req_text)
    assert frame.modal == "shall"

    # 2. Detection & fusion
    pipeline = Phase4Pipeline()
    candidates = pipeline.detect_all_gaps(req_text, frame=frame)
    scorer = HeuristicFusionScorer()
    fused = deduplicate_and_rank_candidates(candidates=candidates, scorer=scorer, req_text=req_text, frame=frame)

    assert len(fused) >= 1
    # Locate the gap corresponding to the vague term 'quickly'
    vague_gap = next((g for g in fused if g.span_text == "quickly"), fused[0])

    # 3. Offline question generation
    expl, q = get_template_explanation_and_question(vague_gap.gap_type, vague_gap.subtype, vague_gap.span_text)
    assert q.endswith("?")
    assert q.count("?") == 1
    assert len(q.split()) <= 30

    # 4. Refinement with stakeholder answer
    st_answer = StakeholderAnswer(
        req_id="TEST_001",
        gap_type=vague_gap.gap_type,
        subtype=vague_gap.subtype,
        span_text=vague_gap.span_text,
        question=q,
        answer="within 100 milliseconds",
    )

    refined, method = refine_requirement(req_text, st_answer, llm_client=None)
    assert "within 100 milliseconds" in refined
    if vague_gap.span_text == "quickly":
        assert "quickly" not in refined

    # 5. Strict numeric preservation check
    is_valid, _ = validate_numeric_preservation(req_text, st_answer.answer, refined)
    assert is_valid is True

    # 6. ISO 29148 before vs after
    iso_before = evaluate_iso_29148(req_text, detected_gaps=fused)
    iso_after = evaluate_iso_29148(refined)
    assert iso_after.score() >= iso_before.score()


# ============================================================================
# 4. Edge Cases & Robustness
# ============================================================================

def test_invalid_input_handling():
    """Test pipeline response to empty strings or non-normative input."""
    pipeline = Phase4Pipeline()
    scorer = HeuristicFusionScorer()

    # Empty string
    candidates_empty = pipeline.detect_all_gaps("")
    fused_empty = deduplicate_and_rank_candidates(candidates_empty, scorer, "")
    assert fused_empty == []

    # Whitespace only
    candidates_ws = pipeline.detect_all_gaps("   \t\n  ")
    fused_ws = deduplicate_and_rank_candidates(candidates_ws, scorer, "   \t\n  ")
    assert fused_ws == []


def test_numeric_preservation_rejection():
    """Validate that unauthorized number tampering is strictly caught and rejected."""
    orig = "The sensor shall report 5 values every 10 seconds."
    ans = "using port 8080"

    # Dropped original number 5
    tampered_dropped = "The sensor shall report values every 10 seconds using port 8080."
    is_valid, reason_dropped = validate_numeric_preservation(orig, ans, tampered_dropped)
    assert is_valid is False
    assert "5" in reason_dropped

    # Invented unauthorized number 999
    tampered_invented = "The sensor shall report 5 values every 10 seconds using port 8080 at 999 baud."
    is_valid_inv, reason_inv = validate_numeric_preservation(orig, ans, tampered_invented)
    assert is_valid_inv is False
    assert "999" in reason_inv


# ============================================================================
# 5. CLI Subcommand Registration & Consistency
# ============================================================================

def test_cli_subcommands_consistency():
    """Verify all 12 CLI subcommands defined in specification are registered."""
    parser = create_parser()
    expected_cmds = [
        "download",
        "build-corpus",
        "sample",
        "annotate-stats",
        "train-smell",
        "train-span",
        "train-fusion",
        "eval",
        "rate-make",
        "rate-score",
        "report",
        "serve",
    ]

    import argparse
    sub_action = next((a for a in parser._actions if isinstance(a, argparse._SubParsersAction)), None)
    assert sub_action is not None
    registered_cmds = list(sub_action.choices.keys())

    for cmd in expected_cmds:
        assert cmd in registered_cmds


def test_cli_serve_dry_run():
    """Verify serve subcommand execution in test environment."""
    ret_main = main(["serve", "--app", "main"])
    assert ret_main == 0

    ret_annotate = main(["serve", "--app", "annotate"])
    assert ret_annotate == 0
