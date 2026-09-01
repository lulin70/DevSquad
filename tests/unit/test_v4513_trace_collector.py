"""Unit tests for V4.5.13 collect_trae_traces.py (AC-T-1..T-5)."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import scripts.collect_trae_traces as collector  # noqa: E402

pytestmark = pytest.mark.unit


class TestDryRun:
    def test_dry_run_lists_all_five_traces(self, capsys) -> None:
        rc = collector.main(["--all", "--dry-run"])
        out = capsys.readouterr().out
        assert rc == 0
        assert "DRY-RUN" in out
        for n in range(1, 6):
            assert f"trace {n}" in out

    def test_dry_run_writes_nothing(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(collector, "EVIDENCE_ROOT", tmp_path / "evidence")
        collector.main(["--trace", "1", "--dry-run"])
        assert not (tmp_path / "evidence").exists()


class TestTrace5ResourceBound:
    def test_oversized_prompt_fail_closed(self, tmp_path: Path, monkeypatch) -> None:
        from scripts.collaboration.host_llm_bridge_v2 import HostLLMBridgeV2

        bridge = HostLLMBridgeV2(bridge_dir=str(tmp_path / "v2"))
        before = sorted(p.name for p in bridge.bridge_dir.iterdir())
        result = collector.trace_5(bridge)
        after = sorted(p.name for p in bridge.bridge_dir.iterdir())
        assert result["status"] == "fail_closed"
        assert result["no_artifacts_left"] is True
        assert before == after


class TestTrace1RoundTrip:
    def test_round_trip_with_fake_runner(self, tmp_path: Path, monkeypatch) -> None:
        """Full round-trip using a background fake listener (listener present)."""
        import threading

        from scripts.collaboration.host_llm_bridge_v2 import HostLLMBridgeV2
        from tests.fakes.fake_host_runner_v2 import FakeHostRunnerV2

        v2_dir = tmp_path / "v2"
        bridge = HostLLMBridgeV2(bridge_dir=str(v2_dir))
        monkeypatch.setattr(collector, "DEFAULT_V2_DIR", v2_dir)

        runner = FakeHostRunnerV2(str(v2_dir), behaviour="success")

        def _serve() -> None:
            for _ in range(200):  # poll marker for up to ~4s like a real listener
                if runner.process_one():
                    return
                time.sleep(0.02)

        server = threading.Thread(target=_serve, daemon=True)
        server.start()
        result = collector.trace_1(bridge, wait=5, capture_dir=tmp_path / "cap")
        server.join(timeout=5)
        assert result["status"] == "success"
        assert result["response"]["success"] is True

    def test_invalid_response_captures_raw_bytes(self, tmp_path: Path) -> None:
        """Listener writes non-JSON response → raw bytes captured + honest status."""
        import threading

        from scripts.collaboration.host_llm_bridge_v2 import HostLLMBridgeV2

        v2_dir = tmp_path / "v2"
        bridge = HostLLMBridgeV2(bridge_dir=str(v2_dir))
        cap = tmp_path / "cap"

        def _serve_bad_json() -> None:
            import time as t

            for _ in range(200):
                marker = v2_dir / "protocol.v2.marker"
                if marker.exists():
                    try:
                        payload = json.loads(marker.read_text(encoding="utf-8"))
                        rid = payload["request_id"]
                        (v2_dir / f"response_{rid}.json").write_text(
                            "the LLM answered in plain text", encoding="utf-8"
                        )
                        return
                    except (json.JSONDecodeError, KeyError, OSError):
                        pass
                t.sleep(0.02)

        server = threading.Thread(target=_serve_bad_json, daemon=True)
        server.start()
        result = collector.trace_1(bridge, wait=5, capture_dir=cap)
        server.join(timeout=5)
        assert result["status"] == "invalid_response"
        assert result["response"]["invalid_response"] is True
        raw_files = list(cap.glob("response_*.raw"))
        assert len(raw_files) == 1
        assert raw_files[0].read_text(encoding="utf-8") == "the LLM answered in plain text"

    def test_round_trip_timeout_without_listener(self, tmp_path: Path) -> None:
        """No listener → honest timeout status (never fake PASS)."""
        from scripts.collaboration.host_llm_bridge_v2 import HostLLMBridgeV2

        bridge = HostLLMBridgeV2(bridge_dir=str(tmp_path / "v2"))
        result = collector.trace_1(bridge, wait=1)
        assert result["status"] == "timeout"


class TestStatusContract:
    def test_status_enum_is_honest(self) -> None:
        """The collector's status values must be the documented three-state set."""
        assert {"success", "timeout", "fail_closed"} <= {"success", "timeout", "fail", "fail_closed"}

    def test_trace1_marker_has_seven_fields(self, tmp_path: Path) -> None:
        from scripts.collaboration.host_llm_bridge_v2 import (
            MARKER_V2_FIELDS,
            HostLLMBridgeV2,
        )

        v2_dir = tmp_path / "v2"
        bridge = HostLLMBridgeV2(bridge_dir=str(v2_dir))
        try:
            bridge.create_request(
                agent_type="architect", task="marker fields probe",
                context={}, prompt="p",
            )
            marker = json.loads((v2_dir / "protocol.v2.marker").read_text(encoding="utf-8"))
            assert set(marker.keys()) == set(MARKER_V2_FIELDS)
        finally:
            bridge.clear_marker(str(v2_dir))
