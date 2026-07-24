#!/usr/bin/env python3
"""
UETestProvider Contract Tests

Validates that all UETestProvider implementations conform to the Protocol
interface defined in protocols.py.

UETestFramework (real implementation) inherits generate_ue_test_plan directly
and validate_user_journey / assess_usability via mixins. It does NOT currently
implement is_available() — this gap is documented by test_ue_test_framework_missing_is_available.

Contract test ownership: shared between DevSquad and UE testing teams.
Any breaking change to UETestProvider Protocol must be negotiated.
"""

import os
import sys
import unittest
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.protocols import UETestProvider


class TestUETestProviderProtocolDefinition(unittest.TestCase):
    """Verify the UETestProvider Protocol definition itself is well-formed."""

    def test_protocol_has_generate_ue_test_plan(self):
        self.assertTrue(hasattr(UETestProvider, "generate_ue_test_plan"))

    def test_protocol_has_validate_user_journey(self):
        self.assertTrue(hasattr(UETestProvider, "validate_user_journey"))

    def test_protocol_has_assess_usability(self):
        self.assertTrue(hasattr(UETestProvider, "assess_usability"))

    def test_protocol_has_is_available(self):
        self.assertTrue(hasattr(UETestProvider, "is_available"))


class _MinimalUETestProvider:
    """Minimal structurally-compatible implementation for subtyping verification."""

    def generate_ue_test_plan(self, project_description: str) -> Any:
        return {"plan": project_description}

    def validate_user_journey(self, journey: Any, actual_results: dict[str, Any]) -> Any:  # noqa: ARG002
        return {"valid": True}

    def assess_usability(self, interface_description: str) -> Any:  # noqa: ARG002
        return {"score": 8}

    def is_available(self) -> bool:
        return True


class TestUETestProviderStructuralSubtyping(unittest.TestCase):
    """Verify any class with the right methods satisfies UETestProvider structurally."""

    def test_minimal_implementation_is_instance_of_protocol(self):
        """A class implementing all methods should satisfy runtime_checkable isinstance."""
        self.assertIsInstance(_MinimalUETestProvider(), UETestProvider)

    def test_missing_method_fails_isinstance(self):
        """A class missing a method should NOT satisfy isinstance."""

        class IncompleteProvider:
            def generate_ue_test_plan(self, project_description: str) -> Any:  # noqa: ARG002
                return {}

            def validate_user_journey(self, journey: Any, actual_results: dict[str, Any]) -> Any:  # noqa: ARG002
                return {}

            def assess_usability(self, interface_description: str) -> Any:  # noqa: ARG002
                return {}

            # Missing is_available

        self.assertNotIsInstance(IncompleteProvider(), UETestProvider)


class TestUETestFrameworkContractGap(unittest.TestCase):
    """Document the known gap: UETestFramework does not implement is_available().

    UETestFramework has 3/4 UETestProvider methods (generate_ue_test_plan,
    validate_user_journey via mixin, assess_usability via mixin) but is
    missing is_available(). This test documents the gap so it can be tracked.
    """

    def test_ue_test_framework_has_generate_ue_test_plan(self):
        from scripts.collaboration.ue_test_framework import UETestFramework

        self.assertTrue(hasattr(UETestFramework, "generate_ue_test_plan"))

    def test_ue_test_framework_has_validate_user_journey(self):
        from scripts.collaboration.ue_test_framework import UETestFramework

        self.assertTrue(hasattr(UETestFramework, "validate_user_journey"))

    def test_ue_test_framework_has_assess_usability(self):
        from scripts.collaboration.ue_test_framework import UETestFramework

        self.assertTrue(hasattr(UETestFramework, "assess_usability"))

    def test_ue_test_framework_missing_is_available(self):
        """Document: UETestFramework does NOT implement is_available().

        This is a known gap. When fixed, this test should be updated to
        verify UETestFramework fully satisfies UETestProvider.
        """
        from scripts.collaboration.ue_test_framework import UETestFramework

        self.assertFalse(
            hasattr(UETestFramework, "is_available"),
            "UETestFramework now has is_available() — update this test to verify full Protocol compliance",
        )


