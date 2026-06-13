"""Tests for UETestFramework module."""

import pytest

from scripts.collaboration.ue_test_framework import (
    JourneyStep,
    UETestFramework,
    UserJourney,
    UserPersona,
    WCAG_AA_CHECKS,
)


class TestDefinePersona:
    """Tests for UETestFramework.define_persona."""

    def test_creates_persona_with_all_fields(self):
        fw = UETestFramework()
        persona = fw.define_persona(
            "first-time-user", "beginner",
            ["Complete registration"], ["Cannot find button"],
        )
        assert isinstance(persona, UserPersona)
        assert persona.name == "first-time-user"
        assert persona.tech_level == "beginner"
        assert persona.goals == ["Complete registration"]
        assert persona.frustrations == ["Cannot find button"]

    def test_persona_default_patience_threshold(self):
        fw = UETestFramework()
        persona = fw.define_persona("user", "intermediate", [], [])
        assert persona.patience_threshold == 0.7

    def test_persona_stored_internally(self):
        fw = UETestFramework()
        fw.define_persona("p1", "beginner", ["g1"], [])
        fw.define_persona("p2", "advanced", ["g2"], [])
        assert len(fw._personas) == 2
        assert fw._personas[0].name == "p1"
        assert fw._personas[1].name == "p2"

    def test_persona_to_dict(self):
        fw = UETestFramework()
        persona = fw.define_persona("dev", "advanced", ["Ship code"], ["Slow CI"])
        d = persona.to_dict()
        assert d["name"] == "dev"
        assert d["tech_level"] == "advanced"
        assert d["goals"] == ["Ship code"]
        assert d["frustrations"] == ["Slow CI"]


class TestDefineJourney:
    """Tests for UETestFramework.define_journey."""

    def test_creates_journey_with_steps(self):
        fw = UETestFramework()
        persona = fw.define_persona("user", "beginner", ["Sign up"], [])
        steps = [
            JourneyStep("Open page", "Page loads", "Refresh browser"),
            JourneyStep("Fill form", "Form submitted", "Re-enter data"),
        ]
        journey = fw.define_journey("signup", persona, steps)
        assert isinstance(journey, UserJourney)
        assert journey.name == "signup"
        assert journey.persona is persona
        assert len(journey.steps) == 2

    def test_journey_critical_path_default(self):
        fw = UETestFramework()
        persona = fw.define_persona("u", "beginner", [], [])
        journey = fw.define_journey("j", persona, [])
        assert journey.critical_path is True

    def test_journey_total_time_budget(self):
        fw = UETestFramework()
        persona = fw.define_persona("u", "beginner", [], [])
        steps = [
            JourneyStep("Step 1", "OK", "Retry", time_budget_seconds=10.0),
            JourneyStep("Step 2", "OK", "Retry", time_budget_seconds=20.0),
        ]
        journey = fw.define_journey("j", persona, steps)
        assert journey.total_time_budget == 30.0

    def test_journey_step_count(self):
        fw = UETestFramework()
        persona = fw.define_persona("u", "beginner", [], [])
        steps = [JourneyStep(f"Step {i}", "OK", "Retry") for i in range(5)]
        journey = fw.define_journey("j", persona, steps)
        assert journey.step_count == 5

    def test_journey_stored_internally(self):
        fw = UETestFramework()
        persona = fw.define_persona("u", "beginner", [], [])
        fw.define_journey("j1", persona, [])
        fw.define_journey("j2", persona, [])
        assert len(fw._journeys) == 2


