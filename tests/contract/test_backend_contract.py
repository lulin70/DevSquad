#!/usr/bin/env python3
"""
Contract tests for V4.5.2 cross-module public APIs.

These tests verify the **stable contracts** between modules — fields, types,
and naming conventions that other code depends on. Breaking these contracts
is a major version bump, not a minor change.

Contracts under test (Test Plan §3.4):
  C1 LLMBackend.path ∈ {"B", "A", "C", "B+A+C", "B-passthrough"}
  C2 RoleDefinition.sequential_only: bool, default False
  C3 PerfSnapshot 字段 (path/call_count/p50/p95/p99/avg/min/max)
  C4 HostLLMBridge.validate_request_id: [a-zA-Z0-9_]{1,64}
  C5 TaskScale.orchestrator ∈ {"auto", "mini", "consensus"}
"""

from __future__ import annotations

import os
import sys
from dataclasses import fields

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

pytestmark = pytest.mark.contract


# ---------------------------------------------------------------------------
# C1: LLMBackend.path contract
# ---------------------------------------------------------------------------


class TestBackendPathContract:
    """C1: All LLMBackend subclasses expose .path ∈ allowed values."""

    def test_backend_path_in_allowed_set(self):
        from scripts.collaboration.host_llm_bridge import HostBridgeBackend
        from scripts.collaboration.llm_backend import (
            AnthropicBackend,
            FallbackBackend,
            MockBackend,
            OpenAIBackend,
            TraeBackend,
        )

        allowed = {"B", "A", "C", "A+C", "B+A+C", "B-passthrough", "fallback", "host_llm"}

        # MockBackend
        assert MockBackend().path in allowed, f"MockBackend.path={MockBackend().path}"

        # Class-level path attributes
        assert OpenAIBackend.path in allowed
        assert AnthropicBackend.path in allowed
        assert TraeBackend.path in allowed
        assert FallbackBackend.path in allowed
        assert HostBridgeBackend.path in allowed

    def test_specific_path_values(self):
        """Specific subclasses map to specific paths."""
        from scripts.collaboration.host_llm_bridge import HostBridgeBackend
        from scripts.collaboration.llm_backend import (
            AnthropicBackend,
            FallbackBackend,
            MockBackend,
            OpenAIBackend,
            TraeBackend,
        )

        assert MockBackend().path == "C"
        assert OpenAIBackend.path == "A"
        assert AnthropicBackend.path == "A"
        assert TraeBackend.path == "B-passthrough"
        assert FallbackBackend.path == "A+C"
        assert HostBridgeBackend.path == "B"

    def test_backend_path_attribute_exists_on_abc(self):
        """LLMBackend ABC declares path attribute (default 'C')."""
        from scripts.collaboration.llm_backend import LLMBackend
        assert hasattr(LLMBackend, "path")
        assert LLMBackend.path == "C"


# ---------------------------------------------------------------------------
# C2: RoleDefinition.sequential_only contract
# ---------------------------------------------------------------------------


class TestRoleSequentialOnlyContract:
    """C2: RoleDefinition.sequential_only: bool, default False."""

    def test_sequential_only_field_exists(self):
        from scripts.collaboration.models_dispatch import RoleDefinition
        field_names = {f.name for f in fields(RoleDefinition)}
        assert "sequential_only" in field_names

    def test_sequential_only_default_false(self):
        """Default sequential_only=False (regular roles run in parallel)."""
        from scripts.collaboration.models_dispatch import RoleDefinition

        role = RoleDefinition(
            role_id="test-role",
            name="Test Role",
            aliases=[],
            prompt="dummy",
            keywords=[],
            weight=1.0,
            description="For contract test",
        )
        assert role.sequential_only is False

    def test_solo_coder_is_sequential_only(self):
        """solo-coder role is the single sequential_only=True role (V4.5.2)."""
        from scripts.collaboration.models_dispatch import ROLE_REGISTRY

        assert "solo-coder" in ROLE_REGISTRY, "solo-coder not found in ROLE_REGISTRY"
        assert ROLE_REGISTRY["solo-coder"].sequential_only is True


# ---------------------------------------------------------------------------
# C3: PerfSnapshot fields contract
# ---------------------------------------------------------------------------


