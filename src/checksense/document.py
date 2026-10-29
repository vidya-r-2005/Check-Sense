"""SRS Document Extraction, Segmentation, Batch Analysis, and Reporting Engine.

Provides comprehensive support for parsing authentic SRS documents in:
- PDF (.pdf) via pypdf (scanned PDF detection, page tracking)
- Microsoft Word (.docx) via python-docx (paragraphs, headings, tables, bullets)
- Plain text (.txt) (section header recognition, ID preservation, bullet grouping)

Performs batch multi-head defect analysis, candidate fusion, transparent clarity scoring,
grounded question formulation, governed refinement tracking, and report generation.
"""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .baseline import CandidateGap
from .eval_refinement import evaluate_iso_29148
from .frame import RequirementFrame, extract_requirement_frame
from .fusion import deduplicate_and_rank_candidates
from .generation import (
    generate_gap_explanation_and_question,
    get_template_explanation_and_question,
)
from .heads import Phase4Pipeline
from .refinement import StakeholderAnswer, refine_requirement, validate_numeric_preservation

NORMATIVE_MODALS = {"shall", "must"}
MODAL_PATTERN = re.compile(r"\b(shall|must|should|will|is\s+required\s+to)\b", re.IGNORECASE)

# Common SRS requirement ID patterns (e.g. REQ-001, [SR-1.2], 3.2.1, TAB-01)
REQ_ID_PATTERN = re.compile(
    r"^(?:\[?((?:[A-Za-z]{2,8}[-_]|(?:REQ|SRS|SYS|SW|HW|FUN|NFUN|SEC|PERF|UC|TAB|SPEC)\s*[-_]?)[A-Za-z0-9\.\-_]+)\]?|(\d+(?:\.\d+){1,4}))\s*[:\.-]?\s+(.*)$"
)

# Common SRS Section heading patterns
HEADING_NUMBER_PATTERN = re.compile(r"^(?:Section\s+)?(\d+(?:\.\d+)*)\s+([A-Z][\w\s\-]{2,60})$")


# ============================================================================
# 1. Data Models
# ============================================================================

@dataclass
class DocumentRequirement:
    """Represents a candidate requirement extracted from an SRS document."""

    req_id: str
    text: str
    source_file: str = ""
    section: str = "General"
    page_num: int | None = None
    line_num: int | None = None
    is_uncertain: bool = False
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CandidateQuestion:
    """Represents a clarification question generated for a detected gap."""

    question_id: str
    gap_type: str
    subtype: str
    span_text: str
    explanation: str
    question: str
    source: str = "Template"
    status: str = "open"  # "open", "answered", "unresolved"
    stakeholder_answer: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RequirementAnalysisResult:
    """Comprehensive analysis result for an individual requirement in an SRS document."""

    requirement: DocumentRequirement
    frame: RequirementFrame
    raw_candidates: list[CandidateGap]
    fused_gaps: list[CandidateGap]
    smell_prob: float
    iso_score: float
    iso_details: dict[str, Any]
    clarity_heuristic: float
    questions: list[CandidateQuestion]
    current_text: str
    is_approved: bool = False
    refinement_history: list[dict[str, Any]] = field(default_factory=list)

    @property
    def has_defects(self) -> bool:
        return len(self.fused_gaps) > 0

    @property
    def defect_count(self) -> int:
        return len(self.fused_gaps)

    @property
    def defect_categories(self) -> list[str]:
        return sorted({g.gap_type for g in self.fused_gaps})

    def to_dict(self) -> dict[str, Any]:
        return {
            "req_id": self.requirement.req_id,
            "section": self.requirement.section,
            "page_num": self.requirement.page_num,
            "source_file": self.requirement.source_file,
            "original_text": self.requirement.text,
            "current_text": self.current_text,
            "is_approved": self.is_approved,
            "defect_count": self.defect_count,
            "defect_categories": self.defect_categories,
            "smell_prob": round(self.smell_prob, 4),
            "iso_score": round(self.iso_score, 4),
            "clarity_heuristic": round(self.clarity_heuristic, 4),
            "fused_gaps": [asdict(g) for g in self.fused_gaps],
            "questions": [q.to_dict() for q in self.questions],
            "refinement_history": self.refinement_history,
        }


