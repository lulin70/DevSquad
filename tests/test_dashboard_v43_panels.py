#!/usr/bin/env python3
"""Tests for V4.3.0 Dashboard panels (P1-6).

Verifies the four panel rendering functions in
``scripts/dashboard/v43_panels.py`` using a Mock Streamlit container so the
tests do not require an active Streamlit runtime.

Test plan reference: docs/testing/V4.3.0_TEST_PLAN.md §3 (P1-6 row).
"""

from __future__ import annotations

import os
import sys
import time
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Dashboard panels import streamlit at module load time; skip if unavailable.
pytest.importorskip("streamlit")

from scripts.dashboard.v43_panels import (  # noqa: E402
    render_loop_rollback_panel,
    render_plugin_events_panel,
    render_ponytail_mode_panel,
    render_todo_drift_panel,
)


def _make_container() -> MagicMock:
    """Build a Mock Streamlit container with ``columns()`` unpacking support.

    ``st.columns(n)`` returns a list of n container-like objects in real
    Streamlit; a bare ``MagicMock()`` returns a single non-iterable mock,
    which breaks ``col1, col2, col3 = target.columns(3)`` unpacking. This
    helper pre-configures the return value so unpacking works.
    """
    container = MagicMock()
    container.columns.return_value = [MagicMock() for _ in range(3)]
    return container


# ============================================================
# Ponytail mode indicator tests
# ============================================================


class TestPonytailModePanel:
    def test_ponytail_mode_indicator_lite(self) -> None:
        """lite mode renders a green success badge."""
        container = _make_container()
        render_ponytail_mode_panel("lite", container=container)
        container.markdown.assert_called_once()
        html = container.markdown.call_args.args[0]
        assert "status-success" in html
        assert "lite" in html
        container.metric.assert_called_once()
        assert container.metric.call_args.kwargs["value"] == "Lite"

    def test_ponytail_mode_indicator_full(self) -> None:
        """full mode renders a blue info badge."""
        container = _make_container()
        render_ponytail_mode_panel("full", container=container)
        container.markdown.assert_called_once()
        html = container.markdown.call_args.args[0]
        assert "status-info" in html
        assert "full" in html
        container.metric.assert_called_once()
        assert container.metric.call_args.kwargs["value"] == "Full"

    def test_ponytail_mode_indicator_ultra_renders_danger(self) -> None:
        """ultra mode (dead code) renders a red danger badge if it appears."""
        container = _make_container()
        render_ponytail_mode_panel("ultra", container=container)
        html = container.markdown.call_args.args[0]
        assert "status-danger" in html

    def test_ponytail_mode_indicator_empty_defaults_to_full(self) -> None:
        """Empty mode string defaults to full (backward compatible)."""
        container = _make_container()
        render_ponytail_mode_panel("", container=container)
        html = container.markdown.call_args.args[0]
        assert "status-info" in html
        assert "full" in html


# ============================================================
# Loop rollback panel tests
# ============================================================


class TestLoopRollbackPanel:
    def test_loop_rollback_panel_zero_count(self) -> None:
        """Zero rollbacks shows 0/max and zero progress."""
        container = _make_container()
        render_loop_rollback_panel(
            rollback_count=0,
            max_iterations=3,
            artifacts_count=0,
            last_target="NONE",
            container=container,
        )
        container.subheader.assert_called_once()
        container.columns.assert_called_once_with(3)
        container.progress.assert_called_once()
        progress_value = container.progress.call_args.args[0]
        assert progress_value == 0.0

    def test_loop_rollback_panel_near_limit(self) -> None:
        """Near-limit count (2/3) shows progress ~0.667."""
        container = _make_container()
        render_loop_rollback_panel(
            rollback_count=2,
            max_iterations=3,
            artifacts_count=5,
            last_target="DEV",
            container=container,
        )
        progress_value = container.progress.call_args.args[0]
        assert abs(progress_value - (2 / 3)) < 0.01

    def test_loop_rollback_panel_at_limit(self) -> None:
        """At-limit count (3/3) shows progress clamped to 1.0."""
        container = _make_container()
        render_loop_rollback_panel(
            rollback_count=3,
            max_iterations=3,
            artifacts_count=12,
            last_target="TEST",
            container=container,
        )
        progress_value = container.progress.call_args.args[0]
        assert progress_value == 1.0

    def test_loop_rollback_panel_zero_max_does_not_divide_by_zero(self) -> None:
        """max_iterations=0 does not raise (defensive budget guard)."""
        container = _make_container()
        render_loop_rollback_panel(
            rollback_count=0,
            max_iterations=0,
            artifacts_count=0,
            last_target="NONE",
            container=container,
        )
        container.progress.assert_called_once()
        assert container.progress.call_args.args[0] == 0.0


