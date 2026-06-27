"""State query mixin for WorkflowEngine.

Extracts read-only state queries (status, classification, summary) and
executor registration so the main engine file can focus on
initialization and orchestration.

Responsibilities (from IMPROVEMENT_PLAN_V3.9.2.md P2-3):
    - Workflow instance status summary (progress, completion rate)
    - Step classification by node_type (deterministic / llm / hybrid)
    - Concise step-count summary for cost estimation
    - Executor registration (action name -> callable)
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from .workflow_engine_base import (
    NodeType,
    WorkflowEngineBase,
)

logger = logging.getLogger(__name__)


class WorkflowEngineStateMixin(WorkflowEngineBase):
    """Provides workflow state queries and executor registration."""

    def get_workflow_status(self, instance_id: str) -> dict[str, Any] | None:
        """Return a status summary for a workflow instance.

        Args:
            instance_id: Identifier of the workflow instance.

        Returns:
            Dictionary with instance_id, workflow_id, status, progress
            (e.g. "3/10"), completion_rate percentage, current_step,
            failed_steps, and has_checkpoint flag. Returns None if the
            instance is not found.
        """
        instance = self.instances.get(instance_id)
        if not instance:
            return None

        definition = self.definitions.get(instance.workflow_id)
        total_steps = len(definition.steps) if definition else 0
        completed = len(instance.completed_steps)

        return {
            "instance_id": instance_id,
            "workflow_id": instance.workflow_id,
            "status": instance.status.value,
            "progress": f"{completed}/{total_steps}",
            "completion_rate": (completed / total_steps * 100) if total_steps > 0 else 0,
            "current_step": instance.current_step,
            "failed_steps": instance.failed_steps,
            "has_checkpoint": instance.checkpoint_id is not None,
        }

    def register_executor(self, action: str, executor: Callable[..., Any]) -> None:
        """Register a callable executor for a step action name.

        Args:
            action: Action name that maps to the executor.
            executor: Callable ``(step, variables) -> result``.
        """
        self.executors[action] = executor

    def classify_steps(self, workflow_id: str | None = None) -> dict[str, Any]:
        """V3.8 #6: Classify workflow steps by node_type and return stats.

        Counts how many steps are deterministic, llm, or hybrid for the
        given workflow definition. When ``workflow_id`` is None, the
        most recently created definition is used.

        Returns
        -------
        Dict with keys:
            - ``total``: total step count
            - ``deterministic``: count of DETERMINISTIC steps
            - ``llm``: count of LLM steps
            - ``hybrid``: count of HYBRID steps
            - ``deterministic_pct``: percentage (0-100)
            - ``llm_pct``: percentage (0-100)
            - ``hybrid_pct``: percentage (0-100)
            - ``by_step``: list of ``{step_id, name, node_type}`` dicts
        """
        empty_result: dict[str, Any] = {
            "total": 0,
            "deterministic": 0,
            "llm": 0,
            "hybrid": 0,
            "deterministic_pct": 0.0,
            "llm_pct": 0.0,
            "hybrid_pct": 0.0,
            "by_step": [],
        }

        if workflow_id is None:
            if not self.definitions:
                return empty_result
            workflow_id = next(reversed(self.definitions))

        definition = self.definitions.get(workflow_id)
        if not definition:
            return empty_result

        steps = definition.steps
        total = len(steps)
        det = sum(1 for s in steps if s.node_type == NodeType.DETERMINISTIC)
        llm = sum(1 for s in steps if s.node_type == NodeType.LLM)
        hybrid = sum(1 for s in steps if s.node_type == NodeType.HYBRID)

        def pct(n: int) -> float:
            return round(n / total * 100, 2) if total > 0 else 0.0

        return {
            "total": total,
            "deterministic": det,
            "llm": llm,
            "hybrid": hybrid,
            "deterministic_pct": pct(det),
            "llm_pct": pct(llm),
            "hybrid_pct": pct(hybrid),
            "by_step": [
                {"step_id": s.step_id, "name": s.name, "node_type": s.node_type.value}
                for s in steps
            ],
        }

    def get_step_summary(self, workflow_id: str | None = None) -> dict[str, int]:
        """V3.8 #6: Return a concise step-count summary by node_type.

        Useful for cost estimation and debugging — answers "how many
        steps in this workflow need an LLM call?" without the full
        ``classify_steps`` breakdown.

        Args:
            workflow_id: Workflow definition ID to summarize. When None,
                the most recently created definition is used (matching
                ``classify_steps`` behavior). When no definitions exist,
                all counts are zero.

        Returns:
            Dict with keys ``deterministic``, ``llm``, ``hybrid``,
            ``total``. ``total`` is the sum of the other three.
        """
        classified = self.classify_steps(workflow_id)
        return {
            "deterministic": classified["deterministic"],
            "llm": classified["llm"],
            "hybrid": classified["hybrid"],
            "total": classified["total"],
        }
