#!/usr/bin/env python3
"""
Lifecycle Shortcut Helpers — V3.8.1 P1: Helper functions extracted from
ShortcutLifecycleAdapter and FullLifecycleAdapter.

This module contains the shared helper functions, utility methods, and
constants used by both :class:`ShortcutLifecycleAdapter` and
:class:`FullLifecycleAdapter`. It was split out of
``lifecycle_shortcut_adapter.py`` to keep the adapter classes focused on
their public API and reduce code duplication.

Contents
--------
- Gate engine initialization helpers
- Checkpoint manager initialization helpers
- State persistence (save/restore) helpers
- Phase lookup helpers (get_all_phases, get_phase)
- Gate checking helpers
- View mapping helpers
- Spec template helpers (init_spec, analyze_spec, validate_spec)
- Phase execution order builder (topological sort)

Spec reference: docs/spec/SPEC_Lifecycle_Unified_Architecture_C.md
"""

from __future__ import annotations

import contextlib
import json
import logging
from pathlib import Path
from typing import Any, cast

from .lifecycle_gate import check_gate_basic, check_gate_with_unified_engine
from .lifecycle_protocol import (
    GateResult,
    LifecycleMode,
    PhaseDefinition,
    PhaseState,
)
from .lifecycle_templates import SPEC_TEMPLATES, VIEW_MAPPINGS, ViewMapping

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Gate engine initialization
# ---------------------------------------------------------------------------


def init_gate_engine(
    use_unified_gate: bool,
    adapter_name: str = "LifecycleAdapter",
) -> tuple[Any, Any, Any, bool]:
    """Initialize the UnifiedGateEngine if requested.

    Args:
        use_unified_gate: Whether to attempt using the unified gate engine.
        adapter_name: Name of the adapter (for logging).

    Returns:
        Tuple of (gate_engine, GateType, PhaseGateContext, use_unified_gate).
        When the engine is unavailable, gate_engine is None and
        use_unified_gate is False.
    """
    if not use_unified_gate:
        return None, None, None, False

    try:
        from scripts.collaboration.unified_gate_engine import (
            GateType,
            PhaseGateContext,
            get_shared_gate_engine,
        )

        gate_engine = get_shared_gate_engine()
        logger.debug("UnifiedGateEngine initialized for %s", adapter_name)
        return gate_engine, GateType, PhaseGateContext, True
    except ImportError as e:
        logger.warning("UnifiedGateEngine not available: %s", e)
        return None, None, None, False


# ---------------------------------------------------------------------------
# Checkpoint manager initialization
# ---------------------------------------------------------------------------


def init_checkpoint_manager_for_task(task_id: str) -> Any:
    """Initialize a CheckpointManager for the given task ID.

    Args:
        task_id: Identifier of the task to track.

    Returns:
        A CheckpointManager instance, or None if unavailable.
    """
    try:
        from scripts.collaboration.checkpoint_manager import CheckpointManager

        manager = CheckpointManager()
        logger.info("CheckpointManager initialized for task %s", task_id)
        return manager
    except ImportError as e:
        logger.warning("CheckpointManager not available: %s", e)
        return None


def create_checkpoint_manager(storage_path: str = ".") -> Any:
    """Create a CheckpointManager at the given storage path.

    Args:
        storage_path: Base directory under which checkpoints/ and handoffs/
            subdirs are created. Callers must NOT pass a path already ending
            in "checkpoints" (nested duplicates would be created).

    Returns:
        A CheckpointManager instance, or None if unavailable.
    """
    try:
        from scripts.collaboration.checkpoint_manager import CheckpointManager

        manager = CheckpointManager(storage_path=storage_path)
        logger.info("CheckpointManager enabled at %s", storage_path)
        return manager
    except (ImportError, AttributeError, OSError) as e:
        logger.warning("Failed to enable checkpoint integration: %s", e)
        return None


# ---------------------------------------------------------------------------
# State persistence (save/restore)
# ---------------------------------------------------------------------------


