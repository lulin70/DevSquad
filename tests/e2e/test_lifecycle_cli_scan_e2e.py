"""Real subprocess E2E for lifecycle CLI document and JUnit evidence paths."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.e2e


def test_lifecycle_cli_scans_document_and_junit_without_writing(tmp_path):
    document = tmp_path / "requirements.md"
    document.write_text("# Objectives\n", encoding="utf-8")
    junit = tmp_path / "junit.xml"
    junit.write_text(
        '<testsuite><testcase name="bad"><failure>broken</failure></testcase></testsuite>',
        encoding="utf-8",
    )
    before_document = document.read_bytes()
    before_junit = junit.read_bytes()
    env = os.environ.copy()
    env.update({"PYTHONPATH": str(PROJECT_ROOT), "DEVSQUAD_LLM_BACKEND": "mock", "NO_COLOR": "1"})
    completed = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "cli.py"),
            "lifecycle",
            "test",
            "--task",
            "scan evidence",
            "--backend",
            "mock",
            "--format",
            "json",
            "--document",
            f"P1={document}",
            "--junit",
            f"P7={junit}",
            "--no-warmup",
            "--no-compression",
            "--no-memory",
            "--no-skillify",
        ],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["document_scans"][0]["parsed"] is True
    assert payload["lifecycle_findings"]
    assert payload["remediation_proposals"][0]["approval_required"] is True
    assert document.read_bytes() == before_document
    assert junit.read_bytes() == before_junit
