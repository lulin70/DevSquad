#!/usr/bin/env python3
"""
DevSquad Dashboard application entry point.

This module wires together the split dashboard components and provides the
main Streamlit execution flow.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st  # noqa: E402

from scripts.auth import AuthManager  # noqa: E402
from scripts.dashboard.auth_views import (
    render_admin_system_config_page,
    render_admin_users_page,
)  # noqa: E402
from scripts.dashboard.components import (
    apply_custom_css,
    handle_auto_refresh,
    render_action_panel,
    render_footer,
    render_header,
    render_sidebar,
    set_page_config,
)  # noqa: E402
from scripts.dashboard.dispatch_views import (
    get_dispatcher,
    render_task_dispatch_page,
)  # noqa: E402
from scripts.dashboard.lifecycle_views import (
    load_lifecycle_protocol,
    render_cli_mapping_table,
    render_gate_status_panel,
    render_phase_timeline,
)  # noqa: E402
from scripts.dashboard.metrics_views import (
    render_metrics_overview,
    render_performance_panel,
)  # noqa: E402


def main() -> None:
    """Main dashboard entry point."""
    set_page_config()
    apply_custom_css()

    auth = AuthManager(
        config_path=os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "config", "deployment.yaml"
        )
    )

    auth.authenticate_streamlit()

    current_user = auth.get_current_user()

    page = render_sidebar(auth, current_user)

    handle_auto_refresh()

    render_header(current_user)

    protocol_data = load_lifecycle_protocol()
    dispatcher = get_dispatcher()

    can_execute = current_user.can_execute_phases() if current_user else False

    if page == "Overview":
        render_metrics_overview(protocol_data)
        st.divider()
        if can_execute:
            render_action_panel(protocol_data)
        else:
            st.info("🔒 Phase execution requires Operator or Admin role")

    elif page == "Phases":
        render_phase_timeline(protocol_data)

    elif page == "Mapping":
        render_cli_mapping_table(protocol_data)

    elif page == "Gates":
        render_gate_status_panel(protocol_data)

    elif page == "Performance":
        render_performance_panel()

    elif page == "Task Dispatch":
        if can_execute:
            render_task_dispatch_page(dispatcher)
        else:
            st.error("🔒 Task dispatch requires Operator or Admin role")
            st.info("Please contact your administrator to request elevated permissions.")

    if st.session_state.get("page") == "admin_users":
        if current_user and current_user.role.value == "admin":
            render_admin_users_page(auth)
        else:
            st.error("🔒 Access denied. Admin role required.")

    if st.session_state.get("page") == "system_config":
        if current_user and current_user.role.value == "admin":
            render_admin_system_config_page(auth)
        else:
            st.error("🔒 Access denied. Admin role required.")

    st.divider()

    render_footer(current_user)


if __name__ == "__main__":
    main()
