"""Lifecycle/shutdown mixin for MultiAgentDispatcher.

Extracts graceful shutdown logic so the main dispatcher file can focus on
orchestration.
"""

import logging
from typing import Any

from .dispatcher_base import DispatcherBase

logger = logging.getLogger(__name__)


class DispatcherLifecycleMixin(DispatcherBase):
    """Provides graceful shutdown helpers used by MultiAgentDispatcher."""

    warmup_manager: Any
    memory_bridge: Any
    usage_tracker: Any
    enterprise: Any
    _audit_logger: Any

    def shutdown(self) -> None:
        """Gracefully shut down all components."""
        self._shutdown_component(
            self.warmup_manager, "shutdown",
            (RuntimeError, OSError, AttributeError), "Warmup shutdown failed")
        self._shutdown_component(
            self.memory_bridge, "cleanup_expired_memories",
            (OSError, AttributeError, RuntimeError), "Memory cleanup failed")
        self._shutdown_component(
            self.usage_tracker, "persist",
            (OSError, ValueError, AttributeError), "Usage tracker persist failed")
        self._shutdown_component(
            self.enterprise.audit_logger, "force_flush",
            (OSError, AttributeError, RuntimeError), "Audit flush failed")
        self._shutdown_component(
            self._audit_logger, "close",
            (OSError, AttributeError, RuntimeError), "Dispatch audit close failed")
        self._shutdown_component(
            self.enterprise.tenant_manager, "clear_context",
            (AttributeError, RuntimeError, OSError), "Tenant cleanup failed")

    def _shutdown_component(
        self, component: Any, method: str, exc_types: tuple[type[BaseException], ...], msg: str
    ) -> None:
        """Safely call a shutdown method on a component."""
        if not component:
            return
        try:
            getattr(component, method)()
        except exc_types as e:
            logger.debug("%s: %s", msg, e)
