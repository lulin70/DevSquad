#!/usr/bin/env python3
"""Failure taxonomy for dispatch results (V4.6.0 P1-b).

Inspired by tester-army/e2e's three-verdict model (passed / failed / blocked,
docs/prd/V4.6.0_e2e-inspired-testing_PRD.md §5): a dispatch failure is either

- ``product_failed``      — the product's own judgment said no (schema
                            violation, empty content, incomplete coverage,
                            consensus rejection, ...), or
- ``environment_blocked`` — a prerequisite outside the product stopped the
                            run (credentials, network, quota, provider 5xx,
                            timeout).

The distinction decides what CI does: a blocked run is retried, a product
failure goes red immediately. Before this taxonomy every failure looked the
same — the V4.5.22 ``test_dispatch_with_openai`` outage cost a full debugging
session to attribute.

Contract clause C19 (DETERMINISTIC_CONTRACT.md): dispatch failures carry a
``failure_class``; ``environment_blocked`` and ``product_failed`` exit the
CLI with 2 and 1 respectively. Both remain non-zero — C9/C10's "incomplete
coverage exits non-zero" promise is untouched.

Classification works from the *error text*: the worker catch sites prefix the
exception type name (``format_worker_error``), so ``APIConnectionError:``,
``RateLimitError:`` and friends are reliably detectable without threading
exception objects through WorkerResult (which carries ``error: str`` by
contract).
"""

from __future__ import annotations

import sys
from enum import Enum
from typing import Any

__all__ = [
    "FailureClass",
    "classify_error_text",
    "dispatch_exit_code",
    "exit_code_for_exception",
    "failure_class_for_dispatch",
    "format_worker_error",
]


class FailureClass(str, Enum):
    """Outcome class of a failed dispatch.

    ``(str, Enum)`` rather than ``StrEnum`` — StrEnum requires Python 3.11+
    and the support matrix is 3.10-3.12 (V4.6.0 P1-a CI lesson).
    """

    NONE = "none"
    PRODUCT_FAILED = "product_failed"
    ENVIRONMENT_BLOCKED = "environment_blocked"


# Substrings (lowercase, matched case-insensitively) that mark an error as
# environment-caused. Checked against ``"<ExceptionTypeName>: <message>"``
# strings — the type-name prefix from format_worker_error makes provider
# exception classes reliably detectable. Ordered by specificity; a single
# match decides.
ENVIRONMENT_ERROR_MARKERS: tuple[str, ...] = (
    # openai / anthropic SDK exception class names (type-name prefix)
    "apiconnectionerror",
    "apitimeouterror",
    "apistatuserror",
    "authenticationerror",
    "permissiondeniederror",
    "ratelimiterror",
    "internalservererror",
    "apiresponsevalidationerror: 5",  # 5xx only; 4xx is product-side config
    # generic transport / infra markers (message text)
    "connection error",
    "connection refused",
    "connection reset",
    "connect timeout",
    "request timed out",
    "timed out",
    "ssl:",
    "sslerror",
    "proxy",
    "getaddrinfo failed",
    "name or service not known",
    "temporary failure in name resolution",
    "rate limit",
    "quota exceeded",
    "insufficient_quota",
    "service unavailable",
    "bad gateway",
    "backend unavailable",
    "host bridge unavailable",
    "credential",
    "api key",
    "unauthorized",
    "forbidden",
    # provider status codes embedded by SDK messages ("Error code: 429 - ...")
    "error code: 401",
    "error code: 403",
    "error code: 407",
    "error code: 429",
    "error code: 500",
    "error code: 502",
    "error code: 503",
    "error code: 504",
)

# Exit codes (C19): 0 success / 1 product failure / 2 environment blocked.
EXIT_SUCCESS = 0
EXIT_PRODUCT_FAILED = 1
EXIT_ENVIRONMENT_BLOCKED = 2


def format_worker_error(exc: BaseException) -> str:
    """Render a caught exception for ``WorkerResult.error``.

    Prefixes the exception type name so classification can rely on provider
    exception classes (``APIConnectionError: ...``) instead of message text
    alone. Catch sites replace ``str(e)`` with this call — no model or
    WorkerResult signature change.
    """
    return f"{type(exc).__name__}: {exc}"


def classify_error_text(error: str | None) -> FailureClass:
    """Classify one error string into the taxonomy.

    Unknown / empty text classifies as ``PRODUCT_FAILED`` — a failure we
    cannot attribute is a product failure until proven otherwise (fail-closed
    attribution: blocked is a *claim about the environment* and must be
    earned by a known marker, never the default).
    """
    if not error:
        return FailureClass.PRODUCT_FAILED
    lowered = error.lower()
    for marker in ENVIRONMENT_ERROR_MARKERS:
        if marker in lowered:
            return FailureClass.ENVIRONMENT_BLOCKED
    return FailureClass.PRODUCT_FAILED


def failure_class_for_dispatch(
    worker_results: list[dict[str, Any]] | None,
    errors: list[str] | None,
) -> FailureClass:
    """Aggregate the failure class of a whole dispatch.

    Rule (PRD §5.2): any environment-classified failure wins — the
    environment is the *cause*; incomplete coverage it produces is the
    *effect*. Everything else that fails is a product failure.
    """
    has_any_failure = False
    for wr in worker_results or []:
        if isinstance(wr, dict) and not wr.get("success", True):
            has_any_failure = True
            if classify_error_text(wr.get("error") or wr.get("error_detail")) is FailureClass.ENVIRONMENT_BLOCKED:
                return FailureClass.ENVIRONMENT_BLOCKED
    for err in errors or []:
        if err:
            has_any_failure = True
            if classify_error_text(err) is FailureClass.ENVIRONMENT_BLOCKED:
                return FailureClass.ENVIRONMENT_BLOCKED
    return FailureClass.PRODUCT_FAILED if has_any_failure else FailureClass.NONE


def dispatch_exit_code(result: Any) -> int:
    """Map a DispatchResult to the C19 CLI exit code.

    0 = success, 1 = product_failed, 2 = environment_blocked. Callers that
    only test ``!= 0`` are unaffected (both failures stay non-zero).
    """
    if getattr(result, "success", False):
        return EXIT_SUCCESS
    details = getattr(result, "details", None) or {}
    failure_class = details.get("failure_class")
    if failure_class == FailureClass.ENVIRONMENT_BLOCKED.value:
        return EXIT_ENVIRONMENT_BLOCKED
    return EXIT_PRODUCT_FAILED


def exit_code_for_exception(exc: BaseException) -> int:
    """Attribute an exception that escaped the dispatch pipeline (C19).

    Pre-dispatch phases (RBAC, role matching) run before any WorkerResult
    exists, so a provider outage there surfaces as a raw exception at the CLI
    boundary instead of a classified DispatchResult. The CLI catch site
    classifies the same way as in-pipeline failures: blocked-type markers
    exit 2, everything else — including unknown exceptions — stays at exit 1
    (fail-closed attribution, never default to blocked).

    Also prints the ``failure_class`` disclosure to stderr so the exit code is
    never silent — a CI reading the log can attribute without re-running.
    """
    failure_class = classify_error_text(format_worker_error(exc))
    print(f"failure_class: {failure_class.value}", file=sys.stderr)
    if failure_class is FailureClass.ENVIRONMENT_BLOCKED:
        return EXIT_ENVIRONMENT_BLOCKED
    return EXIT_PRODUCT_FAILED
