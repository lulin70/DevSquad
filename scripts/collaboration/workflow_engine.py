#!/usr/bin/env python3
"""
WorkflowEngine - Simplified workflow engine for DevSquad.

Integrates with:
- CheckpointManager for state persistence
- Coordinator for task execution
- Dispatcher for role-based dispatching

Features:
1. Task-to-workflow auto-splitting
2. Step-by-step execution with checkpointing
3. Agent handoff support
4. Resume from checkpoint

Implementation notes:
    - This module is a facade. The class body keeps only ``__init__``.
    - Auxiliary concerns are split into single-responsibility mixins under
      ``workflow_engine_*_mixin.py`` and the shared structural base /
      data classes in ``workflow_engine_base.py`` (same package).
    - Public API (``WorkflowEngine``, ``WorkflowStatus``, ``StepStatus``,
      ``NodeType``, ``WorkflowStep``, ``WorkflowDefinition``,
      ``WorkflowInstance``, ``RequirementChange``, ``PHASE_TEMPLATES``,
      ``LIFECYCLE_TEMPLATES``) remains importable from this module for
      backward compatibility.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from .checkpoint_manager import CheckpointManager
from .workflow_engine_base import (
    LIFECYCLE_TEMPLATES,
    PHASE_TEMPLATES,
    NodeType,
    RequirementChange,
    StepStatus,
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowStatus,
    WorkflowStep,
)
from .workflow_engine_lifecycle_mixin import WorkflowEngineLifecycleMixin
from .workflow_engine_persistence_mixin import WorkflowEnginePersistenceMixin
from .workflow_engine_state_mixin import WorkflowEngineStateMixin
from .workflow_engine_transition_mixin import WorkflowEngineTransitionMixin

# Re-export public API symbols for backward compatibility.
# All symbols imported above are intentionally re-exported so that
# ``from .workflow_engine import X`` keeps working after the split.
__all__ = [
    "LIFECYCLE_TEMPLATES",
    "NodeType",
    "PHASE_TEMPLATES",
    "RequirementChange",
    "StepStatus",
    "WorkflowDefinition",
    "WorkflowEngine",
    "WorkflowInstance",
    "WorkflowStatus",
    "WorkflowStep",
]


class WorkflowEngine(
    WorkflowEngineLifecycleMixin,
    WorkflowEngineTransitionMixin,
    WorkflowEnginePersistenceMixin,
    WorkflowEngineStateMixin,
):
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
        self.executors: dict[str, Callable[..., Any]] = {}

        self.coordinator = coordinator
        self.dispatcher = dispatcher
        # Pass the base storage_path; CheckpointManager creates the
        # checkpoints/ and handoffs/ subdirs itself (avoids nesting like
        # workflows/checkpoints/checkpoints).
        self.checkpoint_manager = CheckpointManager(storage_path=str(self.storage_path))
        self.checkpoint_interval = 2
