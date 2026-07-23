#!/usr/bin/env python3
"""Consensus Engine + Worker Integration Tests (V4.2.1 P1-1 — Test Pyramid Lift).

Integration tests for ConsensusEngine voting and consensus decision-making.
Verifies that multi-role voting produces correct consensus outcomes.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from scripts.collaboration.consensus import ConsensusEngine
from scripts.collaboration.models import DecisionOutcome, Vote
from scripts.collaboration.worker import Worker

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


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


def _make_worker(role_id: str, worker_id: str) -> Worker:
    """Build a Worker with a mocked scratchpad (only vote_on_proposal is used)."""
    return Worker(
        worker_id=worker_id,
        role_id=role_id,
        role_prompt=f"You are {role_id}.",
        scratchpad=MagicMock(),
    )


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


# --------------------------------------------------------------------------- #
# T1: Basic voting flow
# --------------------------------------------------------------------------- #


class T1_ConsensusBasicVoting(unittest.TestCase):
    """Basic voting flow — multiple roles vote, consensus is reached."""

    def test_proposal_lifecycle_create_vote_decide(self) -> None:
        """Creating a proposal, casting votes, and reaching consensus yields a record."""
        engine = ConsensusEngine()
        proposal = engine.create_proposal(
            topic="DB selection",
            proposer_id="coord-001",
            content="Use PostgreSQL",
        )
        engine.cast_vote(
            proposal.proposal_id,
            _make_vote("arch-1", "architect", decision=True, weight=1.5),
        )
        engine.cast_vote(
            proposal.proposal_id,
            _make_vote("coder-1", "solo-coder", decision=True, weight=1.0),
        )
        record = engine.reach_consensus(proposal.proposal_id)

        self.assertEqual(record.outcome, DecisionOutcome.APPROVED)
        self.assertEqual(record.topic, "DB selection")
        self.assertEqual(record.votes_for, 2)
        self.assertEqual(record.votes_against, 0)

    def test_record_stored_and_retrievable(self) -> None:
        """A reached consensus record is stored and retrievable via get_record/get_all_records."""
        engine = ConsensusEngine()
        record, _ = _run_consensus(
            engine,
            [_make_vote("a", "architect", True, 1.5), _make_vote("b", "tester", True, 1.0)],
        )

        fetched = engine.get_record(record.record_id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.outcome, record.outcome)
        all_records = engine.get_all_records()
        self.assertEqual(len(all_records), 1)
        self.assertEqual(all_records[0].record_id, record.record_id)

    def test_all_participants_recorded(self) -> None:
        """Every voter's id appears in the record.participants list."""
        engine = ConsensusEngine()
        votes = [
            _make_vote("arch-1", "architect", True, 1.5),
            _make_vote("pm-1", "product-manager", True, 1.2),
            _make_vote("coder-1", "solo-coder", True, 1.0),
        ]
        record, _ = _run_consensus(engine, votes)

        self.assertEqual(set(record.participants), {"arch-1", "pm-1", "coder-1"})

    def test_proposal_closed_after_consensus(self) -> None:
        """After reach_consensus the proposal status becomes 'closed'."""
        engine = ConsensusEngine()
        proposal = engine.create_proposal(topic="X", proposer_id="c", content="decide")
        engine.cast_vote(proposal.proposal_id, _make_vote("a", "tester", True, 1.0))
        self.assertEqual(proposal.status, "open")

        engine.reach_consensus(proposal.proposal_id)
        self.assertEqual(proposal.status, "closed")

    def test_worker_vote_on_proposal_feeds_into_engine(self) -> None:
        """A Worker's vote_on_proposal output is accepted by ConsensusEngine.cast_vote."""
        engine = ConsensusEngine()
        proposal = engine.create_proposal(topic="API design", proposer_id="coord", content="REST + versioning")
        worker = _make_worker("architect", "arch-007")

        result = worker.vote_on_proposal(proposal.proposal_id, decision=True, reason="aligns with standards")
        self.assertEqual(result["proposal_id"], proposal.proposal_id)
        vote = result["vote"]
        self.assertEqual(vote.voter_id, "arch-007")
        self.assertEqual(vote.voter_role, "architect")
        self.assertAlmostEqual(vote.weight, 1.5)  # architect default weight

        engine.cast_vote(proposal.proposal_id, vote)
        record = engine.reach_consensus(proposal.proposal_id)
        self.assertEqual(record.outcome, DecisionOutcome.APPROVED)
        self.assertIn("arch-007", record.participants)


