"""Merged post-dispatch step mixins.

This module is the V4.1.2 Phase 3 Wave 3 consolidation of the following 4
previously-separate mixin files:

- ``dispatch_steps_consensus_mixin.py``  -> ``PostDispatchConsensusMixin``
- ``dispatch_steps_feedback_mixin.py``   -> ``PostDispatchFeedbackMixin``
- ``dispatch_steps_quality_mixin.py``    -> ``PostDispatchQualityMixin``
- ``dispatch_steps_services_mixin.py``   -> ``PostDispatchServicesMixin``

The original files have been converted to thin shims that re-export from this
module for backward compatibility; they will be deleted in V4.2.0.
"""

import logging
from typing import Any, cast

from .consensus_gate import ConsensusGateResult
from .dispatch_steps_base import PostDispatchBase
from .severity_router import AutoFixResult
from .tech_debt_manager import TechDebtManager
from .two_stage_review_gate import ReviewFinding, ReviewStage, TwoStageReviewResult

logger = logging.getLogger(__name__)


class PostDispatchConsensusMixin(PostDispatchBase):
    """Provides consensus resolution and five-axis consensus helpers."""

    def _resolve_consensus(
        self, collection: Any, mode: str
    ) -> tuple[list[dict[str, Any]], Any]:
        """Resolve consensus and get compression info. Returns (consensus_records, compression_info)."""
        consensus_records: list[dict[str, Any]] = []
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
            from .constants import (
                FIVE_AXIS_DEFAULT_CONFIDENCE,
                FIVE_AXIS_DEFAULT_SCORE,
                FIVE_AXIS_PERFORMANCE_CONFIDENCE,
                FIVE_AXIS_PERFORMANCE_SCORE,
                FIVE_AXIS_SECURITY_CONFIDENCE,
                FIVE_AXIS_SECURITY_SCORE,
            )
            for wr in worker_results:
                output_text = wr.get("output") or wr.get("error") or ""
                if output_text:
                    fa_engine.add_axis_vote(review, ReviewAxis.CORRECTNESS, FIVE_AXIS_DEFAULT_SCORE, FIVE_AXIS_DEFAULT_CONFIDENCE)
                    fa_engine.add_axis_vote(review, ReviewAxis.READABILITY, FIVE_AXIS_DEFAULT_SCORE, FIVE_AXIS_DEFAULT_CONFIDENCE)
                    fa_engine.add_axis_vote(review, ReviewAxis.ARCHITECTURE, FIVE_AXIS_DEFAULT_SCORE, FIVE_AXIS_DEFAULT_CONFIDENCE)
                    fa_engine.add_axis_vote(review, ReviewAxis.SECURITY, FIVE_AXIS_SECURITY_SCORE, FIVE_AXIS_SECURITY_CONFIDENCE)
                    fa_engine.add_axis_vote(review, ReviewAxis.PERFORMANCE, FIVE_AXIS_PERFORMANCE_SCORE, FIVE_AXIS_PERFORMANCE_CONFIDENCE)
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

    def _run_consensus_gate(
        self,
        task_description: str,
        worker_results: list[dict[str, Any]],
    ) -> ConsensusGateResult:
        """Step 15.5: Pre-decision consensus gate (HC-2).

        Uses ConsensusGate to run ConsensusEngine as a *pre-decision*
        check before result assembly.  This is not a post-hoc conflict
        resolver — it evaluates whether worker outputs collectively meet
        consensus before committing the final result.

        HC-3: Always returns a ConsensusGateResult (never None).
        On infrastructure error, returns a fail-soft result with
        ``approved=True, needs_review=True`` — the result is flagged
        for human review rather than silently failing open.
        """
        try:
            from .consensus_gate import ConsensusGate

            # Use the dispatcher's consensus_engine if available
            engine = getattr(self.dispatcher, "consensus_engine", None)
            if engine is None:
                logger.debug("ConsensusGate skipped: no consensus_engine available")
                return ConsensusGateResult(
                    approved=True,
                    outcome="SKIPPED",
                    reason="No consensus_engine available (safe degradation)",
                    consensus_record=None,
                    needs_review=True,
                )

            gate = ConsensusGate()
            result = gate.check(
                task_description=task_description,
                worker_results=worker_results,
                consensus_engine=engine,
            )
            if self.usage_tracker:
                self.usage_tracker.tick("consensus_gate")
            logger.info(
                "ConsensusGate: outcome=%s approved=%s needs_review=%s",
                result.outcome,
                result.approved,
                result.needs_review,
            )
            return result
        except (ImportError, AttributeError, ValueError, RuntimeError) as cg_err:
            logger.warning("ConsensusGate failed (safe degradation, HC-3): %s", cg_err)
            # HC-3: Never return None (would be fail-open). Return a
            # fail-soft result flagging needs_review for human oversight.
            return ConsensusGateResult(
                approved=True,
                outcome="ERROR",
                reason=f"ConsensusGate infrastructure error: {cg_err}",
                consensus_record=None,
                needs_review=True,
            )


