#!/usr/bin/env python3
"""P0 version consistency checks.

Verifies that the version declared in the package, project metadata, and
key documentation files all reference the same canonical version.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from scripts.collaboration._version import __version__

PROJECT_ROOT = Path(__file__).parent.parent


def _read_text(rel_path: str) -> str:
    path = PROJECT_ROOT / rel_path
    if not path.exists():
        pytest.fail(f"Required file does not exist: {path}")
    return path.read_text(encoding="utf-8")


def test_version_file_matches_package_version():
    """根目录 VERSION 文件中的版本号必须与 _version.py 一致。"""
    version_text = _read_text("VERSION").strip()
    assert version_text == __version__, (
        f"VERSION file ({version_text}) does not match package version ({__version__})"
    )


def test_pyproject_version_matches_package_version():
    """pyproject.toml 中的 project.version 必须与 _version.py 一致。"""
    pyproject_text = _read_text("pyproject.toml")
    match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject_text, re.MULTILINE)
    assert match, "Could not find project.version in pyproject.toml"
    assert match.group(1) == __version__, (
        f"pyproject.toml version ({match.group(1)}) does not match package version ({__version__})"
    )


def test_readme_contains_package_version():
    """README.md 必须包含当前版本号。"""
    readme_text = _read_text("README.md")
    assert __version__ in readme_text, (
        f"README.md does not contain version {__version__}"
    )


def test_skill_doc_contains_package_version():
    """SKILL.md 必须包含当前版本号。"""
    skill_text = _read_text("SKILL.md")
    assert __version__ in skill_text, (
        f"SKILL.md does not contain version {__version__}"
    )


def test_changelog_contains_package_version():
    """CHANGELOG.md 必须包含当前版本号的最新条目。"""
    changelog_text = _read_text("CHANGELOG.md")
    assert __version__ in changelog_text, (
        f"CHANGELOG.md does not contain version {__version__}"
    )


def test_dockerfile_label_uses_package_version():
    """Dockerfile 中的版本标签必须与当前版本号一致。"""
    dockerfile_text = _read_text("Dockerfile")
    assert __version__ in dockerfile_text, (
        f"Dockerfile does not contain version {__version__}"
    )


def test_skill_manifest_uses_package_version():
    """skill-manifest.yaml 中的版本号必须与 _version.py 一致。"""
    manifest_text = _read_text("skill-manifest.yaml")
    match = re.search(r'^version:\s*([0-9.]+)', manifest_text, re.MULTILINE)
    assert match, "Could not find version in skill-manifest.yaml"
    assert match.group(1) == __version__, (
        f"skill-manifest.yaml version ({match.group(1)}) does not match package version ({__version__})"
    )
