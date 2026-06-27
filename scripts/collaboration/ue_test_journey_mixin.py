"""User journey mixin for UETestFramework.

Extracts user-journey definition, validation, journey-driven test case
generation, error-recovery test extraction, and cognitive-load
assessment so the main framework file can focus on orchestration.

Responsibilities (from IMPROVEMENT_PLAN_V3.9.2.md P2-3):
    - User journey definition & storage
    - Journey validation against actual results
    - Journey test case generation
    - Error recovery test extraction
    - Cognitive load assessment (Miller's law)
"""

from typing import Any

from .ue_test_framework_base import (
    JourneyStep,
    JourneyValidation,
    UETestFrameworkBase,
    UserJourney,
)


class UETestJourneyMixin(UETestFrameworkBase):
    """Provides user journey definition, validation, and analysis."""

    def define_journey(
        self,
        name: str,
        persona: UserJourney,
        steps: list[JourneyStep],
    ) -> UserJourney:
        """Define a user journey with expected outcomes per step.

        Each step has: action, expected_outcome, error_recovery,
        time_budget_seconds, frustration_triggers.

        Args:
            name: Journey name
            persona: Associated user persona
            steps: List of journey steps

        Returns:
            Created UserJourney instance.
        """
        journey = UserJourney(name=name, persona=persona, steps=steps)
        self._journeys.append(journey)
        return journey

    def validate_user_journey(
        self,
        journey: UserJourney,
        actual_results: dict[str, Any],
    ) -> JourneyValidation:
        """Validate actual results against expected journey outcomes.

        Checks:
        - Task completion rate
        - Error recovery success
        - Time budget adherence
        - Frustration events (unexpected errors, confusing UI)
        - Cognitive load indicators (number of decisions per step)

        Args:
            journey: The user journey to validate against.
            actual_results: Dictionary with actual test results containing:
                - "steps_completed": int
                - "steps_total": int
                - "errors_recovered": int
                - "errors_total": int
                - "time_used_seconds": float
                - "frustration_events": int
                - "decisions_per_step": list[float]

        Returns:
            JourneyValidation with computed scores.
        """
        steps_completed = actual_results.get("steps_completed", 0)
        steps_total = actual_results.get("steps_total", journey.step_count)
        errors_recovered = actual_results.get("errors_recovered", 0)
        errors_total = actual_results.get("errors_total", 0)
        time_used = actual_results.get("time_used_seconds", 0.0)
        frustration_events = actual_results.get("frustration_events", 0)
        decisions_per_step = actual_results.get("decisions_per_step", [])

        completion_rate = steps_completed / max(steps_total, 1)
        error_recovery_rate = errors_recovered / max(errors_total, 1) if errors_total > 0 else 1.0
        time_budget = journey.total_time_budget
        time_adherence = min(time_budget / max(time_used, 0.001), 1.0) if time_used > 0 else 1.0

        avg_decisions = sum(decisions_per_step) / max(len(decisions_per_step), 1) if decisions_per_step else 0.0
        cognitive_load = min(avg_decisions / 7.0, 1.0)  # 7 = Miller's law threshold

        overall = (
            completion_rate * 0.35
            + error_recovery_rate * 0.20
            + time_adherence * 0.20
            + max(0, 1 - frustration_events / max(steps_total, 1)) * 0.15
            + max(0, 1 - cognitive_load) * 0.10
        )

        return JourneyValidation(
            journey_name=journey.name,
            completion_rate=completion_rate,
            error_recovery_rate=error_recovery_rate,
            time_budget_adherence=time_adherence,
            frustration_events=frustration_events,
            cognitive_load_score=cognitive_load,
            overall_ue_score=overall,
        )

    def _generate_journey_tests(self) -> list[dict[str, Any]]:
        """Generate journey test cases from defined journeys."""
        tests = []
        for journey in self._journeys:
            test: dict[str, Any] = {
                "name": journey.name,
                "persona": journey.persona.name,
                "critical": journey.critical_path,
                "total_time_budget": journey.total_time_budget,
                "steps": [],
            }
            for step in journey.steps:
                test["steps"].append(
                    {
                        "action": step.action,
                        "expected_outcome": step.expected_outcome,
                        "error_recovery": step.error_recovery,
                        "time_budget_seconds": step.time_budget_seconds,
                        "frustration_triggers": step.frustration_triggers,
                    }
                )
            tests.append(test)
        return tests

    def _generate_error_recovery_tests(self) -> list[dict[str, Any]]:
        """Generate error recovery test scenarios from journeys."""
        tests = []
        for journey in self._journeys:
            for step in journey.steps:
                if step.error_recovery:
                    tests.append(
                        {
                            "journey": journey.name,
                            "step": step.action,
                            "recovery": step.error_recovery,
                            "triggers": step.frustration_triggers,
                        }
                    )
        return tests

    def _assess_cognitive_load(self) -> dict[str, Any]:
        """Assess cognitive load based on defined journeys."""
        if not self._journeys:
            return {"score": 0.0, "assessment": "No journeys defined"}

        total_decisions = 0
        total_steps = 0
        max_decisions_per_step = 0

        for journey in self._journeys:
            for step in journey.steps:
                decisions = len(step.frustration_triggers) + 1
                total_decisions += decisions
                total_steps += 1
                max_decisions_per_step = max(max_decisions_per_step, decisions)

        avg_decisions = total_decisions / max(total_steps, 1)
        score = min(avg_decisions / 7.0, 1.0)  # Miller's law: 7 +/- 2

        assessment = "Low"
        if score > 0.7:
            assessment = "High - needs simplification"
        elif score > 0.4:
            assessment = "Medium - consider reducing options"

        return {
            "score": round(score, 3),
            "assessment": assessment,
            "avg_decisions_per_step": round(avg_decisions, 2),
            "max_decisions_per_step": max_decisions_per_step,
            "total_steps": total_steps,
            "total_journeys": len(self._journeys),
        }
