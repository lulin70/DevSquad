#!/usr/bin/env python3
"""
Confidence Score System

Provides confidence scoring for LLM responses to help agents make better decisions.

Features:
- Multi-factor confidence calculation
- Response quality assessment
- Uncertainty detection
- Threshold-based decision making
- Historical confidence tracking

Usage:
    from scripts.collaboration.confidence_score import ConfidenceScorer

    scorer = ConfidenceScorer()

    # Calculate confidence for a response
    score = scorer.calculate_confidence(
        prompt="Design a REST API",
        response="Here's the API design...",
        metadata={"model": "gpt-4", "temperature": 0.7}
    )

    # Check if confidence meets threshold
    if score.is_confident(threshold=0.7):
        # Proceed with high confidence
        pass
    else:
        # Request human review or retry
        pass
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ConfidenceLevel(Enum):
    """Confidence level categories"""

    VERY_HIGH = "very_high"  # >= 0.9
    HIGH = "high"  # >= 0.7
    MEDIUM = "medium"  # >= 0.5
    LOW = "low"  # >= 0.3
    VERY_LOW = "very_low"  # < 0.3


@dataclass
class ConfidenceScore:
    """Confidence score result"""

    overall_score: float  # 0.0 to 1.0
    level: ConfidenceLevel
    factors: dict[str, float]  # Individual factor scores
    reasoning: list[str]  # Explanation of score
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())

    def is_confident(self, threshold: float = 0.7) -> bool:
        """Check if confidence meets threshold"""
        return self.overall_score >= threshold

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "overall_score": self.overall_score,
            "level": self.level.value,
            "factors": self.factors,
            "reasoning": self.reasoning,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


class ConfidenceScorer:
    """
    Confidence Scorer for LLM Responses

    Calculates confidence based on multiple factors:
    1. Response completeness
    2. Uncertainty indicators
    3. Specificity and detail
    4. Consistency
    5. Model metadata (temperature, model quality)
    """

    # Uncertainty phrases that indicate low confidence
    UNCERTAINTY_PHRASES = [
        "i think",
        "maybe",
        "perhaps",
        "possibly",
        "might be",
        "could be",
        "not sure",
        "uncertain",
        "unclear",
        "ambiguous",
        "i'm not certain",
        "i don't know",
        "hard to say",
        "it depends",
        "it's possible",
        "it seems",
        "appears to be",
    ]

    # Hedging words that reduce confidence
    HEDGING_WORDS = [
        "probably",
        "likely",
        "unlikely",
        "somewhat",
        "fairly",
        "relatively",
        "generally",
        "typically",
        "usually",
        "often",
    ]

    def __init__(self, weights: dict[str, float] | None = None, min_response_length: int = 50):
        """
        Initialize confidence scorer

        Args:
            weights: Custom weights for each factor (default: equal weights)
            min_response_length: Minimum expected response length
        """
        self.weights = weights or {
            "completeness": 0.25,
            "certainty": 0.25,
            "specificity": 0.20,
            "consistency": 0.15,
            "model_quality": 0.15,
        }
        self.min_response_length = min_response_length
        self._max_history = 1000

        self.history: list[ConfidenceScore] = []

    def calculate_confidence(
        self, prompt: str, response: str, metadata: dict[str, Any] | None = None
    ) -> ConfidenceScore:
        """
        Calculate confidence score for a response

        Args:
            prompt: Original prompt
            response: LLM response
            metadata: Additional metadata (model, temperature, etc.)

        Returns:
            ConfidenceScore object
        """
        metadata = metadata or {}
        factors = {}
        reasoning = []

        # 1. Completeness score
        completeness, comp_reason = self._calculate_completeness(prompt, response)
        factors["completeness"] = completeness
        reasoning.extend(comp_reason)

        # 2. Certainty score (inverse of uncertainty)
        certainty, cert_reason = self._calculate_certainty(response)
        factors["certainty"] = certainty
        reasoning.extend(cert_reason)

        # 3. Specificity score
        specificity, spec_reason = self._calculate_specificity(response)
        factors["specificity"] = specificity
        reasoning.extend(spec_reason)

        # 4. Consistency score
        consistency, cons_reason = self._calculate_consistency(response)
        factors["consistency"] = consistency
        reasoning.extend(cons_reason)

        # 5. Model quality score
        model_quality, model_reason = self._calculate_model_quality(metadata)
        factors["model_quality"] = model_quality
        reasoning.extend(model_reason)

        # Calculate weighted overall score
        overall_score = sum(factors[factor] * self.weights[factor] for factor in self.weights)

        # Determine confidence level
        level = self._determine_level(overall_score)

        # Create confidence score object
        score = ConfidenceScore(
            overall_score=overall_score, level=level, factors=factors, reasoning=reasoning, metadata=metadata
        )

        # Add to history
        self.history.append(score)

        if len(self.history) > self._max_history:
            self.history = self.history[-self._max_history :]

        return score

    def _calculate_completeness(self, _prompt: str, response: str) -> tuple[float, list[str]]:
        """Calculate response completeness"""
        reasoning = []
        score = 0.0

        # Check response length
        if len(response) < self.min_response_length:
            score = 0.3
            reasoning.append(f"Response too short ({len(response)} chars)")
        elif len(response) < self.min_response_length * 2:
            score = 0.6
            reasoning.append("Response length adequate")
        else:
            score = 0.9
            reasoning.append("Response length good")

        # Check for incomplete sentences
        if response.endswith("...") or response.count("...") > 2:
            score *= 0.7
            reasoning.append("Response appears incomplete (ellipsis)")

        # Check for truncation indicators
        truncation_indicators = ["[truncated]", "[continued]", "...and more"]
        if any(indicator in response.lower() for indicator in truncation_indicators):
            score *= 0.5
            reasoning.append("Response appears truncated")

        return min(score, 1.0), reasoning

    def _calculate_certainty(self, response: str) -> tuple[float, list[str]]:
        """Calculate response certainty (inverse of uncertainty)"""
        reasoning = []
        response_lower = response.lower()

        # Count uncertainty phrases
        uncertainty_count = sum(1 for phrase in self.UNCERTAINTY_PHRASES if phrase in response_lower)

        # Count hedging words
        hedging_count = sum(1 for word in self.HEDGING_WORDS if f" {word} " in f" {response_lower} ")

        # Calculate certainty score
        total_uncertainty = uncertainty_count + (hedging_count * 0.5)

        if total_uncertainty == 0:
            score = 1.0
            reasoning.append("No uncertainty indicators found")
        elif total_uncertainty <= 2:
            score = 0.8
            reasoning.append(f"Minor uncertainty ({int(total_uncertainty)} indicators)")
        elif total_uncertainty <= 5:
            score = 0.5
            reasoning.append(f"Moderate uncertainty ({int(total_uncertainty)} indicators)")
        else:
            score = 0.2
            reasoning.append(f"High uncertainty ({int(total_uncertainty)} indicators)")

        return score, reasoning

    def _calculate_specificity(self, response: str) -> tuple[float, list[str]]:
        """Calculate response specificity and detail level"""
        reasoning = []

        # Check for specific details (numbers, code, examples)
        has_numbers = bool(re.search(r"\d+", response))
        has_code = bool(re.search(r"```|`[^`]+`", response))
        has_examples = bool(re.search(r"(for example|e\.g\.|such as|like)", response, re.IGNORECASE))
        has_lists = bool(re.search(r"^\s*[-*\d]+\.?\s", response, re.MULTILINE))

        specificity_indicators = sum([has_numbers, has_code, has_examples, has_lists])

        if specificity_indicators >= 3:
            score = 1.0
            reasoning.append("High specificity (numbers, code, examples, lists)")
        elif specificity_indicators == 2:
            score = 0.7
            reasoning.append("Good specificity (some concrete details)")
        elif specificity_indicators == 1:
            score = 0.5
            reasoning.append("Moderate specificity (limited details)")
        else:
            score = 0.3
            reasoning.append("Low specificity (mostly abstract)")

        # Check for vague language
        vague_phrases = ["something", "somehow", "various", "several", "many", "some"]
        vague_count = sum(1 for phrase in vague_phrases if phrase in response.lower())

        if vague_count > 5:
            score *= 0.7
            reasoning.append(f"Contains vague language ({vague_count} instances)")

        return score, reasoning

    def _calculate_consistency(self, response: str) -> tuple[float, list[str]]:
        """Calculate internal consistency of response"""
        reasoning = []
        score = 1.0

        # Check for contradictions
        contradiction_patterns = [
            (r"(yes|true|correct).*?(no|false|incorrect)", "yes/no contradiction"),
            (r"(always|never).*?(sometimes|occasionally)", "absolute/conditional contradiction"),
            (r"(should|must).*?(should not|must not)", "directive contradiction"),
        ]

        for pattern, description in contradiction_patterns:
            if re.search(pattern, response, re.IGNORECASE | re.DOTALL):
                score *= 0.6
                reasoning.append(f"Potential contradiction: {description}")

        # Check for self-corrections
        correction_phrases = ["actually", "correction", "i mean", "rather", "instead"]
        correction_count = sum(1 for phrase in correction_phrases if phrase in response.lower())

        if correction_count > 0:
            score *= 1.0 - (correction_count * 0.1)
            reasoning.append(f"Contains self-corrections ({correction_count})")

        if score == 1.0:
            reasoning.append("No consistency issues detected")

        return max(score, 0.0), reasoning

    def _calculate_model_quality(self, metadata: dict[str, Any]) -> tuple[float, list[str]]:
        """Calculate score based on model metadata"""
        reasoning = []
        score = 0.7  # Default score

        # Model quality tiers
        model = metadata.get("model", "").lower()
        if "gpt-4" in model or "claude-3" in model:
            score = 0.95
            reasoning.append("High-quality model (GPT-4/Claude-3)")
        elif "gpt-3.5" in model or "claude-2" in model:
            score = 0.8
            reasoning.append("Good quality model (GPT-3.5/Claude-2)")
        elif model:
            score = 0.6
            reasoning.append(f"Standard model ({model})")
        else:
            reasoning.append("Model unknown (default score)")

        # Temperature adjustment
        temperature = metadata.get("temperature")
        if temperature is not None:
            if temperature <= 0.3:
                score *= 1.1  # More deterministic = higher confidence
                reasoning.append(f"Low temperature ({temperature}) increases confidence")
            elif temperature >= 0.9:
                score *= 0.9  # More creative = lower confidence
                reasoning.append(f"High temperature ({temperature}) reduces confidence")

        # Token count (longer responses may indicate more thought)
        token_count = metadata.get("token_count", 0)
        if token_count > 1000:
            score *= 1.05
            reasoning.append("Detailed response (high token count)")

        return min(score, 1.0), reasoning

    def _determine_level(self, score: float) -> ConfidenceLevel:
        """Determine confidence level from score"""
        if score >= 0.9:
            return ConfidenceLevel.VERY_HIGH
        elif score >= 0.7:
            return ConfidenceLevel.HIGH
        elif score >= 0.5:
            return ConfidenceLevel.MEDIUM
        elif score >= 0.3:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.VERY_LOW

    def score_response(self, response: str, prompt: str = "", metadata: dict[str, Any] | None = None) -> ConfidenceScore:
        """
        Score a response for confidence (convenience wrapper).

        Args:
            response: LLM response text
            prompt: Original prompt (optional)
            metadata: Additional metadata (model, temperature, etc.)

        Returns:
            ConfidenceScore object
        """
        return self.calculate_confidence(prompt=prompt, response=response, metadata=metadata)

    def get_average_confidence(self, limit: int | None = None) -> float:
        """Get average confidence from recent history"""
        if not self.history:
            return 0.0

        recent = self.history[-limit:] if limit else self.history
        return sum(score.overall_score for score in recent) / len(recent)

    def get_confidence_trend(self, window: int = 10) -> str:
        """Get confidence trend (improving/declining/stable)"""
        if len(self.history) < window:
            return "insufficient_data"

        recent = self.history[-window:]
        first_half = recent[: window // 2]
        second_half = recent[window // 2 :]

        first_avg = sum(s.overall_score for s in first_half) / len(first_half)
        second_avg = sum(s.overall_score for s in second_half) / len(second_half)

        diff = second_avg - first_avg

        if diff > 0.1:
            return "improving"
        elif diff < -0.1:
            return "declining"
        else:
            return "stable"

    def export_stats(self) -> dict[str, Any]:
        """Export confidence statistics"""
        if not self.history:
            return {"total_scores": 0, "average_confidence": 0.0, "trend": "no_data"}

        return {
            "total_scores": len(self.history),
            "average_confidence": self.get_average_confidence(),
            "recent_average": self.get_average_confidence(limit=10),
            "trend": self.get_confidence_trend(),
            "level_distribution": self._get_level_distribution(),
            "factor_averages": self._get_factor_averages(),
        }

    def _get_level_distribution(self) -> dict[str, int]:
        """Get distribution of confidence levels"""
        distribution = {level.value: 0 for level in ConfidenceLevel}
        for score in self.history:
            distribution[score.level.value] += 1
        return distribution

    def _get_factor_averages(self) -> dict[str, float]:
        """Get average scores for each factor"""
        if not self.history:
            return {}

        factor_sums = {}
        for score in self.history:
            for factor, value in score.factors.items():
                factor_sums[factor] = factor_sums.get(factor, 0) + value

        return {factor: total / len(self.history) for factor, total in factor_sums.items()}


# Global scorer instance
_scorer_instance: ConfidenceScorer | None = None


def get_confidence_scorer(weights: dict[str, float] | None = None, min_response_length: int = 50) -> ConfidenceScorer:
    """Get or create global confidence scorer instance"""
    global _scorer_instance

    if _scorer_instance is None:
        _scorer_instance = ConfidenceScorer(weights=weights, min_response_length=min_response_length)

    return _scorer_instance


def reset_scorer() -> None:
    """Reset global scorer instance (for testing)"""
    global _scorer_instance
    _scorer_instance = None


__version__ = "1.0.0"
__all__ = [
    "ConfidenceScorer",
    "ConfidenceScore",
    "ConfidenceLevel",
    "get_confidence_scorer",
    "reset_scorer",
]