@dataclass
class DocumentQualitySummary:
    """Aggregated quality metrics across all requirements in an analyzed document."""

    filename: str
    total_candidates: int
    total_analyzed: int
    clean_requirements_count: int
    defective_requirements_count: int
    clean_ratio: float
    total_detected_gaps: int
    category_counts: dict[str, int]
    macro_avg_iso_score: float
    macro_avg_clarity_score: float
    total_questions_count: int
    answered_questions_count: int
    unresolved_questions_count: int
    approved_refinements_count: int
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ============================================================================
# 2. Transparent Clarity Heuristic Calculation
# ============================================================================

def compute_clarity_heuristic(
    text: str,
    fused_gaps: list[CandidateGap],
    smell_prob: float = 0.5,
    has_normative: bool = True,
) -> float:
    """Compute transparent, documented clarity score [0.0, 1.0].

    Transparent rule-based heuristic penalty calculation:
    - Initial base score: 1.00
    - Penalties per detected gap based on severity:
      * Severity 3 (Critical defect): -0.30 per gap
      * Severity 2 (Rework defect): -0.15 per gap
      * Severity 1 (Minor defect): -0.05 per gap
    - Smell probability penalty: -0.20 * smell_prob
    - Non-normative phrasing penalty: -0.15 if lacking 'shall' or 'must'
    - Clamped to range [0.00, 1.00].

    Distinction: This is a documented heuristic penalty index, clearly separate
    from the ISO/IEC/IEEE 29148 4-characteristic conformance score.
    """
    score = 1.00

    # Severity penalties
    for gap in fused_gaps:
        if gap.severity >= 3:
            score -= 0.30
        elif gap.severity == 2:
            score -= 0.15
        else:
            score -= 0.05

    # Smell model penalty
    score -= 0.20 * max(0.0, min(1.0, smell_prob))

    # Normative keyword penalty
    if not has_normative:
        score -= 0.15

    return round(max(0.0, min(1.0, score)), 4)


# ============================================================================
# 3. Document Text Extraction & Segmentation
# ============================================================================

def clean_inline_text(text: str) -> str:
    """Normalize internal spacing and clean control characters."""
    return " ".join(text.split())


def is_heading_or_toc(line: str) -> bool:
    """Detect whether a line is likely a section heading or table-of-contents entry."""
    s = line.strip()
    if not s:
        return True

    # TOC dots pattern: e.g. "3.1 Requirements .......... 14"
    if re.search(r"\.{4,}\s*\d+$", s) or re.search(r"_{4,}\s*\d+$", s):
        return True

    # Standard heading numbering: "1.0 Scope", "3.2 Functional Requirements"
    if HEADING_NUMBER_PATTERN.match(s):
        return True

    # Markdown style header
    if re.match(r"^#{1,6}\s+", s):
        return True

    # Short uppercase or title-case lines with no verb and <= 6 words
    words = s.split()
    if len(words) <= 6 and not s.endswith((".", ";", "?", "!")):
        if s.isupper() or all(w[0].isupper() for w in words if w[0].isalpha()):
            return True

    return False


NARRATIVE_SECTIONS = {
    "intro",
    "scope",
    "overview",
    "background",
    "purpose",
    "reference",
    "history",
    "revision",
    "document",
    "toc",
    "contents",
}


def is_narrative_section(section: str) -> bool:
    """Check if section name indicates non-requirement background narrative."""
    s = section.lower()
    return any(k in s for k in NARRATIVE_SECTIONS)


def parse_requirement_line(
    raw_text: str,
    default_id: str,
    current_section: str = "General",
    page_num: int | None = None,
    line_num: int | None = None,
    source_file: str = "",
) -> DocumentRequirement | None:
    """Inspect a candidate line and create a DocumentRequirement if valid."""
    cleaned = clean_inline_text(raw_text)
    if not cleaned or len(cleaned.split()) < 3:
        return None

    # Check for embedded explicit ID
    match = REQ_ID_PATTERN.match(cleaned)
    if match:
        extracted_id = match.group(1) or match.group(2)
        req_body = match.group(3).strip()
        assigned_id = extracted_id
    else:
        assigned_id = default_id
        req_body = cleaned

    if not req_body or len(req_body.split()) < 3:
        return None

    # Check if requirement contains a normative modal verb
    has_modal = bool(MODAL_PATTERN.search(req_body))
    has_id = bool(match)

    # Narrative text without an explicit requirement ID or modal verb in intro/scope sections is not a requirement
    if not has_id and not has_modal and is_narrative_section(current_section):
        return None

    is_uncertain = not has_modal

    return DocumentRequirement(
        req_id=assigned_id,
        text=req_body,
        source_file=source_file,
        section=current_section,
        page_num=page_num,
        line_num=line_num,
        is_uncertain=is_uncertain,
        notes="Non-normative modal phrasing" if is_uncertain else "",
    )


