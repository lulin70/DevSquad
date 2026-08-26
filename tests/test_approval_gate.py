"""Unit tests for ApprovalGate (V4.5.1).

12 tests covering the 7-dimension Iron Rules:
1.  test_auto_approve_when_callback_none — Happy (backward compat)
2.  test_user_callback_approve — Happy (callback approves)
3.  test_user_callback_deny — Happy (callback denies)
4.  test_callback_exception_fail_closed — Error (callback raises → deny)
5.  test_call_counter_increments_on_request_approval — Anti-Ghost
6.  test_call_counter_increments_on_get_records — Anti-Ghost
7.  test_call_counter_increments_on_export_markdown — Anti-Ghost
8.  test_get_call_count_returns_module_counter — Anti-Ghost
9.  test_export_markdown_empty_when_no_records — Boundary
10. test_export_markdown_non_empty_when_records — Happy
11. test_approval_request_dataclass_fields — Happy (dataclass shape)
12. test_approval_result_dataclass_fields_and_to_dict — Happy (dataclass shape)
13. test_dispatch_with_callback_populates_records_and_md — Integration
14. test_dispatch_without_callback_backward_compat — Integration (auto-approve)
15. test_dispatch_to_markdown_contains_approval_gate_section — Integration
16. test_dispatch_to_dict_contains_approval_records_key — Integration

Uses REAL components (MultiAgentDispatcher with default mock backend),
not Mock — per V4.4.4/V4.5.1 implementation rules.
"""

from __future__ import annotations

import os
import sys

import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scripts.collaboration import approval_gate as approval_gate_module  # noqa: E402
from scripts.collaboration.approval_gate import (  # noqa: E402
    ApprovalGate,
    ApprovalRequest,
    ApprovalResult,
    get_call_count,
)
from scripts.collaboration.dispatcher import MultiAgentDispatcher  # noqa: E402

pytestmark = [pytest.mark.unit]


@pytest.fixture
def dispatcher() -> MultiAgentDispatcher:
    """Create a real MultiAgentDispatcher with default mock backend."""
    return MultiAgentDispatcher()


# ---------------------------------------------------------------------------
# 1. ApprovalGate auto-approve when callback is None (backward compat)
# ---------------------------------------------------------------------------


def test_auto_approve_when_callback_none() -> None:
    """Happy: callback=None → auto-approve with backward-compat reason."""
    gate = ApprovalGate()
    result = gate.request_approval("write_file", "Write output.py")

    assert result.approved is True, "auto-approve must return approved=True"
    assert "auto" in result.reason.lower(), (
        f"reason should mention auto-approve, got: {result.reason!r}"
    )
    # A record must still be collected even when auto-approving.
    records = gate.get_records()
    assert len(records) == 1, f"expected 1 record, got {len(records)}"
    assert records[0]["approved"] is True
    assert records[0]["operation_type"] == "write_file"


# ---------------------------------------------------------------------------
# 2. ApprovalGate user callback approve/deny
# ---------------------------------------------------------------------------


def test_user_callback_approve() -> None:
    """Happy: user callback returns approved=True → gate records approval."""

    def cb(request: ApprovalRequest) -> ApprovalResult:
        assert request.operation_type == "create_pr"
        assert request.description == "Open PR #42"
        return ApprovalResult(approved=True, reason="LGTM")

    gate = ApprovalGate(approval_callback=cb)
    result = gate.request_approval("create_pr", "Open PR #42", details={"branch": "feat"})

    assert result.approved is True
    assert result.reason == "LGTM"
    records = gate.get_records()
    assert len(records) == 1
    assert records[0]["approved"] is True
    assert records[0]["reason"] == "LGTM"
    assert records[0]["details"] == {"branch": "feat"}


def test_user_callback_deny() -> None:
    """Happy: user callback returns approved=False → gate records denial."""

    def cb(request: ApprovalRequest) -> ApprovalResult:
        return ApprovalResult(approved=False, reason="Secrets detected in diff")

    gate = ApprovalGate(approval_callback=cb)
    result = gate.request_approval("create_pr", "Open PR with secrets")

    assert result.approved is False
    assert "secrets" in result.reason.lower()
    records = gate.get_records()
    assert len(records) == 1
    assert records[0]["approved"] is False
    assert records[0]["reason"] == "Secrets detected in diff"


# ---------------------------------------------------------------------------
# 3. ApprovalGate callback exception → fail-closed deny
# ---------------------------------------------------------------------------


def test_callback_exception_fail_closed() -> None:
    """Error: callback raises → gate fail-closes to deny."""

    def cb(request: ApprovalRequest) -> ApprovalResult:
        raise RuntimeError("UI crashed")

    gate = ApprovalGate(approval_callback=cb)
    result = gate.request_approval("send_message", "Post to #prod-alerts")

    assert result.approved is False, "callback exception must fail-closed to deny"
    assert "error" in result.reason.lower() or "callback" in result.reason.lower(), (
        f"reason should mention the callback error, got: {result.reason!r}"
    )
    assert "UI crashed" in result.reason, "reason should contain the exception message"
    records = gate.get_records()
    assert len(records) == 1
    assert records[0]["approved"] is False


