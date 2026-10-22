"""Sampling and data partitioning protocol for CheckSense (Phase 3).

Per MASTER_SPEC.md Section 4:
Samples at least 600 requirements from at least 20 PURE documents using seed 42.
Holds out approximately 25% of documents as an unseen, untouched test set
(document-level hold-out to strictly prevent cross-requirement document contamination).
Generates sample manifests, the 600+ requirement pool, pilot double-annotation sheets,
and the canonical gold annotation templates.
"""

from __future__ import annotations

import csv
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

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


def partition_documents(
    doc_ids: list[str],
    held_out_ratio: float = 0.25,
    seed: int = 42,
) -> tuple[list[str], list[str]]:
    """Deterministically partition documents into dev and held-out test sets.

    Ensures 0 document overlap between splits.
    """
    sorted_docs = sorted(doc_ids)
    rng = random.Random(seed)
    shuffled = sorted_docs.copy()
    rng.shuffle(shuffled)

    k_test = max(1, round(len(sorted_docs) * held_out_ratio))
    test_docs = sorted(shuffled[:k_test])
    dev_docs = sorted(shuffled[k_test:])

    # Strict invariant assertion: disjoint document sets
    overlap = set(test_docs) & set(dev_docs)
    if overlap:
        raise ValueError(f"Contamination error: documents overlap between dev and test: {overlap}")

    return dev_docs, test_docs


