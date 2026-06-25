#!/usr/bin/env python3
"""
DevSquad Dashboard package.

Public API re-exports are preserved so that ``from scripts.dashboard import X``
continues to work after ``scripts/dashboard.py`` was split into this package.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.dashboard.app import main  # noqa: E402
from scripts.dashboard.auth_views import (  # noqa: E402
    render_admin_system_config_page,
    render_admin_users_page,
)
from scripts.dashboard.components import (  # noqa: E402
    DashboardConfig,
    apply_custom_css,
    handle_auto_refresh,
    render_action_panel,
    render_footer,
    render_header,
    render_sidebar,
    set_page_config,
)
from scripts.dashboard.dispatch_views import (  # noqa: E402
    get_dispatcher,
    render_dispatch_result,
    render_task_dispatch_page,
)
from scripts.dashboard.lifecycle_views import (  # noqa: E402
    load_lifecycle_protocol,
    render_cli_mapping_table,
    render_gate_status_panel,
    render_phase_timeline,
)
from scripts.dashboard.metrics_views import (  # noqa: E402
    fetch_api_metrics,
    render_metrics_overview,
    render_performance_panel,
)

__all__ = [
    "main",
    "DashboardConfig",
    "apply_custom_css",
    "handle_auto_refresh",
    "render_action_panel",
    "render_footer",
    "render_header",
    "render_sidebar",
    "set_page_config",
    "load_lifecycle_protocol",
    "render_cli_mapping_table",
    "render_gate_status_panel",
    "render_phase_timeline",
    "fetch_api_metrics",
    "render_metrics_overview",
    "render_performance_panel",
    "get_dispatcher",
    "render_dispatch_result",
    "render_task_dispatch_page",
    "render_admin_system_config_page",
    "render_admin_users_page",
]
