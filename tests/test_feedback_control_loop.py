"""E2E closed-loop tests for FeedbackControlLoop (P1-B).

Tests the full Sense-Decide-Act-Feedback iteration cycle with:
- FakeDispatcher returning configurable DispatchResult sequences
- FakeLLMBackend for intelligent refinement path
- Quality gate scenarios: pass-first, improve-then-pass, never-pass
- Dry-run mode, thread safety, iteration history tracking
"""

import threading
from typing import Any

from scripts.collaboration.dispatch_models import DispatchResult
from scripts.collaboration.feedback_control_loop import FeedbackControlLoop


class FakeDispatcher:
    """Dispatcher that returns scripted results in sequence."""

    def __init__(self, results: list[DispatchResult] | None = None):
        self._results = results or []
        self._index = 0
        self._call_count = 0
        self._received_tasks: list[str] = []
        self._received_roles: list[list[str] | None] = []
        self._received_modes: list[str] = []

    def dispatch(self, task: str, roles: list[str] | None = None, mode: str = "auto", **_kwargs: Any) -> DispatchResult:
        self._call_count += 1
        self._received_tasks.append(task)
        self._received_roles.append(roles)
        self._received_modes.append(mode)

        if self._index < len(self._results):
            result = self._results[self._index]
            self._index += 1
            return result
        if self._results:
            return self._results[-1]
        return DispatchResult(success=True, task_description=task, summary="default")


class FakeLLMBackend:
    """LLM backend returning scripted responses for task refinement."""

    def __init__(self, responses: list[str] | None = None, default: str = "Refined task with clearer objectives"):
        self._responses = responses or []
        self._index = 0
        self._default = default
        self._call_count = 0
        self._received_prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self._call_count += 1
        self._received_prompts.append(prompt)
        if self._index < len(self._responses):
            resp = self._responses[self._index]
            self._index += 1
            return resp
        return self._default


def _make_result(
    success: bool = True,
    worker_results: list[dict[str, Any]] | None = None,
    consensus_records: list[dict[str, Any]] | None = None,
    errors: list[str] | None = None,
    summary: str = "ok",
) -> DispatchResult:
    """Helper to build a DispatchResult with sensible defaults."""
    return DispatchResult(
        success=success,
        task_description="test",
        summary=summary,
        worker_results=worker_results or [],
        consensus_records=consensus_records or [],
        errors=errors or [],
        duration_seconds=0.1,
    )


# ============================================================================
# E2E: Quality Gate Scenarios
# ============================================================================


class TestFeedbackLoopQualityGate:
    """Tests covering quality gate pass/fail/early-exit scenarios."""

    def test_pass_on_first_iteration(self):
        """Quality gate met immediately — loop exits after 1 iteration."""
        result = _make_result(
            success=True,
            worker_results=[{"role_id": "architect", "success": True}],
            consensus_records=[{"outcome": "APPROVED"}],
        )
        dispatcher = FakeDispatcher([result])
        loop = FeedbackControlLoop(dispatcher, quality_gate=0.5, max_iterations=3)

        best = loop.run("design API")

        assert loop.iteration_count == 1
        assert best is result
        assert loop.best_quality >= 0.5
        assert dispatcher._call_count == 1

    def test_improve_then_pass(self):
        """First iteration fails gate, second passes — loop exits early."""
        low_quality = _make_result(
            success=False,
            worker_results=[{"role_id": "coder", "success": False, "error": "timeout"}],
            errors=["worker timeout"],
        )
        high_quality = _make_result(
            success=True,
            worker_results=[{"role_id": "coder", "success": True}],
            consensus_records=[{"outcome": "APPROVED"}],
        )
        dispatcher = FakeDispatcher([low_quality, high_quality])
        loop = FeedbackControlLoop(dispatcher, quality_gate=0.6, max_iterations=3)

        best = loop.run("implement feature")

        assert loop.iteration_count == 2
        assert best is high_quality
        assert loop.best_quality >= 0.6
        assert len(loop.iteration_history) == 2
        assert loop.iteration_history[0]["passed"] is False
        assert loop.iteration_history[1]["passed"] is True

    def test_never_passes_returns_best(self):
        """Quality never meets gate — returns best (highest score) result."""
        r1 = _make_result(
            success=False,
            worker_results=[{"role_id": "a", "success": False, "error": "err"}],
            errors=["e1"],
        )
        r2 = _make_result(
            success=True,
            worker_results=[{"role_id": "a", "success": True}, {"role_id": "b", "success": False, "error": "x"}],
        )
        r3 = _make_result(
            success=False,
            worker_results=[{"role_id": "a", "success": False, "error": "y"}],
            errors=["e2", "e3"],
        )
        dispatcher = FakeDispatcher([r1, r2, r3])
        loop = FeedbackControlLoop(dispatcher, quality_gate=0.95, max_iterations=3)

        best = loop.run("hard task")

        assert loop.iteration_count == 4  # max_iterations + 1
        assert best is r2  # r2 has highest quality (success + partial workers)
        assert len(loop.iteration_history) == 4
        assert all(not h["passed"] for h in loop.iteration_history)

    def test_zero_quality_when_result_is_none(self):
        """None result yields quality 0.0."""
        dispatcher = FakeDispatcher([])
        # Empty FakeDispatcher returns default success result, so test None explicitly
        loop = FeedbackControlLoop(dispatcher, quality_gate=0.99, max_iterations=1)
        # Force None result via _assess_quality direct call
        quality = loop._assess_quality(None)
        assert quality == 0.0


