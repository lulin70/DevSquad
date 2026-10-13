"""Subprocess E2E for the V4.7.0 deterministic review taxonomy."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]

pytestmark = [pytest.mark.e2e, pytest.mark.slow]


_RUN_GATE = """
import json
import sys
from scripts.collaboration.two_stage_review_gate import TwoStageReviewGate

payload = json.loads(sys.stdin.read())
result = TwoStageReviewGate(enable_redesign_audit=False).review(code_changes=payload)
print(json.dumps({"stage2": result.stage2_result.value, "report": TwoStageReviewGate(enable_redesign_audit=False).format_report(result), "findings": [item.to_dict() for item in result.findings]}))
"""


def _run_gate(files: dict[str, str]) -> dict[str, object]:
    env = os.environ.copy()
    env.update({"PYTHONPATH": str(_PROJECT_ROOT), "PYTHONUNBUFFERED": "1", "NO_COLOR": "1"})
    completed = subprocess.run(
        [sys.executable, "-c", _RUN_GATE],
        cwd=_PROJECT_ROOT,
        env=env,
        input=json.dumps({"files": {path: {"content": content} for path, content in files.items()}}),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert completed.returncode == 0, completed.stderr[-1200:]
    return json.loads(completed.stdout)


def test_real_review_gate_reports_route_break_with_evidence() -> None:
    output = _run_gate(
        {"src/routes.py": "@app.get('/users')\ndef users():\n    return {'ok': True}\nredirect('/missing')\n"}
    )

    assert output["stage2"] == "fail"
    finding = next(item for item in output["findings"] if item["category"] == "BREAK-5")
    assert finding["file_path"] == "src/routes.py"
    assert finding["line_range"] == "4"
    assert "BV-BREAK5-nav-target-missing" in finding["description"]
    assert "[BREAK-5]" in output["report"]
    assert "File: `src/routes.py`" in output["report"]
    assert "Line: `4`" in output["report"]


def test_real_review_gate_discloses_documentation_scope() -> None:
    output = _run_gate({"README.md": "review notes\n"})

    scope = next(item for item in output["findings"] if item["category"] == "break_vuln_scope")
    assert scope["severity"] == "info"
    assert "not_applicable" in scope["description"]
    assert output["stage2"] == "warn"
    assert output["report"]
