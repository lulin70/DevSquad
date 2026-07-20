#!/usr/bin/env python3
"""
Metrics and performance visualisations for the DevSquad dashboard.
"""

import logging
import os
import sys
from typing import Any, Literal

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st  # noqa: E402

logger = logging.getLogger(__name__)


def render_metrics_overview(protocol_data: dict[str, Any] | None) -> None:
    """Render key metrics overview cards with enhanced styling."""
    if not protocol_data:
        return

    protocol = protocol_data["protocol"]
    phases = protocol_data["phases"]

    try:
        status = protocol.get_status()

        total_phases = len(phases)
        completed = len(status.completed_phases)
        failed = len(status.failed_phases)
        blocked = len(status.blocked_phases)
        running = total_phases - completed - failed - blocked

        completion_rate = (completed / total_phases * 100) if total_phases > 0 else 0

        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            st.metric(
                label="Total Phases", value=f"{total_phases}", delta=None, help="Total number of lifecycle phases"
            )

        with col2:
            delta_color: Literal["normal", "inverse"] = (
                "normal" if completion_rate >= 50 else "inverse"
            )
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
            st.metric(
                label="Progress",
                value=f"{completion_rate:.1f}%",
                delta=None,
                help="Overall project progress",
                delta_color="normal",
            )

    except (KeyError, ValueError, TypeError, AttributeError, RuntimeError, ConnectionError) as e:
        logger.error("Could not load metrics: %s", e)
        st.warning(f"Could not load metrics: {e}")


def fetch_api_metrics() -> dict[str, Any] | None:
    """
    Fetch real metrics from API server.
    Returns dict if successful, None if API unreachable.
    """
    try:
        response = requests.get("http://localhost:8000/api/v1/metrics/current", timeout=3)
        if response.status_code == 200:
            data = response.json()
            # ``response.json()`` returns ``Any``; narrow to dict so the declared
            # return type holds (a non-dict JSON payload is treated as no data).
            if isinstance(data, dict):
                return data
            return None
        return None
    except (requests.ConnectionError, requests.Timeout):
        return None
    except (ValueError, requests.RequestException) as e:
        logger.debug("API metrics fetch failed: %s", e)
        return None


def render_performance_panel() -> None:
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

            # W1-T2: Interactive performance charts
            st.divider()
            _render_performance_charts(metrics_data)
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


# ── W1-T2: Interactive performance charts ──

# Morandi color palette for charts (per user_profile: comfortable, not harsh)
_MORANDI_CHART_COLORS: dict[str, str] = {
    "primary": "#7B9EA8",      # Morandi blue-gray
    "success": "#8FA886",      # Morandi sage
    "warning": "#C9A87C",      # Morandi tan
    "danger": "#B58484",       # Morandi rose
    "info": "#9DB5C2",         # Morandi light blue
    "neutral": "#B0B0B0",      # Morandi gray
}


def _render_performance_charts(metrics_data: dict[str, Any]) -> None:
    """Render interactive performance charts using Streamlit native charts.

    Avoids adding plotly as a hard dependency; uses st.bar_chart / st.line_chart
    which are streamlit built-ins (Altair under the hood, hover-interactive).

    Args:
        metrics_data: Dict from /api/v1/metrics/current containing avg_response_time_ms,
            p95_latency_ms, success_rate, throughput, cpu_usage_percent, memory_usage_percent.
    """
    st.markdown("### 📈 Performance Visualizations")

    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        st.markdown("**Response Time Breakdown**")
        # Bar chart comparing avg vs P95 latency
        avg_ms = _safe_float(metrics_data.get("avg_response_time_ms", 0))
        p95_ms = _safe_float(metrics_data.get("p95_latency_ms", 0))
        latency_data = [
            {"Metric": "Avg Response", "Milliseconds": avg_ms, "Color": _MORANDI_CHART_COLORS["primary"]},
            {"Metric": "P95 Latency", "Milliseconds": p95_ms, "Color": _MORANDI_CHART_COLORS["warning"]},
        ]
        st.bar_chart(
            latency_data,
            x="Metric",
            y="Milliseconds",
            color="Color",
            use_container_width=True,
        )
        st.caption(f"Avg: **{avg_ms:.0f}ms** | P95: **{p95_ms:.0f}ms**")

    with col_chart2:
        st.markdown("**System Health Indicators**")
        # Horizontal bar chart for utilization
        cpu = _safe_float(metrics_data.get("cpu_usage_percent", 0))
        mem = _safe_float(metrics_data.get("memory_usage_percent", 0))
        success = _safe_float(metrics_data.get("success_rate", 100))
        health_data = [
            {"Resource": "CPU", "Percent": cpu},
            {"Resource": "Memory", "Percent": mem},
            {"Resource": "Success Rate", "Percent": success},
        ]
        st.bar_chart(
            health_data,
            x="Resource",
            y="Percent",
            use_container_width=True,
        )
        st.caption(f"CPU: **{cpu:.1f}%** | Mem: **{mem:.1f}%** | Success: **{success:.1f}%**")

    # Throughput gauge (using st.metric for simplicity, no extra deps)
    st.divider()
    st.markdown("**Throughput & Reliability**")
    col_t1, col_t2, col_t3 = st.columns(3)
    throughput = _safe_float(metrics_data.get("throughput", 0))
    with col_t1:
        st.metric(
            label="⚡ Throughput",
            value=f"{throughput:.1f} req/s",
            delta=f"{throughput * 60:.0f} req/min",
            help="Requests processed per second",
        )
    with col_t2:
        st.metric(
            label="✅ Success Rate",
            value=f"{success:.1f}%",
            delta=f"{(success - 95):.1f}%" if success >= 95 else f"-{max(0, 95 - success):.1f}%",
            delta_color="normal" if success >= 95 else "inverse",
            help="Target: ≥95%",
        )
    with col_t3:
        # P95 vs target (800ms is typical SLO)
        p95_target = 800.0
        delta_p95 = p95_ms - p95_target
        st.metric(
            label="🎯 P95 vs SLO",
            value=f"{p95_ms:.0f}ms",
            delta=f"{delta_p95:+.0f}ms vs {p95_target:.0f}ms SLO",
            delta_color="inverse" if delta_p95 > 0 else "normal",
            help="Negative = better than SLO",
        )


def _safe_float(value: Any) -> float:
    """Safely convert API response value to float (handles str/int/None)."""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
