#!/usr/bin/env python3
"""Audit CLI — V4.5.3 P12.2.6.

Exposes DispatchAuditLogger as a CLI subcommand:

    devsquad audit                       # last 20 entries, text format
    devsquad audit --limit 100           # specific count
    devsquad audit --format json         # JSON output
    devsquad audit --event-type dispatch_start  # filter by event type
    devsquad audit --verify              # validate hash chain integrity

Sensitive fields (api_key, password, secret, token) in details dict are
auto-redacted in text output.

Anti-ghost: get_call_counter() exposed.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
from argparse import ArgumentParser
from pathlib import Path
from typing import Any, cast

# Ensure repo root on path
sys.path.insert(0, ".")


# ---------- Anti-ghost counter ----------

_call_counter: int = 0
_call_counter_lock = threading.Lock()


def _inc_call_counter() -> None:
    global _call_counter
    with _call_counter_lock:
        _call_counter += 1


def get_call_counter() -> int:
    """Return current anti-ghost counter value."""
    with _call_counter_lock:
        return _call_counter


# ---------- Sensitive field redaction ----------


_SENSITIVE_KEYS = frozenset(
    {"api_key", "apikey", "password", "passwd", "secret", "token", "private_key"}
)


def _redact_sensitive(value: Any) -> Any:
    """Recursively redact sensitive keys in dict/list values."""
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if isinstance(k, str) and k.lower() in _SENSITIVE_KEYS:
                out[k] = "***REDACTED***"
            else:
                out[k] = _redact_sensitive(v)
        return out
    if isinstance(value, list):
        return [_redact_sensitive(v) for v in value]
    return value


# ---------- Output formatters ----------


def _format_text(entries: list[dict[str, Any]]) -> str:
    """Format audit entries as human-readable text."""
    lines = []
    for entry in entries:
        ts = entry.get("timestamp", 0)
        et = entry.get("event_type", "?")
        uid = entry.get("user_id", "?")
        details = _redact_sensitive(entry.get("details", {}))
        hash_short = (entry.get("entry_hash") or "")[:8]
        lines.append(f"[{ts:.2f}] {et:25s} user={uid:20s} hash={hash_short}")
        if details:
            detail_str = json.dumps(details, sort_keys=True, ensure_ascii=False)
            if len(detail_str) > 200:
                detail_str = detail_str[:200] + "..."
            lines.append(f"    {detail_str}")
    return "\n".join(lines)


def _format_json(entries: list[dict[str, Any]]) -> str:
    """Format audit entries as JSON."""
    redacted = [_redact_sensitive(e) for e in entries]
    return json.dumps(redacted, indent=2, sort_keys=True, ensure_ascii=False)


# ---------- Hash chain verification ----------


def verify_chain(entries: list[dict[str, Any]]) -> tuple[bool, str]:
    """Verify SHA-256 chain integrity.

    Args:
        entries: Audit entries from DispatchAuditLogger (already ordered).

    Returns:
        (True, "OK") if chain valid; (False, error_message) otherwise.
    """
    import hashlib

    prev_hash = "0" * 64
    for i, entry in enumerate(entries):
        ts = entry.get("timestamp", 0)
        et = entry.get("event_type", "")
        uid = entry.get("user_id", "")
        details_json = json.dumps(
            entry.get("details", {}), sort_keys=True, separators=(",", ":")
        )
        payload = (
            f"{prev_hash}"
            f"{len(et):d}:{et}"
            f"{len(uid):d}:{uid}"
            f"{ts:.6f}"
            f"{details_json}"
        ).encode()
        expected = hashlib.sha256(payload).hexdigest()
        actual = entry.get("entry_hash")
        if actual != expected:
            return False, f"Chain broken at entry #{i}: expected {expected}, got {actual}"
        prev_hash = actual
    return True, "OK"


# ---------- Audit loader ----------


def _load_entries(db_path: str | None) -> list[dict[str, Any]]:
    """Load audit entries from SQLite DB or in-memory logger.

    Args:
        db_path: SQLite database path. If None, returns empty list.

    Returns:
        List of audit entry dicts (with event_type, user_id, timestamp,
        details, prev_hash, entry_hash).
    """
    if db_path is None:
        return []
    db = Path(db_path)
    if not db.exists():
        return []
    import sqlite3

    entries: list[dict[str, Any]] = []
    try:
        with sqlite3.connect(str(db)) as conn:
            cur = conn.execute(
                "SELECT event_type, user_id, timestamp, details, prev_hash, entry_hash "
                "FROM dispatch_audit ORDER BY id ASC"
            )
            for row in cur.fetchall():
                try:
                    details = json.loads(row[3]) if row[3] else {}
                except json.JSONDecodeError:
                    details = {"_raw": row[3]}
                entries.append(
                    {
                        "event_type": row[0],
                        "user_id": row[1],
                        "timestamp": row[2],
                        "details": details,
                        "prev_hash": row[4],
                        "entry_hash": row[5],
                    }
                )
    except sqlite3.Error:
        return []
    return entries


# ---------- CLI entry point ----------


def cmd_audit(args: argparse.Namespace) -> int:
    """Implements `devsquad audit` subcommand.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Exit code (0 success, 1 verify failure).
    """
    _inc_call_counter()
    entries = _load_entries(args.db_path)
    if args.event_type:
        entries = [e for e in entries if e.get("event_type") == args.event_type]
    if args.limit:
        entries = entries[-args.limit :]

    if args.verify:
        ok, msg = verify_chain(entries)
        if args.format == "json":
            print(json.dumps({"valid": ok, "message": msg}, indent=2))
        else:
            print(f"Chain verification: {msg}")
        return 0 if ok else 1

    if args.format == "json":
        print(_format_json(entries))
    else:
        if not entries:
            print("(no audit entries)")
        else:
            print(_format_text(entries))
    return 0


def register_subparser(
    subparsers: Any,  # argparse._SubParsersAction
) -> argparse.ArgumentParser:
    """Register `audit` subparser on the parent subparsers.

    Args:
        subparsers: Parent argparse subparsers action.

    Returns:
        The audit subparser.
    """
    p = subparsers.add_parser(
        "audit", help="Inspect dispatch audit log (V4.5.3 P12.2.6)"
    )
    p.add_argument(
        "--limit", "-n", type=int, default=20, help="Max entries to show (default 20)"
    )
    p.add_argument(
        "--format",
        "-f",
        choices=["text", "json"],
        default="text",
        help="Output format",
    )
    p.add_argument(
        "--event-type",
        help="Filter by event type (e.g. dispatch_start, dispatch_end)",
    )
    p.add_argument(
        "--verify",
        action="store_true",
        help="Verify SHA-256 hash chain integrity (exit non-zero on tamper)",
    )
    p.add_argument(
        "--db-path",
        default=None,
        help="Path to dispatch_audit SQLite DB (defaults to in-memory)",
    )
    p.set_defaults(func=cmd_audit)
    return cast(ArgumentParser, p)


if __name__ == "__main__":
    # Allow standalone invocation for testing
    parser = argparse.ArgumentParser(description="DevSquad audit log inspector")
    register_subparser(parser.add_subparsers(dest="command"))
    args = parser.parse_args()
    if hasattr(args, "func"):
        sys.exit(args.func(args))
    else:
        parser.print_help()
        sys.exit(1)
