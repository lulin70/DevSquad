#!/usr/bin/env python3
"""
ConsensusGate — Pre-decision consensus gate (硬约束 HC-2).

Wraps ConsensusEngine as a *pre-decision* gate that evaluates worker
results before final result assembly.  This aligns with the project
hard constraint:

    "ConsensusEngine必须作为核心决策机制前置介入所有关键决策点,
    不可仅作为后置补救措施"

And the safe-degradation constraint:

    "共识门在关键决策失败时必须安全降级,禁止fail-open直接执行"

Design:
  - ``check()`` creates a proposal, simulates votes from worker results,
    and returns a ``ConsensusGateResult``.
  - **Non-critical mode** (default): exceptions and SPLIT outcomes pass
    with ``needs_review=True`` (safe degradation — not fail-open because
    the result is flagged for human review).
  - **Critical mode** (``critical=True``): exceptions and TIMEOUT block
    execution (fail-closed).  Used for irreversible operations like
    sending emails, financial transactions, or report generation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .models_base import Vote

if TYPE_CHECKING:
    from .consensus import ConsensusEngine

logger = logging.getLogger(__name__)

# Role-based voting weights (matches ConsensusEngine design).
_ROLE_WEIGHTS: dict[str, float] = {
    "architect": 1.5,
    "product-manager": 1.2,
    "pm": 1.2,
}


@dataclass
class ConsensusGateResult:
    """Result of a ConsensusGate check.

    Attributes:
        approved: Whether the gate allows the action to proceed.
        outcome: Consensus outcome string (APPROVED/REJECTED/SPLIT/ESCALATED/TIMEOUT/ERROR).
        reason: Human-readable explanation of the decision.
        consensus_record: The underlying ConsensusRecord (or None on error).
        needs_review: Whether human review is required (safe degradation flag).
    """

    approved: bool
    outcome: str
    reason: str
    consensus_record: Any | None = None
    needs_review: bool = False


class ConsensusGate:
    """Pre-decision consensus gate using ConsensusEngine.

    Unlike the post-hoc ``Coordinator.resolve_conflicts()``, this gate
    runs *before* final result assembly to ensure worker outputs meet
    consensus before being committed.

    Usage in dispatch pipeline (Step 15.5, before result assembly)::

        gate = ConsensusGate()
        gate_result = gate.check(
            task_description=task_description,
            worker_results=worker_results,
            consensus_engine=self.consensus_engine,
        )
        if not gate_result.approved:
            result.success = False
            result.errors.append(f"Consensus gate blocked: {gate_result.reason}")
        if gate_result.needs_review:
            result.details["needs_review"] = True
    """

    def check(
        self,
        task_description: str,
        worker_results: list[dict[str, Any]],
        consensus_engine: ConsensusEngine,
        critical: bool = False,
    ) -> ConsensusGateResult:
        """Run pre-decision consensus check on worker results.

        Args:
            task_description: The original task being evaluated.
            worker_results: List of worker result dicts (must contain
                ``role_id``, ``success``, ``error`` keys).
            consensus_engine: The ConsensusEngine instance to use.
            critical: If True, exceptions and TIMEOUT block execution
                (fail-closed).  If False, they pass with needs_review.

        Returns:
            ConsensusGateResult with the gate decision.
        """
        try:
            # Edge case: no worker results → TIMEOUT
            if not worker_results:
                return ConsensusGateResult(
                    approved=not critical,
                    outcome="TIMEOUT",
                    reason="No worker results to evaluate",
                    consensus_record=None,
                    needs_review=True,
                )

            # Create proposal
            proposal = consensus_engine.create_proposal(
                topic=f"Pre-dispatch gate: {task_description[:80]}",
                proposer_id="consensus-gate",
                content=f"Approve execution results for: {task_description}",
                options=["approve", "reject"],
            )

            # Simulate votes from worker results
            for wr in worker_results:
                role_id = wr.get("role_id", "unknown")
                success = wr.get("success", False)
                error = wr.get("error", "")

                # Determine vote weight based on role
                weight = _ROLE_WEIGHTS.get(role_id, 1.0)

                # Veto: critical errors trigger negative weight (escalation)
                if error and "CRITICAL" in error.upper():
                    weight = -1.0

                vote = Vote(
                    voter_id=role_id,
                    voter_role=role_id,
                    decision=success,
                    reason=error or ("Approved" if success else "Rejected"),
                    weight=weight,
                )
                consensus_engine.cast_vote(proposal.proposal_id, vote)

            # Reach consensus
            record = consensus_engine.reach_consensus(proposal.proposal_id)
            outcome_str = record.outcome.value.upper()

            if outcome_str == "APPROVED":
                return ConsensusGateResult(
                    approved=True,
                    outcome=outcome_str,
                    reason=record.final_decision or "Approved by consensus",
                    consensus_record=record,
                    needs_review=False,
                )
            elif outcome_str == "REJECTED":
                return ConsensusGateResult(
                    approved=False,
                    outcome=outcome_str,
                    reason=record.final_decision or "Rejected by consensus",
                    consensus_record=record,
                    needs_review=False,
                )
            elif outcome_str == "ESCALATED":
                # Veto detected — block and escalate
                return ConsensusGateResult(
                    approved=False,
                    outcome=outcome_str,
                    reason=record.escalation_reason or "Escalated due to veto",
                    consensus_record=record,
                    needs_review=True,
                )
            elif outcome_str == "SPLIT":
                # Split — pass but flag for review (non-critical mode)
                return ConsensusGateResult(
                    approved=True,
                    outcome=outcome_str,
                    reason=record.final_decision or "Opinion split — needs discussion",
                    consensus_record=record,
                    needs_review=True,
                )
            else:
                # TIMEOUT or unknown — safe degradation
                return ConsensusGateResult(
                    approved=not critical,
                    outcome=outcome_str,
                    reason="No decisive votes recorded",
                    consensus_record=record,
                    needs_review=True,
                )

        except (ValueError, AttributeError, TypeError, RuntimeError) as exc:
            # Safe degradation: log and return needs_review
            # Non-critical: allow but flag (not fail-open because needs_review=True)
            # Critical: block (fail-closed)
            logger.warning("ConsensusGate exception (critical=%s): %s", critical, exc)
            return ConsensusGateResult(
                approved=not critical,
                outcome="ERROR",
                reason=f"ConsensusEngine exception: {exc}",
                consensus_record=None,
                needs_review=True,
            )
