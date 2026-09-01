#!/usr/bin/env python3
"""V4.5.8 Wave 1 file-backed persistence for risk registers."""
from __future__ import annotations

import contextlib
import errno
import json
import logging
import math
import os
import re
import sys
import tempfile
import threading
import time
from collections import deque
from collections.abc import Iterator, MutableMapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_call_counter_er: int = 0


class RiskStoreError(Exception):
    """Base class for FileRiskStore errors."""


class RiskStoreValidationError(RiskStoreError):
    """The register id or storage path is unsafe."""


class RiskStoreLockError(RiskStoreError):
    """The cross-process lock could not be acquired before the timeout."""


class RiskStoreCorruptError(RiskStoreError):
    """The register file is missing, malformed, or has an unsupported schema."""


SCHEMA_VERSION = 1
DEFAULT_ROOT = Path(".devsquad_data") / "risks"
_REG_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

# V4.5.12: SQLite re-project trigger thresholds (docs/prd/V4.5.10_PRD.md §6).
CAPACITY_WARNING_THRESHOLD = 10000
SLOW_QUERY_MS_THRESHOLD = 50.0
CONCURRENT_WINDOW_SECONDS = 60.0

# V4.5.13: cross-host detection (AC-CH-1..3).
# errnos whose semantics indicate remote/shared-storage failure rather than
# local contention (EAGAIN == local contention is intentionally excluded).
_REMOTE_ERRNOS: frozenset[int] = frozenset(
    value
    for name in ("ESTALE", "EREMOTE", "EBADRPC")
    for value in (getattr(errno, name, None),)
    if value is not None
)
# Cache "once per store instance" flag attribute name to avoid re-detecting.
_REMOTE_FS_FLAG = "_remote_fs_recorded"


def _looks_like_remote_fs(path: Path) -> bool:
    """Best-effort remote-filesystem detection via statvfs ST_REMOTE.

    Returns False when the platform does not expose ST_REMOTE (macOS) or
    statvfs fails — never raises (observability must not break the store).
    """
    st_remote = getattr(os, "ST_REMOTE", 0)
    if not st_remote:  # macOS/Windows: flag not defined → no-op (AC-CH-3)
        return False
    try:
        return bool(os.statvfs(path).f_flag & st_remote)
    except (OSError, AttributeError, ValueError):
        return False


def get_call_counter_er() -> int:
    """Return the module-level anti-ghost counter."""
    return _call_counter_er


def _inc_call_counter_er() -> None:
    global _call_counter_er
    _call_counter_er += 1


# ---------------------------------------------------------------------------
# V4.5.12: RiskStoreStats — SQLite re-project trigger observability (AC-SQL-1..4)
# ---------------------------------------------------------------------------

_call_counter_stats_er: int = 0
_stats_counter_lock = threading.Lock()


def get_risk_store_stats_counter_er() -> int:
    """Return the V4.5.12 stats activation counter (anti-ghost)."""
    return _call_counter_stats_er


def _inc_risk_store_stats_counter_er() -> None:
    global _call_counter_stats_er
    with _stats_counter_lock:
        _call_counter_stats_er += 1


