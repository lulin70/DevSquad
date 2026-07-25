"""Tests for Loop Engineering RollbackStrategy (V4.3.0 P1-4).

Covers:
    - Per-dimension rollback mapping (D1-D6)
    - Independent hard cap (max_rollback_iterations)
    - Accumulated artifacts across rollbacks
    - RollbackStrategy methods (determine_rollback, execute_rollback, should_stop)
    - LoopScheduler.decide_rollback integration
    - LoopKernel rollback wiring + STOP_FAILURE on cap exceeded
"""

from __future__ import annotations

import pytest

from scripts.collaboration.loop_engineering import (
    EvaluatorMode,
    IndependentEvaluator,
    LoopEngineeringConfig,
    LoopKernel,
    LoopScheduler,
    RollbackStrategy,
    RollbackTarget,
    SchedulingAction,
    UnifiedMemory,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _AlwaysWorkProbe:
    """DiscoveryProbe that always returns work (never 'done')."""

    def discover(self, objective: str, iter_index: int, memory: object) -> dict:  # noqa: ARG002
        return {"focus": f"Work {iter_index}", "tasks": ["task1"], "iter_index": iter_index}


class _CompletingProbe:
    """DiscoveryProbe that returns work at iter 0, done at iter >= 1."""

    def discover(self, objective: str, iter_index: int, memory: object) -> dict:  # noqa: ARG002
        if iter_index == 0:
            return {"focus": "Initial work", "tasks": ["task1"], "iter_index": iter_index}
        return {"focus": "All done", "tasks": [], "iter_index": iter_index, "done": True}


class _AlwaysFailEvaluator(IndependentEvaluator):
    """Evaluator that always fails verification."""

    def __init__(self) -> None:
        super().__init__(mode=EvaluatorMode.STRICT)

    def evaluate(self, _objective: str, _handoff_result: dict, _iter_index: int) -> tuple[bool, list[str]]:
        return False, ["always fail"]


class _FailNEvaluator(IndependentEvaluator):
    """Evaluator that fails the first N calls, then always passes."""

    def __init__(self, fail_count: int) -> None:
        super().__init__(mode=EvaluatorMode.STRICT)
        self._fail_count = fail_count
        self._calls = 0

    def evaluate(self, _objective: str, _handoff_result: dict, _iter_index: int) -> tuple[bool, list[str]]:
        self._calls += 1
        if self._calls <= self._fail_count:
            return False, [f"failure {self._calls}"]
        return True, []


# ---------------------------------------------------------------------------
# D1-D6 dimension mapping tests
# ---------------------------------------------------------------------------


class TestRollbackStrategyDimensionMapping:
    """Verify per-dimension rollback target mapping (D1-D6)."""

    def test_rollback_strategy_d1_to_dev(self) -> None:
        """D1 (Discovery failure) maps to DEV."""
        strategy = RollbackStrategy()
        assert strategy.determine_rollback("D1") == RollbackTarget.DEV

    def test_rollback_strategy_d2_to_dev(self) -> None:
        """D2 (Handoff failure) maps to DEV."""
        strategy = RollbackStrategy()
        assert strategy.determine_rollback("D2") == RollbackTarget.DEV

    def test_rollback_strategy_d3_to_test(self) -> None:
        """D3 (Verification failure) maps to TEST (not DEV)."""
        strategy = RollbackStrategy()
        assert strategy.determine_rollback("D3") == RollbackTarget.TEST

    def test_rollback_strategy_d4_to_dev(self) -> None:
        """D4 (Persistence failure) maps to DEV."""
        strategy = RollbackStrategy()
        assert strategy.determine_rollback("D4") == RollbackTarget.DEV

    def test_rollback_strategy_d5_to_dev(self) -> None:
        """D5 (Scheduling failure) maps to DEV."""
        strategy = RollbackStrategy()
        assert strategy.determine_rollback("D5") == RollbackTarget.DEV

    def test_rollback_strategy_d6_to_dev(self) -> None:
        """D6 (Reporting failure) maps to DEV."""
        strategy = RollbackStrategy()
        assert strategy.determine_rollback("D6") == RollbackTarget.DEV


# ---------------------------------------------------------------------------
# max_rollback_iterations tests
# ---------------------------------------------------------------------------


class TestRollbackMaxIterations:
    """Verify independent hard cap on rollback iterations."""

    def test_rollback_max_iterations_default_3(self) -> None:
        """Default max_rollback_iterations is 3."""
        config = LoopEngineeringConfig()
        assert config.max_rollback_iterations == 3
        strategy = RollbackStrategy()
        assert strategy.should_stop(3) is True
        assert strategy.should_stop(2) is False

    def test_rollback_max_iterations_configurable(self) -> None:
        """max_rollback_iterations is configurable via LoopEngineeringConfig."""
        config = LoopEngineeringConfig(max_rollback_iterations=5)
        assert config.max_rollback_iterations == 5
        config.validate()

        strategy = RollbackStrategy(max_rollback_iterations=5)
        assert strategy.should_stop(4) is False
        assert strategy.should_stop(5) is True

    def test_rollback_max_iterations_exceeds_stop_failure(self, tmp_path) -> None:
        """When rollback count exceeds hard cap, kernel returns STOP_FAILURE."""
        config = LoopEngineeringConfig(
            max_iterations=10,
            max_rollback_iterations=2,
            human_checkpoint_every=0,
        )
        kernel = LoopKernel(
            config=config,
            discovery_probe=_AlwaysWorkProbe(),
            evaluator=_AlwaysFailEvaluator(),
            memory=UnifiedMemory(storage_dir=str(tmp_path / "loop")),
        )
        report = kernel.run("test objective")

        assert report.final_status == "failed"
        assert "Rollback iterations" in report.error
        assert "hard cap" in report.error
        # 2 rollbacks performed (count=2), 3rd failure triggers STOP_FAILURE
        assert kernel.rollback_count == 2
        # total_iterations is 1 (rollback retries iter 0, never advances)
        assert report.total_iterations == 1
        # 3 cycles total: 2 rollbacks + 1 final STOP_FAILURE
        assert len(report.cycles) == 3


# ---------------------------------------------------------------------------
# Accumulated artifacts tests
# ---------------------------------------------------------------------------


class TestAccumulatedArtifacts:
    """Verify artifacts are accumulated and merged across rollbacks."""

    def test_accumulated_artifacts_passed(self, tmp_path) -> None:
        """After a rollback, previous cycle artifacts are accumulated and accessible."""
        config = LoopEngineeringConfig(
            max_iterations=10,
            max_rollback_iterations=3,
            human_checkpoint_every=0,
        )
        kernel = LoopKernel(
            config=config,
            discovery_probe=_CompletingProbe(),
            evaluator=_FailNEvaluator(fail_count=1),
            memory=UnifiedMemory(storage_dir=str(tmp_path / "loop")),
        )
        report = kernel.run("test objective")

        # The loop should complete (1 rollback then pass then done)
        assert report.final_status == "completed"
        # 1 rollback occurred (1 failure then pass)
        assert kernel.rollback_count == 0  # reset on success
        # Accumulated artifacts contain the failed cycle's discovery + handoff
        artifacts = kernel.accumulated_artifacts
        assert len(artifacts.get("discoveries", [])) == 1
        assert len(artifacts.get("handoffs", [])) == 1
        assert len(artifacts.get("verification_errors", [])) == 1

    def test_accumulated_artifacts_merged(self, tmp_path) -> None:
        """After multiple rollbacks, artifacts from all failed cycles are merged."""
        config = LoopEngineeringConfig(
            max_iterations=10,
            max_rollback_iterations=5,
            human_checkpoint_every=0,
        )
        kernel = LoopKernel(
            config=config,
            discovery_probe=_CompletingProbe(),
            evaluator=_FailNEvaluator(fail_count=3),
            memory=UnifiedMemory(storage_dir=str(tmp_path / "loop")),
        )
        report = kernel.run("test objective")

        # The loop should complete (3 rollbacks then pass then done)
        assert report.final_status == "completed"
        # Accumulated artifacts contain 3 failed cycles' discoveries + handoffs
        artifacts = kernel.accumulated_artifacts
        assert len(artifacts.get("discoveries", [])) == 3
        assert len(artifacts.get("handoffs", [])) == 3
        # All 3 error messages merged into one list
        errors = artifacts.get("verification_errors", [])
        assert len(errors) == 3
        assert "failure 1" in errors
        assert "failure 2" in errors
        assert "failure 3" in errors


# ---------------------------------------------------------------------------
# RollbackStrategy method tests
# ---------------------------------------------------------------------------


class TestRollbackStrategyMethods:
    """Verify RollbackStrategy methods (execute_rollback, should_stop)."""

    def test_execute_rollback_records_context(self) -> None:
        """execute_rollback records metadata in context dict and returns True."""
        strategy = RollbackStrategy()
        ctx: dict = {}
        result = strategy.execute_rollback(RollbackTarget.DEV, ctx)
        assert result is True
        assert ctx["rollback_target"] == "dev"
        assert ctx["rollback_executed"] is True

    def test_execute_rollback_none_returns_false(self) -> None:
        """execute_rollback with NONE target returns False, no context written."""
        strategy = RollbackStrategy()
        ctx: dict = {}
        result = strategy.execute_rollback(RollbackTarget.NONE, ctx)
        assert result is False
        assert ctx == {}

    def test_should_stop_boundary(self) -> None:
        """should_stop returns True at exactly max, False below max."""
        strategy = RollbackStrategy(max_rollback_iterations=3)
        assert strategy.should_stop(0) is False
        assert strategy.should_stop(1) is False
        assert strategy.should_stop(2) is False
        assert strategy.should_stop(3) is True
        assert strategy.should_stop(4) is True

    def test_unknown_dimension_defaults_to_dev(self) -> None:
        """Unknown dimension identifiers default to DEV."""
        strategy = RollbackStrategy()
        assert strategy.determine_rollback("D9") == RollbackTarget.DEV
        assert strategy.determine_rollback("unknown") == RollbackTarget.DEV


# ---------------------------------------------------------------------------
# LoopScheduler.decide_rollback integration tests
# ---------------------------------------------------------------------------


class TestSchedulerDecideRollback:
    """Verify LoopScheduler.decide_rollback integration."""

    def test_scheduler_decide_rollback_returns_rollback(self) -> None:
        """decide_rollback returns ROLLBACK action when under cap."""
        scheduler = LoopScheduler(rollback_strategy=RollbackStrategy(3))
        decision = scheduler.decide_rollback(0, "D3", 0, 3)
        assert decision.action == SchedulingAction.ROLLBACK
        assert decision.next_iteration == 0  # retry same iteration
        assert "test" in decision.reason  # D3 -> TEST

    def test_scheduler_decide_rollback_exceeds_cap(self) -> None:
        """decide_rollback returns STOP_FAILURE when cap exceeded."""
        scheduler = LoopScheduler(rollback_strategy=RollbackStrategy(3))
        decision = scheduler.decide_rollback(0, "D3", 3, 3)
        assert decision.action == SchedulingAction.STOP_FAILURE
        assert "hard cap" in decision.reason


# ---------------------------------------------------------------------------
# Config validation tests
# ---------------------------------------------------------------------------


class TestRollbackConfigValidation:
    """Verify LoopEngineeringConfig.max_rollback_iterations validation."""

    def test_config_validate_max_rollback_iterations_zero(self) -> None:
        """max_rollback_iterations=0 raises ValueError."""
        config = LoopEngineeringConfig(max_rollback_iterations=0)
        with pytest.raises(ValueError, match="max_rollback_iterations"):
            config.validate()

    def test_config_validate_max_rollback_iterations_negative(self) -> None:
        """max_rollback_iterations < 0 raises ValueError."""
        config = LoopEngineeringConfig(max_rollback_iterations=-1)
        with pytest.raises(ValueError, match="max_rollback_iterations"):
            config.validate()

    def test_config_validate_max_rollback_iterations_one(self) -> None:
        """max_rollback_iterations=1 is valid (minimum allowed)."""
        config = LoopEngineeringConfig(max_rollback_iterations=1)
        config.validate()
        assert config.max_rollback_iterations == 1
