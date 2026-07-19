#!/usr/bin/env python3
"""
V3.8 Integration Tests — Verify ghost features are wired into the dispatch pipeline.

These tests verify that the three "ghost feature" modules are actually called
during dispatch (not just unit-tested in isolation):

  1. JudgeAgent       — called during post-dispatch to consolidate findings
  2. ContentCache     — checked before LLM API calls in the worker path
  3. MicroTaskPlanner — decomposes tasks when use_micro_tasks=True
  4. All three work together in a full dispatch
  5. Backward compatibility — dispatch works without any V3.8 modules configured
"""

from __future__ import annotations

import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.content_cache import ContentCache
from scripts.collaboration.dispatcher import MultiAgentDispatcher
from scripts.collaboration.judge_agent import JudgeAgent
from scripts.collaboration.llm_backend import LLMBackend
from scripts.collaboration.llm_cache import LLMCache
from scripts.collaboration.micro_task_planner import MicroTaskPlanner
from scripts.collaboration.two_stage_review_gate import (
    ReviewFinding,
    ReviewStage,
    StageResult,
    TwoStageReviewResult,
)


class _FakeBackend(LLMBackend):
    """Non-Mock LLM backend that returns a canned response.

    Used to exercise the ContentCache code path (which is skipped when
    the backend is a MockBackend).
    """

    def __init__(self) -> None:
        self.call_count = 0

    def generate(self, _prompt: str, **_kwargs: object) -> str:
        self.call_count += 1
        return "fake LLM response for testing"

    def is_available(self) -> bool:
        return True


# ---------------------------------------------------------------------------
# Test 1: JudgeAgent is called during dispatch when configured
# ---------------------------------------------------------------------------


class TestJudgeAgentIntegration:
    """Verify JudgeAgent is invoked during the post-dispatch pipeline."""

    def test_judge_agent_called_when_findings_exist(self) -> None:
        """JudgeAgent.judge() is called when the two-stage review produces findings.

        The two-stage review gate does not produce findings for mock worker
        outputs, so we patch ``_run_two_stage_review`` to return a result with
        findings — this exercises the judge consolidation step (Step 23)
        that runs after the severity router.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            judge = JudgeAgent(confidence_threshold=0.0)
            judge_spy = MagicMock(wraps=judge.judge)
            judge.judge = judge_spy  # type: ignore[method-assign]

            disp = MultiAgentDispatcher(persist_dir=tmpdir, judge_agent=judge)

            # Craft a review result with findings so the judge has work to do.
            crafted_review = TwoStageReviewResult(
                stage1_result=StageResult.WARN,
                stage2_result=StageResult.WARN,
                findings=[
                    ReviewFinding(
                        ReviewStage.CODE_QUALITY,
                        "warning",
                        "security",
                        "Potential SQL injection in query builder",
                        file_path="src/db.py",
                        suggestion="Use parameterized queries",
                    ),
                    ReviewFinding(
                        ReviewStage.CODE_QUALITY,
                        "warning",
                        "security",
                        "Potential SQL injection in query builder",
                        file_path="src/db.py",
                        suggestion="Use parameterized queries",
                    ),
                ],
                overall_passed=True,
                summary="Two warnings found",
            )

            with patch.object(disp.post_dispatch, "_run_two_stage_review", return_value=crafted_review):
                result = disp.dispatch(
                    "Review the database layer for security issues",
                    roles=["solo-coder"],
                )

            # The judge should have been called with the findings.
            assert judge_spy.called, "JudgeAgent.judge() was not called during dispatch"
            assert result.judge_result is not None, "judge_result not populated on DispatchResult"
            assert "accepted_findings" in result.judge_result
            # Two duplicate findings → at least one should be merged/rejected.
            assert result.judge_result["rejected_count"] >= 1 or result.judge_result["merged_count"] >= 1
            disp.shutdown()

    def test_judge_agent_not_called_when_not_configured(self) -> None:
        """When no JudgeAgent is configured, judge_result stays None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            disp = MultiAgentDispatcher(persist_dir=tmpdir)
            result = disp.dispatch("Write a function", roles=["solo-coder"])
            assert result.judge_result is None
            assert disp.post_dispatch.judge_agent is None
            disp.shutdown()

    def test_judge_agent_wired_to_post_dispatch(self) -> None:
        """The judge_agent passed to the dispatcher reaches PostDispatchPipeline."""
        with tempfile.TemporaryDirectory() as tmpdir:
            judge = JudgeAgent()
            disp = MultiAgentDispatcher(persist_dir=tmpdir, judge_agent=judge)
            assert disp.post_dispatch.judge_agent is judge
            disp.shutdown()