def extract_from_txt(
    content: bytes | str,
    filename: str = "document.txt",
) -> tuple[list[DocumentRequirement], list[str]]:
    """Extract and segment candidate requirements from a plain text file."""
    warnings: list[str] = []
    if isinstance(content, bytes):
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = content.decode("latin-1")
                warnings.append(f"Decoded {filename} using latin-1 encoding fallback.")
            except Exception as e:
                return [], [f"Failed to decode text file: {e}"]
    else:
        text = content

    lines = text.splitlines()
    if not lines or not text.strip():
        return [], ["Text document is empty."]

    requirements: list[DocumentRequirement] = []
    current_section = "General"
    req_counter = 1

    buffer: list[str] = []
    buffer_line = 1

    for line_idx, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line:
            if buffer:
                combined = " ".join(buffer)
                candidate = parse_requirement_line(
                    raw_text=combined,
                    default_id=f"REQ-{req_counter:03d}",
                    current_section=current_section,
                    line_num=buffer_line,
                    source_file=filename,
                )
                if candidate:
                    requirements.append(candidate)
                    req_counter += 1
                buffer.clear()
            continue

        # Check section heading
        if is_heading_or_toc(line):
            if buffer:
                combined = " ".join(buffer)
                candidate = parse_requirement_line(
                    raw_text=combined,
                    default_id=f"REQ-{req_counter:03d}",
                    current_section=current_section,
                    line_num=buffer_line,
                    source_file=filename,
                )
                if candidate:
                    requirements.append(candidate)
                    req_counter += 1
                buffer.clear()

            # Update section name
            clean_head = re.sub(r"^#{1,6}\s*", "", line).strip()
            current_section = clean_head
            continue

        # Bullet or numbered item check
        is_bullet = bool(re.match(r"^[-*•]\s+|\(?[0-9a-zA-Z]\)\s+|\d+\.\s+", line))
        has_id = bool(REQ_ID_PATTERN.match(line))
        prev_ended = bool(buffer and buffer[-1].rstrip().endswith((".", "!", "?")) and not buffer[-1].rstrip().endswith(":"))
        starts_new_sentence = bool(line and (line[0].isupper() or line[0].isdigit() or line[0] == "["))

        if (is_bullet or has_id or (prev_ended and starts_new_sentence)) and buffer:
            combined = " ".join(buffer)
            candidate = parse_requirement_line(
                raw_text=combined,
                default_id=f"REQ-{req_counter:03d}",
                current_section=current_section,
                line_num=buffer_line,
                source_file=filename,
            )
            if candidate:
                requirements.append(candidate)
                req_counter += 1
            buffer.clear()

        if not buffer:
            buffer_line = line_idx
        buffer.append(line)

    if buffer:
        combined = " ".join(buffer)
        candidate = parse_requirement_line(
            raw_text=combined,
            default_id=f"REQ-{req_counter:03d}",
            current_section=current_section,
            line_num=buffer_line,
            source_file=filename,
        )
        if candidate:
            requirements.append(candidate)

    if not requirements:
        warnings.append("No candidate requirements could be extracted from text file.")

    return requirements, warnings


