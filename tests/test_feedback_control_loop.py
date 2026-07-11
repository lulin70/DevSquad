"""Tests for FeedbackControlLoop — V3.7.0 closed-loop iteration engine.

Covers:
- __init__ with parameter clamping (quality_gate, max_iterations)
- run() with dry_run, real dispatch, quality gate pass/fail, max iterations
- _assess_quality() with all factor combinations
- _generate_adjustment() with various failure patterns
- _refine_task() / _llm_refine_task() with multiple backend types
- reset() and get_statistics()
"""

import pytest

from scripts.collaboration.feedback_control_loop import FeedbackControlLoop

# ---------------------------------------------------------------------------
# Stub helpers
# ---------------------------------------------------------------------------


class StubDispatcher:
    """Minimal dispatcher stub for testing run()."""

    def __init__(self, results=None):
        self._results = results or []
        self._call_count = 0
        self.calls = []

    def dispatch(self, task, roles=None, mode="auto", **kwargs):
        self.calls.append({"task": task, "roles": roles, "mode": mode, "kwargs": kwargs})
        if self._call_count < len(self._results):
            result = self._results[self._call_count]
        else:
            result = self._results[-1] if self._results else None
        self._call_count += 1
        return result


class StubResult:
    """Minimal DispatchResult stub."""

    def __init__(
        self,
        success=True,
        worker_results=None,
        consensus_records=None,
        errors=None,
        summary="test summary",
    ):
        self.success = success
        self.worker_results = worker_results or []
        self.consensus_records = consensus_records or []
        self.errors = errors or []
        self.summary = summary
        self.task_description = "test task"


class StubLLMBackend:
    """Stub LLM backend with configurable generate()."""

    def __init__(self, response="Refined task description here"):
        self._response = response
        self.generate_calls = []

    def generate(self, prompt):
        self.generate_calls.append(prompt)
        return self._response


class StubLLMBackendCall:
    """Stub LLM backend with call() method."""

    def __init__(self, response="Refined via call"):
        self._response = response

    def call(self, _prompt):
        return self._response


class StubLLMBackendChat:
    """Stub LLM backend with chat() method."""

    def __init__(self, response="Refined via chat"):
        self._response = response

    def chat(self, _messages):
        return {"content": self._response}


# ---------------------------------------------------------------------------
# __init__ and properties
# ---------------------------------------------------------------------------


class TestInit:
    def test_defaults(self):
        loop = FeedbackControlLoop(StubDispatcher())
        assert loop.quality_gate == 0.7
        assert loop.max_iterations == 3
        assert loop.iteration_count == 0
        assert loop.iteration_history == []
        assert loop.best_result is None
        assert loop.best_quality == 0.0

    def test_custom_params(self):
        loop = FeedbackControlLoop(
            StubDispatcher(),
            quality_gate=0.9,
            max_iterations=5,
        )
        assert loop.quality_gate == 0.9
        assert loop.max_iterations == 5

    def test_quality_gate_clamped_high(self):
        loop = FeedbackControlLoop(StubDispatcher(), quality_gate=1.5)
        assert loop.quality_gate == 1.0

    def test_quality_gate_clamped_low(self):
        loop = FeedbackControlLoop(StubDispatcher(), quality_gate=-0.5)
        assert loop.quality_gate == 0.0

    def test_max_iterations_minimum_one(self):
        loop = FeedbackControlLoop(StubDispatcher(), max_iterations=0)
        assert loop.max_iterations == 1

    def test_max_iterations_negative(self):
        loop = FeedbackControlLoop(StubDispatcher(), max_iterations=-5)
        assert loop.max_iterations == 1


# ---------------------------------------------------------------------------
# run() — dry_run mode
# ---------------------------------------------------------------------------