# --------------------------------------------------------------------------- #
# T2: Unanimous approval
# --------------------------------------------------------------------------- #


class T2_UnanimousApproval(unittest.TestCase):
    """All roles agree — consensus outcome is APPROVED."""

    def test_all_approve_yields_approved(self) -> None:
        """Three approving votes with no opposition produce APPROVED."""
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

    def test_unanimous_final_decision_equals_content(self) -> None:
        """On unanimous APPROVED, final_decision equals the proposal content."""
        engine = ConsensusEngine()
        content = "Adopt event-sourcing pattern"
        record, _ = _run_consensus(
            engine,
            [_make_vote("a", "architect", True, 1.5), _make_vote("b", "tester", True, 1.0)],
            content=content,
        )
        self.assertEqual(record.outcome, DecisionOutcome.APPROVED)
        self.assertEqual(record.final_decision, content)

    def test_unanimous_votes_count_correct(self) -> None:
        """votes_for counts all approvers; votes_against and abstain are zero."""
        engine = ConsensusEngine()
        record, _ = _run_consensus(
            engine,
            [
                _make_vote("a", "architect", True, 1.5),
                _make_vote("b", "product-manager", True, 1.2),
                _make_vote("c", "solo-coder", True, 1.0),
            ],
        )
        self.assertEqual(record.votes_for, 3)
        self.assertEqual(record.votes_against, 0)
        self.assertEqual(record.votes_abstain, 0)

    def test_two_approve_zero_reject_approved(self) -> None:
        """Two approvers and no reject votes yield APPROVED (weight_ratio ~1.0)."""
        engine = ConsensusEngine()
        record, _ = _run_consensus(
            engine,
            [_make_vote("a", "tester", True, 1.0), _make_vote("b", "devops", True, 1.0)],
        )
        self.assertEqual(record.outcome, DecisionOutcome.APPROVED)
        self.assertAlmostEqual(record.total_weight_for, 2.0)

    def test_unanimous_with_role_weights(self) -> None:
        """Unanimous approval across architect (1.5) + product-manager (1.2) + coder (1.0)."""
        engine = ConsensusEngine()
        record, _ = _run_consensus(
            engine,
            [
                _make_vote("a", "architect", True, 1.5),
                _make_vote("b", "product-manager", True, 1.2),
                _make_vote("c", "solo-coder", True, 1.0),
            ],
        )
        self.assertEqual(record.outcome, DecisionOutcome.APPROVED)
        self.assertAlmostEqual(record.total_weight_for, 3.7)


# --------------------------------------------------------------------------- #
# T3: Split vote handling
# --------------------------------------------------------------------------- #


class T3_SplitVoteHandling(unittest.TestCase):
    """Divided opinions — consensus outcome is SPLIT."""

    def test_one_vs_one_split(self) -> None:
        """One approve vs one reject (equal weight) yields SPLIT (count_ratio ~0.5)."""
        engine = ConsensusEngine()
        record, _ = _run_consensus(
            engine,
            [
                _make_vote("a", "tester", True, 1.0),
                _make_vote("b", "devops", False, 1.0, reason="too costly"),
            ],
        )
        self.assertEqual(record.outcome, DecisionOutcome.SPLIT)

    def test_two_vs_two_split(self) -> None:
        """Two approve vs two reject (equal weights) yields SPLIT."""
        engine = ConsensusEngine()
        record, _ = _run_consensus(
            engine,
            [
                _make_vote("a", "tester", True, 1.0),
                _make_vote("b", "devops", True, 1.0),
                _make_vote("c", "tester", False, 1.0),
                _make_vote("d", "devops", False, 1.0),
            ],
        )
        self.assertEqual(record.outcome, DecisionOutcome.SPLIT)

    def test_weighted_split_approve_lighter(self) -> None:
        """Approve (1.0) vs heavier reject (1.5) yields SPLIT (count 50%, weight<0.51)."""
        engine = ConsensusEngine()
        record, _ = _run_consensus(
            engine,
            [
                _make_vote("coder", "solo-coder", True, 1.0),
                _make_vote("arch", "architect", False, 1.5, reason="arch risk"),
            ],
        )
        self.assertEqual(record.outcome, DecisionOutcome.SPLIT)

    def test_split_escalation_reason(self) -> None:
        """A SPLIT record carries escalation_reason 'Split decision'."""
        engine = ConsensusEngine()
        record, _ = _run_consensus(
            engine,
            [
                _make_vote("a", "tester", True, 1.0),
                _make_vote("b", "devops", False, 1.0),
            ],
        )
        self.assertEqual(record.outcome, DecisionOutcome.SPLIT)
        self.assertEqual(record.escalation_reason, "Split decision")

    def test_split_resets_fatigue_counter(self) -> None:
        """A SPLIT outcome does not count as unanimous — fatigue counter resets to 0."""
        engine = ConsensusEngine(fatigue_threshold=5)
        # Two unanimous rounds first
        _run_consensus(engine, [_make_vote("a", "tester", True, 1.0)])
        _run_consensus(engine, [_make_vote("a", "tester", True, 1.0)])
        self.assertEqual(engine.get_fatigue_status()["consecutive_unanimous"], 2)

        # A split round
        _run_consensus(
            engine,
            [
                _make_vote("a", "tester", True, 1.0),
                _make_vote("b", "devops", False, 1.0),
            ],
        )
        self.assertEqual(engine.get_fatigue_status()["consecutive_unanimous"], 0)


