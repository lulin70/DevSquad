#!/usr/bin/env python3
"""V4.5.8 Wave 1 file-backed persistence for risk registers."""
from __future__ import annotations

import contextlib
import json
import logging
import math
import os
import re
import sys
import tempfile
import time
from collections.abc import Iterator, MutableMapping
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


def get_call_counter_er() -> int:
    """Return the module-level anti-ghost counter."""
    return _call_counter_er


def _inc_call_counter_er() -> None:
    global _call_counter_er
    _call_counter_er += 1


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

    def _paths(self, register_id: str) -> tuple[Path, Path]:
        return _safe_path(self.root, register_id), _safe_path(self.root, register_id, ".lock")

    def _open_lock(self, lock_path: Path) -> Any:
        _resolved_root(self.root)
        self.root.mkdir(parents=True, exist_ok=True)
        if lock_path.is_symlink():
            raise RiskStoreValidationError(f"Refusing symlinked lock path: {lock_path}")
        handle = open(lock_path, "a+b")  # noqa: SIM115
        try:
            _acquire_lock(handle, self.lock_timeout)
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
        self._check_not_in_transaction(register_id)
        target, lock_path = self._paths(register_id)
        handle = self._open_lock(lock_path)
        try:
            return self._read_payload(target, register_id)
        finally:
            _release_lock(handle)
            handle.close()

    def save(self, register_id: str, payload: dict[str, Any]) -> None:
        """Validate and atomically save a payload under the cross-process lock."""
        _inc_call_counter_er()
        _check_payload(payload, register_id)
        self._check_not_in_transaction(register_id)
        target, lock_path = self._paths(register_id)
        handle = self._open_lock(lock_path)
        try:
            if target.is_symlink():
                raise RiskStoreValidationError(f"Refusing symlinked canonical file: {target}")
            self._atomic_write(target, payload)
        finally:
            _release_lock(handle)
            handle.close()

    def transaction(self, register_id: str) -> FileRiskStoreTransaction:
        """Create a context manager for one locked read-modify-write transaction."""
        _inc_call_counter_er()
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
        finally:
            if self._handle is not None:
                _release_lock(self._handle)
                self._handle.close()
                self._handle = None
            self._payload = None
            self._store._active_transactions.discard(self.register_id)
        return False


__all__ = [
    "DEFAULT_ROOT",
    "FileRiskStore",
    "FileRiskStoreTransaction",
    "RiskStoreCorruptError",
    "RiskStoreError",
    "RiskStoreLockError",
    "RiskStoreValidationError",
    "SCHEMA_VERSION",
    "get_call_counter_er",
]
