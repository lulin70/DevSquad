#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for FeedbackControlLoop module (V3.6.0)

Tests cover:
- Dry-run mode simulation
- Quality gate pass (no iteration)
- Quality gate fail (iteration triggered)
- Max iterations limit enforcement
- Quality assessment accuracy
- Task refinement logic
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from scripts.collaboration.dispatcher import DispatchResult
from scripts.collaboration.feedback_control_loop import FeedbackControlLoop


class MockDispatcher:
    """Mock dispatcher for testing FeedbackControlLoop."""

    def __init__(self, results_sequence=None):
        self.results_sequence = results_sequence or []
        self.call_count = 0

    def dispatch(self, task, roles=None, mode="auto", **kwargs):
        """Return pre-configured result or default success result."""
        if self.call_count < len(self.results_sequence):
            result = self.results_sequence[self.call_count]
        else:
            result = DispatchResult(
                success=True,
                task_description=task,
                matched_roles=roles or [],
                summary="Default successful dispatch",
                duration_seconds=1.0,
            )
        self.call_count += 1
        return result


class TestFeedbackControlLoopDryRun:
    """Test dry-run mode functionality."""

    def test_dry_run_returns_immediately(self):
        """Dry run should return without calling dispatcher."""
        mock_disp = MockDispatcher()
        loop = FeedbackControlLoop(mock_disp, quality_gate=0.7, max_iterations=3)

        result = loop.run("Test task", dry_run=True)

        assert result is not None
        assert result.success is True
        assert "[DRY RUN]" in result.summary
        assert mock_disp.call_count == 0, "Dispatcher should not be called in dry_run"

    def test_dry_run_records_iteration_history(self):
        """Dry run should record one iteration in history."""
        mock_disp = MockDispatcher()
        loop = FeedbackControlLoop(mock_disp)

        loop.run("Test task", dry_run=True)

        assert loop.iteration_count == 1
        assert len(loop.iteration_history) == 1
        assert loop.iteration_history[0]["iteration"] == 1


class TestFeedbackControlLoopQualityGatePass:
    """Test behavior when quality gate passes on first attempt."""

    def test_high_quality_result_no_iteration(self):
        """Result with high quality should not trigger refinement."""
        high_quality_result = DispatchResult(
            success=True,
            task_description="High quality task",
            matched_roles=["architect", "tester"],
            worker_results=[
                {"role_id": "architect", "success": True, "output": "Good design"},
                {"role_id": "tester", "success": True, "output": "Good tests"},
            ],
            consensus_records=[{"outcome": "APPROVED", "topic": "Design"}],
            summary="High quality output",
            duration_seconds=2.0,
        )

        mock_disp = MockDispatcher(results_sequence=[high_quality_result])
        loop = FeedbackControlLoop(mock_disp, quality_gate=0.7, max_iterations=3)

        result = loop.run("Test task")

        assert result.success is True
        assert loop.iteration_count == 1, "Should only iterate once when quality passes"
        assert loop.best_quality >= 0.7
        stats = loop.get_statistics()
        assert stats["converged"] is True
        assert stats["converged_at_iteration"] == 1

    def test_perfect_quality_score(self):
        """Perfect result should get maximum quality score."""
        perfect_result = DispatchResult(
            success=True,
            task_description="Perfect task",
            matched_roles=["architect", "security", "tester"],
            worker_results=[
                {"role_id": "architect", "success": True, "output": "Design"},
                {"role_id": "security", "success": True, "output": "Secure"},
                {"role_id": "tester", "success": True, "output": "Tested"},
            ],
            consensus_records=[
                {"outcome": "APPROVED", "topic": "Design"},
                {"outcome": "APPROVED", "topic": "Security"},
            ],
            summary="Perfect execution",
            duration_seconds=1.5,
        )

        mock_disp = MockDispatcher(results_sequence=[perfect_result])
        loop = FeedbackControlLoop(mock_disp)

        loop.run("Test task")
        quality = loop._assess_quality(perfect_result)

        assert quality >= 0.85, f"Expected high quality score, got {quality}"


