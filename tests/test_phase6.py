"""Comprehensive Unit and Regression Tests for CheckSense Phase 6.

Covers:
- LLMClient protocol, Ollama configuration, and unreachable daemon handling
- MockLLMClient response injection and call history
- Generation output JSON parsing, markdown fence stripping, and error handling
- Clarification question constraints (single '?', <=30 words, non-empty)
- Deterministic per-subtype templates coverage and validity
- High-level candidate explanation and question enrichment
- Graceful offline / unavailable LLM behavior (guaranteed template fallback)
- StakeholderAnswer dataclass and validation
- Strict numeric preservation validation (rejects dropped or invented numbers)
- Normative modal verb check (shall / must / should / will)
- Rule-based requirement refinement fallback across defect types
- LLM requirement refinement with automatic fallback on validation failure
"""

from __future__ import annotations

import pytest

from checksense import (
    CandidateGap,
    LLMUnavailableError,
    MockLLMClient,
    OllamaClient,
    StakeholderAnswer,
    enrich_candidates_with_questions,
    extract_numbers,
    generate_gap_explanation_and_question,
    get_template_explanation_and_question,
    refine_requirement,
    rule_based_refinement_edit,
    validate_generation_output,
    validate_numeric_preservation,
)
from checksense.annotation import ALL_SUBTYPES

# ============================================================================
# 1. LLMClient Protocol & Mock Adapter Tests
# ============================================================================

def test_ollama_client_defaults_and_unreachable():
    """OllamaClient initializes with spec defaults and handles unreachable host."""
    client = OllamaClient(host="http://127.0.0.1:65432", model="qwen2.5:7b", ping_timeout=0.1)
    assert client.model == "qwen2.5:7b"
    assert client.host == "http://127.0.0.1:65432"
    # Unreachable host must return False without crashing
    assert not client.is_available()

    # Generating on unavailable client raises LLMUnavailableError
    with pytest.raises(LLMUnavailableError):
        client.generate("Test prompt")


def test_mock_llm_client_responses():
    """MockLLMClient yields programmed responses and records call history."""
    mock = MockLLMClient(
        responses={"ambiguity": '{"explanation": "Expl", "question": "What is x?"}'},
        available=True,
    )
    assert mock.is_available()

    resp = mock.generate("Analyze this ambiguity defect")
    assert "What is x?" in resp
    assert len(mock.call_history) == 1
    assert mock.call_history[0]["prompt"] == "Analyze this ambiguity defect"


# ============================================================================
# 2. Output Validation & Question Constraint Tests
# ============================================================================

def test_validate_generation_output_clean_json():
    """Valid JSON with compliant question passes validation."""
    raw = '{"explanation": "The term is vague.", "question": "What is the expected latency threshold in milliseconds?"}'
    is_valid, expl, q, errors = validate_generation_output(raw)
    assert is_valid
    assert expl == "The term is vague."
    assert q == "What is the expected latency threshold in milliseconds?"
    assert not errors


def test_validate_generation_output_markdown_fence():
    """JSON enclosed within markdown code blocks is cleanly parsed."""
    raw = """```json
    {
      "explanation": "No actor is specified for this operation.",
      "question": "Which system component executes this transaction?"
    }
    ```"""
    is_valid, expl, q, errors = validate_generation_output(raw)
    assert is_valid
    assert "No actor" in expl
    assert q.endswith("?")
    assert not errors


def test_validate_generation_output_malformed_json():
    """Malformed or invalid JSON is rejected with descriptive error."""
    raw = "I think the requirement is vague because it uses several."
    is_valid, _, _, errors = validate_generation_output(raw)
    assert not is_valid
    assert any("JSON" in e for e in errors)


def test_validate_generation_output_missing_keys():
    """JSON missing 'question' or 'explanation' is rejected."""
    raw = '{"explanation": "Missing actor."}'
    is_valid, _, _, errors = validate_generation_output(raw)
    assert not is_valid
    assert any("Missing required keys" in e for e in errors)


def test_validate_question_constraints_multiple_question_marks():
    """Question containing more than one question mark is rejected."""
    raw = '{"explanation": "Ambiguous.", "question": "What is the latency? Is it 50ms?"}'
    is_valid, _, _, errors = validate_generation_output(raw)
    assert not is_valid
    assert any("exactly one question mark" in e for e in errors)


def test_validate_question_constraints_no_question_mark():
    """Question missing trailing question mark is rejected."""
    raw = '{"explanation": "Ambiguous.", "question": "State the maximum acceptable latency"}'
    is_valid, _, _, errors = validate_generation_output(raw)
    assert not is_valid
    assert any("must end with a question mark" in e for e in errors)


