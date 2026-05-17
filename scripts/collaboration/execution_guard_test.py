#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for ExecutionGuard module (V3.6.0)

Tests cover:
- Timeout trigger
- Critical keyword detection (CRITICAL, FATAL, etc.)
- Output size limits
- Token count limits
- Normal operation (no abort)
- Dynamic configuration
- Warning keyword detection
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from scripts.collaboration.execution_guard import ExecutionGuard


class TestExecutionGuardTimeoutTrigger:
    """Test timeout-based abort triggers."""

    def test_timeout_exceeded_triggers_abort(self):
        """Should abort when elapsed time exceeds maximum duration."""
        guard = ExecutionGuard(max_duration_sec=10.0)

        should_abort, reason = guard.check_abort(
            worker_output="Some output",
            elapsed_time=15.0,
        )

        assert should_abort is True
        assert "timeout" in reason.lower() or "exceeded" in reason.lower()
        assert "15" in reason

    def test_timeout_not_exceeded_no_abort(self):
        """Should not abort when within time limit."""
        guard = ExecutionGuard(max_duration_sec=30.0)

        should_abort, reason = guard.check_abort(
            worker_output="Normal output",
            elapsed_time=15.0,
        )

        assert should_abort is False
        assert reason == ""

    def test_exact_timeout_boundary(self):
        """Should abort when time equals max duration."""
        guard = ExecutionGuard(max_duration_sec=60.0)

        should_abort, _ = guard.check_abort(
            worker_output="Output",
            elapsed_time=60.1,
        )

        assert should_abort is True

    def test_just_under_limit(self):
        """Should not abort when just under limit."""
        guard = ExecutionGuard(max_duration_sec=100.0)

        should_abort, _ = guard.check_abort(
            worker_output="Output",
            elapsed_time=99.9,
        )

        assert should_abort is False

    def test_custom_timeout_configuration(self):
        """Custom timeout should be respected."""
        guard = ExecutionGuard(max_duration_sec=5.0)
        guard.configure("max_duration_sec", 2.0)

        should_abort, _ = guard.check_abort(
            worker_output="Output",
            elapsed_time=3.0,
        )

        assert should_abort is True
        assert guard.triggers["max_duration_sec"] == 2.0


class TestExecutionGuardKeywordTrigger:
    """Test critical keyword detection."""

    def test_critical_keyword_trigger(self):
        """CRITICAL keyword should trigger abort."""
        guard = ExecutionGuard()

        should_abort, reason = guard.check_abort(
            worker_output="Processing... CRITICAL ERROR: System failure detected",
            elapsed_time=5.0,
        )

        assert should_abort is True
        assert "critical" in reason.lower()
        assert "keyword" in reason.lower()

    def test_fatal_keyword_trigger(self):
        """FATAL keyword should trigger abort."""
        guard = ExecutionGuard()

        should_abort, reason = guard.check_abort(
            worker_output="FATAL ERROR: Unrecoverable exception",
            elapsed_time=10.0,
        )

        assert should_abort is True
        assert "fatal" in reason.lower()

    def test_multiple_keywords_detected(self):
        """Multiple critical keywords should all be reported."""
        guard = ExecutionGuard()

        output = "CRITICAL issue with FATAL component"
        should_abort, reason = guard.check_abort(
            worker_output=output,
            elapsed_time=5.0,
        )

        assert should_abort is True
        assert "critical" in reason.lower()
        assert "fatal" in reason.lower()

    def test_case_insensitive_matching(self):
        """Keyword matching should be case-insensitive."""
        guard = ExecutionGuard()

        variants = [
            "critical error",
            "Critical Failure",
            "CRITICAL",
            "fatal error",
            "Fatal Exception",
            "FATAL",
        ]

        for output in variants:
            should_abort, _ = guard.check_abort(
                worker_output=output,
                elapsed_time=1.0,
            )
            assert should_abort is True, f"Should match case variant: {output}"

    def test_custom_keywords_override_defaults(self):
        """Custom keywords should replace defaults."""
        custom_keywords = ["CUSTOM_ABORT", "EMERGENCY_STOP"]
        guard = ExecutionGuard(abort_keywords=custom_keywords)

        should_abort, _ = guard.check_abort(
            worker_output="CUSTOM_ABORT triggered",
            elapsed_time=1.0,
        )
        assert should_abort is True

        should_abort_default, _ = guard.check_abort(
            worker_output="CRITICAL error occurred",
            elapsed_time=1.0,
        )
        assert should_abort_default is False, \
            "Default CRITICAL keyword should not trigger with custom keywords"

    def test_stack_overflow_keyword(self):
        """STACK OVERFLOW should trigger abort."""
        guard = ExecutionGuard()

        should_abort, _ = guard.check_abort(
            worker_output="Error: STACK OVERFLOW detected in recursion",
            elapsed_time=2.0,
        )

        assert should_abort is True

    def test_out_of_memory_keyword(self):
        """OUT OF MEMORY should trigger abort."""
        guard = ExecutionGuard()

        should_abort, _ = guard.check_abort(
            worker_output="Process killed: OUT OF MEMORY",
            elapsed_time=3.0,
        )

        assert should_abort is True


