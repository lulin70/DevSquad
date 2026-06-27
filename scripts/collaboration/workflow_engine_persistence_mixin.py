"""Persistence mixin for WorkflowEngine.

Extracts checkpoint creation, checkpoint-based resume, and agent handoff
so the main engine file can focus on initialization and orchestration.

Responsibilities (from IMPROVEMENT_PLAN_V3.9.2.md P2-3):
    - Checkpoint creation from current instance state
    - Resume a workflow instance from its last checkpoint
    - Agent handoff document creation and persistence
"""

from __future__ import annotations

import logging

from .workflow_engine_base import (
    HandoffDocument,
    WorkflowEngineBase,
    WorkflowInstance,
    WorkflowStatus,
    WorkflowStep,
)

logger = logging.getLogger(__name__)


class WorkflowEnginePersistenceMixin(WorkflowEngineBase):
    """Provides checkpoint persistence, resume, and agent handoff."""

    def _save_checkpoint(self, instance: WorkflowInstance, current_step: WorkflowStep) -> None:
        definition = self.definitions.get(instance.workflow_id)
        all_step_ids = [s.step_id for s in (definition.steps if definition else [])]
        remaining = [
            sid for sid in all_step_ids if sid not in instance.completed_steps and sid not in instance.failed_steps
        ]

        checkpoint = self.checkpoint_manager.create_checkpoint_from_dispatch(
            task_id=instance.instance_id,
            step_name=current_step.name,
            agent_id=current_step.role_id,
            completed_steps=instance.completed_steps,
            remaining_steps=remaining,
            context=instance.variables,
            outputs=instance.results,
        )
        instance.checkpoint_id = checkpoint.checkpoint_id

    def resume_from_checkpoint(self, instance_id: str) -> WorkflowInstance | None:
        """Restore a workflow instance's state from its last checkpoint.

        Args:
            instance_id: Identifier of the workflow instance.

        Returns:
            The restored WorkflowInstance with completed_steps, variables,
            results, and current_step updated from the checkpoint. Returns
            None if the instance is not found; returns the instance
            unchanged if no checkpoint exists or loading fails.
        """
        instance = self.instances.get(instance_id)
        if not instance:
            return None

        if not instance.checkpoint_id:
            logger.warning("No checkpoint found for instance: %s", instance_id)
            return instance

        checkpoint = self.checkpoint_manager.load_checkpoint(instance.checkpoint_id)
        if not checkpoint:
            logger.warning("Failed to load checkpoint: %s", instance.checkpoint_id)
            return instance

        instance.completed_steps = checkpoint.completed_steps
        instance.variables = checkpoint.context_snapshot
        instance.results = checkpoint.outputs

        if checkpoint.remaining_steps:
            instance.current_step = checkpoint.remaining_steps[0]
            instance.status = WorkflowStatus.RUNNING
        else:
            instance.status = WorkflowStatus.COMPLETED

        logger.info("Resumed instance %s from checkpoint %s", instance_id, instance.checkpoint_id)
        return instance

    def handoff(self, instance_id: str, from_agent: str, to_agent: str, reason: str = "") -> HandoffDocument | None:
        """Create and persist a handoff document between agents.

        Args:
            instance_id: Identifier of the workflow instance.
            from_agent: Identifier of the agent handing off.
            to_agent: Identifier of the receiving agent.
            reason: Optional reason for the handoff.

        Returns:
            The created HandoffDocument, or None when the instance is not
            found.
        """
        instance = self.instances.get(instance_id)
        if not instance:
            return None

        definition = self.definitions.get(instance.workflow_id)
        all_step_ids = [s.step_id for s in (definition.steps if definition else [])]
        remaining = [sid for sid in all_step_ids if sid not in instance.completed_steps]

        handoff = HandoffDocument(
            task_id=instance_id,
            from_agent=from_agent,
            to_agent=to_agent,
            completed_work=[f"Completed step: {sid}" for sid in instance.completed_steps],
            current_state=instance.variables,
            next_steps=remaining,
            handoff_reason=reason or "agent_handoff",
        )

        self.checkpoint_manager.save_handoff(handoff)
        instance.handoff_history.append(handoff.handoff_id)
        instance.current_agent_id = to_agent

        logger.info("Handoff: %s -> %s for instance %s", from_agent, to_agent, instance_id)
        return handoff