# ---------------------------------------------------------------------------
# 4. _call_counter_er anti-ghost: increments on every public method call
# ---------------------------------------------------------------------------


def test_call_counter_increments_on_request_approval() -> None:
    """Anti-Ghost: _call_counter_er increments on request_approval()."""
    before = approval_gate_module._call_counter_er
    gate = ApprovalGate()
    gate.request_approval("write_file", "anti-ghost probe")
    after = approval_gate_module._call_counter_er
    assert after > before, (
        f"_call_counter_er did not increment on request_approval: "
        f"before={before}, after={after}"
    )


def test_call_counter_increments_on_get_records() -> None:
    """Anti-Ghost: _call_counter_er increments on get_records()."""
    gate = ApprovalGate()
    before = approval_gate_module._call_counter_er
    gate.get_records()
    after = approval_gate_module._call_counter_er
    assert after > before, (
        f"_call_counter_er did not increment on get_records: "
        f"before={before}, after={after}"
    )


def test_call_counter_increments_on_export_markdown() -> None:
    """Anti-Ghost: _call_counter_er increments on export_markdown()."""
    gate = ApprovalGate()
    before = approval_gate_module._call_counter_er
    gate.export_markdown()
    after = approval_gate_module._call_counter_er
    assert after > before, (
        f"_call_counter_er did not increment on export_markdown: "
        f"before={before}, after={after}"
    )


# ---------------------------------------------------------------------------
# 5. get_call_count() returns the module-level counter
# ---------------------------------------------------------------------------


def test_get_call_count_returns_module_counter() -> None:
    """Anti-Ghost: get_call_count() mirrors approval_gate_module._call_counter_er."""
    # Touch the module to bump the counter deterministically.
    gate = ApprovalGate()
    gate.request_approval("write_file", "probe for get_call_count")
    module_value = approval_gate_module._call_counter_er
    assert get_call_count() == module_value, (
        f"get_call_count()={get_call_count()} != _call_counter_er={module_value}"
    )


# ---------------------------------------------------------------------------
# 6. export_markdown() returns empty string when no records, non-empty when records exist
# ---------------------------------------------------------------------------


def test_export_markdown_empty_when_no_records() -> None:
    """Boundary: no records → export_markdown() returns empty string."""
    gate = ApprovalGate()
    md = gate.export_markdown()
    assert md == "", f"expected empty string when no records, got: {md!r}"


def test_export_markdown_non_empty_when_records() -> None:
    """Happy: records exist → export_markdown() returns non-empty markdown."""
    gate = ApprovalGate()
    gate.request_approval("write_file", "Write report.md")
    md = gate.export_markdown()
    assert md != "", "expected non-empty markdown when records exist"
    assert "## Approval Gate" in md, "markdown must contain the Approval Gate header"
    assert "write_file" in md
    assert "Write report.md" in md
    assert "APPROVED" in md


# ---------------------------------------------------------------------------
# 7. ApprovalRequest dataclass fields (operation_type, description, details, timestamp)
# ---------------------------------------------------------------------------


def test_approval_request_dataclass_fields() -> None:
    """Happy: ApprovalRequest has the 4 required fields with correct defaults."""
    req = ApprovalRequest(operation_type="send_message", description="Post update")
    assert req.operation_type == "send_message"
    assert req.description == "Post update"
    # details defaults to an empty dict (not shared across instances).
    assert req.details == {}
    assert req.details is not None
    # timestamp defaults to a positive float (now).
    assert isinstance(req.timestamp, float)
    assert req.timestamp > 0

    # Explicit values are respected.
    req2 = ApprovalRequest(
        operation_type="create_pr",
        description="Open PR",
        details={"target": "main", "files": 3},
        timestamp=12345.6,
    )
    assert req2.operation_type == "create_pr"
    assert req2.description == "Open PR"
    assert req2.details == {"target": "main", "files": 3}
    assert req2.timestamp == 12345.6

    # default_factory produces independent dicts (no shared mutable default bug).
    a = ApprovalRequest(operation_type="a", description="b")
    b = ApprovalRequest(operation_type="c", description="d")
    a.details["k"] = "v"
    assert "k" not in b.details, "default_factory must produce independent dicts"


# ---------------------------------------------------------------------------
# 8. ApprovalResult dataclass fields (approved, reason, timestamp) and to_dict()
# ---------------------------------------------------------------------------


