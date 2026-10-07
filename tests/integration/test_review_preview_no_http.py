"""Integration proof that review preview makes zero LLM calls (W1-4, contract C11).

The traps are placed at the transport and constructor layers — deeper than the
backend interface — because a preview that merely "returns early" could still
have initialized a backend or opened a connection as a side effect.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from scripts.cli_dispatch import cmd_dispatch
from scripts.cli_lifecycle import cmd_lifecycle

_CLI = Path(__file__).resolve().parents[2] / "scripts" / "cli.py"


def _load_cli_main():
    # scripts/cli/ package shadows scripts/cli.py; import the file directly.
    spec = importlib.util.spec_from_file_location("scripts_cli_module", _CLI)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.main


def _make_repo(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "keep.py").write_text("print('keep')\n", encoding="utf-8")
    (tmp_path / "src" / "two.py").write_text("print('two')\n", encoding="utf-8")
    (tmp_path / ".env").write_text("TOKEN=secret\n", encoding="utf-8")
    return tmp_path


@pytest.fixture()
def zero_llm_traps(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Trap every layer a real review would touch: transport, SDK, dispatcher."""
    violations: list[str] = []

    def _trap_transport(layer: str):
        def _raise(*args: object, **kwargs: object) -> None:
            violations.append(f"HTTP transport used: {layer}")

        return _raise

    def _trap_init(name: str):
        def _raise(self: object, *args: object, **kwargs: object) -> None:
            violations.append(f"constructor reached: {name}")

        return _raise

    try:
        import httpx

        monkeypatch.setattr(httpx.Client, "send", _trap_transport("httpx.Client.send"))
        monkeypatch.setattr(httpx.AsyncClient, "send", _trap_transport("httpx.AsyncClient.send"))
    except ImportError:  # pragma: no cover - httpx is a dependency of the SDKs
        pass

    try:
        import openai

        monkeypatch.setattr(openai.OpenAI, "__init__", _trap_init("openai.OpenAI"))
    except ImportError:  # pragma: no cover
        pass

    try:
        import anthropic

        monkeypatch.setattr(anthropic.Anthropic, "__init__", _trap_init("anthropic.Anthropic"))
    except ImportError:  # pragma: no cover
        pass

    from scripts.collaboration.dispatcher import MultiAgentDispatcher

    monkeypatch.setattr(MultiAgentDispatcher, "__init__", _trap_init("MultiAgentDispatcher"))
    return violations


def _preview_argv(repo: Path, entry: str) -> list[str]:
    base = [
        sys.executable,
        str(_CLI),
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
    return base[2:]


def test_dispatch_preview_never_touches_transport_or_dispatcher(
    tmp_path: Path,
    zero_llm_traps: list[str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = _make_repo(tmp_path)
    argv = _preview_argv(repo, "dispatch")
    monkeypatch.setattr(sys, "argv", ["cli.py", *argv])

    exit_code = _load_cli_main()()

    assert exit_code == 0
    assert zero_llm_traps == [], f"preview touched LLM layers: {zero_llm_traps}"
    assert '"preview": true' in capsys.readouterr().out


def test_lifecycle_review_preview_never_touches_transport_or_dispatcher(
    tmp_path: Path,
    zero_llm_traps: list[str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = _make_repo(tmp_path)
    argv = _preview_argv(repo, "review")
    monkeypatch.setattr(sys, "argv", ["cli.py", *argv])

    exit_code = _load_cli_main()()

    assert exit_code == 0
    assert zero_llm_traps == [], f"preview touched LLM layers: {zero_llm_traps}"
    assert '"preview": true' in capsys.readouterr().out


def test_preview_with_async_flag_still_avoids_async_dispatch(
    tmp_path: Path,
    zero_llm_traps: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _make_repo(tmp_path)
    argv = _preview_argv(repo, "dispatch") + ["--async"]
    monkeypatch.setattr(sys, "argv", ["cli.py", *argv])

    assert _load_cli_main()() == 0
    assert zero_llm_traps == []


def test_cmd_dispatch_guard_rejects_non_review_mode(
    tmp_path: Path, zero_llm_traps: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    import argparse

    repo = _make_repo(tmp_path)
    args = argparse.Namespace(
        task="review these files",
        task_positional=None,
        roles=None,
        mode="auto",
        preview=True,
        verbose=False,
        quick=False,
        host=None,
        changeset=["src/keep.py"],
        include=(),
        exclude=(),
        max_file_size=10 * 1024 * 1024,
        repo_root=str(repo),
        rule=None,
        deleted=(),
        format="json",
    )

    assert cmd_dispatch(args) == 1
    assert "--preview requires --mode review" in capsys.readouterr().err
    assert zero_llm_traps == []


def test_cmd_lifecycle_guard_requires_changeset(
    tmp_path: Path, zero_llm_traps: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    import argparse

    repo = _make_repo(tmp_path)
    args = argparse.Namespace(
        lifecycle_command="review",
        task="review these files",
        task_positional=None,
        preview=True,
        verbose=False,
        changeset=None,
        include=(),
        exclude=(),
        max_file_size=10 * 1024 * 1024,
        repo_root=str(repo),
        rule=None,
        deleted=(),
        format="json",
    )

    assert cmd_lifecycle(args) == 1
    assert "--preview requires --changeset" in capsys.readouterr().err
    assert zero_llm_traps == []
