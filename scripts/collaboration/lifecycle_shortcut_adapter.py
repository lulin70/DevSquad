#!/usr/bin/env python3
"""
Lifecycle Adapters - ShortcutLifecycleAdapter + FullLifecycleAdapter 实现

ShortcutLifecycleAdapter:
  - 实现 LifecycleProtocol，使用 CLI 6-command 快捷方式
  - 将 CLI 命令映射到 11-phase 片段
  - 集成 UnifiedGateEngine 和 CheckpointManager

FullLifecycleAdapter:
  - 完整 11-phase 生命周期适配器
  - 自动依赖解析和阶段排序
  - 支持可选阶段跳过

从 lifecycle_protocol.py 拆分而来，lifecycle_protocol.py 会 re-export 以保持向后兼容。

Spec reference: docs/spec/SPEC_Lifecycle_Unified_Architecture_C.md
"""

import contextlib
import json
import logging
from pathlib import Path
from typing import Any

from .lifecycle_gate import check_gate_basic, check_gate_with_unified_engine
from .lifecycle_protocol import (
    GateResult,
    LifecycleMode,
    LifecycleProtocol,
    LifecycleStatus,
    PhaseDefinition,
    PhaseResult,
    PhaseState,
)
from .lifecycle_templates import SPEC_TEMPLATES, VIEW_MAPPINGS, ViewMapping

