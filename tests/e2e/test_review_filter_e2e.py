from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_CLI = _PROJECT_ROOT / "scripts" / "cli.py"

pytestmark = [pytest.mark.e2e, pytest.mark.slow]


def test_cli_review_filter_controls_real_user_path(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "keep.py").write_text("print('keep')\n", encoding="utf-8")
    (repo / "src" / "drop.py").write_text("print('drop')\n", encoding="utf-8")
    (repo / ".env").write_text("TOKEN=secret\n", encoding="utf-8")

    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": str(_PROJECT_ROOT),
            "PYTHONUNBUFFERED": "1",
            "DEVSQUAD_LLM_BACKEND": "mock",
            "NO_COLOR": "1",
            "TERM": "dumb",
        }
    )
    command = [
        sys.executable,
        str(_CLI),
        "dispatch",
        "-t",
        "review these files",
        "--mode",
        "review",
        "--changeset",
        "src/keep.py",
        "src/drop.py",
        ".env",
        "--repo-root",
        str(repo),
        "--exclude",
        "src/drop.py",
        "--include",
        ".env",
        "--format",
        "json",
    ]
    completed = subprocess.run(
        command,
        cwd=_PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )

    assert completed.returncode == 0, completed.stderr[:1000]
    output = json.loads(completed.stdout)
    review_filter = output["review_filter"]
    assert review_filter["retained_paths"] == ["src/keep.py"]
    assert output["review_bundles"] == [["src/keep.py"]]
    assert any(item["gate"] == "user_exclude" for item in review_filter["excluded_paths"])
    assert any(item["gate"] == "secret_exclude" for item in review_filter["excluded_paths"])
    assert ".env" not in output["report"]
    assert "secret_exclude" in output["report"]
    assert "sensitive path excluded before user configuration" in output["report"]
