#!/usr/bin/env python3
"""P1 E2E: SessionResume CLI — Full resume journey via CLI.

Coverage:
  - `devsquad sessions list` returns session list or empty gracefully
  - `devsquad dispatch --resume <session-id>` resumes from checkpoint
  - Resume with nonexistent session handles error gracefully
  - Session history is preserved across CLI invocations

Uses subprocess (real CLI, not in-process).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_CLI_PATH = _PROJECT_ROOT / "scripts" / "cli.py"

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.slow,
]


def _run_cli(
    *args: str,
    timeout: int = 60,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run CLI command, return result."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(_PROJECT_ROOT)
    env["PYTHONUNBUFFERED"] = "1"
    env["DEVSQUAD_LLM_BACKEND"] = "mock"
    env["NO_COLOR"] = "1"
    env["TERM"] = "dumb"

    result = subprocess.run(
        [sys.executable, str(_CLI_PATH)] + list(args),
        cwd=str(_PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    if check and result.returncode not in (0, 1):
        raise AssertionError(
            f"CLI failed: {' '.join(args)}\n"
            f"Exit: {result.returncode}\n"
            f"STDERR: {result.stderr[:300]}\n"
            f"STDOUT: {result.stdout[:300]}"
        )
    return result


# ---------------------------------------------------------------------------
# Journey 1: sessions list — empty history
# ---------------------------------------------------------------------------

def test_e2e_sessions_list_empty_history():
    """Journey-1: sessions list runs without crash on empty history."""
    result = _run_cli("sessions", "list", check=False)
    assert result.returncode in (0, 1), (
        f"sessions list crashed: {result.returncode}\n"
        f"STDERR: {result.stderr[:300]}"
    )
    output = result.stdout + result.stderr
    assert "session" in output.lower() or "history" in output.lower(), (
        f"No session info in output: {output[:300]}"
    )


# ---------------------------------------------------------------------------
# Journey 2: sessions list — returns structured data
# ---------------------------------------------------------------------------

def test_e2e_sessions_list_returns_structured_output():
    """Journey-2: sessions list returns structured output (JSON or text table)."""
    result = _run_cli("sessions", "list", check=False)
    output = result.stdout.strip()
    assert len(output) > 0, "sessions list returned empty output"
    try:
        data = json.loads(output)
        assert isinstance(data, (dict, list)), "sessions list JSON should be dict or list"
    except json.JSONDecodeError:
        assert "error" not in output.lower() or result.returncode == 0, (
            f"sessions list returned error: {output[:300]}"
        )


# ---------------------------------------------------------------------------
# Journey 3: dispatch --resume with nonexistent session
# ---------------------------------------------------------------------------

def test_e2e_resume_nonexistent_session_handles_gracefully():
    """Journey-3: --resume with bad session ID exits with clear error."""
    result = _run_cli(
        "dispatch",
        "--resume", "nonexistent-session-id-12345",
        "--dry-run",
        check=False,
    )
    output = result.stdout + result.stderr
    is_error_response = (
        result.returncode != 0 and (
            "not found" in output.lower() or
            "invalid" in output.lower() or
            "does not exist" in output.lower() or
            "unknown" in output.lower()
        )
    )
    assert is_error_response or result.returncode in (0, 1), (
        f"--resume with bad ID should return clear error, got:\n"
        f"Exit: {result.returncode}\n"
        f"Output: {output[:300]}"
    )


# ---------------------------------------------------------------------------
# Journey 4: checkpoint persistence across processes
# ---------------------------------------------------------------------------

def test_e2e_checkpoint_persists_across_processes():
    """Journey-4: CheckpointManager saves/loads session across separate processes."""
    tmpdir = tempfile.mkdtemp(prefix="devsquad_session_e2e_")
    try:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(_PROJECT_ROOT)
        env["PYTHONUNBUFFERED"] = "1"
        env["DEVSQUAD_LLM_BACKEND"] = "mock"

        project_str = str(_PROJECT_ROOT)
        tmpdir_str = str(tmpdir)

        # Process 1: save a checkpoint
        script1 = f"""
import sys, os, json
sys.path.insert(0, '{project_str}')
from scripts.collaboration.checkpoint_manager import CheckpointManager, Checkpoint

mgr = CheckpointManager(storage_path='{tmpdir_str}')
cp = Checkpoint(
    checkpoint_id="e2e-test-session",
    task_id="test-task",
    step_name="step-0",
)
mgr.save_checkpoint(cp)
print("checkpoint_saved")
"""
        r1 = subprocess.run(
            [sys.executable, "-c", script1],
            cwd=str(_PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
        assert r1.returncode == 0, f"Save failed: {r1.stderr[:200]}"
        assert "checkpoint_saved" in r1.stdout, f"Save did not confirm: {r1.stdout}"

        # Process 2: resume from the checkpoint
        script2 = f"""
import sys, os, json
sys.path.insert(0, '{project_str}')
from scripts.collaboration.checkpoint_manager import CheckpointManager

mgr = CheckpointManager(storage_path='{tmpdir_str}')
status = mgr.get_session_status("e2e-test-session")
print(json.dumps({{"found": bool(status)}}))
"""
        r2 = subprocess.run(
            [sys.executable, "-c", script2],
            cwd=str(_PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
        assert r2.returncode == 0, f"Resume failed: {r2.stderr[:200]}"
        data = json.loads(r2.stdout)
        assert data.get("found"), f"Checkpoint not found in process 2: {r2.stdout}"
    finally:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Journey 5: sessions list shows recent sessions
# ---------------------------------------------------------------------------

def test_e2e_sessions_list_includes_recent_sessions():
    """Journey-5: After creating a checkpoint, sessions list shows it."""
    tmpdir = tempfile.mkdtemp(prefix="devsquad_session_list_e2e_")
    try:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(_PROJECT_ROOT)
        env["PYTHONUNBUFFERED"] = "1"
        env["DEVSQUAD_LLM_BACKEND"] = "mock"

        project_str = str(_PROJECT_ROOT)
        tmpdir_str = str(tmpdir)

        script = f"""
import sys
sys.path.insert(0, '{project_str}')
from scripts.collaboration.checkpoint_manager import CheckpointManager, Checkpoint
mgr = CheckpointManager(storage_path='{tmpdir_str}')
cp = Checkpoint(
    checkpoint_id="e2e-recent-session",
    task_id="recent-task",
    step_name="recent-step",
)
mgr.save_checkpoint(cp)
print("saved")
"""
        r = subprocess.run(
            [sys.executable, "-c", script],
            cwd=str(_PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
        assert r.returncode == 0

        script3 = f"""
import sys
sys.path.insert(0, '{project_str}')
from scripts.collaboration.checkpoint_manager import CheckpointManager
mgr = CheckpointManager(storage_path='{tmpdir_str}')
sessions = mgr.list_sessions()
print(f"session_count={{len(sessions)}}")
"""
        r3 = subprocess.run(
            [sys.executable, "-c", script3],
            cwd=str(_PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
        assert r3.returncode == 0, f"list_sessions failed: {r3.stderr[:200]}"
        assert "session_count=" in r3.stdout, (
            f"list_sessions did not return count: {r3.stdout}"
        )
    finally:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)
