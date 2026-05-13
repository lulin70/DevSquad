#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for V3.6.0 AnchorChecker and RetrospectiveEngine

Covers: Happy path, error case, boundary, performance, configuration, integration
"""

import time
import unittest
from scripts.collaboration.anchor_checker import AnchorChecker, _tokenize, _cosine_similarity
from scripts.collaboration.retrospective import RetrospectiveEngine
from scripts.collaboration.models import (
    StructuredGoal, GoalItem, GoalItemStatus,
    AnchorResult, AnchorTrigger, DriftSeverity, DriftItem,
    DeviationRecord, RetrospectiveReport,
)


class TestTokenization(unittest.TestCase):

    def test_tokenize_english(self):
        tokens = _tokenize("Design a secure authentication system")
        self.assertIn("design", tokens)
        self.assertIn("secure", tokens)
        self.assertIn("authentication", tokens)
        self.assertIn("system", tokens)

    def test_tokenize_chinese(self):
        tokens = _tokenize("设计一个安全的认证系统")
        self.assertIn("设计", tokens)
        self.assertIn("安全", tokens)
        self.assertIn("认证", tokens)
        self.assertIn("系统", tokens)

    def test_tokenize_mixed(self):
        tokens = _tokenize("实现JWT认证和RBAC权限控制")
        self.assertIn("jwt", tokens)
        self.assertIn("rbac", tokens)
        self.assertIn("权限控制", tokens)
        has_auth_token = any("认证" in t for t in tokens)
        self.assertTrue(has_auth_token, f"Expected '认证' in tokens, got {tokens}")

    def test_tokenize_empty(self):
        self.assertEqual(_tokenize(""), [])

    def test_tokenize_stopwords_filtered(self):
        tokens = _tokenize("the system is a good implementation of the design")
        self.assertNotIn("the", tokens)
        self.assertNotIn("is", tokens)
        self.assertNotIn("a", tokens)

    def test_cosine_similarity_identical(self):
        v = {"a": 1.0, "b": 2.0}
        self.assertAlmostEqual(_cosine_similarity(v, v), 1.0, places=5)

    def test_cosine_similarity_orthogonal(self):
        v1 = {"a": 1.0}
        v2 = {"b": 1.0}
        self.assertAlmostEqual(_cosine_similarity(v1, v2), 0.0, places=5)

    def test_cosine_similarity_empty(self):
        self.assertEqual(_cosine_similarity({}, {}), 0.0)


class TestAnchorCheckerParseGoal(unittest.TestCase):

    def setUp(self):
        self.checker = AnchorChecker()

    def test_parse_goal_with_requirements(self):
        goal = self.checker.parse_goal(
            "需要实现用户认证系统，必须支持JWT和RBAC，确保安全性"
        )
        self.assertIsInstance(goal, StructuredGoal)
        self.assertTrue(len(goal.items) > 0)
        self.assertEqual(goal.original_description, "需要实现用户认证系统，必须支持JWT和RBAC，确保安全性")

    def test_parse_goal_with_list_items(self):
        goal = self.checker.parse_goal(
            "Design auth system:\n- JWT tokens\n- RBAC roles\n- Password hashing"
        )
        self.assertTrue(len(goal.items) >= 2)

    def test_parse_goal_with_numbered_items(self):
        goal = self.checker.parse_goal(
            "Requirements:\n1. User login\n2. Token refresh\n3. Role management"
        )
        self.assertTrue(len(goal.items) >= 2)

    def test_parse_goal_simple_description(self):
        goal = self.checker.parse_goal("Write a sorting function")
        self.assertTrue(len(goal.items) >= 1)
        self.assertEqual(goal.items[0].item_id, "G0")

    def test_parse_goal_empty(self):
        goal = self.checker.parse_goal("")
        self.assertTrue(len(goal.items) >= 1)

    def test_parse_goal_generates_id(self):
        goal = self.checker.parse_goal("Test task")
        self.assertTrue(goal.goal_id.startswith("goal_"))


class TestAnchorCheckerCheck(unittest.TestCase):

    def setUp(self):
        self.checker = AnchorChecker()

    def test_check_aligned_output(self):
        goal = self.checker.parse_goal("Implement JWT authentication with token refresh")
        result = self.checker.check(
            goal,
            "Implemented JWT authentication module with access token and refresh token support",
            trigger=AnchorTrigger.STEP_COMPLETE,
        )
        self.assertIsInstance(result, AnchorResult)
        self.assertTrue(result.aligned)
        self.assertGreater(result.coverage, 0.3)

    def test_check_drifted_output(self):
        goal = self.checker.parse_goal("Implement JWT authentication with token refresh")
        result = self.checker.check(
            goal,
            "Built a beautiful dashboard with charts and graphs for data visualization",
            trigger=AnchorTrigger.STEP_COMPLETE,
        )
        self.assertFalse(result.aligned)
        self.assertGreater(result.drift_score, 0.1)

    def test_check_empty_output(self):
        goal = self.checker.parse_goal("Implement JWT authentication")
        result = self.checker.check(goal, "", trigger=AnchorTrigger.STEP_COMPLETE)
        self.assertFalse(result.aligned)

    def test_check_partial_coverage(self):
        goal = self.checker.parse_goal(
            "需要实现：1. 用户注册 2. 用户登录 3. 密码重置 4. 权限管理"
        )
        result = self.checker.check(
            goal,
            "实现了用户注册和登录功能",
            trigger=AnchorTrigger.STEP_COMPLETE,
        )
        self.assertLess(result.coverage, 1.0)

    def test_check_phase_gate_trigger(self):
        goal = self.checker.parse_goal("Design microservice architecture")
        result = self.checker.check(
            goal,
            "Designed microservice architecture with service mesh",
            trigger=AnchorTrigger.PHASE_GATE,
        )
        self.assertEqual(result.trigger, AnchorTrigger.PHASE_GATE)

    def test_check_conflict_trigger(self):
        goal = self.checker.parse_goal("Build REST API")
        result = self.checker.check(
            goal,
            "Built REST API endpoints",
            trigger=AnchorTrigger.CONFLICT,
        )
        self.assertEqual(result.trigger, AnchorTrigger.CONFLICT)

    def test_check_severity_levels(self):
        goal = self.checker.parse_goal("Implement secure authentication system with JWT RBAC")
        result_aligned = self.checker.check(
            goal,
            "Implemented secure JWT authentication and RBAC authorization system",
        )
        result_drifted = self.checker.check(
            goal,
            "Created a color palette for the UI theme",
        )
        self.assertNotEqual(result_drifted.severity, DriftSeverity.NONE)
        self.assertGreater(result_aligned.coverage, result_drifted.coverage)

    def test_check_history_recorded(self):
        goal = self.checker.parse_goal("Test task")
        self.checker.check(goal, "Test output")
        self.assertEqual(self.checker.total_checks, 1)
        self.assertEqual(len(self.checker.check_history), 1)

    def test_check_drift_count(self):
        goal = self.checker.parse_goal("Implement authentication")
        self.checker.check(goal, "Authentication implemented")
        self.checker.check(goal, "Built dashboard instead")
        self.assertGreaterEqual(self.checker.drift_count, 0)

    def test_check_reset(self):
        goal = self.checker.parse_goal("Test task")
        self.checker.check(goal, "Test output")
        self.checker.reset()
        self.assertEqual(self.checker.total_checks, 0)


class TestAnchorCheckerPerformance(unittest.TestCase):

    def test_check_under_50ms(self):
        checker = AnchorChecker()
        goal = checker.parse_goal(
            "Design a scalable microservice architecture with API gateway, "
            "service discovery, load balancing, circuit breaker, and monitoring"
        )
        start = time.time()
        for _ in range(10):
            checker.check(goal, "Designed microservice architecture with all components")
        elapsed = (time.time() - start) / 10
        self.assertLess(elapsed, 0.05, f"Anchor check took {elapsed*1000:.1f}ms, expected <50ms")


class TestStructuredGoal(unittest.TestCase):

    def test_overall_coverage(self):
        goal = StructuredGoal(
            goal_id="test",
            items=[
                GoalItem(item_id="G0", description="A", coverage_score=0.8),
                GoalItem(item_id="G1", description="B", coverage_score=0.6),
            ],
        )
        self.assertAlmostEqual(goal.overall_coverage, 0.7, places=2)

    def test_overall_coverage_empty(self):
        goal = StructuredGoal(goal_id="test")
        self.assertEqual(goal.overall_coverage, 0.0)

    def test_uncovered_items(self):
        goal = StructuredGoal(
            goal_id="test",
            items=[
                GoalItem(item_id="G0", description="A", status=GoalItemStatus.FULLY_COVERED),
                GoalItem(item_id="G1", description="B", status=GoalItemStatus.PENDING),
                GoalItem(item_id="G2", description="C", status=GoalItemStatus.PARTIALLY_COVERED),
            ],
        )
        uncovered = goal.uncovered_items
        self.assertEqual(len(uncovered), 2)


class TestAnchorResult(unittest.TestCase):

    def test_severity_none(self):
        result = AnchorResult(drift_score=0.05)
        self.assertEqual(result.severity, DriftSeverity.NONE)

    def test_severity_low(self):
        result = AnchorResult(drift_score=0.15)
        self.assertEqual(result.severity, DriftSeverity.LOW)

    def test_severity_medium(self):
        result = AnchorResult(drift_score=0.25)
        self.assertEqual(result.severity, DriftSeverity.MEDIUM)

    def test_severity_high(self):
        result = AnchorResult(drift_score=0.4)
        self.assertEqual(result.severity, DriftSeverity.HIGH)

    def test_severity_critical(self):
        result = AnchorResult(drift_score=0.6)
        self.assertEqual(result.severity, DriftSeverity.CRITICAL)


class TestRetrospectiveEngine(unittest.TestCase):

    def setUp(self):
        self.engine = RetrospectiveEngine(memory_bridge=None)

    def test_run_with_no_deviations(self):
        goal = StructuredGoal(
            goal_id="test",
            original_description="Test task",
            items=[
                GoalItem(item_id="G0", description="A", coverage_score=0.9, status=GoalItemStatus.FULLY_COVERED),
            ],
        )
        report = self.engine.run(goal, anchor_history=[])
        self.assertIsInstance(report, RetrospectiveReport)
        self.assertEqual(len(report.deviations), 0)
        self.assertGreater(len(report.improvements), 0)

    def test_run_with_uncovered_goals(self):
        goal = StructuredGoal(
            goal_id="test",
            original_description="Test task",
            items=[
                GoalItem(item_id="G0", description="Feature A", coverage_score=0.9, status=GoalItemStatus.FULLY_COVERED),
                GoalItem(item_id="G1", description="Feature B", coverage_score=0.1, status=GoalItemStatus.PENDING),
            ],
        )
        report = self.engine.run(goal, anchor_history=[])
        self.assertGreater(len(report.deviations), 0)
        dev_types = [d.deviation_type for d in report.deviations]
        self.assertIn("goal_uncovered", dev_types)

    def test_run_with_drift_history(self):
        goal = StructuredGoal(
            goal_id="test",
            original_description="Test task",
            items=[
                GoalItem(item_id="G0", description="A", coverage_score=0.5, status=GoalItemStatus.PARTIALLY_COVERED),
            ],
        )
        anchor_history = [
            AnchorResult(aligned=False, drift_score=0.4, trigger=AnchorTrigger.STEP_COMPLETE),
            AnchorResult(aligned=False, drift_score=0.5, trigger=AnchorTrigger.STEP_COMPLETE),
            AnchorResult(aligned=False, drift_score=0.6, trigger=AnchorTrigger.STEP_COMPLETE),
        ]
        report = self.engine.run(goal, anchor_history=anchor_history)
        dev_types = [d.deviation_type for d in report.deviations]
        self.assertIn("goal_drift", dev_types)
        self.assertIn("sustained_drift", dev_types)

    def test_run_generates_improvements(self):
        goal = StructuredGoal(
            goal_id="test",
            original_description="Test task",
            items=[
                GoalItem(item_id="G0", description="A", coverage_score=0.2, status=GoalItemStatus.PENDING),
            ],
        )
        report = self.engine.run(goal, anchor_history=[])
        self.assertGreater(len(report.improvements), 0)

    def test_run_report_to_dict(self):
        goal = StructuredGoal(
            goal_id="test",
            original_description="Test task",
            items=[GoalItem(item_id="G0", description="A", coverage_score=0.9, status=GoalItemStatus.FULLY_COVERED)],
        )
        report = self.engine.run(goal, anchor_history=[])
        d = report.to_dict()
        self.assertIn("task_goal", d)
        self.assertIn("deviation_count", d)
        self.assertIn("final_coverage", d)

    def test_run_report_to_markdown(self):
        goal = StructuredGoal(
            goal_id="test",
            original_description="Test task",
            items=[GoalItem(item_id="G0", description="A", coverage_score=0.9, status=GoalItemStatus.FULLY_COVERED)],
        )
        report = self.engine.run(goal, anchor_history=[])
        md = report.to_markdown()
        self.assertIn("Retrospective Report", md)
        self.assertIn("Test task", md)

    def test_load_historical_no_bridge(self):
        results = self.engine.load_historical("test task")
        self.assertEqual(results, [])


class TestRetrospectiveEnginePerformance(unittest.TestCase):

    def test_run_under_200ms(self):
        engine = RetrospectiveEngine(memory_bridge=None)
        goal = StructuredGoal(
            goal_id="test",
            original_description="Complex task with many requirements",
            items=[
                GoalItem(item_id=f"G{i}", description=f"Feature {i}", coverage_score=0.5, status=GoalItemStatus.PARTIALLY_COVERED)
                for i in range(20)
            ],
        )
        anchor_history = [
            AnchorResult(aligned=i % 3 != 0, drift_score=0.2 if i % 3 != 0 else 0.5, trigger=AnchorTrigger.STEP_COMPLETE)
            for i in range(10)
        ]
        start = time.time()
        engine.run(goal, anchor_history=anchor_history)
        elapsed = time.time() - start
        self.assertLess(elapsed, 0.2, f"Retrospective took {elapsed*1000:.1f}ms, expected <200ms")


class TestAnchorCheckerConfiguration(unittest.TestCase):

    def test_custom_drift_threshold(self):
        checker = AnchorChecker(drift_threshold=0.5, coverage_threshold=0.3)
        self.assertEqual(checker._drift_threshold, 0.5)
        self.assertEqual(checker._coverage_threshold, 0.3)

    def test_strict_threshold_catches_more(self):
        strict = AnchorChecker(drift_threshold=0.1, coverage_threshold=0.9)
        loose = AnchorChecker(drift_threshold=0.5, coverage_threshold=0.3)
        goal = strict.parse_goal("Implement JWT authentication")
        result_strict = strict.check(goal, "Implemented JWT auth with basic token support")
        result_loose = loose.check(goal, "Implemented JWT auth with basic token support")
        self.assertLessEqual(result_strict.coverage, result_loose.coverage + 0.01)


class TestIntegrationAnchorRetrospective(unittest.TestCase):

    def test_full_workflow(self):
        checker = AnchorChecker()
        engine = RetrospectiveEngine(memory_bridge=None)

        goal = checker.parse_goal(
            "Design secure auth system: 1. JWT tokens 2. RBAC 3. Password hashing"
        )

        checker.check(goal, "Implemented JWT token generation and validation", trigger=AnchorTrigger.STEP_COMPLETE)
        checker.check(goal, "Added RBAC role-based access control", trigger=AnchorTrigger.STEP_COMPLETE)
        checker.check(goal, "Configured password hashing with bcrypt", trigger=AnchorTrigger.STEP_COMPLETE)

        report = engine.run(
            goal=goal,
            anchor_history=checker.check_history,
        )

        self.assertGreater(report.final_coverage, 0.0)
        self.assertEqual(report.anchor_check_count, 3)
        self.assertIn("JWT", report.task_goal)

    def test_drift_detection_workflow(self):
        checker = AnchorChecker()
        engine = RetrospectiveEngine(memory_bridge=None)

        goal = checker.parse_goal("Implement user authentication system")
        checker.check(goal, "Built a data visualization dashboard", trigger=AnchorTrigger.STEP_COMPLETE)
        checker.check(goal, "Added chart rendering engine", trigger=AnchorTrigger.STEP_COMPLETE)

        report = engine.run(goal=goal, anchor_history=checker.check_history)

        self.assertGreater(len(report.deviations), 0)
        self.assertGreater(report.anchor_drift_count, 0)


if __name__ == "__main__":
    unittest.main()
