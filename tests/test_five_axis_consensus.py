#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for FiveAxisConsensusEngine (P1-4: ConsensusEngine Five-Axis Extension).

Spec reference: SPEC_V35_Agent_Skills_Quality_Framework.md Section 7.4
"""

import pytest
from scripts.collaboration.five_axis_consensus import (
    ReviewAxis,
    AxisVote,
    FiveAxisReview,
    ConsensusResult,
    FiveAxisConsensusEngine,
    create_default_engine,
    create_strict_engine,
    create_security_focused_engine,
)


class TestReviewAxisEnum:
    """Test the five-axis enum."""

    def test_five_axes_exist(self):
        expected = ["CORRECTNESS", "READABILITY", "ARCHITECTURE", "SECURITY", "PERFORMANCE"]
        for name in expected:
            assert hasattr(ReviewAxis, name)

    def test_axis_values(self):
        assert ReviewAxis.CORRECTNESS.value == "correctness"
        assert ReviewAxis.SECURITY.value == "security"


class TestAxisVote:
    """Test individual axis vote."""

    def test_positive_vote(self):
        vote = AxisVote(
            axis=ReviewAxis.CORRECTNESS,
            score=0.9,
            confidence=0.8,
        )
        assert vote.is_positive() is True
        assert vote.is_negative() is False

    def test_negative_vote(self):
        vote = AxisVote(
            axis=ReviewAxis.SECURITY,
            score=0.2,
            confidence=0.7,
        )
        assert vote.is_positive() is False
        assert vote.is_negative() is True

    def test_neutral_vote(self):
        vote = AxisVote(
            axis=ReviewAxis.READABILITY,
            score=0.5,
            confidence=0.6,
        )
        assert vote.is_positive() is False
        assert vote.is_negative() is False

    def test_score_clamped_to_range(self):
        engine = FiveAxisConsensusEngine()
        review = engine.create_review("test", "test")
        vote = engine.add_axis_vote(review, ReviewAxis.CORRECTNESS, 1.5, -0.5)
        assert vote.score == 1.0  # Clamped from 1.5 to max 1.0
        assert vote.confidence == 0.0  # Clamped from -0.5 to min 0.0


class TestFiveAxisReview:
    """Test complete review structure."""

    def test_create_review(self):
        engine = FiveAxisConsensusEngine()
        review = engine.create_review("reviewer_1", "solo-coder")
        assert review.reviewer_id == "reviewer_1"
        assert review.role == "solo-coder"
        assert len(review.votes) == 0

    def test_add_axis_votes(self):
        engine = FiveAxisConsensusEngine()
        review = engine.create_review("r1", "coder")
        engine.add_axis_vote(review, ReviewAxis.CORRECTNESS, 0.8, 0.9)
        engine.add_axis_vote(review, ReviewAxis.SECURITY, 0.7, 0.8)
        assert len(review.votes) == 2

    def test_calculate_overall_score(self):
        engine = FiveAxisConsensusEngine()
        review = engine.create_review("r1", "tester")
        engine.add_axis_vote(review, ReviewAxis.CORRECTNESS, 0.9, 0.9)
        engine.add_axis_vote(review, ReviewAxis.SECURITY, 0.6, 0.7)
        overall = review.calculate_overall()
        assert 0.0 < overall < 1.0

    def test_get_vote_for_specific_axis(self):
        engine = FiveAxisConsensusEngine()
        review = engine.create_review("r1", "security")
        engine.add_axis_vote(review, ReviewAxis.SECURITY, 0.85, 0.95)
        sec_vote = review.get_vote_for_axis(ReviewAxis.SECURITY)
        assert sec_vote is not None
        assert sec_vote.score == 0.85

    def test_get_nonexistent_axis_returns_none(self):
        engine = FiveAxisConsensusEngine()
        review = engine.create_review("r1", "architect")
        result = review.get_vote_for_axis(ReviewAxis.PERFORMANCE)
        assert result is None


class TestConsensusComputation:
    """Test consensus computation across multiple reviews."""

    def setup_method(self):
        self.engine = create_default_engine()

    def test_single_review_consensus(self):
        review = self.engine.create_review("r1", "coder")
        self.engine.add_axis_vote(review, ReviewAxis.CORRECTNESS, 0.9, 0.9)
        self.engine.add_axis_vote(review, ReviewAxis.SECURITY, 0.8, 0.8)

        result = self.engine.compute_consensus([review])
        assert len(result.reviews) == 1
        assert "correctness" in result.axis_consensus
        assert "security" in result.axis_consensus

    def test_multiple_reviews_aggregation(self):
        r1 = self.engine.create_review("r1", "coder")
        self.engine.add_axis_vote(r1, ReviewAxis.CORRECTNESS, 0.9, 0.9)

        r2 = self.engine.create_review("r2", "tester")
        self.engine.add_axis_vote(r2, ReviewAxis.CORRECTNESS, 0.7, 0.8)

        result = self.engine.compute_consensus([r1, r2])
        assert len(result.reviews) == 2
        corr = result.axis_consensus.get("correctness", 0)
        assert 0.6 <= corr <= 1.0  # Weighted average of two scores

    def test_high_scores_approve(self):
        review = self.engine.create_review("r1", "architect")
        for axis in ReviewAxis:
            self.engine.add_axis_vote(review, axis, 0.9, 0.9)

        result = self.engine.compute_consensus([review])
        assert result.verdict == "APPROVE"

    def test_low_scores_reject(self):
        review = self.engine.create_review("r1", "coder")
        for axis in ReviewAxis:
            self.engine.add_axis_vote(review, axis, 0.3, 0.7)

        result = self.engine.compute_consensus([review])
        assert result.verdict == "REJECT"

    def test_mixed_scores_conditional(self):
        review = self.engine.create_review("r1", "tester")
        self.engine.add_axis_vote(review, ReviewAxis.CORRECTNESS, 0.8, 0.8)
        self.engine.add_axis_vote(review, ReviewAxis.SECURITY, 0.4, 0.7)
        self.engine.add_axis_vote(review, ReviewAxis.READABILITY, 0.6, 0.6)

        result = self.engine.compute_consensus([review])
        assert result.verdict in ("CONDITIONAL", "REJECT")


class TestStrictMode:
    """Test strict mode behavior."""

    def test_security_veto_in_strict_mode(self):
        engine = create_strict_engine()
        review = engine.create_review("r1", "security")

        # High scores on all axes except security
        for axis in ReviewAxis:
            if axis != ReviewAxis.SECURITY:
                engine.add_axis_vote(review, axis, 0.95, 0.9)
        # Low security score
        engine.add_axis_vote(review, ReviewAxis.SECURITY, 0.3, 0.9)

        result = engine.compute_consensus([review])
        assert result.verdict == "REJECT"
        assert any(item["axis"] == "security" for item in result.action_items)

    def test_strict_mode_pass_with_good_security(self):
        engine = create_strict_engine()
        review = engine.create_review("r1", "devops")
        for axis in ReviewAxis:
            engine.add_axis_vote(review, axis, 0.9, 0.95)  # Higher confidence

        result = engine.compute_consensus([review])
        assert result.verdict in ("APPROVE", "CONDITIONAL")  # Both acceptable with high scores


class TestActionItems:
    """Test action item generation."""

    def test_action_items_for_weak_axes(self):
        engine = create_default_engine()
        review = engine.create_review("r1", "architect")
        engine.add_axis_vote(review, ReviewAxis.CORRECTNESS, 0.9, 0.9)
        engine.add_axis_vote(review, ReviewAxis.SECURITY, 0.3, 0.8)
        engine.add_axis_vote(review, ReviewAxis.PERFORMANCE, 0.35, 0.7)

        result = engine.compute_consensus([review])
        weak_items = [a for a in result.action_items if a["severity"] != "critical"]
        assert len(weak_items) >= 1  # At least performance should be flagged


class TestUtilityMethods:
    """Test utility and query methods."""

    def test_get_axis_names(self):
        engine = FiveAxisConsensusEngine()
        names = engine.get_axis_names()
        assert len(names) == 5
        assert "correctness" in names
        assert "security" in names

    def test_get_default_weights(self):
        engine = FiveAxisConsensusEngine()
        weights = engine.get_default_weights()
        assert len(weights) == 5
        total = sum(weights.values())
        assert abs(total - 1.0) < 0.01  # Should sum to ~1.0

    def test_result_to_dict_serialization(self):
        engine = FiveAxisConsensusEngine()
        review = engine.create_review("r1", "test")
        engine.add_axis_vote(review, ReviewAxis.CORRECTNESS, 0.8, 0.8)
        result = engine.compute_consensus([review])
        d = result.to_dict()
        assert "verdict" in d
        assert "overall_consensus" in d
        assert "axis_consensus" in d


class TestFactoryFunctions:
    """Test factory functions for common configurations."""

    def test_default_engine_not_strict(self):
        engine = create_default_engine()
        assert engine._strict_mode is False

    def test_strict_engine_is_strict(self):
        engine = create_strict_engine()
        assert engine._strict_mode is True

    def test_security_focused_has_higher_security_weight(self):
        default = create_default_engine()
        focused = create_security_focused_engine()
        default_sec_weight = default._weights[ReviewAxis.SECURITY]
        focused_sec_weight = focused._weights[ReviewAxis.SECURITY]
        assert focused_sec_weight > default_sec_weight

    def test_factory_functions_create_instances(self):
        for factory in [create_default_engine, create_strict_engine, create_security_focused_engine]:
            engine = factory()
            assert isinstance(engine, FiveAxisConsensusEngine)


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_reviews_list(self):
        engine = FiveAxisConsensusEngine()
        result = engine.compute_consensus([])
        assert result.verdict == "REJECT"
        assert len(result.reviews) == 0

    def test_review_with_no_votes(self):
        engine = FiveAxisConsensusEngine()
        review = engine.create_review("r1", "empty")
        result = engine.compute_consensus([review])
        assert result.overall_consensus == 0.0

    def test_all_axes_covered_in_single_review(self):
        engine = FiveAxisConsensusEngine()
        review = engine.create_review("r1", "comprehensive")
        for axis in ReviewAxis:
            engine.add_axis_vote(review, axis, 0.75, 0.8)

        result = engine.compute_consensus([review])
        assert len(result.axis_consensus) == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
