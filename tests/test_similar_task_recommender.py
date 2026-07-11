"""Tests for scripts.collaboration.similar_task_recommender.

Covers SimilarTaskRecommender: recommend(), get_role_suggestion(),
and helper methods (_extract_most_common_roles, _extract_most_common_intent,
_calculate_avg_duration, _determine_confidence).
"""

from __future__ import annotations

from typing import Any

from scripts.collaboration.similar_task_recommender import SimilarTaskRecommender


class StubFingerprint:
    """Stub PerformanceFingerprint for controlled testing."""

    def __init__(self, similar: list[dict[str, Any]] | None = None):
        self._similar = similar or []

    def find_similar(self, _task: str, top_k: int = 3) -> list[dict[str, Any]]:  # noqa: ARG002
        return list(self._similar)


def _make_case(
    task: str = "test task",
    roles: list[str] | None = None,
    intent: str | None = "implement",
    success: bool = True,
    duration: float = 10.0,
    similarity: float = 0.8,
) -> dict[str, Any]:
    return {
        "task": task,
        "roles_used": ["architect", "coder"] if roles is None else roles,
        "intent": intent,
        "success": success,
        "total_duration": duration,
        "similarity": similarity,
    }


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


class TestInit:
    def test_init_with_explicit_fingerprint(self):
        fp = StubFingerprint()
        rec = SimilarTaskRecommender(fingerprint_db=fp)  # type: ignore[arg-type]
        assert rec._fp is fp

    def test_init_creates_default_fingerprint(self):
        rec = SimilarTaskRecommender()
        assert rec._fp is not None


# ---------------------------------------------------------------------------
# recommend
# ---------------------------------------------------------------------------


class TestRecommend:
    def test_no_similar_cases_returns_low_confidence(self):
        rec = SimilarTaskRecommender(fingerprint_db=StubFingerprint(similar=[]))  # type: ignore[arg-type]
        result = rec.recommend("new task")
        assert result["similar_cases"] == []
        assert result["recommended_roles"] == []
        assert result["recommended_intent"] is None
        assert result["estimated_duration_s"] == 0.0
        assert result["confidence"] == "low"

    def test_with_successful_cases(self):
        cases = [_make_case(success=True, similarity=0.85), _make_case(success=True, similarity=0.75)]
        rec = SimilarTaskRecommender(fingerprint_db=StubFingerprint(cases))  # type: ignore[arg-type]
        result = rec.recommend("implement auth")
        assert len(result["similar_cases"]) == 2
        assert result["confidence"] == "high"
        assert len(result["recommended_roles"]) > 0
        assert result["recommended_intent"] == "implement"

    def test_with_no_successful_cases(self):
        cases = [_make_case(success=False, roles=["architect"], intent="review", similarity=0.6)]
        rec = SimilarTaskRecommender(fingerprint_db=StubFingerprint(cases))  # type: ignore[arg-type]
        result = rec.recommend("review code")
        assert len(result["similar_cases"]) == 1
        assert result["recommended_roles"] == ["architect"]
        assert result["recommended_intent"] == "review"
        assert result["confidence"] == "medium"

    def test_with_no_successful_cases_and_no_roles(self):
        cases = [_make_case(success=False, roles=[], intent=None, similarity=0.3)]
        rec = SimilarTaskRecommender(fingerprint_db=StubFingerprint(cases))  # type: ignore[arg-type]
        result = rec.recommend("unknown task")
        assert result["recommended_roles"] == []
        assert result["recommended_intent"] is None
        assert result["confidence"] == "low"

    def test_formatted_cases_contain_correct_fields(self):
        cases = [_make_case(task="auth", roles=["coder"], intent="test", success=True, duration=5.5, similarity=0.9)]
        rec = SimilarTaskRecommender(fingerprint_db=StubFingerprint(cases))  # type: ignore[arg-type]
        result = rec.recommend("auth")
        case = result["similar_cases"][0]
        assert case["task"] == "auth"
        assert case["roles"] == ["coder"]
        assert case["intent"] == "test"
        assert case["success"] is True
        assert case["duration_s"] == 5.5
        assert case["similarity"] == 0.9

    def test_estimated_duration_is_average(self):
        cases = [
            _make_case(success=True, duration=10.0, similarity=0.8),
            _make_case(success=True, duration=20.0, similarity=0.7),
        ]
        rec = SimilarTaskRecommender(fingerprint_db=StubFingerprint(cases))  # type: ignore[arg-type]
        result = rec.recommend("task")
        assert result["estimated_duration_s"] == 15.0

    def test_estimated_duration_ignores_zero(self):
        cases = [
            _make_case(success=True, duration=0.0, similarity=0.8),
            _make_case(success=True, duration=10.0, similarity=0.7),
        ]
        rec = SimilarTaskRecommender(fingerprint_db=StubFingerprint(cases))  # type: ignore[arg-type]
        result = rec.recommend("task")
        assert result["estimated_duration_s"] == 10.0


# ---------------------------------------------------------------------------
# get_role_suggestion
# ---------------------------------------------------------------------------


