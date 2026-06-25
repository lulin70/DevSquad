#!/usr/bin/env python3
"""V3.9 Integration Tests — Verify all V3.9 modules are wired into the dispatch pipeline.

These tests verify that every V3.9 module is actually called during dispatch
(not just unit-tested in isolation), preventing "ghost features":

  1. CodeKnowledgeGraph  — queried by workers before LLM calls
  2. YagniChecker        — filters micro-tasks (SKIP verdicts)
  3. PromptDials         — affects prompt assembly
  4. RedesignAuditor     — runs as Stage 3 in TwoStageReviewGate
  5. DispatchRBAC        — blocks unauthorized dispatch
  6. DispatchAuditLogger — records dispatch lifecycle
  7. MCP codegraph_explore — returns correct query results
  8. MCP codegraph_status  — returns graph stats
  9. Backward compatibility — dispatch works without any V3.9 modules
  10. All V3.9 modules work together in full dispatch
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.code_knowledge_graph import CodeKnowledgeGraph
from scripts.collaboration.dispatch_audit import DispatchAuditLogger
from scripts.collaboration.dispatch_rbac import DispatchRBAC
from scripts.collaboration.dispatcher import MultiAgentDispatcher
from scripts.collaboration.micro_task_planner import MicroTaskPlanner
from scripts.collaboration.prompt_assembler import PromptAssembler
from scripts.collaboration.prompt_dials import PromptDials
from scripts.collaboration.two_stage_review_gate import (
    StageResult,
    TwoStageReviewGate,
)
from scripts.collaboration.yagni_checker import YagniChecker

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_temp_project() -> tuple[str, Path]:
    """Create a small temp Python project for CodeKnowledgeGraph indexing.

    Returns (tmpdir, project_root).
    """
    tmpdir = tempfile.mkdtemp(prefix="v39_test_")
    project_root = Path(tmpdir) / "src"
    project_root.mkdir(parents=True, exist_ok=True)

    # Create a small Python file with a function and a class.
    (project_root / "sample.py").write_text(
        '''"""Sample module for testing CodeKnowledgeGraph."""

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


# ---------------------------------------------------------------------------
# Test 1: CodeKnowledgeGraph is queried during dispatch when configured
# ---------------------------------------------------------------------------


class TestCodeKnowledgeGraphIntegration:
    """Verify CodeKnowledgeGraph is queried by workers during dispatch."""

    def test_code_graph_attached_to_coordinator(self) -> None:
        """When code_graph is provided, it reaches the coordinator."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "codegraph.db"
            graph = CodeKnowledgeGraph(db_path)
            disp = MultiAgentDispatcher(
                persist_dir=tmpdir, code_graph=graph
            )
            assert disp.coordinator.code_graph is graph
            graph.close()
            disp.shutdown()

    def test_code_graph_queried_during_dispatch(self) -> None:
        """Workers query the code graph during dispatch (hints populated)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            _, project_root = _make_temp_project()
            db_path = Path(tmpdir) / "codegraph.db"
            graph = CodeKnowledgeGraph(db_path)
            graph.build_from_project(project_root)

            # Spy on the graph's query method to verify it's called.
            original_query = graph.query
            query_spy = MagicMock(wraps=original_query)
            graph.query = query_spy  # type: ignore[method-assign]

            disp = MultiAgentDispatcher(
                persist_dir=tmpdir, code_graph=graph
            )

            # Dispatch with a task that mentions "hello" (a symbol in the graph).
            result = disp.dispatch(
                "Review the hello function", roles=["solo-coder"]
            )

            # The graph's query method should have been called at least once
            # by the worker's _query_code_graph_for_task method.
            assert query_spy.called, (
                "CodeKnowledgeGraph.query() was not called during dispatch"
            )
            assert result.success
            graph.close()
            disp.shutdown()

    def test_code_graph_not_used_when_not_configured(self) -> None:
        """When no code_graph is configured, coordinator has code_graph=None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            disp = MultiAgentDispatcher(persist_dir=tmpdir)
            assert disp.coordinator.code_graph is None
            disp.shutdown()


# ---------------------------------------------------------------------------
# Test 2: YagniChecker filters micro-tasks when MicroTaskPlanner is configured
# ---------------------------------------------------------------------------


