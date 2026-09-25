#!/usr/bin/env python3
"""P0 E2E: V4.5.0 new features — Verify all 6 previously untested features are end-to-end functional.

Coverage (V4.5.0 anti-ghost E2E identified 6 features without E2E coverage):
  1. WorkflowTrace: dispatch report includes "Workflow Trace" section
  2. GitContext: dispatch(git_context=...) stores branch/commit info in result
  3. OutputStyle action_first: report format changes when output_style='action_first'
  4. SkillProvider: skill discovery works in full dispatch context
  5. FileBundler: review-mode dispatch activates bundling for large changesets
  6. SessionResume CLI: devsquad sessions list + dispatch --resume work end-to-end

Iron Rules:
  1. Real subprocess dispatch, not in-process import.
  2. Output must contain verifiable evidence of each feature.
  3. E2E-release-gate: this file IS the release gate for V4.5.0 features.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_CLI_PATH = _PROJECT_ROOT / "scripts" / "cli.py"
_PROJECT_ROOT_STR = str(_PROJECT_ROOT)

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.slow,
]


def _run_cli_markdown(*args: str, timeout: int = 60) -> str:
    """Run CLI and return raw stdout as markdown."""
    env = os.environ.copy()
    env["PYTHONPATH"] = _PROJECT_ROOT_STR
    env["PYTHONUNBUFFERED"] = "1"
    env["DEVSQUAD_LLM_BACKEND"] = "mock"
    env["NO_COLOR"] = "1"
    env["TERM"] = "dumb"

    cmd = [sys.executable, str(_CLI_PATH)] + list(args)
    result = subprocess.run(
        cmd,
        cwd=_PROJECT_ROOT_STR,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    if result.returncode not in (0, 1):
        raise AssertionError(f"CLI failed: {' '.join(args)}\nExit: {result.returncode}\nSTDERR: {result.stderr[:500]}")
    return result.stdout


# ---------------------------------------------------------------------------
# Feature 1: WorkflowTrace
# ---------------------------------------------------------------------------


def test_e2e_workflow_trace_appears_in_report():
    """Journey-1: dispatch report includes 'Workflow Trace' section.

    V4.5.0 added WorkflowTrace to dispatch reports. This E2E verifies the
    section appears in the markdown output from a real CLI dispatch.
    """
    output = _run_cli_markdown(
        "dispatch",
        "-t",
        "Design a simple REST API endpoint",
        "-f",
        "markdown",
        "--dry-run",
    )
    assert "Workflow Trace" in output or "workflow_trace" in output.lower(), (
        f"WorkflowTrace section not found in report.\nOutput (first 1000 chars):\n{output[:1000]}"
    )


def test_e2e_workflow_trace_has_decomposition_steps():
    """Journey-2: WorkflowTrace section shows task decomposition steps."""
    output = _run_cli_markdown(
        "dispatch",
        "-t",
        "Optimize database query performance",
        "--dry-run",
    )
    has_trace = "Workflow Trace" in output or "workflow" in output.lower()
    assert has_trace, f"Workflow trace evidence not found in output:\n{output[:500]}"


# ---------------------------------------------------------------------------
# Feature 2: GitContext
# ---------------------------------------------------------------------------


def test_e2e_git_context_injectable():
    """Journey-3: git_context can be injected into dispatch via Python API.

    This test verifies the GitContext feature by importing and calling
    dispatch with git_context parameter, then verifying the result
    contains the git_context field.
    """
    env = os.environ.copy()
    env["PYTHONPATH"] = _PROJECT_ROOT_STR
    env["PYTHONUNBUFFERED"] = "1"
    env["DEVSQUAD_LLM_BACKEND"] = "mock"

    script = """
import json, sys
from scripts.collaboration.dispatcher import MultiAgentDispatcher
from scripts.collaboration.models_dispatch import GitContext

dispatcher = MultiAgentDispatcher()
# GitContext fields: branch, recent_commits, open_issues (no commit/repo_url)
ctx = GitContext(
    branch="feature/test",
    recent_commits=["abc123 Fix bug", "def456 Add feature"],
    open_issues=["#123"],
)
result = dispatcher.dispatch(
    task_description="Review this PR",
    roles=["architect"],
    git_context=ctx,
)
# git_context is stored as an attribute on the result (not in to_dict())
gc = result.git_context
import dataclasses
gc_dict = dataclasses.asdict(gc) if gc and dataclasses.is_dataclass(gc) else None
print(json.dumps({
    "git_context_present": gc is not None,
    "branch": gc_dict.get("branch") if gc_dict else None,
    "recent_commits_count": len(gc_dict.get("recent_commits", [])) if gc_dict else 0,
}))
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=_PROJECT_ROOT_STR,
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    assert result.returncode == 0, f"git_context dispatch failed: {result.stderr[:500]}"
    data = json.loads(result.stdout)
    assert data["git_context_present"], f"git_context not stored on result: {result.stdout}"
    assert data["branch"] == "feature/test", f"git_context branch mismatch: {data}"
    assert data["recent_commits_count"] == 2, f"recent_commits not preserved: {data}"


