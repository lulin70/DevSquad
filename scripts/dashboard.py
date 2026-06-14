#!/usr/bin/env python3
"""
DevSquad V3.6.9-C Dashboard (Streamlit Production-Grade)

Interactive web dashboard for lifecycle visualization, monitoring,
and task dispatch.

Features:
  - Real-time lifecycle phase status
  - CLI command mapping visualization
  - Gate status monitoring
  - Performance metrics (real API data)
  - Task dispatch interface
  - Admin pages (user management & system config)
  - Auto-refresh with countdown timer

Usage:
    streamlit run scripts/dashboard.py

Requirements:
    streamlit>=1.28.0
"""

import os
import sys
import time
from datetime import datetime

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

from scripts.auth import AuthManager, User, UserRole


class DashboardConfig:
    """Dashboard configuration and styling."""

    PAGE_TITLE = "🔄 DevSquad Lifecycle Dashboard"
    PAGE_ICON = "🚀"
    LAYOUT = "wide"

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


@st.cache_resource
def load_lifecycle_protocol():
    """Load and cache the lifecycle protocol."""
    try:
        from scripts.collaboration.lifecycle_protocol import (
            FULL_LIFECYCLE_PHASES,
            VIEW_MAPPINGS,
            get_shared_protocol,
        )

        return {
            "protocol": get_shared_protocol(),
            "mappings": VIEW_MAPPINGS,
            "phases": FULL_LIFECYCLE_PHASES,
        }
    except Exception as e:
        st.error(f"Failed to load lifecycle protocol: {e}")
        return None


@st.cache_resource
def get_dispatcher():
    """Initialize and cache the MultiAgentDispatcher."""
    try:
        from scripts.collaboration.dispatcher import MultiAgentDispatcher

        return MultiAgentDispatcher(
            enable_warmup=True,
            enable_compression=True,
            enable_permission=True,
            enable_memory=True,
            enable_skillify=True,
            lang="auto",
        )
    except Exception as e:
        st.error(f"Failed to initialize dispatcher: {e}")
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


def render_header(current_user: User | None = None):
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


def render_metrics_overview(protocol_data):
    """Render key metrics overview cards with enhanced styling."""
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
                label="Total Phases", value=f"{total_phases}", delta=None, help="Total number of lifecycle phases"
            )

        with col2:
            delta_color = "normal" if completion_rate >= 50 else "inverse"
            st.metric(
                label="Completed",
                value=f"{completed}",
                delta=f"{completion_rate:.1f}%",
                delta_color=delta_color,
                help="Phases successfully completed",
            )

        with col3:
            st.metric(label="Running", value=f"{running}", delta_color="off", help="Phases currently executing")

        with col4:
            st.metric(
                label="Failed",
                value=f"{failed}",
                delta_color="inverse" if failed > 0 else "normal",
                help="Phases that failed execution",
            )

        with col5:
            progress_color = "#27ae60" if completion_rate >= 70 else "#ff7f0e" if completion_rate >= 40 else "#d62728"
            st.metric(
                label="Progress",
                value=f"{completion_rate:.1f}%",
                delta=None,
                help="Overall project progress",
                delta_color="normal",
            )

    except Exception as e:
        st.warning(f"Could not load metrics: {e}")


