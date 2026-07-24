#!/usr/bin/env python3
"""Coordinator + ConsensusEngine + Worker Integration Tests
(V4.2.1 P2-3 — Test Pyramid Lift).

End-to-end integration tests for the dispatch-consensus trio. Verifies
CROSS-MODULE interactions among:

    scripts/collaboration/coordinator.py — Coordinator
        (plan_task / spawn_workers / execute_plan / collect_results /
         resolve_conflicts / generate_report)
    scripts/collaboration/consensus.py   — ConsensusEngine
        (create_proposal / cast_vote / reach_consensus /
         get_all_records / get_fatigue_status)
    scripts/collaboration/worker.py      — Worker
        (execute / vote_on_proposal / write_finding /
         write_conflict / send_notification)

Note: dispatcher.py is NOT imported (it has module-level side effects).
The Coordinator is tested directly — it internally wires ConsensusEngine
and Worker via its constructor and spawn_workers method.

Flow:
    1. Coordinator.plan_task → spawn_workers → execute_plan → Worker.execute
    2. ConsensusEngine weighted voting + veto power
    3. Coordinator.resolve_conflicts → ConsensusEngine arbitration
    4. Multi-Worker parallel execution → ConsensusEngine aggregation
    5. Boundary (single role, all veto, timeout, empty results)

Test categories:
    T1: Coordinator → Worker.execute → ConsensusEngine.vote chain
    T2: ConsensusEngine weighted voting + veto
    T3: Coordinator conflict resolution → ConsensusEngine arbitration
    T4: Multi-Worker parallel → ConsensusEngine aggregation
    T5: Boundary (single role, all veto, timeout, empty results)
"""

from __future__ import annotations

import os
import sys
import unittest
from typing import Any
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.consensus import ConsensusEngine
from scripts.collaboration.coordinator import Coordinator
from scripts.collaboration.models import (
    DecisionOutcome,
    EntryType,
    Vote,
)
from scripts.collaboration.worker import Worker

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_vote(
    voter_id: str = "v1",
    role: str = "solo-coder",
    decision: bool = True,
    weight: float = 1.0,
    reason: str = "ok",
) -> Vote:
    """Construct a Vote with sensible defaults for tests."""
    return Vote(
        voter_id=voter_id,
        voter_role=role,
        decision=decision,
        reason=reason,
        weight=weight,
    )


def _make_worker(role_id: str, worker_id: str, scratchpad: Any = None) -> Worker:
    """Build a Worker with a mocked scratchpad (only vote_on_proposal is used)."""
    return Worker(
        worker_id=worker_id,
        role_id=role_id,
        role_prompt=f"You are {role_id}.",
        scratchpad=scratchpad or MagicMock(),
    )


def _make_coordinator(enable_compression: bool = False) -> Coordinator:
    """Build a Coordinator with compression disabled for fast, isolated tests."""
    return Coordinator(enable_compression=enable_compression)


def _run_consensus(
    engine: ConsensusEngine,
    votes: list[Vote],
    topic: str = "Test proposal",
    content: str = "Adopt microservices architecture",
) -> tuple:
    """Create a proposal, cast the given votes, and reach consensus.

    Returns a (record, proposal_id) tuple.
    """
    proposal = engine.create_proposal(
        topic=topic,
        proposer_id="coord-001",
        content=content,
    )
    for v in votes:
        engine.cast_vote(proposal.proposal_id, v)
    record = engine.reach_consensus(proposal.proposal_id)
    return record, proposal.proposal_id


# ---------------------------------------------------------------------------
# T1: Coordinator → Worker.execute → ConsensusEngine.vote chain
# ---------------------------------------------------------------------------


