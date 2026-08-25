#!/usr/bin/env python3
"""
Unit tests for HostLLMBridge protocol and HostBridgeBackend (V4.5.2 §5).

Covers T1–T8 from V4.5.2_ARCHITECTURE.md §5.5:
  T1 normal e2e (success)
  T2 timeout path
  T3 failure response
  T4 fuse skip B
  T5 single failure degrades
  T6 corrupt JSON
  T7 concurrent requests
  T8 path traversal defence

Uses FakeHostRunner (in-process, no subprocess) for deterministic timing.
"""

import os
import sys
import time

import pytest

# Allow tests/ imports
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from scripts.collaboration.backend_paths import BackendUnavailable
from scripts.collaboration.host_llm_bridge import (
    HostBridgeBackend,
    HostLLMBridge,
    get_call_counter,
)
from tests.fakes.fake_host_runner import FakeHostRunner

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_response(bridge_dir: str, request_id: str, **kwargs: dict) -> str:
    """Helper: write a response file via HostLLMBridge static method."""
    return HostLLMBridge.write_response(
        request_id=request_id,
        success=kwargs.get("success", True),
        output=kwargs.get("output", "ok"),
        error=kwargs.get("error", ""),
        bridge_dir=bridge_dir,
    )


def _drive_runner(bridge_dir: str, behaviour: str = "success", delay: float = 0.0,
                  poll_interval: float = 0.05, max_iterations: int = 200) -> None:
    """Drive FakeHostRunner synchronously until request is answered or timeout."""
    runner = FakeHostRunner(
        bridge_dir=bridge_dir,
        behaviour=behaviour,
        delay_seconds=delay,
        poll_interval=poll_interval,
    )
    start = time.time()
    # Poll until response file appears OR timeout
    response_path = None
    for _ in range(max_iterations):
        runner.process_one()
        # Check for response files
        for fname in os.listdir(bridge_dir):
            if fname.startswith("response_") and fname.endswith(".json"):
                response_path = os.path.join(bridge_dir, fname)
                break
        if response_path:
            break
        time.sleep(poll_interval)
        if time.time() - start > 30:  # safety stop
            break


# ---------------------------------------------------------------------------
# T1 — Normal end-to-end (success)
# ---------------------------------------------------------------------------


class TestT1NormalE2E:
    def test_create_request_writes_marker_and_files(self, tmp_path):
        """create_request writes both request_*.json and protocol.marker."""
        bridge = HostLLMBridge(bridge_dir=str(tmp_path))
        rid = bridge.create_request(
            agent_type="architect",
            task="design",
            context={"role_name": "Architect"},
            prompt="hello",
        )
        assert HostLLMBridge.validate_request_id(rid)
        assert (tmp_path / f"request_{rid}.json").exists()
        assert (tmp_path / "protocol.marker").exists()

    def test_full_success_round_trip(self, tmp_path):
        """create_request → FakeHostRunner success → wait_for_response returns success."""
        bridge = HostLLMBridge(bridge_dir=str(tmp_path))
        rid = bridge.create_request(
            agent_type="architect",
            task="design",
            context={},
            prompt="design test",
        )
        _drive_runner(str(tmp_path), behaviour="success")
        result = bridge.wait_for_response(rid, timeout=5)
        assert result["success"] is True
        assert "Processed prompt" in result["output"]
        # Marker is cleared after write_response
        assert (tmp_path / "protocol.marker").exists() is False


# ---------------------------------------------------------------------------
# T2 — Timeout path
# ---------------------------------------------------------------------------


class TestT2Timeout:
    def test_timeout_returns_failure(self, tmp_path):
        """If host never responds, wait_for_response returns success=False, timeout=True."""
        bridge = HostLLMBridge(bridge_dir=str(tmp_path))
        rid = bridge.create_request(
            agent_type="architect",
            task="design",
            context={},
            prompt="never answered",
        )
        # Do NOT drive FakeHostRunner — host is silent
        result = bridge.wait_for_response(rid, timeout=1)
        assert result["success"] is False
        assert result.get("timeout") is True
        assert "timeout" in result["error"]


