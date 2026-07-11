"""Tests for scripts.collaboration.adaptive_role_selector.

Covers AdaptiveRoleSelector's three-tier selection strategy, manual stats
updates, role effectiveness reporting, and graceful degradation.
"""

from __future__ import annotations

from typing import Any

from scripts.collaboration.adaptive_role_selector import AdaptiveRoleSelector

# ---------------------------------------------------------------------------
# Stub helpers
# ---------------------------------------------------------------------------


class StubFingerprint:
    """Stub PerformanceFingerprint for controlled testing."""

    def __init__(
        self,
        similar: list[dict[str, Any]] | None = None,
        fingerprints: list[dict[str, Any]] | None = None,
        stats: dict[str, Any] | None = None,
    ):
        self._similar = similar or []
        self._fingerprints = fingerprints or []
        self._stats = stats or {"top_roles": []}

    def find_similar(self, _task: str, top_k: int = 3) -> list[dict[str, Any]]:  # noqa: ARG002
        return list(self._similar)

    def get_all_fingerprints(self) -> list[dict[str, Any]]:
        return list(self._fingerprints)

    def get_stats(self) -> dict[str, Any]:
        return dict(self._stats)


def _make_case(
    roles: list[str] | None = None,
    success: bool = True,
    duration: float = 10.0,
    similarity: float = 0.8,
    intent: str | None = None,
) -> dict[str, Any]:
    return {
        "roles_used": ["architect", "coder"] if roles is None else roles,
        "success": success,
        "total_duration": duration,
        "similarity": similarity,
        "intent": intent,
    }


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------


class TestInit:
    def test_default_creates_fingerprint(self):
        selector = AdaptiveRoleSelector()
        assert selector._fp is not None
        assert selector._role_stats == {}

    def test_with_provided_fingerprint(self):
        fp = StubFingerprint()
        selector = AdaptiveRoleSelector(fingerprint_db=fp)
        assert selector._fp is fp

    def test_role_stats_starts_empty(self):
        selector = AdaptiveRoleSelector(fingerprint_db=StubFingerprint())
        assert selector._role_stats == {}


# ---------------------------------------------------------------------------
# select_roles - tier 1: similar tasks
# ---------------------------------------------------------------------------


class TestSelectFromSimilarTasks:
    def test_returns_roles_from_similar_successful_case(self):
        similar = [_make_case(roles=["architect", "coder"], success=True, similarity=0.9)]
        selector = AdaptiveRoleSelector(fingerprint_db=StubFingerprint(similar=similar))
        result = selector.select_roles("implement auth")
        assert "architect" in result
        assert "coder" in result

    def test_returns_empty_when_no_similar_cases(self):
        selector = AdaptiveRoleSelector(fingerprint_db=StubFingerprint(similar=[]))
        result = selector.select_roles("implement auth")
        assert result == []

    def test_returns_empty_when_similar_cases_all_failed(self):
        similar = [_make_case(roles=["architect", "coder"], success=False)]
        selector = AdaptiveRoleSelector(fingerprint_db=StubFingerprint(similar=similar))
        result = selector.select_roles("implement auth")
        assert result == []

    def test_returns_empty_when_similar_cases_no_roles(self):
        similar = [_make_case(roles=[], success=True)]
        selector = AdaptiveRoleSelector(fingerprint_db=StubFingerprint(similar=similar))
        result = selector.select_roles("implement auth")
        assert result == []

    def test_filters_by_min_success_rate(self):
        similar = [
            _make_case(roles=["architect", "coder"], success=True, similarity=0.9),
            _make_case(roles=["architect", "coder"], success=True, similarity=0.9),
            _make_case(roles=["architect", "coder"], success=False, similarity=0.9),
        ]
        selector = AdaptiveRoleSelector(fingerprint_db=StubFingerprint(similar=similar))
        result = selector.select_roles("implement auth", min_success_rate=0.8)
        assert result == []

    def test_passes_min_success_rate(self):
        similar = [
            _make_case(roles=["architect", "coder"], success=True, similarity=0.9),
            _make_case(roles=["architect", "coder"], success=True, similarity=0.9),
        ]
        selector = AdaptiveRoleSelector(fingerprint_db=StubFingerprint(similar=similar))
        result = selector.select_roles("implement auth", min_success_rate=0.5)
        assert "architect" in result

    def test_respects_max_roles(self):
        similar = [_make_case(roles=["a", "b", "c", "d", "e", "f", "g"], success=True)]
        selector = AdaptiveRoleSelector(fingerprint_db=StubFingerprint(similar=similar))
        result = selector.select_roles("task", max_roles=3)
        assert len(result) <= 3

    def test_selects_best_combination_by_score(self):
        similar = [
            _make_case(roles=["architect", "coder"], success=True, similarity=0.95),
            _make_case(roles=["tester", "coder"], success=True, similarity=0.5),
        ]
        selector = AdaptiveRoleSelector(fingerprint_db=StubFingerprint(similar=similar))
        result = selector.select_roles("task")
        assert "architect" in result

    def test_aggregates_multiple_successful_cases(self):
        similar = [
            _make_case(roles=["architect", "coder"], success=True, duration=10.0, similarity=0.8),
            _make_case(roles=["architect", "coder"], success=True, duration=20.0, similarity=0.9),
        ]
        selector = AdaptiveRoleSelector(fingerprint_db=StubFingerprint(similar=similar))
        result = selector.select_roles("task")
        assert sorted(result) == ["architect", "coder"]

    def test_different_combinations_tracked_separately(self):
        similar = [
            _make_case(roles=["architect", "coder"], success=True, similarity=0.9),
            _make_case(roles=["tester", "coder"], success=True, similarity=0.95),
        ]
        selector = AdaptiveRoleSelector(fingerprint_db=StubFingerprint(similar=similar))
        result = selector.select_roles("task")
        assert len(result) <= 5


