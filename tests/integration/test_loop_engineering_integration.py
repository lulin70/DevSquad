#!/usr/bin/env python3
"""LoopEngineering Kernel + HandoffAdapter Integration Tests (V4.2.1 P2-2 — Test Pyramid Improvement).

End-to-end integration tests for cross-module interaction between the
LoopEngineering kernel, CheckpointManager (SHA-256 integrity, handoff
documents, auto-cleanup, lifecycle state persistence), and the
ShortcutLifecycleAdapter (CLI 6-command shortcuts → lifecycle state).

Integration flow verified:

    LoopKernel.run(objective)
      → DiscoveryProbe.discover → HandoffAdapter.dispatch → IndependentEvaluator
      → UnifiedMemory.persist_cycle → LoopScheduler.decide
      → cycle.handoff dict → HandoffDocument → CheckpointManager.save_handoff
      → CheckpointManager.save_checkpoint (SHA-256) → load_checkpoint (integrity)
      → CheckpointManager.save_lifecycle_state → list/load/delete
      → ShortcutLifecycleAdapter.save_state/restore_state (cross-session)
      → create_checkpoint_from_lifecycle (protocol → checkpoint bridge)

These tests focus on CROSS-MODULE interactions (kernel ↔ checkpoint,
handoff ↔ checkpoint, lifecycle adapter ↔ checkpoint). Unit-level behavior
of individual methods is covered by tests/test_loop_engineering.py,
tests/test_lifecycle_protocol.py, and tests/unit/test_checkpoint_atomic_write.py.

Test categories:
    T1: Loop kernel + checkpoint save/restore integration
    T2: Handoff document generation integration (cycle → handoff doc → restored)
    T3: SHA-256 integrity verification (tampered state → restore fails)
    T4: Lifecycle state persistence across sessions (save → list → restore)
    T5: Auto-cleanup of old checkpoints (max retention exceeded → oldest deleted)
    T6: ShortcutLifecycleAdapter integration (CLI shortcuts → lifecycle state)
    T7: Edge cases + graceful degradation (empty state, missing, corrupted)
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.checkpoint_manager import (
    Checkpoint,
    CheckpointManager,
    CheckpointStatus,
    HandoffDocument,
)
from scripts.collaboration.lifecycle_protocol import (
    LifecycleMode,
    ShortcutLifecycleAdapter,
)
from scripts.collaboration.loop_engineering import (
    CycleResult,
    EvaluatorMode,
    HandoffAdapter,
    LoopEngineeringConfig,
    LoopKernel,
    LoopRunReport,
    LoopType,
    UnifiedMemory,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _CompletingDiscoveryProbe:
    """DiscoveryProbe that returns work at iter 0, done at iter 1.

    Lets integration tests exercise a LoopKernel.run() that terminates with
    final_status="completed" without relying on the default DiscoveryProbe
    (which never naturally completes because completed_items are never
    populated in UnifiedMemory.persist_cycle).
    """

    def discover(self, objective: str, iter_index: int, memory: object) -> dict:
        if iter_index == 0:
            return {
                "focus": f"Initial analysis for: {objective}",
                "tasks": ["analyze_objective", "identify_scope"],
                "iter_index": iter_index,
            }
        return {
            "focus": "All tasks completed",
            "tasks": [],
            "iter_index": iter_index,
            "done": True,
        }


class _MultiIterationDiscoveryProbe:
    """DiscoveryProbe that runs for N iterations before completing."""

    def __init__(self, work_iterations: int = 3) -> None:
        self._work_iterations = work_iterations

    def discover(self, objective: str, iter_index: int, memory: object) -> dict:
        if iter_index < self._work_iterations:
            return {
                "focus": f"Work iteration {iter_index} for: {objective}",
                "tasks": [f"task_{iter_index}"],
                "iter_index": iter_index,
            }
        return {
            "focus": "All tasks completed",
            "tasks": [],
            "iter_index": iter_index,
            "done": True,
        }


def _make_checkpoint_from_cycle(cycle: CycleResult, task_id: str = "loop-task") -> Checkpoint:
    """Build a Checkpoint from a LoopKernel CycleResult for persistence."""
    return Checkpoint(
        task_id=task_id,
        step_id=f"iter-{cycle.iter_index}",
        step_name=f"Loop iteration {cycle.iter_index}",
        agent_id="loop-kernel",
        status=CheckpointStatus.ACTIVE,
        completed_steps=[f"iter-{i}" for i in range(cycle.iter_index)],
        remaining_steps=[f"iter-{cycle.iter_index}"],
        progress_percentage=float(cycle.iter_index) / 10.0,
        context_snapshot={
            "verification_passed": cycle.verification_passed,
            "discovery_focus": cycle.discovery.get("focus", ""),
        },
        outputs={"handoff_status": cycle.handoff.get("status", "")},
    )


def _make_handoff_from_cycle(cycle: CycleResult, task_id: str = "loop-task") -> HandoffDocument:
    """Build a HandoffDocument from a LoopKernel CycleResult."""
    return HandoffDocument(
        task_id=task_id,
        from_agent="loop-kernel",
        to_agent="next-agent",
        completed_work=[f"Iteration {cycle.iter_index}: {cycle.discovery.get('focus', '')}"],
        current_state={
            "verification_passed": cycle.verification_passed,
            "handoff_status": cycle.handoff.get("status", ""),
        },
        next_steps=cycle.discovery.get("tasks", []),
        pending_issues=list(cycle.verification_errors),
        important_notes=[f"Iter {cycle.iter_index} status={cycle.handoff.get('status')}"],
        context_for_next=cycle.discovery,
    )


# ---------------------------------------------------------------------------
# T1: Loop kernel + checkpoint save/restore integration
# ---------------------------------------------------------------------------


class T1_LoopKernelCheckpointIntegration(unittest.TestCase):
    """T1: LoopKernel cycle results → CheckpointManager save/restore."""

    def setUp(self) -> None:
        self._work_dir = tempfile.mkdtemp(prefix="le_t1_")
        self._mem_dir = Path(self._work_dir) / "loop_mem"
        self.manager = CheckpointManager(storage_path=self._work_dir)
        self.memory = UnifiedMemory(storage_dir=str(self._mem_dir))

    def tearDown(self) -> None:
        shutil.rmtree(self._work_dir, ignore_errors=True)

    def _make_kernel(self, probe: object | None = None) -> LoopKernel:
        config = LoopEngineeringConfig(
            loop_type=LoopType.CODING,
            evaluator_mode=EvaluatorMode.STANDARD,
            max_iterations=10,
            human_checkpoint_every=0,
        )
        return LoopKernel(
            config=config,
            discovery_probe=probe or _CompletingDiscoveryProbe(),
            memory=self.memory,
        )

    def test_01_loop_run_produces_cycles_that_can_be_checkpointed(self) -> None:
        """Verify: LoopKernel.run() produces cycles; cycle data → save_checkpoint → load_checkpoint."""
        kernel = self._make_kernel()
        report = kernel.run("Build feature X")
        self.assertEqual(report.final_status, "completed")
        self.assertGreaterEqual(len(report.cycles), 1)

        cycle = report.cycles[0]
        cp = _make_checkpoint_from_cycle(cycle)
        self.assertTrue(self.manager.save_checkpoint(cp),
                        "save_checkpoint must succeed for cycle-derived checkpoint")
        loaded = self.manager.load_checkpoint(cp.checkpoint_id)
        self.assertIsNotNone(loaded, "load_checkpoint must return the saved checkpoint")
        self.assertEqual(loaded.task_id, cp.task_id)
        self.assertEqual(loaded.context_snapshot["verification_passed"],
                         cycle.verification_passed)

    def test_02_completing_loop_final_cycle_carries_done_flag(self) -> None:
        """Verify: completing loop's final cycle discovery has done=True, persisted in checkpoint."""
        kernel = self._make_kernel()
        report = kernel.run("Build feature Y")
        final_cycle = report.cycles[-1]
        self.assertTrue(final_cycle.discovery.get("done"),
                        "Final cycle discovery must carry done=True")

        cp = _make_checkpoint_from_cycle(final_cycle, task_id="final-task")
        cp.context_snapshot["done"] = final_cycle.discovery.get("done")
        self.manager.save_checkpoint(cp)
        loaded = self.manager.load_checkpoint(cp.checkpoint_id)
        self.assertIsNotNone(loaded)
        self.assertTrue(loaded.context_snapshot.get("done"))

    def test_03_multiple_cycles_produce_multiple_checkpoints(self) -> None:
        """Verify: multi-iteration loop → one checkpoint per cycle → list_checkpoints returns all."""
        kernel = self._make_kernel(probe=_MultiIterationDiscoveryProbe(work_iterations=3))
        report = kernel.run("Build feature Z")
        self.assertEqual(report.final_status, "completed")

        saved_ids = []
        for cycle in report.cycles:
            cp = _make_checkpoint_from_cycle(cycle, task_id="multi-task")
            self.manager.save_checkpoint(cp)
            saved_ids.append(cp.checkpoint_id)

        listed = self.manager.list_checkpoints(task_id="multi-task")
        self.assertEqual(len(listed), len(saved_ids),
                         "list_checkpoints must return one entry per saved checkpoint")
        listed_ids = {cp.checkpoint_id for cp in listed}
        self.assertEqual(listed_ids, set(saved_ids))

    def test_04_create_checkpoint_from_dispatch_with_loop_data(self) -> None:
        """Verify: create_checkpoint_from_dispatch uses loop cycle progress data."""
        kernel = self._make_kernel()
        report = kernel.run("Build feature W")
        cycle = report.cycles[0]

        completed = [f"iter-{i}" for i in range(cycle.iter_index + 1)]
        remaining = ["iter-next"]
        cp = self.manager.create_checkpoint_from_dispatch(
            task_id="dispatch-task",
            step_name=f"Loop iter {cycle.iter_index}",
            agent_id="loop-kernel",
            completed_steps=completed,
            remaining_steps=remaining,
            context={"focus": cycle.discovery.get("focus", "")},
            outputs={"handoff": cycle.handoff},
        )
        self.assertEqual(cp.task_id, "dispatch-task")
        self.assertAlmostEqual(cp.progress_percentage, len(completed) / (len(completed) + len(remaining)))
        loaded = self.manager.load_checkpoint(cp.checkpoint_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.completed_steps, completed)

    def test_05_get_latest_checkpoint_returns_most_recent(self) -> None:
        """Verify: get_latest_checkpoint returns the newest checkpoint for a task."""
        kernel = self._make_kernel(probe=_MultiIterationDiscoveryProbe(work_iterations=2))
        report = kernel.run("Build feature L")
        last_cp = None
        for cycle in report.cycles:
            cp = _make_checkpoint_from_cycle(cycle, task_id="latest-task")
            self.manager.save_checkpoint(cp)
            last_cp = cp
            time.sleep(0.02)  # ensure mtimes differ

        latest = self.manager.get_latest_checkpoint("latest-task")
        self.assertIsNotNone(latest)
        self.assertEqual(latest.checkpoint_id, last_cp.checkpoint_id,
                         "get_latest_checkpoint must return the most recently saved checkpoint")