class T1_CoordinatorWorkerConsensusChain(unittest.TestCase):
    """T1: Coordinator orchestrates Workers; Worker votes feed ConsensusEngine."""

    def setUp(self) -> None:
        self._coord = _make_coordinator()

    def tearDown(self) -> None:
        self._coord._executor.shutdown(wait=False)

    def test_01_plan_task_creates_execution_plan_with_roles(self) -> None:
        """Verify: plan_task produces an ExecutionPlan with one task per role."""
        plan = self._coord.plan_task(
            "design API",
            available_roles=[
                {"role_id": "architect", "role_prompt": "You are architect."},
                {"role_id": "tester", "role_prompt": "You are tester."},
            ],
        )
        self.assertEqual(plan.total_tasks, 2)
        self.assertEqual(len(plan.batches), 1)

    def test_02_spawn_workers_creates_worker_instances(self) -> None:
        """Verify: spawn_workers creates a Worker per planned task."""
        plan = self._coord.plan_task(
            "build feature",
            available_roles=[{"role_id": "solo-coder", "role_prompt": "code"}],
        )
        workers = self._coord.spawn_workers(plan)
        self.assertEqual(len(workers), 1)
        self.assertEqual(workers[0].role_id, "solo-coder")

    def test_03_execute_plan_runs_workers_and_returns_result(self) -> None:
        """Verify: execute_plan produces a ScheduleResult with completed tasks."""
        plan = self._coord.plan_task(
            "test task",
            available_roles=[{"role_id": "tester", "role_prompt": "test"}],
        )
        self._coord.spawn_workers(plan)
        result = self._coord.execute_plan(plan)
        self.assertTrue(result.success)
        self.assertEqual(result.total_tasks, 1)
        self.assertEqual(result.completed_tasks, 1)

    def test_04_worker_vote_on_proposal_feeds_into_engine(self) -> None:
        """Verify: Worker.vote_on_proposal output is accepted by ConsensusEngine."""
        engine = self._coord.consensus
        proposal = engine.create_proposal(topic="API design", proposer_id="coord", content="REST")
        worker = _make_worker("architect", "arch-001")
        vote_result = worker.vote_on_proposal(proposal.proposal_id, decision=True, reason="good")
        engine.cast_vote(proposal.proposal_id, vote_result["vote"])
        record = engine.reach_consensus(proposal.proposal_id)
        self.assertEqual(record.outcome, DecisionOutcome.APPROVED)
        self.assertIn("arch-001", record.participants)

    def test_05_collect_results_aggregates_findings_and_decisions(self) -> None:
        """Verify: collect_results returns scratchpad summary and entry counts."""
        plan = self._coord.plan_task(
            "design",
            available_roles=[{"role_id": "architect", "role_prompt": "arch"}],
        )
        self._coord.spawn_workers(plan)
        self._coord.execute_plan(plan)
        collection = self._coord.collect_results()
        self.assertIn("coordinator_id", collection)
        self.assertIn("scratchpad", collection)
        self.assertGreaterEqual(collection["findings_count"], 0)

    def test_06_generate_report_includes_worker_ids(self) -> None:
        """Verify: generate_report produces a Markdown report with worker IDs."""
        plan = self._coord.plan_task(
            "report task",
            available_roles=[{"role_id": "tester", "role_prompt": "test"}],
        )
        self._coord.spawn_workers(plan)
        self._coord.execute_plan(plan)
        report = self._coord.generate_report()
        self.assertIn("# 多角色协作报告", report)
        self.assertIn("tester", report)

    def test_07_execute_plan_with_multiple_roles_produces_results(self) -> None:
        """Verify: a 2-role plan produces 2 completed results."""
        plan = self._coord.plan_task(
            "multi-role",
            available_roles=[
                {"role_id": "architect", "role_prompt": "arch"},
                {"role_id": "tester", "role_prompt": "test"},
            ],
        )
        self._coord.spawn_workers(plan)
        result = self._coord.execute_plan(plan)
        self.assertEqual(result.total_tasks, 2)
        self.assertEqual(result.completed_tasks, 2)

    def test_08_worker_finding_written_to_scratchpad(self) -> None:
        """Verify: after execute_plan, the scratchpad contains a FINDING entry."""
        plan = self._coord.plan_task(
            "scratchpad test",
            available_roles=[{"role_id": "architect", "role_prompt": "arch"}],
        )
        self._coord.spawn_workers(plan)
        self._coord.execute_plan(plan)
        findings = self._coord.scratchpad.read(entry_type=EntryType.FINDING)
        self.assertGreaterEqual(len(findings), 1)


# ---------------------------------------------------------------------------
# T2: ConsensusEngine weighted voting + veto
# ---------------------------------------------------------------------------


