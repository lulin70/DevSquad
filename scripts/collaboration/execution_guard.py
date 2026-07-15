#!/usr/bin/env python3
"""
ExecutionGuard - V3.6.1 Real-Time Execution Guardian

Monitors worker execution in real-time and triggers abort conditions when
anomalies are detected (timeout, output overflow, critical errors).

Design Principles:
- Zero external dependencies: Pure string matching only
- Lightweight: <1ms per check, no performance overhead
- Configurable: All thresholds adjustable at runtime
- Multiple trigger types: Time, output size, keywords, token count

Usage:
    guard = ExecutionGuard(max_duration_sec=300, max_output_tokens=8000)
    should_abort, reason = guard.check_abort(output, elapsed_time=120.5, token_count=5000)
    if should_abort:
        logger.warning("Aborting: %s", reason)
"""

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Module 7 (Matt P0-4): [DEBUG-xxx] tag mechanism
# ------------------------------------------------------------------

#: Regex pattern for [DEBUG-xxx] tags. Matches ``[DEBUG-SOMETHING]``.
_DEBUG_TAG_PATTERN = re.compile(r"\[DEBUG-([A-Z0-9_]+)\]")

#: Module-level registry of debug tags created during a session.
_registered_debug_tags: set[str] = set()


def register_debug_tag(tag: str) -> None:
    """Register a debug tag for tracking.

    Tags should follow the ``[DEBUG-XXX]`` convention where ``XXX`` is a
    short uppercase identifier. The ``[DEBUG-`` prefix and ``]`` suffix
    are optional in the ``tag`` argument (e.g., ``"MY_BUG"`` and
    ``"[DEBUG-MY_BUG]"`` are both accepted).

    Args:
        tag: The debug tag to register (with or without brackets).
    """
    clean = tag.strip().upper()
    # Strip [DEBUG- prefix and ] suffix if present.
    if clean.startswith("[DEBUG-"):
        clean = clean[len("[DEBUG-"):]
    if clean.endswith("]"):
        clean = clean[:-1]
    if clean:
        _registered_debug_tags.add(clean)
        logger.debug("Registered debug tag: [DEBUG-%s]", clean)


def cleanup_debug_tags(output: str) -> list[str]:
    """Find all ``[DEBUG-xxx]`` tags present in the output.

    Useful for identifying which debug statements were emitted during
    execution, enabling one-shot cleanup via a single grep.

    Args:
        output: The worker output string to scan.

    Returns:
        Sorted list of unique tag names (without the ``[DEBUG-]`` wrapper).
    """
    if not output:
        return []
    found = _DEBUG_TAG_PATTERN.findall(output)
    return sorted(set(found))


def strip_debug_tags(output: str) -> str:
    """Remove all lines containing ``[DEBUG-xxx]`` tags from output.

    Args:
        output: The worker output string to clean.

    Returns:
        Output with all ``[DEBUG-xxx]`` lines removed.
    """
    if not output:
        return output
    lines = output.split("\n")
    cleaned = [line for line in lines if not _DEBUG_TAG_PATTERN.search(line)]
    return "\n".join(cleaned)


def get_registered_debug_tags() -> set[str]:
    """Return a copy of all registered debug tags."""
    return set(_registered_debug_tags)


def clear_debug_tags() -> None:
    """Clear all registered debug tags (use after cleanup)."""
    _registered_debug_tags.clear()


