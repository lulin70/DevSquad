"""Merged UE Test mixins for UETestFramework.

This module is the V4.1.2 Phase 3 Wave 3 consolidation of the following 4
previously-separate mixin files:

- ``ue_test_accessibility_mixin.py``  -> ``UETestAccessibilityMixin``
- ``ue_test_heuristic_mixin.py``      -> ``UETestHeuristicMixin``
- ``ue_test_journey_mixin.py``        -> ``UETestJourneyMixin``
- ``ue_test_persona_mixin.py``        -> ``UETestPersonaMixin``

The original files have been converted to thin shims that re-export from this
module for backward compatibility; they will be deleted in V4.2.0.
"""

import logging
from typing import Any

from .ue_test_framework_base import (
    HeuristicCheck,
    JourneyStep,
    JourneyValidation,
    UETestFrameworkBase,
    UsabilityReport,
    UserJourney,
    UserPersona,
)

logger = logging.getLogger(__name__)

# ============================================================
# WCAG 2.1 AA Accessibility Checks
# ============================================================

WCAG_AA_CHECKS: list[dict[str, str]] = [
    {"check": "1.1.1 Non-text Content", "category": "perceivable", "description": "All non-text content has text alternatives"},
    {"check": "1.3.1 Info and Relationships", "category": "perceivable", "description": "Information conveyed through presentation is also available in text"},
    {"check": "1.4.3 Contrast (Minimum)", "category": "perceivable", "description": "Text contrast ratio at least 4.5:1 for normal text"},
    {"check": "1.4.11 Non-text Contrast", "category": "perceivable", "description": "UI components and graphical objects contrast ratio at least 3:1"},
    {"check": "2.1.1 Keyboard", "category": "operable", "description": "All functionality available from keyboard"},
    {"check": "2.4.3 Focus Order", "category": "operable", "description": "Focus order preserves meaning and operability"},
    {"check": "2.4.6 Headings and Labels", "category": "operable", "description": "Headings and labels describe topic or purpose"},
    {"check": "2.4.7 Focus Visible", "category": "operable", "description": "Keyboard focus indicator always visible"},
    {"check": "3.1.1 Language of Page", "category": "understandable", "description": "Default human language of page determinable"},
    {"check": "3.2.2 On Input", "category": "understandable", "description": "Changing input setting does not automatically change context"},
    {"check": "3.3.1 Error Identification", "category": "understandable", "description": "Errors automatically detected and described in text"},
    {"check": "3.3.2 Labels or Instructions", "category": "understandable", "description": "Labels provided when user input required"},
    {"check": "4.1.2 Name Role Value", "category": "robust", "description": "Name and role determinable, states can be set programmatically"},
    {"check": "4.1.3 Status Messages", "category": "robust", "description": "Status messages can be programmatically determined"},
]


class UETestAccessibilityMixin(UETestFrameworkBase):
    """Provides WCAG 2.1 AA accessibility check generation."""

    def _generate_accessibility_checks(self) -> list[dict[str, Any]]:
        """Generate WCAG 2.1 AA accessibility check list."""
        checks = []
        for wcag in WCAG_AA_CHECKS:
            checks.append(
                {
                    "check": wcag["check"],
                    "category": wcag["category"],
                    "description": wcag["description"],
                    "status": "pending",
                    "automated": wcag["category"] in ("perceivable", "operable"),
                }
            )
        return checks


