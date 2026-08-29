"""Integration tests for FileRiskStore (V4.5.8 Wave 1).

Coverage focus (≥6 cases):
- Two real processes coordinating through the same file (multiprocessing).
- Lock acquired by an external party blocks transactions cleanly.
- Transaction semantics for read-modify-write atomicity across threads.
- Corruption recovery via fail-closed semantics (no silent wipe).
- Symlink targets refused at the canonical file boundary.
- Atomic write survives concurrent writers via the shared lock.
"""
from __future__ import annotations

import json
import multiprocessing as mp
import threading
import time
from pathlib import Path

import pytest

from scripts.collaboration.file_risk_store import (
    FileRiskStore,
    RiskStoreCorruptError,
    RiskStoreLockError,
    RiskStoreValidationError,
)
from scripts.collaboration.risk_register import RiskItem

pytestmark = pytest.mark.integration


def _item(rid: str, desc: str) -> RiskItem:
    return RiskItem(id=rid, description=desc, probability=0.4, impact=0.5, category="general")


# ---------------------------------------------------------------------------
# Multiprocess workers (run in spawned subprocesses).
# ---------------------------------------------------------------------------


def _writer_process(root: str, register_id: str, count: int) -> None:
    store = FileRiskStore(root=Path(root), lock_timeout=5.0)
    items = {f"R-{i}": _item(f"R-{i}", f"writer-{i}") for i in range(count)}
    store.save(register_id, store.items_to_payload(register_id, items))


def _reader_process(root: str, register_id: str, queue: mp.Queue) -> None:  # type: ignore[type-arg]
    store = FileRiskStore(root=Path(root), lock_timeout=5.0)
    payload = store.load(register_id)
    queue.put([item["id"] for item in payload["items"]])


def _join_or_fail(proc: mp.process.BaseProcess, timeout: float = 60.0) -> None:
    """Join a spawned subprocess; fail with a clear message on timeout.

    Under a fully loaded machine (e.g. the ~35min full-regression run) a
    spawned worker may take >10s just to boot Python and import the
    collaboration package. ``exitcode is None`` after ``join(timeout)`` means
    the process was still running — treat that as an infrastructure timeout,
    not a data-loss failure.
    """
    proc.join(timeout=timeout)
    if proc.exitcode is None:
        proc.terminate()
        proc.join(timeout=5)
        pytest.fail(
            f"{proc.name} did not exit within {timeout}s "
            "(spawn boot timeout under load; not a store assertion failure)"
        )
    assert proc.exitcode == 0


class TestCrossProcessVisibility:
    def test_writer_then_reader_subprocess(self, tmp_path: Path) -> None:
        _writer_process(str(tmp_path), "default", 3)

        ctx = mp.get_context("spawn")
        queue: mp.Queue = ctx.Queue()  # type: ignore[type-arg]
        proc = ctx.Process(target=_reader_process, args=(str(tmp_path), "default", queue))
        proc.start()
        _join_or_fail(proc)
        ids = queue.get(timeout=5)
        assert sorted(ids) == ["R-0", "R-1", "R-2"]


def _transaction_worker(root: str, register_id: str, idx: int) -> None:
    store = FileRiskStore(root=Path(root), lock_timeout=5.0)
    with store.transaction(register_id) as payload:
        existing_ids = {item["id"] for item in payload["items"]}
        new_id = f"R-T{idx}"
        if new_id not in existing_ids:
            payload["items"].append(_item(new_id, f"tx-{idx}").to_dict())


class TestConcurrentWriters:
    def test_concurrent_transactions_do_not_lose_entries(self, tmp_path: Path) -> None:
        ctx = mp.get_context("spawn")
        procs = [
            ctx.Process(target=_transaction_worker, args=(str(tmp_path), "default", i))
            for i in range(4)
        ]
        for proc in procs:
            proc.start()
        for proc in procs:
            _join_or_fail(proc)

        store = FileRiskStore(root=tmp_path, lock_timeout=5.0)
        payload = store.load("default")
        ids = sorted(item["id"] for item in payload["items"])
        assert ids == ["R-T0", "R-T1", "R-T2", "R-T3"]


class TestThreadedConcurrency:
    def test_threaded_transactions_observe_initial_state(self, tmp_path: Path) -> None:
        store = FileRiskStore(root=tmp_path, lock_timeout=5.0)
        store.save(
            "default",
            store.items_to_payload("default", {"R-0": _item("R-0", "seed")}),
        )

        errors: list[BaseException] = []

        def worker(idx: int) -> None:
            try:
                with store.transaction("default") as payload:
                    payload["items"].append(_item(f"R-th{idx}", f"th-{idx}").to_dict())
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)
        assert not errors, errors

        loaded = store.load("default")
        ids = sorted(item["id"] for item in loaded["items"] if item["id"].startswith("R-th"))
        assert ids == ["R-th0", "R-th1", "R-th2", "R-th3", "R-th4"]


class TestCorruptionRecovery:
    def test_corrupt_file_is_not_wiped(self, tmp_path: Path) -> None:
        store = FileRiskStore(root=tmp_path, lock_timeout=1.0)
        store.save("default", store.items_to_payload("default", {"R-1": _item("R-1", "ok")}))
        # Overwrite with truncated bytes simulating SIGKILL mid-write.
        (tmp_path / "default.json").write_bytes(b"{")
        with pytest.raises(RiskStoreCorruptError):
            store.load("default")
        # The store must still refuse to silently overwrite a corrupt file.
        with pytest.raises(RiskStoreCorruptError):
            store.load("default")
        # Operator can manually replace the bad file; subsequent load returns empty.
        (tmp_path / "default.json").write_text(
            json.dumps({"version": 1, "register_id": "default", "items": []}),
            encoding="utf-8",
        )
        data = store.load("default")
        assert data["items"] == []


class TestSymlinkAndLockFailures:
    def test_symlink_target_under_root_refused(self, tmp_path: Path) -> None:
        store = FileRiskStore(root=tmp_path, lock_timeout=1.0)
        outside = tmp_path / "outside.json"
        outside.write_text(
            json.dumps({"version": 1, "register_id": "default", "items": []}),
            encoding="utf-8",
        )
        symlinked = tmp_path / "default.json"
        try:
            symlinked.symlink_to(outside)
            with pytest.raises(RiskStoreValidationError):
                store.load("default")
        finally:
            if symlinked.is_symlink():
                symlinked.unlink()

    def test_external_blocker_causes_lock_timeout(self, tmp_path: Path) -> None:
        store = FileRiskStore(root=tmp_path, lock_timeout=0.2)
        lock_path = tmp_path / "default.lock"
        blocker = open(lock_path, "a+b")  # noqa: SIM115
        try:
            import fcntl

            fcntl.flock(blocker.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            start = time.monotonic()
            with pytest.raises(RiskStoreLockError):
                store.load("default")
            elapsed = time.monotonic() - start
            assert 0.18 <= elapsed <= 2.0, f"timeout fired too early/late: {elapsed}"
        finally:
            import fcntl

            fcntl.flock(blocker.fileno(), fcntl.LOCK_UN)
            blocker.close()