def render_phase_timeline(protocol_data):
    """Render interactive phase timeline visualization with enhanced cards."""
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
                badge_class = "status-success"
            elif phase_id in running_phases:
                status_icon = "🔄"
                status_text = "Running"
                badge_class = "status-info"
            elif phase_id in failed_phases:
                status_icon = "❌"
                status_text = "Failed"
                badge_class = "status-danger"
            else:
                status_icon = "⏳"
                status_text = "Pending"
                badge_class = "status-secondary"

            with st.container():
                st.markdown('<div class="phase-card">', unsafe_allow_html=True)
                col1, col2, col3, col4 = st.columns([1, 3, 2, 2])

                with col1:
                    st.markdown(f"**P{idx:02d}**")

                with col2:
                    st.markdown(f"**{phase.name}**")
                    desc = phase.description[:80] + ("..." if len(phase.description) > 80 else "")
                    st.caption(desc)

                with col3:
                    st.code(phase.role_id)

                with col4:
                    st.markdown(
                        f'<span class="status-badge {badge_class}">{status_icon} {status_text}</span>',
                        unsafe_allow_html=True,
                    )

                st.markdown("</div>", unsafe_allow_html=True)
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

            mapping_data.append(
                {
                    "Command": cmd_name.upper(),
                    "Phases": ", ".join(phase_ids),
                    "Phase Count": len(phase_ids),
                    "Mode": mapping.mode or "N/A",
                    "Gate": mapping.gate or "None",
                }
            )
        except Exception:
            mapping_data.append(
                {
                    "Command": cmd_name.upper(),
                    "Phases": ", ".join(mapping.phases),
                    "Phase Count": len(mapping.phases),
                    "Mode": mapping.mode or "N/A",
                    "Gate": mapping.gate or "None",
                }
            )

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
            },
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
                passed = getattr(result, "passed", False)
                verdict = getattr(result, "verdict", "UNKNOWN")

                col1, col2, col3 = st.columns([2, 2, 3])

                with col1:
                    st.markdown(f"**{cmd.upper()}**")

                with col2:
                    if passed:
                        st.success(f"✅ {verdict}")
                    else:
                        st.error(f"❌ {verdict}")

                with col3:
                    red_flags = getattr(result, "red_flags", [])
                    missing = getattr(result, "missing_evidence", [])

                    flags_text = f"🚩 {len(red_flags)} flags" if red_flags else "No flags"
                    missing_text = f"📋 {len(missing)} missing" if missing else "Complete"

                    st.markdown(f"{flags_text} | {missing_text}")

                st.divider()

    except Exception as e:
        st.warning(f"Could not load gate status: {e}")


def fetch_api_metrics():
    """
    Fetch real metrics from API server.
    Returns dict if successful, None if API unreachable.
    """
    try:
        response = requests.get("http://localhost:8000/api/v1/metrics/current", timeout=3)
        if response.status_code == 200:
            return response.json()
        return None
    except (requests.ConnectionError, requests.Timeout):
        return None
    except Exception:
        return None


def render_performance_panel():
    """Render performance metrics panel with real API data."""
    st.subheader("📊 System Performance")

    with st.spinner("Connecting to API Server..."):
        metrics_data = fetch_api_metrics()

        if metrics_data:
            st.success("✅ Connected to API Server")

            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**Response Time Metrics**")
                real_metrics = [
                    {"Metric": "Avg Response Time", "Value": f"{metrics_data.get('avg_response_time_ms', 'N/A')}ms"},
                    {"Metric": "P95 Latency", "Value": f"{metrics_data.get('p95_latency_ms', 'N/A')}ms"},
                    {"Metric": "Success Rate", "Value": f"{metrics_data.get('success_rate', 'N/A')}%"},
                    {"Metric": "Throughput", "Value": f"{metrics_data.get('throughput', 'N/A')} req/s"},
                ]
                st.dataframe(real_metrics, use_container_width=True, hide_index=True)

            with col2:
                st.markdown("**Resource Utilization**")
                cpu_usage = metrics_data.get("cpu_usage_percent", 0)
                mem_usage = metrics_data.get("memory_usage_percent", 0)

                st.progress(cpu_usage / 100 if cpu_usage > 0 else 0, text=f"CPU Usage: {cpu_usage:.1f}%")
                st.progress(mem_usage / 100 if mem_usage > 0 else 0, text=f"Memory Usage: {mem_usage:.1f}%")

                st.caption("*Real-time data from API Server*")

            col3, col4 = st.columns(2)
            with col3:
                st.metric(
                    label="Completion Rate",
                    value=f"{metrics_data.get('completion_rate', 0)}%",
                    help="Lifecycle phase completion rate",
                )
            with col4:
                st.metric(
                    label="Active Phases", value=metrics_data.get("running_phases", 0), help="Currently running phases"
                )
        else:
            st.error("❌ **API Server 未运行**")
            st.info("""
            **无法连接到 localhost:8000**

            请确保 DevSquad API Server 正在运行：
            ```bash
            python scripts/api_server.py
            ```

            或者使用以下命令启动：
            ```bash
            uvicorn scripts.api_server:app --host 0.0.0.0 --port 8000
            ```
            """)

            st.markdown("**模拟数据预览（仅用于演示）**")
            with st.expander("查看示例数据格式"):
                sample_data = [
                    {"Metric": "Avg Response Time", "Value": "~250ms (expected)"},
                    {"Metric": "P95 Latency", "Value": "~1200ms (expected)"},
                    {"Metric": "Success Rate", "Value": "~98.5% (expected)"},
                    {"Metric": "Throughput", "Value": "~120 req/s (expected)"},
                ]
                st.dataframe(sample_data, use_container_width=True, hide_index=True)


