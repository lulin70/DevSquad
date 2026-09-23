#!/usr/bin/env python3
"""TRAE cache content-diff checks for the version-consistency gate.

Extracted from ``check_version_consistency.py`` (V4.5.20 size-gate refactor).

Why these checks exist: the version-field checks can all pass while the
SKILL.md / skill-manifest.yaml body shipped in the TRAE skill panel is stale
(the V4.3.1 bug: 30/30 PASS while users saw V4.3.0 content). These pairs
compare the repo source file byte-for-byte against each TRAE cache layer.

``CONTENT_DIFF_PAIRS`` and ``check_content_diff`` are re-exported from
``check_version_consistency`` so the CLI and its public names are unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from scripts.check_version_consistency_types import VersionCheck

REPO_ROOT = Path(__file__).resolve().parent.parent


# === Content diff pairs (V4.3.1 enhancement) ===
# Pairs of (source_file, cache_file) that must be byte-identical.
# Catches the V4.3.1 bug where only the `version:` field was synced to TRAE
# caches but the SKILL.md body remained stale (V4.3.0 description, old test
# counts). Version-field-only checks gave 30/30 PASS while users saw stale
# content in the TRAE skill panel.
@dataclass
class ContentDiffSpec:
    """Specification for a content diff check between source and cache file.

    source_path:
        Project-relative path of the canonical source file.
    cache_path:
        Absolute path of the cache file to compare against.
    description:
        Human-readable label shown in the report.
    optional:
        If True, a missing cache file is OK (reported as SKIP, not FAIL).
        Used for L1/L2 TRAE caches that don't exist in CI environments.
    """

    source_path: str
    cache_path: Path
    description: str
    optional: bool = False


CONTENT_DIFF_PAIRS: list[ContentDiffSpec] = [
    # L1: User-level TRAE CN cache (China edition)
    ContentDiffSpec(
        source_path="SKILL.md",
        cache_path=Path.home() / ".trae-cn" / "skills" / "devsquad" / "SKILL.md",
        description="TRAE L1 cache (~/.trae-cn) SKILL.md content",
        optional=True,
    ),
    # L2: User-level TRAE cache (International edition)
    ContentDiffSpec(
        source_path="SKILL.md",
        cache_path=Path.home() / ".trae" / "skills" / "devsquad" / "SKILL.md",
        description="TRAE L2 cache (~/.trae) SKILL.md content",
        optional=True,
    ),
    # L3: TRAE workspace root .trae (TRAE actually reads from here!)
    # This is /Users/lin/trae_projects/.trae/, NOT DevSquad/.trae/.
    # Discovered 2026-07-27: Skill panel showed V4.1.7 even after DevSquad/.trae
    # was synced, because TRAE reads from workspace root .trae, not project .trae.
    # V4.5.13: this is now the SINGLE-SOURCE skill registration layer.
    ContentDiffSpec(
        source_path="SKILL.md",
        cache_path=REPO_ROOT.parent / ".trae" / "skills" / "devsquad" / "SKILL.md",
        description="TRAE L3 cache (workspace root .trae) SKILL.md content",
        optional=True,
    ),
    # L4: DevSquad project .trae (historical/backup, not read by TRAE directly)
    ContentDiffSpec(
        source_path="SKILL.md",
        cache_path=REPO_ROOT / ".trae" / "skills" / "devsquad" / "SKILL.md",
        description="TRAE L4 cache (DevSquad .trae) SKILL.md content",
        optional=True,
    ),
    # skill-manifest.yaml (same 4 layers)
    ContentDiffSpec(
        source_path="skill-manifest.yaml",
        cache_path=Path.home() / ".trae-cn" / "skills" / "devsquad" / "skill-manifest.yaml",
        description="TRAE L1 cache (~/.trae-cn) skill-manifest.yaml content",
        optional=True,
    ),
    ContentDiffSpec(
        source_path="skill-manifest.yaml",
        cache_path=Path.home() / ".trae" / "skills" / "devsquad" / "skill-manifest.yaml",
        description="TRAE L2 cache (~/.trae) skill-manifest.yaml content",
        optional=True,
    ),
    ContentDiffSpec(
        source_path="skill-manifest.yaml",
        cache_path=REPO_ROOT.parent / ".trae" / "skills" / "devsquad" / "skill-manifest.yaml",
        description="TRAE L3 cache (workspace root .trae) skill-manifest.yaml content",
        optional=True,
    ),
    ContentDiffSpec(
        source_path="skill-manifest.yaml",
        cache_path=REPO_ROOT / ".trae" / "skills" / "devsquad" / "skill-manifest.yaml",
        description="TRAE L4 cache (DevSquad .trae) skill-manifest.yaml content",
        optional=True,
    ),
]


def check_content_diff(spec: ContentDiffSpec) -> VersionCheck:
    """Verify that cache file is byte-identical to source file.

    Returns a VersionCheck-like result. ``expected`` carries the source path
    and ``found`` carries "identical" / "differs" / None for missing files.
    """
    source = REPO_ROOT / spec.source_path
    if not source.exists():
        return VersionCheck(
            file=spec.description,
            expected=spec.source_path,
            found=None,
            passed=False,
            detail=f"source file missing: {spec.source_path}",
        )
    if not spec.cache_path.exists():
        if spec.optional:
            return VersionCheck(
                file=spec.description,
                expected=spec.source_path,
                found=None,
                passed=True,
                detail=f"SKIP (optional cache, not found): {spec.description}",
            )
        return VersionCheck(
            file=spec.description,
            expected=spec.source_path,
            found=None,
            passed=False,
            detail=f"cache file missing: {spec.cache_path}",
        )
    try:
        source_content = source.read_text(encoding="utf-8")
        cache_content = spec.cache_path.read_text(encoding="utf-8")
    except OSError as exc:
        return VersionCheck(
            file=spec.description,
            expected=spec.source_path,
            found=None,
            passed=False,
            detail=f"read error: {exc}",
        )
    if source_content == cache_content:
        return VersionCheck(
            file=spec.description,
            expected=spec.source_path,
            found="identical",
            passed=True,
            detail=f"{spec.description}: identical to source OK",
        )
    # Compute first diverging line for actionable diagnostics
    source_lines = source_content.splitlines()
    cache_lines = cache_content.splitlines()
    first_diff_line = 0
    max_lines = max(len(source_lines), len(cache_lines))
    for i in range(max_lines):
        s = source_lines[i] if i < len(source_lines) else "<EOF>"
        c = cache_lines[i] if i < len(cache_lines) else "<EOF>"
        if s != c:
            first_diff_line = i + 1
            break
    return VersionCheck(
        file=spec.description,
        expected=spec.source_path,
        found="differs",
        passed=False,
        detail=(
            f"{spec.description}: content differs from source "
            f"(source={len(source_lines)}L, cache={len(cache_lines)}L, "
            f"first diff at line {first_diff_line})"
        ),
    )
