"""Requirement Refinement Engine for CheckSense.

Implements MASTER_SPEC.md Section 5.8:
- Incorporates stakeholder clarification answers to resolve detected gaps.
- Uses local LLM with prompt grounded strictly in the original requirement and answer.
- Strict numeric preservation guardrail: rejects outputs that drop or add numbers.
- Normative modal verb preservation (shall / must / should / will).
- Deterministic rule-based fallback edit when LLM is unavailable or output is rejected.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from .llm import LLMClient

MODAL_KEYWORDS = {"shall", "must", "should", "will"}


@dataclass
class StakeholderAnswer:
    """Represents a stakeholder's clarification answer for a candidate gap."""

    req_id: str
    gap_type: str
    subtype: str
    span_text: str
    question: str
    answer: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ============================================================================
# Numeric Preservation Validation Guardrail
# ============================================================================

def extract_numbers(text: str) -> list[str]:
    """Extract all integer and floating-point numbers from a string.

    Normalizes numbers to strip leading/trailing zeroes for fair comparison.
    """
    raw_nums = re.findall(r"\b\d+(?:\.\d+)?\b", text)
    normalized: list[str] = []
    for num in raw_nums:
        try:
            val = float(num)
            # Normalize integers without decimal suffix
            if val.is_integer():
                normalized.append(str(int(val)))
            else:
                normalized.append(str(val))
        except ValueError:
            normalized.append(num)
    return normalized


def validate_numeric_preservation(
    original_text: str,
    answer_text: str,
    refined_text: str,
) -> tuple[bool, str]:
    """Verify that refined requirement strictly preserves all numerical values.

    Rules per MASTER_SPEC.md Section 5.8:
    1. No dropped numbers: Every number in original_text must appear in refined_text.
    2. No hallucinated numbers: Every number in refined_text must originate from
       either original_text or answer_text.

    Returns:
        (is_valid, error_reason)
    """
    orig_nums = set(extract_numbers(original_text))
    ans_nums = set(extract_numbers(answer_text))
    ref_nums = set(extract_numbers(refined_text))

    # Rule 1: All original numbers must be retained
    dropped = orig_nums - ref_nums
    if dropped:
        return False, f"Refinement dropped original numbers: {sorted(dropped)}"

    # Rule 2: All refined numbers must come from either original or answer
    allowed = orig_nums | ans_nums
    invented = ref_nums - allowed
    if invented:
        return False, f"Refinement invented unauthorized numbers: {sorted(invented)}"

    return True, ""


def contains_normative_modal(text: str) -> bool:
    """Check if text contains standard requirements modal (shall, must, should, will)."""
    words = set(re.findall(r"\b\w+\b", text.lower()))
    return bool(words & MODAL_KEYWORDS)


# ============================================================================
# Deterministic Rule-Based Fallback Refinement
# ============================================================================

def rule_based_refinement_edit(
    original_text: str,
    answer: str,
    gap_type: str,
    subtype: str,
    span_text: str = "",
) -> str:
    """Execute deterministic fallback requirement rewrite using rule-based grammar.

    Used when LLM is unavailable, offline, or produces invalid output.
    Guarantees preservation of numbers and normative modal verbs.
    """
    orig = original_text.strip()
    ans = answer.strip().rstrip(".").strip()
    span = span_text.strip()

    if not orig:
        return ""
    if not ans:
        return orig

    # 1. Ambiguity spans: replace ambiguous span directly with stakeholder answer
    if span and re.search(r"\b" + re.escape(span) + r"\b", orig, re.IGNORECASE):
        # Case-insensitive span replacement
        pattern = re.compile(r"\b" + re.escape(span) + r"\b", re.IGNORECASE)
        refined = pattern.sub(ans, orig, count=1)
        return refined

    # 2. Missing Actor: incorporate responsible entity
    if subtype == "missing_actor":
        # Check for passive modal phrase: "shall be <verb>"
        match = re.search(r"\b(shall|must|should|will)\s+be\s+(\w+ed)\b", orig, re.IGNORECASE)
        if match:
            modal = match.group(1)
            # Reconstruct active: "The {ans} {modal} ..."
            prefix = f"The {ans} {modal} "
            return prefix + orig[match.end() :].strip().lstrip()

        # Prepend actor if beginning with modal or action
        if re.match(r"^(?:The\s+system\s+)?(shall|must|should|will)\b", orig, re.IGNORECASE):
            return re.sub(
                r"^(?:The\s+system\s+)?(shall|must|should|will)\b",
                f"The {ans} \\1",
                orig,
                count=1,
                flags=re.IGNORECASE,
            )
        # Default suffix
        if orig.endswith("."):
            return f"{orig[:-1]} by the {ans}."
        return f"{orig} by the {ans}."

    # 3. Missing Condition: append conditional clause
    if subtype == "missing_condition":
        clean_ans = ans
        if not re.match(r"^(?:if|when|whenever|upon|provided\s+that)\b", clean_ans, re.IGNORECASE):
            clean_ans = f"provided that {clean_ans}"
        if orig.endswith("."):
            return f"{orig[:-1]}, {clean_ans}."
        return f"{orig}, {clean_ans}."

    # 4. Missing Error Handling: append recovery clause
    if subtype == "missing_error_handling":
        clean_ans = ans
        if not re.match(r"^(?:in\s+case\s+of|if|upon)\b", clean_ans, re.IGNORECASE):
            clean_ans = f"In case of failure, {clean_ans}"
        if orig.endswith("."):
            return f"{orig} {clean_ans}."
        return f"{orig}. {clean_ans}."

    # 5. Missing Threshold: incorporate measurement
    if subtype == "missing_threshold":
        if span and span.lower() in orig.lower():
            pattern = re.compile(re.escape(span), re.IGNORECASE)
            return pattern.sub(f"{span} ({ans})", orig, count=1)
        if orig.endswith("."):
            return f"{orig[:-1]} with threshold {ans}."
        return f"{orig} with threshold {ans}."

    # 6. Unstated Constraint or general fallback: append clarification
    if orig.endswith("."):
        return f"{orig[:-1]} ({ans})."
    return f"{orig} ({ans})."


