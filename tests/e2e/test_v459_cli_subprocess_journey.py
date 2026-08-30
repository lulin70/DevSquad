"""Release-gate E2E tests for the real CLI user journey.

These tests deliberately launch ``scripts/cli.py`` in a separate process. The
in-process dispatcher tests cover Python API behavior; this file covers the
actual executable entry point, argument parsing, exit codes, and JSON output.
The explicit CLI async flag is a V4.5.10 item; it is not asserted here before
that interface exists.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CLI = PROJECT_ROOT / "scripts" / "cli.py"


def _run_cli(*args: str, env_overrides: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(
        {
            "DEVSQUAD_LLM_BACKEND": "mock",
            "DEVSQUAD_API_AUTH_DISABLED": "1",
            "PYTHONUNBUFFERED": "1",
        }
    )
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        [sys.executable, str(CLI), "dispatch", *args],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


@pytest.mark.e2e
def test_cli_subprocess_sync_dispatch_json_journey() -> None:
    result = _run_cli(
        "-t",
        "Design a small REST API",
        "-r",
        "architect",
        "-f",
        "json",
        "--no-warmup",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["success"] is True
    assert payload["matched_roles"] == ["architect"]
    assert "architect" in payload["report"]
    assert "MOCK MODE" in payload["report"]


@pytest.mark.e2e
def test_cli_subprocess_env_is_preserved_until_async_flag_exists() -> None:
    """The real CLI accepts the env without falsely claiming async dispatch.

    ``DEVSQUAD_USE_ASYNC`` is consumed by the Python async-dispatch path, not
    by the current CLI command. V4.5.10 will add and test ``--async``.
    """
    result = _run_cli(
        "review a Python module",
        "-r",
        "tester",
        "-f",
        "json",
        "--no-warmup",
        env_overrides={"DEVSQUAD_USE_ASYNC": "1"},
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["success"] is True
    assert payload["matched_roles"] == ["tester"]
    assert payload["report"]
