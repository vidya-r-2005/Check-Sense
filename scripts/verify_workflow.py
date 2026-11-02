"""Verify the entire CheckSense workflow end-to-end."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from checksense.document import (
    extract_srs_document,
    analyze_srs_requirements,
    summarize_srs_analysis,
    apply_refinement_to_analysis_result,
    commit_approved_refinement,
    generate_markdown_srs_report,
    generate_csv_srs_report,
    generate_audit_trail_json,
)
from checksense.heads import Phase4Pipeline
from checksense.fusion import MLPFusionScorer

def main():
    print("=" * 65)
    print("CheckSense End-to-End Workflow Verification")
    print("=" * 65)

    pipeline = Phase4Pipeline(
        smell_model_path=REPO_ROOT / "results" / "smell_classifier" / "smell_classifier.joblib",
        span_model_path=REPO_ROOT / "results" / "span_tagger" / "span_tagger.joblib",
    )
    fusion = MLPFusionScorer.load(REPO_ROOT / "results" / "fusion_model" / "fusion_model.joblib")

    # 1. Ingestion
    sample_file = REPO_ROOT / "data" / "samples" / "Ground_Station_SRS.txt"
    txt = sample_file.read_bytes()
    reqs, warnings = extract_srs_document(txt, sample_file.name)
    print(f"[1] Ingestion: Extracted {len(reqs)} requirements from {sample_file.name}")
    assert len(reqs) == 8, f"Expected 8 requirements, got {len(reqs)}"

    # Also verify Library Management System sample ingestion
    lib_file = REPO_ROOT / "data" / "samples" / "Library_Management_System_SRS.txt"
    if lib_file.exists():
        lib_reqs, _ = extract_srs_document(lib_file.read_bytes(), lib_file.name)
        print(f"    Ingestion: Extracted {len(lib_reqs)} requirements from {lib_file.name}")
        assert len(lib_reqs) >= 16

    # 2. Batch Analysis
    results = analyze_srs_requirements(reqs, pipeline=pipeline, fusion_scorer=fusion)
    summary = summarize_srs_analysis(results, sample_file.name, warnings)
    print(f"[2] Analysis: Total={summary.total_analyzed}, Clean={summary.clean_requirements_count}, Defective={summary.defective_requirements_count}")
    assert summary.total_analyzed == 8

    # 3. Clarification Question
    req1 = next(r for r in results if r.requirement.req_id == "REQ-001")
    assert req1.questions, "REQ-001 should have a clarification question"
    q1 = req1.questions[0]
    print(f"[3] Grounded Clarification Q: '{q1.question}'")

    # 4. Refinement Proposal & Strict Numeric Guardrail
    prop_text, is_valid, msg, method = apply_refinement_to_analysis_result(
        result=req1,
        question_id=q1.question_id,
        stakeholder_answer="within 250 milliseconds",
    )
    print(f"[4] Refinement Proposed: '{prop_text}'")
    print(f"    Strict Numeric Audit: {'PASSED' if is_valid else 'FAILED'} (Reason: {msg})")
    assert is_valid, "Numeric preservation audit should pass"
    assert "250" in prop_text, "Refined text must contain 250"

    # 5. Stakeholder Governance Commit
    iso_before = req1.iso_score
    commit_approved_refinement(
        result=req1,
        question_id=q1.question_id,
        stakeholder_answer="within 250 milliseconds",
        refined_text=prop_text,
        method_used=method,
    )
    print(f"[5] Revision Committed: Approved={req1.is_approved}, ISO Delta={req1.iso_score - iso_before:+.2f}")
    assert req1.is_approved is True

    # 6. Traceability Matrix & Exports
    md = generate_markdown_srs_report(summary, results)
    csv = generate_csv_srs_report(results)
    json_audit = generate_audit_trail_json(summary, results)
    print(f"[6] Multi-Format Exports Verified:")
    print(f"    - Markdown Report: {len(md):,} characters")
    print(f"    - CSV Requirements Table: {len(csv):,} characters")
    print(f"    - Complete JSON Audit Trail: {len(json_audit):,} characters")

    print("=" * 65)
    print("[SUCCESS] All 6 workflow steps verified and working perfectly!")
    print("=" * 65)

if __name__ == "__main__":
    main()
