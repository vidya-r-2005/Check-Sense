"""Requirement frame extraction using spaCy dependency parsing.

Extracts semantic slots from requirements sentences:
- actor: subject or agent performing the action
- modal: normative modal verb (shall, must, should, will)
- action: primary predicate / verb
- object: target patient / direct object
- condition: precondition or triggering clause (if, when, upon, etc.)
- quantity: numerical or quantitative constraint
- exception: failure or exceptional handling clause (unless, except, etc.)

Missing slots provide candidate gaps and fusion features as specified in MASTER_SPEC.md.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import spacy
from spacy.language import Language
from spacy.tokens import Doc, Token

_NLP_MODEL: Language | None = None

MODAL_LEMMAS = {"shall", "must", "should", "will", "can", "may", "could", "would"}
CONDITION_MARKERS = {
    "if",
    "when",
    "whenever",
    "upon",
    "where",
    "while",
    "after",
    "before",
    "as soon as",
    "as long as",
    "provided that",
    "in case",
    "in the event that",
}
EXCEPTION_MARKERS = {
    "unless",
    "except",
    "except for",
    "except when",
    "excluding",
    "otherwise",
    "with the exception of",
    "in the event of an error",
    "in case of failure",
}


def get_spacy_nlp(model_name: str = "en_core_web_sm") -> Language:
    """Load or retrieve the cached spaCy language model."""
    global _NLP_MODEL
    if _NLP_MODEL is None:
        try:
            _NLP_MODEL = spacy.load(model_name)
        except OSError:
            spacy.cli.download(model_name)
            _NLP_MODEL = spacy.load(model_name)
    return _NLP_MODEL


@dataclass
class RequirementFrame:
    """Normalized semantic frame for a requirement sentence."""

    text: str
    actor: str | None = None
    actor_span: tuple[int, int] | None = None
    modal: str | None = None
    modal_span: tuple[int, int] | None = None
    action: str | None = None
    action_span: tuple[int, int] | None = None
    object: str | None = None
    object_span: tuple[int, int] | None = None
    condition: str | None = None
    condition_span: tuple[int, int] | None = None
    quantity: str | None = None
    quantity_span: tuple[int, int] | None = None
    exception: str | None = None
    exception_span: tuple[int, int] | None = None
    is_passive: bool = False
    missing_slots: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert frame to dictionary."""
        return asdict(self)


def _get_span_bounds(tokens: list[Token]) -> tuple[int, int] | None:
    """Get character start and end for a list of tokens."""
    if not tokens:
        return None
    start = min(t.idx for t in tokens)
    end = max(t.idx + len(t.text) for t in tokens)
    return (start, end)


def _expand_noun_phrase(token: Token) -> tuple[str, tuple[int, int]]:
    """Expand a noun token to its full noun phrase span."""
    # Find all subtree tokens that belong to the phrase excluding punctuation
    phrase_tokens = [
        t for t in token.subtree
        if not t.is_punct and t.dep_ not in {"relcl", "advcl", "prep"}
    ]
    if not phrase_tokens:
        phrase_tokens = [token]
    phrase_tokens.sort(key=lambda t: t.i)
    bounds = _get_span_bounds(phrase_tokens) or (token.idx, token.idx + len(token.text))
    text = token.doc.text[bounds[0] : bounds[1]].strip()
    return text, bounds


