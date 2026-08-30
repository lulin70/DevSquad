#!/usr/bin/env python3
"""Unit tests for HostLLMBridgeV2 (V4.5.6 P4-P5 Wave 1; V4.5.10 hardened).

Coverage:
- 7-field marker / prompt separation / no inline prompt (G-β)
- strict marker schema (fail-closed) / resource limits
- path security (canonical, traversal, symlink, regular-file)
- v1/v2 isolation (no migration, version-scoped marker)
- request_id security / atomic write / anti-ghost counter
"""
from __future__ import annotations

import json
import os
import stat
import threading
from pathlib import Path

import pytest

from scripts.collaboration.host_llm_bridge_v2 import (
    MARKER_V2_FIELDS,
    MAX_PROMPT_BYTES,
    HostLLMBridgeV2,
    InvalidRequestIdError,
    RequestFilePathError,
    ResourceLimitError,
    _inc_call_counter_er,
    get_call_counter_er,
)


@pytest.fixture
def temp_bridge_dir(tmp_path: Path) -> Path:
    """Isolated bridge dir for each test."""
    return tmp_path / "host_llm_bridge"


@pytest.fixture
def bridge(temp_bridge_dir: Path) -> HostLLMBridgeV2:
    """Fresh bridge instance per test."""
    return HostLLMBridgeV2(bridge_dir=temp_bridge_dir)


class TestMarkerV2FullFields:
    """verify protocol.v2.marker contains exactly the 7 v2 fields."""

    def test_marker_v2_full_fields(self, bridge: HostLLMBridgeV2, temp_bridge_dir: Path) -> None:
        _inc_call_counter_er()
        request_id = bridge.create_request(
            agent_type="architect",
            task="Design system",
            context={"project_root": "/tmp/proj"},
            prompt="You are an architect...",
            timeout_seconds=300,
        )
        marker_path = temp_bridge_dir / HostLLMBridgeV2.MARKER_FILENAME
        assert marker_path.exists(), "marker file must be created"
        with open(marker_path) as f:
            marker_data = json.load(f)
        # Exactly the 7 upstream fields (no protocol_version, no extras)
        assert set(marker_data.keys()) == set(MARKER_V2_FIELDS)
        assert marker_data["request_id"] == request_id
        assert marker_data["agent_type"] == "architect"
        assert marker_data["task"] == "Design system"
        assert marker_data["timeout_seconds"] == 300
        assert marker_data["request_file"].endswith(f"request_{request_id}.json")
        assert marker_data["prompt_file"].endswith(f"request_{request_id}.prompt")
        assert marker_data["timestamp"]

    def test_marker_filename_is_versioned(self) -> None:
        """V2 marker must be protocol.v2.marker (isolation from v1)."""
        assert HostLLMBridgeV2.MARKER_FILENAME == "protocol.v2.marker"

    def test_read_marker_returns_v2_format(self, bridge: HostLLMBridgeV2) -> None:
        bridge.create_request(
            agent_type="test-expert",
            task="Test design",
            context=None,
            prompt="...",
        )
        marker = HostLLMBridgeV2.read_marker(bridge_dir=bridge.bridge_dir)
        assert marker is not None
        assert marker["_format"] == "v2"
        assert marker["agent_type"] == "test-expert"


