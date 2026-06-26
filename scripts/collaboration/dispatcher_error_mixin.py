"""Error handling mixin for MultiAgentDispatcher.

Extracts uniform dispatch error handling for sync and async paths.
"""

import logging
import time
from typing import Any

from .dispatch_models import DispatchResult
from .dispatcher_base import DispatcherBase
from .user_friendly_error import make_user_friendly_error

logger = logging.getLogger(__name__)


class DispatcherErrorMixin(DispatcherBase):
    """Provides uniform error handling used by MultiAgentDispatcher."""

    enterprise: Any
    metrics_service: Any

    def _handle_dispatch_error(
        self,
        error: Exception,
        task_description: str,
        tenant_ctx: Any,
        phase: str,
        start_time: float,
        lang: str,
        is_async: bool = False,
    ) -> DispatchResult:
        """Handle dispatch errors uniformly for sync and async paths."""
        prefix = "Async " if is_async else ""
        if isinstance(error, (ValueError, TypeError, AttributeError)):
            logger.error(
                "%sdispatch validation error for task '%s': %s - %s",
                prefix, task_description[:50], type(error).__name__, error, exc_info=True,
            )
            error_key, metrics_label = "dispatch_failed", "validation"
        elif isinstance(error, (ImportError, ModuleNotFoundError)):
            logger.error(
                "Missing dependency during %sdispatch of task '%s': %s",
                prefix.lower(), task_description[:50], error, exc_info=True,
            )
            error_key, metrics_label = "backend_unavailable", "dependency"
        else:
            logger.critical(
                "UNEXPECTED ERROR in %sdispatch task '%s': %s - %s",
                prefix.lower(), task_description[:50], type(error).__name__, error, exc_info=True,
            )
            error_key, metrics_label = "dispatch_failed", "unknown"

        self.enterprise.clear_tenant_context(tenant_ctx)
        self.metrics_service.safe_record(lambda m: (
            m.record_error(metrics_label, "dispatcher"),
            m.tasks_in_progress_gauge.labels(phase=phase).dec(),
        ))
        friendly = make_user_friendly_error(error_key, original_error=error)
        return DispatchResult(
            success=False,
            task_description=task_description,
            matched_roles=[],
            summary=friendly.message,
            errors=[friendly.format()],
            duration_seconds=time.time() - start_time,
            lang=lang,
        )