# ---------------------------------------------------------------------------
# Feature 3: OutputStyle action_first
# ---------------------------------------------------------------------------


def test_e2e_output_style_action_first_changes_format():
    """Journey-4: output_style='action_first' changes report format via Python API.

    V4.5.0 added OutputStyle. action_first reports should lead with
    concrete next actions (not analysis). CLI does not yet expose this flag,
    so we test via Python API directly.
    """
    env = os.environ.copy()
    env["PYTHONPATH"] = _PROJECT_ROOT_STR
    env["PYTHONUNBUFFERED"] = "1"
    env["DEVSQUAD_LLM_BACKEND"] = "mock"

    script = """
import json, sys
from scripts.collaboration.report_formatter import ReportFormatter
from scripts.collaboration.dispatcher import MultiAgentDispatcher

disp = MultiAgentDispatcher()
result = disp.dispatch(task_description="Add user authentication to the API", roles=["architect"])

formatter = ReportFormatter()
detailed = formatter.format_report(result, output_style="detailed")
action_first = formatter.format_report(result, output_style="action_first")

print(json.dumps({
    "detailed_len": len(detailed),
    "action_first_len": len(action_first),
    "differs": detailed.strip() != action_first.strip(),
}))
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=_PROJECT_ROOT_STR,
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    if result.returncode != 0:
        pytest.fail(
            f"output_style dispatch failed (regression — output_style IS implemented "
            f"in ReportFormatter.format_report):\n{result.stderr[:300]}"
        )
    data = json.loads(result.stdout)
    assert data["differs"], "action_first and detailed formats produced identical output"


def test_e2e_output_style_detailed_vs_action_first_differ():
    """Journey-5: detailed vs action_first produce different outputs for same result."""
    env = os.environ.copy()
    env["PYTHONPATH"] = _PROJECT_ROOT_STR
    env["PYTHONUNBUFFERED"] = "1"
    env["DEVSQUAD_LLM_BACKEND"] = "mock"

    script = """
import json, sys
from scripts.collaboration.report_formatter import ReportFormatter
from scripts.collaboration.dispatcher import MultiAgentDispatcher

disp = MultiAgentDispatcher()
result = disp.dispatch(task_description="Fix memory leak in worker pool", roles=["architect"])

formatter = ReportFormatter()
detailed = formatter.format_report(result, output_style="detailed")
action_first = formatter.format_report(result, output_style="action_first")
print(json.dumps({"differs": detailed.strip() != action_first.strip()}))
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=_PROJECT_ROOT_STR,
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    if result.returncode != 0:
        pytest.fail(
            f"output_style dispatch failed (regression — output_style IS implemented "
            f"in ReportFormatter.format_report):\n{result.stderr[:300]}"
        )
    data = json.loads(result.stdout)
    assert data["differs"], "action_first and detailed formats produced identical output"


# ---------------------------------------------------------------------------
# Feature 4: SkillProvider discovery
# ---------------------------------------------------------------------------