# ---------------------------------------------------------------------------
# Test 2: ContentCache is checked before LLM calls when configured
# ---------------------------------------------------------------------------


class TestContentCacheIntegration:
    """Verify ContentCache is checked before LLM API calls in the worker path."""

    def test_content_cache_checked_before_llm_call(self) -> None:
        """When a ContentCache is configured, it is checked before the LLM backend.

        Uses a _FakeBackend (non-Mock) so the worker's cache-check code path
        is exercised. On the first call, the cache misses and the backend is
        called; the response is then stored in the ContentCache.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ContentCache(wrapped=LLMCache(cache_dir=tmpdir + "/cache"))
            backend = _FakeBackend()
            disp = MultiAgentDispatcher(persist_dir=tmpdir, content_cache=cache, llm_backend=backend)

            assert disp.coordinator.content_cache is cache, "ContentCache not wired to coordinator"

            result = disp.dispatch("Write a hello world function", roles=["solo-coder"])

            # The ContentCache should have recorded at least one miss
            # (the first LLM call for the solo-coder role).
            assert cache.misses >= 1, "ContentCache.get() was not called before LLM call"
            # The backend should have been called at least once (cache miss).
            assert backend.call_count >= 1, "LLM backend was not called on cache miss"
            assert result.success
            disp.shutdown()

    def test_content_cache_populated_after_response(self) -> None:
        """After an LLM response, the ContentCache is populated (set called)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = ContentCache(wrapped=LLMCache(cache_dir=tmpdir + "/cache"))
            backend = _FakeBackend()
            disp = MultiAgentDispatcher(persist_dir=tmpdir, content_cache=cache, llm_backend=backend)

            disp.dispatch("Write a hello world function", roles=["solo-coder"])

            # After the dispatch, the wrapped cache should have at least one entry
            # (the response was stored via content_cache.set).
            stats = cache.get_stats()
            assert stats["has_wrapped"], "ContentCache should have a wrapped cache"
            # The wrapped LLMCache should have recorded at least one set.
            wrapped_stats = stats.get("wrapped_stats", {})
            assert wrapped_stats.get("sets", 0) >= 1, "ContentCache.set() was not called after LLM response"
            disp.shutdown()

    def test_content_cache_not_used_when_not_configured(self) -> None:
        """When no ContentCache is configured, workers have content_cache=None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            disp = MultiAgentDispatcher(persist_dir=tmpdir)
            assert disp.content_cache is None
            assert disp.coordinator.content_cache is None
            disp.shutdown()


# ---------------------------------------------------------------------------
# Test 3: MicroTaskPlanner decomposes tasks when use_micro_tasks=True
# ---------------------------------------------------------------------------


class TestMicroTaskPlannerIntegration:
    """Verify MicroTaskPlanner is invoked when use_micro_tasks=True."""

    def test_micro_task_plan_populated_when_enabled(self) -> None:
        """When use_micro_tasks=True and a planner is configured, the plan is stored."""
        with tempfile.TemporaryDirectory() as tmpdir:
            planner = MicroTaskPlanner()
            disp = MultiAgentDispatcher(persist_dir=tmpdir, micro_task_planner=planner)

            result = disp.dispatch(
                "Write a hello world function. Then write tests for it.",
                roles=["solo-coder"],
                use_micro_tasks=True,
            )

            assert result.micro_task_plan is not None, "micro_task_plan not populated when use_micro_tasks=True"
            assert "micro_tasks" in result.micro_task_plan
            assert len(result.micro_task_plan["micro_tasks"]) >= 1
            assert "total_estimated_minutes" in result.micro_task_plan
            disp.shutdown()

    def test_micro_task_plan_not_populated_when_disabled(self) -> None:
        """When use_micro_tasks=False (default), no micro-task plan is produced."""
        with tempfile.TemporaryDirectory() as tmpdir:
            planner = MicroTaskPlanner()
            disp = MultiAgentDispatcher(persist_dir=tmpdir, micro_task_planner=planner)

            result = disp.dispatch(
                "Write a hello world function",
                roles=["solo-coder"],
                # use_micro_tasks defaults to False
            )

            assert result.micro_task_plan is None
            disp.shutdown()

    def test_micro_task_plan_not_populated_without_planner(self) -> None:
        """When no planner is configured, use_micro_tasks=True is a no-op."""
        with tempfile.TemporaryDirectory() as tmpdir:
            disp = MultiAgentDispatcher(persist_dir=tmpdir)

            result = disp.dispatch(
                "Write a hello world function",
                roles=["solo-coder"],
                use_micro_tasks=True,
            )

            assert result.micro_task_plan is None
            disp.shutdown()

    def test_micro_task_plan_with_file_spec(self) -> None:
        """Micro-task decomposition uses file specs passed via kwargs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            planner = MicroTaskPlanner()
            disp = MultiAgentDispatcher(persist_dir=tmpdir, micro_task_planner=planner)

            result = disp.dispatch(
                "Implement the auth module",
                roles=["solo-coder"],
                use_micro_tasks=True,
                files=["src/auth.py", "tests/test_auth.py"],
            )

            assert result.micro_task_plan is not None
            tasks = result.micro_task_plan["micro_tasks"]
            # With 2 files, the planner should create at least 2 micro-tasks.
            assert len(tasks) >= 2
            disp.shutdown()


