"""V4.5.1: Approval Gate — User-level approval for external operations.

Design (V451-1):
    When ``approval_callback`` is provided to ``dispatch()``, the gate
    intercepts worker operations that affect external systems (write file,
    create PR, send message) and asks the user to approve before execution.

    When ``approval_callback`` is ``None`` (default), the gate auto-approves
    every request — behavior is identical to V4.5.0 (backward compatible).

Anti-ghost:
    Module-level ``_call_counter`` is incremented on every public method
    invocation. ``check_module_activation.py`` asserts ``_call_counter > 0``
    in CI to prove the gate is wired into the dispatch pipeline.

Roadmap: V4.5.1 V451-1 (Approval Gate).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Anti-ghost counter (incremented on every public method call).
# ---------------------------------------------------------------------------
_call_counter: int = 0


def get_call_count() -> int:
    """Return the module-level call counter (anti-ghost introspection)."""
    return _call_counter


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ApprovalRequest:
    """A request for user approval before an external operation.

    Attributes
    ----------
    operation_type:
        Category of the operation (e.g. ``"write_file"``, ``"create_pr"``,
        ``"send_message"``).
    description:
        Human-readable summary of what the worker intends to do.
    details:
        Arbitrary key-value metadata (file path, PR title, message body).
    timestamp:
        Unix timestamp when the request was created.
    """

    operation_type: str
    description: str
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class ApprovalResult:
    """The user's (or auto-approve) response to an ApprovalRequest.

    Attributes
    ----------
    approved:
        ``True`` if the operation may proceed, ``False`` to block.
    reason:
        Human-readable explanation (especially for denials).
    timestamp:
        Unix timestamp when the decision was made.
    """

    approved: bool
    reason: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary for report embedding."""
        return {
            "approved": self.approved,
            "reason": self.reason,
            "timestamp": self.timestamp,
        }


# Type alias for the user-supplied callback.
ApprovalCallback = Callable[[ApprovalRequest], ApprovalResult]


# ---------------------------------------------------------------------------
# ApprovalGate
# ---------------------------------------------------------------------------


class ApprovalGate:
    """Gate that mediates worker → external-system operations.

    Parameters
    ----------
    approval_callback:
        When provided, every ``request_approval`` call delegates to this
        callback. When ``None`` (default), all requests are auto-approved
        (backward compatible with V4.5.0).
    """

    def __init__(self, approval_callback: ApprovalCallback | None = None) -> None:
        self._callback: ApprovalCallback | None = approval_callback
        self._records: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Public API (each increments _call_counter — anti-ghost)
    # ------------------------------------------------------------------

    def request_approval(
        self,
        operation_type: str,
        description: str,
        details: dict[str, Any] | None = None,
    ) -> ApprovalResult:
        """Ask for approval before an external operation.

        When ``approval_callback`` is ``None``, returns an auto-approve
        result (backward compatible). When provided, delegates to the
        callback and records the decision.
        """
        global _call_counter
        _call_counter += 1

        request = ApprovalRequest(
            operation_type=operation_type,
            description=description,
            details=details or {},
        )

        if self._callback is None:
            result = ApprovalResult(
                approved=True,
                reason="Auto-approved (no approval_callback configured)",
            )
        else:
            try:
                result = self._callback(request)
            except Exception as exc:
                # Fail-closed: if the callback itself errors, deny.
                result = ApprovalResult(
                    approved=False,
                    reason=f"Approval callback error: {exc}",
                )

        # Record the interaction for the dispatch report.
        self._records.append({
            "operation_type": request.operation_type,
            "description": request.description,
            "details": request.details,
            "approved": result.approved,
            "reason": result.reason,
            "timestamp": result.timestamp,
        })

        return result

    def get_records(self) -> list[dict[str, Any]]:
        """Return all approval interactions recorded during this dispatch.

        Each entry is a dict with keys: operation_type, description,
        details, approved, reason, timestamp.
        """
        global _call_counter
        _call_counter += 1
        return list(self._records)

    def export_markdown(self) -> str:
        """Render the approval records as a Markdown section.

        Returns an empty string when no requests were made (the report
        formatter omits the section in that case).
        """
        global _call_counter
        _call_counter += 1

        if not self._records:
            return ""

        lines = ["## Approval Gate", ""]
        for i, rec in enumerate(self._records, 1):
            status = "APPROVED" if rec["approved"] else "DENIED"
            lines.append(f"{i}. **{status}** — {rec['operation_type']}: {rec['description']}")
            if rec["reason"]:
                lines.append(f"   - Reason: {rec['reason']}")
        lines.append("")
        return "\n".join(lines)
