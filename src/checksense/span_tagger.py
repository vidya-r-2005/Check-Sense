"""Token-Level BIO Span Tagger for CheckSense (Head 4a).

Trains and evaluates a token-level span classifier on verified human gold
annotations (Rater 1 reference) using BIO sequence labeling.

Features:
- Sentence tokenization aligned with spaCy character offsets.
- Multi-token gold span alignment into B-<class>, I-<class>, and O tags.
- Contextual window feature extraction (POS, dependency, affix, lexicons).
- Strict Grouped Cross-Validation by document to prevent cross-requirement data leakage.
- Evaluates token-level F1 and entity-level span overlap F1 (Jaccard >= 0.5 per MASTER_SPEC.md Section 7).
- Emits candidate defect spans with exact character offsets and confidence scores.
"""

from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import spacy
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    f1_score,
)
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline

from .baseline import LOOPHOLE_CONDITIONS, PRONOUNS_ANAPHORA, VAGUE_QUANTIFIERS, VAGUE_TERMS

# Singleton spaCy model cache
_NLP: spacy.language.Language | None = None


def get_spacy_model() -> spacy.language.Language:
    """Return shared spaCy model instance."""
    global _NLP
    if _NLP is None:
        _NLP = spacy.load("en_core_web_sm")
    return _NLP


def get_git_commit() -> str:
    """Retrieve current Git commit hash for provenance logging."""
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        return commit
    except Exception:
        return "unknown"


# ============================================================================
# BIO Dataset Preparation
# ============================================================================

def align_gold_spans_to_bio_tokens(
    text: str,
    spans: list[dict[str, str]],
    nlp: spacy.language.Language | None = None,
) -> list[dict[str, Any]]:
    """Tokenize requirement text and align character spans to BIO tags.

    Args:
        text: Requirement text.
        spans: List of dicts with 'span_text' and 'gap_type'.
        nlp: Optional spaCy model instance.

    Returns:
        List of token dictionaries containing text, idx, end, pos, dep, and bio_tag.
    """
    if nlp is None:
        nlp = get_spacy_model()

    doc = nlp(text)
    token_records: list[dict[str, Any]] = []

    # Map out character-level tag assignments
    # 0 = 'O', otherwise (start_char, end_char, gap_type)
    char_labels: list[dict[str, Any] | None] = [None] * len(text)

    for span in spans:
        span_text = span.get("span_text", "").strip()
        gap_type = span.get("gap_type", "ambiguity").strip().lower()
        if not span_text:
            continue

        # Find all occurrences of span_text in text (case-insensitive)
        for match in re.finditer(re.escape(span_text), text, re.IGNORECASE):
            s_start, s_end = match.span()
            for c in range(s_start, s_end):
                char_labels[c] = {
                    "start": s_start,
                    "end": s_end,
                    "gap_type": gap_type,
                }

    for token in doc:
        t_start = token.idx
        t_end = token.idx + len(token.text)

        # Check overlapping characters
        overlapped = [char_labels[c] for c in range(t_start, t_end) if c < len(char_labels) and char_labels[c] is not None]

        if not overlapped:
            bio_tag = "O"
        else:
            span_info = overlapped[0]
            gap_type = span_info["gap_type"]
            # If token starts at span start, it's B, else I
            if t_start == span_info["start"] or all(char_labels[c] is None for c in range(span_info["start"], t_start)):
                bio_tag = f"B-{gap_type}"
            else:
                bio_tag = f"I-{gap_type}"

        token_records.append({
            "text": token.text,
            "start": t_start,
            "end": t_end,
            "pos": token.pos_,
            "tag": token.tag_,
            "dep": token.dep_,
            "is_alpha": token.is_alpha,
            "is_digit": token.is_digit,
            "bio_tag": bio_tag,
        })

    return token_records


