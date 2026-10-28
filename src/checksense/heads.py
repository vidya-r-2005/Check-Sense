"""Phase 4 Specialized Gap Detection Heads (Heads 4a, 4b, 4c).

Implements the three architectural gap heads defined in MASTER_SPEC.md Section 5:
- Head 4a (Ambiguity):
    * Lexicon span detector (vague terms, quantifiers, pronouns, coordination).
    * Sentence-level smell probability from trained TfidfSmellClassifier.
    * Token-level BIO defect spans from trained LinearSpanTagger.
- Head 4b (Completeness):
    * Semantic frame slot heuristics (missing actor, condition, threshold, error handling).
    * Respects Rule 0: skips gaps if defined in SRS document context.
- Head 4c (Implicit):
    * Domain checklist ontology covering unstated constraints for sensitive operations
      (authentication, password, deletion, payment, personal data).

All heads emit CandidateGap objects ready for candidate-level fusion in Phase 5.
"""

from __future__ import annotations

from pathlib import Path

from .baseline import (
    CandidateGap,
    detect_rule_gaps,
)
from .frame import RequirementFrame, extract_requirement_frame
from .smell import TfidfSmellClassifier
from .span_tagger import LinearSpanTagger


class Phase4Pipeline:
    """Specialized Phase 4 multi-head gap detection engine."""

    def __init__(
        self,
        smell_model_path: Path | None = None,
        span_model_path: Path | None = None,
    ):
        self.smell_model: TfidfSmellClassifier | None = None
        self.span_tagger: LinearSpanTagger | None = None

        if smell_model_path and Path(smell_model_path).exists():
            try:
                self.smell_model = TfidfSmellClassifier.load(Path(smell_model_path))
            except Exception as e:
                print(f"[Phase4Pipeline] Warning loading smell model: {e}")

        if span_model_path and Path(span_model_path).exists():
            try:
                self.span_tagger = LinearSpanTagger.load(Path(span_model_path))
            except Exception as e:
                print(f"[Phase4Pipeline] Warning loading span model: {e}")

    def detect_head_4a_ambiguity(
        self,
        text: str,
        frame: RequirementFrame,
        doc_context: str | None = None,
    ) -> list[CandidateGap]:
        """Head 4a: Ambiguity detection combining lexicon, smell score, and span tagger."""
        # 1. Base rule & lexicon gaps
        base_gaps = detect_rule_gaps(text, frame=frame, doc_context=doc_context)
        ambiguity_gaps = [g for g in base_gaps if g.gap_type == "ambiguity"]

        # 2. Get sentence smell probability if model is loaded
        smell_prob = 0.5
        if self.smell_model:
            try:
                probs = self.smell_model.predict_smell_probability([text])
                smell_prob = float(probs[0])
            except Exception:
                smell_prob = 0.5

        # Rescale lexicon gap probabilities with sentence smell probability
        for g in ambiguity_gaps:
            g.probability = round(float(0.6 * g.probability + 0.4 * smell_prob), 4)

        # 3. Span Tagger predictions
        if self.span_tagger:
            try:
                predicted_spans = self.span_tagger.predict_spans(text)
                for ps in predicted_spans:
                    if ps["gap_type"] == "ambiguity":
                        # Check if span already covered by base gaps
                        already_covered = any(
                            g.span_text.lower() == ps["span_text"].lower()
                            or ps["span_text"].lower() in g.span_text.lower()
                            for g in ambiguity_gaps
                        )
                        if not already_covered and ps["span_text"].strip():
                            ambiguity_gaps.append(
                                CandidateGap(
                                    gap_type="ambiguity",
                                    subtype="vague_term",
                                    span_text=ps["span_text"],
                                    start_char=ps["start_char"],
                                    end_char=ps["end_char"],
                                    severity=2,
                                    probability=round(float(smell_prob), 4),
                                    explanation=f"Identified ambiguous token span '{ps['span_text']}' lacking operational specification.",
                                    question=f"What specific measurable threshold or technical standard defines '{ps['span_text']}' in this context?",
                                )
                            )
            except Exception:
                pass

        return ambiguity_gaps

    def detect_head_4b_completeness(
        self,
        text: str,
        frame: RequirementFrame,
        doc_context: str | None = None,
    ) -> list[CandidateGap]:
        """Head 4b: Completeness detection from frame slots and omissions."""
        base_gaps = detect_rule_gaps(text, frame=frame, doc_context=doc_context)
        return [g for g in base_gaps if g.gap_type == "incompleteness"]

    def detect_head_4c_implicit(
        self,
        text: str,
        frame: RequirementFrame,
        doc_context: str | None = None,
    ) -> list[CandidateGap]:
        """Head 4c: Implicit constraints from domain checklist ontology."""
        base_gaps = detect_rule_gaps(text, frame=frame, doc_context=doc_context)
        return [g for g in base_gaps if g.gap_type == "implicit"]

    def detect_all_gaps(
        self,
        text: str,
        frame: RequirementFrame | None = None,
        doc_context: str | None = None,
    ) -> list[CandidateGap]:
        """Execute Heads 4a, 4b, and 4c and return union of candidate gaps."""
        if frame is None:
            frame = extract_requirement_frame(text)

        gaps_4a = self.detect_head_4a_ambiguity(text, frame=frame, doc_context=doc_context)
        gaps_4b = self.detect_head_4b_completeness(text, frame=frame, doc_context=doc_context)
        gaps_4c = self.detect_head_4c_implicit(text, frame=frame, doc_context=doc_context)

        all_gaps = gaps_4a + gaps_4b + gaps_4c

        # Sort by severity descending, probability descending
        all_gaps.sort(key=lambda g: (g.severity, g.probability), reverse=True)
        return all_gaps


def run_phase4_heads(
    text: str,
    doc_context: str | None = None,
    smell_model_path: Path | None = None,
    span_model_path: Path | None = None,
) -> list[CandidateGap]:
    """Convenience helper to run all Phase 4 gap detection heads on requirement text."""
    pipeline = Phase4Pipeline(smell_model_path=smell_model_path, span_model_path=span_model_path)
    return pipeline.detect_all_gaps(text, doc_context=doc_context)