@dataclass
class RiskStoreStats:
    """Aggregated observability signals for a ``FileRiskStore``.

    Exposes the four SQLite re-project trigger conditions from
    ``docs/prd/V4.5.10_PRD.md`` §6 without leaking register contents:

    - ``capacity``: item count at the most recent load/save (trigger: >10k)
    - ``concurrent_writes_1m``: writes in the last 60s sliding window
      (trigger: sustained high rate across services)
    - ``cross_host_lock_signals``: lock acquisitions from a different host
      signature (trigger: remote-shared storage)
    - ``slow_query_signals``: query+filter rounds exceeding
      ``SLOW_QUERY_MS_THRESHOLD`` (trigger: complex query demand)

    Aggregated numbers only — no risk content, register_id, or user data.
    """

    capacity: int = 0
    concurrent_writes_1m: int = 0
    cross_host_lock_signals: int = 0
    slow_query_signals: int = 0
    last_updated: float = 0.0
    _write_times: deque[float] = field(default_factory=deque, repr=False, compare=False)

    def record_write(self, item_count: int, now: float | None = None) -> None:
        """Record a completed write with the resulting item count."""
        now = time.monotonic() if now is None else now
        self.capacity = item_count
        self.last_updated = now
        window_start = now - CONCURRENT_WINDOW_SECONDS
        times = self._write_times
        times.append(now)
        while times and times[0] < window_start:
            times.popleft()
        self.concurrent_writes_1m = len(times)

    def record_load(self, item_count: int, now: float | None = None) -> None:
        """Record a completed load with the observed item count."""
        now = time.monotonic() if now is None else now
        self.capacity = item_count
        self.last_updated = now

    def record_cross_host_signal(self) -> None:
        """Record one cross-host lock acquisition signal."""
        self.cross_host_lock_signals += 1
        self.last_updated = time.monotonic()

    def record_slow_query(self, duration_ms: float, now: float | None = None) -> None:
        """Record one slow-query signal when ``duration_ms`` exceeds threshold."""
        if duration_ms > SLOW_QUERY_MS_THRESHOLD:
            self.slow_query_signals += 1
            self.last_updated = time.monotonic() if now is None else now

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe snapshot (no deque internals)."""
        return {
            "capacity": self.capacity,
            "concurrent_writes_1m": self.concurrent_writes_1m,
            "cross_host_lock_signals": self.cross_host_lock_signals,
            "slow_query_signals": self.slow_query_signals,
            "last_updated": self.last_updated,
        }


def _validate_register_id(register_id: str) -> None:
    if not isinstance(register_id, str) or _REG_ID_PATTERN.fullmatch(register_id) is None:
        raise RiskStoreValidationError(
            f"register_id {register_id!r} must match [A-Za-z0-9_-]{{1,64}}"
        )


def _resolved_root(root: Path) -> Path:
    if root.exists() and root.is_symlink():
        raise RiskStoreValidationError(f"Refusing symlinked risk store root: {root}")
    return root.resolve()


def _safe_path(root: Path, register_id: str, suffix: str = ".json") -> Path:
    _validate_register_id(register_id)
    root_resolved = _resolved_root(root)
    raw = root / f"{register_id}{suffix}"
    if raw.is_symlink():
        raise RiskStoreValidationError(f"Refusing symlinked canonical path: {raw}")
    candidate = raw.resolve()
    try:
        common = os.path.commonpath((str(root_resolved), str(candidate)))
    except ValueError as exc:
        raise RiskStoreValidationError(f"Path is outside risk store root: {candidate}") from exc
    if common != str(root_resolved):
        raise RiskStoreValidationError(f"Path is outside risk store root: {candidate}")
    return candidate


def _empty_payload(register_id: str) -> dict[str, Any]:
    return {"version": SCHEMA_VERSION, "register_id": register_id, "items": []}


def _enum_value(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _check_item(raw: Any, index: int) -> None:
    if not isinstance(raw, dict):
        raise RiskStoreCorruptError(f"items[{index}] must be an object")
    required = ("id", "description", "probability", "impact", "response_strategy", "status")
    missing = [key for key in required if key not in raw]
    if missing:
        raise RiskStoreCorruptError(f"items[{index}] missing fields: {', '.join(missing)}")
    if not isinstance(raw["id"], str) or not isinstance(raw["description"], str):
        raise RiskStoreCorruptError(f"items[{index}] id and description must be strings")
    if not isinstance(raw["probability"], (int, float)) or not isinstance(raw["impact"], (int, float)):
        raise RiskStoreCorruptError(f"items[{index}] probability and impact must be numbers")
    if not isinstance(raw["response_strategy"], str) or not isinstance(raw["status"], str):
        raise RiskStoreCorruptError(f"items[{index}] enum fields must be strings")
    if "owner" in raw and not isinstance(raw["owner"], str):
        raise RiskStoreCorruptError(f"items[{index}] owner must be a string")
    if "category" in raw and not isinstance(raw["category"], str):
        raise RiskStoreCorruptError(f"items[{index}] category must be a string")


def _check_payload(payload: Any, register_id: str) -> None:
    if not isinstance(payload, dict):
        raise RiskStoreCorruptError("Risk store JSON top-level value must be an object")
    if payload.get("version") != SCHEMA_VERSION:
        raise RiskStoreCorruptError(f"Unsupported risk store schema version: {payload.get('version')!r}")
    if payload.get("register_id") != register_id:
        raise RiskStoreCorruptError(
            f"Risk store register_id mismatch: {payload.get('register_id')!r} != {register_id!r}"
        )
    items = payload.get("items")
    if not isinstance(items, list):
        raise RiskStoreCorruptError("Risk store field 'items' must be a list")
    for index, raw in enumerate(items):
        _check_item(raw, index)


def _item_to_dict(item: Any) -> dict[str, Any]:
    return {
        "id": item.id,
        "description": item.description,
        "probability": float(item.probability),
        "impact": float(item.impact),
        "response_strategy": _enum_value(item.response_strategy),
        "owner": item.owner,
        "status": _enum_value(item.status),
        "category": item.category,
    }


def _items_to_payload(register_id: str, items: Iterator[Any]) -> dict[str, Any]:
    return {
        "version": SCHEMA_VERSION,
        "register_id": register_id,
        "items": [_item_to_dict(item) for item in items],
    }


def _fcntl_lock(handle: Any, timeout: float) -> None:
    import fcntl

    deadline = time.monotonic() + timeout
    while True:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except BlockingIOError:
            if time.monotonic() >= deadline:
                raise RiskStoreLockError(
                    f"Could not acquire risk store lock within {timeout:.3f}s"
                ) from None
            time.sleep(min(0.05, max(0.001, deadline - time.monotonic())))
        except OSError as exc:
            # V4.5.13: remote-semantics errno → re-raise so the caller can
            # record a cross-host signal; other OSErrors keep propagating.
            if exc.errno in _REMOTE_ERRNOS:
                raise
            if time.monotonic() >= deadline:
                raise RiskStoreLockError(
                    f"Could not acquire risk store lock within {timeout:.3f}s"
                ) from None
            time.sleep(min(0.05, max(0.001, deadline - time.monotonic())))


def _fcntl_unlock(handle: Any) -> None:
    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _msvcrt_lock(handle: Any, timeout: float) -> None:
    import msvcrt

    deadline = time.monotonic() + timeout
    while True:
        try:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            return
        except OSError:
            if time.monotonic() >= deadline:
                raise RiskStoreLockError(
                    f"Could not acquire risk store lock within {timeout:.3f}s"
                ) from None
            time.sleep(min(0.05, max(0.001, deadline - time.monotonic())))


def _msvcrt_unlock(handle: Any) -> None:
    import msvcrt

    try:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    except OSError:
        pass


def _acquire_lock(handle: Any, timeout: float) -> None:
    if sys.platform == "win32":
        _msvcrt_lock(handle, timeout)
    else:
        _fcntl_lock(handle, timeout)


def _release_lock(handle: Any) -> None:
    if sys.platform == "win32":
        _msvcrt_unlock(handle)
    else:
        _fcntl_unlock(handle)


class FileRiskStore:
    """Persist RiskRegister payloads under ``.devsquad_data/risks``."""

    def __init__(self, root: Path | str = DEFAULT_ROOT, lock_timeout: float = 5.0) -> None:
        # math.isfinite rejects NaN and ±Inf: a NaN deadline would never be
        # reached by ``time.monotonic() >= deadline`` and hang the lock loop.
        if not math.isfinite(lock_timeout) or lock_timeout < 0:
            raise ValueError("lock_timeout must be a finite non-negative number")
        self.root = Path(root)
        self.lock_timeout = float(lock_timeout)
        # register_ids currently locked by an active transaction on this
        # instance. flock is per-fd, so re-acquiring the same exclusive lock
        # from load()/save() inside a transaction would deadlock; guard it.
        self._active_transactions: set[str] = set()
        # V4.5.12: SQLite re-project trigger observability (AC-SQL-1).
        self.stats = RiskStoreStats()
        # V4.5.13: auto cross-host signal on remote filesystem (AC-CH-1).
        if _looks_like_remote_fs(self.root):
            self.stats.record_cross_host_signal()
            setattr(self, _REMOTE_FS_FLAG, True)

    def _paths(self, register_id: str) -> tuple[Path, Path]:
        return _safe_path(self.root, register_id), _safe_path(self.root, register_id, ".lock")

    def _open_lock(self, lock_path: Path) -> Any:
        _resolved_root(self.root)
        self.root.mkdir(parents=True, exist_ok=True)
        if lock_path.is_symlink():
            raise RiskStoreValidationError(f"Refusing symlinked lock path: {lock_path}")
        # V4.5.13: re-check remote fs once per instance after mount appears.
        if not getattr(self, _REMOTE_FS_FLAG, False) and _looks_like_remote_fs(self.root):
            self.stats.record_cross_host_signal()
            setattr(self, _REMOTE_FS_FLAG, True)
        handle = open(lock_path, "a+b")  # noqa: SIM115
        try:
            _acquire_lock(handle, self.lock_timeout)
        except OSError as exc:
            # V4.5.13: remote-semantics errno → auto signal (AC-CH-2).
            if exc.errno in _REMOTE_ERRNOS:
                self.stats.record_cross_host_signal()
            handle.close()
            raise
        except Exception:
            handle.close()
            raise
        return handle

    def _read_payload(self, target: Path, register_id: str) -> dict[str, Any]:
        if not target.exists():
            return _empty_payload(register_id)
        if target.is_symlink():
            raise RiskStoreValidationError(f"Refusing symlinked canonical file: {target}")
        try:
            with target.open(encoding="utf-8") as handle:
                payload = json.load(handle)
        except json.JSONDecodeError as exc:
            raise RiskStoreCorruptError(f"Corrupt JSON in risk store {target}: {exc.msg}") from exc
        except OSError as exc:
            raise RiskStoreCorruptError(f"Cannot read risk store {target}: {exc}") from exc
        _check_payload(payload, register_id)
        return payload

    def _atomic_write(self, target: Path, payload: dict[str, Any]) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, ensure_ascii=False)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
            try:
                directory_fd = os.open(target.parent, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            except OSError:
                logger.debug("Directory fsync unavailable for %s", target.parent)
        except Exception:  # noqa: BLE001
            with contextlib.suppress(OSError):
                os.unlink(temporary)
            raise

    def _check_not_in_transaction(self, register_id: str) -> None:
        if register_id in self._active_transactions:
            raise RiskStoreError(
                f"register '{register_id}' is locked by an active transaction on "
                "this store; call load()/save() outside the transaction or use "
                "the transaction payload directly"
            )

    def load(self, register_id: str) -> dict[str, Any]:
        """Load a validated payload while holding the cross-process lock."""
        _inc_call_counter_er()
        _inc_risk_store_stats_counter_er()
        self._check_not_in_transaction(register_id)
        target, lock_path = self._paths(register_id)
        handle = self._open_lock(lock_path)
        try:
            payload = self._read_payload(target, register_id)
            # V4.5.12: capacity signal (AC-SQL-2).
            self.stats.record_load(len(payload.get("items", [])))
            return payload
        finally:
            _release_lock(handle)
            handle.close()

    def save(self, register_id: str, payload: dict[str, Any]) -> None:
        """Validate and atomically save a payload under the cross-process lock."""
        _inc_call_counter_er()
        _inc_risk_store_stats_counter_er()
        _check_payload(payload, register_id)
        self._check_not_in_transaction(register_id)
        target, lock_path = self._paths(register_id)
        handle = self._open_lock(lock_path)
        try:
            if target.is_symlink():
                raise RiskStoreValidationError(f"Refusing symlinked canonical file: {target}")
            self._atomic_write(target, payload)
            # V4.5.12: capacity + concurrent-write sliding window (AC-SQL-2).
            self.stats.record_write(len(payload.get("items", [])))
        finally:
            _release_lock(handle)
            handle.close()

    def transaction(self, register_id: str) -> FileRiskStoreTransaction:
        """Create a context manager for one locked read-modify-write transaction."""
        _inc_call_counter_er()
        _inc_risk_store_stats_counter_er()
        target, lock_path = self._paths(register_id)
        return FileRiskStoreTransaction(self, register_id, target, lock_path)

    def items_to_payload(self, register_id: str, items: dict[str, Any] | Iterator[Any]) -> dict[str, Any]:
        """Serialize RiskItem objects to schema v1."""
        _inc_call_counter_er()
        values = items.values() if isinstance(items, dict) else items
        payload = _items_to_payload(register_id, values)
        _check_payload(payload, register_id)
        return payload

    def payload_to_items(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Deserialize a validated schema v1 payload into ``{id: RiskItem}``."""
        _inc_call_counter_er()
        from .risk_register import RiskItem

        items: dict[str, RiskItem] = {}
        for raw in payload.get("items", []):
            item = RiskItem.from_dict(raw)
            items[item.id] = item
        return items