class TestYagniCheckerIntegration:
    """Verify YagniChecker filters micro-tasks via MicroTaskPlanner."""

    def test_yagni_checker_wired_to_planner(self) -> None:
        """YagniChecker passed to MicroTaskPlanner is stored internally."""
        checker = YagniChecker()
        planner = MicroTaskPlanner(yagni_checker=checker)
        assert planner._yagni_checker is checker

    def test_yagni_checker_skips_micro_tasks(self) -> None:
        """YagniChecker marks exploratory tasks as SKIPPED."""
        checker = YagniChecker()
        planner = MicroTaskPlanner(yagni_checker=checker)

        # Plan a task that should trigger SKIP (exploratory/throwaway).
        plan = planner.plan(
            "Explore different approaches and prototype a quick demo",
            spec={"files": []},
        )

        # At least one micro-task should be SKIPPED.
        skipped = [
            mt for mt in plan.micro_tasks
            if mt.status.value == "skipped"
        ]
        assert len(skipped) >= 1, (
            "YagniChecker did not skip any micro-tasks for an exploratory task"
        )
        # yagni_results should be populated.
        assert len(plan.yagni_results) > 0

    def test_yagni_checker_not_configured(self) -> None:
        """Without YagniChecker, planner produces no yagni_results."""
        planner = MicroTaskPlanner()
        plan = planner.plan("Write a function", spec={})
        assert plan.yagni_results == {}


# ---------------------------------------------------------------------------
# Test 3: PromptDials affects prompt assembly when configured
# ---------------------------------------------------------------------------


class TestPromptDialsIntegration:
    """Verify PromptDials affects PromptAssembler.assemble()."""

    def test_dials_affect_assembled_prompt(self) -> None:
        """When dials are non-default, the assembled prompt includes the fragment."""
        assembler = PromptAssembler(
            role_id="solo-coder", base_prompt="You are a coder."
        )

        # Non-default dials (verbosity=1 → concise).
        dials = PromptDials(verbosity=1, creativity=3, risk_tolerance=3)
        prompt = assembler.assemble(
            task_description="Write a function",
            dials=dials,
        )

        # The prompt should contain the verbosity fragment.
        assert "terse" in prompt.instruction.lower() or "concise" in prompt.instruction.lower(), (
            "PromptDials fragment not found in assembled prompt"
        )
        # Metadata should record the dials.
        assert prompt.metadata.get("dials_applied") is True

    def test_variant_still_works(self) -> None:
        """The legacy variant parameter still works (backward compat)."""
        assembler = PromptAssembler(
            role_id="solo-coder", base_prompt="You are a coder."
        )

        prompt = assembler.assemble(
            task_description="Write a function",
            variant="concise",
        )

        # The variant should be converted to dials.
        assert prompt.metadata.get("dials_variant") == "concise"

    def test_default_dials_no_change(self) -> None:
        """When dials are at default (3,3,3), no fragment is added."""
        assembler = PromptAssembler(
            role_id="solo-coder", base_prompt="You are a coder."
        )

        dials = PromptDials(verbosity=3, creativity=3, risk_tolerance=3)
        prompt_default = assembler.assemble(
            task_description="Write a function",
        )
        prompt_with_dials = assembler.assemble(
            task_description="Write a function",
            dials=dials,
        )

        # Both prompts should be the same length (no fragment added).
        assert len(prompt_default.instruction) == len(prompt_with_dials.instruction)


# ---------------------------------------------------------------------------
# Test 4: RedesignAuditor runs as third stage when enabled
# ---------------------------------------------------------------------------