class TestStrictMarkerSchema:
    """V4.5.10 AC-β-3: marker schema failures are fail-closed."""

    @pytest.fixture(autouse=True)
    def _make_dir(self, temp_bridge_dir: Path) -> None:
        temp_bridge_dir.mkdir(parents=True, exist_ok=True)

    def _base_marker(self, request_id: str, tmp_path: Path) -> dict:
        return {
            "request_id": request_id,
            "agent_type": "architect",
            "task": "t",
            "request_file": str(tmp_path / f"request_{request_id}.json"),
            "prompt_file": str(tmp_path / f"request_{request_id}.prompt"),
            "timeout_seconds": 600,
            "timestamp": "2026-08-30T00:00:00+00:00",
        }

    def test_missing_field_refused(self, temp_bridge_dir: Path) -> None:
        data = self._base_marker("abc_1", temp_bridge_dir)
        del data["prompt_file"]
        (temp_bridge_dir / HostLLMBridgeV2.MARKER_FILENAME).write_text(json.dumps(data))
        assert HostLLMBridgeV2.read_marker(bridge_dir=temp_bridge_dir) is None

    def test_extra_field_refused(self, temp_bridge_dir: Path) -> None:
        data = self._base_marker("abc_1", temp_bridge_dir)
        data["protocol_version"] = 2  # extra field must not be tolerated
        (temp_bridge_dir / HostLLMBridgeV2.MARKER_FILENAME).write_text(json.dumps(data))
        assert HostLLMBridgeV2.read_marker(bridge_dir=temp_bridge_dir) is None

    def test_wrong_type_refused(self, temp_bridge_dir: Path) -> None:
        data = self._base_marker("abc_1", temp_bridge_dir)
        data["timeout_seconds"] = "600"  # must be int
        (temp_bridge_dir / HostLLMBridgeV2.MARKER_FILENAME).write_text(json.dumps(data))
        assert HostLLMBridgeV2.read_marker(bridge_dir=temp_bridge_dir) is None

    def test_invalid_request_id_refused(self, temp_bridge_dir: Path) -> None:
        data = self._base_marker("../evil", temp_bridge_dir)
        (temp_bridge_dir / HostLLMBridgeV2.MARKER_FILENAME).write_text(json.dumps(data))
        assert HostLLMBridgeV2.read_marker(bridge_dir=temp_bridge_dir) is None

    def test_out_of_dir_path_refused(self, temp_bridge_dir: Path) -> None:
        data = self._base_marker("abc_1", temp_bridge_dir)
        data["request_file"] = "/etc/passwd"
        (temp_bridge_dir / HostLLMBridgeV2.MARKER_FILENAME).write_text(json.dumps(data))
        assert HostLLMBridgeV2.read_marker(bridge_dir=temp_bridge_dir) is None

    def test_v1_format_marker_refused(self, temp_bridge_dir: Path) -> None:
        """v2 reader never processes v1-format markers (fail-closed)."""
        (temp_bridge_dir / HostLLMBridgeV2.MARKER_FILENAME).write_text(
            json.dumps({"request_id": "legacy_20260601", "ts": 1787575254.6})
        )
        assert HostLLMBridgeV2.read_marker(bridge_dir=temp_bridge_dir) is None


class TestPromptFileSeparate:
    """V4.5.10 AC-β-1/2: prompt lives only in the .prompt file."""

    def test_request_json_has_no_inline_prompt(
        self, bridge: HostLLMBridgeV2, temp_bridge_dir: Path
    ) -> None:
        prompt_text = "Long prompt with\nmultiple\nlines and special chars: {}"
        request_id = bridge.create_request(
            agent_type="solo-coder",
            task="Implement feature",
            context=None,
            prompt=prompt_text,
        )
        prompt_path = temp_bridge_dir / f"request_{request_id}.prompt"
        assert prompt_path.exists()
        assert prompt_path.read_text(encoding="utf-8") == prompt_text
        request_data = json.loads(
            (temp_bridge_dir / f"request_{request_id}.json").read_text(encoding="utf-8")
        )
        assert "prompt" not in request_data, "request JSON must not embed prompt"
        assert request_data["prompt_file"].endswith(f"request_{request_id}.prompt")

    def test_prompt_file_is_canonical_source(
        self, bridge: HostLLMBridgeV2, temp_bridge_dir: Path
    ) -> None:
        prompt_text = "canonical prompt source"
        request_id = bridge.create_request(
            agent_type="architect", task="t", context=None, prompt=prompt_text
        )
        request_data = HostLLMBridgeV2.read_request(request_id, bridge_dir=temp_bridge_dir)
        assert request_data is not None
        prompt_file = request_data["prompt_file"]
        assert Path(prompt_file).read_text(encoding="utf-8") == prompt_text