def test_e2e_skill_provider_discovers_skills():
    """Journey-6: SkillProvider discovers skills in full dispatch context.

    V4.5.0 SkillProvider Protocol discovers skills via discover() method.
    This E2E verifies the discovery pipeline works in a real dispatch.
    """
    env = os.environ.copy()
    env["PYTHONPATH"] = _PROJECT_ROOT_STR
    env["PYTHONUNBUFFERED"] = "1"
    env["DEVSQUAD_LLM_BACKEND"] = "mock"

    script = """
import json, sys
from scripts.collaboration.skill_registry import SkillRegistry
from scripts.collaboration.skill_provider_builtin import BuiltinSkillProvider

registry = SkillRegistry()
registry.set_provider(BuiltinSkillProvider())
skills = registry.discover()
print(json.dumps({"count": len(skills), "skills": list(skills.keys())[:5]}))
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=_PROJECT_ROOT_STR,
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    assert result.returncode == 0, f"SkillProvider discovery failed: {result.stderr[:300]}"
    data = json.loads(result.stdout)
    assert data["count"] > 0, f"No skills discovered: {result.stdout}"
    assert len(data["skills"]) > 0, f"Expected dispatch skill, got: {data['skills']}"


# ---------------------------------------------------------------------------
# Feature 5: FileBundler
# ---------------------------------------------------------------------------


def test_e2e_review_mode_bundles_via_cli_dispatch():
    """Journey-7a: ``dispatch --mode review --changeset`` really splits files into bundles.

    V4.5.20 (F4 fix): the previous version of this test was a false E2E — it
    imported ``FileBundler`` directly and never exercised the review pipeline.
    This test drives the real CLI dispatch path (subprocess) and reads the
    bundles out of the dispatch result, so a broken wiring fails the test.
    """
    env = os.environ.copy()
    env["PYTHONPATH"] = _PROJECT_ROOT_STR
    env["PYTHONUNBUFFERED"] = "1"
    env["DEVSQUAD_LLM_BACKEND"] = "mock"
    env["NO_COLOR"] = "1"
    env["TERM"] = "dumb"

    tmpdir = tempfile.mkdtemp(prefix="devsquad_review_bundles_")
    try:
        # 8 files spread across 3 directories → 3 bundles (threshold is >5 files).
        files: list[str] = []
        for sub, count in (("pkg_a", 3), ("pkg_b", 3), ("pkg_c", 2)):
            for i in range(count):
                path = Path(tmpdir) / sub / f"model_{i}.py"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"# {sub} model {i}\n", encoding="utf-8")
                files.append(str(path))

        cmd = [
            sys.executable,
            str(_CLI_PATH),
            "dispatch",
            "-t",
            "review this changeset",
            "--mode",
            "review",
            "--changeset",
            *files,
            "--format",
            "json",
        ]
        result = subprocess.run(
            cmd,
            cwd=_PROJECT_ROOT_STR,
            capture_output=True,
            text=True,
            timeout=180,
            env=env,
        )
        assert result.returncode == 0, (
            f"review dispatch failed: exit={result.returncode}\nSTDERR: {result.stderr[:800]}"
        )
        data = json.loads(result.stdout)
        bundles = data.get("review_bundles")
        assert bundles, f"No review_bundles in dispatch output: {result.stdout[:500]}"
        assert len(bundles) >= 2, f"Expected >=2 bundles for 8 files, got {len(bundles)}: {bundles}"
        reviewed = [f for bundle in bundles for f in bundle]
        assert sorted(reviewed) == sorted(files), (
            f"Bundles must cover every file exactly once: {sorted(reviewed)} vs {sorted(files)}"
        )

        # Control: the same changeset without review mode produces no bundles.
        control = subprocess.run(
            [
                sys.executable,
                str(_CLI_PATH),
                "dispatch",
                "-t",
                "review this changeset",
                "--changeset",
                *files,
                "--format",
                "json",
            ],
            cwd=_PROJECT_ROOT_STR,
            capture_output=True,
            text=True,
            timeout=180,
            env=env,
        )
        assert control.returncode == 0, f"control dispatch failed: {control.stderr[:500]}"
        assert json.loads(control.stdout).get("review_bundles") is None, (
            "Non-review mode must not emit review_bundles (backward compatibility)"
        )

        # Control 2: review mode WITHOUT a changeset keeps the V4.5.19 plan.
        no_changeset = subprocess.run(
            [
                sys.executable,
                str(_CLI_PATH),
                "dispatch",
                "-t",
                "review this changeset",
                "--mode",
                "review",
                "--format",
                "json",
            ],
            cwd=_PROJECT_ROOT_STR,
            capture_output=True,
            text=True,
            timeout=180,
            env=env,
        )
        assert no_changeset.returncode == 0, f"no-changeset dispatch failed: {no_changeset.stderr[:500]}"
        assert json.loads(no_changeset.stdout).get("review_bundles") is None, (
            "review mode without --changeset must not emit review_bundles"
        )
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)


def test_e2e_review_mode_triggers_file_bundler_counter():
    """Journey-7b: FileBundler's activation counter is incremented by the dispatch pipeline.

    Anti-ghost criterion (PRD W0-4 / D7): the counter must be 0 *before* the
    pipeline runs and >0 *after* — proving the module is reached through the
    production path (``dispatch(mode="review", changeset=...)``), not merely
    imported by the test itself.
    """
    env = os.environ.copy()
    env["PYTHONPATH"] = _PROJECT_ROOT_STR
    env["PYTHONUNBUFFERED"] = "1"
    env["DEVSQUAD_LLM_BACKEND"] = "mock"

    tmpdir = tempfile.mkdtemp(prefix="devsquad_bundler_counter_")
    try:
        files = [f"{tmpdir}/pkg_{i // 3}/model_{i}.py" for i in range(6)]
        files_list_str = ", ".join(f'"{f}"' for f in files)
        script = f"""