class TestGetRoleSuggestion:
    def test_returns_roles_from_recommend(self):
        cases = [_make_case(success=True, roles=["architect", "coder"], similarity=0.9)]
        rec = SimilarTaskRecommender(fingerprint_db=StubFingerprint(cases))  # type: ignore[arg-type]
        roles = rec.get_role_suggestion("implement feature")
        assert "architect" in roles
        assert "coder" in roles

    def test_returns_empty_when_no_data(self):
        rec = SimilarTaskRecommender(fingerprint_db=StubFingerprint([]))  # type: ignore[arg-type]
        assert rec.get_role_suggestion("new task") == []


# ---------------------------------------------------------------------------
# _extract_most_common_roles
# ---------------------------------------------------------------------------


class TestExtractMostCommonRoles:
    def test_returns_most_common_combo(self):
        rec = SimilarTaskRecommender(fingerprint_db=StubFingerprint())  # type: ignore[arg-type]
        cases = [
            {"roles": ["architect", "coder"]},
            {"roles": ["architect", "coder"]},
            {"roles": ["tester"]},
        ]
        roles = rec._extract_most_common_roles(cases)
        assert set(roles) == {"architect", "coder"}

    def test_returns_union_when_no_clear_winner(self):
        rec = SimilarTaskRecommender(fingerprint_db=StubFingerprint())  # type: ignore[arg-type]
        cases = [{"roles": []}, {"roles": []}]
        roles = rec._extract_most_common_roles(cases)
        assert roles == []

    def test_empty_cases(self):
        rec = SimilarTaskRecommender(fingerprint_db=StubFingerprint())  # type: ignore[arg-type]
        assert rec._extract_most_common_roles([]) == []

    def test_cases_with_no_roles_key(self):
        rec = SimilarTaskRecommender(fingerprint_db=StubFingerprint())  # type: ignore[arg-type]
        cases = [{}, {}]
        roles = rec._extract_most_common_roles(cases)
        assert roles == []


# ---------------------------------------------------------------------------
# _extract_most_common_intent
# ---------------------------------------------------------------------------


class TestExtractMostCommonIntent:
    def test_returns_most_common(self):
        rec = SimilarTaskRecommender(fingerprint_db=StubFingerprint())  # type: ignore[arg-type]
        cases = [{"intent": "implement"}, {"intent": "implement"}, {"intent": "review"}]
        assert rec._extract_most_common_intent(cases) == "implement"

    def test_returns_none_when_no_intents(self):
        rec = SimilarTaskRecommender(fingerprint_db=StubFingerprint())  # type: ignore[arg-type]
        cases = [{"intent": None}, {}]
        assert rec._extract_most_common_intent(cases) is None

    def test_empty_cases(self):
        rec = SimilarTaskRecommender(fingerprint_db=StubFingerprint())  # type: ignore[arg-type]
        assert rec._extract_most_common_intent([]) is None


# ---------------------------------------------------------------------------
# _calculate_avg_duration
# ---------------------------------------------------------------------------


class TestCalculateAvgDuration:
    def test_avg_of_positive_durations(self):
        rec = SimilarTaskRecommender(fingerprint_db=StubFingerprint())  # type: ignore[arg-type]
        cases = [{"duration_s": 10.0}, {"duration_s": 20.0}, {"duration_s": 30.0}]
        assert rec._calculate_avg_duration(cases) == 20.0

    def test_ignores_zero_durations(self):
        rec = SimilarTaskRecommender(fingerprint_db=StubFingerprint())  # type: ignore[arg-type]
        cases = [{"duration_s": 0.0}, {"duration_s": 10.0}]
        assert rec._calculate_avg_duration(cases) == 10.0

    def test_returns_zero_when_all_zero(self):
        rec = SimilarTaskRecommender(fingerprint_db=StubFingerprint())  # type: ignore[arg-type]
        cases = [{"duration_s": 0.0}, {"duration_s": 0.0}]
        assert rec._calculate_avg_duration(cases) == 0.0

    def test_empty_cases(self):
        rec = SimilarTaskRecommender(fingerprint_db=StubFingerprint())  # type: ignore[arg-type]
        assert rec._calculate_avg_duration([]) == 0.0


# ---------------------------------------------------------------------------
# _determine_confidence
# ---------------------------------------------------------------------------


class TestDetermineConfidence:
    def test_high_confidence(self):
        rec = SimilarTaskRecommender(fingerprint_db=StubFingerprint())  # type: ignore[arg-type]
        assert rec._determine_confidence(0.8) == "high"
        assert rec._determine_confidence(0.71) == "high"
        assert rec._determine_confidence(1.0) == "high"

    def test_medium_confidence(self):
        rec = SimilarTaskRecommender(fingerprint_db=StubFingerprint())  # type: ignore[arg-type]
        assert rec._determine_confidence(0.5) == "medium"
        assert rec._determine_confidence(0.41) == "medium"
        assert rec._determine_confidence(0.7) == "medium"

    def test_low_confidence(self):
        rec = SimilarTaskRecommender(fingerprint_db=StubFingerprint())  # type: ignore[arg-type]
        assert rec._determine_confidence(0.4) == "low"
        assert rec._determine_confidence(0.3) == "low"
        assert rec._determine_confidence(0.0) == "low"
