"""Subprocess E2E for the deterministic review preview (W1-4, C11-C13).

The zero-HTTP proof here is the strongest available in a subprocess: the CLI is
launched with ``--backend openai`` pointing at a closed port with a fake key.
A real dispatch would attempt the connection and exit non-zero (no mock
fallback is allowed for an explicit backend); preview must exit 0.
"""

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


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "keep.py").write_text("print('keep')\n", encoding="utf-8")
    (repo / "src" / "two.py").write_text("print('two')\n", encoding="utf-8")
    (repo / ".env").write_text("TOKEN=secret\n", encoding="utf-8")
    return repo


def _run_cli(command: list[str], env_overrides: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": str(_PROJECT_ROOT),
            "PYTHONUNBUFFERED": "1",
            "NO_COLOR": "1",
            "TERM": "dumb",
        }
    )
    env.update(env_overrides or {})
    return subprocess.run(
        [sys.executable, str(_CLI), *command],
        cwd=_PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _preview_command(repo: Path, entry: str = "dispatch") -> list[str]:
    base = [
        entry,
        "-t",
        "review these files",
        "--changeset",
        "src/keep.py",
        "src/two.py",
        ".env",
        "--repo-root",
        str(repo),
        "--format",
        "json",
    ]
    if entry == "dispatch":
        base.extend(["--mode", "review", "--preview"])
    else:
        base.append("--preview")
    return base


def test_preview_json_summary_is_default(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)

    completed = _run_cli(_preview_command(repo, "dispatch") + ["--backend", "mock"])

    assert completed.returncode == 0, completed.stderr[:1000]
    output = json.loads(completed.stdout)
    assert output["preview"] is True
    assert output["candidate_count"] == 3
    assert output["retained_count"] == 2
    assert output["gate_counts"]["secret_exclude"] == 1
    assert output["bundle_count"] == 1
    assert "review_filter" not in output


def test_preview_verbose_contains_path_details(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)

    completed = _run_cli(_preview_command(repo, "dispatch") + ["--verbose"])

    assert completed.returncode == 0, completed.stderr[:1000]
    output = json.loads(completed.stdout)
    assert output["review_filter"]["retained_paths"] == ["src/keep.py", "src/two.py"]
    assert output["bundles"][0]["files"] == ["src/keep.py", "src/two.py"]


def test_preview_redacts_secret_paths(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)

    completed = _run_cli(_preview_command(repo, "dispatch") + ["--verbose"])

    assert completed.returncode == 0, completed.stderr[:1000]
    assert ".env" not in completed.stdout
    assert "[REDACTED sensitive path]" in completed.stdout


def test_preview_does_not_call_http(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    # Dead port + fake key: any real dispatch attempt fails closed; preview
    # never builds the backend, so it must exit 0 with a preview payload.
    env = {
        "DEVSQUAD_LLM_BACKEND": "openai",
        "OPENAI_API_KEY": "sk-e2e-fake-key-not-real",
        "OPENAI_BASE_URL": "http://127.0.0.1:9/v1",
        "OPENAI_MODEL": "gpt-4",
    }

    completed = _run_cli(_preview_command(repo, "dispatch"), env)

    assert completed.returncode == 0, completed.stderr[:1000]
    output = json.loads(completed.stdout)
    assert output["preview"] is True
    assert output["retained_count"] == 2


def test_preview_async_flag_does_not_enter_async_dispatch(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    env = {
        "DEVSQUAD_LLM_BACKEND": "openai",
        "OPENAI_API_KEY": "sk-e2e-fake-key-not-real",
        "OPENAI_BASE_URL": "http://127.0.0.1:9/v1",
    }

    completed = _run_cli(_preview_command(repo, "dispatch") + ["--async"], env)

    assert completed.returncode == 0, completed.stderr[:1000]
    assert json.loads(completed.stdout)["preview"] is True


def _write_diff(repo: Path) -> Path:
    diff_file = repo.parent / "changes.diff"
    diff_file.write_text(
        """diff --git a/src/keep.py b/src/keep.py
--- a/src/keep.py
+++ b/src/keep.py
@@ -1 +1 @@
-print('keep')
+print('updated')
""",
        encoding="utf-8",
    )
    return diff_file


def test_dispatch_preview_accepts_diff_file(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    diff_file = _write_diff(repo)

    completed = _run_cli(
        [
            "dispatch",
            "-t",
            "review diff",
            "--mode",
            "review",
            "--preview",
            "--diff-file",
            str(diff_file),
            "--repo-root",
            str(repo),
            "--format",
            "json",
        ]
    )

    assert completed.returncode == 0, completed.stderr[:1000]
    output = json.loads(completed.stdout)
    assert output["candidate_count"] == 1
    assert output["retained_count"] == 1
    assert "diff --git" not in completed.stdout


def test_lifecycle_review_entry_supports_diff_file_preview(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    diff_file = _write_diff(repo)

    completed = _run_cli(
        [
            "review",
            "-t",
            "review diff",
            "--preview",
            "--diff-file",
            str(diff_file),
            "--repo-root",
            str(repo),
            "--format",
            "json",
        ]
    )

    assert completed.returncode == 0, completed.stderr[:1000]
    assert json.loads(completed.stdout)["candidate_count"] == 1


def test_malformed_diff_file_fails_closed(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    diff_file = repo.parent / "malformed.diff"
    diff_file.write_text("diff --git a/only-one-path\n", encoding="utf-8")

    completed = _run_cli(
        [
            "dispatch",
            "-t",
            "review diff",
            "--mode",
            "review",
            "--preview",
            "--diff-file",
            str(diff_file),
            "--repo-root",
            str(repo),
        ]
    )

    assert completed.returncode == 1
    assert "malformed diff header" in completed.stderr
    assert "Traceback" not in completed.stderr


def test_diff_file_and_changeset_are_mutually_exclusive(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    diff_file = _write_diff(repo)
    completed = _run_cli(
        [
            "dispatch",
            "-t",
            "review diff",
            "--mode",
            "review",
            "--preview",
            "--changeset",
            "src/keep.py",
            "--diff-file",
            str(diff_file),
            "--repo-root",
            str(repo),
        ]
    )

    assert completed.returncode == 1
    assert "mutually exclusive" in completed.stderr


def test_lifecycle_review_entry_supports_preview(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)

    completed = _run_cli(_preview_command(repo, "review") + ["--verbose"])

    assert completed.returncode == 0, completed.stderr[:1000]
    output = json.loads(completed.stdout)
    assert output["preview"] is True
    assert output["review_filter"]["retained_paths"] == ["src/keep.py", "src/two.py"]


def test_preview_requires_review_mode(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    command = [
        "dispatch",
        "-t",
        "review these files",
        "--preview",
        "--changeset",
        "src/keep.py",
        "--repo-root",
        str(repo),
    ]

    completed = _run_cli(command)

    assert completed.returncode == 1
    assert "--preview requires --mode review" in completed.stderr


def test_preview_rejects_quick(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    command = [
        "dispatch",
        "-t",
        "review these files",
        "--mode",
        "review",
        "--preview",
        "--quick",
        "--changeset",
        "src/keep.py",
        "--repo-root",
        str(repo),
    ]

    completed = _run_cli(command)

    assert completed.returncode == 1
    assert "incompatible with --quick" in completed.stderr


def test_preview_requires_changeset(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    command = [
        "dispatch",
        "-t",
        "review these files",
        "--mode",
        "review",
        "--preview",
        "--repo-root",
        str(repo),
    ]

    completed = _run_cli(command)

    assert completed.returncode == 1
    assert "--preview requires --changeset" in completed.stderr