class TestFeedbackControlLoopQualityGateFail:
    """Test behavior when quality gate fails and iteration occurs."""

    def test_low_quality_triggers_iteration(self):
        """Low quality result should trigger at least one refinement."""
        low_quality_result = DispatchResult(
            success=False,
            task_description="Low quality task",
            matched_roles=["architect"],
            worker_results=[
                {"role_id": "architect", "success": False, "error": "Timeout error"},
            ],
            errors=["Timeout error occurred"],
            summary="Failed execution",
            duration_seconds=10.0,
        )

        improved_result = DispatchResult(
            success=True,
            task_description="Improved task",
            matched_roles=["architect", "tester"],
            worker_results=[
                {"role_id": "architect", "success": True, "output": "Better design"},
                {"role_id": "tester", "success": True, "output": "Tests added"},
            ],
            summary="Improved execution",
            duration_seconds=3.0,
        )

        mock_disp = MockDispatcher(results_sequence=[low_quality_result, improved_result])
        loop = FeedbackControlLoop(mock_disp, quality_gate=0.7, max_iterations=3)

        result = loop.run("Test task")

        assert mock_disp.call_count == 2, f"Expected 2 calls, got {mock_disp.call_count}"
        assert loop.iteration_count == 2
        assert len(loop.iteration_history) == 2
        assert loop.iteration_history[0]["passed"] is False
        stats = loop.get_statistics()
        assert stats["iterations"] == 2

    def test_adjustment_generated_on_failure(self):
        """Adjustment should be generated when quality fails."""
        failed_result = DispatchResult(
            success=False,
            task_description="Failed task",
            worker_results=[
                {"role_id": "coder", "success": False, "error": "Compilation error"},
            ],
            errors=["Compilation error: syntax error"],
            summary="Failed",
            duration_seconds=5.0,
        )

        mock_disp = MockDispatcher(results_sequence=[failed_result])
        loop = FeedbackControlLoop(mock_disp, quality_gate=0.8, max_iterations=2)

        loop.run("Test task")

        assert len(loop.iteration_history) >= 1
        first_iter = loop.iteration_history[0]
        assert first_iter["passed"] is False
        assert "adjustment" in first_iter, "Adjustment should be recorded"
        assert len(first_iter["adjustment"]) > 0, "Adjustment should not be empty"


class TestFeedbackControlLoopMaxIterations:
    """Test max iterations limit enforcement."""

    def test_stops_at_max_iterations(self):
        """Should stop iterating after reaching max_iterations limit."""
        bad_result = DispatchResult(
            success=False,
            task_description="Always failing",
            worker_results=[
                {"role_id": "architect", "success": False, "error": "Error"},
            ],
            errors=["Persistent error"],
            summary="Failed",
            duration_seconds=1.0,
        )

        mock_disp = MockDispatcher(results_sequence=[bad_result] * 5)
        loop = FeedbackControlLoop(mock_disp, quality_gate=0.9, max_iterations=2)

        result = loop.run("Test task")

        total_calls = 1 + loop.max_iterations
        assert mock_disp.call_count == total_calls, \
            f"Expected {total_calls} calls, got {mock_disp.call_count}"
        assert loop.iteration_count == total_calls
        stats = loop.get_statistics()
        assert stats["iterations"] == total_calls
        assert stats["converged"] is False, "Should not converge with persistent failures"

    def test_max_iterations_of_one(self):
        """Max iterations of 1 means only initial + 1 retry."""
        fail_result = DispatchResult(
            success=False,
            task_description="Fail",
            worker_results=[],
            errors=["Error"],
            summary="Fail",
            duration_seconds=1.0,
        )

        mock_disp = MockDispatcher(results_sequence=[fail_result] * 3)
        loop = FeedbackControlLoop(mock_disp, quality_gate=0.99, max_iterations=1)

        loop.run("Task")

        assert loop.iteration_count == 2, "Should have initial + 1 iteration"


class TestFeedbackControlLoopQualityAssessment:
    """Test quality assessment logic."""

    def test_successful_dispatch_higher_score(self):
        """Successful dispatch should score higher than failed."""
        success = DispatchResult(
            success=True,
            task_description="Success",
            worker_results=[{"role_id": "arch", "success": True}],
            duration_seconds=1.0,
        )
        failure = DispatchResult(
            success=False,
            task_description="Failure",
            worker_results=[{"role_id": "arch", "success": False}],
            errors=["Error"],
            duration_seconds=1.0,
        )

        loop = FeedbackControlLoop(MockDispatcher())
        success_quality = loop._assess_quality(success)
        fail_quality = loop._assess_quality(failure)

        assert success_quality > fail_quality, \
            f"Success ({success_quality}) should be higher than failure ({fail_quality})"

    def test_more_workers_higher_score(self):
        """More successful workers should increase quality score."""
        few_workers = DispatchResult(
            success=True,
            task_description="Few workers",
            worker_results=[
                {"role_id": "arch", "success": True},
                {"role_id": "arch", "success": False},
            ],
            duration_seconds=1.0,
        )
        many_workers = DispatchResult(
            success=True,
            task_description="Many workers",
            worker_results=[
                {"role_id": "arch", "success": True},
                {"role_id": "sec", "success": True},
                {"role_id": "test", "success": True},
            ],
            duration_seconds=1.0,
        )

        loop = FeedbackControlLoop(MockDispatcher())
        few_score = loop._assess_quality(few_workers)
        many_score = loop._assess_quality(many_workers)

        assert many_score > few_score, \
            f"Many workers ({many_score}) should score higher than few ({few_score})"

    def test_errors_reduce_score(self):
        """Errors should reduce quality score."""
        clean = DispatchResult(
            success=True,
            task_description="Clean",
            worker_results=[{"role_id": "arch", "success": True}],
            duration_seconds=1.0,
        )
        with_errors = DispatchResult(
            success=True,
            task_description="With errors",
            worker_results=[{"role_id": "arch", "success": True}],
            errors=["Warning 1", "Warning 2", "Warning 3", "Warning 4"],
            duration_seconds=1.0,
        )

        loop = FeedbackControlLoop(MockDispatcher())
        clean_score = loop._assess_quality(clean)
        error_score = loop._assess_quality(with_errors)

        assert error_score < clean_score, \
            f"With errors ({error_score}) should score lower than clean ({clean_score})"

    def test_consensus_increases_score(self):
        """Consensus approval should increase quality score."""
        no_consensus = DispatchResult(
            success=True,
            task_description="No consensus",
            worker_results=[{"role_id": "arch", "success": True}],
            consensus_records=[],
            duration_seconds=1.0,
        )
        with_consensus = DispatchResult(
            success=True,
            task_description="With consensus",
            worker_results=[{"role_id": "arch", "success": True}],
            consensus_records=[
                {"outcome": "APPROVED", "topic": "Design"},
                {"outcome": "APPROVED", "topic": "Security"},
            ],
            duration_seconds=1.0,
        )

        loop = FeedbackControlLoop(MockDispatcher())
        no_con_score = loop._assess_quality(no_consensus)
        con_score = loop._assess_quality(with_consensus)

        assert con_score > no_con_score, \
            f"With consensus ({con_score}) should score higher than without ({no_con_score})"

    def test_none_result_zero_score(self):
        """None result should return zero quality."""
        loop = FeedbackControlLoop(MockDispatcher())
        assert loop._assess_quality(None) == 0.0