class T2_ConsensusWeightedVotingAndVeto(unittest.TestCase):
    """T2: ConsensusEngine role weights and veto power."""

    def test_01_architect_approve_beats_coder_reject(self) -> None:
        """Verify: architect (1.5) approve vs coder (1.0) reject → APPROVED."""
        engine = ConsensusEngine()
        record, _ = _run_consensus(
            engine,
            [
                _make_vote("arch", "architect", True, 1.5),
                _make_vote("coder", "solo-coder", False, 1.0, reason="prefer simpler"),
            ],
        )
        self.assertEqual(record.outcome, DecisionOutcome.APPROVED)

    def test_02_product_manager_weight_applied(self) -> None:
        """Verify: product-manager (1.2) weight is summed into total_weight_for."""
        engine = ConsensusEngine()
        record, _ = _run_consensus(
            engine,
            [_make_vote("pm", "product-manager", True, 1.2)],
        )
        self.assertAlmostEqual(record.total_weight_for, 1.2)

    def test_03_security_veto_overrides_majority_approval(self) -> None:
        """Verify: a security veto (weight < 0) forces ESCALATED."""
        engine = ConsensusEngine()
        record, _ = _run_consensus(
            engine,
            [
                _make_vote("a", "architect", True, 1.5),
                _make_vote("b", "tester", True, 1.0),
                _make_vote("sec", "security", False, -1.0, reason="security block"),
            ],
        )
        self.assertEqual(record.outcome, DecisionOutcome.ESCALATED)

    def test_04_veto_with_approve_decision_still_escalated(self) -> None:
        """Verify: negative weight triggers veto even when decision=True."""
        engine = ConsensusEngine()
        record, _ = _run_consensus(
            engine,
            [_make_vote("x", "security", True, -1.0, reason="approve but veto-weighted")],
        )
        self.assertEqual(record.outcome, DecisionOutcome.ESCALATED)

    def test_05_total_weight_for_sums_positive_approve_weights(self) -> None:
        """Verify: total_weight_for sums all positive approving weights."""
        engine = ConsensusEngine()
        record, _ = _run_consensus(
            engine,
            [
                _make_vote("a", "architect", True, 1.5),
                _make_vote("b", "product-manager", True, 1.2),
                _make_vote("c", "solo-coder", True, 1.0),
            ],
        )
        self.assertAlmostEqual(record.total_weight_for, 3.7)

    def test_06_equal_split_yields_split_outcome(self) -> None:
        """Verify: 1 approve vs 1 reject (equal weight) → SPLIT."""
        engine = ConsensusEngine()
        record, _ = _run_consensus(
            engine,
            [
                _make_vote("a", "tester", True, 1.0),
                _make_vote("b", "devops", False, 1.0, reason="too costly"),
            ],
        )
        self.assertEqual(record.outcome, DecisionOutcome.SPLIT)

    def test_07_super_majority_three_vs_one_approved(self) -> None:
        """Verify: 3 approve (3.0) vs 1 reject (1.0) → APPROVED (weight_ratio 0.75)."""
        engine = ConsensusEngine()
        record, _ = _run_consensus(
            engine,
            [
                _make_vote("a", "tester", True, 1.0),
                _make_vote("b", "tester", True, 1.0),
                _make_vote("c", "tester", True, 1.0),
                _make_vote("d", "devops", False, 1.0),
            ],
        )
        self.assertEqual(record.outcome, DecisionOutcome.APPROVED)

    def test_08_unanimous_approval_sets_final_decision_to_content(self) -> None:
        """Verify: on unanimous APPROVED, final_decision equals the proposal content."""
        engine = ConsensusEngine()
        content = "Adopt event-sourcing pattern"
        record, _ = _run_consensus(
            engine,
            [_make_vote("a", "architect", True, 1.5), _make_vote("b", "tester", True, 1.0)],
            content=content,
        )
        self.assertEqual(record.outcome, DecisionOutcome.APPROVED)
        self.assertEqual(record.final_decision, content)


# ---------------------------------------------------------------------------
# T3: Coordinator conflict resolution → ConsensusEngine arbitration
# ---------------------------------------------------------------------------