class TestResourceLimits:
    """V4.5.10 AC-β-4: oversized payloads fail closed."""

    def test_oversized_prompt_rejected(self, bridge: HostLLMBridgeV2) -> None:
        with pytest.raises(ResourceLimitError):
            bridge.create_request(
                agent_type="architect",
                task="t",
                context=None,
                prompt="x" * (MAX_PROMPT_BYTES + 1),
            )

    def test_oversized_prompt_leaves_no_marker(self, bridge: HostLLMBridgeV2, temp_bridge_dir: Path) -> None:
        with pytest.raises(ResourceLimitError):
            bridge.create_request(
                agent_type="architect",
                task="t",
                context=None,
                prompt="x" * (MAX_PROMPT_BYTES + 1),
            )
        assert not (temp_bridge_dir / HostLLMBridgeV2.MARKER_FILENAME).exists()

    def test_oversized_response_rejected(self, bridge: HostLLMBridgeV2) -> None:
        with pytest.raises(ResourceLimitError):
            HostLLMBridgeV2.write_response(
                request_id="abc_1",
                success=True,
                output="x" * (5 * 1024 * 1024),
                bridge_dir=bridge.bridge_dir,
            )


class TestPathSecurity:
    """V4.5.10 R-path: canonical paths, traversal, symlink refusal."""

    def test_request_file_path_within_bridge_dir(self, bridge: HostLLMBridgeV2) -> None:
        request_id = bridge.create_request(
            agent_type="architect", task="test", context=None, prompt="x"
        )
        data = HostLLMBridgeV2.read_request(request_id, bridge_dir=bridge.bridge_dir)
        assert data is not None
        assert data["request_id"] == request_id

    def test_request_file_path_outside_bridge_dir_raises(self, bridge: HostLLMBridgeV2) -> None:
        with pytest.raises(RequestFilePathError):
            HostLLMBridgeV2._validate_path_within("/etc/passwd", bridge.bridge_dir)

    def test_request_file_path_traversal_raises(self, bridge: HostLLMBridgeV2) -> None:
        with pytest.raises(RequestFilePathError):
            HostLLMBridgeV2._validate_path_within(
                str(bridge.bridge_dir / ".." / ".." / "etc" / "passwd"),
                bridge.bridge_dir,
            )

    def test_symlink_refused_on_read(self, bridge: HostLLMBridgeV2, tmp_path: Path) -> None:
        """A symlink pointing to a real JSON must be refused (O_NOFOLLOW)."""
        request_id = bridge.create_request(
            agent_type="architect", task="t", context=None, prompt="secret"
        )
        # Symlink request file → outside secret file
        outside = tmp_path / "secret.json"
        outside.write_text(json.dumps({"prompt": "leaked"}))
        link = bridge.bridge_dir / f"request_{request_id}.json"
        link.unlink()
        link.symlink_to(outside)
        assert HostLLMBridgeV2.read_request(request_id, bridge_dir=bridge.bridge_dir) is None

    def test_symlink_marker_refused(self, bridge: HostLLMBridgeV2, tmp_path: Path) -> None:
        """A symlinked marker must be refused (fail-closed)."""
        outside = tmp_path / "marker.json"
        outside.write_text(
            json.dumps(
                {
                    "request_id": "abc_1",
                    "agent_type": "a",
                    "task": "t",
                    "request_file": str(bridge.bridge_dir / "request_abc_1.json"),
                    "prompt_file": str(bridge.bridge_dir / "request_abc_1.prompt"),
                    "timeout_seconds": 600,
                    "timestamp": "2026-08-30T00:00:00+00:00",
                }
            )
        )
        marker = bridge.bridge_dir / HostLLMBridgeV2.MARKER_FILENAME
        marker.symlink_to(outside)
        assert HostLLMBridgeV2.read_marker(bridge_dir=bridge.bridge_dir) is None


