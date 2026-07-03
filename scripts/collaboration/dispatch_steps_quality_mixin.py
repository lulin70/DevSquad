"""Quality, review, and consolidation post-dispatch step mixins."""

import logging
from typing import Any

from .dispatch_steps_base import PostDispatchBase
from .severity_router import AutoFixResult
from .two_stage_review_gate import ReviewFinding, ReviewStage, TwoStageReviewResult

logger = logging.getLogger(__name__)


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
