"""Unit and regression tests for CheckSense Phase 3.

Covers:
- Phase 3 Sampling Protocol (seed 42 determinism, document disjointness, sample size >=600, test hold-out ~25%)
- Gold annotation schema and pilot sheet generation
- Cohen's kappa calculation (unweighted and quadratically weighted)
- Inter-rater agreement analysis and disagreement reporting
- Annotation progress auditing and CLI subcommands
- Streamlit application integrity
"""

from __future__ import annotations

import csv
import json
import py_compile
from pathlib import Path

import pytest

from checksense import (
    compute_annotation_agreement,
    compute_cohens_kappa,
    compute_dataset_annotation_stats,
    interpret_kappa,
    load_pilot_expected_ids,
    partition_documents,
    sample_requirements,
)
from checksense.cli import main
from checksense.sample import ANNOTATION_COLUMNS


def test_partition_documents_determinism():
    docs = [f"doc_{i:02d}" for i in range(24)]
    dev1, test1 = partition_documents(docs, held_out_ratio=0.25, seed=42)
    dev2, test2 = partition_documents(docs, held_out_ratio=0.25, seed=42)
    assert dev1 == dev2
    assert test1 == test2


def test_partition_documents_disjointness():
    docs = [f"doc_{i:02d}" for i in range(28)]
    dev, test = partition_documents(docs, held_out_ratio=0.25, seed=42)
    assert len(set(dev) & set(test)) == 0, "Document contamination detected between dev and test!"
    assert len(test) == round(len(docs) * 0.25)
    assert len(dev) == len(docs) - len(test)


def test_sample_protocol_counts_and_manifest(tmp_path: Path):
    interim_file = Path("data/interim/pure_requirements.jsonl")
    assert interim_file.exists(), "Interim requirements corpus must exist"

    manifest = sample_requirements(
        input_file=interim_file,
        output_dir=tmp_path,
        n_samples=600,
        n_documents=20,
        seed=42,
        held_out_ratio=0.25,
        pilot_size=50,
    )

    assert manifest["total_sampled"] >= 600, f"Expected >=600 sampled, got {manifest['total_sampled']}"
    assert manifest["total_documents"] >= 20, f"Expected >=20 documents, got {manifest['total_documents']}"
    assert manifest["test_count"] >= 140, f"Expected >=140 test requirements, got {manifest['test_count']}"
    assert manifest["dev_count"] >= 440, f"Expected >=440 dev requirements, got {manifest['dev_count']}"
    assert manifest["contamination_audit"]["disjoint_documents"] is True

    # Check manifest JSON file
    manifest_path = tmp_path / "sample_manifest.json"
    assert manifest_path.is_file()
    saved_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert saved_data["seed"] == 42
    assert saved_data["total_sampled"] == manifest["total_sampled"]