def extract_from_docx(
    content: bytes,
    filename: str = "document.docx",
) -> tuple[list[DocumentRequirement], list[str]]:
    """Extract candidate requirements from Microsoft Word (.docx) document.

    Parses paragraphs, heading styles, bullet lists, and tables safely without macro execution.
    """
    import docx

    warnings: list[str] = []
    if not content:
        return [], ["Word document is empty."]

    try:
        doc = docx.Document(io.BytesIO(content))
    except Exception as e:
        return [], [f"Failed to parse Word document ({filename}): {e}"]

    requirements: list[DocumentRequirement] = []
    current_section = "General"
    req_counter = 1

    # 1. Parse paragraphs & headings
    for p_idx, p in enumerate(doc.paragraphs, start=1):
        text = p.text.strip()
        if not text:
            continue

        style_name = p.style.name.lower() if p.style and p.style.name else ""

        # Check heading styles
        if "heading" in style_name or is_heading_or_toc(text):
            current_section = clean_inline_text(text)
            continue

        candidate = parse_requirement_line(
            raw_text=text,
            default_id=f"REQ-{req_counter:03d}",
            current_section=current_section,
            line_num=p_idx,
            source_file=filename,
        )
        if candidate:
            requirements.append(candidate)
            req_counter += 1

    # 2. Parse tables (e.g. SRS requirements matrix)
    for t_idx, table in enumerate(doc.tables, start=1):
        if not table.rows:
            continue

        # Inspect headers if available
        headers = [clean_inline_text(cell.text).lower() for cell in table.rows[0].cells]
        id_col_idx = next(
            (i for i, h in enumerate(headers) if any(k in h for k in ["id", "identifier", "ref", "req#", "req_id"])),
            None,
        )
        req_col_idx = next(
            (
                i
                for i, h in enumerate(headers)
                if i != id_col_idx
                and any(k in h for k in ["statement", "description", "specification", "detail", "text", "requirement"])
            ),
            None,
        )
        if req_col_idx is None and len(headers) > 1:
            req_col_idx = 1 if id_col_idx == 0 else 0

        start_row = 1 if (id_col_idx is not None or req_col_idx is not None) else 0

        for r_idx in range(start_row, len(table.rows)):
            row = table.rows[r_idx]
            cells = row.cells
            if not cells:
                continue

            if req_col_idx is not None and req_col_idx < len(cells):
                req_text = clean_inline_text(cells[req_col_idx].text)
                cell_id = clean_inline_text(cells[id_col_idx].text) if id_col_idx is not None and id_col_idx < len(cells) else ""
            else:
                # Concatenate row text
                cell_texts = [clean_inline_text(c.text) for c in cells if clean_inline_text(c.text)]
                req_text = " — ".join(cell_texts)
                cell_id = ""

            if not req_text or len(req_text.split()) < 3:
                continue

            assigned_id = cell_id if cell_id else f"REQ-{req_counter:03d}"
            candidate = DocumentRequirement(
                req_id=assigned_id,
                text=req_text,
                source_file=filename,
                section=f"{current_section} (Table {t_idx})",
                line_num=r_idx,
                is_uncertain=not bool(MODAL_PATTERN.search(req_text)),
            )
            requirements.append(candidate)
            req_counter += 1

    if not requirements:
        warnings.append("Document parsed successfully, but zero candidate requirements were found.")

    return requirements, warnings


def extract_from_pdf(
    content: bytes,
    filename: str = "document.pdf",
) -> tuple[list[DocumentRequirement], list[str]]:
    """Extract candidate requirements from an Adobe PDF document via pypdf.

    Tracks 1-based page numbers and gracefully handles scanned (image-only) PDFs.
    """
    import pypdf

    warnings: list[str] = []
    if not content:
        return [], ["PDF file is empty."]

    try:
        reader = pypdf.PdfReader(io.BytesIO(content))
    except Exception as e:
        return [], [f"Failed to read PDF document ({filename}): {e}"]

    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception:
            return [], [f"PDF document ({filename}) is password-protected and could not be decrypted."]

    total_pages = len(reader.pages)
    if total_pages == 0:
        return [], ["PDF document has 0 pages."]

    total_chars = 0
    requirements: list[DocumentRequirement] = []
    current_section = "General"
    req_counter = 1

    for page_idx, page in enumerate(reader.pages, start=1):
        try:
            page_text = page.extract_text() or ""
        except Exception as e:
            warnings.append(f"Error extracting text from page {page_idx}: {e}")
            continue

        total_chars += len(page_text.strip())
        lines = page_text.splitlines()

        for line_idx, line_raw in enumerate(lines, start=1):
            line = clean_inline_text(line_raw)
            if not line:
                continue

            # Heading detection
            if is_heading_or_toc(line):
                current_section = line
                continue

            candidate = parse_requirement_line(
                raw_text=line,
                default_id=f"REQ-{req_counter:03d}",
                current_section=current_section,
                page_num=page_idx,
                line_num=line_idx,
                source_file=filename,
            )
            if candidate:
                requirements.append(candidate)
                req_counter += 1

    # Detect scanned / image-only PDFs
    if total_chars < 50:
        warnings.append(
            f"PDF '{filename}' appears to be a scanned image or contains no extractable text "
            f"({total_chars} characters found). OCR preprocessing is required for scanned documents."
        )

    if not requirements and total_chars >= 50:
        warnings.append("Text was extracted from PDF, but no normative requirement statements were identified.")

    return requirements, warnings