# ---------------------------------------------------------------------------
# T2: Handoff document generation integration
# ---------------------------------------------------------------------------


class T2_HandoffDocumentIntegration(unittest.TestCase):
    """T2: LoopKernel cycle handoff dict → HandoffDocument → save/load roundtrip."""

    def setUp(self) -> None:
        self._work_dir = tempfile.mkdtemp(prefix="le_t2_")
        self._mem_dir = Path(self._work_dir) / "loop_mem"
        self.manager = CheckpointManager(storage_path=self._work_dir)
        self.memory = UnifiedMemory(storage_dir=str(self._mem_dir))
        config = LoopEngineeringConfig(
            evaluator_mode=EvaluatorMode.STANDARD,
            max_iterations=10,
            human_checkpoint_every=0,
        )
        self.kernel = LoopKernel(
            config=config,
            discovery_probe=_CompletingDiscoveryProbe(),
            memory=self.memory,
        )

    def tearDown(self) -> None:
        shutil.rmtree(self._work_dir, ignore_errors=True)

    def test_01_loop_handoff_dict_to_handoff_document_roundtrip(self) -> None:
        """Verify: cycle.handoff dict → HandoffDocument → save_handoff → load_handoff preserves data."""
        report = self.kernel.run("Build feature A")
        cycle = report.cycles[0]
        # Loop handoff is a dict; bridge to HandoffDocument for checkpoint persistence
        self.assertIn("status", cycle.handoff)

        doc = _make_handoff_from_cycle(cycle, task_id="handoff-task")
        self.assertTrue(self.manager.save_handoff(doc),
                        "save_handoff must succeed for cycle-derived handoff")
        loaded = self.manager.load_handoff(doc.handoff_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.task_id, "handoff-task")
        self.assertEqual(loaded.from_agent, "loop-kernel")
        self.assertEqual(loaded.current_state["handoff_status"], cycle.handoff.get("status"))
        self.assertEqual(loaded.next_steps, cycle.discovery.get("tasks", []))

    def test_02_handoff_markdown_contains_loop_output(self) -> None:
        """Verify: HandoffDocument.to_markdown renders cycle focus and handoff status."""
        report = self.kernel.run("Build feature B")
        cycle = report.cycles[0]
        doc = _make_handoff_from_cycle(cycle, task_id="md-task")
        md = doc.to_markdown()
        self.assertIn("# Task Handoff Document", md)
        self.assertIn(cycle.discovery.get("focus", ""), md)
        # current_state JSON should include the handoff status
        self.assertIn(str(cycle.handoff.get("status")), md)

    def test_03_multiple_handoffs_for_task_listed(self) -> None:
        """Verify: get_task_handoffs returns all handoffs for a task, sorted ascending."""
        report = self.kernel.run("Build feature C")
        saved_ids = []
        for cycle in report.cycles:
            doc = _make_handoff_from_cycle(cycle, task_id="list-task")
            self.manager.save_handoff(doc)
            saved_ids.append(doc.handoff_id)

        handoffs = self.manager.get_task_handoffs("list-task")
        self.assertEqual(len(handoffs), len(saved_ids),
                         "get_task_handoffs must return every saved handoff for the task")
        returned_ids = {h.handoff_id for h in handoffs}
        self.assertEqual(returned_ids, set(saved_ids))

    def test_04_suggest_skills_from_loop_handoff_content(self) -> None:
        """Verify: suggest_skills maps loop handoff content keywords to skill recommendations."""
        # Cycle 0 focus mentions "analysis"; handoff output mentions tasks
        report = self.kernel.run("Implement test suite for module")
        cycle = report.cycles[0]
        doc = _make_handoff_from_cycle(cycle, task_id="skill-task")
        md = doc.to_markdown()
        skills = self.manager.suggest_skills(md)
        self.assertIsInstance(skills, list)
        self.assertGreater(len(skills), 0)
        # "test" keyword in the objective/handoff should map to test skill
        self.assertIn("test", skills)


