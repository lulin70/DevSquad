#!/usr/bin/env python3
"""V4.5.11 HostLLMBridge retention / PRUNE_MAX_FILES unit tests."""
from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from scripts.collaboration.host_llm_bridge import (
    HostLLMBridge,
)
from scripts.collaboration.host_llm_bridge import (
    _prune_old_files as v1_prune,
)
from scripts.collaboration.host_llm_bridge_v2 import HostLLMBridgeV2


def _write_old(path: Path, mtime: float) -> None:
    path.write_text("{}", encoding="utf-8")
    os.utime(path, (mtime, mtime))


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEVSQUAD_BRIDGE_PRUNE_MAX_FILES", raising=False)


# ---- v2 ----


def test_v2_prune_default_keeps_latest_100(tmp_path: Path) -> None:
    bridge = HostLLMBridgeV2(bridge_dir=tmp_path / "v2")
    now = time.time()
    for i in range(120):
        _write_old(bridge.bridge_dir / f"request_r{i:04d}.json", now - (120 - i))
    removed = bridge._prune_old_files(bridge.bridge_dir, bridge._resolve_prune_max_files())
    assert removed == 20
    remaining = sorted(p.name for p in bridge.bridge_dir.iterdir())
    assert len(remaining) == 100
    assert remaining[0] == "request_r0020.json"
    assert remaining[-1] == "request_r0119.json"


def test_v2_prune_env_override_zero_disables(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEVSQUAD_BRIDGE_PRUNE_MAX_FILES", "0")
    bridge = HostLLMBridgeV2(bridge_dir=tmp_path / "v2")
    now = time.time()
    for i in range(50):
        _write_old(bridge.bridge_dir / f"request_r{i:04d}.json", now + i)
    removed = bridge._prune_old_files(bridge.bridge_dir, bridge._resolve_prune_max_files())
    assert removed == 0
    assert len(list(bridge.bridge_dir.iterdir())) == 50


def test_v2_prune_env_override_5_keeps_five(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEVSQUAD_BRIDGE_PRUNE_MAX_FILES", "5")
    bridge = HostLLMBridgeV2(bridge_dir=tmp_path / "v2")
    now = time.time()
    for i in range(15):
        _write_old(bridge.bridge_dir / f"request_r{i:04d}.json", now + i)
    removed = bridge._prune_old_files(bridge.bridge_dir, bridge._resolve_prune_max_files())
    assert removed == 10
    remaining = sorted(p.name for p in bridge.bridge_dir.iterdir())
    assert len(remaining) == 5
    assert remaining[-1] == "request_r0014.json"


def test_v2_prune_skips_marker_and_tmp(tmp_path: Path) -> None:
    bridge = HostLLMBridgeV2(bridge_dir=tmp_path / "v2")
    now = time.time()
    for i in range(110):
        _write_old(bridge.bridge_dir / f"request_r{i:04d}.json", now - (110 - i))
    marker = bridge.bridge_dir / HostLLMBridgeV2.MARKER_FILENAME
    _write_old(marker, now - 9999)
    tmp_file = bridge.bridge_dir / "request_r0001.json.tmp"
    _write_old(tmp_file, now - 9999)
    removed = bridge._prune_old_files(bridge.bridge_dir, bridge._resolve_prune_max_files())
    assert removed == 10
    assert marker.exists()
    assert tmp_file.exists()


def test_v2_resolve_prune_max_files_rejects_negative(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEVSQUAD_BRIDGE_PRUNE_MAX_FILES", "-1")
    with pytest.raises(ValueError):
        HostLLMBridgeV2._resolve_prune_max_files()


def test_v2_resolve_prune_max_files_rejects_garbage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEVSQUAD_BRIDGE_PRUNE_MAX_FILES", "abc")
    with pytest.raises(ValueError):
        HostLLMBridgeV2._resolve_prune_max_files()


# ---- v1 ----


def test_v1_prune_helper_module_level(tmp_path: Path) -> None:
    bridge_dir = tmp_path / "v1"
    bridge_dir.mkdir()
    now = time.time()
    for i in range(105):
        _write_old(bridge_dir / f"request_r{i:04d}.json", now - (105 - i))
    # mark some extras that should never be touched
    marker = bridge_dir / "protocol.marker"
    _write_old(marker, now - 9999)
    removed = v1_prune(str(bridge_dir), 100)
    assert removed == 5
    assert marker.exists()
    assert len(list(bridge_dir.iterdir())) == 101  # 100 retained + marker


def test_v1_prune_helper_zero_disables(tmp_path: Path) -> None:
    bridge_dir = tmp_path / "v1"
    bridge_dir.mkdir()
    now = time.time()
    for i in range(10):
        _write_old(bridge_dir / f"request_r{i:04d}.json", now + i)
    removed = v1_prune(str(bridge_dir), 0)
    assert removed == 0
    assert len(list(bridge_dir.iterdir())) == 10


def test_v1_create_request_invokes_prune(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEVSQUAD_BRIDGE_PRUNE_MAX_FILES", "3")
    bridge_dir = tmp_path / "v1"
    bridge_dir.mkdir()
    bridge = HostLLMBridge(bridge_dir=str(bridge_dir))
    now = time.time()
    # pre-existing old files to be evicted
    for i in range(5):
        _write_old(bridge_dir / f"request_old{i:02d}.json", now - 100 + i)
    request_id = bridge.create_request(
        agent_type="architect",
        task="t",
        context={},
        prompt="p",
        timeout_seconds=10,
    )
    # 5 old + 1 new + marker = at least 7 entries before prune
    json_files = [
        p for p in bridge_dir.iterdir()
        if p.name.startswith("request_") and p.name.endswith(".json")
    ]
    assert len(json_files) == 3
    newest = max(p.name for p in json_files)
    assert newest.startswith(f"request_{request_id}")
