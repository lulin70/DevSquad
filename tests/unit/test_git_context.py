"""Unit tests for GitContext (V4.4.4).

7 tests covering the 7-dimension Iron Rules:
1. test_auto_detect — Happy (in git repo → branch detected)
2. test_non_git_dir — Error (non-git → returns None)
3. test_timeout — Error (slow git → timeout → None)
4. test_prompt_injection — Integration (Coordinator prompt has Git Context)
5. test_scratchpad_entry — Side-Effect (DECISION entry created)
6. test_backward_compat — Config (git_context=None → no change)
7. test_call_counter — Anti-Ghost (_call_counter increments)

Uses REAL components (MultiAgentDispatcher with default mock backend)
for dispatch-level tests. The timeout test uses unittest.mock.patch on
subprocess.run — the only sanctioned mock usage, since reliably making
``git`` slow is not feasible in CI.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from unittest import mock

import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import scripts.collaboration.models_dispatch as models_dispatch_module  # noqa: E402
from scripts.collaboration.dispatcher import MultiAgentDispatcher  # noqa: E402
from scripts.collaboration.models import EntryType, GitContext  # noqa: E402

pytestmark = [pytest.mark.unit]


@pytest.fixture
def dispatcher() -> MultiAgentDispatcher:
    """Create a real MultiAgentDispatcher with default mock backend."""
    return MultiAgentDispatcher()


# ---------------------------------------------------------------------------
# Test 1: auto_detect (Happy — in git repo → branch detected)
# ---------------------------------------------------------------------------


def test_auto_detect() -> None:
    """Happy: GitContext.auto_detect in a git repo returns a populated context."""
    # The DevSquad project root is a git repo. auto_detect uses the cwd,
    # so we ensure we're in the project root.
    original_cwd = os.getcwd()
    try:
        os.chdir(_PROJECT_ROOT)
        ctx = GitContext.auto_detect(timeout=2.0)
    finally:
        os.chdir(original_cwd)

    if ctx is None:
        pytest.skip("git not available or not a git repo in CI — skipping Happy test")
    assert ctx.branch, f"branch must be non-empty, got {ctx.branch!r}"
    # recent_commits may be empty if the repo has no commits, but the
    # DevSquad repo has commits, so we expect ≥1.
    assert len(ctx.recent_commits) >= 1, (
        f"expected ≥1 recent commit, got {ctx.recent_commits}"
    )


# ---------------------------------------------------------------------------
# Test 2: non-git dir (Error — returns None)
# ---------------------------------------------------------------------------


def test_non_git_dir() -> None:
    """Error: GitContext.auto_detect in a non-git directory returns None."""
    with tempfile.TemporaryDirectory() as tmp:
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp)
            ctx = GitContext.auto_detect(timeout=2.0)
        finally:
            os.chdir(original_cwd)
    assert ctx is None, f"auto_detect in non-git dir must return None, got {ctx}"


# ---------------------------------------------------------------------------
# Test 3: timeout (Error — slow git → timeout → None)
# ---------------------------------------------------------------------------


def test_timeout() -> None:
    """Error: subprocess timeout → GitContext.auto_detect returns None."""
    # Mock subprocess.run to raise TimeoutExpired, simulating a slow git.
    # This is the only sanctioned mock usage — reliably making ``git``
    # slow is not feasible in CI.
    with mock.patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="git", timeout=0.001)):
        ctx = GitContext.auto_detect(timeout=0.001)
    assert ctx is None, "timeout must result in None, not an exception"


# ---------------------------------------------------------------------------
# Test 4: prompt injection (Integration — Coordinator prompt has Git Context)
# ---------------------------------------------------------------------------


def test_prompt_injection(dispatcher: MultiAgentDispatcher) -> None:
    """Integration: dispatch with git_context → DECISION entry contains branch.

    The GitContext.to_prompt_section() is appended to the task description
    passed to the Coordinator. The side-effect is a DECISION Scratchpad
    entry whose content includes the branch name.
    """
    ctx = GitContext(
        branch="feature/test-branch",
        recent_commits=["abc1234 test commit"],
        open_issues=["#42"],
    )
    # Verify the prompt section itself contains the branch.
    section = ctx.to_prompt_section()
    assert "## Git Context" in section
    assert "feature/test-branch" in section
    assert "abc1234 test commit" in section
    assert "#42" in section

    # Dispatch with the git_context and verify the DECISION entry was
    # written to the scratchpad (proving the injection path ran).
    dispatcher.dispatch("Design a feature", git_context=ctx)
    decisions = dispatcher.scratchpad.read(entry_type=EntryType.DECISION)
    git_decisions = [d for d in decisions if "Git Context" in d.content]
    assert len(git_decisions) >= 1, "expected ≥1 Git Context DECISION entry"
    assert "feature/test-branch" in git_decisions[0].content, (
        "DECISION entry must mention the branch name"
    )


# ---------------------------------------------------------------------------
# Test 5: scratchpad entry (Side-Effect — DECISION entry created)
# ---------------------------------------------------------------------------


def test_scratchpad_entry(dispatcher: MultiAgentDispatcher) -> None:
    """Side-Effect: dispatch with git_context writes a DECISION entry to Scratchpad."""
    ctx = GitContext(
        branch="bugfix/issue-99",
        recent_commits=["def5678 fix bug"],
        open_issues=["#99"],
    )
    decisions_before = dispatcher.scratchpad.read(entry_type=EntryType.DECISION)
    count_before = len(decisions_before)

    dispatcher.dispatch("Fix a bug", git_context=ctx)

    decisions_after = dispatcher.scratchpad.read(entry_type=EntryType.DECISION)
    assert len(decisions_after) > count_before, "new DECISION entry must be created"

    # Find the git-context entry and verify its tags + content.
    git_entries = [d for d in decisions_after if "git-context" in d.tags]
    assert len(git_entries) >= 1, "DECISION entry must be tagged 'git-context'"
    entry = git_entries[-1]
    assert "Git Context" in entry.content
    assert "bugfix/issue-99" in entry.content
    assert entry.role_id == "coordinator", (
        f"DECISION entry role_id must be 'coordinator', got {entry.role_id}"
    )


# ---------------------------------------------------------------------------
# Test 6: backward compat (Config — git_context=None → no change)
# ---------------------------------------------------------------------------


def test_backward_compat(dispatcher: MultiAgentDispatcher) -> None:
    """Config: git_context=None preserves existing behavior (no DECISION entry)."""
    result = dispatcher.dispatch("Design a feature", git_context=None)
    # No git-context DECISION entry should exist.
    decisions = dispatcher.scratchpad.read(entry_type=EntryType.DECISION)
    git_decisions = [d for d in decisions if "git-context" in d.tags]
    assert len(git_decisions) == 0, (
        "git_context=None must not write any git-context DECISION entry"
    )
    # The result task_description should not contain the Git Context section.
    assert "## Git Context" not in result.task_description, (
        "task_description must not contain Git Context when git_context=None"
    )
    # The dispatch should still succeed (backward compat).
    assert result.success, "dispatch without git_context should succeed"


# ---------------------------------------------------------------------------
# Test 7: call_counter (Anti-Ghost)
# ---------------------------------------------------------------------------


def test_call_counter() -> None:
    """Anti-Ghost: module-level _call_counter increments on GitContext construction."""
    before = models_dispatch_module._call_counter
    # Construct a GitContext — should bump the counter.
    GitContext(branch="test-branch")
    after = models_dispatch_module._call_counter
    assert after > before, (
        f"_call_counter did not increment: before={before}, after={after}"
    )
