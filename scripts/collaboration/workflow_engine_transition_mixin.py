"""Transition mixin for WorkflowEngine.

Extracts workflow instance start and step-execution (state transition)
logic so the main engine file can focus on initialization and
orchestration.

Responsibilities (from IMPROVEMENT_PLAN_V3.9.2.md P2-3):
    - Start a new workflow instance (transition PENDING -> RUNNING)
    - Execute the current step and advance to the next step
    - Default step executor that delegates to the dispatcher
    - Next-step resolution within a workflow definition
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

from .workflow_engine_base import (
    StepStatus,
    WorkflowDefinition,
    WorkflowEngineBase,
    WorkflowInstance,
    WorkflowStatus,
    WorkflowStep,
)

logger = logging.getLogger(__name__)


class WorkflowEngineTransitionMixin(WorkflowEngineBase):
    """Provides workflow instance start and step-execution transitions."""

    def start_workflow(self, workflow_id: str, variables: dict[str, Any] | None = None) -> WorkflowInstance | None:
        """Start a new workflow instance from a registered definition.

        Args:
            workflow_id: Identifier of the workflow definition to start.
            variables: Optional initial variables for the instance.

        Returns:
            The created WorkflowInstance, or None when the definition is
            not found.
        """
        definition = self.definitions.get(workflow_id)
        if not definition:
            logger.warning("Workflow not found: %s", workflow_id)
            return None

        instance = WorkflowInstance(
            workflow_id=workflow_id,
            variables=variables or {},
            status=WorkflowStatus.RUNNING,
            started_at=datetime.now().isoformat(),
        )

        if definition.steps:
            instance.current_step = definition.steps[0].step_id

        self.instances[instance.instance_id] = instance
        logger.info("Workflow started: %s", instance.instance_id)
        return instance

    def execute_step(self, instance_id: str, step_executor: Callable[..., Any] | None = None) -> WorkflowStep | None:
        """Execute the current step of a workflow instance.

        Args:
            instance_id: Identifier of the workflow instance.
            step_executor: Optional callable ``(step, variables) -> result``.
                When None, a registered executor or the default executor is
                used.

        Returns:
            The executed WorkflowStep with updated status/result, or None
            when the instance or its current step cannot be found.
        """
        instance = self.instances.get(instance_id)
        if not instance:
            return None

        definition = self.definitions.get(instance.workflow_id)
        if not definition:
            return None

        current_step: WorkflowStep | None = None
        for step in definition.steps:
            if step.step_id == instance.current_step:
                current_step = step
                break

        if not current_step:
            return None

        current_step.status = StepStatus.RUNNING

        try:
            if step_executor is not None:
                result = step_executor(current_step, instance.variables)
            elif current_step.action in self.executors:
                result = self.executors[current_step.action](current_step, instance.variables)
            else:
                result = self._default_step_executor(current_step, instance.variables)

            current_step.result = result
            current_step.status = StepStatus.COMPLETED
            instance.completed_steps.append(current_step.step_id)

            if len(instance.completed_steps) % self.checkpoint_interval == 0:
                self._save_checkpoint(instance, current_step)

            next_step = self._get_next_step(definition, current_step)
            if next_step:
                instance.current_step = next_step.step_id
            else:
                instance.status = WorkflowStatus.COMPLETED
                instance.completed_at = datetime.now().isoformat()

        except (RuntimeError, ValueError, AttributeError, TypeError) as e:
            current_step.status = StepStatus.FAILED
            current_step.error = str(e)
            instance.failed_steps.append(current_step.step_id)
            instance.error = str(e)
            logger.warning("Step %s failed: %s", current_step.step_id, e)

        return current_step

    def _default_step_executor(self, step: WorkflowStep, _variables: dict[str, Any]) -> Any:
        if self.dispatcher:
            result = self.dispatcher.dispatch(
                task_description=step.description,
                roles=[step.role_id],
            )
            return {"dispatch_success": result.success, "summary": getattr(result, "summary", "")[:200]}
        return {"action": step.action, "role": step.role_id, "status": "mock_completed"}

    def _get_next_step(self, definition: WorkflowDefinition, current_step: WorkflowStep) -> WorkflowStep | None:
        found_current = False
        for step in definition.steps:
            if found_current:
                return step
            if step.step_id == current_step.step_id:
                found_current = True
        return None
