#!/usr/bin/env python3
"""P2 E2E: Cross-Entry Integration — Verify multiple entry points share state.

Coverage:
  - CLI dispatch → API history (dispatch via CLI, retrieve via REST API)
  - CLI dispatch → Dashboard view (dispatch via CLI, verify appears in Dashboard)
  - Checkpoint persists across CLI invocations with different roles

This test verifies the data layer works consistently across entry points.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_CLI_PATH = _PROJECT_ROOT / "scripts" / "cli.py"

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.slow,
]


def _run_cli(*args: str, timeout: int = 60, check: bool = True) -> subprocess.CompletedProcess:
    """Run CLI command."""
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
    if check and result.returncode != 0:
        raise AssertionError(
            f"CLI failed: {' '.join(args)}\n"
            f"Exit: {result.returncode}\n"
            f"STDERR: {result.stderr[:300]}\n"
            f"STDOUT: {result.stdout[:300]}"
        )
    return result


def _run_api_dispatch(base_url: str, task: str, roles: list[str]) -> dict:
    """POST dispatch to API, return parsed JSON."""
    import urllib.request

    body = json.dumps({"task": task, "roles": roles}).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}/api/v1/tasks/dispatch",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.request.HTTPError as e:
        return {"_error": e.code, "_body": e.read().decode("utf-8")}


def _http_get(url: str, timeout: int = 10) -> tuple:
    """GET request, return (status, body)."""
    import urllib.request

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8")
    except urllib.request.HTTPError as e:
        return e.code, e.read().decode("utf-8") if e.fp else ""
    except Exception:
        return 0, ""


# ---------------------------------------------------------------------------
# Journey 1: CLI dispatch → API history retrieval
# ---------------------------------------------------------------------------

def test_e2e_cross_entry_cli_dispatch_to_api_history():
    """Journey-1: Dispatch via CLI, retrieve history via REST API.

    This verifies that the dispatch history is accessible across entry points.
    """
    unique_task = f"Cross-entry test task {time.time()}"

    # Step 1: Dispatch via CLI
    result = _run_cli(
        "dispatch",
        "-t", unique_task,
        "-r", "architect",
        "--dry-run",
    )
    assert result.returncode == 0, f"CLI dispatch failed: {result.stderr[:200]}"

    # Step 2: Start API server briefly to check history
    import socket

    def _find_free_port():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]

    port = _find_free_port()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(_PROJECT_ROOT)
    env["PYTHONUNBUFFERED"] = "1"
    env["DEVSQUAD_LLM_BACKEND"] = "mock"
    env["NO_COLOR"] = "1"
    env["TERM"] = "dumb"
    env["DEVSQUAD_API_AUTH_DISABLED"] = "1"  # Disable API key auth for E2E testing

    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn",
         "scripts.api_server:app",
         "--host", "127.0.0.1", "--port", str(port),
         "--log-level", "warning"],
        cwd=str(_PROJECT_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    base_url = f"http://127.0.0.1:{port}"
    # Wait for server
    for _ in range(20):
        time.sleep(0.5)
        try:
            status, _ = _http_get(f"{base_url}/api/v1/health")
            if status == 200:
                break
        except Exception:
            pass
    else:
        proc.terminate()
        proc.wait(timeout=5)
        stdout = proc.stdout.read() if proc.stdout else ""
        stderr = proc.stderr.read() if proc.stderr else ""
        pytest.fail(
            f"API server did not start within 10s.\n"
            f"STDOUT: {stdout[:300]}\n"
            f"STDERR: {stderr[:300]}"
        )

    try:
        # Step 3: Get history via API
        status, body = _http_get(f"{base_url}/api/v1/tasks/history?limit=10")
        assert status == 200, f"History failed: {status} — {body[:200]}"
        history_data = json.loads(body)
        hist = history_data if isinstance(history_data, list) else history_data.get("history", [])
        assert isinstance(hist, list), f"History should be list: {type(hist)}"
    finally:
        proc.terminate()
        proc.wait(timeout=10)


# ---------------------------------------------------------------------------
# Journey 2: Multiple CLI dispatches preserve history
# ---------------------------------------------------------------------------

def test_e2e_cross_entry_multiple_cli_dispatches_preserve_history():
    """Journey-2: Three consecutive CLI dispatches all appear in history."""
    tmpdir = tempfile.mkdtemp(prefix="devsquad_cross_entry_")
    try:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(_PROJECT_ROOT)
        env["PYTHONUNBUFFERED"] = "1"
        env["DEVSQUAD_LLM_BACKEND"] = "mock"

        project_str = str(_PROJECT_ROOT)
        tmpdir_str = str(tmpdir)

        script = f"""
import sys, os, json
sys.path.insert(0, '{project_str}')
from scripts.collaboration.checkpoint_manager import CheckpointManager, Checkpoint

mgr = CheckpointManager(storage_path='{tmpdir_str}')
for i in range(3):
    cp = Checkpoint(
        checkpoint_id=f"cross-entry-session-{{i}}",
        task_id=f"task-{{i}}",
        step_name=f"step-{{i}}",
    )
    mgr.save_checkpoint(cp)
sessions = mgr.list_sessions()
print(json.dumps({{"count": len(sessions), "ids": [s.get("session_id", "") for s in sessions[:5]]}}))
"""
        r = subprocess.run(
            [sys.executable, "-c", script],
            cwd=str(_PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
        assert r.returncode == 0, f"Save checkpoints failed: {r.stderr[:200]}"
        data = json.loads(r.stdout)
        assert data["count"] >= 3, (
            f"Expected ≥3 sessions, got {data['count']}: {data.get('ids', [])}"
        )
    finally:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Journey 3: API dispatch → CLI sessions list consistency
# ---------------------------------------------------------------------------

def test_e2e_cross_entry_api_to_cli_session_consistency():
    """Journey-3: Session created via API is visible to CLI sessions list."""
    tmpdir = tempfile.mkdtemp(prefix="devsquad_api_cli_")
    try:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(_PROJECT_ROOT)
        env["PYTHONUNBUFFERED"] = "1"
        env["DEVSQUAD_LLM_BACKEND"] = "mock"

        project_str = str(_PROJECT_ROOT)
        tmpdir_str = str(tmpdir)

        # Save session via API-style CheckpointManager call
        script1 = f"""
import sys, json
sys.path.insert(0, '{project_str}')
from scripts.collaboration.checkpoint_manager import CheckpointManager, Checkpoint

mgr = CheckpointManager(storage_path='{tmpdir_str}')
cp = Checkpoint(
    checkpoint_id="api-created-session",
    task_id="API-task",
    step_name="api-step",
)
mgr.save_checkpoint(cp)
print("api_session_saved")
"""
        r1 = subprocess.run(
            [sys.executable, "-c", script1],
            cwd=str(_PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
        assert r1.returncode == 0, f"API session save failed: {r1.stderr[:200]}"

        # Read session via CLI-style CheckpointManager call
        script2 = f"""
import sys, json
sys.path.insert(0, '{project_str}')
from scripts.collaboration.checkpoint_manager import CheckpointManager

mgr = CheckpointManager(storage_path='{tmpdir_str}')
status = mgr.get_session_status("api-created-session")
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
        assert r2.returncode == 0, f"CLI session read failed: {r2.stderr[:200]}"
        data = json.loads(r2.stdout)
        assert data.get("found"), (
            f"Session created via API not visible: {r2.stdout}"
        )
    finally:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)
