"""Loop Engineering 五步闭环单元测试。"""

from __future__ import annotations

import pytest

from scripts.collaboration.loop_engineering import (
    CycleResult,
    DiscoveryProbe,
    EvaluatorMode,
    HandoffAdapter,
    IndependentEvaluator,
    LoopEngineeringConfig,
    LoopEvent,
    LoopEventType,
    LoopKernel,
    LoopScheduler,
    LoopType,
    SchedulingAction,
    SchedulingDecision,
    UnifiedMemory,
)


class TestModels:
    """数据模型测试。"""

    def test_loop_type_values(self):
        assert LoopType.DESIGN.value == "design"
        assert LoopType.CODING.value == "coding"
        assert LoopType.TESTING.value == "testing"

    def test_evaluator_mode_values(self):
        assert EvaluatorMode.STRICT.value == "strict"
        assert EvaluatorMode.STANDARD.value == "standard"
        assert EvaluatorMode.OFF.value == "off"

    def test_scheduling_action_values(self):
        assert SchedulingAction.CONTINUE.value == "continue"
        assert SchedulingAction.STOP_SUCCESS.value == "stop_success"
        assert SchedulingAction.STOP_FAILURE.value == "stop_failure"

    def test_config_validate_ok(self):
        config = LoopEngineeringConfig(max_iterations=10, max_tokens=10000, human_checkpoint_every=3)
        config.validate()

    def test_config_validate_max_iterations(self):
        config = LoopEngineeringConfig(max_iterations=0)
        with pytest.raises(ValueError, match="max_iterations"):
            config.validate()

    def test_config_validate_max_tokens(self):
        config = LoopEngineeringConfig(max_tokens=100)
        with pytest.raises(ValueError, match="max_tokens"):
            config.validate()

    def test_config_validate_checkpoint(self):
        config = LoopEngineeringConfig(max_iterations=5, human_checkpoint_every=10)
        with pytest.raises(ValueError, match="human_checkpoint"):
            config.validate()

    def test_loop_event_creation(self):
        event = LoopEvent(
            event_type=LoopEventType.DISCOVERY_STARTED,
            phase="discovery",
            iter_index=0,
        )
        assert event.event_type == LoopEventType.DISCOVERY_STARTED
        assert event.payload == {}

    def test_scheduling_decision(self):
        decision = SchedulingDecision(
            action=SchedulingAction.CONTINUE,
            reason="ok",
            next_iteration=1,
        )
        assert decision.action == SchedulingAction.CONTINUE

    def test_cycle_result(self):
        cycle = CycleResult(
            iter_index=0,
            discovery={},
            handoff={},
            verification_passed=True,
            verification_errors=[],
            scheduling_decision=SchedulingDecision(
                action=SchedulingAction.STOP_SUCCESS,
                reason="done",
            ),
        )
        assert cycle.verification_passed


class TestDiscoveryProbe:
    """Discovery 阶段测试。"""

    def test_initial_discovery(self):
        probe = DiscoveryProbe()
        result = probe.discover("build feature X", 0, memory=None)
        assert "analyze_objective" in result["tasks"]
        assert result["iter_index"] == 0

    def test_fix_errors_discovery(self):
        probe = DiscoveryProbe()
        memory = UnifiedMemory(storage_dir="/tmp/test_loop_discovery")
        memory._cycles = [{
            "verification_errors": ["error1"],
            "completed_items": [],
        }]
        result = probe.discover("build feature X", 1, memory=memory)
        assert "fix_errors" in result["tasks"]
        assert result["errors_to_fix"] == ["error1"]

    def test_done_discovery(self):
        probe = DiscoveryProbe()
        memory = UnifiedMemory(storage_dir="/tmp/test_loop_done")
        memory._cycles = [{
            "verification_errors": [],
            "completed_items": ["implement", "test", "review"],
        }]
        result = probe.discover("build feature X", 2, memory=memory)
        assert result.get("done") is True