class UETestHeuristicMixin(UETestFrameworkBase):
    """Provides Nielsen's 10 heuristic usability assessment."""

    def assess_usability(self, interface_description: str) -> UsabilityReport:
        """Assess usability against Nielsen's 10 heuristics.

        Uses LLM if available, otherwise rule-based assessment.

        Args:
            interface_description: Description of the interface to assess.

        Returns:
            UsabilityReport with heuristic evaluation results.
        """
        if self.llm_backend is not None:
            return self._assess_with_llm(interface_description)
        return self._assess_rule_based(interface_description)

    def _assess_rule_based(self, interface_description: str) -> UsabilityReport:
        """Rule-based heuristic assessment using keyword matching."""
        lower_desc = interface_description.lower()
        assessed = []
        critical_issues = []
        recommendations = []

        for h in self._heuristics:
            check = HeuristicCheck(
                name=h.name,
                description=h.description,
            )
            positive_keywords = self._heuristic_positive_keywords(h.name)
            negative_keywords = self._heuristic_negative_keywords(h.name)

            pos_score = sum(1 for kw in positive_keywords if kw in lower_desc)
            neg_score = sum(1 for kw in negative_keywords if kw in lower_desc)

            if neg_score > 0:
                check.passed = False
                check.severity = "major" if neg_score > 1 else "minor"
                check.evidence = f"Found {neg_score} violation indicator(s)"
                critical_issues.append(f"{h.name}: {check.evidence}")
                recommendations.append(self._heuristic_recommendation(h.name))
            elif pos_score > 0:
                check.passed = True
                check.evidence = f"Found {pos_score} positive indicator(s)"
            else:
                check.passed = None
                check.evidence = "No indicators found in description"

            assessed.append(check)

        passed_count = sum(1 for h in assessed if h.passed is True)
        total = len(assessed)
        overall = passed_count / max(total, 1)

        return UsabilityReport(
            heuristics=assessed,
            overall_score=overall,
            critical_issues=critical_issues,
            recommendations=recommendations,
        )

    def _assess_with_llm(self, interface_description: str) -> UsabilityReport:
        """LLM-assisted heuristic assessment."""
        try:
            prompt = self._build_usability_prompt(interface_description)
            response = self.llm_backend.generate(prompt)
            return self._parse_llm_usability_response(response)
        except (RuntimeError, ValueError, TypeError, ConnectionError) as e:
            logger.debug("LLM usability assessment failed, falling back to rule-based: %s", e)
            return self._assess_rule_based(interface_description)

    def _build_usability_prompt(self, description: str) -> str:
        heuristic_list = "\n".join(
            f"{i+1}. {h.name}: {h.description}" for i, h in enumerate(self._heuristics)
        )
        return (
            f"Assess the following interface against Nielsen's 10 usability heuristics.\n"
            f"Interface description:\n{description}\n\n"
            f"Heuristics:\n{heuristic_list}\n\n"
            f"For each heuristic, provide:\n"
            f"- passed: true/false\n"
            f"- evidence: brief explanation\n"
            f"- severity: cosmetic/minor/major/critical (if failed)\n\n"
            f"Respond in JSON format with 'heuristics' array and 'recommendations' array."
        )

    def _parse_llm_usability_response(self, response: str) -> UsabilityReport:
        """Parse LLM response into UsabilityReport."""
        import json

        try:
            data = json.loads(response)
        except (json.JSONDecodeError, TypeError):
            return self._assess_rule_based(response)

        heuristics = []
        critical_issues = []
        for item in data.get("heuristics", []):
            h = HeuristicCheck(
                name=item.get("name", ""),
                description=item.get("description", ""),
                passed=item.get("passed"),
                evidence=item.get("evidence", ""),
                severity=item.get("severity", ""),
            )
            heuristics.append(h)
            if h.passed is False and h.severity in ("major", "critical"):
                critical_issues.append(f"{h.name}: {h.evidence}")

        recommendations = data.get("recommendations", [])
        passed_count = sum(1 for h in heuristics if h.passed is True)
        overall = passed_count / max(len(heuristics), 1)

        return UsabilityReport(
            heuristics=heuristics,
            overall_score=overall,
            critical_issues=critical_issues,
            recommendations=recommendations,
        )

    def _default_heuristics(self) -> list[HeuristicCheck]:
        """Nielsen's 10 usability heuristics as checkable items."""
        return [
            HeuristicCheck(
                "visibility_of_system_status",
                "System should always keep users informed about what is going on",
            ),
            HeuristicCheck(
                "match_between_system_and_real_world",
                "System should speak the users' language",
            ),
            HeuristicCheck(
                "user_control_and_freedom",
                "Users need emergency exits from unwanted states",
            ),
            HeuristicCheck(
                "consistency_and_standards",
                "Users should not have to wonder whether different words mean the same thing",
            ),
            HeuristicCheck(
                "error_prevention",
                "Better than good error messages is careful design to prevent problems",
            ),
            HeuristicCheck(
                "recognition_rather_than_recall",
                "Minimize user memory load by making objects/actions visible",
            ),
            HeuristicCheck(
                "flexibility_and_efficiency_of_use",
                "Accelerators for expert users without hindering novices",
            ),
            HeuristicCheck(
                "aesthetic_and_minimalist_design",
                "Dialogues should not contain irrelevant information",
            ),
            HeuristicCheck(
                "help_users_recognize_diagnose_and_recover_from_errors",
                "Error messages should be expressed in plain language",
            ),
            HeuristicCheck(
                "help_and_documentation",
                "Users may need help, should be easy to search and focused on task",
            ),
        ]

    @staticmethod
    def _heuristic_positive_keywords(name: str) -> list[str]:
        """Keywords suggesting a heuristic is satisfied."""
        keyword_map = {
            "visibility_of_system_status": ["loading", "progress", "status", "feedback", "indicator", "spinner"],
            "match_between_system_and_real_world": ["intuitive", "natural", "familiar", "real-world", "metaphor"],
            "user_control_and_freedom": ["undo", "cancel", "back", "redo", "rollback", "revert"],
            "consistency_and_standards": ["consistent", "standard", "uniform", "convention", "pattern"],
            "error_prevention": ["validation", "confirm", "preview", "warning", "guard", "constraint"],
            "recognition_rather_than_recall": ["visible", "icon", "menu", "dropdown", "suggestion", "autocomplete"],
            "flexibility_and_efficiency_of_use": ["shortcut", "keyboard", "macro", "template", "accelerator"],
            "aesthetic_and_minimalist_design": ["clean", "minimal", "simple", "focused", "uncluttered"],
            "help_users_recognize_diagnose_and_recover_from_errors": ["error message", "helpful", "suggestion", "recovery"],
            "help_and_documentation": ["help", "documentation", "tooltip", "guide", "tutorial", "search"],
        }
        return keyword_map.get(name, [])

    @staticmethod
    def _heuristic_negative_keywords(name: str) -> list[str]:
        """Keywords suggesting a heuristic is violated."""
        keyword_map = {
            "visibility_of_system_status": ["no feedback", "frozen", "unresponsive", "silent", "stuck"],
            "match_between_system_and_real_world": ["jargon", "technical term", "confusing label", "ambiguous"],
            "user_control_and_freedom": ["no undo", "no cancel", "irreversible", "trapped", "forced"],
            "consistency_and_standards": ["inconsistent", "different meaning", "confusing", "contradictory"],
            "error_prevention": ["easy to mistake", "no validation", "no confirmation", "destructive"],
            "recognition_rather_than_recall": ["remember", "hidden", "memorize", "invisible", "not visible"],
            "flexibility_and_efficiency_of_use": ["no shortcut", "slow", "tedious", "repetitive", "manual"],
            "aesthetic_and_minimalist_design": ["cluttered", "overwhelming", "busy", "too much", "crowded"],
            "help_users_recognize_diagnose_and_recover_from_errors": ["cryptic error", "error code", "unhelpful", "generic error"],
            "help_and_documentation": ["no help", "no documentation", "no tooltip", "no guide"],
        }
        return keyword_map.get(name, [])

    @staticmethod
    def _heuristic_recommendation(name: str) -> str:
        """Recommendation for a violated heuristic."""
        rec_map = {
            "visibility_of_system_status": "Add loading indicators, progress bars, or status messages for all async operations",
            "match_between_system_and_real_world": "Replace technical jargon with user-friendly language and familiar concepts",
            "user_control_and_freedom": "Add undo/cancel/revert options for all destructive or significant actions",
            "consistency_and_standards": "Standardize terminology, layout patterns, and interaction behaviors across the interface",
            "error_prevention": "Add input validation, confirmation dialogs, and constraints to prevent common mistakes",
            "recognition_rather_than_recall": "Make options visible with menus, icons, and suggestions instead of requiring memory",
            "flexibility_and_efficiency_of_use": "Add keyboard shortcuts, templates, and accelerators for expert users",
            "aesthetic_and_minimalist_design": "Remove irrelevant information and simplify the interface to focus on core tasks",
            "help_users_recognize_diagnose_and_recover_from_errors": "Write error messages in plain language with specific recovery suggestions",
            "help_and_documentation": "Add searchable help documentation, tooltips, and contextual guidance",
        }
        return rec_map.get(name, "Review and improve this aspect of the interface")


