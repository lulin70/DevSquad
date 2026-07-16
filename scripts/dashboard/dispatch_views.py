#!/usr/bin/env python3
"""
Task dispatch interface and result rendering for the DevSquad dashboard.
"""

import logging
import os
import sys
import time
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st  # noqa: E402

from scripts.dashboard.components import DashboardConfig  # noqa: E402

logger = logging.getLogger(__name__)


@st.cache_resource
def get_dispatcher() -> Any | None:
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
    except (ImportError, AttributeError, RuntimeError) as e:
        st.error(f"Failed to initialize dispatcher: {e}")
        return None


def render_task_dispatch_page(dispatcher: Any | None) -> None:
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

        st.selectbox(
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

        st.selectbox(
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

                except (RuntimeError, ValueError, ConnectionError, TimeoutError, KeyError) as e:
                    logger.error("Dispatch failed: %s", e, exc_info=True)
                    st.error(f"❌ Dispatch failed: {e}")
                    with st.expander("🔍 Error details", expanded=False):
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


def render_dispatch_result(result: Any, duration: float) -> None:
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
                st.markdown(f"- **Workflow**: `{' -> '.join(workflow_chain[:5])}`")
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
