#!/usr/bin/env python3
"""Check dependency sync between requirements-dev.txt and pyproject.toml [dev].

Detects drift where a package appears in one file but not the other, preventing
the class of bug seen in V4.0.10 where fakeredis/redis were added to
pyproject.toml [dev] but missing from requirements-dev.txt.

Exit code:
    0 — requirements-dev.txt and pyproject.toml [dev] package sets match
    1 — drift detected (details printed to stdout)

Usage:
    python scripts/check_dependency_sync.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQ_FILE = ROOT / "requirements-dev.txt"
PYPROJECT = ROOT / "pyproject.toml"

_CONSTRAINT_SEPARATORS = (">=", "<=", "==", "!=", "~=", ">", "<")


def normalize(spec: str) -> str:
    """Normalize a dependency spec to its bare package name.

    Handles extras (``uvicorn[standard]``), version constraints
    (``pytest>=7.0``), inline comments, and underscore/hyphen differences
    (per PEP 503 normalization).
    """
    spec = spec.split("#")[0].strip()
    spec = re.sub(r"\[.*?\]", "", spec)
    for sep in _CONSTRAINT_SEPARATORS:
        if sep in spec:
            spec = spec.split(sep)[0]
            break
    return spec.strip().lower().replace("_", "-")


def parse_requirements(path: Path) -> set[str]:
    """Parse a requirements.txt file into a set of normalized package names."""
    pkgs: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        pkg = normalize(line)
        if pkg:
            pkgs.add(pkg)
    return pkgs


def parse_pyproject_dev(path: Path) -> set[str]:
    """Parse pyproject.toml [project.optional-dependencies] dev list.

    Uses regex to avoid a tomllib/tomli dependency, keeping the script
    runnable on Python 3.10+ without extra installs.
    """
    text = path.read_text(encoding="utf-8")
    match = re.search(r"^dev\s*=\s*\[(.*?)\]", text, re.DOTALL | re.MULTILINE)
    if not match:
        return set()
    body = match.group(1)
    specs = re.findall(r'"([^"]+)"', body)
    return {normalize(s) for s in specs if normalize(s)}


def main() -> int:
    req_pkgs = parse_requirements(REQ_FILE)
    dev_pkgs = parse_pyproject_dev(PYPROJECT)

    only_in_req = req_pkgs - dev_pkgs
    only_in_dev = dev_pkgs - req_pkgs

    if not only_in_req and not only_in_dev:
        print(f"OK: requirements-dev.txt and pyproject.toml [dev] in sync ({len(req_pkgs)} packages).")
        return 0

    print("ERROR: dependency drift between requirements-dev.txt and pyproject.toml [dev]")
    if only_in_req:
        print(f"  Only in requirements-dev.txt ({len(only_in_req)}): {sorted(only_in_req)}")
    if only_in_dev:
        print(f"  Only in pyproject.toml [dev] ({len(only_in_dev)}): {sorted(only_in_dev)}")
    print()
    print("Fix: add missing packages to both files so they stay in sync.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