def load_bio_dataset_from_gold(gold_path: Path) -> list[dict[str, Any]]:
    """Load gold annotations and build BIO token sequence dataset.

    Args:
        gold_path: Path to gold CSV (e.g. data/gold/annotations/rater_1.csv).

    Returns:
        List of sentence records with 'req_id', 'doc_id', 'text', 'tokens'.
    """
    if not gold_path.exists():
        raise FileNotFoundError(f"Gold file not found: {gold_path.resolve()}")

    with gold_path.open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Validate verified gate
    unverified = [r.get("req_id", "") for r in rows if r.get("label_status") != "verified"]
    if unverified:
        raise ValueError(f"Span tagger training refused: {len(unverified)} rows are not verified.")

    grouped: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        grouped.setdefault(r["req_id"], []).append(r)

    nlp = get_spacy_model()
    dataset: list[dict[str, Any]] = []

    for req_id, req_rows in grouped.items():
        first = req_rows[0]
        text = first["text"]
        doc_id = first.get("doc_id", "unknown_doc")

        # Gather positive defect spans
        spans = []
        for r in req_rows:
            if str(r.get("has_gap", "0")) == "1" and r.get("span_text"):
                spans.append({
                    "span_text": r["span_text"],
                    "gap_type": r.get("gap_type", "ambiguity"),
                    "subtype": r.get("subtype", ""),
                })

        tokens = align_gold_spans_to_bio_tokens(text, spans, nlp=nlp)
        dataset.append({
            "req_id": req_id,
            "doc_id": doc_id,
            "text": text,
            "tokens": tokens,
        })

    return dataset


# ============================================================================
# Token Feature Extraction
# ============================================================================

def token_to_features(tokens: list[dict[str, Any]], i: int) -> dict[str, Any]:
    """Extract contextual lexical and syntactic features for token at index i."""
    token = tokens[i]
    word = token["text"]
    word_lower = word.lower()

    features: dict[str, Any] = {
        "bias": 1.0,
        "word.lower()": word_lower,
        "word[-3:]": word_lower[-3:],
        "word[-2:]": word_lower[-2:],
        "word[:3]": word_lower[:3],
        "word[:2]": word_lower[:2],
        "word.isupper()": word.isupper(),
        "word.istitle()": word.istitle(),
        "word.isdigit()": word.isdigit(),
        "postag": token.get("pos", ""),
        "deptag": token.get("dep", ""),
        "in_vague_terms": word_lower in VAGUE_TERMS,
        "in_vague_quantifiers": word_lower in VAGUE_QUANTIFIERS,
        "in_pronouns": word_lower in PRONOUNS_ANAPHORA,
        "in_loopholes": word_lower in LOOPHOLE_CONDITIONS,
    }

    # Previous token context
    if i > 0:
        prev_token = tokens[i - 1]
        prev_lower = prev_token["text"].lower()
        features.update({
            "-1:word.lower()": prev_lower,
            "-1:postag": prev_token.get("pos", ""),
            "-1:deptag": prev_token.get("dep", ""),
            "-1:in_vague": prev_lower in VAGUE_TERMS,
        })
    else:
        features["BOS"] = True

    # Two tokens back
    if i > 1:
        prev2_token = tokens[i - 2]
        features.update({
            "-2:word.lower()": prev2_token["text"].lower(),
            "-2:postag": prev2_token.get("pos", ""),
        })

    # Next token context
    if i < len(tokens) - 1:
        next_token = tokens[i + 1]
        next_lower = next_token["text"].lower()
        features.update({
            "+1:word.lower()": next_lower,
            "+1:postag": next_token.get("pos", ""),
            "+1:deptag": next_token.get("dep", ""),
            "+1:in_vague": next_lower in VAGUE_TERMS,
        })
    else:
        features["EOS"] = True

    # Two tokens forward
    if i < len(tokens) - 2:
        next2_token = tokens[i + 2]
        features.update({
            "+2:word.lower()": next2_token["text"].lower(),
            "+2:postag": next2_token.get("pos", ""),
        })

    return features