# ---------------------------------------------------------------------------
# T3: SHA-256 integrity verification
# ---------------------------------------------------------------------------


class T3_SHA256IntegrityVerification(unittest.TestCase):
    """T3: SHA-256 hash — tampered state → load_checkpoint returns None."""

    def setUp(self) -> None:
        self._work_dir = tempfile.mkdtemp(prefix="le_t3_")
        self.manager = CheckpointManager(storage_path=self._work_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self._work_dir, ignore_errors=True)

    def _save_sample(self, task_id: str = "integrity-task") -> Checkpoint:
        cp = Checkpoint(
            task_id=task_id,
            step_id="step-1",
            step_name="Integrity check",
            agent_id="tester",
            status=CheckpointStatus.ACTIVE,
            completed_steps=["s1"],
            remaining_steps=["s2"],
            progress_percentage=50.0,
            context_snapshot={"key": "value"},
        )
        self.assertTrue(self.manager.save_checkpoint(cp))
        return cp

    def test_01_save_load_preserves_integrity(self) -> None:
        """Verify: save_checkpoint → load_checkpoint succeeds when file is untampered."""
        cp = self._save_sample()
        loaded = self.manager.load_checkpoint(cp.checkpoint_id)
        self.assertIsNotNone(loaded, "Untampered checkpoint must load successfully")
        self.assertEqual(loaded.checkpoint_id, cp.checkpoint_id)
        self.assertEqual(loaded.context_snapshot, {"key": "value"})

    def test_02_tampered_checkpoint_content_load_returns_none(self) -> None:
        """Verify: modifying checkpoint file content on disk → load returns None (hash mismatch)."""
        cp = self._save_sample()
        path = self.manager.checkpoints_dir / f"{cp.checkpoint_id}.json"
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        data["context_snapshot"]["key"] = "tampered"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)

        loaded = self.manager.load_checkpoint(cp.checkpoint_id)
        self.assertIsNone(loaded, "Tampered checkpoint must fail integrity check and return None")

    def test_03_tampered_hash_field_load_returns_none(self) -> None:
        """Verify: corrupting the stored checkpoint_hash → load returns None."""
        cp = self._save_sample()
        path = self.manager.checkpoints_dir / f"{cp.checkpoint_id}.json"
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        data["checkpoint_hash"] = "0" * 64
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)

        loaded = self.manager.load_checkpoint(cp.checkpoint_id)
        self.assertIsNone(loaded, "Hash mismatch must cause load to return None")

    def test_04_corrupted_json_file_load_returns_none(self) -> None:
        """Verify: invalid JSON in checkpoint file → load returns None (graceful, no exception)."""
        cp = self._save_sample()
        path = self.manager.checkpoints_dir / f"{cp.checkpoint_id}.json"
        with open(path, "w", encoding="utf-8") as f:
            f.write("{ this is not valid json,,,")

        loaded = self.manager.load_checkpoint(cp.checkpoint_id)
        self.assertIsNone(loaded, "Corrupted JSON must not raise; load returns None")


