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
        "--model-type",
        choices=["tfidf_lr", "spanbert_lr", "all"],
        default="tfidf_lr",
        help="Classifier architecture.",
    )
    p_smell.add_argument("--seed", type=int, default=42, help="Random seed.")
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
        default=Path("data/gold/annotations.csv"),
        help="Path to verified gold annotations.",
    )
    p_span.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/span_tagger"),
        help="Destination directory for model and metrics.",
    )
    p_span.add_argument("--seed", type=int, default=42, help="Random seed.")
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
        default=Path("data/gold/annotations.csv"),
        help="Path to verified gold annotations.",
    )
    p_fusion.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/fusion_model"),
        help="Destination directory for model and calibration data.",
    )
    p_fusion.add_argument("--seed", type=int, default=42, help="Random seed.")
    p_fusion.set_defaults(func=_cmd_train_fusion)

    # 8. eval
    p_eval = subparsers.add_parser(
        "eval",
        help="Evaluate gap detection pipeline on gold test set (refuses unverified rows).",
    )
    p_eval.add_argument(
        "--gold-file",
        type=Path,
        default=Path("data/gold/annotations.csv"),
        help="Gold annotation file with label_status.",
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
    print(f"[CheckSense CLI] 'sample' subcommand invoked (n={args.n_samples}, seed={args.seed}).")
    print(f"Output directory: {args.output_dir.resolve()}")
    print("Status: Implementation is scheduled in Phase 3.")
    return 0


def _cmd_annotate_stats(args: argparse.Namespace) -> int:
    print("[CheckSense CLI] 'annotate-stats' subcommand invoked.")
    print(f"Gold file: {args.gold_file.resolve()}")
    print("Status: Implementation is scheduled in Phase 3.")
    return 0


def _cmd_train_smell(args: argparse.Namespace) -> int:
    print(f"[CheckSense CLI] 'train-smell' subcommand invoked (model={args.model_type}, device={args.device}).")
    print(f"Output directory: {args.output_dir.resolve()}")
    print("Status: Implementation is scheduled in Phase 4.")
    return 0


def _cmd_train_span(args: argparse.Namespace) -> int:
    print(f"[CheckSense CLI] 'train-span' subcommand invoked (seed={args.seed}, device={args.device}).")
    print(f"Output directory: {args.output_dir.resolve()}")
    print("Status: Implementation is scheduled in Phase 4.")
    return 0


def _cmd_train_fusion(args: argparse.Namespace) -> int:
    print(f"[CheckSense CLI] 'train-fusion' subcommand invoked (seed={args.seed}).")
    print(f"Output directory: {args.output_dir.resolve()}")
    print("Status: Implementation is scheduled in Phase 5.")
    return 0


def _cmd_eval(args: argparse.Namespace) -> int:
    print(f"[CheckSense CLI] 'eval' subcommand invoked (req_level={args.req_level}).")
    print(f"Gold annotations: {args.gold_file.resolve()}")
    print("Status: Implementation is scheduled in Phase 2 & 8 (strict label_status verification).")
    return 0


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
    print("[CheckSense CLI] 'report' subcommand invoked.")
    print(f"Results dir: {args.results_dir.resolve()} -> Output dir: {args.output_dir.resolve()}")
    print("Status: Implementation is scheduled in Phase 8.")
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    print(f"[CheckSense CLI] 'serve' subcommand invoked for app={args.app} on {args.host}:{args.port}.")
    target_app = "app/streamlit_app.py" if args.app == "main" else "app/annotate.py"
    print(f"Target script: {target_app}")
    print("Status: Implementation is scheduled in Phase 3 (annotate) and Phase 9 (main).")
    return 0


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
