#!/usr/bin/env python3
# ruff: noqa: ARG002 — pytest fixtures are used for side effects (env vars, cache cleanup)
"""
V4.1.1 Security Hardening Tests

Coverage across 4 dimensions:
  Dimension 1: MCP Permission Control — tool permission levels
                (READ_ONLY/WRITE/ADMIN) with fail-closed semantics.
  Dimension 2: RBAC Global Protection — RBAC checks applied to MCP
                dispatch tool execution path.
  Dimension 3: Audit HMAC — HMAC-SHA256 chain hash replaces plain
                SHA-256, with backward compatibility for legacy entries.
  Dimension 4: PermissionGuard fail-closed — exceptions during permission
                check result in DENY (default) instead of ALLOW.

These tests do NOT require the MCP SDK to be installed. They exercise
the permission logic directly on DevSquadMCPServer's public/private
methods, which are defined regardless of MCP_AVAILABLE.

Follows AAA pattern (Arrange-Act-Assert) and the user's testing
philosophy: tests find bugs, never accommodate them.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.collaboration.dispatch_audit import (
    GENESIS_HASH,
    AuditEntry,
    DispatchAuditLogger,
)
from scripts.collaboration.dispatch_rbac import DispatchRBAC, PermissionResult
from scripts.collaboration.permission_guard import (
    ActionType,
    DecisionOutcome,
    PermissionGuard,
    PermissionLevel,
    ProposedAction,
)
from scripts.mcp_server import (
    MCP_ROLE_LEVELS,
    MCP_TOOL_PERMISSIONS,
    DevSquadMCPServer,
    MCPPermissionLevel,
    MCPPermissionResult,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass
class MockAuthManager:
    """Mock AuthManager with a credentials dict (matches AuthManager API).

    Reused from tests/test_dispatch_rbac.py for consistency.
    """

    credentials: dict = field(default_factory=dict)


@pytest.fixture
def clean_hmac_cache():
    """Save and restore the class-level HMAC key cache for test isolation.

    DispatchAuditLogger._hmac_key_cache is class-level so all instances in
    a process share the same random key (when DEV_SQUAD_AUDIT_HMAC_KEY is
    not set). This fixture ensures tests that rely on the cache state are
    not polluted by prior tests.
    """
    original = DispatchAuditLogger._hmac_key_cache
    DispatchAuditLogger._hmac_key_cache = None
    try:
        yield
    finally:
        DispatchAuditLogger._hmac_key_cache = original


@pytest.fixture
def mcp_env_admin(monkeypatch):
    """Set MCP env vars for an admin user."""
    monkeypatch.setenv("DEV_SQUAD_MCP_USER_ROLE", "admin")
    monkeypatch.setenv("DEV_SQUAD_MCP_USER_ID", "admin_user")
    yield


@pytest.fixture
def mcp_env_operator(monkeypatch):
    """Set MCP env vars for an operator user."""
    monkeypatch.setenv("DEV_SQUAD_MCP_USER_ROLE", "operator")
    monkeypatch.setenv("DEV_SQUAD_MCP_USER_ID", "op_user")
    yield


@pytest.fixture
def mcp_env_viewer(monkeypatch):
    """Set MCP env vars for a viewer user."""
    monkeypatch.setenv("DEV_SQUAD_MCP_USER_ROLE", "viewer")
    monkeypatch.setenv("DEV_SQUAD_MCP_USER_ID", "viewer_user")
    yield


# ===========================================================================
# Dimension 1: MCP Permission Control
# ===========================================================================


class TestMCPPermissionLevel:
    """Verify the MCPPermissionLevel enum and permission mappings."""

    def test_permission_levels_ordered(self):
        """READ_ONLY < WRITE < ADMIN ordering."""
        assert MCPPermissionLevel.READ_ONLY < MCPPermissionLevel.WRITE
        assert MCPPermissionLevel.WRITE < MCPPermissionLevel.ADMIN

    def test_all_tools_have_permission_level(self):
        """Every registered tool has a permission level."""
        expected_tools = {
            "multiagent_dispatch",
            "multiagent_quick",
            "multiagent_roles",
            "multiagent_status",
            "multiagent_analyze",
            "multiagent_shutdown",
            "codegraph_explore",
            "codegraph_status",
            "codegraph_refresh",
        }
        assert expected_tools.issubset(set(MCP_TOOL_PERMISSIONS.keys()))

    def test_dispatch_and_quick_require_write(self):
        """multiagent_dispatch and multiagent_quick require WRITE."""
        assert MCP_TOOL_PERMISSIONS["multiagent_dispatch"] == MCPPermissionLevel.WRITE
        assert MCP_TOOL_PERMISSIONS["multiagent_quick"] == MCPPermissionLevel.WRITE

    def test_shutdown_requires_admin(self):
        """multiagent_shutdown requires ADMIN."""
        assert MCP_TOOL_PERMISSIONS["multiagent_shutdown"] == MCPPermissionLevel.ADMIN

    def test_readonly_tools_require_readonly(self):
        """Status, roles, analyze, explore, status are READ_ONLY."""
        readonly_tools = [
            "multiagent_roles",
            "multiagent_status",
            "multiagent_analyze",
            "codegraph_explore",
            "codegraph_status",
        ]
        for tool in readonly_tools:
            assert MCP_TOOL_PERMISSIONS[tool] == MCPPermissionLevel.READ_ONLY

    def test_role_levels_mapping(self):
        """admin=ADMIN, operator=WRITE, viewer=READ_ONLY."""
        assert MCP_ROLE_LEVELS["admin"] == MCPPermissionLevel.ADMIN
        assert MCP_ROLE_LEVELS["operator"] == MCPPermissionLevel.WRITE
        assert MCP_ROLE_LEVELS["viewer"] == MCPPermissionLevel.READ_ONLY


class TestMCPResolveUserContext:
    """Test _resolve_user_context reads from env vars."""

    def test_returns_none_when_no_role_env(self, monkeypatch):
        """No DEV_SQUAD_MCP_USER_ROLE → None (fail-closed)."""
        monkeypatch.delenv("DEV_SQUAD_MCP_USER_ROLE", raising=False)
        server = DevSquadMCPServer()
        assert server._resolve_user_context() is None

    def test_returns_context_with_role(self, monkeypatch):
        """Role set in env → dict with role and default user_id."""
        monkeypatch.setenv("DEV_SQUAD_MCP_USER_ROLE", "admin")
        monkeypatch.delenv("DEV_SQUAD_MCP_USER_ID", raising=False)
        server = DevSquadMCPServer()
        ctx = server._resolve_user_context()
        assert ctx is not None
        assert ctx["role"] == "admin"
        assert ctx["user_id"] == "mcp_user"

    def test_returns_context_with_custom_user_id(self, monkeypatch):
        """Custom user_id from env."""
        monkeypatch.setenv("DEV_SQUAD_MCP_USER_ROLE", "operator")
        monkeypatch.setenv("DEV_SQUAD_MCP_USER_ID", "alice")
        server = DevSquadMCPServer()
        ctx = server._resolve_user_context()
        assert ctx is not None
        assert ctx["role"] == "operator"
        assert ctx["user_id"] == "alice"


class TestMCPCheckPermission:
    """Test _check_mcp_permission fail-closed semantics (Dimension 1)."""

    def test_no_user_context_denied(self):
        """No user context → DENY (fail-closed)."""
        server = DevSquadMCPServer()
        result = server._check_mcp_permission("multiagent_status", None)
        assert isinstance(result, MCPPermissionResult)
        assert result.allowed is False
        assert "fail-closed" in result.reason.lower()
        assert result.user_level is None

    def test_none_role_in_context_denied(self):
        """User context with no role → DENY."""
        server = DevSquadMCPServer()
        result = server._check_mcp_permission(
            "multiagent_status", {"user_id": "u1"}
        )
        assert result.allowed is False
        assert "role" in result.reason.lower()

    def test_unknown_role_denied(self):
        """Unknown role string → DENY (fail-closed)."""
        server = DevSquadMCPServer()
        result = server._check_mcp_permission(
            "multiagent_status", {"role": "superuser", "user_id": "u1"}
        )
        assert result.allowed is False
        assert "unknown role" in result.reason.lower()

    def test_viewer_denied_write_tool(self):
        """Viewer (READ_ONLY) cannot invoke WRITE-level tools."""
        server = DevSquadMCPServer()
        ctx = {"role": "viewer", "user_id": "v1"}
        result = server._check_mcp_permission("multiagent_dispatch", ctx)
        assert result.allowed is False
        assert result.user_level == MCPPermissionLevel.READ_ONLY
        assert result.required_level == MCPPermissionLevel.WRITE

    def test_viewer_allowed_readonly_tool(self):
        """Viewer can invoke READ_ONLY tools."""
        server = DevSquadMCPServer()
        ctx = {"role": "viewer", "user_id": "v1"}
        result = server._check_mcp_permission("multiagent_status", ctx)
        assert result.allowed is True

    def test_operator_denied_admin_tool(self):
        """Operator (WRITE) cannot invoke ADMIN-level tools."""
        server = DevSquadMCPServer()
        ctx = {"role": "operator", "user_id": "o1"}
        result = server._check_mcp_permission("multiagent_shutdown", ctx)
        assert result.allowed is False
        assert result.user_level == MCPPermissionLevel.WRITE
        assert result.required_level == MCPPermissionLevel.ADMIN

    def test_operator_allowed_write_tool(self):
        """Operator can invoke WRITE-level tools."""
        server = DevSquadMCPServer()
        ctx = {"role": "operator", "user_id": "o1"}
        result = server._check_mcp_permission("multiagent_dispatch", ctx)
        assert result.allowed is True

    def test_admin_allowed_all_tools(self):
        """Admin can invoke every registered tool."""
        server = DevSquadMCPServer()
        ctx = {"role": "admin", "user_id": "a1"}
        for tool_name in MCP_TOOL_PERMISSIONS:
            result = server._check_mcp_permission(tool_name, ctx)
            assert result.allowed is True, f"Admin should be allowed tool={tool_name}"

    def test_unknown_tool_denied_defaults_admin(self):
        """Unknown tool name defaults to ADMIN requirement → denied for non-admin."""
        server = DevSquadMCPServer()
        ctx = {"role": "operator", "user_id": "o1"}
        result = server._check_mcp_permission("nonexistent_tool", ctx)
        assert result.allowed is False
        assert result.required_level == MCPPermissionLevel.ADMIN

    def test_unknown_tool_allowed_for_admin(self):
        """Unknown tool defaults to ADMIN, admin is allowed."""
        server = DevSquadMCPServer()
        ctx = {"role": "admin", "user_id": "a1"}
        result = server._check_mcp_permission("nonexistent_tool", ctx)
        assert result.allowed is True


class TestMCPEnforceToolPermission:
    """Test _enforce_tool_permission integration (Dimension 1 + 2)."""

    def test_disabled_returns_none(self, monkeypatch):
        """When enable_permission_check=False, always returns None."""
        monkeypatch.delenv("DEV_SQUAD_MCP_USER_ROLE", raising=False)
        server = DevSquadMCPServer(enable_permission_check=False)
        assert server._enforce_tool_permission("multiagent_dispatch") is None

    def test_no_user_context_returns_denial_json(self, monkeypatch):
        """No user context → JSON denial string."""
        monkeypatch.delenv("DEV_SQUAD_MCP_USER_ROLE", raising=False)
        server = DevSquadMCPServer()
        result = server._enforce_tool_permission("multiagent_dispatch")
        assert result is not None
        data = json.loads(result)
        assert data["success"] is False
        assert data["denied"] is True
        assert "error" in data

    def test_admin_allowed_returns_none(self, mcp_env_admin):
        """Admin invoking a READ_ONLY tool → None (allowed)."""
        server = DevSquadMCPServer()
        result = server._enforce_tool_permission("multiagent_status")
        assert result is None

    def test_viewer_denied_returns_json(self, mcp_env_viewer):
        """Viewer invoking a WRITE tool → JSON denial."""
        server = DevSquadMCPServer()
        result = server._enforce_tool_permission("multiagent_dispatch")
        assert result is not None
        data = json.loads(result)
        assert data["denied"] is True


# ===========================================================================
# Dimension 2: RBAC Global Protection
# ===========================================================================


class TestMCPRBACIntegration:
    """Test RBAC checks are applied to dispatch tool execution (Dimension 2)."""

    def test_rbac_not_applied_to_non_dispatch_tools(self, mcp_env_admin):
        """Non-dispatch tools (e.g. multiagent_status) skip RBAC even with
        a fail-closed RBAC that would deny everything."""
        # Server with fail-closed RBAC (denies all dispatch).
        server = DevSquadMCPServer(rbac=DispatchRBAC(fail_closed=True))
        # multiagent_status is READ_ONLY and NOT in _RBAC_GUARDED_TOOLS.
        result = server._enforce_tool_permission("multiagent_status")
        # Should be allowed (None) because RBAC is not checked for this tool.
        assert result is None

    def test_rbac_fail_closed_denies_dispatch(self, mcp_env_admin):
        """Dispatch tool with fail-closed RBAC → denied by RBAC."""
        # Admin passes MCP check, but fail-closed RBAC denies all.
        server = DevSquadMCPServer(rbac=DispatchRBAC(fail_closed=True))
        result = server._enforce_tool_permission(
            "multiagent_dispatch", roles=["architect"], mode="auto"
        )
        assert result is not None
        data = json.loads(result)
        assert data["denied"] is True

    def test_rbac_open_mode_allows_dispatch(self, mcp_env_admin):
        """Dispatch tool with open-mode RBAC → allowed."""
        # Default RBAC (no auth_manager) is open mode.
        server = DevSquadMCPServer()
        result = server._enforce_tool_permission(
            "multiagent_dispatch", roles=["architect"], mode="auto"
        )
        assert result is None

    def test_rbac_denies_operator_security_role(self, mcp_env_operator):
        """Operator passes MCP check (WRITE) but RBAC denies security role."""
        # AuthManager has an operator user who cannot dispatch security.
        auth = MockAuthManager(
            credentials={"op_user": {"role": "operator", "name": "Op"}}
        )
        server = DevSquadMCPServer(auth_manager=auth)
        result = server._enforce_tool_permission(
            "multiagent_dispatch", roles=["security"], mode="auto"
        )
        assert result is not None
        data = json.loads(result)
        assert data["denied"] is True

    def test_rbac_allows_operator_coder_role(self, mcp_env_operator):
        """Operator passes MCP check and RBAC allows coder + parallel."""
        auth = MockAuthManager(
            credentials={"op_user": {"role": "operator", "name": "Op"}}
        )
        server = DevSquadMCPServer(auth_manager=auth)
        result = server._enforce_tool_permission(
            "multiagent_dispatch", roles=["coder"], mode="parallel"
        )
        assert result is None

    def test_rbac_denies_operator_consensus_mode(self, mcp_env_operator):
        """Operator passes MCP check but RBAC denies consensus mode."""
        auth = MockAuthManager(
            credentials={"op_user": {"role": "operator", "name": "Op"}}
        )
        server = DevSquadMCPServer(auth_manager=auth)
        result = server._enforce_tool_permission(
            "multiagent_dispatch", roles=["coder"], mode="consensus"
        )
        assert result is not None
        data = json.loads(result)
        assert data["denied"] is True

    def test_rbac_check_delegates_to_engine(self, mcp_env_admin):
        """_check_rbac_permission delegates to DispatchRBAC.check_dispatch_permission."""
        server = DevSquadMCPServer()
        ctx = {"role": "admin", "user_id": "admin_user"}
        result = server._check_rbac_permission(ctx, ["architect"], "auto")
        assert isinstance(result, PermissionResult)
        # Open mode (no auth_manager) → allowed.
        assert result.allowed is True

    def test_quick_dispatch_also_rbac_guarded(self, mcp_env_admin):
        """multiagent_quick is in _RBAC_GUARDED_TOOLS and triggers RBAC."""
        server = DevSquadMCPServer(rbac=DispatchRBAC(fail_closed=True))
        result = server._enforce_tool_permission(
            "multiagent_quick", roles=["architect"], mode="auto"
        )
        assert result is not None
        data = json.loads(result)
        assert data["denied"] is True


# ===========================================================================
# Dimension 3: Audit HMAC
# ===========================================================================


class TestAuditHMACChain:
    """Test HMAC-SHA256 audit chain (Dimension 3)."""

    def test_hmac_chain_verifies_true(self, monkeypatch, clean_hmac_cache):
        """A valid HMAC chain verifies successfully."""
        monkeypatch.setenv("DEV_SQUAD_AUDIT_HMAC_KEY", "test-secret-key-for-v411")
        logger = DispatchAuditLogger()
        logger.log_dispatch_start("u1", "task", ["architect"])
        logger.log_dispatch_end("u1", success=True, duration=0.5)
        assert logger.verify_chain() is True
        assert logger.verify_hmac_chain() is True

    def test_hmac_chain_empty_verifies_true(self, monkeypatch, clean_hmac_cache):
        """Empty chain verifies as True."""
        monkeypatch.setenv("DEV_SQUAD_AUDIT_HMAC_KEY", "test-secret-key-for-v411")
        logger = DispatchAuditLogger()
        assert logger.verify_chain() is True
        assert logger.verify_hmac_chain() is True

    def test_tampered_details_detected_by_hmac(self, monkeypatch, clean_hmac_cache):
        """Tampering with entry details breaks HMAC chain."""
        monkeypatch.setenv("DEV_SQUAD_AUDIT_HMAC_KEY", "test-secret-key-for-v411")
        logger = DispatchAuditLogger()
        logger.log_dispatch_start("u1", "task", ["architect"])
        logger._entries[0].details = {"tampered": True}
        assert logger.verify_hmac_chain() is False
        assert logger.verify_chain() is False

    def test_tampered_entry_hash_detected_by_hmac(self, monkeypatch, clean_hmac_cache):
        """Tampering with entry_hash breaks HMAC chain."""
        monkeypatch.setenv("DEV_SQUAD_AUDIT_HMAC_KEY", "test-secret-key-for-v411")
        logger = DispatchAuditLogger()
        logger.log_dispatch_start("u1", "task", ["architect"])
        logger._entries[0].entry_hash = "f" * 64
        assert logger.verify_hmac_chain() is False

    def test_tampered_prev_hash_detected_by_hmac(self, monkeypatch, clean_hmac_cache):
        """Tampering with prev_hash breaks HMAC chain."""
        monkeypatch.setenv("DEV_SQUAD_AUDIT_HMAC_KEY", "test-secret-key-for-v411")
        logger = DispatchAuditLogger()
        logger.log_dispatch_start("u1", "task1", ["architect"])
        logger.log_dispatch_end("u1", success=True, duration=0.5)
        logger._entries[1].prev_hash = "a" * 64
        assert logger.verify_hmac_chain() is False

    def test_hmac_key_from_env_var(self, monkeypatch, clean_hmac_cache):
        """HMAC key is loaded from DEV_SQUAD_AUDIT_HMAC_KEY env var."""
        monkeypatch.setenv("DEV_SQUAD_AUDIT_HMAC_KEY", "my-secret-key")
        logger = DispatchAuditLogger()
        assert logger._get_hmac_key() == b"my-secret-key"

    def test_hmac_key_generated_when_env_unset(self, monkeypatch, clean_hmac_cache):
        """When env var unset, a random key is generated and cached."""
        monkeypatch.delenv("DEV_SQUAD_AUDIT_HMAC_KEY", raising=False)
        logger = DispatchAuditLogger()
        key1 = logger._get_hmac_key()
        key2 = logger._get_hmac_key()
        # Same key returned (cached at class level).
        assert key1 == key2
        # Key is 32 bytes.
        assert len(key1) == 32

    def test_hmac_key_cached_across_instances(self, monkeypatch, clean_hmac_cache):
        """When env var unset, all instances share the same cached key."""
        monkeypatch.delenv("DEV_SQUAD_AUDIT_HMAC_KEY", raising=False)
        logger1 = DispatchAuditLogger()
        key1 = logger1._get_hmac_key()
        logger2 = DispatchAuditLogger()
        key2 = logger2._get_hmac_key()
        assert key1 == key2

    def test_different_keys_produce_different_hashes(self, monkeypatch, clean_hmac_cache):
        """Different HMAC keys produce different hashes for same payload."""
        monkeypatch.setenv("DEV_SQUAD_AUDIT_HMAC_KEY", "key-a")
        logger_a = DispatchAuditLogger()
        hash_a = logger_a._compute_hash(
            "dispatch_start", "u1", 1000.0, {"task": "x"}, GENESIS_HASH
        )

        monkeypatch.setenv("DEV_SQUAD_AUDIT_HMAC_KEY", "key-b")
        logger_b = DispatchAuditLogger()
        hash_b = logger_b._compute_hash(
            "dispatch_start", "u1", 1000.0, {"task": "x"}, GENESIS_HASH
        )
        assert hash_a != hash_b

    def test_verify_hmac_chain_with_explicit_entries(self, monkeypatch, clean_hmac_cache):
        """verify_hmac_chain accepts an explicit entries list."""
        monkeypatch.setenv("DEV_SQUAD_AUDIT_HMAC_KEY", "test-key")
        logger = DispatchAuditLogger()
        logger.log_dispatch_start("u1", "task", ["architect"])
        entries = logger.get_entries(limit=10)
        # Pass reversed list (most-recent-first from get_entries).
        entries_reversed = list(reversed(entries))
        assert logger.verify_hmac_chain(entries_reversed) is True
        # Tampered explicit list.
        entries_reversed[0].details = {"hacked": True}
        assert logger.verify_hmac_chain(entries_reversed) is False


class TestAuditLegacyBackwardCompat:
    """Test backward compatibility with legacy SHA-256 entries (Dimension 3)."""

    def test_legacy_sha256_entry_passes_verify_chain(self, monkeypatch, clean_hmac_cache):
        """Legacy SHA-256 entry passes verify_chain (with warning)."""
        monkeypatch.setenv("DEV_SQUAD_AUDIT_HMAC_KEY", "hmac-key")
        logger = DispatchAuditLogger()
        # Manually create a legacy entry using plain SHA-256.
        legacy_hash = logger._compute_legacy_hash(
            "dispatch_start", "u1", 1000.0, {"task": "legacy"}, GENESIS_HASH
        )
        entry = AuditEntry(
            event_type="dispatch_start",
            user_id="u1",
            timestamp=1000.0,
            details={"task": "legacy"},
            prev_hash=GENESIS_HASH,
            entry_hash=legacy_hash,
        )
        logger._entries.append(entry)
        logger._prev_hash = legacy_hash
        # verify_chain should pass (HMAC fails, legacy matches, warning logged).
        assert logger.verify_chain() is True

    def test_legacy_sha256_entry_fails_strict_hmac(self, monkeypatch, clean_hmac_cache):
        """Legacy SHA-256 entry fails verify_hmac_chain (strict, no fallback)."""
        monkeypatch.setenv("DEV_SQUAD_AUDIT_HMAC_KEY", "hmac-key")
        logger = DispatchAuditLogger()
        legacy_hash = logger._compute_legacy_hash(
            "dispatch_start", "u1", 1000.0, {"task": "legacy"}, GENESIS_HASH
        )
        entry = AuditEntry(
            event_type="dispatch_start",
            user_id="u1",
            timestamp=1000.0,
            details={"task": "legacy"},
            prev_hash=GENESIS_HASH,
            entry_hash=legacy_hash,
        )
        logger._entries.append(entry)
        # verify_hmac_chain should fail (HMAC doesn't match, no legacy fallback).
        assert logger.verify_hmac_chain() is False

    def test_mixed_chain_legacy_then_hmac_fails_strict(self, monkeypatch, clean_hmac_cache):
        """A chain with both legacy and HMAC entries fails strict verification."""
        monkeypatch.setenv("DEV_SQUAD_AUDIT_HMAC_KEY", "hmac-key")
        logger = DispatchAuditLogger()
        # Legacy first entry.
        legacy_hash = logger._compute_legacy_hash(
            "dispatch_start", "u1", 1000.0, {"task": "legacy"}, GENESIS_HASH
        )
        legacy_entry = AuditEntry(
            event_type="dispatch_start",
            user_id="u1",
            timestamp=1000.0,
            details={"task": "legacy"},
            prev_hash=GENESIS_HASH,
            entry_hash=legacy_hash,
        )
        logger._entries.append(legacy_entry)
        logger._prev_hash = legacy_hash
        # HMAC second entry.
        logger.log_dispatch_end("u1", success=True, duration=0.5)
        # verify_chain passes (backward compat), verify_hmac_chain fails.
        assert logger.verify_chain() is True
        assert logger.verify_hmac_chain() is False

    def test_new_entries_use_hmac_not_legacy(self, monkeypatch, clean_hmac_cache):
        """New entries written by log_* methods use HMAC, not legacy SHA-256."""
        monkeypatch.setenv("DEV_SQUAD_AUDIT_HMAC_KEY", "hmac-key")
        logger = DispatchAuditLogger()
        logger.log_dispatch_start("u1", "task", ["architect"])
        entry = logger._entries[0]
        # Compute what the legacy hash would be.
        legacy = logger._compute_legacy_hash(
            entry.event_type, entry.user_id, entry.timestamp,
            entry.details, entry.prev_hash,
        )
        # The stored hash should NOT match legacy (it should be HMAC).
        assert entry.entry_hash != legacy
        # Strict HMAC verification passes.
        assert logger.verify_hmac_chain() is True


# ===========================================================================
# Dimension 4: PermissionGuard fail-closed
# ===========================================================================


class TestPermissionGuardFailClosed:
    """Test PermissionGuard fail-closed mode (Dimension 4)."""

    def test_fail_closed_default_is_true(self):
        """PermissionGuard defaults to fail_closed=True."""
        guard = PermissionGuard()
        assert guard._fail_closed is True

    def test_fail_closed_explicit_true(self):
        """fail_closed=True can be set explicitly."""
        guard = PermissionGuard(fail_closed=True)
        assert guard._fail_closed is True

    def test_fail_open_explicit_false(self):
        """fail_closed=False enables fail-open mode."""
        guard = PermissionGuard(fail_closed=False)
        assert guard._fail_closed is False

    def test_fail_closed_denies_on_exception(self):
        """When _check_impl raises and fail_closed=True → DENY."""
        guard = PermissionGuard(fail_closed=True)
        action = ProposedAction(
            action_type=ActionType.FILE_READ,
            target="test.txt",
            description="test action",
        )
        with patch.object(
            PermissionGuard,
            "_check_impl",
            side_effect=RuntimeError("simulated internal error"),
        ):
            decision = guard.check(action)
        assert decision.outcome == DecisionOutcome.DENIED
        assert "fail-closed" in decision.reason.lower()
        assert "RuntimeError" in decision.reason

    def test_fail_open_allows_on_exception(self):
        """When _check_impl raises and fail_closed=False → ALLOW."""
        guard = PermissionGuard(fail_closed=False)
        action = ProposedAction(
            action_type=ActionType.FILE_READ,
            target="test.txt",
            description="test action",
        )
        with patch.object(
            PermissionGuard,
            "_check_impl",
            side_effect=RuntimeError("simulated internal error"),
        ):
            decision = guard.check(action)
        assert decision.outcome == DecisionOutcome.ALLOWED
        assert "fail-open" in decision.reason.lower()

    def test_normal_check_unaffected_when_no_exception(self):
        """Normal check (no exception) works regardless of fail_closed."""
        guard_closed = PermissionGuard(
            current_level=PermissionLevel.BYPASS, fail_closed=True
        )
        guard_open = PermissionGuard(
            current_level=PermissionLevel.BYPASS, fail_closed=False
        )
        action = ProposedAction(
            action_type=ActionType.FILE_READ,
            target="test.txt",
        )
        # BYPASS mode → ALLOWED regardless of fail_closed.
        decision_closed = guard_closed.check(action)
        decision_open = guard_open.check(action)
        assert decision_closed.outcome == DecisionOutcome.ALLOWED
        assert decision_open.outcome == DecisionOutcome.ALLOWED

    def test_exception_audit_recorded(self):
        """When an exception occurs, the fail-closed decision is audited."""
        guard = PermissionGuard(fail_closed=True, audit_log=True)
        action = ProposedAction(
            action_type=ActionType.FILE_DELETE,
            target="/important/file",
            description="dangerous op",
        )
        with patch.object(
            PermissionGuard,
            "_check_impl",
            side_effect=ValueError("bug in rule engine"),
        ):
            decision = guard.check(action)
        # The decision should be DENIED.
        assert decision.outcome == DecisionOutcome.DENIED
        # An audit entry should have been recorded.
        assert len(guard._audit_log) >= 1
        audit_entry = guard._audit_log[-1]
        assert audit_entry.decision is not None
        assert audit_entry.decision.outcome == DecisionOutcome.DENIED

    def test_fail_closed_handles_various_exception_types(self):
        """fail-closed handles different exception types gracefully."""
        guard = PermissionGuard(fail_closed=True)
        action = ProposedAction(target="test.txt")
        for exc in [
            ValueError("bad value"),
            TypeError("bad type"),
            KeyError("missing key"),
            RuntimeError("runtime error"),
            OSError("os error"),
        ]:
            with patch.object(
                PermissionGuard, "_check_impl", side_effect=exc
            ):
                decision = guard.check(action)
            assert decision.outcome == DecisionOutcome.DENIED, (
                f"Should DENY for {type(exc).__name__}"
            )

    def test_fail_open_handles_various_exception_types(self):
        """fail-open allows on any exception type (insecure, debug only)."""
        guard = PermissionGuard(fail_closed=False)
        action = ProposedAction(target="test.txt")
        for exc in [ValueError("bad"), TypeError("bad"), KeyError("bad")]:
            with patch.object(
                PermissionGuard, "_check_impl", side_effect=exc
            ):
                decision = guard.check(action)
            assert decision.outcome == DecisionOutcome.ALLOWED


class TestPermissionGuardFailClosedIntegration:
    """Integration: fail-closed works with real check flow (no mocking)."""

    def test_bypass_mode_does_not_trigger_fail_closed(self):
        """BYPASS mode short-circuits before any exception-prone logic."""
        guard = PermissionGuard(
            current_level=PermissionLevel.BYPASS, fail_closed=True
        )
        action = ProposedAction(
            action_type=ActionType.SHELL_EXECUTE,
            target="rm -rf /",
            description="dangerous",
        )
        decision = guard.check(action)
        # BYPASS → ALLOWED (no exception, fail_closed irrelevant).
        assert decision.outcome == DecisionOutcome.ALLOWED

    def test_plan_mode_denies_writes_without_exception(self):
        """PLAN mode denies writes through normal logic, not fail-closed."""
        guard = PermissionGuard(
            current_level=PermissionLevel.PLAN, fail_closed=True
        )
        action = ProposedAction(
            action_type=ActionType.FILE_DELETE,
            target="file.txt",
        )
        decision = guard.check(action)
        assert decision.outcome == DecisionOutcome.DENIED
        # Reason should mention PLAN, not fail-closed.
        assert "plan" in decision.reason.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
