#!/usr/bin/env python3
"""FeedbackControlLoop + PerformanceFingerprint + SimilarTaskRecommender
+ AdaptiveRoleSelector + ExecutionGuard Integration Tests.

Integration tests for the feedback loop chain:
    FeedbackControlLoop (Sense-Decide-Act-Feedback closed loop)
    PerformanceFingerprint (TF-IDF similarity + execution recording)
    SimilarTaskRecommender (historical fingerprint-based recommendation)
    AdaptiveRoleSelector (success rate-driven role selection)
    ExecutionGuard (real-time execution monitoring + abort)

Flow:
    1. FeedbackControlLoop.run() → dispatcher.dispatch() → _assess_quality()
       → _generate_adjustment() → _refine_task() → iterate
    2. PerformanceFingerprint.record_execution() → persist → find_similar() (TF-IDF)
    3. SimilarTaskRecommender.recommend() → fingerprint.find_similar() → extract roles/intent
    4. AdaptiveRoleSelector.select_roles() → fingerprint.find_similar() → success rate filter
    5. ExecutionGuard.check_abort() → timeout/keyword/token/size detection

References:
    - scripts/collaboration/feedback_control_loop.py
    - scripts/collaboration/performance_fingerprint.py
    - scripts/collaboration/similar_task_recommender.py
    - scripts/collaboration/adaptive_role_selector.py
    - scripts/collaboration/execution_guard.py
    - scripts/collaboration/dispatch_models.py (DispatchResult)
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import threading
import unittest
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.adaptive_role_selector import AdaptiveRoleSelector
from scripts.collaboration.dispatch_models import DispatchResult
from scripts.collaboration.execution_guard import (
    ExecutionGuard,
)
from scripts.collaboration.feedback_control_loop import FeedbackControlLoop
from scripts.collaboration.performance_fingerprint import PerformanceFingerprint
from scripts.collaboration.similar_task_recommender import SimilarTaskRecommender

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeDispatcher:
    """Dispatcher that returns scripted DispatchResult sequences.

    Mirrors the pattern from tests/test_feedback_control_loop.py but lives
    inline so this integration test file is self-contained.
    """

    def __init__(self, results: list[DispatchResult] | None = None) -> None:
        self._results = results or []
        self._index = 0
        self._call_count = 0
        self.received_tasks: list[str] = []
        self.received_roles: list[list[str] | None] = []
        self.received_modes: list[str] = []

    def dispatch(
        self, task: str, roles: list[str] | None = None, mode: str = "auto", **_kwargs: Any
    ) -> DispatchResult:
        self._call_count += 1
        self.received_tasks.append(task)
        self.received_roles.append(roles)
        self.received_modes.append(mode)
        if self._index < len(self._results):
            result = self._results[self._index]
            self._index += 1
            return result
        if self._results:
            return self._results[-1]
        return DispatchResult(success=True, task_description=task, summary="default")

    @property
    def call_count(self) -> int:
        return self._call_count


class _FakeLLMBackend:
    """Minimal fake LLM backend for FeedbackControlLoop._llm_refine_task()."""

    def __init__(self, response: str = "Refined task with clearer objectives and constraints") -> None:
        self._response = response
        self.call_count = 0
        self.received_prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.call_count += 1
        self.received_prompts.append(prompt)
        return self._response


def _make_result(
    success: bool = True,
    worker_results: list[dict[str, Any]] | None = None,
    consensus_records: list[dict[str, Any]] | None = None,
    errors: list[str] | None = None,
    summary: str = "ok",
    task_description: str = "test task",
) -> DispatchResult:
    """Build a DispatchResult with sensible defaults for quality scoring."""
    return DispatchResult(
        success=success,
        task_description=task_description,
        summary=summary,
        worker_results=worker_results or [],
        consensus_records=consensus_records or [],
        errors=errors or [],
        duration_seconds=0.1,
    )


def _make_result_with_error_attrs(
    success: bool = False,
    error_message: str = "timeout exceeded",
    error_type: str = "TimeoutError",
    task_description: str = "test task",
) -> DispatchResult:
    """Build a failed DispatchResult carrying error_message/error_type attrs.

    PerformanceFingerprint._extract_error_patterns reads these attributes via
    getattr, so they must be set on the dataclass instance.
    """
    result = DispatchResult(
        success=success,
        task_description=task_description,
        summary="failed",
        errors=[error_message],
        duration_seconds=0.1,
    )
    object.__setattr__(result, "error_message", error_message)
    object.__setattr__(result, "error_type", error_type)
    return result


# ---------------------------------------------------------------------------
# T1: FeedbackControlLoop closed-loop iteration integration
# ---------------------------------------------------------------------------


class T1_FeedbackControlLoopIntegration(unittest.TestCase):
    """Tests covering the Sense-Decide-Act-Feedback closed loop."""

    def test_01_loop_passes_on_first_iteration_when_quality_meets_gate(self) -> None:
        """Verify: high-quality result exits loop after 1 iteration.

        Quality scoring: success(0.4) + worker_ratio(0.3) + consensus_ratio(0.2) = 0.9.
        Gate 0.5 is met immediately, so only 1 dispatch call is made.
        """
        result = _make_result(
            success=True,
            worker_results=[{"role_id": "architect", "success": True}],
            consensus_records=[{"outcome": "APPROVED"}],
        )
        dispatcher = _FakeDispatcher([result])
        loop = FeedbackControlLoop(dispatcher, quality_gate=0.5, max_iterations=3)

        best = loop.run("design API")

        self.assertEqual(loop.iteration_count, 1)
        self.assertIs(best, result)
        self.assertGreaterEqual(loop.best_quality, 0.5)
        self.assertEqual(dispatcher.call_count, 1)

    def test_02_loop_iterates_then_passes_when_quality_improves(self) -> None:
        """Verify: first iteration fails gate, second passes → early exit.

        First result: success=False, failed worker → low quality.
        Second result: success=True, approved consensus → quality meets gate.
        """
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
        dispatcher = _FakeDispatcher([low_quality, high_quality])
        loop = FeedbackControlLoop(dispatcher, quality_gate=0.5, max_iterations=3)

        best = loop.run("implement feature")

        self.assertEqual(loop.iteration_count, 2)
        self.assertIs(best, high_quality)
        self.assertEqual(dispatcher.call_count, 2)
        stats = loop.get_statistics()
        self.assertTrue(stats["converged"])
        self.assertEqual(stats["converged_at_iteration"], 2)

    def test_03_loop_exhausts_max_iterations_when_quality_never_passes(self) -> None:
        """Verify: never-meeting gate → loop runs max_iterations + 1 times.

        max_iterations=2 means range(3) → iterations 1, 2, 3.
        Each returns a failed result → loop exhausts all attempts.
        """
        failed = _make_result(
            success=False,
            worker_results=[{"role_id": "coder", "success": False, "error": "error"}],
            errors=["persistent failure"],
        )
        dispatcher = _FakeDispatcher([failed, failed, failed])
        loop = FeedbackControlLoop(dispatcher, quality_gate=0.8, max_iterations=2)

        loop.run("impossible task")

        self.assertEqual(loop.iteration_count, 3)
        self.assertEqual(dispatcher.call_count, 3)
        stats = loop.get_statistics()
        self.assertFalse(stats["converged"])
        self.assertIsNone(stats["converged_at_iteration"])

    def test_04_loop_dry_run_mode_skips_actual_dispatch(self) -> None:
        """Verify: dry_run=True uses _dry_run_dispatch, never calls dispatcher.

        Dry-run produces a DispatchResult with summary "[DRY RUN] ..." and
        exits after 1 iteration (no refinement needed).
        """
        dispatcher = _FakeDispatcher([])
        loop = FeedbackControlLoop(dispatcher, quality_gate=0.7, max_iterations=3)

        result = loop.run("plan a task", dry_run=True)

        self.assertEqual(dispatcher.call_count, 0)
        self.assertEqual(loop.iteration_count, 1)
        self.assertTrue(result.success)
        self.assertIn("[DRY RUN]", result.summary)

    def test_05_loop_with_llm_backend_refines_task_intelligently(self) -> None:
        """Verify: LLM backend generate() is called for task refinement.

        First iteration fails → _refine_task calls _llm_refine_task which
        invokes backend.generate(prompt). The refined task is sent to the
        second dispatch call.
        """
        failed = _make_result(
            success=False,
            worker_results=[{"role_id": "coder", "success": False, "error": "bug"}],
            errors=["timeout"],
        )
        passed = _make_result(
            success=True,
            worker_results=[{"role_id": "coder", "success": True}],
            consensus_records=[{"outcome": "APPROVED"}],
        )
        dispatcher = _FakeDispatcher([failed, passed])
        llm = _FakeLLMBackend("Refined: add explicit error handling and retry logic")
        loop = FeedbackControlLoop(dispatcher, quality_gate=0.5, max_iterations=2, llm_backend=llm)

        loop.run("build feature")

        self.assertEqual(llm.call_count, 1)
        self.assertEqual(dispatcher.call_count, 2)
        self.assertIn("Refined:", dispatcher.received_tasks[1])


# ---------------------------------------------------------------------------
# T2: PerformanceFingerprint TF-IDF similarity + recording integration
# ---------------------------------------------------------------------------


class T2_PerformanceFingerprintIntegration(unittest.TestCase):
    """Tests covering fingerprint recording, persistence, and TF-IDF search."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.mkdtemp(prefix="fp_integ_")
        self.fp = PerformanceFingerprint(persist_dir=self._tmpdir)

    def tearDown(self) -> None:
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_01_record_execution_then_find_similar_returns_matching_task(self) -> None:
        """Verify: record_execution → find_similar returns the recorded task.

        TF-IDF similarity between "implement user authentication" and
        "implement user login" should be > 0 due to shared tokens
        (implement, user).
        """
        result = _make_result(success=True)
        self.fp.record_execution(
            task="implement user authentication",
            result=result,
            timing={"total": 10.0, "coding": 8.0},
            roles_used=["architect", "coder"],
            intent="feature_implementation",
        )

        similar = self.fp.find_similar("implement user login", top_k=3)

        self.assertEqual(len(similar), 1)
        self.assertGreater(similar[0]["similarity"], 0.0)
        self.assertEqual(similar[0]["task"], "implement user authentication")

    def test_02_find_similar_returns_empty_on_cold_start(self) -> None:
        """Verify: empty fingerprint database → find_similar returns []."""
        similar = self.fp.find_similar("any task", top_k=3)
        self.assertEqual(similar, [])
        self.assertEqual(self.fp.get_fingerprint_count(), 0)

    def test_03_tfidf_similarity_returns_high_score_for_identical_tasks(self) -> None:
        """Verify: identical task text → similarity == 1.0 (cosine of same vector)."""
        result = _make_result(success=True)
        self.fp.record_execution(
            task="design secure api gateway",
            result=result,
            timing={"total": 5.0},
            roles_used=["architect"],
        )

        similar = self.fp.find_similar("design secure api gateway", top_k=1)

        self.assertEqual(len(similar), 1)
        self.assertAlmostEqual(similar[0]["similarity"], 1.0, places=3)

    def test_04_tfidf_similarity_returns_zero_for_unrelated_tasks(self) -> None:
        """Verify: no shared tokens → similarity == 0.0 → excluded from results.

        "authentication security" vs "deploy database server" share no
        English tokens; find_similar filters out sim==0 entries.
        """
        result = _make_result(success=True)
        self.fp.record_execution(
            task="authentication security login",
            result=result,
            timing={"total": 5.0},
            roles_used=["security"],
        )

        similar = self.fp.find_similar("deploy database server", top_k=3)

        self.assertEqual(similar, [])

    def test_05_get_stats_reports_correct_metrics_after_multiple_records(self) -> None:
        """Verify: get_stats aggregates total, success_rate, top_roles, top_intents."""
        for i in range(3):
            self.fp.record_execution(
                task=f"implement feature number {i}",
                result=_make_result(success=(i < 2)),
                timing={"total": float(10 + i)},
                roles_used=["architect", "coder"],
                intent="feature_implementation",
            )

        stats = self.fp.get_stats()

        self.assertEqual(stats["total"], 3)
        self.assertAlmostEqual(stats["success_rate"], 0.6667, places=3)
        self.assertEqual(stats["failure_count"], 1)
        self.assertGreaterEqual(stats["avg_duration"], 10.0)
        self.assertEqual(len(stats["top_roles"]), 2)
        self.assertEqual(stats["top_intents"][0]["intent"], "feature_implementation")