# ---------------------------------------------------------------------------
# select_roles - tier 2: intent-based
# ---------------------------------------------------------------------------


class TestSelectByIntent:
    def test_falls_back_to_intent_when_no_similar(self):
        fingerprints = [
            _make_case(roles=["architect", "coder"], success=True, intent="design"),
            _make_case(roles=["architect", "coder"], success=True, intent="design"),
        ]
        selector = AdaptiveRoleSelector(
            fingerprint_db=StubFingerprint(similar=[], fingerprints=fingerprints)
        )
        result = selector.select_roles("task", intent="design")
        assert "architect" in result
        assert "coder" in result

    def test_intent_no_matches_returns_empty(self):
        fingerprints = [_make_case(roles=["architect"], success=True, intent="design")]
        selector = AdaptiveRoleSelector(
            fingerprint_db=StubFingerprint(similar=[], fingerprints=fingerprints)
        )
        result = selector.select_roles("task", intent="coding")
        assert result == []

    def test_intent_filters_by_success_rate(self):
        fingerprints = [
            _make_case(roles=["architect", "coder"], success=True, intent="design"),
            _make_case(roles=["architect", "coder"], success=False, intent="design"),
            _make_case(roles=["architect", "coder"], success=False, intent="design"),
        ]
        selector = AdaptiveRoleSelector(
            fingerprint_db=StubFingerprint(similar=[], fingerprints=fingerprints)
        )
        result = selector.select_roles("task", intent="design", min_success_rate=0.5)
        assert result == []

    def test_intent_respects_max_roles(self):
        fingerprints = [
            _make_case(roles=["a", "b", "c", "d", "e", "f"], success=True, intent="x"),
        ]
        selector = AdaptiveRoleSelector(
            fingerprint_db=StubFingerprint(similar=[], fingerprints=fingerprints)
        )
        result = selector.select_roles("task", intent="x", max_roles=2)
        assert len(result) <= 2

    def test_intent_selects_best_success_rate(self):
        fingerprints = [
            _make_case(roles=["architect", "coder"], success=True, intent="design"),
            _make_case(roles=["architect", "coder"], success=True, intent="design"),
            _make_case(roles=["tester", "coder"], success=True, intent="design"),
        ]
        selector = AdaptiveRoleSelector(
            fingerprint_db=StubFingerprint(similar=[], fingerprints=fingerprints)
        )
        result = selector.select_roles("task", intent="design")
        assert "architect" in result

    def test_intent_skips_fingerprints_without_roles(self):
        fingerprints = [
            _make_case(roles=[], success=True, intent="design"),
            _make_case(roles=["architect"], success=True, intent="design"),
        ]
        selector = AdaptiveRoleSelector(
            fingerprint_db=StubFingerprint(similar=[], fingerprints=fingerprints)
        )
        result = selector.select_roles("task", intent="design")
        assert "architect" in result


# ---------------------------------------------------------------------------
# select_roles - tier 3: fallback
# ---------------------------------------------------------------------------


class TestSelectFallback:
    def test_returns_empty_when_no_data_and_no_intent(self):
        selector = AdaptiveRoleSelector(fingerprint_db=StubFingerprint())
        result = selector.select_roles("task")
        assert result == []

    def test_returns_empty_when_no_data_with_intent(self):
        selector = AdaptiveRoleSelector(
            fingerprint_db=StubFingerprint(fingerprints=[])
        )
        result = selector.select_roles("task", intent="design")
        assert result == []

    def test_similar_takes_precedence_over_intent(self):
        similar = [_make_case(roles=["architect"], success=True, similarity=0.9)]
        fingerprints = [_make_case(roles=["coder"], success=True, intent="design")]
        selector = AdaptiveRoleSelector(
            fingerprint_db=StubFingerprint(similar=similar, fingerprints=fingerprints)
        )
        result = selector.select_roles("task", intent="design")
        assert "architect" in result
        assert "coder" not in result

    def test_falls_to_intent_when_similar_returns_empty(self):
        similar = [_make_case(roles=["architect"], success=False)]
        fingerprints = [_make_case(roles=["coder"], success=True, intent="design")]
        selector = AdaptiveRoleSelector(
            fingerprint_db=StubFingerprint(similar=similar, fingerprints=fingerprints)
        )
        result = selector.select_roles("task", intent="design")
        assert "coder" in result


