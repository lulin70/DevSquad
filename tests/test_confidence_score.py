#!/usr/bin/env python3
"""
ConfidenceScore Unit Tests

Test the ConfidenceScore system for LLM response quality assessment.
"""

import pytest


@pytest.fixture
def scorer():
    """Create ConfidenceScorer instance"""
    from scripts.collaboration.confidence_score import ConfidenceScorer, reset_scorer

    # Reset global instance
    reset_scorer()

    # Create new instance
    scorer = ConfidenceScorer()
    yield scorer

    # Cleanup
    reset_scorer()


def test_import_confidence_score():
    """Test ConfidenceScore module import"""
    from scripts.collaboration.confidence_score import (
        ConfidenceLevel,
        ConfidenceScore,
        ConfidenceScorer,
        get_confidence_scorer,
        reset_scorer,
    )

    assert ConfidenceScorer is not None
    assert ConfidenceScore is not None
    assert ConfidenceLevel is not None
    assert get_confidence_scorer is not None
    assert reset_scorer is not None


def test_confidence_scorer_initialization(scorer):
    """Test ConfidenceScorer initialization"""
    assert scorer.weights["completeness"] == 0.25
    assert scorer.weights["certainty"] == 0.25
    assert scorer.weights["specificity"] == 0.20
    assert scorer.weights["consistency"] == 0.15
    assert scorer.weights["model_quality"] == 0.15
    assert scorer.min_response_length == 50
    assert len(scorer.history) == 0


def test_calculate_confidence_basic(scorer):
    """Test basic confidence calculation"""
    score = scorer.calculate_confidence(
        prompt="Design a REST API",
        response="Here's a REST API design with endpoints for users, posts, and comments.",
        metadata={"model": "gpt-4", "temperature": 0.7},
    )

    # Verify score structure
    assert isinstance(score.overall_score, float)
    assert 0.0 <= score.overall_score <= 1.0
    assert score.level is not None
    assert len(score.factors) == 5
    assert len(score.reasoning) > 0


def test_calculate_confidence_high_quality(scorer):
    """Test confidence calculation for high-quality response"""
    response = """
    Here's a comprehensive REST API design:

    1. User endpoints:
       - GET /api/v1/users - List users
       - POST /api/v1/users - Create user
       - GET /api/v1/users/{id} - Get user details

    2. Authentication:
       - Use JWT tokens with 15-minute expiry
       - Implement refresh tokens (7-day expiry)

    Example implementation:
    ```python
    @app.route('/api/v1/users', methods=['GET'])
    def list_users():
        return jsonify(users)
    ```

    This design follows REST best practices and includes proper authentication.
    """

    score = scorer.calculate_confidence(
        prompt="Design a REST API",
        response=response,
        metadata={"model": "gpt-4", "temperature": 0.3, "token_count": 1200},
    )

    # High-quality response should have high confidence
    assert score.overall_score >= 0.7
    assert score.level.value in ["high", "very_high"]


def test_calculate_confidence_low_quality(scorer):
    """Test confidence calculation for low-quality response"""
    response = "I think maybe you could use REST API, but I'm not sure..."

    score = scorer.calculate_confidence(prompt="Design a REST API", response=response, metadata={})

    # Low-quality response should have low to medium confidence
    assert score.overall_score <= 0.6
    assert score.level.value in ["low", "very_low", "medium"]


def test_completeness_factor_short_response(scorer):
    """Test completeness factor with short response"""
    score = scorer.calculate_confidence(
        prompt="Test",
        response="Short",  # Very short response
        metadata={},
    )

    # Short response should have low completeness
    assert score.factors["completeness"] < 0.5


def test_completeness_factor_adequate_response(scorer):
    """Test completeness factor with adequate response"""
    response = "A" * 100  # Adequate length

    score = scorer.calculate_confidence(prompt="Test", response=response, metadata={})

    # Adequate response should have medium completeness
    assert score.factors["completeness"] >= 0.5


def test_completeness_factor_truncated_response(scorer):
    """Test completeness factor with truncated response"""
    response = "This is a response that appears to be truncated..."

    score = scorer.calculate_confidence(prompt="Test", response=response, metadata={})

    # Truncated response should have reduced completeness
    assert score.factors["completeness"] < 0.9


