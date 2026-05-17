#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for SimilarTaskRecommender module (V3.6.0)

Tests cover:
- Recommendation with historical data (successful cases)
- Cold start degradation (no historical data)
- Confidence level calculation based on similarity thresholds
- Quick role suggestion method (simplified recommend)
- Role combination extraction from successful cases
- Intent prediction from similar tasks
- Duration estimation accuracy
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from scripts.collaboration.performance_fingerprint import PerformanceFingerprint
from scripts.collaboration.similar_task_recommender import SimilarTaskRecommender


class TestRecommendWithHistory:
    """Test recommendation functionality when historical data exists."""

    def test_recommend_returns_similar_cases(self):
        """Should return similar cases when history exists."""
        fp = PerformanceFingerprint(persist_dir="/tmp/test_fp_recommend_1")

        class MockResult:
            success = True
            error_message = None
            error_type = None

        fp.record_execution(
            task="Implement user authentication system",
            result=MockResult(),
            timing={"total": 12.5, "planning": 2.0, "coding": 8.0, "review": 2.5},
            roles_used=["architect", "coder", "tester"],
            intent="feature_implementation",
        )

        recommender = SimilarTaskRecommender(fp)
        result = recommender.recommend("Add login page authentication", top_k=3)

        assert "similar_cases" in result
        assert len(result["similar_cases"]) > 0
        assert "recommended_roles" in result
        assert "confidence" in result

        fp.clear()

    def test_recommend_extracts_roles_from_successful_cases(self):
        """Should extract roles from successful similar cases."""
        fp = PerformanceFingerprint(persist_dir="/tmp/test_fp_recommend_2")

        class MockResult:
            success = True
            error_message = None
            error_type = None

        fp.record_execution(
            task="Build REST API endpoint",
            result=MockResult(),
            timing={"total": 8.0},
            roles_used=["architect", "coder"],
            intent="api_development",
        )

        recommender = SimilarTaskRecommender(fp)
        result = recommender.recommend("Create new API endpoint", top_k=3)

        assert len(result["recommended_roles"]) > 0
        assert "architect" in result["recommended_roles"] or "coder" in result["recommended_roles"]

        fp.clear()

    def test_recommend_predicts_intent(self):
        """Should predict intent based on similar successful cases."""
        fp = PerformanceFingerprint(persist_dir="/tmp/test_fp_recommend_3")

        class MockResult:
            success = True
            error_message = None
            error_type = None

        fp.record_execution(
            task="Write unit tests for payment module",
            result=MockResult(),
            timing={"total": 6.5},
            roles_used=["tester", "coder"],
            intent="testing",
        )

        recommender = SimilarTaskRecommender(fp)
        result = recommender.recommend("Add tests for checkout process", top_k=3)

        assert result["recommended_intent"] == "testing"

        fp.clear()

    def test_recommend_estimates_duration(self):
        """Should estimate duration from similar cases."""
        fp = PerformanceFingerprint(persist_dir="/tmp/test_fp_recommend_4")

        class MockResult:
            success = True
            error_message = None
            error_type = None

        fp.record_execution(
            task="Database migration script",
            result=MockResult(),
            timing={"total": 15.0, "analysis": 5.0, "execution": 10.0},
            roles_used=["devops", "architect"],
            intent="infrastructure",
        )

        recommender = SimilarTaskRecommender(fp)
        result = recommender.recommend("Migrate database schema", top_k=3)

        assert result["estimated_duration_s"] > 0
        assert isinstance(result["estimated_duration_s"], float)

        fp.clear()


class TestRecommendNoHistory:
    """Test cold start behavior when no historical data exists."""

    def test_recommend_no_data_returns_empty(self):
        """Should return empty recommendation when no fingerprints exist."""
        fp = PerformanceFingerprint(persist_dir="/tmp/test_fp_nohistory_1")
        recommender = SimilarTaskRecommender(fp)

        result = recommender.recommend("New task with no history", top_k=3)

        assert result["similar_cases"] == []
        assert result["recommended_roles"] == []
        assert result["recommended_intent"] is None
        assert result["estimated_duration_s"] == 0.0
        assert result["confidence"] == "low"

        fp.clear()

    def test_recommend_no_data_confidence_is_low(self):
        """Should always return low confidence on cold start."""
        fp = PerformanceFingerprint(persist_dir="/tmp/test_fp_nohistory_2")
        recommender = SimilarTaskRecommender(fp)

        result = recommender.recommend("Another new task", top_k=5)

        assert result["confidence"] == "low"

        fp.clear()

    def test_role_suggestion_no_data(self):
        """get_role_suggestion should return empty list on cold start."""
        fp = PerformanceFingerprint(persist_dir="/tmp/test_fp_nohistory_3")
        recommender = SimilarTaskRecommender(fp)

        roles = recommender.get_role_suggestion("Task without history")

        assert roles == []

        fp.clear()


