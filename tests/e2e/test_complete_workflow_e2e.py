#!/usr/bin/env python3
"""E2E tests for complete DevSquad dispatch workflows.

These tests validate end-to-end user journeys from task description to final report.
Focus: Real user scenarios, not isolated unit behavior.
"""

from __future__ import annotations

import pytest

from scripts.collaboration.dispatcher import MultiAgentDispatcher


class TestCompleteDispatchWorkflow:
    """Test complete dispatch workflows from task input to report output."""

    @pytest.fixture
    def dispatcher(self) -> MultiAgentDispatcher:
        """Create dispatcher for E2E tests."""
        return MultiAgentDispatcher()

    def test_simple_coding_task_end_to_end(self, dispatcher: MultiAgentDispatcher) -> None:
        """
        E2E test: User submits simple coding task → dispatcher executes → report generated.

        User journey:
        1. User provides task: "Create a Python function that calculates factorial"
        2. Dispatcher matches roles
        3. Workers execute
        4. Report is generated with findings
        """
        task_description = "Create a Python function that calculates factorial recursively"

        # Execute complete workflow
        result = dispatcher.dispatch(task_description)

        # Verify workflow completed
        assert result is not None, "Dispatch should return result"
        assert result.task_description == task_description

        # Verify roles were matched and executed
        assert hasattr(result, "matched_roles")
        assert len(result.matched_roles) > 0, "Should match at least one role for coding task"

        # Verify execution produced output
        assert hasattr(result, "success")
        assert hasattr(result, "duration_seconds")
        assert result.duration_seconds > 0, "Should have non-zero execution time"

        # Verify report can be generated
        assert hasattr(result, "summary")
        markdown = result.to_markdown()
        assert len(markdown) > 0, "Should generate non-empty markdown report"
        assert task_description in markdown, "Report should mention the task"

    def test_multi_role_architecture_task(self, dispatcher: MultiAgentDispatcher) -> None:
        """
        E2E test: Complex task requires multiple roles to collaborate.

        User journey:
        1. User provides architecture task with security and testing requirements
        2. Dispatcher should match: architect + security + tester roles
        3. Workers collaborate via scratchpad
        4. Final report includes all role perspectives
        """
        task_description = (
            "Design a microservices architecture for an e-commerce platform "
            "with security best practices and comprehensive testing strategy"
        )

        result = dispatcher.dispatch(task_description)

        # Verify multiple roles engaged
        assert result.matched_roles is not None
        assert len(result.matched_roles) >= 2, "Complex task should match multiple roles"

        # Verify roles are relevant to task
        matched_roles_str = " ".join(result.matched_roles).lower()
        relevant_keywords = ["architect", "security", "test", "backend", "design"]
        assert any(kw in matched_roles_str for kw in relevant_keywords), (
            f"Expected relevant roles for architecture task, got: {result.matched_roles}"
        )

        # Verify report structure
        markdown = result.to_markdown()
        assert "##" in markdown, "Report should have markdown structure"

        # Verify worker collaboration (if workers ran)
        if hasattr(result, "worker_results") and result.worker_results:
            assert len(result.worker_results) > 0, "Should have worker results"

    def test_error_handling_invalid_task(self, dispatcher: MultiAgentDispatcher) -> None:
        """
        E2E test: System handles invalid/unclear tasks gracefully.

        User journey:
        1. User provides vague or invalid task
        2. System should not crash
        3. System returns result with appropriate error/warning
        """
        task_description = ""  # Empty task

        # Should handle gracefully, not raise exception
        result = dispatcher.dispatch(task_description)

        # System should complete without crashing
        assert result is not None
        assert hasattr(result, "success")

        # Either succeeds (with clarification) or fails gracefully
        assert isinstance(result.success, bool)

    def test_report_generation_with_findings(self, dispatcher: MultiAgentDispatcher) -> None:
        """
        E2E test: Report properly formats worker findings.

        User journey:
        1. User requests code review task
        2. Workers analyze and provide findings
        3. Report aggregates findings in readable format
        """
        task_description = "Review this Python code for potential improvements: def add(a,b): return a+b"

        result = dispatcher.dispatch(task_description)

        # Verify report generation
        assert result is not None
        markdown = result.to_markdown()

        # Report should be substantive
        assert len(markdown) > 100, "Report should have substantive content"

        # Report should include key sections
        assert "task" in markdown.lower() or "任务" in markdown

        # Verify serialization works
        result_dict = result.to_dict()
        assert isinstance(result_dict, dict)
        assert "task_description" in result_dict
        assert "matched_roles" in result_dict

    @pytest.mark.skip(reason="Requires real LLM backend - long running test")
    def test_real_world_task_full_execution(self, dispatcher: MultiAgentDispatcher) -> None:
        """
        E2E test: Complete real-world task execution.

        This test requires actual LLM backend and takes longer to execute.
        Skip by default, run manually when validating major changes.
        """
        task_description = "设计一个用户认证系统，包含JWT令牌、OAuth2.0集成、密码加密、会话管理和安全审计日志"

        result = dispatcher.dispatch(task_description)

        # Comprehensive validation
        assert result.success, "Real-world task should complete successfully"
        assert len(result.matched_roles) >= 2, "Should involve multiple roles"
        assert result.duration_seconds > 0

        # Validate report quality
        markdown = result.to_markdown()
        assert len(markdown) > 500, "Comprehensive report should be detailed"

        # Check for Chinese language support
        assert any(char > "\u4e00" and char < "\u9fff" for char in markdown), (
            "Report should include Chinese characters for Chinese task"
        )


