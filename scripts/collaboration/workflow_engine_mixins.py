"""Merged WorkflowEngine mixins.

This module is the V4.1.2 Phase 3 Wave 3 consolidation of the following 4
previously-separate mixin files:

- ``workflow_engine_lifecycle_mixin.py``     -> ``WorkflowEngineLifecycleMixin``
- ``workflow_engine_persistence_mixin.py``   -> ``WorkflowEnginePersistenceMixin``
- ``workflow_engine_state_mixin.py``         -> ``WorkflowEngineStateMixin``
- ``workflow_engine_transition_mixin.py``    -> ``WorkflowEngineTransitionMixin``

The original files have been converted to thin shims that re-export from this
module for backward compatibility; they will be deleted in V4.2.0.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

from .workflow_engine_base import (
    LIFECYCLE_TEMPLATES,
    PHASE_TEMPLATES,
    HandoffDocument,
    NodeType,
    RequirementChange,
    StepStatus,
    WorkflowDefinition,
    WorkflowEngineBase,
    WorkflowInstance,
    WorkflowStatus,
    WorkflowStep,
)

logger = logging.getLogger(__name__)


class WorkflowEngineLifecycleMixin(WorkflowEngineBase):
    """Provides workflow/lifecycle creation and change-request handling."""

    def create_workflow_from_task(
        self,
        task_title: str,
        task_description: str = "",
        target_agent: str | None = None,
    ) -> WorkflowDefinition:
        """
        Create a workflow from a task description.

        Automatically splits the task into steps based on keyword analysis.
        """
        steps = self._split_task_into_steps(task_title, task_description, target_agent)

        definition = WorkflowDefinition(
            name=task_title,
            description=task_description,
            steps=steps,
            metadata={
                "target_agent": target_agent,
                "created_by": "WorkflowEngine",
            },
        )

        self.definitions[definition.workflow_id] = definition
        logger.info("Workflow created: %s (%d steps)", definition.workflow_id, len(steps))
        return definition

    def _split_task_into_steps(
        self, task_title: str, task_description: str, target_agent: str | None = None
    ) -> list[WorkflowStep]:
        task_text = f"{task_title} {task_description}".lower()
        kinds = self._detect_task_kinds(task_text)

        steps = self._build_steps_for_kinds(kinds)

        if not steps:
            steps.append(
                WorkflowStep(
                    step_id="step_1",
                    name="Task Execution",
                    description=task_description or task_title,
                    role_id=target_agent or "solo-coder",
                    action="execute",
                )
            )

        return steps

    @staticmethod
    def _detect_task_kinds(task_text: str) -> dict[str, bool]:
        """Detect which task categories are implied by the task text."""
        return {
            "architecture": any(kw in task_text for kw in ["architecture", "design", "system", "架构", "设计"]),
            "ui_design": any(kw in task_text for kw in ["ui", "interface", "frontend", "界面", "交互"]),
            "development": any(kw in task_text for kw in ["develop", "implement", "code", "开发", "实现", "编码"]),
            "testing": any(kw in task_text for kw in ["test", "verify", "quality", "测试", "验证"]),
            "product": any(kw in task_text for kw in ["requirement", "product", "prd", "需求", "产品"]),
            "deployment": any(kw in task_text for kw in ["deploy", "release", "ci/cd", "部署", "发布"]),
            "security": any(kw in task_text for kw in ["security", "auth", "vulnerability", "安全", "认证"]),
        }

    @staticmethod
    def _build_steps_for_kinds(kinds: dict[str, bool]) -> list[WorkflowStep]:
        """Build the ordered workflow steps triggered by the detected task kinds.

        Each spec is ``(required_kinds, mode, step_fields)`` where ``mode`` is
        ``"any"`` (triggered when any of the kinds is set) or ``"all"``
        (triggered only when all of the kinds are set).
        """
        specs: list[tuple[list[str], str, tuple[str, str, str, str]]] = [
            (["product", "architecture"], "any", ("Requirements Analysis", "Analyze task requirements and create detailed specification", "product-manager", "analyze_requirements")),
            (["architecture"], "any", ("Architecture Design", "Design system architecture and technology selection", "architect", "design_architecture")),
            (["security"], "any", ("Security Review", "Review security implications and recommend protections", "security", "security_review")),
            (["ui_design"], "any", ("UI Design", "Design user interface and interaction flow", "ui-designer", "design_ui")),
            (["testing"], "any", ("Test Design", "Create test strategy and test cases", "tester", "design_tests")),
            (["development"], "any", ("Development", "Implement feature code", "solo-coder", "develop")),
            (["testing", "development"], "all", ("Test Execution", "Execute test cases and verify functionality", "tester", "execute_tests")),
            (["deployment"], "any", ("Deployment", "Deploy and release the system", "devops", "deploy")),
        ]
        steps: list[WorkflowStep] = []
        step_id = 1
        for required, mode, (name, description, role_id, action) in specs:
            triggered = all(kinds[k] for k in required) if mode == "all" else any(kinds[k] for k in required)
            if not triggered:
                continue
            steps.append(
                WorkflowStep(
                    step_id=f"step_{step_id}",
                    name=name,
                    description=description,
                    role_id=role_id,
                    action=action,
                )
            )
            step_id += 1
        return steps

    def create_lifecycle(self, template_name: str = "full") -> WorkflowDefinition:
        """
        Create a workflow from a predefined lifecycle template.

        Available templates: full, backend, frontend, internal_tool, minimal
        """
        if template_name not in LIFECYCLE_TEMPLATES:
            raise ValueError(f"Unknown template: {template_name}. Available: {list(LIFECYCLE_TEMPLATES.keys())}")

        phase_ids = LIFECYCLE_TEMPLATES[template_name]
        steps = []
        for pid in phase_ids:
            pt = PHASE_TEMPLATES[pid]
            # V3.8 #6: propagate node_type annotation from template.
            # Falls back to HYBRID when template omits the field.
            node_type_value = pt.get("node_type", "hybrid")
            try:
                node_type = NodeType(node_type_value)
            except ValueError:
                node_type = NodeType.HYBRID
            steps.append(
                WorkflowStep(
                    step_id=pid,
                    name=pt["name"],
                    description=pt["description"],
                    role_id=pt["role_id"],
                    action=pt["action"],
                    dependencies=pt["dependencies"],
                    artifacts_in=pt["artifacts_in"],
                    artifacts_out=pt["artifacts_out"],
                    gate_condition=pt["gate_condition"],
                    reviewers=pt["reviewers"],
                    optional=pt["optional"],
                    node_type=node_type,
                )
            )

        definition = WorkflowDefinition(
            name=f"lifecycle-{template_name}",
            description=f"DevSquad V3.8 {template_name} lifecycle ({len(steps)} phases)",
            steps=steps,
            metadata={"template": template_name, "lifecycle_version": "3.8.0"},
        )
        self.definitions[definition.workflow_id] = definition
        logger.info("Lifecycle workflow created: %s (%s, %d phases)", definition.workflow_id, template_name, len(steps))
        return definition

    def submit_change_request(
        self,
        instance_id: str,
        description: str,
        reason: str,
        requested_by: str = "user",
    ) -> RequirementChange | None:
        """
        Submit a requirement change request for a running workflow.

        Returns impact analysis and affected phases.
        """
        instance = self.instances.get(instance_id)
        if not instance:
            return None

        if instance.status not in (WorkflowStatus.RUNNING, WorkflowStatus.PAUSED):
            logger.warning(
                "Cannot submit change request for instance %s with status %s", instance_id, instance.status.value
            )
            return None

        definition = self.definitions.get(instance.workflow_id)
        if not definition:
            return None

        affected: list[str] = []
        for step in definition.steps:
            if step.step_id not in instance.completed_steps:
                affected.append(step.step_id)

        earliest: str | None = None
        for step in definition.steps:
            if step.step_id not in instance.completed_steps:
                earliest = step.step_id
                break

        sanitized_desc = description[:500]
        sanitized_reason = reason[:500]
        sanitized_by = requested_by[:100]

        change_request = RequirementChange(
            description=sanitized_desc,
            reason=sanitized_reason,
            requested_by=sanitized_by,
            affected_phases=affected,
            rollback_to=earliest or "",
        )

        logger.info("Change request submitted: %s (rollback_to=%s)", change_request.change_id, earliest)
        return change_request


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