class TestFeedbackControlLoopTaskRefinement:
    """Test task refinement logic."""

    def test_refine_task_merges_original_and_adjustment(self):
        """Refined task should contain both original and adjustment."""
        loop = FeedbackControlLoop(MockDispatcher())

        original = "Design a REST API"
        adjustment = "Add security role review | Simplify authentication"

        refined = loop._refine_task(original, adjustment)

        assert original in refined
        assert adjustment in refined
        assert "[Iteration Feedback]" in refined

    def test_generate_adjustment_for_failed_workers(self):
        """Should generate relevant adjustments for failed workers."""
        failed_result = DispatchResult(
            success=False,
            task_description="Complex task",
            worker_results=[
                {"role_id": "security", "success": False, "error": "Permission denied"},
                {"role_id": "devops", "success": False, "error": "Timeout"},
            ],
            errors=["Security check failed", "Deployment timeout"],
            summary="Multiple failures",
            duration_seconds=15.0,
        )

        loop = FeedbackControlLoop(MockDispatcher())
        adjustment = loop._generate_adjustment(failed_result, 0.3)

        assert isinstance(adjustment, str)
        assert len(adjustment) > 10, "Adjustment should be meaningful"
        assert "security" in adjustment.lower() or "timeout" in adjustment.lower() or "fail" in adjustment.lower()

    def test_generate_adjustment_for_empty_results(self):
        """Should handle empty worker results gracefully."""
        empty_result = DispatchResult(
            success=False,
            task_description="Empty task",
            worker_results=[],
            errors=["No output generated"],
            summary="No results",
            duration_seconds=0.5,
        )

        loop = FeedbackControlLoop(MockDispatcher())
        adjustment = loop._generate_adjustment(empty_result, 0.2)

        assert isinstance(adjustment, str)
        assert len(adjustment) > 0


class TestFeedbackControlLoopStatistics:
    """Test statistics and history tracking."""

    def test_get_statistics_after_run(self):
        """Statistics should reflect execution history."""
        results = [
            DispatchResult(success=False, task_description="T", worker_results=[], errors=["E"], duration_seconds=1),
            DispatchResult(success=True, task_description="T", worker_results=[{"role_id": "a", "success": True}], duration_seconds=1),
        ]

        mock_disp = MockDispatcher(results_sequence=results)
        loop = FeedbackControlLoop(mock_disp, quality_gate=0.8, max_iterations=2)

        loop.run("Test task")

        stats = loop.get_statistics()
        assert stats["iterations"] >= 2
        assert stats["iterations"] <= 3
        assert 0 <= stats["best_quality"] <= 1
        assert 0 <= stats["worst_quality"] <= 1
        assert 0 <= stats["avg_quality"] <= 1
        assert "history" in stats
        assert len(stats["history"]) >= 2

    def test_reset_clears_state(self):
        """Reset should clear all state for reuse."""
        mock_disp = MockDispatcher(results_sequence=[
            DispatchResult(success=True, task_description="T", duration_seconds=1)
        ])
        loop = FeedbackControlLoop(mock_disp)

        loop.run("First task")
        assert loop.iteration_count > 0

        loop.reset()
        assert loop.iteration_count == 0
        assert loop.best_quality == 0.0
        assert len(loop.iteration_history) == 0

    def test_best_result_tracking(self):
        """Should track best result across iterations."""
        poor = DispatchResult(success=False, task_description="T", worker_results=[], errors=["E"], duration_seconds=1)
        good = DispatchResult(success=True, task_description="T", worker_results=[{"r": "a", "s": True}], duration_seconds=1)

        mock_disp = MockDispatcher(results_sequence=[poor, good])
        loop = FeedbackControlLoop(mock_disp, quality_gate=0.95, max_iterations=2)

        loop.run("Test")

        assert loop.best_result is not None
        assert loop.best_result.success is True
        assert loop.best_quality > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