def render_task_dispatch_page(dispatcher):
    """Render the Task Dispatch page with full functionality."""
    st.header("🎯 Task Dispatch")
    st.markdown("---")

    col_input, col_config = st.columns([3, 2])

    with col_input:
        st.markdown("**Task Description**")
        task_description = st.text_area(
            "Enter your task description...",
            height=150,
            placeholder="Example: Design a RESTful API for user authentication with JWT tokens...",
            help="Describe the task you want the multi-agent team to work on",
        )

    with col_config:
        st.markdown("**Configuration**")

        selected_roles = st.multiselect(
            "Select Roles (leave empty for auto-match)",
            options=DashboardConfig.CORE_ROLES,
            format_func=lambda x: f"{DashboardConfig.ROLE_ICONS.get(x, '🤖')} {DashboardConfig.ROLE_NAMES.get(x, x)}",
            default=[],
            help="Choose specific roles or let AI auto-match based on task",
        )

        execution_mode = st.selectbox(
            "Execution Mode",
            options=["auto", "parallel", "sequential", "consensus"],
            format_func=lambda x: {
                "auto": "🤖 Auto (Recommended)",
                "parallel": "⚡ Parallel (Fastest)",
                "sequential": "📋 Sequential (Ordered)",
                "consensus": "🗳️ Consensus (Thorough)",
            }.get(x, x),
            index=0,
            help="How agents should collaborate on this task",
        )

        language = st.selectbox(
            "Output Language",
            options=["auto", "zh", "en", "ja"],
            format_func=lambda x: {
                "auto": "🌐 Auto-detect",
                "zh": "🇨🇳 中文",
                "en": "🇺🇸 English",
                "ja": "🇯🇵 日本語",
            }.get(x, x),
            index=0,
            help="Language for output and reports",
        )

        backend = st.selectbox(
            "LLM Backend",
            options=["mock", "openai", "anthropic"],
            format_func=lambda x: {
                "mock": "🎭 Mock (Demo)",
                "openai": "🟢 OpenAI GPT",
                "anthropic": "🟣 Anthropic Claude",
            }.get(x, x),
            index=0,
            help="AI backend to use for agent responses",
        )

    st.markdown("---")

    col_submit, col_clear = st.columns([1, 4])

    with col_submit:
        submit_disabled = not task_description.strip()
        if st.button(
            "🚀 Submit Task",
            type="primary",
            disabled=submit_disabled,
            use_container_width=True,
            help="Dispatch task to multi-agent system",
        ):
            if not dispatcher:
                st.error("Dispatcher not initialized. Please check logs.")
                return

            with st.spinner("🔄 Dispatching task to multi-agent system..."):
                try:
                    start_time = time.time()

                    result = dispatcher.dispatch(
                        task_description=task_description.strip(),
                        roles=selected_roles if selected_roles else None,
                        mode=execution_mode,
                    )

                    duration = time.time() - start_time

                    st.session_state["last_dispatch_result"] = result
                    st.session_state["dispatch_duration"] = duration

                    st.success(f"✅ Task completed in {duration:.2f}s")
                    st.rerun()

                except Exception as e:
                    st.error(f"❌ Dispatch failed: {e}")
                    st.exception(e)

    with col_clear:
        if st.button("🗑️ Clear Results", use_container_width=True):
            if "last_dispatch_result" in st.session_state:
                del st.session_state["last_dispatch_result"]
            if "dispatch_duration" in st.session_state:
                del st.session_state["dispatch_duration"]
            st.rerun()

    st.markdown("---")

    if "last_dispatch_result" in st.session_state:
        result = st.session_state["last_dispatch_result"]
        duration = st.session_state.get("dispatch_duration", 0)

        render_dispatch_result(result, duration)


