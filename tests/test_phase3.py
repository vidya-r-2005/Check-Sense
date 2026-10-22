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

from checksense import (
    compute_annotation_agreement,
    compute_cohens_kappa,
    compute_dataset_annotation_stats,
    interpret_kappa,
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
