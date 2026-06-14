#!/usr/bin/env python3
"""DispatchStepsMixin — Step execution methods extracted from MultiAgentDispatcher.

This mixin reduces the God Class by moving dispatch pipeline step methods
into a separate module. All methods access `self.*` attributes from the
dispatcher instance at runtime via mixin composition.
"""

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from .ue_test_framework import UETestFramework
from .tech_debt_manager import TechDebtManager

logger = logging.getLogger(__name__)


class DispatchStepsMixin:
    """Mixin containing dispatch pipeline step methods.

    These methods are called by MultiAgentDispatcher._post_dispatch_steps()
    and related orchestration methods. They rely on `self` being a fully
    initialized MultiAgentDispatcher instance.
    """

    # ------------------------------------------------------------------
    # Step 8: Collect worker results
    # ------------------------------------------------------------------

    def _collect_worker_results(self, exec_result: Any) -> Tuple[List[Dict[str, Any]], float, float]:
        """Collect worker results from execution result into standardized dicts."""
        step6_time = time.time()
        worker_results: List[Dict[str, Any]] = []
        for r in exec_result.results:
            role_id = r.worker_id.split("-")[0] if "-" in r.worker_id else r.worker_id
            from .models import ROLE_REGISTRY

            rdef = ROLE_REGISTRY.get(role_id)
            role_name = rdef.name if rdef else role_id
            worker_results.append(
                {
                    "worker_id": r.worker_id,
                    "role_id": role_id,
                    "role_name": role_name,
                    "task_id": r.task_id,
                    "success": r.success,
                    "output": (r.output.get("finding_summary", "") if isinstance(r.output, dict) else str(r.output))
                    if r.output
                    else None,
                    "error": r.error,
                }
            )
        step7_time = time.time()
        return worker_results, step6_time, step7_time

    # ------------------------------------------------------------------
    # Step 10: Resolve consensus
    # ------------------------------------------------------------------

    def _resolve_consensus(
        self, collection: Any, mode: str
    ) -> Tuple[List[Dict[str, Any]], Any]:
        """Resolve consensus and get compression info. Returns (consensus_records, compression_info)."""
        consensus_records = []
        conflicts_count = collection.get("conflicts_count", 0)
        if conflicts_count > 0 or mode == "consensus":
            resolutions = self.coordinator.resolve_conflicts()
            for rec in resolutions:
                self._safe_metrics(lambda m: m.record_consensus_round(rec.outcome.value))
                consensus_records.append(
                    {
                        "topic": rec.topic,
                        "outcome": rec.outcome.value,
                        "final_decision": rec.final_decision,
                        "votes_for": rec.votes_for,
                        "votes_against": rec.votes_against,
                        "votes_abstain": rec.votes_abstain,
                    }
                )

        compression_info = None
        if self.enable_compression and self.compressor:
            stats = self.coordinator.get_compression_stats()
            if stats:
                compression_info = stats

        return consensus_records, compression_info

    # ------------------------------------------------------------------
    # Step 11: Check permissions
    # ------------------------------------------------------------------

    def _check_permissions(
        self, task: str, worker_results: List[Dict[str, Any]], consensus_records: List[Dict[str, Any]], **kwargs: Any
    ) -> List[Dict[str, Any]]:
        """Check permissions via PermissionGuard and RBAC.

        Returns:
            List of permission check results.
        """
        permission_checks = []
        if self.enable_permission and self.permission_guard:
            permission_checks = self._check_permission_guard(permission_checks)

        # RBAC fine-grained check
        if self.enable_rbac and self.rbac_engine:
            permission_checks = self._check_rbac_permission(permission_checks, **kwargs)

        return permission_checks

    # ------------------------------------------------------------------
    # Step 12: Process memory pipeline
    # ------------------------------------------------------------------

    def _process_memory_pipeline(
        self,
        task: str,
        worker_results: List[Dict[str, Any]],
        lang: str,
        scratchpad_summary: str,
        role_ids: List[str],
    ) -> Tuple[Optional[Dict[str, Any]], List[str]]:
        """Process memory pipeline: capture + MCE classify + AI news inject."""
        errors: List[str] = []

        memory_stats = self._capture_memory(task, scratchpad_summary, role_ids, errors)
        memory_stats = self._classify_mce(scratchpad_summary, task, memory_stats, errors)
        self._inject_ai_news(task, errors)

        return memory_stats, errors

    # ------------------------------------------------------------------
    # Step 13: Learn skills
    # ------------------------------------------------------------------

    def _learn_skills(
        self,
        task: str,
        worker_results: List[Dict[str, Any]],
        matched_roles: List[Dict[str, Any]],
        exec_result: Any,
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Learn skills via Skillifier. Returns (skill_proposals, errors)."""
        errors: List[str] = []
        skill_proposals = []
        patterns = None

        if self.enable_skillify and self.skillifier and exec_result.success:
            try:
                patterns = self.skillifier.analyze_history()
                if patterns:
                    skill_proposals = self._propose_skills_from_patterns(patterns)
            except (ValueError, AttributeError, RuntimeError, ImportError) as skill_err:
                errors.append(f"Skillifier error: {skill_err}")

        if self.prompt_variant_gen and patterns:
            try:
                for pattern in patterns:
                    if pattern.confidence > 0.5:
                        variants = self.prompt_variant_gen.generate_from_pattern(pattern)
                        if variants:
                            if self.usage_tracker:
                                self.usage_tracker.tick("prompt_variant_generated")
            except (ValueError, AttributeError, RuntimeError) as e:
                logger.warning(f"PromptVariantGenerator failed: {e}")

        return skill_proposals, errors

    # ------------------------------------------------------------------
    # Step 14: Five-axis consensus
    # ------------------------------------------------------------------

    def _run_five_axis_consensus(
        self, task: str, worker_results: List[Dict[str, Any]], mode: str, exec_result: Any
    ) -> Optional[Dict[str, Any]]:
        """Run five-axis consensus review (consensus mode only)."""
        if mode != "consensus" or not exec_result.success:
            return None

        try:
            from .five_axis_consensus import FiveAxisConsensusEngine, ReviewAxis

            fa_engine = FiveAxisConsensusEngine()
            review = fa_engine.create_review("system", "dispatcher")
            for wr in worker_results:
                output_text = wr.get("output") or wr.get("error") or ""
                if output_text:
                    fa_engine.add_axis_vote(review, ReviewAxis.CORRECTNESS, 0.8, 0.7)
                    fa_engine.add_axis_vote(review, ReviewAxis.READABILITY, 0.8, 0.7)
                    fa_engine.add_axis_vote(review, ReviewAxis.ARCHITECTURE, 0.8, 0.7)
                    fa_engine.add_axis_vote(review, ReviewAxis.SECURITY, 0.7, 0.6)
                    fa_engine.add_axis_vote(review, ReviewAxis.PERFORMANCE, 0.7, 0.6)
                    break
            fa_result = fa_engine.compute_consensus([review])
            five_axis_result = {
                "verdict": fa_result.verdict,
                "overall_consensus": fa_result.overall_consensus,
                "axis_consensus": fa_result.axis_consensus,
                "action_items": fa_result.action_items,
            }
            if self.usage_tracker:
                self.usage_tracker.tick("five_axis_consensus")
            return five_axis_result
        except (ImportError, AttributeError, ValueError, RuntimeError) as fa_err:
            logger.debug("Five-axis consensus failed: %s", fa_err)
            return None

    # ------------------------------------------------------------------
    # Step 15: Retrospective
    # ------------------------------------------------------------------

    def _run_retrospective(
        self,
        task: str,
        worker_results: List[Dict[str, Any]],
        structured_goal: Any,
        exec_result: Any,
        total_duration: float,
    ) -> Any:
        """Run RetrospectiveEngine analysis. Returns report or None."""
        if not self.retrospective_engine or not structured_goal or not exec_result.success:
            return None

        try:
            if self.usage_tracker:
                self.usage_tracker.tick("retrospective")
            anchor_history = self.anchor_checker.check_history if self.anchor_checker else []
            retrospective_report = self.retrospective_engine.run(
                goal=structured_goal,
                anchor_history=anchor_history,
                worker_outputs={
                    wr["role_id"]: wr.get("output", "") for wr in worker_results if wr.get("output")
                },
                task_duration_seconds=total_duration,
            )
            return retrospective_report
        except (ValueError, AttributeError, RuntimeError, ImportError) as retro_err:
            logger.warning("Retrospective failed: %s", retro_err)
            return None

    # ------------------------------------------------------------------
    # Step 18: Feedback loop
    # ------------------------------------------------------------------

    def _run_feedback_loop(
        self,
        task: str,
        result: Any,
        lang: str,
        roles: Optional[List[str]],
        mode: str,
        dry_run: bool,
        kwargs: Dict[str, Any],
    ) -> Any:
        """Run FeedbackControlLoop iteration. Returns final (possibly refined) result.

        Modes:
            True:  Always run feedback loop (up to 3 iterations)
            "auto": Only trigger when first-pass quality < 0.5 (critical failure)
            False: Never run feedback loop
        """
        if self.enable_feedback_loop is False or dry_run:
            return result

        # Auto mode: assess first-pass quality, only trigger on critical failure
        if self.enable_feedback_loop == "auto":
            try:
                from .feedback_control_loop import FeedbackControlLoop
                loop = FeedbackControlLoop(dispatcher=self)
                first_quality = loop._assess_quality(result)
                if first_quality >= 0.5:
                    logger.debug(
                        "Feedback loop auto-skip: first-pass quality %.2f >= 0.5 threshold",
                        first_quality,
                    )
                    return result
                logger.info(
                    "Feedback loop auto-triggered: first-pass quality %.2f < 0.5",
                    first_quality,
                )
            except (ImportError, ValueError, AttributeError) as e:
                logger.debug("Feedback loop auto-assessment failed: %s", e)
                return result

        try:
            from .feedback_control_loop import FeedbackControlLoop

            feedback_loop = FeedbackControlLoop(
                dispatcher=self,
                quality_gate=0.7,
                max_iterations=3,
                llm_backend=self.llm_backend,
            )
            result = feedback_loop.run(
                task,
                roles=roles,
                mode=mode,
                **{k: v for k, v in kwargs.items() if k not in ["dry_run"]},
            )
            if self.usage_tracker:
                self.usage_tracker.tick("feedback_loop_executed")
            logger.info(
                "Feedback loop completed: %d iterations, best_quality=%.2f",
                feedback_loop.iteration_count,
                feedback_loop.best_quality,
            )
        except (ImportError, ValueError, AttributeError, RuntimeError) as loop_err:
            logger.warning("Feedback control loop failed: %s", loop_err)

        return result

    # ------------------------------------------------------------------
    # Step 19: UE testing
    # ------------------------------------------------------------------

    def _run_ue_testing(
        self,
        task: str,
        role_ids: List[str],
        worker_results: List[Dict[str, Any]],
        lang: str,
    ) -> Optional[Dict[str, Any]]:
        """Step 19: Generate UE test plan when tester role is involved.

        Bridges Tester and PM perspectives to produce user-experience-focused
        test dimensions that go beyond code correctness.

        Returns:
            Dict with ue_test_plan data, or None if tester role not involved.
        """
        tester_involved = any(
            rid in ("tester", "product-manager", "ui-designer")
            for rid in role_ids
        )
        if not tester_involved:
            return None

        try:
            if not hasattr(self, '_ue_framework') or self._ue_framework is None:
                self._ue_framework = UETestFramework(llm_backend=self.llm_backend)
            framework = self._ue_framework
            plan = framework.generate_ue_test_plan(task)

            # Extract tester/PM outputs for journey validation
            tester_output = ""
            pm_output = ""
            for wr in worker_results:
                role = wr.get("role_id", "")
                if role == "tester":
                    tester_output = wr.get("output", "")
                elif role == "product-manager":
                    pm_output = wr.get("output", "")

            # If PM defined user stories, validate against them
            if pm_output:
                validation = framework.validate_user_journey(
                    plan.journey_tests[0] if plan.journey_tests else None,
                    {"pm_output": pm_output, "tester_output": tester_output},
                )
                if validation:
                    return {
                        "persona_scenarios": plan.persona_scenarios,
                        "journey_tests": plan.journey_tests,
                        "heuristic_checks": [
                            {"name": h.name, "description": h.description, "passed": h.passed}
                            for h in plan.heuristic_checks
                        ],
                        "accessibility_checks": plan.accessibility_checks,
                        "cognitive_load_assessment": plan.cognitive_load_assessment,
                        "journey_validation": {
                            "completion_rate": validation.completion_rate,
                            "error_recovery_rate": validation.error_recovery_rate,
                            "frustration_events": validation.frustration_events,
                            "overall_ue_score": validation.overall_ue_score,
                        },
                    }

            return {
                "persona_scenarios": plan.persona_scenarios,
                "journey_tests": plan.journey_tests,
                "heuristic_checks": [
                    {"name": h.name, "description": h.description, "passed": h.passed}
                    for h in plan.heuristic_checks
                ],
                "accessibility_checks": plan.accessibility_checks,
                "cognitive_load_assessment": plan.cognitive_load_assessment,
            }
        except (ValueError, AttributeError, ImportError, RuntimeError) as e:
            logger.debug("UE test plan generation failed: %s", e)
            return None

    # ------------------------------------------------------------------
    # Step 20: Tech debt scan
    # ------------------------------------------------------------------

    def _run_tech_debt_scan(
        self,
        task: str,
        worker_results: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Step 20: Scan for technical debt after dispatch.

        Bridges Tester and Architect perspectives to identify and track
        technical debt items from dispatch results.

        Returns:
            Dict with tech_debt_report data, or None on failure.
        """
        try:
            # Skip if no tester or architect role involved
            has_relevant_role = any(
                wr.get("role_id") in ("tester", "architect")
                for wr in worker_results
            )
            if not has_relevant_role:
                return None

            if not hasattr(self, '_debt_manager') or self._debt_manager is None:
                self._debt_manager = TechDebtManager(persist_dir=self.persist_dir)
            manager = self._debt_manager

            # Identify debts from worker outputs
            for wr in worker_results:
                role = wr.get("role_id", "")
                output = wr.get("output", "")
                if not output:
                    continue

                # Tester identifies test gaps
                if role == "tester":
                    self._extract_test_debts(manager, output, task)

                # Architect identifies structural debts
                elif role == "architect":
                    self._extract_arch_debts(manager, output, task)

            # Generate report
            report = manager.get_debt_report()
            return {
                "total_debts": report.total_debts,
                "by_category": report.by_category,
                "by_severity": report.by_severity,
                "top_priority": [
                    {
                        "id": d.id,
                        "category": d.category.value,
                        "description": d.description,
                        "severity": d.severity.value,
                        "effort": d.effort.value,
                    }
                    for d in report.top_priority[:5]
                ],
                "debt_to_value_ratio": report.debt_to_value_ratio,
                "remediation_progress": report.remediation_progress,
            }
        except (ValueError, AttributeError, ImportError, RuntimeError) as e:
            logger.debug("Tech debt scan failed: %s", e)
            return None

    def _extract_test_debts(self, manager: Any, output: str, task: str) -> None:
        """Extract test-gap debts from tester output."""
        from .tech_debt_manager import DebtCategory, DebtSeverity, DebtEffort
        lower = output.lower()
        if "missing test" in lower or "no test" in lower or "untested" in lower:
            manager.identify_debt(
                source="tester",
                category=DebtCategory.TEST_GAP,
                description=f"Test gap identified during dispatch: {task[:80]}",
                location="dispatch_output",
                severity=DebtSeverity.MEDIUM,
                effort=DebtEffort.MINOR,
                tags=["auto-detected", "test-gap"],
            )
        if "flaky" in lower or "intermittent" in lower:
            manager.identify_debt(
                source="tester",
                category=DebtCategory.TEST_GAP,
                description=f"Flaky test detected: {task[:80]}",
                location="dispatch_output",
                severity=DebtSeverity.HIGH,
                effort=DebtEffort.MODERATE,
                tags=["auto-detected", "flaky-test"],
            )

    def _extract_arch_debts(self, manager: Any, output: str, task: str) -> None:
        """Extract architecture debts from architect output."""
        from .tech_debt_manager import DebtCategory, DebtSeverity, DebtEffort
        lower = output.lower()
        if "circular" in lower or "cyclic" in lower:
            manager.identify_debt(
                source="architect",
                category=DebtCategory.ARCHITECTURE,
                description=f"Circular dependency: {task[:80]}",
                location="dispatch_output",
                severity=DebtSeverity.HIGH,
                effort=DebtEffort.MAJOR,
                tags=["auto-detected", "circular-dep"],
            )
        if "god class" in lower or "too large" in lower or "monolith" in lower:
            manager.identify_debt(
                source="architect",
                category=DebtCategory.ARCHITECTURE,
                description=f"God class / oversized module: {task[:80]}",
                location="dispatch_output",
                severity=DebtSeverity.HIGH,
                effort=DebtEffort.MAJOR,
                tags=["auto-detected", "god-class"],
            )
        if "tight coupling" in lower or "coupled" in lower:
            manager.identify_debt(
                source="architect",
                category=DebtCategory.ARCHITECTURE,
                description=f"Tight coupling: {task[:80]}",
                location="dispatch_output",
                severity=DebtSeverity.MEDIUM,
                effort=DebtEffort.MODERATE,
                tags=["auto-detected", "coupling"],
            )

    # ------------------------------------------------------------------
    # Result building helpers
    # ------------------------------------------------------------------

    def _build_step_timings(
        self, step1: float, step2: float, step3: float, step4: float, step5: float,
        step6: float, step7: float, step8: float, step9: float, step10: float,
        step11: float, step12: float,
    ) -> Dict[str, float]:
        """Build step timings dict from absolute timestamps."""
        names = ["analyze", "warmup", "plan", "spawn", "execute", "collect",
                 "consensus", "compress", "permission", "memory", "skillify"]
        times = [step1, step2, step3, step4, step5, step6, step7, step8, step9, step10, step11, step12]
        return {name: round(times[i + 1] - times[i], 3) for i, name in enumerate(names)}

    def _build_lifecycle_trace(self, step_timings: Dict[str, float]) -> Dict[str, Any]:
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

        phase_durations: Dict[str, float] = {}
        phase_steps: Dict[str, list[str]] = {}
        for step_name, duration in step_timings.items():
            phase = step_to_lifecycle.get(step_name, "P10_Delivery")
            phase_durations[phase] = phase_durations.get(phase, 0.0) + duration
            phase_steps.setdefault(phase, []).append(step_name)

        return {
            "lifecycle_phases": phase_durations,
            "phase_steps": phase_steps,
            "mapping_version": "1.0",
        }

    def _build_summary(self, task: str, roles: List[str], exec_result: Any, sp_summary: str) -> str:
        """Build execution summary."""
        return self.report_formatter.build_summary(task, roles, exec_result, sp_summary)