class TestRunDryRun:
    def test_dry_run_returns_result(self):
        loop = FeedbackControlLoop(StubDispatcher())
        result = loop.run("Design system", dry_run=True)
        assert result is not None
        assert loop.iteration_count == 1

    def test_dry_run_records_history(self):
        loop = FeedbackControlLoop(StubDispatcher())
        loop.run("Design system", dry_run=True)
        assert len(loop.iteration_history) == 1
        record = loop.iteration_history[0]
        assert record["iteration"] == 1
        assert "quality" in record
        assert "passed" in record
        assert "task_preview" in record
        assert "timestamp" in record

    def test_dry_run_does_not_call_dispatcher(self):
        dispatcher = StubDispatcher()
        loop = FeedbackControlLoop(dispatcher)
        loop.run("Design system", dry_run=True)
        assert len(dispatcher.calls) == 0


# ---------------------------------------------------------------------------
# run() — real dispatch, quality gate pass on first iteration
# ---------------------------------------------------------------------------


class TestRunQualityGatePass:
    def test_passes_on_first_iteration(self):
        """High-quality result passes the gate immediately."""
        good_result = StubResult(
            success=True,
            worker_results=[{"success": True, "role_id": "arch"}],
            consensus_records=[{"outcome": "APPROVED"}],
        )
        dispatcher = StubDispatcher(results=[good_result])
        loop = FeedbackControlLoop(dispatcher, quality_gate=0.5)
        result = loop.run("Design system")
        assert result is good_result
        assert loop.iteration_count == 1

    def test_records_best_quality(self):
        good_result = StubResult(
            success=True,
            worker_results=[{"success": True}],
        )
        dispatcher = StubDispatcher(results=[good_result])
        loop = FeedbackControlLoop(dispatcher, quality_gate=0.3)
        loop.run("Design system")
        assert loop.best_quality > 0


# ---------------------------------------------------------------------------
# run() — quality gate fail, iterate until pass
# ---------------------------------------------------------------------------


class TestRunIterateUntilPass:
    def test_iterates_until_quality_passes(self):
        """First result is low quality, second is high quality."""
        bad_result = StubResult(
            success=False,
            worker_results=[{"success": False, "error": "failed", "role_id": "arch"}],
            errors=["error1"],
        )
        good_result = StubResult(
            success=True,
            worker_results=[{"success": True, "role_id": "arch"}],
            consensus_records=[{"outcome": "APPROVED"}],
        )
        dispatcher = StubDispatcher(results=[bad_result, good_result])
        loop = FeedbackControlLoop(dispatcher, quality_gate=0.5, max_iterations=3)
        result = loop.run("Design system")
        assert result is good_result
        assert loop.iteration_count == 2

    def test_max_iterations_reached(self):
        """All results fail the gate, loop stops at max_iterations."""
        bad_result = StubResult(
            success=False,
            worker_results=[],
            errors=["error"],
        )
        dispatcher = StubDispatcher(results=[bad_result])
        loop = FeedbackControlLoop(dispatcher, quality_gate=0.9, max_iterations=2)
        loop.run("Design system")
        assert loop.iteration_count == 3  # max_iterations + 1 (0, 1, 2)

    def test_best_result_tracked_across_iterations(self):
        """Best result is tracked even when gate not met."""
        low_quality = StubResult(success=False, worker_results=[])
        medium_quality = StubResult(
            success=True,
            worker_results=[{"success": True}],
        )
        dispatcher = StubDispatcher(results=[low_quality, medium_quality])
        loop = FeedbackControlLoop(dispatcher, quality_gate=0.95, max_iterations=2)
        result = loop.run("Design system")
        assert result is medium_quality
        assert loop.best_quality > 0

    def test_task_refined_between_iterations(self):
        """Task description is refined between iterations."""
        bad_result = StubResult(success=False, worker_results=[], errors=["error"])
        dispatcher = StubDispatcher(results=[bad_result])
        loop = FeedbackControlLoop(dispatcher, quality_gate=0.9, max_iterations=1)
        loop.run("Original task")
        # Second call should have refined task
        assert len(dispatcher.calls) == 2
        assert "Iteration Feedback" in dispatcher.calls[1]["task"]


# ---------------------------------------------------------------------------
# _assess_quality
# ---------------------------------------------------------------------------


