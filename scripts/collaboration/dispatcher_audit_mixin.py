"""Audit logging mixin for MultiAgentDispatcher.

Extracts dispatch-level audit helpers so the main dispatcher file can focus
on orchestration logic.
"""

import logging
from typing import Any

from .dispatch_models import DispatchResult
from .dispatcher_base import DispatcherBase

logger = logging.getLogger(__name__)


class DispatcherAuditMixin(DispatcherBase):
    """Provides audit logging helpers used by MultiAgentDispatcher."""

    _audit_logger: Any

    def _log_dispatch_end_audit(
        self, user_id: str, success: bool, duration: float
    ) -> None:
        """Log dispatch_end event to the audit logger (if configured)."""
        if self._audit_logger is None:
            return
        try:
            self._audit_logger.log_dispatch_end(
                user_id=user_id,
                success=success,
                duration=duration,
            )
        except (ValueError, RuntimeError, OSError) as audit_err:
            logger.warning("Audit log_dispatch_end failed: %s", audit_err)

    def _log_dispatch_error_audit(
        self, user_id: str, error: Exception
    ) -> None:
        """Log an error event to the audit logger (if configured)."""
        if self._audit_logger is None:
            return
        try:
            self._audit_logger.log_error(
                user_id=user_id,
                error_type=type(error).__name__,
                context={"message": str(error)[:200]},
            )
        except (ValueError, RuntimeError, OSError) as audit_err:
            logger.warning("Audit log_error failed: %s", audit_err)

    def _attach_audit_entries(self, result: DispatchResult) -> None:
        """Attach recent audit entries to the dispatch result."""
        if self._audit_logger is None:
            return
        try:
            entries = self._audit_logger.get_entries(limit=50)
            result.audit_entries = [
                {
                    "event_type": e.event_type,
                    "user_id": e.user_id,
                    "timestamp": e.timestamp,
                    "details": e.details,
                    "entry_hash": e.entry_hash,
                }
                for e in entries
            ]
        except (ValueError, RuntimeError, OSError) as audit_err:
            logger.warning("Audit get_entries failed: %s", audit_err)