def save_lifecycle_state_to_checkpoint(
    checkpoint_manager: Any,
    task_id: str,
    current_phase: str | None,
    phase_states: dict[str, PhaseState],
    completed_phases: list[str],
    mode: LifecycleMode,
    metadata: dict[str, Any] | None = None,
) -> bool:
    """Save lifecycle state to the checkpoint manager.

    Args:
        checkpoint_manager: The CheckpointManager instance.
        task_id: Task identifier.
        current_phase: Currently active phase ID (or None).
        phase_states: Mapping of phase ID to PhaseState.
        completed_phases: List of completed phase IDs.
        mode: Current lifecycle mode.
        metadata: Optional metadata to include in the checkpoint.

    Returns:
        True if saved successfully, False otherwise.
    """
    if not checkpoint_manager or not task_id:
        return False

    try:
        phase_states_str = {
            pid: (state.value if hasattr(state, "value") else str(state))
            for pid, state in phase_states.items()
        }
        mode_str = mode.value if hasattr(mode, "value") else str(mode)

        return cast(
            bool,
            checkpoint_manager.save_lifecycle_state(
                task_id=task_id,
                current_phase=current_phase,
                phase_states=phase_states_str,
                completed_phases=completed_phases.copy(),
                mode=mode_str,
                metadata=metadata or {},
            ),
        )
    except (OSError, AttributeError, ValueError) as e:
        logger.warning("Failed to save lifecycle state: %s", e)
        return False


def restore_lifecycle_state_from_checkpoint(
    checkpoint_manager: Any,
    task_id: str,
    default_mode: LifecycleMode = LifecycleMode.SHORTCUT,
) -> dict[str, Any] | None:
    """Restore lifecycle state from the checkpoint manager.

    Args:
        checkpoint_manager: The CheckpointManager instance.
        task_id: Task identifier.
        default_mode: Mode to use if the checkpoint has no mode field.

    Returns:
        Dictionary with restored state fields (current_phase,
        completed_phases, phase_states, mode, metadata), or None on
        failure / when no checkpoint exists.
    """
    if not checkpoint_manager or not task_id:
        return None

    try:
        state = checkpoint_manager.load_lifecycle_state(task_id)
        if not state:
            return None

        current_phase = state.get("current_phase")
        completed_phases = state.get("completed_phases", [])

        # Rebuild phase_states dict from string values
        phase_states: dict[str, PhaseState] = {}
        phase_states_raw = state.get("phase_states", {})
        for pid, pstate in phase_states_raw.items():
            try:
                phase_states[pid] = PhaseState(pstate)
            except ValueError:
                phase_states[pid] = PhaseState.PENDING

        # Restore mode
        mode_raw = state.get("mode", default_mode.value)
        with contextlib.suppress(ValueError):
            mode = LifecycleMode(mode_raw)

        metadata = state.get("metadata", {})

        logger.info(
            "Restored lifecycle state: task=%s, phase=%s",
            task_id,
            current_phase,
        )
        return {
            "current_phase": current_phase,
            "completed_phases": completed_phases,
            "phase_states": phase_states,
            "mode": mode if "mode" in dir() else default_mode,
            "metadata": metadata,
        }
    except (OSError, AttributeError, ValueError, KeyError) as e:
        logger.warning("Failed to restore lifecycle state: %s", e)
        return None


# ---------------------------------------------------------------------------
# Phase lookup helpers
# ---------------------------------------------------------------------------


def get_all_phase_definitions() -> list[PhaseDefinition]:
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


def get_phase_definition(phase_id: str) -> PhaseDefinition | None:
    """Look up a single phase definition by ID.

    Args:
        phase_id: Identifier of the phase to retrieve.

    Returns:
        The matching PhaseDefinition, or None when not found.
    """
    for p in get_all_phase_definitions():
        if p.phase_id == phase_id:
            return p
    return None


# ---------------------------------------------------------------------------
# Gate checking helpers
# ---------------------------------------------------------------------------


def check_phase_gate(
    target: str,
    phase_def: PhaseDefinition | None,
    phase_states: dict[str, PhaseState],
    completed_phases: list[str],
    use_unified_gate: bool,
    gate_engine: Any,
    gate_type: Any,
    phase_gate_context: Any,
    strict_optional: bool = False,
) -> GateResult:
    """Check the gate conditions for a phase.

    Args:
        target: Phase ID to check.
        phase_def: PhaseDefinition for the target phase (or None).
        phase_states: Current phase states mapping.
        completed_phases: List of completed phase IDs.
        use_unified_gate: Whether to use the unified gate engine.
        gate_engine: The UnifiedGateEngine instance (or None).
        gate_type: GateType enum class (or None).
        phase_gate_context: PhaseGateContext class (or None).
        strict_optional: Whether to enforce strict optional phase checks.

    Returns:
        GateResult indicating whether the gate passed.
    """
    if not target:
        return GateResult(passed=True, verdict="APPROVE")

    if not phase_def:
        return GateResult(
            passed=False, verdict="REJECT", gap_report=f"Phase {target} not found"
        )

    # Use UnifiedGateEngine if available
    if use_unified_gate and gate_engine:
        try:
            return check_gate_with_unified_engine(
                target,
                phase_def,
                phase_states,
                completed_phases,
                gate_engine,
                gate_type,
                phase_gate_context,
            )
        except Exception as e:  # Broad catch: unpredictable gate engine
            logger.warning("UnifiedGateEngine failed, falling back: %s", e)

    # Fallback to basic gate checks
    return check_gate_basic(
        target, phase_def, phase_states, completed_phases, strict_optional=strict_optional
    )