# --------------------------------------------------------------------------- #
# T4: Veto power
# --------------------------------------------------------------------------- #


class T4_VetoPower(unittest.TestCase):
    """A veto (weight < 0) forces ESCALATED regardless of the majority."""

    def test_single_veto_escalated(self) -> None:
        """A single vote with negative weight triggers ESCALATED."""
        engine = ConsensusEngine()
        record, _ = _run_consensus(
            engine,
            [_make_vote("sec", "security", False, -1.0, reason="hard veto")],
        )
        self.assertEqual(record.outcome, DecisionOutcome.ESCALATED)

    def test_veto_overrides_majority_approval(self) -> None:
        """A veto overrides an otherwise-unanimous approval majority."""
        engine = ConsensusEngine()
        record, _ = _run_consensus(
            engine,
            [
                _make_vote("a", "architect", True, 1.5),
                _make_vote("b", "product-manager", True, 1.2),
                _make_vote("c", "solo-coder", True, 1.0),
                _make_vote("sec", "security", False, -1.0, reason="security block"),
            ],
        )
        self.assertEqual(record.outcome, DecisionOutcome.ESCALATED)
        self.assertNotEqual(record.outcome, DecisionOutcome.APPROVED)

    def test_veto_escalation_reason(self) -> None:
        """An ESCALATED (veto) record carries escalation_reason 'Veto vote detected'."""
        engine = ConsensusEngine()
        record, _ = _run_consensus(
            engine,
            [
                _make_vote("a", "tester", True, 1.0),
                _make_vote("sec", "security", False, -1.0),
            ],
        )
        self.assertEqual(record.outcome, DecisionOutcome.ESCALATED)
        self.assertEqual(record.escalation_reason, "Veto vote detected")

    def test_veto_with_approve_decision_still_escalated(self) -> None:
        """Negative weight triggers veto even when decision=True (approve)."""
        engine = ConsensusEngine()
        record, _ = _run_consensus(
            engine,
            [_make_vote("x", "security", True, -1.0, reason="approve but veto-weighted")],
        )
        self.assertEqual(record.outcome, DecisionOutcome.ESCALATED)

    def test_veto_records_total_weight_against(self) -> None:
        """total_weight_against equals the absolute veto weight on ESCALATED records."""
        engine = ConsensusEngine()
        record, _ = _run_consensus(
            engine,
            [
                _make_vote("a", "architect", True, 1.5),
                _make_vote("sec", "security", False, -2.0, reason="double veto"),
            ],
        )
        self.assertEqual(record.outcome, DecisionOutcome.ESCALATED)
        self.assertAlmostEqual(record.total_weight_against, 2.0)
        self.assertAlmostEqual(record.total_weight_for, 1.5)


# --------------------------------------------------------------------------- #
# T5: Weighted voting
# --------------------------------------------------------------------------- #