class TestGenerateUETestPlan:
    """Tests for UETestFramework.generate_ue_test_plan (without LLM)."""

    def test_generates_plan_with_project_description(self):
        fw = UETestFramework()
        plan = fw.generate_ue_test_plan("User Registration System")
        assert plan.project == "User Registration System"

    def test_plan_contains_heuristic_checks(self):
        fw = UETestFramework()
        plan = fw.generate_ue_test_plan("Test Project")
        assert len(plan.heuristic_checks) == 10

    def test_plan_contains_accessibility_checks(self):
        fw = UETestFramework()
        plan = fw.generate_ue_test_plan("Test Project")
        assert len(plan.accessibility_checks) > 0

    def test_plan_contains_default_persona_when_none_defined(self):
        fw = UETestFramework()
        plan = fw.generate_ue_test_plan("Test Project")
        assert len(plan.persona_scenarios) == 1
        assert plan.persona_scenarios[0]["persona"] == "default-user"

    def test_plan_uses_defined_personas(self):
        fw = UETestFramework()
        fw.define_persona("admin", "advanced", ["Manage users"], ["Slow dashboard"])
        plan = fw.generate_ue_test_plan("Admin Panel")
        assert len(plan.persona_scenarios) == 1
        assert plan.persona_scenarios[0]["persona"] == "admin"

    def test_plan_uses_defined_journeys(self):
        fw = UETestFramework()
        persona = fw.define_persona("u", "beginner", [], [])
        steps = [JourneyStep("Login", "Logged in", "Retry")]
        fw.define_journey("login", persona, steps)
        plan = fw.generate_ue_test_plan("Test Project")
        assert len(plan.journey_tests) == 1
        assert plan.journey_tests[0]["name"] == "login"

    def test_plan_contains_cognitive_load_assessment(self):
        fw = UETestFramework()
        plan = fw.generate_ue_test_plan("Test Project")
        assert "score" in plan.cognitive_load_assessment

    def test_plan_to_markdown(self):
        fw = UETestFramework()
        plan = fw.generate_ue_test_plan("Test Project")
        md = plan.to_markdown()
        assert "UE Test Plan" in md
        assert "Test Project" in md


class TestValidateUserJourney:
    """Tests for UETestFramework.validate_user_journey."""

    def _make_journey(self, fw):
        persona = fw.define_persona("u", "beginner", [], [])
        steps = [
            JourneyStep("Step 1", "OK", "Retry", time_budget_seconds=10.0),
            JourneyStep("Step 2", "OK", "Retry", time_budget_seconds=10.0),
        ]
        return fw.define_journey("test_journey", persona, steps)

    def test_perfect_results(self):
        fw = UETestFramework()
        journey = self._make_journey(fw)
        results = {
            "steps_completed": 2,
            "steps_total": 2,
            "errors_recovered": 0,
            "errors_total": 0,
            "time_used_seconds": 10.0,
            "frustration_events": 0,
            "decisions_per_step": [1.0, 1.0],
        }
        validation = fw.validate_user_journey(journey, results)
        assert validation.completion_rate == 1.0
        assert validation.overall_ue_score >= 0.8

    def test_partial_completion(self):
        fw = UETestFramework()
        journey = self._make_journey(fw)
        results = {
            "steps_completed": 1,
            "steps_total": 2,
            "errors_recovered": 0,
            "errors_total": 0,
            "time_used_seconds": 10.0,
            "frustration_events": 0,
        }
        validation = fw.validate_user_journey(journey, results)
        assert validation.completion_rate == 0.5

    def test_error_recovery_rate(self):
        fw = UETestFramework()
        journey = self._make_journey(fw)
        results = {
            "steps_completed": 2,
            "steps_total": 2,
            "errors_recovered": 1,
            "errors_total": 2,
            "time_used_seconds": 10.0,
            "frustration_events": 0,
        }
        validation = fw.validate_user_journey(journey, results)
        assert validation.error_recovery_rate == 0.5

    def test_time_budget_exceeded(self):
        fw = UETestFramework()
        journey = self._make_journey(fw)
        results = {
            "steps_completed": 2,
            "steps_total": 2,
            "errors_recovered": 0,
            "errors_total": 0,
            "time_used_seconds": 100.0,
            "frustration_events": 0,
        }
        validation = fw.validate_user_journey(journey, results)
        assert validation.time_budget_adherence < 1.0

    def test_cognitive_load_from_decisions(self):
        fw = UETestFramework()
        journey = self._make_journey(fw)
        results = {
            "steps_completed": 2,
            "steps_total": 2,
            "errors_recovered": 0,
            "errors_total": 0,
            "time_used_seconds": 10.0,
            "frustration_events": 0,
            "decisions_per_step": [7.0, 7.0],
        }
        validation = fw.validate_user_journey(journey, results)
        assert validation.cognitive_load_score == 1.0

    def test_validation_to_dict(self):
        fw = UETestFramework()
        journey = self._make_journey(fw)
        results = {
            "steps_completed": 2,
            "steps_total": 2,
            "errors_recovered": 0,
            "errors_total": 0,
            "time_used_seconds": 10.0,
            "frustration_events": 0,
        }
        validation = fw.validate_user_journey(journey, results)
        d = validation.to_dict()
        assert "journey_name" in d
        assert "completion_rate" in d
        assert "overall_ue_score" in d