class TestAssessQuality:
    def test_none_result_returns_zero(self):
        loop = FeedbackControlLoop(StubDispatcher())
        assert loop._assess_quality(None) == 0.0

    def test_success_true_high_score(self):
        loop = FeedbackControlLoop(StubDispatcher())
        result = StubResult(success=True, worker_results=[{"success": True}])
        score = loop._assess_quality(result)
        assert score > 0.5

    def test_success_false_lower_score(self):
        loop = FeedbackControlLoop(StubDispatcher())
        result = StubResult(success=False, worker_results=[{"success": False}])
        score = loop._assess_quality(result)
        assert score < 0.7

    def test_no_worker_results(self):
        loop = FeedbackControlLoop(StubDispatcher())
        result = StubResult(success=True, worker_results=[])
        score = loop._assess_quality(result)
        assert 0 < score < 1.0

    def test_consensus_approved(self):
        loop = FeedbackControlLoop(StubDispatcher())
        result = StubResult(
            success=True,
            worker_results=[{"success": True}],
            consensus_records=[{"outcome": "APPROVED"}],
        )
        score = loop._assess_quality(result)
        assert score > 0.7

    def test_consensus_rejected(self):
        loop = FeedbackControlLoop(StubDispatcher())
        result = StubResult(
            success=True,
            worker_results=[{"success": True}],
            consensus_records=[{"outcome": "REJECTED"}],
        )
        score = loop._assess_quality(result)
        assert score < 1.0

    def test_errors_reduce_score(self):
        loop = FeedbackControlLoop(StubDispatcher())
        result_no_errors = StubResult(success=True, worker_results=[{"success": True}])
        result_with_errors = StubResult(
            success=True,
            worker_results=[{"success": True}],
            errors=["err1", "err2"],
        )
        assert loop._assess_quality(result_with_errors) < loop._assess_quality(result_no_errors)

    def test_score_clamped_to_max_1(self):
        loop = FeedbackControlLoop(StubDispatcher())
        result = StubResult(
            success=True,
            worker_results=[{"success": True}],
            consensus_records=[{"outcome": "APPROVED"}],
        )
        score = loop._assess_quality(result)
        assert score <= 1.0

    def test_score_clamped_to_min_0(self):
        loop = FeedbackControlLoop(StubDispatcher())
        result = StubResult(
            success=False,
            worker_results=[],
            errors=["e1", "e2", "e3", "e4"],
        )
        score = loop._assess_quality(result)
        assert score >= 0.0

    def test_partial_worker_success(self):
        loop = FeedbackControlLoop(StubDispatcher())
        result = StubResult(
            success=True,
            worker_results=[
                {"success": True},
                {"success": False},
                {"success": True},
            ],
        )
        score = loop._assess_quality(result)
        assert 0 < score < 1.0


# ---------------------------------------------------------------------------
# _generate_adjustment
# ---------------------------------------------------------------------------


