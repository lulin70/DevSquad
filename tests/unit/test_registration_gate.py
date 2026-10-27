#!/usr/bin/env python3
"""Unit tests: RegistrationGate fail-closed signal registration (V4.9.0 P2-W3).

Anchors ③④⑤⑥⑦⑧⑨⑪ of the design's negative-first test plan
(docs/planning/V4.9.0_W3_registration-gate_DESIGN.md §7):

- ③ BV critical unregistered → FAIL with the signal type in violations.
- ④ warning/spec findings produce no mandatory signal → PASS.
- ⑤ live ticket tracked → PASS; **fixed still counts as live** (D4
  deadlock-avoidance regression anchor); tracked_by recorded.
- ⑥ only closed tickets → regressed FAIL with reopen guidance.
- ⑦ fail-closed: missing ledger = legal empty ledger → unregistered FAIL
  (not internal_error); corrupt ledger → DefectLedgerError (the mixin
  converts it — unit level asserts the pure refusal).
- ⑧ environment_blocked run → no mandatory signal → PASS.
- ⑨ W4×W3 composition: feature-gate blocking errors are a
  product_failed signal → registration required (D13).
- ⑪ advisory report: non-mandatory types seen but unfiled; critical
  categories excluded; never affects the audit exit code.

All fixtures are real components — real sqlite3 audit DB, real
ReviewFinding objects, real DefectLedger writes (W1/W2 fixture pattern);
no mocked ``details``.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

import pytest

from scripts.cli_defect import cmd_defect_audit
from scripts.collaboration.defect_ledger import DefectLedger, DefectLedgerError
from scripts.collaboration.registration_gate import (
    RegistrationGate,
    RegistrationGateResult,
    unfiled_signal_report,
)
from scripts.collaboration.two_stage_review_gate import ReviewFinding, ReviewStage

pytestmark = pytest.mark.unit

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


def _finding(category: str, severity: str, stage: ReviewStage = ReviewStage.CODE_QUALITY) -> ReviewFinding:
    """A real ReviewFinding — BV checks put the BV ID in ``category``."""
    return ReviewFinding(
        stage=stage,
        severity=severity,
        category=category,
        description=f"review hit {category}",
        file_path="api/routes/dispatch.py",
        line_range="42",
        suggestion=f"Review and fix {category}.",
    )


@pytest.fixture
def audit_db(tmp_path: Path) -> Path:
    """A real SQLite audit DB seeded with the events every test needs.

    Event layout (ids matter — signal refs are ``audit:event=<N>``):
      1: review_findings [BREAK-1 critical]           — filing source for a live BREAK-1 DEF
      2: dispatch_end  failure_class=product_failed   — filing source for a failure:product_failed DEF
      3: dispatch_end  success=True                   — clean regression run for close()
      4: dispatch_end  findings=[BREAK-2, missing_file] — advisory scan source + BREAK-2 filing source
      5: dispatch_end  findings=[BREAK-1 critical]    — critical in dispatch_end → advisory must EXCLUDE
    """
    db_path = tmp_path / "audit" / "dispatch_audit.db"
    db_path.parent.mkdir(parents=True)
    conn = sqlite3.connect(db_path)
    conn.execute(_AUDIT_DDL)

    def _bv_dict(f: ReviewFinding) -> dict:
        return f.to_dict()

    events = [
        ("review_findings", {"findings": [_bv_dict(_finding("BREAK-1", "critical"))]}),
        ("dispatch_end", {"failure_class": "product_failed", "success": False}),
        ("dispatch_end", {"success": True, "duration": 1.5}),
        (
            "dispatch_end",
            {
                "findings": [
                    _bv_dict(_finding("BREAK-2", "warning")),
                    _bv_dict(_finding("missing_file", "warning", ReviewStage.SPEC_COMPLIANCE)),
                ]
            },
        ),
        ("dispatch_end", {"findings": [_bv_dict(_finding("BREAK-1", "critical"))]}),
    ]
    for i, (event_type, details) in enumerate(events, start=1):
        conn.execute(
            "INSERT INTO dispatch_audit (event_type, user_id, timestamp, details, prev_hash, entry_hash)"
            " VALUES (?, 'tester', ?, ?, '0', '0')",
            (event_type, 1700000000.0 + i, json.dumps(details)),
        )
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def ledger(tmp_path: Path, audit_db: Path) -> DefectLedger:
    return DefectLedger(
        ledger_path=tmp_path / ".devsquad" / "defects.json",
        audit_db_path=audit_db,
    )


class TestSignalExtraction:
    """③④⑧⑨ input side — extract_signal_types (D2 live computation)."""

    def test_bv_critical_finding_is_mandatory_signal(self) -> None:
        types = RegistrationGate.extract_signal_types([], [], [_finding("BREAK-1", "critical")])
        assert types == ["review:break-vuln:BREAK-1"]

    def test_warning_and_spec_findings_produce_no_signal(self) -> None:
        """④ — BREAK-2 (warning) + missing_file (spec) stay outside the gate."""
        findings = [
            _finding("BREAK-2", "warning"),
            _finding("missing_file", "warning", ReviewStage.SPEC_COMPLIANCE),
        ]
        assert RegistrationGate.extract_signal_types([], [], findings) == []

    def test_worker_failure_is_product_failed_signal(self) -> None:
        worker_results = [{"success": False, "error": "RuntimeError: deterministic product failure"}]
        assert RegistrationGate.extract_signal_types(worker_results, [], []) == ["failure:product_failed"]

    def test_environment_blocked_run_has_no_signal(self) -> None:
        """⑧ — environment blocked is a claim about the environment, not a defect signal."""
        worker_results = [{"success": False, "error": "APIConnectionError: error code: 503"}]
        assert RegistrationGate.extract_signal_types(worker_results, [], []) == []

    def test_feature_gate_blocking_error_is_product_failed_signal(self) -> None:
        """⑨ D13 W4×W3: a feature-gate FAIL run must register its failure."""
        errors = ["Feature gate blocked: checklist_missing: .devsquad/acceptance_checklist.json"]
        assert RegistrationGate.extract_signal_types([], errors, []) == ["failure:product_failed"]

    def test_clean_run_has_no_signal(self) -> None:
        assert RegistrationGate.extract_signal_types([], [], []) == []


class TestGateVerdicts:
    """③⑤⑥⑦ core — evaluate against a real ledger (D4 live = open|fixed)."""

    def test_bv_critical_unregistered_fails(self, ledger: DefectLedger) -> None:
        """③ — critical signal, empty ledger → unregistered FAIL."""
        result = RegistrationGate().evaluate(
            worker_results=[],
            errors=[],
            findings=[_finding("BREAK-1", "critical")],
            ledger_path=ledger.ledger_path,
        )
        assert result.verdict == "fail"
        assert result.error is None  # unregistered, not internal_error
        signal = result.signals[0]
        assert signal["type"] == "review:break-vuln:BREAK-1"
        assert signal["status"] == "unregistered"
        assert any("review:break-vuln:BREAK-1" in v and "no live DEF ticket" in v for v in result.violations)

    def test_open_ticket_tracks_signal_pass(self, ledger: DefectLedger) -> None:
        """⑤ — open ticket covers the signal type."""
        ledger.add("audit:event=1&finding=0", "route without handler")
        result = RegistrationGate().evaluate(
            worker_results=[],
            errors=[],
            findings=[_finding("BREAK-1", "critical")],
            ledger_path=ledger.ledger_path,
        )
        assert result.verdict == "pass"
        assert result.signals[0]["status"] == "tracked"
        assert result.signals[0]["tracked_by"] == ["DEF-001"]

    def test_fixed_ticket_still_tracks_signal_pass(self, ledger: DefectLedger) -> None:
        """⑤ D4 deadlock regression anchor — ``fixed`` is a live tracking
        state; open-only matching would leave fixed defects with no legal
        exit (refix keeps fixed, reopen only works from closed)."""
        entry = ledger.add("audit:event=1&finding=0", "route without handler")
        ledger.update(entry.id, commit_sha="abc123", summary="add missing handler")
        result = RegistrationGate().evaluate(
            worker_results=[],
            errors=[],
            findings=[_finding("BREAK-1", "critical")],
            ledger_path=ledger.ledger_path,
        )
        assert result.verdict == "pass"
        assert result.signals[0]["status"] == "tracked"
        assert result.signals[0]["tracked_by"] == ["DEF-001"]

    def test_closed_only_tickets_regress_fail_with_reopen_guidance(self, ledger: DefectLedger) -> None:
        """⑥ — signal type with only closed tickets = regression → FAIL."""
        entry = ledger.add("audit:event=1&finding=0", "route without handler")
        ledger.update(entry.id, commit_sha="abc123", summary="add missing handler")
        ledger.close(entry.id, run_ref="audit:event=3")
        result = RegistrationGate().evaluate(
            worker_results=[],
            errors=[],
            findings=[_finding("BREAK-1", "critical")],
            ledger_path=ledger.ledger_path,
        )
        assert result.verdict == "fail"
        signal = result.signals[0]
        assert signal["status"] == "regressed"
        assert signal["tracked_by"] == []
        assert signal["closed_ids"] == ["DEF-001"]
        assert any("regressed" in v and "reopen" in v for v in result.violations)

    def test_missing_ledger_is_legal_empty_unregistered_fail(self, tmp_path: Path) -> None:
        """⑦ — missing ledger file = empty ledger → unregistered FAIL (not internal_error)."""
        result = RegistrationGate().evaluate(
            worker_results=[],
            errors=["RuntimeError: product failure"],
            findings=[],
            ledger_path=tmp_path / ".devsquad" / "defects.json",
        )
        assert result.verdict == "fail"
        assert result.error is None
        assert result.signals[0] == {
            "type": "failure:product_failed",
            "status": "unregistered",
            "tracked_by": [],
            "closed_ids": [],
        }

    def test_corrupt_ledger_raises_ledger_error(self, tmp_path: Path) -> None:
        """⑦ fail-closed — corrupt ledger refuses to load; the mixin layer
        converts this into an internal_error FAIL."""
        ledger_path = tmp_path / ".devsquad" / "defects.json"
        ledger_path.parent.mkdir(parents=True)
        ledger_path.write_text("{not json", encoding="utf-8")
        with pytest.raises(DefectLedgerError):
            RegistrationGate().evaluate(
                worker_results=[],
                errors=[],
                findings=[],
                ledger_path=ledger_path,
            )

    def test_environment_blocked_run_passes_gate(self, tmp_path: Path) -> None:
        """⑧ — no mandatory signal → gate passes (ledger file absent = empty)."""
        worker_results = [{"success": False, "error": "APIConnectionError: error code: 503"}]
        result = RegistrationGate().evaluate(
            worker_results=worker_results,
            errors=[],
            findings=[],
            ledger_path=tmp_path / ".devsquad" / "defects.json",
        )
        assert result.verdict == "pass"
        assert result.signals == []

    def test_feature_gate_error_run_requires_registration(self, tmp_path: Path) -> None:
        """⑨ D13 — a W4-gate-blocked run files as product_failed → FAIL until tracked."""
        errors = ["Feature gate blocked: checklist_missing: .devsquad/acceptance_checklist.json"]
        result = RegistrationGate().evaluate(
            worker_results=[],
            errors=errors,
            findings=[],
            ledger_path=tmp_path / ".devsquad" / "defects.json",
        )
        assert result.verdict == "fail"
        assert result.signals[0]["type"] == "failure:product_failed"


class TestResultContract:
    """to_dict / internal_error contract consumed by details + audit (D9)."""

    def test_internal_error_is_fail_closed(self) -> None:
        result = RegistrationGateResult.internal_error("ledger exploded")
        assert result.verdict == "fail"
        assert result.passed is False
        assert result.error == "ledger exploded"
        assert result.violations == ["gate_error: ledger exploded"]

    def test_to_dict_shape_and_summary_counts(self, tmp_path: Path) -> None:
        ledger_path = tmp_path / ".devsquad" / "defects.json"
        result = RegistrationGate().evaluate(
            worker_results=[],
            errors=["RuntimeError: product failure"],
            findings=[_finding("BREAK-1", "critical")],
            ledger_path=ledger_path,
        )
        data = result.to_dict()
        assert set(data.keys()) == {"verdict", "ledger_path", "summary", "signals", "violations", "error"}
        assert data["verdict"] == "fail"
        assert data["ledger_path"] == str(ledger_path)
        assert data["summary"] == {"mandatory": 2, "tracked": 0, "unregistered": 2, "regressed": 0}
        assert {s["type"] for s in data["signals"]} == {
            "failure:product_failed",
            "review:break-vuln:BREAK-1",
        }


class TestUnfiledSignalReport:
    """⑪ D11 advisory — non-mandatory types seen in dispatch_end events."""

    def test_unfiled_warning_and_spec_types_listed(self, ledger: DefectLedger) -> None:
        advisory, warnings = unfiled_signal_report(ledger.ledger_path, ledger.audit_db_path)
        assert warnings == []
        types = {item["type"] for item in advisory}
        assert types == {"review:break-vuln:BREAK-2", "review:spec:missing_file"}
        for item in advisory:
            assert item["seen_count"] == 1
            assert item["last_event_id"] == 4

    def test_live_ticket_excludes_type_from_advisory(self, ledger: DefectLedger) -> None:
        ledger.add("audit:event=4&finding=0", "handler without return")
        advisory, _ = unfiled_signal_report(ledger.ledger_path, ledger.audit_db_path)
        assert {item["type"] for item in advisory} == {"review:spec:missing_file"}

    def test_critical_categories_excluded_from_advisory(self, ledger: DefectLedger) -> None:
        """Mandatory scope is gated fail-closed when enabled — the advisory
        deliberately never lists it (event 5 carries BREAK-1 critical)."""
        advisory, _ = unfiled_signal_report(ledger.ledger_path, ledger.audit_db_path)
        assert all("BREAK-1" not in item["type"] for item in advisory)

    def test_missing_audit_db_returns_empty_with_warning(self, tmp_path: Path) -> None:
        advisory, warnings = unfiled_signal_report(
            ledger_path=tmp_path / ".devsquad" / "defects.json",
            audit_db_path=tmp_path / "audit" / "nope.db",
        )
        assert advisory == []
        assert any("audit DB not found" in w for w in warnings)


class TestAuditCliAdvisoryOutput:
    """⑪ — ``devsquad defect audit`` prints the advisory, exit code unchanged."""

    @staticmethod
    def _args(ledger: DefectLedger, **kwargs: object) -> argparse.Namespace:
        defaults: dict[str, object] = {
            "ledger_path": str(ledger.ledger_path),
            "audit_db_path": str(ledger.audit_db_path),
            "json": False,
        }
        defaults.update(kwargs)
        return argparse.Namespace(**defaults)

    def test_audit_exit_zero_and_advisory_lines_in_text_mode(
        self, ledger: DefectLedger, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert cmd_defect_audit(self._args(ledger)) == 0
        out = capsys.readouterr().out
        assert "ledger audit: OK" in out
        assert "ADVISORY: unfiled review:break-vuln:BREAK-2 (seen 1 time(s), last event 4)" in out
        assert "ADVISORY: unfiled review:spec:missing_file" in out

    def test_audit_json_mode_carries_unfiled_advisory_key(
        self, ledger: DefectLedger, capsys: pytest.CaptureFixture[str]
    ) -> None:
        capsys.readouterr()
        assert cmd_defect_audit(self._args(ledger, json=True)) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["ok"] is True
        assert payload["issues"] == []
        assert {item["type"] for item in payload["unfiled_advisory"]} == {
            "review:break-vuln:BREAK-2",
            "review:spec:missing_file",
        }


class TestCliKwargsInjection:
    """⑫ CLI wiring: _build_dispatch_kwargs reads .devsquad.yaml defect_ledger (D5)."""

    @staticmethod
    def _args(**overrides: object) -> argparse.Namespace:
        defaults: dict[str, object] = {
            "persist_dir": "/tmp/rg_cli_test",
            "no_warmup": True,
            "no_compression": True,
            "skip_permission": True,
            "no_memory": True,
            "no_skillify": True,
            "stream": False,
            "lang": "auto",
            "permission_level": None,
            "backend": "mock",
            "base_url": None,
            "model": None,
        }
        defaults.update(overrides)
        return argparse.Namespace(**defaults)

    def test_absent_yaml_key_injects_nothing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from scripts.cli_dispatch import _build_dispatch_kwargs
        from scripts.collaboration.config_manager import ConfigManager

        yaml_path = tmp_path / ".devsquad.yaml"
        yaml_path.write_text("backend: mock\ntimeout: 60\n")
        monkeypatch.setenv("DEVSQUAD_CONFIG_PATH", str(yaml_path))
        ConfigManager.reset()
        try:
            kwargs, err = _build_dispatch_kwargs(self._args())
        finally:
            ConfigManager.reset()
        assert err is None
        assert "enable_registration_gate" not in kwargs

    def test_disabled_ledger_injects_nothing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from scripts.cli_dispatch import _build_dispatch_kwargs
        from scripts.collaboration.config_manager import ConfigManager

        yaml_path = tmp_path / ".devsquad.yaml"
        yaml_path.write_text("backend: mock\ndefect_ledger:\n  enabled: false\n")
        monkeypatch.setenv("DEVSQUAD_CONFIG_PATH", str(yaml_path))
        ConfigManager.reset()
        try:
            kwargs, err = _build_dispatch_kwargs(self._args())
        finally:
            ConfigManager.reset()
        assert err is None
        assert "enable_registration_gate" not in kwargs

    def test_enabled_ledger_injects_gate_kwarg(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from scripts.cli_dispatch import _build_dispatch_kwargs
        from scripts.collaboration.config_manager import ConfigManager

        yaml_path = tmp_path / ".devsquad.yaml"
        yaml_path.write_text("backend: mock\ndefect_ledger:\n  enabled: true\n")
        monkeypatch.setenv("DEVSQUAD_CONFIG_PATH", str(yaml_path))
        ConfigManager.reset()
        try:
            kwargs, err = _build_dispatch_kwargs(self._args())
        finally:
            ConfigManager.reset()
        assert err is None
        assert kwargs["enable_registration_gate"] is True