# ---------------------------------------------------------------------------
# T3: SimilarTaskRecommender integration with PerformanceFingerprint
# ---------------------------------------------------------------------------


class T3_SimilarTaskRecommenderIntegration(unittest.TestCase):
    """Tests covering SimilarTaskRecommender ↔ PerformanceFingerprint integration."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.mkdtemp(prefix="rec_integ_")
        self.fp = PerformanceFingerprint(persist_dir=self._tmpdir)
        self.recommender = SimilarTaskRecommender(self.fp)

    def tearDown(self) -> None:
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_01_recommend_returns_roles_from_successful_similar_tasks(self) -> None:
        """Verify: recommend() extracts roles from successful similar cases.

        Record a successful execution with [architect, coder], then query a
        similar task. recommended_roles should include both roles.
        """
        self.fp.record_execution(
            task="implement user authentication system",
            result=_make_result(success=True),
            timing={"total": 12.0},
            roles_used=["architect", "coder"],
            intent="feature_implementation",
        )

        result = self.recommender.recommend("implement user login system", top_k=3)

        self.assertGreater(len(result["similar_cases"]), 0)
        self.assertIn("architect", result["recommended_roles"])
        self.assertIn("coder", result["recommended_roles"])
        self.assertEqual(result["recommended_intent"], "feature_implementation")

    def test_02_recommend_returns_low_confidence_on_cold_start(self) -> None:
        """Verify: no historical data → confidence="low", empty recommendations."""
        result = self.recommender.recommend("brand new task", top_k=3)

        self.assertEqual(result["similar_cases"], [])
        self.assertEqual(result["recommended_roles"], [])
        self.assertIsNone(result["recommended_intent"])
        self.assertEqual(result["confidence"], "low")
        self.assertEqual(result["estimated_duration_s"], 0.0)

    def test_03_recommend_extracts_most_common_intent_from_successful_cases(self) -> None:
        """Verify: intent is the most common among successful similar cases.

        Record 2 successful cases with intent="bug_fix" and 1 with
        intent="feature_implementation". recommend() should return "bug_fix"
        as the most common intent.
        """
        for _ in range(2):
            self.fp.record_execution(
                task="fix authentication bug in login",
                result=_make_result(success=True),
                timing={"total": 5.0},
                roles_used=["coder"],
                intent="bug_fix",
            )
        self.fp.record_execution(
            task="fix authentication bug in login",
            result=_make_result(success=True),
            timing={"total": 5.0},
            roles_used=["coder"],
            intent="feature_implementation",
        )

        result = self.recommender.recommend("fix authentication bug in login", top_k=5)

        self.assertEqual(result["recommended_intent"], "bug_fix")

    def test_04_recommend_estimates_duration_from_historical_data(self) -> None:
        """Verify: estimated_duration_s is the average of successful case durations."""
        for duration in (10.0, 20.0, 30.0):
            self.fp.record_execution(
                task="implement data export feature",
                result=_make_result(success=True),
                timing={"total": duration},
                roles_used=["coder"],
                intent="feature_implementation",
            )

        result = self.recommender.recommend("implement data export feature", top_k=3)

        self.assertGreater(result["estimated_duration_s"], 0)
        avg = (10.0 + 20.0 + 30.0) / 3
        self.assertAlmostEqual(result["estimated_duration_s"], round(avg, 2), places=1)


# ---------------------------------------------------------------------------
# T4: AdaptiveRoleSelector success rate-driven selection integration
# ---------------------------------------------------------------------------


class T4_AdaptiveRoleSelectorIntegration(unittest.TestCase):
    """Tests covering AdaptiveRoleSelector ↔ PerformanceFingerprint integration."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.mkdtemp(prefix="sel_integ_")
        self.fp = PerformanceFingerprint(persist_dir=self._tmpdir)
        self.selector = AdaptiveRoleSelector(self.fp)

    def tearDown(self) -> None:
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_01_select_roles_returns_roles_from_similar_successful_tasks(self) -> None:
        """Verify: select_roles uses similar task history with success rate filter.

        Record a successful [architect, coder] execution for a task, then
        select_roles for a similar task should return those roles.
        """
        self.fp.record_execution(
            task="implement user authentication",
            result=_make_result(success=True),
            timing={"total": 10.0},
            roles_used=["architect", "coder"],
            intent="feature_implementation",
        )

        roles = self.selector.select_roles("implement user login", min_success_rate=0.5)

        self.assertGreater(len(roles), 0)
        self.assertIn("architect", roles)
        self.assertIn("coder", roles)

    def test_02_select_roles_falls_back_to_intent_when_no_similar_tasks(self) -> None:
        """Verify: no similar tasks → intent-based selection kicks in.

        Record a task with intent="bug_fix", then query a dissimilar task
        with the same intent. Intent-based fallback should find roles.
        """
        self.fp.record_execution(
            task="fix memory leak in parser",
            result=_make_result(success=True),
            timing={"total": 8.0},
            roles_used=["coder", "tester"],
            intent="bug_fix",
        )

        roles = self.selector.select_roles(
            "deploy database server cluster",
            intent="bug_fix",
            min_success_rate=0.5,
        )

        self.assertGreater(len(roles), 0)
        self.assertIn("coder", roles)

    def test_03_select_roles_returns_empty_when_no_data_available(self) -> None:
        """Verify: cold start (no fingerprints, no intent) → empty list (fallback)."""
        roles = self.selector.select_roles("any task", intent=None, min_success_rate=0.5)
        self.assertEqual(roles, [])

    def test_04_get_role_report_combines_manual_and_fingerprint_stats(self) -> None:
        """Verify: get_role_report merges manual update_stats + fingerprint data.

        Manual stats: update_stats(["reviewer"], True, 5.0).
        Fingerprint: record_execution with ["architect", "coder"].
        Report should include both "reviewer" (manual) and "architect"/"coder" (fingerprint).
        """
        self.selector.update_stats(["reviewer"], True, 5.0)
        self.fp.record_execution(
            task="implement feature",
            result=_make_result(success=True),
            timing={"total": 10.0},
            roles_used=["architect", "coder"],
            intent="feature_implementation",
        )

        report = self.selector.get_role_report()

        self.assertIn("reviewer", report)
        self.assertEqual(report["reviewer"]["total"], 1)
        self.assertEqual(report["reviewer"]["successes"], 1)
        self.assertIn("architect", report)
        self.assertIn("coder", report)


