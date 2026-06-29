#!/usr/bin/env python3
"""
Metrics and performance visualisations for the DevSquad dashboard.
"""

import logging
import os
import sys
from typing import Any

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
            return response.json()
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
