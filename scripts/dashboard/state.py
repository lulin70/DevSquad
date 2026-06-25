#!/usr/bin/env python3
"""
Streamlit session_state management helpers for the DevSquad dashboard.
"""

from typing import Any

import streamlit as st


def get_state(key: str, default: Any | None = None) -> Any:
    """Get a value from st.session_state with a default fallback."""
    return st.session_state.get(key, default)


def set_state(key: str, value: Any) -> None:
    """Set a value in st.session_state."""
    st.session_state[key] = value


def init_state(defaults: dict[str, Any]) -> None:
    """Initialize missing session_state keys with default values."""
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def clear_state(keys: list[str]) -> None:
    """Remove the given keys from session_state if they exist."""
    for key in keys:
        st.session_state.pop(key, None)
