#!/usr/bin/env python3
"""AutonomousLoopController + GitDriver Integration Tests (V4.2.1 P2-3 — Test Pyramid Improvement).

End-to-end integration tests for the autonomous iteration pipeline and the
automated git driver. These tests verify CROSS-MODULE interactions across the
``scripts/collaboration/autonomous`` package and the dispatcher wiring, not the
unit-level behavior already covered by ``tests/test_autonomous.py``.

Integration surface exercised here:

    AutonomousLoopController
      ↔ NotesMemory (cross-module persistence of run state)
      ↔ LoopKernel (4-phase plan→dev→verify→fix loop, max_iterations enforcement)
      ↔ ConsensusEngine (HC-2 consensus gate, approval/rejection paths)
      ↔ MultiAgentDispatcher (autonomous_enabled wiring, dispatch_autonomous)

    GitDriver
      ↔ SmartConfirmation (3-mode confirmation gate for write operations)
      ↔ real git subprocess (commit / branch / tag / status in a temp repo)

Note: GitDriver is a sibling component of AutonomousLoopController inside the
``autonomous`` package; the controller does not invoke GitDriver directly.
These tests therefore cover each component's real boundaries (real git, real
NotesMemory files, real dispatcher wiring) and how they behave as an integrated
autonomous workflow, plus the cross-module dispatcher→controller wiring.

Test categories:
    T1: AutonomousLoopController basic iteration loop (start → iterate → terminal)
    T2: GitDriver commit / branch / tag integration (real git in temp dir)
    T3: Max iterations enforcement (autonomous_max_iterations reached → stop)
    T4: Stop condition integration (pause / stop / auto_resume checkpoint)
    T5: Error handling integration (git failure, dispatcher exception, consensus reject)
    T6: Dispatcher wiring integration (autonomous_enabled → controller instantiated)
    T7: Edge cases + graceful degradation (disabled mode, empty repo, confirmation modes)
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.autonomous import (
    AutonomousLoopController,
    GitDriver,
    NotesMemory,
    RunState,
    RunStatus,
    SmartConfirmation,
)
from scripts.collaboration.autonomous.git_driver import GitResult
from scripts.collaboration.autonomous.loop_controller import (
    AutonomousConfig,
    AutonomousRunReport,
)
from scripts.collaboration.autonomous.smart_confirmation import (
    ConfirmationMode,
    ConfirmationVerdict,
)
from scripts.collaboration.dispatcher import MultiAgentDispatcher
from scripts.collaboration.loop_engineering import LoopRunReport

# ---------------------------------------------------------------------------
# Test helpers: minimal stubs for cross-module boundaries
# ---------------------------------------------------------------------------


class StubDispatcher:
    """Minimal dispatcher stub compatible with HandoffAdapter.

    Returns a structured handoff result so the LoopKernel can complete a full
    five-step cycle. Like the unit-test stub, it never marks the objective
    "done", so the loop reaches ``max_iterations`` and ends in FAILED — this is
    a stub limitation, not a P3-1 bug.
    """

    def dispatch(self, task_description: str, **kwargs: Any) -> dict[str, Any]:  # noqa: ARG002
        return {
            "status": "ok",
            "output": f"stub-dispatched: {task_description}",
            "tasks": [{"name": "stub-task"}],
        }


class RaisingDispatcher:
    """Dispatcher stub that raises on dispatch() to test error propagation."""

    def dispatch(self, task_description: str, **kwargs: Any) -> dict[str, Any]:  # noqa: ARG002
        raise RuntimeError("simulated dispatcher failure")


class StubConsensusEngine:
    """Minimal ConsensusEngine stub implementing the create→vote→reach flow.

    ``allow`` controls whether ``reach_consensus`` reports an approved outcome.
    """

    def __init__(self, *, allow: bool = True) -> None:
        self._allow = allow
        self.proposals: list[dict[str, Any]] = []
        self._next_id = 0
        self._votes: dict[str, list[Any]] = {}

    def create_proposal(
        self,
        topic: str,
        proposer_id: str,
        content: str,
        options: list[str] | None = None,  # noqa: ARG002
        deadline: Any = None,  # noqa: ARG002
    ) -> Any:
        self._next_id += 1
        proposal_id = f"stub-prop-{self._next_id}"

        class StubProposal:
            def __init__(self, pid: str, t: str, pid2: str, c: str) -> None:
                self.proposal_id = pid
                self.topic = t
                self.proposer_id = pid2
                self.proposal_content = c
                self.votes: list[Any] = []
                self.status = "open"

        self.proposals.append({
            "proposal_id": proposal_id,
            "topic": topic,
            "proposer_id": proposer_id,
            "content": content,
        })
        self._votes[proposal_id] = []
        return StubProposal(proposal_id, topic, proposer_id, content)

    def cast_vote(self, proposal_id: str, vote: Any) -> Any:
        if proposal_id in self._votes:
            self._votes[proposal_id].append(vote)
        return None

    def reach_consensus(self, proposal_id: str) -> Any:  # noqa: ARG002
        votes_count = len(self._votes.get(proposal_id, []))
        is_allowed = self._allow

        class StubOutcome:
            def __init__(self, approved: bool) -> None:
                self.value = "approved" if approved else "rejected"

        class StubRecord:
            def __init__(self) -> None:
                self.outcome = StubOutcome(is_allowed)
                self.votes_for = votes_count if is_allowed else 0
                self.votes_against = 0 if is_allowed else votes_count

        return StubRecord()


def _init_real_git_repo(repo_path: Path) -> None:
    """Initialize a real git repo with local user config (for GitDriver tests)."""
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "test@example.com",
    }
    subprocess.run(["git", "init"], cwd=str(repo_path), check=True, env=env, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(repo_path), check=True, env=env, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=str(repo_path), check=True, env=env, capture_output=True,
    )


def _make_completed_loop_report() -> LoopRunReport:
    """Build a LoopRunReport with final_status='completed' for consensus tests."""
    return LoopRunReport(
        objective="integration test objective",
        total_iterations=2,
        final_status="completed",
    )


# ---------------------------------------------------------------------------
# T1: AutonomousLoopController basic iteration loop
# ---------------------------------------------------------------------------


class T1_AutonomousLoopControllerIterationLoop(unittest.TestCase):
    """T1: AutonomousLoopController start → iterate → terminal state."""

    def setUp(self) -> None:
        self._notes_dir = tempfile.mkdtemp(prefix="auto_t1_")

    def tearDown(self) -> None:
        shutil.rmtree(self._notes_dir, ignore_errors=True)

    def _make_controller(
        self, objective: str = "build feature X", max_iterations: int = 2,
    ) -> AutonomousLoopController:
        config = AutonomousConfig(
            objective=objective,
            max_iterations=max_iterations,
            notes_memory_dir=self._notes_dir,
            dispatcher=StubDispatcher(),
        )
        return AutonomousLoopController(config=config)

    def test_01_run_returns_autonomous_run_report(self) -> None:
        """Verify: run() returns an AutonomousRunReport carrying the objective."""
        controller = self._make_controller()
        report = controller.run()
        self.assertIsInstance(report, AutonomousRunReport)
        self.assertEqual(report.objective, "build feature X")

    def test_02_run_transitions_state_to_terminal(self) -> None:
        """Verify: after run() the RunState reaches a terminal status."""
        controller = self._make_controller()
        report = controller.run()
        self.assertIsNotNone(report.state)
        self.assertIn(
            report.state.status,
            (RunStatus.COMPLETED, RunStatus.STOPPED, RunStatus.FAILED),
        )
        self.assertTrue(report.state.is_terminal)

    def test_03_run_persists_state_to_notes_memory(self) -> None:
        """Verify: LoopController ↔ NotesMemory integration — state survives to disk."""
        controller = self._make_controller(objective="persist integration")
        controller.run(run_id="t1-persist")

        memory = NotesMemory(storage_dir=self._notes_dir)
        loaded = memory.load("t1-persist")
        self.assertIsNotNone(loaded, "RunState must be persisted across modules")
        self.assertEqual(loaded.objective, "persist integration")
        self.assertTrue(loaded.is_terminal)
        # The on-disk file path matches the documented naming convention.
        self.assertTrue((Path(self._notes_dir) / "run_t1-persist.json").exists())

    def test_04_run_generates_run_id_when_omitted(self) -> None:
        """Verify: omitted run_id yields an auto-generated non-empty identifier."""
        controller = self._make_controller()
        report = controller.run()
        self.assertTrue(report.run_id)
        self.assertIsNotNone(controller.get_state())
        self.assertEqual(controller.get_state().run_id, report.run_id)


# ---------------------------------------------------------------------------
# T2: GitDriver commit / branch / tag integration (real git in temp dir)
# ---------------------------------------------------------------------------


class T2_GitDriverRealGitIntegration(unittest.TestCase):
    """T2: GitDriver against a real git repository in a temp dir."""

    def setUp(self) -> None:
        self._repo_dir = tempfile.mkdtemp(prefix="auto_git_t2_")
        _init_real_git_repo(Path(self._repo_dir))

    def tearDown(self) -> None:
        shutil.rmtree(self._repo_dir, ignore_errors=True)

    def test_01_commit_creates_real_git_commit(self) -> None:
        """Verify: GitDriver.commit with auto_confirm creates a real commit."""
        (Path(self._repo_dir) / "feature.txt").write_text("data", encoding="utf-8")
        driver = GitDriver(repo_path=self._repo_dir, auto_confirm=True)

        result = driver.commit("implement feature module", files=["feature.txt"])

        self.assertTrue(result.success, f"commit failed: {result.error}")
        self.assertTrue(result.confirmed)
        log = subprocess.run(
            ["git", "log", "--oneline"],
            cwd=self._repo_dir, capture_output=True, text=True, check=True,
        )
        self.assertIn("implement feature module", log.stdout)

    def test_02_status_and_uncommitted_changes_reflect_workdir(self) -> None:
        """Verify: GitDriver.status / has_uncommitted_changes read the real workdir."""
        driver = GitDriver(repo_path=self._repo_dir, auto_confirm=True)
        self.assertFalse(driver.has_uncommitted_changes())

        (Path(self._repo_dir) / "new.txt").write_text("x", encoding="utf-8")
        self.assertTrue(driver.has_uncommitted_changes())
        status_result = driver.status()
        self.assertTrue(status_result.success)
        self.assertIn("new.txt", status_result.output)

    def test_03_create_branch_and_tag_on_real_repo(self) -> None:
        """Verify: GitDriver.create_branch + tag operate on a real repo."""
        # An initial commit is required before branching/tagging.
        (Path(self._repo_dir) / "init.txt").write_text("init", encoding="utf-8")
        subprocess.run(
            ["git", "add", "init.txt"], cwd=self._repo_dir, capture_output=True, check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "init"], cwd=self._repo_dir, capture_output=True, check=True,
        )

        driver = GitDriver(repo_path=self._repo_dir, auto_confirm=True)
        branch_result = driver.create_branch("feature-branch")
        self.assertTrue(branch_result.success, f"branch failed: {branch_result.error}")

        tag_result = driver.tag("v1.2.3", message="release 1.2.3")
        self.assertTrue(tag_result.success, f"tag failed: {tag_result.error}")

        tags = subprocess.run(
            ["git", "tag", "-l"],
            cwd=self._repo_dir, capture_output=True, text=True, check=True,
        )
        self.assertIn("v1.2.3", tags.stdout)

    def test_04_commit_blocked_by_smart_confirmation_without_auto_confirm(self) -> None:
        """Verify: SmartConfirmation blocks a commit when auto_confirm=False (real repo)."""
        (Path(self._repo_dir) / "blocked.txt").write_text("y", encoding="utf-8")
        # Message deliberately avoids whitelist keywords so SMART mode requires confirmation.
        driver = GitDriver(repo_path=self._repo_dir, auto_confirm=False)

        result = driver.commit("update production config", files=["blocked.txt"])

        self.assertFalse(result.success)
        self.assertFalse(result.confirmed)
        self.assertIn("requires confirmation", result.error)
        # No commit must have been created.
        log = subprocess.run(
            ["git", "log", "--oneline"],
            cwd=self._repo_dir, capture_output=True, text=True, check=False,
        )
        self.assertEqual(log.stdout, "")


# ---------------------------------------------------------------------------
# T3: Max iterations enforcement
# ---------------------------------------------------------------------------


class T3_MaxIterationsEnforcement(unittest.TestCase):
    """T3: autonomous_max_iterations caps the iteration count."""

    def setUp(self) -> None:
        self._notes_dir = tempfile.mkdtemp(prefix="auto_t3_")

    def tearDown(self) -> None:
        shutil.rmtree(self._notes_dir, ignore_errors=True)

    def test_01_max_iterations_one_caps_total_iterations(self) -> None:
        """Verify: max_iterations=1 → loop_report.total_iterations <= 1."""
        config = AutonomousConfig(
            objective="iter cap test",
            max_iterations=1,
            notes_memory_dir=self._notes_dir,
            dispatcher=StubDispatcher(),
        )
        controller = AutonomousLoopController(config=config)
        report = controller.run()
        self.assertIsNotNone(report.loop_report)
        self.assertLessEqual(report.loop_report.total_iterations, 1)

    def test_02_max_iterations_propagated_to_run_state(self) -> None:
        """Verify: AutonomousConfig.max_iterations reaches the RunState."""
        config = AutonomousConfig(
            objective="propagation test",
            max_iterations=7,
            notes_memory_dir=self._notes_dir,
            dispatcher=StubDispatcher(),
        )
        controller = AutonomousLoopController(config=config)
        report = controller.run()
        self.assertEqual(report.state.max_iterations, 7)

    def test_03_max_iterations_zero_terminates_without_crash(self) -> None:
        """Verify: max_iterations=0 terminates gracefully (no crash, terminal state)."""
        config = AutonomousConfig(
            objective="zero iter test",
            max_iterations=0,
            notes_memory_dir=self._notes_dir,
            dispatcher=StubDispatcher(),
        )
        controller = AutonomousLoopController(config=config)
        report = controller.run()
        self.assertTrue(report.state.is_terminal)
        # With zero iterations the kernel reports final_status="failed" and the
        # controller maps that to FAILED.
        self.assertEqual(report.state.status, RunStatus.FAILED)

    def test_04_dispatcher_max_iterations_propagated_to_run(self) -> None:
        """Verify: dispatcher.autonomous_max_iterations flows into the run report."""
        work_dir = tempfile.mkdtemp(prefix="auto_t3_disp_")
        try:
            disp = MultiAgentDispatcher(
                persist_dir=work_dir,
                enable_warmup=False,
                enable_memory=False,
                enable_skillify=False,
                autonomous_enabled=True,
                autonomous_max_iterations=2,
            )
            report = disp.dispatch_autonomous("dispatcher iter cap")
            self.assertEqual(report.state.max_iterations, 2)
            disp.shutdown()
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# T4: Stop condition integration (pause / stop / auto_resume)
# ---------------------------------------------------------------------------


class T4_StopConditionAndResumeIntegration(unittest.TestCase):
    """T4: pause / stop / auto_resume checkpoint integration across modules."""

    def setUp(self) -> None:
        self._notes_dir = tempfile.mkdtemp(prefix="auto_t4_")

    def tearDown(self) -> None:
        shutil.rmtree(self._notes_dir, ignore_errors=True)

    def test_01_pause_marks_state_paused_and_resumable(self) -> None:
        """Verify: pause() flips state to PAUSED and the checkpoint is resumable."""
        config = AutonomousConfig(
            objective="pause test",
            notes_memory_dir=self._notes_dir,
            dispatcher=StubDispatcher(),
        )
        controller = AutonomousLoopController(config=config)
        controller._state = RunState(
            run_id="t4-pause", objective="pause test", status=RunStatus.PLANNING,
        )
        controller.pause()
        self.assertEqual(controller.get_state().status, RunStatus.PAUSED)
        self.assertTrue(controller.get_state().can_resume)

    def test_02_stop_marks_state_stopped_terminal(self) -> None:
        """Verify: stop() flips state to STOPPED (terminal)."""
        config = AutonomousConfig(
            objective="stop test",
            notes_memory_dir=self._notes_dir,
            dispatcher=StubDispatcher(),
        )
        controller = AutonomousLoopController(config=config)
        controller._state = RunState(
            run_id="t4-stop", objective="stop test", status=RunStatus.VERIFYING,
        )
        controller.stop()
        self.assertEqual(controller.get_state().status, RunStatus.STOPPED)
        self.assertTrue(controller.get_state().is_terminal)

    def test_03_auto_resume_continues_from_paused_checkpoint(self) -> None:
        """Verify: auto_resume=True resumes a previously PAUSED run (notes persisted)."""
        memory = NotesMemory(storage_dir=self._notes_dir)
        memory.save(RunState(
            run_id="t4-resumable",
            objective="resume test",
            status=RunStatus.PAUSED,
            current_iteration=2,
        ))

        config = AutonomousConfig(
            objective="resume test",
            max_iterations=5,
            notes_memory_dir=self._notes_dir,
            dispatcher=StubDispatcher(),
            auto_resume=True,
        )
        controller = AutonomousLoopController(config=config)
        report = controller.run(run_id="t4-resumable")

        resumed_notes = [n for n in report.state.notes if "Resumed" in n]
        self.assertGreaterEqual(len(resumed_notes), 1)

    def test_04_no_auto_resume_when_flag_off(self) -> None:
        """Verify: auto_resume=False starts a fresh run even if a PAUSED checkpoint exists."""
        memory = NotesMemory(storage_dir=self._notes_dir)
        memory.save(RunState(
            run_id="t4-no-resume",
            objective="t",
            status=RunStatus.PAUSED,
        ))

        config = AutonomousConfig(
            objective="t",
            max_iterations=1,
            notes_memory_dir=self._notes_dir,
            dispatcher=StubDispatcher(),
            auto_resume=False,
        )
        controller = AutonomousLoopController(config=config)
        report = controller.run(run_id="t4-no-resume")

        resumed_notes = [n for n in report.state.notes if "Resumed" in n]
        self.assertEqual(len(resumed_notes), 0)


# ---------------------------------------------------------------------------
# T5: Error handling integration
# ---------------------------------------------------------------------------


class T5_ErrorHandlingIntegration(unittest.TestCase):
    """T5: git failures, dispatcher exceptions, and consensus rejection paths."""

    def setUp(self) -> None:
        self._notes_dir = tempfile.mkdtemp(prefix="auto_t5_")

    def tearDown(self) -> None:
        shutil.rmtree(self._notes_dir, ignore_errors=True)

    def test_01_git_driver_on_nonexistent_repo_returns_failure(self) -> None:
        """Verify: GitDriver on a non-existent path returns a failed GitResult (no raise)."""
        bogus = os.path.join(self._notes_dir, "does-not-exist")
        driver = GitDriver(repo_path=bogus, auto_confirm=True)
        result = driver.status()
        self.assertIsInstance(result, GitResult)
        self.assertFalse(result.success)
        self.assertTrue(result.error)

    def test_02_commit_with_allow_push_no_remote_fails_gracefully(self) -> None:
        """Verify: commit+push with no remote → push fails but no exception escapes."""
        repo_dir = tempfile.mkdtemp(prefix="auto_t5_push_")
        try:
            _init_real_git_repo(Path(repo_dir))
            (Path(repo_dir) / "f.txt").write_text("x", encoding="utf-8")
            driver = GitDriver(repo_path=repo_dir, auto_confirm=True)

            result = driver.commit("add file", files=["f.txt"], allow_push=True)

            self.assertFalse(result.success)
            self.assertTrue(result.error)
        finally:
            shutil.rmtree(repo_dir, ignore_errors=True)

    def test_03_dispatcher_exception_contained_as_failed(self) -> None:
        """Verify: a raising dispatcher is contained → run ends FAILED.

        Cross-module error path: HandoffAdapter catches the dispatcher
        exception (logs WARNING, returns status='error') so it never reaches
        the controller's try/except. The LoopKernel then exhausts its
        consecutive-failure limit and the controller maps final_status='failed'
        to RunStatus.FAILED. The run error therefore reflects the kernel's
        failure-limit message, not the raw dispatcher exception.
        """
        config = AutonomousConfig(
            objective="error propagation test",
            max_iterations=3,
            notes_memory_dir=self._notes_dir,
            dispatcher=RaisingDispatcher(),
        )
        controller = AutonomousLoopController(config=config)
        report = controller.run(run_id="t5-raise")

        self.assertEqual(report.state.status, RunStatus.FAILED)
        self.assertTrue(report.state.is_terminal)
        self.assertIn("Consecutive failures", report.state.error)

    def test_04_consensus_rejection_marks_run_failed(self) -> None:
        """Verify: a rejecting ConsensusEngine flips a completed run to FAILED."""
        consensus = StubConsensusEngine(allow=False)
        config = AutonomousConfig(
            objective="consensus reject test",
            max_iterations=1,
            notes_memory_dir=self._notes_dir,
            dispatcher=StubDispatcher(),
            consensus_engine=consensus,
        )
        controller = AutonomousLoopController(config=config)
        controller._state = RunState(
            run_id="t5-reject",
            objective="consensus reject test",
            status=RunStatus.VERIFYING,
        )

        rejected = controller._check_consensus_gate(_make_completed_loop_report())
        self.assertFalse(rejected)
        self.assertGreaterEqual(len(consensus.proposals), 1)


# ---------------------------------------------------------------------------
# T6: Dispatcher wiring integration
# ---------------------------------------------------------------------------


class T6_DispatcherWiringIntegration(unittest.TestCase):
    """T6: MultiAgentDispatcher ↔ AutonomousLoopController wiring."""

    def setUp(self) -> None:
        self._work_dir = tempfile.mkdtemp(prefix="auto_t6_")

    def tearDown(self) -> None:
        shutil.rmtree(self._work_dir, ignore_errors=True)

    def _make_dispatcher(self, **kwargs: Any) -> MultiAgentDispatcher:
        return MultiAgentDispatcher(
            persist_dir=self._work_dir,
            enable_warmup=False,
            enable_memory=False,
            enable_skillify=False,
            **kwargs,
        )

    def test_01_autonomous_disabled_by_default_controller_none(self) -> None:
        """Verify: default dispatcher has autonomous_enabled=False and controller None."""
        disp = self._make_dispatcher()
        try:
            self.assertFalse(disp.autonomous_enabled)
            self.assertIsNone(disp.autonomous_controller)
        finally:
            disp.shutdown()

    def test_02_autonomous_enabled_instantiates_controller(self) -> None:
        """Verify: autonomous_enabled=True wires a non-None autonomous_controller."""
        disp = self._make_dispatcher(
            autonomous_enabled=True, autonomous_max_iterations=4,
        )
        try:
            self.assertTrue(disp.autonomous_enabled)
            self.assertIsNotNone(disp.autonomous_controller)
        finally:
            disp.shutdown()

    def test_03_dispatch_autonomous_raises_when_disabled(self) -> None:
        """Verify: dispatch_autonomous on a disabled dispatcher raises RuntimeError."""
        disp = self._make_dispatcher()
        try:
            with self.assertRaises(RuntimeError) as ctx:
                disp.dispatch_autonomous("anything")
            self.assertIn("not enabled", str(ctx.exception).lower())
        finally:
            disp.shutdown()

    def test_04_dispatch_autonomous_returns_report_when_enabled(self) -> None:
        """Verify: dispatch_autonomous returns an AutonomousRunReport when enabled."""
        disp = self._make_dispatcher(
            autonomous_enabled=True, autonomous_max_iterations=1,
        )
        try:
            report = disp.dispatch_autonomous("integration objective")
            self.assertIsInstance(report, AutonomousRunReport)
            self.assertEqual(report.objective, "integration objective")
            self.assertTrue(report.state.is_terminal)
        finally:
            disp.shutdown()

    def test_05_dispatch_autonomous_run_id_propagated(self) -> None:
        """Verify: dispatch_autonomous forwards run_id through the wiring."""
        disp = self._make_dispatcher(
            autonomous_enabled=True, autonomous_max_iterations=1,
        )
        try:
            report = disp.dispatch_autonomous("run id objective", run_id="t6-custom-id")
            self.assertEqual(report.run_id, "t6-custom-id")
        finally:
            disp.shutdown()


# ---------------------------------------------------------------------------
# T7: Edge cases + graceful degradation
# ---------------------------------------------------------------------------


class T7_EdgeCasesAndGracefulDegradation(unittest.TestCase):
    """T7: disabled mode, readonly ops, confirmation modes, no-dispatcher edge."""

    def setUp(self) -> None:
        self._notes_dir = tempfile.mkdtemp(prefix="auto_t7_")
        self._repo_dir = tempfile.mkdtemp(prefix="auto_t7_git_")
        _init_real_git_repo(Path(self._repo_dir))

    def tearDown(self) -> None:
        shutil.rmtree(self._notes_dir, ignore_errors=True)
        shutil.rmtree(self._repo_dir, ignore_errors=True)

    def test_01_readonly_git_ops_work_without_auto_confirm(self) -> None:
        """Verify: status() is read-only and bypasses SmartConfirmation entirely."""
        driver = GitDriver(repo_path=self._repo_dir, auto_confirm=False)
        result = driver.status()
        self.assertTrue(result.success)
        self.assertIsInstance(result, GitResult)

    def test_02_whitelist_only_mode_blocks_commit(self) -> None:
        """Verify: WHITELIST_ONLY confirmation blocks commit (not in whitelist)."""
        confirmer = SmartConfirmation(mode=ConfirmationMode.WHITELIST_ONLY)
        decision = confirmer.evaluate("git commit: update module")
        self.assertEqual(decision.verdict, ConfirmationVerdict.REQUIRE_CONFIRMATION)
        # A GitDriver using this confirmer must therefore refuse the commit.
        driver = GitDriver(
            repo_path=self._repo_dir, confirmer=confirmer, auto_confirm=False,
        )
        (Path(self._repo_dir) / "w.txt").write_text("z", encoding="utf-8")
        result = driver.commit("update module", files=["w.txt"])
        self.assertFalse(result.success)

    def test_03_controller_runs_with_no_dispatcher(self) -> None:
        """Verify: controller runs (and terminates) even with dispatcher=None."""
        config = AutonomousConfig(
            objective="no dispatcher edge",
            max_iterations=1,
            notes_memory_dir=self._notes_dir,
            dispatcher=None,
        )
        controller = AutonomousLoopController(config=config)
        report = controller.run(run_id="t7-no-dispatcher")
        # No dispatcher → the loop must still reach a terminal state without crashing.
        self.assertTrue(report.state.is_terminal)

    def test_04_empty_objective_does_not_crash_controller(self) -> None:
        """Verify: an empty objective is handled gracefully (terminal state reached)."""
        config = AutonomousConfig(
            objective="",
            max_iterations=1,
            notes_memory_dir=self._notes_dir,
            dispatcher=StubDispatcher(),
        )
        controller = AutonomousLoopController(config=config)
        report = controller.run(run_id="t7-empty-obj")
        self.assertTrue(report.state.is_terminal)
        self.assertEqual(report.objective, "")

    def test_05_get_sleep_guard_stats_none_when_disabled(self) -> None:
        """Verify: with no sleep_guard_config, get_sleep_guard_stats() returns None."""
        config = AutonomousConfig(
            objective="sleep guard off",
            notes_memory_dir=self._notes_dir,
            dispatcher=StubDispatcher(),
        )
        controller = AutonomousLoopController(config=config)
        self.assertIsNone(controller.get_sleep_guard_stats())


if __name__ == "__main__":
    unittest.main()
