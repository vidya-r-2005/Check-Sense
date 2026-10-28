"""Explanation and clarification question generation for CheckSense.

Implements MASTER_SPEC.md Section 5.6:
- Local LLM prompt construction grounded strictly in requirement text and detected gap.
- JSON output parsing with strict format and constraint validation:
  1. Parseable JSON with 'explanation' and 'question'.
  2. Exactly one question mark '?' located at the end.
  3. At most 30 words in the question.
  4. Never invent facts, assume specifications, or propose answers.
- Deterministic per-subtype templates as fallback when LLM is unavailable or output is invalid.
"""

from __future__ import annotations

import json
import re
from typing import Any

from .annotation import validate_clarification_question
from .baseline import CandidateGap
from .llm import LLMClient

# ============================================================================
# Deterministic Per-Subtype Templates (Fallback Reference)
# ============================================================================

# Format: subtype -> (explanation_template, question_template)
# Placeholders: {span}, {text}
SUBTYPE_TEMPLATES: dict[str, tuple[str, str]] = {
    "vague_term": (
        "The term '{span}' is ambiguous and lacks quantifiable or measurable criteria.",
        "What specific measurable threshold or technical standard defines '{span}' in this context?",
    ),
    "vague_quantifier": (
        "The quantifier '{span}' is indefinite and creates scope ambiguity.",
        "What is the complete enumeration or exact numerical bound intended by '{span}'?",
    ),
    "anaphora": (
        "The pronoun '{span}' has an ambiguous or unstated antecedent.",
        "Which specific entity or component does '{span}' refer to in this requirement?",
    ),
    "coordination": (
        "The conjunction '{span}' introduces ambiguous logical coordination between clauses.",
        "Should both options be supported simultaneously, or is only one option selectable at a time?",
    ),
    "missing_actor": (
        "The requirement omits the specific system component, role, or user responsible for this action.",
        "Which specific component, role, or user is responsible for performing this action?",
    ),
    "missing_condition": (
        "The triggering event, precondition, or operating state for this behavior is unstated.",
        "Under what concrete system states or triggering events is this action mandatory versus omitted?",
    ),
    "missing_threshold": (
        "The required performance, latency, or capacity threshold is omitted.",
        "What is the maximum acceptable threshold and unit of measurement for '{span}'?",
    ),
    "missing_error_handling": (
        "The requirement does not specify rollback, recovery, or notification behavior if the operation fails.",
        "What error handling or rollback procedure occurs if the operation fails?",
    ),
    "unstated_constraint": (
        "An implicit domain, security, privacy, or safety constraint is unstated for this action.",
        "What specific security, privacy, or audit constraints govern this operation?",
    ),
}

DEFAULT_FALLBACK = (
    "The requirement contains an unstated or ambiguous defect that requires stakeholder clarification.",
    "What specific requirement or constraint clarifies this behavior?",
)


def get_template_explanation_and_question(
    gap_type: str,
    subtype: str,
    span_text: str = "",
) -> tuple[str, str]:
    """Retrieve deterministic explanation and question for a gap subtype."""
    clean_subtype = subtype.strip().lower()
    span = span_text.strip() or "the specified item"

    expl_tmpl, q_tmpl = SUBTYPE_TEMPLATES.get(clean_subtype, DEFAULT_FALLBACK)
    explanation = expl_tmpl.format(span=span)
    question = q_tmpl.format(span=span)

    # Sanity check against validation rules
    errs = validate_clarification_question(question)
    if errs:
        # Guarantee a valid question
        question = "What specific technical constraint clarifies this requirement?"

    return explanation, question


# ============================================================================
# LLM Prompt Construction
# ============================================================================

SYSTEM_PROMPT = """You are an expert requirements engineering assistant for software specifications.
Given a requirement sentence and an identified defect gap, formulate:
1. A concise, one-sentence explanation of why the gap exists.
2. Exactly one clarification question for the stakeholder to resolve the defect.

STRICT INSTRUCTIONS:
- You must output ONLY a valid JSON object with keys "explanation" and "question".
- Do NOT wrap in markdown formatting or write introductory text.
- The question MUST end with a single question mark '?' and contain NO other question marks.
- The question MUST NOT exceed 30 words.
- NEVER invent facts, assume specifications, or propose answers. Ground the question solely in the stated text.
"""


