#!/usr/bin/env python3
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from .checkpoint_manager import CheckpointManager, HandoffDocument

logger = logging.getLogger(__name__)


class WorkflowStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    WAITING_HANDOVER = "waiting_handover"


class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class NodeType(Enum):
    """V3.8: Classification of workflow step execution semantics.

    - ``DETERMINISTIC``: Pure logic / no LLM call (e.g. data transforms,
      file I/O, rule checks). Output is fully reproducible.
    - ``LLM``: Step whose primary work is an LLM call (e.g. requirements
      analysis, architecture design, code review).
    - ``HYBRID``: Mix of deterministic and LLM work (default — preserves
      backward compatibility for steps created without annotation).
    """

    DETERMINISTIC = "deterministic"
    LLM = "llm"
    HYBRID = "hybrid"


@dataclass
class WorkflowStep:
    step_id: str = field(default_factory=lambda: f"step-{uuid.uuid4().hex[:6]}")
    name: str = ""
    description: str = ""
    role_id: str = ""
    action: str = ""
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    conditions: dict[str, Any] = field(default_factory=dict)
    timeout: int = 3600
    retry_count: int = 3
    status: StepStatus = StepStatus.PENDING
    result: Any = None
    error: str = ""
    dependencies: list[str] = field(default_factory=list)
    artifacts_in: str = ""
    artifacts_out: str = ""
    gate_condition: str = ""
    reviewers: list[str] = field(default_factory=list)
    optional: bool = False
    skip_reason: str = ""
    # V3.8 #6: Deterministic vs LLM step separation.
    # Defaults to HYBRID for backward compatibility — existing steps
    # created without an explicit node_type are treated as mixed.
    node_type: NodeType = NodeType.HYBRID

    def to_dict(self) -> dict[str, Any]:
        """Serialize the workflow step to a dictionary.

        Returns:
            Dictionary containing all step fields with `status` and
            `node_type` converted to their string values.
        """
        d = {
            "step_id": self.step_id,
            "name": self.name,
            "description": self.description,
            "role_id": self.role_id,
            "action": self.action,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "conditions": self.conditions,
            "timeout": self.timeout,
            "retry_count": self.retry_count,
            "status": self.status.value if isinstance(self.status, StepStatus) else self.status,
            "result": self.result,
            "error": self.error,
            "dependencies": self.dependencies,
            "artifacts_in": self.artifacts_in,
            "artifacts_out": self.artifacts_out,
            "gate_condition": self.gate_condition,
            "reviewers": self.reviewers,
            "optional": self.optional,
            "skip_reason": self.skip_reason,
            "node_type": self.node_type.value
            if isinstance(self.node_type, NodeType)
            else self.node_type,
        }
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkflowStep":
        """Reconstruct a WorkflowStep from a serialized dictionary.

        Args:
            data: Dict produced by `to_dict`. The `status` field, if a
                string, is converted back to a `StepStatus` enum; invalid
                values fall back to `PENDING`. The `node_type` field, if
                a string, is converted back to a `NodeType` enum; invalid
                or missing values fall back to `HYBRID` (backward compat).

        Returns:
            A new WorkflowStep instance populated from `data`.
        """
        data_copy = dict(data)
        if isinstance(data_copy.get("status"), str):
            try:
                data_copy["status"] = StepStatus(data_copy["status"])
            except ValueError:
                data_copy["status"] = StepStatus.PENDING
        if isinstance(data_copy.get("node_type"), str):
            try:
                data_copy["node_type"] = NodeType(data_copy["node_type"])
            except ValueError:
                data_copy["node_type"] = NodeType.HYBRID
        elif "node_type" not in data_copy:
            data_copy["node_type"] = NodeType.HYBRID
        return cls(**data_copy)

    def is_deterministic(self) -> bool:
        """Return True if this step is purely deterministic (no LLM call)."""
        return self.node_type == NodeType.DETERMINISTIC

    def is_llm(self) -> bool:
        """Return True if this step's primary work is an LLM call."""
        return self.node_type == NodeType.LLM

    @property
    def requires_llm(self) -> bool:
        """V3.8 #6: Return True if this step requires an LLM call.

        Both ``NodeType.LLM`` and ``NodeType.HYBRID`` steps involve at
        least one LLM call, so they return ``True``. Pure
        ``NodeType.DETERMINISTIC`` steps return ``False`` — useful for
        cost estimation and for skipping LLM backends during execution.
        """
        return self.node_type in (NodeType.LLM, NodeType.HYBRID)