# ============================================================================
# E2E: Dry Run Mode
# ============================================================================


class TestFeedbackLoopDryRun:
    """Tests for dry-run mode (simulation without actual dispatch)."""

    def test_dry_run_returns_result_without_dispatch(self):
        dispatcher = FakeDispatcher([])
        loop = FeedbackControlLoop(dispatcher, quality_gate=0.9, max_iterations=3)

        result = loop.run("simulate task", dry_run=True)

        assert result is not None
        assert result.success is True
        assert "DRY RUN" in result.summary
        assert dispatcher._call_count == 0
        assert loop.iteration_count == 1

    def test_dry_run_history_recorded(self):
        dispatcher = FakeDispatcher([])
        loop = FeedbackControlLoop(dispatcher, quality_gate=0.5, max_iterations=2)

        loop.run("simulate", dry_run=True)

        assert len(loop.iteration_history) == 1
        record = loop.iteration_history[0]
        assert "iteration" in record
        assert "quality" in record
        assert "passed" in record
        assert "task_preview" in record
        assert "timestamp" in record


# ============================================================================
# E2E: LLM-Assisted Refinement
# ============================================================================


class TestFeedbackLoopLLMRefinement:
    """Tests for LLM-assisted task refinement path."""

    def test_llm_refinement_invoked_on_failure(self):
        low_quality = _make_result(
            success=False,
            worker_results=[{"role_id": "coder", "success": False, "error": "timeout"}],
            errors=["timeout"],
        )
        high_quality = _make_result(
            success=True,
            worker_results=[{"role_id": "coder", "success": True}],
        )
        dispatcher = FakeDispatcher([low_quality, high_quality])
        llm = FakeLLMBackend(default="Refined: break task into smaller steps")
        loop = FeedbackControlLoop(dispatcher, quality_gate=0.6, max_iterations=3, llm_backend=llm)

        loop.run("implement complex feature")

        assert llm._call_count == 1
        assert len(llm._received_prompts) == 1
        assert "implement complex feature" in llm._received_prompts[0]
        # Second task should be the LLM-refined version
        assert dispatcher._received_tasks[1] == "Refined: break task into smaller steps"

    def test_llm_failure_falls_back_to_concat(self):
        """LLM raising exception falls back to algorithmic concatenation."""

        class FailingLLM:
            def generate(self, _prompt: str) -> str:
                raise RuntimeError("LLM unavailable")

        low_quality = _make_result(
            success=False,
            worker_results=[{"role_id": "a", "success": False, "error": "x"}],
            errors=["e1"],
        )
        high_quality = _make_result(success=True, worker_results=[{"role_id": "a", "success": True}])
        dispatcher = FakeDispatcher([low_quality, high_quality])
        loop = FeedbackControlLoop(dispatcher, quality_gate=0.6, max_iterations=2, llm_backend=FailingLLM())

        loop.run("test task")

        # Second task should contain adjustment (not LLM response)
        assert "test task" in dispatcher._received_tasks[1]
        # Should have appended adjustment rather than LLM default
        assert len(dispatcher._received_tasks[1]) > len("test task")

    def test_llm_returns_empty_string_falls_back(self):
        """LLM returning empty/short response falls back to concatenation."""
        low_quality = _make_result(success=False, errors=["e1"])
        high_quality = _make_result(success=True, worker_results=[{"role_id": "a", "success": True}])
        dispatcher = FakeDispatcher([low_quality, high_quality])
        llm = FakeLLMBackend(default="short")  # < 10 chars, triggers fallback
        loop = FeedbackControlLoop(dispatcher, quality_gate=0.6, max_iterations=2, llm_backend=llm)

        loop.run("original task")

        # Should fall back to concatenation, not use "short"
        assert "original task" in dispatcher._received_tasks[1]


