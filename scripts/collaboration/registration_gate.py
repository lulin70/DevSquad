#!/usr/bin/env python3
"""RegistrationGate — V4.9.0 P2-W3: fail-closed signal-no-evaporation gate.

A dispatch run whose terminal state carries a mandatory signal
(``failure:product_failed`` or a BV-critical review finding category)
cannot finish green while that signal type has no live DEF ticket
(state ``open`` or ``fixed``) in ``.devsquad/defects.json``. Run-scoped
signals used to evaporate at run end; with the ledger enabled, the gate
holds the run red until the signal is tracked (PRD §4.3 first
principle: signals must not evaporate).

Design authority: ``docs/planning/V4.9.0_W3_registration-gate_DESIGN.md``.

Semantics (design §3):
    - Signals are computed live at Step 23.6 from the terminal state in
      scope — ``failure_class_for_dispatch(worker_results, errors_so_far)``
      plus the two-stage-review findings — never from worker self-reports
      (D2). Gate-own errors are injected after extraction, so the gate
      never demands a ticket for its own failure (no self-reference).
    - Matching is signal-type level (D3, v1 boundary): one live ticket of
      a type covers that type's occurrences; root-cause distinction is
      human triage.
    - A "live" ticket is ``open`` or ``fixed`` (D4): ``fixed`` is still
      tracked (fix registered, regression verification pending — the W1
      close contract blocks verbal closes); ``closed`` + present signal
      means regression → reopen.
    - Fail-closed (D7): a corrupt/unreadable ledger is a gate-internal
      error → FAIL; a missing ledger is a legal empty ledger → every
      mandatory signal is unregistered → FAIL. No silent pass exists.
    - No SHA256 anchoring (D8): the ledger is a live cross-run store —
      filing against earlier runs while a dispatch executes is legal, so
      hash anchoring would misjudge legitimate writes (unlike W4's frozen
      checklist contract).

Also provides :func:`unfiled_signal_report` — the advisory half of the
registration story (D11): non-mandatory signal types (BV warning + spec
categories) seen in the audit DB without a live ticket are listed by
``devsquad defect audit`` without affecting its exit code. The category
mapping reuses the W2 §4.1 rule (BV code → ``review:break-vuln:<ID>``,
else ``review:spec:<category>``); ``defect_ledger.py`` is frozen by
design D12, so the rule is restated here against the same
``review_taxonomy`` source. Pure stdlib; no LLM; deterministic.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .defect_ledger import (
    DEFAULT_AUDIT_DB_PATH,
    DEFAULT_LEDGER_PATH,
    DefectLedger,
    DefectLedgerError,
    mandatory_signal_types,
)
from .failure_taxonomy import FailureClass, failure_class_for_dispatch
from .review_taxonomy import BV_CATEGORIES, BV_CRITICAL
from .two_stage_review_gate import ReviewFinding

__all__ = [
    "RegistrationGate",
    "RegistrationGateResult",
    "unfiled_signal_report",
]

_BV_CODES: frozenset[str] = frozenset(c.code for c in BV_CATEGORIES)
_LIVE_STATES = ("open", "fixed")


@dataclass
class RegistrationGateResult:
    """Outcome of one registration-gate evaluation (Step 23.6).

    ``verdict`` is ``"pass"`` iff every mandatory signal extracted from
    the run is ``tracked``; ``unregistered`` (no ticket at all) and
    ``regressed`` (only closed tickets — reopen required) both FAIL
    (D4/D6). ``signals`` carries the per-type tri-state matrix;
    ``violations`` the human-readable failure reasons with filing
    guidance (the run's dispatch_end audit event is where the filing
    signal-ref lives — W2 persisted findings/failure_class there);
    ``error`` is non-None only for gate-internal failures (fail-closed,
    D7).
    """

    verdict: str
    ledger_path: str
    signals: list[dict[str, Any]] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def passed(self) -> bool:
        return self.verdict == "pass"

    def to_dict(self) -> dict[str, Any]:
        """Serialize for ``details["registration_gate"]`` / audit events (D9)."""
        counts = {"tracked": 0, "unregistered": 0, "regressed": 0}
        for signal in self.signals:
            status = signal.get("status")
            if status in counts:
                counts[status] += 1
        return {
            "verdict": self.verdict,
            "ledger_path": self.ledger_path,
            "summary": {"mandatory": len(self.signals), **counts},
            "signals": [dict(signal) for signal in self.signals],
            "violations": list(self.violations),
            "error": self.error,
        }

    @classmethod
    def internal_error(cls, message: str, ledger_path: str = "unknown") -> RegistrationGateResult:
        """Fail-closed result for gate-internal errors (never a silent pass)."""
        return cls(
            verdict="fail",
            ledger_path=ledger_path,
            error=message,
            violations=[f"gate_error: {message}"],
        )


class RegistrationGate:
    """Mandatory-signal registration gate evaluated at dispatch finalize.

    Usage inside the dispatch pipeline (design §4)::

        gate = RegistrationGate()
        result = gate.evaluate(worker_results, errors, findings)  # Step 23.6
    """

    def evaluate(
        self,
        *,
        worker_results: list[dict[str, Any]] | None,
        errors: list[str] | None,
        findings: list[ReviewFinding] | None,
        ledger_path: str | Path = DEFAULT_LEDGER_PATH,
    ) -> RegistrationGateResult:
        """Evaluate the registration state of the run's mandatory signals.

        Raises :class:`DefectLedgerError` when the ledger is corrupt or
        fails load validation — the mixin converts that to an
        internal-error FAIL (fail-closed, D7); this method stays pure so
        unit tests can assert the refusal directly.
        """
        path_str = str(ledger_path)
        signal_types = self.extract_signal_types(worker_results, errors, findings)
        entries = DefectLedger(ledger_path=path_str).list_defects()
        live: dict[str, list[str]] = {}
        closed: dict[str, list[str]] = {}
        for entry in entries:
            stype = str(entry.signal.get("type", ""))
            if not stype:
                continue
            if entry.state.value in _LIVE_STATES:
                live.setdefault(stype, []).append(entry.id)
            elif entry.state.value == "closed":
                closed.setdefault(stype, []).append(entry.id)

        signals: list[dict[str, Any]] = []
        violations: list[str] = []
        for stype in signal_types:
            tracked_by = sorted(live.get(stype, []))
            closed_ids = sorted(closed.get(stype, []))
            if tracked_by:
                status = "tracked"
            elif closed_ids:
                status = "regressed"
                violations.append(
                    f"mandatory signal '{stype}' regressed: closed DEF ticket(s) "
                    f"{', '.join(closed_ids)} exist but none is live — reopen one "
                    f"(devsquad defect reopen <DEF-NNN> --reason ...)"
                )
            else:
                status = "unregistered"
                violations.append(
                    f"mandatory signal '{stype}' has no live DEF ticket "
                    f"(ledger: {path_str}); file one via 'devsquad defect add "
                    "--signal-ref <this run's audit event ref> --summary ...' "
                    "or fix the defect"
                )
            signals.append({"type": stype, "status": status, "tracked_by": tracked_by, "closed_ids": closed_ids})
        verdict = "fail" if violations else "pass"
        return RegistrationGateResult(
            verdict=verdict,
            ledger_path=path_str,
            signals=signals,
            violations=violations,
        )

    @staticmethod
    def extract_signal_types(
        worker_results: list[dict[str, Any]] | None,
        errors: list[str] | None,
        findings: list[ReviewFinding] | None,
    ) -> list[str]:
        """Mandatory signal types carried by this run (D2, deterministic order).

        The failure class is computed from the terminal state in scope
        (``worker_results`` + errors-so-far); a BV-critical finding
        category files as ``review:break-vuln:<ID>``. The result is the
        intersection with :func:`mandatory_signal_types` — defense in
        depth keeping the scope closed if the taxonomy ever grows.
        """
        types: set[str] = set()
        failure_class = failure_class_for_dispatch(worker_results, errors)
        if failure_class is FailureClass.PRODUCT_FAILED:
            types.add("failure:product_failed")
        for finding in findings or []:
            category = str(getattr(finding, "category", ""))
            if category in BV_CRITICAL:
                types.add(f"review:break-vuln:{category}")
        return sorted(types & mandatory_signal_types())


def unfiled_signal_report(
    ledger_path: str | Path = DEFAULT_LEDGER_PATH,
    audit_db_path: str | Path = DEFAULT_AUDIT_DB_PATH,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Advisory report: non-mandatory signal types seen but not live-tracked.

    Scans ``dispatch_end`` audit events for warning/spec finding
    categories (the mandatory scope is gated fail-closed when enabled,
    D11 — it is deliberately excluded here) and diffs them against the
    ledger's live ticket types. Returns ``(advisory, warnings)``:
    ``advisory`` items are ``{"type", "seen_count", "last_event_id"}``;
    ``warnings`` carries honest degradation notes (audit DB missing /
    unreadable / ledger unreadable) — advisory is best-effort disclosure
    and never hijacks the invariant part of ``defect audit``.
    """
    audit_path = Path(audit_db_path)
    if not audit_path.exists():
        return [], [f"audit DB not found at {audit_path} — no advisory scan"]
    try:
        live_types = {
            str(entry.signal.get("type", ""))
            for entry in DefectLedger(ledger_path=ledger_path, audit_db_path=audit_path).list_defects()
            if entry.state.value in _LIVE_STATES
        }
    except DefectLedgerError as exc:
        return [], [f"ledger unreadable: {exc}"]
    seen: dict[str, dict[str, Any]] = {}
    try:
        conn = sqlite3.connect(f"file:{audit_path}?mode=ro", uri=True)
        try:
            rows = conn.execute("SELECT id, details FROM dispatch_audit WHERE event_type = 'dispatch_end'").fetchall()
        finally:
            conn.close()
    except sqlite3.Error as exc:
        return [], [f"audit DB query failed: {exc}"]
    for event_id, details_raw in rows:
        try:
            details = json.loads(details_raw) if isinstance(details_raw, str) else None
        except json.JSONDecodeError:
            continue
        if not isinstance(details, dict):
            continue
        findings = details.get("findings")
        if not isinstance(findings, list):
            continue
        for item in findings:
            if not isinstance(item, dict):
                continue
            category = str(item.get("category", ""))
            if not category or category in BV_CRITICAL:
                continue
            stype = f"review:break-vuln:{category}" if category in _BV_CODES else f"review:spec:{category}"
            record = seen.setdefault(stype, {"type": stype, "seen_count": 0, "last_event_id": event_id})
            record["seen_count"] += 1
            record["last_event_id"] = event_id
    advisory = [seen[stype] for stype in sorted(seen) if stype not in live_types]
    return advisory, []
