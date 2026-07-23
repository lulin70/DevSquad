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
PRD_DIR = REPO_ROOT / "docs" / "prd"

# Match version tags in PRD filenames: V3.9, V4.1.0, V4.2.1, etc.
# Captures the version string without the leading "V" prefix.
PRD_FILENAME_VERSION_RE = re.compile(r"^V(\d+\.\d+(?:\.\d+)?)")


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

    absolute_path:
        If set, use this path instead of ``REPO_ROOT / relative_path``.
        Used for TRAE skill cache files located outside the repo
        (e.g., ``~/.trae-cn/skills/devsquad/``).

    optional:
        If True, a missing file is OK (reported as SKIP, not FAIL).
        Used for TRAE cache layers that don't exist in CI environments.
    """

    relative_path: str
    pattern: re.Pattern[str]
    description: str
    check_mode: str = "contains"
    absolute_path: Path | None = None
    optional: bool = False

    def read_text(self) -> str | None:
        path = self.absolute_path if self.absolute_path else REPO_ROOT / self.relative_path
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
        pattern=re.compile(r'^ARG\s+VERSION\s*=\s*"?(\d+\.\d+\.\d+)"?', re.MULTILINE),
        description="Dockerfile VERSION arg",
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
    FileSpec(
        relative_path="skills/__init__.py",
        pattern=re.compile(r"DevSquad V(\d+\.\d+\.\d+)", re.MULTILINE),
        description="skills package docstring version",
    ),
    FileSpec(
        relative_path="docs/spec/SPEC.md",
        pattern=re.compile(r"DevSquad V(\d+\.\d+\.\d+)", re.MULTILINE),
        description="SPEC.md title version",
    ),
    FileSpec(
        relative_path="docs/architecture/ARCHITECTURE_V4.md",
        pattern=re.compile(r"V(\d+\.\d+\.\d+)", re.MULTILINE),
        description="ARCHITECTURE_V4.md version",
    ),
    # === TRAE skill cache layers (L1/L2/L3) ===
    # CLAUDE.md documents that TRAE reads from ~/.trae-cn/skills/devsquad/ (L1,
    # highest priority). Failing to sync these causes the TRAE skill panel to
    # show stale versions. See CLAUDE.md "TRAE 技能缓存层" section.
    # All cache entries are optional=True: CI environments don't have them.
    FileSpec(
        relative_path="~/.trae-cn/skills/devsquad/skill-manifest.yaml",
        pattern=re.compile(r"^version:\s*[\"']?(\d+\.\d+\.\d+)", re.MULTILINE),
        description="TRAE L1 cache (~/.trae-cn) skill-manifest.yaml",
        absolute_path=Path.home() / ".trae-cn" / "skills" / "devsquad" / "skill-manifest.yaml",
        optional=True,
    ),
    FileSpec(
        relative_path="~/.trae-cn/skills/devsquad/SKILL.md",
        pattern=re.compile(r"^version:\s*(\d+\.\d+\.\d+)", re.MULTILINE),
        description="TRAE L1 cache (~/.trae-cn) SKILL.md",
        absolute_path=Path.home() / ".trae-cn" / "skills" / "devsquad" / "SKILL.md",
        optional=True,
    ),
    FileSpec(
        relative_path="~/.trae/skills/devsquad/skill-manifest.yaml",
        pattern=re.compile(r"^version:\s*[\"']?(\d+\.\d+\.\d+)", re.MULTILINE),
        description="TRAE L2 cache (~/.trae) skill-manifest.yaml",
        absolute_path=Path.home() / ".trae" / "skills" / "devsquad" / "skill-manifest.yaml",
        optional=True,
    ),
    FileSpec(
        relative_path="~/.trae/skills/devsquad/SKILL.md",
        pattern=re.compile(r"^version:\s*(\d+\.\d+\.\d+)", re.MULTILINE),
        description="TRAE L2 cache (~/.trae) SKILL.md",
        absolute_path=Path.home() / ".trae" / "skills" / "devsquad" / "SKILL.md",
        optional=True,
    ),
    FileSpec(
        relative_path=".trae/skills/devsquad/skill-manifest.yaml",
        pattern=re.compile(r"^version:\s*[\"']?(\d+\.\d+\.\d+)", re.MULTILINE),
        description="TRAE L3 cache (project .trae) skill-manifest.yaml",
        optional=True,
    ),
    FileSpec(
        relative_path=".trae/skills/devsquad/SKILL.md",
        pattern=re.compile(r"^version:\s*(\d+\.\d+\.\d+)", re.MULTILINE),
        description="TRAE L3 cache (project .trae) SKILL.md",
        optional=True,
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
        if spec.optional:
            return VersionCheck(
                file=spec.relative_path,
                expected=expected,
                found=None,
                passed=True,
                detail=f"SKIP (optional, not found): {spec.description}",
            )
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


def _check_prd_files() -> list[VersionCheck]:
    """Check PRD files for internal version consistency (P2-11).

    Each PRD file in ``docs/prd/`` carries a version tag in its filename
    (e.g., ``V3.9_PRD_Code_Intelligence.md`` → version ``"3.9"``). This
    function verifies that the filename version appears somewhere in the
    file content. A mismatch indicates the PRD body has drifted from its
    declared version (e.g., content was updated to reference V4.2 but the
    filename still says V3.9).

    Results are non-blocking WARN-level: PRD files are historical artifacts
    and may legitimately reference older version tags. The check surfaces
    drift for human review without failing CI.

    Returns:
        List of :class:`VersionCheck` results. Empty if ``docs/prd/`` does
        not exist or contains no versioned PRD files.
    """
    if not PRD_DIR.exists():
        return []
    results: list[VersionCheck] = []
    for prd_file in sorted(PRD_DIR.glob("*.md")):
        match = PRD_FILENAME_VERSION_RE.match(prd_file.name)
        if not match:
            continue  # Skip files without a version prefix (e.g., README.md)
        filename_version = match.group(1)
        try:
            content = prd_file.read_text(encoding="utf-8")
        except OSError:
            results.append(VersionCheck(
                file=f"docs/prd/{prd_file.name}",
                expected=filename_version,
                found=None,
                passed=True,  # non-blocking: optional PRD file unreadable
                detail=f"SKIP (unreadable): {prd_file.name}",
            ))
            continue
        # Use digit-boundary lookarounds instead of \b: PRD files typically
        # write "V3.9" (V is a word char, so \b between V and 3 fails to
        # match). (?<!\d) and (?!\d) correctly allow "V3.9" while rejecting
        # "13.9" or "3.91".
        pattern = re.compile(rf"(?<!\d){re.escape(filename_version)}(?!\d)")
        if pattern.search(content):
            results.append(VersionCheck(
                file=f"docs/prd/{prd_file.name}",
                expected=filename_version,
                found=filename_version,
                passed=True,
                detail=f"PRD version {filename_version} found in content OK",
            ))
        else:
            # Non-blocking WARN: PRD content does not reference its filename version.
            # passed=True so this does not fail CI; detail prefixed with WARN for
            # human review.
            results.append(VersionCheck(
                file=f"docs/prd/{prd_file.name}",
                expected=filename_version,
                found=None,
                passed=True,
                detail=f"WARN: PRD version {filename_version} not found in content "
                       f"(filename/content drift)",
            ))
    return results


def _status_label(result: VersionCheck) -> str:
    """Derive display status label from a VersionCheck result."""
    if result.detail.startswith("SKIP"):
        return "SKIP"
    if result.detail.startswith("WARN"):
        return "WARN"
    if result.passed:
        return "PASS"
    return "FAIL"


def _print_results(results: list[VersionCheck]) -> dict[str, list[VersionCheck]]:
    """Print per-file results and return categorized buckets.

    Returns:
        Dict with keys "passed", "skipped", "warnings", "failed".
    """
    skipped = [r for r in results if r.detail.startswith("SKIP")]
    warnings = [r for r in results if r.detail.startswith("WARN")]
    passed = [
        r for r in results
        if r.passed and not r.detail.startswith("SKIP") and not r.detail.startswith("WARN")
    ]
    failed = [r for r in results if not r.passed]

    for r in results:
        print(f"  [{_status_label(r)}] {r.file:<45} {r.detail}")

    print("-" * 70)
    print(
        f"Results: {len(passed)} passed, {len(skipped)} skipped, "
        f"{len(warnings)} warnings, {len(failed)} failed "
        f"(out of {len(results)} checks)"
    )
    return {"passed": passed, "skipped": skipped, "warnings": warnings, "failed": failed}


def main() -> int:
    parser = argparse.ArgumentParser(description="Check version consistency across project files.")
    parser.add_argument("--strict", action="store_true", help="fail on warnings too")
    args = parser.parse_args()

    expected = get_canonical_version()
    if expected is None:
        print(f"ERROR: could not read canonical version from {CANONICAL_VERSION_FILE}")
        return 2

    print(f"Canonical version: {expected} (from scripts/collaboration/_version.py)")
    print(f"Checking {len(FILES_TO_CHECK)} file spec(s)...")
    print("-" * 70)

    results = [check_file(spec, expected) for spec in FILES_TO_CHECK]

    # P2-11: PRD internal version consistency (non-blocking WARN-level).
    prd_results = _check_prd_files()
    results.extend(prd_results)

    buckets = _print_results(results)
    failed = buckets["failed"]
    warnings = buckets["warnings"]
    passed = buckets["passed"]
    skipped = buckets["skipped"]

    if failed:
        print("\nVersion mismatches detected:")
        for r in failed:
            print(f"  - {r.file}: expected {r.expected}, found {r.found}")
            print(f"    {r.detail}")
        return 1

    if warnings and args.strict:
        print("\nWarnings treated as failures (--strict mode):")
        for r in warnings:
            print(f"  - {r.file}: {r.detail}")
        return 1

    if warnings:
        print(f"\n{len(warnings)} warning(s) (non-blocking). All {len(passed)} required version checks passed.")
    else:
        print(f"\nAll {len(passed)} required version checks passed ({len(skipped)} optional skipped). Version {expected} is consistent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
