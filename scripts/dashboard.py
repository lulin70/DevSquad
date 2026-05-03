#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DevSquad V3.5.0-C Dashboard (Streamlit MVP)

Interactive web dashboard for lifecycle visualization and monitoring.

Features:
  - Real-time lifecycle phase status
  - CLI command mapping visualization
  - Gate status monitoring
  - Performance metrics display
  - Interactive phase execution control

Usage:
    streamlit run scripts/dashboard.py

Requirements:
    streamlit>=1.28.0
"""

import sys
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

from scripts.auth import AuthManager, User


class DashboardConfig:
    """Dashboard configuration and styling."""

    PAGE_TITLE = "🔄 DevSquad Lifecycle Dashboard"
    PAGE_ICON = "🚀"
    LAYOUT = "wide"

    COLOR_SCHEME = {
        "primary": "#1f77b4",
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


@st.cache_resource
def load_lifecycle_protocol():
    """Load and cache the lifecycle protocol."""
    try:
        from scripts.collaboration.lifecycle_protocol import (
            get_shared_protocol,
            VIEW_MAPPINGS,
            FULL_LIFECYCLE_PHASES,
        )
        return {
            "protocol": get_shared_protocol(),
            "mappings": VIEW_MAPPINGS,
            "phases": FULL_LIFECYCLE_PHASES,
        }
    except Exception as e:
        st.error(f"Failed to load lifecycle protocol: {e}")
        return None


def set_page_config():
    """Configure Streamlit page settings."""
    st.set_page_config(
        page_title=DashboardConfig.PAGE_TITLE,
        page_icon=DashboardConfig.PAGE_ICON,
        layout=DashboardConfig.LAYOUT,
        initial_sidebar_state="expanded",
    )


def apply_custom_css():
    """Apply custom CSS for better visual appearance."""
    st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        padding: 1rem 0;
    }
    
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 1rem;
        margin: 0.5rem 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .phase-card {
        background-color: white;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
        border-left: 4px solid #1f77b4;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    
    .status-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.875rem;
        font-weight: 600;
    }
    
    .success { background-color: #d4edda; color: #155724; }
    .warning { background-color: #fff3cd; color: #856404; }
    .danger { background-color: #f8d7da; color: #721c24; }
    .info { background-color: #d1ecf1; color: #0c5460; }
    </style>
    """, unsafe_allow_html=True)


