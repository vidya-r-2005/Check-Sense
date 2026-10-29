"""CheckSense Interactive Streamlit Application.

End-to-end requirements defect detection, candidate-level fusion,
grounded question formulation, and governed refinement engine.

Extended for complete SRS Document Analysis (.pdf, .docx, .txt),
batch defect analysis, candidate review & editing, transparent clarity scoring,
traceability matrices, and multi-format report exports.

Governed by docs/MASTER_SPEC.md.
"""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from checksense import (
    CandidateGap,
    HeuristicFusionScorer,
    MLPFusionScorer,
    Phase4Pipeline,
    StakeholderAnswer,
    apply_refinement_to_analysis_result,
    commit_approved_refinement,
    deduplicate_and_rank_candidates,
    evaluate_iso_29148,
    extract_requirement_frame,
    extract_srs_document,
    generate_audit_trail_json,
    generate_csv_srs_report,
    generate_gap_explanation_and_question,
    generate_markdown_srs_report,
    get_template_explanation_and_question,
    refine_requirement,
    summarize_srs_analysis,
    validate_numeric_preservation,
)
from checksense.document import (
    DocumentQualitySummary,
    RequirementAnalysisResult,
    analyze_srs_requirements,
)
from checksense.llm import OllamaClient

SAMPLE_REQUIREMENTS = [
    (
        "Ambiguity Example (Vague Term)",
        "The system shall process user transactions quickly upon receipt.",
    ),
    (
        "Incompleteness Example (Missing Condition & Threshold)",
        "The engine shall trigger an alert and shut down.",
    ),
    (
        "Implicit Constraint Example (Payment & Security)",
        "Upon subscription, the user shall enter their credit card number to confirm payment.",
    ),
    (
        "Clean Requirement (High Quality)",
        "The telemetry module shall transmit diagnostic packets within 50 milliseconds of engine startup.",
    ),
    (
        "Complex Requirement with Numbers",
        "The controller shall maintain temperature between 20 and 25 degrees Celsius for 60 seconds.",
    ),
]


@st.cache_resource
def load_pipeline() -> tuple[Phase4Pipeline, Any, bool]:
    """Load detector pipeline, fusion scorer, and probe Ollama availability."""
    smell_p = Path("results/smell_classifier/smell_classifier.joblib")
    span_p = Path("results/span_tagger/span_tagger.joblib")
    fusion_p = Path("results/fusion_model/fusion_model.joblib")

    pipeline = Phase4Pipeline(
        smell_model_path=smell_p if smell_p.exists() else None,
        span_model_path=span_p if span_p.exists() else None,
    )

    if fusion_p.exists():
        try:
            fusion_scorer = MLPFusionScorer.load(fusion_p)
        except Exception:
            fusion_scorer = HeuristicFusionScorer()
    else:
        fusion_scorer = HeuristicFusionScorer()

    ollama_client = OllamaClient(timeout=1.0)
    ollama_online = ollama_client.is_available()

    return pipeline, fusion_scorer, ollama_online


def highlight_spans(text: str, gaps: list[CandidateGap]) -> str:
    """Highlight problematic defect spans with HTML markup."""
    if not gaps:
        return html.escape(text)

    spans_to_mark: list[tuple[int, int, str, str]] = []
    for g in gaps:
        if g.start_char is not None and g.end_char is not None and g.start_char < g.end_char:
            spans_to_mark.append((g.start_char, g.end_char, g.gap_type, g.subtype))
        elif g.span_text and g.span_text in text:
            idx = text.find(g.span_text)
            spans_to_mark.append((idx, idx + len(g.span_text), g.gap_type, g.subtype))

    if not spans_to_mark:
        return html.escape(text)

    spans_to_mark.sort(key=lambda x: (x[0], -x[1]))

    out: list[str] = []
    cur_idx = 0

    for s_start, s_end, g_type, s_type in spans_to_mark:
        if s_start < cur_idx:
            continue
        out.append(html.escape(text[cur_idx:s_start]))

        color = "#ffebee" if g_type == "ambiguity" else ("#fff8e1" if g_type == "incompleteness" else "#e8f5e9")
        border = "#e53935" if g_type == "ambiguity" else ("#fbc02d" if g_type == "incompleteness" else "#43a047")

        marked_text = html.escape(text[s_start:s_end])
        out.append(
            f'<span style="background-color: {color}; border-bottom: 2px solid {border}; '
            f'padding: 2px 4px; border-radius: 3px; font-weight: 500;" '
            f'title="[{g_type}] {s_type}">{marked_text}</span>'
        )
        cur_idx = s_end

    out.append(html.escape(text[cur_idx:]))
    return "".join(out)


