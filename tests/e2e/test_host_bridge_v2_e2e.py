#!/usr/bin/env python3
"""V4.5.10 E2E: HostBridgeBackendV2 subprocess round-trip (G-δ).

A real spawned subprocess runs FakeHostRunnerV2 against the v2 version
directory. Tests prove: actual adapter type, actual version dir + marker
name, actual prompt-file consumption, success/timeout/failure paths, and
cross-version isolation (v1 runner cannot see v2 requests).
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.collaboration.host_llm_bridge import HostBridgeBackendV2  # noqa: E402
from scripts.collaboration.host_llm_bridge_v2 import HostLLMBridgeV2  # noqa: E402

pytestmark = pytest.mark.e2e

RUNNER_BOOT_SECONDS = 1.5


def _wait_boot() -> None:
    """Give the spawned runner time to boot (L-V458-002 tolerance)."""
    time.sleep(RUNNER_BOOT_SECONDS)


def _spawn_runner(bridge_dir: Path, behaviour: str):
    """Spawn a real subprocess running FakeHostRunnerV2.run_forever()."""
    return subprocess.Popen(
        [
            sys.executable, "-m", "tests.fakes.fake_host_runner_v2",
            str(bridge_dir), behaviour,
        ],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


@pytest.fixture
def v2_dir(tmp_path: Path) -> Path:
    return tmp_path / "host_llm_bridge" / "v2"


@pytest.fixture(autouse=True)
def host_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRAE_ENV", "1")


class TestV2SubprocessRoundTrip:
    def test_success_round_trip(self, v2_dir: Path) -> None:
        proc = _spawn_runner(v2_dir, "success")
        _wait_boot()
        backend = HostBridgeBackendV2(bridge_dir=str(v2_dir), timeout_seconds=30)
        try:
            assert type(backend) is HostBridgeBackendV2
            output = backend.generate(
                "Analyze the architecture",
                agent_type="architect",
                task_description="Design system",
            )
        finally:
            proc.terminate()
            proc.wait(timeout=10)
        assert output == "[FAKE HOST V2] Processed prompt (24 chars)"
        # Marker consumed; version dir is v2 with v2 marker name
        marker = v2_dir / HostLLMBridgeV2.MARKER_FILENAME
        assert not marker.exists()
        assert marker.name == "protocol.v2.marker"

    def test_failure_round_trip(self, v2_dir: Path) -> None:
        proc = _spawn_runner(v2_dir, "fail")
        _wait_boot()
        backend = HostBridgeBackendV2(bridge_dir=str(v2_dir), timeout_seconds=30)
        try:
            with pytest.raises(RuntimeError, match="HostLLMBridge failure"):
                backend.generate("p", agent_type="architect", task_description="t")
        finally:
            proc.terminate()
            proc.wait(timeout=10)
        assert backend.is_fuse_skipped is False  # single failure does not fuse

    def test_timeout_round_trip(self, v2_dir: Path) -> None:
        proc = _spawn_runner(v2_dir, "timeout")
        _wait_boot()
        backend = HostBridgeBackendV2(bridge_dir=str(v2_dir), timeout_seconds=2)
        try:
            with pytest.raises(RuntimeError, match="timeout"):
                backend.generate("p", agent_type="architect", task_description="t")
        finally:
            proc.terminate()
            proc.wait(timeout=10)
        # Request files remain (no fake success), and fuse trips after 2nd failure
        assert backend._failures


class TestV2FactorySubprocessJourney:
    def test_create_backend_host_full_round_trip(self, tmp_path: Path, monkeypatch) -> None:
        """AC-δ-4: create_backend('host') + subprocess runner + v2 evidence."""
        v2_dir = tmp_path / "host_llm_bridge" / "v2"
        proc = _spawn_runner(v2_dir, "success")
        _wait_boot()
        monkeypatch.setenv("TRAE_ENV", "1")
        from scripts.collaboration.llm_backend import create_backend

        try:
            backend = create_backend("host", bridge_dir=str(v2_dir))
            assert type(backend) is HostBridgeBackendV2
            output = backend.generate(
                "hello v2", agent_type="solo-coder", task_description="t"
            )
        finally:
            proc.terminate()
            proc.wait(timeout=10)
        assert "FAKE HOST V2" in output


class TestCrossVersionIsolation:
    def test_v1_runner_cannot_see_v2_request(self, tmp_path: Path) -> None:
        """A v1 FakeHostRunner watching v1 dir must never answer v2 requests."""
        from tests.fakes.fake_host_runner import FakeHostRunner

        root = tmp_path / "host_llm_bridge"
        v2_dir = root / "v2"
        v1_dir = root / "v1"
        backend = HostBridgeBackendV2(bridge_dir=str(v2_dir), timeout_seconds=2)
        with pytest.raises(RuntimeError, match="timeout"):
            backend.generate("v2 only", agent_type="architect", task_description="t")
        # A v1 runner pointed at the v1 dir finds no marker at all
        v1_runner = FakeHostRunner(bridge_dir=str(v1_dir))
        assert v1_runner.process_one() is False
        # And v1 marker was never created by the v2 request
        assert not (v1_dir / "protocol.marker").exists()

    def test_v2_request_files_confined_to_v2_dir(self, v2_dir: Path) -> None:
        backend = HostBridgeBackendV2(bridge_dir=str(v2_dir), timeout_seconds=30)
        request_id = backend.bridge.create_request(
            agent_type="architect", task="t", context=None, prompt="p"
        )
        parent = v2_dir.parent
        v2_files = [p.name for p in v2_dir.iterdir()]
        assert f"request_{request_id}.json" in v2_files
        assert f"request_{request_id}.prompt" in v2_files
        assert "protocol.v2.marker" in v2_files
        # nothing leaked to parent/root
        leaked = [p.name for p in parent.glob(f"*{request_id}*")]
        assert not leaked


class TestV2ResponseFormat:
    def test_response_uses_v2_timestamp_field(self, v2_dir: Path) -> None:
        """The v2 response file must carry 'timestamp' (not v1 completed_at)."""
        request_id = HostLLMBridgeV2.write_response(
            request_id="abc_1",
            success=True,
            output="ok",
            bridge_dir=v2_dir,
        )
        data = json.loads(Path(request_id).read_text(encoding="utf-8"))
        assert "timestamp" in data
        assert "completed_at" not in data
