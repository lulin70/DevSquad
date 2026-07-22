#!/usr/bin/env python3
"""
Admin authentication and system configuration views for the DevSquad dashboard.
"""

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st  # noqa: E402

from scripts.auth import AuthManager  # noqa: E402
from scripts.dashboard.dispatch_views import get_dispatcher  # noqa: E402
from scripts.dashboard.lifecycle_views import load_lifecycle_protocol  # noqa: E402

logger = logging.getLogger(__name__)


def render_admin_users_page(auth: AuthManager) -> None:
    """Render Admin User Management page."""
    st.header("👥 User Management")
    st.markdown("---")

    credentials = auth.credentials

    if not credentials:
        st.info("No users configured in deployment.yaml")
        return

    st.markdown(f"**Total Users:** {len(credentials)}")

    for username, cred in credentials.items():
        with st.expander(f"👤 {username}", expanded=False):
            col1, col2, col3 = st.columns(3)

            with col1:
                st.markdown(f"**Name:** {cred.get('name', username)}")
                st.markdown(f"**Email:** {cred.get('email', 'N/A')}")

            with col2:
                role = cred.get("role", "viewer")
                role_badge = {"admin": "status-danger", "operator": "status-warning", "viewer": "status-secondary"}.get(
                    role, "status-secondary"
                )
                st.markdown(f'<span class="status-badge {role_badge}">{role.upper()}</span>', unsafe_allow_html=True)

            with col3:
                st.selectbox(
                    "Change Role",
                    options=["admin", "operator", "viewer"],
                    index=["admin", "operator", "viewer"].index(role) if role in ["admin", "operator", "viewer"] else 2,
                    key=f"role_{username}",
                    disabled=True,
                    help="Role changes require editing config/deployment.yaml",
                )
                st.caption("ℹ️ Edit config file to change roles")

    st.markdown("---")
    st.info("""
    **User Management Notes:**
    - Users are configured in `config/deployment.yaml`
    - To add/edit users, modify the `authentication.credentials.usernames` section
    - Restart the dashboard after configuration changes
    """)


def render_admin_system_config_page(auth: AuthManager) -> None:
    """Render Admin System Configuration page (read-only)."""
    st.header("⚙️ System Configuration")
    st.markdown("---")

    st.markdown("**Environment Variables**")

    env_vars = {
        "PYTHONPATH": os.environ.get("PYTHONPATH", "Not set"),
        "HOME": os.environ.get("HOME", "Not set"),
        "LANG": os.environ.get("LANG", "Not set"),
        "TERM": os.environ.get("TERM", "Not set"),
    }

    env_data = [{"Variable": k, "Value": v} for k, v in env_vars.items()]
    st.dataframe(env_data, use_container_width=True, hide_index=True)

    st.markdown("---")

    st.markdown("**System Information**")

    sys_info = [
        {
            "Item": "Python Version",
            "Value": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        },
        {"Item": "Platform", "Value": sys.platform},
        {"Item": "Working Directory", "Value": os.getcwd()},
        {"Item": "DevSquad Version", "Value": "V4.1.7"},
        {"Item": "Dashboard Mode", "Value": "Production-Grade"},
    ]
    st.dataframe(sys_info, use_container_width=True, hide_index=True)

    st.markdown("---")

    st.markdown("**Configuration Status**")

    config_items = [
        {"Component": "Authentication", "Status": "✅ Enabled" if auth.credentials else "⚠️ No Config"},
        {"Component": "Lifecycle Protocol", "Status": "✅ Loaded" if load_lifecycle_protocol() else "❌ Failed"},
        {"Component": "Multi-Agent Dispatcher", "Status": "✅ Ready" if get_dispatcher() else "❌ Not Initialized"},
        {
            "Component": "Auto-Refresh",
            "Status": f"{'✅ Active' if st.session_state.get('auto_refresh', False) else '⚪ Inactive'}",
        },
    ]
    st.dataframe(config_items, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.caption("ℹ️ This page is read-only. Configuration changes require editing source files.")
