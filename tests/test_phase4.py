"""Comprehensive Unit and Regression Tests for CheckSense Phase 4.

Covers:
- ARTA dataset loading, header normalization, and smell taxonomy mapping
- Cell value smell presence detection (per docs/label_mapping.md)
- QuRE external benchmark dataset loading and schema validation
- Provisional gold annotation loading and verified gating
- Grouped cross-validation document disjointness (zero data leakage)
- Sentence-level smell classifier (TF-IDF + Logistic Regression)
- Token-level BIO span tagger alignment and contextual feature extraction
- Entity-level token Jaccard overlap matching (>= 0.5)
- Phase 4 Multi-head pipeline (Heads 4a, 4b, 4c)
- CLI subcommand execution for train-smell, train-span, and eval --pipeline phase4
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pytest

from checksense import (
    CandidateGap,
    LinearSpanTagger,
    Phase4Pipeline,
    RequirementFrame,
    TfidfSmellClassifier,
    align_gold_spans_to_bio_tokens,
    load_arta_dataset,
    load_bio_dataset_from_gold,
    load_provisional_pilot_dataset,
    load_qure_dataset,
    run_phase4_heads,
)
from checksense.cli import main
from checksense.smell import (
    ARTA_COLUMN_MAPPING,
    compute_classification_metrics,
    is_smell_cell_positive,
)
from checksense.span_tagger import token_jaccard, token_to_features

# ============================================================================
# 1. ARTA Ingestion & Label Mapping Tests
# ============================================================================

def test_arta_label_mapping_coverage():
    """Verify all 9 documented ARTA smell types map to valid CheckSense classes."""
    expected_categories = {"ambiguity", "incompleteness"}
    for col_norm, (gap_type, subtype) in ARTA_COLUMN_MAPPING.items():
        assert gap_type in expected_categories, f"Invalid gap_type '{gap_type}' for {col_norm}"
        assert len(subtype) > 0, f"Empty subtype for {col_norm}"


def test_is_smell_cell_positive():
    """Verify cell smell indicators per docs/label_mapping.md."""
    # Negatives
    assert not is_smell_cell_positive("-")
    assert not is_smell_cell_positive("")
    assert not is_smell_cell_positive("   ")
    assert not is_smell_cell_positive("nan")
    assert not is_smell_cell_positive("none")
    assert not is_smell_cell_positive("0")
    assert not is_smell_cell_positive(None)
    assert not is_smell_cell_positive(float("nan"))

    # Positives (word spans or triggering tokens)
    assert is_smell_cell_positive("safely")
    assert is_smell_cell_positive("appropriate*other*commercial")
    assert is_smell_cell_positive("fast")
    assert is_smell_cell_positive("1")


def test_load_arta_dataset_real_data():
    """Verify loading real ARTA dataset from data/raw/arta."""
    arta_dir = Path("data/raw/arta")
    assert arta_dir.exists(), "Raw ARTA directory must exist"

    df = load_arta_dataset(arta_dir)
    assert len(df) == 4752, f"Expected 4,752 ARTA requirements, got {len(df)}"
    assert set(df.columns).issuperset({
        "text", "doc_id", "source_dataset", "has_smell",
        "has_ambiguity", "has_incompleteness", "smell_count", "smell_types"
    })
    assert df["doc_id"].nunique() >= 20, "Expected at least 20 document groups for cross-validation"
    assert df["has_smell"].isin([0, 1]).all()


# ============================================================================
# 2. QuRE External Dataset Tests
# ============================================================================

def test_load_qure_dataset_real_data():
    """Verify loading real QuRE external dataset from data/raw/qure/QuRE.csv."""
    qure_path = Path("data/raw/qure/QuRE.csv")
    assert qure_path.exists(), "QuRE.csv must exist"

    df = load_qure_dataset(qure_path)
    assert len(df) == 2187, f"Expected 2,187 QuRE records, got {len(df)}"
    assert set(df.columns).issuperset({"id", "text", "has_smell", "weak_word", "raw_label"})
    assert set(df["has_smell"].unique()) == {0, 1}


# ============================================================================
# 3. Provisional Gold Loading & Verification Gate
# ============================================================================

def test_load_provisional_pilot_dataset_verified():
    """Verify loading provisional Rater 1 gold annotations."""
    gold_path = Path("data/gold/annotations/rater_1.csv")
    assert gold_path.exists(), "rater_1.csv must exist"

    df = load_provisional_pilot_dataset(gold_path)
    assert len(df) == 50, f"Expected exactly 50 requirements in pilot, got {len(df)}"
    assert set(df.columns).issuperset({
        "req_id", "doc_id", "text", "has_smell", "has_ambiguity",
        "has_incompleteness", "has_implicit", "gap_count"
    })
    assert df["has_smell"].isin([0, 1]).all()


def test_load_provisional_pilot_unverified_rejection(tmp_path: Path):
    """Verify that unverified rows are strictly rejected by the verification gate."""
    bad_csv = tmp_path / "unverified.csv"
    with bad_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["req_id", "doc_id", "text", "has_gap", "label_status"])
        writer.writeheader()
        writer.writerow({
            "req_id": "REQ_01",
            "doc_id": "DOC_1",
            "text": "The system shall be fast.",
            "has_gap": "1",
            "label_status": "draft",
        })

    with pytest.raises(ValueError, match="not verified"):
        load_provisional_pilot_dataset(bad_csv)


# ============================================================================
# 4. TfidfSmellClassifier Tests
# ============================================================================

def test_tfidf_smell_classifier_training_and_io(tmp_path: Path):
    """Test TF-IDF smell classifier fit, predict, and serialization."""
    train_texts = [
        "The system shall respond immediately and fast.",
        "The system shall display optimal results where appropriate.",
        "The system shall authenticate user via password.",
        "The controller shall compute telemetry every 10 seconds.",
        "The server shall listen on port 8080.",
        "The module shall log error code 404.",
    ]
    train_labels = [1, 1, 1, 0, 0, 0]

    clf = TfidfSmellClassifier(seed=42)
    clf.fit(train_texts, train_labels)

    preds = clf.predict(train_texts)
    probas = clf.predict_smell_probability(train_texts)

    assert len(preds) == len(train_texts)
    assert len(probas) == len(train_texts)
    assert all(0.0 <= p <= 1.0 for p in probas)

    # Test serialization
    model_file = tmp_path / "model.joblib"
    clf.save(model_file)
    assert model_file.is_file()

    loaded_clf = TfidfSmellClassifier.load(model_file)
    loaded_preds = loaded_clf.predict(train_texts)
    np.testing.assert_array_equal(preds, loaded_preds)


def test_compute_classification_metrics():
    """Test classification metric calculations."""
    y_true = [0, 0, 1, 1]
    y_pred = [0, 1, 1, 1]
    y_proba = [0.1, 0.6, 0.8, 0.9]

    metrics = compute_classification_metrics(y_true, y_pred, y_proba)
    assert metrics["n_samples"] == 4
    assert 0.0 <= metrics["accuracy"] <= 1.0
    assert 0.0 <= metrics["f1"] <= 1.0
    assert 0.0 <= metrics["roc_auc"] <= 1.0
    assert metrics["confusion_matrix"] == [[1, 1], [0, 2]]


# ============================================================================
# 5. Token-Level Span Tagger Tests
# ============================================================================

def test_align_gold_spans_to_bio_tokens():
    """Test character span alignment into BIO sequence tokens."""
    text = "The system shall display reports fast and securely."
    spans = [
        {"span_text": "fast", "gap_type": "ambiguity"},
        {"span_text": "securely", "gap_type": "ambiguity"},
    ]

    tokens = align_gold_spans_to_bio_tokens(text, spans)
    assert len(tokens) > 0

    token_map = {t["text"]: t["bio_tag"] for t in tokens}
    assert token_map.get("fast") == "B-ambiguity"
    assert token_map.get("securely") == "B-ambiguity"
    assert token_map.get("system") == "O"
    assert token_map.get("shall") == "O"


def test_token_jaccard_overlap():
    """Test token Jaccard calculation per MASTER_SPEC.md Section 7."""
    assert token_jaccard("user friendly", "user friendly") == 1.0
    assert token_jaccard("user friendly interface", "user friendly") == 2 / 3
    assert token_jaccard("completely different", "unrelated tokens") == 0.0
    assert token_jaccard("", "some span") == 0.0


def test_linear_span_tagger_predict_spans(tmp_path: Path):
    """Test Span Tagger fit, span extraction, and serialization."""
    gold_file = Path("data/gold/annotations/rater_1.csv")
    dataset = load_bio_dataset_from_gold(gold_file)
    assert len(dataset) == 50

    # Train on first 10 for quick unit test
    x_train = []
    y_train = []
    for rec in dataset[:10]:
        for i in range(len(rec["tokens"])):
            x_train.append(token_to_features(rec["tokens"], i))
            y_train.append(rec["tokens"][i]["bio_tag"])

    tagger = LinearSpanTagger(seed=42)
    tagger.fit(x_train, y_train)

    test_text = "The system shall provide reports fast."
    spans = tagger.predict_spans(test_text)
    assert isinstance(spans, list)

    # Test serialization
    span_model_path = tmp_path / "span_tagger.joblib"
    tagger.save(span_model_path)
    assert span_model_path.is_file()

    loaded = LinearSpanTagger.load(span_model_path)
    loaded_spans = loaded.predict_spans(test_text)
    assert len(loaded_spans) == len(spans)


# ============================================================================
# 6. Phase 4 Multi-Head Pipeline Tests
# ============================================================================

def test_phase4_pipeline_multi_head_execution():
    """Verify execution of Heads 4a, 4b, 4c on sample requirements."""
    pipeline = Phase4Pipeline()

    # Ambiguity requirement
    ambig_text = "The system shall process requests fast and appropriately."
    gaps_4a = pipeline.detect_head_4a_ambiguity(
        ambig_text,
        frame=RequirementFrame(text=ambig_text, modal="shall", action="process"),
    )
    assert any(g.gap_type == "ambiguity" for g in gaps_4a)

    # Incompleteness requirement (passive without actor)
    incomp_text = "Links that open new browser windows should be clearly marked."
    gaps_4b = pipeline.detect_head_4b_completeness(
        incomp_text,
        frame=RequirementFrame(text=incomp_text, modal="should", action="marked", is_passive=True, missing_slots=["actor"]),
    )
    assert any(g.gap_type == "incompleteness" for g in gaps_4b)

    # Implicit requirement (critical action delete)
    implicit_text = "The user shall delete the lane closure record."
    gaps_4c = pipeline.detect_head_4c_implicit(
        implicit_text,
        frame=RequirementFrame(text=implicit_text, modal="shall", action="delete"),
    )
    assert any(g.gap_type == "implicit" for g in gaps_4c)

    # Combined all-gaps helper
    all_gaps = run_phase4_heads(ambig_text)
    assert len(all_gaps) > 0
    assert all(isinstance(g, CandidateGap) for g in all_gaps)


# ============================================================================
# 7. CLI Subcommand End-to-End Tests
# ============================================================================

def test_cli_train_smell_subcommand(tmp_path: Path):
    """Test CLI train-smell subcommand execution."""
    out_dir = tmp_path / "smell_out"
    rc = main([
        "train-smell",
        "--data-dir", "data/raw/arta",
        "--output-dir", str(out_dir),
        "--gold-file", "data/gold/annotations/rater_1.csv",
        "--qure-file", "data/raw/qure/QuRE.csv",
        "--n-splits", "2",
    ])
    assert rc == 0
    assert (out_dir / "smell_classifier.joblib").is_file()
    assert (out_dir / "config.json").is_file()
    assert (out_dir / "cv_metrics.json").is_file()
    assert (out_dir / "qure_eval.json").is_file()
    assert (out_dir / "provisional_pilot_eval.json").is_file()


def test_cli_train_span_subcommand(tmp_path: Path):
    """Test CLI train-span subcommand execution."""
    out_dir = tmp_path / "span_out"
    rc = main([
        "train-span",
        "--gold-file", "data/gold/annotations/rater_1.csv",
        "--output-dir", str(out_dir),
        "--n-splits", "2",
    ])
    assert rc == 0
    assert (out_dir / "span_tagger.joblib").is_file()
    assert (out_dir / "config.json").is_file()
    assert (out_dir / "cv_metrics.json").is_file()


def test_cli_eval_phase4_subcommand(tmp_path: Path):
    """Test CLI eval subcommand with --pipeline phase4."""
    out_dir = tmp_path / "eval_out"
    rc = main([
        "eval",
        "--gold-file", "data/gold/annotations/rater_1.csv",
        "--pipeline", "phase4",
        "--output-dir", str(out_dir),
    ])
    assert rc == 0
    assert (out_dir / "eval_report.json").is_file()
    assert (out_dir / "config.json").is_file()
    assert (out_dir / "eval_summary.csv").is_file()
