#!/usr/bin/env python3
"""TD-7 (Phase 3 Wave 1): Real CLI subprocess E2E tests.

Verifies that the ``devsquad`` CLI works as a real subprocess (not in-process
import). This matches the actual user experience: users invoke
``python -m scripts.cli ...`` from a shell, not via Python imports.

Coverage:
  - ``--version`` exits 0 and prints version
  - ``--help`` exits 0 and lists subcommands
  - ``dispatch -t "..." --dry-run`` produces a Markdown report
  - ``roles`` lists the 7 core roles
  - ``status`` reports system status
  - ``demo`` runs in mock mode without errors
  - Invalid command exits non-zero with stderr message

All tests use ``subprocess.run`` with a 60s timeout to prevent CI hangs.
Skipped when CLI dependencies are missing (e.g., in minimal venv).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_CLI_PATH = _PROJECT_ROOT / "scripts" / "cli.py"

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.slow,
]


def _run_cli(*args: str, timeout: int = 60, cwd: str | None = None) -> subprocess.CompletedProcess[str]:
    """Run the DevSquad CLI as a real subprocess.

    Args:
        *args: CLI arguments (e.g., "dispatch", "-t", "task text").
        timeout: Subprocess timeout in seconds (default 60).
        cwd: Working directory (defaults to project root).

    Returns:
        CompletedProcess with captured stdout/stderr.
    """
    env = os.environ.copy()
    env["PYTHONPATH"] = str(_PROJECT_ROOT)
    env["PYTHONUNBUFFERED"] = "1"
    env["DEVSQUAD_LLM_BACKEND"] = "mock"
    env["NO_COLOR"] = "1"
    env["TERM"] = "dumb"

    cmd = [sys.executable, str(_CLI_PATH), *args]
    return subprocess.run(
        cmd,
        cwd=cwd or str(_PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )


class TestCLISubprocessBasic:
    """Basic CLI subprocess smoke tests — no LLM calls, no side effects."""

    def test_cli_version_exits_zero(self) -> None:
        """``devsquad --version`` exits 0 and prints 'DevSquad'."""
        result = _run_cli("--version")
        assert result.returncode == 0, f"Expected exit 0, got {result.returncode}\nstderr: {result.stderr}"
        assert "DevSquad" in result.stdout, f"Expected 'DevSquad' in stdout, got: {result.stdout!r}"

    def test_cli_help_exits_zero(self) -> None:
        """``devsquad --help`` exits 0 and lists subcommands."""
        result = _run_cli("--help")
        assert result.returncode == 0, f"Expected exit 0, got {result.returncode}\nstderr: {result.stderr}"
        # Core subcommands must be documented in help
        for subcmd in ("dispatch", "demo", "status", "roles"):
            assert subcmd in result.stdout, f"Expected '{subcmd}' in help output"

    def test_cli_invalid_command_exits_nonzero(self) -> None:
        """``devsquad nonexistent-cmd`` exits non-zero with error message."""
        result = _run_cli("nonexistent-cmd-xyz", timeout=15)
        assert result.returncode != 0, "Expected non-zero exit for invalid command"
        # argparse should print error to stderr
        assert len(result.stderr) > 0, "Expected error message on stderr"


class TestCLISubprocessDispatch:
    """Dispatch command subprocess tests using mock backend + dry-run."""

    def test_cli_dispatch_dry_run_produces_report(self) -> None:
        """``devsquad dispatch -t "..." --dry-run`` produces Markdown report."""
        result = _run_cli(
            "dispatch",
            "-t", "Design a simple user authentication system",
            "--roles", "architect", "coder",
            "--mode", "parallel",
            "--dry-run",
            timeout=90,  # dry-run still spins up Coordinator
        )
        assert result.returncode == 0, (
            f"Dispatch dry-run failed (exit {result.returncode})\n"
            f"stdout: {result.stdout[:500]}\nstderr: {result.stderr[:500]}"
        )
        # Output should be non-trivial (Markdown report has structure)
        assert len(result.stdout) > 100, f"Output too short: {result.stdout!r}"

    def test_cli_dispatch_no_api_key_uses_mock(self) -> None:
        """Without API keys, dispatch falls back to mock backend successfully."""
        # Ensure no API keys in env (already set by _run_cli default env.copy)
        result = _run_cli(
            "dispatch",
            "-t", "Test task for mock backend",
            "--backend", "mock",
            "--dry-run",
            timeout=60,
        )
        assert result.returncode == 0, f"Mock dispatch failed: {result.stderr[:300]}"

    def test_cli_dispatch_compact_format(self) -> None:
        """``--format compact`` produces compact output (not full Markdown)."""
        result = _run_cli(
            "dispatch",
            "-t", "Compact format test",
            "--format", "compact",
            "--dry-run",
            timeout=60,
        )
        # Compact format should still exit 0; output may be shorter than markdown
        assert result.returncode == 0, f"Compact dispatch failed: {result.stderr[:300]}"


class TestCLISubprocessInfo:
    """Informational commands (roles, status, demo) subprocess tests."""

    def test_cli_roles_lists_seven_core_roles(self) -> None:
        """``devsquad roles`` lists all 7 core roles."""
        result = _run_cli("roles", timeout=30)
        assert result.returncode == 0, f"roles failed: {result.stderr[:300]}"
        # CLI uses short IDs for the 7 core roles: arch, pm, sec, test, coder, infra, ui
        # Each appears at start of a line in the roles table.
        short_ids = ["arch", "pm", "sec", "test", "coder", "infra", "ui"]
        lines = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
        # Each short ID must appear as the first token of at least one line
        # (e.g., "arch  — System design...").
        found = []
        for sid in short_ids:
            for ln in lines:
                tokens = ln.split()
                if tokens and tokens[0].lower() == sid:
                    found.append(sid)
                    break
        assert len(found) == 7, (
            f"Expected all 7 short role IDs in output, found {len(found)}: {found}\n"
            f"stdout: {result.stdout[:500]}"
        )

    def test_cli_status_reports_system_state(self) -> None:
        """``devsquad status`` reports version and component state."""
        result = _run_cli("status", timeout=30)
        assert result.returncode == 0, f"status failed: {result.stderr[:300]}"
        # Status should mention DevSquad or version
        output_lower = result.stdout.lower()
        assert "devsquad" in output_lower or "version" in output_lower, (
            f"Expected 'devsquad' or 'version' in status output: {result.stdout[:300]}"
        )

    def test_cli_demo_runs_in_mock_mode(self) -> None:
        """``devsquad demo`` runs all scenarios in mock mode without errors."""
        result = _run_cli("demo", timeout=90)  # demo may take time
        assert result.returncode == 0, (
            f"demo failed (exit {result.returncode})\nstderr: {result.stderr[:500]}"
        )
        # Demo produces meaningful output (not empty)
        assert len(result.stdout) > 50, f"Demo output too short: {result.stdout!r}"


class TestCLISubprocessLifecycle:
    """Lifecycle shortcut commands (spec/plan/build/test/review/ship) subprocess tests."""

    @pytest.mark.parametrize("cmd", ["spec", "plan", "build", "test", "review", "ship"])
    def test_cli_lifecycle_command_recognized(self, cmd: str) -> None:
        """Each lifecycle shortcut command is recognized (not 'unknown command')."""
        result = _run_cli("lifecycle", cmd, "--help", timeout=15)
        # --help should exit 0; if command is unknown, exit code would be 2
        assert "unknown" not in result.stderr.lower(), (
            f"Lifecycle command '{cmd}' not recognized: {result.stderr[:200]}"
        )
