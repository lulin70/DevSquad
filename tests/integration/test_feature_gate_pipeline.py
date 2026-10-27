#!/usr/bin/env python3
"""Integration tests: feature gate through the production dispatch path (V4.9.0 P2-W4).

Anchors ①②⑦ of the design's negative-first test plan
(docs/planning/V4.9.0_W4_feature-gate_DESIGN.md §7):

- ① backward compat: gate disabled (no config key / default constructor)
  → the whole dispatch chain leaves ZERO feature-gate trace: no
  ``details["feature_gate"]``, no audit ``dispatch_end`` key, no Markdown
  section — behavior byte-identical to 4.8.x.
- ② tamper: the checklist is rewritten between anchoring (pre-steps) and
  evaluation (Step 23.5) → verdict FAIL ``checklist_tampered``,
  ``success=False``.
- ⑦ C19 ordering: a feature-gate FAIL run recomputes its terminal
  ``failure_class`` to ``product_failed`` (Step 24 consumes Step-23.5
  errors — W2 lesson ①: no timing break).

The tamper window is exercised for real: an event-bus handler rewrites the
checklist file at ``post_dispatch.execution_completed`` (after anchoring,
before Step 23.5). Commands use ``sys.executable`` — no network, no
external binaries.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from scripts.collaboration.dispatch_audit import DispatchAuditLogger
from scripts.collaboration.dispatcher import MultiAgentDispatcher
from scripts.collaboration.failure_taxonomy import EXIT_PRODUCT_FAILED, dispatch_exit_code

_OK_CMD = f"{sys.executable} -c 'import sys; sys.exit(0)'"
_FAIL_CMD = f"{sys.executable} -c 'import sys; sys.exit(1)'"


class _OkBackend:
    """Deterministic local backend (no network, no API key)."""

    model = "feature-gate-fake-model"

    def is_available(self) -> bool:
        return True

    def generate(self, prompt: str, **kwargs: Any) -> str:
        return "Structured answer: 4"

    def generate_stream(self, prompt: str, **kwargs: Any):
        yield "Structured answer: 4"


def _write_checklist(tmp_path: Path, items: list[dict[str, Any]]) -> Path:
    checklist = tmp_path / ".devsquad" / "acceptance_checklist.json"
    checklist.parent.mkdir(parents=True, exist_ok=True)
    checklist.write_text(json.dumps({"schema_version": 1, "items": items}))
    return checklist


def _item(entry_id: str, command: str, *, description: str = "criterion", waive: str | None = None) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "id": entry_id,
        "description": description,
        "verify": {"kind": "command", "command": command},
    }
    if waive is not None:
        entry["waive_reason"] = waive
    return entry


def test_disabled_gate_leaves_zero_trace(tmp_path: Path):
    """① default-off: no details key, no audit key, no Markdown section."""
    audit = DispatchAuditLogger()
    disp = MultiAgentDispatcher(llm_backend=_OkBackend(), audit_logger=audit, enable_memory=False)
    try:
        result = disp.dispatch("What is 2+2?", roles=["architect"])
    finally:
        disp.shutdown()

    # The dispatch itself must be unaffected.
    assert result.success
    assert result.details.get("failure_class") == "none"
    # Five zero-trace faces (design §5): details, result attribute,
    # Markdown, audit event. to_dict() keeps the key with a None value —
    # the same shape contract as two_stage_review (always-present key).
    assert "feature_gate" not in result.details
    assert result.feature_gate is None
    assert result.to_dict()["feature_gate"] is None
    assert "Feature gate" not in result.to_markdown()
    ends = audit.query(event_type="dispatch_end")
    assert len(ends) == 1
    assert "feature_gate" not in ends[0].details
    # W2 baseline intact: terminal signals still present.
    assert ends[0].details["failure_class"] == "none"
    assert audit.verify_chain()


def test_enabled_gate_passes_and_renders_matrix(tmp_path: Path):
    """Enabled + all-pass checklist → verdict pass, matrix rendered, run green."""
    checklist = _write_checklist(
        tmp_path,
        [
            _item("AC-1", _OK_CMD, description="login returns 200"),
            _item("AC-2", _OK_CMD, description="logout clears session"),
        ],
    )
    audit = DispatchAuditLogger()
    disp = MultiAgentDispatcher(
        llm_backend=_OkBackend(),
        audit_logger=audit,
        enable_memory=False,
        enable_feature_gate=True,
        feature_gate_checklist=str(checklist),
        feature_gate_command_timeout_seconds=30,
    )
    try:
        result = disp.dispatch("What is 2+2?", roles=["architect"])
    finally:
        disp.shutdown()

    assert result.success
    gate = result.details["feature_gate"]
    assert gate["verdict"] == "pass"
    assert gate["summary"] == {"total": 2, "pass": 2, "fail": 0, "waived": 0}
    assert gate["anchored_sha256"] == gate["computed_sha256"]
    assert gate["checklist_path"] == str(checklist.resolve())
    # Markdown matrix section (④: rendering carries descriptions).
    report = result.to_markdown()
    assert "Feature gate" in report
    assert "`pass`" in report
    assert "login returns 200" in report
    # Audit event carries the matrix (D4: dual-hash tamper evidence).
    ends = audit.query(event_type="dispatch_end")
    assert len(ends) == 1
    audited = ends[0].details["feature_gate"]
    assert audited["verdict"] == "pass"
    assert audited["anchored_sha256"] == gate["anchored_sha256"]
    assert audit.verify_chain()
    # No gate errors → C19 stays none.
    assert result.details["failure_class"] == "none"


def test_tampered_checklist_fails_gate_and_recomputes_failure_class(tmp_path: Path):
    """② + ⑦: rewrite between anchor (pre-steps) and Step 23.5 →
    checklist_tampered FAIL, success=False, terminal failure_class
    recomputed to product_failed (Step 24 consumes Step-23.5 errors)."""

    def _tamper_handler(**_kwargs: Any) -> None:
        # Fires at post_dispatch.execution_completed — after anchoring,
        # before Step 23.5. This simulates a worker (or anything) moving
        # the goalposts during execution.
        checklist.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "items": [_item("AC-1", _OK_CMD, description="sneaky rewrite")],
                }
            )
        )

    checklist = _write_checklist(
        tmp_path,
        [_item("AC-1", _OK_CMD, description="original criterion")],
    )
    audit = DispatchAuditLogger()
    disp = MultiAgentDispatcher(
        llm_backend=_OkBackend(),
        audit_logger=audit,
        enable_memory=False,
        enable_feature_gate=True,
        feature_gate_checklist=str(checklist),
        feature_gate_command_timeout_seconds=30,
    )
    disp.event_bus.on("post_dispatch.execution_completed", _tamper_handler)
    try:
        result = disp.dispatch("What is 2+2?", roles=["architect"])
    finally:
        disp.shutdown()

    assert not result.success
    gate = result.details["feature_gate"]
    assert gate["verdict"] == "fail"
    assert any("checklist_tampered" in v for v in gate["violations"])
    assert gate["anchored_sha256"] != gate["computed_sha256"]
    # Gate errors landed in result.errors (Step-21 pattern, D6).
    assert any("Feature gate" in e for e in result.errors)
    # ⑦ C19 terminal recompute: Step 24 ran AFTER Step 23.5 and saw errors.
    assert result.details["failure_class"] == "product_failed"
    assert dispatch_exit_code(result) == EXIT_PRODUCT_FAILED
    assert "product_failed" in result.to_markdown()
    # Audit event carries the tamper evidence (dual hashes differ).
    ends = audit.query(event_type="dispatch_end")
    assert len(ends) == 1
    audited = ends[0].details["feature_gate"]
    assert audited["verdict"] == "fail"
    assert audited["anchored_sha256"] != audited["computed_sha256"]
    assert audit.verify_chain()


def test_failing_checklist_command_fails_run(tmp_path: Path):
    """Enabled + failing command → gap FAIL, run red, C19 product_failed."""
    checklist = _write_checklist(
        tmp_path,
        [
            _item("AC-1", _OK_CMD, description="covered"),
            _item("AC-2", _FAIL_CMD, description="uncovered criterion"),
        ],
    )
    disp = MultiAgentDispatcher(
        llm_backend=_OkBackend(),
        enable_memory=False,
        enable_feature_gate=True,
        feature_gate_checklist=str(checklist),
        feature_gate_command_timeout_seconds=30,
    )
    try:
        result = disp.dispatch("What is 2+2?", roles=["architect"])
    finally:
        disp.shutdown()

    assert not result.success
    gate = result.details["feature_gate"]
    assert gate["verdict"] == "fail"
    assert gate["summary"]["fail"] == 1
    assert gate["gaps"] == [{"id": "AC-2", "description": "uncovered criterion"}]
    assert any("Feature gate gap: AC-2" in e for e in result.errors)
    assert result.details["failure_class"] == "product_failed"


def test_missing_checklist_fails_closed_when_enabled(tmp_path: Path):
    """D10: enabled + no checklist file → FAIL (never a vacuous pass)."""
    disp = MultiAgentDispatcher(
        llm_backend=_OkBackend(),
        enable_memory=False,
        enable_feature_gate=True,
        feature_gate_checklist=str(tmp_path / ".devsquad" / "acceptance_checklist.json"),
        feature_gate_command_timeout_seconds=30,
    )
    try:
        result = disp.dispatch("What is 2+2?", roles=["architect"])
    finally:
        disp.shutdown()

    assert not result.success
    gate = result.details["feature_gate"]
    assert gate["verdict"] == "fail"
    assert any("checklist_missing" in v for v in gate["violations"])
    assert result.details["failure_class"] == "product_failed"