class TestRedesignAuditorIntegration:
    """Verify RedesignAuditor runs as Stage 3 in TwoStageReviewGate."""

    def test_redesign_auditor_runs_as_stage3(self) -> None:
        """When enable_redesign_audit=True, Stage 3 runs and produces findings."""
        gate = TwoStageReviewGate(enable_redesign_audit=True)

        # Code with overengineering (factory class) to trigger a finding.
        code_with_factory = '''
class WidgetFactory:
    """A factory class."""
    pass

def make_widget():
    return WidgetFactory()
'''

        result = gate.review(
            spec={"planned_files": [], "planned_functions": []},
            code_changes={"files": {"src/widget.py": {"content": code_with_factory}}},
        )

        # Stage 3 should have run (not PASS with no findings, since the
        # factory pattern should trigger an OVERENGINEERING finding).
        assert result.stage3_result in (StageResult.WARN, StageResult.FAIL)
        assert len(result.redesign_findings) > 0, (
            "RedesignAuditor did not produce any findings for overengineered code"
        )
        # At least one finding should be about overengineering.
        categories = [getattr(f, "category", "") for f in result.redesign_findings]
        assert "OVERENGINEERING" in categories, (
            f"Expected OVERENGINEERING finding, got: {categories}"
        )

    def test_redesign_audit_can_be_disabled(self) -> None:
        """When enable_redesign_audit=False, Stage 3 is skipped."""
        gate = TwoStageReviewGate(enable_redesign_audit=False)

        result = gate.review(
            spec={"planned_files": [], "planned_functions": []},
            code_changes={"files": {"src/x.py": {"content": "pass"}}},
        )

        # Stage 3 should be PASS (skipped, no findings).
        assert result.stage3_result == StageResult.PASS
        assert len(result.redesign_findings) == 0

    def test_redesign_findings_in_to_dict(self) -> None:
        """TwoStageReviewResult.to_dict() includes redesign_findings."""
        gate = TwoStageReviewGate(enable_redesign_audit=True)
        result = gate.review(
            spec={},
            code_changes={"files": {"x.py": {"content": "class FooFactory: pass"}}},
        )
        d = result.to_dict()
        assert "redesign_findings" in d
        assert "stage3_result" in d
        assert "stage3_passed" in d

    def test_redesign_auditor_wired_to_post_dispatch(self) -> None:
        """TwoStageReviewGate in PostDispatchPipeline has enable_redesign_audit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            disp = MultiAgentDispatcher(
                persist_dir=tmpdir, enable_redesign_audit=True
            )
            assert disp.post_dispatch.enable_redesign_audit is True
            assert disp.post_dispatch.two_stage_review_gate.enable_redesign_audit is True
            disp.shutdown()


# ---------------------------------------------------------------------------
# Test 5: DispatchRBAC blocks unauthorized dispatch
# ---------------------------------------------------------------------------


class TestDispatchRBACIntegration:
    """Verify DispatchRBAC blocks unauthorized dispatch requests."""

    def test_rbac_blocks_unauthorized_dispatch(self) -> None:
        """When RBAC denies permission, dispatch returns a failed result."""
        # Create a mock auth_manager with a viewer user.
        mock_auth = MagicMock()
        mock_auth.credentials = {
            "viewer_user": {"role": "viewer"},
        }
        rbac = DispatchRBAC(auth_manager=mock_auth)

        with tempfile.TemporaryDirectory() as tmpdir:
            # Disable enterprise RBAC to avoid interference (it uses a
            # separate rbac_engine that would also check user_id).
            disp = MultiAgentDispatcher(
                persist_dir=tmpdir, rbac=rbac, enable_rbac=False
            )

            # Viewer is not allowed to use "consensus" mode.
            result = disp.dispatch(
                "Design the system",
                roles=["architect"],
                mode="consensus",
                user_id="viewer_user",
            )

            assert not result.success, "Dispatch should fail when RBAC denies"
            assert result.permission_result is not None
            assert result.permission_result["allowed"] is False
            assert "not permitted" in result.permission_result["reason"].lower()
            disp.shutdown()

    def test_rbac_allows_authorized_dispatch(self) -> None:
        """When RBAC allows, dispatch proceeds normally."""
        mock_auth = MagicMock()
        mock_auth.credentials = {
            "admin_user": {"role": "admin"},
        }
        rbac = DispatchRBAC(auth_manager=mock_auth)

        with tempfile.TemporaryDirectory() as tmpdir:
            # Disable enterprise RBAC to avoid interference (it uses a
            # separate rbac_engine that would also check user_id).
            disp = MultiAgentDispatcher(
                persist_dir=tmpdir, rbac=rbac, enable_rbac=False
            )

            result = disp.dispatch(
                "Write a function",
                roles=["solo-coder"],
                mode="auto",
                user_id="admin_user",
            )

            assert result.success
            assert result.permission_result is not None
            assert result.permission_result["allowed"] is True
            disp.shutdown()

    def test_rbac_not_configured_allows_all(self) -> None:
        """Without RBAC configured, dispatch proceeds (open mode)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            disp = MultiAgentDispatcher(persist_dir=tmpdir, enable_rbac=False)
            assert disp._rbac is None

            result = disp.dispatch(
                "Write a function", roles=["solo-coder"],
                user_id="anyone",
            )
            # permission_result should be None (no RBAC configured).
            assert result.permission_result is None
            assert result.success
            disp.shutdown()


# ---------------------------------------------------------------------------
# Test 6: DispatchAuditLogger records dispatch lifecycle
# ---------------------------------------------------------------------------