# ============================================================================
# E2E: Iteration History & Best Result Tracking
# ============================================================================


class TestFeedbackLoopHistory:
    """Tests for iteration_history and best_result tracking."""

    def test_history_cleared_between_runs(self):
        r1 = _make_result(success=True, worker_results=[{"role_id": "a", "success": True}])
        dispatcher = FakeDispatcher([r1, r1])
        loop = FeedbackControlLoop(dispatcher, quality_gate=0.5, max_iterations=2)

        loop.run("first run")
        assert len(loop.iteration_history) == 1

        loop.run("second run")
        assert len(loop.iteration_history) == 1  # cleared, not accumulated

    def test_best_result_updated_each_iteration(self):
        r1 = _make_result(success=False, errors=["e1"])
        r2 = _make_result(success=True, worker_results=[{"role_id": "a", "success": True}])
        r3 = _make_result(
            success=True,
            worker_results=[{"role_id": "a", "success": True}, {"role_id": "b", "success": True}],
            consensus_records=[{"outcome": "APPROVED"}],
        )
        dispatcher = FakeDispatcher([r1, r2, r3])
        loop = FeedbackControlLoop(dispatcher, quality_gate=0.95, max_iterations=3)

        loop.run("track best")

        # r3 should be best (success + full workers + consensus)
        assert loop.best_result is r3
        assert loop.best_quality >= 0.8

    def test_history_contains_adjustment_when_refining(self):
        low = _make_result(success=False, errors=["timeout"])
        high = _make_result(success=True, worker_results=[{"role_id": "a", "success": True}])
        dispatcher = FakeDispatcher([low, high])
        loop = FeedbackControlLoop(dispatcher, quality_gate=0.6, max_iterations=2)

        loop.run("needs refinement")

        first_record = loop.iteration_history[0]
        assert "adjustment" in first_record
        assert "refined_task" in first_record
        assert "needs refinement" in first_record["task_preview"]


# ============================================================================
# E2E: Thread Safety
# ============================================================================


class TestFeedbackLoopThreadSafety:
    """Tests for RLock-based thread safety."""

    def test_concurrent_runs_serialized(self):
        """Concurrent run() calls are serialized by RLock — no corruption."""
        result = _make_result(success=True, worker_results=[{"role_id": "a", "success": True}])
        dispatcher = FakeDispatcher([result] * 10)
        loop = FeedbackControlLoop(dispatcher, quality_gate=0.5, max_iterations=1)

        errors: list[Exception] = []

        def worker():
            try:
                loop.run("concurrent task")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        # Each run resets history, so final history should have 1 entry
        assert len(loop.iteration_history) == 1


# ============================================================================
# E2E: Quality Assessment Subsystem
# ============================================================================


