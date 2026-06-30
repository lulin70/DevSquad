#!/usr/bin/env python3
"""
Shared UI components, styling and layout helpers for the DevSquad dashboard.
"""

import logging
import os
import sys
import time
from datetime import datetime
from typing import Any, Literal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st  # noqa: E402

from scripts.auth import AuthManager, User, UserRole  # noqa: E402

logger = logging.getLogger(__name__)


class DashboardConfig:
    """Dashboard configuration and styling."""

    PAGE_TITLE = "🔄 DevSquad Lifecycle Dashboard"
    PAGE_ICON = "🚀"
    LAYOUT: Literal["wide"] = "wide"

    COLOR_SCHEME = {
        "primary": "#4A90D9",
        "success": "#2ca02c",
        "warning": "#ff7f0e",
        "danger": "#d62728",
        "info": "#17becf",
        "background": "#ffffff",
        "text": "#333333",
    }

    PHASE_COLORS = {
        "pending": "#95a5a6",
        "running": "#3498db",
        "completed": "#27ae60",
        "failed": "#e74c3c",
        "skipped": "#f39c12",
        "blocked": "#c0392b",
    }

    CORE_ROLES = [
        "architect",
        "product-manager",
        "security",
        "tester",
        "solo-coder",
        "devops",
        "ui-designer",
    ]

    ROLE_ICONS = {
        "architect": "🏗️",
        "product-manager": "📋",
        "security": "🔒",
        "tester": "🧪",
        "solo-coder": "💻",
        "devops": "⚙️",
        "ui-designer": "🎨",
    }

    ROLE_NAMES = {
        "architect": "架构师",
        "product-manager": "产品经理",
        "security": "安全专家",
        "tester": "测试专家",
        "solo-coder": "开发者",
        "devops": "运维工程师",
        "ui-designer": "UI设计师",
    }


def set_page_config() -> None:
    """Configure Streamlit page settings."""
    st.set_page_config(
        page_title=DashboardConfig.PAGE_TITLE,
        page_icon=DashboardConfig.PAGE_ICON,
        layout=DashboardConfig.LAYOUT,
        initial_sidebar_state="expanded",
    )


def apply_custom_css() -> None:
    """Apply custom CSS for production-grade visual appearance."""
    st.markdown(
        """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    * {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    }

    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #4A90D9;
        text-align: center;
        padding: 1rem 0;
        background: linear-gradient(135deg, #4A90D9 0%, #357ABD 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }

    .metric-card {
        background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%);
        border-radius: 12px;
        padding: 1.5rem;
        margin: 0.5rem 0;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.07);
        border: 1px solid #e9ecef;
        transition: all 0.3s ease;
    }

    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 12px rgba(0, 0, 0, 0.12);
    }

    .phase-card {
        background-color: white;
        border-radius: 10px;
        padding: 1.25rem;
        margin: 0.5rem 0;
        border-left: 4px solid #4A90D9;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.06);
        transition: all 0.3s ease;
    }

    .phase-card:hover {
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
    }

    .status-badge {
        display: inline-block;
        padding: 0.35rem 0.85rem;
        border-radius: 9999px;
        font-size: 0.875rem;
        font-weight: 600;
        letter-spacing: 0.02em;
    }

    .status-success { background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
    .status-warning { background-color: #fff3cd; color: #856404; border: 1px solid #ffeaa7; }
    .status-danger { background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
    .status-info { background-color: #d1ecf1; color: #0c5460; border: 1px solid #bee5eb; }
    .status-secondary { background-color: #e2e3e5; color: #383d41; border: 1px solid #d6d8db; }

    .task-input textarea {
        border: 2px solid #4A90D9 !important;
        border-radius: 8px !important;
        font-family: 'Monaco', 'Menlo', monospace !important;
        font-size: 14px !important;
    }

    .primary-btn {
        background: linear-gradient(135deg, #4A90D9 0%, #357ABD 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 0.65rem 1.5rem !important;
        font-weight: 600 !important;
        transition: all 0.3s ease !important;
    }

    .primary-btn:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 12px rgba(74, 144, 217, 0.35) !important;
    }

    [data-testid="stMetric"] {
        background-color: white;
        padding: 1rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.06);
    }

    .loading-spinner {
        display: inline-block;
        width: 20px;
        height: 20px;
        border: 3px solid rgba(74, 144, 217, 0.3);
        border-top-color: #4A90D9;
        border-radius: 50%;
        animation: spin 1s linear infinite;
    }

    @keyframes spin {
        to { transform: rotate(360deg); }
    }

    .countdown-timer {
        font-size: 0.9rem;
        color: #666;
        font-weight: 500;
        padding: 0.5rem 1rem;
        background: #f8f9fa;
        border-radius: 20px;
        display: inline-block;
    }

    div[data-testid="stExpander"] {
        border: 1px solid #dee2e6;
        border-radius: 8px;
    }

    h2, h3 {
        color: #2c3e50 !important;
        font-weight: 600 !important;
    }
    </style>
    """,
        unsafe_allow_html=True,
    )