class FileRiskStoreTransaction(MutableMapping[str, Any]):
    """Mapping-compatible transaction handle returned by ``transaction``."""

    def __init__(self, store: FileRiskStore, register_id: str, target: Path, lock_path: Path) -> None:
        self._store = store
        self.register_id = register_id
        self._target = target
        self._lock_path = lock_path
        self._handle: Any | None = None
        self._payload: dict[str, Any] | None = None

    @property
    def payload(self) -> dict[str, Any]:
        if self._payload is None:
            raise RiskStoreError("Transaction is not active")
        return self._payload

    def __getitem__(self, key: str) -> Any:
        return self.payload[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.payload[key] = value

    def __delitem__(self, key: str) -> None:
        del self.payload[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.payload)

    def __len__(self) -> int:
        return len(self.payload)

    def __enter__(self) -> FileRiskStoreTransaction:
        if self._handle is not None:
            raise RiskStoreError("Transaction is already active")
        self._store._active_transactions.add(self.register_id)
        self._handle = self._store._open_lock(self._lock_path)
        try:
            self._payload = self._store._read_payload(self._target, self.register_id)
        except Exception:
            self._store._active_transactions.discard(self.register_id)
            _release_lock(self._handle)
            self._handle.close()
            self._handle = None
            raise
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        try:
            if exc_type is None:
                payload = self.payload
                _check_payload(payload, self.register_id)
                if self._target.is_symlink():
                    raise RiskStoreValidationError(
                        f"Refusing symlinked canonical file: {self._target}"
                    )
                self._store._atomic_write(self._target, payload)
                # V4.5.12: transaction commit is a write (AC-SQL-2).
                self._store.stats.record_write(len(payload.get("items", [])))
        finally:
            if self._handle is not None:
                _release_lock(self._handle)
                self._handle.close()
                self._handle = None
            self._payload = None
            self._store._active_transactions.discard(self.register_id)
        return False


__all__ = [
    "CAPACITY_WARNING_THRESHOLD",
    "CONCURRENT_WINDOW_SECONDS",
    "DEFAULT_ROOT",
    "FileRiskStore",
    "FileRiskStoreTransaction",
    "RiskStoreCorruptError",
    "RiskStoreError",
    "RiskStoreLockError",
    "RiskStoreStats",
    "RiskStoreValidationError",
    "SCHEMA_VERSION",
    "SLOW_QUERY_MS_THRESHOLD",
    "get_call_counter_er",
    "get_risk_store_stats_counter_er",
]