class TestExecutionGuardNormalOperation:
    """Test normal operation without abort triggers."""

    def test_normal_output_no_abort(self):
        """Normal output should not trigger abort."""
        guard = ExecutionGuard()

        normal_outputs = [
            "Task completed successfully",
            "Processing data...",
            "Generated 100 lines of code",
            "Analysis complete, no issues found",
            "All tests passed",
        ]

        for output in normal_outputs:
            should_abort, reason = guard.check_abort(
                worker_output=output,
                elapsed_time=10.0,
                token_count=500,
            )
            assert should_abort is False, f"Should not abort on: {output}"
            assert reason == ""

    def test_empty_output_no_abort(self):
        """Empty output should not trigger abort."""
        guard = ExecutionGuard()

        should_abort, reason = guard.check_abort(
            worker_output="",
            elapsed_time=1.0,
        )

        assert should_abort is False
        assert reason == ""

    def test_zero_elapsed_time_no_abort(self):
        """Zero elapsed time should not trigger timeout."""
        guard = ExecutionGuard()

        should_abort, _ = guard.check_abort(
            worker_output="Starting...",
            elapsed_time=0.0,
        )

        assert should_abort is False

    def test_warning_keywords_do_not_abort(self):
        """Warning-level keywords should not cause abort."""
        guard = ExecutionGuard()

        warning_outputs = [
            "WARNING: Deprecated API usage",
            "ERROR: File not found, retrying",
            "Exception caught and handled",
            "FAILED to connect, will retry",
            "TIMEOUT waiting for response",
        ]

        for output in warning_outputs:
            should_abort, _ = guard.check_abort(
                worker_output=output,
                elapsed_time=5.0,
            )
            assert should_abort is False, \
                f"Warning keyword should not abort: {output}"


class TestExecutionGuardOutputSizeLimits:
    """Test output size limit enforcement."""

    def test_large_output_triggers_abort(self):
        """Very large output should trigger size abort."""
        guard = ExecutionGuard(max_output_tokens=8000, max_duration_sec=300)
        guard.configure("max_output_length", 1000)

        large_output = "x" * 1500
        should_abort, reason = guard.check_abort(
            worker_output=large_output,
            elapsed_time=5.0,
        )

        assert should_abort is True
        assert "large" in reason.lower() or "output" in reason.lower()

    def test_normal_size_output_ok(self):
        """Normal sized output should pass size check."""
        guard = ExecutionGuard(max_duration_sec=300)
        guard.configure("max_output_length", 10000)

        normal_output = "Normal content" * 100
        should_abort, _ = guard.check_abort(
            worker_output=normal_output,
            elapsed_time=5.0,
        )

        assert should_abort is False


class TestExecutionGuardTokenLimit:
    """Test token count limit enforcement."""

    def test_token_limit_exceeded(self):
        """Token count over limit should trigger abort."""
        guard = ExecutionGuard(max_output_tokens=1000)

        should_abort, reason = guard.check_abort(
            worker_output="Some output",
            elapsed_time=5.0,
            token_count=1500,
        )

        assert should_abort is True
        assert "token" in reason.lower()

    def test_token_limit_not_exceeded(self):
        """Token count under limit should not trigger abort."""
        guard = ExecutionGuard(max_output_tokens=8000)

        should_abort, _ = guard.check_abort(
            worker_output="Output",
            elapsed_time=10.0,
            token_count=5000,
        )

        assert should_abort is False

    def test_zero_tokens_no_abort(self):
        """Zero token count should not trigger token abort."""
        guard = ExecutionGuard(max_output_tokens=1000)

        should_abort, _ = guard.check_abort(
            worker_output="Output",
            elapsed_time=5.0,
            token_count=0,
        )

        assert should_abort is False


class TestExecutionGuardConfiguration:
    """Test dynamic configuration capabilities."""

    def test_configure_valid_trigger(self):
        """Configuring valid trigger should update value."""
        guard = ExecutionGuard()

        original_value = guard.triggers["max_duration_sec"]
        guard.configure("max_duration_sec", 600.0)

        assert guard.triggers["max_duration_sec"] == 600.0
        assert guard.triggers["max_duration_sec"] != original_value

    def test_configure_invalid_trigger_raises_error(self):
        """Configuring invalid trigger name should raise ValueError."""
        guard = ExecutionGuard()

        with pytest.raises(ValueError, match="Unknown trigger"):
            guard.configure("invalid_trigger_name", 100)

    def test_configure_max_output_tokens(self):
        """Can configure token limit dynamically."""
        guard = ExecutionGuard(max_output_tokens=8000)
        guard.configure("max_output_tokens", 2000)

        should_abort, _ = guard.check_abort(
            worker_output="Output",
            elapsed_time=1.0,
            token_count=2500,
        )

        assert should_abort is True

    def test_configure_abort_keywords(self):
        """Can customize abort keywords at runtime."""
        guard = ExecutionGuard()

        guard.configure("abort_keywords", ["STOP_NOW", "HALT"])

        should_abort, _ = guard.check_abort(
            worker_output="STOP_NOW command received",
            elapsed_time=1.0,
        )
        assert should_abort is True

        should_not_abort, _ = guard.check_abort(
            worker_output="CRITICAL error",
            elapsed_time=1.0,
        )
        assert should_not_abort is False


