"""Comprehensive Unit and Regression Tests for CheckSense Phase 7.

Covers:
- Baseline B1: Rules-only detector reuse
- Baseline B2: Span tagger alone (direct BIO span to CandidateGap mapping)
- Baseline B3: Single zero-shot LLM with span grounding (ungrounded spans discarded)
- Baseline B4: Multi-LLM majority voting ensemble (consensus on >=2 models)
- Head removal ablations (no_4a, no_4b, no_4c)
- Plain union ablation (union of heads without Phase 5 candidate fusion)
- Question formulation strategy comparison (template vs. LLM)
- Prompting strategy comparison (generic vs. gap-conditioned)
- Offline and unavailable LLM handling across baselines
- Acceptance criteria: reproduction of results/summary.csv
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from checksense import (
    MockLLMClient,
    compare_prompting_strategies,
    compare_question_formulation_strategies,
    detect_ablation_no_4a,
    detect_ablation_no_4b,
    detect_ablation_no_4c,
    detect_ablation_plain_union,
    detect_b2_span_alone_gaps,
    detect_b3_zeroshot_llm_gaps,
    detect_b4_multi_llm_majority_gaps,
    detect_rule_gaps,
    run_comparative_benchmark,
)
from checksense.cli import main
from checksense.heads import Phase4Pipeline

# ============================================================================
# 1. Baseline B1 Tests (Rules-Only)
# ============================================================================

def test_b1_rules_baseline_execution():
    """Verify B1 rule baseline identifies lexicon and frame-slot gaps."""
    text = "The system shall process several transactions quickly."
    gaps = detect_rule_gaps(text)
    assert len(gaps) >= 1
    assert any(g.gap_type == "ambiguity" for g in gaps)
    assert any(g.span_text in ("several", "quickly") for g in gaps)


# ============================================================================
# 2. Baseline B2 Tests (Span Tagger Alone)
# ============================================================================

def test_b2_span_alone_mapping():
    """Verify B2 maps token BIO predictions directly to CandidateGap."""
    class DummySpanTagger:
        def predict_spans(self, text: str):
            return [
                {
                    "span_text": "appropriate",
                    "gap_type": "ambiguity",
                    "start_char": 24,
                    "end_char": 35,
                    "confidence": 0.88,
                }
            ]

    text = "The system shall provide appropriate latency."
    gaps = detect_b2_span_alone_gaps(text, span_tagger=DummySpanTagger())

    assert len(gaps) == 1
    cand = gaps[0]
    assert cand.gap_type == "ambiguity"
    assert cand.subtype == "vague_term"
    assert cand.span_text == "appropriate"
    assert cand.start_char == 24
    assert cand.end_char == 35
    assert cand.probability == 0.88
    assert cand.question.endswith("?")


def test_b2_span_alone_missing_model_returns_empty():
    """When span tagger model is missing or None, returns empty list without error."""
    gaps = detect_b2_span_alone_gaps("Any text", span_tagger=None, span_model_path=Path("nonexistent.joblib"))
    assert gaps == []


# ============================================================================
# 3. Baseline B3 Tests (Single Zero-Shot LLM & Span Grounding)
# ============================================================================

def test_b3_zeroshot_llm_span_grounding_retains_grounded():
    """Span grounding retains candidates whose spans exist verbatim in text."""
    req_text = "The system shall process several records quickly."
    llm_response = """[
        {"gap_type": "ambiguity", "subtype": "vague_quantifier", "span_text": "several", "severity": 2},
        {"gap_type": "ambiguity", "subtype": "vague_term", "span_text": "quickly", "severity": 2}
    ]"""
    mock = MockLLMClient(responses=llm_response)

    gaps = detect_b3_zeroshot_llm_gaps(req_text, llm_client=mock)
    assert len(gaps) == 2
    assert gaps[0].span_text == "several"
    assert gaps[0].start_char == 25
    assert gaps[1].span_text == "quickly"


def test_b3_zeroshot_llm_span_grounding_discards_hallucinated():
    """Ungrounded spans (hallucinated text not in requirement) are strictly discarded per Section 7."""
    req_text = "The system shall authenticate the user credentials."
    # LLM hallucinates "database server" which does not appear in req_text
    llm_response = """[
        {"gap_type": "ambiguity", "subtype": "vague_term", "span_text": "database server", "severity": 2},
        {"gap_type": "implicit", "subtype": "unstated_constraint", "span_text": "", "severity": 3}
    ]"""
    mock = MockLLMClient(responses=llm_response)

    gaps = detect_b3_zeroshot_llm_gaps(req_text, llm_client=mock)
    # The hallucinated span "database server" must be discarded! Only implicit remains.
    assert len(gaps) == 1
    assert gaps[0].gap_type == "implicit"


def test_b3_zeroshot_llm_offline_handling():
    """When LLM is offline or unreachable, B3 returns empty list without error."""
    mock = MockLLMClient(available=False)
    gaps = detect_b3_zeroshot_llm_gaps("Any text", llm_client=mock)
    assert gaps == []


# ============================================================================
# 4. Baseline B4 Tests (Multi-LLM Majority Vote)
# ============================================================================

def test_b4_multi_llm_majority_voting_consensus():
    """Candidates detected by >= 2 of 3 models are accepted by majority vote."""
    req_text = "The system shall process several transactions quickly."

    # Model 1 detects "several" and "quickly"
    m1 = MockLLMClient(responses='[{"gap_type": "ambiguity", "subtype": "vague_quantifier", "span_text": "several", "severity": 2}, {"gap_type": "ambiguity", "subtype": "vague_term", "span_text": "quickly", "severity": 2}]')
    # Model 2 detects "several" only
    m2 = MockLLMClient(responses='[{"gap_type": "ambiguity", "subtype": "vague_quantifier", "span_text": "several", "severity": 2}]')
    # Model 3 detects "several" only
    m3 = MockLLMClient(responses='[{"gap_type": "ambiguity", "subtype": "vague_quantifier", "span_text": "several", "severity": 2}]')

    clients = [("m1", m1), ("m2", m2), ("m3", m3)]
    consensus = detect_b4_multi_llm_majority_gaps(req_text, clients=clients)

    # "several" has 3 votes (>= 2) -> accepted!
    # "quickly" has only 1 vote (< 2) -> rejected!
    assert len(consensus) == 1
    assert consensus[0].span_text == "several"


def test_b4_multi_llm_lack_of_quorum():
    """When fewer than 2 models are available, B4 returns empty list without error."""
    m1 = MockLLMClient(available=True, responses="[]")
    m2 = MockLLMClient(available=False)
    m3 = MockLLMClient(available=False)

    clients = [("m1", m1), ("m2", m2), ("m3", m3)]
    consensus = detect_b4_multi_llm_majority_gaps("Any text", clients=clients)
    assert consensus == []


# ============================================================================
# 5. Ablation Studies Tests
# ============================================================================

def test_ablation_head_omissions():
    """Verify selective head omission ablations."""
    pipeline = Phase4Pipeline()
    text = "Upon login, the user password shall be deleted."

    # Ablation -Head 4a: zero ambiguity gaps emitted
    gaps_no_4a = detect_ablation_no_4a(text, pipeline)
    assert all(g.gap_type != "ambiguity" for g in gaps_no_4a)

    # Ablation -Head 4b: zero completeness gaps emitted
    gaps_no_4b = detect_ablation_no_4b(text, pipeline)
    assert all(g.gap_type != "incompleteness" for g in gaps_no_4b)

    # Ablation -Head 4c: zero implicit gaps emitted
    gaps_no_4c = detect_ablation_no_4c(text, pipeline)
    assert all(g.gap_type != "implicit" for g in gaps_no_4c)


def test_ablation_plain_union():
    """Plain union returns all emitted candidates without fusion scorer deduplication."""
    pipeline = Phase4Pipeline()
    text = "The system shall process several records quickly."
    gaps_union = detect_ablation_plain_union(text, pipeline)
    assert len(gaps_union) >= 1


# ============================================================================
# 6. Question Formulation & Prompting Comparisons
# ============================================================================

def test_compare_question_formulation_strategies():
    """Compare question formulation quality between template and LLM."""
    dummy_reqs = [
        {"gap_type": "ambiguity", "subtype": "vague_term", "span_text": "fast", "text": "Fast engine."},
        {"gap_type": "incompleteness", "subtype": "missing_actor", "span_text": "", "text": "Shall be processed."},
    ]
    res = compare_question_formulation_strategies(dummy_reqs, llm_client=None)
    tmpl_stats = res["template_strategy"]
    assert tmpl_stats["count"] == 2
    assert tmpl_stats["compliant_rate"] == 1.0
    assert tmpl_stats["mean_words"] > 5.0


def test_compare_prompting_strategies():
    """Compare generic vs gap-conditioned prompting."""
    res = compare_prompting_strategies(
        requirement_text="The system shall process records quickly.",
        gap_type="ambiguity",
        subtype="vague_term",
        span_text="quickly",
        llm_client=None,
    )
    assert "conditioned_response" in res
    assert res["conditioned_response"].endswith("?")


# ============================================================================
# 7. One Command Reproduces results/summary.csv
# ============================================================================

def test_summary_csv_reproduction_benchmark(tmp_path: Path):
    """Verify run_comparative_benchmark reproduces summary CSV with all 10 systems."""
    gold_path = Path("data/gold/annotations/rater_1.csv")
    if not gold_path.exists():
        pytest.skip("Provisional gold annotations file not found.")

    output_csv = tmp_path / "summary.csv"
    records = run_comparative_benchmark(gold_file=gold_path, output_summary_file=output_csv)

    assert output_csv.exists()
    assert len(records) == 10

    system_names = [r["system"] for r in records]
    assert "B1_rules" in system_names
    assert "B2_span_alone" in system_names
    assert "B3_zeroshot_llm" in system_names
    assert "B4_multi_llm" in system_names
    assert "Phase4_multi_head" in system_names
    assert "Phase5_fusion" in system_names
    assert "Ablation_no_4a" in system_names
    assert "Ablation_no_4b" in system_names
    assert "Ablation_no_4c" in system_names
    assert "Ablation_plain_union" in system_names

    # Verify CSV file contents
    with output_csv.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        csv_rows = list(reader)
    assert len(csv_rows) == 10
    assert "macro_f1" in csv_rows[0]
    assert "micro_f1" in csv_rows[0]
    assert "status" in csv_rows[0]


def test_cli_report_subcommand_help():
    """Verify CLI report subcommand help options."""
    with pytest.raises(SystemExit) as exc_info:
        main(["report", "--help"])
    assert exc_info.value.code == 0
