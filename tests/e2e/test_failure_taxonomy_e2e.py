#!/usr/bin/env python3
"""E2E: C19 failure taxonomy through the real CLI subprocess (V4.6.0 P1-b).

PRD §7.3 J3 — the blocked journey: with a deliberately invalid provider
credential, the dispatch must fail with exit code **2** and carry the
``environment_blocked`` disclosure in its output — never a silent,
unclassified failure that a CI would have to attribute by hand.

(The product-failure journey, exit 1, is covered at integration level in
``tests/integration/test_failure_class_propagation.py`` — a product-side
judgment failure cannot be forced through the real CLI without a live LLM
that misbehaves on cue.)
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_CLI_PATH = _PROJECT_ROOT / "scripts" / "cli.py"

pytestmark = [pytest.mark.e2e]


def test_blocked_backend_exits_2_with_disclosure():
    env = os.environ.copy()
    env["PYTHONPATH"] = str(_PROJECT_ROOT)
    env["PYTHONUNBUFFERED"] = "1"
    # Force the OpenAI backend with a present-but-invalid credential. A
    # present env value wins over .env re-injection (V4.5.20 finding), so
    # the subprocess cannot fall back to any working provider.
    env["DEVSQUAD_LLM_BACKEND"] = "openai"
    env["DEVSQUAD_OPENAI_API_KEY"] = "sk-invalid-for-c19-blocked-journey"
    env["DEVSQUAD_OPENAI_BASE_URL"] = "http://127.0.0.1:9"  # discard port: nothing listens
    env["DEVSQUAD_OPENAI_MODEL"] = "c19-probe-model"
    env["TERM"] = "dumb"
    env["NO_COLOR"] = "1"

    result = subprocess.run(
        [sys.executable, str(_CLI_PATH), "dispatch", "-t", "C19 blocked journey probe", "-r", "arch"],
        cwd=str(_PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=300,
        env=env,
    )

    output = result.stdout + result.stderr
    # C19: blocked runs exit 2 (non-zero — C9/C10 untouched) and say so.
    assert result.returncode == 2, f"expected exit 2 (environment_blocked), got {result.returncode}:\n{output[-800:]}"
    assert "environment_blocked" in output, f"exit 2 must carry the environment_blocked disclosure:\n{output[-800:]}"