class TestAssessUsability:
    """Tests for UETestFramework.assess_usability (rule-based mode)."""

    def test_rule_based_assessment_returns_report(self):
        fw = UETestFramework()
        report = fw.assess_usability("A clean, minimal interface with consistent patterns and undo support")
        assert report.overall_score is not None
        assert len(report.heuristics) == 10

    def test_positive_keywords_boost_score(self):
        fw = UETestFramework()
        good_desc = (
            "A clean minimal interface with loading progress indicators, "
            "undo and cancel support, consistent standard patterns, "
            "validation and error prevention, visible icons and menus, "
            "keyboard shortcuts, helpful error messages, and documentation"
        )
        report = fw.assess_usability(good_desc)
        assert report.overall_score > 0

    def test_negative_keywords_lower_score(self):
        fw = UETestFramework()
        bad_desc = (
            "No feedback when loading, frozen unresponsive UI, "
            "no undo no cancel, inconsistent confusing labels, "
            "no validation, hidden invisible options, "
            "no shortcut tedious repetitive, cluttered overwhelming, "
            "cryptic error codes, no help no documentation"
        )
        report = fw.assess_usability(bad_desc)
        assert len(report.critical_issues) > 0

    def test_neutral_description_no_indicators(self):
        fw = UETestFramework()
        report = fw.assess_usability("A basic web page with some content")
        # Most heuristics should have passed=None (no indicators found)
        untested = [h for h in report.heuristics if h.passed is None]
        assert len(untested) > 0

    def test_report_has_recommendations_on_failure(self):
        fw = UETestFramework()
        report = fw.assess_usability("No feedback, no undo, cryptic error")
        assert len(report.recommendations) > 0

    def test_report_to_dict(self):
        fw = UETestFramework()
        report = fw.assess_usability("Clean interface with undo support")
        d = report.to_dict()
        assert "overall_score" in d
        assert "heuristics" in d
        assert "critical_issues" in d
        assert "recommendations" in d


class TestNielsenHeuristics:
    """Tests for Nielsen's 10 usability heuristics presence."""

    EXPECTED_HEURISTICS = [
        "visibility_of_system_status",
        "match_between_system_and_real_world",
        "user_control_and_freedom",
        "consistency_and_standards",
        "error_prevention",
        "recognition_rather_than_recall",
        "flexibility_and_efficiency_of_use",
        "aesthetic_and_minimalist_design",
        "help_users_recognize_diagnose_and_recover_from_errors",
        "help_and_documentation",
    ]

    def test_all_10_heuristics_present(self):
        fw = UETestFramework()
        heuristic_names = [h.name for h in fw._heuristics]
        for name in self.EXPECTED_HEURISTICS:
            assert name in heuristic_names, f"Missing heuristic: {name}"

    def test_exactly_10_heuristics(self):
        fw = UETestFramework()
        assert len(fw._heuristics) == 10

    def test_each_heuristic_has_description(self):
        fw = UETestFramework()
        for h in fw._heuristics:
            assert len(h.description) > 0, f"Heuristic {h.name} has no description"

    def test_heuristic_positive_keywords_exist(self):
        fw = UETestFramework()
        for name in self.EXPECTED_HEURISTICS:
            keywords = fw._heuristic_positive_keywords(name)
            assert len(keywords) > 0, f"No positive keywords for {name}"

    def test_heuristic_negative_keywords_exist(self):
        fw = UETestFramework()
        for name in self.EXPECTED_HEURISTICS:
            keywords = fw._heuristic_negative_keywords(name)
            assert len(keywords) > 0, f"No negative keywords for {name}"

    def test_heuristic_recommendations_exist(self):
        fw = UETestFramework()
        for name in self.EXPECTED_HEURISTICS:
            rec = fw._heuristic_recommendation(name)
            assert len(rec) > 0, f"No recommendation for {name}"


