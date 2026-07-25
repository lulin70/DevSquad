#!/usr/bin/env python3
"""V4.3.0 Dashboard panels — status visualization for new features.

Provides pure rendering functions for four V4.3.0 capabilities:
    - Ponytail mode indicator (lite/full)
    - Loop rollback statistics panel
    - Plugin hot-load event stream
    - Todo drift monitor status

Each function accepts data as parameters and renders into a Streamlit
container (defaults to the global ``streamlit`` module when ``container``
is None). Functions do not read global state, making them trivially
testable with a Mock container.

Spec reference: docs/prd/V4.3.0_PRD.md §3.2 (P1-6)
                docs/architecture/V4.3.0_ARCHITECTURE.md §6.4
"""

from __future__ import annotations

from typing import Any

import streamlit as st

# Badge CSS class mapping for ponytail modes (reuses classes from apply_custom_css).
# - lite: green (lightweight, test/UI roles)
# - full: blue (default, backward compatible with V3.10.0)
# - ultra: red (dead code removed per PRD §3.2; should never appear)
_PONYTAIL_BADGE: dict[str, str] = {
    "lite": "status-success",
    "full": "status-info",
    "ultra": "status-danger",
}


def render_ponytail_mode_panel(mode: str, container: Any = None) -> None:
    """Render the Ponytail mode indicator panel.

    Args:
        mode: The active ponytail mode (``"lite"`` or ``"full"``).
            ``"ultra"`` is dead code (removed per PRD §3.2) and renders a
            red danger badge if it ever appears.
        container: A Streamlit container/module to render into. If None,
            the global ``streamlit`` module is used.
    """
    target = container if container is not None else st
    mode_lower = (mode or "full").lower()
    badge_class = _PONYTAIL_BADGE.get(mode_lower, "status-secondary")
    target.markdown(
        f'<span class="status-badge {badge_class}">Ponytail: {mode_lower}</span>',
        unsafe_allow_html=True,
    )
    target.metric(label="Active Mode", value=mode_lower.capitalize())


def render_loop_rollback_panel(
    rollback_count: int,
    max_iterations: int,
    artifacts_count: int,
    last_target: str,
    container: Any = None,
) -> None:
    """Render the Loop rollback statistics panel.

    Args:
        rollback_count: Number of rollbacks performed so far.
        max_iterations: Hard cap on rollback iterations (default 3).
        artifacts_count: Number of accumulated artifacts across iterations.
        last_target: Last rollback target phase (``"DEV"``/``"TEST"``/``"NONE"``).
        container: A Streamlit container/module to render into. If None,
            the global ``streamlit`` module is used.
    """
    target = container if container is not None else st
    target.subheader("🔄 Loop Rollback Status")
    col1, col2, col3 = target.columns(3)
    col1.metric(label="Rollbacks", value=f"{rollback_count}/{max_iterations}")
    col2.metric(label="Accumulated Artifacts", value=artifacts_count)
    col3.metric(label="Last Target", value=last_target or "—")
    budget = max_iterations if max_iterations > 0 else 1
    ratio = min(1.0, rollback_count / budget)
    target.progress(ratio, text=f"Rollback budget used: {rollback_count}/{max_iterations}")


def render_plugin_events_panel(events: list[dict[str, Any]], container: Any = None) -> None:
    """Render the plugin hot-load event stream panel.

    Args:
        events: List of audit-log event dicts. Each dict should have
            ``timestamp``, ``method``, ``name``, and ``success`` keys.
            Only the last 10 events are displayed.
        container: A Streamlit container/module to render into. If None,
            the global ``streamlit`` module is used.
    """
    target = container if container is not None else st
    target.subheader("🔌 Plugin Hot-Load Events")
    if not events:
        target.info("No plugin events recorded yet.")
        return
    recent = list(reversed(events))[:10]
    rows = [
        {
            "Timestamp": e.get("timestamp", ""),
            "Plugin": e.get("name", ""),
            "Action": e.get("method", ""),
            "Status": "✅ success" if e.get("success") else "❌ failure",
        }
        for e in recent
    ]
    target.dataframe(rows, use_container_width=True, hide_index=True)


def render_todo_drift_panel(
    total: int,
    registered: int,
    unregistered: int,
    last_scan: str,
    container: Any = None,
) -> None:
    """Render the todo drift monitor status panel.

    Args:
        total: Total tech-debt markers found in the last scan.
        registered: Number of markers registered in the tracker.
        unregistered: Number of new unregistered markers (tech debt).
        last_scan: ISO timestamp of the last scan.
        container: A Streamlit container/module to render into. If None,
            the global ``streamlit`` module is used.
    """
    target = container if container is not None else st
    target.subheader("📋 Todo Drift Monitor")
    col1, col2, col3 = target.columns(3)
    col1.metric(label="Total Markers", value=total)
    col2.metric(label="Registered", value=registered)
    debt_color = "inverse" if unregistered > 0 else "normal"
    col3.metric(
        label="Unregistered",
        value=unregistered,
        delta="debt" if unregistered > 0 else "clean",
        delta_color=debt_color,
    )
    target.caption(f"Last scan: {last_scan or 'never'}")


__all__ = [
    "render_ponytail_mode_panel",
    "render_loop_rollback_panel",
    "render_plugin_events_panel",
    "render_todo_drift_panel",
]