def extract_requirement_frame(text: str, nlp: Language | None = None) -> RequirementFrame:
    """Extract requirement frame slots using dependency parsing.

    Args:
        text: The requirement sentence.
        nlp: Optional pre-loaded spaCy Language instance.

    Returns:
        A populated RequirementFrame instance.
    """
    if nlp is None:
        nlp = get_spacy_nlp()

    doc: Doc = nlp(text.strip())

    modal_token: Token | None = None
    action_token: Token | None = None
    actor_text: str | None = None
    actor_span: tuple[int, int] | None = None
    object_text: str | None = None
    object_span: tuple[int, int] | None = None
    is_passive = False

    # 1. Locate modal auxiliary
    for token in doc:
        if token.tag_ == "MD" or token.lower_ in MODAL_LEMMAS:
            modal_token = token
            break

    # 2. Locate action verb
    if modal_token and modal_token.head.pos_ in {"VERB", "AUX"}:
        action_token = modal_token.head
    else:
        # Fall back to root verb
        for token in doc:
            if token.dep_ == "ROOT" and token.pos_ in {"VERB", "AUX"}:
                action_token = token
                break

    # 3. Detect passive voice
    if action_token:
        for child in action_token.children:
            if child.dep_ in {"auxpass", "aux"} and child.lemma_ == "be":
                is_passive = True
            elif child.dep_ == "nsubjpass":
                is_passive = True

    # 4. Extract Actor & Object depending on voice
    if action_token:
        if is_passive:
            # In passive voice, syntactic subject is semantic patient/object
            for child in action_token.children:
                if child.dep_ == "nsubjpass":
                    object_text, object_span = _expand_noun_phrase(child)
                    break

            # Check for agent preposition phrase ("by the administrator")
            for child in action_token.children:
                if child.dep_ == "agent" or (child.dep_ == "prep" and child.lower_ == "by"):
                    for pobj in child.children:
                        if pobj.dep_ == "pobj":
                            actor_text, actor_span = _expand_noun_phrase(pobj)
                            break
                    if actor_text:
                        break
        else:
            # Active voice: nsubj is the actor
            for child in action_token.children:
                if child.dep_ in {"nsubj", "csubj"}:
                    actor_text, actor_span = _expand_noun_phrase(child)
                    break

            # Direct object (dobj / obj)
            for child in action_token.children:
                if child.dep_ in {"dobj", "obj", "attr"}:
                    object_text, object_span = _expand_noun_phrase(child)
                    break

    # 5. Extract Condition Clauses (e.g. if, when, upon, after, before, while)
    condition_text: str | None = None
    condition_span: tuple[int, int] | None = None

    # Check for leading or embedded conditional markers
    text_lower = text.lower()
    for marker in sorted(CONDITION_MARKERS, key=len, reverse=True):
        idx = text_lower.find(marker)
        if idx != -1:
            # Check token boundary
            is_start = idx == 0 or not text_lower[idx - 1].isalnum()
            end_idx = idx + len(marker)
            is_end = end_idx == len(text_lower) or not text_lower[end_idx].isalnum()
            if is_start and is_end:
                # Find the clause boundary (comma, semicolon, or end of sentence)
                clause_end = len(text)
                for delim in [",", ";"]:
                    delim_pos = text.find(delim, idx)
                    if delim_pos != -1 and (idx == 0 or delim_pos < clause_end):
                        clause_end = delim_pos
                        break
                # For trailing condition without punctuation
                if clause_end == len(text) and idx > 0:
                    cand = text[idx:].strip(". \t\r\n")
                    clause_end = idx + len(cand)

                cond_raw = text[idx:clause_end].strip()
                if len(cond_raw.split()) >= 2:  # Must have substantive clause content
                    condition_text = cond_raw
                    condition_span = (idx, idx + len(cond_raw))
                    break

    # 6. Extract Exception Clauses (unless, except, otherwise, in case of failure)
    exception_text: str | None = None
    exception_span: tuple[int, int] | None = None

    for marker in sorted(EXCEPTION_MARKERS, key=len, reverse=True):
        idx = text_lower.find(marker)
        if idx != -1:
            is_start = idx == 0 or not text_lower[idx - 1].isalnum()
            end_idx = idx + len(marker)
            is_end = end_idx == len(text_lower) or not text_lower[end_idx].isalnum()
            if is_start and is_end:
                clause_end = len(text)
                for delim in [",", ";"]:
                    delim_pos = text.find(delim, idx)
                    if delim_pos != -1:
                        clause_end = delim_pos
                        break
                exc_raw = text[idx:clause_end].strip(". \t\r\n")
                if len(exc_raw.split()) >= 1:
                    exception_text = exc_raw
                    exception_span = (idx, idx + len(exc_raw))
                    break

    # 7. Extract Quantity Phrases (nummod, quantities, time units)
    quantity_text: str | None = None
    quantity_span: tuple[int, int] | None = None

    for token in doc:
        if token.like_num or token.tag_ == "CD" or token.dep_ == "nummod":
            # Expand to include unit / noun e.g. "5 seconds", "at least 3 attempts"
            unit_tokens = [token]
            if token.head and token.head.i != token.i:
                unit_tokens.append(token.head)
            for left in token.lefts:
                if left.lower_ in {"at", "least", "most", "more", "than", "less", "within", "up", "to"}:
                    unit_tokens.append(left)
            unit_tokens.sort(key=lambda t: t.i)
            bounds = _get_span_bounds(unit_tokens)
            if bounds:
                quantity_text = doc.text[bounds[0] : bounds[1]].strip()
                quantity_span = bounds
                break

    # 8. Determine Missing Slots
    missing_slots: list[str] = []
    if not actor_text:
        missing_slots.append("actor")
    if not modal_token:
        missing_slots.append("modal")
    if not action_token:
        missing_slots.append("action")
    if not object_text:
        missing_slots.append("object")
    if not condition_text:
        missing_slots.append("condition")

    modal_span = (modal_token.idx, modal_token.idx + len(modal_token.text)) if modal_token else None
    action_span = (action_token.idx, action_token.idx + len(action_token.text)) if action_token else None

    return RequirementFrame(
        text=text,
        actor=actor_text,
        actor_span=actor_span,
        modal=modal_token.text if modal_token else None,
        modal_span=modal_span,
        action=action_token.text if action_token else None,
        action_span=action_span,
        object=object_text,
        object_span=object_span,
        condition=condition_text,
        condition_span=condition_span,
        quantity=quantity_text,
        quantity_span=quantity_span,
        exception=exception_text,
        exception_span=exception_span,
        is_passive=is_passive,
        missing_slots=missing_slots,
    )
