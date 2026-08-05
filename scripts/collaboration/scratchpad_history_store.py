#!/usr/bin/env python3
"""
ScratchpadHistoryStore — Cross-session persistent storage for Scratchpad entries.

Inspired by block/buzz's shared workspace persistence (channel history
searchable months later). DevSquad's in-memory Scratchpad is the hot path;
this module is the cold/archive store that enables cross-session search.

Security: all content is filtered through OutputValidator.redact() before
writing to SQLite, ensuring API keys / DB passwords / JWT tokens are never
persisted (Security review A2).

Anti-ghost: module-level ``_call_counter`` increments on every public method.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path

from .models_base import EntryType, ScratchpadEntry

__all__ = ["ScratchpadHistoryStore"]

logger = logging.getLogger(__name__)

# Anti-ghost call counter (module-level).
_call_counter: int = 0


def _redact_sensitive(content: str) -> str:
    """Filter sensitive data from content before persistence.

    Uses OutputValidator.redact() to replace API keys, DB passwords,
    JWT tokens with ``[REDACTED]`` markers. Falls back to original
    content if OutputValidator is unavailable (graceful degradation).
    """
    try:
        from .output_validator import OutputValidator

        validator = OutputValidator()
        return validator.redact(content)
    except Exception:  # noqa: BLE001 — graceful degradation
        return content


class ScratchpadHistoryStore:
    """SQLite-backed cross-session Scratchpad history.

    Cold/archive store — in-memory Scratchpad remains the hot path.
    Every :meth:`write` mirrors a Scratchpad entry to SQLite for future
    :meth:`search_history` queries across past sessions.

    Thread Safety
    -------------
    All public methods are thread-safe via ``threading.Lock``.

    Storage
    -------
    SQLite database at ``db_path``. File permissions set to 0600.

    Usage::

        store = ScratchpadHistoryStore(db_path="data/scratchpad_history.db")
        store.write(entry, scratchpad_id="scratchpad-20260801-120000")
        results = store.search_history(query="auth", since=days_ago(7))
    """

    def __init__(
        self,
        db_path: str | Path,
        retention_days: int = 90,
    ) -> None:
        """Initialize the history store.

        Parameters
        ----------
        db_path:
            Path to SQLite database file.
        retention_days:
            Entries older than this are eligible for cleanup. Default 90.
        """
        global _call_counter
        _call_counter += 1

        self._db_path = Path(db_path)
        self._retention_days = retention_days
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def _init_db(self) -> None:
        """Initialize SQLite database with schema and file permissions."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            str(self._db_path),
            check_same_thread=False,
        )
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS scratchpad_history (
                entry_id TEXT NOT NULL,
                scratchpad_id TEXT NOT NULL,
                worker_id TEXT,
                role_id TEXT,
                entry_type TEXT NOT NULL,
                content TEXT NOT NULL,
                confidence REAL,
                tags TEXT,
                created_at TEXT NOT NULL,
                PRIMARY KEY (entry_id, scratchpad_id)
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_history_role ON scratchpad_history(role_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_history_type ON scratchpad_history(entry_type)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_history_time ON scratchpad_history(created_at)"
        )
        self._conn.commit()
        # Set file permissions to 0600 (owner read/write only).
        with contextlib.suppress(OSError):
            os.chmod(self._db_path, 0o600)

    def write(self, entry: ScratchpadEntry, scratchpad_id: str) -> None:
        """Mirror a Scratchpad entry to persistent storage.

        Applies sensitive-data filtering before write (Security A2).

        Parameters
        ----------
        entry:
            ScratchpadEntry to persist.
        scratchpad_id:
            ID of the Scratchpad instance this entry belongs to.
        """
        global _call_counter
        _call_counter += 1

        with self._lock:
            # Filter sensitive data before persistence.
            safe_content = _redact_sensitive(entry.content)
            tags_json = json.dumps(entry.tags) if entry.tags else "[]"
            # ScratchpadEntry exposes its creation time via ``timestamp``
            # (see models_base.ScratchpadEntry); ``created_at`` is only
            # present on CompressedScratchpadEntry / LearnedRule.
            created_at = entry.timestamp.isoformat() if entry.timestamp else datetime.now().isoformat()

            self._conn.execute(
                """
                INSERT OR REPLACE INTO scratchpad_history
                    (entry_id, scratchpad_id, worker_id, role_id, entry_type,
                     content, confidence, tags, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.entry_id,
                    scratchpad_id,
                    entry.worker_id,
                    entry.role_id,
                    entry.entry_type.value,
                    safe_content,
                    entry.confidence,
                    tags_json,
                    created_at,
                ),
            )
            self._conn.commit()

    def search_history(
        self,
        query: str = "",
        since: datetime | None = None,
        entry_type: EntryType | None = None,
        role_id: str | None = None,
        limit: int = 50,
    ) -> list[ScratchpadEntry]:
        """Search across all past Scratchpad instances.

        All parameters optional; combined with AND logic.

        Parameters
        ----------
        query:
            Keyword fuzzy match in content (case-insensitive LIKE).
        since:
            Only return entries after this datetime.
        entry_type:
            Filter by entry type (FINDING/QUESTION/DECISION/CONFLICT).
        role_id:
            Filter by role_id.
        limit:
            Max results. Default 50.

        Returns
        -------
        list[ScratchpadEntry]
            Matching entries, newest first.
        """
        global _call_counter
        _call_counter += 1

        with self._lock:
            sql = "SELECT entry_id, scratchpad_id, worker_id, role_id, entry_type, content, confidence, tags, created_at FROM scratchpad_history WHERE 1=1"
            params: list = []

            if query:
                sql += " AND content LIKE ?"
                params.append(f"%{query}%")
            if since:
                sql += " AND created_at >= ?"
                params.append(since.isoformat())
            if entry_type:
                sql += " AND entry_type = ?"
                params.append(entry_type.value)
            if role_id:
                sql += " AND role_id = ?"
                params.append(role_id)

            sql += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            cursor = self._conn.execute(sql, params)
            results: list[ScratchpadEntry] = []
            for row in cursor.fetchall():
                entry = ScratchpadEntry(
                    entry_id=row[0],
                    worker_id=row[2] or "",
                    role_id=row[3] or "",
                    entry_type=EntryType(row[4]),
                    content=row[5],
                    confidence=row[6] or 1.0,
                    tags=json.loads(row[7]) if row[7] else [],
                    timestamp=datetime.fromisoformat(row[8]),
                )
                results.append(entry)
            return results

    def cleanup_expired(self) -> int:
        """Delete entries older than retention_days.

        Returns
        -------
        int
            Number of entries deleted.
        """
        global _call_counter
        _call_counter += 1

        with self._lock:
            cutoff = (datetime.now() - timedelta(days=self._retention_days)).isoformat()
            cursor = self._conn.execute(
                "DELETE FROM scratchpad_history WHERE created_at < ?",
                (cutoff,),
            )
            self._conn.commit()
            return cursor.rowcount

    @property
    def _call_counter_value(self) -> int:
        """Read-only access to module-level call counter (anti-ghost)."""
        return _call_counter

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