class PostDispatchFeedbackMixin(PostDispatchBase):
    """Provides feedback loop, UE testing, and tech-debt scanning."""

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
                from .ue_test_framework import UETestFramework
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
                    cast(Any, plan.journey_tests[0] if plan.journey_tests else None),
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


class PostDispatchQualityMixin(PostDispatchBase):
    """Provides retrospective, two-stage review, severity router, and judge consolidation."""

    def _run_retrospective(
        self,
        _task: str,
        worker_results: list[dict[str, Any]],
        structured_goal: Any,
        exec_result: Any,
        total_duration: float,
    ) -> Any:
        """Run RetrospectiveEngine analysis and persist LearnedRule entries.

        Phase 4: Closes the failure-learning loop by extracting rules from
        the retrospective report and persisting them via LearnedRuleStore.
        Triggers on BOTH success and failure — failed tasks are prioritized
        for learning per spec §5.7 (failure/retry/over-budget/consensus-miss).
        Returns the report or None.
        """
        # Guard: require engine + structured_goal.
        # NOTE: exec_result.success is intentionally NOT gated — failures
        # must trigger retrospective to extract learning rules.
        if not self.retrospective_engine or not structured_goal:
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

            # Phase 4: Extract + persist LearnedRule entries.
            # This is the critical call that closes the learning loop —
            # without it RetrospectiveEngine.run() output never feeds back
            # into future dispatches (ghost-feature).
            if self.learned_rule_store is not None:
                learned_rules = self.retrospective_engine.extract_learned_rules(
                    report=retrospective_report,
                    task_id=(_task or "")[:80],
                )
                tier_counts: dict[str, int] = {"tier1": 0, "tier2": 0, "rejected": 0}
                for rule in learned_rules:
                    tier = self.learned_rule_store.add_rule(rule)
                    if tier in tier_counts:
                        tier_counts[tier] += 1
                logger.info(
                    "RetrospectiveSkill closed loop: extracted %d rules "
                    "(tier1=%d, tier2=%d, rejected=%d) — task success=%s",
                    len(learned_rules),
                    tier_counts["tier1"],
                    tier_counts["tier2"],
                    tier_counts["rejected"],
                    getattr(exec_result, "success", None),
                )
            else:
                logger.debug(
                    "RetrospectiveSkill ran but LearnedRuleStore is None — "
                    "rules not persisted (ghost-feature risk)"
                )

            return retrospective_report
        except (ValueError, AttributeError, RuntimeError, ImportError) as retro_err:
            logger.warning("Retrospective failed: %s", retro_err)
            return None

    def _run_two_stage_review(
        self,
        plan: Any,
        worker_results: list[dict[str, Any]],
        structured_goal: Any,
    ) -> TwoStageReviewResult | None:
        """Run the two-stage code review gate.

        Stage 1 verifies spec/plan compliance; Stage 2 checks code
        quality. Returns None when the gate is disabled or fails to
        initialize (graceful degradation — never blocks dispatch).
        """
        if not self.enable_two_stage_review:
            return None
        try:
            # Build spec requirements from structured goal when available
            spec_requirements: dict[str, Any] = {}
            if structured_goal is not None:
                required_roles = getattr(structured_goal, "required_roles", None)
                if required_roles:
                    spec_requirements["required_roles"] = list(required_roles)
                acceptance_criteria = getattr(structured_goal, "acceptance_criteria", None)
                if acceptance_criteria:
                    spec_requirements["acceptance_criteria"] = list(acceptance_criteria)

            result = self.two_stage_review_gate.review(
                plan=plan,
                worker_results=worker_results,
                spec_requirements=spec_requirements,
            )
            if self.usage_tracker:
                self.usage_tracker.tick("two_stage_review")
            return result
        except (ValueError, AttributeError, TypeError, RuntimeError) as exc:
            logger.warning("Two-stage review gate failed: %s", exc)
            return None

    def _run_severity_router(
        self,
        worker_results: list[dict[str, Any]],
        review_result: TwoStageReviewResult | None,
    ) -> AutoFixResult | None:
        """Run the severity router to process findings and attempt auto-fix.

        Collects findings from worker outputs and the two-stage review
        result, then runs the auto-fix loop (development mode only).
        Returns None when the router is disabled (graceful degradation).
        """
        if not self.enable_severity_router:
            return None
        try:
            findings = self.severity_router.collect_findings(
                worker_results=worker_results,
                review_result=review_result,
            )
            # Emit findings to the event bus for observability
            self.event_bus.emit(
                self.severity_router.EVENT_FINDINGS,
                findings=[f.to_dict() for f in findings],
                count=len(findings),
            )
            # Run the auto-fix loop. In production mode this is a
            # no-op (collect-only). The fix_callable is None because
            # the dispatch pipeline does not itself apply code fixes;
            # downstream consumers (e.g. EnhancedWorker) can subscribe
            # to the event bus to perform actual fixes.
            result = self.severity_router.run_auto_fix_loop(findings)
            if self.usage_tracker:
                self.usage_tracker.tick("severity_router")
            return result
        except (ValueError, AttributeError, TypeError, RuntimeError) as exc:
            logger.warning("Severity router failed: %s", exc)
            return None

    def _run_judge_consolidation(
        self,
        review_result: TwoStageReviewResult | None,
        auto_fix_result: AutoFixResult | None,
    ) -> Any:
        """Run the judge agent to consolidate/deduplicate findings.

        Collects :class:`ReviewFinding` objects from the two-stage
        review gate result and converts :class:`FixAction` objects from
        the severity router back into :class:`ReviewFinding` objects,
        then passes the combined list through
        :meth:`JudgeAgent.judge` for deduplication, conflict resolution,
        and confidence filtering.

        Returns the :class:`JudgeResult` (or ``None`` when no judge
        agent is configured or the call fails — graceful degradation
        that never blocks dispatch).
        """
        if self.judge_agent is None:
            return None
        try:
            findings: list[ReviewFinding] = []

            # Collect findings from the two-stage review gate result.
            if review_result is not None:
                findings.extend(review_result.findings)

            # Convert FixAction objects from the severity router back
            # into ReviewFinding objects so the judge can dedup them
            # alongside the review-gate findings.
            if auto_fix_result is not None:
                for action in auto_fix_result.actions:
                    # Map SeverityLevel back to a ReviewFinding severity
                    # string ("critical"/"warning"/"info").
                    sev = action.severity.value
                    if sev in ("high", "medium"):
                        rf_severity = "warning"
                    elif sev == "low":
                        rf_severity = "info"
                    else:
                        # critical → "critical", info → "info"
                        rf_severity = sev if sev in ("critical", "info") else "warning"
                    findings.append(
                        ReviewFinding(
                            stage=ReviewStage.CODE_QUALITY,
                            severity=rf_severity,
                            category="routed_finding",
                            description=action.description,
                            file_path=action.file_path,
                            suggestion=action.suggested_fix,
                        )
                    )

            if not findings:
                return None

            result = self.judge_agent.judge(findings, context={})
            if self.usage_tracker:
                self.usage_tracker.tick("judge_agent")
            logger.info(
                "JudgeAgent consolidated %d findings: %d accepted, %d rejected, %d merged",
                len(findings),
                len(result.accepted_findings),
                result.rejected_count,
                result.merged_count,
            )
            return result
        except (ValueError, AttributeError, TypeError, RuntimeError) as exc:
            logger.warning("Judge agent consolidation failed: %s", exc)
            return None


class PostDispatchServicesMixin(PostDispatchBase):
    """Provides permission checks, memory pipeline, and skill learning."""

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

    def _learn_skills(
        self,
        _task: str,
        _worker_results: list[dict[str, Any]],
        _matched_roles: list[dict[str, Any]],
        exec_result: Any,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """Learn skills via Skillifier. Returns (skill_proposals, errors)."""
        errors: list[str] = []
        skill_proposals: list[dict[str, Any]] = []
        patterns = None

        if self.skill_service.enable_skillify and self.skill_service.skillifier and exec_result.success:
            try:
                patterns = self.skill_service.skillifier.analyze_history()
                if patterns:
                    skill_proposals = self.skill_service.propose_from_patterns(patterns)
            except (ValueError, AttributeError, RuntimeError, ImportError) as skill_err:
                errors.append(f"Skillifier error: {skill_err}")

        return skill_proposals, errors
