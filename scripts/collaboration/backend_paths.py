#!/usr/bin/env python3
"""
B/A/C Backend Path Enums and Constants for V4.5.2.

Defines the resolve order (B → A → C), environment triggers,
and error classification for HostLLMBridge + Direct API + Mock fallback.

See docs/architecture/V4.5.2_ARCHITECTURE.md §7 for detailed design.
"""

import logging
from enum import Enum

logger = logging.getLogger(__name__)


class BackendPath(str, Enum):
    """Backend execution path (B/A/C).

    B:  Programming AI Host Bridge (Trae/ClaudeCode, no API key needed)
    A:  Direct API (OpenAI/Anthropic/MOKA, requires API key)
    C:  Honest Mock fallback (always available, always [MOCK MODE] marked)
    """
    B_HOST_BRIDGE = "B"
    A_DIRECT_API = "A"
    C_MOCK = "C"


# === B/A/C Resolve Order (B → A → C) ===
# This order is critical: user expects the fastest path first.
# If a backend reports it's available, we use it immediately.
RESOLVE_ORDER: tuple[BackendPath, ...] = (
    BackendPath.B_HOST_BRIDGE,
    BackendPath.A_DIRECT_API,
    BackendPath.C_MOCK,
)

# === Environment variables that trigger B path (host detection) ===
# If any of these are present, we assume we are running inside
# a programming AI IDE host that supports HostLLMBridge.
HOST_ENV_TRIGGERS: dict[str, str] = {
    "TRAE_ENV": "host_llm",
    "TRAE_AGENT_PATH": "host_llm",
    "CLAUDE_CODE_ENV": "claude_code",
    "ANTHROPIC_ENV": "claude_code",
}

# === A path API key environment triggers (detection order) ===
# Tried in order when backend_type is "auto". First available wins.
API_KEY_ENV_TRIGGERS: tuple[str, ...] = (
    "DEVSQUAD_OPENAI_API_KEY",
    "DEVSQUAD_ANTHROPIC_API_KEY",
    "MOKA_API_KEY",
)

# === Fuse (continuous failure skip) policy (PRD §5.2) ===
# - Single failure → degrade to next path (don't fatal, continue)
# - N consecutive failures with same reason → permanently skip the path
# This prevents infinite waits when B path is permanently down
# but user still gets a conclusion from A or C.
DEGRADE_ON_SINGLE_FAILURE = True
FUSE_SKIP_AFTER_CONSECUTIVE = 2


# === Error classification for fuse counting ===
# Same reason → count toward fuse skip; different reason → reset count.
# Why: consecutive "host_timeout" means B is permanently down, not transient.

class BackendErrorReason:
    """Classify backend failure reason for fuse counting."""

    HOST_TIMEOUT = "host_timeout"
    AUTH_INVALID = "auth_invalid"
    RATE_LIMIT = "rate_limit"
    NETWORK_ERROR = "network_error"
    PROVIDER_ERROR = "provider_error"
    UNKNOWN = "unknown"


def classify_error(exc: Exception) -> str:
    """Classify an exception to a reason string for fuse counting.

    Same reason strings are counted together toward FUSE_SKIP_AFTER_CONSECUTIVE.

    Args:
        exc: The exception that caused the backend failure.

    Returns:
        str: Reason string (one of BackendErrorReason constants).
    """
    # Increment anti-ghost counter on every classify call
    _inc_call_counter_er()

    exc_type = type(exc).__name__

    # Timeout -> B path most likely, but applies to A too
    if isinstance(exc, TimeoutError) or exc_type == "Timeout":
        return BackendErrorReason.HOST_TIMEOUT

    # Try to extract status code from known SDK exceptions
    status_code = _try_extract_status_code(exc)
    if status_code in (401, 403):
        return BackendErrorReason.AUTH_INVALID
    if status_code == 429:
        return BackendErrorReason.RATE_LIMIT

    # Network connectivity errors
    if isinstance(exc, (ConnectionError, OSError)):
        return BackendErrorReason.NETWORK_ERROR

    # RuntimeError (from OpenAI/Anthropic generate failure)
    if isinstance(exc, RuntimeError):
        return BackendErrorReason.PROVIDER_ERROR

    # Fallback
    exc_name = f"{type(exc).__module__}.{exc_type}"
    logger.debug("Backend failure: unknown reason for %s", exc_name, exc_info=False)
    return BackendErrorReason.UNKNOWN


def _try_extract_status_code(exc: Exception) -> int | None:
    """Try to extract HTTP status code from various SDK exceptions.

    Covers openai.APIError, anthropic.APIError, and httpx status codes.
    """
    # Check for status_code attribute (openai.APIError, httpx responses)
    status = getattr(exc, "status_code", None)
    if status is not None:
        return int(status)

    # Check for response.status_code (httpx.HTTPStatusError, etc.)
    response = getattr(exc, "response", None)
    if response is not None:
        status = getattr(response, "status_code", None)
        if status is not None:
            return int(status)

    # Check for status_code on the exception's args (some SDKs pack it there)
    if hasattr(exc, "args") and len(exc.args) > 0:
        for arg in exc.args:
            if isinstance(arg, int) and 400 <= arg <= 599:
                return arg
            if isinstance(arg, dict):
                sc = arg.get("status_code") or arg.get("status")
                if sc is not None:
                    return int(sc)

    return None


# === Custom Exceptions for B/A/C paths ===

class BackendUnavailable(Exception):
    """Raised when no backend path is available.

    This happens when:
    - User explicitly requested "host" but host is not available
    - All paths failed and we reached the end of B/A/C
    """
    pass


class BackendTimeout(BackendUnavailable):
    """Raised when a backend request times out (only for B/A paths)."""
    pass


class BackendAuthError(BackendUnavailable):
    """Raised when authentication fails (only for A paths)."""
    pass


class BackendRateLimit(BackendUnavailable):
    """Raised when rate limit is hit (only for A paths)."""
    pass


# Anti-Ghost: increment call counter on module activation
# CI: scripts/check_module_activation.py checks this > 0
_call_counter_er: int = 0


def _inc_call_counter_er() -> None:
    """Increment module activation counter (anti-ghost)."""
    global _call_counter_er
    _call_counter_er += 1


def get_call_counter_er() -> int:
    """Return module activation counter (for Anti-Ghost verification)."""
    return _call_counter_er


# Initialize when module loaded
_inc_call_counter_er()
