"""Unit tests for V4.5.13 cross-host auto-signal instrumentation (AC-CH-1..3)."""

from __future__ import annotations

import errno
import os
from pathlib import Path

import pytest

from scripts.collaboration.file_risk_store import (
    _REMOTE_ERRNOS,
    FileRiskStore,
    _looks_like_remote_fs,
)

pytestmark = pytest.mark.unit


class TestRemoteFsDetection:
    def test_st_remote_set_records_signal_at_init(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(os, "ST_REMOTE", 1 << 25, raising=False)
        monkeypatch.setattr(
            os, "statvfs", lambda _p: type("SV", (), {"f_flag": 1 << 25})(), raising=False
        )
        store = FileRiskStore(root=tmp_path)
        assert store.stats.cross_host_lock_signals == 1

    def test_st_remote_unset_is_noop(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(os, "ST_REMOTE", 0, raising=False)
        store = FileRiskStore(root=tmp_path)
        assert store.stats.cross_host_lock_signals == 0

    def test_platform_without_st_remote_is_noop(self, tmp_path: Path, monkeypatch) -> None:
        if hasattr(os, "ST_REMOTE"):
            monkeypatch.delattr(os, "ST_REMOTE", raising=False)
        assert _looks_like_remote_fs(tmp_path) is False
        store = FileRiskStore(root=tmp_path)
        assert store.stats.cross_host_lock_signals == 0

    def test_statvfs_failure_returns_false(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(os, "ST_REMOTE", 1 << 25, raising=False)

        def _boom(_p):
            raise OSError(errno.EIO)

        monkeypatch.setattr(os, "statvfs", _boom, raising=False)
        assert _looks_like_remote_fs(tmp_path) is False


class TestRemoteErrnoSignal:
    def test_remote_errno_constant_excludes_eagain(self) -> None:
        assert errno.EAGAIN not in _REMOTE_ERRNOS
        assert errno.EWOULDBLOCK not in _REMOTE_ERRNOS

    def test_remote_errno_is_reraised_and_signal_recorded(self, tmp_path: Path, monkeypatch) -> None:
        import scripts.collaboration.file_risk_store as frs

        store = FileRiskStore(root=tmp_path, lock_timeout=0.5)

        def _remote_fail(_handle, _timeout):
            raise OSError(errno.ESTALE, "Stale NFS file handle")

        monkeypatch.setattr(frs, "_acquire_lock", _remote_fail)
        with pytest.raises(OSError, match="Stale"):
            store.load("default")
        assert store.stats.cross_host_lock_signals >= 1

    def test_local_contention_does_not_record_signal(self, tmp_path: Path) -> None:
        store = FileRiskStore(root=tmp_path, lock_timeout=0.5)
        with store.transaction("default"):
            tight = FileRiskStore(root=tmp_path, lock_timeout=0.1)
            with pytest.raises(Exception):  # noqa: B017 — RiskStoreLockError expected
                tight.load("default")
        # Local EAGAIN contention must NOT be a cross-host signal.
        assert tight.stats.cross_host_lock_signals == 0