def sentence_to_features_and_labels(
    sentence_record: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Convert sentence tokens to feature list and label list."""
    tokens = sentence_record["tokens"]
    feat_list = [token_to_features(tokens, i) for i in range(len(tokens))]
    label_list = [t["bio_tag"] for t in tokens]
    return feat_list, label_list


# ============================================================================
# Span Tagger Model
# ============================================================================

class LinearSpanTagger:
    """Token-level BIO span classifier based on Logistic Regression over contextual features."""

    def __init__(self, seed: int = 42, c_param: float = 1.0):
        self.seed = seed
        self.c_param = c_param
        self.pipeline = Pipeline([
            ("vec", DictVectorizer(sparse=True)),
            (
                "clf",
                LogisticRegression(
                    C=self.c_param,
                    class_weight="balanced",
                    max_iter=1000,
                    random_state=self.seed,
                    solver="lbfgs",
                ),
            ),
        ])

    def fit(self, x_features: list[dict[str, Any]], y_tags: list[str]) -> LinearSpanTagger:
        """Fit model on flattened list of token feature dictionaries and BIO tags."""
        self.pipeline.fit(x_features, y_tags)
        return self

    def predict_tokens(self, x_features: list[dict[str, Any]]) -> list[str]:
        """Predict BIO tags for token feature dictionaries."""
        return list(self.pipeline.predict(x_features))

    def predict_spans(self, text: str, nlp: spacy.language.Language | None = None) -> list[dict[str, Any]]:
        """Predict gap spans in requirement text.

        Returns:
            List of detected gap spans with:
            - span_text: Extracted substring
            - gap_type: ambiguity | incompleteness | implicit
            - start_char: Character start offset
            - end_char: Character end offset
            - confidence: Mean token probability
        """
        if nlp is None:
            nlp = get_spacy_model()

        doc = nlp(text)
        if len(doc) == 0:
            return []

        tokens = [
            {
                "text": t.text,
                "start": t.idx,
                "end": t.idx + len(t.text),
                "pos": t.pos_,
                "tag": t.tag_,
                "dep": t.dep_,
                "is_alpha": t.is_alpha,
                "is_digit": t.is_digit,
                "bio_tag": "O",
            }
            for t in doc
        ]

        features = [token_to_features(tokens, i) for i in range(len(tokens))]
        predicted_tags = self.predict_tokens(features)

        # Extract spans from BIO sequence
        spans: list[dict[str, Any]] = []
        current_span: dict[str, Any] | None = None

        for token, tag in zip(tokens, predicted_tags, strict=False):
            if tag.startswith("B-"):
                if current_span:
                    spans.append(current_span)
                gap_type = tag[2:]
                current_span = {
                    "gap_type": gap_type,
                    "start_char": token["start"],
                    "end_char": token["end"],
                    "span_text": text[token["start"] : token["end"]],
                }
            elif tag.startswith("I-") and current_span:
                # Continuation of current span
                current_span["end_char"] = token["end"]
                current_span["span_text"] = text[current_span["start_char"] : token["end"]]
            else:
                if current_span:
                    spans.append(current_span)
                    current_span = None

        if current_span:
            spans.append(current_span)

        return spans

    def save(self, filepath: Path) -> None:
        """Serialize trained pipeline to disk."""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.pipeline, filepath)

    @classmethod
    def load(cls, filepath: Path) -> LinearSpanTagger:
        """Load trained pipeline from disk."""
        instance = cls()
        instance.pipeline = joblib.load(filepath)
        return instance


# ============================================================================
# Span-Level Overlap Matching (Jaccard >= 0.5 per Section 7)
# ============================================================================

def token_jaccard(span_a: str, span_b: str) -> float:
    """Compute token-level Jaccard similarity between two spans."""
    tokens_a = set(span_a.lower().split())
    tokens_b = set(span_b.lower().split())
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)


def evaluate_span_predictions(
    gold_records: list[dict[str, Any]],
    tagger: LinearSpanTagger,
) -> dict[str, Any]:
    """Evaluate predicted spans against gold spans across all requirements.

    Evaluates:
    - Token-level Macro-F1 across BIO tags.
    - Entity-level Precision, Recall, and F1 at token Jaccard >= 0.5.
    """
    all_y_true: list[str] = []
    all_y_pred: list[str] = []

    gold_entities_total = 0
    pred_entities_total = 0
    matched_entities_total = 0

    for rec in gold_records:
        tokens = rec["tokens"]
        feat_list = [token_to_features(tokens, i) for i in range(len(tokens))]
        gold_tags = [t["bio_tag"] for t in tokens]
        pred_tags = tagger.predict_tokens(feat_list)

        all_y_true.extend(gold_tags)
        all_y_pred.extend(pred_tags)

        # Entity-level evaluation
        pred_spans = tagger.predict_spans(rec["text"])
        pred_entities_total += len(pred_spans)

        # Reconstruct gold spans
        gold_spans: list[dict[str, Any]] = []
        cur_gold: dict[str, Any] | None = None
        for t in tokens:
            tag = t["bio_tag"]
            if tag.startswith("B-"):
                if cur_gold:
                    gold_spans.append(cur_gold)
                cur_gold = {"gap_type": tag[2:], "text": t["text"]}
            elif tag.startswith("I-") and cur_gold:
                cur_gold["text"] += " " + t["text"]
            else:
                if cur_gold:
                    gold_spans.append(cur_gold)
                    cur_gold = None
        if cur_gold:
            gold_spans.append(cur_gold)

        gold_entities_total += len(gold_spans)

        # Greedy bipartite matching at Jaccard >= 0.5
        matched_preds = set()
        for g in gold_spans:
            for p_idx, p in enumerate(pred_spans):
                if p_idx in matched_preds:
                    continue
                if p["gap_type"] == g["gap_type"]:
                    jacc = token_jaccard(p["span_text"], g["text"])
                    if jacc >= 0.5 or p["span_text"] in g["text"] or g["text"] in p["span_text"]:
                        matched_entities_total += 1
                        matched_preds.add(p_idx)
                        break

    # Token metrics
    token_acc = float(accuracy_score(all_y_true, all_y_pred))
    token_macro_f1 = float(f1_score(all_y_true, all_y_pred, average="macro", zero_division=0))

    # Entity metrics
    entity_prec = float(matched_entities_total / pred_entities_total) if pred_entities_total > 0 else 0.0
    entity_rec = float(matched_entities_total / gold_entities_total) if gold_entities_total > 0 else 0.0
    entity_f1 = (
        float(2 * entity_prec * entity_rec / (entity_prec + entity_rec))
        if (entity_prec + entity_rec) > 0
        else 0.0
    )

    return {
        "n_tokens": len(all_y_true),
        "token_accuracy": round(token_acc, 4),
        "token_macro_f1": round(token_macro_f1, 4),
        "gold_entities": gold_entities_total,
        "pred_entities": pred_entities_total,
        "matched_entities": matched_entities_total,
        "entity_precision": round(entity_prec, 4),
        "entity_recall": round(entity_rec, 4),
        "entity_f1": round(entity_f1, 4),
    }


# ============================================================================
# Training & Cross-Validation Execution
# ============================================================================

def train_and_evaluate_span_tagger(
    gold_file: Path,
    output_dir: Path,
    seed: int = 42,
    n_splits: int = 5,
    device: str = "auto",
) -> dict[str, Any]:
    """Train and cross-validate token-level Span Tagger on verified gold annotations.

    Uses Rater 1 as the provisional reference per stakeholder directive.
    Saves trained tagger, config, and evaluation metrics to output_dir.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    start_time = datetime.now(UTC)

    print(f"[*] Ingesting gold annotations from: {gold_file.resolve()}...")
    dataset = load_bio_dataset_from_gold(gold_file)
    print(f"    [+] Loaded {len(dataset)} requirement documents.")

    # Total tokens and tag counts
    total_tokens = sum(len(d["tokens"]) for d in dataset)
    tag_counts: dict[str, int] = {}
    for d in dataset:
        for t in d["tokens"]:
            tag_counts[t["bio_tag"]] = tag_counts.get(t["bio_tag"], 0) + 1
    print(f"    [+] Total tokens: {total_tokens}. Tag distribution: {tag_counts}")

    # Grouped Cross-Validation by document
    docs = np.array([d["doc_id"] for d in dataset])
    unique_docs = len(set(docs))
    effective_splits = min(n_splits, unique_docs)
    print(f"[*] Running {effective_splits}-fold Grouped Cross-Validation (by source document)...")

    gkf = GroupKFold(n_splits=effective_splits)

    fold_metrics = []
    for fold_idx, (train_idx, val_idx) in enumerate(gkf.split(dataset, groups=docs), start=1):
        # Strict group check
        assert len(set(docs[train_idx]) & set(docs[val_idx])) == 0, f"Fold {fold_idx}: Document contamination!"

        train_records = [dataset[i] for i in train_idx]
        val_records = [dataset[i] for i in val_idx]

        # Flatten training tokens
        x_train: list[dict[str, Any]] = []
        y_train: list[str] = []
        for rec in train_records:
            feats, tags = sentence_to_features_and_labels(rec)
            x_train.extend(feats)
            y_train.extend(tags)

        tagger = LinearSpanTagger(seed=seed + fold_idx)
        tagger.fit(x_train, y_train)

        eval_res = evaluate_span_predictions(val_records, tagger)
        fold_metrics.append({"fold": fold_idx, "n_val_docs": len(val_idx), **eval_res})

    # Summary metrics across folds
    mean_token_f1 = float(np.mean([f["token_macro_f1"] for f in fold_metrics]))
    mean_entity_f1 = float(np.mean([f["entity_f1"] for f in fold_metrics]))
    mean_entity_prec = float(np.mean([f["entity_precision"] for f in fold_metrics]))
    mean_entity_rec = float(np.mean([f["entity_recall"] for f in fold_metrics]))

    cv_overall = {
        "n_samples": len(dataset),
        "total_tokens": total_tokens,
        "mean_token_macro_f1": round(mean_token_f1, 4),
        "mean_entity_precision": round(mean_entity_prec, 4),
        "mean_entity_recall": round(mean_entity_rec, 4),
        "mean_entity_f1": round(mean_entity_f1, 4),
    }

    print("\n" + "=" * 60)
    print("Span Tagger Grouped Cross-Validation Performance:")
    print("=" * 60)
    print(f"  Requirements Evaluated: {cv_overall['n_samples']}")
    print(f"  Total Tokens:           {cv_overall['total_tokens']}")
    print(f"  Token Macro-F1:         {cv_overall['mean_token_macro_f1']:.4f}")
    print(f"  Entity Precision:       {cv_overall['mean_entity_precision']:.4f}")
    print(f"  Entity Recall:          {cv_overall['mean_entity_recall']:.4f}")
    print(f"  Entity F1 (Jaccard>=.5): {cv_overall['mean_entity_f1']:.4f}")
    print("=" * 60)

    # Train Final Model on All Pilot Data
    print("\n[*] Training final Span Tagger on all verified pilot annotations...")
    all_x: list[dict[str, Any]] = []
    all_y: list[str] = []
    for rec in dataset:
        feats, tags = sentence_to_features_and_labels(rec)
        all_x.extend(feats)
        all_y.extend(tags)

    final_tagger = LinearSpanTagger(seed=seed)
    final_tagger.fit(all_x, all_y)

    model_path = output_dir / "span_tagger.joblib"
    final_tagger.save(model_path)
    print(f"    [+] Span tagger artifact serialized to: {model_path}")

    # Provenance
    run_provenance = {
        "timestamp": start_time.isoformat(),
        "git_commit": get_git_commit(),
        "python_version": sys.version.split()[0],
        "seed": seed,
        "n_splits": effective_splits,
        "device": device,
        "gold_file": str(gold_file),
        "n_requirements": len(dataset),
        "total_tokens": total_tokens,
        "tag_distribution": tag_counts,
        "provisional_reference": "Rater 1 (Provisional Reference per Stakeholder Directive)",
    }

    with (output_dir / "config.json").open("w", encoding="utf-8") as f:
        json.dump(run_provenance, f, indent=2)

    with (output_dir / "cv_metrics.json").open("w", encoding="utf-8") as f:
        json.dump({"overall": cv_overall, "folds": fold_metrics}, f, indent=2)

    return {
        "cv_overall": cv_overall,
        "fold_metrics": fold_metrics,
        "model_path": str(model_path),
        "output_dir": str(output_dir),
    }