# ---------------------------------------------------------------------------
# T4: Lifecycle state persistence across sessions
# ---------------------------------------------------------------------------


class T4_LifecycleStatePersistenceIntegration(unittest.TestCase):
    """T4: save_lifecycle_state → list → load → delete roundtrip across sessions."""

    def setUp(self) -> None:
        self._work_dir = tempfile.mkdtemp(prefix="le_t4_")
        self.manager = CheckpointManager(storage_path=self._work_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self._work_dir, ignore_errors=True)

    def test_01_save_load_lifecycle_state_roundtrip(self) -> None:
        """Verify: save_lifecycle_state → load_lifecycle_state preserves all fields."""
        phase_states = {"P1": "completed", "P2": "running", "P3": "pending"}
        completed = ["P1"]
        ok = self.manager.save_lifecycle_state(
            task_id="task-rt",
            current_phase="P2",
            phase_states=phase_states,
            completed_phases=completed,
            mode="shortcut",
        )
        self.assertTrue(ok)
        loaded = self.manager.load_lifecycle_state("task-rt")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["current_phase"], "P2")
        self.assertEqual(loaded["phase_states"], phase_states)
        self.assertEqual(loaded["completed_phases"], completed)
        self.assertEqual(loaded["mode"], "shortcut")

    def test_02_list_lifecycle_states_multiple_tasks(self) -> None:
        """Verify: list_lifecycle_states returns all saved tasks, sorted by saved_at descending."""
        self.manager.save_lifecycle_state(
            task_id="task-a", current_phase="P1", phase_states={"P1": "running"},
            completed_phases=[], mode="shortcut",
        )
        time.sleep(0.02)
        self.manager.save_lifecycle_state(
            task_id="task-b", current_phase="P2", phase_states={"P2": "running"},
            completed_phases=["P1"], mode="full",
        )
        time.sleep(0.02)
        self.manager.save_lifecycle_state(
            task_id="task-c", current_phase="P3", phase_states={"P3": "running"},
            completed_phases=["P1", "P2"], mode="shortcut",
        )

        states = self.manager.list_lifecycle_states()
        self.assertEqual(len(states), 3)
        task_ids = [s["task_id"] for s in states]
        self.assertIn("task-a", task_ids)
        self.assertIn("task-b", task_ids)
        self.assertIn("task-c", task_ids)
        # Most recently saved should be first (descending by saved_at)
        self.assertEqual(states[0]["task_id"], "task-c")

    def test_03_delete_lifecycle_state(self) -> None:
        """Verify: delete_lifecycle_state removes state; subsequent load returns None."""
        self.manager.save_lifecycle_state(
            task_id="task-del", current_phase="P1", phase_states={"P1": "running"},
            completed_phases=[], mode="shortcut",
        )
        self.assertIsNotNone(self.manager.load_lifecycle_state("task-del"))
        self.assertTrue(self.manager.delete_lifecycle_state("task-del"))
        self.assertIsNone(self.manager.load_lifecycle_state("task-del"),
                          "After delete, load must return None")
        # Deleting again returns False (already gone)
        self.assertFalse(self.manager.delete_lifecycle_state("task-del"))

    def test_04_save_with_gate_results_and_metadata(self) -> None:
        """Verify: save with gate_results + metadata → load preserves them."""
        gate_results = {"P1": {"passed": True, "verdict": "APPROVE"}}
        metadata = {"adapter_type": "full", "execution_order": ["P1", "P2", "P3"]}
        self.manager.save_lifecycle_state(
            task_id="task-meta", current_phase="P2",
            phase_states={"P1": "completed", "P2": "running"},
            completed_phases=["P1"], mode="full",
            gate_results=gate_results, metadata=metadata,
        )
        loaded = self.manager.load_lifecycle_state("task-meta")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["gate_results"], gate_results)
        self.assertEqual(loaded["metadata"], metadata)
        self.assertEqual(loaded["version"], "3.8.0")