# ---------------------------------------------------------------------------
# Test 4: All three modules work together in a full dispatch
# ---------------------------------------------------------------------------


class TestAllThreeModulesTogether:
    """Verify JudgeAgent, ContentCache, and MicroTaskPlanner work together."""

    def test_full_dispatch_with_all_v38_modules(self) -> None:
        """A single dispatch with all three V3.8 modules configured succeeds."""
        with tempfile.TemporaryDirectory() as tmpdir:
            judge = JudgeAgent(confidence_threshold=0.0)
            cache = ContentCache(wrapped=LLMCache(cache_dir=tmpdir + "/cache"))
            planner = MicroTaskPlanner()
            backend = _FakeBackend()

            disp = MultiAgentDispatcher(
                persist_dir=tmpdir,
                judge_agent=judge,
                content_cache=cache,
                micro_task_planner=planner,
                llm_backend=backend,
            )

            # Craft a review result with findings so the judge is exercised.
            crafted_review = TwoStageReviewResult(
                stage1_result=StageResult.WARN,
                stage2_result=StageResult.WARN,
                findings=[
                    ReviewFinding(
                        ReviewStage.CODE_QUALITY,
                        "warning",
                        "style",
                        "Function too long",
                        file_path="src/auth.py",
                        suggestion="Split into smaller functions",
                    ),
                ],
                overall_passed=True,
                summary="One warning",
            )

            with patch.object(disp.post_dispatch, "_run_two_stage_review", return_value=crafted_review):
                result = disp.dispatch(
                    "Implement the auth module with login and logout",
                    roles=["solo-coder"],
                    use_micro_tasks=True,
                    files=["src/auth.py"],
                )

            assert result.success, "Dispatch with all V3.8 modules should succeed"
            # Micro-task plan should be populated.
            assert result.micro_task_plan is not None
            assert len(result.micro_task_plan["micro_tasks"]) >= 1
            # ContentCache should have been checked (at least one miss).
            assert cache.misses >= 1
            # JudgeAgent should have been called (findings exist).
            assert result.judge_result is not None
            assert len(result.judge_result["accepted_findings"]) >= 0
            disp.shutdown()


# ---------------------------------------------------------------------------
# Test 5: Backward compatibility — dispatch works without any V3.8 modules
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    """Verify dispatch works when no V3.8 modules are configured."""

    def test_dispatch_without_v38_modules(self) -> None:
        """A standard dispatch with no V3.8 modules succeeds and has None results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            disp = MultiAgentDispatcher(persist_dir=tmpdir)

            result = disp.dispatch("Write a hello world function", roles=["solo-coder"])

            assert result.success, "Dispatch without V3.8 modules should succeed"
            # V3.8 optional fields should be None (not configured).
            assert result.judge_result is None
            assert result.micro_task_plan is None
            # The dispatcher should not have any V3.8 module references.
            assert disp.judge_agent is None
            assert disp.content_cache is None
            assert disp.micro_task_planner is None
            assert disp.post_dispatch.judge_agent is None
            assert disp.coordinator.content_cache is None
            disp.shutdown()

    def test_dispatch_with_use_micro_tasks_but_no_planner(self) -> None:
        """use_micro_tasks=True without a planner is a graceful no-op."""
        with tempfile.TemporaryDirectory() as tmpdir:
            disp = MultiAgentDispatcher(persist_dir=tmpdir)

            result = disp.dispatch(
                "Write a function",
                roles=["solo-coder"],
                use_micro_tasks=True,
            )

            assert result.success
            assert result.micro_task_plan is None
            disp.shutdown()

    def test_to_dict_includes_v38_fields(self) -> None:
        """DispatchResult.to_dict() includes the new V3.8 fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            disp = MultiAgentDispatcher(persist_dir=tmpdir)
            result = disp.dispatch("Write a function", roles=["solo-coder"])
            d = result.to_dict()
            assert "judge_result" in d
            assert "micro_task_plan" in d
            assert d["judge_result"] is None
            assert d["micro_task_plan"] is None
            disp.shutdown()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "--no-cov"])
