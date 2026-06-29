#!/usr/bin/env python3
"""
Version Consistency Checker

Validates that the project version number is consistent across all canonical
locations. Run this before any release to catch version drift early.

Canonical source: scripts/collaboration/_version.py (__version__ string)

Usage:
    python scripts/check_version_consistency.py
    python scripts/check_version_consistency.py --strict  # fail on warnings too

Exit codes:
    0 = all checks passed
    1 = one or more files have inconsistent version
    2 = script error (could not read canonical source)

Added in P2-6 (V3.9.2) to prevent the version-drift issues that occurred
during V3.6.x/V3.7.x/V3.8.x -> V3.9.2 migration.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

REPO_ROOT = Path(__file__).resolve().parent.parent
CANONICAL_VERSION_FILE = REPO_ROOT / "scripts" / "collaboration" / "_version.py"


class VersionCheck(NamedTuple):
    """Result of a single file version check."""

    file: str
    expected: str
    found: str | None
    passed: bool
    detail: str = ""


@dataclass
class FileSpec:
    """Specification for a single file's version check.

    check_mode:
        "first_match" — the FIRST regex match must equal the expected version
                        (use for CHANGELOG where latest entry must be current)
        "contains"    — the expected version must appear AT LEAST once
                        (use for README/SKILL/CLAUDE where historical refs are OK)
    """

    relative_path: str
    pattern: re.Pattern[str]
    description: str
    check_mode: str = "contains"

    def read_text(self) -> str | None:
        path = REPO_ROOT / self.relative_path
        if not path.exists():
            return None
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return None


# === Files to check ===
# Each spec defines: (relative_path, regex_pattern, description)
# The regex MUST have a single capturing group for the version string.
FILES_TO_CHECK: list[FileSpec] = [
    FileSpec(
        relative_path="pyproject.toml",
        pattern=re.compile(r'^version\s*=\s*"(\d+\.\d+\.\d+)"', re.MULTILINE),
        description="project metadata version",
    ),
    FileSpec(
        relative_path="scripts/collaboration/_version.py",
        pattern=re.compile(r'^__version__\s*=\s*"(\d+\.\d+\.\d+)"', re.MULTILINE),
        description="canonical __version__ string",
    ),
    FileSpec(
        relative_path="skill-manifest.yaml",
        pattern=re.compile(r"^version:\s*[\"']?(\d+\.\d+\.\d+)", re.MULTILINE),
        description="skill manifest version",
    ),
    FileSpec(
        relative_path="Dockerfile",
        pattern=re.compile(r'^LABEL version="(\d+\.\d+\.\d+)"', re.MULTILINE),
        description="Docker image label",
    ),
    FileSpec(
        relative_path="helm/devsquad/Chart.yaml",
        pattern=re.compile(r"^version:\s*(\d+\.\d+\.\d+)", re.MULTILINE),
        description="Helm chart version",
    ),
    FileSpec(
        relative_path="helm/devsquad/Chart.yaml",
        pattern=re.compile(r'^appVersion:\s*"(\d+\.\d+\.\d+)"', re.MULTILINE),
        description="Helm chart appVersion",
    ),
    FileSpec(
        relative_path="CHANGELOG.md",
        pattern=re.compile(r"^##\s*\[(\d+\.\d+\.\d+)\]", re.MULTILINE),
        description="CHANGELOG latest entry",
        check_mode="first_match",
    ),
    FileSpec(
        relative_path="CHANGELOG-CN.md",
        pattern=re.compile(r"^##\s*\[(\d+\.\d+\.\d+)\]", re.MULTILINE),
        description="CHANGELOG-CN latest entry",
        check_mode="first_match",
    ),
    FileSpec(
        relative_path="README.md",
        pattern=re.compile(r"V(\d+\.\d+\.\d+)", re.MULTILINE),
        description="README.md version badge",
    ),
    FileSpec(
        relative_path="README-CN.md",
        pattern=re.compile(r"V(\d+\.\d+\.\d+)", re.MULTILINE),
        description="README-CN.md version badge",
    ),
    FileSpec(
        relative_path="README-JP.md",
        pattern=re.compile(r"V(\d+\.\d+\.\d+)", re.MULTILINE),
        description="README-JP.md version badge",
    ),
    FileSpec(
        relative_path="SKILL.md",
        pattern=re.compile(r"V(\d+\.\d+\.\d+)", re.MULTILINE),
        description="SKILL.md version reference",
    ),
    FileSpec(
        relative_path="CLAUDE.md",
        pattern=re.compile(r"V(\d+\.\d+\.\d+)", re.MULTILINE),
        description="CLAUDE.md version reference",
    ),
    FileSpec(
        relative_path="config/deployment.yaml",
        pattern=re.compile(r"V(\d+\.\d+\.\d+)", re.MULTILINE),
        description="deployment.yaml version reference",
    ),
    FileSpec(
        relative_path="COMPARISON.md",
        pattern=re.compile(r"V(\d+\.\d+\.\d+)", re.MULTILINE),
        description="COMPARISON.md version reference",
    ),
]


def get_canonical_version() -> str | None:
    """Read canonical version from _version.py."""
    try:
        content = CANONICAL_VERSION_FILE.read_text(encoding="utf-8")
        match = re.search(r'^__version__\s*=\s*"(\d+\.\d+\.\d+)"', content, re.MULTILINE)
        if match:
            return match.group(1)
    except OSError:
        pass
    return None


def check_file(spec: FileSpec, expected: str) -> VersionCheck:
    """Check a single file for version consistency."""
    content = spec.read_text()
    if content is None:
        return VersionCheck(
            file=spec.relative_path,
            expected=expected,
            found=None,
            passed=False,
            detail=f"file not found or unreadable: {spec.relative_path}",
        )

    matches = spec.pattern.findall(content)
    if not matches:
        return VersionCheck(
            file=spec.relative_path,
            expected=expected,
            found=None,
            passed=False,
            detail=f"no version match in {spec.relative_path} ({spec.description})",
        )

    if spec.check_mode == "first_match":
        # The FIRST match must equal the expected version (e.g., CHANGELOG latest entry)
        first = matches[0]
        if first == expected:
            return VersionCheck(
                file=spec.relative_path,
                expected=expected,
                found=first,
                passed=True,
                detail=f"{spec.description}: latest={first} OK",
            )
        return VersionCheck(
            file=spec.relative_path,
            expected=expected,
            found=first,
            passed=False,
            detail=f"{spec.description}: expected latest={expected}, found latest={first}",
        )

    # "contains" mode: expected version must appear AT LEAST once
    if expected in matches:
        return VersionCheck(
            file=spec.relative_path,
            expected=expected,
            found=expected,
            passed=True,
            detail=f"{spec.description}: contains {expected} OK",
        )

    # Expected version not found — report first match as the found value
    return VersionCheck(
        file=spec.relative_path,
        expected=expected,
        found=matches[0],
        passed=False,
        detail=f"{spec.description}: expected {expected} not found (found {matches[0]})",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Check version consistency across project files.")
    parser.add_argument("--strict", action="store_true", help="fail on warnings too")
    parser.parse_args()

    expected = get_canonical_version()
    if expected is None:
        print(f"ERROR: could not read canonical version from {CANONICAL_VERSION_FILE}")
        return 2

    print(f"Canonical version: {expected} (from scripts/collaboration/_version.py)")
    print(f"Checking {len(FILES_TO_CHECK)} file spec(s)...")
    print("-" * 70)

    results = [check_file(spec, expected) for spec in FILES_TO_CHECK]

    passed = [r for r in results if r.passed]
    failed = [r for r in results if not r.passed]

    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"  [{status}] {r.file:<45} {r.detail}")

    print("-" * 70)
    print(f"Results: {len(passed)} passed, {len(failed)} failed (out of {len(results)} checks)")

    if failed:
        print("\nVersion mismatches detected:")
        for r in failed:
            print(f"  - {r.file}: expected {r.expected}, found {r.found}")
            print(f"    {r.detail}")
        return 1

    print(f"\nAll {len(results)} version checks passed. Version {expected} is consistent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
