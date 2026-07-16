"""Lifecycle creation mixin for WorkflowEngine.

Extracts workflow / lifecycle creation and change-request handling so the
main engine file can focus on initialization and orchestration.

Responsibilities (from IMPROVEMENT_PLAN_V3.9.2.md P2-3):
    - Task-to-workflow auto-splitting (keyword-based step generation)
    - Predefined lifecycle template instantiation (PHASE_TEMPLATES /
      LIFECYCLE_TEMPLATES)
    - Requirement change-request submission with affected-phase analysis
"""

from __future__ import annotations

import logging

from .workflow_engine_base import (
    LIFECYCLE_TEMPLATES,
    PHASE_TEMPLATES,
    NodeType,
    RequirementChange,
    WorkflowDefinition,
    WorkflowEngineBase,
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
