"""Integration tests for V4.5.8 Wave 2 cross-process CLI persistence.

Each test spawns a real subprocess running ``python3 -m scripts.cli_risks``
(or imports the CLI in a child process) to guarantee the V4.5.7
"in-memory dict only" bug does not regress.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _python() -> str:
    return sys.executable


def _clean_store(root: Path) -> None:
    if root.exists():
        shutil.rmtree(root)


@pytest.fixture
def isolated_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Each test uses its own `.devsquad_data/risks/` directory."""
    root = tmp_path / ".devsquad_data" / "risks"
    root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("PYTHONPATH", str(PROJECT_ROOT))
    monkeypatch.chdir(tmp_path)
    return root


def _run_cli(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    return subprocess.run(
        [_python(), "-m", "scripts.cli_risks", *args],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


pytestmark = pytest.mark.integration


class TestCrossProcessPersistence:
    def test_add_in_subprocess_visible_to_list_in_other(self, isolated_store: Path) -> None:
        cwd = isolated_store.parent.parent
        _clean_store(isolated_store)
        add_proc = _run_cli(
            [
                "risks", "add", "cross-process risk",
                "--probability", "0.5", "--impact", "0.6",
                "--category", "security", "--owner", "architect",
            ],
            cwd,
        )
        assert add_proc.returncode == 0, add_proc.stderr

        list_proc = _run_cli(["risks", "list", "--format", "json"], cwd)
        assert list_proc.returncode == 0, list_proc.stderr
        payload = json.loads(list_proc.stdout)
        assert len(payload) == 1
        assert payload[0]["description"] == "cross-process risk"

    def test_show_in_subprocess_after_remote_add(self, isolated_store: Path) -> None:
        cwd = isolated_store.parent.parent
        _clean_store(isolated_store)
        add_proc = _run_cli(
            [
                "risks", "add", "show-after-add",
                "--probability", "0.3", "--impact", "0.4",
                "--category", "technical", "--owner", "devops",
            ],
            cwd,
        )
        rid = json.loads(add_proc.stdout)["id"]

        show_proc = _run_cli(["risks", "show", rid], cwd)
        assert show_proc.returncode == 0, show_proc.stderr
        assert "show-after-add" in show_proc.stdout

    def test_assess_mitigate_close_visible_across_processes(self, isolated_store: Path) -> None:
        cwd = isolated_store.parent.parent
        _clean_store(isolated_store)

        add_proc = _run_cli(
            [
                "risks", "add", "lifecycle",
                "--probability", "0.4", "--impact", "0.5",
                "--category", "general", "--owner", "architect",
            ],
            cwd,
        )
        assert add_proc.returncode == 0, add_proc.stderr
        rid = json.loads(add_proc.stdout)["id"]

        assess_proc = _run_cli(
            [
                "risks", "assess", rid,
                "--votes", '{"architect":[0.7,0.8],"security":[0.6,0.7]}',
            ],
            cwd,
        )
        assert assess_proc.returncode == 0, assess_proc.stderr

        mitigate_proc = _run_cli(
            [
                "risks", "mitigate", rid,
                "--strategy", "mitigate", "--owner", "devops", "--plan", "add backup",
            ],
            cwd,
        )
        assert mitigate_proc.returncode == 0, mitigate_proc.stderr

        # Approval unavailable → fail-closed → must NOT change state.
        close_denied = _run_cli(["risks", "close", rid, "--require-approval"], cwd)
        assert close_denied.returncode == 2, close_denied.stderr
        assert "approval unavailable" in close_denied.stderr

        # Inspect state from a separate process: must still be MITIGATING.
        list_proc = _run_cli(["risks", "list", "--format", "json"], cwd)
        payload = json.loads(list_proc.stdout)
        assert payload[0]["status"] == "mitigating"

        # Clear after approval gate succeeds (callback provided through env).
        env_proc = subprocess.run(
            [
                _python(), "-c",
                (
                    f"import os, sys; sys.path.insert(0, {str(PROJECT_ROOT)!r}); os.chdir({str(cwd)!r}); "
                    "from scripts.cli_risks import main; "
                    f"sys.exit(main(['risks','close',{rid!r},'--require-approval','--register-id','default']))"
                ),
            ],
            cwd=cwd,
            env=os.environ.copy(),
            text=True,
            capture_output=True,
            check=False,
        )
        # Without approval_callback the close still fails closed.
        assert env_proc.returncode == 2


class TestApprovalFailClosed:
    def test_close_with_approval_unavailable_exits_2(self, isolated_store: Path) -> None:
        cwd = isolated_store.parent.parent
        _clean_store(isolated_store)
        add_proc = _run_cli(
            [
                "risks", "add", "close-gated",
                "--probability", "0.4", "--impact", "0.5",
                "--category", "general", "--owner", "architect",
            ],
            cwd,
        )
        rid = json.loads(add_proc.stdout)["id"]
        close_proc = _run_cli(["risks", "close", rid, "--require-approval"], cwd)
        assert close_proc.returncode == 2
        assert "approval unavailable" in close_proc.stderr
        list_proc = _run_cli(["risks", "list", "--format", "json"], cwd)
        payload = json.loads(list_proc.stdout)
        assert payload[0]["status"] == "open"

    def test_clear_with_approval_unavailable_does_not_clear(self, isolated_store: Path) -> None:
        cwd = isolated_store.parent.parent
        _clean_store(isolated_store)
        _run_cli(
            [
                "risks", "add", "keep-me",
                "--probability", "0.4", "--impact", "0.5",
                "--category", "general", "--owner", "architect",
            ],
            cwd,
        )
        clear_proc = _run_cli(["risks", "clear", "--require-approval"], cwd)
        assert clear_proc.returncode == 2
        assert "approval unavailable" in clear_proc.stderr
        list_proc = _run_cli(["risks", "list", "--format", "json"], cwd)
        assert len(json.loads(list_proc.stdout)) == 1


class TestCorruptStoreErrorCode:
    def test_corrupt_json_returns_exit_3(self, isolated_store: Path) -> None:
        cwd = isolated_store.parent.parent
        _clean_store(isolated_store)
        # Seed valid state.
        _run_cli(
            [
                "risks", "add", "seed",
                "--probability", "0.4", "--impact", "0.5",
                "--category", "general", "--owner", "architect",
            ],
            cwd,
        )
        # Corrupt the JSON.
        canonical = cwd / ".devsquad_data" / "risks" / "default.json"
        canonical.write_text("{not-json", encoding="utf-8")
        list_proc = _run_cli(["risks", "list"], cwd)
        assert list_proc.returncode == 3
        assert "ERROR" in list_proc.stderr

    def test_bad_arguments_do_not_emit_traceback(self, isolated_store: Path) -> None:
        cwd = isolated_store.parent.parent
        _clean_store(isolated_store)
        proc = _run_cli(["risks", "add"], cwd)  # missing required args
        assert proc.returncode == 2
        assert "Traceback" not in proc.stderr