class T5_WeightedVoting(unittest.TestCase):
    """Role weights influence the outcome beyond raw vote counts."""

    def test_architect_approve_beats_coder_reject(self) -> None:
        """Architect (1.5) approve beats coder (1.0) reject → APPROVED (weight_ratio ~0.6)."""
        engine = ConsensusEngine()
        record, _ = _run_consensus(
            engine,
            [
                _make_vote("arch", "architect", True, 1.5),
                _make_vote("coder", "solo-coder", False, 1.0, reason="prefer simpler"),
            ],
        )
        self.assertEqual(record.outcome, DecisionOutcome.APPROVED)

    def test_coder_approve_loses_to_architect_reject_split(self) -> None:
        """Coder (1.0) approve vs architect (1.5) reject → SPLIT (weight<0.51, count 50%)."""
        engine = ConsensusEngine()
        record, _ = _run_consensus(
            engine,
            [
                _make_vote("coder", "solo-coder", True, 1.0),
                _make_vote("arch", "architect", False, 1.5, reason="arch concern"),
            ],
        )
        self.assertEqual(record.outcome, DecisionOutcome.SPLIT)

    def test_total_weight_for_sums_positive_approve_weights(self) -> None:
        """total_weight_for sums the weights of all approving votes."""
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
        self.assertAlmostEqual(record.total_weight_against, 0.0)

    def test_normal_reject_not_in_total_weight_against(self) -> None:
        """A positive-weight reject contributes to weight ratio but not total_weight_against."""
        engine = ConsensusEngine()
        # 3 approve (3.0) vs 2 reject (2.0 positive) → APPROVED
        record, _ = _run_consensus(
            engine,
            [
                _make_vote("a", "tester", True, 1.0),
                _make_vote("b", "tester", True, 1.0),
                _make_vote("c", "tester", True, 1.0),
                _make_vote("d", "devops", False, 1.0),
                _make_vote("e", "devops", False, 1.0),
            ],
        )
        self.assertEqual(record.outcome, DecisionOutcome.APPROVED)
        # total_weight_against only tracks negative-weight (veto) rejects → 0
        self.assertAlmostEqual(record.total_weight_against, 0.0)
        self.assertEqual(record.votes_against, 2)

    def test_weighted_three_vs_two_approved(self) -> None:
        """Three approve (3.0) vs two reject (2.0) → APPROVED (weight_ratio ~0.6)."""
        engine = ConsensusEngine()
        record, _ = _run_consensus(
            engine,
            [
                _make_vote("a", "tester", True, 1.0),
                _make_vote("b", "tester", True, 1.0),
                _make_vote("c", "tester", True, 1.0),
                _make_vote("d", "devops", False, 1.0),
                _make_vote("e", "devops", False, 1.0),
            ],
        )
        self.assertEqual(record.outcome, DecisionOutcome.APPROVED)


# --------------------------------------------------------------------------- #
# T6: Empty and edge cases
# --------------------------------------------------------------------------- #


class T6_EmptyAndEdgeCases(unittest.TestCase):
    """Empty ballots, single votes, and boundary error handling."""

    def test_no_votes_returns_timeout(self) -> None:
        """Reaching consensus with no votes cast yields TIMEOUT."""
        engine = ConsensusEngine()
        proposal = engine.create_proposal(topic="无人投票", proposer_id="coord", content="decide")
        record = engine.reach_consensus(proposal.proposal_id)
        self.assertEqual(record.outcome, DecisionOutcome.TIMEOUT)
        self.assertEqual(record.votes_for, 0)
        self.assertEqual(record.votes_against, 0)

    def test_single_approve_vote_approved(self) -> None:
        """A single approving vote yields APPROVED (weight_ratio ~1.0)."""
        engine = ConsensusEngine()
        record, _ = _run_consensus(engine, [_make_vote("only", "tester", True, 1.0)])
        self.assertEqual(record.outcome, DecisionOutcome.APPROVED)
        self.assertEqual(record.votes_for, 1)

    def test_single_reject_vote_rejected(self) -> None:
        """A single positive-weight reject vote yields REJECTED (weight_ratio ~0)."""
        engine = ConsensusEngine()
        record, _ = _run_consensus(engine, [_make_vote("only", "tester", False, 1.0, reason="no")])
        self.assertEqual(record.outcome, DecisionOutcome.REJECTED)
        self.assertEqual(record.votes_against, 1)

    def test_cast_vote_on_unknown_proposal_raises(self) -> None:
        """cast_vote on a non-existent proposal id raises ValueError."""
        engine = ConsensusEngine()
        with self.assertRaises(ValueError):
            engine.cast_vote("does-not-exist", _make_vote("a", "tester", True, 1.0))

    def test_cast_vote_on_closed_proposal_raises(self) -> None:
        """Casting a vote after consensus is reached raises ValueError (proposal closed)."""
        engine = ConsensusEngine()
        proposal = engine.create_proposal(topic="closed", proposer_id="coord", content="done")
        engine.cast_vote(proposal.proposal_id, _make_vote("a", "tester", True, 1.0))
        engine.reach_consensus(proposal.proposal_id)
        with self.assertRaises(ValueError):
            engine.cast_vote(proposal.proposal_id, _make_vote("b", "tester", True, 1.0))

    def test_reach_consensus_on_unknown_proposal_raises(self) -> None:
        """reach_consensus on a non-existent proposal id raises ValueError."""
        engine = ConsensusEngine()
        with self.assertRaises(ValueError):
            engine.reach_consensus("missing-proposal-id")


