"""Shared base for WorkflowEngine and its mixins.

Declares the workflow enums (``WorkflowStatus``, ``StepStatus``,
``NodeType``), data classes (``WorkflowStep``, ``RequirementChange``,
``WorkflowDefinition``, ``WorkflowInstance``), the lifecycle template
constants (``PHASE_TEMPLATES``, ``LIFECYCLE_TEMPLATES``), and the
:class:`WorkflowEngineBase` structural class so that the split
WorkflowEngine mixins can be type-checked by mypy without heavy casts or
``# type: ignore`` comments.

Public symbols are re-exported by :mod:`scripts.collaboration.workflow_engine`
for backward compatibility.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from .checkpoint_manager import CheckpointManager, HandoffDocument


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
    def from_dict(cls, data: dict[str, Any]) -> WorkflowStep:
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


# ============================================================
# Lifecycle Template Constants
# ============================================================

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


# ============================================================
# Structural Base
# ============================================================


class WorkflowEngineBase:
    """Structural base for WorkflowEngine mixins.

    Attributes are declared as class-level annotations; concrete values are
    assigned by ``WorkflowEngine.__init__``. Mixins reference these
    attributes so that they can be type-checked by mypy without casts.
    Method stubs are provided for cross-mixin calls; concrete
    implementations live in the individual mixins.
    """

    # Instance state assigned by WorkflowEngine.__init__
    storage_path: Path
    definitions: dict[str, WorkflowDefinition]
    instances: dict[str, WorkflowInstance]
    executors: dict[str, Callable[..., Any]]
    coordinator: Any
    dispatcher: Any
    checkpoint_manager: CheckpointManager
    checkpoint_interval: int

    # --- Method stubs implemented by mixins ---

    def _save_checkpoint(self, instance: WorkflowInstance, current_step: WorkflowStep) -> None:
        """Persist a checkpoint for the instance (implemented by persistence mixin)."""
        raise NotImplementedError

    def classify_steps(self, workflow_id: str | None = None) -> dict[str, Any]:
        """Classify workflow steps by node_type (implemented by state mixin)."""
        raise NotImplementedError


# Re-export HandoffDocument so mixins importing from this base can access it
# without reaching back into checkpoint_manager directly. Kept here to mirror
# the original module's public surface and avoid import churn in mixins.
__all__ = [
    "HandoffDocument",
    "LIFECYCLE_TEMPLATES",
    "NodeType",
    "PHASE_TEMPLATES",
    "RequirementChange",
    "StepStatus",
    "WorkflowDefinition",
    "WorkflowEngineBase",
    "WorkflowInstance",
    "WorkflowStatus",
    "WorkflowStep",
]
