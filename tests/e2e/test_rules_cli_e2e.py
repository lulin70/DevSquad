#!/usr/bin/env python3
"""Real-subprocess E2E coverage for W1-2 rule explanation."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_CLI_PATH = _PROJECT_ROOT / "scripts" / "cli.py"

pytestmark = [pytest.mark.e2e, pytest.mark.slow]


def test_rules_check_is_explainable_from_a_real_shell(tmp_path: Path) -> None:
    rule_file = tmp_path / "rule.json"
    rule_file.write_text(
        json.dumps({"rules": [{"pattern": "**/*.py", "body": {"review": True, "owner": "cli"}}]}),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(_PROJECT_ROOT)
    env["PYTHONUNBUFFERED"] = "1"

    result = subprocess.run(
        [
            sys.executable,
            str(_CLI_PATH),
            "rules",
            "check",
            "src/app.py",
            "--rule",
            str(rule_file),
            "--repo-root",
            str(tmp_path),
        ],
        cwd=str(_PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert "Layer: cli" in result.stdout
    assert "Pattern: **/*.py" in result.stdout
    assert '"owner": "cli"' in result.stdout
