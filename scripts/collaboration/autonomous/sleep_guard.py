"""SleepGuard: 防止自主迭代无限循环的安全机制。

借鉴 TraeMultiAgentSkill 的 SleepGuard 理念：
- 连续失败时指数退避 sleep，避免在错误状态下狂奔
- N 次连续失败后硬停止，防止资源浪费
- 成功时重置退避计数器

三种状态：
- NORMAL: 正常运行，无 sleep
- BACKOFF: 连续失败，指数退避
- HARD_STOP: 超过最大连续失败数，强制停止
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class GuardState(Enum):
    """SleepGuard 状态。"""

    NORMAL = "normal"
    BACKOFF = "backoff"
    HARD_STOP = "hard_stop"


@dataclass
class SleepGuardConfig:
    """SleepGuard 配置。

    Attributes:
        max_consecutive_failures: 连续失败上限，超过则 HARD_STOP
        initial_backoff_seconds: 初始退避秒数
        max_backoff_seconds: 最大退避秒数（指数退避上限）
        multiplier: 退避乘数（每次失败 sleep *= multiplier）
    """

    max_consecutive_failures: int = 5
    initial_backoff_seconds: float = 1.0
    max_backoff_seconds: float = 60.0
    multiplier: float = 2.0


@dataclass
class SleepGuardStats:
    """SleepGuard 运行统计。"""

    total_failures: int = 0
    total_successes: int = 0
    total_sleep_seconds: float = 0.0
    current_consecutive_failures: int = 0
    max_consecutive_failures_seen: int = 0
    state_history: list[str] = field(default_factory=list)


class SleepGuard:
    """防止自主迭代无限循环的安全守卫。

    工作原理：
    1. 每次迭代后调用 record_success() 或 record_failure()
    2. 连续失败时，下次迭代前调用 maybe_sleep() 会执行指数退避
    3. 连续失败超过 max_consecutive_failures 时，状态变为 HARD_STOP

    Usage:
        guard = SleepGuard()
        for i in range(max_iterations):
            result = run_iteration()
            if result.success:
                guard.record_success()
            else:
                guard.record_failure()
            if guard.should_stop():
                break
            guard.maybe_sleep()
    """

    def __init__(self, config: SleepGuardConfig | None = None) -> None:
        self._config = config or SleepGuardConfig()
        self._stats = SleepGuardStats()
        self._state = GuardState.NORMAL
        self._current_backoff = self._config.initial_backoff_seconds

    @property
    def state(self) -> GuardState:
        """当前状态。"""
        return self._state

    @property
    def stats(self) -> SleepGuardStats:
        """运行统计。"""
        return self._stats

    def record_success(self) -> None:
        """记录一次成功，重置退避计数器。"""
        self._stats.total_successes += 1
        self._stats.current_consecutive_failures = 0
        self._current_backoff = self._config.initial_backoff_seconds
        if self._state == GuardState.BACKOFF:
            self._state = GuardState.NORMAL
            self._stats.state_history.append("normal")

    def record_failure(self) -> None:
        """记录一次失败，增加退避计数器。"""
        self._stats.total_failures += 1
        self._stats.current_consecutive_failures += 1
        if self._stats.current_consecutive_failures > self._stats.max_consecutive_failures_seen:
            self._stats.max_consecutive_failures_seen = self._stats.current_consecutive_failures

        if self._stats.current_consecutive_failures >= self._config.max_consecutive_failures:
            self._state = GuardState.HARD_STOP
            self._stats.state_history.append("hard_stop")
            logger.warning(
                "SleepGuard HARD_STOP: %d consecutive failures (max=%d)",
                self._stats.current_consecutive_failures,
                self._config.max_consecutive_failures,
            )
        else:
            self._state = GuardState.BACKOFF
            self._stats.state_history.append("backoff")
            logger.info(
                "SleepGuard BACKOFF: %d consecutive failures, next sleep=%.1fs",
                self._stats.current_consecutive_failures,
                self._current_backoff,
            )

    def should_stop(self) -> bool:
        """是否应该硬停止。"""
        return self._state == GuardState.HARD_STOP

    def maybe_sleep(self) -> float:
        """如果处于 BACKOFF 状态，执行 sleep 并返回 sleep 时长。

        Returns:
            实际 sleep 的秒数（0.0 表示未 sleep）。
        """
        if self._state != GuardState.BACKOFF:
            return 0.0

        sleep_time = min(self._current_backoff, self._config.max_backoff_seconds)
        time.sleep(sleep_time)
        self._stats.total_sleep_seconds += sleep_time

        self._current_backoff = min(
            self._current_backoff * self._config.multiplier,
            self._config.max_backoff_seconds,
        )
        return sleep_time

    def reset(self) -> None:
        """重置所有状态和统计。"""
        self._stats = SleepGuardStats()
        self._state = GuardState.NORMAL
        self._current_backoff = self._config.initial_backoff_seconds


__all__ = [
    "GuardState",
    "SleepGuard",
    "SleepGuardConfig",
    "SleepGuardStats",
]