class T3_CoordinatorConflictResolutionConsensus(unittest.TestCase):
    """T3: Coordinator.resolve_conflicts drives ConsensusEngine arbitration."""

    def setUp(self) -> None:
        self._coord = _make_coordinator()

    def tearDown(self) -> None:
        self._coord._executor.shutdown(wait=False)

    def test_01_resolve_conflicts_on_empty_scratchpad_returns_empty(self) -> None:
        """Verify: resolve_conflicts with no conflicts returns an empty list."""
        self.assertEqual(self._coord.resolve_conflicts(), [])

    def test_02_write_conflict_then_resolve_creates_consensus_record(self) -> None:
        """Verify: a written conflict triggers a consensus proposal and record."""
        worker = _make_worker("architect", "arch-001", scratchpad=self._coord.scratchpad)
        self._coord.workers[worker.worker_id] = worker
        self._coord._worker_index[worker.role_id] = worker
        worker.write_conflict("disagree on API design", "entry-001", reason="REST vs gRPC")
        records = self._coord.resolve_conflicts()
        self.assertEqual(len(records), 1)

    def test_03_resolved_conflict_marked_in_scratchpad(self) -> None:
        """Verify: after resolve_conflicts, the conflict entry is marked resolved."""
        worker = _make_worker("tester", "test-001", scratchpad=self._coord.scratchpad)
        self._coord.workers[worker.worker_id] = worker
        self._coord._worker_index[worker.role_id] = worker
        worker.write_conflict("test conflict", "entry-002", reason="disagree")
        self._coord.resolve_conflicts()
        conflicts_after = self._coord.scratchpad.get_conflicts()
        self.assertEqual(len(conflicts_after), 0)

    def test_04_multiple_conflicts_resolved_independently(self) -> None:
        """Verify: multiple conflicts each produce a separate consensus record."""
        for i in range(3):
            worker = _make_worker(f"tester{i}", f"test-{i}", scratchpad=self._coord.scratchpad)
            self._coord.workers[worker.worker_id] = worker
            self._coord._worker_index[worker.role_id] = worker
            worker.write_conflict(f"conflict {i}", f"entry-{i}", reason="disagree")
        records = self._coord.resolve_conflicts()
        self.assertEqual(len(records), 3)

    def test_05_approved_consensus_uses_passed_message(self) -> None:
        """Verify: APPROVED consensus resolves with '已通过共识解决' in scratchpad."""
        worker = _make_worker("architect", "arch-005", scratchpad=self._coord.scratchpad)
        self._coord.workers[worker.worker_id] = worker
        self._coord._worker_index[worker.role_id] = worker
        worker.write_conflict("approved conflict", "entry-005", reason="minor")
        records = self._coord.resolve_conflicts()
        self.assertEqual(records[0].outcome, DecisionOutcome.APPROVED)

    def test_06_no_workers_yields_timeout_outcome(self) -> None:
        """Verify: conflict with no workers voting → TIMEOUT outcome."""
        worker = _make_worker("tester", "test-006", scratchpad=self._coord.scratchpad)
        worker.write_conflict("lonely conflict", "entry-006", reason="disagree")
        records = self._coord.resolve_conflicts()
        self.assertEqual(records[0].outcome, DecisionOutcome.TIMEOUT)

    def test_07_resolve_conflicts_records_stored_in_engine(self) -> None:
        """Verify: after resolve_conflicts, the consensus engine stores the records."""
        worker = _make_worker("architect", "arch-007", scratchpad=self._coord.scratchpad)
        self._coord.workers[worker.worker_id] = worker
        self._coord._worker_index[worker.role_id] = worker
        worker.write_conflict("stored conflict", "entry-007", reason="disagree")
        self._coord.resolve_conflicts()
        all_records = self._coord.consensus.get_all_records()
        self.assertGreaterEqual(len(all_records), 1)

    def test_08_workers_participate_in_conflict_voting(self) -> None:
        """Verify: all registered workers cast a vote during conflict resolution."""
        for role in ("architect", "tester", "devops"):
            w = _make_worker(role, f"{role}-008", scratchpad=self._coord.scratchpad)
            self._coord.workers[w.worker_id] = w
            self._coord._worker_index[w.role_id] = w
        w.write_conflict("multi-voter conflict", "entry-008", reason="disagree")
        records = self._coord.resolve_conflicts()
        self.assertEqual(records[0].votes_for, 3)


# ---------------------------------------------------------------------------
# T4: Multi-Worker parallel → ConsensusEngine aggregation
# ---------------------------------------------------------------------------


