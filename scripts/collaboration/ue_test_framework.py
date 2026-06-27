#!/usr/bin/env python3
"""
UETestFramework - UE 测试框架 (Tester + PM 协作)

从用户视角生成和验证体验测试，而非仅从代码正确性视角。
桥接 Tester（测试覆盖）和 PM（用户故事）两种视角。

核心能力:
- UserPersona: 定义用户画像（技术水平、目标、痛点）
- UserJourney: 定义用户旅程（步骤、预期、错误恢复）
- UETestFramework: 生成 UE 测试计划、验证旅程、评估可用性
- Nielsen 10 启发式评估
- WCAG 2.1 AA 无障碍检查
- 认知负载评估

Implementation notes:
    - This module is a facade. The class body keeps only ``__init__`` and the
      core ``generate_ue_test_plan()`` orchestration method.
    - Auxiliary concerns are split into single-responsibility mixins under
      ``ue_test_*_mixin.py`` and the shared structural base in
      ``ue_test_framework_base.py`` (same package):
        * persona       -> UETestPersonaMixin
        * journey       -> UETestJourneyMixin
        * heuristic     -> UETestHeuristicMixin
        * accessibility -> UETestAccessibilityMixin
    - Public API (``UETestFramework``, all dataclasses, ``WCAG_AA_CHECKS``,
      ``quick_ue_assess``, ``quick_journey_validate``) remains importable from
      this module for backward compatibility.

使用示例:
    from scripts.collaboration.ue_test_framework import UETestFramework

    framework = UETestFramework()
    persona = framework.define_persona("first-time-user", "beginner",
                                        ["完成注册"], ["找不到按钮"])
    journey = framework.define_journey("signup", persona, steps=[...])
    plan = framework.generate_ue_test_plan("用户注册系统")
    print(plan.to_markdown())
"""

from typing import Any

from .ue_test_accessibility_mixin import WCAG_AA_CHECKS, UETestAccessibilityMixin
from .ue_test_framework_base import (
    HeuristicCheck,
    JourneyStep,
    JourneyValidation,
    UETestPlan,
    UsabilityReport,
    UserJourney,
    UserPersona,
)
from .ue_test_heuristic_mixin import UETestHeuristicMixin
from .ue_test_journey_mixin import UETestJourneyMixin
from .ue_test_persona_mixin import UETestPersonaMixin

# Re-export public API symbols for backward compatibility.
# All dataclasses + WCAG_AA_CHECKS are imported above and intentionally
# re-exported so that ``from .ue_test_framework import X`` keeps working
# after the split.
__all__ = [
    "UETestFramework",
    "UserPersona",
    "JourneyStep",
    "UserJourney",
    "HeuristicCheck",
    "UETestPlan",
    "JourneyValidation",
    "UsabilityReport",
    "WCAG_AA_CHECKS",
    "quick_ue_assess",
    "quick_journey_validate",
]


class UETestFramework(
    UETestPersonaMixin,
    UETestJourneyMixin,
    UETestHeuristicMixin,
    UETestAccessibilityMixin,
):
    """UE-focused test framework bridging Tester and PM perspectives.

    Generates user journey tests, usability heuristics checks, and
    accessibility validation from a product-user perspective, not just
    a code-correctness perspective.
    """

    def __init__(self, llm_backend: Any = None):
        """Initialize UE test framework.

        Args:
            llm_backend: Optional LLM backend for AI-assisted assessment.
                         If None, rule-based assessment is used.
        """
        self.llm_backend = llm_backend
        self._personas: list[UserPersona] = []
        self._journeys: list[UserJourney] = []
        self._heuristics: list[HeuristicCheck] = self._default_heuristics()

    def generate_ue_test_plan(self, project_description: str) -> UETestPlan:
        """Generate a comprehensive UE test plan.

        Combines PM's user story perspective with Tester's coverage perspective.
        Output includes:
        - Persona-based test scenarios
        - User journey test cases
        - Usability heuristics checklist (Nielsen's 10)
        - Accessibility checks (WCAG 2.1 AA)
        - Error recovery tests (what happens when user makes mistakes)
        - Cognitive load assessment
        - First-time user experience tests

        Args:
            project_description: Description of the project to test.

        Returns:
            UETestPlan with all generated test items.
        """
        persona_scenarios = self._generate_persona_scenarios()
        journey_tests = self._generate_journey_tests()
        heuristic_checks = list(self._heuristics)
        accessibility_checks = self._generate_accessibility_checks()
        error_recovery_tests = self._generate_error_recovery_tests()
        cognitive_load = self._assess_cognitive_load()

        return UETestPlan(
            project=project_description,
            persona_scenarios=persona_scenarios,
            journey_tests=journey_tests,
            heuristic_checks=heuristic_checks,
            accessibility_checks=accessibility_checks,
            error_recovery_tests=error_recovery_tests,
            cognitive_load_assessment=cognitive_load,
        )


# ============================================================
# Convenience Functions
# ============================================================


def quick_ue_assess(interface_description: str) -> UsabilityReport:
    """Quick usability assessment without defining personas/journeys.

    Args:
        interface_description: Description of the interface.

    Returns:
        UsabilityReport with heuristic evaluation.
    """
    framework = UETestFramework()
    return framework.assess_usability(interface_description)


def quick_journey_validate(
    journey: UserJourney,
    actual_results: dict[str, Any],
) -> JourneyValidation:
    """Quick journey validation.

    Args:
        journey: The user journey to validate.
        actual_results: Actual test results.

    Returns:
        JourneyValidation with computed scores.
    """
    framework = UETestFramework()
    return framework.validate_user_journey(journey, actual_results)
