"""Unit tests for Phase 1: Real dataset acquisition, verification, and PURE corpus build."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
INTERIM_FILE = ROOT / "data" / "interim" / "pure_requirements.jsonl"
STATS_FILE = ROOT / "data" / "interim" / "pure_filtering_stats.json"
MANIFEST_FILE = ROOT / "data" / "MANIFEST.md"
LABEL_MAPPING_FILE = ROOT / "docs" / "label_mapping.md"

MODAL_PATTERN = re.compile(r"\b(shall|must|should|will)\b", re.IGNORECASE)


def compute_md5(path: Path) -> str:
    md5 = hashlib.md5()
    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            md5.update(chunk)
    return md5.hexdigest()


def test_manifest_structure():
    assert MANIFEST_FILE.is_file(), "data/MANIFEST.md is missing"
    content = MANIFEST_FILE.read_text(encoding="utf-8")
    for name in ["PURE", "ARTA", "QuRE", "7897601"]:
        assert name in content, f"Missing {name} in MANIFEST.md"


def test_pure_raw_files_exist_and_hashes_valid():
    pure_dir = RAW_DIR / "pure"
    assert pure_dir.is_dir(), "data/raw/pure is missing"

    expected = {
        "requirements-xml.zip": "c81235c40f88a2c947ae66e0eddad585",
        "req_document.xsd": "f44c255db9414afb7c39265697abcb33",
        "requirements.zip": "bc319fe28619f6290badff328ca159dd",
    }
    for filename, expected_md5 in expected.items():
        file_path = pure_dir / filename
        assert file_path.is_file(), f"Missing PURE file: {filename}"
        assert compute_md5(file_path) == expected_md5, f"Checksum mismatch on {filename}"


def test_arta_raw_file_exists_and_hash_valid():
    arta_file = RAW_DIR / "arta" / "ARTADataset_release1.zip"
    assert arta_file.is_file(), "data/raw/arta/ARTADataset_release1.zip is missing"
    assert compute_md5(arta_file) == "92a09adc5e4b9cd96370e7f09fe466d2"


def test_qure_raw_files_exist_and_hashes_valid():
    qure_dir = RAW_DIR / "qure"
    assert (qure_dir / "QuRE.csv").is_file()
    assert (qure_dir / "description.md").is_file()
    assert compute_md5(qure_dir / "QuRE.csv") == "80565e3b8996d8af1598813aafc87cb3"
    assert compute_md5(qure_dir / "description.md") == "e7b7a3526c0471fe6853daa13e5613d7"


def test_interim_pure_corpus_schema():
    assert INTERIM_FILE.is_file(), "pure_requirements.jsonl is missing"
    lines = [line.strip() for line in INTERIM_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) > 2000, f"Expected >2000 candidate requirements, got {len(lines)}"

    required_keys = {"req_id", "doc_id", "text", "source_file", "sent_idx", "token_count"}
    for idx, line in enumerate(lines[:100]):
        row = json.loads(line)
        assert required_keys.issubset(row.keys()), f"Row {idx} missing required keys"
        assert len(row["text"].strip()) > 0
        assert row["token_count"] >= 5
        assert row["token_count"] <= 60


def test_pure_corpus_filtering_constraints():
    lines = [line.strip() for line in INTERIM_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]
    seen_docs = set()
    seen_req_ids = set()

    for line in lines:
        row = json.loads(line)
        # 1. Unique req_id
        assert row["req_id"] not in seen_req_ids, f"Duplicate req_id: {row['req_id']}"
        seen_req_ids.add(row["req_id"])
        seen_docs.add(row["doc_id"])

        # 2. Modal verb present
        assert MODAL_PATTERN.search(row["text"]), f"No modal verb in: {row['text']}"

        # 3. Token count [5, 60]
        tokens = row["text"].split()
        assert 5 <= len(tokens) <= 60, f"Invalid token length ({len(tokens)}) in: {row['text']}"

    # 4. All 18 documents represented
    assert len(seen_docs) == 18, f"Expected 18 documents, got {len(seen_docs)}"


def test_filtering_audit_stats_integrity():
    assert STATS_FILE.is_file(), "pure_filtering_stats.json is missing"
    data = json.loads(STATS_FILE.read_text(encoding="utf-8"))
    summary = data["summary"]
    assert summary["total_documents_processed"] == 18
    assert summary["documents_dropped"] == 0
    assert summary["total_candidate_requirements_retained"] == 2928

    total = summary["total_raw_sentences_extracted"]
    retained = summary["total_candidate_requirements_retained"]
    removed_sum = (
        summary["removed_duplicates"]
        + summary["removed_headings"]
        + summary["removed_no_modal_verb"]
        + summary["removed_too_short_lt5"]
        + summary["removed_too_long_gt60"]
    )
    assert total == retained + removed_sum, "Audit counts do not balance!"


def test_label_mapping_doc_exists():
    assert LABEL_MAPPING_FILE.is_file()
    content = LABEL_MAPPING_FILE.read_text(encoding="utf-8")
    assert "DS1.xlsx" in content
    assert "vague_term" in content
    assert "vague_quantifier" in content