# ---------------------------------------------------------------------------
# T5: ExecutionGuard real-time monitoring + abort integration
# ---------------------------------------------------------------------------


class T5_ExecutionGuardIntegration(unittest.TestCase):
    """Tests covering ExecutionGuard abort conditions and configuration."""

    def test_01_check_abort_triggers_on_timeout(self) -> None:
        """Verify: elapsed_time > max_duration_sec → abort with timeout reason."""
        guard = ExecutionGuard(max_duration_sec=10.0)
        abort, reason = guard.check_abort("normal output", elapsed_time=15.0)
        self.assertTrue(abort)
        self.assertIn("Timeout", reason)

    def test_02_check_abort_triggers_on_critical_keywords(self) -> None:
        """Verify: critical keyword in output → abort with keyword reason.

        "FATAL ERROR" is in the default abort_keywords list.
        """
        guard = ExecutionGuard(max_duration_sec=300.0)
        abort, reason = guard.check_abort("Process crashed: FATAL ERROR", elapsed_time=5.0)
        self.assertTrue(abort)
        self.assertIn("Critical keywords", reason)
        self.assertIn("FATAL", reason)

    def test_03_check_abort_returns_false_for_normal_output(self) -> None:
        """Verify: normal output within thresholds → no abort."""
        guard = ExecutionGuard(max_duration_sec=300.0, max_output_tokens=8000)
        abort, reason = guard.check_abort("Task completed successfully", elapsed_time=10.0, token_count=100)
        self.assertFalse(abort)
        self.assertEqual(reason, "")
        self.assertEqual(guard.check_count, 1)
        self.assertEqual(guard.abort_count, 0)

    def test_04_configure_adjusts_threshold_dynamically(self) -> None:
        """Verify: configure() updates trigger threshold at runtime.

        Initial max_duration=300 → 100s does not trigger.
        After configure("max_duration_sec", 50) → 100s triggers abort.
        """
        guard = ExecutionGuard(max_duration_sec=300.0)
        abort_before, _ = guard.check_abort("ok", elapsed_time=100.0)
        self.assertFalse(abort_before)

        guard.configure("max_duration_sec", 50.0)
        abort_after, reason_after = guard.check_abort("ok", elapsed_time=100.0)
        self.assertTrue(abort_after)
        self.assertIn("Timeout", reason_after)

    def test_05_check_abort_triggers_on_output_size_overflow(self) -> None:
        """Verify: output length > max_output_length → abort with size reason.

        Default max_output_length=50000. Generate 50001 chars → abort.
        """
        guard = ExecutionGuard(max_duration_sec=300.0)
        large_output = "x" * 50001
        abort, reason = guard.check_abort(large_output, elapsed_time=5.0)
        self.assertTrue(abort)
        self.assertIn("Output too large", reason)

    def test_06_estimate_token_count_and_check_warnings(self) -> None:
        """Verify: estimate_token_count uses ratio; check_warnings finds WARNING.

        token_estimate_ratio=4.0 → 40 chars ≈ 10 tokens.
        "WARNING: high memory" contains "WARNING" → check_warnings returns it.
        """
        guard = ExecutionGuard()
        tokens = guard.estimate_token_count("a" * 40)
        self.assertEqual(tokens, 10)

        warnings = guard.check_warnings("WARNING: high memory usage")
        self.assertIn("WARNING", warnings)


