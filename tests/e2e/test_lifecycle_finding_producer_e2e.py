"""Subprocess e2e test for lifecycle finding producer output."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_adapter_produces_json_findings_in_real_python_subprocess() -> None:
    script = """
import json
from scripts.collaboration.lifecycle_shortcut_adapter import ShortcutLifecycleAdapter

adapter = ShortcutLifecycleAdapter(use_unified_gate=False)
artifacts = {
    "P1": {"missing": ["objectives"]},
    "P8": {"failures": [{"category": "VULN-1", "description": "secret serialization", "evidence": ["secret-field"]}]},
    "P10": {"checks": {"rollback_plan": False}},
}
result = []
for phase, data in artifacts.items():
    result.extend(item.to_dict() for item in adapter.produce_findings(phase, data))
print(json.dumps(result, sort_keys=True))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    findings = json.loads(completed.stdout)
    assert {finding["lifecycle_phase"] for finding in findings} == {"P1", "P8", "P10"}
    assert {finding["category"] for finding in findings} == {"BREAK-1", "VULN-1", "BREAK-2"}
    assert all("rule_id" in finding and "evidence" in finding for finding in findings)
    assert "secret-field" in next(f["evidence"] for f in findings if f["lifecycle_phase"] == "P8")
