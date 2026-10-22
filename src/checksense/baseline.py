"""Baseline Rule Detector (B1) for CheckSense.

Implements rule-based gap detection across the three taxonomy classes:
1. Ambiguity:
   - vague_term: vague adjectives, adverbs, non-verifiable terms
   - vague_quantifier: open-ended quantifiers, 'etc.', 'and so on'
   - anaphora: vague pronouns without clear referents
   - coordination: ambiguous 'and/or' coordination
2. Incompleteness:
   - missing_actor: passive sentences without agent or impersonal subjects
   - missing_condition: loophole phrases or missing triggers for state-altering actions
   - missing_threshold: qualitative bounds without numeric threshold
   - missing_error_handling: critical operations without failure handling
3. Implicit:
   - unstated_constraint: critical domain actions without security, privacy, or audit constraints

Severity (1-3) and deterministic clarification questions are assigned per MASTER_SPEC.md.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from .frame import RequirementFrame, extract_requirement_frame

# ============================================================================
# Lexicons for Ambiguity and Incompleteness
# ============================================================================

VAGUE_TERMS = {
    "fast",
    "quickly",
    "slow",
    "efficient",
    "efficiently",
    "user-friendly",
    "user friendly",
    "robust",
    "robustly",
    "appropriate",
    "appropriately",
    "adequate",
    "adequately",
    "sufficient",
    "sufficiently",
    "reasonable",
    "reasonably",
    "normal",
    "normally",
    "seamless",
    "seamlessly",
    "easy",
    "easily",
    "optimal",
    "optimally",
    "clean",
    "cleanly",
    "proper",
    "properly",
    "clear",
    "clearly",
    "secure",
    "securely",
    "high-performance",
    "high performance",
    "real-time",
    "real time",
    "as soon as possible",
    "state of the art",
    "flexible",
    "intuitive",
    "reliable",
    "convenient",
}

VAGUE_QUANTIFIERS = {
    "many",
    "few",
    "several",
    "some",
    "most",
    "various",
    "multiple",
    "numerous",
    "approximately",
    "nearly",
    "almost",
    "etc",
    "etc.",
    "and so on",
    "such as",
    "including but not limited to",
    "a lot of",
}

PRONOUNS_ANAPHORA = {
    "it",
    "they",
    "them",
    "their",
    "theirs",
    "this",
    "these",
    "those",
    "its",
}

LOOPHOLE_CONDITIONS = {
    "if applicable",
    "if necessary",
    "when possible",
    "where appropriate",
    "as appropriate",
    "as needed",
    "if desired",
    "where suitable",
    "as applicable",
}

THRESHOLD_VAGUE_ADJECTIVES = {
    "minimum delay",
    "low latency",
    "high throughput",
    "maximum speed",
    "sufficient bandwidth",
    "minimal impact",
    "high capacity",
}

CRITICAL_ACTIONS = {
    "delete",
    "erase",
    "wipe",
    "purge",
    "transfer",
    "authenticate",
    "authorize",
    "charge",
    "pay",
    "transmit",
    "encrypt",
    "decrypt",
    "export",
    "disconnect",
    "terminate",
    "shutdown",
}

IMPLICIT_DOMAIN_CONSTRAINTS = {
    "password": ("security", "How should passwords be encrypted, salted, or validated against complexity rules?"),
    "credit card": ("compliance", "What PCI-DSS encryption and masking standards apply to credit card data?"),
    "payment": ("financial audit", "What audit logging and transaction rollback mechanisms must be enforced for payments?"),
    "personal data": ("privacy", "What privacy regulations and retention constraints govern this personal data?"),
    "authenticate": ("session security", "What timeout, multi-factor, and lockout constraints apply to authentication?"),
    "delete": ("data retention", "Is this deletion soft or hard, and what confirmation or recovery period is required?"),
}


@dataclass
class CandidateGap:
    """Represents a single detected gap candidate in a requirement."""

    gap_type: str  # ambiguity | incompleteness | implicit
    subtype: str
    span_text: str
    start_char: int | None
    end_char: int | None
    severity: int  # 1 (minor), 2 (rework), 3 (critical)
    probability: float  # Heuristic confidence score in [0.0, 1.0]
    explanation: str
    question: str

    def to_dict(self) -> dict[str, Any]:
        """Convert gap to dictionary."""
        return asdict(self)


def _find_exact_phrase(text: str, phrase: str) -> tuple[int, int] | None:
    """Case-insensitive exact word-boundary phrase matcher."""
    pattern = r"\b" + re.escape(phrase) + r"\b"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.span()
    return None


def detect_rule_gaps(
    text: str,
    frame: RequirementFrame | None = None,
    doc_context: str | None = None,
) -> list[CandidateGap]:
    """Detect candidate requirement gaps using rule baseline B1.

    Args:
        text: The requirement text.
        frame: Optional pre-extracted RequirementFrame.
        doc_context: Optional SRS document context to satisfy Rule 0.

    Returns:
        List of CandidateGap objects, sorted by severity descending and probability descending.
    """
    if frame is None:
        frame = extract_requirement_frame(text)

    gaps: list[CandidateGap] = []
    text_lower = text.lower()

    # -------------------------------------------------------------------------
    # 1. Ambiguity Checks
    # -------------------------------------------------------------------------

    # 1a. Coordination: and/or
    and_or_span = _find_exact_phrase(text, "and/or")
    if and_or_span:
        gaps.append(
            CandidateGap(
                gap_type="ambiguity",
                subtype="coordination",
                span_text=text[and_or_span[0] : and_or_span[1]],
                start_char=and_or_span[0],
                end_char=and_or_span[1],
                severity=2,
                probability=0.90,
                explanation="The coordination 'and/or' introduces branching ambiguity regarding whether conditions are conjunctive or disjunctive.",
                question="Should both options be supported simultaneously, or is only one option selectable at a time?",
            )
        )

    # 1b. Vague Terms (adjectives, adverbs, unverifiable claims)
    for term in sorted(VAGUE_TERMS, key=len, reverse=True):
        span = _find_exact_phrase(text, term)
        if span:
            # Rule 0: check if defined elsewhere in doc context
            if doc_context and f"{term} is defined as" in doc_context.lower():
                continue
            matched_text = text[span[0] : span[1]]
            gaps.append(
                CandidateGap(
                    gap_type="ambiguity",
                    subtype="vague_term",
                    span_text=matched_text,
                    start_char=span[0],
                    end_char=span[1],
                    severity=2 if term not in {"as soon as possible", "high-performance"} else 3,
                    probability=0.88,
                    explanation=f"The term '{matched_text}' is subjective and lacks an objectively verifiable acceptance criterion.",
                    question=f"What specific measurable threshold or technical standard defines '{matched_text}' in this context?",
                )
            )

    # 1c. Vague Quantifiers (imprecise bounds, open-ended lists)
    for quantifier in sorted(VAGUE_QUANTIFIERS, key=len, reverse=True):
        span = _find_exact_phrase(text, quantifier)
        if span:
            matched_text = text[span[0] : span[1]]
            severity = 2 if quantifier in {"etc", "etc.", "and so on", "such as"} else 1
            gaps.append(
                CandidateGap(
                    gap_type="ambiguity",
                    subtype="vague_quantifier",
                    span_text=matched_text,
                    start_char=span[0],
                    end_char=span[1],
                    severity=severity,
                    probability=0.85,
                    explanation=f"The quantifier '{matched_text}' creates an open-ended specification without a definite boundary.",
                    question=f"What is the complete enumeration or exact numerical bound intended by '{matched_text}'?",
                )
            )

    # 1d. Anaphora / Vague Pronouns
    for pronoun in PRONOUNS_ANAPHORA:
        span = _find_exact_phrase(text, pronoun)
        if span:
            matched_text = text[span[0] : span[1]]
            gaps.append(
                CandidateGap(
                    gap_type="ambiguity",
                    subtype="anaphora",
                    span_text=matched_text,
                    start_char=span[0],
                    end_char=span[1],
                    severity=1,
                    probability=0.75,
                    explanation=f"The pronoun '{matched_text}' lacks an explicit antecedent in this requirement.",
                    question=f"Which specific entity or component does '{matched_text}' refer to?",
                )
            )

    # -------------------------------------------------------------------------
    # 2. Incompleteness Checks
    # -------------------------------------------------------------------------

    # 2a. Missing Actor (Passive without agent, or missing subject)
    if frame.is_passive and not frame.actor:
        span = frame.action_span or (0, len(text))
        gaps.append(
            CandidateGap(
                gap_type="incompleteness",
                subtype="missing_actor",
                span_text=text[span[0] : span[1]] if frame.action_span else text,
                start_char=span[0] if frame.action_span else 0,
                end_char=span[1] if frame.action_span else len(text),
                severity=2,
                probability=0.92,
                explanation="The requirement is stated in passive voice without specifying the responsible system or human actor.",
                question="Which specific component, role, or user is responsible for performing this action?",
            )
        )
    elif "actor" in frame.missing_slots:
        gaps.append(
            CandidateGap(
                gap_type="incompleteness",
                subtype="missing_actor",
                span_text=text[:15],
                start_char=0,
                end_char=min(15, len(text)),
                severity=2,
                probability=0.80,
                explanation="No explicit actor or subject was identified to carry out the required behavior.",
                question="Which system component or user role executes this requirement?",
            )
        )

    # 2b. Missing Condition / Loophole phrases
    for loophole in LOOPHOLE_CONDITIONS:
        span = _find_exact_phrase(text, loophole)
        if span:
            matched_text = text[span[0] : span[1]]
            gaps.append(
                CandidateGap(
                    gap_type="incompleteness",
                    subtype="missing_condition",
                    span_text=matched_text,
                    start_char=span[0],
                    end_char=span[1],
                    severity=2,
                    probability=0.90,
                    explanation=f"The loophole phrase '{matched_text}' makes the execution condition discretionary and untestable.",
                    question="Under what concrete system states or triggering events is this action mandatory versus omitted?",
                )
            )

    # 2c. Missing Threshold on vague metrics
    for phrase in THRESHOLD_VAGUE_ADJECTIVES:
        span = _find_exact_phrase(text, phrase)
        if span:
            matched_text = text[span[0] : span[1]]
            gaps.append(
                CandidateGap(
                    gap_type="incompleteness",
                    subtype="missing_threshold",
                    span_text=matched_text,
                    start_char=span[0],
                    end_char=span[1],
                    severity=2,
                    probability=0.86,
                    explanation=f"The metric '{matched_text}' specifies a desired quality without a numeric bound or unit.",
                    question=f"What is the maximum acceptable threshold and unit of measurement for '{matched_text}'?",
                )
            )

    # 2d. Missing Error Handling for critical actions
    if frame.action and frame.action.lower() in CRITICAL_ACTIONS:
        if not frame.exception:
            action_span = frame.action_span or (0, len(text))
            gaps.append(
                CandidateGap(
                    gap_type="incompleteness",
                    subtype="missing_error_handling",
                    span_text=frame.action,
                    start_char=action_span[0],
                    end_char=action_span[1],
                    severity=3,
                    probability=0.85,
                    explanation=f"The critical operation '{frame.action}' specifies normal execution but omits failure and error-handling behavior.",
                    question=f"What error handling or rollback procedure occurs if the {frame.action} operation fails?",
                )
            )

    # -------------------------------------------------------------------------
    # 3. Implicit Constraints Checks
    # -------------------------------------------------------------------------
    for trigger, (constraint_domain, q_text) in IMPLICIT_DOMAIN_CONSTRAINTS.items():
        span = _find_exact_phrase(text, trigger)
        if span:
            # Rule 0: check if the constraint domain is already stated in the requirement
            if constraint_domain not in text_lower:
                matched_text = text[span[0] : span[1]]
                gaps.append(
                    CandidateGap(
                        gap_type="implicit",
                        subtype="unstated_constraint",
                        span_text=matched_text,
                        start_char=span[0],
                        end_char=span[1],
                        severity=3,
                        probability=0.82,
                        explanation=f"Operations involving '{matched_text}' implicitly require unstated {constraint_domain} constraints.",
                        question=q_text,
                    )
                )

    # Deduplicate gaps with identical (gap_type, subtype, start_char, end_char)
    unique_gaps: list[CandidateGap] = []
    seen: set[tuple[str, str, int | None, int | None]] = set()
    for g in gaps:
        key = (g.gap_type, g.subtype, g.start_char, g.end_char)
        if key not in seen:
            seen.add(key)
            unique_gaps.append(g)

    # Sort by severity descending, then probability descending
    unique_gaps.sort(key=lambda g: (g.severity, g.probability), reverse=True)
    return unique_gaps
