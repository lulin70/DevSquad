#!/usr/bin/env python3
"""Unit tests for failure_taxonomy (V4.6.0 P1-b, contract C19).

Covers the PRD §7.1 matrix: exception/message mapping table, aggregation
precedence (any blocked failure wins), fail-closed attribution (unknown
text is product_failed, never blocked), and the C19 exit-code mapping.
"""

from __future__ import annotations

import pytest

from scripts.collaboration.failure_taxonomy import (
    EXIT_ENVIRONMENT_BLOCKED,
    EXIT_PRODUCT_FAILED,
    EXIT_SUCCESS,
    FailureClass,
    classify_error_text,
    dispatch_exit_code,
    exit_code_for_exception,
    failure_class_for_dispatch,
    format_worker_error,
)

# ── format_worker_error: type-name prefix ──


class TestFormatWorkerError:
    def test_prefixes_exception_type_name(self):
        text = format_worker_error(RuntimeError("boom"))
        assert text == "RuntimeError: boom"

    def test_provider_exception_class_is_detectable(self):
        class APIConnectionError(Exception): ...

        text = format_worker_error(APIConnectionError("Connection error."))
        assert "APIConnectionError" in text
        assert classify_error_text(text) is FailureClass.ENVIRONMENT_BLOCKED


# ── classify_error_text: mapping table ──


class TestClassifyErrorText:
    @pytest.mark.parametrize(
        ("error_text", "expected"),
        [
            # provider SDK exception classes (type-name prefix from the catch sites)
            ("APIConnectionError: Connection error.", FailureClass.ENVIRONMENT_BLOCKED),
            ("APITimeoutError: Request timed out.", FailureClass.ENVIRONMENT_BLOCKED),
            ("APIStatusError: Error code: 429 - rate limited", FailureClass.ENVIRONMENT_BLOCKED),
            ("AuthenticationError: Error code: 401 - invalid key", FailureClass.ENVIRONMENT_BLOCKED),
            ("RateLimitError: quota exceeded", FailureClass.ENVIRONMENT_BLOCKED),
            ("InternalServerError: Error code: 503", FailureClass.ENVIRONMENT_BLOCKED),
            # transport / infra message text
            ("ConnectionError: connection refused", FailureClass.ENVIRONMENT_BLOCKED),
            ("OSError: getaddrinfo failed", FailureClass.ENVIRONMENT_BLOCKED),
            ("HTTPException: service unavailable", FailureClass.ENVIRONMENT_BLOCKED),
            # product-side failures — must NOT be blocked
            ("ValueError: schema violation: missing 'summary'", FailureClass.PRODUCT_FAILED),
            ("EmptyContentError: content was empty (fail-closed)", FailureClass.PRODUCT_FAILED),
            ("ConsensusGateError: consensus rejected the plan", FailureClass.PRODUCT_FAILED),
            ("CoverageError: 0 of 1 requested roles returned", FailureClass.PRODUCT_FAILED),
            # fail-closed attribution: unknown text is product_failed
            ("WeirdUnknownError: something inexplicable", FailureClass.PRODUCT_FAILED),
            ("", FailureClass.PRODUCT_FAILED),
            (None, FailureClass.PRODUCT_FAILED),
            # trap: "429" inside an unrelated product error must not match on
            # its own — the marker is the full "error code: 429" phrase
            ("SchemaError: expected 429 fields, got 3", FailureClass.PRODUCT_FAILED),
        ],
    )
    def test_mapping_table(self, error_text: str | None, expected: FailureClass):
        assert classify_error_text(error_text) is expected

    def test_case_insensitive(self):
        assert classify_error_text("APICONNECTIONERROR: down") is FailureClass.ENVIRONMENT_BLOCKED


# ── aggregation precedence ──


class TestFailureClassForDispatch:
    def test_no_failures_is_none(self):
        workers = [{"success": True}, {"success": True}]
        assert failure_class_for_dispatch(workers, []) is FailureClass.NONE

    def test_product_failure_only(self):
        workers = [{"success": False, "error": "ValueError: bad schema"}]
        assert failure_class_for_dispatch(workers, []) is FailureClass.PRODUCT_FAILED

    def test_blocked_failure_wins_over_product(self):
        # The environment is the cause; the product-side coverage gap it
        # produces is the effect.
        workers = [
            {"success": False, "error": "ValueError: bad schema"},
            {"success": False, "error": "APIConnectionError: connection error."},
        ]
        assert failure_class_for_dispatch(workers, []) is FailureClass.ENVIRONMENT_BLOCKED

    def test_errors_list_considered(self):
        assert failure_class_for_dispatch([], ["RateLimitError: 429"]) is FailureClass.ENVIRONMENT_BLOCKED
        assert failure_class_for_dispatch([], ["ValueError: bad"]) is FailureClass.PRODUCT_FAILED

    def test_failed_worker_with_empty_error_is_product(self):
        workers = [{"success": False, "error": ""}]
        assert failure_class_for_dispatch(workers, []) is FailureClass.PRODUCT_FAILED


# ── C19 exit-code mapping ──


class _FakeResult:
    def __init__(self, success: bool, failure_class: str | None = None):
        self.success = success
        self.details = {"failure_class": failure_class} if failure_class else {}


class TestDispatchExitCode:
    def test_success_is_zero(self):
        assert dispatch_exit_code(_FakeResult(True)) == EXIT_SUCCESS

    def test_product_failed_is_one(self):
        assert dispatch_exit_code(_FakeResult(False, "product_failed")) == EXIT_PRODUCT_FAILED

    def test_environment_blocked_is_two(self):
        assert dispatch_exit_code(_FakeResult(False, "environment_blocked")) == EXIT_ENVIRONMENT_BLOCKED

    def test_failure_without_class_is_one(self):
        # Backward compat: a failed result with no failure_class details
        # (e.g. built by an older path) must still exit 1, never 0.
        assert dispatch_exit_code(_FakeResult(False)) == EXIT_PRODUCT_FAILED


class TestExitCodeForException:
    """Exceptions escaping the pipeline (pre-dispatch) are still attributed."""

    def test_provider_connection_error_exits_two(self):
        # The J3 blocked journey: APIConnectionError raised by pre-dispatch
        # role matching before any worker exists. Classification is
        # text-based, so a same-named local stub stands in for the provider
        # SDK class (openai is not installed in every CI env).
        class APIConnectionError(Exception):
            pass

        assert exit_code_for_exception(APIConnectionError("Connection error.")) == EXIT_ENVIRONMENT_BLOCKED

    def test_unknown_exception_exits_one(self):
        # Fail-closed: an exception with no environment marker is a product
        # failure — blocked is never the default.
        assert exit_code_for_exception(RuntimeError("schema violation: expected 429 fields")) == EXIT_PRODUCT_FAILED

    def test_env_text_in_message_exits_two(self):
        assert exit_code_for_exception(RuntimeError("Connection refused while contacting provider")) == (
            EXIT_ENVIRONMENT_BLOCKED
        )
