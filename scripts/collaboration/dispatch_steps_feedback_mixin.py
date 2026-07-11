"""Feedback loop, UE testing, and technical-debt post-dispatch step mixins."""

import logging
from typing import Any, cast

from .dispatch_steps_base import PostDispatchBase
from .tech_debt_manager import TechDebtManager

logger = logging.getLogger(__name__)


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