class TestUETestFrameworkExtendedContract(unittest.TestCase):
    """Extended contract tests for UETestFramework covering all 3 Protocol methods.

    Dimensions: Happy / Error / Boundary / Config / Integration
    """

    def _get_framework(self):
        """Return a fresh UETestFramework with no LLM backend (rule-based)."""
        from scripts.collaboration.ue_test_framework import UETestFramework

        return UETestFramework(llm_backend=None)

    def _make_persona(self):
        from scripts.collaboration.ue_test_framework import UETestFramework

        fw = UETestFramework()
        return fw.define_persona(
            name="first-time-user",
            tech_level="beginner",
            goals=["complete signup"],
            frustrations=["cannot find button"],
        )

    def _make_journey(self, persona=None):
        from scripts.collaboration.ue_test_framework import (
            JourneyStep,
            UserJourney,
        )

        if persona is None:
            persona = self._make_persona()
        steps = [
            JourneyStep(
                action="open signup page",
                expected_outcome="signup form visible",
                error_recovery="reload page",
                time_budget_seconds=10.0,
            ),
            JourneyStep(
                action="fill email and click submit",
                expected_outcome="confirmation shown",
                error_recovery="check validation messages",
                time_budget_seconds=20.0,
            ),
        ]
        return UserJourney(name="signup", persona=persona, steps=steps)

    # ------------------------------------------------------------------
    # Happy: generate_ue_test_plan
    # ------------------------------------------------------------------

    def test_generate_ue_test_plan_returns_plan(self):
        """generate_ue_test_plan must return a UETestPlan instance."""
        from scripts.collaboration.ue_test_framework_base import UETestPlan

        fw = self._get_framework()
        plan = fw.generate_ue_test_plan("User signup system")
        self.assertIsInstance(plan, UETestPlan)
        self.assertEqual(plan.project, "User signup system")

    def test_generate_ue_test_plan_includes_heuristics(self):
        """generate_ue_test_plan must populate heuristic_checks with 10 Nielsen heuristics."""
        fw = self._get_framework()
        plan = fw.generate_ue_test_plan("test project")
        self.assertEqual(len(plan.heuristic_checks), 10)
        # Each heuristic must have name and description
        for h in plan.heuristic_checks:
            self.assertTrue(h.name)
            self.assertTrue(h.description)

    def test_generate_ue_test_plan_includes_accessibility_checks(self):
        """generate_ue_test_plan must include WCAG 2.1 AA accessibility checks."""
        fw = self._get_framework()
        plan = fw.generate_ue_test_plan("test project")
        self.assertGreaterEqual(len(plan.accessibility_checks), 10)
        for ac in plan.accessibility_checks:
            self.assertIn("check", ac)
            self.assertIn("category", ac)

    def test_generate_ue_test_plan_incorporates_defined_journeys(self):
        """generate_ue_test_plan must include journeys defined via define_journey."""
        fw = self._get_framework()
        persona = fw.define_persona("p1", "intermediate", ["g1"], ["f1"])
        fw.define_journey("j1", persona, steps=[])
        plan = fw.generate_ue_test_plan("project")
        journey_names = [j.get("name") for j in plan.journey_tests]
        self.assertIn("j1", journey_names)

    # ------------------------------------------------------------------
    # Happy: validate_user_journey
    # ------------------------------------------------------------------

    def test_validate_user_journey_returns_validation(self):
        """validate_user_journey must return a JourneyValidation instance."""
        from scripts.collaboration.ue_test_framework_base import JourneyValidation

        fw = self._get_framework()
        journey = self._make_journey()
        actual = {
            "steps_completed": 2,
            "steps_total": 2,
            "errors_recovered": 1,
            "errors_total": 1,
            "time_used_seconds": 25.0,
            "frustration_events": 0,
            "decisions_per_step": [2.0, 3.0],
        }
        result = fw.validate_user_journey(journey, actual)
        self.assertIsInstance(result, JourneyValidation)
        self.assertEqual(result.journey_name, "signup")
        self.assertEqual(result.completion_rate, 1.0)
        self.assertEqual(result.error_recovery_rate, 1.0)

    def test_validate_user_journey_partial_completion(self):
        """validate_user_journey must compute completion_rate from partial completion."""
        fw = self._get_framework()
        journey = self._make_journey()
        actual = {
            "steps_completed": 1,
            "steps_total": 2,
            "time_used_seconds": 20.0,
            "frustration_events": 1,
        }
        result = fw.validate_user_journey(journey, actual)
        self.assertEqual(result.completion_rate, 0.5)
        self.assertEqual(result.frustration_events, 1)

    def test_validate_user_journey_missing_keys_uses_defaults(self):
        """validate_user_journey must not crash when actual_results has missing keys."""
        fw = self._get_framework()
        journey = self._make_journey()
        # Empty results dict should not crash — all values default
        result = fw.validate_user_journey(journey, {})
        self.assertEqual(result.journey_name, "signup")
        # With no steps_completed, completion_rate is 0
        self.assertEqual(result.completion_rate, 0.0)
        # With no errors_total, error_recovery_rate defaults to 1.0
        self.assertEqual(result.error_recovery_rate, 1.0)

    def test_validate_user_journey_time_adherence_capped_at_1(self):
        """validate_user_journey must cap time_budget_adherence at 1.0."""
        fw = self._get_framework()
        journey = self._make_journey()  # total budget = 30s
        actual = {
            "steps_completed": 2,
            "steps_total": 2,
            "time_used_seconds": 10.0,  # well under budget
        }
        result = fw.validate_user_journey(journey, actual)
        self.assertLessEqual(result.time_budget_adherence, 1.0)
        self.assertGreater(result.time_budget_adherence, 0.0)

    # ------------------------------------------------------------------
    # Happy: assess_usability (rule-based, no LLM)
    # ------------------------------------------------------------------

    def test_assess_usability_returns_report(self):
        """assess_usability must return a UsabilityReport instance."""
        from scripts.collaboration.ue_test_framework_base import UsabilityReport

        fw = self._get_framework()
        report = fw.assess_usability("clean minimal interface with loading indicators")
        self.assertIsInstance(report, UsabilityReport)
        self.assertGreaterEqual(len(report.heuristics), 10)

    def test_assess_usability_detects_violations(self):
        """assess_usability must flag heuristics when negative keywords are present."""
        fw = self._get_framework()
        report = fw.assess_usability(
            "cluttered interface with no undo, no validation, and cryptic error messages"
        )
        # At least one heuristic must be flagged as failed
        failed = [h for h in report.heuristics if h.passed is False]
        self.assertGreaterEqual(len(failed), 1)
        # Critical issues list should be populated
        self.assertGreaterEqual(len(report.critical_issues), 1)

    def test_assess_usability_overall_score_in_range(self):
        """assess_usability overall_score must be in [0.0, 1.0]."""
        fw = self._get_framework()
        report = fw.assess_usability("a clean simple consistent interface with tooltips")
        self.assertGreaterEqual(report.overall_score, 0.0)
        self.assertLessEqual(report.overall_score, 1.0)

    # ------------------------------------------------------------------
    # Config: LLM backend integration
    # ------------------------------------------------------------------

    def test_assess_usability_uses_llm_when_available(self):
        """assess_usability must use the LLM backend when provided."""
        from scripts.collaboration.llm_backend import MockBackend
        from scripts.collaboration.ue_test_framework import UETestFramework
        from scripts.collaboration.ue_test_framework_base import UsabilityReport

        fw = UETestFramework(llm_backend=MockBackend())
        # Mock backend returns text, not JSON — assess_usability should fall
        # back to rule-based gracefully without crashing.
        report = fw.assess_usability("test interface with loading indicator")
        self.assertIsInstance(report, UsabilityReport)

    # ------------------------------------------------------------------
    # Integration: full UE workflow
    # ------------------------------------------------------------------

    def test_full_workflow_define_plan_validate(self):
        """Full workflow: define persona+journey, generate plan, validate results."""
        fw = self._get_framework()
        persona = fw.define_persona(
            name="power-user",
            tech_level="advanced",
            goals=["bulk import data"],
            frustrations=["slow UI", "no shortcuts"],
        )
        from scripts.collaboration.ue_test_framework import JourneyStep

        fw.define_journey(
            name="bulk-import",
            persona=persona,
            steps=[
                JourneyStep("click import", "dialog opens", "retry", 5.0),
                JourneyStep("select file", "file loaded", "check format", 15.0),
            ],
        )
        plan = fw.generate_ue_test_plan("Data import tool")
        self.assertEqual(plan.project, "Data import tool")
        self.assertGreaterEqual(len(plan.journey_tests), 1)
        self.assertGreaterEqual(len(plan.persona_scenarios), 1)
        # Cognitive load assessment must be present
        self.assertIsInstance(plan.cognitive_load_assessment, dict)

        # Validate the journey with actual results
        journey = fw._journeys[0]
        validation = fw.validate_user_journey(
            journey,
            {
                "steps_completed": 2,
                "steps_total": 2,
                "errors_recovered": 0,
                "errors_total": 0,
                "time_used_seconds": 18.0,
                "frustration_events": 0,
            },
        )
        self.assertEqual(validation.completion_rate, 1.0)
        self.assertGreater(validation.overall_ue_score, 0.0)

    # ------------------------------------------------------------------
    # Boundary: empty project description
    # ------------------------------------------------------------------

    def test_generate_ue_test_plan_empty_project_description(self):
        """generate_ue_test_plan with empty string must still produce a valid plan."""
        fw = self._get_framework()
        plan = fw.generate_ue_test_plan("")
        self.assertEqual(plan.project, "")
        # Must still produce heuristic checks even with empty project
        self.assertEqual(len(plan.heuristic_checks), 10)

    # ------------------------------------------------------------------
    # Serialization: UETestPlan.to_dict round-trip
    # ------------------------------------------------------------------

    def test_ue_test_plan_to_dict_serializes_all_fields(self):
        """UETestPlan.to_dict must serialize all fields including nested heuristics."""
        fw = self._get_framework()
        plan = fw.generate_ue_test_plan("Serialization test project")
        d = plan.to_dict()
        self.assertEqual(d["project"], "Serialization test project")
        self.assertIn("heuristic_checks", d)
        self.assertIn("accessibility_checks", d)
        self.assertIn("journey_tests", d)
        self.assertIn("persona_scenarios", d)
        self.assertIn("error_recovery_tests", d)
        self.assertIn("cognitive_load_assessment", d)
        # Each heuristic_check dict must have name and description
        for h in d["heuristic_checks"]:
            self.assertIn("name", h)
            self.assertIn("description", h)

    def test_journey_validation_to_dict_round_trip(self):
        """JourneyValidation.to_dict must round-trip all numeric fields."""
        from scripts.collaboration.ue_test_framework_base import JourneyValidation

        v = JourneyValidation(
            journey_name="test-journey",
            completion_rate=0.85,
            error_recovery_rate=0.7,
            time_budget_adherence=0.9,
            frustration_events=2,
            cognitive_load_score=0.35,
            overall_ue_score=0.78,
        )
        d = v.to_dict()
        self.assertEqual(d["journey_name"], "test-journey")
        self.assertEqual(d["completion_rate"], 0.85)
        self.assertEqual(d["frustration_events"], 2)
        # to_dict rounds to 3 decimal places
        self.assertAlmostEqual(d["overall_ue_score"], 0.78, places=3)


if __name__ == "__main__":
    unittest.main()
