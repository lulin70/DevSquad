#!/usr/bin/env python3
"""Unit tests for HostLLMBridgeV2 (V4.5.6 P4-P5 Wave 1).

Coverage:
- test_marker_v2_full_fields
- test_prompt_file_separate
- test_request_file_path_within_bridge_dir
- test_request_file_path_outside_bridge_dir_raises
- test_marker_v1_backward_compatible
- test_atomic_write_prompt_and_marker
- test_subagent_type_map_architect_to_search
- test_subagent_type_map_default_general_purpose_task
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from scripts.collaboration.host_llm_bridge_v2 import (
    MARKER_V2_FIELDS,
    HostLLMBridgeV2,
    InvalidRequestIdError,
    RequestFilePathError,
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
    """verify protocol.marker contains all 7 v2 fields."""

    def test_marker_v2_full_fields(self, bridge: HostLLMBridgeV2, temp_bridge_dir: Path) -> None:
        """Marker must contain all 7 fields (G1 fix)."""
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
        # All 7 fields present
        for field in MARKER_V2_FIELDS:
            assert field in marker_data, f"missing field: {field}"
        # Verify field values
        assert marker_data["request_id"] == request_id
        assert marker_data["agent_type"] == "architect"
        assert marker_data["task"] == "Design system"
        assert marker_data["timeout_seconds"] == 300
        assert marker_data["request_file"].endswith(f"request_{request_id}.json")
        assert marker_data["prompt_file"].endswith(f"request_{request_id}.prompt")
        assert marker_data["timestamp"]


class TestPromptFileSeparate:
    """verify request_{id}.prompt exists independently."""

    def test_prompt_file_separate(self, bridge: HostLLMBridgeV2, temp_bridge_dir: Path) -> None:
        """prompt file must exist separately from request.json (G2 fix)."""
        _inc_call_counter_er()
        prompt_text = "Long prompt with\nmultiple\nlines and special chars: {}"
        request_id = bridge.create_request(
            agent_type="solo-coder",
            task="Implement feature",
            context=None,
            prompt=prompt_text,
        )
        prompt_path = temp_bridge_dir / f"request_{request_id}.prompt"
        assert prompt_path.exists(), "prompt file must exist"
        with open(prompt_path) as f:
            content = f.read()
        assert content == prompt_text
        # Verify request.json does NOT have large prompt inline (or has smaller)
        request_path = temp_bridge_dir / f"request_{request_id}.json"
        with open(request_path) as f:
            request_data = json.load(f)
        # Request json contains prompt but the standalone file is the canonical source
        assert request_data["prompt"] == prompt_text


class TestRequestFilePathSecurity:
    """verify commonpath validation rejects out-of-bridge paths."""

    def test_request_file_path_within_bridge_dir(self, bridge: HostLLMBridgeV2) -> None:
        """Valid path inside bridge_dir is accepted."""
        _inc_call_counter_er()
        # Write a request directly via read_request to trigger validation
        request_id = bridge.create_request(
            agent_type="architect",
            task="test",
            context=None,
            prompt="x",
        )
        # Reading the request should succeed (file is inside bridge_dir)
        data = HostLLMBridgeV2.read_request(request_id, bridge_dir=bridge.bridge_dir)
        assert data is not None
        assert data["request_id"] == request_id

    def test_request_file_path_outside_bridge_dir_raises(self, bridge: HostLLMBridgeV2, tmp_path: Path) -> None:
        """Request with request_file outside bridge_dir raises RequestFilePathError."""
        _inc_call_counter_er()
        # Create a fake request json OUTSIDE bridge_dir with malicious request_file
        outside_dir = tmp_path / "outside"
        outside_dir.mkdir()
        outside_request = outside_dir / "request_evil.json"
        outside_request.write_text(json.dumps({
            "request_id": "evil_123",
            "request_file": "/etc/passwd",  # malicious: outside bridge_dir
            "prompt": "leak secrets",
        }))
        # Monkey-patch to make read_request read our outside file
        # Instead: validate via the static helper directly
        with pytest.raises(RequestFilePathError):
            HostLLMBridgeV2._validate_request_file_path(
                "/etc/passwd", bridge.bridge_dir
            )

    def test_request_file_path_traversal_raises(self, bridge: HostLLMBridgeV2) -> None:
        """Path traversal via '..' must be rejected."""
        with pytest.raises(RequestFilePathError):
            HostLLMBridgeV2._validate_request_file_path(
                str(bridge.bridge_dir / ".." / ".." / "etc" / "passwd"),
                bridge.bridge_dir,
            )


class TestMarkerV1BackwardCompatible:
    """verify v1 2-field marker can still be read."""

    def test_marker_v1_backward_compatible(self, bridge: HostLLMBridgeV2, temp_bridge_dir: Path) -> None:
        """A v1-format marker file should still be readable (returns _format='v1')."""
        marker_path = temp_bridge_dir / HostLLMBridgeV2.MARKER_FILENAME
        marker_path.write_text(json.dumps({
            "request_id": "legacy_20260601",
            "ts": 1787575254.6,
        }))
        marker = HostLLMBridgeV2.read_marker(bridge_dir=temp_bridge_dir)
        assert marker is not None
        assert marker["_format"] == "v1"
        assert marker["request_id"] == "legacy_20260601"

    def test_marker_v2_has_v2_format(self, bridge: HostLLMBridgeV2) -> None:
        """A v2 marker (with agent_type) returns _format='v2'."""
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

    def test_v1_marker_migrated_on_init(self, temp_bridge_dir: Path) -> None:
        """On bridge init, legacy v1 marker is renamed to .v1.bak."""
        marker_path = temp_bridge_dir / HostLLMBridgeV2.MARKER_FILENAME
        marker_path.parent.mkdir(parents=True, exist_ok=True)
        marker_path.write_text(json.dumps({"request_id": "old", "ts": 1.0}))
        # Init new bridge — should migrate
        HostLLMBridgeV2(bridge_dir=temp_bridge_dir)
        # Marker should be backed up, original gone
        assert not marker_path.exists()
        assert (marker_path.with_name(marker_path.name + ".v1.bak")).exists()


class TestAtomicWrite:
    """verify atomic write semantics."""

    def test_atomic_write_prompt_and_marker(self, bridge: HostLLMBridgeV2, temp_bridge_dir: Path) -> None:
        """create_request should atomically write all 3 files."""
        _inc_call_counter_er()
        request_id = bridge.create_request(
            agent_type="ui-designer",
            task="Design UI",
            context={"theme": "dark"},
            prompt="You are a UI designer",
        )
        # All 3 files exist
        assert (temp_bridge_dir / f"request_{request_id}.json").exists()
        assert (temp_bridge_dir / f"request_{request_id}.prompt").exists()
        assert (temp_bridge_dir / HostLLMBridgeV2.MARKER_FILENAME).exists()
        # No leftover .tmp files
        tmp_files = list(temp_bridge_dir.glob("*.tmp"))
        assert not tmp_files, f"atomic write left temp files: {tmp_files}"

    def test_write_response_clears_marker(self, bridge: HostLLMBridgeV2, temp_bridge_dir: Path) -> None:
        """write_response should clear the marker file."""
        _inc_call_counter_er()
        request_id = bridge.create_request(
            agent_type="solo-coder",
            task="Implement",
            context=None,
            prompt="...",
        )
        # Marker exists
        assert (temp_bridge_dir / HostLLMBridgeV2.MARKER_FILENAME).exists()
        # Write response
        HostLLMBridgeV2.write_response(
            request_id=request_id,
            success=True,
            output="Result",
            bridge_dir=temp_bridge_dir,
        )
        # Marker should be gone
        assert not (temp_bridge_dir / HostLLMBridgeV2.MARKER_FILENAME).exists()
        # Response exists
        assert (temp_bridge_dir / f"response_{request_id}.json").exists()


class TestSubagentTypeMap:
    """verify subagent_type_map constants."""

    def test_subagent_type_map_architect_to_search(self) -> None:
        """Architect role should map to 'search' (code-search heavy)."""
        from scripts.collaboration.host_llm_bridge import HostBridgeBackend
        assert HostBridgeBackend.resolve_subagent_type("architect") == "search"

    def test_subagent_type_map_default_general_purpose_task(self) -> None:
        """Unknown role falls back to 'general_purpose_task'."""
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
        """Concurrent increments must not lose updates."""
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
        # All increments must be visible
        assert get_call_counter_er() >= before + N * 4