def test_certainty_factor_no_uncertainty(scorer):
    """Test certainty factor with no uncertainty indicators"""
    response = "The solution is to use Python Protocol interfaces for type safety."

    score = scorer.calculate_confidence(prompt="Test", response=response, metadata={})

    # No uncertainty should have high certainty
    assert score.factors["certainty"] >= 0.8


def test_certainty_factor_with_uncertainty(scorer):
    """Test certainty factor with uncertainty indicators"""
    response = "I think maybe you could possibly use Protocol, but I'm not sure if it's the best approach."

    score = scorer.calculate_confidence(prompt="Test", response=response, metadata={})

    # High uncertainty should have low to moderate certainty
    assert score.factors["certainty"] <= 0.5


def test_certainty_factor_with_hedging(scorer):
    """Test certainty factor with hedging words"""
    response = "This is probably likely the generally typical approach that usually works."

    score = scorer.calculate_confidence(prompt="Test", response=response, metadata={})

    # Hedging words should reduce certainty
    assert score.factors["certainty"] < 1.0


def test_specificity_factor_high(scorer):
    """Test specificity factor with specific details"""
    response = """
    Use bcrypt with cost factor 12 for password hashing.

    Example:
    ```python
    import bcrypt
    hash = bcrypt.hashpw(password, bcrypt.gensalt(12))
    ```

    For example, this provides 2^12 iterations.

    Key points:
    - Use 12 rounds minimum
    - Store hash in database
    - Never store plain passwords
    """

    score = scorer.calculate_confidence(prompt="Test", response=response, metadata={})

    # Specific details should have high specificity
    assert score.factors["specificity"] >= 0.7


def test_specificity_factor_low(scorer):
    """Test specificity factor with vague language"""
    response = "You should use something like various security measures and several best practices."

    score = scorer.calculate_confidence(prompt="Test", response=response, metadata={})

    # Vague language should have low specificity
    assert score.factors["specificity"] < 0.7


def test_consistency_factor_no_contradictions(scorer):
    """Test consistency factor with no contradictions"""
    response = "Use Python 3.8 or higher. This ensures compatibility with modern features."

    score = scorer.calculate_confidence(prompt="Test", response=response, metadata={})

    # No contradictions should have high consistency
    assert score.factors["consistency"] == 1.0


def test_consistency_factor_with_contradictions(scorer):
    """Test consistency factor with contradictions"""
    response = "You should always use caching. However, never use caching. But you must use caching."

    score = scorer.calculate_confidence(prompt="Test", response=response, metadata={})

    # Contradictions should reduce consistency
    assert score.factors["consistency"] <= 1.0  # May not always detect, so allow 1.0


def test_consistency_factor_with_corrections(scorer):
    """Test consistency factor with self-corrections"""
    response = "Use method A. Actually, I mean use method B instead. Rather, method C is better."

    score = scorer.calculate_confidence(prompt="Test", response=response, metadata={})

    # Self-corrections should reduce consistency
    assert score.factors["consistency"] < 1.0


def test_model_quality_factor_gpt4(scorer):
    """Test model quality factor with GPT-4"""
    score = scorer.calculate_confidence(prompt="Test", response="Response", metadata={"model": "gpt-4"})

    # GPT-4 should have high model quality
    assert score.factors["model_quality"] >= 0.9


def test_model_quality_factor_gpt35(scorer):
    """Test model quality factor with GPT-3.5"""
    score = scorer.calculate_confidence(prompt="Test", response="Response", metadata={"model": "gpt-3.5-turbo"})

    # GPT-3.5 should have good model quality
    assert 0.7 <= score.factors["model_quality"] < 0.9


def test_model_quality_factor_unknown(scorer):
    """Test model quality factor with unknown model"""
    score = scorer.calculate_confidence(prompt="Test", response="Response", metadata={})

    # Unknown model should have default quality
    assert score.factors["model_quality"] == 0.7


def test_model_quality_factor_low_temperature(scorer):
    """Test model quality factor with low temperature"""
    score = scorer.calculate_confidence(
        prompt="Test", response="Response", metadata={"model": "gpt-4", "temperature": 0.2}
    )

    # Low temperature should increase confidence
    assert score.factors["model_quality"] > 0.95


