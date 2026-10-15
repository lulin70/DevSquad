"""Subprocess E2E test for the document scan to proposal path."""

import json
import subprocess
import sys

import pytest

pytestmark = pytest.mark.e2e


def test_real_python_subprocess_scans_and_renders_proposal(tmp_path):
    document = tmp_path / "requirements.md"
    document.write_text("# Objectives\n", encoding="utf-8")
    script = """
import json
import sys
from scripts.collaboration.lifecycle_protocol import render_proposals_json, scan_document, proposals_from_findings
result = scan_document(sys.argv[1], "P1", required_sections={"acceptance": "Acceptance Criteria"})
print(json.dumps({"parsed": result.parsed, "proposal": json.loads(render_proposals_json(proposals_from_findings(result.findings)))}))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script, str(document)],
        capture_output=True,
        text=True,
        check=True,
    )
    output = json.loads(completed.stdout)
    assert output["parsed"] is True
    assert output["proposal"][0]["approval_required"] is True
    assert output["proposal"][0]["lifecycle_phase"] == "P1"
