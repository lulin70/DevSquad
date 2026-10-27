#!/usr/bin/env python3
"""V4.9.0 P2-W3 registration gate — e2e scenario runner (design §7 ⑭).

Drives the production dispatch pipeline (`MultiAgentDispatcher.dispatch`,
deterministic local backends — no network, no API key) plus the REAL
user command surface (`scripts/cli.py defect add/update/close/reopen`)
in isolated temp workspaces. The ledger path is the production default
`.devsquad/defects.json` resolved from the workspace CWD (D5).

Scenarios (one fresh workspace each):
  A  red → file → tracked → green
     A1 failing run, empty ledger      → gate FAIL (unregistered), run red
     file DEF-001 from A1's real audit dispatch_end event (CLI)
     A2 same failure, DEF live         → gate PASS (tracked), run red from
                                          the defect itself — the gate never
                                          masks the run's own failure
     A3 fixed run                      → run green, gate PASS (0 signals)
  B  regressed → reopen → tracked
     seed a full DEF lifecycle via CLI (add → update → close on a clean run)
     B1 failing run, only closed DEF   → gate FAIL (regressed) with reopen
                                          guidance
     reopen DEF-001 (CLI)
     B2 same failing run               → gate PASS (tracked), run red
  C  disabled zero trace
     C1 failing run, gate off          → run red from the worker failure,
                                          ZERO registration-gate trace in
                                          details / Markdown / audit event

Every assertion failing exits non-zero — this script is both the
scenario driver and its own verification harness. Reports are the raw
`result.to_markdown()` of each run (W4 evidence format).

Run:  .venv/bin/python docs/e2e_evidence/V4.9.0_W3_registration_gate_e2e/run_e2e.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from scripts.collaboration.dispatch_audit import DispatchAuditLogger  # noqa: E402
from scripts.collaboration.dispatcher import MultiAgentDispatcher  # noqa: E402

_EVIDENCE_DIR = Path(__file__).resolve().parent

_FAILURES: list[str] = []


class _FailBackend:
    """Every call fails deterministically (no environment marker → product_failed)."""

    model = "w3-e2e-fail-model"

    def is_available(self) -> bool:
        return True

    def generate(self, prompt: str, **kwargs: Any) -> str:
        raise RuntimeError("deterministic product failure")

    def generate_stream(self, prompt: str, **kwargs: Any):
        raise RuntimeError("deterministic product failure")
        yield ""  # pragma: no cover


class _OkBackend:
    model = "w3-e2e-ok-model"

    def is_available(self) -> bool:
        return True

    def generate(self, prompt: str, **kwargs: Any) -> str:
        return "Structured answer: 4"

    def generate_stream(self, prompt: str, **kwargs: Any):
        yield "Structured answer: 4"


class _Workspace:
    """A temp project directory the dispatch runs inside (chdir)."""

    def __init__(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()  # noqa: SIM115
        self.root = Path(self._tmp.name)
        (self.root / ".devsquad").mkdir()
        (self.root / "audit").mkdir()
        self._old_cwd: str | None = None

    def __enter__(self) -> _Workspace:
        self._old_cwd = os.getcwd()
        os.chdir(self.root)
        return self

    def __exit__(self, *_exc: object) -> None:
        assert self._old_cwd is not None
        os.chdir(self._old_cwd)
        self._tmp.cleanup()

    # -- helpers ---------------------------------------------------------

    def dispatch(self, backend: Any, *, enable_registration_gate: bool, task: str) -> Any:
        # A fresh audit logger per run: dispatcher.shutdown() closes the
        # injected logger, and a fresh one reloads the chain + keeps
        # writing rows to the same sqlite file (correct event ids).
        audit = DispatchAuditLogger(db_path=self.root / "audit" / "dispatch_audit.db")
        disp = MultiAgentDispatcher(
            llm_backend=backend,
            audit_logger=audit,
            enable_memory=False,
            enable_registration_gate=enable_registration_gate,
        )
        try:
            return disp.dispatch(task, roles=["architect"])
        finally:
            disp.shutdown()
            audit.close()

    def last_end_event_id(self) -> int:
        """The DB row id of the newest dispatch_end event (signal-ref source)."""
        import sqlite3

        conn = sqlite3.connect(self.root / "audit" / "dispatch_audit.db")
        try:
            row = conn.execute(
                "SELECT id FROM dispatch_audit WHERE event_type = 'dispatch_end' ORDER BY id DESC LIMIT 1"
            ).fetchone()
        finally:
            conn.close()
        assert row, "no dispatch_end event recorded"
        return int(row[0])

    def end_event(self, event_id: int) -> dict:
        import json as _json
        import sqlite3

        conn = sqlite3.connect(self.root / "audit" / "dispatch_audit.db")
        try:
            row = conn.execute("SELECT details FROM dispatch_audit WHERE id = ?", (event_id,)).fetchone()
        finally:
            conn.close()
        assert row, f"dispatch_end event {event_id} not found"
        return _json.loads(row[0])

    def defect_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        proc = subprocess.run(
            [
                sys.executable,
                str(_REPO_ROOT / "scripts" / "cli.py"),
                "defect",
                *args,
                "--ledger-path",
                str(self.root / ".devsquad" / "defects.json"),
                "--audit-db-path",
                str(self.root / "audit" / "dispatch_audit.db"),
            ],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(_REPO_ROOT),
        )
        if proc.returncode != 0:
            raise AssertionError(f"defect CLI failed ({proc.returncode}): {' '.join(args)}\n{proc.stderr}")
        return proc

    @property
    def ledger_json(self) -> dict:
        import json

        return json.loads((self.root / ".devsquad" / "defects.json").read_text(encoding="utf-8"))


def _check(label: str, condition: bool, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {label}" + (f" — {detail}" if detail and not condition else ""))
    if not condition:
        _FAILURES.append(label)


def _write_report(name: str, markdown: str) -> None:
    path = _EVIDENCE_DIR / name
    path.write_text(markdown, encoding="utf-8")
    print(f"  report → {name}")


def scenario_a() -> None:
    print("\nScenario A — red → file (CLI) → tracked → green")
    with _Workspace() as ws:
        # A1: failing run, empty ledger → gate FAIL (unregistered).
        a1 = ws.dispatch(_FailBackend(), enable_registration_gate=True, task="Compute 2+2 (broken build)")
        _write_report("run_a1_report.md", a1.to_markdown())
        gate = a1.details.get("registration_gate", {})
        _check("A1 run red", not a1.success)
        _check("A1 gate verdict fail", gate.get("verdict") == "fail")
        _check(
            "A1 signal unregistered",
            gate.get("signals")
            == [
                {
                    "type": "failure:product_failed",
                    "status": "unregistered",
                    "tracked_by": [],
                    "closed_ids": [],
                }
            ],
        )
        _check("A1 C19 product_failed", a1.details.get("failure_class") == "product_failed")
        a1_end = ws.last_end_event_id()
        _check(
            "A1 audit carries gate verdict",
            ws.end_event(a1_end).get("registration_gate", {}).get("verdict") == "fail",
        )

        # File DEF-001 from A1's real dispatch_end event (user CLI surface).
        ws.defect_cli(
            "add",
            "--signal-ref",
            f"audit:event={a1_end}&failure=product_failed",
            "--summary",
            "deterministic product failure in worker path",
        )
        _check("A DEF-001 filed open", ws.ledger_json["entries"][0]["state"] == "open")

        # A2: same failure, DEF live → gate PASS (tracked), run still red.
        a2 = ws.dispatch(_FailBackend(), enable_registration_gate=True, task="Compute 2+2 (broken build)")
        _write_report("run_a2_report.md", a2.to_markdown())
        gate = a2.details.get("registration_gate", {})
        _check("A2 run red from the defect itself", not a2.success)
        _check("A2 gate verdict pass", gate.get("verdict") == "pass")
        _check(
            "A2 signal tracked by DEF-001",
            gate.get("signals", [{}])[0].get("tracked_by") == ["DEF-001"],
        )
        _check("A2 no gate errors", not any("Registration gate blocked" in e for e in a2.errors))

        # A3: fixed run → green, gate PASS (0 mandatory signals).
        a3 = ws.dispatch(_OkBackend(), enable_registration_gate=True, task="Compute 2+2 (fixed)")
        _write_report("run_a3_report.md", a3.to_markdown())
        gate = a3.details.get("registration_gate", {})
        _check("A3 run green", a3.success)
        _check("A3 gate verdict pass", gate.get("verdict") == "pass")
        _check("A3 zero mandatory signals", gate.get("summary", {}).get("mandatory") == 0)
        _check("A3 failure_class none", a3.details.get("failure_class") == "none")


def scenario_b() -> None:
    print("\nScenario B — regressed (closed DEF) → reopen (CLI) → tracked")
    with _Workspace() as ws:
        # Seed: a failing run (product_failed event) + a clean run (close ref).
        ws.dispatch(_FailBackend(), enable_registration_gate=False, task="Seed failing run")
        fail_event = ws.last_end_event_id()
        ws.dispatch(_OkBackend(), enable_registration_gate=False, task="Seed clean run")
        clean_event = ws.last_end_event_id()

        # Full W1 lifecycle via the user CLI: add → update → close.
        ws.defect_cli(
            "add",
            "--signal-ref",
            f"audit:event={fail_event}&failure=product_failed",
            "--summary",
            "seed defect for regression scenario",
        )
        ws.defect_cli("update", "DEF-001", "--commit", "abc123", "--summary", "register the fix")
        ws.defect_cli("close", "DEF-001", "--run-ref", f"audit:event={clean_event}")
        _check("B DEF-001 closed", ws.ledger_json["entries"][0]["state"] == "closed")

        # B1: failing run → only closed tickets → regressed FAIL.
        b1 = ws.dispatch(_FailBackend(), enable_registration_gate=True, task="Compute 2+2 (regression)")
        _write_report("run_b1_report.md", b1.to_markdown())
        gate = b1.details.get("registration_gate", {})
        _check("B1 run red", not b1.success)
        _check("B1 gate verdict fail", gate.get("verdict") == "fail")
        signal = (gate.get("signals") or [{}])[0]
        _check("B1 signal regressed", signal.get("status") == "regressed")
        _check("B1 closed_ids DEF-001", signal.get("closed_ids") == ["DEF-001"])
        _check(
            "B1 violation carries reopen guidance",
            any("regressed" in v and "reopen" in v for v in gate.get("violations", [])),
        )

        # Reopen via CLI, then B2: same failing run → tracked PASS.
        ws.defect_cli("reopen", "DEF-001", "--reason", "regression reproduced by scenario B")
        b2 = ws.dispatch(_FailBackend(), enable_registration_gate=True, task="Compute 2+2 (regression)")
        _write_report("run_b2_report.md", b2.to_markdown())
        gate = b2.details.get("registration_gate", {})
        _check("B2 run red from the defect", not b2.success)
        _check("B2 gate verdict pass", gate.get("verdict") == "pass")
        _check(
            "B2 signal tracked by reopened DEF-001",
            (gate.get("signals") or [{}])[0].get("tracked_by") == ["DEF-001"],
        )


def scenario_c() -> None:
    print("\nScenario C — disabled (default): zero trace on a red run")
    with _Workspace() as ws:
        c1 = ws.dispatch(_FailBackend(), enable_registration_gate=False, task="Compute 2+2 (gate off)")
        _write_report("run_c_report.md", c1.to_markdown())
        _check("C1 run red from the worker failure", not c1.success)
        _check("C1 C19 product_failed (W2 baseline intact)", c1.details.get("failure_class") == "product_failed")
        # Five zero-trace faces (design §5).
        _check("C1 no details key", "registration_gate" not in c1.details)
        _check("C1 result attribute None", c1.registration_gate is None)
        _check("C1 to_dict None", c1.to_dict().get("registration_gate") is None)
        _check("C1 no Markdown section", "Registration gate" not in c1.to_markdown())
        end = ws.end_event(ws.last_end_event_id())
        _check("C1 audit event has no key", "registration_gate" not in end)
        _check("C1 audit W2 baseline", end.get("failure_class") == "product_failed")


def main() -> int:
    scenario_a()
    scenario_b()
    scenario_c()
    print(f"\n{'=' * 60}")
    if _FAILURES:
        print(f"E2E FAILED — {len(_FAILURES)} assertion(s):")
        for failure in _FAILURES:
            print(f"  - {failure}")
        return 1
    print("E2E PASSED — all scenario assertions green; reports written to:")
    print(f"  {_EVIDENCE_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