def extract_srs_document(
    content: bytes,
    filename: str,
) -> tuple[list[DocumentRequirement], list[str]]:
    """Unified document extraction dispatcher supporting PDF, DOCX, and TXT."""
    ext = Path(filename).suffix.lower()

    if ext == ".txt":
        return extract_from_txt(content, filename=filename)
    elif ext == ".docx":
        return extract_from_docx(content, filename=filename)
    elif ext == ".pdf":
        return extract_from_pdf(content, filename=filename)
    else:
        return [], [f"Unsupported file format '{ext}'. Only .pdf, .docx, and .txt files are supported."]


# ============================================================================
# 4. Batch Requirement Analysis Engine
# ============================================================================

def analyze_srs_requirements(
    requirements: list[DocumentRequirement],
    pipeline: Phase4Pipeline,
    fusion_scorer: Any,
    llm_client: Any | None = None,
) -> list[RequirementAnalysisResult]:
    """Execute end-to-end multi-head defect analysis on all extracted requirements."""
    results: list[RequirementAnalysisResult] = []

    for req in requirements:
        req_text = req.text.strip()

        # 1. Dependency Frame Extraction
        frame = extract_requirement_frame(req_text)

        # 2. Multi-Head Gap Detection (Heads 4a, 4b, 4c)
        raw_candidates = pipeline.detect_all_gaps(req_text, frame=frame)

        # 3. Sentence-level smell probability
        smell_prob = 0.5
        if pipeline.smell_model:
            try:
                smell_prob = float(pipeline.smell_model.predict_smell_probability([req_text])[0])
            except Exception:
                smell_prob = 0.5

        # 4. Phase 5 Fusion & Deduplication
        fused_gaps = deduplicate_and_rank_candidates(
            candidates=raw_candidates,
            scorer=fusion_scorer,
            req_text=req_text,
            frame=frame,
            smell_prob=smell_prob,
        )

        # 5. ISO/IEC/IEEE 29148 Conformance Evaluation
        iso_char = evaluate_iso_29148(req_text, detected_gaps=fused_gaps)

        # 6. Transparent Clarity Heuristic Penalty Score
        clarity_score = compute_clarity_heuristic(
            text=req_text,
            fused_gaps=fused_gaps,
            smell_prob=smell_prob,
            has_normative=iso_char.is_normative,
        )

        # 7. Formulate grounded clarification questions for detected gaps
        candidate_questions: list[CandidateQuestion] = []
        for q_idx, gap in enumerate(fused_gaps, start=1):
            expl = ""
            q = ""
            source = "Template"

            if llm_client and llm_client.is_available():
                try:
                    expl, q = generate_gap_explanation_and_question(
                        requirement_text=req_text,
                        gap_type=gap.gap_type,
                        subtype=gap.subtype,
                        span_text=gap.span_text,
                        llm_client=llm_client,
                    )
                    source = "LLM (qwen2.5:7b)"
                except Exception:
                    expl, q = get_template_explanation_and_question(
                        gap_type=gap.gap_type,
                        subtype=gap.subtype,
                        span_text=gap.span_text,
                    )
                    source = "Template Fallback"
            else:
                expl, q = get_template_explanation_and_question(
                    gap_type=gap.gap_type,
                    subtype=gap.subtype,
                    span_text=gap.span_text,
                )
                source = "Template"

            candidate_questions.append(
                CandidateQuestion(
                    question_id=f"{req.req_id}-Q{q_idx}",
                    gap_type=gap.gap_type,
                    subtype=gap.subtype,
                    span_text=gap.span_text,
                    explanation=expl,
                    question=q,
                    source=source,
                    status="open",
                )
            )

        results.append(
            RequirementAnalysisResult(
                requirement=req,
                frame=frame,
                raw_candidates=raw_candidates,
                fused_gaps=fused_gaps,
                smell_prob=smell_prob,
                iso_score=iso_char.score(),
                iso_details=iso_char.to_dict(),
                clarity_heuristic=clarity_score,
                questions=candidate_questions,
                current_text=req_text,
                is_approved=False,
                refinement_history=[],
            )
        )

    return results


