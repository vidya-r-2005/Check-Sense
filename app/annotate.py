"""CheckSense Human Annotation Tool (Phase 3).

Streamlit application for human gold annotation, pilot double-annotation,
and verification of candidate requirement gaps per MASTER_SPEC.md Section 4.

Binding Rules:
1. LLM/AI suggestions are always marked [DRAFT] and saved as label_status='draft'
   until explicitly verified by a human rater.
2. Only human confirmation sets label_status='verified'.
3. Clean requirements are saved with has_gap=0.
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import streamlit as st

from checksense.baseline import detect_rule_gaps
from checksense.frame import extract_requirement_frame

# Taxonomy definitions
TAXONOMY: dict[str, list[str]] = {
    "ambiguity": [
        "vague_term",
        "vague_quantifier",
        "anaphora",
        "coordination",
    ],
    "incompleteness": [
        "missing_actor",
        "missing_condition",
        "missing_threshold",
        "missing_error_handling",
    ],
    "implicit": [
        "unstated_constraint",
    ],
}

ALL_SUBTYPES: list[str] = [sub for subs in TAXONOMY.values() for sub in subs]

ANNOTATION_COLUMNS = [
    "req_id",
    "doc_id",
    "text",
    "has_gap",
    "gap_type",
    "subtype",
    "span_text",
    "severity",
    "explanation",
    "question",
    "stakeholder_answer",
    "refined_text",
    "annotator",
    "label_status",
    "notes",
]


def load_requirements_pool(pool_path: Path) -> list[dict[str, Any]]:
    """Load requirements pool from JSONL or pilot CSV."""
    if not pool_path.exists():
        return []
    records: list[dict[str, Any]] = []
    if pool_path.suffix.lower() == ".jsonl":
        with open(pool_path, encoding="utf-8") as f:
            for line in f:
                line_str = line.strip()
                if line_str:
                    records.append(json.loads(line_str))
    elif pool_path.suffix.lower() == ".csv":
        with open(pool_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            seen: set[str] = set()
            for row in reader:
                req_id = row.get("req_id", "").strip()
                if req_id and req_id not in seen:
                    records.append({
                        "req_id": req_id,
                        "doc_id": row.get("doc_id", ""),
                        "text": row.get("text", ""),
                        "source_file": row.get("notes", ""),
                    })
                    seen.add(req_id)
    return records


def load_existing_annotations(csv_path: Path) -> dict[str, list[dict[str, str]]]:
    """Load existing annotation rows mapped by req_id."""
    if not csv_path.exists():
        return defaultdict(list)
    req_map: dict[str, list[dict[str, str]]] = defaultdict(list)
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            req_id = row.get("req_id", "").strip()
            if req_id:
                req_map[req_id].append(row)
    return req_map


def save_annotation_rows(
    csv_path: Path,
    req_id: str,
    new_rows: list[dict[str, Any]],
) -> None:
    """Safely update or insert annotation rows for a specific req_id."""
    existing_map = load_existing_annotations(csv_path)
    existing_map[req_id] = [
        {col: str(r.get(col, "")) for col in ANNOTATION_COLUMNS}
        for r in new_rows
    ]

    # Write out complete CSV atomically
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ANNOTATION_COLUMNS)
        writer.writeheader()
        for rid in sorted(existing_map.keys()):
            for row in existing_map[rid]:
                writer.writerow(row)


def main():
    st.set_page_config(
        page_title="CheckSense Gold Annotation Tool",
        page_icon="🔍",
        layout="wide",
    )

    st.title("🔍 CheckSense: Requirement Gap Annotation & Verification Tool")
    st.markdown(
        "**Phase 3 Protocol:** Human-in-the-loop gold annotation. "
        "AI suggestions are tagged `[DRAFT]` and require explicit human verification to confirm."
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

        # Target annotation CSV
        st.subheader("📁 File Paths")
        source_mode = st.radio(
            "Source Dataset",
            ["Pilot Sample (50 reqs)", "Full Sample Pool (600+ reqs)", "Custom Path"],
        )
        if source_mode == "Pilot Sample (50 reqs)":
            source_file = Path("data/gold/pilot_sample.csv")
        elif source_mode == "Full Sample Pool (600+ reqs)":
            source_file = Path("data/gold/sample_pool.jsonl")
        else:
            source_file = Path(st.text_input("Custom Source Path", "data/gold/pilot_sample.csv"))

        target_file = Path(
            st.text_input("Save Target CSV", "data/gold/annotations.csv")
        )

        requirements = load_requirements_pool(source_file)
        existing_annots = load_existing_annotations(target_file)

        st.markdown("---")
        st.subheader("📊 Verification Progress")
        n_total = len(requirements)
        n_reviewed = len(existing_annots)
        n_verified = sum(
            1 for rows in existing_annots.values()
            if any(r.get("label_status") == "verified" for r in rows)
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
            f"No requirements found in `{source_file}`. "
            "Run `python -m checksense.cli sample` to generate the sampling pool."
        )
        return

    # Navigation Controls
    col_nav1, col_nav2, col_nav3 = st.columns([2, 2, 4])
    with col_nav1:
        req_indices = list(range(len(requirements)))
        selected_idx = st.selectbox(
            "Select Requirement",
            options=req_indices,
            format_func=lambda i: f"#{i+1} [{requirements[i]['req_id']}] ({'VERIFIED' if any(r.get('label_status') == 'verified' for r in existing_annots.get(requirements[i]['req_id'], [])) else 'UNREVIEWED'})",
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
            if any(r.get("label_status") == "verified" for r in current_saved):
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
            rule_gaps = detect_rule_gaps(req_text, req_id=req_id)
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

    decision = st.radio(
        "Does this requirement contain a defect or quality gap?",
        ["Clean (No Gap)", "Defective (Has Gap)"],
        index=0 if current_saved and any(r.get("has_gap") == "0" for r in current_saved) else 1 if current_saved else 0,
        horizontal=True,
    )

    if decision == "Clean (No Gap)":
        clean_notes = st.text_input(
            "Notes / Verification Justification",
            value=current_saved[0].get("notes", "") if current_saved else "Requirement is unambiguous, complete, and verifiable.",
        )
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            if st.button("💾 Save as DRAFT (Clean)", use_container_width=True):
                save_annotation_rows(
                    target_file,
                    req_id,
                    [{
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
                    }],
                )
                st.success("Saved as clean [DRAFT].")
                st.rerun()
        with col_c2:
            if st.button("✅ Confirm & VERIFY Clean Requirement", type="primary", use_container_width=True):
                save_annotation_rows(
                    target_file,
                    req_id,
                    [{
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
                    }],
                )
                st.success("Confirmed and saved as [VERIFIED] clean requirement!")
                st.rerun()

    else:
        # Multi-gap editor
        existing_gap_rows = [r for r in current_saved if r.get("has_gap") in ("1", "true", "True") or r.get("gap_type")]
        if not existing_gap_rows and rule_gaps:
            st.info("💡 Tip: You can pre-fill from an AI draft suggestion below.")
            if st.button("📋 Import First B1 Rule Suggestion"):
                rg0 = rule_gaps[0]
                existing_gap_rows = [{
                    "req_id": req_id,
                    "doc_id": doc_id,
                    "text": req_text,
                    "has_gap": "1",
                    "gap_type": rg0.gap_type,
                    "subtype": rg0.subtype,
                    "span_text": rg0.span_text,
                    "severity": str(rg0.severity),
                    "explanation": rg0.explanation,
                    "question": rg0.question,
                    "stakeholder_answer": "",
                    "refined_text": "",
                    "annotator": annotator_id,
                    "label_status": "draft",
                    "notes": "Imported from Baseline B1 (Draft)",
                }]

        # Primary gap entry form
        row0 = existing_gap_rows[0] if existing_gap_rows else {}
        c_class, c_sub, c_sev = st.columns(3)
        with c_class:
            selected_class = st.selectbox(
                "Gap Class",
                options=["ambiguity", "incompleteness", "implicit"],
                index=["ambiguity", "incompleteness", "implicit"].index(row0.get("gap_type", "ambiguity")) if row0.get("gap_type") in ["ambiguity", "incompleteness", "implicit"] else 0,
            )
        with c_sub:
            subtypes = TAXONOMY[selected_class]
            curr_sub = row0.get("subtype", subtypes[0])
            sub_idx = subtypes.index(curr_sub) if curr_sub in subtypes else 0
            selected_subtype = st.selectbox("Subtype", options=subtypes, index=sub_idx)
        with c_sev:
            curr_sev = int(row0.get("severity", "2")) if str(row0.get("severity", "")).isdigit() else 2
            selected_sev = st.radio(
                "Severity (1=Minor, 2=Rework, 3=Wrong Behaviour / Safety)",
                [1, 2, 3],
                index=curr_sev - 1,
                horizontal=True,
            )

        col_span, col_expl = st.columns(2)
        with col_span:
            span_val = st.text_input(
                "Defective Span Text",
                value=row0.get("span_text", ""),
                help="Substring in requirement (for ambiguity and incompleteness).",
            )
            if span_val and span_val not in req_text and selected_class != "implicit":
                st.warning("⚠️ Warning: Span text is not an exact substring of the requirement text.")
        with col_expl:
            expl_val = st.text_input(
                "Explanation",
                value=row0.get("explanation", ""),
                help="One concise sentence explaining the defect.",
            )

        col_q, col_ans = st.columns(2)
        with col_q:
            q_val = st.text_input(
                "Clarification Question",
                value=row0.get("question", ""),
                help="Targeted question ending with exactly one '?'",
            )
            if q_val and not q_val.strip().endswith("?"):
                st.warning("⚠️ Clarification question must end with a question mark ('?').")
        with col_ans:
            ans_val = st.text_input(
                "Stakeholder Answer (Optional)",
                value=row0.get("stakeholder_answer", ""),
                help="Answer clarifying the requirement.",
            )

        refined_val = st.text_area(
            "Refined Requirement (Optional)",
            value=row0.get("refined_text", ""),
            help="Rewritten requirement closing the gap.",
        )
        notes_val = st.text_input("Annotator Notes", value=row0.get("notes", ""))

        col_save_draft, col_save_verify = st.columns(2)
        with col_save_draft:
            if st.button("💾 Save as DRAFT (Pending Review)", use_container_width=True):
                save_annotation_rows(
                    target_file,
                    req_id,
                    [{
                        "req_id": req_id,
                        "doc_id": doc_id,
                        "text": req_text,
                        "has_gap": "1",
                        "gap_type": selected_class,
                        "subtype": selected_subtype,
                        "span_text": span_val,
                        "severity": str(selected_sev),
                        "explanation": expl_val,
                        "question": q_val,
                        "stakeholder_answer": ans_val,
                        "refined_text": refined_val,
                        "annotator": annotator_id,
                        "label_status": "draft",
                        "notes": notes_val,
                    }],
                )
                st.success("Gap saved as [DRAFT].")
                st.rerun()

        with col_save_verify:
            if st.button("✅ Confirm & VERIFY Gap Label", type="primary", use_container_width=True):
                if not span_val and selected_class != "implicit":
                    st.error("Span text is required for ambiguity and incompleteness gaps.")
                    return
                if q_val and not q_val.strip().endswith("?"):
                    st.error("Question must end with '?' before verification.")
                    return
                save_annotation_rows(
                    target_file,
                    req_id,
                    [{
                        "req_id": req_id,
                        "doc_id": doc_id,
                        "text": req_text,
                        "has_gap": "1",
                        "gap_type": selected_class,
                        "subtype": selected_subtype,
                        "span_text": span_val,
                        "severity": str(selected_sev),
                        "explanation": expl_val,
                        "question": q_val,
                        "stakeholder_answer": ans_val,
                        "refined_text": refined_val,
                        "annotator": annotator_id,
                        "label_status": "verified",
                        "notes": notes_val,
                    }],
                )
                st.success("Confirmed and saved as human [VERIFIED] gap!")
                st.rerun()


if __name__ == "__main__":
    main()
