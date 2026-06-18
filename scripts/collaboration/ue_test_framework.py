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

使用示例:
    from scripts.collaboration.ue_test_framework import UETestFramework

    framework = UETestFramework()
    persona = framework.define_persona("first-time-user", "beginner",
                                        ["完成注册"], ["找不到按钮"])
    journey = framework.define_journey("signup", persona, steps=[...])
    plan = framework.generate_ue_test_plan("用户注册系统")
    print(plan.to_markdown())
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# ============================================================
# Data Classes
# ============================================================


@dataclass
class UserPersona:
    """用户画像定义。

    Attributes:
        name: 画像名称（如 "first-time-user", "power-user"）
        tech_level: 技术水平 "beginner" | "intermediate" | "advanced"
        goals: 该画像想要达成的目标列表
        frustrations: 常见痛点列表
        patience_threshold: 容错耐心 0-1，越高越容忍错误（默认 0.7）
    """

    name: str
    tech_level: str  # beginner/intermediate/advanced
    goals: list[str]
    frustrations: list[str]
    patience_threshold: float = 0.7

    def to_dict(self) -> dict[str, Any]:
        """Serialize the user persona to a dictionary.

        Returns:
            Dictionary containing name, tech_level, goals, frustrations,
            and patience_threshold.
        """
        return {
            "name": self.name,
            "tech_level": self.tech_level,
            "goals": self.goals,
            "frustrations": self.frustrations,
            "patience_threshold": self.patience_threshold,
        }


@dataclass
class JourneyStep:
    """用户旅程中的单一步骤。

    Attributes:
        action: 用户执行的操作描述
        expected_outcome: 预期结果
        error_recovery: 出错时用户应如何恢复
        time_budget_seconds: 完成此步骤的时间预算（默认 30 秒）
        frustration_triggers: 可能触发挫败感的事件列表
    """

    action: str
    expected_outcome: str
    error_recovery: str
    time_budget_seconds: float = 30.0
    frustration_triggers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the journey step to a dictionary.

        Returns:
            Dictionary containing action, expected_outcome, error_recovery,
            time_budget_seconds, and frustration_triggers.
        """
        return {
            "action": self.action,
            "expected_outcome": self.expected_outcome,
            "error_recovery": self.error_recovery,
            "time_budget_seconds": self.time_budget_seconds,
            "frustration_triggers": self.frustration_triggers,
        }


@dataclass
class UserJourney:
    """用户旅程定义。

    Attributes:
        name: 旅程名称
        persona: 关联的用户画像
        steps: 旅程步骤列表
        critical_path: 是否为关键路径（必须成功的旅程，默认 True）
    """

    name: str
    persona: UserPersona
    steps: list[JourneyStep]
    critical_path: bool = True

    @property
    def total_time_budget(self) -> float:
        """所有步骤的时间预算总和。"""
        return sum(s.time_budget_seconds for s in self.steps)

    @property
    def step_count(self) -> int:
        """步骤数量。"""
        return len(self.steps)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the user journey to a dictionary.

        Returns:
            Dictionary containing name, persona name, serialized steps,
            critical_path flag, and total_time_budget.
        """
        return {
            "name": self.name,
            "persona": self.persona.name,
            "steps": [s.to_dict() for s in self.steps],
            "critical_path": self.critical_path,
            "total_time_budget": self.total_time_budget,
        }


@dataclass
class HeuristicCheck:
    """Nielsen 可用性启发式检查项。

    Attributes:
        name: 启发式名称（英文标识符）
        description: 启发式描述
        passed: 是否通过（None=未检查）
        evidence: 评估证据
        severity: 问题严重程度 cosmetic/minor/major/critical
    """

    name: str
    description: str
    passed: bool | None = None
    evidence: str = ""
    severity: str = ""  # cosmetic/minor/major/critical

    def to_dict(self) -> dict[str, Any]:
        """Serialize the heuristic check to a dictionary.

        Returns:
            Dictionary containing name, description, passed, evidence,
            and severity.
        """
        return {
            "name": self.name,
            "description": self.description,
            "passed": self.passed,
            "evidence": self.evidence,
            "severity": self.severity,
        }