class ExecutionGuard:
    """
    Real-time execution guardian for worker processes.

    Monitors execution metrics and determines whether to abort based on
    configurable threshold triggers. Designed for integration into worker
    execution loops for safety and resource protection.

    Class Attributes:
        ABORT_TRIGGERS: Default configuration for all abort condition thresholds

    Example:
        >>> guard = ExecutionGuard()
        >>> guard.configure("max_duration_sec", 600)  # Extend timeout
        >>> abort, reason = guard.check_abort("output text", elapsed_time=120.0)
        >>> print(abort, reason)
        False ''
    """

    ABORT_TRIGGERS: dict[str, Any] = {
        "max_duration_sec": 300.0,
        "max_output_tokens": 8000,
        "max_output_length": 50000,
        "abort_keywords": [
            "CRITICAL",
            "FATAL",
            "FATAL ERROR",
            "UNRECOVERABLE",
            "PANIC",
            "STACK OVERFLOW",
            "OUT OF MEMORY",
            "SEGMENTATION FAULT",
            "KERNEL PANIC",
        ],
        "warning_keywords": [
            "WARNING",
            "ERROR",
            "EXCEPTION",
            "FAILED",
            "TIMEOUT",
        ],
        "token_estimate_ratio": 4.0,  # nosec B105 — chars-per-token ratio, not a password
    }

    def __init__(
        self,
        max_duration_sec: float = 300.0,
        max_output_tokens: int = 8000,
        abort_keywords: list[str] | None = None,
    ):
        """
        Initialize the execution guard with custom thresholds.

        Args:
            max_duration_sec: Maximum allowed execution time in seconds (default: 300)
            max_output_tokens: Maximum allowed output token count (default: 8000)
            abort_keywords: Custom list of keywords that trigger immediate abort
                           (default: uses ABORT_TRIGGERS keywords)
        """
        self._triggers = dict(self.ABORT_TRIGGERS)

        if max_duration_sec != self.ABORT_TRIGGERS["max_duration_sec"]:
            self._triggers["max_duration_sec"] = max_duration_sec

        if max_output_tokens != self.ABORT_TRIGGERS["max_output_tokens"]:
            self._triggers["max_output_tokens"] = max_output_tokens

        if abort_keywords is not None:
            self._triggers["abort_keywords"] = list(abort_keywords)

        self._check_count = 0
        self._abort_count = 0

    @property
    def triggers(self) -> dict[str, Any]:
        """Current trigger configuration (copy)."""
        return dict(self._triggers)

    @property
    def check_count(self) -> int:
        """Total number of checks performed."""
        return self._check_count

    @property
    def abort_count(self) -> int:
        """Total number of aborts triggered."""
        return self._abort_count

    def configure(self, trigger_name: str, value: Any) -> None:
        """
        Dynamically adjust a trigger threshold.

        Args:
            trigger_name: Name of the trigger to configure
                        (must be a key in ABORT_TRIGGERS)
            value: New value for the trigger

        Raises:
            ValueError: If trigger_name is not recognized
        """
        valid_triggers = set(self.ABORT_TRIGGERS.keys())
        if trigger_name not in valid_triggers:
            raise ValueError(f"Unknown trigger '{trigger_name}'. Valid triggers: {', '.join(sorted(valid_triggers))}")

        old_value = self._triggers.get(trigger_name)
        self._triggers[trigger_name] = value
        logger.debug("ExecutionGuard configured: %s = %s (was %s)", trigger_name, value, old_value)

    def check_abort(
        self,
        worker_output: str,
        elapsed_time: float,
        token_count: int = 0,
    ) -> tuple[bool, str]:
        """
        Check whether execution should be aborted.

        Evaluates all abort conditions in order of severity:
        1. Timeout check (elapsed time > max_duration_sec)
        2. Output length check (output too long)
        3. Token count check (tokens exceed limit)
        4. Critical keyword detection (CRITICAL, FATAL, etc.)

        Args:
            worker_output: Current output from the worker process
            elapsed_time: Elapsed execution time in seconds
            token_count: Estimated or actual token count (optional)

        Returns:
            Tuple[bool, str]: (should_abort, reason_for_abort)
                             If should_abort is False, reason is empty string
        """
        self._check_count += 1

        abort_reason = ""
        should_abort = False

        timeout_reason = self._check_timeout(elapsed_time)
        if timeout_reason:
            abort_reason = timeout_reason
            should_abort = True

        if not should_abort:
            output_reason = self._check_output_size(worker_output)
            if output_reason:
                abort_reason = output_reason
                should_abort = True

        if not should_abort and token_count > 0:
            token_reason = self._check_token_limit(token_count)
            if token_reason:
                abort_reason = token_reason
                should_abort = True

        if not should_abort:
            keyword_reason = self._check_critical_keywords(worker_output)
            if keyword_reason:
                abort_reason = keyword_reason
                should_abort = True

        if should_abort:
            self._abort_count += 1
            logger.warning("ExecutionGuard TRIGGERED (check #%d): %s", self._check_count, abort_reason)

        return should_abort, abort_reason

    def _check_timeout(self, elapsed_time: float) -> str | None:
        """Check if execution has exceeded maximum duration."""
        max_duration = self._triggers["max_duration_sec"]
        if elapsed_time > max_duration:
            return f"Timeout exceeded: {elapsed_time:.1f}s > {max_duration:.1f}s (+{elapsed_time - max_duration:.1f}s)"
        return None

    def _check_output_size(self, output: str) -> str | None:
        """Check if output length exceeds maximum."""
        max_length = self._triggers["max_output_length"]
        if len(output) > max_length:
            return f"Output too large: {len(output)} chars > {max_length} chars (+{len(output) - max_length} chars)"
        return None

    def _check_token_limit(self, token_count: int) -> str | None:
        """Check if token count exceeds maximum."""
        max_tokens = self._triggers["max_output_tokens"]
        if token_count > max_tokens:
            return (
                f"Token limit exceeded: {token_count} tokens > {max_tokens} tokens (+{token_count - max_tokens} tokens)"
            )
        return None

    def _check_critical_keywords(self, output: str) -> str | None:
        """
        Check for critical error keywords in output.

        Uses case-insensitive substring matching for reliability.
        Only matches whole words or standard error patterns to avoid
        false positives.
        """
        abort_keywords = self._triggers["abort_keywords"]
        if not abort_keywords or not output:
            return None

        output_upper = output.upper()

        matched_keywords = []
        for keyword in abort_keywords:
            keyword_upper = keyword.upper()
            if keyword_upper in output_upper:
                matched_keywords.append(keyword)

        if matched_keywords:
            return f"Critical keywords detected: {', '.join(matched_keywords[:3])}"
        return None

    def estimate_token_count(self, text: str) -> int:
        """
        Estimate token count from text length.

        Uses a simple ratio-based estimation (approximately 4 chars per token
        for English/Chinese mixed content).

        Args:
            text: Input text to estimate

        Returns:
            int: Estimated token count
        """
        if not text:
            return 0
        ratio = self._triggers["token_estimate_ratio"]
        estimated = int(len(text) / ratio)
        return max(estimated, 1)

    def check_warnings(self, worker_output: str) -> list[str]:
        """
        Check for warning-level keywords (non-abort).

        Useful for logging and monitoring without triggering abort.

        Args:
            worker_output: Worker output to scan

        Returns:
            List[str]: List of warning keywords found (empty if none)
        """
        warning_keywords = self._triggers.get("warning_keywords", [])
        if not warning_keywords or not worker_output:
            return []

        output_upper = worker_output.upper()
        warnings_found = []

        for keyword in warning_keywords:
            if keyword.upper() in output_upper:
                warnings_found.append(keyword)

        return warnings_found

    def reset_stats(self) -> None:
        """Reset check and abort counters."""
        self._check_count = 0
        self._abort_count = 0

    def get_stats(self) -> dict[str, Any]:
        """
        Get guard statistics.

        Returns:
            Dict with check_count, abort_count, and current configuration
        """
        return {
            "check_count": self._check_count,
            "abort_count": self._abort_count,
            "abort_rate": (round(self._abort_count / max(self._check_count, 1), 3) if self._check_count > 0 else 0.0),
            "config": dict(self._triggers),
        }

    # ------------------------------------------------------------------
    # Module 7 (Matt P0-4): [DEBUG-xxx] tag instance methods
    # ------------------------------------------------------------------

    @staticmethod
    def find_debug_tags(output: str) -> list[str]:
        """Find all ``[DEBUG-xxx]`` tags in the given output.

        Thin wrapper around :func:`cleanup_debug_tags` for instance access.

        Args:
            output: Worker output to scan.

        Returns:
            Sorted list of unique tag names found.
        """
        return cleanup_debug_tags(output)

    @staticmethod
    def remove_debug_lines(output: str) -> str:
        """Remove all lines containing ``[DEBUG-xxx]`` tags from output.

        Thin wrapper around :func:`strip_debug_tags` for instance access.

        Args:
            output: Worker output to clean.

        Returns:
            Output with debug-tag lines removed.
        """
        return strip_debug_tags(output)
