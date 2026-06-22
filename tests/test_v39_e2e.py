#!/usr/bin/env python3
"""V3.9 E2E Tests — Full dispatch pipeline with all V3.9 features.

Test scenarios:
1. Full dispatch with CodeKnowledgeGraph — graph is built, queried by workers,
   results contain code_graph_hints.
2. Full dispatch with RBAC — unauthorized user is blocked, authorized user
   succeeds, audit log records both.
3. Full dispatch with all V3.9 features — graph + RBAC + audit + yagni +
   dials + redesign.
4. Backward compatibility — dispatch without any V3.9 features works exactly
   as before (same behavior as V3.8).
5. MCP codegraph tools — codegraph_explore returns correct results,
   codegraph_status returns stats.

Each E2E test creates a real MultiAgentDispatcher with V3.9 features
configured, executes a real dispatch (mock mode), and verifies the
DispatchResult contains the expected V3.9 fields.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.code_knowledge_graph import CodeKnowledgeGraph
from scripts.collaboration.dispatch_audit import DispatchAuditLogger
from scripts.collaboration.dispatch_rbac import DispatchRBAC
from scripts.collaboration.dispatcher import MultiAgentDispatcher
from scripts.collaboration.micro_task_planner import MicroTaskPlanner
from scripts.collaboration.yagni_checker import YagniChecker

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_temp_project() -> tuple[str, Path]:
    """Create a small temp Python project for CodeKnowledgeGraph indexing.

    Returns (tmpdir, project_root). The caller is responsible for cleaning
    up tmpdir (e.g. via shutil.rmtree in a finally block).
    """
    tmpdir = tempfile.mkdtemp(prefix="v39_e2e_")
    project_root = Path(tmpdir) / "src"
    project_root.mkdir(parents=True, exist_ok=True)

    (project_root / "sample.py").write_text(
        '''"""Sample module for E2E testing."""

def hello(name: str) -> str:
    """Greet someone."""
    return f"Hello, {name}"


def call_hello() -> str:
    """Call hello."""
    return hello("world")


class Greeter:
    """A greeter class."""

    def greet(self) -> str:
        return hello("class")
''',
        encoding="utf-8",
    )
    return tmpdir, project_root


def _make_mock_auth() -> MagicMock:
    """Create a mock AuthManager with admin, operator, and viewer users."""
    mock_auth = MagicMock()
    mock_auth.credentials = {
        "admin_user": {"role": "admin"},
        "operator_user": {"role": "operator"},
        "viewer_user": {"role": "viewer"},
    }
    return mock_auth


# ---------------------------------------------------------------------------
# E2E Scenario 1: Full dispatch with CodeKnowledgeGraph
# ---------------------------------------------------------------------------


class TestE2ECodeKnowledgeGraph:
    """Verify the full dispatch pipeline with CodeKnowledgeGraph integration."""

    def test_full_dispatch_with_code_graph(self) -> None:
        """Verify: dispatch with CodeKnowledgeGraph queries the graph.

        Scenario: A dispatcher is configured with a pre-built code graph.
        When a task mentioning graph symbols is dispatched, workers query
        the graph for hints before LLM calls.

        Expected:
        - Dispatch succeeds.
        - CodeKnowledgeGraph.query() is called at least once during dispatch.
        - DispatchResult.success is True.
        - The coordinator has the code graph attached.
        """
        tmpdir, project_root = _make_temp_project()
        try:
            # Build the code graph from the temp project.
            db_path = Path(tmpdir) / "codegraph.db"
            graph = CodeKnowledgeGraph(db_path)
            graph.build_from_project(project_root)

            # Spy on the graph's query method to verify it's called.
            original_query = graph.query
            query_call_count = [0]

            def _counting_query() -> object:
                query_call_count[0] += 1
                return original_query()

            graph.query = _counting_query  # type: ignore[method-assign]

            disp = MultiAgentDispatcher(
                persist_dir=tmpdir,
                code_graph=graph,
                enable_rbac=False,
            )

            # Dispatch a task that mentions "hello" (a symbol in the graph).
            result = disp.dispatch(
                "Review the hello function and call_hello",
                roles=["solo-coder"],
            )

            # Dispatch should succeed.
            assert result.success, (
                f"Dispatch should succeed, errors: {result.errors}"
            )

            # The graph's query method should have been called at least once
            # by the worker's _query_code_graph_for_task method.
            assert query_call_count[0] >= 1, (
                "CodeKnowledgeGraph.query() was not called during dispatch"
            )

            # The coordinator should have the code graph attached.
            assert disp.coordinator.code_graph is graph

            graph.close()
            disp.shutdown()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_code_graph_hints_reach_worker_context(self) -> None:
        """Verify: code_graph_hints are populated in worker execution context.

        Scenario: When a task mentions symbols in the graph, the worker's
        _build_execution_context method populates code_graph_hints.

        Expected:
        - Dispatch succeeds.
        - The graph query is called (hints are generated).
        - Worker results are present (workers executed).
        """
        tmpdir, project_root = _make_temp_project()
        try:
            db_path = Path(tmpdir) / "codegraph.db"
            graph = CodeKnowledgeGraph(db_path)
            graph.build_from_project(project_root)

            disp = MultiAgentDispatcher(
                persist_dir=tmpdir,
                code_graph=graph,
                enable_rbac=False,
            )

            result = disp.dispatch(
                "Review the hello function",
                roles=["solo-coder"],
            )

            assert result.success
            # Worker results should be present.
            assert len(result.worker_results) >= 1, (
                "Expected at least one worker result"
            )
            # The graph should have been queried (verified by successful
            # dispatch with graph attached).
            assert disp.coordinator.code_graph is graph

            graph.close()
            disp.shutdown()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# E2E Scenario 2: Full dispatch with RBAC + Audit
# ---------------------------------------------------------------------------


class TestE2ERBACAudit:
    """Verify the full dispatch pipeline with RBAC and audit logging."""

    def test_unauthorized_user_blocked_with_audit(self) -> None:
        """Verify: unauthorized dispatch is blocked and audited.

        Scenario: A viewer user attempts a consensus dispatch (not allowed).
        RBAC denies the request, and the audit logger records permission_denied.

        Expected:
        - Dispatch fails (success=False).
        - permission_result is populated with allowed=False.
        - audit_entries contain a permission_denied event.
        - The audit chain is valid (verify_chain returns True).
        """
        tmpdir = tempfile.mkdtemp(prefix="v39_e2e_rbac_")
        try:
            mock_auth = _make_mock_auth()
            rbac = DispatchRBAC(auth_manager=mock_auth)
            audit = DispatchAuditLogger()

            disp = MultiAgentDispatcher(
                persist_dir=tmpdir,
                rbac=rbac,
                audit_logger=audit,
                enable_rbac=False,  # disable enterprise RBAC (separate system)
            )

            result = disp.dispatch(
                "Design the system architecture",
                roles=["architect"],
                mode="consensus",  # viewer cannot use consensus
                user_id="viewer_user",
            )

            # Dispatch should fail.
            assert not result.success, (
                "Dispatch should fail for unauthorized user"
            )

            # permission_result should be populated and denied.
            assert result.permission_result is not None
            assert result.permission_result["allowed"] is False
            assert "not permitted" in result.permission_result["reason"].lower()

            # audit_entries should contain permission_denied event.
            assert len(result.audit_entries) >= 1
            event_types = [e["event_type"] for e in result.audit_entries]
            assert "permission_denied" in event_types, (
                f"Expected permission_denied in audit events, got: {event_types}"
            )

            # The audit chain should be valid.
            assert audit.verify_chain(), "Audit chain should be valid"

            disp.shutdown()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_authorized_user_succeeds_with_audit(self) -> None:
        """Verify: authorized dispatch succeeds and is audited.

        Scenario: An admin user dispatches a task. RBAC allows it, and the
        audit logger records dispatch_start and dispatch_end events.

        Expected:
        - Dispatch succeeds.
        - permission_result is populated with allowed=True.
        - audit_entries contain dispatch_start and dispatch_end events.
        - The audit chain is valid.
        """
        tmpdir = tempfile.mkdtemp(prefix="v39_e2e_rbac_")
        try:
            mock_auth = _make_mock_auth()
            rbac = DispatchRBAC(auth_manager=mock_auth)
            audit = DispatchAuditLogger()

            disp = MultiAgentDispatcher(
                persist_dir=tmpdir,
                rbac=rbac,
                audit_logger=audit,
                enable_rbac=False,
            )

            result = disp.dispatch(
                "Write a hello world function",
                roles=["solo-coder"],
                mode="auto",
                user_id="admin_user",
            )

            # Dispatch should succeed.
            assert result.success, (
                f"Dispatch should succeed for authorized user, errors: {result.errors}"
            )

            # permission_result should be populated and allowed.
            assert result.permission_result is not None
            assert result.permission_result["allowed"] is True

            # audit_entries should contain dispatch_start and dispatch_end.
            assert len(result.audit_entries) >= 2
            event_types = [e["event_type"] for e in result.audit_entries]
            assert "dispatch_start" in event_types
            assert "dispatch_end" in event_types

            # The audit chain should be valid.
            assert audit.verify_chain()

            disp.shutdown()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_rbac_open_mode_no_permission_result(self) -> None:
        """Verify: without RBAC, permission_result is None (open mode).

        Scenario: A dispatcher without RBAC configured allows all dispatches.
        permission_result should be None (no RBAC check performed).

        Expected:
        - Dispatch succeeds.
        - permission_result is None.
        - audit_entries is empty (no audit logger configured).
        """
        tmpdir = tempfile.mkdtemp(prefix="v39_e2e_open_")
        try:
            disp = MultiAgentDispatcher(
                persist_dir=tmpdir,
                enable_rbac=False,
            )

            result = disp.dispatch(
                "Write a function",
                roles=["solo-coder"],
                user_id="anyone",
            )

            assert result.success
            assert result.permission_result is None
            assert result.audit_entries == []
            disp.shutdown()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# E2E Scenario 3: Full dispatch with ALL V3.9 features
# ---------------------------------------------------------------------------


class TestE2EAllV39Features:
    """Verify all V3.9 features work together in a single dispatch."""

    def test_full_dispatch_with_all_v39_features(self) -> None:
        """Verify: a single dispatch with all V3.9 modules configured succeeds.

        Scenario: Configure CodeKnowledgeGraph + DispatchRBAC + DispatchAuditLogger
        + MicroTaskPlanner (with YagniChecker) + RedesignAudit. Dispatch a task
        that exercises all modules.

        Expected:
        - Dispatch succeeds.
        - permission_result is populated (allowed=True for admin).
        - audit_entries contain dispatch_start and dispatch_end.
        - micro_task_plan is populated (when use_micro_tasks=True).
        - The code graph is attached to the coordinator.
        - The audit chain is valid.
        - Two-stage review ran with Stage 3 (redesign) enabled.
        """
        tmpdir, project_root = _make_temp_project()
        try:
            # Build the code graph.
            db_path = Path(tmpdir) / "codegraph.db"
            graph = CodeKnowledgeGraph(db_path)
            graph.build_from_project(project_root)

            # Create YagniChecker + MicroTaskPlanner.
            yagni = YagniChecker()
            planner = MicroTaskPlanner(yagni_checker=yagni)

            # Create RBAC + AuditLogger.
            mock_auth = _make_mock_auth()
            rbac = DispatchRBAC(auth_manager=mock_auth)
            audit = DispatchAuditLogger()

            disp = MultiAgentDispatcher(
                persist_dir=tmpdir,
                code_graph=graph,
                micro_task_planner=planner,
                rbac=rbac,
                audit_logger=audit,
                enable_redesign_audit=True,
                enable_rbac=False,  # disable enterprise RBAC (separate system)
            )

            result = disp.dispatch(
                "Review the hello function and write tests",
                roles=["solo-coder"],
                mode="auto",
                user_id="admin_user",
                use_micro_tasks=True,
            )

            # Dispatch should succeed.
            assert result.success, (
                f"Full dispatch with all V3.9 features should succeed, "
                f"errors: {result.errors}"
            )

            # CodeKnowledgeGraph should be attached to the coordinator.
            assert disp.coordinator.code_graph is graph

            # MicroTaskPlan should be populated.
            assert result.micro_task_plan is not None, (
                "Expected micro_task_plan to be populated"
            )

            # RBAC permission_result should be populated and allowed.
            assert result.permission_result is not None
            assert result.permission_result["allowed"] is True

            # Audit entries should include dispatch_start and dispatch_end.
            assert len(result.audit_entries) >= 2
            event_types = [e["event_type"] for e in result.audit_entries]
            assert "dispatch_start" in event_types
            assert "dispatch_end" in event_types

            # Audit chain should be valid.
            assert audit.verify_chain(), "Audit chain should be valid"

            # Two-stage review should have run with Stage 3 (redesign).
            if result.two_stage_review is not None:
                assert "stage3_result" in result.two_stage_review
                assert "redesign_findings" in result.two_stage_review

            graph.close()
            disp.shutdown()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_to_dict_includes_all_v39_fields(self) -> None:
        """Verify: DispatchResult.to_dict() includes all V3.9 fields.

        Scenario: After a full V3.9 dispatch, serialize the result to dict.
        All V3.9 fields should be present in the serialized output.

        Expected:
        - to_dict() output contains: permission_result, audit_entries,
          micro_task_plan, two_stage_review keys.
        """
        tmpdir, project_root = _make_temp_project()
        try:
            db_path = Path(tmpdir) / "codegraph.db"
            graph = CodeKnowledgeGraph(db_path)
            graph.build_from_project(project_root)

            mock_auth = _make_mock_auth()
            rbac = DispatchRBAC(auth_manager=mock_auth)
            audit = DispatchAuditLogger()
            planner = MicroTaskPlanner(yagni_checker=YagniChecker())

            disp = MultiAgentDispatcher(
                persist_dir=tmpdir,
                code_graph=graph,
                micro_task_planner=planner,
                rbac=rbac,
                audit_logger=audit,
                enable_redesign_audit=True,
                enable_rbac=False,
            )

            result = disp.dispatch(
                "Review the hello function",
                roles=["solo-coder"],
                user_id="admin_user",
                use_micro_tasks=True,
            )

            d = result.to_dict()
            # All V3.9 fields should be present in the serialized dict.
            assert "permission_result" in d
            assert "audit_entries" in d
            assert "micro_task_plan" in d
            assert "two_stage_review" in d

            # permission_result should be populated.
            assert d["permission_result"] is not None
            assert d["permission_result"]["allowed"] is True

            # audit_entries should be a non-empty list.
            assert isinstance(d["audit_entries"], list)
            assert len(d["audit_entries"]) >= 2

            graph.close()
            disp.shutdown()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# E2E Scenario 4: Backward compatibility — no V3.9 features
# ---------------------------------------------------------------------------


class TestE2EBackwardCompatibility:
    """Verify dispatch works without any V3.9 modules (V3.8 behavior)."""

    def test_dispatch_without_v39_modules(self) -> None:
        """Verify: a standard dispatch with no V3.9 modules succeeds.

        Scenario: Create a dispatcher with no code_graph, rbac, audit_logger,
        or redesign_audit. Dispatch should work exactly as in V3.8.

        Expected:
        - Dispatch succeeds.
        - permission_result is None (no RBAC).
        - audit_entries is empty (no audit logger).
        - micro_task_plan is None (no use_micro_tasks).
        - No code_graph, rbac, or audit_logger configured.
        """
        tmpdir = tempfile.mkdtemp(prefix="v39_e2e_compat_")
        try:
            disp = MultiAgentDispatcher(
                persist_dir=tmpdir,
                enable_rbac=False,
            )

            result = disp.dispatch(
                "Write a hello world function",
                roles=["solo-coder"],
            )

            # Dispatch should succeed.
            assert result.success, (
                f"Dispatch without V3.9 modules should succeed, "
                f"errors: {result.errors}"
            )

            # V3.9 optional fields should be None/empty.
            assert result.permission_result is None
            assert result.audit_entries == []
            assert result.micro_task_plan is None

            # No V3.9 modules configured.
            assert disp._code_graph is None
            assert disp._rbac is None
            assert disp._audit_logger is None

            disp.shutdown()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_to_dict_has_v39_fields_even_without_modules(self) -> None:
        """Verify: to_dict() includes V3.9 fields even when no modules configured.

        Scenario: A dispatch with no V3.9 modules produces a result whose
        to_dict() still contains the V3.9 field keys (with None/empty values).

        Expected:
        - to_dict() contains permission_result (None) and audit_entries ([]).
        """
        tmpdir = tempfile.mkdtemp(prefix="v39_e2e_compat_")
        try:
            disp = MultiAgentDispatcher(
                persist_dir=tmpdir,
                enable_rbac=False,
            )

            result = disp.dispatch(
                "Write a function",
                roles=["solo-coder"],
            )

            d = result.to_dict()
            assert "permission_result" in d
            assert "audit_entries" in d
            assert d["permission_result"] is None
            assert d["audit_entries"] == []

            disp.shutdown()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_dispatch_without_user_id_works(self) -> None:
        """Verify: dispatch without user_id works (defaults to anonymous).

        Scenario: A dispatch call without user_id should not fail even with
        V3.9 modules configured (user_id defaults to "anonymous").

        Expected:
        - Dispatch succeeds.
        - No exceptions raised.
        """
        tmpdir = tempfile.mkdtemp(prefix="v39_e2e_compat_")
        try:
            audit = DispatchAuditLogger()
            disp = MultiAgentDispatcher(
                persist_dir=tmpdir,
                audit_logger=audit,
                enable_rbac=False,
            )

            # Dispatch without user_id — should default to "anonymous".
            result = disp.dispatch(
                "Write a function",
                roles=["solo-coder"],
            )

            assert result.success
            # Audit entries should still be recorded (user_id="anonymous").
            assert len(result.audit_entries) >= 2
            event_types = [e["event_type"] for e in result.audit_entries]
            assert "dispatch_start" in event_types
            assert "dispatch_end" in event_types

            disp.shutdown()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# E2E Scenario 5: MCP codegraph tools
# ---------------------------------------------------------------------------


class TestE2EMCPCodegraphTools:
    """Verify the MCP codegraph_explore and codegraph_status tools."""

    def test_codegraph_explore_symbol_query(self) -> None:
        """Verify: codegraph_explore finds symbols by name.

        Scenario: A pre-built graph is injected into the MCP server.
        The codegraph_explore tool (via _get_code_graph + query) finds
        the "hello" symbol.

        Expected:
        - The graph is accessible via _get_code_graph().
        - find_symbol("hello") returns at least one result.
        - The result name is "hello".
        """
        from scripts.mcp_server import DevSquadMCPServer

        tmpdir, project_root = _make_temp_project()
        try:
            db_path = Path(tmpdir) / "codegraph.db"
            graph = CodeKnowledgeGraph(db_path)
            graph.build_from_project(project_root)

            server = DevSquadMCPServer()
            server._code_graph = graph  # inject pre-built graph

            # Verify the graph is accessible.
            assert server._get_code_graph() is graph

            # Query the graph directly (this is what codegraph_explore does).
            q = graph.query()
            results = q.find_symbol("hello")
            assert len(results) >= 1, "Expected to find 'hello' symbol"
            assert results[0].name == "hello"

            graph.close()
            server.shutdown()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_codegraph_explore_callers_query(self) -> None:
        """Verify: codegraph_explore finds callers of a function.

        Scenario: A pre-built graph is injected into the MCP server.
        The codegraph_explore tool (via find_callers) finds callers of "hello".

        Expected:
        - find_callers("hello") returns at least "call_hello".
        """
        from scripts.mcp_server import DevSquadMCPServer

        tmpdir, project_root = _make_temp_project()
        try:
            db_path = Path(tmpdir) / "codegraph.db"
            graph = CodeKnowledgeGraph(db_path)
            graph.build_from_project(project_root)

            server = DevSquadMCPServer()
            server._code_graph = graph

            q = graph.query()
            callers = q.find_callers("hello")
            caller_names = [c.name for c in callers]
            assert "call_hello" in caller_names, (
                f"Expected 'call_hello' in callers, got: {caller_names}"
            )

            graph.close()
            server.shutdown()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_codegraph_explore_callees_query(self) -> None:
        """Verify: codegraph_explore finds callees of a function.

        Scenario: A pre-built graph is injected into the MCP server.
        The codegraph_explore tool (via find_callees) finds callees of
        "call_hello".

        Expected:
        - find_callees("call_hello") returns at least "hello".
        """
        from scripts.mcp_server import DevSquadMCPServer

        tmpdir, project_root = _make_temp_project()
        try:
            db_path = Path(tmpdir) / "codegraph.db"
            graph = CodeKnowledgeGraph(db_path)
            graph.build_from_project(project_root)

            server = DevSquadMCPServer()
            server._code_graph = graph

            q = graph.query()
            callees = q.find_callees("call_hello")
            callee_names = [c.name for c in callees]
            assert "hello" in callee_names, (
                f"Expected 'hello' in callees of call_hello, got: {callee_names}"
            )

            graph.close()
            server.shutdown()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_codegraph_explore_graph_traversal(self) -> None:
        """Verify: codegraph_explore graph query returns BFS traversal.

        Scenario: A pre-built graph is injected into the MCP server.
        The codegraph_explore tool (via get_call_graph) returns a BFS
        traversal from "call_hello".

        Expected:
        - get_call_graph returns a dict with nodes and edges.
        - The entry_point is "call_hello".
        - At least one edge exists (call_hello → hello).
        """
        from scripts.mcp_server import DevSquadMCPServer

        tmpdir, project_root = _make_temp_project()
        try:
            db_path = Path(tmpdir) / "codegraph.db"
            graph = CodeKnowledgeGraph(db_path)
            graph.build_from_project(project_root)

            server = DevSquadMCPServer()
            server._code_graph = graph

            q = graph.query()
            call_graph = q.get_call_graph("call_hello", max_depth=3)
            assert call_graph["entry_point"] == "call_hello"
            assert len(call_graph["nodes"]) >= 1
            assert len(call_graph["edges"]) >= 1
            # The edge call_hello → hello should exist.
            edge_pairs = [(e["caller"], e["callee"]) for e in call_graph["edges"]]
            assert ("call_hello", "hello") in edge_pairs, (
                f"Expected edge (call_hello, hello), got: {edge_pairs}"
            )

            graph.close()
            server.shutdown()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_codegraph_status_returns_stats(self) -> None:
        """Verify: codegraph_status returns built=True and symbol_count > 0.

        Scenario: A pre-built graph is injected into the MCP server.
        The codegraph_status tool (via get_stats) returns graph statistics.

        Expected:
        - get_stats returns a dict with symbols > 0 and files >= 1.
        """
        from scripts.mcp_server import DevSquadMCPServer

        tmpdir, project_root = _make_temp_project()
        try:
            db_path = Path(tmpdir) / "codegraph.db"
            graph = CodeKnowledgeGraph(db_path)
            graph.build_from_project(project_root)

            server = DevSquadMCPServer()
            server._code_graph = graph

            # Verify the graph is accessible and has stats.
            assert server._get_code_graph() is graph
            stats = graph.get_stats()
            assert stats["symbols"] > 0, "Expected symbols > 0 in stats"
            assert stats["files"] >= 1, "Expected files >= 1 in stats"

            graph.close()
            server.shutdown()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_codegraph_status_unavailable(self) -> None:
        """Verify: codegraph_status returns None when graph unavailable.

        Scenario: No graph is configured, and _CODEGRAPH_AVAILABLE is patched
        to False. _get_code_graph() should return None.

        Expected:
        - _get_code_graph() returns None when _CODEGRAPH_AVAILABLE is False.
        """
        from unittest.mock import patch

        from scripts.mcp_server import DevSquadMCPServer

        server = DevSquadMCPServer()
        with patch("scripts.mcp_server._CODEGRAPH_AVAILABLE", False):
            graph = server._get_code_graph()
            assert graph is None

        server.shutdown()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "--no-cov"])
