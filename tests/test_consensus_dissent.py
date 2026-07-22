"""Tests for V4.2.1 P1-7 Consensus Dissent Requirement.

Validates that when require_dissent=True, ConsensusEngine warns about
voters who did not identify a risk in their vote.risk_identified field.
This prevents "rubber-stamp" consensus where all roles vote yes without
genuine scrutiny.
"""

from scripts.collaboration.consensus import ConsensusEngine
from scripts.collaboration.models import DecisionOutcome, Vote


class TestConsensusDissent:
    """V4.2.1 P1-7: Dissent requirement."""

    def _make_vote(
        self,
        voter_id: str = "v1",
        role: str = "coder",
        decision: bool = True,
        risk: str | None = None,
        weight: float = 1.0,
    ) -> Vote:
        return Vote(
            voter_id=voter_id,
            voter_role=role,
            decision=decision,
            reason="ok",
            weight=weight,
            risk_identified=risk,
        )

    def _run_consensus(self, engine: ConsensusEngine, votes: list[Vote]):
        """Helper: create proposal, cast votes, reach consensus."""
        proposal = engine.create_proposal(
            topic="Test",
            proposer_id="coord",
            content="Decision",
        )
        for v in votes:
            engine.cast_vote(proposal.proposal_id, v)
        return engine.reach_consensus(proposal.proposal_id)

    def test_disabled_by_default(self):
        """require_dissent=False (default) → no dissent warnings."""
        engine = ConsensusEngine()  # default: require_dissent=False
        record = self._run_consensus(
            engine,
            [self._make_vote("v1"), self._make_vote("v2")],
        )
        dissent_warnings = [w for w in record.warnings if "Dissent" in w]
        assert dissent_warnings == []

    def test_enabled_warns_on_missing_risk(self):
        """require_dissent=True + no risk_identified → warning."""
        engine = ConsensusEngine(require_dissent=True)
        record = self._run_consensus(
            engine,
            [self._make_vote("v1"), self._make_vote("v2")],  # no risk
        )
        dissent_warnings = [w for w in record.warnings if "Dissent" in w]
        assert len(dissent_warnings) == 1
        assert "2/2" in dissent_warnings[0]
        assert "v1" in dissent_warnings[0]
        assert "v2" in dissent_warnings[0]

    def test_enabled_no_warning_when_all_provide_risk(self):
        """require_dissent=True + all have risk_identified → no warning."""
        engine = ConsensusEngine(require_dissent=True)
        record = self._run_consensus(
            engine,
            [
                self._make_vote("v1", risk="Performance bottleneck in loop"),
                self._make_vote("v2", risk="Security: unvalidated input"),
            ],
        )
        dissent_warnings = [w for w in record.warnings if "Dissent" in w]
        assert dissent_warnings == []

    def test_partial_missing(self):
        """1/2 voters missing risk → warning mentions only that voter."""
        engine = ConsensusEngine(require_dissent=True)
        record = self._run_consensus(
            engine,
            [
                self._make_vote("v1", risk="Memory leak risk"),
                self._make_vote("v2"),  # missing risk
            ],
        )
        dissent_warnings = [w for w in record.warnings if "Dissent" in w]
        assert len(dissent_warnings) == 1
        assert "1/2" in dissent_warnings[0]
        assert "v1" not in dissent_warnings[0]
        assert "v2" in dissent_warnings[0]

    def test_empty_string_risk_treated_as_missing(self):
        """Empty/whitespace risk_identified treated as missing."""
        engine = ConsensusEngine(require_dissent=True)
        record = self._run_consensus(
            engine,
            [
                self._make_vote("v1", risk="   "),  # whitespace only
                self._make_vote("v2", risk=""),  # empty
            ],
        )
        dissent_warnings = [w for w in record.warnings if "Dissent" in w]
        assert len(dissent_warnings) == 1
        assert "2/2" in dissent_warnings[0]

    def test_warning_non_blocking(self):
        """Dissent warning does not change outcome — still APPROVED."""
        engine = ConsensusEngine(require_dissent=True)
        record = self._run_consensus(
            engine,
            [self._make_vote("v1"), self._make_vote("v2")],
        )
        assert record.outcome == DecisionOutcome.APPROVED
        # Warning present but non-blocking
        assert any("Dissent" in w for w in record.warnings)

    def test_works_with_reject_votes(self):
        """Dissent check applies to reject votes too."""
        engine = ConsensusEngine(require_dissent=True)
        record = self._run_consensus(
            engine,
            [
                self._make_vote("v1", decision=False, risk="Too risky"),
                self._make_vote("v2", decision=False),  # missing risk
            ],
        )
        dissent_warnings = [w for w in record.warnings if "Dissent" in w]
        assert len(dissent_warnings) == 1
        assert "1/2" in dissent_warnings[0]

    def test_combine_with_fatigue(self):
        """Dissent + fatigue warnings can coexist in record.warnings."""
        engine = ConsensusEngine(fatigue_threshold=1, require_dissent=True)
        # First unanimous vote without risk → triggers both fatigue + dissent
        record = self._run_consensus(
            engine,
            [self._make_vote("v1"), self._make_vote("v2")],
        )
        has_fatigue = any("fatigue" in w.lower() for w in record.warnings)
        has_dissent = any("Dissent" in w for w in record.warnings)
        assert has_fatigue
        assert has_dissent

    def test_default_require_dissent_is_false(self):
        """Default value is False (backward compatible)."""
        engine = ConsensusEngine()
        assert engine._require_dissent is False