# ---------------------------------------------------------------------------
# View mapping helpers
# ---------------------------------------------------------------------------


def get_view_mapping_for_command(command: str) -> ViewMapping | None:
    """Return the view mapping for a CLI command.

    Args:
        command: CLI command name.

    Returns:
        The matching ViewMapping, or None when no mapping exists.
    """
    return VIEW_MAPPINGS.get(command)


def find_current_mapping(current_phase: str | None) -> ViewMapping | None:
    """Find the view mapping that covers the current phase.

    Args:
        current_phase: The currently active phase ID (or None).

    Returns:
        The ViewMapping covering the current phase, or None.
    """
    if not current_phase:
        return None
    for mapping in VIEW_MAPPINGS.values():
        if mapping.covers_phase(current_phase):
            return mapping
    return None


def resolve_command_to_phase_definitions(command: str) -> list[PhaseDefinition]:
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
    return [p for p in get_all_phase_definitions() if mapping.covers_phase(p.phase_id)]


# ---------------------------------------------------------------------------
# Phase execution order builder (topological sort)
# ---------------------------------------------------------------------------


def build_phase_execution_order() -> list[str]:
    """Build topological execution order based on phase dependencies.

    Returns:
        List of phase IDs in topological (dependency-respecting) order.
    """
    from scripts.collaboration.workflow_engine import PHASE_TEMPLATES

    visited: set[str] = set()
    order: list[str] = []

    def visit(phase_id: str) -> None:
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

    logger.debug("Full execution order: %s", order)
    return order


# ---------------------------------------------------------------------------
# Spec template helpers
# ---------------------------------------------------------------------------


def create_spec_from_template(
    template_id: str = "requirements",
    project_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Initialize a specification document from template.

    Args:
        template_id: Template type (requirements/architecture/technical).
        project_info: Optional project information to pre-fill.

    Returns:
        Dict with success status and spec document structure.
    """
    template = SPEC_TEMPLATES.get(template_id)
    if not template:
        return {"success": False, "error": f"Unknown template: {template_id}"}

    doc: dict[str, Any] = {
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


def analyze_source_directory(
    source_dir: str = ".",
    template_id: str = "requirements",
) -> dict[str, Any]:
    """Analyze existing codebase to generate specification draft.

    Uses CodeMapGenerator for multi-language code analysis.

    Args:
        source_dir: Root directory to analyze.
        template_id: Template to use for structuring the analysis.

    Returns:
        Dict with success status and analysis results.
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
            "languages": list(
                {m.get("language", "python") for m in code_map.values() if isinstance(m, dict)}
            ),
        }

        return {"success": True, "analysis": analysis, "template_id": template_id}
    except (ImportError, AttributeError, OSError, ValueError) as e:
        return {"success": False, "error": str(e)}


def validate_spec_data(
    spec_path: str | None = None,
    template_id: str | None = None,
    spec_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate specification completeness and consistency.

    Args:
        spec_path: Path to specification file (optional).
        template_id: Template to validate against.
        spec_data: Specification data dict to validate (optional).

    Returns:
        Dict with validation results.
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
        if check == "not_empty" and (
            not value or (isinstance(value, str) and not value.strip())
        ):
            results["warnings"].append(
                {
                    "field": field_name,
                    "message": f"Field '{field_name}' should not be empty",
                    "severity": severity,
                }
            )

    return results


__all__ = [
    # Gate engine
    "init_gate_engine",
    # Checkpoint
    "init_checkpoint_manager_for_task",
    "create_checkpoint_manager",
    "save_lifecycle_state_to_checkpoint",
    "restore_lifecycle_state_from_checkpoint",
    # Phase lookup
    "get_all_phase_definitions",
    "get_phase_definition",
    # Gate checking
    "check_phase_gate",
    # View mapping
    "get_view_mapping_for_command",
    "find_current_mapping",
    "resolve_command_to_phase_definitions",
    # Execution order
    "build_phase_execution_order",
    # Spec helpers
    "create_spec_from_template",
    "analyze_source_directory",
    "validate_spec_data",
]