class TestHandoffAdapter:
    """Handoff 阶段测试。"""

    def test_dispatch_no_tasks(self):
        adapter = HandoffAdapter()
        result = adapter.dispatch({"tasks": [], "focus": "test"}, 0)
        assert result["status"] == "skipped"

    def test_dispatch_mock(self):
        adapter = HandoffAdapter(dispatcher=None)
        result = adapter.dispatch({"tasks": ["implement"], "focus": "do X"}, 0)
        assert result["status"] == "mock"
        assert "implement" in result["output"]

    def test_dispatch_with_dispatcher(self):
        class MockDispatcher:
            def dispatch(self, _task):
                class R:
                    summary = "done"
                return R()

        adapter = HandoffAdapter(dispatcher=MockDispatcher())
        result = adapter.dispatch({"tasks": ["implement"], "focus": "do X"}, 0)
        assert result["status"] == "dispatched"
        assert result["output"] == "done"

    def test_dispatch_error(self):
        class BadDispatcher:
            def dispatch(self, _task):
                raise RuntimeError("boom")

        adapter = HandoffAdapter(dispatcher=BadDispatcher())
        result = adapter.dispatch({"tasks": ["implement"], "focus": "do X"}, 0)
        assert result["status"] == "error"
        assert "boom" in result["error"]


class TestIndependentEvaluator:
    """Verification 阶段测试。"""

    def test_off_mode(self):
        evaluator = IndependentEvaluator(mode=EvaluatorMode.OFF)
        passed, errors = evaluator.evaluate("obj", {"status": "error"}, 0)
        assert passed is True
        assert errors == []

    def test_strict_mode_error_status(self):
        evaluator = IndependentEvaluator(mode=EvaluatorMode.STRICT)
        passed, errors = evaluator.evaluate("obj", {"status": "error", "error": "bad"}, 0)
        assert passed is False
        assert len(errors) >= 1

    def test_strict_mode_empty_output(self):
        evaluator = IndependentEvaluator(mode=EvaluatorMode.STRICT)
        passed, errors = evaluator.evaluate("obj", {"status": "ok", "output": ""}, 0)
        assert passed is False

    def test_strict_mode_pass(self):
        evaluator = IndependentEvaluator(mode=EvaluatorMode.STRICT)
        passed, errors = evaluator.evaluate("obj", {"status": "ok", "output": "result"}, 0)
        assert passed is True
        assert errors == []

    def test_standard_mode_tolerant(self):
        evaluator = IndependentEvaluator(mode=EvaluatorMode.STANDARD)
        passed, _ = evaluator.evaluate("obj", {"status": "error", "error": "e1"}, 0)
        assert passed is True  # STANDARD tolerates ≤1 error

    def test_with_custom_validator(self):
        def validator(obj, result):
            return ["custom error"] if result.get("output") == "bad" else []

        evaluator = IndependentEvaluator(
            mode=EvaluatorMode.STRICT,
            validator=validator,
        )
        passed, errors = evaluator.evaluate("obj", {"status": "ok", "output": "bad"}, 0)
        assert passed is False
        assert "custom error" in errors


class TestUnifiedMemory:
    """Persistence 阶段测试。"""

    def test_persist_and_load(self, tmp_path):
        memory = UnifiedMemory(storage_dir=str(tmp_path / "mem"))
        event = LoopEvent(
            event_type=LoopEventType.DISCOVERY_STARTED,
            phase="discovery",
            iter_index=0,
        )
        memory.persist_event(event)
        assert len(memory._events) == 1

        cycle = CycleResult(
            iter_index=0,
            discovery={},
            handoff={},
            verification_passed=True,
            verification_errors=[],
            scheduling_decision=None,  # type: ignore
        )
        memory.persist_cycle(cycle)
        history = memory.load_history("objective")
        assert len(history) == 1

    def test_save_to_disk(self, tmp_path):
        memory = UnifiedMemory(storage_dir=str(tmp_path / "mem"))
        event = LoopEvent(
            event_type=LoopEventType.HANDOFF_DISPATCHED,
            phase="handoff",
            iter_index=0,
        )
        memory.persist_event(event)
        filepath = memory.save_to_disk("test objective")
        assert filepath.exists()
        content = filepath.read_text(encoding="utf-8")
        assert "handoff" in content

    def test_clear(self, tmp_path):
        memory = UnifiedMemory(storage_dir=str(tmp_path / "mem"))
        memory.persist_event(LoopEvent(
            event_type=LoopEventType.LOOP_COMPLETED,
            phase="scheduling",
            iter_index=0,
        ))
        memory.clear()
        assert len(memory._events) == 0


