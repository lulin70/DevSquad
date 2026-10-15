#!/usr/bin/env python3
"""Integration tests: host-adapter exit codes (V4.7.0 TD-002, contract C19).

Before TD-002 the ``--host`` adapter branch returned a flat 0/1, so a host
dispatch blocked by the environment (host bridge unavailable, provider
connection refused) exited 1 — indistinguishable from a product failure.
These tests pin the fix through the real production path:

- ``_print_host_result`` attributes failures through the failure taxonomy:
  ``environment_blocked`` exits 2 with the stderr disclosure, product
  failures exit 1, success exits 0.
- The adapter-level fallback (no ``raw_result``) classifies the error text
  fail-closed — unknown stays ``product_failed``.
- ``MultiHostAdapter.dispatch`` carries the pipeline's ``raw_result`` so
  the taxonomy class survives the adapter boundary.
"""

from __future__ import annotations

import argparse
import io
import json
from contextlib import redirect_stderr, redirect_stdout
from typing import Any

from scripts.cli_dispatch import _print_host_result
from scripts.collaboration.dispatch_models import DispatchResult
from scripts.collaboration.dispatcher import MultiAgentDispatcher
from scripts.collaboration.failure_taxonomy import (
    EXIT_ENVIRONMENT_BLOCKED,
    EXIT_PRODUCT_FAILED,
    EXIT_SUCCESS,
)
from scripts.collaboration.multi_host_adapter import HostType, MultiHostAdapter


class _ExplodingBackend:
    """Real-looking backend that fails with a provider exception type."""

    def __init__(self, exc: Exception) -> None:
        self.exc = exc
        self.model = "host-exit-fake-model"

    def is_available(self) -> bool:
        return True

    def generate(self, prompt: str, **kwargs: Any) -> str:
        raise self.exc

    def generate_stream(self, prompt: str, **kwargs: Any):
        raise self.exc


class _OkBackend:
    model = "host-exit-fake-model"

    def is_available(self) -> bool:
        return True

    def generate(self, prompt: str, **kwargs: Any) -> str:
        return "Structured answer: 4"

    def generate_stream(self, prompt: str, **kwargs: Any):
        yield "Structured answer: 4"


def _make_args(fmt: str = "markdown") -> argparse.Namespace:
    return argparse.Namespace(format=fmt)


def _make_host_result(
    *,
    success: bool,
    failure_class: str | None = None,
    with_raw: bool = True,
    error: str | None = None,
) -> dict[str, Any]:
    raw = None
    if with_raw:
        raw = DispatchResult(
            success=success,
            task_description="TD-002 host exit probe",
            details={"failure_class": failure_class} if failure_class else {},
        )
    return {
        "host": "trae",
        "report": "host report body",
        "success": success,
        "roles": ["architect"],
        "raw_result": raw,
        **({"error": error} if error is not None else {}),
    }