class UETestJourneyMixin(UETestFrameworkBase):
    """Provides user journey definition, validation, and analysis."""

    def define_journey(
        self,
        name: str,
        persona: UserPersona,
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


class UETestPersonaMixin(UETestFrameworkBase):
    """Provides user persona definition and scenario generation."""

    def define_persona(
        self,
        name: str,
        tech_level: str,
        goals: list[str],
        frustrations: list[str],
    ) -> UserPersona:
        """Define a user persona for UE testing.

        Args:
            name: Persona name (e.g., "first-time-user", "power-user")
            tech_level: "beginner" | "intermediate" | "advanced"
            goals: What this persona wants to achieve
            frustrations: Common pain points for this persona

        Returns:
            Created UserPersona instance.
        """
        persona = UserPersona(
            name=name,
            tech_level=tech_level,
            goals=goals,
            frustrations=frustrations,
        )
        self._personas.append(persona)
        return persona

    def _generate_persona_scenarios(self) -> list[dict[str, Any]]:
        """Generate test scenarios from defined personas."""
        scenarios = []
        for persona in self._personas:
            scenarios.append(
                {
                    "persona": persona.name,
                    "tech_level": persona.tech_level,
                    "goals": persona.goals,
                    "frustrations": persona.frustrations,
                    "patience_threshold": persona.patience_threshold,
                    "test_focus": self._persona_test_focus(persona),
                }
            )
        if not scenarios:
            scenarios.append(
                {
                    "persona": "default-user",
                    "tech_level": "intermediate",
                    "goals": ["Complete core task"],
                    "frustrations": ["Confusing navigation"],
                    "patience_threshold": 0.7,
                    "test_focus": ["core_journey", "error_recovery"],
                }
            )
        return scenarios

    def _persona_test_focus(self, persona: UserPersona) -> list[str]:
        """Determine test focus areas based on persona characteristics."""
        focus = []
        if persona.tech_level == "beginner":
            focus.extend(["onboarding", "discoverability", "error_prevention"])
        elif persona.tech_level == "advanced":
            focus.extend(["shortcuts", "customization", "efficiency"])
        else:
            focus.extend(["core_journey", "error_recovery"])

        if persona.patience_threshold < 0.5:
            focus.append("response_time")
        if len(persona.frustrations) > 2:
            focus.append("frustration_handling")

        return focus