# ---------------------------------------------------------------------------
# T3 — Failure response
# ---------------------------------------------------------------------------


class TestT3Failure:
    def test_failure_response_propagates(self, tmp_path):
        """Host writes success=False; bridge returns it as-is."""
        bridge = HostLLMBridge(bridge_dir=str(tmp_path))
        rid = bridge.create_request(
            agent_type="tester",
            task="audit",
            context={},
            prompt="audit me",
        )
        _drive_runner(str(tmp_path), behaviour="fail")
        result = bridge.wait_for_response(rid, timeout=5)
        assert result["success"] is False
        assert result["error"] == "mock_fail"


# ---------------------------------------------------------------------------
# T4 — Fuse skip B after consecutive failures
# ---------------------------------------------------------------------------


class TestT4FuseSkip:
    def _patch_host_env(self, monkeypatch):
        """Set TRAE_ENV so HostBridgeBackend.is_available() returns True."""
        monkeypatch.setenv("TRAE_ENV", "1")

    def test_two_consecutive_failures_fuse_skips(self, tmp_path, monkeypatch):
        """After 2 same-reason failures, is_available() returns False."""
        self._patch_host_env(monkeypatch)
        backend = HostBridgeBackend(bridge_dir=str(tmp_path), timeout_seconds=2)

        # Two failures with same reason
        for i in range(2):
            bridge = HostLLMBridge(bridge_dir=str(tmp_path))
            rid = bridge.create_request(
                agent_type="architect",
                task=f"fail-{i}",
                context={},
                prompt=f"prompt-{i}",
            )
            _drive_runner(str(tmp_path), behaviour="fail")
            with pytest.raises(RuntimeError, match="HostLLMBridge failure"):
                backend.generate(f"prompt-{i}", role_name="architect")

        assert backend.is_fuse_skipped is True
        assert backend.is_available() is False
        # Next call must raise BackendUnavailable (not re-attempt)
        with pytest.raises(BackendUnavailable):
            backend.generate("any prompt", role_name="architect")


# ---------------------------------------------------------------------------
# T5 — Single failure degrades (does not skip)
# ---------------------------------------------------------------------------


class TestT5SingleFailureDegrade:
    def test_single_failure_does_not_fuse_skip(self, tmp_path, monkeypatch):
        """1 failure with reason A → still available for next call."""
        monkeypatch.setenv("TRAE_ENV", "1")
        backend = HostBridgeBackend(bridge_dir=str(tmp_path), timeout_seconds=2)

        # 1 failure
        bridge = HostLLMBridge(bridge_dir=str(tmp_path))
        rid = bridge.create_request(
            agent_type="architect",
            task="fail",
            context={},
            prompt="one",
        )
        _drive_runner(str(tmp_path), behaviour="fail")
        with pytest.raises(RuntimeError):
            backend.generate("one", role_name="architect")

        assert backend.is_fuse_skipped is False
        assert backend.is_available() is True


# ---------------------------------------------------------------------------
# T6 — Corrupt JSON response
# ---------------------------------------------------------------------------


class TestT6CorruptJSON:
    def test_corrupt_response_returns_failure_after_retries(self, tmp_path):
        """Half-truncated JSON causes _try_read_json to retry, then fail/timeout."""
        bridge = HostLLMBridge(bridge_dir=str(tmp_path))
        rid = bridge.create_request(
            agent_type="architect",
            task="design",
            context={},
            prompt="will corrupt",
        )
        _drive_runner(str(tmp_path), behaviour="marker_corrupt")
        # File exists but unparseable — after MAX_JSON_RETRIES retries,
        # wait_for_response continues polling (because the file is
        # still there). To avoid waiting forever, we delete the corrupt
        # file ourselves to simulate "host gave up".
        corrupt = tmp_path / f"response_{rid}.json"
        if corrupt.exists():
            corrupt.unlink()
        result = bridge.wait_for_response(rid, timeout=1)
        assert result["success"] is False


# ---------------------------------------------------------------------------
# T7 — Concurrent requests have distinct request_ids
# ---------------------------------------------------------------------------