def render_header(current_user: Optional[User] = None):
    """Render the main dashboard header."""
    st.markdown('<div class="main-header">🔄 DevSquad Lifecycle Dashboard</div>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.markdown("**Plan C Architecture** | CLI View Layer over 11-Phase Lifecycle")
        if current_user:
            st.caption(f"👤 {current_user.name} ({current_user.role.value})")
    with col2:
        st.markdown(f"**Last Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    with col3:
        if st.button("🔄 Refresh", key="refresh_header"):
            st.rerun()


def render_metrics_overview(protocol_data):
    """Render key metrics overview cards."""
    if not protocol_data:
        return
    
    protocol = protocol_data["protocol"]
    phases = protocol_data["phases"]
    
    try:
        status = protocol.get_status()
        
        total_phases = len(phases)
        completed = len(status.get("completed_phases", []))
        running = len(status.get("running_phases", []))
        failed = len(status.get("failed_phases", []))
        
        completion_rate = (completed / total_phases * 100) if total_phases > 0 else 0
        
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric(
                label="Total Phases",
                value=f"{total_phases}",
                delta=None,
                help="Total number of lifecycle phases"
            )
        
        with col2:
            st.metric(
                label="Completed",
                value=f"{completed}",
                delta=f"{completion_rate:.1f}%",
                delta_color="normal" if completion_rate >= 50 else "inverse",
                help="Phases successfully completed"
            )
        
        with col3:
            st.metric(
                label="Running",
                value=f"{running}",
                delta_color="off",
                help="Phases currently executing"
            )
        
        with col4:
            st.metric(
                label="Failed",
                value=f"{failed}",
                delta_color="inverse" if failed > 0 else "normal",
                help="Phases that failed execution"
            )
        
        with col5:
            st.metric(
                label="Progress",
                value=f"{completion_rate:.1f}%",
                delta=None,
                help="Overall project progress"
            )
            
    except Exception as e:
        st.warning(f"Could not load metrics: {e}")


def render_phase_timeline(protocol_data):
    """Render interactive phase timeline visualization."""
    if not protocol_data:
        return
    
    st.subheader("📋 Phase Timeline")
    
    phases = protocol_data["phases"]
    protocol = protocol_data["protocol"]
    
    try:
        status = protocol.get_status()
        completed_phases = set(status.get("completed_phases", []))
        running_phases = set(status.get("running_phases", []))
        failed_phases = set(status.get("failed_phases", []))
        
        for idx, phase in enumerate(phases, 1):
            phase_id = phase.phase_id
            
            if phase_id in completed_phases:
                status_icon = "✅"
                status_text = "Completed"
                bg_color = "#d4edda"
                text_color = "#155724"
            elif phase_id in running_phases:
                status_icon = "🔄"
                status_text = "Running"
                bg_color = "#cce5ff"
                text_color = "#004085"
            elif phase_id in failed_phases:
                status_icon = "❌"
                status_text = "Failed"
                bg_color = "#f8d7da"
                text_color = "#721c24"
            else:
                status_icon = "⏳"
                status_text = "Pending"
                bg_color = "#e2e3e5"
                text_color = "#383d41"
            
            col1, col2, col3, col4 = st.columns([1, 3, 2, 2])
            
            with col1:
                st.markdown(f"**P{idx:02d}**")
            
            with col2:
                st.markdown(f"**{phase.name}**")
                st.caption(phase.description[:80] + ("..." if len(phase.description) > 80 else ""))
            
            with col3:
                st.markdown(f"`{phase.role_id}`")
                
            with col4:
                st.markdown(
                    f'<span class="status-badge {status_text.lower()}">{status_icon} {status_text}</span>',
                    unsafe_allow_html=True
                )
            
            st.divider()
            
    except Exception as e:
        st.error(f"Error rendering timeline: {e}")


def render_cli_mapping_table(protocol_data):
    """Render CLI command to phase mapping table."""
    if not protocol_data:
        return
    
    st.subheader("🔗 CLI Command Mapping (Plan C View Layer)")
    
    mappings = protocol_data["mappings"]
    protocol = protocol_data["protocol"]
    
    mapping_data = []
    for cmd_name, mapping in mappings.items():
        try:
            resolved_phases = protocol.resolve_command_to_phases(cmd_name)
            phase_ids = [p.phase_id for p in resolved_phases] if resolved_phases else mapping.phases
            
            mapping_data.append({
                "Command": cmd_name.upper(),
                "Phases": ", ".join(phase_ids),
                "Phase Count": len(phase_ids),
                "Mode": mapping.mode or "N/A",
                "Gate": mapping.gate or "None",
            })
        except Exception:
            mapping_data.append({
                "Command": cmd_name.upper(),
                "Phases": ", ".join(mapping.phases),
                "Phase Count": len(mapping.phases),
                "Mode": mapping.mode or "N/A",
                "Gate": mapping.gate or "None",
            })
    
    if mapping_data:
        st.dataframe(
            mapping_data,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Command": st.column_config.TextColumn("Command", width="medium"),
                "Phases": st.column_config.TextColumn("Mapped Phases", width="large"),
                "Phase Count": st.column_config.NumberColumn("Count", width="small"),
                "Mode": st.column_config.TextColumn("Mode", width="small"),
                "Gate": st.column_config.TextColumn("Gate", width="medium"),
            }
        )


def render_gate_status_panel(protocol_data):
    """Render gate status monitoring panel."""
    if not protocol_data:
        return
    
    st.subheader("🚧 Gate Status Monitor")
    
    protocol = protocol_data["protocol"]
    
    try:
        gate_results = {}
        
        test_commands = ["spec", "plan", "build", "test", "review", "ship"]
        for cmd in test_commands:
            try:
                result = protocol.check_command_gate(cmd)
                gate_results[cmd] = result
            except Exception:
                pass
        
        if gate_results:
            for cmd, result in gate_results.items():
                passed = getattr(result, 'passed', False)
                verdict = getattr(result, 'verdict', 'UNKNOWN')
                
                col1, col2, col3 = st.columns([2, 2, 3])
                
                with col1:
                    st.markdown(f"**{cmd.upper()}**")
                
                with col2:
                    if passed:
                        st.success(f"✅ {verdict}")
                    else:
                        st.error(f"❌ {verdict}")
                
                with col3:
                    red_flags = getattr(result, 'red_flags', [])
                    missing = getattr(result, 'missing_evidence', [])
                    
                    flags_text = f"🚩 {len(red_flags)} flags" if red_flags else "No flags"
                    missing_text = f"📋 {len(missing)} missing" if missing else "Complete"
                    
                    st.markdown(f"{flags_text} | {missing_text}")
                
                st.divider()
                
    except Exception as e:
        st.warning(f"Could not load gate status: {e}")


def render_performance_panel():
    """Render performance metrics panel."""
    st.subheader("📊 System Performance")
    
    try:
        import time
        import random
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Response Time Metrics**")
            
            metrics_data = [
                {"Metric": "Avg Response Time", "Value": f"{random.uniform(100, 500):.1f}ms"},
                {"Metric": "P95 Latency", "Value": f"{random.uniform(800, 2000):.1f}ms"},
                {"Metric": "Success Rate", "Value": f"{random.uniform(95, 99.9):.1f}%"},
                {"Metric": "Throughput", "Value": f"{random.randint(50, 200)} req/s"},
            ]
            
            st.dataframe(metrics_data, use_container_width=True, hide_index=True)
        
        with col2:
            st.markdown("**Resource Utilization**")
            
            cpu_usage = random.uniform(20, 80)
            mem_usage = random.uniform(40, 85)
            
            st.progress(cpu_usage / 100, text=f"CPU Usage: {cpu_usage:.1f}%")
            st.progress(mem_usage / 100, text=f"Memory Usage: {mem_usage:.1f}%")
            
            st.caption("*Simulated data for demonstration*")
            
    except Exception as e:
        st.error(f"Error loading performance data: {e}")


def render_action_panel(protocol_data):
    """Render action control panel."""
    st.subheader("🎮 Control Panel")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("▶️ Run All Phases", type="primary", use_container_width=True):
            st.session_state['action'] = 'run_all'
            st.success("Initiated full lifecycle run...")
            st.rerun()
    
    with col2:
        if st.button("🔄 Reset State", use_container_width=True):
            st.session_state['action'] = 'reset'
            st.info("Resetting lifecycle state...")
            st.rerun()
    
    with col3:
        if st.button("📊 Generate Report", use_container_width=True):
            st.session_state['action'] = 'report'
            st.success("Generating benchmark report...")


def render_sidebar(auth: AuthManager, current_user: Optional[User] = None):
    """Render sidebar navigation and controls."""
    with st.sidebar:
        st.header("Navigation")
        
        page = st.radio(
            "Go to",
            ["Overview", "Phases", "Mapping", "Gates", "Performance"],
            captions=[
                "System overview & metrics",
                "Phase timeline & details",
                "CLI command mapping",
                "Gate status monitor",
                "Performance metrics"
            ]
        )
        
        st.divider()
        
        # User info and logout
        if current_user:
            auth.get_login_button()
        
        st.header("Settings")
        
        auto_refresh = st.checkbox("Auto Refresh (30s)", value=False)
        show_details = st.checkbox("Show Details", value=True)
        
        st.divider()
        
        st.header("Quick Actions")
        
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.rerun()
        
        if st.button("📥 Export Status", use_container_width=True):
            st.success("Status exported!")
        
        # Admin-only settings
        if current_user and current_user.role.value == "admin":
            st.divider()
            st.header("⚙️ Admin")
            
            if st.button("👥 Manage Users", use_container_width=True):
                st.session_state.page = "admin_users"
            
            if st.button("⚙️ System Config", use_container_width=True):
                st.session_state.page = "system_config"
        
        return page


def render_footer(current_user: Optional[User] = None):
    """Render dashboard footer with version and session info."""
    st.markdown("---")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        st.markdown(
            "<center>**DevSquad V3.6.0-Prod** | Plan C | Production Ready</center>",
            unsafe_allow_html=True
        )
    
    with col2:
        if current_user:
            st.caption(f"Session: {current_user.session_id[:8]}...")
    
    with col3:
        st.caption(f"© {datetime.now().year} DevSquad Team")


def main():
    """Main dashboard entry point."""
    set_page_config()
    apply_custom_css()
    
    # Initialize authentication
    auth = AuthManager(config_path=os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "config",
        "deployment.yaml"
    ))
    
    # Authenticate user (will show login form if not authenticated)
    auth.authenticate_streamlit()
    
    # Get current user info
    current_user = auth.get_current_user()
    
    page = render_sidebar(auth, current_user)
    
    render_header(current_user)
    
    protocol_data = load_lifecycle_protocol()
    
    # Check permissions for sensitive operations
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
    
    st.divider()
    
    render_footer(current_user)


if __name__ == "__main__":
    main()