def test_validate_question_constraints_word_limit():
    """Question exceeding 30 words is rejected."""
    long_q = "Can you please clarify in exhaustive detail exactly what the specific system actor, component, or external subsystem responsible for processing these database records should do when high network latency occurs under peak load conditions?"
    raw = f'{{"explanation": "Too long.", "question": "{long_q}"}}'
    is_valid, _, _, errors = validate_generation_output(raw)
    assert not is_valid
    assert any("exceeds 30 words" in e for e in errors)


# ============================================================================
# 3. Deterministic Per-Subtype Templates Tests
# ============================================================================

def test_all_taxonomy_subtypes_have_valid_templates():
    """Every subtype in the taxonomy has a valid template satisfying question rules."""
    for subtype in ALL_SUBTYPES:
        expl, q = get_template_explanation_and_question(
            gap_type="ambiguity",
            subtype=subtype,
            span_text="sample_span",
        )
        assert len(expl) > 0, f"Empty explanation for subtype '{subtype}'"
        assert q.endswith("?"), f"Template question for '{subtype}' must end in '?'"
        assert q.count("?") == 1, f"Template question for '{subtype}' must have exactly 1 '?'"
        assert len(q.split()) <= 30, f"Template question for '{subtype}' exceeds 30 words"


# ============================================================================
# 4. Candidate Generation Engine & Offline Fallback Tests
# ============================================================================

def test_generate_with_mock_llm_success():
    """When LLM returns valid output, high-level engine returns 'llm' method."""
    mock = MockLLMClient(
        responses='{"explanation": "Vague term used.", "question": "What threshold defines acceptable performance?"}'
    )
    cand = CandidateGap(
        gap_type="ambiguity",
        subtype="vague_term",
        span_text="acceptable",
        start_char=10,
        end_char=20,
        severity=2,
        probability=0.85,
        explanation="",
        question="",
    )
    expl, q, method = generate_gap_explanation_and_question(
        candidate=cand,
        req_text="The system shall provide acceptable performance.",
        llm_client=mock,
    )
    assert method == "llm"
    assert expl == "Vague term used."
    assert q == "What threshold defines acceptable performance?"


def test_generate_with_mock_llm_invalid_triggers_fallback():
    """When LLM produces invalid output, engine falls back to deterministic template."""
    # LLM produces multiple question marks and >30 words
    bad_output = '{"explanation": "Bad.", "question": "What? Why? Who?"}'
    mock = MockLLMClient(responses=bad_output)
    cand = CandidateGap(
        gap_type="ambiguity",
        subtype="vague_term",
        span_text="fast",
        start_char=5,
        end_char=9,
        severity=2,
        probability=0.8,
        explanation="",
        question="",
    )
    expl, q, method = generate_gap_explanation_and_question(
        candidate=cand,
        req_text="The engine shall be fast.",
        llm_client=mock,
    )
    assert method == "template_fallback"
    assert q.endswith("?")
    assert q.count("?") == 1


def test_generate_without_llm_offline_guarantee():
    """When no LLM is provided or LLM is offline, engine generates template cleanly."""
    cand = CandidateGap(
        gap_type="incompleteness",
        subtype="missing_condition",
        span_text="",
        start_char=None,
        end_char=None,
        severity=3,
        probability=0.9,
        explanation="",
        question="",
    )
    expl, q, method = generate_gap_explanation_and_question(
        candidate=cand,
        req_text="The system shall shut down the reactor.",
        llm_client=None,
    )
    assert method == "template_fallback"
    assert "condition" in expl.lower() or "event" in expl.lower()
    assert q.endswith("?")


def test_enrich_candidates_with_questions():
    """Batch enrichment updates candidate objects with validated explanations and questions."""
    cands = [
        CandidateGap(
            gap_type="ambiguity",
            subtype="vague_quantifier",
            span_text="several",
            start_char=10,
            end_char=17,
            severity=2,
            probability=0.8,
            explanation="",
            question="",
        )
    ]
    enriched = enrich_candidates_with_questions(
        candidates=cands,
        req_text="The system shall process several records.",
        llm_client=None,
    )
    assert len(enriched) == 1
    assert enriched[0].explanation != ""
    assert enriched[0].question.endswith("?")


# ============================================================================
# 5. Numeric Preservation Guardrail Tests
# ============================================================================

def test_extract_numbers():
    """Extracts and normalizes integers and decimals."""
    nums = extract_numbers("The 10 sensors must report within 2.5 seconds or 05 retries.")
    assert "10" in nums
    assert "2.5" in nums
    assert "5" in nums