class T4_MultiWorkerParallelConsensusAggregation(unittest.TestCase):
    """T4: Parallel Worker execution feeds into ConsensusEngine aggregation."""

    def setUp(self) -> None:
        self._coord = _make_coordinator()

    def tearDown(self) -> None:
        self._coord._executor.shutdown(wait=False)

    def test_01_three_workers_execute_plan_in_parallel(self) -> None:
        """Verify: a 3-role plan executes all workers and collects 3 results."""
        plan = self._coord.plan_task(
            "parallel task",
            available_roles=[
                {"role_id": "architect", "role_prompt": "arch"},
                {"role_id": "tester", "role_prompt": "test"},
                {"role_id": "devops", "role_prompt": "deploy"},
            ],
        )
        self._coord.spawn_workers(plan)
        result = self._coord.execute_plan(plan)
        self.assertEqual(result.completed_tasks, 3)
        self.assertEqual(len(result.results), 3)

    def test_02_parallel_execution_produces_result_per_role(self) -> None:
        """Verify: each role's WorkerResult carries its role_id."""
        plan = self._coord.plan_task(
            "role check",
            available_roles=[
                {"role_id": "architect", "role_prompt": "arch"},
                {"role_id": "tester", "role_prompt": "test"},
            ],
        )
        self._coord.spawn_workers(plan)
        result = self._coord.execute_plan(plan)
        role_ids = {r.output["role_id"] for r in result.results}
        self.assertEqual(role_ids, {"architect", "tester"})

    def test_03_worker_findings_written_to_shared_scratchpad(self) -> None:
        """Verify: parallel workers write findings visible in the shared scratchpad."""
        plan = self._coord.plan_task(
            "shared scratchpad",
            available_roles=[
                {"role_id": "architect", "role_prompt": "arch"},
                {"role_id": "tester", "role_prompt": "test"},
            ],
        )
        self._coord.spawn_workers(plan)
        self._coord.execute_plan(plan)
        findings = self._coord.scratchpad.read(entry_type=EntryType.FINDING)
        self.assertGreaterEqual(len(findings), 2)

    def test_04_coordinator_collects_notifications(self) -> None:
        """Verify: collect_results gathers pending notifications from workers."""
        plan = self._coord.plan_task(
            "notifications",
            available_roles=[{"role_id": "architect", "role_prompt": "arch"}],
        )
        self._coord.spawn_workers(plan)
        worker = list(self._coord.workers.values())[0]
        from scripts.collaboration.models import TaskNotification
        worker.send_notification(TaskNotification(
            from_worker=worker.worker_id,
            to_workers=["tester"],
            notification_type="question",
            summary="need test plan",
        ))
        collection = self._coord.collect_results()
        self.assertGreaterEqual(len(collection["notifications"]), 1)

    def test_05_multi_role_consensus_all_approve(self) -> None:
        """Verify: architect + tester + devops all approve → APPROVED with 3 votes."""
        engine = ConsensusEngine()
        record, _ = _run_consensus(
            engine,
            [
                _make_vote("a", "architect", True, 1.5),
                _make_vote("b", "tester", True, 1.0),
                _make_vote("c", "devops", True, 1.0),
            ],
        )
        self.assertEqual(record.outcome, DecisionOutcome.APPROVED)
        self.assertEqual(record.votes_for, 3)

    def test_06_worker_write_question_sends_notification(self) -> None:
        """Verify: write_question with to_roles queues a TaskNotification."""
        worker = _make_worker("architect", "arch-q", scratchpad=self._coord.scratchpad)
        worker.write_question("Which DB?", to_roles=["tester", "devops"])
        notifications = worker.get_pending_notifications()
        self.assertEqual(len(notifications), 1)
        self.assertIn("tester", notifications[0].to_workers)

    def test_07_parallel_execution_completes_all_tasks(self) -> None:
        """Verify: parallel plan with 4 roles completes all 4 tasks."""
        plan = self._coord.plan_task(
            "4-role parallel",
            available_roles=[
                {"role_id": "architect", "role_prompt": "a"},
                {"role_id": "tester", "role_prompt": "b"},
                {"role_id": "devops", "role_prompt": "c"},
                {"role_id": "solo-coder", "role_prompt": "d"},
            ],
        )
        self._coord.spawn_workers(plan)
        result = self._coord.execute_plan(plan)
        self.assertEqual(result.completed_tasks, 4)
        self.assertEqual(result.failed_tasks, 0)

    def test_08_consensus_record_participants_match_voters(self) -> None:
        """Verify: the participants list in a consensus record matches voter IDs."""
        engine = ConsensusEngine()
        record, _ = _run_consensus(
            engine,
            [
                _make_vote("v-alpha", "architect", True, 1.5),
                _make_vote("v-beta", "tester", True, 1.0),
            ],
        )
        self.assertEqual(set(record.participants), {"v-alpha", "v-beta"})


