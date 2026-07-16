#!/usr/bin/env python3
"""
DispatchAuditLogger — Audit logging for dispatch pipeline.

Records dispatch lifecycle events with append-only storage and SHA-256
chain hash (adopted from Security review S3).

Each entry's hash is computed as::

    SHA-256(prev_hash + len(event_type):event_type + len(user_id):user_id +
    timestamp(%.6f) + json.dumps(details))

Length-prefixed fields eliminate boundary ambiguity (e.g. event_type="dispatch",
user_id="_start" vs event_type="dispatch_start", user_id=""). The timestamp is
formatted with fixed 6-decimal precision for cross-version stability.

The first entry has ``prev_hash = "0" * 64`` (64 hex zeros). Each subsequent
entry's ``prev_hash`` is the ``entry_hash`` of the previous entry. This
creates a tamper-evident chain: modifying any entry invalidates all
subsequent hashes.

Storage
-------
- If ``db_path`` is provided, entries are persisted to a SQLite database.
- If ``db_path`` is None, entries are kept in-memory only (lost on exit).

Event Types
-----------
- ``dispatch_start``        — Dispatch operation began.
- ``dispatch_end``          — Dispatch operation completed.
- ``permission_denied``     — RBAC denied a dispatch request.
- ``error``                 — Error occurred during dispatch.

Usage::

    from scripts.collaboration.dispatch_audit import DispatchAuditLogger

    logger = DispatchAuditLogger()  # in-memory
    h1 = logger.log_dispatch_start("u1", "Design auth system", ["architect"])
    h2 = logger.log_dispatch_end("u1", success=True, duration=1.23)
    assert logger.verify_chain() is True
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

__all__ = ["DispatchAuditLogger", "AuditEntry"]

logger = logging.getLogger(__name__)

# Environment variable name for the HMAC secret key used to tamper-proof the
# audit chain. When unset, a random per-process key is generated (with a
# WARNING) — this means verification cannot span process restarts.
_AUDIT_HMAC_KEY_ENV = "DEV_SQUAD_AUDIT_HMAC_KEY"


# The genesis hash for the first entry in the chain (64 hex zeros).
GENESIS_HASH = "0" * 64


@dataclass
class AuditEntry:
    """A single audit log entry in the dispatch pipeline.

    Attributes
    ----------
    event_type:
        One of dispatch_start|dispatch_end|permission_denied|error.
    user_id:
        The user who triggered the event.
    timestamp:
        Unix timestamp (seconds since epoch) when the event was recorded.
    details:
        JSON-serializable dict with event-specific context.
    prev_hash:
        Hash of the previous entry in the chain (GENESIS_HASH for first).
    entry_hash:
        SHA-256 hash of this entry (computed from prev_hash +
        len(event_type):event_type + len(user_id):user_id +
        timestamp(%.6f) + json.dumps(details)).
    """

    event_type: str
    user_id: str
    timestamp: float
    details: dict = field(default_factory=dict)
    prev_hash: str = ""
    entry_hash: str = ""


class DispatchAuditLogger:
    """Append-only audit logger with HMAC-SHA256 chain hash.

    Records dispatch lifecycle events (start, end, permission_denied, error)
    with cryptographic integrity. Each entry's hash chains to the previous
    entry, making tampering detectable via :meth:`verify_chain` or the
    stricter :meth:`verify_hmac_chain`.

    The chain uses HMAC-SHA256 with a secret key (loaded from the
    ``DEV_SQUAD_AUDIT_HMAC_KEY`` environment variable) so that an attacker
    who can modify the log cannot recompute valid hashes without the key.
    The previous plain SHA-256 chain (pre-V4.1.1) is still recognized by
    :meth:`verify_chain` for backward compatibility (with a WARNING).

    Thread Safety
    -------------
    All public methods are thread-safe via ``threading.Lock``.

    Storage
    -------
    - ``db_path=None`` (default): in-memory only (lost on exit).
    - ``db_path=Path(...)``: persisted to SQLite database.
    """

    # Class-level cache for the randomly-generated HMAC key (when the env
    # var is not set). This ensures all instances in the same process share
    # the same key, so persistence tests within one process still verify.
    _hmac_key_cache: bytes | None = None

    def __init__(self, db_path: Path | None = None) -> None:
        """Initialize the audit logger.

        Parameters
        ----------
        db_path:
            Path to SQLite database file for persistence. If None,
            entries are kept in-memory only.
        """
        self._db_path = db_path
        self._lock = threading.Lock()
        self._entries: list[AuditEntry] = []
        self._prev_hash: str = GENESIS_HASH
        self._conn: sqlite3.Connection | None = None

        if db_path is not None:
            self._init_db()

    # ------------------------------------------------------------------
    # HMAC key management
    # ------------------------------------------------------------------

    def _get_hmac_key(self) -> bytes:
        """Load or create the HMAC secret key.

        The key is loaded from the ``DEV_SQUAD_AUDIT_HMAC_KEY`` environment
        variable. If the env var is not set, a random 32-byte key is
        generated once per process (cached at class level) and a WARNING is
        logged — in this state, audit chain verification cannot span
        process restarts because the random key is lost on exit.

        Returns
        -------
        bytes
            The HMAC key.
        """
        env_key = os.environ.get(_AUDIT_HMAC_KEY_ENV)
        if env_key:
            return env_key.encode("utf-8")
        if DispatchAuditLogger._hmac_key_cache is None:
            DispatchAuditLogger._hmac_key_cache = secrets.token_bytes(32)
            logger.warning(
                "%s not set — generated a random HMAC key for this process. "
                "Audit chain verification will FAIL across process restarts. "
                "Set the env var in production for persistent tamper-proofing.",
                _AUDIT_HMAC_KEY_ENV,
            )
        return DispatchAuditLogger._hmac_key_cache

    def _init_db(self) -> None:
        """Initialize the SQLite database and load existing entries."""
        if self._db_path is None:
            return
        # Ensure parent directory exists.
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS dispatch_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                user_id TEXT NOT NULL,
                timestamp REAL NOT NULL,
                details TEXT NOT NULL,
                prev_hash TEXT NOT NULL,
                entry_hash TEXT NOT NULL
            )
        """)
        self._conn.commit()
        # Load existing entries to rebuild the chain state.
        self._load_existing_entries()

    def _load_existing_entries(self) -> None:
        """Load existing entries from the database to rebuild chain state."""
        if self._conn is None:
            return
        cursor = self._conn.execute(
            "SELECT event_type, user_id, timestamp, details, prev_hash, entry_hash "
            "FROM dispatch_audit ORDER BY id ASC"
        )
        for row in cursor:
            entry = AuditEntry(
                event_type=row[0],
                user_id=row[1],
                timestamp=row[2],
                details=json.loads(row[3]),
                prev_hash=row[4],
                entry_hash=row[5],
            )
            self._entries.append(entry)
            self._prev_hash = entry.entry_hash

    def _build_hash_payload(
        self,
        event_type: str,
        user_id: str,
        timestamp: float,
        details: dict,
        prev_hash: str,
    ) -> bytes:
        """Build the canonical length-prefixed payload for an audit entry.

        The payload format eliminates boundary ambiguity:

            prev_hash + len(event_type):event_type + len(user_id):user_id
            + timestamp(%.6f) + json.dumps(details)

        Parameters
        ----------
        event_type:
            The event type string.
        user_id:
            The user ID string.
        timestamp:
            The Unix timestamp.
        details:
            The details dict (JSON-serialized with sorted keys).
        prev_hash:
            The previous entry's hash (or GENESIS_HASH for first entry).

        Returns
        -------
        bytes
            The UTF-8 encoded payload bytes.
        """
        details_json = json.dumps(details, sort_keys=True)
        payload = f"{prev_hash}{len(event_type)}:{event_type}{len(user_id)}:{user_id}{timestamp:.6f}{details_json}"
        return payload.encode("utf-8")

    def _compute_hash(
        self,
        event_type: str,
        user_id: str,
        timestamp: float,
        details: dict,
        prev_hash: str,
    ) -> str:
        """Compute the HMAC-SHA256 hash for an audit entry.

        Uses HMAC-SHA256 with a secret key (from
        ``DEV_SQUAD_AUDIT_HMAC_KEY``) so that an attacker who can modify
        the log cannot recompute valid hashes without the key.

        Parameters
        ----------
        event_type:
            The event type string.
        user_id:
            The user ID string.
        timestamp:
            The Unix timestamp.
        details:
            The details dict (JSON-serialized with sorted keys).
        prev_hash:
            The previous entry's hash (or GENESIS_HASH for first entry).

        Returns
        -------
        str
            The 64-character hex HMAC-SHA256 digest.
        """
        payload = self._build_hash_payload(
            event_type, user_id, timestamp, details, prev_hash
        )
        key = self._get_hmac_key()
        return hmac.new(key, payload, hashlib.sha256).hexdigest()

    def _compute_legacy_hash(
        self,
        event_type: str,
        user_id: str,
        timestamp: float,
        details: dict,
        prev_hash: str,
    ) -> str:
        """Compute the legacy plain SHA-256 hash (pre-V4.1.1, no HMAC key).

        Used only by :meth:`verify_chain` for backward compatibility with
        entries written before the HMAC upgrade. New entries always use
        :meth:`_compute_hash` (HMAC).
        """
        payload = self._build_hash_payload(
            event_type, user_id, timestamp, details, prev_hash
        )
        return hashlib.sha256(payload).hexdigest()

    def _append_entry(
        self,
        event_type: str,
        user_id: str,
        details: dict,
    ) -> str:
        """Append a new audit entry to the chain.

        Parameters
        ----------
        event_type:
            The event type string.
        user_id:
            The user ID string.
        details:
            The details dict.

        Returns
        -------
        str
            The entry hash of the newly appended entry.
        """
        with self._lock:
            timestamp = time.time()
            entry_hash = self._compute_hash(
                event_type=event_type,
                user_id=user_id,
                timestamp=timestamp,
                details=details,
                prev_hash=self._prev_hash,
            )
            entry = AuditEntry(
                event_type=event_type,
                user_id=user_id,
                timestamp=timestamp,
                details=details,
                prev_hash=self._prev_hash,
                entry_hash=entry_hash,
            )
            self._entries.append(entry)
            self._prev_hash = entry_hash

            # Persist to database if configured.
            if self._conn is not None:
                self._conn.execute(
                    "INSERT INTO dispatch_audit "
                    "(event_type, user_id, timestamp, details, prev_hash, entry_hash) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        entry.event_type,
                        entry.user_id,
                        entry.timestamp,
                        json.dumps(entry.details, sort_keys=True),
                        entry.prev_hash,
                        entry.entry_hash,
                    ),
                )
                self._conn.commit()

            return entry_hash

    # ------------------------------------------------------------------
    # Public logging API
    # ------------------------------------------------------------------

    def log_dispatch_start(
        self,
        user_id: str,
        task: str,
        roles: list[str],
    ) -> str:
        """Log dispatch start. Returns entry hash.

        Parameters
        ----------
        user_id:
            The user initiating the dispatch.
        task:
            The task description.
        roles:
            The dispatch roles requested.

        Returns
        -------
        str
            The SHA-256 entry hash.
        """
        details = {"task": task, "roles": list(roles)}
        return self._append_entry("dispatch_start", user_id, details)

    def log_dispatch_end(
        self,
        user_id: str,
        success: bool,
        duration: float,
    ) -> str:
        """Log dispatch end. Returns entry hash.

        Parameters
        ----------
        user_id:
            The user who initiated the dispatch.
        success:
            Whether the dispatch succeeded.
        duration:
            Duration in seconds.

        Returns
        -------
        str
            The SHA-256 entry hash.
        """
        details = {"success": success, "duration": duration}
        return self._append_entry("dispatch_end", user_id, details)

    def log_permission_denied(
        self,
        user_id: str,
        reason: str,
    ) -> str:
        """Log permission denial. Returns entry hash.

        Parameters
        ----------
        user_id:
            The user whose request was denied.
        reason:
            The denial reason.

        Returns
        -------
        str
            The SHA-256 entry hash.
        """
        details = {"reason": reason}
        return self._append_entry("permission_denied", user_id, details)

    def log_error(
        self,
        user_id: str,
        error_type: str,
        context: dict,
    ) -> str:
        """Log error during dispatch. Returns entry hash.

        Parameters
        ----------
        user_id:
            The user who triggered the error.
        error_type:
            The error type/exception name.
        context:
            Additional error context dict.

        Returns
        -------
        str
            The SHA-256 entry hash.
        """
        details = {"error_type": error_type, "context": dict(context)}
        return self._append_entry("error", user_id, details)

    # ------------------------------------------------------------------
    # Query and verification API
    # ------------------------------------------------------------------

    def get_entries(self, limit: int = 100) -> list[AuditEntry]:
        """Retrieve recent audit entries.

        Parameters
        ----------
        limit:
            Maximum number of entries to return (most recent first).

        Returns
        -------
        list[AuditEntry]
            List of audit entries, most recent first.
        """
        with self._lock:
            if limit <= 0:
                return []
            # Return most recent first.
            return list(reversed(self._entries[-limit:]))

    def verify_chain(self) -> bool:
        """Verify the integrity of the audit chain.

        Recomputes every entry's hash from its fields and checks that:
        1. The first entry's prev_hash equals GENESIS_HASH.
        2. Each entry's entry_hash matches the recomputed hash.
        3. Each entry's prev_hash matches the previous entry's entry_hash.

        Verification uses HMAC-SHA256. For backward compatibility with
        entries written before the V4.1.1 HMAC upgrade, if the HMAC
        recomputation does not match, the legacy plain SHA-256 hash is
        tried — if it matches, a WARNING is logged (the entry is treated
        as a legacy entry) and verification continues. A genuinely
        tampered entry matches neither hash and fails verification.

        Returns
        -------
        bool
            True if the chain is intact, False if any entry is tampered.
        """
        with self._lock:
            if not self._entries:
                return True  # Empty chain is valid.

            expected_prev = GENESIS_HASH
            for entry in self._entries:
                # Check prev_hash chains correctly.
                if entry.prev_hash != expected_prev:
                    return False
                # Recompute HMAC hash and check it matches.
                recomputed = self._compute_hash(
                    event_type=entry.event_type,
                    user_id=entry.user_id,
                    timestamp=entry.timestamp,
                    details=entry.details,
                    prev_hash=entry.prev_hash,
                )
                if recomputed != entry.entry_hash:
                    # Backward compat: try legacy plain SHA-256 (pre-HMAC).
                    legacy = self._compute_legacy_hash(
                        event_type=entry.event_type,
                        user_id=entry.user_id,
                        timestamp=entry.timestamp,
                        details=entry.details,
                        prev_hash=entry.prev_hash,
                    )
                    if legacy == entry.entry_hash:
                        logger.warning(
                            "Audit entry uses legacy SHA-256 hash (pre-HMAC). "
                            "Re-hash with HMAC for full tamper-proofing. "
                            "event_type=%s user_id=%s",
                            entry.event_type,
                            entry.user_id,
                        )
                    else:
                        return False
                expected_prev = entry.entry_hash
            return True

    def verify_hmac_chain(self, entries: list[AuditEntry] | None = None) -> bool:
        """Strictly verify the HMAC chain integrity (no legacy fallback).

        Recomputes the HMAC-SHA256 hash for every entry and checks that:
        1. The first entry's prev_hash equals GENESIS_HASH.
        2. Each entry's entry_hash matches the recomputed HMAC hash.
        3. Each entry's prev_hash matches the previous entry's entry_hash.

        Unlike :meth:`verify_chain`, this method does NOT fall back to the
        legacy plain SHA-256 hash. Entries that use the old (non-HMAC) hash
        will fail verification. Use this for security-critical verification
        where all entries are expected to be HMAC-signed.

        Parameters
        ----------
        entries:
            Optional list of entries to verify. If None, all entries in
            this logger are verified.

        Returns
        -------
        bool
            True if the HMAC chain is intact, False if any entry is
            tampered or uses a legacy (non-HMAC) hash.
        """
        with self._lock:
            to_verify = entries if entries is not None else self._entries
            if not to_verify:
                return True  # Empty chain is valid.

            expected_prev = GENESIS_HASH
            for entry in to_verify:
                if entry.prev_hash != expected_prev:
                    return False
                recomputed = self._compute_hash(
                    event_type=entry.event_type,
                    user_id=entry.user_id,
                    timestamp=entry.timestamp,
                    details=entry.details,
                    prev_hash=entry.prev_hash,
                )
                if recomputed != entry.entry_hash:
                    return False
                expected_prev = entry.entry_hash
            return True

    def count(self) -> int:
        """Return the total number of entries in the chain."""
        with self._lock:
            return len(self._entries)

    def close(self) -> None:
        """Close the database connection if open."""
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None