# ============================================================
# Plugin events panel tests
# ============================================================


class TestPluginEventsPanel:
    def test_plugin_events_panel_empty(self) -> None:
        """Empty event list shows an info message, no dataframe."""
        container = _make_container()
        render_plugin_events_panel([], container=container)
        container.subheader.assert_called_once()
        container.info.assert_called_once()
        container.dataframe.assert_not_called()

    def test_plugin_events_panel_with_events(self) -> None:
        """Non-empty event list renders a dataframe with formatted rows."""
        container = _make_container()
        events = [
            {
                "timestamp": "2026-07-24T10:00:00Z",
                "method": "hot_register",
                "name": "my_plugin",
                "success": True,
            },
            {
                "timestamp": "2026-07-24T10:01:00Z",
                "method": "hot_unregister",
                "name": "my_plugin",
                "success": False,
            },
        ]
        render_plugin_events_panel(events, container=container)
        container.dataframe.assert_called_once()
        rows = container.dataframe.call_args.args[0]
        assert len(rows) == 2
        # Reversed (most recent first)
        assert rows[0]["Action"] == "hot_unregister"
        assert "failure" in rows[0]["Status"]
        assert rows[1]["Action"] == "hot_register"
        assert "success" in rows[1]["Status"]

    def test_plugin_events_panel_caps_at_ten(self) -> None:
        """More than 10 events only displays the last 10."""
        container = _make_container()
        events = [
            {
                "timestamp": f"2026-07-24T10:0{i}:00Z",
                "method": "reload",
                "name": f"plugin_{i}",
                "success": True,
            }
            for i in range(15)
        ]
        render_plugin_events_panel(events, container=container)
        rows = container.dataframe.call_args.args[0]
        assert len(rows) == 10
        # Most recent (plugin_14) should be first after reverse
        assert rows[0]["Plugin"] == "plugin_14"


# ============================================================
# Todo drift panel tests
# ============================================================


class TestTodoDriftPanel:
    def test_todo_drift_panel_no_debt(self) -> None:
        """Zero unregistered markers shows clean status."""
        container = _make_container()
        render_todo_drift_panel(
            total=5,
            registered=5,
            unregistered=0,
            last_scan="2026-07-24T10:00:00Z",
            container=container,
        )
        container.subheader.assert_called_once()
        container.columns.assert_called_once_with(3)
        container.caption.assert_called_once()
        assert "2026-07-24" in container.caption.call_args.args[0]
        # Third column metric should show "clean" delta
        col3 = container.columns.return_value[2]
        col3_metric_kwargs = col3.metric.call_args.kwargs
        assert col3_metric_kwargs["delta"] == "clean"
        assert col3_metric_kwargs["delta_color"] == "normal"

    def test_todo_drift_panel_with_debt(self) -> None:
        """Non-zero unregistered markers shows debt warning."""
        container = _make_container()
        render_todo_drift_panel(
            total=8,
            registered=5,
            unregistered=3,
            last_scan="2026-07-24T11:00:00Z",
            container=container,
        )
        col3 = container.columns.return_value[2]
        col3_metric_kwargs = col3.metric.call_args.kwargs
        assert col3_metric_kwargs["value"] == 3
        assert col3_metric_kwargs["delta"] == "debt"
        assert col3_metric_kwargs["delta_color"] == "inverse"

    def test_todo_drift_panel_empty_scan_shows_never(self) -> None:
        """Empty last_scan string renders 'never' in the caption."""
        container = _make_container()
        render_todo_drift_panel(
            total=0,
            registered=0,
            unregistered=0,
            last_scan="",
            container=container,
        )
        assert "never" in container.caption.call_args.args[0]


# ============================================================
# Performance / latency test
# ============================================================


class TestStatusUpdateLatency:
    def test_status_update_latency(self) -> None:
        """Rendering all four panels completes in < 100ms (Mock container).

        Performance gate: the panel functions must be cheap to invoke since
        the dashboard refreshes on a 30s auto-refresh cycle and should never
        block the UI thread. With a Mock container (no real rendering), the
        overhead is pure Python dispatch.
        """
        container = _make_container()
        events = [
            {
                "timestamp": "2026-07-24T10:00:00Z",
                "method": "hot_register",
                "name": "p",
                "success": True,
            }
        ]

        start = time.perf_counter()
        render_ponytail_mode_panel("full", container=container)
        render_loop_rollback_panel(1, 3, 2, "DEV", container=container)
        render_plugin_events_panel(events, container=container)
        render_todo_drift_panel(5, 4, 1, "2026-07-24T10:00:00Z", container=container)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < 100.0, f"Panel rendering took {elapsed_ms:.2f}ms (> 100ms budget)"
