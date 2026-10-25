#!/usr/bin/env python3
"""`devsquad defect` CLI subcommands (V4.9.0 P2-W1).

Wires :class:`~scripts.collaboration.defect_ledger.DefectLedger` into the
top-level CLI as a sibling of dispatch/status (design §4.2):

    devsquad defect add    --signal-ref R --summary S [--json]
    devsquad defect update <DEF-NNN> --commit SHA --summary S [--json]
    devsquad defect close   <DEF-NNN> --run-ref R [--json]
    devsquad defect reopen  <DEF-NNN> --reason R [--json]
    devsquad defect list    [--state open|fixed|closed] [--json]
    devsquad defect audit   [--json]

Exit codes follow the C19 contract: 0 success / 1 product refusal
(state-machine violation, unresolvable signal, validation failure) /
2 environment blocked (ledger I/O or audit DB unreachable).
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections.abc import Callable
from functools import wraps
from pathlib import Path

from scripts.collaboration.defect_ledger import (
    DEFAULT_AUDIT_DB_PATH,
    DEFAULT_LEDGER_PATH,
    ENVIRONMENT_BLOCKED_EXIT,
    PRODUCT_FAILED_EXIT,
    Defect,
    DefectLedger,
    DefectLedgerError,
)

_call_counter_dl = 0


def get_call_counter_dl() -> int:
    """Anti-ghost: activation counter for the defect ledger CLI."""
    return _call_counter_dl


def _inc_call_counter_dl() -> None:
    global _call_counter_dl
    _call_counter_dl += 1


def _error_code(exc: Exception) -> int:
    if isinstance(exc, DefectLedgerError):
        return PRODUCT_FAILED_EXIT
    if isinstance(exc, (OSError, sqlite3.Error)):
        return ENVIRONMENT_BLOCKED_EXIT
    return PRODUCT_FAILED_EXIT


def _safe_command(func: Callable[[argparse.Namespace], int]) -> Callable[[argparse.Namespace], int]:
    @wraps(func)
    def wrapped(args: argparse.Namespace) -> int:
        try:
            return func(args)
        except Exception as exc:  # CLI boundary: never expose a traceback.
            print(f"ERROR: {exc}", file=sys.stderr)
            return _error_code(exc)

    return wrapped


def _get_ledger(args: argparse.Namespace) -> DefectLedger:
    return DefectLedger(
        ledger_path=Path(getattr(args, "ledger_path", None) or DEFAULT_LEDGER_PATH),
        audit_db_path=Path(getattr(args, "audit_db_path", None) or DEFAULT_AUDIT_DB_PATH),
    )


def _emit(entry: Defect, as_json: bool) -> None:
    if as_json:
        print(json.dumps(entry.to_dict(), ensure_ascii=False))
        return
    fix = entry.fix["commit"] if entry.fix else "-"
    print(f"{entry.id}  {entry.state.value:<6}  signal={entry.signal['ref']}  fix={fix}")


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--ledger-path", default=DEFAULT_LEDGER_PATH, help="Ledger file path")
    parser.add_argument("--audit-db-path", default=DEFAULT_AUDIT_DB_PATH, help="Dispatch audit SQLite DB path")
    parser.add_argument("--json", action="store_true", help="Single-line JSON output")


@_safe_command
def cmd_defect_add(args: argparse.Namespace) -> int:
    _inc_call_counter_dl()
    ledger = _get_ledger(args)
    entry = ledger.add(signal_ref=args.signal_ref, summary=args.summary)
    _emit(entry, getattr(args, "json", False))
    return 0


@_safe_command
def cmd_defect_update(args: argparse.Namespace) -> int:
    _inc_call_counter_dl()
    ledger = _get_ledger(args)
    entry = ledger.update(defect_id=args.defect_id, commit_sha=args.commit, summary=args.summary)
    _emit(entry, getattr(args, "json", False))
    return 0


@_safe_command
def cmd_defect_close(args: argparse.Namespace) -> int:
    _inc_call_counter_dl()
    ledger = _get_ledger(args)
    entry = ledger.close(defect_id=args.defect_id, run_ref=args.run_ref)
    _emit(entry, getattr(args, "json", False))
    return 0


@_safe_command
def cmd_defect_reopen(args: argparse.Namespace) -> int:
    _inc_call_counter_dl()
    ledger = _get_ledger(args)
    entry = ledger.reopen(defect_id=args.defect_id, reason=args.reason)
    _emit(entry, getattr(args, "json", False))
    return 0


@_safe_command
def cmd_defect_list(args: argparse.Namespace) -> int:
    _inc_call_counter_dl()
    ledger = _get_ledger(args)
    entries = ledger.list_defects(state=getattr(args, "state", None))
    if getattr(args, "json", False):
        print(json.dumps([e.to_dict() for e in entries], ensure_ascii=False))
        return 0
    if not entries:
        print("no defects")
        return 0
    for entry in entries:
        _emit(entry, as_json=False)
    return 0


@_safe_command
def cmd_defect_audit(args: argparse.Namespace) -> int:
    _inc_call_counter_dl()
    ledger = _get_ledger(args)
    issues = ledger.audit_report()
    if getattr(args, "json", False):
        print(json.dumps({"ok": not issues, "issues": issues}, ensure_ascii=False))
    elif issues:
        for issue in issues:
            print(f"FAIL: {issue}", file=sys.stderr)
    else:
        print("ledger audit: OK")
    return 1 if issues else 0


def register_defect_subparser(subparsers: argparse._SubParsersAction) -> None:
    p_defect = subparsers.add_parser("defect", help="Cross-run defect ledger (V4.9.0 P2-W1)")
    defect_sub = p_defect.add_subparsers(dest="defect_command", required=True, help="Defect subcommand")

    p_add = defect_sub.add_parser("add", help="File a defect from a real signal (create->open)")
    _add_common_arguments(p_add)
    p_add.add_argument(
        "--signal-ref", required=True, help="audit:event=<N>&finding=<i> | audit:event=<N>&failure=<class>"
    )
    p_add.add_argument("--summary", required=True, help="One-line human summary")
    p_add.set_defaults(func=cmd_defect_add)

    p_update = defect_sub.add_parser("update", help="Register a fix (open->fixed, or refix)")
    _add_common_arguments(p_update)
    p_update.add_argument("defect_id", metavar="DEF-NNN", help="Defect id")
    p_update.add_argument("--commit", required=True, help="Fix commit SHA")
    p_update.add_argument("--summary", required=True, help="Fix summary")
    p_update.set_defaults(func=cmd_defect_update)

    p_close = defect_sub.add_parser("close", help="Close after a clean regression run (fixed->closed)")
    _add_common_arguments(p_close)
    p_close.add_argument("defect_id", metavar="DEF-NNN", help="Defect id")
    p_close.add_argument("--run-ref", required=True, help="Regression run reference audit:event=<N>")
    p_close.set_defaults(func=cmd_defect_close)

    p_reopen = defect_sub.add_parser("reopen", help="Reopen a closed defect (closed->open, regressed)")
    _add_common_arguments(p_reopen)
    p_reopen.add_argument("defect_id", metavar="DEF-NNN", help="Defect id")
    p_reopen.add_argument("--reason", required=True, help="Mandatory reopen reason")
    p_reopen.set_defaults(func=cmd_defect_reopen)

    p_list = defect_sub.add_parser("list", help="List defects")
    _add_common_arguments(p_list)
    p_list.add_argument("--state", choices=["open", "fixed", "closed"], default=None)
    p_list.set_defaults(func=cmd_defect_list)

    p_audit = defect_sub.add_parser("audit", help="Cross-check ledger invariants (fail-closed)")
    _add_common_arguments(p_audit)
    p_audit.set_defaults(func=cmd_defect_audit)