@dataclass
class UETestPlan:
    """UE 测试计划。

    Attributes:
        project: 项目描述
        persona_scenarios: 基于用户画像的测试场景
        journey_tests: 用户旅程测试用例
        heuristic_checks: Nielsen 启发式检查清单
        accessibility_checks: WCAG 2.1 AA 无障碍检查
        error_recovery_tests: 错误恢复测试
        cognitive_load_assessment: 认知负载评估
    """

    project: str
    persona_scenarios: list[dict[str, Any]]
    journey_tests: list[dict[str, Any]]
    heuristic_checks: list[HeuristicCheck]
    accessibility_checks: list[dict[str, Any]]
    error_recovery_tests: list[dict[str, Any]]
    cognitive_load_assessment: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Serialize the UE test plan to a dictionary.

        Returns:
            Dictionary containing project, persona_scenarios, journey_tests,
            serialized heuristic_checks, accessibility_checks,
            error_recovery_tests, and cognitive_load_assessment.
        """
        return {
            "project": self.project,
            "persona_scenarios": self.persona_scenarios,
            "journey_tests": self.journey_tests,
            "heuristic_checks": [h.to_dict() for h in self.heuristic_checks],
            "accessibility_checks": self.accessibility_checks,
            "error_recovery_tests": self.error_recovery_tests,
            "cognitive_load_assessment": self.cognitive_load_assessment,
        }

    def to_markdown(self) -> str:
        """Render the UE test plan as a Markdown document.

        Returns:
            Multi-line Markdown string with sections for project info,
            persona scenarios, journey tests, heuristic checks,
            accessibility checks, error recovery tests, and cognitive
            load assessment.
        """
        lines = [
            "# UE Test Plan",
            "",
            f"**Project**: {self.project}",
            f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]

        if self.persona_scenarios:
            lines.append("## Persona Scenarios")
            for idx, sc in enumerate(self.persona_scenarios, 1):
                lines.append(f"### {idx}. {sc.get('persona', 'Unknown')}")
                for goal in sc.get("goals", []):
                    lines.append(f"- Goal: {goal}")
                for frust in sc.get("frustrations", []):
                    lines.append(f"- Frustration: {frust}")
                lines.append("")

        if self.journey_tests:
            lines.append("## Journey Tests")
            for idx, jt in enumerate(self.journey_tests, 1):
                lines.append(f"### {idx}. {jt.get('name', 'Unknown')}")
                lines.append(f"- Persona: {jt.get('persona', 'N/A')}")
                lines.append(f"- Critical: {'Yes' if jt.get('critical', False) else 'No'}")
                for step in jt.get("steps", []):
                    lines.append(f"  1. {step.get('action', 'N/A')} -> {step.get('expected_outcome', 'N/A')}")
                lines.append("")

        if self.heuristic_checks:
            lines.append("## Nielsen's 10 Heuristics")
            for hc in self.heuristic_checks:
                status = "PASS" if hc.passed else ("FAIL" if hc.passed is False else "UNTESTED")
                lines.append(f"- [{status}] **{hc.name}**: {hc.description}")
                if hc.evidence:
                    lines.append(f"  - Evidence: {hc.evidence}")
                if hc.severity:
                    lines.append(f"  - Severity: {hc.severity}")
            lines.append("")

        if self.accessibility_checks:
            lines.append("## Accessibility Checks (WCAG 2.1 AA)")
            for ac in self.accessibility_checks:
                lines.append(f"- {ac.get('check', 'N/A')}: {ac.get('status', 'N/A')}")
            lines.append("")

        if self.error_recovery_tests:
            lines.append("## Error Recovery Tests")
            for ert in self.error_recovery_tests:
                lines.append(f"- {ert.get('scenario', 'N/A')}: {ert.get('recovery', 'N/A')}")
            lines.append("")

        if self.cognitive_load_assessment:
            lines.append("## Cognitive Load Assessment")
            for key, val in self.cognitive_load_assessment.items():
                lines.append(f"- **{key}**: {val}")
            lines.append("")

        lines.extend(["---", "*Generated by UETestFramework*"])
        return "\n".join(lines)


@dataclass
class JourneyValidation:
    """用户旅程验证结果。

    Attributes:
        journey_name: 旅程名称
        completion_rate: 任务完成率 0-1
        error_recovery_rate: 错误恢复率 0-1
        time_budget_adherence: 时间预算遵守率 0-1
        frustration_events: 挫败事件数量
        cognitive_load_score: 认知负载评分 0-1（越低越好）
        overall_ue_score: 综合UE评分 0-1
    """

    journey_name: str
    completion_rate: float
    error_recovery_rate: float
    time_budget_adherence: float
    frustration_events: int
    cognitive_load_score: float
    overall_ue_score: float

    def to_dict(self) -> dict[str, Any]:
        """Serialize the journey validation result to a dictionary.

        Returns:
            Dictionary containing journey name and rounded metric scores
            for completion, error recovery, time budget, frustration events,
            cognitive load, and overall UE score.
        """
        return {
            "journey_name": self.journey_name,
            "completion_rate": round(self.completion_rate, 3),
            "error_recovery_rate": round(self.error_recovery_rate, 3),
            "time_budget_adherence": round(self.time_budget_adherence, 3),
            "frustration_events": self.frustration_events,
            "cognitive_load_score": round(self.cognitive_load_score, 3),
            "overall_ue_score": round(self.overall_ue_score, 3),
        }

    def to_markdown(self) -> str:
        """Render the journey validation as a Markdown table.

        Returns:
            Markdown string with a metrics table and pass/fail indicators.
        """
        lines = [
            f"# Journey Validation: {self.journey_name}",
            "",
            "| Metric | Value | |",
            "|--------|-------|-|",
            f"| Completion Rate | {self.completion_rate:.0%} | {'PASS' if self.completion_rate >= 0.8 else 'FAIL'} |",
            f"| Error Recovery Rate | {self.error_recovery_rate:.0%} | {'PASS' if self.error_recovery_rate >= 0.7 else 'FAIL'} |",
            f"| Time Budget Adherence | {self.time_budget_adherence:.0%} | {'PASS' if self.time_budget_adherence >= 0.8 else 'FAIL'} |",
            f"| Frustration Events | {self.frustration_events} | {'PASS' if self.frustration_events <= 2 else 'WARN'} |",
            f"| Cognitive Load Score | {self.cognitive_load_score:.2f} | {'PASS' if self.cognitive_load_score <= 0.4 else 'WARN'} |",
            f"| **Overall UE Score** | **{self.overall_ue_score:.0%}** | {'PASS' if self.overall_ue_score >= 0.7 else 'FAIL'} |",
            "",
        ]
        return "\n".join(lines)


@dataclass
class UsabilityReport:
    """可用性评估报告。

    Attributes:
        heuristics: 启发式检查结果列表
        overall_score: 综合评分 0-1
        critical_issues: 关键问题列表
        recommendations: 改进建议列表
    """

    heuristics: list[HeuristicCheck]
    overall_score: float
    critical_issues: list[str]
    recommendations: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Serialize the usability report to a dictionary.

        Returns:
            Dictionary containing heuristic check dicts, rounded overall
            score, critical issues, and recommendations.
        """
        return {
            "heuristics": [h.to_dict() for h in self.heuristics],
            "overall_score": round(self.overall_score, 3),
            "critical_issues": self.critical_issues,
            "recommendations": self.recommendations,
        }

    def to_markdown(self) -> str:
        """Render the usability report as a Markdown document.

        Returns:
            Markdown string with overall score, heuristic pass counts,
            critical issues, and recommendations sections.
        """
        lines = [
            "# Usability Report",
            "",
            f"**Overall Score**: {self.overall_score:.0%}",
            "",
        ]

        passed = sum(1 for h in self.heuristics if h.passed is True)
        total = len(self.heuristics)
        lines.append(f"**Heuristics**: {passed}/{total} passed")
        lines.append("")

        if self.critical_issues:
            lines.append("## Critical Issues")
            for ci in self.critical_issues:
                lines.append(f"- {ci}")
            lines.append("")

        if self.recommendations:
            lines.append("## Recommendations")
            for rec in self.recommendations:
                lines.append(f"- {rec}")
            lines.append("")

        lines.extend(["---", "*Generated by UETestFramework*"])
        return "\n".join(lines)


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


# ============================================================
# Core Framework
# ============================================================


class UETestFramework:
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
        self._heuristics = self._default_heuristics()

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
        except Exception as e:
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

    def _generate_journey_tests(self) -> list[dict[str, Any]]:
        """Generate journey test cases from defined journeys."""
        tests = []
        for journey in self._journeys:
            test = {
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
