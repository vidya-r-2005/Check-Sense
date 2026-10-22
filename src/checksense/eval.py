"""Evaluation runner and strict label-status gating for CheckSense.

Enforces Rule 4 from AGENTS.md and MASTER_SPEC.md:
    "Gold labels need label_status=verified (human-confirmed).
     LLM drafts stay 'draft'. Evaluation refuses non-verified rows."

If any evaluated row in the gold dataset does not have label_status == 'verified',
the evaluation runner immediately halts with an UnverifiedEvaluationError and
refuses to emit metrics or write results.
"""

from __future__ import annotations

import csv
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .baseline import detect_rule_gaps
from .metrics import EvaluationReport, evaluate_predictions


class UnverifiedEvaluationError(ValueError):
    """Raised when evaluation is attempted on unverified gold annotation rows."""

    pass


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


def load_and_verify_gold_data(gold_path: Path) -> dict[str, list[dict[str, Any]]]:
    """Load gold annotation file and enforce strict human verification.

    Args:
        gold_path: Path to gold CSV or JSONL file.

    Returns:
        Mapping of req_id -> list of verified gold gap dictionaries.

    Raises:
        FileNotFoundError: If gold file does not exist.
        UnverifiedEvaluationError: If any row is missing or has label_status != 'verified'.
    """
    if not gold_path.exists():
        raise FileNotFoundError(f"Gold annotations file not found: {gold_path.resolve()}")

    rows: list[dict[str, Any]] = []

    if gold_path.suffix.lower() == ".jsonl":
        with gold_path.open("r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                line = line.strip()
                if line:
                    item = json.loads(line)
                    item["_row_num"] = line_no
                    rows.append(item)
    else:
        # Default to CSV
        with gold_path.open("r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row_no, row in enumerate(reader, start=2):
                row["_row_num"] = row_no
                rows.append(row)

    if not rows:
        raise ValueError(f"Gold annotation file is empty: {gold_path}")

    # Strict Gating Check
    unverified_violations: list[str] = []
    req_gold: dict[str, list[dict[str, Any]]] = {}

    for row in rows:
        req_id = str(row.get("req_id", f"unknown_{row['_row_num']}"))
        status = row.get("label_status")

        if status != "verified":
            unverified_violations.append(
                f"Row {row['_row_num']} (req_id='{req_id}'): label_status='{status}' (expected 'verified')"
            )

        req_gold.setdefault(req_id, []).append(row)

    if unverified_violations:
        sample = "\n  - ".join(unverified_violations[:5])
        n_more = len(unverified_violations) - 5
        more_str = f"\n  ... and {n_more} more unverified rows" if n_more > 0 else ""
        raise UnverifiedEvaluationError(
            f"Evaluation REJECTED: Found {len(unverified_violations)} unverified rows in '{gold_path}'.\n"
            f"Per MASTER_SPEC.md Rule 4, evaluation strictly refuses to run on rows unless label_status='verified'.\n"
            f"Violations:\n  - {sample}{more_str}"
        )

    return req_gold


def load_predictions(pred_path: Path) -> dict[str, list[dict[str, Any]]]:
    """Load predicted gaps from CSV or JSONL.

    Args:
        pred_path: Path to predictions file.

    Returns:
        Mapping of req_id -> list of predicted gap dictionaries.
    """
    req_preds: dict[str, list[dict[str, Any]]] = {}

    if pred_path.suffix.lower() == ".jsonl":
        with pred_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    item = json.loads(line)
                    req_id = str(item.get("req_id", ""))
                    req_preds.setdefault(req_id, []).append(item)
    else:
        with pred_path.open("r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                req_id = str(row.get("req_id", ""))
                req_preds.setdefault(req_id, []).append(row)

    return req_preds


def generate_baseline_predictions(
    req_gold: dict[str, list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    """Generate Baseline B1 rule predictions for requirements in gold set."""
    req_preds: dict[str, list[dict[str, Any]]] = {}

    for req_id, gold_rows in req_gold.items():
        # Get requirement text from first row
        text = str(gold_rows[0].get("text", ""))
        if not text:
            continue
        gaps = detect_rule_gaps(text)
        req_preds[req_id] = [g.to_dict() for g in gaps]

    return req_preds


def run_evaluation(
    gold_file: Path,
    predictions_file: Path | None = None,
    output_dir: Path | None = None,
    req_level: bool = False,
    model_name: str = "B1_rules",
) -> EvaluationReport:
    """Execute evaluation on verified gold annotations.

    Args:
        gold_file: Path to gold annotations (strictly gated).
        predictions_file: Optional path to pre-computed predictions.
        output_dir: Optional directory to store logged results.
        req_level: Whether to evaluate matching at requirement level.
        model_name: Identifier for model/baseline being evaluated.

    Returns:
        EvaluationReport dataclass.

    Raises:
        UnverifiedEvaluationError: If any gold row has label_status != 'verified'.
    """
    # 1. Gate check: load and verify all rows
    req_gold = load_and_verify_gold_data(gold_file)

    # 2. Get predictions (from file or generate B1 baseline)
    if predictions_file and predictions_file.exists():
        req_preds = load_predictions(predictions_file)
    else:
        req_preds = generate_baseline_predictions(req_gold)

    # 3. Compute metrics
    report = evaluate_predictions(req_preds, req_gold, req_level=req_level)

    # 4. Save results with provenance if output_dir provided
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)

        run_provenance = {
            "timestamp": datetime.now(UTC).isoformat(),
            "git_commit": get_git_commit(),
            "gold_file": str(gold_file.resolve()),
            "predictions_file": str(predictions_file.resolve()) if predictions_file else "generated_b1",
            "model_name": model_name,
            "req_level": req_level,
        }

        # Save config & metadata
        with (output_dir / "config.json").open("w", encoding="utf-8") as f:
            json.dump(run_provenance, f, indent=2)

        # Save full metrics JSON
        with (output_dir / "eval_report.json").open("w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2)

        # Save concise summary CSV
        summary_rows = [
            {"metric": "macro_f1", "value": report.macro_f1},
            {"metric": "micro_f1", "value": report.micro_f1},
            {"metric": "micro_f2", "value": report.micro_f2},
            {"metric": "has_gap_f1", "value": report.has_gap_f1},
            {"metric": "has_gap_pr_auc", "value": report.has_gap_pr_auc},
            {"metric": "false_alarm_rate_clean", "value": report.false_alarm_rate_clean},
            {"metric": "spearman_rho", "value": report.spearman_rho},
            {"metric": "ndcg_at_3", "value": report.ndcg_at_3},
            {"metric": "ece", "value": report.ece},
            {"metric": "brier_score", "value": report.brier_score},
        ]
        for cname, cmetrics in report.per_class.items():
            summary_rows.extend([
                {"metric": f"class_{cname}_precision", "value": cmetrics.precision},
                {"metric": f"class_{cname}_recall", "value": cmetrics.recall},
                {"metric": f"class_{cname}_f1", "value": cmetrics.f1},
            ])

        with (output_dir / "eval_summary.csv").open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["metric", "value"])
            writer.writeheader()
            writer.writerows(summary_rows)

    return report
