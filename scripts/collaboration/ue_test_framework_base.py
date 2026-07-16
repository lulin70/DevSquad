"""Shared base for UETestFramework and its mixins.

Declares the UE test data classes (``UserPersona``, ``JourneyStep``,
``UserJourney``, ``HeuristicCheck``, ``UETestPlan``, ``JourneyValidation``,
``UsabilityReport``) and the :class:`UETestFrameworkBase` structural class so
that the split UETestFramework mixins can be type-checked by mypy without
heavy casts or ``# type: ignore`` comments.

Public symbols are re-exported by :mod:`scripts.collaboration.ue_test_framework`
for backward compatibility.
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
        sections = [
            self._format_persona_scenarios(),
            self._format_journey_tests(),
            self._format_heuristic_checks(),
            self._format_accessibility_checks(),
            self._format_error_recovery_tests(),
            self._format_cognitive_load(),
        ]
        for section in sections:
            lines.extend(section)
        lines.extend(["---", "*Generated by UETestFramework*"])
        return "\n".join(lines)

    def _format_persona_scenarios(self) -> list[str]:
        if not self.persona_scenarios:
            return []
        lines = ["## Persona Scenarios"]
        for idx, sc in enumerate(self.persona_scenarios, 1):
            lines.append(f"### {idx}. {sc.get('persona', 'Unknown')}")
            for goal in sc.get("goals", []):
                lines.append(f"- Goal: {goal}")
            for frust in sc.get("frustrations", []):
                lines.append(f"- Frustration: {frust}")
            lines.append("")
        return lines

    def _format_journey_tests(self) -> list[str]:
        if not self.journey_tests:
            return []
        lines = ["## Journey Tests"]
        for idx, jt in enumerate(self.journey_tests, 1):
            lines.append(f"### {idx}. {jt.get('name', 'Unknown')}")
            lines.append(f"- Persona: {jt.get('persona', 'N/A')}")
            lines.append(f"- Critical: {'Yes' if jt.get('critical', False) else 'No'}")
            for step in jt.get("steps", []):
                lines.append(f"  1. {step.get('action', 'N/A')} -> {step.get('expected_outcome', 'N/A')}")
            lines.append("")
        return lines

    def _format_heuristic_checks(self) -> list[str]:
        if not self.heuristic_checks:
            return []
        lines = ["## Nielsen's 10 Heuristics"]
        for hc in self.heuristic_checks:
            status = "PASS" if hc.passed else ("FAIL" if hc.passed is False else "UNTESTED")
            lines.append(f"- [{status}] **{hc.name}**: {hc.description}")
            if hc.evidence:
                lines.append(f"  - Evidence: {hc.evidence}")
            if hc.severity:
                lines.append(f"  - Severity: {hc.severity}")
        lines.append("")
        return lines

    def _format_accessibility_checks(self) -> list[str]:
        if not self.accessibility_checks:
            return []
        lines = ["## Accessibility Checks (WCAG 2.1 AA)"]
        for ac in self.accessibility_checks:
            lines.append(f"- {ac.get('check', 'N/A')}: {ac.get('status', 'N/A')}")
        lines.append("")
        return lines

    def _format_error_recovery_tests(self) -> list[str]:
        if not self.error_recovery_tests:
            return []
        lines = ["## Error Recovery Tests"]
        for ert in self.error_recovery_tests:
            lines.append(f"- {ert.get('scenario', 'N/A')}: {ert.get('recovery', 'N/A')}")
        lines.append("")
        return lines

    def _format_cognitive_load(self) -> list[str]:
        if not self.cognitive_load_assessment:
            return []
        lines = ["## Cognitive Load Assessment"]
        for key, val in self.cognitive_load_assessment.items():
            lines.append(f"- **{key}**: {val}")
        lines.append("")
        return lines


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
# Structural Base
# ============================================================


class UETestFrameworkBase:
    """Structural base for UETestFramework mixins.

    Attributes are declared as class-level annotations; concrete values are
    assigned by ``UETestFramework.__init__``. Mixins reference these
    attributes so that they can be type-checked by mypy without casts.
    """

    # Instance state assigned by UETestFramework.__init__
    llm_backend: Any
    _personas: list[UserPersona]
    _journeys: list[UserJourney]
    _heuristics: list[HeuristicCheck]