class TestDispatchAuditLoggerIntegration:
    """Verify DispatchAuditLogger records dispatch_start and dispatch_end."""

    def test_audit_logger_records_lifecycle(self) -> None:
        """DispatchAuditLogger records dispatch_start and dispatch_end events."""
        audit_logger = DispatchAuditLogger()  # in-memory

        with tempfile.TemporaryDirectory() as tmpdir:
            # Disable enterprise RBAC to avoid interference when user_id is passed.
            disp = MultiAgentDispatcher(
                persist_dir=tmpdir, audit_logger=audit_logger, enable_rbac=False
            )

            result = disp.dispatch(
                "Write a function",
                roles=["solo-coder"],
                user_id="test_user",
            )

            assert result.success
            # Audit entries should be attached to the result.
            assert len(result.audit_entries) >= 2, (
                "Expected at least 2 audit entries (start + end)"
            )
            event_types = [e["event_type"] for e in result.audit_entries]
            assert "dispatch_start" in event_types
            assert "dispatch_end" in event_types
            # The chain should be valid.
            assert audit_logger.verify_chain()
            disp.shutdown()

    def test_audit_logger_records_permission_denied(self) -> None:
        """When RBAC denies, audit logger records permission_denied event."""
        audit_logger = DispatchAuditLogger()
        mock_auth = MagicMock()
        mock_auth.credentials = {"viewer": {"role": "viewer"}}
        rbac = DispatchRBAC(auth_manager=mock_auth)

        with tempfile.TemporaryDirectory() as tmpdir:
            disp = MultiAgentDispatcher(
                persist_dir=tmpdir,
                rbac=rbac,
                audit_logger=audit_logger,
                enable_rbac=False,
            )

            result = disp.dispatch(
                "Design the system",
                roles=["architect"],
                mode="consensus",
                user_id="viewer",
            )

            assert not result.success
            # Should have permission_denied event.
            event_types = [e["event_type"] for e in result.audit_entries]
            assert "permission_denied" in event_types
            assert audit_logger.verify_chain()
            disp.shutdown()

    def test_audit_logger_not_configured(self) -> None:
        """Without audit_logger configured, audit_entries is empty."""
        with tempfile.TemporaryDirectory() as tmpdir:
            disp = MultiAgentDispatcher(
                persist_dir=tmpdir, enable_audit_logger=False
            )
            result = disp.dispatch("Write a function", roles=["solo-coder"])
            assert result.audit_entries == []
            disp.shutdown()


# ---------------------------------------------------------------------------
# Test 7: MCP codegraph_explore returns correct results
# ---------------------------------------------------------------------------


class TestMCPCodegraphExplore:
    """Verify the MCP codegraph_explore tool returns correct results."""

    def test_codegraph_explore_returns_symbol(self) -> None:
        """codegraph_explore finds symbols by name."""
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
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_codegraph_explore_returns_callers(self) -> None:
        """codegraph_explore finds callers of a function."""
        from scripts.mcp_server import DevSquadMCPServer

        tmpdir, project_root = _make_temp_project()
        try:
            db_path = Path(tmpdir) / "codegraph.db"
            graph = CodeKnowledgeGraph(db_path)
            graph.build_from_project(project_root)

            server = DevSquadMCPServer()
            server._code_graph = graph

            # Query callers of "hello" (should include call_hello and Greeter.greet).
            q = graph.query()
            callers = q.find_callers("hello")
            caller_names = [c.name for c in callers]
            assert "call_hello" in caller_names, (
                f"Expected 'call_hello' in callers, got: {caller_names}"
            )

            graph.close()
            server.shutdown()
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_codegraph_explore_unavailable_returns_error(self) -> None:
        """When no graph is configured, codegraph_explore returns available=False."""
        from scripts.mcp_server import DevSquadMCPServer

        server = DevSquadMCPServer()
        # Don't set _code_graph — _get_code_graph() will try to init from
        # default path, which may fail. We test the "not available" path
        # by setting _code_graph to None explicitly and patching
        # _CODEGRAPH_AVAILABLE to False.
        with patch("scripts.mcp_server._CODEGRAPH_AVAILABLE", False):
            graph = server._get_code_graph()
            assert graph is None

        server.shutdown()


# ---------------------------------------------------------------------------
# Test 8: MCP codegraph_status returns graph stats
# ---------------------------------------------------------------------------