class TestPermissionsAndIsolation:
    """V4.5.10 AC-θ-1..4: dirs 0700, files 0600, v1 untouched."""

    @pytest.mark.skipif(os.name != "posix", reason="POSIX permissions")
    def test_dir_permissions_0700(self, bridge: HostLLMBridgeV2) -> None:
        mode = stat.S_IMODE(os.stat(bridge.bridge_dir).st_mode)
        assert mode == 0o700

    @pytest.mark.skipif(os.name != "posix", reason="POSIX permissions")
    def test_file_permissions_0600(self, bridge: HostLLMBridgeV2, temp_bridge_dir: Path) -> None:
        request_id = bridge.create_request(
            agent_type="architect", task="t", context=None, prompt="p"
        )
        for name in (
            f"request_{request_id}.json",
            f"request_{request_id}.prompt",
            HostLLMBridgeV2.MARKER_FILENAME,
        ):
            mode = stat.S_IMODE(os.stat(temp_bridge_dir / name).st_mode)
            assert mode == 0o600, f"{name} mode {oct(mode)} != 0o600"

    def test_v2_init_never_touches_v1_marker(self, temp_bridge_dir: Path) -> None:
        """v1 marker in the same dir must survive v2 init (no migration)."""
        v1_marker = temp_bridge_dir / "protocol.marker"
        temp_bridge_dir.mkdir(parents=True, exist_ok=True)
        v1_marker.write_text(json.dumps({"request_id": "old", "ts": 1.0}))
        HostLLMBridgeV2(bridge_dir=temp_bridge_dir)
        assert v1_marker.exists(), "v2 must not rename/delete v1 marker"
        assert not (temp_bridge_dir / "protocol.marker.v1.bak").exists()

    def test_v1_and_v2_same_root_isolated(self, tmp_path: Path) -> None:
        """v1 and v2 dirs/marker/request files must not overlap."""
        root = tmp_path / "bridge_root"
        v2_bridge = HostLLMBridgeV2(bridge_dir=root / "v2")
        v1_marker_dir = root / "v1"
        v1_marker_dir.mkdir(parents=True)
        (v1_marker_dir / "protocol.marker").write_text(
            json.dumps({"request_id": "v1req", "ts": 1.0})
        )
        request_id = v2_bridge.create_request(
            agent_type="architect", task="t", context=None, prompt="p"
        )
        # v2 files are all inside v2 dir
        assert (root / "v2" / f"request_{request_id}.json").exists()
        assert (root / "v2" / HostLLMBridgeV2.MARKER_FILENAME).exists()
        # v1 dir untouched
        assert (v1_marker_dir / "protocol.marker").exists()
        assert not list(v1_marker_dir.glob(f"request_{request_id}*"))

    def test_cleanup_is_version_scoped(self, bridge: HostLLMBridgeV2, temp_bridge_dir: Path) -> None:
        request_id = bridge.create_request(
            agent_type="architect", task="t", context=None, prompt="p"
        )
        HostLLMBridgeV2.write_response(
            request_id=request_id,
            success=True,
            output="ok",
            bridge_dir=temp_bridge_dir,
        )
        result = bridge.wait_for_response(request_id, timeout=2)
        assert result["success"] is True
        # request/prompt cleaned inside v2 dir only; marker cleared
        assert not (temp_bridge_dir / f"request_{request_id}.json").exists()
        assert not (temp_bridge_dir / f"request_{request_id}.prompt").exists()
        assert not (temp_bridge_dir / HostLLMBridgeV2.MARKER_FILENAME).exists()
        assert (temp_bridge_dir / f"response_{request_id}.json").exists()


