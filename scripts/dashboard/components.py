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
        "primary": "#7B9EA8",
        "success": "#8FA886",
        "warning": "#C9A87C",
        "danger": "#B58484",
        "info": "#9DB5C2",
        "background": "#F5F3F0",
        "text": "#4A4A4A",
    }

    PHASE_COLORS = {
        "pending": "#B0B0B0",
        "running": "#7B9EA8",
        "completed": "#8FA886",
        "failed": "#B58484",
        "skipped": "#C9A87C",
        "blocked": "#9B8AA4",
    }

    # W2-T1: Dark mode color palette (Morandi-tuned, only lightness adjusted)
    LIGHT_MODE_COLORS = {
        "bg-primary": "#F5F3F0",
        "bg-card": "#FFFFFF",
        "text-primary": "#4A4A4A",
        "text-secondary": "#666666",
        "accent-primary": "#7B9EA8",
        "accent-success": "#8FA886",
        "accent-warning": "#C9A87C",
        "accent-danger": "#B58484",
    }

    DARK_MODE_COLORS = {
        "bg-primary": "#1F1F23",
        "bg-card": "#2A2A30",
        "text-primary": "#E8E6E3",
        "text-secondary": "#A8A6A3",
        "accent-primary": "#9DB5C2",  # Morandi info (brighter on dark)
        "accent-success": "#A8C2A0",
        "accent-warning": "#DDB589",
        "accent-danger": "#C9A0A0",
    }

    # W2-T3: Toast notification colors (4 levels, Morandi-aligned)
    TOAST_COLORS = {
        "info": "#9DB5C2",     # Morandi info
        "success": "#8FA886",  # Morandi success
        "warning": "#C9A87C",  # Morandi warning
        "error": "#B58484",    # Morandi danger
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

    # W2-T2: Lucide-style SVG icons (single-color stroke, currentColor for theme adaptation)
    # Source: Lucide icons (https://lucide.dev) — MIT licensed
    # Each value is the inner SVG content (paths), to be wrapped with <svg> tag by get_role_icon()
    ROLE_SVG_ICONS = {
        "architect": (
            '<line x1="3" y1="22" x2="21" y2="22"/>'
            '<line x1="6" y1="18" x2="6" y2="11"/>'
            '<line x1="10" y1="18" x2="10" y2="11"/>'
            '<line x1="14" y1="18" x2="14" y2="11"/>'
            '<line x1="18" y1="18" x2="18" y2="11"/>'
            '<polygon points="12 2 20 7 4 7"/>'
        ),
        "product-manager": (
            '<rect x="8" y="2" width="8" height="4" rx="1" ry="1"/>'
            '<path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>'
            '<path d="M12 11h4"/>'
            '<path d="M12 16h4"/>'
            '<path d="M8 11h.01"/>'
            '<path d="M8 16h.01"/>'
        ),
        "security": (
            '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>'
            '<path d="m9 12 2 2 4-4"/>'
        ),
        "tester": (
            '<path d="M10 2v7.31"/>'
            '<path d="M14 9.3V2"/>'
            '<path d="M8.5 2h7"/>'
            '<path d="M14 9.3a6.5 6.5 0 1 1-4 0"/>'
            '<path d="M5.52 16h12.96"/>'
        ),
        "solo-coder": (
            '<path d="m18 16 4-4-4-4"/>'
            '<path d="m6 8-4 4 4 4"/>'
            '<path d="m14.5 4-5 16"/>'
        ),
        "devops": (
            '<path d="M20 7h-9"/>'
            '<path d="M14 17H5"/>'
            '<circle cx="17" cy="17" r="3"/>'
            '<circle cx="7" cy="7" r="3"/>'
        ),
        "ui-designer": (
            '<circle cx="13.5" cy="6.5" r=".5" fill="currentColor"/>'
            '<circle cx="17.5" cy="10.5" r=".5" fill="currentColor"/>'
            '<circle cx="8.5" cy="7.5" r=".5" fill="currentColor"/>'
            '<circle cx="6.5" cy="12.5" r=".5" fill="currentColor"/>'
            '<path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.926 0 1.648-.746 1.648-1.688 0-.437-.18-.835-.437-1.125-.29-.289-.438-.652-.438-1.125a1.64 1.64 0 0 1 1.668-1.668h1.996c3.051 0 5.555-2.503 5.555-5.554C21.965 6.012 17.461 2 12 2z"/>'
        ),
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
    """Apply custom CSS for production-grade visual appearance.

    W2-T1: Uses CSS variables + [data-theme="dark"] selector for dark mode.
    W2-T3: Includes .toast-container / .toast styles for notification system.
    """
    st.markdown(
        """
    <style>
    /* W2-T1: CSS variables for light/dark mode (Morandi palette) */
    :root {
        --bg-primary: #F5F3F0;
        --bg-card: #FFFFFF;
        --text-primary: #4A4A4A;
        --text-secondary: #666666;
        --accent-primary: #7B9EA8;
        --accent-success: #8FA886;
        --accent-warning: #C9A87C;
        --accent-danger: #B58484;
        --border-subtle: #e9ecef;
        --shadow-card: rgba(0, 0, 0, 0.07);
        --shadow-hover: rgba(0, 0, 0, 0.12);
    }

    [data-theme="dark"] {
        --bg-primary: #1F1F23;
        --bg-card: #2A2A30;
        --text-primary: #E8E6E3;
        --text-secondary: #A8A6A3;
        --accent-primary: #9DB5C2;
        --accent-success: #A8C2A0;
        --accent-warning: #DDB589;
        --accent-danger: #C9A0A0;
        --border-subtle: #3A3A40;
        --shadow-card: rgba(0, 0, 0, 0.3);
        --shadow-hover: rgba(0, 0, 0, 0.5);
    }

    * {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    }

    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: var(--accent-primary);
        text-align: center;
        padding: 1rem 0;
    }

    .metric-card {
        background: var(--bg-card);
        border-radius: 12px;
        padding: 1.5rem;
        margin: 0.5rem 0;
        box-shadow: 0 4px 6px var(--shadow-card);
        border: 1px solid var(--border-subtle);
        transition: all 0.3s ease;
    }

    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 12px var(--shadow-hover);
    }

    .phase-card {
        background-color: var(--bg-card);
        border-radius: 10px;
        padding: 1.25rem;
        margin: 0.5rem 0;
        border: 1px solid var(--border-subtle);
        box-shadow: 0 2px 4px var(--shadow-card);
        transition: all 0.3s ease;
    }

    .phase-card:hover {
        box-shadow: 0 4px 8px var(--shadow-hover);
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
        border: 2px solid var(--accent-primary) !important;
        border-radius: 8px !important;
        font-family: 'Monaco', 'Menlo', monospace !important;
        font-size: 14px !important;
    }

    .primary-btn {
        background: var(--accent-primary) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 0.65rem 1.5rem !important;
        font-weight: 600 !important;
        transition: all 0.3s ease !important;
    }

    .primary-btn:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 12px rgba(123, 158, 168, 0.35) !important;
    }

    [data-testid="stMetric"] {
        background-color: var(--bg-card);
        padding: 1rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px var(--shadow-card);
    }

    .loading-spinner {
        display: inline-block;
        width: 20px;
        height: 20px;
        border: 3px solid rgba(123, 158, 168, 0.3);
        border-top-color: var(--accent-primary);
        border-radius: 50%;
        animation: spin 1s linear infinite;
    }

    @keyframes spin {
        to { transform: rotate(360deg); }
    }

    .countdown-timer {
        font-size: 0.9rem;
        color: var(--text-secondary);
        font-weight: 500;
        padding: 0.5rem 1rem;
        background: var(--bg-primary);
        border-radius: 20px;
        display: inline-block;
    }

    div[data-testid="stExpander"] {
        border: 1px solid var(--border-subtle);
        border-radius: 8px;
    }

    h2, h3 {
        color: var(--text-primary) !important;
        font-weight: 600 !important;
    }

    /* W2-T3: Toast notification styles */
    .toast-container {
        position: fixed;
        top: 1rem;
        right: 1rem;
        z-index: 9999;
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
        pointer-events: none;
    }

    .toast {
        display: flex;
        align-items: center;
        padding: 0.75rem 1.25rem;
        border-radius: 8px;
        color: white;
        font-weight: 500;
        font-size: 0.9rem;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        min-width: 240px;
        max-width: 360px;
        animation: toast-in 0.3s ease, toast-out 0.3s ease forwards;
        animation-delay: 0s, var(--toast-duration);
        pointer-events: auto;
    }

    .toast-info { background: var(--accent-primary); }
    .toast-success { background: var(--accent-success); }
    .toast-warning { background: var(--accent-warning); }
    .toast-error { background: var(--accent-danger); }

    @keyframes toast-in {
        from { opacity: 0; transform: translateX(100%); }
        to { opacity: 1; transform: translateX(0); }
    }

    @keyframes toast-out {
        from { opacity: 1; transform: translateX(0); }
        to { opacity: 0; transform: translateX(100%); }
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
            "DAG",
        ]

        page_captions = [
            "System overview & metrics",
            "Phase timeline & details",
            "CLI command mapping",
            "Gate status monitor",
            "Performance metrics",
            "Create & manage tasks",
            "V4.0.0 Lifecycle dependency graph",
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

        return str(page)


def render_footer(current_user: User | None = None) -> None:
    """Render dashboard footer with version and session info."""
    st.markdown("---")

    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        st.markdown(
            "<center>**DevSquad V4.1.0** | Plan C | Production Ready | 🎨 Enhanced UI</center>", unsafe_allow_html=True
        )

    with col2:
        if current_user:
            st.caption(f"Session: {current_user.session_id[:8]}...")

    with col3:
        st.caption(f"© {datetime.now().year} DevSquad Team")


# --- W2-T1: Dark mode toggle ---

def render_theme_toggle() -> bool:
    """Render dark mode toggle in the sidebar.

    Stores the user's preference in ``st.session_state["dark_mode"]`` and
    injects a small script to set ``<html data-theme="dark">`` so that the
    CSS variables defined in :func:`apply_custom_css` switch accordingly.

    Returns:
        True if dark mode is enabled, False otherwise.
    """
    dark_mode = st.toggle(
        "Dark Mode",
        value=st.session_state.get("dark_mode", False),
        key="dark_mode_toggle",
        help="Switch between Morandi light and dark themes",
    )
    st.session_state["dark_mode"] = dark_mode

    # Inject script to set data-theme attribute on <html>
    theme_attr = "dark" if dark_mode else "light"
    st.markdown(
        f"""
    <script>
        (function() {{
            var root = document.documentElement;
            if (root) {{ root.setAttribute('data-theme', '{theme_attr}'); }}
        }})();
    </script>
    """,
        unsafe_allow_html=True,
    )
    return dark_mode


# --- W2-T2: SVG role icons ---

def get_role_icon(role: str, fmt: str = "svg") -> str:
    """Return the icon for a role.

    Args:
        role: One of :attr:`DashboardConfig.CORE_ROLES`.
        fmt: ``"svg"`` (default) returns an inline ``<svg>`` element using
            ``currentColor`` for stroke so the icon adapts to light/dark
            themes automatically. ``"emoji"`` returns the legacy emoji.

    Returns:
        The icon string. For unknown roles, returns a default square icon
        (SVG) or ``"❓"`` (emoji).
    """
    if fmt == "emoji":
        return DashboardConfig.ROLE_ICONS.get(role, "❓")

    # SVG format (default)
    inner = DashboardConfig.ROLE_SVG_ICONS.get(role)
    if inner is None:
        # Default: a simple question-mark square
        inner = (
            '<rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>'
            '<path d="M9.5 9a2.5 2.5 0 1 1 4 2c-.5.5-1 1-1 2"/>'
            '<line x1="12" y1="16" x2="12" y2="16"/>'
        )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" '
        'viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        f'{inner}</svg>'
    )


# --- W2-T3: Toast notification system ---

_TOAST_COUNTER_KEY = "_toast_counter"


def show_toast(message: str, level: str = "info", duration: int = 5) -> str:
    """Show a toast notification in the top-right corner.

    Args:
        message: The message to display (plain text; HTML is escaped).
        level: One of ``"info"``, ``"success"``, ``"warning"``, ``"error"``.
            Defaults to ``"info"``. Unknown levels fall back to ``"info"``.
        duration: Time in seconds before the toast auto-dismisses.
            Defaults to 5. Must be in [1, 30].

    Returns:
        The unique toast id (used for testing and stacking).

    Note:
        Uses CSS animation (defined in :func:`apply_custom_css`) for
        auto-dismissal — no JavaScript timers required. Multiple toasts
        stack vertically via the ``.toast-container``.
    """
    if level not in DashboardConfig.TOAST_COLORS:
        level = "info"
    duration = max(1, min(30, int(duration)))

    # Generate a unique toast id
    counter = st.session_state.get(_TOAST_COUNTER_KEY, 0) + 1
    st.session_state[_TOAST_COUNTER_KEY] = counter
    toast_id = f"toast-{counter}"

    # HTML-escape the message to prevent XSS
    safe_message = (
        message.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )

    duration_ms = duration * 1000
    st.markdown(
        f"""
    <div class="toast-container" aria-live="polite" aria-atomic="true">
        <div id="{toast_id}" class="toast toast-{level}"
             style="--toast-duration: {duration_ms}ms"
             role="alert">
            {safe_message}
        </div>
    </div>
    """,
        unsafe_allow_html=True,
    )
    return toast_id


# --- W3-T1: Command palette (Cmd+K) ---

# 7 page commands + 1 toggle command (kept compact for fuzzy matching)
COMMAND_PALETTE_ITEMS: list[dict[str, str]] = [
    {"id": "page-overview", "label": "Go to Overview", "hint": "1", "action": "page:Overview"},
    {"id": "page-phases", "label": "Go to Phases", "hint": "2", "action": "page:Phases"},
    {"id": "page-mapping", "label": "Go to Mapping", "hint": "3", "action": "page:Mapping"},
    {"id": "page-gates", "label": "Go to Gates", "hint": "4", "action": "page:Gates"},
    {"id": "page-performance", "label": "Go to Performance", "hint": "5", "action": "page:Performance"},
    {"id": "page-dispatch", "label": "Go to Task Dispatch", "hint": "6", "action": "page:Task Dispatch"},
    {"id": "page-dag", "label": "Go to DAG", "hint": "7", "action": "page:DAG"},
    {"id": "toggle-dark", "label": "Toggle Dark Mode", "hint": "D", "action": "toggle:dark_mode"},
]


def render_command_palette() -> None:
    """Render a Cmd+K command palette overlay.

    Injects HTML/CSS/JS for a modal-like command palette that opens on
    Cmd+K (macOS) or Ctrl+K (other OS). Supports fuzzy search over
    :data:`COMMAND_PALETTE_ITEMS`. Selection triggers a Streamlit
    query param change so the app can route accordingly.

    Note:
        Uses Streamlit's ``set_query_param`` via JS click on a hidden
        button — the app reads the query param on rerun to route.
    """
    import json

    items_json = json.dumps(COMMAND_PALETTE_ITEMS)
    st.markdown(
        f"""
    <style>
    .cmd-palette-overlay {{
        position: fixed; top: 0; left: 0; right: 0; bottom: 0;
        background: rgba(0, 0, 0, 0.4);
        z-index: 10000;
        display: none;
        align-items: flex-start;
        justify-content: center;
        padding-top: 12vh;
    }}
    .cmd-palette-overlay.open {{ display: flex; }}
    .cmd-palette {{
        background: var(--bg-card, #fff);
        border-radius: 12px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
        width: 90%; max-width: 540px;
        overflow: hidden;
        border: 1px solid var(--border-subtle, #e9ecef);
    }}
    .cmd-palette-input {{
        width: 100%; padding: 1rem 1.25rem;
        border: none; outline: none;
        font-size: 1rem;
        background: transparent;
        color: var(--text-primary, #4A4A4A);
        border-bottom: 1px solid var(--border-subtle, #e9ecef);
    }}
    .cmd-palette-list {{ max-height: 320px; overflow-y: auto; }}
    .cmd-palette-item {{
        padding: 0.75rem 1.25rem;
        cursor: pointer;
        display: flex; justify-content: space-between; align-items: center;
        color: var(--text-primary, #4A4A4A);
    }}
    .cmd-palette-item:hover, .cmd-palette-item.selected {{
        background: var(--accent-primary, #7B9EA8);
        color: white;
    }}
    .cmd-palette-item-hint {{
        font-size: 0.75rem;
        background: rgba(0, 0, 0, 0.08);
        padding: 0.15rem 0.5rem;
        border-radius: 4px;
        color: inherit;
    }}
    .cmd-palette-item:hover .cmd-palette-item-hint,
    .cmd-palette-item.selected .cmd-palette-item-hint {{
        background: rgba(255, 255, 255, 0.25);
    }}
    </style>

    <div id="cmd-palette-overlay" class="cmd-palette-overlay" role="dialog"
         aria-modal="true" aria-label="Command palette">
        <div class="cmd-palette">
            <input id="cmd-palette-search" type="text" class="cmd-palette-input"
                   placeholder="Search commands... (Esc to close)"
                   autocomplete="off" />
            <div id="cmd-palette-list" class="cmd-palette-list"></div>
        </div>
    </div>

    <script>
    (function() {{
        var items = {items_json};
        var overlay = document.getElementById('cmd-palette-overlay');
        var searchInput = document.getElementById('cmd-palette-search');
        var listEl = document.getElementById('cmd-palette-list');
        var selectedIdx = 0;

        function fuzzyMatch(query, text) {{
            query = query.toLowerCase(); text = text.toLowerCase();
            if (!query) return true;
            var qi = 0;
            for (var i = 0; i < text.length && qi < query.length; i++) {{
                if (text[i] === query[qi]) qi++;
            }}
            return qi === query.length;
        }}

        function renderList(query) {{
            var matches = items.filter(function(it) {{
                return fuzzyMatch(query || '', it.label);
            }});
            selectedIdx = 0;
            listEl.innerHTML = matches.map(function(it, i) {{
                return '<div class="cmd-palette-item' + (i === 0 ? ' selected' : '') +
                       '" data-action="' + it.action + '" data-idx="' + i + '">' +
                       '<span>' + it.label + '</span>' +
                       '<span class="cmd-palette-item-hint">' + it.hint + '</span>' +
                       '</div>';
            }}).join('');
            // Attach click handlers
            var items_dom = listEl.querySelectorAll('.cmd-palette-item');
            for (var i = 0; i < items_dom.length; i++) {{
                items_dom[i].addEventListener('click', function() {{
                    executeAction(this.getAttribute('data-action'));
                }});
            }}
        }}

        function executeAction(action) {{
            // Use query param to signal the Streamlit app
            var url = new URL(window.location);
            var parts = action.split(':');
            url.searchParams.set('_cmd_action', parts[0]);
            url.searchParams.set('_cmd_target', parts[1] || '');
            window.history.pushState({{}}, '', url);
            closePalette();
            // Trigger Streamlit rerun via hidden button click
            var btn = document.querySelector('[data-testid="stAppViewContainer"] button');
            if (btn) btn.click();
            else window.location.reload();
        }}

        function openPalette() {{
            overlay.classList.add('open');
            searchInput.value = '';
            renderList('');
            setTimeout(function() {{ searchInput.focus(); }}, 50);
        }}

        function closePalette() {{
            overlay.classList.remove('open');
        }}

        // Global Cmd+K / Ctrl+K shortcut
        document.addEventListener('keydown', function(e) {{
            if ((e.metaKey || e.ctrlKey) && e.key === 'k') {{
                e.preventDefault();
                if (overlay.classList.contains('open')) closePalette();
                else openPalette();
                return;
            }}
            if (e.key === 'Escape' && overlay.classList.contains('open')) {{
                closePalette();
                return;
            }}
            if (overlay.classList.contains('open')) {{
                if (e.key === 'ArrowDown') {{
                    e.preventDefault();
                    var items_dom = listEl.querySelectorAll('.cmd-palette-item');
                    if (items_dom.length === 0) return;
                    selectedIdx = Math.min(selectedIdx + 1, items_dom.length - 1);
                    updateSelection(items_dom);
                }} else if (e.key === 'ArrowUp') {{
                    e.preventDefault();
                    var items_dom = listEl.querySelectorAll('.cmd-palette-item');
                    if (items_dom.length === 0) return;
                    selectedIdx = Math.max(selectedIdx - 1, 0);
                    updateSelection(items_dom);
                }} else if (e.key === 'Enter') {{
                    e.preventDefault();
                    var items_dom = listEl.querySelectorAll('.cmd-palette-item');
                    if (items_dom[selectedIdx]) {{
                        executeAction(items_dom[selectedIdx].getAttribute('data-action'));
                    }}
                }}
            }}
        }});

        function updateSelection(items_dom) {{
            for (var i = 0; i < items_dom.length; i++) {{
                if (i === selectedIdx) items_dom[i].classList.add('selected');
                else items_dom[i].classList.remove('selected');
            }}
            // Scroll into view
            if (items_dom[selectedIdx]) {{
                items_dom[selectedIdx].scrollIntoView({{ block: 'nearest' }});
            }}
        }}

        searchInput.addEventListener('input', function() {{
            renderList(this.value);
        }});

        // Close on overlay click (outside palette)
        overlay.addEventListener('click', function(e) {{
            if (e.target === overlay) closePalette();
        }});
    }})();
    </script>
    """,
        unsafe_allow_html=True,
    )


# --- W3-T3: Skeleton screens ---

# 3 skeleton kinds with predefined element counts
SKELETON_KINDS: dict[str, int] = {
    "metric": 4,      # top metric cards
    "phase_row": 5,   # phase timeline rows
    "chart": 1,       # single chart placeholder
}


def render_skeleton(kind: str, count: int | None = None) -> None:
    """Render a skeleton loading placeholder.

    Args:
        kind: One of ``"metric"``, ``"phase_row"``, ``"chart"``.
            Unknown kinds fall back to ``"metric"``.
        count: Number of skeleton elements to render. If None, uses
            the default count for the kind (see :data:`SKELETON_KINDS`).

    Note:
        Uses CSS ``@keyframes skeleton-shimmer`` for a subtle pulsing
        effect. Replaces ``st.spinner`` for initial data loading.
    """
    if kind not in SKELETON_KINDS:
        kind = "metric"
    if count is None:
        count = SKELETON_KINDS[kind]
    count = max(1, min(20, int(count)))  # safety clamp

    # Build skeleton elements based on kind
    if kind == "metric":
        element_html = (
            '<div class="skeleton skeleton-metric">'
            '<div class="skeleton-line skeleton-line-short"></div>'
            '<div class="skeleton-line skeleton-line-long"></div>'
            "</div>"
        )
        container_class = "skeleton-metric-row"
    elif kind == "phase_row":
        element_html = (
            '<div class="skeleton skeleton-phase-row">'
            '<div class="skeleton-circle"></div>'
            '<div class="skeleton-line skeleton-line-medium"></div>'
            '<div class="skeleton-line skeleton-line-short"></div>'
            "</div>"
        )
        container_class = "skeleton-phase-list"
    else:  # chart
        element_html = (
            '<div class="skeleton skeleton-chart">'
            '<div class="skeleton-chart-bar" style="height: 60%"></div>'
            '<div class="skeleton-chart-bar" style="height: 80%"></div>'
            '<div class="skeleton-chart-bar" style="height: 45%"></div>'
            '<div class="skeleton-chart-bar" style="height: 70%"></div>'
            '<div class="skeleton-chart-bar" style="height: 55%"></div>'
            "</div>"
        )
        container_class = "skeleton-chart-container"

    elements = element_html * count
    st.markdown(
        f"""
    <style>
    @keyframes skeleton-shimmer {{
        0% {{ background-position: -200% 0; }}
        100% {{ background-position: 200% 0; }}
    }}
    .skeleton {{
        background: linear-gradient(
            90deg,
            var(--border-subtle, #e9ecef) 25%,
            rgba(0, 0, 0, 0.06) 50%,
            var(--border-subtle, #e9ecef) 75%
        );
        background-size: 200% 100%;
        animation: skeleton-shimmer 1.5s ease-in-out infinite;
        border-radius: 8px;
    }}
    .skeleton-metric-row {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 1rem;
        margin: 0.5rem 0;
    }}
    .skeleton-metric {{
        padding: 1.5rem;
        border-radius: 12px;
        background: var(--bg-card, #fff);
        border: 1px solid var(--border-subtle, #e9ecef);
    }}
    .skeleton-line {{
        height: 0.875rem;
        margin-bottom: 0.5rem;
        border-radius: 4px;
    }}
    .skeleton-line-short {{ width: 40%; }}
    .skeleton-line-medium {{ width: 65%; }}
    .skeleton-line-long {{ width: 85%; }}
    .skeleton-phase-list {{
        display: flex; flex-direction: column;
        gap: 0.5rem;
        margin: 0.5rem 0;
    }}
    .skeleton-phase-row {{
        display: flex; align-items: center; gap: 0.75rem;
        padding: 1rem;
        background: var(--bg-card, #fff);
        border-radius: 10px;
        border: 1px solid var(--border-subtle, #e9ecef);
    }}
    .skeleton-circle {{
        width: 28px; height: 28px;
        border-radius: 50%;
        flex-shrink: 0;
        background: linear-gradient(
            90deg,
            var(--border-subtle, #e9ecef) 25%,
            rgba(0, 0, 0, 0.06) 50%,
            var(--border-subtle, #e9ecef) 75%
        );
        background-size: 200% 100%;
        animation: skeleton-shimmer 1.5s ease-in-out infinite;
    }}
    .skeleton-chart-container {{
        margin: 0.5rem 0;
        padding: 1rem;
        background: var(--bg-card, #fff);
        border-radius: 10px;
        border: 1px solid var(--border-subtle, #e9ecef);
        height: 240px;
    }}
    .skeleton-chart {{
        display: flex; align-items: flex-end;
        gap: 0.5rem;
        height: 100%;
    }}
    .skeleton-chart-bar {{
        flex: 1;
        background: linear-gradient(
            90deg,
            var(--border-subtle, #e9ecef) 25%,
            rgba(0, 0, 0, 0.06) 50%,
            var(--border-subtle, #e9ecef) 75%
        );
        background-size: 200% 100%;
        animation: skeleton-shimmer 1.5s ease-in-out infinite;
        border-radius: 4px 4px 0 0;
    }}
    [data-theme="dark"] .skeleton,
    [data-theme="dark"] .skeleton-circle,
    [data-theme="dark"] .skeleton-chart-bar {{
        background: linear-gradient(
            90deg,
            var(--border-subtle, #3A3A40) 25%,
            rgba(255, 255, 255, 0.04) 50%,
            var(--border-subtle, #3A3A40) 75%
        );
        background-size: 200% 100%;
    }}
    </style>
    <div class="{container_class}" role="status" aria-live="polite"
         aria-label="Loading content">
        {elements}
    </div>
    """,
        unsafe_allow_html=True,
    )
