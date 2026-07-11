"""Status/history mixin for MultiAgentDispatcher.

Extracts status reporting and dispatch history helpers.
"""

import logging
from typing import Any

from ._version import __version__
from .dispatcher_base import DispatcherBase
from .rbac_engine import Permission, PermissionDeniedError

logger = logging.getLogger(__name__)


class DispatcherStatusMixin(DispatcherBase):
    """Provides status and history helpers used by MultiAgentDispatcher."""

    coordinator: Any
    scratchpad: Any
    batch_scheduler: Any
    consensus_engine: Any
    compressor: Any
    permission_guard: Any
    warmup_manager: Any
    memory_bridge: Any
    skillifier: Any
    quality_guard: Any
    execution_guard: Any
    _dispatch_history: list[Any]
    enterprise: Any

    def get_status(self) -> dict[str, Any]:
        """获取系统状态"""
        status = {
            "version": __version__,
            "persist_dir": self.persist_dir,
            "components": {
                "coordinator": self.coordinator is not None,
                "scratchpad": self.scratchpad is not None,
                "batch_scheduler": self.batch_scheduler is not None,
                "consensus": self.consensus_engine is not None,
                "compressor": self.compressor is not None,
                "permission_guard": self.permission_guard is not None,
                "warmup_manager": self.warmup_manager is not None,
                "memory_bridge": self.memory_bridge is not None,
                "skillifier": self.skillifier is not None,
                "quality_guard": self.quality_guard is not None,
                "performance_monitor": True,
                "execution_guard": self.execution_guard is not None,
            },
            "dispatch_count": len(self._dispatch_history),
            "scratchpad_stats": self.scratchpad.get_stats() if self.scratchpad else {},
        }
        self._append_perf_status(status)
        self._append_warmup_status(status)
        self._append_memory_status(status)
        return status

    def _append_perf_status(self, status: dict[str, Any]) -> None:
        """Append performance stats to status dict."""
        try:
            perf_stats = self._perf_monitor.get_statistics()
            status["performance"] = perf_stats
            regression = self._perf_monitor.detect_regression()
            if regression:
                status["regression_detected"] = regression
        except (ValueError, AttributeError, RuntimeError) as e:
            logger.debug("Performance stats collection failed: %s", e)

    def _append_warmup_status(self, status: dict[str, Any]) -> None:
        """Append warmup metrics to status dict."""
        if not self.warmup_manager:
            return
        try:
            metrics = self.warmup_manager.get_metrics()
            status["warmup_metrics"] = {
                "cache_size": metrics.cache_size,
                "hit_rate": round(metrics.cache_hit_rate, 3) if metrics.cache_hit_rate else 0,
                "tasks_completed": metrics.tasks_completed,
                "eager_duration_ms": round(metrics.eager_duration_ms, 2),
            }
        except (AttributeError, ValueError, RuntimeError):
            status["warmup_metrics"] = None

    def _append_memory_status(self, status: dict[str, Any]) -> None:
        """Append memory stats to status dict."""
        if not self.memory_bridge:
            return
        try:
            mem_stats = self.memory_bridge.get_statistics()
            status["memory_stats"] = {
                "total_memories": mem_stats.total_memories,
                "by_type_counts": mem_stats.by_type_counts,
                "index_built": mem_stats.index_built,
            }
        except (AttributeError, ValueError, OSError):
            status["memory_stats"] = None

    def get_history(self, limit: int = 10, **kwargs: Any) -> list[dict[str, Any]]:
        """Get dispatch history."""
        if self.enterprise.rbac_engine:
            try:
                user_id = kwargs.get('user_id', 'default')
                self.enterprise.rbac_engine.enforce(user_id, Permission.TASK_READ)
            except PermissionDeniedError as e:
                logger.warning("RBAC denied: %s", e)
                return []
        return [r.to_dict() for r in self._dispatch_history[-limit:]]

    def get_performance_stats(self) -> dict[str, Any]:
        """Get performance statistics."""
        return self._perf_monitor.get_statistics()

    def check_performance_regression(self) -> dict[str, Any] | None:
        """Check for performance regression."""
        return self._perf_monitor.detect_regression()