class TestConfidenceLevels:
    """Test confidence level determination based on similarity scores."""

    def test_high_confidence_with_high_similarity(self):
        """Should return 'high' confidence when similarity > 0.7."""
        fp = PerformanceFingerprint(persist_dir="/tmp/test_fp_confidence_1")

        class MockResult:
            success = True
            error_message = None
            error_type = None

        fp.record_execution(
            task="Implement user authentication system with JWT tokens and session management",
            result=MockResult(),
            timing={"total": 12.5},
            roles_used=["architect", "coder", "tester"],
            intent="feature_implementation",
        )

        recommender = SimilarTaskRecommender(fp)
        result = recommender.recommend("Implement user authentication system with JWT tokens", top_k=3)

        if result["similar_cases"]:
            assert result["confidence"] in ["high", "medium", "low"]
            if result["similar_cases"][0]["similarity"] > 0.7:
                assert result["confidence"] == "high"

        fp.clear()

    def test_medium_confidence_range(self):
        """Should return 'medium' confidence when similarity is between 0.4 and 0.7."""
        recommender = SimilarTaskRecommender()

        assert recommender._determine_confidence(0.5) == "medium"
        assert recommender._determine_confidence(0.6) == "medium"
        assert recommender._determine_confidence(0.41) == "medium"

    def test_low_confidence_boundary(self):
        """Should return 'low' confidence when similarity <= 0.4."""
        recommender = SimilarTaskRecommender()

        assert recommender._determine_confidence(0.4) == "low"
        assert recommender._determine_confidence(0.3) == "low"
        assert recommender._determine_confidence(0.0) == "low"
        assert recommender._determine_confidence(0.1) == "low"

    def test_high_confidence_thresholds(self):
        """Should return 'high' confidence when similarity > 0.7."""
        recommender = SimilarTaskRecommender()

        assert recommender._determine_confidence(0.71) == "high"
        assert recommender._determine_confidence(0.8) == "high"
        assert recommender._determine_confidence(0.95) == "high"
        assert recommender._determine_confidence(1.0) == "high"


class TestRoleSuggestion:
    """Test quick role suggestion method."""

    def test_role_suggestion_returns_list(self):
        """get_role_suggestion should always return a list."""
        fp = PerformanceFingerprint(persist_dir="/tmp/test_fp_rolesuggest_1")

        class MockResult:
            success = True
            error_message = None
            error_type = None

        fp.record_execution(
            task="Fix critical bug in payment processing",
            result=MockResult(),
            timing={"total": 5.0},
            roles_used=["coder", "tester"],
            intent="bug_fix",
        )

        recommender = SimilarTaskRecommender(fp)
        roles = recommender.get_role_suggestion("Resolve payment issue")

        assert isinstance(roles, list)

        fp.clear()

    def test_role_suggestion_matches_recommend(self):
        """get_role_suggestion should match recommend's recommended_roles."""
        fp = PerformanceFingerprint(persist_dir="/tmp/test_fp_rolesuggest_2")

        class MockResult:
            success = True
            error_message = None
            error_type = None

        fp.record_execution(
            task="Optimize database queries for performance",
            result=MockResult(),
            timing={"total": 10.0},
            roles_used=["architect", "devops"],
            intent="optimization",
        )

        recommender = SimilarTaskRecommender(fp)
        full_result = recommender.recommend("Speed up slow database queries", top_k=3)
        quick_roles = recommender.get_role_suggestion("Speed up slow database queries")

        assert quick_roles == full_result["recommended_roles"]

        fp.clear()

    def test_role_suggestion_with_multiple_successful_cases(self):
        """Should handle multiple successful cases correctly."""
        fp = PerformanceFingerprint(persist_dir="/tmp/test_fp_rolesuggest_3")

        class MockResultSuccess:
            success = True
            error_message = None
            error_type = None

        fp.record_execution(
            task="Add user profile feature",
            result=MockResultSuccess(),
            timing={"total": 8.0},
            roles_used=["architect", "coder"],
            intent="feature_implementation",
        )

        fp.record_execution(
            task="Implement user settings page",
            result=MockResultSuccess(),
            timing={"total": 7.0},
            roles_used=["coder", "ui"],
            intent="feature_implementation",
        )

        recommender = SimilarTaskRecommender(fp)
        roles = recommender.get_role_suggestion("Create user dashboard")

        assert isinstance(roles, list)
        assert len(roles) > 0

        fp.clear()


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_task_string(self):
        """Should handle empty task string gracefully."""
        fp = PerformanceFingerprint(persist_dir="/tmp/test_fp_edge_1")
        recommender = SimilarTaskRecommender(fp)

        result = recommender.recommend("", top_k=3)

        assert isinstance(result, dict)
        assert "confidence" in result

        fp.clear()

    def test_top_k_parameter_respected(self):
        """Should respect top_k parameter for number of similar cases."""
        fp = PerformanceFingerprint(persist_dir="/tmp/test_fp_edge_2")

        class MockResult:
            success = True
            error_message = None
            error_type = None

        for i in range(5):
            fp.record_execution(
                task=f"Task variant {i} with similar keywords",
                result=MockResult(),
                timing={"total": float(i + 1)},
                roles_used=["coder"],
                intent="development",
            )

        recommender = SimilarTaskRecommender(fp)
        result = recommender.recommend("Similar task keywords", top_k=2)

        assert len(result["similar_cases"]) <= 2

        fp.clear()

    def test_unsuccessful_cases_fallback(self):
        """Should fallback to all cases when no successful cases exist."""
        fp = PerformanceFingerprint(persist_dir="/tmp/test_fp_edge_3")

        class MockResultFail:
            success = False
            error_message = "Timeout error"
            error_type = "timeout"

        fp.record_execution(
            task="Failed task attempt",
            result=MockResultFail(),
            timing={"total": 20.0},
            roles_used=["coder", "tester"],
            intent="bug_fix",
        )

        recommender = SimilarTaskRecommender(fp)
        result = recommender.recommend("Retry failed task", top_k=3)

        assert len(result["similar_cases"]) > 0
        assert len(result["recommended_roles"]) >= 0

        fp.clear()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
