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

            # W1-T1: Real-time execution visualization
            # Use st.status to show progressive phases + role pipeline
            try:
                start_time = time.time()

                # Determine actual roles for visualization (auto-match if empty)
                viz_roles = selected_roles if selected_roles else _predict_auto_roles(
                    task_description, dispatcher
                )

                with st.status("🔄 Dispatching task to multi-agent system...", expanded=True) as status:
                    # Phase 1: Initialization
                    st.write("📋 **Phase 1/4**: Initializing dispatcher and validating input...")
                    _render_role_pipeline(viz_roles, active_idx=-1, status="pending")
                    time.sleep(0.05)

                    # Phase 2: Role matching
                    st.write("🎯 **Phase 2/4**: Matching roles to task...")
                    _render_role_pipeline(viz_roles, active_idx=0, status="matching")
                    time.sleep(0.05)

                    # Phase 3: Parallel execution
                    st.write("⚡ **Phase 3/4**: Agents executing in parallel...")
                    _render_role_pipeline(viz_roles, active_idx=len(viz_roles) - 1, status="executing")
                    time.sleep(0.05)

                    # Phase 4: Consensus & report assembly
                    st.write("🗳️ **Phase 4/4**: Building consensus and assembling report...")

                    # Actual dispatch call (real work happens here)
                    result = dispatcher.dispatch(
                        task_description=task_description.strip(),
                        roles=selected_roles if selected_roles else None,
                        mode=execution_mode,
                    )

                    duration = time.time() - start_time

                    # Mark all roles as completed
                    _render_role_pipeline(viz_roles, active_idx=len(viz_roles), status="completed")

                    if result.success:
                        status.update(
                            label=f"✅ Dispatch completed in {duration:.2f}s",
                            state="complete",
                            expanded=False,
                        )
                    else:
                        status.update(
                            label=f"❌ Dispatch failed in {duration:.2f}s",
                            state="error",
                            expanded=False,
                        )

                    st.session_state["last_dispatch_result"] = result
                    st.session_state["dispatch_duration"] = duration
                    st.session_state["last_viz_roles"] = viz_roles

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


# ── W1-T1: Real-time execution visualization helpers ──


_ROLE_PIPELINE_ICONS: dict[str, str] = {
    "pending": "⏳",
    "matching": "🎯",
    "executing": "⚡",
    "completed": "✅",
    "failed": "❌",
}

_ROLE_PIPELINE_COLORS: dict[str, str] = {
    "pending": "#B0B0B0",
    "matching": "#C9A87C",
    "executing": "#7B9EA8",
    "completed": "#8FA886",
    "failed": "#B58484",
}


def _predict_auto_roles(task_description: str, dispatcher: Any | None) -> list[str]:
    """Predict roles for visualization when auto-match is selected.

    Uses dispatcher.analyze_task() if available; falls back to keyword heuristics.
    Returns 2-4 role IDs for visualization purposes only (actual dispatch uses
    the real auto-match result).
    """
    role_ids = _try_dispatcher_analyze(task_description, dispatcher)
    if role_ids:
        return role_ids[:4]
    return _keyword_fallback_roles(task_description)[:4]


def _try_dispatcher_analyze(task_description: str, dispatcher: Any | None) -> list[str]:
    """Try to get role IDs from dispatcher.analyze_task(); return [] on failure."""
    if dispatcher is None:
        return []
    try:
        matched = dispatcher.analyze_task(task_description)
    except (AttributeError, RuntimeError, TypeError):
        return []
    if not matched or not isinstance(matched, list):
        return []
    role_ids = [m.get("name", "") for m in matched if isinstance(m, dict)]
    return [r for r in role_ids if r]


# Keyword-based heuristic fallback (must match DashboardConfig.CORE_ROLES values)
_KEYWORD_ROLE_MAP: list[tuple[tuple[str, ...], str]] = [
    (("security", "vulnerability", "audit", "安全", "漏洞"), "security"),
    (("test", "quality", "测试", "质量"), "tester"),
    (("deploy", "ci", "cd", "docker", "部署"), "devops"),
    (("ui", "frontend", "界面", "前端"), "ui-designer"),
    (("architecture", "design", "架构", "设计"), "architect"),
    (("requirement", "prd", "需求", "产品"), "product-manager"),
]


def _keyword_fallback_roles(task_description: str) -> list[str]:
    """Return role IDs based on keyword matching; defaults to architect/tester/solo-coder."""
    text = task_description.lower()
    roles = [role for keywords, role in _KEYWORD_ROLE_MAP if any(k in text for k in keywords)]
    if not roles:
        roles = ["architect", "tester", "solo-coder"]
    return roles


def _render_role_pipeline(roles: list[str], active_idx: int, status: str) -> None:
    """Render role pipeline as colored badges showing parallel execution.

    Args:
        roles: List of role IDs in the dispatch.
        active_idx: Index of the currently-active role (-1 = none started,
            len(roles) = all completed).
        status: Pipeline status (pending/matching/executing/completed/failed).
    """
    if not roles:
        st.caption("_No roles predicted yet_")
        return

    badges: list[str] = []
    for i, role_id in enumerate(roles):
        icon = DashboardConfig.ROLE_ICONS.get(role_id, "🤖")
        name = DashboardConfig.ROLE_NAMES.get(role_id, role_id)

        if status == "completed":
            state_icon = _ROLE_PIPELINE_ICONS["completed"]
            color = _ROLE_PIPELINE_COLORS["completed"]
        elif status == "failed":
            state_icon = _ROLE_PIPELINE_ICONS["failed"]
            color = _ROLE_PIPELINE_COLORS["failed"]
        elif i < active_idx:
            state_icon = _ROLE_PIPELINE_ICONS["completed"]
            color = _ROLE_PIPELINE_COLORS["completed"]
        elif i == active_idx:
            state_icon = _ROLE_PIPELINE_ICONS.get(status, "⚡")
            color = _ROLE_PIPELINE_COLORS.get(status, "#7B9EA8")
        else:
            state_icon = _ROLE_PIPELINE_ICONS["pending"]
            color = _ROLE_PIPELINE_COLORS["pending"]

        badges.append(
            f'<span style="background:{color};color:white;padding:0.35rem 0.7rem;'
            f'border-radius:9999px;font-size:0.8rem;font-weight:600;margin:0 0.2rem;">'
            f'{state_icon} {icon} {name}</span>'
        )

    st.markdown(
        f'<div style="padding:0.5rem 0;">{"".join(badges)}</div>',
        unsafe_allow_html=True,
    )
