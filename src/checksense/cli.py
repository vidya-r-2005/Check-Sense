"""Command Line Interface for CheckSense.

Usage:
    python -m checksense.cli <command> [options]

Subcommands:
    download         Acquire and verify real external datasets (PURE, ARTA, QuRE, etc.)
    build-corpus     Parse raw requirements into clean, structured interim JSONL
    sample           Sample requirements for pilot / gold human annotation with held-out splits
    annotate-stats   Calculate annotation statistics and inter-rater agreement (Cohen's kappa)
    train-smell      Train and evaluate the sentence-level smell classifier
    train-span       Train and evaluate the token-level SpanBERT span tagger
    train-fusion     Train the candidate-level fusion and severity scorer
    eval             Evaluate predictions against human-verified gold labels
    rate-make        Generate blinded human rating sheets for questions and refinements
    rate-score       Score blinded human ratings with agreement and bootstrap statistics
    report           Generate paper-ready performance reports from logged results
    serve            Launch the CheckSense analysis or annotation Streamlit application
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from .version import __version__


def create_parser() -> argparse.ArgumentParser:
    """Create the top-level argument parser and subcommands."""
    parser = argparse.ArgumentParser(
        prog="python -m checksense.cli",
        description="CheckSense: NLP system for detecting gaps in software requirements.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"CheckSense {__version__}",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        title="subcommands",
        description="Valid CheckSense operations",
        required=True,
    )

    # 1. download
    p_download = subparsers.add_parser(
        "download",
        help="Download and verify real datasets from Zenodo / open repositories.",
    )
    p_download.add_argument(
        "--dataset",
        choices=["pure", "arta", "qure", "promise_exp", "dalpiaz", "unverified", "all"],
        default="all",
        help="Target dataset to acquire and verify (default: all).",
    )
    p_download.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/raw"),
        help="Target destination directory for raw downloads.",
    )
    p_download.add_argument(
        "--skip-checksum",
        action="store_true",
        help="Skip checksum verification (NOT recommended; logged in MANIFEST).",
    )
    p_download.set_defaults(func=_cmd_download)

    # 2. build-corpus
    p_build = subparsers.add_parser(
        "build-corpus",
        help="Parse raw PURE requirements into data/interim/pure_requirements.jsonl.",
    )
    p_build.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data/raw/pure"),
        help="Directory containing raw PURE XML and PDF documents.",
    )
    p_build.add_argument(
        "--output-file",
        type=Path,
        default=Path("data/interim/pure_requirements.jsonl"),
        help="Destination JSONL path for normalized requirements.",
    )
    p_build.add_argument(
        "--min-tokens",
        type=int,
        default=5,
        help="Minimum token length for requirements (default: 5).",
    )
    p_build.add_argument(
        "--max-tokens",
        type=int,
        default=60,
        help="Maximum token length for requirements (default: 60).",
    )
    p_build.set_defaults(func=_cmd_build_corpus)

    # 3. sample
    p_sample = subparsers.add_parser(
        "sample",
        help="Sample requirements for human annotation and partition held-out documents.",
    )
    p_sample.add_argument(
        "--input-file",
        type=Path,
        default=Path("data/interim/pure_requirements.jsonl"),
        help="Source interim requirements JSONL.",
    )
    p_sample.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/gold"),
        help="Destination directory for sample sheets and splits.",
    )
    p_sample.add_argument(
        "--n-samples",
        type=int,
        default=600,
        help="Total number of requirements to sample (default: 600).",
    )
    p_sample.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Deterministic sampling random seed (default: 42).",
    )
    p_sample.add_argument(
        "--held-out-ratio",
        type=float,
        default=0.25,
        help="Ratio of documents to partition into held-out test set (default: 0.25).",
    )
    p_sample.set_defaults(func=_cmd_sample)

    # 4. annotate-stats
    p_annot = subparsers.add_parser(
        "annotate-stats",
        help="Compute annotation statistics, verification progress, and inter-rater agreement.",
    )
    p_annot.add_argument(
        "--gold-file",
        type=Path,
        default=Path("data/gold/annotations.csv"),
        help="Path to human annotation CSV file.",
    )
    p_annot.add_argument(
        "--pilot-file-a",
        type=Path,
        default=None,
        help="First annotator file for Cohen's kappa agreement.",
    )
    p_annot.add_argument(
        "--pilot-file-b",
        type=Path,
        default=None,
        help="Second annotator file for Cohen's kappa agreement.",
    )
    p_annot.add_argument(
        "--pilot-reference-file",
        "--pilot-ref-file",
        dest="pilot_reference_file",
        type=Path,
        default=Path("data/gold/pilot_sample.csv"),
        help="Canonical pilot reference CSV containing complete intended pilot requirements (default: data/gold/pilot_sample.csv).",
    )
    p_annot.set_defaults(func=_cmd_annotate_stats)

    # 5. train-smell
    p_smell = subparsers.add_parser(
        "train-smell",
        help="Train and cross-validate sentence-level smell classifier on ARTA.",
    )
    p_smell.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data/raw/arta"),
        help="Directory containing ARTA dataset spreadsheets.",
    )
    p_smell.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/smell_classifier"),
        help="Destination directory for model checkpoints and evaluation logs.",
    )
    p_smell.add_argument(
        "--qure-file",
        type=Path,
        default=Path("data/raw/qure/QuRE.csv"),
        help="Path to external QuRE evaluation dataset.",
    )
    p_smell.add_argument(
        "--gold-file",
        type=Path,
        default=Path("data/gold/annotations/rater_1.csv"),
        help="Path to verified provisional gold annotations.",
    )
    p_smell.add_argument(
        "--model-type",
        choices=["tfidf_lr", "spanbert_lr", "all"],
        default="tfidf_lr",
        help="Classifier architecture.",
    )
    p_smell.add_argument("--seed", type=int, default=42, help="Random seed.")
    p_smell.add_argument("--n-splits", type=int, default=5, help="Number of grouped CV splits.")
    p_smell.add_argument("--device", type=str, default="auto", help="Compute device ('auto', 'cpu', 'cuda').")
    p_smell.set_defaults(func=_cmd_train_smell)

    # 6. train-span
    p_span = subparsers.add_parser(
        "train-span",
        help="Train and fine-tune token-level SpanBERT span tagger on human gold spans.",
    )
    p_span.add_argument(
        "--gold-file",
        type=Path,
        default=Path("data/gold/annotations/rater_1.csv"),
        help="Path to verified gold annotations.",
    )
    p_span.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/span_tagger"),
        help="Destination directory for model and metrics.",
    )
    p_span.add_argument("--seed", type=int, default=42, help="Random seed.")
    p_span.add_argument("--n-splits", type=int, default=5, help="Number of grouped CV splits.")
    p_span.add_argument("--device", type=str, default="auto", help="Compute device.")
    p_span.set_defaults(func=_cmd_train_span)

    # 7. train-fusion
    p_fusion = subparsers.add_parser(
        "train-fusion",
        help="Train the candidate-level fusion and severity scorer (MLP / fallback).",
    )
    p_fusion.add_argument(
        "--gold-file",
        type=Path,
        default=Path("data/gold/annotations/rater_1.csv"),
        help="Path to verified gold annotations.",
    )
    p_fusion.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/fusion_model"),
        help="Destination directory for model and calibration data.",
    )
    p_fusion.add_argument(
        "--smell-model",
        type=Path,
        default=Path("results/smell_classifier/smell_classifier.joblib"),
        help="Path to trained smell classifier artifact.",
    )
    p_fusion.add_argument(
        "--span-model",
        type=Path,
        default=Path("results/span_tagger/span_tagger.joblib"),
        help="Path to trained span tagger artifact.",
    )
    p_fusion.add_argument("--seed", type=int, default=42, help="Random seed.")
    p_fusion.add_argument("--n-splits", type=int, default=5, help="Number of grouped CV splits.")
    p_fusion.set_defaults(func=_cmd_train_fusion)

    # 8. eval
    p_eval = subparsers.add_parser(
        "eval",
        help="Evaluate gap detection pipeline on gold test set (refuses unverified rows).",
    )
    p_eval.add_argument(
        "--gold-file",
        type=Path,
        default=Path("data/gold/annotations/rater_1.csv"),
        help="Gold annotation file with label_status.",
    )
    p_eval.add_argument(
        "--predictions-file",
        type=Path,
        default=None,
        help="Optional path to pre-generated predictions file.",
    )
    p_eval.add_argument(
        "--pipeline",
        choices=[
            "b1",
            "b2",
            "b3",
            "b4",
            "phase4",
            "phase5",
            "ablation_no_4a",
            "ablation_no_4b",
            "ablation_no_4c",
            "ablation_plain_union",
        ],
        default="b1",
        help="Gap detection pipeline (baselines: 'b1', 'b2', 'b3', 'b4'; architectures: 'phase4', 'phase5'; ablations: 'ablation_no_4a', 'ablation_no_4b', 'ablation_no_4c', 'ablation_plain_union').",
    )
    p_eval.add_argument(
        "--smell-model",
        type=Path,
        default=Path("results/smell_classifier/smell_classifier.joblib"),
        help="Path to trained smell classifier artifact.",
    )
    p_eval.add_argument(
        "--span-model",
        type=Path,
        default=Path("results/span_tagger/span_tagger.joblib"),
        help="Path to trained span tagger artifact.",
    )
    p_eval.add_argument(
        "--fusion-model",
        type=Path,
        default=Path("results/fusion_model/fusion_model.joblib"),
        help="Path to trained fusion scorer artifact.",
    )
    p_eval.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/eval"),
        help="Directory to save evaluation results and metrics.",
    )
    p_eval.add_argument(
        "--req-level",
        action="store_true",
        help="Evaluate matching at requirement level rather than token span Jaccard.",
    )
    p_eval.set_defaults(func=_cmd_eval)

    # 9. rate-make
    p_rmake = subparsers.add_parser(
        "rate-make",
        help="Generate blinded human rating sheets with reference questions mixed in.",
    )
    p_rmake.add_argument(
        "--test-results",
        type=Path,
        default=Path("results/eval/predictions.jsonl"),
        help="Pipeline generation outputs.",
    )
    p_rmake.add_argument(
        "--output-sheet",
        type=Path,
        default=Path("results/ratings/blinded_rating_sheet.csv"),
        help="Output CSV for human raters.",
    )
    p_rmake.add_argument("--seed", type=int, default=42, help="Random seed for blinding.")
    p_rmake.set_defaults(func=_cmd_rate_make)

    # 10. rate-score
    p_rscore = subparsers.add_parser(
        "rate-score",
        help="Score human rating sheets with agreement (kappa) and bootstrap non-inferiority.",
    )
    p_rscore.add_argument(
        "--sheet-a",
        type=Path,
        required=True,
        help="First completed rating sheet CSV.",
    )
    p_rscore.add_argument(
        "--sheet-b",
        type=Path,
        default=None,
        help="Second completed rating sheet CSV for inter-rater reliability.",
    )
    p_rscore.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/ratings"),
        help="Output directory for rating metrics.",
    )
    p_rscore.set_defaults(func=_cmd_rate_score)

    # 11. report
    p_report = subparsers.add_parser(
        "report",
        help="Compile paper-ready tables and summary report strictly from results/*.csv.",
    )
    p_report.add_argument(
        "--results-dir",
        type=Path,
        default=Path("results"),
        help="Directory containing logged evaluation outputs.",
    )
    p_report.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports"),
        help="Directory to save compiled report and tables.",
    )
    p_report.add_argument(
        "--gold-file",
        type=Path,
        default=Path("data/gold/annotations/rater_1.csv"),
        help="Path to verified gold annotations.",
    )
    p_report.add_argument(
        "--summary-file",
        type=Path,
        default=Path("results/summary.csv"),
        help="Destination path for the comparative summary CSV.",
    )
    p_report.set_defaults(func=_cmd_report)

    # 12. serve
    p_serve = subparsers.add_parser(
        "serve",
        help="Launch CheckSense Streamlit application (analysis app or annotation app).",
    )
    p_serve.add_argument(
        "--app",
        choices=["main", "annotate"],
        default="main",
        help="Streamlit application to run ('main' -> app/streamlit_app.py, 'annotate' -> app/annotate.py).",
    )
    p_serve.add_argument(
        "--port",
        type=int,
        default=8501,
        help="Server port (default: 8501).",
    )
    p_serve.add_argument(
        "--host",
        type=str,
        default="localhost",
        help="Server host address (default: localhost).",
    )
    p_serve.set_defaults(func=_cmd_serve)

    return parser


# Command handlers (skeletons with status logging)
def _cmd_download(args: argparse.Namespace) -> int:
    from .acquisition import DATASET_CONFIGS, acquire_dataset

    print(f"[CheckSense CLI] 'download' subcommand invoked for dataset={args.dataset}")
    print(f"Destination: {args.output_dir.resolve()}")

    targets = list(DATASET_CONFIGS.keys()) if args.dataset == "all" else [args.dataset]
    for target in targets:
        if target not in DATASET_CONFIGS:
            print(f"[-] Dataset '{target}' is not an auto-download target. Check HUMAN_TODO.md.")
            continue
        try:
            acquire_dataset(
                dataset_key=target,
                output_base_dir=args.output_dir,
                skip_checksum=args.skip_checksum,
            )
        except Exception as e:
            print(f"[-] ERROR acquiring {target}: {e}")
            return 1
    return 0


def _cmd_build_corpus(args: argparse.Namespace) -> int:
    from .corpus import build_pure_corpus

    print("[CheckSense CLI] 'build-corpus' subcommand invoked.")
    print(f"Input: {args.input_dir.resolve()} -> Output: {args.output_file.resolve()}")
    try:
        build_pure_corpus(
            input_dir=args.input_dir,
            output_file=args.output_file,
            min_tokens=args.min_tokens,
            max_tokens=args.max_tokens,
        )
        return 0
    except Exception as e:
        print(f"[-] ERROR building corpus: {e}")
        return 1


def _cmd_sample(args: argparse.Namespace) -> int:
    from .sample import sample_requirements

    print(f"[CheckSense CLI] 'sample' subcommand invoked (n={args.n_samples}, seed={args.seed}).")
    print(f"Input: {args.input_file.resolve()} -> Output: {args.output_dir.resolve()}")
    try:
        manifest = sample_requirements(
            input_file=args.input_file,
            output_dir=args.output_dir,
            n_samples=args.n_samples,
            seed=args.seed,
            held_out_ratio=args.held_out_ratio,
        )
        print("\n" + "=" * 60)
        print("CheckSense Phase 3 Sampling Complete")
        print("=" * 60)
        print(f"Total Sampled:             {manifest['total_sampled']}")
        print(f"Development Set:           {manifest['dev_count']} reqs ({manifest['dev_documents_count']} documents)")
        print(f"Held-Out Test Set:         {manifest['test_count']} reqs ({manifest['test_documents_count']} documents)")
        print(f"Held-Out Document Ratio:   {manifest['held_out_ratio_effective']:.1%}")
        print(f"Pilot Double-Annotate:     {manifest['pilot_sample_size']} reqs")
        print(f"Contamination Audit:       {manifest['contamination_audit']['status']}")
        print(f"Sample Manifest:           {args.output_dir / 'sample_manifest.json'}")
        print(f"Pilot Sample CSV:          {args.output_dir / 'pilot_sample.csv'}")
        print("=" * 60 + "\n")
        return 0
    except Exception as e:
        print(f"[-] ERROR sampling requirements: {e}")
        return 1


def _cmd_annotate_stats(args: argparse.Namespace) -> int:
    from .agreement import (
        compute_annotation_agreement,
        compute_dataset_annotation_stats,
        load_pilot_expected_ids,
    )

    print("[CheckSense CLI] 'annotate-stats' subcommand invoked.")
    if bool(args.pilot_file_a) != bool(args.pilot_file_b):
        print("[-] ERROR: Both --pilot-file-a and --pilot-file-b must be provided to compute agreement.")
        return 1

    if args.pilot_file_a and args.pilot_file_b:
        print(f"Comparing Rater A ({args.pilot_file_a}) vs Rater B ({args.pilot_file_b})...")
        ref_file = args.pilot_reference_file
        print(f"Validating coverage against pilot reference file: {ref_file}...")
        try:
            expected_ids = load_pilot_expected_ids(ref_file)
        except Exception as e:
            print(f"[-] ERROR loading pilot reference file '{ref_file}': {e}")
            return 1

        print(f"Loaded {len(expected_ids)} expected requirement IDs from pilot reference.")
        try:
            report = compute_annotation_agreement(
                args.pilot_file_a,
                args.pilot_file_b,
                expected_req_ids=expected_ids,
            )
            print("\n" + "=" * 60)
            print("CheckSense Inter-Rater Reliability (Cohen's Kappa)")
            print("=" * 60)
            print(f"Evaluated Requirements:       {report['n_evaluated']}")
            print(f"Binary has_gap Kappa:         {report['has_gap_kappa']['kappa']:.4f} ({report['has_gap_kappa']['interpretation']})")
            print(f"Gap Type (3-Class + Clean):   {report['gap_type_kappa']['kappa']:.4f} ({report['gap_type_kappa']['interpretation']})")
            print(f"Subtype Kappa:                {report['subtype_kappa']['kappa']:.4f} ({report['subtype_kappa']['interpretation']})")
            print(f"Severity Kappa (Unweighted):  {report['severity_unweighted_kappa']['kappa']:.4f} ({report['severity_unweighted_kappa']['interpretation']})")
            print(f"Severity Kappa (Quadratic W): {report['severity_quadratic_kappa']['kappa']:.4f} ({report['severity_quadratic_kappa']['interpretation']})")
            print(f"Total Disagreements:          {report['n_disagreements']}")
            print("=" * 60 + "\n")
            return 0
        except Exception as e:
            print(f"[-] ERROR calculating agreement: {e}")
            return 1

    # Single gold file progress stats
    print(f"Auditing annotation file: {args.gold_file.resolve()}...")
    if not args.gold_file.exists():
        print(f"[*] Annotation file not found: {args.gold_file.resolve()}")
        print("    No human annotations recorded yet. Status: Human annotation queue initialized.")
        return 0
    try:
        stats = compute_dataset_annotation_stats(args.gold_file)
        print("\n" + "=" * 60)
        print("CheckSense Annotation Progress & Verification Audit")
        print("=" * 60)
        print(f"Total Requirements:           {stats['total_requirements']}")
        print(f"Verified (Human Confirmed):   {stats['verified_requirements']}")
        print(f"Draft (Awaiting Verification):{stats['draft_requirements']}")
        print(f"Unreviewed:                   {stats['unreviewed_requirements']}")
        print(f"Clean Requirements:           {stats['clean_requirements']}")
        print(f"Total Gaps Identified:        {stats['total_gaps_annotated']}")
        print("-" * 60)
        print("Gaps by Class:")
        for k, v in stats["class_distribution"].items():
            print(f"  {k:20s}: {v}")
        print("-" * 60)
        print("Gaps by Subtype:")
        for k, v in stats["subtype_distribution"].items():
            print(f"  {k:25s}: {v}")
        print("-" * 60)
        print("Gaps by Severity:")
        for k, v in sorted(stats["severity_distribution"].items()):
            print(f"  Severity {k}: {v}")
        print("=" * 60 + "\n")
        return 0
    except Exception as e:
        print(f"[-] ERROR auditing annotations: {e}")
        return 1


def _cmd_train_smell(args: argparse.Namespace) -> int:
    from .smell import train_and_cross_validate_smell_classifier

    print(f"[CheckSense CLI] 'train-smell' subcommand invoked (model={args.model_type}, device={args.device}).")
    print(f"Data directory:   {args.data_dir.resolve()}")
    print(f"Output directory: {args.output_dir.resolve()}")

    try:
        train_and_cross_validate_smell_classifier(
            data_dir=args.data_dir,
            output_dir=args.output_dir,
            model_type=args.model_type,
            seed=args.seed,
            n_splits=args.n_splits,
            qure_file=args.qure_file,
            gold_file=args.gold_file,
            device=args.device,
        )
        print("\n[+] Smell classifier training, cross-validation, and evaluation successfully completed!")
        return 0
    except Exception as e:
        print(f"[-] ERROR training smell classifier: {e}")
        return 1


def _cmd_train_span(args: argparse.Namespace) -> int:
    from .span_tagger import train_and_evaluate_span_tagger

    print(f"[CheckSense CLI] 'train-span' subcommand invoked (seed={args.seed}, device={args.device}).")
    print(f"Gold file:        {args.gold_file.resolve()}")
    print(f"Output directory: {args.output_dir.resolve()}")

    try:
        train_and_evaluate_span_tagger(
            gold_file=args.gold_file,
            output_dir=args.output_dir,
            seed=args.seed,
            n_splits=args.n_splits,
            device=args.device,
        )
        print("\n[+] Span tagger training, cross-validation, and evaluation successfully completed!")
        return 0
    except Exception as e:
        print(f"[-] ERROR training span tagger: {e}")
        return 1


def _cmd_train_fusion(args: argparse.Namespace) -> int:
    from .fusion import train_and_cross_validate_fusion_scorer

    print(f"[CheckSense CLI] 'train-fusion' subcommand invoked (seed={args.seed}, n_splits={args.n_splits}).")
    print(f"Gold annotations: {args.gold_file.resolve()}")
    print(f"Output directory: {args.output_dir.resolve()}")

    try:
        train_and_cross_validate_fusion_scorer(
            gold_file=args.gold_file,
            output_dir=args.output_dir,
            smell_model_path=args.smell_model if args.smell_model.exists() else None,
            span_model_path=args.span_model if args.span_model.exists() else None,
            seed=args.seed,
            n_splits=args.n_splits,
        )
        print("\n[+] Candidate-level fusion scorer training and cross-validation completed!")
        return 0
    except Exception as e:
        print(f"[-] ERROR training fusion scorer: {e}")
        return 1


def _cmd_eval(args: argparse.Namespace) -> int:
    from .eval import UnverifiedEvaluationError, run_evaluation

    print(f"[CheckSense CLI] 'eval' subcommand invoked (req_level={args.req_level}, pipeline={args.pipeline}).")
    print(f"Gold annotations: {args.gold_file.resolve()}")
    if args.predictions_file:
        print(f"Predictions file: {args.predictions_file.resolve()}")
    elif args.pipeline == "phase5":
        print("Predictions: Running Phase 5 Candidate-Level Fusion Scorer")
    elif args.pipeline == "phase4":
        print("Predictions: Running Phase 4 multi-head models (Heads 4a, 4b, 4c)")
    else:
        print("Predictions: Running Baseline B1 (rules only)")

    try:
        report = run_evaluation(
            gold_file=args.gold_file,
            predictions_file=args.predictions_file,
            output_dir=args.output_dir,
            req_level=args.req_level,
            pipeline=args.pipeline,
            smell_model_path=args.smell_model,
            span_model_path=args.span_model,
            fusion_model_path=args.fusion_model,
        )

        print("\n" + "=" * 60)
        print("CheckSense Evaluation Report")
        print("=" * 60)
        print(f"Evaluated Requirements:       {report.n_requirements}")
        print(f"Clean Requirements (no gaps): {report.n_clean_requirements}")
        print(f"Total Gold Gaps:              {report.n_gold_gaps}")
        print(f"Total Predicted Gaps:         {report.n_pred_gaps}")
        print(f"Matching Protocol:            {'Requirement-Level' if report.req_level else 'Token Span Jaccard (>=0.5)'}")
        print("-" * 60)
        print(f"Primary Metric (Macro-F1):    {report.macro_f1:.4f}")
        print(f"Micro-F1:                     {report.micro_f1:.4f}")
        print(f"Micro-F2:                     {report.micro_f2:.4f}")
        print("-" * 60)
        print("Per-Class Gap Metrics:")
        for cname, cm in report.per_class.items():
            print(f"  [{cname}] TP={cm.tp}, FP={cm.fp}, FN={cm.fn} | P={cm.precision:.4f}, R={cm.recall:.4f}, F1={cm.f1:.4f}")
        print("-" * 60)
        print(f"Requirement Has-Gap Accuracy: {report.has_gap_accuracy:.4f}")
        print(f"Requirement Has-Gap PR-AUC:   {report.has_gap_pr_auc:.4f}")
        print(f"False-Alarm Rate (Clean):     {report.false_alarm_rate_clean:.4f}")
        print(f"Severity Spearman Rho:        {report.spearman_rho:.4f}")
        print(f"Severity nDCG@3:              {report.ndcg_at_3:.4f}")
        print(f"Expected Calibration Error:   {report.ece:.4f}")
        print(f"Brier Score:                  {report.brier_score:.4f}")
        print("=" * 60)
        if args.output_dir:
            print(f"[+] Evaluation artifacts saved to: {args.output_dir.resolve()}")
        return 0
    except UnverifiedEvaluationError as e:
        print(f"\n[-] EVALUATION HALTED BY GATE:\n{e}")
        return 2
    except Exception as e:
        print(f"\n[-] ERROR running evaluation: {e}")
        return 1


def _cmd_rate_make(args: argparse.Namespace) -> int:
    print("[CheckSense CLI] 'rate-make' subcommand invoked.")
    print(f"Output sheet: {args.output_sheet.resolve()}")
    print("Status: Implementation is scheduled in Phase 8.")
    return 0


def _cmd_rate_score(args: argparse.Namespace) -> int:
    print("[CheckSense CLI] 'rate-score' subcommand invoked.")
    print(f"Input sheet: {args.sheet_a.resolve()}")
    print("Status: Implementation is scheduled in Phase 8.")
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    from .comparative import run_comparative_benchmark

    print("[CheckSense CLI] 'report' subcommand invoked (Phase 7 Comparative Benchmarks & Ablations).")
    print(f"Gold annotations: {args.gold_file.resolve()}")
    print(f"Summary destination: {args.summary_file.resolve()}")

    try:
        run_comparative_benchmark(
            gold_file=args.gold_file,
            output_summary_file=args.summary_file,
        )
        print(f"\n[+] Comparative summary benchmark successfully generated at: {args.summary_file.resolve()}")
        return 0
    except Exception as e:
        print(f"\n[-] ERROR generating comparative report: {e}")
        return 1


def _cmd_serve(args: argparse.Namespace) -> int:
    import subprocess

    print(f"[CheckSense CLI] 'serve' subcommand invoked for app={args.app} on {args.host}:{args.port}.")
    target_app = "app/streamlit_app.py" if args.app == "main" else "app/annotate.py"
    target_path = Path(target_app)
    if not target_path.exists():
        phase_str = "Phase 9 (main analysis app)" if args.app == "main" else "Phase 3 (annotation app)"
        print(f"[*] Target script '{target_app}' is scheduled for {phase_str}.")
        return 0

    print(f"[+] Target application: {target_app}")
    # In automated test runners, avoid blocking on server execution
    if "pytest" in sys.modules or getattr(args, "dry_run", False):
        print("[CheckSense CLI] Test environment detected: skipping interactive Streamlit server launch.")
        return 0

    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(target_path),
        "--server.port",
        str(args.port),
        "--server.address",
        str(args.host),
    ]
    try:
        return subprocess.call(cmd)
    except KeyboardInterrupt:
        print("\n[CheckSense CLI] Streamlit server stopped by user.")
        return 0
    except Exception as e:
        print(f"[-] ERROR starting Streamlit server: {e}")
        return 1


def main(argv: Sequence[str] | None = None) -> int:
    """Main entrypoint for CheckSense CLI."""
    parser = create_parser()
    args = parser.parse_args(argv)
    if hasattr(args, "func"):
        return args.func(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
