#!/usr/bin/env python3
"""Lifecycle gate helpers for deterministic lifecycle findings and phase transitions.
Lifecycle Gate - Gate 机制实现

提供阶段转换的门控检查能力：
  - check_gate_basic(): 基础 fallback 门控检查（依赖 + 状态）
  - check_gate_with_unified_engine(): 使用 UnifiedGateEngine 的增强门控检查

从 lifecycle_protocol.py 拆分而来，ShortcutLifecycleAdapter 和 FullLifecycleAdapter
会委托到此处，避免在两个 adapter 中重复实现。

Spec reference: docs/spec/SPEC_Lifecycle_Unified_Architecture_C.md
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, Any

from .lifecycle_finding_producers import PHASE_PRODUCERS, produce_phase_findings

if TYPE_CHECKING:
    from .lifecycle_protocol import GateResult, PhaseDefinition, PhaseState

logger = logging.getLogger(__name__)


def _merge_findings(result: GateResult, target: str, artifacts: Mapping[str, Any] | None) -> GateResult:
    """Attach deterministic lifecycle findings to a gate result."""
    if target in PHASE_PRODUCERS:
        result.lifecycle_findings.extend(produce_phase_findings(target, artifacts))
    return result


def _role_participation_gate(phase_def: Any, artifacts: Mapping[str, Any] | None) -> GateResult | None:
    """Run the role participation gate when participating roles are supplied.

    Returns ``None`` when the artifacts carry no participating roles so that
    callers keep their existing behaviour (backward compatible).
    """
    if not isinstance(artifacts, Mapping):
        return None
    participating_roles = artifacts.get("participating_roles")
    if not participating_roles:
        return None
    phase = {
        "role_id": phase_def.role_id,
        "reviewers": list(phase_def.reviewers),
    }
    return check_role_participation(phase, participating_roles)


def check_role_participation(
    phase: Mapping[str, Any],
    participating_roles: Iterable[str],
) -> GateResult:
    """Check that every role required by a phase has participated.

    Args:
        phase: Phase definition mapping with ``role_id`` and ``reviewers``.
        participating_roles: Role IDs that took part in the phase.

    Returns:
        Passing GateResult when all required roles participated, otherwise a
        failing GateResult that names each missing role.
    """
    from .lifecycle_protocol import GateResult
    from .workflow_engine_base import required_roles_for_phase

    required = required_roles_for_phase(phase)
    participated = {role for role in participating_roles if role}
    missing = [role for role in required if role not in participated]
    if not missing:
        return GateResult(passed=True, verdict="APPROVE")
    return GateResult(
        passed=False,
        verdict="REJECT",
        missing_evidence=[{"role": role, "reason": "required participant missing"} for role in missing],
        gap_report=f"Missing required roles: {', '.join(missing)}",
    )


def check_gate_basic(
    target: str,
    phase_def: PhaseDefinition,
    phase_states: dict[str, PhaseState],
    completed_phases: list[str],
    *,
    strict_optional: bool = False,
    artifacts: Mapping[str, Any] | None = None,
) -> GateResult:
    """
    Basic fallback gate check without UnifiedGateEngine.

    Args:
        target: Target phase ID.
        phase_def: PhaseDefinition for the target phase.
        phase_states: Current phase state mapping.
        completed_phases: List of completed phase IDs.
        strict_optional: If True, enforce dependency checks strictly for non-optional phases
            (used by FullLifecycleAdapter). If False (ShortcutLifecycleAdapter), report unmet
            dependencies conditionally while still handling blocked/completed phases.
        artifacts: Optional artifact mapping used to produce lifecycle findings.

    Returns:
        GateResult indicating whether the gate passed.
    """
    from .lifecycle_protocol import GateResult, PhaseState

    role_gate = _role_participation_gate(phase_def, artifacts)
    if role_gate is not None and not role_gate.passed:
        return _merge_findings(role_gate, target, artifacts)

    if strict_optional and not phase_def.optional:
        for dep in phase_def.dependencies:
            if dep not in completed_phases:
                dep_state = phase_states.get(dep, PhaseState.PENDING)
                if dep_state != PhaseState.COMPLETED:
                    return _merge_findings(
                        GateResult(passed=False, verdict="BLOCKED", gap_report=f"Unmet dependencies: {dep}"),
                        target,
                        artifacts,
                    )
    current_state = phase_states.get(target, PhaseState.PENDING)
    if current_state == PhaseState.BLOCKED:
        return _merge_findings(
            GateResult(passed=False, verdict="BLOCKED", gap_report="Phase is blocked"), target, artifacts
        )
    if current_state == PhaseState.COMPLETED:
        return _merge_findings(GateResult(passed=True, verdict="APPROVE"), target, artifacts)

    if not strict_optional:
        unmet_deps = [d for d in phase_def.dependencies if d not in completed_phases]
        if unmet_deps:
            return _merge_findings(
                GateResult(
                    passed=False,
                    verdict="CONDITIONAL",
                    missing_evidence=[{"dependency": d} for d in unmet_deps],
                    gap_report=f"Unmet dependencies: {', '.join(unmet_deps)}",
                ),
                target,
                artifacts,
            )

    return _merge_findings(GateResult(passed=True, verdict="APPROVE"), target, artifacts)


def check_gate_with_unified_engine(
    target: str,
    phase_def: PhaseDefinition,
    phase_states: dict[str, PhaseState],
    completed_phases: list[str],
    gate_engine: Any,
    gate_type: Any,
    phase_gate_context_cls: Any,
    *,
    artifacts: Mapping[str, Any] | None = None,
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
    from .lifecycle_protocol import GateResult, PhaseState

    role_gate = _role_participation_gate(phase_def, artifacts)
    if role_gate is not None and not role_gate.passed:
        return _merge_findings(role_gate, target, artifacts)

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

    return _merge_findings(
        GateResult(
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
        ),
        target,
        artifacts,
    )