class TestAtomicWrite:
    """verify atomic write semantics."""

    def test_atomic_write_prompt_and_marker(self, bridge: HostLLMBridgeV2, temp_bridge_dir: Path) -> None:
        _inc_call_counter_er()
        request_id = bridge.create_request(
            agent_type="ui-designer",
            task="Design UI",
            context={"theme": "dark"},
            prompt="You are a UI designer",
        )
        assert (temp_bridge_dir / f"request_{request_id}.json").exists()
        assert (temp_bridge_dir / f"request_{request_id}.prompt").exists()
        assert (temp_bridge_dir / HostLLMBridgeV2.MARKER_FILENAME).exists()
        tmp_files = list(temp_bridge_dir.glob("*.tmp"))
        assert not tmp_files, f"atomic write left temp files: {tmp_files}"

    def test_write_response_clears_marker(self, bridge: HostLLMBridgeV2, temp_bridge_dir: Path) -> None:
        _inc_call_counter_er()
        request_id = bridge.create_request(
            agent_type="solo-coder",
            task="Implement",
            context=None,
            prompt="...",
        )
        assert (temp_bridge_dir / HostLLMBridgeV2.MARKER_FILENAME).exists()
        HostLLMBridgeV2.write_response(
            request_id=request_id,
            success=True,
            output="Result",
            bridge_dir=temp_bridge_dir,
        )
        assert not (temp_bridge_dir / HostLLMBridgeV2.MARKER_FILENAME).exists()
        assert (temp_bridge_dir / f"response_{request_id}.json").exists()


class TestSubagentTypeMap:
    """verify subagent_type_map constants."""

    def test_subagent_type_map_architect_to_search(self) -> None:
        from scripts.collaboration.host_llm_bridge import HostBridgeBackend
        assert HostBridgeBackend.resolve_subagent_type("architect") == "search"

    def test_subagent_type_map_default_general_purpose_task(self) -> None:
        from scripts.collaboration.host_llm_bridge import HostBridgeBackend
        assert HostBridgeBackend.resolve_subagent_type("solo-coder") == "general_purpose_task"
        assert HostBridgeBackend.resolve_subagent_type("test-expert") == "general_purpose_task"
        assert HostBridgeBackend.resolve_subagent_type("ui-designer") == "general_purpose_task"
        assert HostBridgeBackend.resolve_subagent_type("product-manager") == "general_purpose_task"
        assert HostBridgeBackend.resolve_subagent_type("unknown-role") == "general_purpose_task"


class TestRequestIdValidation:
    """verify request_id security."""

    def test_validate_request_id_legal(self) -> None:
        for req_id in ["abc", "ABC_123", "x" * 128, "20260825_abc12345"]:
            assert HostLLMBridgeV2.validate_request_id(req_id), f"should accept: {req_id}"

    def test_validate_request_id_illegal(self) -> None:
        for req_id in ["", "../etc/passwd", "abc/def", "abc;rm", "a" * 129, None, 123]:
            assert not HostLLMBridgeV2.validate_request_id(req_id), f"should reject: {req_id!r}"

    def test_invalid_request_id_raises(self, bridge: HostLLMBridgeV2) -> None:
        with pytest.raises(InvalidRequestIdError):
            HostLLMBridgeV2.write_response(
                request_id="../etc/passwd",
                success=True,
                output="evil",
                bridge_dir=bridge.bridge_dir,
            )


class TestAntiGhostCounter:
    """verify _call_counter_er increments on representative calls."""

    def test_call_counter_er_increments(self, bridge: HostLLMBridgeV2) -> None:
        before = get_call_counter_er()
        bridge.create_request(
            agent_type="architect",
            task="x",
            context=None,
            prompt="x",
        )
        assert get_call_counter_er() > before

    def test_call_counter_er_thread_safe(self, bridge: HostLLMBridgeV2) -> None:
        before = get_call_counter_er()
        N = 50

        def worker() -> None:
            for _ in range(N):
                _inc_call_counter_er()

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert get_call_counter_er() >= before + N * 4