class TestGenerateAdjustment:
    def test_failed_workers_single_role(self):
        loop = FeedbackControlLoop(StubDispatcher())
        result = StubResult(
            success=False,
            worker_results=[{"success": False, "error": "err", "role_id": "architect"}],
        )
        adjustment = loop._generate_adjustment(result, 0.3)
        assert "architect" in adjustment

    def test_failed_workers_multiple_roles(self):
        loop = FeedbackControlLoop(StubDispatcher())
        result = StubResult(
            success=False,
            worker_results=[
                {"success": False, "error": "err", "role_id": "architect"},
                {"success": False, "error": "err", "role_id": "tester"},
            ],
        )
        adjustment = loop._generate_adjustment(result, 0.3)
        assert "architect" in adjustment or "tester" in adjustment

    def test_timeout_error(self):
        loop = FeedbackControlLoop(StubDispatcher())
        result = StubResult(
            success=False,
            worker_results=[],
            errors=["Task timed out after 30s"],
        )
        adjustment = loop._generate_adjustment(result, 0.3)
        assert "timeout" in adjustment.lower() or "complexity" in adjustment.lower()

    def test_permission_error(self):
        loop = FeedbackControlLoop(StubDispatcher())
        result = StubResult(
            success=False,
            worker_results=[],
            errors=["Permission denied for resource"],
        )
        adjustment = loop._generate_adjustment(result, 0.3)
        assert "permission" in adjustment.lower()

    def test_resource_error(self):
        loop = FeedbackControlLoop(StubDispatcher())
        result = StubResult(
            success=False,
            worker_results=[],
            errors=["Out of memory"],
        )
        adjustment = loop._generate_adjustment(result, 0.3)
        assert "resource" in adjustment.lower() or "memory" in adjustment.lower()

    def test_no_worker_results(self):
        loop = FeedbackControlLoop(StubDispatcher())
        result = StubResult(success=True, worker_results=[])
        adjustment = loop._generate_adjustment(result, 0.5)
        assert "vague" in adjustment.lower() or "criteria" in adjustment.lower()

    def test_low_success_rate(self):
        loop = FeedbackControlLoop(StubDispatcher())
        result = StubResult(
            success=False,
            worker_results=[
                {"success": True},
                {"success": False, "error": "err", "role_id": "a"},
                {"success": False, "error": "err", "role_id": "b"},
                {"success": False, "error": "err", "role_id": "c"},
            ],
        )
        adjustment = loop._generate_adjustment(result, 0.3)
        assert "success rate" in adjustment.lower() or "simplifying" in adjustment.lower()

    def test_quality_critically_low(self):
        loop = FeedbackControlLoop(StubDispatcher())
        result = StubResult(success=True, worker_results=[{"success": True}])
        adjustment = loop._generate_adjustment(result, 0.2)
        assert "critically" in adjustment.lower() or "reformulation" in adjustment.lower()

    def test_quality_moderately_low(self):
        loop = FeedbackControlLoop(StubDispatcher())
        result = StubResult(success=True, worker_results=[{"success": True}])
        adjustment = loop._generate_adjustment(result, 0.5)
        assert "acceptable" in adjustment.lower() or "strengthen" in adjustment.lower()

    def test_no_specific_issues_general_refinement(self):
        loop = FeedbackControlLoop(StubDispatcher())
        result = StubResult(success=True, worker_results=[{"success": True}])
        adjustment = loop._generate_adjustment(result, 0.65)
        assert "refinement" in adjustment.lower() or "review" in adjustment.lower()

    def test_general_error_type(self):
        loop = FeedbackControlLoop(StubDispatcher())
        result = StubResult(
            success=False,
            worker_results=[],
            errors=["Some unknown error occurred"],
        )
        adjustment = loop._generate_adjustment(result, 0.3)
        assert isinstance(adjustment, str)
        assert len(adjustment) > 0


# ---------------------------------------------------------------------------
# _refine_task / _llm_refine_task
# ---------------------------------------------------------------------------


class TestRefineTask:
    def test_no_llm_backend_uses_concatenation(self):
        loop = FeedbackControlLoop(StubDispatcher())
        refined = loop._refine_task("Original task", "Add more details")
        assert "Original task" in refined
        assert "Iteration Feedback" in refined
        assert "Add more details" in refined

    def test_llm_backend_generate_method(self):
        backend = StubLLMBackend(response="LLM refined task description")
        loop = FeedbackControlLoop(StubDispatcher(), llm_backend=backend)
        refined = loop._refine_task("Original task", "feedback")
        assert refined == "LLM refined task description"
        assert len(backend.generate_calls) == 1

    def test_llm_backend_call_method(self):
        backend = StubLLMBackendCall(response="Refined via call method")
        loop = FeedbackControlLoop(StubDispatcher(), llm_backend=backend)
        refined = loop._refine_task("Original task", "feedback")
        assert refined == "Refined via call method"

    def test_llm_backend_chat_method_dict_response(self):
        backend = StubLLMBackendChat(response="Refined via chat")
        loop = FeedbackControlLoop(StubDispatcher(), llm_backend=backend)
        refined = loop._refine_task("Original task", "feedback")
        assert refined == "Refined via chat"

    def test_llm_backend_chat_method_string_response(self):
        class StringChatBackend:
            def chat(self, _messages):
                return "String chat response"

        loop = FeedbackControlLoop(StubDispatcher(), llm_backend=StringChatBackend())
        refined = loop._refine_task("Original", "feedback")
        assert refined == "String chat response"

    def test_llm_backend_unsupported_type_raises(self):
        class UnsupportedBackend:
            pass

        loop = FeedbackControlLoop(StubDispatcher(), llm_backend=UnsupportedBackend())
        with pytest.raises(ValueError, match="Unsupported"):
            loop._llm_refine_task("task", "feedback")

    def test_llm_short_response_falls_back_to_concatenation(self):
        backend = StubLLMBackend(response="short")  # less than 10 chars
        loop = FeedbackControlLoop(StubDispatcher(), llm_backend=backend)
        refined = loop._refine_task("Original task", "feedback")
        assert "Original task" in refined
        assert "Iteration Feedback" in refined

    def test_llm_error_falls_back_to_concatenation(self):
        class ErrorBackend:
            def generate(self, _prompt):
                raise RuntimeError("LLM error")

        loop = FeedbackControlLoop(StubDispatcher(), llm_backend=ErrorBackend())
        refined = loop._refine_task("Original task", "feedback")
        assert "Original task" in refined
        assert "Iteration Feedback" in refined


