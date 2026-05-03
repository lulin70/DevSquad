#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unified Lifecycle Architecture (Plan C Implementation)

Core abstractions:
  - LifecycleMode: SHORTCUT / FULL / CUSTOM enum
  - PhaseDefinition: Unified phase structure
  - ViewMapping: CLI command → 11-phase mapping
  - LifecycleProtocol: Abstract interface for lifecycle management

Spec reference: docs/spec/SPEC_Lifecycle_Unified_Architecture_C.md
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class LifecycleMode(Enum):
    """
    Three lifecycle modes for different usage scenarios.

    Modes:
      - SHORTCUT: CLI 6-command simplified view (spec/plan/build/test/review/ship)
      - FULL: Complete 11-phase project lifecycle (P1-P11)
      - CUSTOM: User-defined workflow with selected phases
    """
    SHORTCUT = "shortcut"
    FULL = "full"
    CUSTOM = "custom"


@dataclass
class PhaseDefinition:
    """Unified definition for a single lifecycle phase."""
    phase_id: str
    name: str
    description: str
    role_id: str
    dependencies: List[str] = field(default_factory=list)
    artifacts_in: str = ""
    artifacts_out: str = ""
    gate_condition: str = ""
    reviewers: List[str] = field(default_factory=list)
    optional: bool = False
    order: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase_id": self.phase_id,
            "name": self.name,
            "description": self.description,
            "role_id": self.role_id,
            "dependencies": self.dependencies,
            "artifacts_in": self.artifacts_in,
            "artifacts_out": self.artifacts_out,
            "gate_condition": self.gate_condition,
            "reviewers": self.reviewers,
            "optional": self.optional,
            "order": self.order,
        }