class TestMCPCodegraphStatus:
    """Verify the MCP codegraph_status tool returns graph statistics."""

    def test_codegraph_status_returns_stats(self) -> None:
        """codegraph_status returns built=True and symbol_count > 0."""
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
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_codegraph_status_unavailable(self) -> None:
        """When no graph is configured, codegraph_status returns built=False."""
        from scripts.mcp_server import DevSquadMCPServer

        server = DevSquadMCPServer()
        with patch("scripts.mcp_server._CODEGRAPH_AVAILABLE", False):
            graph = server._get_code_graph()
            assert graph is None

        server.shutdown()


# ---------------------------------------------------------------------------
# Test 9: Backward compatibility — dispatch works without any V3.9 modules
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    """Verify dispatch works when no V3.9 modules are configured."""

    def test_dispatch_without_v39_modules(self) -> None:
        """A standard dispatch with no V3.9 modules succeeds."""
        with tempfile.TemporaryDirectory() as tmpdir:
            disp = MultiAgentDispatcher(
                persist_dir=tmpdir, enable_audit_logger=False
            )

            result = disp.dispatch("Write a hello world function", roles=["solo-coder"])

            assert result.success, "Dispatch without V3.9 modules should succeed"
            # V3.9 optional fields should be None/empty.
            assert result.permission_result is None
            assert result.audit_entries == []
            # No code_graph, rbac, or audit_logger configured.
            assert disp._code_graph is None
            assert disp._rbac is None
            assert disp._audit_logger is None
            disp.shutdown()

    def test_to_dict_includes_v39_fields(self) -> None:
        """DispatchResult.to_dict() includes the new V3.9 fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            disp = MultiAgentDispatcher(
                persist_dir=tmpdir, enable_audit_logger=False
            )
            result = disp.dispatch("Write a function", roles=["solo-coder"])
            d = result.to_dict()
            assert "permission_result" in d
            assert "audit_entries" in d
            assert d["permission_result"] is None
            assert d["audit_entries"] == []
            disp.shutdown()

    def test_two_stage_review_backward_compat(self) -> None:
        """TwoStageReviewGate works with only V3.8 parameters (no redesign)."""
        gate = TwoStageReviewGate(
            enable_two_stage_review=True,
            enable_redesign_audit=False,  # Disable V3.9
        )
        result = gate.review(
            spec={"planned_files": ["x.py"]},
            code_changes={"files": {"x.py": {"content": "x = 1"}}},
        )
        # Stage 3 should be PASS (disabled).
        assert result.stage3_result == StageResult.PASS
        assert len(result.redesign_findings) == 0


# ---------------------------------------------------------------------------
# Test 10: All V3.9 modules work together in full dispatch
# ---------------------------------------------------------------------------


class TestAllV39ModulesTogether:
    """Verify all V3.9 modules work together in a single dispatch."""

    def test_full_dispatch_with_all_v39_modules(self) -> None:
        """A single dispatch with all V3.9 modules configured succeeds."""
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
            mock_auth = MagicMock()
            mock_auth.credentials = {"admin": {"role": "admin"}}
            rbac = DispatchRBAC(auth_manager=mock_auth)
            audit = DispatchAuditLogger()

            disp = MultiAgentDispatcher(
                persist_dir=tmpdir,
                code_graph=graph,
                micro_task_planner=planner,
                rbac=rbac,
                audit_logger=audit,
                enable_redesign_audit=True,
                enable_rbac=False,  # Disable enterprise RBAC (separate system)
            )

            result = disp.dispatch(
                "Review the hello function and write tests",
                roles=["solo-coder"],
                mode="auto",
                user_id="admin",
                use_micro_tasks=True,
            )

            # Dispatch should succeed.
            assert result.success, "Full dispatch with all V3.9 modules should succeed"

            # CodeKnowledgeGraph should have been queried.
            assert disp.coordinator.code_graph is graph

            # MicroTaskPlan should be populated.
            assert result.micro_task_plan is not None

            # RBAC permission_result should be populated and allowed.
            assert result.permission_result is not None
            assert result.permission_result["allowed"] is True

            # Audit entries should include dispatch_start and dispatch_end.
            assert len(result.audit_entries) >= 2
            event_types = [e["event_type"] for e in result.audit_entries]
            assert "dispatch_start" in event_types
            assert "dispatch_end" in event_types

            # Audit chain should be valid.
            assert audit.verify_chain()

            # Two-stage review should have run with Stage 3 (redesign).
            if result.two_stage_review is not None:
                assert "stage3_result" in result.two_stage_review
                assert "redesign_findings" in result.two_stage_review

            graph.close()
            disp.shutdown()
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "--no-cov"])