def _run_print(host_result: dict[str, Any], fmt: str = "markdown") -> tuple[int, str, str]:
    """Call _print_host_result capturing (exit_code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = _print_host_result(_make_args(fmt), host_result)
    return code, out.getvalue(), err.getvalue()


# --- A. taxonomy attribution through _print_host_result ----------------------


def test_a1_success_exits_0_without_disclosure():
    host_result = _make_host_result(success=True, failure_class="none")
    code, _, err = _run_print(host_result)
    assert code == EXIT_SUCCESS
    assert "failure_class" not in err


def test_a2_product_failure_exits_1():
    host_result = _make_host_result(success=False, failure_class="product_failed")
    code, _, err = _run_print(host_result)
    assert code == EXIT_PRODUCT_FAILED
    assert "environment_blocked" not in err


def test_a3_environment_blocked_exits_2_with_stderr_disclosure():
    host_result = _make_host_result(success=False, failure_class="environment_blocked")
    code, _, err = _run_print(host_result)
    assert code == EXIT_ENVIRONMENT_BLOCKED
    assert "failure_class: environment_blocked" in err


def test_a4_adapter_level_blocked_error_text_exits_2():
    # No raw_result: the adapter-level fallback must classify the error text.
    host_result = _make_host_result(success=False, with_raw=False, error="host bridge unavailable: no marker file")
    code, _, err = _run_print(host_result)
    assert code == EXIT_ENVIRONMENT_BLOCKED
    assert "failure_class: environment_blocked" in err


def test_a5_adapter_level_unknown_error_stays_product_failed():
    # Fail-closed: an unclassifiable adapter error must NOT exit 2.
    host_result = _make_host_result(success=False, with_raw=False, error="schema assembly exploded")
    code, _, err = _run_print(host_result)
    assert code == EXIT_PRODUCT_FAILED
    assert "environment_blocked" not in err


def test_a6_json_format_output_stays_valid_json_and_exit_2():
    host_result = _make_host_result(success=False, failure_class="environment_blocked")
    code, out, err = _run_print(host_result, fmt="json")
    assert code == EXIT_ENVIRONMENT_BLOCKED
    assert "failure_class: environment_blocked" in err
    payload = json.loads(out)
    assert payload["success"] is False
    assert payload["host"] == "trae"


# --- B. real dispatcher -> MultiHostAdapter -> _print_host_result ------------


def _dispatch_via_adapter(backend: Any) -> tuple[int, dict[str, Any]]:
    disp = MultiAgentDispatcher(llm_backend=backend, enable_memory=False)
    try:
        adapter = MultiHostAdapter(host_type=HostType.TRAE, dispatcher=disp)
        host_result = adapter.dispatch("TD-002 adapter journey", roles=["architect"])
    finally:
        disp.shutdown()
    code, _, _ = _run_print(host_result)
    return code, host_result


def test_b1_blocked_backend_through_adapter_exits_2():
    backend = _ExplodingBackend(ConnectionError("connection refused"))
    code, host_result = _dispatch_via_adapter(backend)
    assert code == EXIT_ENVIRONMENT_BLOCKED
    assert host_result["raw_result"].details.get("failure_class") == "environment_blocked"


def test_b2_product_failure_through_adapter_exits_1():
    backend = _ExplodingBackend(RuntimeError("schema assembly exploded"))
    code, host_result = _dispatch_via_adapter(backend)
    assert code == EXIT_PRODUCT_FAILED
    assert host_result["raw_result"].details.get("failure_class") == "product_failed"


def test_b3_success_through_adapter_exits_0():
    code, host_result = _dispatch_via_adapter(_OkBackend())
    assert code == EXIT_SUCCESS
    assert host_result["success"] is True


def test_b4_blocked_backend_stderr_disclosure_through_adapter():
    # Full chain: real dispatcher -> adapter -> _print_host_result must
    # surface the C19 stderr disclosure, not just the exit code.
    backend = _ExplodingBackend(ConnectionError("connection refused"))
    disp = MultiAgentDispatcher(llm_backend=backend, enable_memory=False)
    try:
        adapter = MultiHostAdapter(host_type=HostType.TRAE, dispatcher=disp)
        host_result = adapter.dispatch("stderr disclosure probe", roles=["architect"])
    finally:
        disp.shutdown()
    code, _, err = _run_print(host_result)
    assert code == EXIT_ENVIRONMENT_BLOCKED
    assert "failure_class: environment_blocked" in err


# --- C. adapter boundary contract ---------------------------------------------


def test_c1_adapter_result_dict_carries_raw_result():
    disp = MultiAgentDispatcher(llm_backend=_OkBackend(), enable_memory=False)
    try:
        adapter = MultiHostAdapter(host_type=HostType.TRAE, dispatcher=disp)
        host_result = adapter.dispatch("raw_result contract probe", roles=["architect"])
    finally:
        disp.shutdown()
    # The taxonomy class must survive the adapter boundary.
    assert isinstance(host_result["raw_result"], DispatchResult)
    assert host_result["raw_result"].details.get("failure_class") == "none"


def test_c2_adapter_report_renders_blocked_banner():
    disp = MultiAgentDispatcher(
        llm_backend=_ExplodingBackend(ConnectionError("connection refused")), enable_memory=False
    )
    try:
        adapter = MultiHostAdapter(host_type=HostType.TRAE, dispatcher=disp)
        host_result = adapter.dispatch("blocked banner probe", roles=["architect"])
    finally:
        disp.shutdown()
    assert "environment_blocked" in host_result["report"]


def test_c3_adapter_success_report_has_no_failure_section():
    disp = MultiAgentDispatcher(llm_backend=_OkBackend(), enable_memory=False)
    try:
        adapter = MultiHostAdapter(host_type=HostType.TRAE, dispatcher=disp)
        host_result = adapter.dispatch("clean report probe", roles=["architect"])
    finally:
        disp.shutdown()
    assert host_result["success"] is True
    assert "Failure class" not in host_result["report"]
