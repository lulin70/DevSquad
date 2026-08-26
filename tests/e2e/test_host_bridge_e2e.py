#!/usr/bin/env python3
"""
E2E tests for HostLLMBridge via FakeHostRunner in subprocess isolation (V4.5.2 §5.5).

Covers T9 (subprocess e2e) and T10 (dispatch integration) from the test plan.

Uses multiprocessing.Process to run FakeHostRunner in a separate process,
simulating real CI conditions where the host and bridge are separate processes.
"""

import multiprocessing
import os
import sys
import time

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from scripts.collaboration.host_llm_bridge import HostLLMBridge  # noqa: E402
from scripts.collaboration.llm_backend import create_backend  # noqa: E402
from tests.fakes.fake_host_runner import FakeHostRunner  # noqa: E402

pytestmark = pytest.mark.e2e


# ---------------------------------------------------------------------------
# T9 — Subprocess e2e: create request, host answers in separate process
# ---------------------------------------------------------------------------


class TestT9SubprocessE2E:
    """FakeHostRunner runs in a subprocess; bridge reads the response."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path):
        self.bridge_dir = str(tmp_path)

    def _start_host(self, behaviour: str = "success", delay: float = 0.0):
        """Start FakeHostRunner in a subprocess."""
        proc = multiprocessing.Process(
            target=FakeHostRunner(
                bridge_dir=self.bridge_dir,
                behaviour=behaviour,
                delay_seconds=delay,
            ).run_forever,
            kwargs={"max_iterations": 200},
        )
        proc.start()
        # Give host time to start scanning
        time.sleep(0.1)
        return proc

    def test_subprocess_success_round_trip(self, tmp_path):
        """Host in subprocess reads marker, writes success response."""
        proc = self._start_host("success")
        try:
            bridge = HostLLMBridge(bridge_dir=self.bridge_dir)
            rid = bridge.create_request(
                agent_type="architect",
                task="e2e test",
                context={"role": "architect"},
                prompt="e2e prompt",
            )
            result = bridge.wait_for_response(rid, timeout=10)
            assert result["success"] is True
            assert "Processed prompt" in result["output"]
        finally:
            proc.terminate()
            proc.join(timeout=3)

    def test_subprocess_failure_response(self, tmp_path):
        """Host in subprocess writes failure response."""
        proc = self._start_host("fail")
        try:
            bridge = HostLLMBridge(bridge_dir=self.bridge_dir)
            rid = bridge.create_request(
                agent_type="tester",
                task="e2e fail",
                context={},
                prompt="fail me",
            )
            result = bridge.wait_for_response(rid, timeout=10)
            assert result["success"] is False
            assert result["error"] == "mock_fail"
        finally:
            proc.terminate()
            proc.join(timeout=3)

    def test_subprocess_timeout(self, tmp_path):
        """Host never responds; bridge times out."""
        # Do NOT start host → no one writes response
        bridge = HostLLMBridge(bridge_dir=self.bridge_dir)
        rid = bridge.create_request(
            agent_type="architect",
            task="timeout",
            context={},
            prompt="timeout test",
        )
        result = bridge.wait_for_response(rid, timeout=2)
        assert result["success"] is False
        assert result.get("timeout") is True


# ---------------------------------------------------------------------------
# T10 — Dispatch integration: create_backend("host") + generate
# ---------------------------------------------------------------------------


class TestT10DispatchIntegration:
    """HostBridgeBackend via create_backend("host") with host in subprocess."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path, monkeypatch):
        self.bridge_dir = str(tmp_path)
        # Ensure no real host env vars leak
        for v in ("TRAE_ENV", "TRAE_AGENT_PATH", "CLAUDE_CODE_ENV", "ANTHROPIC_ENV"):
            monkeypatch.delenv(v, raising=False)
        monkeypatch.setenv("TRAE_ENV", "1")  # Simulate host presence

    def _start_host(self, behaviour: str = "success", delay: float = 0.0):
        proc = multiprocessing.Process(
            target=FakeHostRunner(
                bridge_dir=self.bridge_dir,
                behaviour=behaviour,
                delay_seconds=delay,
            ).run_forever,
            kwargs={"max_iterations": 200},
        )
        proc.start()
        time.sleep(0.1)
        return proc

    def test_create_backend_host_with_success(self, tmp_path, monkeypatch):
        """create_backend('host') returns HostBridgeBackend; generate works."""
        # Override bridge_dir via env var or we use the default
        backend = create_backend(
            "host",
            bridge_dir=self.bridge_dir,
            timeout_seconds=10,
        )
        assert backend.path == "B"

        proc = self._start_host("success")
        try:
            result = backend.generate("hello from dispatch", role_name="architect")
            assert isinstance(result, str)
            assert "Processed prompt" in result
        finally:
            proc.terminate()
            proc.join(timeout=3)

    def test_create_backend_host_with_failure(self, tmp_path, monkeypatch):
        """HostBridgeBackend handles host failure gracefully."""
        backend = create_backend(
            "host",
            bridge_dir=self.bridge_dir,
            timeout_seconds=5,
        )
        assert backend.path == "B"

        proc = self._start_host("fail")
        try:
            with pytest.raises(RuntimeError, match="HostLLMBridge failure"):
                backend.generate("fail test", role_name="architect")
        finally:
            proc.terminate()
            proc.join(timeout=3)

    def test_create_backend_host_fuse_skip(self, tmp_path, monkeypatch):
        """2 consecutive failures → B path is fuse-skipped."""
        backend = create_backend(
            "host",
            bridge_dir=self.bridge_dir,
            timeout_seconds=3,
        )
        assert backend.path == "B"

        proc = self._start_host("fail")
        try:
            for _ in range(2):
                with pytest.raises(RuntimeError):
                    backend.generate("fail", role_name="architect")
            assert backend.is_fuse_skipped is True
        finally:
            proc.terminate()
            proc.join(timeout=3)

    def test_create_backend_auto_no_host_returns_mock(self, monkeypatch):
        """When no host env and no API keys, create_backend('auto') returns MockBackend (C path)."""
        for v in ("TRAE_ENV", "TRAE_AGENT_PATH", "CLAUDE_CODE_ENV",
                  "ANTHROPIC_ENV", "DEVSQUAD_OPENAI_API_KEY",
                  "DEVSQUAD_ANTHROPIC_API_KEY", "MOKA_API_KEY"):
            monkeypatch.delenv(v, raising=False)
        backend = create_backend("auto")
        assert backend.path == "C"