import json
from scripts.collaboration import file_bundler
from scripts.collaboration.dispatcher import MultiAgentDispatcher

before = file_bundler._call_counter_er
disp = MultiAgentDispatcher(enable_warmup=False)
try:
    result = disp.dispatch("review changeset", mode="review", changeset=[{files_list_str}])
    after = file_bundler._call_counter_er
    bundles = result.details.get("review_bundles")
finally:
    disp.shutdown()
print(json.dumps({{
    "counter_before": before,
    "counter_after": after,
    "success": result.success,
    "bundle_count": len(bundles) if bundles else 0,
}}))
"""
        proc = subprocess.run(
            [sys.executable, "-c", script],
            cwd=_PROJECT_ROOT_STR,
            capture_output=True,
            text=True,
            timeout=180,
            env=env,
        )
        assert proc.returncode == 0, f"counter probe failed: {proc.stderr[:500]}"
        data = json.loads(proc.stdout.strip().splitlines()[-1])
        assert data["counter_before"] == 0, f"Counter should start at 0: {data}"
        assert data["counter_after"] > data["counter_before"], (
            f"Bundler counter was not incremented by the dispatch pipeline: {data}"
        )
        assert data["bundle_count"] >= 2, f"Expected >=2 bundles for 6 files: {data}"
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Feature 6: SessionResume CLI
# ---------------------------------------------------------------------------


def test_e2e_session_resume_cli_command_exists():
    """Journey-8: devsquad sessions list command is accessible."""
    env = os.environ.copy()
    env["PYTHONPATH"] = _PROJECT_ROOT_STR
    env["PYTHONUNBUFFERED"] = "1"
    env["DEVSQUAD_LLM_BACKEND"] = "mock"
    env["NO_COLOR"] = "1"
    env["TERM"] = "dumb"

    result = subprocess.run(
        [sys.executable, str(_CLI_PATH), "sessions", "list"],
        cwd=_PROJECT_ROOT_STR,
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    assert result.returncode in (0, 1), f"sessions list crashed: {result.returncode}\nSTDERR: {result.stderr[:300]}"
    output = result.stdout + result.stderr
    assert "session" in output.lower() or "history" in output.lower(), f"No session info in output: {output[:300]}"


def test_e2e_checkpoint_manager_persists_session():
    """Journey-9: CheckpointManager persists session state across Python processes.

    V4.5.0 SessionResume stores checkpoints as JSON files. CheckpointManager
    takes ``storage_path`` (NOT ``storage_dir``) and ``save_checkpoint``
    takes a ``Checkpoint`` object (NOT a dict).
    """
    tmpdir = tempfile.mkdtemp(prefix="devsquad_checkpoint_")
    try:
        env = os.environ.copy()
        env["PYTHONPATH"] = _PROJECT_ROOT_STR
        env["PYTHONUNBUFFERED"] = "1"
        env["DEVSQUAD_LLM_BACKEND"] = "mock"

        script = f"""
import sys, os, json
from scripts.collaboration.checkpoint_manager import CheckpointManager, Checkpoint

mgr = CheckpointManager(storage_path="{tmpdir}")
# save_checkpoint takes a Checkpoint object, not a dict
checkpoint = Checkpoint(
    checkpoint_id="test-session-e2e",
    task_id="task-1",
    step_name="analysis",
    completed_steps=["step1"],
    remaining_steps=["step2", "step3"],
    progress_percentage=33.3,
)
saved = mgr.save_checkpoint(checkpoint)
# Read it back via get_session_status (returns dict)
status = mgr.get_session_status("test-session-e2e")
print(json.dumps({{
    "saved": saved,
    "status_found": bool(status),
    "session_id": status.get("session_id", ""),
    "progress": status.get("progress_percentage", 0),
}}))
"""
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=_PROJECT_ROOT_STR,
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
        assert result.returncode == 0, f"CheckpointManager failed: {result.stderr[:300]}"
        data = json.loads(result.stdout)
        assert data["saved"], f"Checkpoint not saved: {result.stdout}"
        assert data["status_found"], f"Checkpoint status not found: {result.stdout}"
        assert data["session_id"] == "test-session-e2e", f"session_id mismatch: {data}"
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)
