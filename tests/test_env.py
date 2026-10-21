"""Unit tests for CheckSense workspace environment and configuration."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


def test_python_version():
    """Verify runtime Python meets the specification requirement (>= 3.11)."""
    assert sys.version_info >= (3, 11), f"Python 3.11+ required, current: {sys.version}"


def test_core_directories_exist():
    """Verify all required repository directories exist."""
    required = [
        "src/checksense",
        "docs",
        "data/raw",
        "data/interim",
        "data/processed",
        "data/gold",
        "notebooks",
        "reports",
        "results",
        "scripts",
        "tests",
        ".vscode",
    ]
    for rel_path in required:
        full_path = ROOT_DIR / rel_path
        assert full_path.exists(), f"Required path {rel_path} does not exist"
        assert full_path.is_dir(), f"Path {rel_path} is not a directory"


def test_gitignore_rules():
    """Verify .gitignore contains mandatory exclusions for raw data, models, and secrets."""
    gitignore = ROOT_DIR / ".gitignore"
    assert gitignore.is_file(), ".gitignore missing"
    content = gitignore.read_text(encoding="utf-8")
    assert "data/raw/*" in content, "Missing raw data exclusion in .gitignore"
    assert "models/*" in content, "Missing models exclusion in .gitignore"
    assert ".env" in content, "Missing .env exclusion in .gitignore"


def test_agents_and_spec_exist():
    """Verify AGENTS.md and docs/MASTER_SPEC.md exist and are non-empty."""
    agents_md = ROOT_DIR / "AGENTS.md"
    master_spec = ROOT_DIR / "docs/MASTER_SPEC.md"
    assert agents_md.is_file() and agents_md.stat().st_size > 0
    assert master_spec.is_file() and master_spec.stat().st_size > 0
