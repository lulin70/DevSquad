#!/usr/bin/env python3
"""Unit tests: FeatureGate live acceptance-coverage matrix (V4.9.0 P2-W4).

Anchors ③④⑤ of the design's negative-first test plan
(docs/planning/V4.9.0_W4_feature-gate_DESIGN.md §7):

- ③ live matrix — real command execution: exit 0 → pass, exit 1 → fail,
  timeout → fail (timed_out), command start failure → fail.
- ④ waiver traceability — waived entries never execute, matrix records
  the reason; gaps/waived lists land in to_dict().
- ⑤ fail-closed boundaries — missing file, unparsable JSON, unknown
  schema_version, empty items, duplicate ids, missing verify, unknown
  verify.kind: all FAIL with explicit violations, no silent pass.

Command determinism discipline: every command uses ``sys.executable -c``
— no network, no external binaries, no PATH assumptions.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from scripts.collaboration.feature_gate import (
    DEFAULT_CHECKLIST_PATH,
    FeatureGate,
    FeatureGateResult,
)

_OK_CMD = f"{sys.executable} -c 'import sys; sys.exit(0)'"
_FAIL_CMD = f"{sys.executable} -c 'import sys; sys.exit(7)'"
_SLEEP_CMD = f"{sys.executable} -c 'import time; time.sleep(30)'"


def _write_checklist(
    tmp_path: Path,
    items: list[dict[str, Any]],
    schema_version: Any = 1,
) -> Path:
    """Write a checklist file and return its path."""
    checklist = tmp_path / ".devsquad" / "acceptance_checklist.json"
    checklist.parent.mkdir(parents=True, exist_ok=True)
    if schema_version is _RAW:
        checklist.write_text(items if isinstance(items, str) else json.dumps(items))
    else:
        checklist.write_text(json.dumps({"schema_version": schema_version, "items": items}))
    return checklist


# Sentinel: write ``items`` as raw file content (for unparsable-JSON tests).
_RAW = object()


def _entry(
    entry_id: str,
    command: str,
    *,
    description: str | None = "entry description",
    waive_reason: str | None = None,
    kind: str = "command",
    drop_verify: bool = False,
) -> dict[str, Any]:
    item: dict[str, Any] = {"id": entry_id, "description": description}
    if not drop_verify:
        item["verify"] = {"kind": kind, "command": command}
    if waive_reason is not None:
        item["waive_reason"] = waive_reason
    return item


class TestAnchor:
    """``FeatureGate.anchor`` — load-time anchoring (D4)."""

    def test_anchor_ok_records_sha256_and_descriptions(self, tmp_path: Path) -> None:
        checklist = _write_checklist(
            tmp_path,
            [
                _entry("AC-1", _OK_CMD, description="first criterion"),
                _entry("AC-2", _OK_CMD, description="second criterion"),
            ],
        )
        anchor = FeatureGate().anchor(checklist)
        assert anchor["status"] == "ok"
        assert anchor["path"] == str(checklist.resolve())
        assert isinstance(anchor["sha256"], str) and len(anchor["sha256"]) == 64
        assert anchor["descriptions"] == ["first criterion", "second criterion"]
        assert anchor["violations"] == []

    def test_anchor_missing_file_records_missing(self, tmp_path: Path) -> None:
        anchor = FeatureGate().anchor(tmp_path / "nope.json")
        assert anchor["status"] == "missing"
        assert anchor["sha256"] is None
        assert any("checklist_missing" in v for v in anchor["violations"])

    def test_anchor_unparsable_json_records_invalid(self, tmp_path: Path) -> None:
        checklist = _write_checklist(tmp_path, "{not json", schema_version=_RAW)  # type: ignore[arg-type]
        anchor = FeatureGate().anchor(checklist)
        assert anchor["status"] == "invalid"
        assert any("checklist_invalid" in v for v in anchor["violations"])


class TestLiveMatrix:
    """③ — the matrix comes from real command execution (D2/D11)."""

    def test_exit_zero_passes(self, tmp_path: Path) -> None:
        checklist = _write_checklist(tmp_path, [_entry("AC-1", _OK_CMD)])
        gate = FeatureGate()
        result = gate.evaluate(gate.anchor(checklist), timeout_seconds=30)
        assert result.verdict == "pass"
        assert result.passed is True
        entry = result.entries[0]
        assert entry["status"] == "pass"
        assert entry["exit_code"] == 0

    def test_exit_nonzero_fails_with_exit_code(self, tmp_path: Path) -> None:
        checklist = _write_checklist(tmp_path, [_entry("AC-1", _FAIL_CMD)])
        gate = FeatureGate()
        result = gate.evaluate(gate.anchor(checklist), timeout_seconds=30)
        assert result.verdict == "fail"
        entry = result.entries[0]
        assert entry["status"] == "fail"
        assert entry["exit_code"] == 7

    def test_timeout_fails_with_timed_out_marker(self, tmp_path: Path) -> None:
        checklist = _write_checklist(tmp_path, [_entry("AC-1", _SLEEP_CMD)])
        gate = FeatureGate()
        result = gate.evaluate(gate.anchor(checklist), timeout_seconds=1)
        assert result.verdict == "fail"
        entry = result.entries[0]
        assert entry["status"] == "fail"
        assert entry["timed_out"] is True

    def test_command_start_failure_fails(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        checklist = _write_checklist(tmp_path, [_entry("AC-1", _OK_CMD)])
        gate = FeatureGate()

        def _raise(*_args: Any, **_kwargs: Any) -> None:
            raise OSError("no shell available")

        monkeypatch.setattr(subprocess, "run", _raise)
        result = gate.evaluate(gate.anchor(checklist), timeout_seconds=30)
        assert result.verdict == "fail"
        entry = result.entries[0]
        assert entry["status"] == "fail"
        assert "command failed to start" in entry["error"]

    def test_command_not_found_fails_with_exit_127(self, tmp_path: Path) -> None:
        checklist = _write_checklist(tmp_path, [_entry("AC-1", "definitely-not-a-command-xyz")])
        gate = FeatureGate()
        result = gate.evaluate(gate.anchor(checklist), timeout_seconds=30)
        assert result.verdict == "fail"
        entry = result.entries[0]
        assert entry["status"] == "fail"
        assert entry["exit_code"] == 127

    def test_tampered_checklist_fails_after_anchor(self, tmp_path: Path) -> None:
        checklist = _write_checklist(tmp_path, [_entry("AC-1", _OK_CMD)])
        gate = FeatureGate()
        anchor = gate.anchor(checklist)
        # Rewrite the checklist after anchoring — moving goalposts (D4).
        checklist.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "items": [_entry("AC-1", _OK_CMD, description="sneaky rewrite")],
                }
            )
        )
        result = gate.evaluate(anchor, timeout_seconds=30)
        assert result.verdict == "fail"
        assert result.computed_sha256 is not None
        assert result.computed_sha256 != result.anchored_sha256
        assert any("checklist_tampered" in v for v in result.violations)


class TestWaiverTraceability:
    """④ — waivers must leave a trace (D9)."""

    def test_waived_entry_never_executes_and_matrix_records_reason(self, tmp_path: Path) -> None:
        checklist = _write_checklist(
            tmp_path,
            [
                _entry("AC-1", _OK_CMD),
                _entry("AC-2", _FAIL_CMD, waive_reason="manual sign-off in PR #42"),
            ],
        )
        gate = FeatureGate()
        result = gate.evaluate(gate.anchor(checklist), timeout_seconds=30)
        # AC-2's command would fail, but the waiver means it never runs.
        assert result.verdict == "pass"
        waived_entry = result.entries[1]
        assert waived_entry["status"] == "waived"
        assert waived_entry["waive_reason"] == "manual sign-off in PR #42"
        assert "command" not in waived_entry
        assert "exit_code" not in waived_entry

    def test_to_dict_exposes_waived_and_gaps_lists(self, tmp_path: Path) -> None:
        checklist = _write_checklist(
            tmp_path,
            [
                _entry("AC-1", _OK_CMD, description="covered"),
                _entry("AC-2", _FAIL_CMD, description="gap", waive_reason="not automated yet"),
                _entry("AC-3", _FAIL_CMD, description="real gap"),
            ],
        )
        gate = FeatureGate()
        result = gate.evaluate(gate.anchor(checklist), timeout_seconds=30)
        data = result.to_dict()
        assert data["verdict"] == "fail"
        assert data["summary"] == {"total": 3, "pass": 1, "fail": 1, "waived": 1}
        assert data["waived"] == [
            {
                "id": "AC-2",
                "description": "gap",
                "waive_reason": "not automated yet",
            }
        ]
        assert data["gaps"] == [{"id": "AC-3", "description": "real gap"}]
        assert data["anchored_sha256"] == data["computed_sha256"]

    def test_blank_waive_reason_is_not_a_waiver(self, tmp_path: Path) -> None:
        checklist = _write_checklist(
            tmp_path,
            [_entry("AC-1", _FAIL_CMD, waive_reason="   ")],
        )
        gate = FeatureGate()
        result = gate.evaluate(gate.anchor(checklist), timeout_seconds=30)
        # Blank waiver normalizes to None → mandatory execution → fail.
        assert result.verdict == "fail"
        assert result.entries[0]["status"] == "fail"


class TestFailClosedBoundaries:
    """⑤ — fail-closed edges: no silent pass, explicit violations (D10)."""

    def test_missing_file_fails_at_evaluate(self, tmp_path: Path) -> None:
        gate = FeatureGate()
        anchor = gate.anchor(tmp_path / "nope.json")
        result = gate.evaluate(anchor, timeout_seconds=30)
        assert result.verdict == "fail"
        assert any("checklist_missing" in v for v in result.violations)

    def test_unparsable_json_fails_with_checklist_invalid(self, tmp_path: Path) -> None:
        checklist = _write_checklist(tmp_path, "{broken", schema_version=_RAW)  # type: ignore[arg-type]
        gate = FeatureGate()
        result = gate.evaluate(gate.anchor(checklist), timeout_seconds=30)
        assert result.verdict == "fail"
        assert any("checklist_invalid" in v for v in result.violations)

    def test_unknown_schema_version_fails(self, tmp_path: Path) -> None:
        checklist = _write_checklist(tmp_path, [_entry("AC-1", _OK_CMD)], schema_version=99)
        gate = FeatureGate()
        result = gate.evaluate(gate.anchor(checklist), timeout_seconds=30)
        assert result.verdict == "fail"
        assert any("schema_version" in v for v in result.violations)

    def test_empty_items_fails(self, tmp_path: Path) -> None:
        checklist = _write_checklist(tmp_path, [])
        gate = FeatureGate()
        result = gate.evaluate(gate.anchor(checklist), timeout_seconds=30)
        assert result.verdict == "fail"
        assert any("items" in v for v in result.violations)

    def test_duplicate_ids_fail(self, tmp_path: Path) -> None:
        checklist = _write_checklist(
            tmp_path,
            [_entry("AC-1", _OK_CMD), _entry("AC-1", _OK_CMD, description="duplicate")],
        )
        gate = FeatureGate()
        result = gate.evaluate(gate.anchor(checklist), timeout_seconds=30)
        assert result.verdict == "fail"
        assert any("duplicate id" in v for v in result.violations)

    def test_unknown_verify_kind_fails(self, tmp_path: Path) -> None:
        checklist = _write_checklist(tmp_path, [_entry("AC-1", _OK_CMD, kind="pytest-selector")])
        gate = FeatureGate()
        result = gate.evaluate(gate.anchor(checklist), timeout_seconds=30)
        assert result.verdict == "fail"
        assert any("verify.kind" in v for v in result.violations)

    def test_missing_verify_fails(self, tmp_path: Path) -> None:
        checklist = _write_checklist(tmp_path, [_entry("AC-1", _OK_CMD, drop_verify=True)])
        gate = FeatureGate()
        result = gate.evaluate(gate.anchor(checklist), timeout_seconds=30)
        assert result.verdict == "fail"
        assert any("'verify'" in v for v in result.violations)


class TestResultContract:
    """to_dict / internal_error contract consumed by details + audit."""

    def test_internal_error_is_fail_closed(self) -> None:
        result = FeatureGateResult.internal_error("gate exploded")
        assert result.verdict == "fail"
        assert result.passed is False
        assert result.error == "gate exploded"
        assert result.violations == ["gate_error: gate exploded"]

    def test_to_dict_shape(self, tmp_path: Path) -> None:
        checklist = _write_checklist(tmp_path, [_entry("AC-1", _OK_CMD)])
        gate = FeatureGate()
        data = gate.evaluate(gate.anchor(checklist), timeout_seconds=30).to_dict()
        expected_keys = {
            "verdict",
            "checklist_path",
            "anchored_sha256",
            "computed_sha256",
            "command_timeout_seconds",
            "summary",
            "entries",
            "violations",
            "gaps",
            "waived",
            "error",
        }
        assert expected_keys == set(data.keys())
        assert data["verdict"] == "pass"
        assert data["gaps"] == []
        assert data["waived"] == []

    def test_default_checklist_path_constant(self) -> None:
        assert DEFAULT_CHECKLIST_PATH == ".devsquad/acceptance_checklist.json"


class TestCliKwargsInjection:
    """CLI wiring: _build_dispatch_kwargs reads .devsquad.yaml feature_gate."""

    @staticmethod
    def _args(**overrides: Any) -> Any:
        from argparse import Namespace

        defaults: dict[str, Any] = {
            "persist_dir": "/tmp/fg_cli_test",
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
        return Namespace(**defaults)

    def test_disabled_yaml_injects_nothing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
        assert "enable_feature_gate" not in kwargs

    def test_enabled_yaml_injects_gate_kwargs(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from scripts.cli_dispatch import _build_dispatch_kwargs
        from scripts.collaboration.config_manager import ConfigManager

        yaml_path = tmp_path / ".devsquad.yaml"
        yaml_path.write_text(
            "backend: mock\n"
            "feature_gate:\n"
            "  enabled: true\n"
            "  checklist: .devsquad/my_checklist.json\n"
            "  command_timeout_seconds: 45\n"
        )
        monkeypatch.setenv("DEVSQUAD_CONFIG_PATH", str(yaml_path))
        ConfigManager.reset()
        try:
            kwargs, err = _build_dispatch_kwargs(self._args())
        finally:
            ConfigManager.reset()
        assert err is None
        assert kwargs["enable_feature_gate"] is True
        assert kwargs["feature_gate_checklist"] == ".devsquad/my_checklist.json"
        assert kwargs["feature_gate_command_timeout_seconds"] == 45