def test_approval_result_dataclass_fields_and_to_dict() -> None:
    """Happy: ApprovalResult has approved/reason/timestamp + to_dict() serialization."""
    # Defaults: reason is "" and timestamp is now.
    res = ApprovalResult(approved=True)
    assert res.approved is True
    assert res.reason == ""
    assert isinstance(res.timestamp, float)
    assert res.timestamp > 0

    # Explicit values.
    res2 = ApprovalResult(approved=False, reason="Denied by policy", timestamp=99.0)
    assert res2.approved is False
    assert res2.reason == "Denied by policy"
    assert res2.timestamp == 99.0

    # to_dict() must contain exactly the 3 required keys with correct values.
    d = res2.to_dict()
    assert set(d.keys()) == {"approved", "reason", "timestamp"}, (
        f"to_dict() keys mismatch: {set(d.keys())}"
    )
    assert d["approved"] is False
    assert d["reason"] == "Denied by policy"
    assert d["timestamp"] == 99.0


# ---------------------------------------------------------------------------
# 9. Dispatch integration: dispatch with approval_callback populates
#    result.approval_records and result.approval_gate_md
# ---------------------------------------------------------------------------


def test_dispatch_with_callback_populates_records_and_md(
    dispatcher: MultiAgentDispatcher,
) -> None:
    """Integration: approval_callback → result.approval_records + approval_gate_md."""

    captured: list[ApprovalRequest] = []

    def cb(request: ApprovalRequest) -> ApprovalResult:
        captured.append(request)
        return ApprovalResult(approved=True, reason="user OK")

    result = dispatcher.dispatch(
        "Refactor the auth module",
        dry_run=True,
        approval_callback=cb,
    )

    # The callback was invoked at least once (dispatch_complete checkpoint).
    assert len(captured) >= 1, "approval_callback was not invoked during dispatch"
    assert captured[0].operation_type == "dispatch_complete"

    # result.approval_records is populated.
    assert isinstance(result.approval_records, list)
    assert len(result.approval_records) >= 1, (
        "approval_records must be populated when approval_callback is provided"
    )
    rec = result.approval_records[0]
    assert rec["approved"] is True
    assert rec["reason"] == "user OK"
    assert rec["operation_type"] == "dispatch_complete"

    # result.approval_gate_md is populated and non-empty.
    assert result.approval_gate_md != "", (
        "approval_gate_md must be populated when approval_callback is provided"
    )
    assert "## Approval Gate" in result.approval_gate_md
    assert "APPROVED" in result.approval_gate_md


# ---------------------------------------------------------------------------
# 10. Dispatch integration: dispatch without approval_callback (backward compat)
#     still populates records with auto-approve
# ---------------------------------------------------------------------------


def test_dispatch_without_callback_backward_compat(
    dispatcher: MultiAgentDispatcher,
) -> None:
    """Integration: no approval_callback → records still populated with auto-approve."""
    result = dispatcher.dispatch("Design a cache layer", dry_run=True)

    # Backward compat: records are populated even without a callback (auto-approve).
    assert isinstance(result.approval_records, list)
    assert len(result.approval_records) >= 1, (
        "approval_records must be populated (auto-approve) even without callback"
    )
    rec = result.approval_records[0]
    assert rec["approved"] is True, "auto-approve record must be approved=True"
    assert "auto" in rec["reason"].lower(), (
        f"auto-approve reason must mention 'auto', got: {rec['reason']!r}"
    )
    assert rec["operation_type"] == "dispatch_complete"

    # approval_gate_md is also populated (non-empty) under auto-approve.
    assert result.approval_gate_md != "", (
        "approval_gate_md must be populated even under auto-approve (backward compat)"
    )
    assert "## Approval Gate" in result.approval_gate_md


# ---------------------------------------------------------------------------
# 11. Dispatch integration: result.to_markdown() contains "## Approval Gate"
#     section when records exist
# ---------------------------------------------------------------------------


def test_dispatch_to_markdown_contains_approval_gate_section(
    dispatcher: MultiAgentDispatcher,
) -> None:
    """Integration: to_markdown() contains '## Approval Gate' when records exist."""
    result = dispatcher.dispatch("Design a payment gateway", dry_run=True)
    md = result.to_markdown()
    assert "## Approval Gate" in md, (
        "to_markdown() must contain '## Approval Gate' section when records exist"
    )
    # The status line should be present.
    assert "APPROVED" in md, "to_markdown() must render the approval status"


# ---------------------------------------------------------------------------
# 12. Dispatch integration: result.to_dict() contains "approval_records" key
# ---------------------------------------------------------------------------


def test_dispatch_to_dict_contains_approval_records_key(
    dispatcher: MultiAgentDispatcher,
) -> None:
    """Integration: to_dict() contains 'approval_records' key."""
    result = dispatcher.dispatch("Design a search index", dry_run=True)
    d = result.to_dict()
    assert "approval_records" in d, "to_dict() must contain 'approval_records' key"
    assert isinstance(d["approval_records"], list)
    assert len(d["approval_records"]) >= 1, (
        "approval_records in to_dict() must be populated after dispatch"
    )