# ============================================================================
# 5. Document-Level Summary Aggregator
# ============================================================================

def summarize_srs_analysis(
    results: list[RequirementAnalysisResult],
    filename: str = "",
    extraction_warnings: list[str] | None = None,
) -> DocumentQualitySummary:
    """Aggregate document-level metrics without double-counting requirements."""
    total_candidates = len(results)
    if total_candidates == 0:
        return DocumentQualitySummary(
            filename=filename,
            total_candidates=0,
            total_analyzed=0,
            clean_requirements_count=0,
            defective_requirements_count=0,
            clean_ratio=0.0,
            total_detected_gaps=0,
            category_counts={"ambiguity": 0, "incompleteness": 0, "implicit": 0},
            macro_avg_iso_score=0.0,
            macro_avg_clarity_score=0.0,
            total_questions_count=0,
            answered_questions_count=0,
            unresolved_questions_count=0,
            approved_refinements_count=0,
            warnings=extraction_warnings or [],
        )

    clean_count = sum(1 for r in results if not r.has_defects)
    defective_count = total_candidates - clean_count
    clean_ratio = clean_count / total_candidates

    total_gaps = sum(r.defect_count for r in results)

    category_counts: dict[str, int] = {"ambiguity": 0, "incompleteness": 0, "implicit": 0}
    for r in results:
        for g in r.fused_gaps:
            cat = g.gap_type.lower()
            category_counts[cat] = category_counts.get(cat, 0) + 1

    macro_avg_iso = sum(r.iso_score for r in results) / total_candidates
    macro_avg_clarity = sum(r.clarity_heuristic for r in results) / total_candidates

    total_q = sum(len(r.questions) for r in results)
    answered_q = sum(sum(1 for q in r.questions if q.status == "answered") for r in results)
    unresolved_q = sum(sum(1 for q in r.questions if q.status in {"open", "unresolved"}) for r in results)
    approved_count = sum(1 for r in results if r.is_approved)

    return DocumentQualitySummary(
        filename=filename,
        total_candidates=total_candidates,
        total_analyzed=total_candidates,
        clean_requirements_count=clean_count,
        defective_requirements_count=defective_count,
        clean_ratio=round(clean_ratio, 4),
        total_detected_gaps=total_gaps,
        category_counts=category_counts,
        macro_avg_iso_score=round(macro_avg_iso, 4),
        macro_avg_clarity_score=round(macro_avg_clarity, 4),
        total_questions_count=total_q,
        answered_questions_count=answered_q,
        unresolved_questions_count=unresolved_q,
        approved_refinements_count=approved_count,
        warnings=extraction_warnings or [],
    )


# ============================================================================
# 6. Interactive Refinement & Approval Processor
# ============================================================================

def apply_refinement_to_analysis_result(
    result: RequirementAnalysisResult,
    question_id: str,
    stakeholder_answer: str,
    llm_client: Any | None = None,
) -> tuple[str, bool, str, str]:
    """Propose revised requirement text for a selected question.

    Returns:
        (proposed_text, is_numeric_valid, audit_message, method_used)
    """
    target_q = next((q for q in result.questions if q.question_id == question_id), None)
    if not target_q:
        return result.current_text, False, f"Question ID '{question_id}' not found.", "None"

    st_answer = StakeholderAnswer(
        req_id=result.requirement.req_id,
        gap_type=target_q.gap_type,
        subtype=target_q.subtype,
        span_text=target_q.span_text,
        question=target_q.question,
        answer=stakeholder_answer.strip(),
    )

    refined_sentence, method_used = refine_requirement(
        original_text=result.current_text,
        stakeholder_answer=st_answer,
        llm_client=llm_client,
    )

    # Validate numbers against original requirement and answer
    is_valid, audit_msg = validate_numeric_preservation(
        original_text=result.requirement.text,
        answer_text=stakeholder_answer.strip(),
        refined_text=refined_sentence,
    )

    return refined_sentence, is_valid, audit_msg, method_used


