"""Unit tests for scripts/check_dependency_lock.py (ROADMAP P2-4).

Covers:
  T1  normal case (versions match) → exit 0
  T2  version mismatch (ruff rev ≠ lock) → exit 1
  T3  missing .pre-commit-config.yaml → exit 2
  T4  missing requirements-dev.lock → exit 2
  T5  non-PyPI hook skipped (pre-commit-hooks)
  T6  local hook (language: system) checks system version
  T7  multiple PyPI hooks checked simultaneously
  T8  rev format v0.15.20 → 0.15.20 conversion
  T9  lock file format ruff==0.15.20 parsing
  T10 repo URL → package name extraction

Additional tests raise the total above 15 (mismatches, script-runner skip,
mixed hooks, system version unavailable, edge cases).
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.check_dependency_lock import (
    extract_package_name,
    get_system_version,
    normalize_rev,
    parse_lock_file,
    parse_pre_commit_config,
    run_check,
)

# === T10: repo URL → package name extraction ===


class TestExtractPackageName(unittest.TestCase):
    def test_ruff_pre_commit(self) -> None:
        self.assertEqual(extract_package_name("https://github.com/astral-sh/ruff-pre-commit"), "ruff")

    def test_black_pre_commit_mirror(self) -> None:
        self.assertEqual(extract_package_name("https://github.com/psf/black-pre-commit-mirror"), "black")

    def test_mirrors_mypy(self) -> None:
        self.assertEqual(extract_package_name("https://github.com/pre-commit/mirrors-mypy"), "mypy")

    def test_pre_commit_hooks_not_stripped(self) -> None:
        # pre-commit-hooks has no matching suffix → stays as-is (treated non-PyPI)
        self.assertEqual(
            extract_package_name("https://github.com/pre-commit/pre-commit-hooks"),
            "pre-commit-hooks",
        )

    def test_url_with_trailing_slash(self) -> None:
        self.assertEqual(extract_package_name("https://github.com/astral-sh/ruff-pre-commit/"), "ruff")


# === T8: rev format conversion ===


class TestNormalizeRev(unittest.TestCase):
    def test_strip_v_prefix(self) -> None:
        self.assertEqual(normalize_rev("v0.15.20"), "0.15.20")

    def test_no_v_prefix(self) -> None:
        self.assertEqual(normalize_rev("0.15.20"), "0.15.20")

    def test_strip_quotes(self) -> None:
        self.assertEqual(normalize_rev('"v0.15.20"'), "0.15.20")

    def test_v_not_stripped_if_not_version(self) -> None:
        self.assertEqual(normalize_rev("vabc"), "vabc")

    def test_single_v_not_stripped(self) -> None:
        self.assertEqual(normalize_rev("v"), "v")


# === T9: lock file format parsing ===


class TestParseLockFile(unittest.TestCase):
    def test_basic_parse(self) -> None:
        text = "ruff==0.15.20\nmypy==2.2.0\n"
        self.assertEqual(parse_lock_file(text), {"ruff": "0.15.20", "mypy": "2.2.0"})

    def test_ignores_comments_and_blanks(self) -> None:
        text = "# header\n\nruff==0.15.20\n"
        self.assertEqual(parse_lock_file(text), {"ruff": "0.15.20"})

    def test_normalizes_underscores(self) -> None:
        text = "mypy_extensions==1.1.0\n"
        self.assertEqual(parse_lock_file(text), {"mypy-extensions": "1.1.0"})

    def test_empty_text(self) -> None:
        self.assertEqual(parse_lock_file(""), {})

    def test_skips_non_pinned_lines(self) -> None:
        # Lines with >= or without == are ignored (lock uses == pinning)
        text = "ruff==0.15.20\npytest>=7.0\n"
        result = parse_lock_file(text)
        self.assertEqual(result, {"ruff": "0.15.20"})


# === parse_pre_commit_config ===


class TestParsePreCommitConfig(unittest.TestCase):
    def test_parse_remote_repo(self) -> None:
        text = (
            "repos:\n"
            "  - repo: https://github.com/astral-sh/ruff-pre-commit\n"
            "    rev: v0.15.20\n"
            "    hooks:\n"
            "      - id: ruff\n"
            "      - id: ruff-format\n"
        )
        entries = parse_pre_commit_config(text)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].repo, "https://github.com/astral-sh/ruff-pre-commit")
        self.assertEqual(entries[0].rev, "v0.15.20")
        self.assertEqual(len(entries[0].hooks), 2)

    def test_parse_local_repo(self) -> None:
        text = "repos:\n  - repo: local\n    hooks:\n      - id: mypy\n        entry: mypy\n        language: system\n"
        entries = parse_pre_commit_config(text)
        self.assertEqual(entries[0].repo, "local")
        self.assertIsNone(entries[0].rev)
        self.assertEqual(entries[0].hooks[0]["language"], "system")
        self.assertEqual(entries[0].hooks[0]["entry"], "mypy")

    def test_parse_empty_config(self) -> None:
        self.assertEqual(parse_pre_commit_config(""), [])
        self.assertEqual(parse_pre_commit_config("repos: []\n"), [])


# === T1–T7 + extra: run_check end-to-end ===


class TestRunCheck(unittest.TestCase):
    """End-to-end tests using tempfile to isolate config/lock files."""

    def _write_files(self, config_text: str, lock_text: str) -> tuple[Path, Path, str]:
        tmpdir = tempfile.mkdtemp()
        config_path = Path(tmpdir) / ".pre-commit-config.yaml"
        lock_path = Path(tmpdir) / "requirements-dev.lock"
        config_path.write_text(config_text, encoding="utf-8")
        lock_path.write_text(lock_text, encoding="utf-8")
        return config_path, lock_path, tmpdir

    # T1: normal case — versions match → exit 0
    def test_t1_versions_match_exit0(self) -> None:
        config = (
            "repos:\n"
            "  - repo: https://github.com/astral-sh/ruff-pre-commit\n"
            "    rev: v0.15.20\n"
            "    hooks:\n"
            "      - id: ruff\n"
        )
        lock = "ruff==0.15.20\n"
        config_path, lock_path, _ = self._write_files(config, lock)
        self.assertEqual(run_check(config_path, lock_path), 0)

    # T2: version mismatch → exit 1
    def test_t2_version_mismatch_exit1(self) -> None:
        config = (
            "repos:\n"
            "  - repo: https://github.com/astral-sh/ruff-pre-commit\n"
            "    rev: v0.14.0\n"
            "    hooks:\n"
            "      - id: ruff\n"
        )
        lock = "ruff==0.15.20\n"
        config_path, lock_path, _ = self._write_files(config, lock)
        self.assertEqual(run_check(config_path, lock_path), 1)

    # T3: missing .pre-commit-config.yaml → exit 2
    def test_t3_missing_config_exit2(self) -> None:
        tmpdir = tempfile.mkdtemp()
        lock_path = Path(tmpdir) / "requirements-dev.lock"
        lock_path.write_text("ruff==0.15.20\n", encoding="utf-8")
        config_path = Path(tmpdir) / ".pre-commit-config.yaml"  # does not exist
        self.assertEqual(run_check(config_path, lock_path), 2)

    # T4: missing requirements-dev.lock → exit 2
    def test_t4_missing_lock_exit2(self) -> None:
        tmpdir = tempfile.mkdtemp()
        config_path = Path(tmpdir) / ".pre-commit-config.yaml"
        config_path.write_text("repos: []\n", encoding="utf-8")
        lock_path = Path(tmpdir) / "requirements-dev.lock"  # does not exist
        self.assertEqual(run_check(config_path, lock_path), 2)

    # T5: non-PyPI hook (pre-commit-hooks) skipped → exit 0
    def test_t5_non_pypi_hook_skipped(self) -> None:
        config = (
            "repos:\n"
            "  - repo: https://github.com/pre-commit/pre-commit-hooks\n"
            "    rev: v4.6.0\n"
            "    hooks:\n"
            "      - id: trailing-whitespace\n"
        )
        lock = "ruff==0.15.20\n"
        config_path, lock_path, _ = self._write_files(config, lock)
        # non-PyPI hook skipped; no PyPI hooks to mismatch → exit 0
        self.assertEqual(run_check(config_path, lock_path), 0)

    # T6: local hook (language: system) checks system version — match
    def test_t6_local_system_hook_match(self) -> None:
        config = (
            "repos:\n  - repo: local\n    hooks:\n      - id: mypy\n        entry: mypy\n        language: system\n"
        )
        lock = "mypy==2.2.0\n"
        config_path, lock_path, _ = self._write_files(config, lock)
        provider = mock.Mock(return_value="2.2.0")
        self.assertEqual(run_check(config_path, lock_path, system_version_provider=provider), 0)

    # T6b: local hook (language: system) — mismatch
    def test_t6b_local_system_hook_mismatch(self) -> None:
        config = (
            "repos:\n  - repo: local\n    hooks:\n      - id: mypy\n        entry: mypy\n        language: system\n"
        )
        lock = "mypy==2.2.0\n"
        config_path, lock_path, _ = self._write_files(config, lock)
        provider = mock.Mock(return_value="2.1.0")
        self.assertEqual(run_check(config_path, lock_path, system_version_provider=provider), 1)

    # T7: multiple PyPI hooks — all match
    def test_t7_multiple_pypi_hooks_all_ok(self) -> None:
        config = (
            "repos:\n"
            "  - repo: https://github.com/astral-sh/ruff-pre-commit\n"
            "    rev: v0.15.20\n"
            "    hooks:\n"
            "      - id: ruff\n"
            "  - repo: https://github.com/psf/black-pre-commit-mirror\n"
            "    rev: 26.5.1\n"
            "    hooks:\n"
            "      - id: black\n"
        )
        lock = "ruff==0.15.20\nblack==26.5.1\n"
        config_path, lock_path, _ = self._write_files(config, lock)
        self.assertEqual(run_check(config_path, lock_path), 0)

    # T7b: multiple PyPI hooks — one mismatch
    def test_t7b_multiple_pypi_hooks_one_mismatch(self) -> None:
        config = (
            "repos:\n"
            "  - repo: https://github.com/astral-sh/ruff-pre-commit\n"
            "    rev: v0.15.20\n"
            "    hooks:\n"
            "      - id: ruff\n"
            "  - repo: https://github.com/psf/black-pre-commit-mirror\n"
            "    rev: 26.5.0\n"
            "    hooks:\n"
            "      - id: black\n"
        )
        lock = "ruff==0.15.20\nblack==26.5.1\n"
        config_path, lock_path, _ = self._write_files(config, lock)
        self.assertEqual(run_check(config_path, lock_path), 1)

    # Local script-runner hook (python scripts/...) silently skipped
    def test_local_script_hook_skipped(self) -> None:
        config = (
            "repos:\n"
            "  - repo: local\n"
            "    hooks:\n"
            "      - id: version-consistency\n"
            "        entry: python scripts/check_version_consistency.py\n"
            "        language: system\n"
        )
        lock = "ruff==0.15.20\n"
        config_path, lock_path, _ = self._write_files(config, lock)
        self.assertEqual(run_check(config_path, lock_path), 0)

    # Mixed hooks: remote PyPI + non-PyPI + local system — all aligned
    def test_mixed_hooks_all_aligned(self) -> None:
        config = (
            "repos:\n"
            "  - repo: https://github.com/astral-sh/ruff-pre-commit\n"
            "    rev: v0.15.20\n"
            "    hooks:\n"
            "      - id: ruff\n"
            "  - repo: https://github.com/pre-commit/pre-commit-hooks\n"
            "    rev: v4.6.0\n"
            "    hooks:\n"
            "      - id: trailing-whitespace\n"
            "  - repo: local\n"
            "    hooks:\n"
            "      - id: mypy\n"
            "        entry: mypy\n"
            "        language: system\n"
        )
        lock = "ruff==0.15.20\nmypy==2.2.0\n"
        config_path, lock_path, _ = self._write_files(config, lock)
        provider = mock.Mock(return_value="2.2.0")
        self.assertEqual(run_check(config_path, lock_path, system_version_provider=provider), 0)

    # Local system hook where the tool is unavailable → ERROR → exit 1
    def test_local_system_hook_unavailable(self) -> None:
        config = (
            "repos:\n  - repo: local\n    hooks:\n      - id: mypy\n        entry: mypy\n        language: system\n"
        )
        lock = "mypy==2.2.0\n"
        config_path, lock_path, _ = self._write_files(config, lock)
        provider = mock.Mock(return_value=None)
        self.assertEqual(run_check(config_path, lock_path, system_version_provider=provider), 1)

    # Empty lock file (exists but no pinned versions) → exit 2
    def test_empty_lock_file_exit2(self) -> None:
        config = (
            "repos:\n"
            "  - repo: https://github.com/astral-sh/ruff-pre-commit\n"
            "    rev: v0.15.20\n"
            "    hooks:\n"
            "      - id: ruff\n"
        )
        lock = "# only comments\n"
        config_path, lock_path, _ = self._write_files(config, lock)
        self.assertEqual(run_check(config_path, lock_path), 2)

    # rev without v-prefix still compares correctly
    def test_rev_without_v_prefix(self) -> None:
        config = (
            "repos:\n"
            "  - repo: https://github.com/psf/black-pre-commit-mirror\n"
            "    rev: 26.5.1\n"
            "    hooks:\n"
            "      - id: black\n"
        )
        lock = "black==26.5.1\n"
        config_path, lock_path, _ = self._write_files(config, lock)
        self.assertEqual(run_check(config_path, lock_path), 0)


# === get_system_version (real subprocess, only for unavailable command) ===


class TestGetSystemVersion(unittest.TestCase):
    def test_unavailable_command_returns_none(self) -> None:
        result = get_system_version("nonexistent_tool_xyz123_456")
        self.assertIsNone(result)

    def test_empty_command_returns_none(self) -> None:
        self.assertIsNone(get_system_version(""))


if __name__ == "__main__":
    unittest.main()
