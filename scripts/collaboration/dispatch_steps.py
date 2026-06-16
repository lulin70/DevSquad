#!/usr/bin/env python3
"""PostDispatchPipeline — Post-dispatch step methods extracted from MultiAgentDispatcher.

This pipeline reduces the God Class by moving post-dispatch pipeline step methods
(steps 8-20) into a separate module. Uses composition pattern: receives all
dependencies via __init__ instead of relying on mixin self.* attribute sharing.

Pipeline steps covered:
  Step 8:  Collect worker results
  Step 10: Resolve consensus
  Step 11: Check permissions
  Step 12: Process memory pipeline
  Step 13: Learn skills
  Step 14: Five-axis consensus
  Step 15: Retrospective
  Step 18: Feedback loop
  Step 19: UE testing
  Step 20: Tech debt scan
"""

import logging
import time
from typing import Any

from .dispatch_models import DispatchResult
from .dispatch_result_assembler import ResultAssembler
from .dispatch_services import MemoryPipelineService, MetricsService, PermissionService, SkillProposalService
from .event_bus import EventBus
from .tech_debt_manager import TechDebtManager
from .ue_test_framework import UETestFramework

logger = logging.getLogger(__name__)


class PostDispatchPipeline:
    """Post-dispatch pipeline containing steps 8-20.

    Receives all dependencies via __init__ (composition pattern) instead of
    relying on mixin self.* attribute sharing.
    """

    def __init__(
        self,
        # Core components
        coordinator: Any,
        report_formatter: Any,
        enterprise: Any,
        # Service instances
        metrics_service: MetricsService,
        permission_service: PermissionService,
        memory_pipeline: MemoryPipelineService,
        skill_service: SkillProposalService,
        # Feature flags
        enable_compression: bool = True,
        enable_permission: bool = True,
        enable_feedback_loop: bool | str = "auto",
        # Additional dependencies
        compressor: Any = None,
        usage_tracker: Any = None,
        retrospective_engine: Any = None,
        anchor_checker: Any = None,
        llm_backend: Any = None,
        persist_dir: str = "",
        # Dispatcher reference (needed for FeedbackControlLoop and post_execution_processing)
        dispatcher: Any = None,
        # Event bus for decoupled communication
        event_bus: EventBus | None = None,
        # Result assembler for direct assembly calls
        result_assembler: ResultAssembler | None = None,
    ) -> None:
        self.coordinator = coordinator
        self.report_formatter = report_formatter
        self.enterprise = enterprise
        self.metrics_service = metrics_service
        self.permission_service = permission_service
        self.memory_pipeline = memory_pipeline
        self.skill_service = skill_service
        self.enable_compression = enable_compression
        self.enable_permission = enable_permission
        self.enable_feedback_loop = enable_feedback_loop
        self.compressor = compressor
        self.usage_tracker = usage_tracker
        self.retrospective_engine = retrospective_engine
        self.anchor_checker = anchor_checker
        self.llm_backend = llm_backend
        self.persist_dir = persist_dir
        self.dispatcher = dispatcher
        self.event_bus = event_bus or EventBus()
        self.result_assembler = result_assembler

        # Lazy-initialized frameworks
        self._ue_framework: UETestFramework | None = None
        self._debt_manager: TechDebtManager | None = None

    # ------------------------------------------------------------------
    # Main execution entry point
    # ------------------------------------------------------------------

    def execute(
        self,
        pre_result,
        exec_result,
        worker_results: list[dict[str, Any]],
        exec_errors: list[str],
        exec_timing: dict[str, float],
        start_time: float,
        phase: str,
        **kwargs: Any,
    ) -> DispatchResult:
        """Steps 9-20: post-processing, consensus, permissions, memory, assembly."""
        task_description = pre_result.task_description
        lang = pre_result.lang
        matched_roles = pre_result.matched_roles
        role_ids = pre_result.role_ids
        concern_packs = pre_result.concern_packs
        intent_match = pre_result.intent_match
        structured_goal = pre_result.structured_goal
        plan = pre_result.plan
        step1_time = pre_result.step1_time
        step2_time = pre_result.step2_time
        step3_time = pre_result.prep_timing.get("step3_time", step2_time)
        step4_time = pre_result.prep_timing.get("step4_time", step3_time)
        step5_time = pre_result.prep_timing.get("step5_time", step4_time)

        errors: list[str] = list(exec_errors)

        step6_time = exec_timing.get("step6_time", step5_time)
        step7_time = exec_timing.get("step7_time", step6_time)

        # Step 9: Post-execution processing (collect, slice, anchor check)
        scratchpad_summary, anchor_result, collection, post_errors, post_timing = self.dispatcher.hooks.post_execution_processing(
            worker_results, structured_goal
        )
        errors.extend(post_errors)
        step8_time = post_timing["step8_time"]

        # Notify listeners that execution processing completed
        self.event_bus.emit(
            "post_dispatch.execution_completed",
            worker_results=worker_results,
            structured_goal=structured_goal,
            scratchpad_summary=scratchpad_summary,
            errors=post_errors,
        )

        # Step 10: Resolve consensus
        mode = kwargs.get('mode', 'auto')
        consensus_records, compression_info = self._resolve_consensus(collection, mode)
        step9_time = time.time()

        # Step 11: Check permissions
        permission_checks = self._check_permissions(task_description, worker_results, consensus_records, **kwargs)
        step10_time = time.time()

        # Step 12: Process memory pipeline
        memory_stats, mem_errors = self._process_memory_pipeline(
            task_description, worker_results, lang, scratchpad_summary, role_ids
        )
        errors.extend(mem_errors)
        step11_time = time.time()

        # Step 13: Learn skills
        skill_proposals, skill_errors = self._learn_skills(task_description, worker_results, matched_roles, exec_result)
        errors.extend(skill_errors)
        step12_time = time.time()

        # Step 14: Run five-axis consensus
        five_axis_result = self._run_five_axis_consensus(task_description, worker_results, mode, exec_result)

        # Step 15: Run retrospective
        total_duration = time.time() - start_time
        retrospective_report = self._run_retrospective(
            task_description, worker_results, structured_goal, exec_result, total_duration
        )

        # Step 16: Assemble result
        step_timings = self._build_step_timings(
            step1_time, step2_time, step3_time, step4_time, step5_time,
            step6_time, step7_time, step8_time, step9_time, step10_time,
            step11_time, step12_time,
        )
        tenant_id = None
        if hasattr(self.dispatcher, '_get_current_tenant_id'):
            tenant_id = self.dispatcher._get_current_tenant_id()
        result = self.result_assembler.assemble(
            task_description=task_description,
            role_ids=role_ids,
            exec_result=exec_result,
            scratchpad_summary=scratchpad_summary,
            consensus_records=consensus_records,
            compression_info=compression_info,
            memory_stats=memory_stats,
            permission_checks=permission_checks,
            skill_proposals=skill_proposals,
            anchor_result=anchor_result,
            retrospective_report=retrospective_report,
            intent_match=intent_match,
            five_axis_result=five_axis_result,
            errors=errors,
            lang=lang,
            concern_packs=concern_packs,
            total_duration=total_duration,
            plan=plan,
            step_timings=step_timings,
            worker_results=worker_results,
            coordinator=self.coordinator,
            tenant_id=tenant_id,
            enterprise=self.enterprise,
        )

        # Lifecycle phase trace
        lifecycle_trace = self._build_lifecycle_trace(step_timings)
        result.details["lifecycle_trace"] = lifecycle_trace

        # Audit: dispatch complete
        self.enterprise.audit_dispatch_complete(result, **kwargs)

        # Step 17: Post-dispatch hooks (fire-and-forget via event bus)
        self.event_bus.emit(
            "post_dispatch.hooks",
            result=result,
            task=task_description,
            role_ids=role_ids,
            total_duration=total_duration,
        )

        # Step 18: Feedback loop
        roles = kwargs.get('roles')
        dry_run = kwargs.get('dry_run', False)
        result = self._run_feedback_loop(task_description, result, lang, roles, mode, dry_run, kwargs)

        # Step 19: UE testing (when tester role is involved)
        ue_test_plan = self._run_ue_testing(task_description, role_ids, worker_results, lang)
        if ue_test_plan:
            result.details["ue_test_plan"] = ue_test_plan

        # Step 20: Tech debt scan
        tech_debt_report = self._run_tech_debt_scan(task_description, worker_results)
        if tech_debt_report:
            result.details["tech_debt_report"] = tech_debt_report

        # Prometheus: record dispatch end (duration + tasks_in_progress)
        self.metrics_service.safe_record(lambda m: (
            m.dispatch_histogram.labels(mode=mode).observe(total_duration),
            m.dispatch_counter.labels(mode=mode, role_count=str(len(role_ids))).inc(),
            m.tasks_in_progress_gauge.labels(phase=phase).dec(),
        ))

        # Multi-tenant context cleanup
        self.enterprise.clear_tenant_context(pre_result.tenant_ctx)

        return result

    # ------------------------------------------------------------------
    # Step 8: Collect worker results
    # ------------------------------------------------------------------

    def _collect_worker_results(self, exec_result: Any) -> tuple[list[dict[str, Any]], float, float]:
        """Collect worker results from execution result into standardized dicts."""
        step6_time = time.time()
        worker_results: list[dict[str, Any]] = []
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
    ) -> tuple[list[dict[str, Any]], Any]:
        """Resolve consensus and get compression info. Returns (consensus_records, compression_info)."""
        consensus_records = []
        conflicts_count = collection.get("conflicts_count", 0)
        if conflicts_count > 0 or mode == "consensus":
            resolutions = self.coordinator.resolve_conflicts()
            for rec in resolutions:
                self.metrics_service.safe_record(lambda m, o=rec.outcome.value: m.record_consensus_round(o))
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
        self, _task: str, _worker_results: list[dict[str, Any]], _consensus_records: list[dict[str, Any]], **kwargs: Any
    ) -> list[dict[str, Any]]:
        """Check permissions via PermissionGuard and RBAC.

        Returns:
            List of permission check results.
        """
        permission_checks: list[dict[str, Any]] = []
        if self.enable_permission and self.permission_service.permission_guard:
            permission_checks = self.permission_service.check_permissions(permission_checks)

        # RBAC fine-grained check
        if self.enterprise.enable_rbac and self.enterprise.rbac_engine:
            permission_checks = self.permission_service.check_rbac(permission_checks, **kwargs)

        return permission_checks

    # ------------------------------------------------------------------
    # Step 12: Process memory pipeline
    # ------------------------------------------------------------------

    def _process_memory_pipeline(
        self,
        task: str,
        _worker_results: list[dict[str, Any]],
        _lang: str,
        scratchpad_summary: str,
        role_ids: list[str],
    ) -> tuple[dict[str, Any] | None, list[str]]:
        """Process memory pipeline: capture + MCE classify + AI news inject."""
        errors: list[str] = []

        memory_stats = self.memory_pipeline.capture(task, scratchpad_summary, role_ids, errors)
        memory_stats = self.memory_pipeline.classify_mce(scratchpad_summary, task, memory_stats, errors)
        self.memory_pipeline.inject_ai_news(task, errors)

        return memory_stats, errors

    # ------------------------------------------------------------------
    # Step 13: Learn skills
    # ------------------------------------------------------------------

    def _learn_skills(
        self,
        _task: str,
        _worker_results: list[dict[str, Any]],
        _matched_roles: list[dict[str, Any]],
        exec_result: Any,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """Learn skills via Skillifier. Returns (skill_proposals, errors)."""
        errors: list[str] = []
        skill_proposals = []
        patterns = None

        if self.skill_service.enable_skillify and self.skill_service.skillifier and exec_result.success:
            try:
                patterns = self.skill_service.skillifier.analyze_history()
                if patterns:
                    skill_proposals = self.skill_service.propose_from_patterns(patterns)
            except (ValueError, AttributeError, RuntimeError, ImportError) as skill_err:
                errors.append(f"Skillifier error: {skill_err}")

        return skill_proposals, errors

    # ------------------------------------------------------------------
    # Step 14: Five-axis consensus
    # ------------------------------------------------------------------

    def _run_five_axis_consensus(
        self, _task: str, worker_results: list[dict[str, Any]], mode: str, exec_result: Any
    ) -> dict[str, Any] | None:
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
        _task: str,
        worker_results: list[dict[str, Any]],
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
        _lang: str,
        roles: list[str] | None,
        mode: str,
        dry_run: bool,
        kwargs: dict[str, Any],
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
                loop = FeedbackControlLoop(dispatcher=self.dispatcher)
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
                dispatcher=self.dispatcher,
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
        role_ids: list[str],
        worker_results: list[dict[str, Any]],
        _lang: str,
    ) -> dict[str, Any] | None:
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
            if self._ue_framework is None:
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
        worker_results: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
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

            if self._debt_manager is None:
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
        from .tech_debt_manager import DebtCategory, DebtEffort, DebtSeverity
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
        from .tech_debt_manager import DebtCategory, DebtEffort, DebtSeverity
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
    ) -> dict[str, float]:
        """Build step timings dict from absolute timestamps."""
        names = ["analyze", "warmup", "plan", "spawn", "execute", "collect",
                 "consensus", "compress", "permission", "memory", "skillify"]
        times = [step1, step2, step3, step4, step5, step6, step7, step8, step9, step10, step11, step12]
        return {name: round(times[i + 1] - times[i], 3) for i, name in enumerate(names)}

    def _build_lifecycle_trace(self, step_timings: dict[str, float]) -> dict[str, Any]:
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

    def _build_summary(self, task: str, roles: list[str], exec_result: Any, sp_summary: str) -> str:
        """Build execution summary."""
        return self.report_formatter.build_summary(task, roles, exec_result, sp_summary)