def commit_approved_refinement(
    result: RequirementAnalysisResult,
    question_id: str,
    stakeholder_answer: str,
    refined_text: str,
    method_used: str,
) -> None:
    """Explicitly commit user-approved revision and update audit history."""
    target_q = next((q for q in result.questions if q.question_id == question_id), None)
    if target_q:
        target_q.status = "answered"
        target_q.stakeholder_answer = stakeholder_answer.strip()

    old_text = result.current_text
    result.current_text = refined_text
    result.is_approved = True

    # Re-evaluate ISO 29148 on refined text
    iso_after = evaluate_iso_29148(refined_text)
    result.iso_score = iso_after.score()
    result.iso_details = iso_after.to_dict()

    # Re-calculate clarity heuristic
    result.clarity_heuristic = compute_clarity_heuristic(
        text=refined_text,
        fused_gaps=[],  # Gap resolved
        smell_prob=0.0,
        has_normative=iso_after.is_normative,
    )

    result.refinement_history.append(
        {
            "timestamp": datetime.now(UTC).isoformat(),
            "question_id": question_id,
            "answer": stakeholder_answer.strip(),
            "previous_text": old_text,
            "refined_text": refined_text,
            "method": method_used,
            "approved_by_user": True,
        }
    )


# ============================================================================
# 7. Exportable Report Generators
# ============================================================================

def generate_markdown_srs_report(
    summary: DocumentQualitySummary,
    results: list[RequirementAnalysisResult],
) -> str:
    """Compile comprehensive Markdown SRS analysis monograph."""
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")

    lines = [
        "# CheckSense SRS Document Analysis Report",
        "",
        f"- **Analyzed File:** `{summary.filename}`",
        f"- **Analysis Timestamp:** `{timestamp}`",
        "- **CheckSense Version:** `0.1.0`",
        "- **Evaluation Governance:** [MASTER_SPEC.md](docs/MASTER_SPEC.md)",
        "",
        "---",
        "",
        "## 1. Executive Summary & Document-Level Quality",
        "",
        "| Metric Name | Value | Interpretation / Aggregation Note |",
        "|---|---|---|",
        f"| **Total Candidate Requirements** | `{summary.total_candidates}` | Total parsed candidate statements |",
        f"| **Clean Requirements (Zero Gaps)** | `{summary.clean_requirements_count}` | Requirements with 0 detected defects |",
        f"| **Requirements with Gaps** | `{summary.defective_requirements_count}` | Requirements flagged with $\\ge 1$ defect |",
        f"| **Clean Requirements Ratio** | `{summary.clean_ratio:.1%}` | Non-double-counted document completeness index |",
        f"| **Total Detected Gaps** | `{summary.total_detected_gaps}` | Ambiguity, incompleteness, and implicit gaps |",
        f"| **Macro-Avg ISO 29148 Score** | `{summary.macro_avg_iso_score:.2f} / 1.00` | Average 4-characteristic conformance index |",
        f"| **Macro-Avg Clarity Score** | `{summary.macro_avg_clarity_score:.2f} / 1.00` | Average penalty-based clarity index |",
        f"| **Generated Clarification Questions** | `{summary.total_questions_count}` | Grounded questions for stakeholders |",
        f"| **Answered Questions** | `{summary.answered_questions_count}` | Questions with recorded answers |",
        f"| **Unresolved Questions** | `{summary.unresolved_questions_count}` | Open questions awaiting stakeholder input |",
        f"| **Approved Refinements** | `{summary.approved_refinements_count}` | Revisions explicitly confirmed by engineer |",
        "",
        "### Defect Category Distribution",
        f"- **Ambiguity Gaps:** `{summary.category_counts.get('ambiguity', 0)}`",
        f"- **Incompleteness Gaps:** `{summary.category_counts.get('incompleteness', 0)}`",
        f"- **Implicit Constraint Gaps:** `{summary.category_counts.get('implicit', 0)}`",
        "",
    ]

    if summary.warnings:
        lines.extend([
            "### ⚠️ Extraction Warnings & Disclosures",
            "",
        ])
        for w in summary.warnings:
            lines.append(f"- ⚠️ {w}")
        lines.append("")

    lines.extend([
        "---",
        "",
        "## 2. Requirement-by-Requirement Analysis",
        "",
    ])

    for idx, r in enumerate(results, start=1):
        status_label = "✅ Approved Revision" if r.is_approved else ("⚠️ Defects Flagged" if r.has_defects else "✅ Clean")
        lines.extend([
            f"### {idx}. [{r.requirement.req_id}] {r.requirement.section}",
            f"- **Source Metadata:** File `{r.requirement.source_file}`, Page `{r.requirement.page_num or 'N/A'}`, Line `{r.requirement.line_num or 'N/A'}`",
            f"- **Analysis Status:** **{status_label}**",
            f"- **Clarity Score:** `{r.clarity_heuristic:.2f}` | **ISO 29148 Score:** `{r.iso_score:.2f}`",
            "",
            "**Original Requirement Text:**",
            f"> {r.requirement.text}",
            "",
        ])

        if r.fused_gaps:
            lines.append("**Detected Defect Gaps:**")
            for g in r.fused_gaps:
                span_str = f"'{g.span_text}'" if g.span_text else "(entire requirement)"
                lines.append(f"- `[{g.gap_type.upper()}]` **{g.subtype}** at span {span_str} (Severity: Level {g.severity}, Confidence: {g.probability:.1%})")
                lines.append(f"  *Diagnostic Explanation:* {g.explanation}")
            lines.append("")

        if r.questions:
            lines.append("**Clarification Questions & Stakeholder Answers:**")
            for q in r.questions:
                q_status = "✅ Answered" if q.status == "answered" else "⚪ Open"
                lines.append(f"- **[{q.question_id}]** `{q_status}` ({q.source}): *{q.question}*")
                if q.stakeholder_answer:
                    lines.append(f"  *Recorded Answer:* **{q.stakeholder_answer}**")
            lines.append("")

        if r.is_approved or r.current_text != r.requirement.text:
            lines.extend([
                "**Refined Requirement Text:**",
                f"> {r.current_text}",
                "",
                f"- **Approval Status:** {'Approved by Stakeholder / Engineer' if r.is_approved else 'Provisional / Unapproved Draft'}",
                "",
            ])

        lines.append("---")
        lines.append("")

    lines.extend([
        "## 3. Requirement Traceability Matrix",
        "",
        "| Req ID | Section | Defect Categories | Questions | Answer Status | Final Approval |",
        "|---|---|---|---|---|---|",
    ])
    for r in results:
        cats = ", ".join(r.defect_categories) if r.defect_categories else "None"
        q_count = len(r.questions)
        ans_status = f"{sum(1 for q in r.questions if q.status == 'answered')}/{q_count} Answered" if q_count > 0 else "N/A"
        appr_status = "Approved" if r.is_approved else ("Clean" if not r.has_defects else "Unapproved")
        lines.append(f"| `{r.requirement.req_id}` | {r.requirement.section} | {cats} | {q_count} | {ans_status} | {appr_status} |")

    lines.append("")
    lines.append("---")
    lines.append("*Report generated automatically by CheckSense NLP Requirements Engineering Engine.*")

    return "\n".join(lines)


