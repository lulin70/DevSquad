"""Dispatch Skill — One-click multi-agent task orchestration.

Provides a high-level skill interface for the MultiAgentDispatcher,
enabling one-click task dispatch with automatic role matching and
parallel execution through the DevSquad collaboration pipeline.

Integration:
    This skill wraps scripts.collaboration.dispatcher.MultiAgentDispatcher
    and exposes it as a standardized Skill interface for the DevSquad system.

Example:
    >>> from skills.dispatch.handler import DispatchSkill
    >>> skill = DispatchSkill()
    >>> result = skill.run("Design a user authentication system")
    >>> print(result["status"])  # "success" or "failed"
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from skills.registry import BaseSkill

_dispatcher = None


def _get_dispatcher():
    """Get or create lazy-initialized MultiAgentDispatcher instance.

    Uses singleton pattern to avoid repeated initialization overhead.
    Dispatcher is created on first call and reused for subsequent calls.

    Returns:
        MultiAgentDispatcher: Configured dispatcher instance ready for use.
    """
    global _dispatcher
    if _dispatcher is None:
        from scripts.collaboration.dispatcher import MultiAgentDispatcher

        _dispatcher = MultiAgentDispatcher()
    return _dispatcher


class DispatchSkill(BaseSkill):
    """Multi-agent task dispatch skill.

    Wraps MultiAgentDispatcher to provide a simplified interface for
    task submission, role matching, parallel execution, and result aggregation.

    Attributes:
        name: Skill identifier ("dispatch")
        description: Human-readable skill description
        version: Skill semantic version

    Example:
        >>> skill = DispatchSkill()
        >>> result = skill.run(
        ...     task="Implement user login API",
        ...     roles=["architect", "solo-coder"],
        ...     mode="auto",
        ... )
        >>> print(result["matched_roles"])
        >>> print(result["report"])
    """
    name = "dispatch"
    description = "Multi-agent task dispatch: submit a task → auto-match roles → parallel execution → structured report"
    version = "3.6.9"

    def run(self, task: str, roles: list = None, mode: str = "auto", dry_run: bool = False) -> dict:
        """Execute multi-agent task dispatch.

        Submits task to MultiAgentDispatcher and returns structured results
        with timing, role matching, worker outputs, and optional reports.

        Args:
            task: Task description in natural language (required)
            roles: Optional list of role IDs (e.g., ["architect", "tester"]).
                   None triggers automatic role matching.
            mode: Execution mode - "auto" (default), "parallel", "sequential"
            dry_run: If True, simulate without actual Worker execution

        Returns:
            Dict with keys:
                - success: bool - Overall success status
                - matched_roles: list - Matched role definitions
                - worker_results: list - Individual Worker outputs
                - report: str or None - Formatted Markdown report
                - intent_match: dict - Intent detection result
                - five_axis_result: dict - Five-axis consensus (if applicable)
                - timing: dict - Execution timing {"total_s": float}
                - status: str - "success" or "failed"

        Example:
            >>> result = skill.run("Review code quality")
            >>> if result["success"]:
            ...     print(f"Completed in {result['timing']['total_s']}s")
        """
        d = _get_dispatcher()
        result = d.dispatch(
            task_description=task,
            roles=roles,
            mode=mode,
            dry_run=dry_run,
        )
        timing = result.timing if hasattr(result, "timing") and isinstance(result.timing, dict) else {}
        return {
            "success": result.success,
            "matched_roles": result.matched_roles,
            "worker_results": result.worker_results,
            "report": getattr(result, "report", None),
            "intent_match": result.intent_match,
            "five_axis_result": result.five_axis_result,
            "timing": {"total_s": round(timing.get("total", 0), 3)},
            "status": "success" if result.success else "failed",
        }

    def quick(self, task: str, **kwargs) -> dict:
        """Quick dispatch with sensible defaults.

        Convenience method for simple use cases where default settings are acceptable.
        Forwards all arguments to run() method.

        Args:
            task: Task description in natural language
            **kwargs: Additional arguments passed to run()

        Returns:
            Same format as run() return value.
        """
        return self.run(task, **kwargs)

    def roles_info(self) -> list:
        """Get information about available collaboration roles.

        Retrieves role definitions from RoleMatcher for display or selection.

        Returns:
            List of dicts with keys:
                - id: Role identifier (e.g., "architect")
                - name: Display name (e.g., "架构师")
                - keywords: First 5 keywords for this role
        """
        from scripts.collaboration.role_matcher import RoleMatcher

        rm = RoleMatcher()
        return [{"id": r.role_id, "name": r.name, "keywords": r.keywords[:5]} for r in rm.roles]