# ---------------------------------------------------------------------------
# T5: Auto-cleanup of old checkpoints
# ---------------------------------------------------------------------------


class T5_AutoCleanupIntegration(unittest.TestCase):
    """T5: cleanup_expired_checkpoints removes old files, keeps recent ones."""

    def setUp(self) -> None:
        self._work_dir = tempfile.mkdtemp(prefix="le_t5_")
        self.manager = CheckpointManager(storage_path=self._work_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self._work_dir, ignore_errors=True)

    def _save_checkpoint(self, task_id: str) -> Checkpoint:
        cp = Checkpoint(
            task_id=task_id,
            step_id=f"step-{task_id}",
            step_name=task_id,
            agent_id="cleanup-test",
            status=CheckpointStatus.ACTIVE,
            completed_steps=["s1"],
            remaining_steps=["s2"],
            progress_percentage=50.0,
        )
        self.manager.save_checkpoint(cp)
        return cp

    def test_01_cleanup_removes_old_checkpoints(self) -> None:
        """Verify: checkpoints older than max_age_hours are deleted by cleanup."""
        old_cp = self._save_checkpoint("old-task")
        recent_cp = self._save_checkpoint("recent-task")
        # Backdate the old checkpoint file mtime by 48 hours
        old_path = self.manager.checkpoints_dir / f"{old_cp.checkpoint_id}.json"
        old_time = time.time() - 48 * 3600
        os.utime(old_path, (old_time, old_time))

        removed = self.manager.cleanup_expired_checkpoints(max_age_hours=24)
        self.assertEqual(removed, 1, "Exactly one old checkpoint should be removed")
        self.assertIsNone(self.manager.load_checkpoint(old_cp.checkpoint_id))
        self.assertIsNotNone(self.manager.load_checkpoint(recent_cp.checkpoint_id),
                             "Recent checkpoint must survive cleanup")

    def test_02_cleanup_keeps_recent_checkpoints(self) -> None:
        """Verify: checkpoints newer than max_age_hours are retained."""
        cp1 = self._save_checkpoint("keep-1")
        cp2 = self._save_checkpoint("keep-2")
        removed = self.manager.cleanup_expired_checkpoints(max_age_hours=24)
        self.assertEqual(removed, 0, "No recent checkpoints should be removed")
        self.assertIsNotNone(self.manager.load_checkpoint(cp1.checkpoint_id))
        self.assertIsNotNone(self.manager.load_checkpoint(cp2.checkpoint_id))

    def test_03_cleanup_returns_count_of_removed(self) -> None:
        """Verify: cleanup_expired_checkpoints returns the count of removed files."""
        cps = [self._save_checkpoint(f"count-{i}") for i in range(3)]
        cutoff = time.time() - 25 * 3600
        for cp in cps:
            path = self.manager.checkpoints_dir / f"{cp.checkpoint_id}.json"
            os.utime(path, (cutoff, cutoff))

        removed = self.manager.cleanup_expired_checkpoints(max_age_hours=24)
        self.assertEqual(removed, 3, "All three backdated checkpoints should be removed")

    def test_04_cleanup_empty_dir_returns_zero(self) -> None:
        """Verify: cleanup on a directory with no checkpoints returns 0."""
        removed = self.manager.cleanup_expired_checkpoints(max_age_hours=24)
        self.assertEqual(removed, 0, "Empty checkpoints dir → cleanup returns 0")


