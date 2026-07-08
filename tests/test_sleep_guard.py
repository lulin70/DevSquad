"""SleepGuard 单元测试。

测试覆盖：
- 正常状态：无 sleep，不停止
- 退避状态：连续失败触发指数退避
- 硬停止：超过最大连续失败数
- 成功重置：成功后重置退避计数器
- 配置自定义：自定义参数
"""

from __future__ import annotations

from pathlib import Path

from scripts.collaboration.autonomous.sleep_guard import (
    GuardState,
    SleepGuard,
    SleepGuardConfig,
)


class TestSleepGuardStates:
    """SleepGuard 状态转换测试。"""

    def test_initial_state_is_normal(self):
        """初始状态应为 NORMAL。"""
        guard = SleepGuard()
        assert guard.state == GuardState.NORMAL
        assert guard.should_stop() is False

    def test_single_failure_enters_backoff(self):
        """单次失败进入 BACKOFF 状态。"""
        guard = SleepGuard()
        guard.record_failure()
        assert guard.state == GuardState.BACKOFF
        assert guard.should_stop() is False

    def test_success_resets_to_normal(self):
        """成功后从 BACKOFF 重置到 NORMAL。"""
        guard = SleepGuard()
        guard.record_failure()
        assert guard.state == GuardState.BACKOFF
        guard.record_success()
        assert guard.state == GuardState.NORMAL
        assert guard.stats.current_consecutive_failures == 0

    def test_max_failures_triggers_hard_stop(self):
        """达到最大连续失败数触发 HARD_STOP。"""
        config = SleepGuardConfig(max_consecutive_failures=3)
        guard = SleepGuard(config=config)
        guard.record_failure()
        guard.record_failure()
        assert guard.state == GuardState.BACKOFF
        guard.record_failure()
        assert guard.state == GuardState.HARD_STOP
        assert guard.should_stop() is True

    def test_non_consecutive_failures_dont_trigger_hard_stop(self):
        """非连续失败不触发 HARD_STOP。"""
        config = SleepGuardConfig(max_consecutive_failures=3)
        guard = SleepGuard(config=config)
        guard.record_failure()
        guard.record_success()
        guard.record_failure()
        guard.record_success()
        guard.record_failure()
        assert guard.state == GuardState.BACKOFF
        assert guard.should_stop() is False


class TestSleepGuardBackoff:
    """SleepGuard 退避逻辑测试。"""

    def test_maybe_sleep_returns_zero_in_normal_state(self):
        """NORMAL 状态下 maybe_sleep 返回 0。"""
        guard = SleepGuard()
        sleep_time = guard.maybe_sleep()
        assert sleep_time == 0.0

    def test_maybe_sleep_executes_sleep_in_backoff(self):
        """BACKOFF 状态下 maybe_sleep 执行 sleep 并返回时长。"""
        config = SleepGuardConfig(
            initial_backoff_seconds=0.01,
            max_backoff_seconds=0.1,
            multiplier=2.0,
        )
        guard = SleepGuard(config=config)
        guard.record_failure()
        sleep_time = guard.maybe_sleep()
        assert sleep_time > 0
        assert guard.stats.total_sleep_seconds > 0

    def test_exponential_backoff_increases(self):
        """连续失败的退避时间应指数增长。"""
        config = SleepGuardConfig(
            initial_backoff_seconds=0.01,
            max_backoff_seconds=10.0,
            multiplier=2.0,
        )
        guard = SleepGuard(config=config)
        guard.record_failure()
        first_sleep = guard.maybe_sleep()
        guard.record_failure()
        second_sleep = guard.maybe_sleep()
        assert second_sleep > first_sleep

    def test_backoff_capped_at_max(self):
        """退避时间不超过 max_backoff_seconds。"""
        config = SleepGuardConfig(
            initial_backoff_seconds=0.01,
            max_backoff_seconds=0.05,
            multiplier=10.0,
        )
        guard = SleepGuard(config=config)
        guard.record_failure()
        guard.maybe_sleep()
        guard.record_failure()
        sleep_time = guard.maybe_sleep()
        assert sleep_time <= 0.05


class TestSleepGuardStats:
    """SleepGuard 统计测试。"""

    def test_stats_track_failures_and_successes(self):
        """统计正确跟踪失败和成功次数。"""
        guard = SleepGuard()
        guard.record_failure()
        guard.record_failure()
        guard.record_success()
        guard.record_failure()
        assert guard.stats.total_failures == 3
        assert guard.stats.total_successes == 1

    def test_stats_track_max_consecutive_failures(self):
        """统计跟踪最大连续失败数。"""
        config = SleepGuardConfig(max_consecutive_failures=10)
        guard = SleepGuard(config=config)
        for _ in range(5):
            guard.record_failure()
        guard.record_success()
        for _ in range(3):
            guard.record_failure()
        assert guard.stats.max_consecutive_failures_seen == 5

    def test_reset_clears_all_state(self):
        """reset 清除所有状态和统计。"""
        guard = SleepGuard()
        guard.record_failure()
        guard.record_failure()
        guard.reset()
        assert guard.state == GuardState.NORMAL
        assert guard.stats.total_failures == 0
        assert guard.stats.current_consecutive_failures == 0


class TestSleepGuardConfig:
    """SleepGuardConfig 配置测试。"""

    def test_default_config(self):
        """默认配置值正确。"""
        config = SleepGuardConfig()
        assert config.max_consecutive_failures == 5
        assert config.initial_backoff_seconds == 1.0
        assert config.max_backoff_seconds == 60.0
        assert config.multiplier == 2.0

    def test_custom_config(self):
        """自定义配置值正确。"""
        config = SleepGuardConfig(
            max_consecutive_failures=10,
            initial_backoff_seconds=0.5,
            max_backoff_seconds=30.0,
            multiplier=1.5,
        )
        assert config.max_consecutive_failures == 10
        assert config.initial_backoff_seconds == 0.5
        assert config.max_backoff_seconds == 30.0
        assert config.multiplier == 1.5


class TestSleepGuardIntegrationWithController:
    """SleepGuard 与 AutonomousLoopController 集成测试。"""

    def test_sleep_guard_disabled_by_default(self, tmp_path: Path):
        """默认不启用 SleepGuard。"""
        from scripts.collaboration.autonomous.loop_controller import AutonomousConfig

        config = AutonomousConfig(
            objective="test",
            notes_memory_dir=str(tmp_path / "sg"),
        )
        assert config.sleep_guard_config is None

    def test_sleep_guard_enabled_via_config(self, tmp_path: Path):
        """通过配置启用 SleepGuard。"""
        from scripts.collaboration.autonomous.loop_controller import (
            AutonomousConfig,
            AutonomousLoopController,
        )

        sg_config = SleepGuardConfig(max_consecutive_failures=3)
        config = AutonomousConfig(
            objective="test",
            notes_memory_dir=str(tmp_path / "sg2"),
            sleep_guard_config=sg_config,
        )
        controller = AutonomousLoopController(config=config)
        assert controller._sleep_guard is not None
        assert controller.get_sleep_guard_stats() is not None

    def test_sleep_guard_none_when_disabled(self, tmp_path: Path):
        """未启用时 get_sleep_guard_stats 返回 None。"""
        from scripts.collaboration.autonomous.loop_controller import (
            AutonomousConfig,
            AutonomousLoopController,
        )

        config = AutonomousConfig(
            objective="test",
            notes_memory_dir=str(tmp_path / "sg3"),
        )
        controller = AutonomousLoopController(config=config)
        assert controller.get_sleep_guard_stats() is None
