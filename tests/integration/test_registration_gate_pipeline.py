#!/usr/bin/env python3
"""Integration tests: registration gate through the production dispatch path (V4.9.0 P2-W3).

Anchors ①② (+⑤ pipeline face, +⑦ mixin fail-closed conversion) of the
design's test plan (docs/planning/V4.9.0_W3_registration-gate_DESIGN.md §7):

- ① backward compat: gate disabled (no config / default constructor)
  → the dispatch chain leaves ZERO registration-gate trace: no
  ``details["registration_gate"]``, no audit ``dispatch_end`` key, no
  Markdown section — behavior byte-identical to 4.8.x.
- ② signal-no-evaporation: enabled + a failed (product_failed) run +
  empty ledger → verdict FAIL ``unregistered``, gate errors land in
  ``result.errors``, ``success=False``, C19 terminal recompute keeps
  ``product_failed`` (Step 24 runs after Step 23.6 — W2 lesson ①).
- ⑤ pipeline face: enabled + the same failed run + a live DEF ticket
  for ``failure:product_failed`` → gate verdict ``pass``, no gate
  errors, the run stays red only from its own worker failure.
- ⑦ mixin conversion: corrupt ledger → the mixin converts the
  ``DefectLedgerError`` into an internal-error FAIL (fail-closed) —
  the run can never finish green on an unreadable ledger.

The ledger path is the production default ``.devsquad/defects.json``
(resolved from CWD, D5: no config knob), so the enabled-gate tests run
under ``monkeypatch.chdir(tmp_path)`` — nothing touches the repo's own
ledger. All fixtures are real: real sqlite3 seed DB (for filing), real
DefectLedger writes, real dispatch pipeline with a deterministic local
backend (no network, no API key).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from scripts.collaboration.defect_ledger import DefectLedger
from scripts.collaboration.dispatch_audit import DispatchAuditLogger
from scripts.collaboration.dispatcher import MultiAgentDispatcher
from scripts.collaboration.failure_taxonomy import EXIT_PRODUCT_FAILED, dispatch_exit_code

# Real dispatch_audit schema (dispatch_audit.py:189-198).
_AUDIT_DDL = """
CREATE TABLE dispatch_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    user_id TEXT NOT NULL,
    timestamp REAL NOT NULL,
    details TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    entry_hash TEXT NOT NULL
)
"""


class _FailBackend:
    """Deterministic local backend whose every call fails (no network).

    The failure text carries no environment marker, so C19 classifies
    the run as ``product_failed`` — the mandatory signal the gate
    guards.
    """

    model = "registration-gate-fake-model"

    def is_available(self) -> bool:
        return True

    def generate(self, prompt: str, **kwargs: Any) -> str:
        raise RuntimeError("deterministic product failure")

    def generate_stream(self, prompt: str, **kwargs: Any):
        raise RuntimeError("deterministic product failure")
        yield ""  # pragma: no cover — generator formality


class _OkBackend:
    """Deterministic local backend for the zero-trace compat test."""

    model = "registration-gate-fake-model"

    def is_available(self) -> bool:
        return True

    def generate(self, prompt: str, **kwargs: Any) -> str:
        return "Structured answer: 4"

    def generate_stream(self, prompt: str, **kwargs: Any):
        yield "Structured answer: 4"


def _dispatch(backend: Any, *, enable_registration_gate: bool, audit: Any = None) -> Any:
    disp = MultiAgentDispatcher(
        llm_backend=backend,
        audit_logger=audit,
        enable_memory=False,
        enable_registration_gate=enable_registration_gate,
    )
    try:
        return disp.dispatch("What is 2+2?", roles=["architect"])
    finally:
        disp.shutdown()


def _seed_defect(tmp_path: Path) -> None:
    """File one live ``failure:product_failed`` DEF in the default ledger.

    Writes a real sqlite seed event and files against it — the W1
    no-free-form-filing contract (signal refs must resolve).
    """
    db_path = tmp_path / "audit" / "seed.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(_AUDIT_DDL)
    conn.execute(
        "INSERT INTO dispatch_audit (event_type, user_id, timestamp, details, prev_hash, entry_hash)"
        " VALUES ('dispatch_end', 'tester', 1700000000.0, ?, '0', '0')",
        (json.dumps({"failure_class": "product_failed", "success": False}),),
    )
    conn.commit()
    conn.close()
    DefectLedger(
        ledger_path=tmp_path / ".devsquad" / "defects.json",
        audit_db_path=db_path,
    ).add("audit:event=1&failure=product_failed", "seed defect for tracked-pass test")


def test_disabled_gate_leaves_zero_trace():
    """① default-off: no details key, no audit key, no Markdown section."""
    audit = DispatchAuditLogger()
    result = _dispatch(_OkBackend(), enable_registration_gate=False, audit=audit)

    assert result.success
    assert result.details.get("failure_class") == "none"
    # Five zero-trace faces (design §5): details, result attribute,
    # to_dict() (always-present key with None — two_stage_review shape
    # contract), Markdown, audit event.
    assert "registration_gate" not in result.details
    assert result.registration_gate is None
    assert result.to_dict()["registration_gate"] is None
    assert "Registration gate" not in result.to_markdown()
    ends = audit.query(event_type="dispatch_end")
    assert len(ends) == 1
    assert "registration_gate" not in ends[0].details
    # W2 baseline intact: terminal signals still present.
    assert ends[0].details["failure_class"] == "none"
    assert audit.verify_chain()


def test_unregistered_signal_fails_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """② enabled + product_failed run + empty ledger → FAIL, run red, C19 keeps product_failed."""
    monkeypatch.chdir(tmp_path)  # default ledger path .devsquad/defects.json → tmp
    audit = DispatchAuditLogger()
    result = _dispatch(_FailBackend(), enable_registration_gate=True, audit=audit)

    assert not result.success
    gate = result.details["registration_gate"]
    assert gate["verdict"] == "fail"
    assert gate["summary"] == {"mandatory": 1, "tracked": 0, "unregistered": 1, "regressed": 0}
    signal = gate["signals"][0]
    assert signal["type"] == "failure:product_failed"
    assert signal["status"] == "unregistered"
    # Gate errors joined the run errors (Step-21 pattern, D6).
    assert any("Registration gate blocked" in e for e in result.errors)
    # C19 ordering (W2 lesson ①): Step 24 recomputes AFTER Step 23.6.
    assert result.details["failure_class"] == "product_failed"
    assert dispatch_exit_code(result) == EXIT_PRODUCT_FAILED
    assert "product_failed" in result.to_markdown()
    # Audit event carries the gate verdict (D9).
    ends = audit.query(event_type="dispatch_end")
    assert len(ends) == 1
    assert ends[0].details["registration_gate"]["verdict"] == "fail"
    assert audit.verify_chain()


def test_live_ticket_tracks_signal_gate_passes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """⑤ pipeline face: a live DEF for the signal type → gate verdict pass,
    no gate errors; the run stays red only from its own worker failure."""
    _seed_defect(tmp_path)
    monkeypatch.chdir(tmp_path)
    audit = DispatchAuditLogger()
    result = _dispatch(_FailBackend(), enable_registration_gate=True, audit=audit)

    # The worker failure itself still fails the run…
    assert not result.success
    # …but the gate is satisfied and adds no errors of its own.
    gate = result.details["registration_gate"]
    assert gate["verdict"] == "pass"
    assert gate["summary"] == {"mandatory": 1, "tracked": 1, "unregistered": 0, "regressed": 0}
    assert gate["signals"][0]["tracked_by"] == ["DEF-001"]
    assert not any("Registration gate blocked" in e for e in result.errors)
    # Markdown renders the matrix with the tracked mark.
    assert "Registration gate" in result.to_markdown()
    assert "tracked" in result.to_markdown()
    ends = audit.query(event_type="dispatch_end")
    assert ends[0].details["registration_gate"]["verdict"] == "pass"
    assert audit.verify_chain()


def test_corrupt_ledger_fails_closed_via_internal_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """⑦ mixin conversion: unreadable ledger → internal-error FAIL, never a silent pass."""
    ledger_path = tmp_path / ".devsquad" / "defects.json"
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text("{not json", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    audit = DispatchAuditLogger()
    result = _dispatch(_FailBackend(), enable_registration_gate=True, audit=audit)

    assert not result.success
    gate = result.details["registration_gate"]
    assert gate["verdict"] == "fail"
    assert gate["error"] is not None
    assert any(v.startswith("gate_error:") for v in gate["violations"])
    assert any("Registration gate blocked: gate_error" in e for e in result.errors)
    assert result.details["failure_class"] == "product_failed"
    assert dispatch_exit_code(result) == EXIT_PRODUCT_FAILED