# ---------------------------------------------------------------------------
# T6: ShortcutLifecycleAdapter integration
# ---------------------------------------------------------------------------


class T6_ShortcutLifecycleAdapterIntegration(unittest.TestCase):
    """T6: ShortcutLifecycleAdapter + CheckpointManager — CLI shortcuts → lifecycle state."""

    def setUp(self) -> None:
        self._work_dir = tempfile.mkdtemp(prefix="le_t6_")

    def tearDown(self) -> None:
        shutil.rmtree(self._work_dir, ignore_errors=True)

    def _make_adapter(self, task_id: str) -> ShortcutLifecycleAdapter:
        adapter = ShortcutLifecycleAdapter(use_unified_gate=False)
        self.assertTrue(adapter.enable_checkpoint_integration(storage_path=self._work_dir),
                        "enable_checkpoint_integration must succeed with a valid path")
        adapter.set_task_id(task_id)
        return adapter

    def _first_no_dep_phase(self, adapter: ShortcutLifecycleAdapter) -> str:
        """Find the first phase with no dependencies (safe to advance without prereqs)."""
        for phase in adapter.get_all_phases():
            if not phase.dependencies:
                return phase.phase_id
        # Fallback: P1 should always exist
        return "P1"

    def test_01_enable_checkpoint_integration_returns_true(self) -> None:
        """Verify: enable_checkpoint_integration wires up a CheckpointManager."""
        adapter = ShortcutLifecycleAdapter(use_unified_gate=False)
        self.assertTrue(adapter.enable_checkpoint_integration(storage_path=self._work_dir))
        # CheckpointManager creates checkpoints/ and handoffs/ subdirs on init
        self.assertTrue((Path(self._work_dir) / "checkpoints").exists())
        self.assertTrue((Path(self._work_dir) / "handoffs").exists())
        # The adapter must have a checkpoint manager wired up
        self.assertIsNotNone(adapter._checkpoint_manager)

    def test_02_advance_phase_save_restore_roundtrip(self) -> None:
        """Verify: advance_to_phase → save_state → fresh adapter restore_state → phase restored."""
        adapter = self._make_adapter("task-advance")
        target = self._first_no_dep_phase(adapter)
        result = adapter.advance_to_phase(target)
        self.assertTrue(result.success, f"advance_to_phase({target}) should succeed")
        self.assertTrue(adapter.save_state(), "save_state must succeed")

        # New adapter instance representing a fresh session
        adapter2 = self._make_adapter("task-advance")
        self.assertTrue(adapter2.restore_state(), "restore_state must succeed on fresh adapter")
        self.assertEqual(adapter2.get_status().current_phase, target,
                         "Restored adapter must have the same current_phase")

    def test_03_complete_phase_persisted_across_sessions(self) -> None:
        """Verify: complete_phase → save → restore → completed_phases preserved."""
        adapter = self._make_adapter("task-complete")
        target = self._first_no_dep_phase(adapter)
        adapter.advance_to_phase(target)
        adapter.complete_phase(target)
        self.assertIn(target, adapter.get_status().completed_phases)
        self.assertTrue(adapter.save_state())

        adapter2 = self._make_adapter("task-complete")
        self.assertTrue(adapter2.restore_state())
        self.assertIn(target, adapter2.get_status().completed_phases,
                      "Completed phase must survive save/restore across sessions")

    def test_04_create_checkpoint_from_lifecycle_protocol(self) -> None:
        """Verify: create_checkpoint_from_lifecycle bridges protocol state → Checkpoint."""
        adapter = self._make_adapter("task-bridge")
        manager = CheckpointManager(storage_path=self._work_dir)
        target = self._first_no_dep_phase(adapter)
        adapter.advance_to_phase(target)
        adapter.complete_phase(target)

        cp = manager.create_checkpoint_from_lifecycle("task-bridge", protocol=adapter)
        self.assertIsNotNone(cp, "create_checkpoint_from_lifecycle must produce a Checkpoint")
        self.assertEqual(cp.task_id, "task-bridge")
        self.assertIn(target, cp.completed_steps,
                      "Completed phase must appear in checkpoint.completed_steps")
        # Checkpoint is persisted — load it back
        loaded = manager.load_checkpoint(cp.checkpoint_id)
        self.assertIsNotNone(loaded, "Lifecycle-derived checkpoint must persist and load")
        self.assertEqual(loaded.agent_id, "lifecycle-protocol")

    def test_05_set_task_id_enables_state_roundtrip(self) -> None:
        """Verify: set_task_id + enable_checkpoint_integration → save/restore roundtrip works."""
        adapter = self._make_adapter("task-id-test")
        target = self._first_no_dep_phase(adapter)
        adapter.advance_to_phase(target)
        adapter.complete_phase(target)
        self.assertTrue(adapter.save_state())

        # Verify the lifecycle state file exists on disk
        state_file = Path(self._work_dir) / "lifecycle" / "task-id-test_lifecycle.json"
        self.assertTrue(state_file.exists(), "Lifecycle state JSON must be written to disk")

        adapter2 = self._make_adapter("task-id-test")
        self.assertTrue(adapter2.restore_state())
        status = adapter2.get_status()
        self.assertEqual(status.mode, LifecycleMode.SHORTCUT)