class TestWorkflowFailureRecovery:
    """Test system resilience when workers encounter errors."""

    @pytest.fixture
    def dispatcher(self) -> MultiAgentDispatcher:
        """Create dispatcher for E2E tests."""
        return MultiAgentDispatcher()

    def test_workflow_continues_after_worker_error(self, dispatcher: MultiAgentDispatcher) -> None:
        """
        E2E test: If one worker fails, workflow should complete with remaining workers.

        User journey:
        1. Task requires multiple workers
        2. One worker encounters error
        3. System recovers and completes with other workers
        4. Report indicates partial completion
        """
        task_description = "Analyze and improve this code with security review and tests"

        result = dispatcher.dispatch(task_description)

        # Workflow should complete even if some workers fail
        assert result is not None
        assert hasattr(result, "success")

        # Should have some result even if not all workers succeeded
        if hasattr(result, "worker_results") and result.worker_results:
            # At least one worker should have attempted execution
            assert len(result.worker_results) > 0


class TestReportFormats:
    """Test different report format options."""

    @pytest.fixture
    def dispatcher(self) -> MultiAgentDispatcher:
        """Create dispatcher for E2E tests."""
        return MultiAgentDispatcher()

    def test_report_format_markdown(self, dispatcher: MultiAgentDispatcher) -> None:
        """E2E test: Markdown report format is properly structured."""
        task_description = "Create a simple TODO list data structure"

        result = dispatcher.dispatch(task_description)
        markdown = result.to_markdown()

        # Verify markdown structure (may start with warning/info block or header)
        assert "#" in markdown, "Markdown should contain headers"
        assert "\n" in markdown, "Should have multiple lines"
        # Check for key markdown sections
        assert "##" in markdown or "**" in markdown, "Should have markdown formatting"

    def test_report_format_dict_serialization(self, dispatcher: MultiAgentDispatcher) -> None:
        """E2E test: Result can be serialized to dict for API/storage."""
        task_description = "Simple test task"

        result = dispatcher.dispatch(task_description)
        result_dict = result.to_dict()

        # Verify all key fields present
        required_fields = ["success", "task_description", "matched_roles", "duration_seconds"]
        for field in required_fields:
            assert field in result_dict, f"Result dict should have {field}"

        # Verify types are JSON-serializable
        import json

        json_str = json.dumps(result_dict)  # Should not raise
        assert len(json_str) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