# ---------------------------------------------------------------------------
# reset()
# ---------------------------------------------------------------------------


class TestReset:
    def test_reset_clears_history(self):
        loop = FeedbackControlLoop(StubDispatcher())
        loop.run("task", dry_run=True)
        assert len(loop.iteration_history) > 0
        loop.reset()
        assert loop.iteration_history == []
        assert loop.iteration_count == 0

    def test_reset_clears_best_result(self):
        loop = FeedbackControlLoop(StubDispatcher())
        loop.run("task", dry_run=True)
        loop.reset()
        assert loop.best_result is None
        assert loop.best_quality == 0.0

    def test_reset_allows_reuse(self):
        loop = FeedbackControlLoop(StubDispatcher())
        loop.run("task1", dry_run=True)
        loop.reset()
        loop.run("task2", dry_run=True)
        assert loop.iteration_count == 1
        assert len(loop.iteration_history) == 1


# ---------------------------------------------------------------------------
# get_statistics()
# ---------------------------------------------------------------------------


class TestGetStatistics:
    def test_empty_statistics(self):
        loop = FeedbackControlLoop(StubDispatcher())
        stats = loop.get_statistics()
        assert stats["iterations"] == 0
        assert stats["best_quality"] == 0.0
        assert stats["converged"] is False
        assert stats["history"] == []

    def test_statistics_after_dry_run(self):
        loop = FeedbackControlLoop(StubDispatcher())
        loop.run("task", dry_run=True)
        stats = loop.get_statistics()
        assert stats["iterations"] == 1
        assert "best_quality" in stats
        assert "converged" in stats
        assert len(stats["history"]) == 1

    def test_statistics_converged(self):
        good_result = StubResult(
            success=True,
            worker_results=[{"success": True}],
            consensus_records=[{"outcome": "APPROVED"}],
        )
        dispatcher = StubDispatcher(results=[good_result])
        loop = FeedbackControlLoop(dispatcher, quality_gate=0.3)
        loop.run("task")
        stats = loop.get_statistics()
        assert stats["converged"] is True
        assert stats["converged_at_iteration"] == 1

    def test_statistics_not_converged(self):
        bad_result = StubResult(success=False, worker_results=[], errors=["err"])
        dispatcher = StubDispatcher(results=[bad_result])
        loop = FeedbackControlLoop(dispatcher, quality_gate=0.95, max_iterations=1)
        loop.run("task")
        stats = loop.get_statistics()
        assert stats["converged"] is False
        assert stats["converged_at_iteration"] is None

    def test_statistics_includes_quality_metrics(self):
        bad_result = StubResult(success=False, worker_results=[], errors=["err"])
        good_result = StubResult(
            success=True,
            worker_results=[{"success": True}],
        )
        dispatcher = StubDispatcher(results=[bad_result, good_result])
        loop = FeedbackControlLoop(dispatcher, quality_gate=0.5, max_iterations=2)
        loop.run("task")
        stats = loop.get_statistics()
        assert "worst_quality" in stats
        assert "avg_quality" in stats
        assert stats["worst_quality"] <= stats["best_quality"]
