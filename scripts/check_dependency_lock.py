#!/usr/bin/env python3
"""
Dependency Lock Consistency Checker (ROADMAP P2-4)

Validates that pre-commit hook tool versions in ``.pre-commit-config.yaml``
align with the locked versions in ``requirements-dev.lock``. This prevents CI
drift caused by stale pre-commit hook versions (project_memory: "pre-commit
hooks 版本陈旧是 CI 漂移的根本原因"; "CI must use versions from
requirements-dev.txt instead of hard-pinning dependencies like ruff, mypy,
and black").

Check rules:
  - Remote PyPI-backed hooks (ruff/black/mypy mirrors): extract the package
    name from the repo URL, normalise the rev (strip leading ``v``), and
    compare with the lock entry.
  - Non-PyPI hooks (e.g. ``pre-commit/pre-commit-hooks`` — a framework-native
    hook repo, not a PyPI package): skipped with an INFO log.
  - Local hooks with ``language: system``: run ``<entry> --version`` and
    compare the installed version with the lock entry. Script-runner entries
    (``python``, ``bash`` …) are skipped silently.

Usage:
    python scripts/check_dependency_lock.py

Exit codes:
    0 = all PyPI-backed hooks aligned with requirements-dev.lock
    1 = version mismatch detected
    2 = file parsing failure (missing/unreadable config or lock file)
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
PRE_COMMIT_CONFIG = REPO_ROOT / ".pre-commit-config.yaml"
LOCK_FILE = REPO_ROOT / "requirements-dev.lock"

# Suffixes stripped from the repo URL basename to derive the PyPI package name.
# Order matters: longest first so "-pre-commit-mirror" is removed before
# "-pre-commit".
_REPO_SUFFIXES = ("-pre-commit-mirror", "-pre-commit", "-mirror")
_REPO_PREFIXES = ("mirrors-",)

# Entry commands that are script runners, not installable tools — skipped
# silently when checking local system hooks (no meaningful version to compare).
_SCRIPT_RUNNERS = {"python", "python3", "bash", "sh", "powershell", "pwsh"}


@dataclass
class RepoEntry:
    """A single ``- repo:`` block from ``.pre-commit-config.yaml``."""

    repo: str
    rev: str | None
    hooks: list[dict[str, str]]


@dataclass
class HookCheck:
    """Result of a single hook version check."""

    name: str
    source: str  # "pre-commit" | "system" | "non-PyPI"
    source_version: str | None
    lock_version: str | None
    status: str  # "OK" | "MISMATCH" | "SKIPPED" | "ERROR"
    detail: str = ""


def extract_package_name(repo_url: str) -> str:
    """Extract the PyPI package name from a pre-commit repo URL.

    Examples:
        ``https://github.com/astral-sh/ruff-pre-commit`` → ``ruff``
        ``https://github.com/psf/black-pre-commit-mirror`` → ``black``
        ``https://github.com/pre-commit/mirrors-mypy`` → ``mypy``
        ``https://github.com/pre-commit/pre-commit-hooks`` → ``pre-commit-hooks``
    """
    name = repo_url.rstrip("/").split("/")[-1]
    for suffix in _REPO_SUFFIXES:
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    for prefix in _REPO_PREFIXES:
        if name.startswith(prefix):
            name = name[len(prefix) :]
            break
    return name.lower()


def normalize_rev(rev: str) -> str:
    """Normalise a rev tag to a comparable version string.

    Strips a leading ``v`` (only when followed by a digit) and surrounding
    quotes::

        v0.15.20 → 0.15.20
        "0.15.20" → 0.15.20
        vabc → vabc  (no strip — not a version prefix)
    """
    rev = rev.strip().strip('"').strip("'")
    if len(rev) > 1 and rev[0] == "v" and rev[1].isdigit():
        rev = rev[1:]
    return rev


def parse_lock_file(text: str) -> dict[str, str]:
    """Parse a requirements lock file into ``{package: version}``.

    Handles lines like ``ruff==0.15.20`` (PEP 440 pinned spec). Comments and
    blank lines are ignored. Package names are lower-cased and underscores
    normalised to hyphens (PEP 503).
    """
    versions: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^([a-zA-Z0-9_.-]+)==([^\s;#]+)", line)
        if match:
            pkg = match.group(1).lower().replace("_", "-")
            versions[pkg] = match.group(2)
    return versions


def parse_pre_commit_config(text: str) -> list[RepoEntry]:
    """Parse ``.pre-commit-config.yaml`` text into a list of repo entries.

    Uses ``yaml.safe_load`` (PyYAML is a core project dependency). Each
    :class:`RepoEntry` carries the repo URL, rev (None for local repos), and
    a list of hook dicts with ``id``/``language``/``entry`` keys.
    """
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        return []
    repos = data.get("repos", [])
    if not isinstance(repos, list):
        return []
    entries: list[RepoEntry] = []
    for repo_block in repos:
        if not isinstance(repo_block, dict):
            continue
        repo_url = str(repo_block.get("repo", ""))
        rev_val = repo_block.get("rev")
        rev = str(rev_val) if rev_val is not None else None
        hooks_raw = repo_block.get("hooks", [])
        hooks: list[dict[str, str]] = []
        if isinstance(hooks_raw, list):
            for hook in hooks_raw:
                if isinstance(hook, dict):
                    hooks.append(
                        {
                            "id": str(hook.get("id", "")),
                            "language": str(hook.get("language", "")),
                            "entry": str(hook.get("entry", "")),
                        }
                    )
        entries.append(RepoEntry(repo=repo_url, rev=rev, hooks=hooks))
    return entries


def get_system_version(command: str) -> str | None:
    """Run ``<command> --version`` and extract the version string.

    Returns the first ``N.N[.N...]`` match found in the combined
    stdout/stderr output, or ``None`` if the command is unavailable.
    """
    tokens = command.split()
    cmd = tokens[0] if tokens else ""
    if not cmd:
        return None
    try:
        result = subprocess.run(  # noqa: S603 — fixed arg list, no shell
            [cmd, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        output = ((result.stdout or "") + (result.stderr or "")).strip()
    except (OSError, subprocess.SubprocessError):
        return None
    match = re.search(r"(\d+\.\d+(?:\.\d+)*)", output)
    return match.group(1) if match else None


def _check_remote_hook(repo_url: str, rev: str | None, lock_versions: dict[str, str]) -> HookCheck:
    """Check a remote (non-local) pre-commit hook against the lock file."""
    pkg_name = extract_package_name(repo_url)
    if pkg_name not in lock_versions:
        return HookCheck(
            name=pkg_name,
            source="non-PyPI",
            source_version=rev,
            lock_version=None,
            status="SKIPPED",
            detail=f"{pkg_name}: {rev} (non-PyPI, skipped)",
        )
    lock_version = lock_versions[pkg_name]
    if rev is None:
        return HookCheck(
            name=pkg_name,
            source="pre-commit",
            source_version=None,
            lock_version=lock_version,
            status="ERROR",
            detail=f"{pkg_name}: missing rev in .pre-commit-config.yaml, lock={lock_version} → ERROR",
        )
    source_version = normalize_rev(rev)
    if source_version == lock_version:
        return HookCheck(
            name=pkg_name,
            source="pre-commit",
            source_version=rev,
            lock_version=lock_version,
            status="OK",
            detail=f"{pkg_name}: pre-commit={rev}, lock={lock_version} → OK",
        )
    return HookCheck(
        name=pkg_name,
        source="pre-commit",
        source_version=rev,
        lock_version=lock_version,
        status="MISMATCH",
        detail=f"{pkg_name}: pre-commit={rev}, lock={lock_version} → MISMATCH",
    )


def _check_local_hook(
    hook: dict[str, str],
    lock_versions: dict[str, str],
    system_version_provider: Callable[[str], str | None],
) -> HookCheck | None:
    """Check a local ``language: system`` hook against the lock file.

    Returns ``None`` when the hook is not a system hook or uses a script
    runner (``python``/``bash`` …) that has no meaningful version to compare.
    """
    if hook.get("language") != "system":
        return None
    entry = hook.get("entry", "")
    tokens = entry.split()
    if not tokens:
        return None
    tool = tokens[0].lower()
    if tool in _SCRIPT_RUNNERS:
        return None  # script-based local hook, not a versioned tool
    if tool not in lock_versions:
        return HookCheck(
            name=tool,
            source="non-PyPI",
            source_version=None,
            lock_version=None,
            status="SKIPPED",
            detail=f"{tool}: local hook (not in lock, skipped)",
        )
    lock_version = lock_versions[tool]
    system_version = system_version_provider(tool)
    if system_version is None:
        return HookCheck(
            name=tool,
            source="system",
            source_version=None,
            lock_version=lock_version,
            status="ERROR",
            detail=f"{tool}: system version unavailable, lock={lock_version} → ERROR",
        )
    if system_version == lock_version:
        return HookCheck(
            name=tool,
            source="system",
            source_version=system_version,
            lock_version=lock_version,
            status="OK",
            detail=f"{tool}: system={system_version}, lock={lock_version} → OK",
        )
    return HookCheck(
        name=tool,
        source="system",
        source_version=system_version,
        lock_version=lock_version,
        status="MISMATCH",
        detail=f"{tool}: system={system_version}, lock={lock_version} → MISMATCH",
    )


def run_check(
    config_path: Path = PRE_COMMIT_CONFIG,
    lock_path: Path = LOCK_FILE,
    system_version_provider: Callable[[str], str | None] | None = None,
) -> int:
    """Run the dependency lock consistency check.

    Args:
        config_path: path to ``.pre-commit-config.yaml``.
        lock_path: path to ``requirements-dev.lock``.
        system_version_provider: callable that receives a tool name and
            returns its installed version (or ``None``). Defaults to
            :func:`get_system_version`. Injected by tests to avoid subprocess.

    Returns:
        0 = success, 1 = version mismatch, 2 = file parsing failure.
    """
    if system_version_provider is None:
        system_version_provider = get_system_version

    if not config_path.exists():
        print(f"[check_dependency_lock] ERROR: {config_path} not found")
        return 2
    if not lock_path.exists():
        print(f"[check_dependency_lock] ERROR: {lock_path} not found")
        return 2
    try:
        config_text = config_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"[check_dependency_lock] ERROR: cannot read {config_path}: {exc}")
        return 2
    try:
        lock_text = lock_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"[check_dependency_lock] ERROR: cannot read {lock_path}: {exc}")
        return 2

    try:
        repo_entries = parse_pre_commit_config(config_text)
    except yaml.YAMLError as exc:
        print(f"[check_dependency_lock] ERROR: failed to parse {config_path}: {exc}")
        return 2

    lock_versions = parse_lock_file(lock_text)
    if not lock_versions:
        print(f"[check_dependency_lock] ERROR: no pinned versions found in {lock_path}")
        return 2

    print("[check_dependency_lock] Checking pre-commit hook versions vs requirements-dev.lock")

    checks: list[HookCheck] = []
    for entry in repo_entries:
        if entry.repo == "local":
            for hook in entry.hooks:
                result = _check_local_hook(hook, lock_versions, system_version_provider)
                if result is not None:
                    checks.append(result)
        else:
            checks.append(_check_remote_hook(entry.repo, entry.rev, lock_versions))

    for check in checks:
        print(f"  {check.detail}")

    mismatches = [c for c in checks if c.status == "MISMATCH"]
    errors = [c for c in checks if c.status == "ERROR"]

    if mismatches or errors:
        print("[check_dependency_lock] FAILED: version mismatch")
        print("[check_dependency_lock] Please align .pre-commit-config.yaml rev with requirements-dev.lock")
        return 1

    print("[check_dependency_lock] All PyPI-backed hooks aligned with requirements-dev.lock")
    return 0


def main() -> int:
    """Entry point for CLI invocation."""
    return run_check()


if __name__ == "__main__":
    sys.exit(main())