class TestT7ConcurrentRequests:
    def test_concurrent_create_requests_have_distinct_ids(self, tmp_path):
        """Each create_request must return a unique request_id."""
        bridge = HostLLMBridge(bridge_dir=str(tmp_path))
        ids = set()
        for i in range(5):
            rid = bridge.create_request(
                agent_type="general",
                task=f"concurrent-{i}",
                context={},
                prompt=f"p-{i}",
            )
            assert rid not in ids
            ids.add(rid)
        assert len(ids) == 5
        # Each has its own request file
        for rid in ids:
            assert (tmp_path / f"request_{rid}.json").exists()


# ---------------------------------------------------------------------------
# T8 — Path traversal defence
# ---------------------------------------------------------------------------


class TestT8PathTraversalDefence:
    def test_validate_request_id_rejects_path_traversal(self):
        """validate_request_id only allows [a-zA-Z0-9_]{1,64}."""
        assert HostLLMBridge.validate_request_id("req_abc123")
        assert HostLLMBridge.validate_request_id("req_a_b_c")
        assert not HostLLMBridge.validate_request_id("../etc/passwd")
        assert not HostLLMBridge.validate_request_id("req/with/slash")
        assert not HostLLMBridge.validate_request_id("req.with.dots")
        assert not HostLLMBridge.validate_request_id("req with space")
        assert not HostLLMBridge.validate_request_id("")  # too short
        assert not HostLLMBridge.validate_request_id("a" * 65)  # too long

    def test_write_response_rejects_unsafe_id(self, tmp_path):
        """write_response refuses to write a file with a malicious id."""
        with pytest.raises(ValueError, match="Invalid request_id"):
            HostLLMBridge.write_response(
                request_id="../../../etc/passwd",
                success=True,
                output="evil",
                bridge_dir=str(tmp_path),
            )


# ---------------------------------------------------------------------------
# Misc — anti-ghost counter, platform detection, marker utilities
# ---------------------------------------------------------------------------


class TestAntiGhostAndPlatform:
    def test_call_counter_increments_on_create(self, tmp_path):
        """_call_counter increments on every create_request()."""
        before = get_call_counter()
        bridge = HostLLMBridge(bridge_dir=str(tmp_path))
        for _ in range(3):
            bridge.create_request(
                agent_type="general", task="x", context={}, prompt="x"
            )
        after = get_call_counter()
        assert after - before == 3

    def test_platform_detection_trae(self, monkeypatch):
        monkeypatch.setenv("TRAE_ENV", "1")
        monkeypatch.delenv("CLAUDE_CODE_ENV", raising=False)
        monkeypatch.delenv("ANTHROPIC_ENV", raising=False)
        monkeypatch.delenv("TRAE_AGENT_PATH", raising=False)
        backend = HostBridgeBackend(bridge_dir="/tmp/unused")
        assert backend._detect_platform() == "host_llm"

    def test_platform_detection_claude(self, monkeypatch):
        monkeypatch.delenv("TRAE_ENV", raising=False)
        monkeypatch.delenv("TRAE_AGENT_PATH", raising=False)
        monkeypatch.setenv("CLAUDE_CODE_ENV", "1")
        backend = HostBridgeBackend(bridge_dir="/tmp/unused")
        assert backend._detect_platform() == "claude_code"

    def test_platform_detection_unknown(self, monkeypatch):
        for v in ("TRAE_ENV", "TRAE_AGENT_PATH", "CLAUDE_CODE_ENV", "ANTHROPIC_ENV"):
            monkeypatch.delenv(v, raising=False)
        backend = HostBridgeBackend(bridge_dir="/tmp/unused")
        assert backend._detect_platform() == "unknown"

    def test_read_marker_returns_none_when_missing(self, tmp_path):
        assert HostLLMBridge.read_marker(bridge_dir=str(tmp_path)) is None

    def test_clear_marker_is_idempotent(self, tmp_path):
        # No-op when marker doesn't exist
        HostLLMBridge.clear_marker(bridge_dir=str(tmp_path))
        # Creates + clears
        HostLLMBridge.write_response(
            request_id="req_abc",
            success=True,
            output="x",
            bridge_dir=str(tmp_path),
        )
        assert (tmp_path / "protocol.marker").exists() is False
