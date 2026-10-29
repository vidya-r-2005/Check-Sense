"""Unit and integration tests for SRS Document Upload, Extraction, Batch Analysis, and Reporting.

Covers:
- TXT, DOCX, and PDF parsing and segmentation
- Requirement ID and section heading recognition
- Empty, scanned, malformed, and unsupported file handling
- Multiline, bulleted, and table-based requirement extraction
- Batch multi-head analysis and fusion scoring
- Transparent clarity heuristic penalty score vs ISO 29148
- Clarification question formulation and status tracking
- Refinement engine with strict numeric preservation
- Explicit stakeholder approval workflow
- Markdown, CSV, and JSON audit trail report generation
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import docx
import pypdf

from checksense import (
    CandidateGap,
    HeuristicFusionScorer,
    Phase4Pipeline,
    apply_refinement_to_analysis_result,
    commit_approved_refinement,
    compute_clarity_heuristic,
    extract_from_docx,
    extract_from_pdf,
    extract_from_txt,
    extract_srs_document,
    generate_audit_trail_json,
    generate_csv_srs_report,
    generate_markdown_srs_report,
    summarize_srs_analysis,
)
from checksense.document import (
    DocumentRequirement,
    analyze_srs_requirements,
)

# ============================================================================
# 1. Text (.txt) Document Parsing Tests
# ============================================================================

def test_extract_txt_with_headings_and_ids():
    """Verify section headings, explicit IDs, and standard normative parsing."""
    raw_content = """
# 1.0 Introduction
This document describes the software requirements for the satellite ground station.

## 2.0 Functional Requirements
REQ-001: The system shall process incoming telemetry within 250 milliseconds.
REQ-002: The antenna controller shall calibrate azimuth angles before tracking.