def test_validate_numeric_preservation_valid():
    """Preserving original numbers and adding answer numbers is valid."""
    orig = "The system shall process 50 transactions within 200 milliseconds."
    ans = "at least 5 concurrent threads"
    refined = "The system shall process 50 transactions across 5 concurrent threads within 200 milliseconds."

    valid, err = validate_numeric_preservation(orig, ans, refined)
    assert valid
    assert err == ""


def test_validate_numeric_preservation_dropped_number():
    """Dropping an original number fails numeric preservation."""
    orig = "The system shall process 50 transactions within 200 milliseconds."
    ans = "fast"
    refined = "The system shall process transactions within 200 milliseconds."  # 50 dropped

    valid, err = validate_numeric_preservation(orig, ans, refined)
    assert not valid
    assert "dropped" in err.lower()
    assert "50" in err


def test_validate_numeric_preservation_invented_number():
    """Introducing an unstated number fails numeric preservation."""
    orig = "The system shall process 50 transactions."
    ans = "immediately"
    refined = "The system shall process 50 transactions within 99 seconds."  # 99 invented

    valid, err = validate_numeric_preservation(orig, ans, refined)
    assert not valid
    assert "invented" in err.lower()
    assert "99" in err


# ============================================================================
# 6. Requirement Refinement Engine Tests
# ============================================================================

def test_rule_based_refinement_span_replacement():
    """Rule fallback replaces ambiguous span directly with answer."""
    orig = "The system shall provide appropriate response time."
    refined = rule_based_refinement_edit(
        original_text=orig,
        answer="a response time under 500 ms",
        gap_type="ambiguity",
        subtype="vague_term",
        span_text="appropriate response time",
    )
    assert "appropriate response time" not in refined
    assert "a response time under 500 ms" in refined


def test_rule_based_refinement_missing_condition():
    """Rule fallback appends conditional clause for missing condition."""
    orig = "The system shall delete the database records."
    refined = rule_based_refinement_edit(
        original_text=orig,
        answer="the user confirms via two-factor authentication",
        gap_type="incompleteness",
        subtype="missing_condition",
        span_text="",
    )
    assert "provided that" in refined.lower()
    assert "two-factor authentication" in refined


def test_rule_based_refinement_missing_error_handling():
    """Rule fallback appends failure recovery clause."""
    orig = "The system shall transmit payment data to the gateway."
    refined = rule_based_refinement_edit(
        original_text=orig,
        answer="the transaction is rolled back and an audit alert is logged",
        gap_type="incompleteness",
        subtype="missing_error_handling",
        span_text="",
    )
    assert "In case of failure" in refined
    assert "rolled back" in refined


def test_refine_requirement_with_mock_llm_valid():
    """LLM refinement succeeds when output satisfies numeric and modal guardrails."""
    mock = MockLLMClient(
        responses="The system shall process 50 transactions within 200 ms."
    )
    ans = StakeholderAnswer(
        req_id="REQ_1",
        gap_type="ambiguity",
        subtype="vague_term",
        span_text="quickly",
        question="What threshold defines quickly?",
        answer="within 200 ms",
    )
    refined, method = refine_requirement(
        original_text="The system shall process 50 transactions quickly.",
        stakeholder_answer=ans,
        llm_client=mock,
    )
    assert method == "llm"
    assert refined == "The system shall process 50 transactions within 200 ms."


def test_refine_requirement_llm_dropping_number_triggers_fallback():
    """When LLM drops an original number, refinement falls back to rule edit."""
    # LLM drops '50'
    bad_llm = MockLLMClient(responses="The system shall process transactions within 200 ms.")
    ans = StakeholderAnswer(
        req_id="REQ_1",
        gap_type="ambiguity",
        subtype="vague_term",
        span_text="quickly",
        question="What threshold defines quickly?",
        answer="within 200 ms",
    )
    refined, method = refine_requirement(
        original_text="The system shall process 50 transactions quickly.",
        stakeholder_answer=ans,
        llm_client=bad_llm,
    )
    assert method == "rule_fallback"
    # Fallback must preserve 50
    assert "50" in refined
    assert "within 200 ms" in refined


def test_refine_requirement_offline_guarantee():
    """Refinement executes rule fallback cleanly when no LLM is present."""
    ans = StakeholderAnswer(
        req_id="REQ_2",
        gap_type="incompleteness",
        subtype="missing_actor",
        span_text="",
        question="Who executes this action?",
        answer="Security Administrator",
    )
    refined, method = refine_requirement(
        original_text="The system shall authenticate user credentials.",
        stakeholder_answer=ans,
        llm_client=None,
    )
    assert method == "rule_fallback"
    assert "Security Administrator" in refined
    assert "shall" in refined