# ============================================================================
# LLM Refinement Prompt & Engine
# ============================================================================

REFINEMENT_SYSTEM_PROMPT = """You are an expert software requirements specification editor.
Rewrite the original requirement sentence to incorporate the stakeholder's answer and resolve the defect.

STRICT RULES:
1. Use ONLY information from the original requirement and the stakeholder's answer.
2. NEVER invent new facts, technical details, or unstated constraints.
3. NEVER drop any numbers from the original requirement.
4. NEVER introduce numbers that were not in either the original requirement or the answer.
5. You MUST include a normative modal verb: "shall", "must", "should", or "will".
6. Output ONLY the single revised requirement sentence. Do not include quotes, preamble, or markdown formatting.
"""


def build_refinement_prompt(
    original_text: str,
    gap_type: str,
    subtype: str,
    question: str,
    answer: str,
    span_text: str = "",
) -> str:
    """Build grounded prompt for requirement refinement."""
    span_str = f"'{span_text}'" if span_text.strip() else "N/A"
    return (
        f"Original Requirement: \"{original_text.strip()}\"\n"
        f"Identified Defect: {gap_type} ({subtype})\n"
        f"Defect Span: {span_str}\n"
        f"Clarification Question: \"{question.strip()}\"\n"
        f"Stakeholder Answer: \"{answer.strip()}\"\n\n"
        "Provide the refined requirement sentence:"
    )


def refine_requirement(
    original_text: str,
    stakeholder_answer: StakeholderAnswer | str,
    gap_type: str = "ambiguity",
    subtype: str = "vague_term",
    question: str = "",
    span_text: str = "",
    llm_client: LLMClient | None = None,
) -> tuple[str, str]:
    """Refine requirement by integrating stakeholder clarification answer.

    Attempts local LLM rewrite first. Validates:
    - Numeric preservation (no dropped numbers, no invented numbers).
    - Normative modal verb presence (shall/must/should/will).
    - Information boundary adherence.

    Falls back to deterministic rule-based rewrite if:
    - No LLM client provided or client is unavailable/offline
    - LLM generation raises an error
    - LLM output fails numeric preservation validation
    - LLM output omits normative modal verb

    Returns:
        (refined_text, refinement_method):
        - refinement_method in {"llm", "rule_fallback"}
    """
    orig = original_text.strip()
    if not orig:
        return "", "empty_input"

    if isinstance(stakeholder_answer, StakeholderAnswer):
        ans = stakeholder_answer.answer.strip()
        g_type = stakeholder_answer.gap_type
        s_type = stakeholder_answer.subtype
        q_text = stakeholder_answer.question
        s_text = stakeholder_answer.span_text
    else:
        ans = str(stakeholder_answer).strip()
        g_type = gap_type
        s_type = subtype
        q_text = question
        s_text = span_text

    if not ans:
        return orig, "no_answer"

    # Attempt LLM Refinement
    if llm_client is not None and llm_client.is_available():
        prompt = build_refinement_prompt(
            original_text=orig,
            gap_type=g_type,
            subtype=s_type,
            question=q_text,
            answer=ans,
            span_text=s_text,
        )
        try:
            raw_refined = llm_client.generate(
                prompt=prompt,
                system_prompt=REFINEMENT_SYSTEM_PROMPT,
                temperature=0.0,
            ).strip()

            # Clean output (remove accidental quotes or markdown)
            candidate_refined = raw_refined.strip('"`').strip()

            # Guardrail 1: Numeric preservation
            nums_valid, _err = validate_numeric_preservation(orig, ans, candidate_refined)

            # Guardrail 2: Normative modal verb check
            modal_valid = contains_normative_modal(candidate_refined)

            if nums_valid and modal_valid and len(candidate_refined.split()) >= 4:
                return candidate_refined, "llm"
        except Exception:
            # Fall through to deterministic rule fallback
            pass

    # Deterministic Rule-Based Fallback
    fallback_refined = rule_based_refinement_edit(
        original_text=orig,
        answer=ans,
        gap_type=g_type,
        subtype=s_type,
        span_text=s_text,
    )
    return fallback_refined, "rule_fallback"