class TestPerfSnapshotFieldContract:
    """C3: PerfSnapshot has stable field set + types."""

    def test_required_fields_present(self):
        from scripts.collaboration.perf_baseline import PerfSnapshot

        field_names = {f.name for f in fields(PerfSnapshot)}
        required = {
            "path", "call_count", "p50_ms", "p95_ms", "p99_ms",
            "avg_ms", "min_ms", "max_ms",
        }
        missing = required - field_names
        assert not missing, f"PerfSnapshot missing required fields: {missing}"

    def test_optional_fields_present(self):
        """Optional but documented fields: excluded_count / baseline_p95_ms / delta_p95_pct / within_threshold."""
        from scripts.collaboration.perf_baseline import PerfSnapshot

        field_names = {f.name for f in fields(PerfSnapshot)}
        optional = {
            "excluded_count", "snapshot_id", "timestamp",
            "baseline_p95_ms", "delta_p95_pct", "within_threshold",
        }
        missing = optional - field_names
        assert not missing, f"PerfSnapshot missing optional fields: {missing}"

    def test_serialization_round_trip_preserves_fields(self):
        from scripts.collaboration.perf_baseline import PerfSnapshot

        snap = PerfSnapshot(
            path="mock", call_count=50,
            p50_ms=10.0, p95_ms=20.0, p99_ms=30.0,
            avg_ms=15.0, min_ms=5.0, max_ms=40.0,
            excluded_count=3,
            snapshot_id="v452",
            timestamp="2026-08-20T10:00:00",
            baseline_p95_ms=18.0,
            delta_p95_pct=11.1,
            within_threshold=False,
        )
        d = snap.to_dict()
        restored = PerfSnapshot.from_dict(d)
        assert restored.path == "mock"
        assert restored.call_count == 50
        assert restored.p95_ms == 20.0
        assert restored.within_threshold is False


# ---------------------------------------------------------------------------
# C4: HostLLMBridge.validate_request_id contract
# ---------------------------------------------------------------------------


class TestRequestIdValidationContract:
    """C4: request_id accepts only [a-zA-Z0-9_]{1,64}."""

    def test_valid_ids_accepted(self):
        from scripts.collaboration.host_llm_bridge import HostLLMBridge

        bridge = HostLLMBridge()
        for valid_id in ["abc", "req_123", "A" * 64, "0_a_z_Z_9", "x"]:
            assert bridge.validate_request_id(valid_id) is True, (
                f"valid id {valid_id!r} should be accepted"
            )

    def test_invalid_ids_rejected(self):
        from scripts.collaboration.host_llm_bridge import HostLLMBridge

        bridge = HostLLMBridge()
        for bad_id in [
            "../etc/passwd",       # path traversal
            "/etc/passwd",         # absolute path
            "id-with-dash",        # dash not allowed
            "id with space",       # space
            "id.with.dot",         # dot
            "id/with/slash",       # slash
            "id\\with\\backslash", # backslash
            "id\nwith\nnewline",   # newline
            "A" * 65,              # too long
            "",                    # empty
            "\x00null",            # null byte
        ]:
            assert bridge.validate_request_id(bad_id) is False, (
                f"invalid id {bad_id!r} should be rejected"
            )


# ---------------------------------------------------------------------------
# C5: TaskScale.orchestrator contract
# ---------------------------------------------------------------------------


class TestTaskScaleOrchestratorContract:
    """C5: TaskScale.orchestrator ∈ {"auto", "mini", "consensus"}."""

    def test_orchestrator_field_exists(self):
        from scripts.collaboration.task_scale_gate import TaskScale
        field_names = {f.name for f in fields(TaskScale)}
        assert "orchestrator" in field_names

    def test_orchestrator_values_in_allowed_set(self):
        from scripts.collaboration.task_scale_gate import TaskScaleGate

        allowed = {"auto", "mini", "consensus"}
        # Sample several tasks; orchestrator must always be in the allowed set
        for task in [
            "修复一个 bug",
            "实现 2 模块功能",
            "新建完整项目 --full",
            "什么是 dispatch?",
            "debug 并发根因",
        ]:
            scale = TaskScaleGate().decide(task)
            assert scale.orchestrator in allowed, (
                f"task={task!r} produced orchestrator={scale.orchestrator!r}"
            )

    def test_level_field_in_allowed_set(self):
        """TaskScale.level ∈ {"S", "M", "L"}."""
        from scripts.collaboration.task_scale_gate import TaskScaleGate

        allowed = {"S", "M", "L"}
        for task in [
            "fix single file bug",
            "implement 2 modules",
            "build new project",
            "answer a question",
        ]:
            scale = TaskScaleGate().decide(task)
            assert scale.level in allowed
