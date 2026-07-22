"""Tests for V4.2.0 P0-6 Consensus Fatigue Detector.

Validates that ConsensusEngine tracks consecutive unanimous approvals
and emits warnings when the count exceeds the threshold, to detect
possible "AI agreement bias" where all roles vote yes without real
scrutiny.
"""

from scripts.collaboration.consensus import ConsensusEngine
from scripts.collaboration.models import DecisionOutcome, Vote


class TestConsensusFatigue:
    """V4.2.0 P0-6: Consensus fatigue detection."""

    def _cast_unanimous_votes(self, engine: ConsensusEngine, proposal_id: str) -> None:
        """Cast 3 approving votes (architect + pm + coder) on a proposal."""
        for voter_id, role, weight in [
            ("arch-1", "architect", 1.5),
            ("pm-1", "product_manager", 1.2),
            ("coder-1", "coder", 1.0),
        ]:
            engine.cast_vote(
                proposal_id,
                Vote(
                    voter_id=voter_id,
                    voter_role=role,
                    decision=True,
                    reason="approve",
                    weight=weight,
                ),
            )

    def _run_n_unanimous(self, engine: ConsensusEngine, n: int) -> list:
        """Run n unanimous consensus rounds, return list of records."""
        records = []
        for i in range(n):
            proposal = engine.create_proposal(
                topic=f"Proposal {i}",
                proposer_id="coord-1",
                content=f"Decision {i}",
            )
            self._cast_unanimous_votes(engine, proposal.proposal_id)
            record = engine.reach_consensus(proposal.proposal_id)
            records.append(record)
        return records

    def test_no_fatigue_below_threshold(self):
        """4 consecutive unanimous (< 5 threshold) → no warning."""
        engine = ConsensusEngine(fatigue_threshold=5)
        records = self._run_n_unanimous(engine, 4)
        assert all(r.warnings == [] for r in records)
        assert engine.get_fatigue_status()["consecutive_unanimous"] == 4

    def test_fatigue_triggered_at_threshold(self):
        """5th consecutive unanimous → warning emitted."""
        engine = ConsensusEngine(fatigue_threshold=5)
        records = self._run_n_unanimous(engine, 5)
        # First 4: no warnings
        assert all(r.warnings == [] for r in records[:4])
        # 5th: warning
        assert len(records[4].warnings) == 1
        assert "Consensus fatigue" in records[4].warnings[0]
        assert "AI agreement bias" in records[4].warnings[0]

    def test_fatigue_counter_resets_after_warning(self):
        """After warning, counter resets to 0."""
        engine = ConsensusEngine(fatigue_threshold=3)
        self._run_n_unanimous(engine, 3)
        assert engine.get_fatigue_status()["consecutive_unanimous"] == 0

    def test_fatigue_counter_resets_on_non_unanimous(self):
        """A rejected proposal resets the counter."""
        engine = ConsensusEngine(fatigue_threshold=5)
        # 3 unanimous
        self._run_n_unanimous(engine, 3)
        assert engine.get_fatigue_status()["consecutive_unanimous"] == 3

        # 1 rejected (all vote against)
        proposal = engine.create_proposal(
            topic="Bad idea",
            proposer_id="coord-1",
            content="Reject this",
        )
        for voter_id, role, weight in [
            ("arch-1", "architect", 1.5),
            ("pm-1", "product_manager", 1.2),
        ]:
            engine.cast_vote(
                proposal.proposal_id,
                Vote(
                    voter_id=voter_id,
                    voter_role=role,
                    decision=False,
                    reason="reject",
                    weight=weight,
                ),
            )
        record = engine.reach_consensus(proposal.proposal_id)
        assert record.outcome == DecisionOutcome.REJECTED
        # Counter should reset
        assert engine.get_fatigue_status()["consecutive_unanimous"] == 0

    def test_fatigue_disabled_when_threshold_zero(self):
        """threshold=0 disables fatigue detection."""
        engine = ConsensusEngine(fatigue_threshold=0)
        records = self._run_n_unanimous(engine, 10)
        assert all(r.warnings == [] for r in records)
        status = engine.get_fatigue_status()
        assert status["enabled"] is False

    def test_fatigue_not_triggered_on_split(self):
        """SPLIT outcome does not increment counter."""
        engine = ConsensusEngine(fatigue_threshold=3)
        # 2 unanimous
        self._run_n_unanimous(engine, 2)

        # 1 split (1 for weight 1.0, 1 against weight 1.5 → weight_ratio 0.4 < 0.51, count 50% → SPLIT)
        proposal = engine.create_proposal(
            topic="Controversial",
            proposer_id="coord-1",
            content="Maybe?",
        )
        engine.cast_vote(
            proposal.proposal_id,
            Vote(voter_id="a", voter_role="coder", decision=True, reason="ok", weight=1.0),
        )
        engine.cast_vote(
            proposal.proposal_id,
            Vote(voter_id="b", voter_role="architect", decision=False, reason="no", weight=1.5),
        )
        record = engine.reach_consensus(proposal.proposal_id)
        assert record.outcome == DecisionOutcome.SPLIT
        # Counter should reset (SPLIT is not unanimous)
        assert engine.get_fatigue_status()["consecutive_unanimous"] == 0

    def test_fatigue_not_triggered_on_escalated(self):
        """ESCALATED (veto) does not increment counter."""
        engine = ConsensusEngine(fatigue_threshold=3)
        # 2 unanimous
        self._run_n_unanimous(engine, 2)

        # 1 veto
        proposal = engine.create_proposal(
            topic="Vetoed",
            proposer_id="coord-1",
            content="Veto this",
        )
        engine.cast_vote(
            proposal.proposal_id,
            Vote(voter_id="sec", voter_role="security", decision=True, reason="ok", weight=1.0),
        )
        engine.cast_vote(
            proposal.proposal_id,
            Vote(voter_id="sec2", voter_role="security", decision=False, reason="veto", weight=-1.0),
        )
        record = engine.reach_consensus(proposal.proposal_id)
        assert record.outcome == DecisionOutcome.ESCALATED
        # Counter should reset
        assert engine.get_fatigue_status()["consecutive_unanimous"] == 0

    def test_get_fatigue_status(self):
        """get_fatigue_status returns correct structure."""
        engine = ConsensusEngine(fatigue_threshold=5)
        status = engine.get_fatigue_status()
        assert status == {
            "consecutive_unanimous": 0,
            "threshold": 5,
            "enabled": True,
        }

    def test_warning_does_not_block_approval(self):
        """Fatigue warning is non-blocking — outcome still APPROVED."""
        engine = ConsensusEngine(fatigue_threshold=2)
        records = self._run_n_unanimous(engine, 2)
        # 2nd record has warning but outcome is still APPROVED
        assert records[1].outcome == DecisionOutcome.APPROVED
        assert len(records[1].warnings) == 1

    def test_custom_threshold(self):
        """Custom threshold of 1 triggers on first unanimous."""
        engine = ConsensusEngine(fatigue_threshold=1)
        records = self._run_n_unanimous(engine, 1)
        assert len(records[0].warnings) == 1

    def test_default_threshold_is_5(self):
        """Default threshold is 5 (backward compatible)."""
        engine = ConsensusEngine()
        assert engine.get_fatigue_status()["threshold"] == 5