def render_header(current_user: User | None = None) -> None:
    """Render the main dashboard header with enhanced styling."""
    st.markdown('<div class="main-header">🚀 DevSquad Lifecycle Dashboard</div>', unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    with col1:
        st.markdown("**Plan C Architecture** | CLI View Layer over 11-Phase Lifecycle")
        if current_user:
            role_badge_class = "status-info" if current_user.role == UserRole.ADMIN else "status-success"
            st.markdown(
                f'<span class="status-badge {role_badge_class}">👤 {current_user.name} ({current_user.role.value})</span>',
                unsafe_allow_html=True,
            )
    with col2:
        st.markdown(f"**Last Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    with col3:
        if st.button("🔄 Refresh", key="refresh_header"):
            st.rerun()
    with col4:
        if st.session_state.get("auto_refresh", False):
            remaining = st.session_state.get("refresh_countdown", 30)
            st.markdown(f'<div class="countdown-timer">⏱️ Auto-refresh in {remaining}s</div>', unsafe_allow_html=True)


def render_action_panel(protocol_data: Any | None) -> None:
    """Render action control panel."""
    st.subheader("🎮 Control Panel")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("▶️ Run All Phases", type="primary", use_container_width=True):
            st.session_state["action"] = "run_all"
            st.success("Initiated full lifecycle run...")
            st.rerun()

    with col2:
        if st.button("🔄 Reset State", use_container_width=True):
            st.session_state["action"] = "reset"
            st.info("Resetting lifecycle state...")
            st.rerun()

    with col3:
        if st.button("📊 Generate Report", use_container_width=True):
            st.session_state["action"] = "report"
            st.success("Generating benchmark report...")


def handle_auto_refresh() -> None:
    """Handle auto-refresh logic with countdown timer."""
    auto_refresh = st.session_state.get("auto_refresh", False)

    if auto_refresh:
        if "refresh_start_time" not in st.session_state:
            st.session_state.refresh_start_time = time.time()

        elapsed = time.time() - st.session_state.refresh_start_time
        remaining = max(0, 30 - int(elapsed))

        st.session_state["refresh_countdown"] = remaining

        if remaining <= 0:
            st.session_state.refresh_start_time = time.time()
            st.rerun()


def render_sidebar(auth: AuthManager, current_user: User | None = None) -> str:
    """Render sidebar navigation and controls with new pages."""
    with st.sidebar:
        st.header("Navigation")

        page_options = [
            "Overview",
            "Phases",
            "Mapping",
            "Gates",
            "Performance",
            "Task Dispatch",
        ]

        page_captions = [
            "System overview & metrics",
            "Phase timeline & details",
            "CLI command mapping",
            "Gate status monitor",
            "Performance metrics",
            "Create & manage tasks",
        ]

        page = st.radio("Go to", page_options, captions=page_captions, label_visibility="collapsed")

        st.divider()

        if current_user:
            auth.get_login_button()

        st.header("Settings")

        auto_refresh = st.checkbox("⏱️ Auto Refresh (30s)", value=st.session_state.get("auto_refresh", False))
        st.session_state["auto_refresh"] = auto_refresh

        st.checkbox("📋 Show Details", value=True)

        st.divider()

        st.header("Quick Actions")

        if st.button("🔄 Refresh Data", use_container_width=True):
            st.rerun()

        if st.button("📥 Export Status", use_container_width=True):
            st.success("Status exported!")

        if current_user and current_user.role.value == "admin":
            st.divider()
            st.header("⚙️ Admin")

            if st.button("👥 Manage Users", use_container_width=True):
                st.session_state.page = "admin_users"

            if st.button("⚙️ System Config", use_container_width=True):
                st.session_state.page = "system_config"

        return page


def render_footer(current_user: User | None = None) -> None:
    """Render dashboard footer with version and session info."""
    st.markdown("---")

    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        st.markdown(
            "<center>**DevSquad V3.7.0** | Plan C | Production Ready | 🎨 Enhanced UI</center>", unsafe_allow_html=True
        )

    with col2:
        if current_user:
            st.caption(f"Session: {current_user.session_id[:8]}...")

    with col3:
        st.caption(f"© {datetime.now().year} DevSquad Team")
