"""Unit tests for CheckSense CLI skeleton and subcommands."""

from __future__ import annotations

import pytest

from checksense import __version__
from checksense.cli import create_parser, main

SUBCOMMANDS = [
    "download",
    "build-corpus",
    "sample",
    "annotate-stats",
    "train-smell",
    "train-span",
    "train-fusion",
    "eval",
    "rate-make",
    "rate-score",
    "report",
    "serve",
]


def test_version_string():
    assert __version__ is not None
    assert len(__version__.split(".")) >= 3


def test_create_parser():
    import argparse
    parser = create_parser()
    assert parser.prog == "python -m checksense.cli"
    sub_action = next(
        (a for a in parser._actions if isinstance(a, argparse._SubParsersAction)),
        None,
    )
    assert sub_action is not None
    for subcmd in SUBCOMMANDS:
        assert subcmd in sub_action.choices, f"Missing subcommand {subcmd}"


@pytest.mark.parametrize("subcmd", SUBCOMMANDS)
def test_subcommand_help(subcmd: str):
    """Verify that every subcommand responds to --help without errors."""
    parser = create_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args([subcmd, "--help"])
    assert exc_info.value.code == 0


def test_main_help():
    """Verify top-level --help exits cleanly."""
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0


def test_subcommand_invocations():
    """Verify default dispatching for skeleton commands."""
    assert main(["download", "--dataset", "pure"]) == 0
    assert main(["build-corpus"]) == 0
    assert main(["sample", "--n-samples", "10"]) == 0
    assert main(["annotate-stats"]) == 0
    assert main(["train-smell"]) == 0
    assert main(["train-span"]) == 0
    assert main(["train-fusion"]) == 0
    assert main(["eval"]) == 0
    assert main(["rate-make"]) == 0
    assert main(["rate-score", "--sheet-a", "dummy.csv"]) == 0
    assert main(["report"]) == 0
    assert main(["serve", "--app", "main"]) == 0