def test_sample_pool_and_pilot_schema(tmp_path: Path):
    interim_file = Path("data/interim/pure_requirements.jsonl")
    manifest = sample_requirements(
        input_file=interim_file,
        output_dir=tmp_path,
        n_samples=600,
        n_documents=20,
        seed=42,
        pilot_size=50,
    )

    # 1. Inspect sample pool JSONL
    pool_file = tmp_path / "sample_pool.jsonl"
    assert pool_file.is_file()
    lines = [json.loads(line) for line in pool_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == manifest["total_sampled"]

    expected_pool_keys = {"req_id", "doc_id", "text", "split", "source_file", "sent_idx", "token_count"}
    for row in lines[:50]:
        assert expected_pool_keys.issubset(row.keys())
        assert row["split"] in ("dev", "test")

    # 2. Inspect pilot CSV
    pilot_file = tmp_path / "pilot_sample.csv"
    assert pilot_file.is_file()
    with open(pilot_file, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        pilot_rows = list(reader)
    assert len(pilot_rows) == 50
    assert reader.fieldnames == ANNOTATION_COLUMNS
    for r in pilot_rows:
        assert r["label_status"] == "draft", "Pilot samples must initialize as draft"
        assert len(r["text"].strip()) > 0

    # 3. Inspect template CSV
    template_file = tmp_path / "annotations_template.csv"
    assert template_file.is_file()
    with open(template_file, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == ANNOTATION_COLUMNS
        assert len(list(reader)) == 0  # Blank template


def test_cohens_kappa_perfect_agreement():
    rater_a = ["ambiguity", "incompleteness", "clean", "implicit", "clean"]
    rater_b = ["ambiguity", "incompleteness", "clean", "implicit", "clean"]
    res = compute_cohens_kappa(rater_a, rater_b)
    assert res["kappa"] == 1.0
    assert res["observed_agreement"] == 1.0
    assert "Almost Perfect" in res["interpretation"]


def test_cohens_kappa_inverse_agreement():
    rater_a = ["clean", "clean", "gap", "gap"]
    rater_b = ["gap", "gap", "clean", "clean"]
    res = compute_cohens_kappa(rater_a, rater_b)
    assert res["kappa"] == -1.0
    assert "Poor" in res["interpretation"]


def test_cohens_kappa_weighted_severity():
    # Identical ratings
    res_exact = compute_cohens_kappa([1, 2, 3], [1, 2, 3], weights="quadratic")
    assert res_exact["kappa"] == 1.0

    # Off-by-one vs Off-by-two
    # Off-by-one (1 vs 2, 2 vs 3): quadratic weight gives high partial credit
    res_close = compute_cohens_kappa([1, 2, 2, 3], [2, 2, 3, 3], weights="quadratic")
    # Off-by-two (1 vs 3): quadratic weight gives 0 partial credit
    res_far = compute_cohens_kappa([1, 1, 3, 3], [3, 3, 1, 1], weights="quadratic")
    assert res_close["kappa"] > res_far["kappa"]


def test_interpret_kappa_scale():
    assert "Poor" in interpret_kappa(-0.1)
    assert "Slight" in interpret_kappa(0.15)
    assert "Fair" in interpret_kappa(0.35)
    assert "Moderate" in interpret_kappa(0.55)
    assert "Substantial" in interpret_kappa(0.75)
    assert "Almost Perfect" in interpret_kappa(0.95)


def test_annotation_agreement_paired_sheets(tmp_path: Path):
    file_a = tmp_path / "rater_a.csv"
    file_b = tmp_path / "rater_b.csv"

    rows_a = [
        {"req_id": "REQ_01", "has_gap": "1", "gap_type": "ambiguity", "subtype": "vague_term", "severity": "2", "label_status": "verified"},
        {"req_id": "REQ_02", "has_gap": "0", "gap_type": "", "subtype": "", "severity": "", "label_status": "verified"},
        {"req_id": "REQ_03", "has_gap": "1", "gap_type": "incompleteness", "subtype": "missing_actor", "severity": "3", "label_status": "verified"},
        {"req_id": "REQ_04", "has_gap": "1", "gap_type": "implicit", "subtype": "unstated_constraint", "severity": "3", "label_status": "verified"},
    ]

    rows_b = [
        {"req_id": "REQ_01", "has_gap": "1", "gap_type": "ambiguity", "subtype": "vague_term", "severity": "2", "label_status": "verified"},
        {"req_id": "REQ_02", "has_gap": "0", "gap_type": "", "subtype": "", "severity": "", "label_status": "verified"},
        {"req_id": "REQ_03", "has_gap": "1", "gap_type": "incompleteness", "subtype": "missing_condition", "severity": "2", "label_status": "verified"},
        {"req_id": "REQ_04", "has_gap": "1", "gap_type": "implicit", "subtype": "unstated_constraint", "severity": "3", "label_status": "verified"},
    ]

    for p, rows in [(file_a, rows_a), (file_b, rows_b)]:
        with open(p, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=ANNOTATION_COLUMNS)
            writer.writeheader()
            for r in rows:
                full_row = {col: r.get(col, "") for col in ANNOTATION_COLUMNS}
                full_row["text"] = f"Sample requirement for {r['req_id']}"
                writer.writerow(full_row)

    report = compute_annotation_agreement(file_a, file_b)
    assert report["n_evaluated"] == 4
    assert report["has_gap_kappa"]["kappa"] == 1.0  # Both agreed perfectly on whether a gap existed
    assert report["gap_type_kappa"]["kappa"] == 1.0  # Both agreed on ambiguity, clean, incompleteness, implicit
    assert report["subtype_kappa"]["kappa"] < 1.0  # Disagreed on missing_actor vs missing_condition on REQ_03
    assert report["n_disagreements"] == 1
    assert report["disagreements"][0]["req_id"] == "REQ_03"


def test_dataset_annotation_stats(tmp_path: Path):
    gold_file = tmp_path / "annotations.csv"
    rows = [
        {"req_id": "R1", "doc_id": "D1", "has_gap": "0", "gap_type": "", "subtype": "", "severity": "", "label_status": "verified"},
        {"req_id": "R2", "doc_id": "D1", "has_gap": "1", "gap_type": "ambiguity", "subtype": "vague_term", "severity": "2", "label_status": "verified"},
        {"req_id": "R3", "doc_id": "D2", "has_gap": "1", "gap_type": "incompleteness", "subtype": "missing_actor", "severity": "3", "label_status": "draft"},
    ]
    with open(gold_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ANNOTATION_COLUMNS)
        writer.writeheader()
        for r in rows:
            full_row = {col: r.get(col, "") for col in ANNOTATION_COLUMNS}
            full_row["text"] = "Dummy requirement text"
            writer.writerow(full_row)

    stats = compute_dataset_annotation_stats(gold_file)
    assert stats["total_requirements"] == 3
    assert stats["verified_requirements"] == 2
    assert stats["draft_requirements"] == 1
    assert stats["clean_requirements"] == 1
    assert stats["total_gaps_annotated"] == 2
    assert stats["class_distribution"]["ambiguity"] == 1
    assert stats["subtype_distribution"]["missing_actor"] == 1


def test_cli_sample_subcommand(tmp_path: Path):
    out_dir = tmp_path / "gold"
    rc = main(["sample", "--n-samples", "60", "--output-dir", str(out_dir)])
    assert rc == 0
    assert (out_dir / "sample_manifest.json").is_file()
    assert (out_dir / "pilot_sample.csv").is_file()


def test_cli_annotate_stats_subcommand(tmp_path: Path):
    gold_file = tmp_path / "stats_test.csv"
    with open(gold_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ANNOTATION_COLUMNS)
        writer.writeheader()
        writer.writerow({
            "req_id": "REQ_01",
            "doc_id": "DOC_A",
            "text": "The system shall be fast.",
            "has_gap": "1",
            "gap_type": "ambiguity",
            "subtype": "vague_term",
            "span_text": "fast",
            "severity": "2",
            "label_status": "verified",
        })

    rc = main(["annotate-stats", "--gold-file", str(gold_file)])
    assert rc == 0


def test_streamlit_annotate_compilation():
    app_path = Path("app/annotate.py")
    assert app_path.is_file()
    # Ensure file compiles cleanly to bytecode without syntax errors
    py_compile.compile(str(app_path), doraise=True)


# ==============================================================================
# Regression Tests for Targeted Annotation-Integrity Issues
# ==============================================================================

def test_held_out_test_set_sequestering(tmp_path: Path):
    """Regression test: Held-out test set cannot be loaded in ordinary annotation workflow."""
    from checksense import load_annotation_workflow_pool

    interim_file = Path("data/interim/pure_requirements.jsonl")
    manifest = sample_requirements(
        input_file=interim_file,
        output_dir=tmp_path,
        n_samples=60,
        n_documents=20,
        seed=42,
    )

    test_pool_file = tmp_path / "test_pool.jsonl"
    dev_pool_file = tmp_path / "dev_pool.jsonl"
    manifest_file = tmp_path / "sample_manifest.json"

    assert test_pool_file.is_file()
    assert dev_pool_file.is_file()

    # 1. Loading explicit test pool file must raise PermissionError
    with pytest.raises(PermissionError) as exc_info:
        load_annotation_workflow_pool(test_pool_file, manifest_path=manifest_file)
    assert "sequestered" in str(exc_info.value).lower()

    # 2. dev_pool.jsonl must contain ZERO test documents
    test_docs = set(manifest["test_documents"])
    dev_records = [json.loads(line) for line in dev_pool_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    for r in dev_records:
        assert r["split"] == "dev", f"Found test record in dev_pool: {r['req_id']}"
        assert r["doc_id"] not in test_docs, f"Found test document in dev_pool: {r['doc_id']}"

    # 3. Loading dev_pool through workflow must succeed
    allowed = load_annotation_workflow_pool(dev_pool_file, manifest_path=manifest_file)
    assert len(allowed) == len(dev_records)
    for r in allowed:
        assert r["doc_id"] not in test_docs


def test_validation_span_and_question_rules():
    """Regression test: Enforce span and question validation before verification."""
    from checksense import validate_clarification_question, validate_gap_row

    req_text = "The telemetry service shall store biometric user data in the database."

    # 1. Empty span for ambiguity/incompleteness is rejected
    errs_empty = validate_gap_row(
        req_text,
        {
            "has_gap": "1",
            "gap_type": "ambiguity",
            "subtype": "vague_term",
            "span_text": "",
            "severity": "2",
            "explanation": "Vague term.",
            "question": "What is the threshold?",
        },
        for_verification=True,
    )
    assert any("span text is required" in e.lower() for e in errs_empty)

    # 2. Span not in requirement is rejected
    errs_missing = validate_gap_row(
        req_text,
        {
            "has_gap": "1",
            "gap_type": "ambiguity",
            "subtype": "vague_term",
            "span_text": "nonexistent_term_xyz",
            "severity": "2",
            "explanation": "Vague term.",
            "question": "What is the threshold?",
        },
        for_verification=True,
    )
    assert any("not an exact substring" in e.lower() for e in errs_missing)

    # 3. Question without question mark is rejected
    errs_no_q = validate_clarification_question("What is the retention period")
    assert any("must end with a question mark" in e.lower() for e in errs_no_q)

    # 4. Question with multiple question marks (e.g. ?? or What? Why?) is rejected
    errs_multi_q1 = validate_clarification_question("What is the retention period??")
    assert any("exactly one question mark" in e.lower() for e in errs_multi_q1)

    errs_multi_q2 = validate_clarification_question("Is it 5 days? Or 10 days?")
    assert any("exactly one question mark" in e.lower() for e in errs_multi_q2)

    # 5. Question with misplaced question mark is rejected
    errs_misplaced = validate_clarification_question("What? is the retention period")
    assert any("must end with a question mark" in e.lower() for e in errs_misplaced)

    # 6. Valid span and valid question pass validation
    errs_valid = validate_gap_row(
        req_text,
        {
            "has_gap": "1",
            "gap_type": "incompleteness",
            "subtype": "missing_condition",
            "span_text": "shall store",
            "severity": "2",
            "explanation": "Condition for storage is omitted.",
            "question": "Under what condition shall the telemetry service store user data?",
        },
        for_verification=True,
    )
    assert len(errs_valid) == 0


def test_inter_rater_agreement_hardening(tmp_path: Path):
    """Regression test: Reject missing IDs, draft rows, and duplicate conflicting records."""
    file_a = tmp_path / "rater_a.csv"
    file_b = tmp_path / "rater_b.csv"

    # Case A: Unverified / draft rows must be rejected
    rows_draft_a = [
        {"req_id": "REQ_01", "has_gap": "1", "gap_type": "ambiguity", "subtype": "vague_term", "severity": "2", "label_status": "draft"},
        {"req_id": "REQ_02", "has_gap": "0", "gap_type": "", "subtype": "", "severity": "", "label_status": "verified"},
    ]
    rows_verified_b = [
        {"req_id": "REQ_01", "has_gap": "1", "gap_type": "ambiguity", "subtype": "vague_term", "severity": "2", "label_status": "verified"},
        {"req_id": "REQ_02", "has_gap": "0", "gap_type": "", "subtype": "", "severity": "", "label_status": "verified"},
    ]

    for p, rows in [(file_a, rows_draft_a), (file_b, rows_verified_b)]:
        with open(p, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=ANNOTATION_COLUMNS)
            w.writeheader()
            for r in rows:
                full = {c: r.get(c, "") for c in ANNOTATION_COLUMNS}
                full["text"] = "Sample req"
                w.writerow(full)

    with pytest.raises(ValueError) as exc_info:
        compute_annotation_agreement(file_a, file_b)
    assert "unverified annotation rejected" in str(exc_info.value).lower()

    # Case B: Incomplete ID coverage must be rejected (file A has REQ_01, file B has REQ_01 and REQ_02)
    rows_verified_a_short = [
        {"req_id": "REQ_01", "has_gap": "1", "gap_type": "ambiguity", "subtype": "vague_term", "severity": "2", "label_status": "verified"},
    ]
    with open(file_a, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=ANNOTATION_COLUMNS)
        w.writeheader()
        for r in rows_verified_a_short:
            full = {c: r.get(c, "") for c in ANNOTATION_COLUMNS}
            full["text"] = "Sample req"
            w.writerow(full)

    with pytest.raises(ValueError) as exc_info:
        compute_annotation_agreement(file_a, file_b)
    assert "mismatch" in str(exc_info.value).lower()

    # Case C: Clean and gap coexistence for same ID must be rejected
    rows_coexist = [
        {"req_id": "REQ_01", "has_gap": "0", "gap_type": "", "subtype": "", "severity": "", "label_status": "verified"},
        {"req_id": "REQ_01", "has_gap": "1", "gap_type": "ambiguity", "subtype": "vague_term", "severity": "2", "label_status": "verified"},
        {"req_id": "REQ_02", "has_gap": "0", "gap_type": "", "subtype": "", "severity": "", "label_status": "verified"},
    ]
    with open(file_a, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=ANNOTATION_COLUMNS)
        w.writeheader()
        for r in rows_coexist:
            full = {c: r.get(c, "") for c in ANNOTATION_COLUMNS}
            full["text"] = "Sample req"
            w.writerow(full)

    with pytest.raises(ValueError) as exc_info:
        compute_annotation_agreement(file_a, file_b)
    assert "integrity violation" in str(exc_info.value).lower()

    # Case D: Duplicate clean rows must be rejected
    rows_dup_clean = [
        {"req_id": "REQ_01", "has_gap": "0", "gap_type": "", "subtype": "", "severity": "", "label_status": "verified"},
        {"req_id": "REQ_01", "has_gap": "0", "gap_type": "", "subtype": "", "severity": "", "label_status": "verified"},
        {"req_id": "REQ_02", "has_gap": "0", "gap_type": "", "subtype": "", "severity": "", "label_status": "verified"},
    ]
    with open(file_a, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=ANNOTATION_COLUMNS)
        w.writeheader()
        for r in rows_dup_clean:
            full = {c: r.get(c, "") for c in ANNOTATION_COLUMNS}
            full["text"] = "Sample req"
            w.writerow(full)

    with pytest.raises(ValueError) as exc_info:
        compute_annotation_agreement(file_a, file_b)
    assert "duplicate clean rows" in str(exc_info.value).lower()

    # Case E: Valid complete paired annotations
    rows_valid_a = [
        {"req_id": "REQ_01", "has_gap": "1", "gap_type": "ambiguity", "subtype": "vague_term", "severity": "2", "label_status": "verified"},
        {"req_id": "REQ_02", "has_gap": "0", "gap_type": "", "subtype": "", "severity": "", "label_status": "verified"},
    ]
    with open(file_a, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=ANNOTATION_COLUMNS)
        w.writeheader()
        for r in rows_valid_a:
            full = {c: r.get(c, "") for c in ANNOTATION_COLUMNS}
            full["text"] = "Sample req"
            w.writerow(full)

    res = compute_annotation_agreement(file_a, file_b)
    assert res["n_evaluated"] == 2
    assert res["has_gap_kappa"]["observed_agreement"] == 1.0

    # Case F: Two files with the SAME incomplete subset of the pilot must be rejected
    expected_pilot_ids = ["REQ_01", "REQ_02", "REQ_03"]
    with pytest.raises(ValueError) as exc_info:
        compute_annotation_agreement(file_a, file_b, expected_req_ids=expected_pilot_ids)
    assert "coverage error" in str(exc_info.value).lower()
    assert "expected 3" in str(exc_info.value).lower()
    assert "req_03" in str(exc_info.value).lower()

    # Case G: pilot_reference_file loading and rejection of same incomplete subset
    pilot_ref_csv = tmp_path / "pilot_ref.csv"
    with open(pilot_ref_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["req_id", "doc_id", "text"])
        w.writeheader()
        for rid in expected_pilot_ids:
            w.writerow({"req_id": rid, "doc_id": "DOC_1", "text": "Requirement text"})

    with pytest.raises(ValueError) as exc_info:
        compute_annotation_agreement(file_a, file_b, pilot_reference_file=pilot_ref_csv)
    assert "coverage error" in str(exc_info.value).lower()

    # Case H: Complete verified files matching pilot reference pass
    rows_valid_full = [
        {"req_id": "REQ_01", "has_gap": "1", "gap_type": "ambiguity", "subtype": "vague_term", "severity": "2", "label_status": "verified"},
        {"req_id": "REQ_02", "has_gap": "0", "gap_type": "", "subtype": "", "severity": "", "label_status": "verified"},
        {"req_id": "REQ_03", "has_gap": "0", "gap_type": "", "subtype": "", "severity": "", "label_status": "verified"},
    ]
    for p in (file_a, file_b):
        with open(p, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=ANNOTATION_COLUMNS)
            w.writeheader()
            for r in rows_valid_full:
                full = {c: r.get(c, "") for c in ANNOTATION_COLUMNS}
                full["text"] = "Sample req"
                w.writerow(full)

    res_full = compute_annotation_agreement(file_a, file_b, pilot_reference_file=pilot_ref_csv)
    assert res_full["n_evaluated"] == 3
    assert res_full["has_gap_kappa"]["observed_agreement"] == 1.0


def test_agreement_cli_pilot_reference_validation(tmp_path: Path):
    """Regression test: CLI validates against complete pilot reference file and rejects partial subsets."""
    pilot_ref = tmp_path / "cli_pilot_ref.csv"
    with open(pilot_ref, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["req_id", "doc_id", "text"])
        w.writeheader()
        for rid in ["REQ_01", "REQ_02", "REQ_03"]:
            w.writerow({"req_id": rid, "doc_id": "DOC_1", "text": "Req text"})

    # 0. Test load_pilot_expected_ids directly
    ids = load_pilot_expected_ids(pilot_ref)
    assert ids == ["REQ_01", "REQ_02", "REQ_03"]

    file_a = tmp_path / "cli_rater_a.csv"
    file_b = tmp_path / "cli_rater_b.csv"

    # 1. Incomplete pilot subset in both files (only REQ_01 and REQ_02)
    incomplete_rows = [
        {"req_id": "REQ_01", "has_gap": "0", "gap_type": "", "subtype": "", "severity": "", "label_status": "verified"},
        {"req_id": "REQ_02", "has_gap": "0", "gap_type": "", "subtype": "", "severity": "", "label_status": "verified"},
    ]
    for p in (file_a, file_b):
        with open(p, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=ANNOTATION_COLUMNS)
            w.writeheader()
            for r in incomplete_rows:
                full = {c: r.get(c, "") for c in ANNOTATION_COLUMNS}
                full["text"] = "Req text"
                w.writerow(full)

    rc_incomplete = main([
        "annotate-stats",
        "--pilot-file-a", str(file_a),
        "--pilot-file-b", str(file_b),
        "--pilot-ref-file", str(pilot_ref),
    ])
    assert rc_incomplete == 1

    # 2. Missing reference file fails clearly
    rc_missing_ref = main([
        "annotate-stats",
        "--pilot-file-a", str(file_a),
        "--pilot-file-b", str(file_b),
        "--pilot-ref-file", str(tmp_path / "nonexistent.csv"),
    ])
    assert rc_missing_ref == 1

    # 3. Invalid reference file (missing req_id column) fails clearly
    invalid_ref = tmp_path / "invalid_ref.csv"
    with open(invalid_ref, "w", newline="", encoding="utf-8") as f:
        f.write("wrong_col_a,wrong_col_b\n1,2\n")
    rc_invalid_ref = main([
        "annotate-stats",
        "--pilot-file-a", str(file_a),
        "--pilot-file-b", str(file_b),
        "--pilot-ref-file", str(invalid_ref),
    ])
    assert rc_invalid_ref == 1

    # 4. Complete, verified files matching pilot reference pass
    complete_rows = [
        {"req_id": "REQ_01", "has_gap": "1", "gap_type": "ambiguity", "subtype": "vague_term", "severity": "2", "label_status": "verified"},
        {"req_id": "REQ_02", "has_gap": "0", "gap_type": "", "subtype": "", "severity": "", "label_status": "verified"},
        {"req_id": "REQ_03", "has_gap": "0", "gap_type": "", "subtype": "", "severity": "", "label_status": "verified"},
    ]
    for p in (file_a, file_b):
        with open(p, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=ANNOTATION_COLUMNS)
            w.writeheader()
            for r in complete_rows:
                full = {c: r.get(c, "") for c in ANNOTATION_COLUMNS}
                full["text"] = "Req text"
                w.writerow(full)

    rc_complete = main([
        "annotate-stats",
        "--pilot-file-a", str(file_a),
        "--pilot-file-b", str(file_b),
        "--pilot-ref-file", str(pilot_ref),
    ])
    assert rc_complete == 0


def test_multi_gap_preservation_and_coexistence(tmp_path: Path):
    """Regression test: Saving multiple gaps preserves all rows and prohibits clean coexistence."""
    from checksense import load_annotation_sheet, save_annotation_rows

    csv_path = tmp_path / "test_annotations.csv"
    req_text = "The user shall login rapidly and download records."

    # 1. Save two distinct gaps for the same requirement
    gap_rows = [
        {
            "req_id": "REQ_100",
            "doc_id": "DOC_A",
            "text": req_text,
            "has_gap": "1",
            "gap_type": "ambiguity",
            "subtype": "vague_term",
            "span_text": "rapidly",
            "severity": "2",
            "explanation": "Rapidly is unquantified.",
            "question": "What is the maximum login latency in seconds?",
            "label_status": "verified",
        },
        {
            "req_id": "REQ_100",
            "doc_id": "DOC_A",
            "text": req_text,
            "has_gap": "1",
            "gap_type": "incompleteness",
            "subtype": "missing_condition",
            "span_text": "download records",
            "severity": "2",
            "explanation": "Condition for download permission is omitted.",
            "question": "What authentication level is required to download records?",
            "label_status": "verified",
        },
    ]

    save_annotation_rows(csv_path, "REQ_100", gap_rows, req_text=req_text, for_verification=True)
    sheet = load_annotation_sheet(csv_path)
    assert len(sheet["REQ_100"]) == 2, "Both gap rows must be preserved in CSV"
    assert sheet["REQ_100"][0]["subtype"] == "vague_term"
    assert sheet["REQ_100"][1]["subtype"] == "missing_condition"

    # 2. Attempting to save a clean row alongside a gap row must fail
    invalid_coexisting = [
        {
            "req_id": "REQ_100",
            "has_gap": "0",
            "gap_type": "",
            "subtype": "",
            "label_status": "verified",
        },
        gap_rows[0],
    ]
    with pytest.raises(ValueError) as exc_info:
        save_annotation_rows(csv_path, "REQ_100", invalid_coexisting, req_text=req_text, for_verification=True)
    assert "integrity violation" in str(exc_info.value).lower()

    # 3. Switching requirement to clean cleanly replaces previous gap rows
    clean_replacement = [{
        "req_id": "REQ_100",
        "doc_id": "DOC_A",
        "text": req_text,
        "has_gap": "0",
        "gap_type": "",
        "subtype": "",
        "span_text": "",
        "severity": "",
        "explanation": "",
        "question": "",
        "label_status": "verified",
        "notes": "Verified as clean",
    }]
    save_annotation_rows(csv_path, "REQ_100", clean_replacement, req_text=req_text, for_verification=True)
    sheet_updated = load_annotation_sheet(csv_path)
    assert len(sheet_updated["REQ_100"]) == 1
    assert sheet_updated["REQ_100"][0]["has_gap"] == "0"

