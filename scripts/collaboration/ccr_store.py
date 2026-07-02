#!/usr/bin/env python3
"""
CCRStore — Compressed Context Retrieval Store (V3.10.0 Phase 3).

Reversible compression backend: when SmartCrusher compresses content, the
original is stored here and a ``trace_id`` marker is emitted in the compressed
output. Workers can later retrieve the full original via
``devsquad_retrieve(trace_id=..., query=...)``.

Spec: docs/spec/v3.10.0_spec.md §5.4

Design:
- Backend: SQLite (default ``data/ccr_store.db``)
- Cache: in-memory LRU (OrderedDict) layered over SQLite
- TTL: ``delete_expired(ttl_days)`` removes stale entries
- Thread-safe: ``threading.Lock`` + ``check_same_thread=False``
- No external dependencies (stdlib only — ponytail rule)
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from collections import OrderedDict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, cast


class CCRStore:
    """Reversible compression store backed by SQLite + in-memory LRU.

    Stores original content keyed by a short trace_id. Retrieval checks the
    LRU cache first, then falls back to SQLite. Expired entries are removed
    by ``delete_expired`` based on ``created_at``.

    All public methods are thread-safe via ``threading.Lock``.

    Attributes:
        db_path: SQLite database file path (``:memory:`` for tests).
        lru_max_size: Maximum number of entries in the in-memory LRU cache.
    """

    def __init__(
        self,
        db_path: str | Path = "data/ccr_store.db",
        lru_max_size: int = 128,
    ) -> None:
        self._db_path = Path(db_path) if db_path != ":memory:" else db_path
        self._lru_max_size = lru_max_size
        self._lru: OrderedDict[str, str] = OrderedDict()
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection = self._open_connection()
        self._init_schema()

    # ------------------------------------------------------------------
    # Connection + schema
    # ------------------------------------------------------------------

    def _open_connection(self) -> sqlite3.Connection:
        if self._db_path != ":memory:":
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(
            str(self._db_path),
            check_same_thread=False,
        )
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ccr_entries (
                    trace_id      TEXT PRIMARY KEY,
                    original      TEXT NOT NULL,
                    metadata      TEXT,
                    created_at    TEXT NOT NULL,
                    last_accessed TEXT NOT NULL,
                    access_count  INTEGER DEFAULT 0
                )
                """
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_ccr_created_at ON ccr_entries(created_at)"
            )
            self._conn.commit()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def store(self, original: str, metadata: dict[str, Any] | None = None) -> str:
        """Store original content and return a trace_id for later retrieval.

        Args:
            original: The full uncompressed content to store.
            metadata: Optional metadata dict (serialized to JSON).

        Returns:
            A 16-character hex trace_id (uuid4 hex, no dashes).
        """
        trace_id = uuid.uuid4().hex
        now_iso = datetime.now().isoformat()
        meta_json = json.dumps(metadata, ensure_ascii=False) if metadata else None
        with self._lock:
            self._conn.execute(
                "INSERT INTO ccr_entries (trace_id, original, metadata, created_at, last_accessed, access_count) "
                "VALUES (?, ?, ?, ?, ?, 0)",
                (trace_id, original, meta_json, now_iso, now_iso),
            )
            self._conn.commit()
            self._lru[trace_id] = original
            self._lru.move_to_end(trace_id)
            self._evict_lru()
        return trace_id

    def retrieve(self, trace_id: str, query: str | None = None) -> str:
        """Retrieve original content by trace_id.

        Args:
            trace_id: The trace_id returned by :meth:`store`.
            query: Optional keyword query. If provided, returns only the
                lines/sentences containing any query term (case-insensitive).
                If no lines match, returns the full original.

        Returns:
            The original content (or a query-filtered excerpt). Empty string
            if trace_id not found.
        """
        original = self._fetch_and_touch(trace_id)
        if original is None:
            return ""
        if query and query.strip():
            return self._keyword_excerpt(original, query)
        return original

    def delete_expired(self, ttl_days: int = 7) -> int:
        """Delete entries older than ``ttl_days`` from both SQLite and LRU.

        Args:
            ttl_days: Maximum age in days. Entries with ``created_at`` older
                than this are deleted.

        Returns:
            Number of entries deleted.
        """
        cutoff = (datetime.now() - timedelta(days=ttl_days)).isoformat()
        with self._lock:
            cursor = self._conn.execute(
                "DELETE FROM ccr_entries WHERE created_at < ?", (cutoff,)
            )
            deleted = cursor.rowcount
            self._conn.commit()
            # Purge LRU entries no longer in DB (simpler: rebuild from survivors)
            if deleted > 0:
                survivor_rows = self._conn.execute(
                    "SELECT trace_id, original FROM ccr_entries"
                ).fetchall()
                survivor_ids = {row[0] for row in survivor_rows}
                for stale_id in list(self._lru.keys()):
                    if stale_id not in survivor_ids:
                        self._lru.pop(stale_id, None)
        return deleted

    def stats(self) -> dict[str, Any]:
        """Return store statistics for dashboard / monitoring.

        Returns:
            Dict with keys: total_entries, lru_size, lru_max_size, db_path.
        """
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) FROM ccr_entries").fetchone()
            total = row[0] if row else 0
        return {
            "total_entries": total,
            "lru_size": len(self._lru),
            "lru_max_size": self._lru_max_size,
            "db_path": str(self._db_path),
        }

    def close(self) -> None:
        """Close the SQLite connection."""
        with self._lock:
            self._conn.close()

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> CCRStore:
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _fetch_and_touch(self, trace_id: str) -> str | None:
        """Fetch original by trace_id, update access metadata, refresh LRU."""
        with self._lock:
            # LRU hit
            if trace_id in self._lru:
                self._lru.move_to_end(trace_id)
                self._touch_db(trace_id)
                return self._lru[trace_id]
            # LRU miss → SQLite
            row = self._conn.execute(
                "SELECT original FROM ccr_entries WHERE trace_id = ?", (trace_id,)
            ).fetchone()
            if row is None:
                return None
            original = cast(str, row[0])
            self._lru[trace_id] = original
            self._lru.move_to_end(trace_id)
            self._evict_lru()
            self._touch_db(trace_id)
            return original

    def _touch_db(self, trace_id: str) -> None:
        """Update last_accessed + access_count in SQLite (best-effort)."""
        now_iso = datetime.now().isoformat()
        self._conn.execute(
            "UPDATE ccr_entries SET last_accessed = ?, access_count = access_count + 1 "
            "WHERE trace_id = ?",
            (now_iso, trace_id),
        )
        self._conn.commit()

    def _evict_lru(self) -> None:
        """Evict oldest LRU entries until size <= lru_max_size. Caller holds lock."""
        while len(self._lru) > self._lru_max_size:
            self._lru.popitem(last=False)

    @staticmethod
    def _keyword_excerpt(original: str, query: str) -> str:
        """Return lines containing any query term (case-insensitive).

        If no lines match, return the full original. This is a lightweight
        stand-in for full BM25 retrieval (YAGNI — ponytail rule).
        """
        terms = [t.lower() for t in query.split() if t.strip()]
        if not terms:
            return original
        lines = original.splitlines()
        matched = [
            line for line in lines if any(term in line.lower() for term in terms)
        ]
        return "\n".join(matched) if matched else original
