#!/usr/bin/env python3
"""
Tests for the split dashboard package.

These tests verify that the monolithic ``scripts/dashboard.py`` was split into
``scripts/dashboard/`` without breaking public imports or the backward-
compatible facade entry point.
"""

import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Dashboard is a visualization feature; skip these tests when streamlit is not installed.
pytest.importorskip("streamlit")


class TestDashboardPackageImports:
    """Ensure the new package and facade expose the expected public API."""

    def test_dashboard_package_imports(self):
        from scripts.dashboard import (
            DashboardConfig,
            apply_custom_css,
            fetch_api_metrics,
            get_dispatcher,
            handle_auto_refresh,
            load_lifecycle_protocol,
            main,
            render_action_panel,
            render_admin_system_config_page,
            render_admin_users_page,
            render_cli_mapping_table,
            render_dispatch_result,
            render_footer,
            render_gate_status_panel,
            render_header,
            render_metrics_overview,
            render_performance_panel,
            render_phase_timeline,
            render_sidebar,
            render_task_dispatch_page,
            set_page_config,
        )

        assert callable(main)
        assert isinstance(DashboardConfig.PAGE_TITLE, str)
        assert "DevSquad" in DashboardConfig.PAGE_TITLE

    def test_facade_entry_point_reexports_main(self):
        import scripts.dashboard as dashboard_pkg
        import scripts.dashboard as facade_module

        # The facade and the package should expose the same ``main``.
        assert facade_module.main is dashboard_pkg.main

    def test_dashboard_config_values(self):
        from scripts.dashboard.components import DashboardConfig

        assert DashboardConfig.LAYOUT == "wide"
        assert "pending" in DashboardConfig.PHASE_COLORS
        assert "architect" in DashboardConfig.CORE_ROLES
        assert DashboardConfig.ROLE_ICONS["architect"]


class TestDashboardSubmodules:
    """Check that each submodule can be imported independently."""

    def test_components_module(self):
        from scripts.dashboard import components

        assert callable(components.set_page_config)
        assert callable(components.render_header)
        assert hasattr(components, "DashboardConfig")

    def test_lifecycle_views_module(self):
        from scripts.dashboard import lifecycle_views

        assert callable(lifecycle_views.load_lifecycle_protocol)
        assert callable(lifecycle_views.render_phase_timeline)

    def test_metrics_views_module(self):
        from scripts.dashboard import metrics_views

        assert callable(metrics_views.render_metrics_overview)
        assert callable(metrics_views.fetch_api_metrics)

    def test_dispatch_views_module(self):
        from scripts.dashboard import dispatch_views

        assert callable(dispatch_views.get_dispatcher)
        assert callable(dispatch_views.render_task_dispatch_page)

    def test_auth_views_module(self):
        from scripts.dashboard import auth_views

        assert callable(auth_views.render_admin_users_page)
        assert callable(auth_views.render_admin_system_config_page)

    def test_app_module(self):
        from scripts.dashboard import app

        assert callable(app.main)


class TestDashboardFacadeFile:
    """Verify the backward-compatible ``scripts/dashboard.py`` facade."""

    def test_facade_file_exists(self):
        facade_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "scripts", "dashboard.py"
        )
        assert os.path.isfile(facade_path)

    def test_facade_file_is_short(self):
        """Facade should be a thin shim, not a duplicate of the old monolith."""
        facade_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "scripts", "dashboard.py"
        )
        with open(facade_path, encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) < 50