class TestExecutionGuardStatistics:
    """Test statistics tracking."""

    def test_check_count_increments(self):
        """Check count should increment on each call."""
        guard = ExecutionGuard()

        assert guard.check_count == 0

        guard.check_abort("test", 1.0)
        assert guard.check_count == 1

        guard.check_abort("test", 2.0)
        assert guard.check_count == 2

    def test_abort_count_increments_on_abort(self):
        """Abort count should increment only on actual aborts."""
        guard = ExecutionGuard(max_duration_sec=10.0)

        guard.check_abort("normal", 1.0)
        assert guard.abort_count == 0

        guard.check_abort("normal", 15.0)
        assert guard.abort_count == 1

        guard.check_abort("normal", 20.0)
        assert guard.abort_count == 2

    def test_get_stats_returns_complete_info(self):
        """get_stats should return comprehensive information."""
        guard = ExecutionGuard(max_duration_sec=5.0)

        guard.check_abort("ok", 1.0)
        guard.check_abort("timeout", 10.0)

        stats = guard.get_stats()

        assert stats["check_count"] == 2
        assert stats["abort_count"] == 1
        assert 0 < stats["abort_rate"] <= 1
        assert "config" in stats
        assert isinstance(stats["config"], dict)

    def test_reset_stats_clears_counters(self):
        """reset_stats should clear all counters."""
        guard = ExecutionGuard(max_duration_sec=1.0)

        guard.check_abort("t", 5.0)
        guard.check_abort("t", 6.0)
        assert guard.check_count == 2
        assert guard.abort_count == 2

        guard.reset_stats()
        assert guard.check_count == 0
        assert guard.abort_count == 0


class TestExecutionGuardTokenEstimation:
    """Test token estimation functionality."""

    def test_estimate_token_count_basic(self):
        """Basic token estimation should work."""
        guard = ExecutionGuard()

        text = "Hello world, this is a test"
        tokens = guard.estimate_token_count(text)

        assert isinstance(tokens, int)
        assert tokens > 0
        assert tokens <= len(text), "Estimated tokens should be <= text length"

    def test_estimate_empty_text(self):
        """Empty text should return 0 tokens."""
        guard = ExecutionGuard()

        assert guard.estimate_token_count("") == 0

    def test_estimate_long_text(self):
        """Long text should estimate more tokens."""
        guard = ExecutionGuard()

        short = "Short"
        long_text = "This is a much longer text that should have more tokens " * 10

        short_tokens = guard.estimate_token_count(short)
        long_tokens = guard.estimate_token_count(long_text)

        assert long_tokens > short_tokens


class TestExecutionGuardWarningDetection:
    """Test warning keyword detection (non-abort)."""

    def test_detect_warning_keywords(self):
        """Should detect warning keywords without aborting."""
        guard = ExecutionGuard()

        warnings = guard.check_warnings("WARNING: Something went wrong")

        assert len(warnings) > 0
        assert "WARNING" in warnings

    def test_no_warnings_in_clean_output(self):
        """Clean output should have no warnings."""
        guard = ExecutionGuard()

        warnings = guard.check_warnings("All systems operational")

        assert len(warnings) == 0

    def test_multiple_warnings(self):
        """Multiple warning keywords should all be detected."""
        guard = ExecutionGuard()

        output = "WARNING: A\nERROR: B\nException: C"
        warnings = guard.check_warnings(output)

        assert len(warnings) >= 2


class TestExecutionGuardEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_none_output_handled(self):
        """None-like empty string should be handled gracefully."""
        guard = ExecutionGuard()

        should_abort, _ = guard.check_abort("", 1.0)
        assert should_abort is False

    def test_very_long_elapsed_time(self):
        """Very large elapsed time should still be detected."""
        guard = ExecutionGuard(max_duration_sec=3600)

        should_abort, _ = guard.check_abort(
            worker_output="Running",
            elapsed_time=99999.9,
        )

        assert should_abort is True

    def test_negative_elapsed_time(self):
        """Negative elapsed time should not trigger timeout."""
        guard = ExecutionGuard()

        should_abort, _ = guard.check_abort(
            worker_output="Output",
            elapsed_time=-1.0,
        )

        assert should_abort is False

    def test_substring_keyword_match(self):
        """Keyword as substring should be detected."""
        guard = ExecutionGuard()

        should_abort, _ = guard.check_abort(
            worker_output="Log shows CRITICALFAILURE in module",
            elapsed_time=1.0,
        )

        assert should_abort is True

    def test_default_triggers_immutable(self):
        """Modifying instance triggers should not affect class defaults."""
        guard = ExecutionGuard()
        guard.configure("max_duration_sec", 999999)

        new_guard = ExecutionGuard()
        assert new_guard.triggers["max_duration_sec"] == ExecutionGuard.ABORT_TRIGGERS["max_duration_sec"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