# --------------------------------------------------------------------------- #
# T7: Fatigue detector
# --------------------------------------------------------------------------- #


class T7_FatigueDetector(unittest.TestCase):
    """Consecutive unanimous approvals trigger a consensus-fatigue warning."""

    def _unanimous_round(self, engine: ConsensusEngine) -> None:
        """Run one round of a single approving vote (unanimous by construction)."""
        _run_consensus(engine, [_make_vote("a", "tester", True, 1.0)])

    def test_fatigue_triggered_at_threshold(self) -> None:
        """Reaching the threshold emits a non-blocking fatigue warning."""
        engine = ConsensusEngine(fatigue_threshold=3)
        proposal = engine.create_proposal(topic="p1", proposer_id="c", content="d1")
        engine.cast_vote(proposal.proposal_id, _make_vote("a", "tester", True, 1.0))
        r1 = engine.reach_consensus(proposal.proposal_id)
        self.assertEqual(r1.warnings, [])

        proposal = engine.create_proposal(topic="p2", proposer_id="c", content="d2")
        engine.cast_vote(proposal.proposal_id, _make_vote("a", "tester", True, 1.0))
        r2 = engine.reach_consensus(proposal.proposal_id)
        self.assertEqual(r2.warnings, [])

        proposal = engine.create_proposal(topic="p3", proposer_id="c", content="d3")
        engine.cast_vote(proposal.proposal_id, _make_vote("a", "tester", True, 1.0))
        r3 = engine.reach_consensus(proposal.proposal_id)
        self.assertEqual(len(r3.warnings), 1)
        self.assertIn("Consensus fatigue", r3.warnings[0])
        # Warning is non-blocking — outcome still APPROVED
        self.assertEqual(r3.outcome, DecisionOutcome.APPROVED)

    def test_fatigue_resets_after_warning(self) -> None:
        """After emitting a warning the consecutive counter resets to 0."""
        engine = ConsensusEngine(fatigue_threshold=2)
        self._unanimous_round(engine)
        self._unanimous_round(engine)
        self.assertEqual(engine.get_fatigue_status()["consecutive_unanimous"], 0)

    def test_fatigue_resets_on_rejection(self) -> None:
        """A rejected proposal resets the consecutive-unanimous counter."""
        engine = ConsensusEngine(fatigue_threshold=5)
        self._unanimous_round(engine)
        self._unanimous_round(engine)
        self.assertEqual(engine.get_fatigue_status()["consecutive_unanimous"], 2)

        # A rejected round
        _run_consensus(engine, [_make_vote("a", "tester", False, 1.0, reason="no")])
        self.assertEqual(engine.get_fatigue_status()["consecutive_unanimous"], 0)

    def test_fatigue_disabled_at_zero(self) -> None:
        """fatigue_threshold=0 disables detection and never warns."""
        engine = ConsensusEngine(fatigue_threshold=0)
        for _ in range(10):
            self._unanimous_round(engine)
        status = engine.get_fatigue_status()
        self.assertFalse(status["enabled"])
        self.assertEqual(status["consecutive_unanimous"], 0)

    def test_get_fatigue_status_structure(self) -> None:
        """get_fatigue_status returns the documented keys and default threshold."""
        engine = ConsensusEngine()
        status = engine.get_fatigue_status()
        self.assertEqual(status["consecutive_unanimous"], 0)
        self.assertEqual(status["threshold"], 5)
        self.assertTrue(status["enabled"])


if __name__ == "__main__":
    unittest.main()
