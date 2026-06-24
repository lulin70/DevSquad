#!/usr/bin/env python3
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ContextEntry:
    key: str
    value: Any
    layer: str = "task"
    source: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    ttl: int | None = None

    def is_expired(self) -> bool:
        """Check whether this entry has exceeded its time-to-live.

        Returns:
            True if a TTL is set and the elapsed time since creation exceeds
            it; False otherwise (including when TTL is None).
        """
        if self.ttl is None:
            return False
        created = datetime.fromisoformat(self.timestamp)
        return (datetime.now() - created).total_seconds() > self.ttl


class DualLayerContextManager:
    """
    Dual-layer context manager for DevSquad.

    Manages two context layers:
    - **Project layer**: Long-lived, project-wide context (architecture decisions, tech stack, conventions)
    - **Task layer**: Short-lived, task-specific context (current task, worker results, scratchpad state)

    This separation prevents task-specific noise from polluting project-level context,
    and allows project context to persist across multiple task dispatches.
    """

    def __init__(self, max_project_entries: int = 100, max_task_entries: int = 50):
        self.project_context: dict[str, ContextEntry] = {}
        self.task_context: dict[str, ContextEntry] = {}
        self.max_project = max_project_entries
        self.max_task = max_task_entries

    def set_project(self, key: str, value: Any, source: str = "", ttl: int | None = None) -> None:
        """Store a value in the project context layer.

        Args:
            key: Lookup key for the value.
            value: Value to store.
            source: Optional source identifier for the value.
            ttl: Optional time-to-live in seconds; entry expires afterwards.
        """
        self.project_context[key] = ContextEntry(
            key=key,
            value=value,
            layer="project",
            source=source,
            ttl=ttl,
        )
        self._evict_if_needed("project")

    def get_project(self, key: str, default: Any = None) -> Any:
        """Retrieve a value from the project context layer.

        Args:
            key: Lookup key for the value.
            default: Value to return when the key is missing or expired.

        Returns:
            The stored value, or ``default`` when missing or expired.
        """
        entry = self.project_context.get(key)
        if entry and not entry.is_expired():
            return entry.value
        if entry and entry.is_expired():
            del self.project_context[key]
        return default

    def set_task(self, key: str, value: Any, source: str = "", ttl: int | None = None) -> None:
        """Store a value in the task context layer.

        Args:
            key: Lookup key for the value.
            value: Value to store.
            source: Optional source identifier for the value.
            ttl: Optional time-to-live in seconds; entry expires afterwards.
        """
        self.task_context[key] = ContextEntry(
            key=key,
            value=value,
            layer="task",
            source=source,
            ttl=ttl,
        )
        self._evict_if_needed("task")

    def get_task(self, key: str, default: Any = None) -> Any:
        """Retrieve a value from the task context layer.

        Args:
            key: Lookup key for the value.
            default: Value to return when the key is missing or expired.

        Returns:
            The stored value, or ``default`` when missing or expired.
        """
        entry = self.task_context.get(key)
        if entry and not entry.is_expired():
            return entry.value
        if entry and entry.is_expired():
            del self.task_context[key]
        return default

    def get_combined(self, keys: list[str] | None = None) -> dict[str, Any]:
        """Merge project and task context entries into a single dictionary.

        Args:
            keys: Optional list of keys to include; when None all non-expired
                entries are returned.

        Returns:
            Dictionary mapping context keys to their values.
        """
        combined = {}
        for k, v in self.project_context.items():
            if not v.is_expired() and (keys is None or k in keys):
                combined[k] = v.value
        for k, v in self.task_context.items():
            if not v.is_expired() and (keys is None or k in keys):
                combined[k] = v.value
        return combined

    def build_prompt_context(self, _role_id: str = "", _task_description: str = "") -> str:
        """Build a Markdown prompt string from current project and task context.

        Args:
            _role_id: Optional role identifier (currently unused).
            _task_description: Optional task description (currently unused).

        Returns:
            Markdown string with project and task context sections.
        """
        parts = []
        if self.project_context:
            parts.append("## Project Context")
            for k, v in self.project_context.items():
                if not v.is_expired():
                    parts.append(f"- **{k}**: {v.value}")

        if self.task_context:
            parts.append("\n## Task Context")
            for k, v in self.task_context.items():
                if not v.is_expired():
                    parts.append(f"- **{k}**: {v.value}")

        return "\n".join(parts)

    def clear_task_context(self) -> None:
        """Remove all entries from the task context layer."""
        self.task_context.clear()

    def clear_all(self) -> None:
        """Remove all entries from both project and task context layers."""
        self.project_context.clear()
        self.task_context.clear()

    def cleanup_expired(self) -> int:
        """Delete expired entries from both context layers.

        Returns:
            Total number of expired entries removed.
        """
        expired_project = [k for k, v in self.project_context.items() if v.is_expired()]
        expired_task = [k for k, v in self.task_context.items() if v.is_expired()]
        for k in expired_project:
            del self.project_context[k]
        for k in expired_task:
            del self.task_context[k]
        return len(expired_project) + len(expired_task)

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics for the context manager.

        Returns:
            Dictionary with project, task, and total entry counts.
        """
        return {
            "project_entries": len(self.project_context),
            "task_entries": len(self.task_context),
            "total_entries": len(self.project_context) + len(self.task_context),
        }

    def _evict_if_needed(self, layer: str) -> None:
        if layer == "project" and len(self.project_context) > self.max_project:
            oldest_key = min(self.project_context, key=lambda k: self.project_context[k].timestamp)
            del self.project_context[oldest_key]
        elif layer == "task" and len(self.task_context) > self.max_task:
            oldest_key = min(self.task_context, key=lambda k: self.task_context[k].timestamp)
            del self.task_context[oldest_key]