# ---------------------------------------------------------------------------
# T7: Edge cases + graceful degradation
# ---------------------------------------------------------------------------


class T7_EdgeCasesAndGracefulDegradationIntegration(unittest.TestCase):
    """T7: Empty state, missing checkpoint, corrupted file, failing dispatcher."""

    def setUp(self) -> None:
        self._work_dir = tempfile.mkdtemp(prefix="le_t7_")
        self.manager = CheckpointManager(storage_path=self._work_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self._work_dir, ignore_errors=True)

    def test_01_load_nonexistent_checkpoint_returns_none(self) -> None:
        """Verify: load_checkpoint with unknown id returns None (no crash)."""
        self.assertIsNone(self.manager.load_checkpoint("does-not-exist"))

    def test_02_load_nonexistent_handoff_returns_none(self) -> None:
        """Verify: load_handoff with unknown id returns None (no crash)."""
        self.assertIsNone(self.manager.load_handoff("no-such-handoff"))

    def test_03_empty_handoff_content_suggest_skills_default(self) -> None:
        """Verify: suggest_skills with empty/whitespace content returns default ['dispatch']."""
        self.assertEqual(self.manager.suggest_skills(""), ["dispatch"])
        self.assertEqual(self.manager.suggest_skills("   \n\t  "), ["dispatch"])

    def test_04_loop_with_failing_dispatcher_graceful_degradation(self) -> None:
        """Verify: HandoffAdapter with a raising dispatcher → status='error', loop continues."""
        failing_dispatcher = MagicMock()
        failing_dispatcher.dispatch.side_effect = RuntimeError("external service down")
        adapter = HandoffAdapter(dispatcher=failing_dispatcher)
        result = adapter.dispatch(
            {"tasks": ["implement"], "focus": "do work", "iter_index": 0}, 0,
        )
        self.assertEqual(result["status"], "error")
        self.assertIn("external service down", result["error"])

        # The loop kernel must tolerate the error handoff: with STANDARD evaluator,
        # an error-status handoff produces verification errors but the loop runs.
        mem_dir = Path(self._work_dir) / "loop_mem"
        memory = UnifiedMemory(storage_dir=str(mem_dir))
        config = LoopEngineeringConfig(
            evaluator_mode=EvaluatorMode.STANDARD,
            max_iterations=2,
            human_checkpoint_every=0,
        )
        kernel = LoopKernel(
            config=config,
            discovery_probe=_CompletingDiscoveryProbe(),
            handoff_adapter=adapter,
            memory=memory,
        )
        report = kernel.run("Build with failing dispatcher")
        self.assertIsInstance(report, LoopRunReport)
        # First cycle handoff must carry the error status
        self.assertEqual(report.cycles[0].handoff["status"], "error")

    def test_05_checkpoint_path_traversal_rejected(self) -> None:
        """Verify: checkpoint IDs with path traversal separators are rejected (load returns None)."""
        # load_checkpoint catches the ValueError from _validate_id and returns
        # None gracefully — callers never see path-traversal files leak through.
        self.assertIsNone(self.manager.load_checkpoint("../etc/passwd"),
                          "Path-traversal ID must be rejected (load returns None)")
        self.assertIsNone(self.manager.load_checkpoint("sub/dir"),
                          "Slash-containing ID must be rejected (load returns None)")
        # The internal validator raises ValueError directly (defence in depth)
        with self.assertRaises(ValueError):
            self.manager._validate_id("../etc/passwd")

    def test_06_redact_sensitive_info_in_handoff_markdown(self) -> None:
        """Verify: save_handoff redacts API keys and emails from the Markdown output."""
        doc = HandoffDocument(
            task_id="redact-task",
            from_agent="agent-a",
            to_agent="agent-b",
            completed_work=["Set up API with sk-secret-key-12345"],
            current_state={"email": "admin@example.com"},
            next_steps=["Configure token: abc123"],
            important_notes=["Password: hunter2"],
        )
        self.assertTrue(self.manager.save_handoff(doc))
        md_path = self.manager.handoffs_dir / f"{doc.handoff_id}.md"
        md_content = md_path.read_text(encoding="utf-8")
        self.assertNotIn("sk-secret-key-12345", md_content,
                         "API key must be redacted from handoff Markdown")
        self.assertNotIn("admin@example.com", md_content,
                         "Email must be masked in handoff Markdown")
        self.assertNotIn("hunter2", md_content,
                         "Password must be redacted from handoff Markdown")


if __name__ == "__main__":
    unittest.main()