def init_session_state():
    """Initialize session state keys for document analysis."""
    if "uploaded_filename" not in st.session_state:
        st.session_state.uploaded_filename = ""
    if "extracted_requirements" not in st.session_state:
        st.session_state.extracted_requirements = []
    if "extraction_warnings" not in st.session_state:
        st.session_state.extraction_warnings = []
    if "analysis_results" not in st.session_state:
        st.session_state.analysis_results = []
    if "document_summary" not in st.session_state:
        st.session_state.document_summary = None
    if "is_analyzed" not in st.session_state:
        st.session_state.is_analyzed = False


def main():
    st.set_page_config(
        page_title="CheckSense — Requirements Defect Analysis Studio",
        page_icon="🔎",
        layout="wide",
    )

    init_session_state()
    pipeline, fusion_scorer, ollama_online = load_pipeline()
    llm_client = OllamaClient(timeout=3.0) if ollama_online else None

    # Sidebar: System & Environment Status
    with st.sidebar:
        st.header("⚙️ CheckSense Engine")
        st.markdown(
            f"- **Head 4a (Smell Classifier):** `{'Trained LogReg' if pipeline.smell_model else 'Rule Lexicon'}`\n"
            f"- **Head 4a (BIO Span Tagger):** `{'Trained Linear/CRF' if pipeline.span_tagger else 'Lexicon Span'}`\n"
            f"- **Head 4b (Completeness):** `Active (Dependency Frame)`\n"
            f"- **Head 4c (Implicit Constraints):** `Active (Domain Ontology)`\n"
            f"- **Phase 5 Fusion Scorer:** `{'MLP Classifier' if isinstance(fusion_scorer, MLPFusionScorer) else 'Heuristic Scorer'}`\n"
            f"- **Local LLM (Ollama):** `{'🟢 Online (qwen2.5:7b)' if ollama_online else '⚪ Offline (Deterministic Fallback)'}`"
        )
        st.divider()
        st.caption(
            "**Scientific Governance:** Held-out test pool (`data/gold/test_pool.jsonl`) remains 100% sequestered and sealed."
        )

    st.title("🔎 CheckSense: SRS Document Defect Analysis & Refinement Engine")
    st.markdown(
        "**Autonomous Multi-Head Detection, Problematic Span Localization, Candidate-Level Fusion, and Governed Refinement.**  \n"
        "*Governed by [MASTER_SPEC.md](docs/MASTER_SPEC.md). All AI refinements require explicit stakeholder review and approval.*"
    )

    tab_doc, tab_single = st.tabs([
        "📑 SRS Document Analysis (Primary)",
        "🔬 Single Requirement Analysis",
    ])

    # ========================================================================
    # TAB 1: SRS DOCUMENT ANALYSIS (PRIMARY WORKFLOW)
    # ========================================================================
    with tab_doc:
        st.subheader("1. Upload SRS Document")
        st.markdown(
            "Upload a complete Software Requirements Specification (SRS) in **PDF (.pdf)**, "
            "**Word (.docx)**, or **Plain Text (.txt)** format. The parser preserves section headings, "
            "requirement IDs, page numbers, and formatting."
        )

        col_up1, col_up2 = st.columns([3, 1])
        with col_up1:
            uploaded_file = st.file_uploader(
                "Choose an SRS Document:",
                type=["pdf", "docx", "txt"],
                help="Supported formats: .pdf, .docx, .txt. Scanned image-only PDFs require OCR preprocessing.",
            )

        with col_up2:
            st.info(
                "**Format Information:**\n"
                "- **PDF:** Text extracted per page with page tracking\n"
                "- **DOCX:** Paragraphs, headings & tables extracted\n"
                "- **TXT:** Segmented by ID, bullets, & section headers"
            )

        # Handle Document Extraction
        if uploaded_file is not None and uploaded_file.name != st.session_state.uploaded_filename:
            file_bytes = uploaded_file.read()
            filename = uploaded_file.name

            with st.spinner(f"Extracting requirements from '{filename}'..."):
                raw_reqs, warnings = extract_srs_document(file_bytes, filename=filename)

            st.session_state.uploaded_filename = filename
            st.session_state.extracted_requirements = raw_reqs
            st.session_state.extraction_warnings = warnings
            st.session_state.is_analyzed = False
            st.session_state.analysis_results = []
            st.session_state.document_summary = None

        # Display Extraction Warnings
        if st.session_state.extraction_warnings:
            for w in st.session_state.extraction_warnings:
                st.warning(f"⚠️ {w}")

        # Candidate Review & Editing Section
        if st.session_state.extracted_requirements:
            st.divider()
            st.subheader("2. Review & Edit Extracted Candidate Requirements")
            st.markdown(
                f"Extracted **{len(st.session_state.extracted_requirements)}** candidate statements from "
                f"`{st.session_state.uploaded_filename}`. Review, edit, or adjust before running full defect analysis."
            )

            # Review table data
            review_rows = []
            for idx, req in enumerate(st.session_state.extracted_requirements):
                review_rows.append(
                    {
                        "#": idx + 1,
                        "Req ID": req.req_id,
                        "Section": req.section,
                        "Page": req.page_num or "-",
                        "Requirement Text": req.text,
                        "Status": "⚠️ Uncertain (Non-normative)" if req.is_uncertain else "Normative",
                    }
                )

            st.dataframe(pd.DataFrame(review_rows), use_container_width=True, height=260)

            col_act1, col_act2 = st.columns([1, 4])
            run_analysis_clicked = col_act1.button(
                "🚀 Analyze SRS Document",
                type="primary",
                use_container_width=True,
            )

            if run_analysis_clicked:
                with st.spinner("Executing Multi-Head Defect Detection, Fusion, and ISO 29148 Assessment on all requirements..."):
                    results = analyze_srs_requirements(
                        requirements=st.session_state.extracted_requirements,
                        pipeline=pipeline,
                        fusion_scorer=fusion_scorer,
                        llm_client=llm_client,
                    )
                    summary = summarize_srs_analysis(
                        results=results,
                        filename=st.session_state.uploaded_filename,
                        extraction_warnings=st.session_state.extraction_warnings,
                    )

                st.session_state.analysis_results = results
                st.session_state.document_summary = summary
                st.session_state.is_analyzed = True
                st.success(f"Analysis complete for {len(results)} requirements!")

        # Results Dashboard
        if st.session_state.is_analyzed and st.session_state.document_summary:
            summary: DocumentQualitySummary = st.session_state.document_summary
            results: list[RequirementAnalysisResult] = st.session_state.analysis_results

            st.divider()
            st.header("📊 Complete SRS Analysis Dashboard")

            # Section A: Document Overview Metrics
            st.subheader("A. Document Overview")
            col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)
            col_m1.metric("Analyzed Requirements", summary.total_analyzed)
            col_m2.metric("Clean Requirements", summary.clean_requirements_count, delta="Zero Defects")
            col_m3.metric("Defective Requirements", summary.defective_requirements_count, delta="Needs Clarification", delta_color="inverse")
            col_m4.metric("Clean Ratio", f"{summary.clean_ratio:.1%}", help="Percentage of requirements with zero defects (non-double-counted).")
            col_m5.metric("Total Defect Gaps", summary.total_detected_gaps)

            col_q1, col_q2, col_q3, col_q4 = st.columns(4)
            col_q1.metric("Macro-Avg ISO 29148", f"{summary.macro_avg_iso_score:.2f} / 1.00", help="Document-wide average 4-characteristic conformance index.")
            col_q2.metric("Macro-Avg Clarity Score", f"{summary.macro_avg_clarity_score:.2f} / 1.00", help="Document-wide average transparent penalty heuristic.")
            col_q3.metric("Generated Questions", summary.total_questions_count)
            col_q4.metric("Approved Refinements", f"{summary.approved_refinements_count} / {summary.defective_requirements_count}")

            # Defect Distribution Breakdown
            st.markdown("### Defect Category Distribution")
            cat_df = pd.DataFrame(
                [
                    {"Category": "Ambiguity (Head 4a)", "Count": summary.category_counts.get("ambiguity", 0), "Description": "Vague terms, imprecise quantifiers, coordination ambiguity"},
                    {"Category": "Incompleteness (Head 4b)", "Count": summary.category_counts.get("incompleteness", 0), "Description": "Missing actors, omitted conditions, missing thresholds, passive voice"},
                    {"Category": "Implicit Constraints (Head 4c)", "Count": summary.category_counts.get("implicit", 0), "Description": "Unstated security, data privacy, payment compliance, audit trails"},
                ]
            )
            st.dataframe(cat_df, use_container_width=True)

            # Section B: Requirement Explorer
            st.divider()
            st.subheader("B. Requirement Explorer")
            st.markdown("Search, filter, and inspect highlighted defect spans across all requirements.")

            col_f1, col_f2, col_f3 = st.columns([2, 1, 1])
            search_query = col_f1.text_input("🔍 Search by Requirement ID or Text:", placeholder="e.g. telemetry, REQ-001")
            filter_cat = col_f2.selectbox("Filter by Defect Category:", options=["All", "Ambiguity", "Incompleteness", "Implicit", "Clean (No Gaps)"])
            sort_by = col_f3.selectbox("Sort by:", options=["Requirement Order", "Defect Count (High to Low)", "Clarity Score (Low to High)", "ISO 29148 Score (Low to High)"])

            # Filter & Sort
            filtered_results = list(results)
            if search_query.strip():
                q_low = search_query.strip().lower()
                filtered_results = [
                    r for r in filtered_results
                    if q_low in r.requirement.req_id.lower() or q_low in r.current_text.lower() or q_low in r.requirement.section.lower()
                ]

            if filter_cat == "Clean (No Gaps)":
                filtered_results = [r for r in filtered_results if not r.has_defects]
            elif filter_cat != "All":
                filtered_results = [r for r in filtered_results if filter_cat.lower() in [c.lower() for c in r.defect_categories]]

            if sort_by == "Defect Count (High to Low)":
                filtered_results.sort(key=lambda r: r.defect_count, reverse=True)
            elif sort_by == "Clarity Score (Low to High)":
                filtered_results.sort(key=lambda r: r.clarity_heuristic)
            elif sort_by == "ISO 29148 Score (Low to High)":
                filtered_results.sort(key=lambda r: r.iso_score)

            st.caption(f"Showing **{len(filtered_results)}** of **{len(results)}** requirements:")

            for r in filtered_results:
                status_icon = "✅" if r.is_approved else ("⚠️" if r.has_defects else "🟢")
                status_text = "Approved Revision" if r.is_approved else ("Defects Detected" if r.has_defects else "Clean Requirement")
                exp_title = f"{status_icon} [{r.requirement.req_id}] {r.requirement.section} — {status_text} (Gaps: {r.defect_count}, Clarity: {r.clarity_heuristic:.2f})"

                with st.expander(exp_title, expanded=False):
                    col_det1, col_det2 = st.columns([3, 1])
                    with col_det1:
                        st.markdown("**Requirement Text with Localized Defect Spans:**")
                        highlighted_html = highlight_spans(r.current_text, r.fused_gaps)
                        st.markdown(
                            f'<div style="padding: 10px; border: 1px solid #ddd; border-radius: 5px; '
                            f'background-color: #fafafa; font-size: 1.05em; line-height: 1.5;">{highlighted_html}</div>',
                            unsafe_allow_html=True,
                        )

                    with col_det2:
                        st.markdown("**Scores & Characteristics:**")
                        st.write(f"- Clarity Score: `{r.clarity_heuristic:.2f} / 1.00`")
                        st.write(f"- ISO 29148: `{r.iso_score:.2f} / 1.00`")
                        st.write(f"- Singular: `{'Yes' if r.iso_details.get('is_singular') else 'No'}`")
                        st.write(f"- Normative: `{'Yes' if r.iso_details.get('is_normative') else 'No'}`")

                    if r.fused_gaps:
                        st.markdown("#### Detected Defect Gaps")
                        gap_rows = []
                        for rank, g in enumerate(r.fused_gaps, start=1):
                            gap_rows.append(
                                {
                                    "Rank": rank,
                                    "Category": g.gap_type.upper(),
                                    "Subtype": g.subtype,
                                    "Span": f"'{g.span_text}'" if g.span_text else "(entire requirement)",
                                    "Severity": f"Level {g.severity}" + (" (Critical)" if g.severity == 3 else (" (Rework)" if g.severity == 2 else " (Minor)")),
                                    "Confidence": f"{g.probability:.1%}",
                                    "Explanation": g.explanation,
                                }
                            )
                        st.dataframe(pd.DataFrame(gap_rows), use_container_width=True)

            # Section C: Clarification & Governed Refinement Workspace
            st.divider()
            st.subheader("C. Clarification & Refinement Workspace")
            st.markdown(
                "Address detected gaps by providing stakeholder clarifications. Propose audited rewrites, "
                "verify strict numeric preservation, and **explicitly approve revisions**."
            )

            reqs_with_questions = [r for r in results if r.questions]
            if not reqs_with_questions:
                st.success("✅ **Zero open clarification questions.** All requirements in this document satisfy normative standards.")
            else:
                req_choices = [f"[{r.requirement.req_id}] {r.requirement.section} ({len(r.questions)} questions)" for r in reqs_with_questions]
                sel_req_idx = st.selectbox("Select Requirement to Clarify:", range(len(req_choices)), format_func=lambda i: req_choices[i])
                active_req_result = reqs_with_questions[sel_req_idx]

                st.markdown(f"**Target Requirement (`{active_req_result.requirement.req_id}`):**")
                st.info(active_req_result.current_text)

                # Question Selection
                q_options = [
                    f"[{q.question_id}] {q.gap_type.upper()}: {q.subtype} — Status: {q.status.upper()}"
                    for q in active_req_result.questions
                ]
                sel_q_idx = st.selectbox("Select Clarification Question:", range(len(q_options)), format_func=lambda i: q_options[i])
                active_q = active_req_result.questions[sel_q_idx]

                st.markdown(f"**Diagnostic Context:** *{active_q.explanation}*")
                st.warning(f"**Targeted Question:** ### {active_q.question}")
                st.caption(f"Source: {active_q.source} | Status: `{active_q.status}`")

                answer_input = st.text_input(
                    "Enter Stakeholder Answer:",
                    value=active_q.stakeholder_answer,
                    placeholder="e.g. within 250 milliseconds / using AES-256 encryption",
                    key=f"ans_input_{active_q.question_id}",
                )

                col_prop1, col_prop2 = st.columns([1, 4])
                propose_clicked = col_prop1.button("Propose Refinement", type="secondary", key=f"btn_prop_{active_q.question_id}")

                if answer_input.strip() or propose_clicked:
                    proposed_text, is_num_valid, audit_msg, method = apply_refinement_to_analysis_result(
                        result=active_req_result,
                        question_id=active_q.question_id,
                        stakeholder_answer=answer_input.strip(),
                        llm_client=llm_client,
                    )

                    st.markdown("#### Before vs. After Refinement Comparison")
                    col_b, col_a = st.columns(2)
                    with col_b:
                        st.markdown("**Current Requirement:**")
                        st.error(active_req_result.current_text)
                        st.caption(f"ISO 29148 Score: `{active_req_result.iso_score:.2f}`")

                    with col_a:
                        st.markdown("**Proposed Refinement:**")
                        st.success(proposed_text)
                        iso_prop = evaluate_iso_29148(proposed_text)
                        st.caption(f"Projected ISO 29148: `{iso_prop.score():.2f}` ({iso_prop.score() - active_req_result.iso_score:+.2f})")

                    # Audit Badges
                    col_aud1, col_aud2, col_aud3 = st.columns(3)
                    col_aud1.metric("Refinement Engine", method)
                    col_aud2.metric("Numeric Preservation", "PASSED" if is_num_valid else "VIOLATION", delta="Zero Tampering" if is_num_valid else "Audit Failed")
                    col_aud3.metric("Approval Status", "Approved" if active_req_result.is_approved else "Draft (Awaiting Approval)")

                    if not is_num_valid:
                        st.error(f"⚠️ **Numeric Validation Error:** {audit_msg}")

                    # Explicit Stakeholder Approval Commit Button
                    st.markdown("---")
                    st.markdown("**Stakeholder Governance Gate:**")
                    st.caption("AI-generated refinements are suggestions and are never finalized without explicit user confirmation.")

                    col_app1, col_app2 = st.columns([2, 3])
                    commit_clicked = col_app1.button(
                        "✅ Accept & Commit Revision",
                        type="primary",
                        key=f"commit_{active_q.question_id}",
                        help="Commits this revision into the requirement, marks the question as answered, and flags as approved.",
                    )

                    if commit_clicked:
                        commit_approved_refinement(
                            result=active_req_result,
                            question_id=active_q.question_id,
                            stakeholder_answer=answer_input.strip(),
                            refined_text=proposed_text,
                            method_used=method,
                        )
                        # Update summary counts
                        st.session_state.document_summary = summarize_srs_analysis(
                            results=results,
                            filename=st.session_state.uploaded_filename,
                            extraction_warnings=st.session_state.extraction_warnings,
                        )
                        st.success(f"Revision committed and approved for `{active_req_result.requirement.req_id}`!")
                        st.rerun()

            # Section D: Summary, Traceability Matrix & Exports
            st.divider()
            st.subheader("D. Summary & Requirement Traceability Matrix")

            trace_rows = []
            for r in results:
                cats = ", ".join(r.defect_categories) if r.defect_categories else "None"
                q_count = len(r.questions)
                ans_count = sum(1 for q in r.questions if q.status == "answered")
                trace_rows.append(
                    {
                        "Req ID": r.requirement.req_id,
                        "Section": r.requirement.section,
                        "Page": r.requirement.page_num or "-",
                        "Defect Categories": cats,
                        "Total Gaps": r.defect_count,
                        "Questions": f"{ans_count}/{q_count} Answered",
                        "Current Text": r.current_text,
                        "Approval": "✅ Approved" if r.is_approved else ("🟢 Clean" if not r.has_defects else "⚠️ Unapproved"),
                    }
                )
            st.dataframe(pd.DataFrame(trace_rows), use_container_width=True)

            # Exportable Reports
            st.markdown("### 📥 Export SRS Analysis Reports")
            col_ex1, col_ex2, col_ex3 = st.columns(3)

            md_report_content = generate_markdown_srs_report(summary, results)
            col_ex1.download_button(
                "📥 Download Markdown Report (.md)",
                data=md_report_content,
                file_name=f"checksense_srs_report_{Path(st.session_state.uploaded_filename).stem}.md",
                mime="text/markdown",
                use_container_width=True,
            )

            csv_report_content = generate_csv_srs_report(results)
            col_ex2.download_button(
                "📥 Download CSV Requirements Table (.csv)",
                data=csv_report_content,
                file_name=f"checksense_requirements_{Path(st.session_state.uploaded_filename).stem}.csv",
                mime="text/csv",
                use_container_width=True,
            )

            json_audit_content = generate_audit_trail_json(summary, results)
            col_ex3.download_button(
                "📥 Download Full JSON Audit Trail (.json)",
                data=json_audit_content,
                file_name=f"checksense_audit_trail_{Path(st.session_state.uploaded_filename).stem}.json",
                mime="application/json",
                use_container_width=True,
            )

    # ========================================================================
    # TAB 2: SINGLE REQUIREMENT ANALYSIS (PRESERVED MODE)
    # ========================================================================
    with tab_single:
        st.subheader("🔬 Single Requirement Analysis & Frame Inspection")
        st.markdown(
            "Paste or select an individual requirement statement to run multi-head gap detection, "
            "BIO span highlighting, and question formulation."
        )

        sample_choice = st.selectbox(
            "Select an authentic demonstration sample:",
            options=["-- Custom Input --"] + [s[0] for s in SAMPLE_REQUIREMENTS],
            key="single_sample_sel",
        )

        initial_text = ""
        if sample_choice != "-- Custom Input --":
            for name, s_text in SAMPLE_REQUIREMENTS:
                if name == sample_choice:
                    initial_text = s_text
                    break

        req_input = st.text_area(
            "Enter a Software Functional Requirement (in English):",
            value=initial_text,
            height=90,
            placeholder="e.g. The telemetry engine shall transmit diagnostic reports quickly upon receipt.",
            key="single_req_input",
        )

        analyze_single_clicked = st.button("🔍 Analyze Single Requirement", type="primary", key="btn_single_analyze")

        req_text_single = req_input.strip()
        if req_text_single and (analyze_single_clicked or sample_choice != "-- Custom Input --"):
            frame = extract_requirement_frame(req_text_single)

            with st.spinner("Analyzing requirement..."):
                raw_cands = pipeline.detect_all_gaps(req_text_single, frame=frame)
                smell_prob_s = 0.5
                if pipeline.smell_model:
                    try:
                        smell_prob_s = float(pipeline.smell_model.predict_smell_probability([req_text_single])[0])
                    except Exception:
                        smell_prob_s = 0.5

                fused_s = deduplicate_and_rank_candidates(
                    candidates=raw_cands,
                    scorer=fusion_scorer,
                    req_text=req_text_single,
                    frame=frame,
                    smell_prob=smell_prob_s,
                )
                iso_s = evaluate_iso_29148(req_text_single, detected_gaps=fused_s)

            st.markdown("**Requirement with Pinpointed Defect Spans:**")
            highlighted_s = highlight_spans(req_text_single, fused_s)
            st.markdown(
                f'<div style="padding: 12px; border: 1px solid #ddd; border-radius: 5px; '
                f'background-color: #fafafa; font-size: 1.1em; line-height: 1.6;">{highlighted_s}</div>',
                unsafe_allow_html=True,
            )

            col_ss1, col_ss2, col_ss3, col_ss4 = st.columns(4)
            col_ss1.metric("Detected Gaps", len(fused_s))
            col_ss2.metric("Smell Probability", f"{smell_prob_s:.1%}")
            col_ss3.metric("ISO 29148 Score", f"{iso_s.score():.2f} / 1.00")
            col_ss4.metric("Status", "Defects Detected" if fused_s else "Clean Requirement")

            if fused_s:
                st.markdown("### Ranked Defect Gaps")
                g_rows = []
                for rank, g in enumerate(fused_s, start=1):
                    g_rows.append(
                        {
                            "Rank": rank,
                            "Class": g.gap_type.upper(),
                            "Subtype": g.subtype,
                            "Span": f"'{g.span_text}'" if g.span_text else "(entire requirement)",
                            "Severity": f"Level {g.severity}",
                            "Confidence": f"{g.probability:.1%}",
                        }
                    )
                st.dataframe(pd.DataFrame(g_rows), use_container_width=True)

                # Single Refinement Section
                top_gap = fused_s[0]
                if llm_client and llm_client.is_available():
                    try:
                        expl_s, q_s = generate_gap_explanation_and_question(
                            requirement_text=req_text_single,
                            gap_type=top_gap.gap_type,
                            subtype=top_gap.subtype,
                            span_text=top_gap.span_text,
                            llm_client=llm_client,
                        )
                    except Exception:
                        expl_s, q_s = get_template_explanation_and_question(top_gap.gap_type, top_gap.subtype, top_gap.span_text)
                else:
                    expl_s, q_s = get_template_explanation_and_question(top_gap.gap_type, top_gap.subtype, top_gap.span_text)

                st.markdown(f"**Diagnostic Context:** *{expl_s}*")
                st.info(f"**Clarification Question:** ### {q_s}")

                single_ans = st.text_input("Enter Clarification Answer:", placeholder="e.g. within 100 milliseconds", key="single_ans_input")
                if single_ans.strip():
                    st_ans_s = StakeholderAnswer(
                        req_id="SINGLE_01",
                        gap_type=top_gap.gap_type,
                        subtype=top_gap.subtype,
                        span_text=top_gap.span_text,
                        question=q_s,
                        answer=single_ans.strip(),
                    )
                    refined_s, method_s = refine_requirement(req_text_single, st_ans_s, llm_client=llm_client)
                    is_valid_num, num_msg = validate_numeric_preservation(req_text_single, single_ans.strip(), refined_s)
                    iso_after_s = evaluate_iso_29148(refined_s)

                    col_sr1, col_sr2 = st.columns(2)
                    col_sr1.error(f"Original: {req_text_single}")
                    col_sr2.success(f"Refined: {refined_s}")

                    st.write(f"- Numeric Preservation: `{'PASSED' if is_valid_num else 'FAILED'}`")
                    st.write(f"- ISO 29148 Delta: `{iso_after_s.score() - iso_s.score():+.2f}`")


if __name__ == "__main__":
    main()
