#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CI Feedback Adapter (P1-5)

Reads CI results and injects context into dispatch pipeline:
  - Parse CI output (pytest, Jest, coverage, lint, build)
  - Extract key metrics: pass/fail, coverage %, errors
  - Generate structured context for Worker prompts
  - Provide actionable feedback for failed checks

Spec reference: SPEC_V35_Agent_Skills_Quality_Framework.md Section 7.5
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CIMetric:
    """A single CI metric with value and status."""
    name: str
    value: Any
    status: str  # "pass", "fail", "warning", "skip"
    details: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "status": self.status,
            "details": self.details,
        }


@dataclass
class CIResult:
    """Complete CI run result."""
    source: str  # e.g., "pytest", "jest", "coverage", "lint"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metrics: List[CIMetric] = field(default_factory=list)
    raw_output: str = ""
    success: bool = False
    duration_seconds: float = 0.0

    def get_metric(self, name: str) -> Optional[CIMetric]:
        for m in self.metrics:
            if m.name == name:
                return m
        return None

    def has_failures(self) -> bool:
        return any(m.status == "fail" for m in self.metrics)

    def to_summary(self) -> str:
        lines = [f"CI Result ({self.source}): {'✅ PASS' if self.success else '❌ FAIL'}"]
        for m in self.metrics:
            icon = {"pass": "✅", "fail": "❌", "warning": "⚠️", "skip": "⏭️"}.get(m.status, "?")
            lines.append(f"  {icon} {m.name}: {m.value}")
        if self.duration_seconds > 0:
            lines.append(f"  ⏱ Duration: {self.duration_seconds:.1f}s")
        return "\n".join(lines)


@dataclass
class CIContext:
    """Structured context extracted from CI results for injection into dispatch."""
    overall_status: str  # "all_pass", "has_failures", "no_ci_data"
    summary: str = ""
    actionable_items: List[Dict[str, Any]] = field(default_factory=list)
    quality_gates: Dict[str, bool] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)

    def to_prompt_injection(self) -> str:
        """Generate prompt-ready context string."""
        lines = [
            "\n## CI/CD Feedback Context\n",
            f"**Overall Status**: {self.overall_status.upper()}",
            "",
        ]

        if self.summary:
            lines.append(f"{self.summary}")
            lines.append("")

        if self.quality_gates:
            lines.append("**Quality Gates**:")
            for gate_name, passed in self.quality_gates.items():
                icon = "✅" if passed else "❌"
                lines.append(f"- {icon} {gate_name}: {'PASS' if passed else 'FAIL'}")
            lines.append("")

        if self.actionable_items:
            lines.append("**Action Items**:")
            for item in self.actionable_items[:10]:  # Limit to top 10
                severity = item.get("severity", "info").upper()
                lines.append(f"- [{severity}] {item.get('message', '')}")
            lines.append("")

        if self.recommendations:
            lines.append("**Recommendations**:")
            for rec in self.recommendations[:5]:  # Limit to top 5
                lines.append(f"- {rec}")

        return "\n".join(lines)


class PytestParser:
    """Parser for pytest-style test output."""

    @staticmethod
    def parse(output: str) -> CIResult:
        result = CIResult(source="pytest", raw_output=output)

        total_match = re.search(r'(\d+) passed', output)
        fail_match = re.search(r'(\d+) failed', output)
        error_match = re.search(r'(\d+) error', output)
        skip_match = re.search(r'(\d+) skipped', output)

        passed = int(total_match.group(1)) if total_match else 0
        failed = int(fail_match.group(1)) if fail_match else 0
        errors = int(error_match.group(1)) if error_match else 0
        skipped = int(skip_match.group(1)) if skip_match else 0

        result.metrics.append(CIMetric("tests_passed", passed, "pass"))
        result.metrics.append(CIMetric("tests_failed", failed, "fail" if failed > 0 else "pass"))
        result.metrics.append(CIMetric("errors", errors, "fail" if errors > 0 else "pass"))
        result.metrics.append(CIMetric("skipped", skipped, "skip"))

        duration_match = re.search(r'in ([\d.]+)s', output)
        if duration_match:
            result.duration_seconds = float(duration_match.group(1))

        result.success = (failed == 0 and errors == 0)
        return result


class CoverageParser:
    """Parser for coverage report output."""

    @staticmethod
    def parse(output: str) -> CIResult:
        result = CIResult(source="coverage", raw_output=output)

        pct_match = re.search(r'TOTAL\s+[\d\s]+\s+(\d+)%', output)
        if pct_match:
            pct = int(pct_match.group(1))
            result.metrics.append(
                CIMetric(
                    "coverage_percentage",
                    f"{pct}%",
                    "pass" if pct >= 80 else ("warning" if pct >= 60 else "fail"),
                    f"Target: ≥80%, Actual: {pct}%",
                )
            )

        line_match = re.search(r'(\d+)\s+missed', output)
        if line_match:
            missed = int(line_match.group(1))
            result.metrics.append(
                CIMetric("lines_missed", missed, "warning" if missed > 10 else "pass")
            )

        result.success = not result.has_failures()
        return result


