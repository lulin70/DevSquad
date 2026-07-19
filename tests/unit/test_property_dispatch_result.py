"""Property-based tests for DispatchResult structural invariants.

Uses Hypothesis to verify that DispatchResult maintains its structural
invariants regardless of input variation:

1. ``duration_seconds`` is always non-negative.
2. ``matched_roles`` is a list of strings.
3. ``errors`` is a list of strings.
4. ``lang`` defaults to ``"zh"`` when not specified.
5. ``to_dict()`` round-trips all primary fields.
6. ``success`` flag is always a boolean.

These are structural invariants — they must hold for ANY valid construction
of DispatchResult, not just for the values we manually think to test.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from scripts.collaboration.dispatch_models import DispatchResult

pytestmark = [pytest.mark.unit]


# ---------------------------------------------------------------------------
# Input strategies
# ---------------------------------------------------------------------------

# Role names: simple ASCII identifiers (avoid exotic unicode in role names
# to keep tests deterministic and readable on failure).
_role_names = st.sampled_from(
    [
        "architect",
        "pm",
        "security",
        "tester",
        "coder",
        "devops",
        "ui",
        "reviewer",
    ]
)

_matched_roles = st.lists(_role_names, min_size=0, max_size=7)

# Task descriptions: keep printable ASCII, length 5-100, to avoid pathological
# inputs that would stress-test string handling rather than DispatchResult.
_task_description = st.text(
    alphabet=st.characters(min_codepoint=32, max_codepoint=126),
    min_size=5,
    max_size=100,
)

_summary = st.text(
    alphabet=st.characters(min_codepoint=32, max_codepoint=126),
    min_size=0,
    max_size=500,
)

# Errors: list of short error strings.
_errors = st.lists(
    st.text(
        alphabet=st.characters(min_codepoint=32, max_codepoint=126),
        min_size=1,
        max_size=80,
    ),
    min_size=0,
    max_size=5,
)

# Duration: non-negative float (we also verify the field accepts 0).
_duration = st.floats(min_value=0.0, max_value=3600.0, allow_nan=False, allow_infinity=False)

_lang = st.sampled_from(["zh", "en"])


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


@given(
    task_description=_task_description,
    matched_roles=_matched_roles,
    summary=_summary,
    errors=_errors,
    duration_seconds=_duration,
    lang=_lang,
)
@settings(max_examples=50, deadline=None)
def test_dispatch_result_duration_non_negative(
    task_description: str,
    matched_roles: list[str],
    summary: str,
    errors: list[str],
    duration_seconds: float,
    lang: str,
) -> None:
    """DispatchResult.duration_seconds must always be >= 0."""
    result = DispatchResult(
        success=True,
        task_description=task_description,
        matched_roles=matched_roles,
        summary=summary,
        errors=errors,
        duration_seconds=duration_seconds,
        lang=lang,
    )
    assert result.duration_seconds >= 0


@given(
    task_description=_task_description,
    matched_roles=_matched_roles,
)
@settings(max_examples=50, deadline=None)
def test_dispatch_result_matched_roles_always_list_of_str(
    task_description: str,
    matched_roles: list[str],
) -> None:
    """DispatchResult.matched_roles must always be a list of strings."""
    result = DispatchResult(
        success=True,
        task_description=task_description,
        matched_roles=matched_roles,
    )
    assert isinstance(result.matched_roles, list)
    assert all(isinstance(r, str) for r in result.matched_roles)


@given(
    task_description=_task_description,
    errors=_errors,
)
@settings(max_examples=50, deadline=None)
def test_dispatch_result_errors_always_list_of_str(
    task_description: str,
    errors: list[str],
) -> None:
    """DispatchResult.errors must always be a list of strings."""
    result = DispatchResult(
        success=False,
        task_description=task_description,
        errors=errors,
    )
    assert isinstance(result.errors, list)
    assert all(isinstance(e, str) for e in result.errors)


@given(task_description=_task_description)
@settings(max_examples=20, deadline=None)
def test_dispatch_result_lang_defaults_to_zh(task_description: str) -> None:
    """DispatchResult.lang must default to 'zh' when not specified."""
    result = DispatchResult(success=True, task_description=task_description)
    assert result.lang == "zh"


@given(
    success=st.booleans(),
    task_description=_task_description,
)
@settings(max_examples=20, deadline=None)
def test_dispatch_result_success_is_bool(success: bool, task_description: str) -> None:
    """DispatchResult.success must always be a boolean."""
    result = DispatchResult(success=success, task_description=task_description)
    assert isinstance(result.success, bool)


@given(
    task_description=_task_description,
    matched_roles=_matched_roles,
    summary=_summary,
    duration_seconds=_duration,
)
@settings(max_examples=30, deadline=None)
def test_dispatch_result_to_dict_round_trips_primary_fields(
    task_description: str,
    matched_roles: list[str],
    summary: str,
    duration_seconds: float,
) -> None:
    """DispatchResult.to_dict() must round-trip primary fields."""
    result = DispatchResult(
        success=True,
        task_description=task_description,
        matched_roles=matched_roles,
        summary=summary,
        duration_seconds=duration_seconds,
    )
    payload = result.to_dict()
    assert payload["success"] is True
    assert payload["task_description"] == task_description
    assert payload["matched_roles"] == matched_roles
    assert payload["summary"] == summary
    # duration_seconds is rounded in to_dict(), so verify approximate equality
    assert abs(payload["duration_seconds"] - duration_seconds) < 0.01


@given(
    task_description=_task_description,
    matched_roles=_matched_roles,
    errors=_errors,
)
@settings(max_examples=30, deadline=None)
def test_dispatch_result_to_dict_types_preserved(
    task_description: str,
    matched_roles: list[str],
    errors: list[str],
) -> None:
    """DispatchResult.to_dict() must preserve container types."""
    result = DispatchResult(
        success=True,
        task_description=task_description,
        matched_roles=matched_roles,
        errors=errors,
    )
    payload = result.to_dict()
    assert isinstance(payload, dict)
    assert isinstance(payload["matched_roles"], list)
    assert isinstance(payload["errors"], list)
    assert isinstance(payload["details"], dict)
