#!/usr/bin/env python3
"""
Lifecycle protocol visualisations: phase timeline, CLI mapping and gate status.
"""

import logging
import os
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st  # noqa: E402

logger = logging.getLogger(__name__)


@st.cache_resource
def load_lifecycle_protocol() -> dict[str, Any] | None:
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
    except (ImportError, AttributeError, RuntimeError) as e:
        st.error(f"Failed to load lifecycle protocol: {e}")
        return None


def render_phase_timeline(protocol_data: dict[str, Any] | None) -> None:
    """Render interactive phase timeline visualization with enhanced cards."""
    if not protocol_data:
        return

    st.subheader("📋 Phase Timeline")

    phases = protocol_data["phases"]
    protocol = protocol_data["protocol"]

    try:
        status = protocol.get_status()
        completed_phases = set(status.completed_phases)
        failed_phases = set(status.failed_phases)
        # LifecycleStatus has no running_phases field; dashboard cannot
        # derive it without access to protocol._phase_states
        running_phases = set()

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

    except (KeyError, ValueError, TypeError, AttributeError, RuntimeError) as e:
        logger.error("Error rendering timeline: %s", e)
        st.error(f"Error rendering timeline: {e}")


def render_cli_mapping_table(protocol_data: dict[str, Any] | None) -> None:
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
        except (KeyError, AttributeError, RuntimeError) as e:
            logger.debug("Could not resolve command '%s': %s", cmd_name, e)
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


def render_gate_status_panel(protocol_data: dict[str, Any] | None) -> None:
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
            except (KeyError, AttributeError, RuntimeError) as e:
                logger.debug("Gate check failed for '%s': %s", cmd, e)
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

    except (KeyError, ValueError, TypeError, AttributeError, RuntimeError) as e:
        logger.error("Could not load gate status: %s", e)
        st.warning(f"Could not load gate status: {e}")
