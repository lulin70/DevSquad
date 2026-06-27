#!/usr/bin/env python3
"""
Tests for ConsensusGate (硬约束 HC-2) — ConsensusEngine 前置介入关键决策点.

Verifies that ConsensusGate correctly wraps ConsensusEngine as a
pre-decision gate (not just a post-hoc conflict resolver), aligning
with the project hard constraint:
"ConsensusEngine必须作为核心决策机制前置介入所有关键决策点,
不可仅作为后置补救措施".

And the safe-degradation constraint:
"共识门在关键决策失败时必须安全降级,禁止fail-open直接执行".

Test layers:
  1. Happy path — all workers approve → gate passes
  2. Rejection — majority rejects → gate blocks
  3. Veto — any worker veto → gate blocks (ESCALATED)
  4. Split — divided opinions → gate passes with needs_review
  5. Safe degradation — ConsensusEngine exception → needs_review (not fail-open)
  6. Critical mode — exception in critical mode → gate blocks
  7. Empty workers — timeout → needs_review
"""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.consensus import ConsensusEngine
from scripts.collaboration.consensus_gate import ConsensusGate, ConsensusGateResult


def _make_worker_result(
    role_id: str, success: bool = True, output: str = "", error: str = ""
) -> dict:
    """Create a standardized worker result dict for testing."""
    return {
        "worker_id": f"{role_id}-001",
        "role_id": role_id,
        "role_name": role_id,
        "task_id": "task-001",
        "success": success,
        "output": output or ("Completed" if success else ""),
        "error": error,
    }


class TestConsensusGateHappyPath(unittest.TestCase):
    """Layer 1: All workers approve → gate passes."""

    def test_all_workers_approve(self) -> None:
        """当所有 worker 成功时，共识门应该通过。"""
        gate = ConsensusGate()
        engine = ConsensusEngine()
        workers = [
            _make_worker_result("architect", success=True),
            _make_worker_result("coder", success=True),
            _make_worker_result("tester", success=True),
        ]

        result = gate.check("test task", workers, engine)

        self.assertTrue(result.approved, "All-success workers should be approved")
        self.assertFalse(result.needs_review, "No review needed when all agree")
        self.assertEqual(result.outcome, "APPROVED")


class TestConsensusGateRejection(unittest.TestCase):
    """Layer 2: Majority rejects → gate blocks."""

    def test_majority_rejects_blocks(self) -> None:
        """当多数 worker 失败时，共识门应该阻止。"""
        gate = ConsensusGate()
        engine = ConsensusEngine()
        workers = [
            _make_worker_result("architect", success=False, error="Failed"),
            _make_worker_result("coder", success=False, error="Failed"),
            _make_worker_result("tester", success=True),
        ]

        result = gate.check("test task", workers, engine)

        self.assertFalse(result.approved, "Majority failure should be blocked")
        self.assertEqual(result.outcome, "REJECTED")


class TestConsensusGateVeto(unittest.TestCase):
    """Layer 3: Any worker veto → gate blocks (ESCALATED)."""

    def test_veto_triggers_escalation(self) -> None:
        """当有 worker 投否决票（严重错误）时，共识门应该阻止并升级。"""
        gate = ConsensusGate()
        engine = ConsensusEngine()
        workers = [
            _make_worker_result("architect", success=True),
            _make_worker_result("security", success=False, error="CRITICAL: security violation"),
        ]

        result = gate.check("test task", workers, engine)

        self.assertFalse(result.approved, "Veto (critical error) should block")
        self.assertIn(result.outcome, ("ESCALATED", "REJECTED"))


class TestConsensusGateSplit(unittest.TestCase):
    """Layer 4: Divided opinions → gate passes with needs_review."""

    def test_split_needs_review(self) -> None:
        """当意见分裂时，共识门应通过但标记 needs_review。"""
        gate = ConsensusGate()
        engine = ConsensusEngine()
        # 2 success + 2 failure → 50/50 split (weight_ratio < 0.51, count_ratio ~0.5)
        workers = [
            _make_worker_result("coder", success=True),
            _make_worker_result("tester", success=True),
            _make_worker_result("devops", success=False, error="Disagree"),
            _make_worker_result("ui", success=False, error="Disagree"),
        ]

        result = gate.check("test task", workers, engine)

        # Split should pass (not block) but flag for review
        self.assertTrue(result.approved, "Split should not hard-block")
        self.assertTrue(result.needs_review, "Split must be flagged for review")


class TestConsensusGateSafeDegradation(unittest.TestCase):
    """Layer 5: ConsensusEngine exception → needs_review (not fail-open)."""

    def test_engine_exception_safe_degrade(self) -> None:
        """当 ConsensusEngine 异常时，安全降级为 needs_review，不直接放行。"""
        gate = ConsensusGate()
        broken_engine = MagicMock(spec=ConsensusEngine)
        broken_engine.create_proposal.side_effect = RuntimeError("Engine crashed")

        workers = [_make_worker_result("architect", success=True)]

        result = gate.check("test task", workers, broken_engine)

        # Safe degradation: not fail-open (needs_review=True)
        # but also not hard-block (approved=True) in non-critical mode
        self.assertTrue(result.approved, "Non-critical mode should not hard-block on exception")
        self.assertTrue(result.needs_review, "Exception must trigger needs_review (not fail-open)")

    def test_engine_exception_critical_mode_blocks(self) -> None:
        """关键决策模式下，ConsensusEngine 异常时必须阻止（fail-closed）。"""
        gate = ConsensusGate()
        broken_engine = MagicMock(spec=ConsensusEngine)
        broken_engine.create_proposal.side_effect = RuntimeError("Engine crashed")

        workers = [_make_worker_result("architect", success=True)]

        result = gate.check("test task", workers, broken_engine, critical=True)

        # Critical mode: must block on exception (safe degradation = deny)
        self.assertFalse(result.approved, "Critical mode must block on exception")
        self.assertTrue(result.needs_review, "Exception must trigger needs_review")


class TestConsensusGateEmptyWorkers(unittest.TestCase):
    """Layer 7: Empty workers → timeout → needs_review."""

    def test_no_workers_timeout(self) -> None:
        """当无 worker 结果时，共识门应标记 needs_review（TIMEOUT）。"""
        gate = ConsensusGate()
        engine = ConsensusEngine()

        result = gate.check("test task", [], engine)

        self.assertTrue(result.needs_review, "No workers should trigger needs_review")


class TestConsensusGateResult(unittest.TestCase):
    """Verify ConsensusGateResult dataclass."""

    def test_result_holds_all_fields(self) -> None:
        """ConsensusGateResult must store all required fields."""
        r = ConsensusGateResult(
            approved=True,
            outcome="APPROVED",
            reason="All workers agreed",
            consensus_record=None,
            needs_review=False,
        )
        self.assertTrue(r.approved)
        self.assertEqual(r.outcome, "APPROVED")
        self.assertEqual(r.reason, "All workers agreed")
        self.assertFalse(r.needs_review)


if __name__ == "__main__":
    unittest.main()