def build_generation_prompt(
    req_text: str,
    gap_type: str,
    subtype: str,
    span_text: str = "",
) -> str:
    """Build grounded prompt for the LLM."""
    span_desc = f"'{span_text}'" if span_text.strip() else "N/A (requirement-level defect)"
    return (
        f"Requirement Text: \"{req_text.strip()}\"\n"
        f"Defect Type: {gap_type}\n"
        f"Defect Subtype: {subtype}\n"
        f"Problematic Span: {span_desc}\n\n"
        "Generate the JSON object with \"explanation\" and \"question\":"
    )


# ============================================================================
# Output Validation Guardrails
# ============================================================================

def _clean_json_string(raw: str) -> str:
    """Extract clean JSON substring from model output."""
    raw = raw.strip()
    # Check for markdown code fences
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if fence_match:
        return fence_match.group(1).strip()

    # Search for outermost JSON braces
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        return raw[start : end + 1].strip()

    return raw


def validate_generation_output(
    raw_output: str,
) -> tuple[bool, str, str, list[str]]:
    """Validate JSON parseability and question constraints per MASTER_SPEC.md.

    Constraints enforced:
    1. Parseable JSON containing 'explanation' and 'question'.
    2. 'explanation' is a non-empty string.
    3. Exactly one question mark '?' at the end of 'question'.
    4. No extra question marks in 'question'.
    5. 'question' word count <= 30 words.

    Returns:
        (is_valid, explanation, question, errors)
    """
    errors: list[str] = []
    if not raw_output or not raw_output.strip():
        return False, "", "", ["Output is empty."]

    cleaned = _clean_json_string(raw_output)

    try:
        data: Any = json.loads(cleaned)
    except json.JSONDecodeError as e:
        return False, "", "", [f"JSON parse error: {e}"]

    if not isinstance(data, dict):
        return False, "", "", ["Parsed JSON is not an object/dictionary."]

    if "explanation" not in data or "question" not in data:
        return False, "", "", ["Missing required keys 'explanation' or 'question'."]

    explanation = str(data.get("explanation", "")).strip()
    question = str(data.get("question", "")).strip()

    if not explanation:
        errors.append("Explanation is empty.")

    # Validate clarification question against CheckSense integrity contract
    q_errors = validate_clarification_question(question)
    errors.extend(q_errors)

    if errors:
        return False, explanation, question, errors

    return True, explanation, question, []


# ============================================================================
# High-Level Generation Engine
# ============================================================================

def generate_gap_explanation_and_question(
    candidate: CandidateGap,
    req_text: str,
    llm_client: LLMClient | None = None,
) -> tuple[str, str, str]:
    """Generate validated explanation and clarification question for a candidate.

    Attempts local LLM generation first if client is available.
    Falls back deterministically to per-subtype templates if:
    - No LLM client provided
    - LLM client is unreachable / not running
    - Generation raises an exception
    - Output validation fails (malformed JSON, >30 words, !=1 question mark)

    Returns:
        (explanation, question, generation_method):
        - generation_method in {"llm", "template_fallback"}
    """
    if llm_client is not None and llm_client.is_available():
        prompt = build_generation_prompt(
            req_text=req_text,
            gap_type=candidate.gap_type,
            subtype=candidate.subtype,
            span_text=candidate.span_text or "",
        )
        try:
            raw_resp = llm_client.generate(
                prompt=prompt,
                system_prompt=SYSTEM_PROMPT,
                temperature=0.0,
            )
            is_valid, expl, q, _errors = validate_generation_output(raw_resp)
            if is_valid:
                return expl, q, "llm"
        except Exception:
            # Fall through to template fallback
            pass

    # Deterministic Template Fallback
    expl, q = get_template_explanation_and_question(
        gap_type=candidate.gap_type,
        subtype=candidate.subtype,
        span_text=candidate.span_text or "",
    )
    return expl, q, "template_fallback"


def enrich_candidates_with_questions(
    candidates: list[CandidateGap],
    req_text: str,
    llm_client: LLMClient | None = None,
) -> list[CandidateGap]:
    """Enrich candidate gaps with validated explanations and questions."""
    enriched: list[CandidateGap] = []
    for cand in candidates:
        expl, q, _method = generate_gap_explanation_and_question(
            candidate=cand,
            req_text=req_text,
            llm_client=llm_client,
        )
        enriched.append(
            CandidateGap(
                gap_type=cand.gap_type,
                subtype=cand.subtype,
                span_text=cand.span_text,
                start_char=cand.start_char,
                end_char=cand.end_char,
                severity=cand.severity,
                probability=cand.probability,
                explanation=expl,
                question=q,
            )
        )
    return enriched