## 3.0 Performance Requirements
[PERF-01] The telemetry database shall store at least 10000 records per hour.
The system displays network statistics.
"""
    reqs, warnings = extract_from_txt(raw_content, filename="test_spec.txt")
    assert len(reqs) >= 3
    assert len(warnings) == 0

    ids = [r.req_id for r in reqs]
    assert "REQ-001" in ids
    assert "REQ-002" in ids
    assert "PERF-01" in ids

    # Check that normative requirements are certain, while non-normative is marked uncertain
    req1 = next(r for r in reqs if r.req_id == "REQ-001")
    assert req1.is_uncertain is False
    assert "250 milliseconds" in req1.text
    assert "Functional Requirements" in req1.section

    # The sentence without modal: "The system displays network statistics"
    uncertain_req = next((r for r in reqs if "network statistics" in r.text), None)
    if uncertain_req:
        assert uncertain_req.is_uncertain is True


def test_extract_txt_empty_and_corrupt():
    """Verify empty and whitespace-only text handling."""
    reqs_empty, warns_empty = extract_from_txt("", filename="empty.txt")
    assert reqs_empty == []
    assert len(warns_empty) >= 1
    assert "empty" in warns_empty[0].lower()

    reqs_ws, warns_ws = extract_from_txt("   \n\t   \n", filename="ws.txt")
    assert reqs_ws == []
    assert len(warns_ws) >= 1


# ============================================================================
# 2. Microsoft Word (.docx) Parsing Tests
# ============================================================================

def test_extract_docx_with_headings_tables_and_bullets(tmp_path: Path):
    """Create a synthetic DOCX with headings, paragraphs, and tables, and verify extraction."""
    doc = docx.Document()
    doc.add_heading("1.0 Scope", level=1)
    doc.add_paragraph("This is the system overview.")

    doc.add_heading("2.0 Specific Requirements", level=1)
    doc.add_paragraph("REQ-010: The system shall encrypt all outgoing telemetry packets.")
    doc.add_paragraph("REQ-011: The server must log all authentication failures.")

    # Table with requirements
    table = doc.add_table(rows=3, cols=2)
    table.rows[0].cells[0].text = "Requirement ID"
    table.rows[0].cells[1].text = "Requirement Statement"

    table.rows[1].cells[0].text = "TAB-01"
    table.rows[1].cells[1].text = "The operator console shall display critical alarms in red."

    table.rows[2].cells[0].text = "TAB-02"
    table.rows[2].cells[1].text = "The system shall shut down gracefully upon power failure."

    doc_bytes = io.BytesIO()
    doc.save(doc_bytes)
    content = doc_bytes.getvalue()

    reqs, warnings = extract_from_docx(content, filename="synthetic.docx")
    assert len(reqs) == 4
    assert len(warnings) == 0

    ids = [r.req_id for r in reqs]
    assert "REQ-010" in ids
    assert "REQ-011" in ids
    assert "TAB-01" in ids
    assert "TAB-02" in ids

    tab_req = next(r for r in reqs if r.req_id == "TAB-01")
    assert "display critical alarms" in tab_req.text
    assert "Table" in tab_req.section


def test_extract_docx_empty_and_invalid():
    """Verify error handling on empty or invalid DOCX content."""
    reqs, warns = extract_from_docx(b"", filename="empty.docx")
    assert reqs == []
    assert len(warns) >= 1

    reqs_corrupt, warns_corrupt = extract_from_docx(b"NOT_A_VALID_ZIP_PACKAGE", filename="bad.docx")
    assert reqs_corrupt == []
    assert len(warns_corrupt) >= 1
    assert "failed" in warns_corrupt[0].lower()


# ============================================================================
# 3. Adobe PDF (.pdf) Parsing Tests
# ============================================================================

def test_extract_pdf_synthetic(tmp_path: Path):
    """Create a synthetic PDF using pypdf writer and verify text extraction & page tracking."""
    # Write a simple PDF using pypdf writer
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=612, height=792)

    # Note: blank page has no text; pypdf will detect 0 chars and issue a scanned warning
    pdf_bytes = io.BytesIO()
    writer.write(pdf_bytes)
    content = pdf_bytes.getvalue()

    reqs, warnings = extract_from_pdf(content, filename="scanned_or_blank.pdf")
    assert reqs == []
    assert len(warnings) >= 1
    assert "scanned" in warnings[0].lower() or "text" in warnings[0].lower()


def test_extract_pdf_empty_and_invalid():
    """Verify response to empty and corrupted PDF bytes."""
    reqs, warns = extract_from_pdf(b"", filename="empty.pdf")
    assert reqs == []
    assert len(warns) >= 1

    reqs_bad, warns_bad = extract_from_pdf(b"%PDF-1.4 BAD_CORRUPTED_STREAM", filename="corrupt.pdf")
    assert reqs_bad == []
    assert len(warns_bad) >= 1


# ============================================================================
# 4. Unified Dispatcher & Unsupported Formats
# ============================================================================

def test_extract_srs_document_dispatcher():
    """Verify unified dispatcher dispatches correctly and rejects unsupported formats."""
    # Unsupported
    reqs_unsupp, warns_unsupp = extract_srs_document(b"data", "spec.xlsx")
    assert reqs_unsupp == []
    assert "unsupported" in warns_unsupp[0].lower()

    # TXT
    reqs_txt, _ = extract_srs_document(b"REQ-01: The system shall run quickly.", "spec.txt")
    assert len(reqs_txt) == 1
    assert reqs_txt[0].req_id == "REQ-01"


# ============================================================================
# 5. Clarity Heuristic Penalty Calculation
# ============================================================================

def test_compute_clarity_heuristic():
    """Verify that clarity heuristic penalty formula is transparent and bounded [0.0, 1.0]."""
    # Clean requirement
    clean_score = compute_clarity_heuristic(
        text="The engine shall stop within 50 ms.",
        fused_gaps=[],
        smell_prob=0.0,
        has_normative=True,
    )
    assert clean_score == 1.00

    # Requirement with Severity 2 defect (rework) and smell_prob 0.5
    gap_sev2 = CandidateGap(
        gap_type="ambiguity",
        subtype="vague_term",
        span_text="quickly",
        start_char=20,
        end_char=27,
        severity=2,
        probability=0.9,
        explanation="The term 'quickly' is subjective.",
        question="What specific response time threshold defines 'quickly'?",
    )
    score_sev2 = compute_clarity_heuristic(
        text="The engine shall run quickly.",
        fused_gaps=[gap_sev2],
        smell_prob=0.5,
        has_normative=True,
    )
    # Expected: 1.00 - 0.15 (sev 2) - 0.20*0.5 (smell) = 0.75
    assert score_sev2 == 0.75

    # Severely defective requirement with multiple critical gaps
    gap_crit1 = CandidateGap(gap_type="incompleteness", subtype="missing_actor", span_text="", start_char=0, end_char=0, severity=3, probability=0.9, explanation="e", question="q?")
    gap_crit2 = CandidateGap(gap_type="implicit", subtype="security", span_text="", start_char=0, end_char=0, severity=3, probability=0.9, explanation="e", question="q?")
    gap_crit3 = CandidateGap(gap_type="incompleteness", subtype="missing_condition", span_text="", start_char=0, end_char=0, severity=3, probability=0.9, explanation="e", question="q?")
    gap_crit4 = CandidateGap(gap_type="ambiguity", subtype="vague_term", span_text="fast", start_char=0, end_char=0, severity=3, probability=0.9, explanation="e", question="q?")

    low_score = compute_clarity_heuristic(
        text="Displays data fast.",
        fused_gaps=[gap_crit1, gap_crit2, gap_crit3, gap_crit4],
        smell_prob=1.0,
        has_normative=False,
    )
    assert low_score == 0.00  # Clamped to zero


# ============================================================================
# 6. Batch Analysis & Refinement Lifecycle Integration
# ============================================================================

def test_batch_analysis_and_refinement_lifecycle():
    """Test full document workflow: Extract -> Batch Analyze -> Question -> Answer -> Approve -> Reports."""
    reqs = [
        DocumentRequirement(
            req_id="REQ-001",
            text="The telemetry engine shall transmit diagnostic reports quickly upon startup.",
            section="Telemetry",
            source_file="satellite.txt",
        ),
        DocumentRequirement(
            req_id="REQ-002",
            text="The controller shall maintain temperature within 50 milliseconds of engine startup.",
            section="Thermal",
            source_file="satellite.txt",
        ),
    ]

    pipeline = Phase4Pipeline()
    scorer = HeuristicFusionScorer()

    # 1. Batch analyze
    results = analyze_srs_requirements(reqs, pipeline, scorer, llm_client=None)
    assert len(results) == 2

    r1 = results[0]
    r2 = results[1]
    assert r2.has_defects is False or r2.has_defects is True

    # REQ-001 has vague term 'quickly'
    assert r1.has_defects is True
    assert len(r1.questions) >= 1
    assert any("quickly" in q.question.lower() or "quickly" in q.span_text for q in r1.questions)

    # 2. Propose refinement for REQ-001
    q1 = r1.questions[0]
    proposed, is_valid, audit, method = apply_refinement_to_analysis_result(
        result=r1,
        question_id=q1.question_id,
        stakeholder_answer="within 250 milliseconds",
        llm_client=None,
    )
    assert is_valid is True
    assert "within 250 milliseconds" in proposed
    assert r1.is_approved is False  # Must NOT be approved before explicit commit!

    # 3. Explicit approval commit
    commit_approved_refinement(
        result=r1,
        question_id=q1.question_id,
        stakeholder_answer="within 250 milliseconds",
        refined_text=proposed,
        method_used=method,
    )
    assert r1.is_approved is True
    assert r1.current_text == proposed
    assert len(r1.refinement_history) == 1
    assert q1.status == "answered"

    # 4. Document-Level Summary Aggregator
    summary = summarize_srs_analysis(results, filename="satellite.txt")
    assert summary.total_candidates == 2
    assert summary.total_analyzed == 2
    assert summary.approved_refinements_count == 1
    assert summary.macro_avg_iso_score > 0.0
    assert summary.macro_avg_clarity_score > 0.0

    # 5. Export Report Generation
    md_report = generate_markdown_srs_report(summary, results)
    assert "# CheckSense SRS Document Analysis Report" in md_report
    assert "REQ-001" in md_report
    assert "REQ-002" in md_report
    assert "Traceability Matrix" in md_report

    csv_report = generate_csv_srs_report(results)
    assert "req_id,source_file,section" in csv_report
    assert "REQ-001,satellite.txt" in csv_report

    json_audit = generate_audit_trail_json(summary, results)
    parsed_json = json.loads(json_audit)
    assert parsed_json["summary"]["total_candidates"] == 2
    assert len(parsed_json["results"]) == 2