logger = logging.getLogger(__name__)


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
        self._current_phase: str | None = None
        self._completed_phases: list[str] = []
        self._phase_states: dict[str, PhaseState] = {}
        self._use_unified_gate = use_unified_gate
        self._gate_engine = None
        self._checkpoint_manager = None
        self._task_id: str | None = None

        # Initialize unified gate engine if requested
        if use_unified_gate:
            try:
                from scripts.collaboration.unified_gate_engine import (
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
        except (ImportError, AttributeError, OSError) as e:
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
                    pid: (state.value if hasattr(state, "value") else str(state))
                    for pid, state in self._phase_states.items()
                }
                mode_str = self._mode.value if hasattr(self._mode, "value") else str(self._mode)

                return self._checkpoint_manager.save_lifecycle_state(
                    task_id=self._task_id,
                    current_phase=self._current_phase,
                    phase_states=phase_states_str,
                    completed_phases=self._completed_phases.copy(),
                    mode=mode_str,
                )
            except (OSError, AttributeError, ValueError) as e:
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
                            self._phase_states[pid] = PhaseState(pstate)
                        except ValueError:
                            self._phase_states[pid] = PhaseState.PENDING

                    mode_raw = state.get("mode", "shortcut")
                    with contextlib.suppress(ValueError):
                        self._mode = LifecycleMode(mode_raw)

                    logger.info(
                        "Restored lifecycle state: task=%s, phase=%s",
                        self._task_id,
                        self._current_phase,
                    )
                    return True
            except (OSError, AttributeError, ValueError, KeyError) as e:
                logger.warning("Failed to restore lifecycle state: %s", e)
                return False
        return False

    def get_mode(self) -> LifecycleMode:
        """Return the current lifecycle mode.

        Returns:
            The LifecycleMode (SHORTCUT or FULL) currently in use.
        """
        return self._mode

    def set_mode(self, mode: LifecycleMode) -> None:
        """Set the lifecycle mode.

        Args:
            mode: LifecycleMode to switch to.
        """
        self._mode = mode

    def get_all_phases(self) -> list[PhaseDefinition]:
        """Return all phase definitions from PHASE_TEMPLATES.

        Returns:
            Sorted list of PhaseDefinition objects covering every phase.
        """
        from scripts.collaboration.workflow_engine import PHASE_TEMPLATES

        phases = []
        for pid, ptmpl in PHASE_TEMPLATES.items():
            phases.append(
                PhaseDefinition(
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
                )
            )
        return sorted(phases, key=lambda p: p.phase_id)

    def get_active_phases(self) -> list[PhaseDefinition]:
        """Return phases active under the current shortcut mapping.

        In SHORTCUT mode with a current phase, returns only the phases covered
        by the current command mapping. Otherwise returns all phases.

        Returns:
            List of PhaseDefinition objects currently in scope.
        """
        if self._mode == LifecycleMode.SHORTCUT and self._current_phase:
            mapping = self._get_current_mapping()
            if mapping:
                return [p for p in self.get_all_phases() if mapping.covers_phase(p.phase_id)]
        return self.get_all_phases()

    def get_phase(self, phase_id: str) -> PhaseDefinition | None:
        """Look up a single phase definition by ID.

        Args:
            phase_id: Identifier of the phase to retrieve.

        Returns:
            The matching PhaseDefinition, or None when not found.
        """
        for p in self.get_all_phases():
            if p.phase_id == phase_id:
                return p
        return None

    def get_current_phase(self) -> PhaseDefinition | None:
        """Return the definition for the currently active phase.

        Returns:
            The current PhaseDefinition, or None when no phase is active.
        """
        if self._current_phase:
            return self.get_phase(self._current_phase)
        return None

    def advance_to_phase(self, phase_id: str) -> PhaseResult:
        """Advance the lifecycle to the specified phase after gate checks.

        Args:
            phase_id: Identifier of the phase to advance to.

        Returns:
            PhaseResult describing the transition. Already-completed phases
            return success idempotently; failed gates or unmet dependencies
            return a blocked result.
        """
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

    def check_gate(self, phase_id: str | None = None) -> GateResult:
        """Check the gate conditions for a phase.

        Args:
            phase_id: Optional phase ID to check; defaults to the current phase.

        Returns:
            GateResult indicating whether the gate passed, with a verdict and
            optional gap report. Returns APPROVE when no target phase is set.
        """
        target = phase_id or self._current_phase
        if not target:
            return GateResult(passed=True, verdict="APPROVE")

        phase_def = self.get_phase(target)
        if not phase_def:
            return GateResult(passed=False, verdict="REJECT", gap_report=f"Phase {target} not found")

        # Use UnifiedGateEngine if available
        if self._use_unified_gate and self._gate_engine:
            try:
                return check_gate_with_unified_engine(
                    target,
                    phase_def,
                    self._phase_states,
                    self._completed_phases,
                    self._gate_engine,
                    self._GateType,
                    self._PhaseGateContext,
                )
            except Exception as e:  # Broad catch: unpredictable gate engine
                logger.warning("UnifiedGateEngine failed, falling back: %s", e)

        # Fallback to basic gate checks
        return check_gate_basic(
            target, phase_def, self._phase_states, self._completed_phases, strict_optional=False
        )

    def get_status(self) -> LifecycleStatus:
        """Return the overall lifecycle status.

        Returns:
            LifecycleStatus with mode, current phase, completed/failed/blocked
            phase lists, progress percent, and the next pending phase.
        """
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

    def get_view_mapping(self, command: str) -> ViewMapping | None:
        """Return the view mapping for a CLI command.

        Args:
            command: CLI command name.

        Returns:
            The matching ViewMapping, or None when no mapping exists.
        """
        return VIEW_MAPPINGS.get(command)

    def resolve_command_to_phases(self, command: str) -> list[PhaseDefinition]:
        """Resolve a CLI command to its covered phase definitions.

        Args:
            command: CLI command name.

        Returns:
            List of PhaseDefinition objects covered by the command; empty when
            the command is unknown.
        """
        mapping = VIEW_MAPPINGS.get(command)
        if not mapping:
            return []

        return [p for p in self.get_all_phases() if mapping.covers_phase(p.phase_id)]

    def _get_current_mapping(self) -> ViewMapping | None:
        if self._current_phase:
            for mapping in VIEW_MAPPINGS.values():
                if mapping.covers_phase(self._current_phase):
                    return mapping
        return None

    def init_spec(
        self,
        template_id: str = "requirements",
        project_info: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Initialize a specification document from template.

        Args:
            template_id: Template type (requirements/architecture/technical)
            project_info: Optional project information to pre-fill

        Returns:
            Dict with success status and spec document structure
        """
        template = SPEC_TEMPLATES.get(template_id)
        if not template:
            return {"success": False, "error": f"Unknown template: {template_id}"}

        doc = {
            "template_id": template_id,
            "name": template.name,
            "phase_id": template.phase_id,
            "sections": {},
        }
        for section in template.sections:
            doc["sections"][section["title"]] = {
                "description": section["description"],
                "content": "",
                "status": "draft",
            }

        if project_info:
            doc["project_info"] = project_info

        return {"success": True, "spec": doc, "template_id": template_id}

    def analyze_spec(
        self,
        source_dir: str = ".",
        template_id: str = "requirements",
    ) -> dict[str, Any]:
        """
        Analyze existing codebase to generate specification draft.

        Uses CodeMapGenerator for multi-language code analysis.

        Args:
            source_dir: Root directory to analyze
            template_id: Template to use for structuring the analysis

        Returns:
            Dict with success status and analysis results
        """
        try:
            from scripts.collaboration.code_map_generator import CodeMapGenerator
            from scripts.collaboration.language_parsers import DEFAULT_PARSERS

            gen = CodeMapGenerator(project_root=source_dir, parsers=DEFAULT_PARSERS)
            code_map = gen.generate_map(output_format="dict")
            dep_graph = gen.get_dependency_graph()

            analysis = {
                "modules": list(code_map.keys()),
                "total_modules": len(code_map),
                "total_classes": sum(m.get("total_classes", 0) for m in code_map.values()),
                "total_functions": sum(m.get("total_functions", 0) for m in code_map.values()),
                "dependencies": dep_graph,
                "languages": list({m.get("language", "python") for m in code_map.values() if isinstance(m, dict)}),
            }

            return {"success": True, "analysis": analysis, "template_id": template_id}
        except (ImportError, AttributeError, OSError, ValueError) as e:
            return {"success": False, "error": str(e)}

    def validate_spec(
        self,
        spec_path: str | None = None,
        template_id: str | None = None,
        spec_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Validate specification completeness and consistency.

        Args:
            spec_path: Path to specification file (optional)
            template_id: Template to validate against
            spec_data: Specification data dict to validate (optional)

        Returns:
            Dict with validation results
        """
        results: dict[str, Any] = {"valid": True, "errors": [], "warnings": []}

        template = SPEC_TEMPLATES.get(template_id or "requirements")
        if not template:
            return {
                "valid": False,
                "errors": [{"message": f"Unknown template: {template_id}"}],
                "warnings": [],
            }

        if spec_data is None:
            if spec_path:
                try:
                    raw = Path(spec_path).read_text(encoding="utf-8")
                    spec_data = json.loads(raw)
                except (OSError, json.JSONDecodeError, ValueError):
                    spec_data = {}
            else:
                spec_data = {}

        sections = spec_data.get("sections", spec_data)

        for field_name in template.required_fields:
            value = sections.get(field_name, spec_data.get(field_name, ""))
            if not value or (isinstance(value, str) and not value.strip()):
                results["errors"].append(
                    {
                        "field": field_name,
                        "message": f"Required field '{field_name}' is missing or empty",
                        "severity": "critical",
                    }
                )
                results["valid"] = False

        for rule in template.validation_rules:
            field_name = rule.get("field", "")
            check = rule.get("check", "")
            severity = rule.get("severity", "warning")
            value = sections.get(field_name, spec_data.get(field_name, ""))
            if check == "not_empty" and (not value or (isinstance(value, str) and not value.strip())):
                results["warnings"].append(
                    {
                        "field": field_name,
                        "message": f"Field '{field_name}' should not be empty",
                        "severity": severity,
                    }
                )

        return results


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
        self._current_phase: str | None = None
        self._completed_phases: list[str] = []
        self._phase_states: dict[str, PhaseState] = {}
        self._use_unified_gate = use_unified_gate
        self._gate_engine = None
        self._checkpoint_manager = None
        self._task_id: str | None = None
        self._skip_optional: bool = False
        self._execution_order: list[str] = []

        # Initialize unified gate engine if requested
        if use_unified_gate:
            try:
                from scripts.collaboration.unified_gate_engine import (
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
            """Recursively visit a phase and its dependencies in topological order.

            Args:
                phase_id: Identifier of the phase to visit.
            """
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
        except (ImportError, AttributeError, OSError) as e:
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
                    pid: (state.value if hasattr(state, "value") else str(state))
                    for pid, state in self._phase_states.items()
                }
                mode_str = self._mode.value if hasattr(self._mode, "value") else str(self._mode)

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
            except (OSError, AttributeError, ValueError) as e:
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
                    with contextlib.suppress(ValueError):
                        self._mode = LifecycleMode(mode_raw)

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
            except (OSError, AttributeError, ValueError, KeyError) as e:
                logger.warning("Failed to restore lifecycle state: %s", e)
                return False
        return False

    def get_mode(self) -> LifecycleMode:
        """Return the current lifecycle mode.

        Returns:
            Always LifecycleMode.FULL for this adapter.
        """
        return self._mode

    def set_mode(self, mode: LifecycleMode) -> None:
        """Set the lifecycle mode.

        Args:
            mode: LifecycleMode to switch to.
        """
        self._mode = mode

    def get_all_phases(self) -> list[PhaseDefinition]:
        """Return all phase definitions from PHASE_TEMPLATES.

        Returns:
            Sorted list of PhaseDefinition objects covering every phase.
        """
        from scripts.collaboration.workflow_engine import PHASE_TEMPLATES

        phases = []
        for pid, ptmpl in PHASE_TEMPLATES.items():
            phases.append(
                PhaseDefinition(
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
                )
            )
        return sorted(phases, key=lambda p: p.phase_id)

    def get_active_phases(self) -> list[PhaseDefinition]:
        """Return phases active under the current configuration.

        When skip_optional is enabled, optional phases are excluded.

        Returns:
            List of PhaseDefinition objects currently in scope.
        """
        all_phases = self.get_all_phases()
        if self._skip_optional:
            return [p for p in all_phases if not p.optional]
        return all_phases

    def get_phase(self, phase_id: str) -> PhaseDefinition | None:
        """Look up a single phase definition by ID.

        Args:
            phase_id: Identifier of the phase to retrieve.

        Returns:
            The matching PhaseDefinition, or None when not found.
        """
        for p in self.get_all_phases():
            if p.phase_id == phase_id:
                return p
        return None

    def get_current_phase(self) -> PhaseDefinition | None:
        """Return the definition for the currently active phase.

        Returns:
            The current PhaseDefinition, or None when no phase is active.
        """
        if self._current_phase:
            return self.get_phase(self._current_phase)
        return None

    def advance_to_phase(self, phase_id: str) -> PhaseResult:
        """Advance the lifecycle to the specified phase after gate checks.

        Args:
            phase_id: Identifier of the phase to advance to.

        Returns:
            PhaseResult describing the transition. Already-completed phases
            return success idempotently; optional phases may be skipped;
            failed gates or unmet dependencies return a blocked result.
        """
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

    def check_gate(self, phase_id: str | None = None) -> GateResult:
        """Check the gate conditions for a phase using strict optional rules.

        Args:
            phase_id: Optional phase ID to check; defaults to the current phase.

        Returns:
            GateResult indicating whether the gate passed, with a verdict and
            optional gap report. Returns APPROVE when no target phase is set.
        """
        target = phase_id or self._current_phase
        if not target:
            return GateResult(passed=True, verdict="APPROVE")

        phase_def = self.get_phase(target)
        if not phase_def:
            return GateResult(passed=False, verdict="REJECT", gap_report=f"Phase {target} not found")

        # Use UnifiedGateEngine if available
        if self._use_unified_gate and self._gate_engine:
            try:
                return check_gate_with_unified_engine(
                    target,
                    phase_def,
                    self._phase_states,
                    self._completed_phases,
                    self._gate_engine,
                    self._GateType,
                    self._PhaseGateContext,
                )
            except Exception as e:  # Broad catch: unpredictable gate engine
                logger.warning("UnifiedGateEngine failed, falling back: %s", e)

        # Fallback to basic gate checks
        return check_gate_basic(
            target, phase_def, self._phase_states, self._completed_phases, strict_optional=True
        )

    def get_status(self) -> LifecycleStatus:
        """Return the overall lifecycle status.

        Returns:
            LifecycleStatus with mode, current phase, completed/failed/blocked
            phase lists, progress percent, and the next pending phase.
        """
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

    def get_view_mapping(self, command: str) -> ViewMapping | None:
        """Return the view mapping for a CLI command.

        Args:
            command: CLI command name.

        Returns:
            The matching ViewMapping, or None when no mapping exists.
        """
        return VIEW_MAPPINGS.get(command)

    def resolve_command_to_phases(self, command: str) -> list[PhaseDefinition]:
        """Resolve a CLI command to its covered phase definitions.

        Args:
            command: CLI command name.

        Returns:
            List of PhaseDefinition objects covered by the command; empty when
            the command is unknown.
        """
        mapping = VIEW_MAPPINGS.get(command)
        if not mapping:
            return []
        return [p for p in self.get_all_phases() if mapping.covers_phase(p.phase_id)]

    def get_next_phase(self) -> str | None:
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

    def get_execution_progress(self) -> dict[str, Any]:
        """Get detailed execution progress information."""
        phases_info = []
        for pid in self._execution_order:
            phase_def = self.get_phase(pid)
            if not phase_def:
                continue
            state = self._phase_states.get(pid, PhaseState.PENDING)
            phases_info.append(
                {
                    "phase_id": pid,
                    "name": phase_def.name,
                    "state": state.value if hasattr(state, "value") else str(state),
                    "optional": phase_def.optional,
                    "role": phase_def.role_id,
                    "completed": pid in self._completed_phases,
                }
            )

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

    def init_spec(
        self,
        template_id: str = "requirements",
        project_info: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Initialize a specification document from a template.

        Args:
            template_id: Identifier of the spec template to use.
            project_info: Optional project metadata to seed the spec.

        Returns:
            Dictionary containing the initialized specification.
        """
        shortcut = ShortcutLifecycleAdapter(use_unified_gate=self._use_unified_gate)
        return shortcut.init_spec(template_id, project_info)

    def analyze_spec(
        self,
        source_dir: str = ".",
        template_id: str = "requirements",
    ) -> dict[str, Any]:
        """Analyze a source directory against a spec template.

        Args:
            source_dir: Directory to analyze.
            template_id: Identifier of the spec template to compare against.

        Returns:
            Dictionary with analysis results.
        """
        shortcut = ShortcutLifecycleAdapter(use_unified_gate=self._use_unified_gate)
        return shortcut.analyze_spec(source_dir, template_id)

    def validate_spec(
        self,
        spec_path: str | None = None,
        template_id: str | None = None,
        spec_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Validate a specification against a template.

        Args:
            spec_path: Optional path to a spec file on disk.
            template_id: Optional template identifier to validate against.
            spec_data: Optional in-memory spec dictionary.

        Returns:
            Dictionary with validation results including errors and warnings.
        """
        shortcut = ShortcutLifecycleAdapter(use_unified_gate=self._use_unified_gate)
        return shortcut.validate_spec(spec_path, template_id, spec_data)


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