def sample_requirements(
    input_file: Path = Path("data/interim/pure_requirements.jsonl"),
    output_dir: Path = Path("data/gold"),
    n_samples: int = 600,
    n_documents: int = 20,
    seed: int = 42,
    held_out_ratio: float = 0.25,
    pilot_size: int = 50,
) -> dict[str, Any]:
    """Execute Phase 3 sampling protocol over authentic PURE requirements.

    Args:
        input_file: Path to interim requirements JSONL.
        output_dir: Destination directory for gold artifacts.
        n_samples: Target minimum sample size (default: 600).
        n_documents: Target minimum document count (default: 20).
        seed: Deterministic random seed (default: 42).
        held_out_ratio: Ratio of documents held out for test (default: 0.25).
        pilot_size: Number of requirements for pilot double-annotation (default: 50).

    Returns:
        Manifest summary dictionary.
    """
    if not input_file.exists():
        raise FileNotFoundError(f"Input interim requirements not found: {input_file}")

    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load and group requirements by document
    docs_to_records: dict[str, list[dict[str, Any]]] = defaultdict(list)
    with open(input_file, encoding="utf-8") as f:
        for line in f:
            line_str = line.strip()
            if not line_str:
                continue
            record = json.loads(line_str)
            docs_to_records[record["doc_id"]].append(record)

    available_docs = sorted(docs_to_records.keys())
    if len(available_docs) < n_documents:
        raise ValueError(
            f"Insufficient documents in corpus: found {len(available_docs)}, "
            f"expected at least {n_documents}."
        )

    # 2. Partition documents into dev and held-out test splits
    dev_docs, test_docs = partition_documents(
        available_docs,
        held_out_ratio=held_out_ratio,
        seed=seed,
    )

    # 3. Stratified sampling within documents
    # Determine per-document sampling quota to hit target sample size
    sampled_records: list[dict[str, Any]] = []
    per_doc_counts: dict[str, int] = {}

    # Target: ~25 per test document (>= 150 test requirements)
    # Remaining from dev documents (>= 450 dev requirements)
    test_target_per_doc = max(25, round((n_samples * held_out_ratio) / len(test_docs)))
    dev_target_per_doc = max(25, round((n_samples * (1 - held_out_ratio)) / len(dev_docs)))

    for split_name, split_doc_list, target_per_doc in [
        ("test", test_docs, test_target_per_doc),
        ("dev", dev_docs, dev_target_per_doc),
    ]:
        for idx, doc_id in enumerate(split_doc_list):
            doc_pool = docs_to_records[doc_id]
            doc_rng = random.Random(seed + idx * 31 + (100 if split_name == "test" else 0))

            k = min(len(doc_pool), target_per_doc)
            selected = doc_rng.sample(doc_pool, k=k)
            # Sort within document by sent_idx for natural document order
            selected.sort(key=lambda r: r.get("sent_idx", 0))

            for row in selected:
                row_copy = dict(row)
                row_copy["split"] = split_name
                sampled_records.append(row_copy)

            per_doc_counts[doc_id] = k

    # If rounding led to slightly less than n_samples, top up from dev documents with capacity
    if len(sampled_records) < n_samples:
        dev_sampled_ids = {r["req_id"] for r in sampled_records}
        for doc_id in dev_docs:
            if len(sampled_records) >= n_samples:
                break
            remaining = [r for r in docs_to_records[doc_id] if r["req_id"] not in dev_sampled_ids]
            if remaining:
                extra = remaining[0]
                extra_copy = dict(extra)
                extra_copy["split"] = "dev"
                sampled_records.append(extra_copy)
                dev_sampled_ids.add(extra_copy["req_id"])
                per_doc_counts[doc_id] += 1

    dev_count = sum(1 for r in sampled_records if r["split"] == "dev")
    test_count = sum(1 for r in sampled_records if r["split"] == "test")

    # 4. Write sample pool (JSONL)
    sample_pool_path = output_dir / "sample_pool.jsonl"
    with open(sample_pool_path, "w", encoding="utf-8") as f:
        for r in sampled_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # 5. Select deterministic pilot sample from dev split
    dev_records = [r for r in sampled_records if r["split"] == "dev"]
    pilot_rng = random.Random(seed)
    actual_pilot_k = min(pilot_size, len(dev_records))
    pilot_records = pilot_rng.sample(dev_records, k=actual_pilot_k)
    # Sort pilot by doc_id, sent_idx
    pilot_records.sort(key=lambda r: (r["doc_id"], r.get("sent_idx", 0)))

    pilot_file_path = output_dir / "pilot_sample.csv"
    with open(pilot_file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ANNOTATION_COLUMNS)
        writer.writeheader()
        for r in pilot_records:
            writer.writerow({
                "req_id": r["req_id"],
                "doc_id": r["doc_id"],
                "text": r["text"],
                "has_gap": "",
                "gap_type": "",
                "subtype": "",
                "span_text": "",
                "severity": "",
                "explanation": "",
                "question": "",
                "stakeholder_answer": "",
                "refined_text": "",
                "annotator": "",
                "label_status": "draft",
                "notes": f"Pilot candidate from {r['source_file']}",
            })

    # 6. Write blank annotation template
    template_path = output_dir / "annotations_template.csv"
    with open(template_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ANNOTATION_COLUMNS)
        writer.writeheader()

    # 7. Write manifest
    manifest_data: dict[str, Any] = {
        "seed": seed,
        "n_samples_requested": n_samples,
        "total_sampled": len(sampled_records),
        "dev_count": dev_count,
        "test_count": test_count,
        "total_documents": len(available_docs),
        "dev_documents_count": len(dev_docs),
        "test_documents_count": len(test_docs),
        "held_out_ratio_effective": round(len(test_docs) / len(available_docs), 4),
        "test_documents": test_docs,
        "dev_documents": dev_docs,
        "per_document_counts": per_doc_counts,
        "pilot_sample_size": len(pilot_records),
        "contamination_audit": {
            "disjoint_documents": len(set(dev_docs) & set(test_docs)) == 0,
            "status": "PASSED (0 document overlap)",
        },
        "artifacts": {
            "sample_pool": str(sample_pool_path),
            "pilot_sample": str(pilot_file_path),
            "annotations_template": str(template_path),
        },
    }

    manifest_path = output_dir / "sample_manifest.json"
    manifest_path.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

    return manifest_data