# ---------------------------------------------------------------------------
# T6: End-to-end + Boundary/Edge cases integration
# ---------------------------------------------------------------------------


class T6_EndToEndAndBoundaryIntegration(unittest.TestCase):
    """End-to-end pipeline + boundary condition tests."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.mkdtemp(prefix="e2e_integ_")

    def tearDown(self) -> None:
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_01_end_to_end_fingerprint_to_recommender_to_selector_pipeline(self) -> None:
        """Verify: record → find_similar → recommend → select_roles pipeline.

        Full pipeline:
        1. Record 2 successful executions with [architect, coder]
        2. SimilarTaskRecommender.recommend() returns roles + intent
        3. AdaptiveRoleSelector.select_roles() returns roles
        4. Both should agree on the role combination
        """
        fp = PerformanceFingerprint(persist_dir=self._tmpdir)
        for _ in range(2):
            fp.record_execution(
                task="implement user authentication module",
                result=_make_result(success=True),
                timing={"total": 12.0},
                roles_used=["architect", "coder"],
                intent="feature_implementation",
            )

        recommender = SimilarTaskRecommender(fp)
        selector = AdaptiveRoleSelector(fp)

        rec_result = recommender.recommend("implement user login module", top_k=3)
        selected_roles = selector.select_roles("implement user login module", min_success_rate=0.5)

        self.assertGreater(len(rec_result["recommended_roles"]), 0)
        self.assertGreater(len(selected_roles), 0)
        for role in rec_result["recommended_roles"]:
            self.assertIn(role, selected_roles)

    def test_02_concurrent_record_execution_is_thread_safe(self) -> None:
        """Verify: concurrent record_execution calls don't corrupt fingerprints.

        Spawn 5 threads each recording 4 fingerprints. Final count should be
        exactly 20 (thread-safe append under RLock).
        """
        fp = PerformanceFingerprint(persist_dir=self._tmpdir)

        def writer(thread_id: int) -> None:
            for i in range(4):
                fp.record_execution(
                    task=f"task from thread {thread_id} item {i}",
                    result=_make_result(success=True),
                    timing={"total": 1.0},
                    roles_used=["coder"],
                    intent="test",
                )

        threads = [threading.Thread(target=writer, args=(t,)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(fp.get_fingerprint_count(), 20)

    def test_03_execution_guard_aborts_long_running_loop_iteration(self) -> None:
        """Verify: ExecutionGuard detects timeout in simulated loop output.

        Simulate a loop iteration that produces FATAL in output → guard
        triggers abort, which would stop the loop in a real integration.
        """
        guard = ExecutionGuard(max_duration_sec=300.0)
        simulated_output = "Processing... FATAL ERROR: out of memory"
        abort, reason = guard.check_abort(simulated_output, elapsed_time=5.0)

        self.assertTrue(abort)
        self.assertIn("FATAL", reason)
        self.assertEqual(guard.abort_count, 1)

        stats = guard.get_stats()
        self.assertEqual(stats["check_count"], 1)
        self.assertEqual(stats["abort_count"], 1)
        self.assertGreater(stats["abort_rate"], 0.0)

    def test_04_empty_task_and_empty_output_handled_gracefully(self) -> None:
        """Verify: empty task text and empty output don't crash any module.

        - PerformanceFingerprint.find_similar("") → [] (no tokens)
        - SimilarTaskRecommender.recommend("") → low confidence
        - AdaptiveRoleSelector.select_roles("") → []
        - ExecutionGuard.check_abort("", 0.0) → no abort
        """
        fp = PerformanceFingerprint(persist_dir=self._tmpdir)
        self.assertEqual(fp.find_similar(""), [])

        recommender = SimilarTaskRecommender(fp)
        rec = recommender.recommend("")
        self.assertEqual(rec["confidence"], "low")
        self.assertEqual(rec["recommended_roles"], [])

        selector = AdaptiveRoleSelector(fp)
        self.assertEqual(selector.select_roles(""), [])

        guard = ExecutionGuard(max_duration_sec=300.0)
        abort, reason = guard.check_abort("", elapsed_time=0.0)
        self.assertFalse(abort)
        self.assertEqual(reason, "")

    def test_05_feedback_loop_reset_clears_iteration_history(self) -> None:
        """Verify: reset() clears history, best_result, best_quality, count.

        Run a loop that produces 2 iterations, then reset() → all state
        returns to initial values.
        """
        failed = _make_result(
            success=False,
            worker_results=[{"role_id": "coder", "success": False, "error": "err"}],
            errors=["err"],
        )
        dispatcher = _FakeDispatcher([failed, failed, failed])
        loop = FeedbackControlLoop(dispatcher, quality_gate=0.9, max_iterations=2)
        loop.run("task")

        self.assertEqual(loop.iteration_count, 3)
        self.assertGreater(len(loop.iteration_history), 0)

        loop.reset()

        self.assertEqual(loop.iteration_count, 0)
        self.assertEqual(loop.iteration_history, [])
        self.assertIsNone(loop.best_result)
        self.assertEqual(loop.best_quality, 0.0)


if __name__ == "__main__":
    unittest.main()