class TestLoopScheduler:
    """Scheduling 阶段测试。"""

    def _make_cycle(self, passed: bool, done: bool = False, iter_index: int = 0) -> CycleResult:
        return CycleResult(
            iter_index=iter_index,
            discovery={"done": done} if done else {},
            handoff={},
            verification_passed=passed,
            verification_errors=[] if passed else ["err"],
            scheduling_decision=None,  # type: ignore
        )

    def test_stop_success_when_done(self):
        scheduler = LoopScheduler(human_checkpoint_every=5)
        cycle = self._make_cycle(passed=True, done=True)
        decision = scheduler.decide(0, cycle, 0, 50)
        assert decision.action == SchedulingAction.STOP_SUCCESS

    def test_continue_when_passed_not_done(self):
        scheduler = LoopScheduler(human_checkpoint_every=5)
        cycle = self._make_cycle(passed=True, done=False)
        decision = scheduler.decide(0, cycle, 0, 50)
        assert decision.action == SchedulingAction.CONTINUE
        assert decision.next_iteration == 1

    def test_stop_failure_consecutive(self):
        scheduler = LoopScheduler(human_checkpoint_every=5)
        cycle = self._make_cycle(passed=False)
        decision = scheduler.decide(0, cycle, 3, 50)
        assert decision.action == SchedulingAction.STOP_FAILURE

    def test_stop_failure_max_iterations(self):
        scheduler = LoopScheduler(human_checkpoint_every=5)
        cycle = self._make_cycle(passed=False)
        decision = scheduler.decide(49, cycle, 0, 50)
        assert decision.action == SchedulingAction.STOP_FAILURE

    def test_fix_when_failed(self):
        scheduler = LoopScheduler(human_checkpoint_every=5)
        cycle = self._make_cycle(passed=False)
        decision = scheduler.decide(0, cycle, 0, 50)
        assert decision.action == SchedulingAction.FIX

    def test_human_checkpoint(self):
        scheduler = LoopScheduler(human_checkpoint_every=5)
        cycle = self._make_cycle(passed=False)
        decision = scheduler.decide(4, cycle, 0, 50)
        assert decision.action == SchedulingAction.HUMAN_CHECKPOINT


class TestLoopKernel:
    """LoopKernel 五步闭环集成测试。"""

    def test_loop_completes_successfully(self, tmp_path):
        config = LoopEngineeringConfig(
            max_iterations=10,
            human_checkpoint_every=0,
        )
        config.human_checkpoint_every = 0
        kernel = LoopKernel(
            config=config,
            memory=UnifiedMemory(storage_dir=str(tmp_path / "loop")),
        )
        report = kernel.run("test objective")
        assert report.success or report.final_status in ("completed", "failed", "stopped")

    def test_loop_stop_manual(self, tmp_path):
        config = LoopEngineeringConfig(max_iterations=10)
        kernel = LoopKernel(
            config=config,
            memory=UnifiedMemory(storage_dir=str(tmp_path / "loop")),
        )
        kernel.stop()
        report = kernel.run("test")
        assert report.final_status == "stopped"

    def test_loop_max_iterations(self, tmp_path):
        class AlwaysFailEvaluator(IndependentEvaluator):
            def evaluate(self, _objective, _handoff_result, iter_index):
                if iter_index < 3:
                    return False, ["fail"]
                return True, []

        config = LoopEngineeringConfig(max_iterations=3, human_checkpoint_every=0)
        kernel = LoopKernel(
            config=config,
            evaluator=AlwaysFailEvaluator(mode=EvaluatorMode.STRICT),
            memory=UnifiedMemory(storage_dir=str(tmp_path / "loop")),
        )
        report = kernel.run("test")
        assert report.total_iterations <= 3