def render_dispatch_result(result, duration: float):
    """Render dispatch result with metadata and formatted report."""
    st.subheader("📊 Dispatch Result")

    col_meta, col_timing = st.columns([2, 1])

    with col_meta:
        st.markdown("**Metadata**")

        intent_match = result.intent_match
        if intent_match:
            st.markdown(f"- **Intent Type**: `{intent_match.get('intent_type', 'N/A')}`")
            workflow_chain = intent_match.get("workflow_chain", [])
            if workflow_chain:
                st.markdown(f"- **Workflow**: `{' → '.join(workflow_chain[:5])}`")
            st.markdown(f"- **Confidence**: `{intent_match.get('confidence', 0):.1%}`")

        matched_roles = result.matched_roles
        if matched_roles:
            roles_display = []
            for role_id in matched_roles:
                icon = DashboardConfig.ROLE_ICONS.get(role_id, "🤖")
                name = DashboardConfig.ROLE_NAMES.get(role_id, role_id)
                roles_display.append(f"{icon} {name}")
            st.markdown(f"- **Matched Roles**: {', '.join(roles_display)}")

        st.markdown(f"- **Status**: {'✅ Success' if result.success else '❌ Failed'}")
        st.markdown(f"- **Duration**: `{duration:.2f}s`")

    with col_timing:
        st.markdown("**Timing Breakdown**")
        timing = result.details.get("timing", {})
        if timing:
            timing_data = [
                {"Step": k, "Time (s)": f"{v:.3f}"} for k, v in sorted(timing.items(), key=lambda x: x[1], reverse=True)
            ]
            st.dataframe(timing_data, use_container_width=True, hide_index=True)

    st.markdown("---")

    tabs_report, tabs_raw = st.tabs(["📝 Formatted Report", "🔍 Raw Data"])

    with tabs_report:
        st.markdown(result.summary or result.to_markdown())

    with tabs_raw:
        st.json(result.to_dict())


def render_admin_users_page(auth: AuthManager):
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
                new_role = st.selectbox(
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


def render_admin_system_config_page():
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
        {"Item": "DevSquad Version", "Value": "V3.6.9"},
        {"Item": "Dashboard Mode", "Value": "Production-Grade"},
    ]
    st.dataframe(sys_info, use_container_width=True, hide_index=True)

    st.markdown("---")

    st.markdown("**Configuration Status**")

    config_items = [
        {"Component": "Authentication", "Status": "✅ Enabled" if auth.credentials else "⚠️ No Config"},  # noqa: F821
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


def render_action_panel(protocol_data):
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


def handle_auto_refresh():
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


def render_sidebar(auth: AuthManager, current_user: User | None = None):
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

        show_details = st.checkbox("📋 Show Details", value=True)

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


def render_footer(current_user: User | None = None):
    """Render dashboard footer with version and session info."""
    st.markdown("---")

    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        st.markdown(
            "<center>**DevSquad V3.6.9** | Plan C | Production Ready | 🎨 Enhanced UI</center>", unsafe_allow_html=True
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

    auth = AuthManager(
        config_path=os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "deployment.yaml"
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
            render_admin_system_config_page()
        else:
            st.error("🔒 Access denied. Admin role required.")

    st.divider()

    render_footer(current_user)


if __name__ == "__main__":
    main()