@dataclass
class RequirementChange:
    change_id: str = field(default_factory=lambda: f"cr-{uuid.uuid4().hex[:6]}")
    description: str = ""
    reason: str = ""
    requested_by: str = ""
    impact_analysis: dict[str, Any] = field(default_factory=dict)
    affected_phases: list[str] = field(default_factory=list)
    review_result: str = "pending"
    rollback_to: str = ""


@dataclass
class WorkflowDefinition:
    workflow_id: str = field(default_factory=lambda: f"wf-{uuid.uuid4().hex[:8]}")
    name: str = ""
    description: str = ""
    steps: list[WorkflowStep] = field(default_factory=list)
    variables: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Serialize the workflow definition to a dictionary.

        Returns:
            Dictionary containing workflow_id, name, description, serialized
            steps, variables, metadata, and created_at.
        """
        return {
            "workflow_id": self.workflow_id,
            "name": self.name,
            "description": self.description,
            "steps": [s.to_dict() for s in self.steps],
            "variables": self.variables,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }


@dataclass
class WorkflowInstance:
    instance_id: str = field(default_factory=lambda: f"inst-{uuid.uuid4().hex[:8]}")
    workflow_id: str = ""
    status: WorkflowStatus = WorkflowStatus.PENDING
    current_step: str | None = None
    completed_steps: list[str] = field(default_factory=list)
    failed_steps: list[str] = field(default_factory=list)
    variables: dict[str, Any] = field(default_factory=dict)
    results: dict[str, Any] = field(default_factory=dict)
    started_at: str | None = None
    completed_at: str | None = None
    error: str = ""
    checkpoint_id: str | None = None
    current_agent_id: str | None = None
    handoff_history: list[str] = field(default_factory=list)


class WorkflowEngine:
    """
    Simplified workflow engine for DevSquad.

    Integrates with:
    - CheckpointManager for state persistence
    - Coordinator for task execution
    - Dispatcher for role-based dispatching

    Features:
    1. Task-to-workflow auto-splitting
    2. Step-by-step execution with checkpointing
    3. Agent handoff support
    4. Resume from checkpoint
    """

    def __init__(self, storage_path: str = "./workflows", coordinator: Any = None, dispatcher: Any = None) -> None:
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.definitions: dict[str, WorkflowDefinition] = {}
        self.instances: dict[str, WorkflowInstance] = {}
        self.executors: dict[str, Callable] = {}

        self.coordinator = coordinator
        self.dispatcher = dispatcher
        self.checkpoint_manager = CheckpointManager(storage_path=str(self.storage_path / "checkpoints"))
        self.checkpoint_interval = 2

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
        steps = []
        task_text = f"{task_title} {task_description}".lower()

        is_architecture = any(kw in task_text for kw in ["architecture", "design", "system", "架构", "设计"])
        is_ui_design = any(kw in task_text for kw in ["ui", "interface", "frontend", "界面", "交互"])
        is_development = any(kw in task_text for kw in ["develop", "implement", "code", "开发", "实现", "编码"])
        is_testing = any(kw in task_text for kw in ["test", "verify", "quality", "测试", "验证"])
        is_product = any(kw in task_text for kw in ["requirement", "product", "prd", "需求", "产品"])
        is_deployment = any(kw in task_text for kw in ["deploy", "release", "ci/cd", "部署", "发布"])
        is_security = any(kw in task_text for kw in ["security", "auth", "vulnerability", "安全", "认证"])

        step_id = 1

        if is_product or is_architecture:
            steps.append(
                WorkflowStep(
                    step_id=f"step_{step_id}",
                    name="Requirements Analysis",
                    description="Analyze task requirements and create detailed specification",
                    role_id="product-manager",
                    action="analyze_requirements",
                )
            )
            step_id += 1

        if is_architecture:
            steps.append(
                WorkflowStep(
                    step_id=f"step_{step_id}",
                    name="Architecture Design",
                    description="Design system architecture and technology selection",
                    role_id="architect",
                    action="design_architecture",
                )
            )
            step_id += 1

        if is_security:
            steps.append(
                WorkflowStep(
                    step_id=f"step_{step_id}",
                    name="Security Review",
                    description="Review security implications and recommend protections",
                    role_id="security",
                    action="security_review",
                )
            )
            step_id += 1

        if is_ui_design:
            steps.append(
                WorkflowStep(
                    step_id=f"step_{step_id}",
                    name="UI Design",
                    description="Design user interface and interaction flow",
                    role_id="ui-designer",
                    action="design_ui",
                )
            )
            step_id += 1

        if is_testing:
            steps.append(
                WorkflowStep(
                    step_id=f"step_{step_id}",
                    name="Test Design",
                    description="Create test strategy and test cases",
                    role_id="tester",
                    action="design_tests",
                )
            )
            step_id += 1

        if is_development:
            steps.append(
                WorkflowStep(
                    step_id=f"step_{step_id}",
                    name="Development",
                    description="Implement feature code",
                    role_id="solo-coder",
                    action="develop",
                )
            )
            step_id += 1

        if is_testing and is_development:
            steps.append(
                WorkflowStep(
                    step_id=f"step_{step_id}",
                    name="Test Execution",
                    description="Execute test cases and verify functionality",
                    role_id="tester",
                    action="execute_tests",
                )
            )
            step_id += 1

        if is_deployment:
            steps.append(
                WorkflowStep(
                    step_id=f"step_{step_id}",
                    name="Deployment",
                    description="Deploy and release the system",
                    role_id="devops",
                    action="deploy",
                )
            )

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

        current_step = None
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

        affected = []
        for step in definition.steps:
            if step.step_id not in instance.completed_steps:
                affected.append(step.step_id)

        earliest = None
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
        if workflow_id is None:
            if not self.definitions:
                return {
                    "total": 0,
                    "deterministic": 0,
                    "llm": 0,
                    "hybrid": 0,
                    "deterministic_pct": 0.0,
                    "llm_pct": 0.0,
                    "hybrid_pct": 0.0,
                    "by_step": [],
                }
            workflow_id = next(reversed(self.definitions))

        definition = self.definitions.get(workflow_id)
        if not definition:
            return {
                "total": 0,
                "deterministic": 0,
                "llm": 0,
                "hybrid": 0,
                "deterministic_pct": 0.0,
                "llm_pct": 0.0,
                "hybrid_pct": 0.0,
                "by_step": [],
            }

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


PHASE_TEMPLATES: dict[str, dict[str, Any]] = {
    "P1": {
        "name": "Requirements Analysis",
        "description": "Analyze task requirements and create detailed specification",
        "role_id": "product-manager",
        "action": "analyze_requirements",
        "dependencies": [],
        "artifacts_in": "User raw requirements",
        "artifacts_out": "User stories, acceptance criteria, priority matrix, NFRs",
        "gate_condition": "Acceptance criteria quantifiable and unambiguous",
        "reviewers": ["architect", "tester", "security", "ui-designer"],
        "optional": False,
        "node_type": "llm",
    },
    "P2": {
        "name": "Architecture Design",
        "description": "Design system architecture and technology selection",
        "role_id": "architect",
        "action": "design_architecture",
        "dependencies": ["P1"],
        "artifacts_in": "P1 deliverables",
        "artifacts_out": "Architecture proposal, tech selection, service boundaries, quality attributes",
        "gate_condition": "Architecture passes weighted consensus (>=70%)",
        "reviewers": ["product-manager", "security", "devops"],
        "optional": False,
        "node_type": "llm",
    },
    "P3": {
        "name": "Technical Design",
        "description": "Detail architecture into developable technical specs",
        "role_id": "architect",
        "action": "design_technical",
        "dependencies": ["P2"],
        "artifacts_in": "P2 deliverables",
        "artifacts_out": "API specs, interface definitions, tech constraints, tech risk assessment",
        "gate_condition": "API specs unambiguous",
        "reviewers": ["solo-coder", "tester"],
        "optional": False,
        "node_type": "llm",
    },
    "P4": {
        "name": "Data Design",
        "description": "Design data storage models and migration plans",
        "role_id": "architect",
        "action": "design_data",
        "dependencies": ["P2"],
        "artifacts_in": "P2 deliverables (+ P3 if available)",
        "artifacts_out": "Data model (ER), table structure, index strategy, migration plan",
        "gate_condition": "Data model 3NF or denormalization justified",
        "reviewers": ["architect", "security"],
        "optional": True,
        "node_type": "hybrid",
    },
    "P5": {
        "name": "Interaction Design",
        "description": "Design user interaction flows and information architecture",
        "role_id": "ui-designer",
        "action": "design_interaction",
        "dependencies": ["P1", "P3"],
        "artifacts_in": "P1 + P3 deliverables",
        "artifacts_out": "Interaction flows, information architecture, prototype, accessibility checklist",
        "gate_condition": "Core flow usability verified",
        "reviewers": ["product-manager", "tester", "security"],
        "optional": True,
        "node_type": "llm",
    },
    "P6": {
        "name": "Security Review",
        "description": "Review security implications and compliance",
        "role_id": "security",
        "action": "security_review",
        "dependencies": ["P2", "P3"],
        "artifacts_in": "P2 + P3 deliverables (+ P4, P5 if exist)",
        "artifacts_out": "Threat model, vulnerability list, compliance report, security fixes",
        "gate_condition": "No P0/P1 vulnerabilities, compliance green",
        "reviewers": ["architect", "devops"],
        "optional": True,
        "node_type": "hybrid",
    },
    "P7": {
        "name": "Test Planning",
        "description": "Plan all test dimensions before development",
        "role_id": "tester",
        "action": "plan_tests",
        "dependencies": ["P1", "P3"],
        "artifacts_in": "P1 + P3 deliverables (+ P6 if exists)",
        "artifacts_out": "Test plan (10 dimensions: functional/integration/performance/security/env/install/regression/acceptance/ui-interaction/user-journey)",
        "gate_condition": "Test plan review passed",
        "reviewers": ["architect", "security", "devops", "product-manager"],
        "optional": False,
        "node_type": "llm",
    },
    "P8": {
        "name": "Implementation",
        "description": "Implement feature code with testability",
        "role_id": "solo-coder",
        "action": "develop",
        "dependencies": ["P3", "P7"],
        "artifacts_in": "P3 + P6 (if exists) + P7 deliverables",
        "artifacts_out": "Runnable code, code review report, unit tests, testability notes",
        "gate_condition": "Code review passed, no P0 defects",
        "reviewers": ["architect", "security", "tester", "solo-coder"],
        "optional": False,
        "node_type": "hybrid",
    },
    "P9": {
        "name": "Test Execution",
        "description": "Execute all test dimensions per P7 plan",
        "role_id": "tester",
        "action": "execute_tests",
        "dependencies": ["P7", "P8"],
        "artifacts_in": "P7 + P8 deliverables",
        "artifacts_out": "Full test report, defect list",
        "gate_condition": "Coverage>=80% + P7 plan 100% executed + no P0 defects",
        "reviewers": ["architect", "product-manager", "security", "devops"],
        "optional": False,
        "node_type": "deterministic",
    },
    "P10": {
        "name": "Deployment & Release",
        "description": "Deploy and release the system to production",
        "role_id": "devops",
        "action": "deploy",
        "dependencies": ["P9"],
        "artifacts_in": "P9 deliverables",
        "artifacts_out": "Deployment plan, release strategy, rollback plan, release checklist, IaC",
        "gate_condition": "Deployment drill passed, rollback verified",
        "reviewers": ["architect", "security", "tester"],
        "optional": False,
        "node_type": "deterministic",
    },
    "P11": {
        "name": "Operations & Assurance",
        "description": "Ensure system runs stably in production",
        "role_id": "devops",
        "action": "operate",
        "dependencies": ["P10"],
        "artifacts_in": "P10 deliverables",
        "artifacts_out": "Monitoring dashboards, alert rules, incident response plans, performance baselines",
        "gate_condition": "P99<target, alert coverage 100%",
        "reviewers": ["architect", "devops"],
        "optional": True,
        "node_type": "deterministic",
    },
}

LIFECYCLE_TEMPLATES: dict[str, list[str]] = {
    "full": ["P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9", "P10", "P11"],
    "backend": ["P1", "P2", "P3", "P4", "P6", "P7", "P8", "P9", "P10", "P11"],
    "frontend": ["P1", "P2", "P3", "P5", "P7", "P8", "P9", "P10", "P11"],
    "internal_tool": ["P1", "P2", "P3", "P7", "P8", "P9", "P10"],
    "minimal": ["P1", "P3", "P7", "P8", "P9"],
}
