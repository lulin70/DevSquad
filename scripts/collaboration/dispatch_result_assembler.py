#!/usr/bin/env python3
"""ResultAssembler — Extracted from MultiAgentDispatcher.

Takes raw dispatch data and builds the final DispatchResult.
Also contains step timing and lifecycle trace building helpers.
"""

import logging
from typing import Any

from .concern_pack_loader import ConcernPackLoader
from .dispatch_models import DispatchResult

logger = logging.getLogger(__name__)

# Dispatch step → Lifecycle phase mapping
DISPATCH_LIFECYCLE_MAPPING = {
    "step0_tenant_setup": "P1_Requirements",
    "step1_language": "P1_Requirements",
    "step2_validation": "P1_Requirements",
    "step3_rules": "P2_Architecture",
    "step4_intent": "P2_Architecture",
    "step5_role_match": "P3_Implementation",
    "step6_security": "P6_Security",
    "step7_preparation": "P3_Implementation",
    "step8_execute": "P3_Implementation",
    "step9_post_exec": "P4_Review",
    "step10_consensus": "P4_Review",
    "step11_permission": "P6_Security",
    "step12_memory": "P5_Integration",
    "step13_skillify": "P8_Optimization",
    "step14_five_axis": "P4_Review",
    "step15_retrospective": "P9_Retrospective",
    "step16_assemble": "P10_Delivery",
    "step17_hooks": "P10_Delivery",
    "step18_feedback": "P11_Monitoring",
    "step19_ue_testing": "P7_TestPlanning",
    "step20_tech_debt": "P9_TestExecution",
}


class ResultAssembler:
    """Assembles the final DispatchResult from raw dispatch pipeline data.

    Usage::

        assembler = ResultAssembler(concern_loader=loader, report_formatter=formatter)
        result = assembler.assemble(
            task_description=...,
            role_ids=...,
            exec_result=...,
            ...
        )
    """

    def __init__(self, concern_loader: ConcernPackLoader, report_formatter: Any) -> None:
        self._concern_loader = concern_loader
        self._report_formatter = report_formatter

    def assemble(
        self,
        task_description: str,
        role_ids: list[str],
        exec_result: Any,
        scratchpad_summary: str,
        consensus_records: list[dict[str, Any]],
        compression_info: Any,
        memory_stats: dict[str, Any] | None,
        permission_checks: list[dict[str, Any]],
        skill_proposals: list[dict[str, Any]],
        anchor_result: Any,
        retrospective_report: Any,
        intent_match: Any,
        five_axis_result: dict[str, Any] | None,
        errors: list[str],
        lang: str,
        concern_packs: Any,
        total_duration: float,
        plan: Any,
        step_timings: dict[str, float],
        worker_results: list[dict[str, Any]],
        coordinator: Any,
        tenant_id: str | None = None,
        enterprise: Any = None,
    ) -> DispatchResult:
        """Assemble the final DispatchResult from all step results."""
        report = coordinator.generate_report()

        # Data masking via enterprise feature
        if enterprise is not None:
            scratchpad_summary = enterprise.apply_data_masking(scratchpad_summary)

        return DispatchResult(
            success=exec_result.success and len(errors) == 0,
            task_description=task_description,
            matched_roles=role_ids,
            summary=self._build_summary(task_description, role_ids, exec_result, scratchpad_summary),
            details={
                "plan_total_tasks": plan.total_tasks,
                "completed_tasks": exec_result.completed_tasks,
                "failed_tasks": exec_result.failed_tasks,
                "report": report,
                "timing": step_timings,
                "tenant_id": tenant_id,
            },
            scratchpad_summary=scratchpad_summary,
            consensus_records=consensus_records,
            compression_info=compression_info,
            memory_stats=memory_stats,
            permission_checks=permission_checks,
            skill_proposals=skill_proposals,
            duration_seconds=total_duration,
            worker_results=worker_results,
            errors=errors,
            lang=lang,
            concern_packs=self._concern_loader.get_pack_info(concern_packs) if concern_packs else [],
            anchor_result=self._build_anchor_dict(anchor_result),
            suggested_next_steps=list(intent_match.suggested_next_steps) if intent_match else [],
            retrospective_report=retrospective_report.to_dict() if retrospective_report else None,
            intent_match=self._build_intent_dict(intent_match),
            five_axis_result=five_axis_result,
        )

    @staticmethod
    def _build_anchor_dict(anchor_result: Any) -> dict[str, Any] | None:
        """Build anchor result dict for DispatchResult."""
        if not anchor_result:
            return None
        return {
            "aligned": anchor_result.aligned,
            "coverage": anchor_result.coverage,
            "drift_score": anchor_result.drift_score,
            "severity": anchor_result.severity.value,
            "recommendation": anchor_result.recommendation,
        }

    @staticmethod
    def _build_intent_dict(intent_match: Any) -> dict[str, Any] | None:
        """Build intent match dict for DispatchResult."""
        if not intent_match:
            return None
        return {
            "intent_type": intent_match.intent_type,
            "workflow_chain": list(intent_match.workflow_chain),
            "confidence": intent_match.confidence,
            "suggested_next_steps": list(intent_match.suggested_next_steps) if hasattr(intent_match, 'suggested_next_steps') else [],
        }

    def _build_summary(self, task: str, roles: list[str], exec_result: Any, sp_summary: str) -> str:
        """Build execution summary."""
        return self._report_formatter.build_summary(task, roles, exec_result, sp_summary)

    @staticmethod
    def build_step_timings(
        step1: float, step2: float, step3: float, step4: float, step5: float,
        step6: float, step7: float, step8: float, step9: float, step10: float,
        step11: float, step12: float,
    ) -> dict[str, float]:
        """Build step timings dict from absolute timestamps."""
        names = ["analyze", "warmup", "plan", "spawn", "execute", "collect",
                 "consensus", "compress", "permission", "memory", "skillify"]
        times = [step1, step2, step3, step4, step5, step6, step7, step8, step9, step10, step11, step12]
        return {name: round(times[i + 1] - times[i], 3) for i, name in enumerate(names)}

    @staticmethod
    def build_lifecycle_trace(step_timings: dict[str, float]) -> dict[str, Any]:
        """Build lifecycle phase trace from step timings.

        Maps dispatch pipeline steps to lifecycle phases (P1-P11),
        aggregating timing per phase for observability.
        """
        step_to_lifecycle = {
            "analyze": "P1_Requirements",
            "warmup": "P2_Architecture",
            "plan": "P3_Implementation",
            "spawn": "P3_Implementation",
            "execute": "P3_Implementation",
            "collect": "P4_Review",
            "consensus": "P4_Review",
            "compress": "P5_Integration",
            "permission": "P6_Security",
            "memory": "P5_Integration",
            "skillify": "P8_Optimization",
        }

        phase_durations: dict[str, float] = {}
        phase_steps: dict[str, list[str]] = {}
        for step_name, duration in step_timings.items():
            phase = step_to_lifecycle.get(step_name, "P10_Delivery")
            phase_durations[phase] = phase_durations.get(phase, 0.0) + duration
            phase_steps.setdefault(phase, []).append(step_name)

        return {
            "lifecycle_phases": phase_durations,
            "phase_steps": phase_steps,
            "mapping_version": "1.0",
        }