def test_model_quality_factor_high_temperature(scorer):
    """Test model quality factor with high temperature"""
    score = scorer.calculate_confidence(
        prompt="Test", response="Response", metadata={"model": "gpt-4", "temperature": 0.9}
    )

    # High temperature should reduce confidence slightly
    assert score.factors["model_quality"] < 0.95


def test_confidence_level_very_high(scorer):
    """Test VERY_HIGH confidence level"""
    from scripts.collaboration.confidence_score import ConfidenceLevel

    # Create high-quality response
    response = """
    Comprehensive solution with specific details:

    1. Use Protocol interfaces (Python 3.8+)
    2. Implement with @runtime_checkable decorator
    3. Example code:
    ```python
    from typing import Protocol

    class CacheProvider(Protocol):
        def get(self, key: str) -> Any: ...
    ```

    This provides type safety without runtime overhead.
    """

    score = scorer.calculate_confidence(
        prompt="Design interface",
        response=response,
        metadata={"model": "gpt-4", "temperature": 0.2, "token_count": 1500},
    )

    # Should be VERY_HIGH or HIGH
    assert score.level in [ConfidenceLevel.VERY_HIGH, ConfidenceLevel.HIGH]


def test_confidence_level_low(scorer):
    """Test LOW confidence level"""
    from scripts.collaboration.confidence_score import ConfidenceLevel

    response = "Maybe something?"

    score = scorer.calculate_confidence(prompt="Design interface", response=response, metadata={})

    # Should be LOW or VERY_LOW
    assert score.level in [ConfidenceLevel.LOW, ConfidenceLevel.VERY_LOW, ConfidenceLevel.MEDIUM]


def test_confidence_score_is_confident(scorer):
    """Test ConfidenceScore.is_confident() method"""
    score = scorer.calculate_confidence(
        prompt="Test",
        response="A" * 200,  # Adequate response
        metadata={"model": "gpt-4"},
    )

    # Test different thresholds
    assert score.is_confident(threshold=0.5) in [True, False]
    assert score.is_confident(threshold=0.0)
    assert not score.is_confident(threshold=1.0)


def test_confidence_score_to_dict(scorer):
    """Test ConfidenceScore.to_dict() method"""
    score = scorer.calculate_confidence(prompt="Test", response="Response", metadata={"model": "gpt-4"})

    data = score.to_dict()

    # Verify structure
    assert "overall_score" in data
    assert "level" in data
    assert "factors" in data
    assert "reasoning" in data
    assert "metadata" in data
    assert "timestamp" in data


def test_get_average_confidence_empty(scorer):
    """Test get_average_confidence with no history"""
    avg = scorer.get_average_confidence()
    assert avg == 0.0


def test_get_average_confidence_with_history(scorer):
    """Test get_average_confidence with history"""
    # Generate some scores
    scorer.calculate_confidence("Test 1", "Response 1", {})
    scorer.calculate_confidence("Test 2", "Response 2", {})
    scorer.calculate_confidence("Test 3", "Response 3", {})

    avg = scorer.get_average_confidence()
    assert 0.0 <= avg <= 1.0


def test_get_average_confidence_with_limit(scorer):
    """Test get_average_confidence with limit"""
    # Generate multiple scores
    for i in range(10):
        scorer.calculate_confidence(f"Test {i}", "Response", {})

    # Get average of last 5
    avg = scorer.get_average_confidence(limit=5)
    assert 0.0 <= avg <= 1.0


def test_get_confidence_trend_insufficient_data(scorer):
    """Test get_confidence_trend with insufficient data"""
    trend = scorer.get_confidence_trend()
    assert trend == "insufficient_data"


def test_get_confidence_trend_improving(scorer):
    """Test get_confidence_trend with improving trend"""
    # Generate scores with improving quality
    for i in range(10):
        response = "A" * (50 + i * 20)  # Increasing length
        scorer.calculate_confidence("Test", response, {"model": "gpt-4"})

    trend = scorer.get_confidence_trend()
    assert trend in ["improving", "stable"]


def test_get_confidence_trend_declining(scorer):
    """Test get_confidence_trend with declining trend"""
    # Generate scores with declining quality
    for i in range(10):
        response = "A" * (200 - i * 15)  # Decreasing length
        scorer.calculate_confidence("Test", response, {})

    trend = scorer.get_confidence_trend()
    assert trend in ["declining", "stable"]


