#!/usr/bin/env python3
"""
Lifecycle Gate - Gate 机制实现

提供阶段转换的门控检查能力：
  - check_gate_basic(): 基础 fallback 门控检查（依赖 + 状态）
  - check_gate_with_unified_engine(): 使用 UnifiedGateEngine 的增强门控检查

从 lifecycle_protocol.py 拆分而来，ShortcutLifecycleAdapter 和 FullLifecycleAdapter
会委托到此处，避免在两个 adapter 中重复实现。

Spec reference: docs/spec/SPEC_Lifecycle_Unified_Architecture_C.md
"""

import logging
from typing import TYPE_CHECKING, Any

from .lifecycle_protocol import GateResult, PhaseDefinition, PhaseState

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def check_gate_basic(
    target: str,
    phase_def: PhaseDefinition,
    phase_states: dict[str, PhaseState],
    completed_phases: list[str],
    *,
    strict_optional: bool = False,
) -> GateResult:
    """
    Basic fallback gate check without UnifiedGateEngine.

    Args:
        target: Target phase ID.
        phase_def: PhaseDefinition for the target phase.
        phase_states: Current phase state mapping.
        completed_phases: List of completed phase IDs.
        strict_optional: If True, enforce dependency checks strictly for non-optional phases
            (used by FullLifecycleAdapter). If False (ShortcutLifecycleAdapter), only check
            that the phase is not blocked/completed.

    Returns:
        GateResult indicating whether the gate passed.
    """
    if strict_optional and not phase_def.optional:
        for dep in phase_def.dependencies:
            if dep not in completed_phases:
                dep_state = phase_states.get(dep, PhaseState.PENDING)
                if dep_state != PhaseState.COMPLETED:
                    return GateResult(
                        passed=False,
                        verdict="BLOCKED",
                        gap_report=f"Unmet dependencies: {dep}",
                    )
    current_state = phase_states.get(target, PhaseState.PENDING)
    if current_state == PhaseState.BLOCKED:
        return GateResult(passed=False, verdict="BLOCKED", gap_report="Phase is blocked")
    if current_state == PhaseState.COMPLETED:
        return GateResult(passed=True, verdict="APPROVE")

    # Check dependencies (non-strict path used by ShortcutLifecycleAdapter)
    if not strict_optional:
        unmet_deps = [d for d in phase_def.dependencies if d not in completed_phases]
        if unmet_deps:
            return GateResult(
                passed=False,
                verdict="CONDITIONAL",
                missing_evidence=[{"dependency": d} for d in unmet_deps],
                gap_report=f"Unmet dependencies: {', '.join(unmet_deps)}",
            )

    return GateResult(passed=True, verdict="APPROVE")


def check_gate_with_unified_engine(
    target: str,
    phase_def: PhaseDefinition,
    phase_states: dict[str, PhaseState],
    completed_phases: list[str],
    gate_engine: Any,
    gate_type: Any,
    phase_gate_context_cls: Any,
) -> GateResult:
    """
    Check gate using UnifiedGateEngine.

    Args:
        target: Target phase ID.
        phase_def: PhaseDefinition for the target phase.
        phase_states: Current phase state mapping.
        completed_phases: List of completed phase IDs.
        gate_engine: UnifiedGateEngine instance.
        gate_type: GateType enum class from unified_gate_engine.
        phase_gate_context_cls: PhaseGateContext class from unified_gate_engine.

    Returns:
        GateResult converted from the unified gate result.
    """
    unmet_deps = [d for d in phase_def.dependencies if d not in completed_phases]

    context = phase_gate_context_cls(
        phase_id=target,
        phase_name=phase_def.name,
        current_state=phase_states.get(target, PhaseState.PENDING).value,
        target_state="running",
        dependencies_met=len(unmet_deps) == 0,
        completed_phases=list(completed_phases),
        unmet_dependencies=unmet_deps,
    )

    unified_result = gate_engine.check(
        gate_type=gate_type.PHASE_TRANSITION,
        context=context,
    )

    return GateResult(
        passed=unified_result.passed,
        verdict=unified_result.verdict,
        red_flags=[
            {"id": issue.get("code", "unknown"), "severity": "critical", **issue}
            for issue in unified_result.critical_issues
        ],
        missing_evidence=[{"key": ev, "required": True} for ev in unified_result.evidence_required],
        gap_report="\n".join(
            [
                f"- [{issue.get('severity', 'unknown')}] {issue.get('message', '')}"
                for issue in unified_result.critical_issues + unified_result.warnings
            ]
        )
        if (unified_result.critical_issues or unified_result.warnings)
        else "",
    )