class TestWCAGAccessibility:
    """Tests for WCAG 2.1 AA accessibility checks."""

    def test_wcag_checks_defined(self):
        assert len(WCAG_AA_CHECKS) > 0

    def test_wcag_checks_have_required_fields(self):
        for check in WCAG_AA_CHECKS:
            assert "check" in check
            assert "category" in check
            assert "description" in check

    def test_wcag_covers_perceivable(self):
        categories = {c["category"] for c in WCAG_AA_CHECKS}
        assert "perceivable" in categories

    def test_wcag_covers_operable(self):
        categories = {c["category"] for c in WCAG_AA_CHECKS}
        assert "operable" in categories

    def test_wcag_covers_understandable(self):
        categories = {c["category"] for c in WCAG_AA_CHECKS}
        assert "understandable" in categories

    def test_wcag_covers_robust(self):
        categories = {c["category"] for c in WCAG_AA_CHECKS}
        assert "robust" in categories

    def test_accessibility_checks_in_test_plan(self):
        fw = UETestFramework()
        plan = fw.generate_ue_test_plan("Test")
        for ac in plan.accessibility_checks:
            assert "check" in ac
            assert "category" in ac
            assert "status" in ac
            assert ac["status"] == "pending"


class TestCognitiveLoadAssessment:
    """Tests for cognitive load assessment."""

    def test_no_journeys_zero_score(self):
        fw = UETestFramework()
        result = fw._assess_cognitive_load()
        assert result["score"] == 0.0
        assert result["assessment"] == "No journeys defined"

    def test_simple_journey_low_cognitive_load(self):
        fw = UETestFramework()
        persona = fw.define_persona("u", "beginner", [], [])
        steps = [JourneyStep("Click button", "Done", "Retry")]
        fw.define_journey("simple", persona, steps)
        result = fw._assess_cognitive_load()
        assert result["score"] < 0.5
        assert result["total_steps"] == 1

    def test_complex_journey_higher_cognitive_load(self):
        fw = UETestFramework()
        persona = fw.define_persona("u", "beginner", [], [])
        # Each frustration_trigger adds to decision count
        steps = [
            JourneyStep("Complex action", "Done", "Retry",
                        frustration_triggers=["confusing", "overwhelming", "ambiguous", "hidden", "slow", "stuck", "error"]),
        ]
        fw.define_journey("complex", persona, steps)
        result = fw._assess_cognitive_load()
        assert result["score"] >= 0.5

    def test_cognitive_load_millers_law(self):
        """Cognitive load should be capped at 1.0 (Miller's law: 7±2)."""
        fw = UETestFramework()
        persona = fw.define_persona("u", "beginner", [], [])
        steps = [
            JourneyStep("Action", "Done", "Retry",
                        frustration_triggers=[f"trigger_{i}" for i in range(20)]),
        ]
        fw.define_journey("overload", persona, steps)
        result = fw._assess_cognitive_load()
        assert result["score"] <= 1.0

    def test_cognitive_load_assessment_labels(self):
        fw = UETestFramework()
        persona = fw.define_persona("u", "beginner", [], [])
        steps = [JourneyStep("Step", "Done", "Retry")]
        fw.define_journey("j", persona, steps)
        result = fw._assess_cognitive_load()
        assert result["assessment"] in ("Low", "Medium - consider reducing options", "High - needs simplification")