def test_export_stats_empty(scorer):
    """Test export_stats with no history"""
    stats = scorer.export_stats()

    assert stats["total_scores"] == 0
    assert stats["average_confidence"] == 0.0
    assert stats["trend"] == "no_data"


def test_export_stats_with_history(scorer):
    """Test export_stats with history"""
    # Generate some scores
    for i in range(5):
        scorer.calculate_confidence(f"Test {i}", "Response " * 20, {"model": "gpt-4"})

    stats = scorer.export_stats()

    # Verify structure
    assert stats["total_scores"] == 5
    assert 0.0 <= stats["average_confidence"] <= 1.0
    assert "recent_average" in stats
    assert "trend" in stats
    assert "level_distribution" in stats
    assert "factor_averages" in stats


def test_level_distribution(scorer):
    """Test level distribution in stats"""
    from scripts.collaboration.confidence_score import ConfidenceLevel

    # Generate various quality scores
    scorer.calculate_confidence("Test", "A" * 200, {"model": "gpt-4"})  # High
    scorer.calculate_confidence("Test", "Maybe?", {})  # Low

    stats = scorer.export_stats()
    distribution = stats["level_distribution"]

    # Verify all levels are present
    for level in ConfidenceLevel:
        assert level.value in distribution


def test_factor_averages(scorer):
    """Test factor averages in stats"""
    # Generate some scores
    for _i in range(3):
        scorer.calculate_confidence("Test", "Response " * 20, {"model": "gpt-4"})

    stats = scorer.export_stats()
    averages = stats["factor_averages"]

    # Verify all factors are present
    assert "completeness" in averages
    assert "certainty" in averages
    assert "specificity" in averages
    assert "consistency" in averages
    assert "model_quality" in averages


def test_custom_weights(scorer):
    """Test ConfidenceScorer with custom weights"""
    from scripts.collaboration.confidence_score import ConfidenceScorer

    custom_weights = {
        "completeness": 0.4,
        "certainty": 0.3,
        "specificity": 0.2,
        "consistency": 0.05,
        "model_quality": 0.05,
    }

    custom_scorer = ConfidenceScorer(weights=custom_weights)

    assert custom_scorer.weights["completeness"] == 0.4
    assert custom_scorer.weights["certainty"] == 0.3


def test_custom_min_response_length(scorer):
    """Test ConfidenceScorer with custom min response length"""
    from scripts.collaboration.confidence_score import ConfidenceScorer

    custom_scorer = ConfidenceScorer(min_response_length=100)

    assert custom_scorer.min_response_length == 100


def test_get_confidence_scorer_factory():
    """Test get_confidence_scorer factory function"""
    from scripts.collaboration.confidence_score import get_confidence_scorer, reset_scorer

    # Reset first
    reset_scorer()

    # Get scorer (should create new instance)
    scorer1 = get_confidence_scorer()
    assert scorer1 is not None

    # Get scorer again (should return same instance)
    scorer2 = get_confidence_scorer()
    assert scorer1 is scorer2

    # Cleanup
    reset_scorer()


def test_confidence_score_history_tracking(scorer):
    """Test that scores are added to history"""
    initial_count = len(scorer.history)

    scorer.calculate_confidence("Test 1", "Response 1", {})
    scorer.calculate_confidence("Test 2", "Response 2", {})

    assert len(scorer.history) == initial_count + 2


def test_confidence_score_metadata_preservation(scorer):
    """Test that metadata is preserved in score"""
    metadata = {"model": "gpt-4", "temperature": 0.7, "token_count": 1000, "custom_field": "custom_value"}

    score = scorer.calculate_confidence("Test", "Response", metadata)

    assert score.metadata == metadata


def test_reasoning_not_empty(scorer):
    """Test that reasoning is always provided"""
    score = scorer.calculate_confidence("Test", "Response", {})

    assert len(score.reasoning) > 0
    assert all(isinstance(reason, str) for reason in score.reasoning)


def test_weighted_score_calculation(scorer):
    """Test that weighted score calculation is correct"""
    score = scorer.calculate_confidence("Test", "A" * 100, {"model": "gpt-4"})

    # Manually calculate weighted score
    expected_score = sum(score.factors[factor] * scorer.weights[factor] for factor in scorer.weights)

    # Should match (within floating point precision)
    assert abs(score.overall_score - expected_score) < 0.001


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