# ---------------------------------------------------------------------------
# update_stats
# ---------------------------------------------------------------------------


class TestUpdateStats:
    def test_updates_single_role_success(self):
        selector = AdaptiveRoleSelector(fingerprint_db=StubFingerprint())
        selector.update_stats(["architect"], True, 10.0)
        assert "architect" in selector._role_stats
        assert selector._role_stats["architect"]["total"] == 1
        assert selector._role_stats["architect"]["successes"] == 1
        assert selector._role_stats["architect"]["durations"] == [10.0]

    def test_updates_single_role_failure(self):
        selector = AdaptiveRoleSelector(fingerprint_db=StubFingerprint())
        selector.update_stats(["coder"], False, 5.0)
        assert selector._role_stats["coder"]["successes"] == 0
        assert selector._role_stats["coder"]["total"] == 1

    def test_updates_multiple_roles(self):
        selector = AdaptiveRoleSelector(fingerprint_db=StubFingerprint())
        selector.update_stats(["architect", "coder", "tester"], True, 15.0)
        assert len(selector._role_stats) == 3
        for role in ["architect", "coder", "tester"]:
            assert selector._role_stats[role]["total"] == 1
            assert selector._role_stats[role]["successes"] == 1

    def test_accumulates_multiple_updates(self):
        selector = AdaptiveRoleSelector(fingerprint_db=StubFingerprint())
        selector.update_stats(["architect"], True, 10.0)
        selector.update_stats(["architect"], False, 20.0)
        selector.update_stats(["architect"], True, 30.0)
        assert selector._role_stats["architect"]["total"] == 3
        assert selector._role_stats["architect"]["successes"] == 2
        assert selector._role_stats["architect"]["durations"] == [10.0, 20.0, 30.0]

    def test_empty_roles_list_noop(self):
        selector = AdaptiveRoleSelector(fingerprint_db=StubFingerprint())
        selector.update_stats([], True, 10.0)
        assert selector._role_stats == {}


# ---------------------------------------------------------------------------
# get_role_report
# ---------------------------------------------------------------------------


class TestGetRoleReport:
    def test_empty_report_when_no_stats(self):
        selector = AdaptiveRoleSelector(fingerprint_db=StubFingerprint())
        report = selector.get_role_report()
        assert report == {}

    def test_report_from_manual_stats(self):
        selector = AdaptiveRoleSelector(fingerprint_db=StubFingerprint())
        selector.update_stats(["architect"], True, 10.0)
        selector.update_stats(["architect"], True, 20.0)
        report = selector.get_role_report()
        assert "architect" in report
        assert report["architect"]["total"] == 2
        assert report["architect"]["successes"] == 2
        assert report["architect"]["success_rate"] == 1.0
        assert report["architect"]["avg_duration"] == 15.0

    def test_report_with_zero_success(self):
        selector = AdaptiveRoleSelector(fingerprint_db=StubFingerprint())
        selector.update_stats(["coder"], False, 5.0)
        report = selector.get_role_report()
        assert report["coder"]["success_rate"] == 0.0

    def test_report_merges_fingerprint_stats(self):
        fp_stats = {
            "top_roles": [
                {"role": "tester", "count": 10},
            ]
        }
        selector = AdaptiveRoleSelector(fingerprint_db=StubFingerprint(stats=fp_stats))
        selector.update_stats(["architect"], True, 10.0)
        report = selector.get_role_report()
        assert "architect" in report
        assert "tester" in report
        assert report["tester"]["total"] == 10
        assert report["tester"]["successes"] == 0

    def test_report_does_not_overwrite_manual_with_fp(self):
        fp_stats = {
            "top_roles": [
                {"role": "architect", "count": 100},
            ]
        }
        selector = AdaptiveRoleSelector(fingerprint_db=StubFingerprint(stats=fp_stats))
        selector.update_stats(["architect"], True, 10.0)
        report = selector.get_role_report()
        assert report["architect"]["total"] == 1

    def test_report_avg_duration_rounded(self):
        selector = AdaptiveRoleSelector(fingerprint_db=StubFingerprint())
        selector.update_stats(["architect"], True, 10.123456)
        selector.update_stats(["architect"], True, 20.654321)
        report = selector.get_role_report()
        assert report["architect"]["avg_duration"] == round(30.777777 / 2, 2)

    def test_report_success_rate_rounded(self):
        selector = AdaptiveRoleSelector(fingerprint_db=StubFingerprint())
        for _ in range(3):
            selector.update_stats(["architect"], True, 10.0)
        selector.update_stats(["architect"], False, 10.0)
        report = selector.get_role_report()
        assert report["architect"]["success_rate"] == 0.75

    def test_report_empty_durations(self):
        selector = AdaptiveRoleSelector(fingerprint_db=StubFingerprint())
        selector._role_stats = {"architect": {"total": 0, "successes": 0, "durations": []}}
        report = selector.get_role_report()
        assert report["architect"]["avg_duration"] == 0.0
        assert report["architect"]["success_rate"] == 0.0