class TestAssessQuality:
    """Tests for _assess_quality with various DispatchResult shapes."""

    def setup_method(self):
        self.loop = FeedbackControlLoop(FakeDispatcher([]), quality_gate=0.5)

    def test_success_boosts_score(self):
        r = _make_result(success=True)
        q = self.loop._assess_quality(r)
        assert q >= 0.4  # success contributes 0.4

    def test_failure_lowers_success_component(self):
        r = _make_result(success=False)
        q = self.loop._assess_quality(r)
        assert q < 0.5  # failure contributes 0.3 (0.3*0.4=0.12 < 0.4)

    def test_worker_ratio_contributes(self):
        r = _make_result(
            success=True,
            worker_results=[
                {"role_id": "a", "success": True},
                {"role_id": "b", "success": True},
            ],
        )
        q = self.loop._assess_quality(r)
        assert q >= 0.7  # 0.4 (success) + 0.3 (full worker ratio)

    def test_partial_worker_ratio(self):
        r = _make_result(
            success=True,
            worker_results=[
                {"role_id": "a", "success": True},
                {"role_id": "b", "success": False},
            ],
        )
        q = self.loop._assess_quality(r)
        # 0.4 (success) + 0.15 (half worker ratio) = 0.55
        assert 0.5 <= q <= 0.65

    def test_consensus_approved_boosts(self):
        r = _make_result(
            success=True,
            consensus_records=[{"outcome": "APPROVED"}, {"outcome": "APPROVED"}],
        )
        q = self.loop._assess_quality(r)
        # 0.4 (success) + 0.1 (no workers) + 0.2 (full consensus) = 0.7
        assert q >= 0.7

    def test_errors_penalty(self):
        r = _make_result(success=True, errors=["e1", "e2", "e3"])
        q = self.loop._assess_quality(r)
        # 0.4 (success) + 0.1 (no workers) + 0.1 (no consensus) - 0.15 (3 errors) = 0.45
        assert q <= 0.5

    def test_score_clamped_to_0_1(self):
        r = _make_result(success=False, errors=["e"] * 100)
        q = self.loop._assess_quality(r)
        assert 0.0 <= q <= 1.0


# ============================================================================
# E2E: Adjustment Generation
# ============================================================================


class TestGenerateAdjustment:
    """Tests for _generate_adjustment failure analysis."""

    def setup_method(self):
        self.loop = FeedbackControlLoop(FakeDispatcher([]), quality_gate=0.5)

    def test_failed_worker_mentioned(self):
        r = _make_result(
            success=False,
            worker_results=[{"role_id": "coder", "success": False, "error": "fail"}],
        )
        adj = self.loop._generate_adjustment(r, 0.3)
        assert "coder" in adj

    def test_timeout_error_detected(self):
        r = _make_result(success=False, errors=["Operation timeout after 30s"])
        adj = self.loop._generate_adjustment(r, 0.3)
        assert "timeout" in adj.lower() or "complexity" in adj.lower()

    def test_permission_error_detected(self):
        r = _make_result(success=False, errors=["Permission denied for resource"])
        adj = self.loop._generate_adjustment(r, 0.3)
        assert "permission" in adj.lower()

    def test_no_workers_suggests_vague_task(self):
        r = _make_result(success=False, worker_results=[], errors=[])
        adj = self.loop._generate_adjustment(r, 0.3)
        assert "vague" in adj.lower() or "criteria" in adj.lower()

    def test_critical_quality_suggests_reformulation(self):
        r = _make_result(success=False, errors=["e1"])
        adj = self.loop._generate_adjustment(r, 0.2)
        assert "reformulation" in adj.lower() or "critical" in adj.lower()

    def test_no_specific_issue_gives_general_refinement(self):
        """When no specific failure pattern matches, general refinement is returned."""
        r = _make_result(
            success=True,
            worker_results=[{"role_id": "a", "success": True}],
            consensus_records=[{"outcome": "APPROVED"}],
            errors=[],
        )
        adj = self.loop._generate_adjustment(r, 0.65)
        assert len(adj) > 0  # always returns something
