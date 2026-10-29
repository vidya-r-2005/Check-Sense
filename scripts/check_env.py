"""Environment and workspace validation script for CheckSense on Windows/POSIX.

Validates:
- Python version (>= 3.11)
- Project directory structure
- Git repository and .gitignore
- CLI importability and version
- Installed Python packages and tools
"""

from __future__ import annotations

import importlib
import platform
import sys
from pathlib import Path

REQUIRED_DIRS = [
    Path("src/checksense"),
    Path("docs"),
    Path("data/raw"),
    Path("data/interim"),
    Path("data/processed"),
    Path("data/gold"),
    Path("notebooks"),
    Path("reports"),
    Path("results"),
    Path("scripts"),
    Path("tests"),
    Path(".vscode"),
]

CORE_PACKAGES = [
    ("pytest", "Testing harness"),
    ("ruff", "Linter and formatter"),
    ("spacy", "spaCy NLP parser"),
    ("sklearn", "scikit-learn machine learning"),
    ("pandas", "Data manipulation"),
    ("streamlit", "Interactive web UI"),
    ("pypdf", "PDF document extraction"),
    ("docx", "Word document extraction"),
]


def check_python_version() -> bool:
    print(f"[*] Python Runtime: {sys.version.split()[0]} on {platform.system()} ({platform.machine()})")
    if sys.version_info < (3, 11):  # noqa: UP036
        print(f"[-] ERROR: Python 3.11+ required. Found {sys.version_info.major}.{sys.version_info.minor}")
        return False
    print("    [+] Python version check passed (>= 3.11).")
    return True


def check_directories(root: Path) -> bool:
    all_ok = True
    print("[*] Checking directory structure:")
    for rel_dir in REQUIRED_DIRS:
        full_path = root / rel_dir
        if full_path.is_dir():
            print(f"    [+] {rel_dir.as_posix()}/ exists.")
        else:
            print(f"    [-] Missing directory: {rel_dir.as_posix()}/")
            all_ok = False
    return all_ok


def check_git(root: Path) -> bool:
    print("[*] Checking Git repository:")
    git_dir = root / ".git"
    gitignore = root / ".gitignore"
    if not git_dir.exists():
        print("    [-] ERROR: .git directory not found. Run 'git init'.")
        return False
    print("    [+] Git repository initialized.")
    if not gitignore.is_file():
        print("    [-] ERROR: .gitignore missing.")
        return False
    print("    [+] .gitignore present.")
    return True


def check_cli_package(root: Path) -> bool:
    print("[*] Checking CheckSense package import:")
    # Ensure src is in sys.path
    src_dir = str(root / "src")
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    try:
        import checksense
        import checksense.cli
        print(f"    [+] Successfully imported 'checksense' v{checksense.__version__}")
        parser = checksense.cli.create_parser()
        import argparse
        sub_action = next(
            (a for a in parser._actions if isinstance(a, argparse._SubParsersAction)),
            None,
        )
        subcommands = list(sub_action.choices.keys()) if sub_action else []
        print(f"    [+] Subparsers loaded ({len(subcommands)} commands): {', '.join(subcommands)}")
        return True
    except Exception as e:
        print(f"    [-] ERROR importing checksense: {e}")
        return False


def check_installed_packages() -> dict[str, bool]:
    print("[*] Checking installed dependencies:")
    status = {}
    for pkg_name, desc in CORE_PACKAGES:
        try:
            mod = importlib.import_module(pkg_name)
            ver = getattr(mod, "__version__", "unknown")
            print(f"    [+] {pkg_name} ({ver}): {desc}")
            status[pkg_name] = True
        except ImportError:
            print(f"    [?] {pkg_name} is not yet installed: {desc}")
            status[pkg_name] = False
    return status


def main() -> int:
    print("=" * 60)
    print("CheckSense Environment & Workspace Verification")
    print("=" * 60)

    root = Path(__file__).resolve().parent.parent

    py_ok = check_python_version()
    dir_ok = check_directories(root)
    git_ok = check_git(root)
    pkg_ok = check_cli_package(root)
    check_installed_packages()

    print("=" * 60)
    if py_ok and dir_ok and git_ok and pkg_ok:
        print("[+] Environment and repository skeleton validation PASSED!")
        return 0
    else:
        print("[-] One or more validation checks FAILED. Review errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