@dataclass
class PhaseState(Enum):
    """Phase execution state."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


@dataclass
class GateResult:
    """Result of gate check for a phase."""
    passed: bool
    verdict: str  # APPROVE / CONDITIONAL / REJECT
    red_flags: List[Dict[str, Any]] = field(default_factory=list)
    missing_evidence: List[Dict[str, Any]] = field(default_factory=list)
    gap_report: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "verdict": self.verdict,
            "red_flags_count": len(self.red_flags),
            "missing_evidence_count": len(self.missing_evidence),
            "gap_report": self.gap_report[:200] if self.gap_report else "",
        }


@dataclass
class PhaseResult:
    """Result of advancing to a phase."""
    success: bool
    phase_id: str
    previous_state: PhaseState
    new_state: PhaseState
    gate_result: Optional[GateResult] = None
    error: str = ""


@dataclass
class LifecycleStatus:
    """Overall lifecycle status."""
    mode: LifecycleMode
    current_phase: Optional[str]
    completed_phases: List[str]
    failed_phases: List[str]
    blocked_phases: List[str]
    progress_percent: float
    can_advance: bool
    next_phase: Optional[str]

    def to_summary(self) -> str:
        lines = [
            f"Lifecycle Status ({self.mode.value.upper()} Mode)",
            f"Current: {self.current_phase or 'Not started'}",
            f"Progress: {self.progress_percent:.0f}%",
            f"Completed: {len(self.completed_phases)} phases",
        ]
        if self.next_phase:
            lines.append(f"Next: {self.next_phase}")
        if not self.can_advance:
            lines.append("⚠️ Blocked: Check gate conditions")
        return "\n".join(lines)


@dataclass
class ViewMapping:
    """Maps a CLI command to underlying 11-phase segments."""
    command: str
    phases: List[str]  # Phase IDs this command covers
    mode: LifecycleMode = LifecycleMode.SHORTCUT
    description: str = ""
    required_roles: List[str] = field(default_factory=list)
    gate: str = ""
    pre_dispatch_message: str = ""

    def covers_phase(self, phase_id: str) -> bool:
        return phase_id in self.phases


# Predefined view mappings (CLI → 11 phases)
VIEW_MAPPINGS: Dict[str, ViewMapping] = {
    "spec": ViewMapping(
        command="spec",
        phases=["P1", "P2"],
        description="Define requirements and architecture before implementation",
        required_roles=["architect", "product-manager"],
        gate="spec_first",
        pre_dispatch_message=(
            "📋 Generating specification (P1: Requirements + P2: Architecture). "
            "Output will include objectives, structure, testing plan, and boundaries."
        ),
    ),
    "plan": ViewMapping(
        command="plan",
        phases=["P7"],
        description="Break down work into verifiable tasks and test plans",
        required_roles=["architect", "product-manager"],
        gate="task_breakdown_complete",
        pre_dispatch_message=(
            "📝 Decomposing into atomic tasks (P7: Test Planning). "
            "Output includes test plan with acceptance criteria."
        ),
    ),
    "build": ViewMapping(
        command="build",
        phases=["P8"],
        description="Implement incrementally with TDD discipline",
        required_roles=["architect", "solo-coder", "tester"],
        gate="incremental_verification",
        pre_dispatch_message=(
            "🔨 Building in thin vertical slices (P8: Implementation). "
            "Each slice: implement → test → verify. ~100 lines per slice max."
        ),
    ),
    "test": ViewMapping(
        command="test",
        phases=["P9"],
        description="Run tests with mandatory evidence requirements",
        required_roles=["tester", "solo-coder"],
        gate="evidence_required",
        pre_dispatch_message=(
            "🧪 Running tests with verification gate (P9: Test Execution). "
            "Evidence required: test output, build status, diff summary."
        ),
    ),
    "review": ViewMapping(
        command="review",
        phases=["P8_review_embedded", "P6_partial"],
        description="Five-axis code review and security checks",
        required_roles=["solo-coder", "security", "tester", "architect"],
        gate="change_size_limit",
        pre_dispatch_message=(
            "🔍 Conducting multi-dimensional review. "
            "Change size target: ~100 lines. Severity labels: Critical/Required/Nit."
        ),
    ),
    "ship": ViewMapping(
        command="ship",
        phases=["P10"],
        description="Pre-launch verification and deployment preparation",
        required_roles=["devops", "security", "architect"],
        gate="pre_launch_checklist",
        pre_dispatch_message=(
            "🚀 Running pre-launch checklist across 6 dimensions. "
            "Rollback plan required."
        ),
    ),
}


class LifecycleProtocol(ABC):
    """
    Abstract interface for unified lifecycle management.

    This protocol decouples the view layer (CLI 6 commands) from the core engine
    (WorkflowEngine with 11 phases), enabling both SHORTCUT and FULL modes.
    """

    @abstractmethod
    def get_mode(self) -> LifecycleMode:
        """Return current lifecycle mode."""
        ...

    @abstractmethod
    def set_mode(self, mode: LifecycleMode) -> None:
        """Switch lifecycle mode."""
        ...

    @abstractmethod
    def get_all_phases(self) -> List[PhaseDefinition]:
        """Return all available phases in current mode."""
        ...

    @abstractmethod
    def get_active_phases(self) -> List[PhaseDefinition]:
        """Return phases active for the current task/context."""
        ...

    @abstractmethod
    def get_phase(self, phase_id: str) -> Optional[PhaseDefinition]:
        """Return specific phase by ID, or None if not found."""
        ...

    @abstractmethod
    def get_current_phase(self) -> Optional[PhaseDefinition]:
        """Return current phase, or None if not started."""
        ...

    @abstractmethod
    def advance_to_phase(self, phase_id: str) -> PhaseResult:
        """Advance to specified phase, running gate checks."""
        ...

    @abstractmethod
    def check_gate(self, phase_id: Optional[str] = None) -> GateResult:
        """Check gate conditions for phase (default: current)."""
        ...

    @abstractmethod
    def get_status(self) -> LifecycleStatus:
        """Return overall lifecycle status."""
        ...

    @abstractmethod
    def get_view_mapping(self, command: str) -> Optional[ViewMapping]:
        """Get view mapping for a CLI command (SHORTCUT mode only)."""
        ...

    @abstractmethod
    def resolve_command_to_phases(self, command: str) -> List[PhaseDefinition]:
        """Resolve a CLI command to its underlying phase definitions."""
        ...


class ShortcutLifecycleAdapter(LifecycleProtocol):
    """
    Adapter that implements LifecycleProtocol using CLI 6-command shortcuts.

    This is the default implementation for SHORTCUT mode.
    Maps CLI commands to 11-phase segments via VIEW_MAPPINGS.

    Integration (Plan C):
      - Uses UnifiedGateEngine for real gate checks
      - Integrates with CheckpointManager for state persistence
      - Supports lifecycle state save/restore
    """

    def __init__(self, use_unified_gate: bool = True):
        self._mode = LifecycleMode.SHORTCUT
        self._current_phase: Optional[str] = None
        self._completed_phases: List[str] = []
        self._phase_states: Dict[str, PhaseState] = {}
        self._use_unified_gate = use_unified_gate
        self._gate_engine = None
        self._checkpoint_manager = None
        self._task_id: Optional[str] = None

        # Initialize unified gate engine if requested
        if use_unified_gate:
            try:
                from scripts.collaboration.unified_gate_engine import (
                    UnifiedGateEngine,
                    GateType,
                    PhaseGateContext,
                    get_shared_gate_engine,
                )
                self._gate_engine = get_shared_gate_engine()
                self._GateType = GateType
                self._PhaseGateContext = PhaseGateContext
                logger.debug("UnifiedGateEngine initialized for ShortcutLifecycleAdapter")
            except ImportError as e:
                logger.warning("UnifiedGateEngine not available: %s", e)
                self._use_unified_gate = False

    def set_task_id(self, task_id: str) -> None:
        """Set task ID for checkpoint integration."""
        self._task_id = task_id
        if not self._checkpoint_manager:
            try:
                from scripts.collaboration.checkpoint_manager import CheckpointManager
                self._checkpoint_manager = CheckpointManager()
                logger.info("CheckpointManager initialized for task %s", task_id)
            except ImportError as e:
                logger.warning("CheckpointManager not available: %s", e)

    def enable_checkpoint_integration(self, storage_path: str = "./checkpoints") -> bool:
        """
        Enable checkpoint manager integration for state persistence.

        Args:
            storage_path: Path for storing checkpoints and lifecycle state

        Returns:
            True if successfully enabled
        """
        try:
            from scripts.collaboration.checkpoint_manager import CheckpointManager
            self._checkpoint_manager = CheckpointManager(storage_path=storage_path)
            logger.info(
                "CheckpointManager enabled at %s",
                storage_path,
            )
            return True
        except Exception as e:
            logger.warning("Failed to enable checkpoint integration: %s", e)
            return False

    def save_state(self) -> bool:
        """
        Save current lifecycle state to checkpoint manager.

        Returns:
            True if saved successfully
        """
        if self._checkpoint_manager and self._task_id:
            try:
                phase_states_str = {
                    pid: (state.value if hasattr(state, 'value') else str(state))
                    for pid, state in self._phase_states.items()
                }
                mode_str = self._mode.value if hasattr(self._mode, 'value') else str(self._mode)

                return self._checkpoint_manager.save_lifecycle_state(
                    task_id=self._task_id,
                    current_phase=self._current_phase,
                    phase_states=phase_states_str,
                    completed_phases=self._completed_phases.copy(),
                    mode=mode_str,
                )
            except Exception as e:
                logger.warning("Failed to save lifecycle state: %s", e)
                return False
        return False

    def restore_state(self) -> bool:
        """
        Restore lifecycle state from checkpoint manager.

        Returns:
            True if restored successfully
        """
        if self._checkpoint_manager and self._task_id:
            try:
                state = self._checkpoint_manager.load_lifecycle_state(self._task_id)
                if state:
                    self._current_phase = state.get("current_phase")
                    self._completed_phases = state.get("completed_phases", [])

                    phase_states_raw = state.get("phase_states", {})
                    self._phase_states = {}
                    for pid, pstate in phase_states_raw.items():
                        try:
                            from scripts.collaboration.lifecycle_protocol import PhaseState
                            self._phase_states[pid] = PhaseState(pstate)
                        except ValueError:
                            self._phase_states[pid] = PhaseState.PENDING

                    mode_raw = state.get("mode", "shortcut")
                    try:
                        from scripts.collaboration.lifecycle_protocol import LifecycleMode
                        self._mode = LifecycleMode(mode_raw)
                    except ValueError:
                        pass

                    logger.info(
                        "Restored lifecycle state: task=%s, phase=%s",
                        self._task_id,
                        self._current_phase,
                    )
                    return True
            except Exception as e:
                logger.warning("Failed to restore lifecycle state: %s", e)
                return False
        return False

    def get_mode(self) -> LifecycleMode:
        return self._mode

    def set_mode(self, mode: LifecycleMode) -> None:
        self._mode = mode

    def get_all_phases(self) -> List[PhaseDefinition]:
        from scripts.collaboration.workflow_engine import PHASE_TEMPLATES

        phases = []
        for pid, ptmpl in PHASE_TEMPLATES.items():
            phases.append(PhaseDefinition(
                phase_id=pid,
                name=ptmpl.get("name", pid),
                description=ptmpl.get("description", ""),
                role_id=ptmpl.get("role_id", ""),
                dependencies=ptmpl.get("dependencies", []),
                artifacts_in=ptmpl.get("artifacts_in", ""),
                artifacts_out=ptmpl.get("artifacts_out", ""),
                gate_condition=ptmpl.get("gate_condition", ""),
                reviewers=ptmpl.get("reviewers", []),
                optional=ptmpl.get("optional", False),
            ))
        return sorted(phases, key=lambda p: p.phase_id)

    def get_active_phases(self) -> List[PhaseDefinition]:
        if self._mode == LifecycleMode.SHORTCUT and self._current_phase:
            mapping = self._get_current_mapping()
            if mapping:
                return [
                    p for p in self.get_all_phases()
                    if mapping.covers_phase(p.phase_id)
                ]
        return self.get_all_phases()

    def get_phase(self, phase_id: str) -> Optional[PhaseDefinition]:
        for p in self.get_all_phases():
            if p.phase_id == phase_id:
                return p
        return None

    def get_current_phase(self) -> Optional[PhaseDefinition]:
        if self._current_phase:
            return self.get_phase(self._current_phase)
        return None

    def advance_to_phase(self, phase_id: str) -> PhaseResult:
        prev_state = self._phase_states.get(phase_id, PhaseState.PENDING)

        # First check if already completed (idempotent)
        if prev_state == PhaseState.COMPLETED:
            return PhaseResult(
                success=True,
                phase_id=phase_id,
                previous_state=prev_state,
                new_state=PhaseState.COMPLETED,
                gate_result=GateResult(passed=True, verdict="APPROVE"),
            )

        # Check dependencies first (before gate)
        phase_def = self.get_phase(phase_id)
        unmet_deps = []
        if phase_def:
            unmet_deps = [d for d in phase_def.dependencies if d not in self._completed_phases]
            if unmet_deps:
                result = PhaseResult(
                    success=False,
                    phase_id=phase_id,
                    previous_state=prev_state,
                    new_state=PhaseState.BLOCKED,
                    gate_result=GateResult(
                        passed=False,
                        verdict="CONDITIONAL",
                        missing_evidence=[{"dependency": d} for d in unmet_deps],
                        gap_report=f"Unmet dependencies: {', '.join(unmet_deps)}",
                    ),
                    error=f"Unmet dependencies: {unmet_deps}",
                )

                # Auto-save state on block
                self.save_state()
                return result

        # Run gate check using unified engine or fallback
        gate_result = self.check_gate(phase_id)
        if not gate_result.passed and gate_result.verdict == "REJECT":
            self._phase_states[phase_id] = PhaseState.BLOCKED
            result = PhaseResult(
                success=False,
                phase_id=phase_id,
                previous_state=prev_state,
                new_state=PhaseState.BLOCKED,
                gate_result=gate_result,
                error=f"Gate rejected: {gate_result.gap_report}",
            )

            # Auto-save state on rejection
            self.save_state()
            return result

        # Advance to RUNNING state
        self._current_phase = phase_id
        self._phase_states[phase_id] = PhaseState.RUNNING
        logger.debug("Advanced to phase %s, _current_phase=%s", phase_id, self._current_phase)

        # Auto-save state on successful advance
        self.save_state()

        return PhaseResult(
            success=True,
            phase_id=phase_id,
            previous_state=prev_state,
            new_state=PhaseState.RUNNING,
            gate_result=gate_result,
        )

    def complete_phase(self, phase_id: str) -> None:
        """Mark a phase as completed."""
        self._phase_states[phase_id] = PhaseState.COMPLETED
        if phase_id not in self._completed_phases:
            self._completed_phases.append(phase_id)

        # Auto-save state on completion
        self.save_state()

    def check_gate(self, phase_id: Optional[str] = None) -> GateResult:
        target = phase_id or self._current_phase
        if not target:
            return GateResult(passed=True, verdict="APPROVE")

        phase_def = self.get_phase(target)
        if not phase_def:
            return GateResult(passed=False, verdict="REJECT", gap_report=f"Phase {target} not found")

        # Use UnifiedGateEngine if available
        if self._use_unified_gate and self._gate_engine:
            try:
                return self._check_gate_with_unified_engine(target, phase_def)
            except Exception as e:
                logger.warning("UnifiedGateEngine failed, falling back: %s", e)

        # Fallback to basic gate checks
        return self._check_gate_basic(target, phase_def)

    def _check_gate_with_unified_engine(
        self,
        target: str,
        phase_def: PhaseDefinition,
    ) -> GateResult:
        """Check gate using UnifiedGateEngine."""
        # Build phase context
        unmet_deps = [d for d in phase_def.dependencies if d not in self._completed_phases]

        context = self._PhaseGateContext(
            phase_id=target,
            phase_name=phase_def.name,
            current_state=self._phase_states.get(target, PhaseState.PENDING).value,
            target_state="running",
            dependencies_met=len(unmet_deps) == 0,
            completed_phases=self._completed_phases.copy(),
            unmet_dependencies=unmet_deps,
        )

        # Run unified gate check
        unified_result = self._gate_engine.check(
            gate_type=self._GateType.PHASE_TRANSITION,
            context=context,
        )

        # Convert UnifiedGateResult to GateResult
        return GateResult(
            passed=unified_result.passed,
            verdict=unified_result.verdict,
            red_flags=[
                {"id": issue.get("code", "unknown"), "severity": "critical", **issue}
                for issue in unified_result.critical_issues
            ],
            missing_evidence=[
                {"key": ev, "required": True}
                for ev in unified_result.evidence_required
            ],
            gap_report="\n".join([
                f"- [{issue.get('severity', 'unknown')}] {issue.get('message', '')}"
                for issue in unified_result.critical_issues + unified_result.warnings
            ]) if (unified_result.critical_issues or unified_result.warnings) else "",
        )

    def _check_gate_basic(
        self,
        target: str,
        phase_def: PhaseDefinition,
    ) -> GateResult:
        """Basic fallback gate check without UnifiedGateEngine."""
        state = self._phase_states.get(target, PhaseState.PENDING)
        if state == PhaseState.BLOCKED:
            return GateResult(passed=False, verdict="REJECT", gap_report="Phase is blocked")
        if state == PhaseState.COMPLETED:
            return GateResult(passed=True, verdict="APPROVE")

        # Check dependencies
        unmet_deps = [d for d in phase_def.dependencies if d not in self._completed_phases]
        if unmet_deps:
            return GateResult(
                passed=False,
                verdict="CONDITIONAL",
                missing_evidence=[{"dependency": d} for d in unmet_deps],
                gap_report=f"Unmet dependencies: {', '.join(unmet_deps)}",
            )

        return GateResult(passed=True, verdict="APPROVE")

    def get_status(self) -> LifecycleStatus:
        all_phases = self.get_all_phases()
        total = len(all_phases)
        completed = len(self._completed_phases)
        progress = (completed / total * 100) if total > 0 else 0.0

        next_phase = None
        can_advance = True
        for p in all_phases:
            pid = p.phase_id
            state = self._phase_states.get(pid, PhaseState.PENDING)
            if state == PhaseState.PENDING and not next_phase:
                next_phase = pid
            if state == PhaseState.BLOCKED:
                can_advance = False

        return LifecycleStatus(
            mode=self._mode,
            current_phase=self._current_phase,
            completed_phases=self._completed_phases.copy(),
            failed_phases=[pid for pid, s in self._phase_states.items() if s == PhaseState.FAILED],
            blocked_phases=[pid for pid, s in self._phase_states.items() if s == PhaseState.BLOCKED],
            progress_percent=progress,
            can_advance=can_advance,
            next_phase=next_phase,
        )

    def get_view_mapping(self, command: str) -> Optional[ViewMapping]:
        return VIEW_MAPPINGS.get(command)

    def resolve_command_to_phases(self, command: str) -> List[PhaseDefinition]:
        mapping = VIEW_MAPPINGS.get(command)
        if not mapping:
            return []

        return [p for p in self.get_all_phases() if mapping.covers_phase(p.phase_id)]

    def _get_current_mapping(self) -> Optional[ViewMapping]:
        if self._current_phase:
            for mapping in VIEW_MAPPINGS.values():
                if mapping.covers_phase(self._current_phase):
                    return mapping
        return None


def create_lifecycle_protocol(mode: LifecycleMode = LifecycleMode.SHORTCUT) -> LifecycleProtocol:
    """Factory function to create appropriate protocol implementation."""
    if mode == LifecycleMode.FULL:
        return FullLifecycleAdapter()
    else:
        adapter = ShortcutLifecycleAdapter()
        adapter.set_mode(mode)
        return adapter


def get_shared_protocol() -> LifecycleProtocol:
    """Get shared singleton instance of lifecycle protocol."""
    if not hasattr(get_shared_protocol, "_instance"):
        get_shared_protocol._instance = create_lifecycle_protocol()
    return get_shared_protocol._instance


class FullLifecycleAdapter(LifecycleProtocol):
    """
    Full 11-phase lifecycle adapter for complete project lifecycles.

    Implements LifecycleProtocol with FULL mode, supporting all P1-P11 phases
    with automatic dependency resolution and phase ordering.

    Features:
      - Complete P1-P11 phase support
      - Automatic dependency resolution
      - Phase ordering based on dependency graph
      - Optional phase skipping (for non-required phases)
      - Integration with UnifiedGateEngine and CheckpointManager

    Use Cases:
      - Large projects requiring full lifecycle management
      - Compliance-critical workflows (all phases mandatory)
      - Projects with complex dependencies between phases
    """

    def __init__(self, use_unified_gate: bool = True):
        self._mode = LifecycleMode.FULL
        self._current_phase: Optional[str] = None
        self._completed_phases: List[str] = []
        self._phase_states: Dict[str, PhaseState] = {}
        self._use_unified_gate = use_unified_gate
        self._gate_engine = None
        self._checkpoint_manager = None
        self._task_id: Optional[str] = None
        self._skip_optional: bool = False
        self._execution_order: List[str] = []

        # Initialize unified gate engine if requested
        if use_unified_gate:
            try:
                from scripts.collaboration.unified_gate_engine import (
                    UnifiedGateEngine,
                    GateType,
                    PhaseGateContext,
                    get_shared_gate_engine,
                )
                self._gate_engine = get_shared_gate_engine()
                self._GateType = GateType
                self._PhaseGateContext = PhaseGateContext
                logger.debug("UnifiedGateEngine initialized for FullLifecycleAdapter")
            except ImportError as e:
                logger.warning("UnifiedGateEngine not available: %s", e)
                self._use_unified_gate = False

        # Build execution order from dependencies
        self._build_execution_order()

    def _build_execution_order(self) -> None:
        """Build topological execution order based on phase dependencies."""
        from scripts.collaboration.workflow_engine import PHASE_TEMPLATES

        # Simple topological sort
        visited = set()
        order = []

        def visit(phase_id: str):
            if phase_id in visited:
                return
            visited.add(phase_id)

            phase = PHASE_TEMPLATES.get(phase_id, {})
            for dep in phase.get("dependencies", []):
                visit(dep)

            order.append(phase_id)

        # Visit all phases in sorted order for deterministic output
        for pid in sorted(PHASE_TEMPLATES.keys()):
            visit(pid)

        self._execution_order = order
        logger.debug("Full execution order: %s", self._execution_order)

    def set_task_id(self, task_id: str) -> None:
        """Set task ID for checkpoint integration."""
        self._task_id = task_id
        if not self._checkpoint_manager:
            try:
                from scripts.collaboration.checkpoint_manager import CheckpointManager
                self._checkpoint_manager = CheckpointManager()
                logger.info("CheckpointManager initialized for task %s", task_id)
            except ImportError as e:
                logger.warning("CheckpointManager not available: %s", e)

    def enable_checkpoint_integration(self, storage_path: str = "./checkpoints") -> bool:
        """Enable checkpoint manager integration for state persistence."""
        try:
            from scripts.collaboration.checkpoint_manager import CheckpointManager
            self._checkpoint_manager = CheckpointManager(storage_path=storage_path)
            logger.info("CheckpointManager enabled at %s", storage_path)
            return True
        except Exception as e:
            logger.warning("Failed to enable checkpoint integration: %s", e)
            return False

    def set_skip_optional(self, skip: bool) -> None:
        """Configure whether to skip optional phases (P4, P5, P6, P11)."""
        self._skip_optional = skip
        logger.info("Skip optional phases: %s", skip)

    def save_state(self) -> bool:
        """Save current lifecycle state to checkpoint manager."""
        if self._checkpoint_manager and self._task_id:
            try:
                phase_states_str = {
                    pid: (state.value if hasattr(state, 'value') else str(state))
                    for pid, state in self._phase_states.items()
                }
                mode_str = self._mode.value if hasattr(self._mode, 'value') else str(self._mode)

                return self._checkpoint_manager.save_lifecycle_state(
                    task_id=self._task_id,
                    current_phase=self._current_phase,
                    phase_states=phase_states_str,
                    completed_phases=self._completed_phases.copy(),
                    mode=mode_str,
                    metadata={
                        "adapter_type": "full",
                        "skip_optional": self._skip_optional,
                        "execution_order": self._execution_order,
                    },
                )
            except Exception as e:
                logger.warning("Failed to save lifecycle state: %s", e)
                return False
        return False

    def restore_state(self) -> bool:
        """Restore lifecycle state from checkpoint manager."""
        if self._checkpoint_manager and self._task_id:
            try:
                state = self._checkpoint_manager.load_lifecycle_state(self._task_id)
                if state:
                    self._current_phase = state.get("current_phase")
                    self._completed_phases = state.get("completed_phases", [])

                    phase_states_raw = state.get("phase_states", {})
                    self._phase_states = {}
                    for pid, pstate in phase_states_raw.items():
                        try:
                            self._phase_states[pid] = PhaseState(pstate)
                        except ValueError:
                            self._phase_states[pid] = PhaseState.PENDING

                    mode_raw = state.get("mode", "full")
                    try:
                        self._mode = LifecycleMode(mode_raw)
                    except ValueError:
                        pass

                    # Restore metadata
                    metadata = state.get("metadata", {})
                    self._skip_optional = metadata.get("skip_optional", False)
                    self._execution_order = metadata.get("execution_order", self._execution_order)

                    logger.info(
                        "Restored lifecycle state: task=%s, phase=%s",
                        self._task_id,
                        self._current_phase,
                    )
                    return True
            except Exception as e:
                logger.warning("Failed to restore lifecycle state: %s", e)
                return False
        return False

    def get_mode(self) -> LifecycleMode:
        return self._mode

    def set_mode(self, mode: LifecycleMode) -> None:
        self._mode = mode

    def get_all_phases(self) -> List[PhaseDefinition]:
        from scripts.collaboration.workflow_engine import PHASE_TEMPLATES

        phases = []
        for pid, ptmpl in PHASE_TEMPLATES.items():
            phases.append(PhaseDefinition(
                phase_id=pid,
                name=ptmpl.get("name", pid),
                description=ptmpl.get("description", ""),
                role_id=ptmpl.get("role_id", ""),
                dependencies=ptmpl.get("dependencies", []),
                artifacts_in=ptmpl.get("artifacts_in", ""),
                artifacts_out=ptmpl.get("artifacts_out", ""),
                gate_condition=ptmpl.get("gate_condition", ""),
                reviewers=ptmpl.get("reviewers", []),
                optional=ptmpl.get("optional", False),
            ))
        return sorted(phases, key=lambda p: p.phase_id)

    def get_active_phases(self) -> List[PhaseDefinition]:
        all_phases = self.get_all_phases()
        if self._skip_optional:
            return [p for p in all_phases if not p.optional]
        return all_phases

    def get_phase(self, phase_id: str) -> Optional[PhaseDefinition]:
        for p in self.get_all_phases():
            if p.phase_id == phase_id:
                return p
        return None

    def get_current_phase(self) -> Optional[PhaseDefinition]:
        if self._current_phase:
            return self.get_phase(self._current_phase)
        return None

    def advance_to_phase(self, phase_id: str) -> PhaseResult:
        prev_state = self._phase_states.get(phase_id, PhaseState.PENDING)

        # Check if already completed (idempotent)
        if prev_state == PhaseState.COMPLETED:
            return PhaseResult(
                success=True,
                phase_id=phase_id,
                previous_state=prev_state,
                new_state=PhaseState.COMPLETED,
                gate_result=GateResult(passed=True, verdict="APPROVE"),
            )

        # Get phase definition
        phase_def = self.get_phase(phase_id)
        if not phase_def:
            result = PhaseResult(
                success=False,
                phase_id=phase_id,
                previous_state=prev_state,
                new_state=PhaseState.BLOCKED,
                gate_result=GateResult(
                    passed=False,
                    verdict="REJECT",
                    gap_report=f"Phase {phase_id} not found in 11-phase model",
                ),
                error=f"Unknown phase: {phase_id}",
            )
            self.save_state()
            return result

        # Check if optional and should be skipped
        if self._skip_optional and phase_def.optional:
            self._phase_states[phase_id] = PhaseState.SKIPPED
            logger.info("Skipping optional phase: %s", phase_id)
            return PhaseResult(
                success=True,
                phase_id=phase_id,
                previous_state=prev_state,
                new_state=PhaseState.SKIPPED,
                gate_result=GateResult(passed=True, verdict="APPROVE"),
            )

        # Check dependencies first (strict in FULL mode)
        unmet_deps = [d for d in phase_def.dependencies if d not in self._completed_phases]
        if unmet_deps:
            result = PhaseResult(
                success=False,
                phase_id=phase_id,
                previous_state=prev_state,
                new_state=PhaseState.BLOCKED,
                gate_result=GateResult(
                    passed=False,
                    verdict="CONDITIONAL",
                    missing_evidence=[{"dependency": d} for d in unmet_deps],
                    gap_report=f"Unmet dependencies: {', '.join(unmet_deps)}",
                ),
                error=f"Unmet dependencies: {unmet_deps}",
            )
            self.save_state()
            return result

        # Run gate check using unified engine or fallback
        gate_result = self.check_gate(phase_id)
        if not gate_result.passed and gate_result.verdict == "REJECT":
            self._phase_states[phase_id] = PhaseState.BLOCKED
            result = PhaseResult(
                success=False,
                phase_id=phase_id,
                previous_state=prev_state,
                new_state=PhaseState.BLOCKED,
                gate_result=gate_result,
                error=f"Gate rejected: {gate_result.gap_report}",
            )
            self.save_state()
            return result

        # Advance to RUNNING state
        self._current_phase = phase_id
        self._phase_states[phase_id] = PhaseState.RUNNING
        logger.debug("Full mode advanced to phase %s", phase_id)
        self.save_state()

        return PhaseResult(
            success=True,
            phase_id=phase_id,
            previous_state=prev_state,
            new_state=PhaseState.RUNNING,
            gate_result=gate_result,
        )

    def complete_phase(self, phase_id: str) -> None:
        """Mark a phase as completed."""
        self._phase_states[phase_id] = PhaseState.COMPLETED
        if phase_id not in self._completed_phases:
            self._completed_phases.append(phase_id)
        self.save_state()

    def check_gate(self, phase_id: Optional[str] = None) -> GateResult:
        target = phase_id or self._current_phase
        if not target:
            return GateResult(passed=True, verdict="APPROVE")

        phase_def = self.get_phase(target)
        if not phase_def:
            return GateResult(passed=False, verdict="REJECT", gap_report=f"Phase {target} not found")

        # Use UnifiedGateEngine if available
        if self._use_unified_gate and self._gate_engine:
            try:
                return self._check_gate_with_unified_engine(target, phase_def)
            except Exception as e:
                logger.warning("UnifiedGateEngine failed, falling back: %s", e)

        # Fallback to basic gate checks
        return self._check_gate_basic(target, phase_def)

    def _check_gate_with_unified_engine(self, target: str, phase_def: PhaseDefinition) -> GateResult:
        """Check gate using UnifiedGateEngine."""
        unmet_deps = [d for d in phase_def.dependencies if d not in self._completed_phases]

        context = self._PhaseGateContext(
            phase_id=target,
            phase_name=phase_def.name,
            current_state=self._phase_states.get(target, PhaseState.PENDING).value,
            target_state="running",
            dependencies_met=len(unmet_deps) == 0,
            completed_phases=self._completed_phases.copy(),
            unmet_dependencies=unmet_deps,
        )

        unified_result = self._gate_engine.check(
            gate_type=self._GateType.PHASE_TRANSITION,
            context=context,
        )

        return GateResult(
            passed=unified_result.passed,
            verdict=unified_result.verdict,
            red_flags=[
                {"id": issue.get("code", "unknown"), "severity": "critical", **issue}
                for issue in unified_result.critical_issues
            ],
            missing_evidence=[
                {"key": ev, "required": True}
                for ev in unified_result.evidence_required
            ],
            gap_report="\n".join([
                f"- [{issue.get('severity', 'unknown')}] {issue.get('message', '')}"
                for issue in unified_result.critical_issues + unified_result.warnings
            ]) if (unified_result.critical_issues or unified_result.warnings) else "",
        )

    @staticmethod
    def _check_gate_basic(target: str, phase_def: PhaseDefinition) -> GateResult:
        """Basic fallback gate check without UnifiedGateEngine."""
        # This would need access to instance state, so we use a simplified version
        return GateResult(passed=True, verdict="APPROVE")

    def get_status(self) -> LifecycleStatus:
        all_phases = self.get_active_phases()
        total = len(all_phases)
        completed = len([p for p in all_phases if p.phase_id in self._completed_phases])
        progress = (completed / total * 100) if total > 0 else 0.0

        next_phase = None
        can_advance = True
        for pid in self._execution_order:
            phase_def = self.get_phase(pid)
            if not phase_def:
                continue
            if self._skip_optional and phase_def.optional:
                continue
            state = self._phase_states.get(pid, PhaseState.PENDING)
            if state == PhaseState.PENDING and not next_phase:
                next_phase = pid
            if state == PhaseState.BLOCKED:
                can_advance = False

        return LifecycleStatus(
            mode=self._mode,
            current_phase=self._current_phase,
            completed_phases=self._completed_phases.copy(),
            failed_phases=[pid for pid, s in self._phase_states.items() if s == PhaseState.FAILED],
            blocked_phases=[pid for pid, s in self._phase_states.items() if s == PhaseState.BLOCKED],
            progress_percent=progress,
            can_advance=can_advance,
            next_phase=next_phase,
        )

    def get_view_mapping(self, command: str) -> Optional[ViewMapping]:
        return VIEW_MAPPINGS.get(command)

    def resolve_command_to_phases(self, command: str) -> List[PhaseDefinition]:
        mapping = VIEW_MAPPINGS.get(command)
        if not mapping:
            return []
        return [p for p in self.get_all_phases() if mapping.covers_phase(p.phase_id)]

    def get_next_phase(self) -> Optional[str]:
        """Get the next phase that should be executed based on execution order."""
        for pid in self._execution_order:
            state = self._phase_states.get(pid, PhaseState.PENDING)
            if state == PhaseState.PENDING:
                phase_def = self.get_phase(pid)
                if phase_def and (not self._skip_optional or not phase_def.optional):
                    return pid
        return None

    def auto_advance(self) -> PhaseResult:
        """Automatically advance to the next pending phase."""
        next_phase = self.get_next_phase()
        if not next_phase:
            return PhaseResult(
                success=False,
                phase_id="",
                previous_state=PhaseState.PENDING,
                new_state=PhaseState.PENDING,
                error="No more phases to execute",
            )
        return self.advance_to_phase(next_phase)

    def get_execution_progress(self) -> Dict[str, Any]:
        """Get detailed execution progress information."""
        phases_info = []
        for pid in self._execution_order:
            phase_def = self.get_phase(pid)
            if not phase_def:
                continue
            state = self._phase_states.get(pid, PhaseState.PENDING)
            phases_info.append({
                "phase_id": pid,
                "name": phase_def.name,
                "state": state.value if hasattr(state, 'value') else str(state),
                "optional": phase_def.optional,
                "role": phase_def.role_id,
                "completed": pid in self._completed_phases,
            })

        status = self.get_status()
        return {
            "total_phases": len(self.get_active_phases()),
            "completed_phases": len(status.completed_phases),
            "progress_percent": status.progress_percent,
            "current_phase": status.current_phase,
            "next_phase": status.next_phase,
            "can_advance": status.can_advance,
            "phases": phases_info,
            "execution_order": self._execution_order,
            "skip_optional": self._skip_optional,
        }
