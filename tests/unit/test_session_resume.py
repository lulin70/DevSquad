#!/usr/bin/env python3
"""Unit tests for V4.5.0 SessionResume CLI (PRD §10.1.2).

Iron Rules applied:
  1. Documentation-first: source files read first —
     - scripts/collaboration/checkpoint_manager.py (list_sessions /
       get_session_status / _map_session_status / _build_task_summary /
       _redact_for_display / module-level _call_counter)
     - scripts/cli_sessions.py (cmd_sessions / load_resumable_task)
     - scripts/collaboration/output_validator.py (redact() — Security A6)
  2. Failure-means-report: REAL CheckpointManager + temp dir on disk, no Mock.
  3. Dimension-completeness: 6 tests (happy / status / detail / error /
     security / anti-ghost).
  4. Side-effect-verification: sensitive-data redaction + _call_counter.
  5. User-journey-first: list → show → resume mirrors the CLI user journey.
  6. e2e-release-gate: covered by the broader V4.5.0 e2e suite.

Anti-ghost note: ``_call_counter`` is a module-level int on
``checkpoint_manager``. We read it via module attribute access
(``cm_module._call_counter``), NOT ``from module import _call_counter``
(which would snapshot a stale int).
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scripts.cli_sessions import load_resumable_task  # noqa: E402
from scripts.collaboration import checkpoint_manager as cm_module  # noqa: E402
from scripts.collaboration.checkpoint_manager import (  # noqa: E402
    Checkpoint,
    CheckpointManager,
    CheckpointStatus,
)

# A realistic OpenAI-style key that OutputValidator recognizes (sk- + >=32 alnum).
# OutputValidator's pattern is ``sk-[A-Za-z0-9]{32,}`` — shorter keys won't fire.
_SENSITIVE_API_KEY = "sk-" + "a" * 40


class TestSessionResume(unittest.TestCase):
    """V4.5.0 SessionResume unit tests (6 tests)."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.mkdtemp(prefix="devsquad_sess_")
        self._manager = CheckpointManager(storage_path=self._tmpdir)

    def tearDown(self) -> None:
        import shutil

        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _make_checkpoint(
        self,
        *,
        checkpoint_id: str = "cp-test-001",
        task_id: str = "task-001",
        status: CheckpointStatus = CheckpointStatus.ACTIVE,
        step_name: str = "architect analysis",
        task_description: str | None = "Design a user auth system",
        completed_steps: list[str] | None = None,
        remaining_steps: list[str] | None = None,
    ) -> Checkpoint:
        """Create and persist a real checkpoint via CheckpointManager."""
        cp = Checkpoint(
            checkpoint_id=checkpoint_id,
            task_id=task_id,
            step_name=step_name,
            agent_id="agent-architect-test",
            status=status,
            completed_steps=completed_steps or ["intent"],
            remaining_steps=remaining_steps or ["design", "review"],
            progress_percentage=0.33,
            context_snapshot={"task": task_description} if task_description else {},
        )
        ok = self._manager.save_checkpoint(cp)
        self.assertTrue(ok, f"failed to save checkpoint {checkpoint_id}")
        return cp

    # ------------------------------------------------------------------
    # 1. list_sessions returns a list of dicts
    # ------------------------------------------------------------------

    def test_list_sessions_returns_list(self) -> None:
        """Happy: list_sessions returns a list of dicts with expected keys."""
        self._make_checkpoint(checkpoint_id="cp-list-1")
        self._make_checkpoint(checkpoint_id="cp-list-2", task_id="task-002")

        sessions = self._manager.list_sessions(limit=20)

        self.assertIsInstance(sessions, list)
        self.assertEqual(len(sessions), 2)
        for s in sessions:
            self.assertIsInstance(s, dict)
            # Each dict must carry the four documented keys.
            self.assertIn("session_id", s)
            self.assertIn("created_at", s)
            self.assertIn("status", s)
            self.assertIn("task_summary", s)

    # ------------------------------------------------------------------
    # 2. each session has a status field with a valid value
    # ------------------------------------------------------------------

    def test_list_sessions_has_status(self) -> None:
        """Happy/Config: every session dict has a ``status`` field in the
        documented value set {completed, interrupted, unknown}."""
        self._make_checkpoint(checkpoint_id="cp-active", status=CheckpointStatus.ACTIVE)
        self._make_checkpoint(checkpoint_id="cp-done", status=CheckpointStatus.COMPLETED)
        self._make_checkpoint(checkpoint_id="cp-fail", status=CheckpointStatus.FAILED)
        self._make_checkpoint(checkpoint_id="cp-exp", status=CheckpointStatus.EXPIRED)

        sessions = self._manager.list_sessions(limit=20)
        statuses = {s["status"] for s in sessions}
        # All four checkpoints surfaced.
        self.assertEqual(len(sessions), 4)
        # ACTIVE/FAILED -> interrupted, COMPLETED -> completed, EXPIRED -> unknown.
        self.assertIn("completed", statuses)
        self.assertIn("interrupted", statuses)
        self.assertIn("unknown", statuses)
        for s in sessions:
            self.assertIn(s["status"], {"completed", "interrupted", "unknown"})

    # ------------------------------------------------------------------
    # 3. get_session_status returns detailed status
    # ------------------------------------------------------------------

    def test_get_session_status(self) -> None:
        """Happy: get_session_status returns a detailed dict for an existing id."""
        self._make_checkpoint(
            checkpoint_id="cp-detail",
            task_id="task-detail",
            step_name="test step",
            task_description="Refactor the auth module",
            completed_steps=["intent", "design"],
            remaining_steps=["implement"],
        )

        status = self._manager.get_session_status("cp-detail")

        self.assertIsInstance(status, dict)
        self.assertTrue(status, "expected non-empty status dict for existing session")
        self.assertEqual(status["session_id"], "cp-detail")
        self.assertEqual(status["task_id"], "task-detail")
        self.assertEqual(status["agent_id"], "agent-architect-test")
        self.assertEqual(status["completed_steps"], ["intent", "design"])
        self.assertEqual(status["remaining_steps"], ["implement"])
        self.assertIn("progress_percentage", status)
        self.assertIn("created_at", status)
        self.assertIn("updated_at", status)
        # task_summary should carry the step name / task text.
        self.assertIn("Refactor the auth module", status["task_summary"])

    # ------------------------------------------------------------------
    # 4. resume nonexistent session -> graceful error, not crash
    # ------------------------------------------------------------------

    def test_resume_nonexistent_session(self) -> None:
        """Error: resuming a nonexistent session-id yields a graceful error,
        never an exception. get_session_status returns {} for missing ids."""
        # get_session_status on a missing id -> empty dict (no raise).
        missing_status = self._manager.get_session_status("cp-does-not-exist")
        self.assertEqual(missing_status, {})

        # load_resumable_task on a missing id -> (None, None, error_msg).
        task, status, err = load_resumable_task("cp-does-not-exist", persist_dir=self._tmpdir)
        self.assertIsNone(task)
        self.assertIsNone(status)
        self.assertIsNotNone(err)
        self.assertIn("cp-does-not-exist", err)

    # ------------------------------------------------------------------
    # 5. sensitive data (API key) in task description is redacted (Security A6)
    # ------------------------------------------------------------------

    def test_sensitive_data_filtered(self) -> None:
        """Side-Effect/Security: an API key embedded in the task description
        is redacted by OutputValidator.redact() in list_sessions output."""
        secret_task = f"Use key {_SENSITIVE_API_KEY} to call the upstream billing API"
        self._make_checkpoint(
            checkpoint_id="cp-secret",
            task_description=secret_task,
            step_name="integration",
        )

        sessions = self._manager.list_sessions(limit=20)
        self.assertEqual(len(sessions), 1)
        summary = sessions[0]["task_summary"]

        # The raw API key MUST NOT appear in the redacted summary.
        self.assertNotIn(
            _SENSITIVE_API_KEY,
            summary,
            "API key leaked into list_sessions output — redaction (Security A6) failed",
        )
        # OutputValidator replaces high-severity spans with "***".
        self.assertIn("***", summary)
        # Non-sensitive context survives.
        self.assertIn("billing API", summary)

        # get_session_status must also redact.
        detail = self._manager.get_session_status("cp-secret")
        self.assertNotIn(_SENSITIVE_API_KEY, detail["task_summary"])
        self.assertIn("***", detail["task_summary"])

    # ------------------------------------------------------------------
    # 6. anti-ghost: module-level _call_counter increments
    # ------------------------------------------------------------------

    def test_call_counter(self) -> None:
        """Side-Effect: module-level ``_call_counter`` increments on every
        SessionResume public method call (anti-ghost guarantee)."""
        before = cm_module._call_counter
        self._make_checkpoint(checkpoint_id="cp-counter")
        self._manager.list_sessions(limit=5)
        self._manager.get_session_status("cp-counter")
        self._manager.get_session_status("cp-missing")  # also increments
        after = cm_module._call_counter
        self.assertGreater(after, before, "module _call_counter did not increment")
        # list_sessions + get_session_status x2 => at least 3 increments
        # (save_checkpoint does not increment the SessionResume counter, which
        # is intentional — the counter tracks the new V4.5.0 surface only).
        self.assertGreaterEqual(after - before, 3)


if __name__ == "__main__":
    unittest.main()