def generate_csv_srs_report(results: list[RequirementAnalysisResult]) -> str:
    """Compile structured CSV table of all requirements and analysis metrics."""
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")

    writer.writerow([
        "req_id",
        "source_file",
        "section",
        "page_num",
        "line_num",
        "original_text",
        "has_defects",
        "defect_count",
        "defect_categories",
        "smell_prob",
        "iso_score",
        "clarity_heuristic",
        "questions_count",
        "unresolved_questions_count",
        "refined_text",
        "is_approved",
    ])

    for r in results:
        cats_str = "; ".join(r.defect_categories)
        unresolved = sum(1 for q in r.questions if q.status in {"open", "unresolved"})
        writer.writerow([
            r.requirement.req_id,
            r.requirement.source_file,
            r.requirement.section,
            r.requirement.page_num or "",
            r.requirement.line_num or "",
            r.requirement.text,
            r.has_defects,
            r.defect_count,
            cats_str,
            round(r.smell_prob, 4),
            round(r.iso_score, 4),
            round(r.clarity_heuristic, 4),
            len(r.questions),
            unresolved,
            r.current_text,
            r.is_approved,
        ])

    return output.getvalue()


def generate_audit_trail_json(
    summary: DocumentQualitySummary,
    results: list[RequirementAnalysisResult],
) -> str:
    """Compile JSON audit trail recording all requirements, detections, questions, and edits."""
    data = {
        "timestamp": datetime.now(UTC).isoformat(),
        "summary": summary.to_dict(),
        "results": [r.to_dict() for r in results],
    }
    return json.dumps(data, indent=2)