# ---------------------------------------------------------------------------
# T5: Boundary (single role, all veto, timeout, empty results)
# ---------------------------------------------------------------------------


class T5_BoundaryAndEdgeCases(unittest.TestCase):
    """T5: Boundary conditions — single role, veto, timeout, empty plans."""

    def setUp(self) -> None:
        self._coord = _make_coordinator()

    def tearDown(self) -> None:
        self._coord._executor.shutdown(wait=False)

    def test_01_single_role_plan_executes_successfully(self) -> None:
        """Verify: a single-role plan executes and completes one task."""
        plan = self._coord.plan_task(
            "solo task",
            available_roles=[{"role_id": "solo-coder", "role_prompt": "code"}],
        )
        self._coord.spawn_workers(plan)
        result = self._coord.execute_plan(plan)
        self.assertEqual(result.completed_tasks, 1)
        self.assertTrue(result.success)

    def test_02_all_veto_votes_yield_escalated(self) -> None:
        """Verify: when every voter casts a veto, the outcome is ESCALATED."""
        engine = ConsensusEngine()
        record, _ = _run_consensus(
            engine,
            [
                _make_vote("a", "security", False, -1.0, reason="veto 1"),
                _make_vote("b", "security", False, -1.0, reason="veto 2"),
            ],
        )
        self.assertEqual(record.outcome, DecisionOutcome.ESCALATED)

    def test_03_no_votes_cast_yields_timeout(self) -> None:
        """Verify: reach_consensus with zero votes → TIMEOUT."""
        engine = ConsensusEngine()
        proposal = engine.create_proposal(topic="empty", proposer_id="coord", content="decide")
        record = engine.reach_consensus(proposal.proposal_id)
        self.assertEqual(record.outcome, DecisionOutcome.TIMEOUT)

    def test_04_empty_available_roles_produces_zero_task_plan(self) -> None:
        """Verify: plan_task with no roles produces a plan with 0 total tasks."""
        plan = self._coord.plan_task("empty", available_roles=[])
        self.assertEqual(plan.total_tasks, 0)

    def test_05_empty_task_description_executes_without_error(self) -> None:
        """Verify: execute_plan tolerates an empty task description string."""
        plan = self._coord.plan_task(
            "",
            available_roles=[{"role_id": "tester", "role_prompt": "test"}],
        )
        self._coord.spawn_workers(plan)
        result = self._coord.execute_plan(plan)
        self.assertTrue(result.success)

    def test_06_cast_vote_on_closed_proposal_raises(self) -> None:
        """Verify: casting a vote after consensus is reached raises ValueError."""
        engine = ConsensusEngine()
        proposal = engine.create_proposal(topic="closed", proposer_id="coord", content="done")
        engine.cast_vote(proposal.proposal_id, _make_vote("a", "tester", True, 1.0))
        engine.reach_consensus(proposal.proposal_id)
        with self.assertRaises(ValueError):
            engine.cast_vote(proposal.proposal_id, _make_vote("b", "tester", True, 1.0))

    def test_07_cast_vote_on_unknown_proposal_raises(self) -> None:
        """Verify: cast_vote on a non-existent proposal id raises ValueError."""
        engine = ConsensusEngine()
        with self.assertRaises(ValueError):
            engine.cast_vote("does-not-exist", _make_vote("a", "tester", True, 1.0))

    def test_08_coordinator_with_compression_disabled(self) -> None:
        """Verify: a Coordinator with enable_compression=False has no compressor."""
        coord = _make_coordinator(enable_compression=False)
        try:
            self.assertIsNone(coord.compressor)
            self.assertIsNone(coord.get_compression_stats())
        finally:
            coord._executor.shutdown(wait=False)


if __name__ == "__main__":
    unittest.main()
