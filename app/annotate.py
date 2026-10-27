"""CheckSense Human Annotation Tool (Phase 3).

Streamlit application for human gold annotation, pilot double-annotation,
and verification of candidate requirement gaps per MASTER_SPEC.md Section 4.

Binding Integrity Rules:
1. Sequestered Held-Out Test Set: Test documents and test-split requirements
   CANNOT be loaded in this annotation workflow.
2. Multi-Gap Support: Allows adding and editing multiple gap rows per requirement
   without replacing or deleting previously saved gaps.
3. Clean vs. Gap Exclusivity: A clean requirement (has_gap=0) and gap rows (has_gap=1)
   can NEVER coexist for the same requirement.
4. Validation Before Verification:
   - For ambiguity and incompleteness, span_text must be a non-empty, exact substring
     of the requirement text.
   - Clarification question must end with exactly one '?' and contain no other question marks.
   - Block save immediately if validation fails.
5. Human Authority: Only explicit human confirmation sets label_status='verified'.
   AI/LLM suggestions always remain marked [DRAFT].
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

from checksense.annotation import (
    TAXONOMY,
    load_annotation_sheet,
    save_annotation_rows,
    validate_requirement_annotations,
)
from checksense.baseline import detect_rule_gaps
from checksense.frame import extract_requirement_frame
from checksense.sample import load_annotation_workflow_pool


def main():
    st.set_page_config(
        page_title="CheckSense Gold Annotation Tool",
        page_icon="🔍",
        layout="wide",
    )

    st.title("🔍 CheckSense: Requirement Gap Annotation & Verification Tool")
    st.markdown(
        "**Phase 3 Protocol:** Human-in-the-loop gold annotation. "
        "AI suggestions are tagged `[DRAFT]`. Only explicit human verification sets `label_status='verified'`."
    )

    # Sidebar: Session Settings & Progress
    with st.sidebar:
        st.header("⚙️ Annotator Configuration")
        annotator_id = st.text_input(
            "Annotator Identifier",
            value=st.session_state.get("annotator_id", "rater_1"),
            key="annotator_input",
        )
        st.session_state["annotator_id"] = annotator_id

        # Target dataset selector
        st.subheader("📁 Dataset Selection")
        source_mode = st.radio(
            "Workflow Queue",
            ["Pilot Sample (50 reqs)", "Development Pool (Dev Split Only)", "Custom Path"],
        )
        if source_mode == "Pilot Sample (50 reqs)":
            source_file = Path("data/gold/pilot_sample.csv")
        elif source_mode == "Development Pool (Dev Split Only)":
            source_file = Path("data/gold/dev_pool.jsonl")
        else:
            custom_input = st.text_input("Custom Queue Path", "data/gold/pilot_sample.csv")
            source_file = Path(custom_input)

        target_file = Path(
            st.text_input("Save Target CSV", "data/gold/annotations.csv")
        )

        # Load requirements using sequestering loader
        try:
            requirements = load_annotation_workflow_pool(source_file)
        except PermissionError as e:
            st.error(f"🚫 {e}")
            return
        except Exception as e:
            st.error(f"Error loading queue: {e}")
            return

        existing_annots = load_annotation_sheet(target_file)

        st.markdown("---")
        st.subheader("📊 Queue Progress")
        n_total = len(requirements)
        n_reviewed = len(existing_annots)
        n_verified = sum(
            1 for rows in existing_annots.values()
            if all(r.get("label_status") == "verified" for r in rows if r)
        )
        n_draft = sum(
            1 for rows in existing_annots.values()
            if any(r.get("label_status") == "draft" for r in rows)
        )
        n_clean = sum(
            1 for rows in existing_annots.values()
            if any(r.get("has_gap") in ("0", "false", "False") for r in rows)
        )

        st.metric("Total in Queue", n_total)
        st.metric("Verified (Confirmed)", n_verified)
        st.metric("Draft (Pending)", n_draft)
        st.metric("Clean (No Gap)", n_clean)
        if n_total > 0:
            st.progress(min(1.0, n_reviewed / n_total))

    if not requirements:
        st.warning(
            f"No accessible development requirements found in `{source_file}`. "
            "Run `python -m checksense.cli sample` to generate the dev pool and pilot sheets."
        )
        return

    # Navigation Controls
    col_nav1, col_nav2, col_nav3 = st.columns([2, 2, 4])
    with col_nav1:
        req_indices = list(range(len(requirements)))
        selected_idx = st.selectbox(
            "Select Requirement",
            options=req_indices,
            format_func=lambda i: (
                f"#{i+1} [{requirements[i]['req_id']}] ("
                f"{'VERIFIED' if all(r.get('label_status') == 'verified' for r in existing_annots.get(requirements[i]['req_id'], [])) and existing_annots.get(requirements[i]['req_id']) else 'UNREVIEWED'})"
            ),
            index=st.session_state.get("current_idx", 0),
        )
        st.session_state["current_idx"] = selected_idx

    req = requirements[selected_idx]
    req_id = req["req_id"]
    doc_id = req["doc_id"]
    req_text = req["text"]
    current_saved = existing_annots.get(req_id, [])

    with col_nav2:
        if st.button("⬅️ Previous") and selected_idx > 0:
            st.session_state["current_idx"] = selected_idx - 1
            st.rerun()
        if st.button("Next ➡️") and selected_idx < len(requirements) - 1:
            st.session_state["current_idx"] = selected_idx + 1
            st.rerun()

    with col_nav3:
        status_badge = "⚪ Unreviewed"
        if current_saved:
            if all(r.get("label_status") == "verified" for r in current_saved):
                status_badge = "🟢 VERIFIED by Human"
            elif any(r.get("label_status") == "draft" for r in current_saved):
                status_badge = "🟡 DRAFT (Awaiting Human Review)"
        st.markdown(f"### Current Status: {status_badge}")

    # Main Card: Requirement Display
    st.markdown("---")
    st.markdown(f"#### **Requirement ID:** `{req_id}` &nbsp;|&nbsp; **Document:** `{doc_id}`")
    st.info(f"**Text:** {req_text}")

    # Frame Extractor Analysis & Baseline Suggestions
    with st.expander("🔬 Automated Analysis & Semantic Frames", expanded=False):
        c_frame, c_b1 = st.columns(2)
        with c_frame:
            st.markdown("##### Extracted Semantic Frame (spaCy)")
            frame = extract_requirement_frame(req_text)
            st.json({
                "actor": frame.actor,
                "modal": frame.modal,
                "action": frame.action,
                "object": frame.object,
                "condition": frame.condition,
                "quantity": frame.quantity,
                "exception": frame.exception,
                "is_passive": frame.is_passive,
                "missing_slots": frame.missing_slots,
            })
        with c_b1:
            st.markdown("##### Baseline B1 Rule Suggestions (`[DRAFT]`)")
            rule_gaps = detect_rule_gaps(req_text, frame=frame)
            if rule_gaps:
                for rg in rule_gaps:
                    st.warning(
                        f"**[DRAFT SUGGESTION]** `{rg.gap_type} / {rg.subtype}`\n\n"
                        f"- **Span:** `\"{rg.span_text}\"`\n"
                        f"- **Severity:** {rg.severity}\n"
                        f"- **Explanation:** {rg.explanation}\n"
                        f"- **Question:** {rg.question}"
                    )
            else:
                st.success("No baseline rule gaps flagged.")

    # Human Annotation Form
    st.markdown("---")
    st.subheader("✍️ Human Annotation Editor")

    # Determine whether current saved state is clean or has gaps
    is_currently_clean = (
        bool(current_saved)
        and len(current_saved) == 1
        and str(current_saved[0].get("has_gap", "")).strip().lower() in ("0", "false")
    )
    decision = st.radio(
        "Annotation Decision for this Requirement:",
        ["Clean (No Quality Gaps)", "Defective (One or More Gaps)"],
        index=0 if is_currently_clean or (not current_saved) else 1,
        horizontal=True,
    )

    if decision == "Clean (No Quality Gaps)":
        clean_notes = st.text_input(
            "Notes / Verification Justification",
            value=current_saved[0].get("notes", "") if is_currently_clean else "Requirement is clear, complete, and verifiable.",
        )
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            if st.button("💾 Save as DRAFT (Clean)", use_container_width=True):
                clean_row = [{
                    "req_id": req_id,
                    "doc_id": doc_id,
                    "text": req_text,
                    "has_gap": "0",
                    "gap_type": "",
                    "subtype": "",
                    "span_text": "",
                    "severity": "",
                    "explanation": "",
                    "question": "",
                    "stakeholder_answer": "",
                    "refined_text": "",
                    "annotator": annotator_id,
                    "label_status": "draft",
                    "notes": clean_notes,
                }]
                save_annotation_rows(target_file, req_id, clean_row, req_text=req_text, for_verification=False)
                st.success("Saved as clean [DRAFT]. Any previous gaps replaced.")
                st.rerun()
        with col_c2:
            if st.button("✅ Confirm & VERIFY Clean Requirement", type="primary", use_container_width=True):
                clean_row = [{
                    "req_id": req_id,
                    "doc_id": doc_id,
                    "text": req_text,
                    "has_gap": "0",
                    "gap_type": "",
                    "subtype": "",
                    "span_text": "",
                    "severity": "",
                    "explanation": "",
                    "question": "",
                    "stakeholder_answer": "",
                    "refined_text": "",
                    "annotator": annotator_id,
                    "label_status": "verified",
                    "notes": clean_notes,
                }]
                save_annotation_rows(target_file, req_id, clean_row, req_text=req_text, for_verification=True)
                st.success("Confirmed and verified clean requirement!")
                st.rerun()

    else:
        # Multi-Gap Workflow
        session_key = f"gaps_{req_id}"
        if session_key not in st.session_state:
            # Initialize from existing saved gaps (if any)
            saved_gaps = [
                r for r in current_saved
                if str(r.get("has_gap", "")).strip().lower() in ("1", "true") or bool(r.get("gap_type"))
            ]
            if saved_gaps:
                st.session_state[session_key] = [dict(g) for g in saved_gaps]
            elif rule_gaps:
                # Pre-fill draft from B1 rule suggestions
                st.session_state[session_key] = [
                    {
                        "req_id": req_id,
                        "doc_id": doc_id,
                        "text": req_text,
                        "has_gap": "1",
                        "gap_type": rg.gap_type,
                        "subtype": rg.subtype,
                        "span_text": rg.span_text,
                        "severity": str(rg.severity),
                        "explanation": rg.explanation,
                        "question": rg.question,
                        "stakeholder_answer": "",
                        "refined_text": "",
                        "annotator": annotator_id,
                        "label_status": "draft",
                        "notes": "Imported from Baseline B1 (Draft)",
                    }
                    for rg in rule_gaps
                ]
            else:
                # Initialize empty gap row
                st.session_state[session_key] = [{
                    "req_id": req_id,
                    "doc_id": doc_id,
                    "text": req_text,
                    "has_gap": "1",
                    "gap_type": "ambiguity",
                    "subtype": "vague_term",
                    "span_text": "",
                    "severity": "2",
                    "explanation": "",
                    "question": "",
                    "stakeholder_answer": "",
                    "refined_text": "",
                    "annotator": annotator_id,
                    "label_status": "draft",
                    "notes": "",
                }]

        current_gaps: list[dict[str, Any]] = st.session_state[session_key]

        st.markdown(f"**Identified Gaps ({len(current_gaps)} total):**")

        # Edit each gap in an expander or container
        for idx, gap in enumerate(current_gaps):
            with st.container(border=True):
                st.markdown(f"##### Gap #{idx + 1}: `{gap.get('gap_type', '')} / {gap.get('subtype', '')}`")
                col_c, col_s, col_sev, col_del = st.columns([2, 2, 2, 1])

                with col_c:
                    curr_c = gap.get("gap_type", "ambiguity")
                    c_idx = ["ambiguity", "incompleteness", "implicit"].index(curr_c) if curr_c in ["ambiguity", "incompleteness", "implicit"] else 0
                    new_class = st.selectbox(
                        "Class",
                        options=["ambiguity", "incompleteness", "implicit"],
                        index=c_idx,
                        key=f"c_{req_id}_{idx}",
                    )
                    gap["gap_type"] = new_class

                with col_s:
                    subtypes = TAXONOMY[new_class]
                    curr_sub = gap.get("subtype", subtypes[0])
                    s_idx = subtypes.index(curr_sub) if curr_sub in subtypes else 0
                    new_sub = st.selectbox(
                        "Subtype",
                        options=subtypes,
                        index=s_idx,
                        key=f"sub_{req_id}_{idx}",
                    )
                    gap["subtype"] = new_sub

                with col_sev:
                    curr_sev = int(gap.get("severity", "2")) if str(gap.get("severity", "")).isdigit() else 2
                    new_sev = st.selectbox(
                        "Severity",
                        options=[1, 2, 3],
                        index=curr_sev - 1,
                        format_func=lambda s: f"Severity {s}",
                        key=f"sev_{req_id}_{idx}",
                    )
                    gap["severity"] = str(new_sev)

                with col_del:
                    st.write("")
                    st.write("")
                    if st.button("🗑️ Delete", key=f"del_{req_id}_{idx}"):
                        current_gaps.pop(idx)
                        st.session_state[session_key] = current_gaps
                        st.rerun()

                col_span, col_expl = st.columns(2)
                with col_span:
                    gap["span_text"] = st.text_input(
                        "Defective Span Text",
                        value=gap.get("span_text", ""),
                        key=f"span_{req_id}_{idx}",
                        help="Exact substring within the requirement text (for ambiguity and incompleteness).",
                    )
                with col_expl:
                    gap["explanation"] = st.text_input(
                        "Explanation",
                        value=gap.get("explanation", ""),
                        key=f"expl_{req_id}_{idx}",
                        help="Concise one-sentence rationale.",
                    )

                col_q, col_ans = st.columns(2)
                with col_q:
                    gap["question"] = st.text_input(
                        "Clarification Question",
                        value=gap.get("question", ""),
                        key=f"q_{req_id}_{idx}",
                        help="Question ending with exactly one '?'",
                    )
                with col_ans:
                    gap["stakeholder_answer"] = st.text_input(
                        "Stakeholder Answer (Optional)",
                        value=gap.get("stakeholder_answer", ""),
                        key=f"ans_{req_id}_{idx}",
                    )

                col_ref, col_notes = st.columns(2)
                with col_ref:
                    gap["refined_text"] = st.text_input(
                        "Refined Requirement (Optional)",
                        value=gap.get("refined_text", ""),
                        key=f"ref_{req_id}_{idx}",
                    )
                with col_notes:
                    gap["notes"] = st.text_input(
                        "Notes",
                        value=gap.get("notes", ""),
                        key=f"notes_{req_id}_{idx}",
                    )

        if st.button("➕ Add Another Gap to this Requirement"):
            current_gaps.append({
                "req_id": req_id,
                "doc_id": doc_id,
                "text": req_text,
                "has_gap": "1",
                "gap_type": "ambiguity",
                "subtype": "vague_term",
                "span_text": "",
                "severity": "2",
                "explanation": "",
                "question": "",
                "stakeholder_answer": "",
                "refined_text": "",
                "annotator": annotator_id,
                "label_status": "draft",
                "notes": "",
            })
            st.session_state[session_key] = current_gaps
            st.rerun()

        st.markdown("---")
        col_save_draft, col_save_verify = st.columns(2)
        with col_save_draft:
            if st.button(f"💾 Save All {len(current_gaps)} Gaps as DRAFT", use_container_width=True):
                for g in current_gaps:
                    g["label_status"] = "draft"
                    g["annotator"] = annotator_id
                    g["has_gap"] = "1"
                    g["req_id"] = req_id
                    g["doc_id"] = doc_id
                    g["text"] = req_text
                save_annotation_rows(target_file, req_id, current_gaps, req_text=req_text, for_verification=False)
                st.success(f"Saved {len(current_gaps)} gap(s) as [DRAFT].")
                st.rerun()

        with col_save_verify:
            if st.button(f"✅ Confirm & VERIFY All {len(current_gaps)} Gaps", type="primary", use_container_width=True):
                for g in current_gaps:
                    g["label_status"] = "verified"
                    g["annotator"] = annotator_id
                    g["has_gap"] = "1"
                    g["req_id"] = req_id
                    g["doc_id"] = doc_id
                    g["text"] = req_text

                # STRICT VALIDATION BEFORE VERIFICATION
                validation_errors = validate_requirement_annotations(
                    req_text=req_text,
                    rows=current_gaps,
                    for_verification=True,
                )
                if validation_errors:
                    st.error("🚫 Cannot verify requirement! Fix the following validation errors:")
                    for err in validation_errors:
                        st.error(f"• {err}")
                    return

                try:
                    save_annotation_rows(target_file, req_id, current_gaps, req_text=req_text, for_verification=True)
                    st.success(f"Confirmed and verified {len(current_gaps)} gap row(s)!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error saving verified rows: {e}")


if __name__ == "__main__":
    main()