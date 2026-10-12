#!/usr/bin/env python3
"""E2E: LLM replay cache through the real CLI subprocess (V4.6.0 P1-a).

PRD §7.3 J1 — the two-run replay journey a real user would experience:

1. Run ``devsquad dispatch`` (read-write) with a real backend: the worker
   responses are recorded on disk.
2. Run the same task again (read): the worker responses replay from disk —
   the run succeeds without paying for the model calls again — and the JSON
   output discloses the replay ratio.

Skipped unless a real backend credential is present (same contract as
``tests/external/``); CI's e2e job injects the credentials and is the primary
consumer — the actions/cache wiring in ``test.yml`` persists the recordings
between PRs, so ordinary PRs replay at ~zero model cost (PRD §4.2).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_CLI_PATH = _PROJECT_ROOT / "scripts" / "cli.py"

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.external,
]


def _has_real_backend() -> bool:
    """True when a real backend credential is available in this environment."""
    return bool(
        os.environ.get("DEVSQUAD_OPENAI_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("MOKA_API_KEY")
        or os.environ.get("DEVSQUAD_ANTHROPIC_API_KEY")
        or os.environ.get("ANTHROPIC_API_KEY")
    )


pytestmark_skip = pytest.mark.skipif(not _has_real_backend(), reason="no real backend credential configured")


def _run_dispatch(task: str, mode: str, backend: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(_PROJECT_ROOT)
    env["PYTHONUNBUFFERED"] = "1"
    env["DEVSQUAD_LLM_BACKEND"] = backend
    env["DEVSQUAD_LLM_REPLAY_CACHE"] = mode
    env["TERM"] = "dumb"
    env["NO_COLOR"] = "1"
    return subprocess.run(
        [
            sys.executable,
            str(_CLI_PATH),
            "dispatch",
            "-t",
            task,
            "-r",
            "arch",
            "-f",
            "json",
        ],
        cwd=str(_PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=300,
        env=env,
    )


@pytest.mark.skipif(not _has_real_backend(), reason="no real backend credential configured")
class TestReplaySubprocessJourney:
    def test_record_then_replay_via_cli(self):
        task = "Reply with exactly the word: e2e-replay-ok"

        # Run 1 (read-write): real calls, responses recorded.
        r1 = _run_dispatch(task, "read-write", backend="auto")
        assert r1.returncode == 0, f"run1 failed:\n{r1.stdout[-800:]}\n{r1.stderr[-800:]}"
        payload1 = json.loads(r1.stdout)
        assert payload1["success"] is True

        # Run 2 (read): the same task replays — the worker path must not call
        # the backend again; the JSON must disclose the replay ratio. The CLI
        # JSON is flat: replay_cache sits at the top level (cli_dispatch).
        r2 = _run_dispatch(task, "read", backend="auto")
        assert r2.returncode == 0, f"run2 failed:\n{r2.stdout[-800:]}\n{r2.stderr[-800:]}"
        payload2 = json.loads(r2.stdout)
        assert payload2["success"] is True
        replay = payload2.get("replay_cache")
        assert replay is not None, "run2 JSON must carry the replay_cache disclosure"
        assert replay["mode"] == "read"
        assert replay["hits"] >= 1, (
            f"run2 should replay recorded responses; got {replay} "
            "(first-run recording may have been invalidated by a prompt change — rerun once)"
        )