class LintParser:
    """Parser for linter output (flake8, eslint, etc.)."""

    @staticmethod
    def parse(output: str) -> CIResult:
        result = CIResult(source="lint", raw_output=output)

        error_count = len(re.findall(r'^[EF]\d+', output, re.MULTILINE))
        warning_count = len(re.findall(r'^W\d+', output, re.MULTILINE))

        result.metrics.append(
            CIMetric("errors", error_count, "fail" if error_count > 0 else "pass")
        )
        result.metrics.append(
            CIMetric("warnings", warning_count, "warning" if warning_count > 0 else "pass")
        )

        result.success = (error_count == 0)
        return result


class BuildParser:
    """Parser for build system output."""

    @staticmethod
    def parse(output: str) -> CIResult:
        result = CIResult(source="build", raw_output=output)

        success_indicators = ['Build succeeded', 'BUILD SUCCESSFUL', 'Build OK']
        fail_indicators = ['Build failed', 'BUILD FAILED', 'Error:', 'error:']

        has_success = any(ind in output for ind in success_indicators)
        has_failure = any(ind in output for ind in fail_indicators)

        result.success = has_success and not has_failure
        result.metrics.append(
            CIMetric("build_status", "success" if result.success else "failed",
                     "pass" if result.success else "fail")
        )

        return result


class CIFeedbackAdapter:
    """
    Main adapter that reads CI results and generates dispatch context.

    Usage:
        adapter = CIFeedbackAdapter()

        ci_result = adapter.parse_ci_output(pytest_output, "pytest")
        context = adapter.generate_context([ci_result])
        injection = context.to_prompt_injection()
    """

    PARSERS = {
        "pytest": PytestParser,
        "coverage": CoverageParser,
        "lint": LintParser,
        "build": BuildParser,
    }

    QUALITY_GATE_THRESHOLDS = {
        "test_pass_rate": 100.0,  # All tests must pass
        "min_coverage": 80.0,     # Minimum coverage percentage
        "zero_lint_errors": True,  # No lint errors allowed
        "build_success": True,    # Build must succeed
    }

    def __init__(self, strict_mode: bool = False):
        self._strict_mode = strict_mode

    def parse_ci_output(self, output: str, source_type: str) -> Optional[CIResult]:
        """
        Parse CI output based on source type.

        Args:
            output: Raw CI output text
            source_type: One of "pytest", "coverage", "lint", "build"

        Returns:
            Parsed CIResult or None if parsing fails
        """
        parser_cls = self.PARSERS.get(source_type.lower())
        if parser_cls is None:
            logger.warning("Unknown CI source type: %s", source_type)
            return None

        try:
            return parser_cls.parse(output)
        except Exception as e:
            logger.error("Failed to parse %s output: %s", source_type, e)
            return None

    def generate_context(self, results: List[CIResult]) -> CIContext:
        """
        Generate structured context from multiple CI results.

        Args:
            results: List of CIResult objects from different sources

        Returns:
            CIContext ready for prompt injection
        """
        if not results:
            return CIContext(
                overall_status="no_ci_data",
                summary="No CI data available. Run tests before proceeding.",
            )

        all_pass = all(r.success for r in results)
        any_fail = any(r.has_failures() for r in results)

        context = CIContext(
            overall_status="all_pass" if all_pass else "has_failures",
            summary=self._build_summary(results),
        )

        context.quality_gates["all_tests_pass"] = all(
            not r.has_failures() for r in results if r.source == "pytest"
        ) or not any(r.source == "pytest" for r in results)
        context.quality_gates["build_succeeds"] = all(
            r.success for r in results if r.source == "build"
        ) or not any(r.source == "build" for r in results)
        context.quality_gates["no_critical_errors"] = not any_fail

        context.actionable_items = self._extract_action_items(results)
        context.recommendations = self._generate_recommendations(results)

        return context

    def _build_summary(self, results: List[CIResult]) -> str:
        summaries = [r.to_summary() for r in results]
        return "\n".join(summaries)

    def _extract_action_items(self, results: List[CIResult]) -> List[Dict[str, Any]]:
        items = []
        for r in results:
            for m in r.metrics:
                if m.status == "fail":
                    items.append({
                        "severity": "critical",
                        "source": r.source,
                        "metric": m.name,
                        "message": f"{m.name} failed: {m.details or m.value}",
                    })
                elif m.status == "warning":
                    items.append({
                        "severity": "warning",
                        "source": r.source,
                        "metric": m.name,
                        "message": f"{m.name} warning: {m.details or m.value}",
                    })
        return sorted(items, key=lambda x: {"critical": 0, "warning": 1}.get(x["severity"], 2))

    def _generate_recommendations(self, results: List[CIResult]) -> List[str]:
        recs = []
        for r in results:
            if r.has_failures():
                recs.append(f"Fix failing tests/checks in {r.source} before proceeding")
            if r.source == "coverage":
                cov = r.get_metric("coverage_percentage")
                if cov and cov.status != "pass":
                    recs.append(f"Increase code coverage (current: {cov.value})")

        if not recs:
            recs.append("All CI checks passed. Safe to proceed.")
        return recs


def create_default_adapter() -> CIFeedbackAdapter:
    """Create adapter with default settings."""
    return CIFeedbackAdapter()


def create_strict_adapter() -> CIFeedbackAdapter:
    """Create adapter in strict mode."""
    return CIFeedbackAdapter(strict_mode=True)
