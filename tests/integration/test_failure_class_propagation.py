#!/usr/bin/env python3
"""Integration tests: failure_class propagation (V4.6.0 P1-b, contract C19).

Verifies the taxonomy through the production dispatch path:

- A blocked backend (connection error) produces
  ``details["failure_class"] == "environment_blocked"``, the Markdown report
  renders the blocked banner, and the C19 exit code is 2.
- A product-side worker failure produces ``product_failed`` and exit code 1.
- Successful dispatches carry ``failure_class == "none"`` and render no
  failure-class section.
"""

from __future__ import annotations

from typing import Any

import pytest

from scripts.collaboration.dispatcher import MultiAgentDispatcher
from scripts.collaboration.failure_taxonomy import (
    EXIT_ENVIRONMENT_BLOCKED,
    EXIT_PRODUCT_FAILED,
    dispatch_exit_code,
)


class _ExplodingBackend:
    """Real-looking backend that fails with a provider exception type."""

    def __init__(self, exc: Exception) -> None:
        self.exc = exc
        self.model = "taxonomy-fake-model"

    def is_available(self) -> bool:
        return True

    def generate(self, prompt: str, **kwargs: Any) -> str:
        raise self.exc

    def generate_stream(self, prompt: str, **kwargs: Any):
        raise self.exc


@pytest.mark.parametrize(
    ("exc", "expected_class", "expected_exit"),
    [
        (ConnectionError("connection refused"), "environment_blocked", EXIT_ENVIRONMENT_BLOCKED),
        (ConnectionResetError("connection reset by peer"), "environment_blocked", EXIT_ENVIRONMENT_BLOCKED),
        (RuntimeError("schema assembly exploded"), "product_failed", EXIT_PRODUCT_FAILED),
        (ValueError("bad output structure"), "product_failed", EXIT_PRODUCT_FAILED),
    ],
)
def test_failure_class_propagates_and_exit_code(exc: Exception, expected_class: str, expected_exit: int):
    backend = _ExplodingBackend(exc)
    disp = MultiAgentDispatcher(llm_backend=backend, enable_memory=False)
    try:
        result = disp.dispatch("Taxonomy propagation probe", roles=["architect"])
    finally:
        disp.shutdown()

    assert not result.success, "the exploding backend must fail the dispatch"
    assert result.details.get("failure_class") == expected_class
    assert dispatch_exit_code(result) == expected_exit

    if expected_class == "environment_blocked":
        assert "environment_blocked" in result.to_markdown()
    else:
        assert "product_failed" in result.to_markdown()


def test_successful_dispatch_has_none_class_and_no_section():
    class _OkBackend:
        model = "taxonomy-fake-model"

        def is_available(self) -> bool:
            return True

        def generate(self, prompt: str, **kwargs: Any) -> str:
            return "Structured answer: 4"

        def generate_stream(self, prompt: str, **kwargs: Any):
            yield "Structured answer: 4"

    disp = MultiAgentDispatcher(llm_backend=_OkBackend(), enable_memory=False)
    try:
        result = disp.dispatch("What is 2+2?", roles=["architect"])
    finally:
        disp.shutdown()

    assert result.success
    assert result.details.get("failure_class") == "none"
    assert "Failure class" not in result.to_markdown()


def test_review_gate_failure_recomputes_failure_class(monkeypatch: pytest.MonkeyPatch):
    """V4.9.0 P2-W2 Step 24: terminal recompute of failure_class.

    The assembler writes details["failure_class"] at Step-17 assembly time
    ("none" for an all-success worker run); the Step-21 review gate then
    appends errors and flips success=False. Before W2 the disclosure stayed
    "none" on a failed run — the terminal recompute must disclose
    product_failed (review blocking text carries no environment markers).
    """
    from scripts.collaboration.two_stage_review_gate import (
        ReviewFinding,
        ReviewStage,
        StageResult,
        TwoStageReviewResult,
    )

    blocking = ReviewFinding(
        stage=ReviewStage.CODE_QUALITY,
        severity="critical",
        category="BREAK-1",
        description="route without handler",
        file_path="api/routes.py",
        line_range="7",
        suggestion="Add a handler.",
    )
    gate_result = TwoStageReviewResult(
        stage1_result=StageResult.FAIL,
        overall_passed=False,
        findings=[blocking],
        blocking_findings=[blocking],
        summary="blocked",
    )

    class _OkBackend:
        model = "taxonomy-fake-model"

        def is_available(self) -> bool:
            return True

        def generate(self, prompt: str, **kwargs: Any) -> str:
            return "Structured answer: 4"

        def generate_stream(self, prompt: str, **kwargs: Any):
            yield "Structured answer: 4"

    disp = MultiAgentDispatcher(llm_backend=_OkBackend(), enable_memory=False)
    monkeypatch.setattr(disp.post_dispatch, "_run_two_stage_review", lambda *_args, **_kwargs: gate_result)
    try:
        result = disp.dispatch("What is 2+2?", roles=["architect"])
    finally:
        disp.shutdown()

    assert not result.success
    assert result.details.get("failure_class") == "product_failed"
    assert dispatch_exit_code(result) == EXIT_PRODUCT_FAILED
    assert "product_failed" in result.to_markdown()


def test_audit_end_event_carries_terminal_signals():
    """V4.9.0 P2-W2: dispatcher.py:578 wiring — the audit dispatch_end
    event carries the run's terminal signals (findings + failure_class)
    so cross-run defect filing resolves against real runs."""
    from scripts.collaboration.dispatch_audit import DispatchAuditLogger

    audit = DispatchAuditLogger()
    disp = MultiAgentDispatcher(audit_logger=audit, enable_memory=False)
    try:
        result = disp.dispatch("What is 2+2?", roles=["architect"])
    finally:
        disp.shutdown()

    assert result.details["failure_class"] == "none"
    ends = audit.query(event_type="dispatch_end")
    assert len(ends) == 1
    details = ends[0].details
    assert details["failure_class"] == "none"
    assert isinstance(details.get("findings"), list)
    assert audit.verify_chain()
