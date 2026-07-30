#!/usr/bin/env python3
"""Integration tests for V4.4.2 P1-2 Dashboard Visibility Enhancement.

Verifies that ``render_dispatch_result`` renders the 6 tab sections
(Worker Outputs / Consensus / Risk Management / Retrospective /
Full Report / Raw Data) without crashing, for three scenarios:

1. A fully-populated ``DispatchResult`` (all fields set).
2. An empty ``DispatchResult`` (no worker_results, no consensus, no
   risk_management_md, no retrospective_report) — must not crash.
3. A result with only worker_results populated.

Streamlit is mocked via ``unittest.mock.patch`` so the tests do not
require an active Streamlit runtime.

Test plan reference: docs/prd/V4.4.2_PRD.md §4.3 (AC-1..AC-4).
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# Dashboard views import streamlit at module load time; skip if unavailable.
pytest.importorskip("streamlit")

from scripts.collaboration.dispatch_models import DispatchResult  # noqa: E402
from scripts.dashboard.dispatch_views import render_dispatch_result  # noqa: E402

pytestmark = pytest.mark.integration


def _build_mock_st() -> MagicMock:
    """Build a Mock streamlit module with working tabs() + expander() CMs.

    ``st.tabs(names)`` returns a list of N MagicMock context managers so
    ``with tab_workers:`` unpacking works. ``st.expander(label)`` returns
    a single MagicMock context manager. ``st.columns(n)`` returns N mocks.
    """
    mock_st = MagicMock()

    # Pre-build 6 tab context managers (render_dispatch_result uses 6 tabs).
    tab_cms = [MagicMock() for _ in range(6)]
    mock_st.tabs.return_value = tab_cms

    # st.expander returns a single context manager per call.
    mock_st.expander.side_effect = lambda *_, **__: MagicMock()

    # st.columns returns a list of N mocks.
    def _columns(n: int = 2, *_args: object, **_kwargs: object) -> list[MagicMock]:
        return [MagicMock() for _ in range(int(n) if isinstance(n, int) else 2)]

    mock_st.columns.side_effect = _columns
    return mock_st


def _full_result() -> DispatchResult:
    """A DispatchResult with all V4.4.2 tab fields populated."""
    return DispatchResult(
        success=True,
        task_description="Design a payment gateway",
        matched_roles=["architect", "security"],
        summary="## Summary\nAll roles completed.",
        worker_results=[
            {
                "worker_id": "arch-abc123",
                "role_id": "architect",
                "role_name": "架构师",
                "task_id": "T-1",
                "success": True,
                "output": "Architecture: microservices + API gateway.",
                "error": None,
            },
            {
                "worker_id": "sec-def456",
                "role_id": "security",
                "role_name": "安全专家",
                "task_id": "T-1",
                "success": True,
                "output": "Threat model: STRIDE applied.",
                "error": None,
            },
        ],
        consensus_records=[
            {"topic": "Use microservices", "outcome": "APPROVED"},
            {"topic": "Skip OAuth2", "outcome": "REJECTED"},
        ],
        risk_management_md="## Risk Management\n- R-001: delivery risk (exposure 0.15)",
        retrospective_report={"summary": "Retrospective: smooth delivery", "action_items": "Add more tests"},
        details={"timing": {"step1": 0.1, "step2": 0.2}},
        duration_seconds=1.23,
    )


def _empty_result() -> DispatchResult:
    """A DispatchResult with all V4.4.2 tab fields empty/default."""
    return DispatchResult(
        success=True,
        task_description="Empty task",
        matched_roles=[],
        summary="",
        worker_results=[],
        consensus_records=[],
        risk_management_md="",
        retrospective_report=None,
        details={},
        duration_seconds=0.0,
    )


# ── AC-1: 6 tabs rendered ──────────────────────────────────────────────


def test_render_dispatch_result_full_result_six_tabs() -> None:
    """AC-1: render_dispatch_result calls st.tabs with 6 labels for a full result."""
    with patch("scripts.dashboard.dispatch_views.st", new=_build_mock_st()) as mock_st:
        render_dispatch_result(_full_result(), duration=1.23)
        assert mock_st.tabs.called, "st.tabs was not called"
        tabs_args = mock_st.tabs.call_args.args[0]
        assert len(tabs_args) == 6, f"expected 6 tabs, got {len(tabs_args)}"
        expected_labels = [
            "👥 Worker Outputs",
            "🗳️ Consensus",
            "🛡️ Risk Management",
            "📊 Retrospective",
            "📝 Full Report",
            "🔍 Raw Data",
        ]
        for actual, expected in zip(tabs_args, expected_labels):
            assert actual == expected, f"tab label mismatch: {actual!r} != {expected!r}"


# ── AC-2: Worker Outputs tab shows each role ───────────────────────────


def test_render_dispatch_result_worker_outputs_expanders() -> None:
    """AC-2: Worker Outputs tab renders one expander per worker_result."""
    with patch("scripts.dashboard.dispatch_views.st", new=_build_mock_st()) as mock_st:
        render_dispatch_result(_full_result(), duration=1.23)
        # 2 worker_results → 2 expander calls.
        assert mock_st.expander.call_count == 2, (
            f"expected 2 expanders (one per worker), got {mock_st.expander.call_count}"
        )


# ── AC-3: Risk Management tab shows risk_management_md ─────────────────


def test_render_dispatch_result_risk_management_markdown() -> None:
    """AC-3: Risk Management tab calls st.markdown with risk_management_md."""
    with patch("scripts.dashboard.dispatch_views.st", new=_build_mock_st()) as mock_st:
        result = _full_result()
        render_dispatch_result(result, duration=1.0)
        # Collect all markdown calls' first arg and assert risk content is present.
        markdown_calls = [str(call.args[0]) if call.args else "" for call in mock_st.markdown.call_args_list]
        risk_rendered = any("Risk Management" in m for m in markdown_calls)
        assert risk_rendered, "risk_management_md content was not rendered via st.markdown"


# ── AC-4: empty result does not crash ──────────────────────────────────


def test_render_dispatch_result_empty_result_no_crash() -> None:
    """AC-4: empty result (no worker_results, no consensus, etc.) does not crash."""
    with patch("scripts.dashboard.dispatch_views.st", new=_build_mock_st()) as mock_st:
        # Should not raise.
        render_dispatch_result(_empty_result(), duration=0.0)
        # st.tabs still called with 6 labels.
        assert mock_st.tabs.called
        # st.info should be called for empty sections (no crash).
        assert mock_st.info.called, "expected st.info calls for empty sections"


# ── Bonus: result with only worker_results ─────────────────────────────


def test_render_dispatch_result_only_worker_results() -> None:
    """A result with only worker_results renders without crashing."""
    result = DispatchResult(
        success=True,
        task_description="Worker-only task",
        matched_roles=["architect"],
        worker_results=[
            {
                "worker_id": "arch-xyz",
                "role_id": "architect",
                "role_name": "架构师",
                "task_id": "T-1",
                "success": True,
                "output": "Done.",
                "error": None,
            }
        ],
    )
    with patch("scripts.dashboard.dispatch_views.st", new=_build_mock_st()) as mock_st:
        render_dispatch_result(result, duration=0.5)
        # One expander for the single worker.
        assert mock_st.expander.call_count == 1
        # st.tabs called with 6 labels.
        assert len(mock_st.tabs.call_args.args[0]) == 6
