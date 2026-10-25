#!/usr/bin/env python3
"""DefectLedger — cross-run defect lifecycle ledger (V4.9.0 P2-W1).

A project-level single-file ledger (``.devsquad/defects.json``) that turns
run-scoped signals (dispatch audit findings / failure classes) into
cross-run lifecycle objects with a closed state machine::

    open --(update)--> fixed --(close, run verified)--> closed
    fixed --(refix)--> fixed;  closed --(reopen)--> open

Design: ``docs/planning/V4.9.0_W1_defect-ledger_DESIGN.md`` (frozen 2026-10-25).

Two upstream defects are structurally prevented (PRD §5): lost transitions
(atomic writes + fail-closed load validation, never silently repairs) and
ID reuse (allocation only via a monotonic ``next_id`` persisted in the same
atomic write; ``add`` accepts no id, ``next_id`` never moves backwards).

Signal references (§5.1): ``audit:event=<N>&finding=<i>`` (0-based index
into the event's ``findings``) and ``audit:event=<N>&failure=<class>`` (the
event's ``failure_class`` must match) — both resolved against the SQLite
dispatch audit DB. The ``audit:`` prefix is the W2 extension point. Pure
stdlib; no LLM; deterministic.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import sqlite3
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

__all__ = ["DefectLedger", "Defect", "DefectState", "DefectLedgerError"]

SCHEMA_VERSION = 1
DEFAULT_LEDGER_PATH = ".devsquad/defects.json"
DEFAULT_AUDIT_DB_PATH = "audit/dispatch_audit.db"

_ID_PATTERN = re.compile(r"^DEF-(\d+)$")
_EVENT_REF_PATTERN = re.compile(r"^audit:event=(\d+)$")

# Closed state machine (design §4.1): (from_state, transition) -> to_state.
_LEGAL_TRANSITIONS: dict[tuple[str, str], str] = {
    ("open", "fix"): "fixed",
    ("fixed", "refix"): "fixed",
    ("fixed", "close"): "closed",
    ("closed", "reopen"): "open",
}

# Exit-code semantics (failure_taxonomy C19) reused at the CLI boundary.
PRODUCT_FAILED_EXIT = 1
ENVIRONMENT_BLOCKED_EXIT = 2


class DefectLedgerError(ValueError):
    """Raised on state-machine violations, load-validation failures,
    unresolvable signal references — every refusal is fail-closed."""


class DefectState(str, Enum):
    """Closed set of lifecycle states (``regressed`` is a reopen reason,
    not a state)."""

    OPEN = "open"
    FIXED = "fixed"
    CLOSED = "closed"


@dataclass
class Defect:
    """One ledger entry; the current state is the tail of ``history``."""

    id: str
    state: DefectState
    signal: dict[str, Any]
    fix: dict[str, Any] | None = None
    regression: dict[str, Any] | None = None
    reopen_reason: str | None = None
    created_at: str = ""
    history: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the on-disk entry shape (JSON-compatible)."""
        return {
            "id": self.id,
            "state": self.state.value,
            "signal": self.signal,
            "fix": self.fix,
            "regression": self.regression,
            "reopen_reason": self.reopen_reason,
            "created_at": self.created_at,
            "history": self.history,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Defect:
        """Rebuild an entry from the on-disk shape."""
        return cls(
            id=data["id"],
            state=DefectState(data["state"]),
            signal=data["signal"],
            fix=data.get("fix"),
            regression=data.get("regression"),
            reopen_reason=data.get("reopen_reason"),
            created_at=data.get("created_at", ""),
            history=list(data.get("history", [])),
        )


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _parse_signal_ref(signal_ref: str) -> dict[str, str | int]:
    """Parse ``audit:event=<N>&finding=<i>`` / ``audit:event=<N>&failure=<class>``.

    Raises :class:`DefectLedgerError` on any other shape.
    """
    if not signal_ref.startswith("audit:"):
        raise DefectLedgerError(f"unsupported signal_ref {signal_ref!r}: W1 supports 'audit:' refs only")
    body = signal_ref[len("audit:") :]
    event_part, sep, selector = body.partition("&")
    if not sep:
        raise DefectLedgerError(f"malformed signal_ref {signal_ref!r}: missing selector")
    match = re.fullmatch(r"event=(\d+)", event_part)
    if not match:
        raise DefectLedgerError(f"malformed signal_ref {signal_ref!r}: expected 'event=<N>'")
    event_id = int(match.group(1))
    finding = re.fullmatch(r"finding=(\d+)", selector)
    if finding:
        return {"event": event_id, "finding": int(finding.group(1))}
    failure = re.fullmatch(r"failure=([a-z_]+)", selector)
    if failure:
        return {"event": event_id, "failure": failure.group(1)}
    raise DefectLedgerError(f"malformed signal_ref {signal_ref!r}: expected 'finding=<i>' or 'failure=<class>'")


@dataclass
class _LedgerFile:
    """In-memory shape of the ledger file."""

    next_id: int = 1
    entries: list[Defect] = field(default_factory=list)


class DefectLedger:
    """Project-level defect ledger with a closed state machine.

    Every public command loads the file first (fail-closed validation),
    applies one transition, and persists via an atomic write. Pure stdlib.
    """

    def __init__(
        self,
        ledger_path: str | Path = DEFAULT_LEDGER_PATH,
        audit_db_path: str | Path = DEFAULT_AUDIT_DB_PATH,
    ) -> None:
        self.ledger_path = Path(ledger_path)
        self.audit_db_path = Path(audit_db_path)

    # ------------------------------------------------------------------
    # Persistence (design §6.1: atomic writes, fail-closed load)
    # ------------------------------------------------------------------

    def _load(self) -> _LedgerFile:
        """Load and validate the ledger; missing file means empty ledger."""
        if not self.ledger_path.exists():
            return _LedgerFile()
        raw = self.ledger_path.read_text(encoding="utf-8")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise DefectLedgerError(f"ledger {self.ledger_path} is not valid JSON (truncated write?): {exc}") from exc
        if not isinstance(data, dict):
            raise DefectLedgerError(f"ledger {self.ledger_path}: top level must be an object")
        version = data.get("schema_version")
        if version != SCHEMA_VERSION:
            raise DefectLedgerError(
                f"ledger schema_version {version!r} is not supported "
                f"(expected {SCHEMA_VERSION}); upgrade DevSquad first"
            )
        next_id = data.get("next_id")
        entries_raw = data.get("entries")
        if not isinstance(next_id, int) or next_id < 1:
            raise DefectLedgerError("ledger 'next_id' must be a positive integer")
        if not isinstance(entries_raw, list):
            raise DefectLedgerError("ledger 'entries' must be a list")
        entries = [Defect.from_dict(e) for e in entries_raw]
        self._validate(entries, next_id)
        return _LedgerFile(next_id=next_id, entries=entries)

    def _validate(self, entries: list[Defect], next_id: int) -> None:
        """Fail-closed invariants (design §6.1.2 + §6.2). No silent repair."""
        seen_ids: set[str] = set()
        for entry in entries:
            match = _ID_PATTERN.match(entry.id)
            if not match:
                raise DefectLedgerError(f"invalid defect id {entry.id!r}")
            if entry.id in seen_ids:
                raise DefectLedgerError(f"duplicate defect id {entry.id}")
            seen_ids.add(entry.id)
            if int(match.group(1)) >= next_id:
                raise DefectLedgerError(f"{entry.id}: id >= next_id ({next_id}) — ID reuse detected, refusing")
            if not entry.history:
                raise DefectLedgerError(f"{entry.id}: empty history — state cannot be derived")
            create = entry.history[0]
            if create.get("transition") != "create" or create.get("to") != "open":
                raise DefectLedgerError(f"{entry.id}: history must start with create->open")
            tail = entry.history[-1]
            if tail.get("to") != entry.state.value:
                raise DefectLedgerError(
                    f"{entry.id}: state '{entry.state.value}' != history tail "
                    f"'{tail.get('to')}' — lost transition suspected, refusing"
                )

    def _save(self, ledger: _LedgerFile) -> None:
        """Atomic write: tempfile in the same directory, fsync, os.replace."""
        payload = {
            "schema_version": SCHEMA_VERSION,
            "next_id": ledger.next_id,
            "entries": [e.to_dict() for e in ledger.entries],
        }
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=str(self.ledger_path.parent), prefix=".defects-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, self.ledger_path)
        except BaseException:
            with contextlib.suppress(OSError):
                os.unlink(tmp_name)
            raise

    # ------------------------------------------------------------------
    # Audit DB (read-only consumption, design §5)
    # ------------------------------------------------------------------

    def _open_audit_db(self) -> sqlite3.Connection:
        if not self.audit_db_path.exists():
            raise DefectLedgerError(
                f"audit DB not found at {self.audit_db_path} — run a dispatch first "
                "(fail-closed: no skip-verification path exists)"
            )
        return sqlite3.connect(f"file:{self.audit_db_path}?mode=ro", uri=True)

    def _fetch_event(self, conn: sqlite3.Connection, event_id: int) -> tuple[float, dict[str, Any]]:
        row = conn.execute("SELECT timestamp, details FROM dispatch_audit WHERE id = ?", (event_id,)).fetchone()
        if row is None:
            raise DefectLedgerError(f"audit event {event_id} not found — signal must be real")
        try:
            details = json.loads(row[1])
        except (TypeError, json.JSONDecodeError) as exc:
            raise DefectLedgerError(f"audit event {event_id}: details is not valid JSON") from exc
        if not isinstance(details, dict):
            raise DefectLedgerError(f"audit event {event_id}: details must be a JSON object")
        return float(row[0]), details

    def _resolve_signal(self, signal_ref: str) -> tuple[str, str]:
        """Resolve a signal reference against the audit DB.

        Returns ``(signal_type, captured_at)``; raises on any failure —
        filing a defect without a resolvable signal is forbidden.
        """
        parsed = _parse_signal_ref(signal_ref)
        conn = self._open_audit_db()
        try:
            timestamp, details = self._fetch_event(conn, int(parsed["event"]))
        finally:
            conn.close()
        if "finding" in parsed:
            findings = details.get("findings")
            index = int(parsed["finding"])
            if not isinstance(findings, list) or not 0 <= index < len(findings):
                raise DefectLedgerError(
                    f"audit event {parsed['event']}: finding index {index} not in "
                    "details['findings'] — signal must be real"
                )
            signal_type = "review:finding"
        else:
            recorded = details.get("failure_class")
            if recorded != parsed["failure"]:
                raise DefectLedgerError(
                    f"audit event {parsed['event']}: failure_class {recorded!r} != "
                    f"{parsed['failure']!r} — signal must be real"
                )
            signal_type = f"failure:{parsed['failure']}"
        captured_at = datetime.fromtimestamp(timestamp).astimezone().isoformat(timespec="seconds")
        return signal_type, captured_at

    def _verify_run_ref(self, run_ref: str) -> str:
        """Regression check before close (design §5.2).

        The run must be an ``audit:event=<N>`` with no product_failed signal
        and no critical findings; environment_blocked does not count.
        """
        match = _EVENT_REF_PATTERN.match(run_ref)
        if not match:
            raise DefectLedgerError(f"malformed run_ref {run_ref!r}: expected 'audit:event=<N>'")
        event_id = int(match.group(1))
        conn = self._open_audit_db()
        try:
            _, details = self._fetch_event(conn, event_id)
        finally:
            conn.close()
        if details.get("failure_class") == "product_failed":
            raise DefectLedgerError(f"cannot close: regression run audit:event={event_id} has a product_failed signal")
        findings = details.get("findings")
        if isinstance(findings, list):
            critical = [f for f in findings if isinstance(f, dict) and f.get("severity") == "critical"]
            if critical:
                raise DefectLedgerError(
                    f"cannot close: regression run audit:event={event_id} has {len(critical)} critical finding(s)"
                )
        return run_ref

    # ------------------------------------------------------------------
    # Commands (design §4)
    # ------------------------------------------------------------------

    def add(self, signal_ref: str, summary: str) -> Defect:
        """create->open. The signal reference must resolve (no free-form filing)."""
        if not summary or not summary.strip():
            raise DefectLedgerError("add requires a non-empty --summary")
        signal_type, captured_at = self._resolve_signal(signal_ref)
        ledger = self._load()
        defect_id = f"DEF-{ledger.next_id:03d}"
        entry = Defect(
            id=defect_id,
            state=DefectState.OPEN,
            signal={
                "type": signal_type,
                "ref": signal_ref,
                "summary": summary.strip(),
                "captured_at": captured_at,
            },
            created_at=_now(),
            history=[
                {
                    "transition": "create",
                    "from": None,
                    "to": "open",
                    "at": _now(),
                    "fields": {"signal_type": signal_type, "signal_ref": signal_ref},
                }
            ],
        )
        ledger.entries.append(entry)
        ledger.next_id += 1
        self._save(ledger)
        return entry

    def update(self, defect_id: str, commit_sha: str, summary: str) -> Defect:
        """open->fixed (or fixed->fixed refix). Mandatory: commit + summary."""
        if not commit_sha or not commit_sha.strip():
            raise DefectLedgerError("update requires a non-empty --commit")
        if not summary or not summary.strip():
            raise DefectLedgerError("update requires a non-empty --summary")
        ledger = self._load()
        entry = self._find(ledger, defect_id)
        if entry.state is DefectState.CLOSED:
            raise DefectLedgerError(f"illegal transition closed->fixed for {defect_id} (reopen first)")
        transition = "fix" if entry.state is DefectState.OPEN else "refix"
        self._transition(ledger, entry, transition, commit_sha.strip(), summary.strip())
        return entry

    def close(self, defect_id: str, run_ref: str) -> Defect:
        """fixed->closed. The regression run must verify clean (§5.2)."""
        if not run_ref or not run_ref.strip():
            raise DefectLedgerError("close requires a non-empty --run-ref")
        run_ref = run_ref.strip()
        ledger = self._load()
        entry = self._find(ledger, defect_id)
        if entry.state is DefectState.OPEN:
            raise DefectLedgerError(f"illegal transition open->closed (skip-state): fix {defect_id} first")
        if entry.state is DefectState.CLOSED:
            raise DefectLedgerError(f"{defect_id} is already closed")
        self._verify_run_ref(run_ref)
        at = _now()
        entry.regression = {"run_ref": run_ref, "at": at}
        entry.state = DefectState.CLOSED
        entry.history.append(
            {"transition": "close", "from": "fixed", "to": "closed", "at": at, "fields": {"run_ref": run_ref}}
        )
        self._save(ledger)
        return entry

    def reopen(self, defect_id: str, reason: str) -> Defect:
        """closed->open (regressed). Mandatory reason; old fix/regression
        values are preserved into history before being cleared."""
        if not reason or not reason.strip():
            raise DefectLedgerError("reopen requires a non-empty --reason")
        ledger = self._load()
        entry = self._find(ledger, defect_id)
        if entry.state is not DefectState.CLOSED:
            raise DefectLedgerError(f"illegal transition {entry.state.value}->open (reopen is closed->open only)")
        at = _now()
        entry.history.append(
            {
                "transition": "reopen",
                "from": "closed",
                "to": "open",
                "at": at,
                "fields": {
                    "reason": reason.strip(),
                    "cleared_fix": entry.fix,
                    "cleared_regression": entry.regression,
                },
            }
        )
        entry.fix = None
        entry.regression = None
        entry.reopen_reason = reason.strip()
        entry.state = DefectState.OPEN
        self._save(ledger)
        return entry

    def list_defects(self, state: str | None = None) -> list[Defect]:
        """List entries, optionally filtered by state."""
        ledger = self._load()
        if state is None:
            return list(ledger.entries)
        wanted = DefectState(state)
        return [e for e in ledger.entries if e.state is wanted]

    def audit_report(self) -> list[str]:
        """Cross-check invariants (design §6.2.2); empty list = clean."""
        issues: list[str] = []
        try:
            ledger = self._load()
        except DefectLedgerError as exc:
            return [str(exc)]
        seen: set[str] = set()
        for entry in ledger.entries:
            if entry.id in seen:
                issues.append(f"{entry.id}: duplicate id")
            seen.add(entry.id)
            match = _ID_PATTERN.match(entry.id)
            if match and int(match.group(1)) >= ledger.next_id:
                issues.append(f"{entry.id}: id >= next_id ({ledger.next_id})")
            if not any(h.get("transition") == "create" for h in entry.history):
                issues.append(f"{entry.id}: history has no create record")
            tail = entry.history[-1]["to"] if entry.history else None
            if tail != entry.state.value:
                issues.append(f"{entry.id}: state/history mismatch")
        return issues

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _find(self, ledger: _LedgerFile, defect_id: str) -> Defect:
        for entry in ledger.entries:
            if entry.id == defect_id:
                return entry
        raise DefectLedgerError(f"defect not found: {defect_id}")

    def _transition(self, ledger: _LedgerFile, entry: Defect, transition: str, commit_sha: str, summary: str) -> None:
        from_state = entry.state.value
        to_state = _LEGAL_TRANSITIONS.get((from_state, transition))
        if to_state is None:
            raise DefectLedgerError(f"illegal transition {from_state}->{transition} for {entry.id}")
        at = _now()
        entry.fix = {"commit": commit_sha, "summary": summary, "at": at}
        entry.state = DefectState(to_state)
        entry.history.append(
            {
                "transition": transition,
                "from": from_state,
                "to": to_state,
                "at": at,
                "fields": {"commit": commit_sha, "summary": summary},
            }
        )
        self._save(ledger)
