#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UnifiedGateEngine - Unified gate engine for layered architecture (Plan C)

Integrates:
  - VerificationGate: Worker output quality validation
  - LifecycleProtocol: Phase transition gates
  - CheckpointManager: State persistence

Provides single entry point for all gate checks in DevSquad.

Spec reference: docs/spec/SPEC_Lifecycle_Unified_Architecture_C.md
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable

logger = logging.getLogger(__name__)


class GateType(Enum):
    """Types of gates in the unified system."""
    PHASE_TRANSITION = "phase_transition"
    WORKER_OUTPUT = "worker_output"
    QUALITY_THRESHOLD = "quality_threshold"
    SECURITY_CHECK = "security_check"
    COMPLIANCE_CHECK = "compliance_check"


class GateSeverity(Enum):
    """Severity levels for gate results."""
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


@dataclass
class UnifiedGateConfig:
    """Configuration for unified gate engine."""
    strict_mode: bool = True
    enable_verification_gate: bool = True
    enable_phase_gate: bool = True
    enable_security_scan: bool = False
    enable_compliance_check: bool = False
    max_output_lines: int = 100
    min_test_coverage: float = 0.8
    allowed_critical_flags: int = 0
    auto_fix_warnings: bool = False


@dataclass
class UnifiedGateResult:
    """Result from unified gate engine check."""
    passed: bool
    gate_type: GateType
    verdict: str  # APPROVE / CONDITIONAL / REJECT
    severity: GateSeverity
    checks_run: int = 0
    checks_passed: int = 0
    critical_issues: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[Dict[str, Any]] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    evidence_required: List[str] = field(default_factory=list)
    execution_time_ms: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "gate_type": self.gate_type.value,
            "verdict": self.verdict,
            "severity": self.severity.value,
            "checks_run": self.checks_run,
            "checks_passed": self.checks_passed,
            "critical_issues_count": len(self.critical_issues),
            "warnings_count": len(self.warnings),
            "evidence_required_count": len(self.evidence_required),
        }

    def to_summary(self) -> str:
        lines = [
            f"Gate Result [{self.gate_type.value}]: {self.verdict}",
            f"Status: {'✅ PASSED' if self.passed else '❌ FAILED'}",
            f"Checks: {self.checks_passed}/{self.checks_run}",
        ]
        if self.critical_issues:
            lines.append(f"Critical Issues: {len(self.critical_issues)}")
        if self.warnings:
            lines.append(f"Warnings: {len(self.warnings)}")
        if self.evidence_required:
            lines.append(f"Evidence Required: {', '.join(self.evidence_required[:3])}")
        return "\n".join(lines)


@dataclass
class PhaseGateContext:
    """Context for phase transition gate check."""
    phase_id: str
    phase_name: str
    current_state: str
    target_state: str
    dependencies_met: bool = False
    completed_phases: List[str] = field(default_factory=list)
    artifacts_available: Dict[str, bool] = field(default_factory=dict)
    reviewers_approved: List[str] = field(default_factory=list)
    custom_conditions: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkerOutputContext:
    """Context for worker output quality gate check."""
    role_id: str
    task_description: str
    output: str
    has_code_changes: bool = False
    has_test_changes: bool = False
    test_results: Optional[Dict[str, Any]] = None
    build_status: Optional[Dict[str, Any]] = None
    diff_summary: Optional[Dict[str, Any]] = None
    coverage_delta: float = 0.0
    claims_complete: bool = False


class UnifiedGateEngine:
    """
    Unified gate engine for DevSquad layered architecture.

    Responsibilities:
    1. Phase transition validation (lifecycle protocol)
    2. Worker output quality verification (verification gate)
    3. Security and compliance checks (optional)
    4. Evidence collection and validation
    5. Integration with checkpoint manager for state persistence

    Design Principles:
    - Single entry point for all gate checks
    - Pluggable checkers for different gate types
    - Configurable strictness levels
    - Comprehensive result reporting
    """

    def __init__(self, config: Optional[UnifiedGateConfig] = None):
        """
        Initialize unified gate engine.

        Args:
            config: Configuration for gate behavior
        """
        self.config = config or UnifiedGateConfig()
        self._checkers: Dict[GateType, Callable] = {
            GateType.PHASE_TRANSITION: self._check_phase_transition,
            GateType.WORKER_OUTPUT: self._check_worker_output,
        }
        self._custom_checkers: Dict[GateType, List[Callable]] = {}
        self._statistics: Dict[str, int] = {
            "total_checks": 0,
            "passed": 0,
            "failed": 0,
            "conditional": 0,
        }

    def register_checker(
        self,
        gate_type: GateType,
        checker: Callable,
        prepend: bool = False,
    ) -> None:
        """
        Register a custom checker for a gate type.

        Args:
            gate_type: Type of gate this checker handles
            checker: Callable that takes context and returns partial result
            prepend: If True, add to front of checker list
        """
        if gate_type not in self._custom_checkers:
            self._custom_checkers[gate_type] = []

        if prepend:
            self._custom_checkers[gate_type].insert(0, checker)
        else:
            self._custom_checkers[gate_type].append(checker)

        logger.debug("Registered custom checker for %s", gate_type.value)

    def check(
        self,
        gate_type: GateType,
        context: Any,
        **kwargs,
    ) -> UnifiedGateResult:
        """
        Run unified gate check.

        Args:
            gate_type: Type of gate to check
            context: Context data (PhaseGateContext or WorkerOutputContext)
            **kwargs: Additional parameters

        Returns:
            UnifiedGateResult with comprehensive check results
        """
        start_time = datetime.now()
        self._statistics["total_checks"] += 1

        logger.info(
            "Running %s gate check (strict=%s)",
            gate_type.value,
            self.config.strict_mode,
        )

        try:
            base_checker = self._checkers.get(gate_type)
            if not base_checker:
                return UnifiedGateResult(
                    passed=False,
                    gate_type=gate_type,
                    verdict="REJECT",
                    severity=GateSeverity.CRITICAL,
                    critical_issues=[{
                        "code": "UNKNOWN_GATE_TYPE",
                        "message": f"No checker registered for {gate_type.value}",
                    }],
                )

            result = base_checker(context, **kwargs)

            # Run custom checkers if any
            custom_results = []
            for checker in self._custom_checkers.get(gate_type, []):
                try:
                    custom_result = checker(context, **kwargs)
                    if isinstance(custom_result, dict):
                        custom_results.append(custom_result)
                except Exception as e:
                    logger.warning("Custom checker error: %s", e)

            # Merge custom results
            if custom_results:
                self._merge_custom_results(result, custom_results)

            # Update statistics
            elapsed = (datetime.now() - start_time).total_seconds() * 1000
            result.execution_time_ms = elapsed

            if result.passed:
                self._statistics["passed"] += 1
            elif result.verdict == "CONDITIONAL":
                self._statistics["conditional"] += 1
            else:
                self._statistics["failed"] += 1

            logger.info(
                "Gate %s completed: %s (%d issues)",
                gate_type.value,
                result.verdict,
                len(result.critical_issues),
            )

            return result

        except Exception as e:
            logger.error("Gate check failed with exception: %s", e)
            return UnifiedGateResult(
                passed=False,
                gate_type=gate_type,
                verdict="REJECT",
                severity=GateSeverity.CRITICAL,
                critical_issues=[{
                    "code": "GATE_EXCEPTION",
                    "message": f"Gate check exception: {str(e)[:200]}",
                }],
                execution_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
            )

    def _merge_custom_results(
        self,
        result: UnifiedGateResult,
        custom_results: List[Dict[str, Any]],
    ) -> None:
        """Merge custom checker results into main result."""
        for custom in custom_results:
            if custom.get("critical_issues"):
                result.critical_issues.extend(custom["critical_issues"])
            if custom.get("warnings"):
                result.warnings.extend(custom["warnings"])
            if custom.get("suggestions"):
                result.suggestions.extend(custom["suggestions"])
            if custom.get("evidence_required"):
                result.evidence_required.extend(custom["evidence_required"])

        # Recalculate verdict based on merged results
        if result.critical_issues:
            result.passed = False
            result.verdict = "REJECT"
            result.severity = GateSeverity.CRITICAL
        elif result.warnings or not result.evidence_required:
            result.verdict = "CONDITIONAL"
            result.severity = GateSeverity.WARNING

    def _check_phase_transition(
        self,
        context: PhaseGateContext,
        **kwargs,
    ) -> UnifiedGateResult:
        """
        Check phase transition gate conditions.

        Validates:
        1. Dependencies are met
        2. Required artifacts are available
        3. Reviewer approvals (if required)
        4. Custom phase conditions
        """
        checks_run = 0
        checks_passed = 0
        critical_issues = []
        warnings = []
        evidence_required = []

        # Check 1: Dependencies
        checks_run += 1
        if context.dependencies_met:
            checks_passed += 1
        else:
            missing_deps = [
                d for d in getattr(context, 'unmet_dependencies', [])
            ]
            if missing_deps:
                critical_issues.append({
                    "code": "UNMET_DEPENDENCIES",
                    "message": f"Unmet dependencies: {', '.join(missing_deps)}",
                    "dependencies": missing_deps,
                })
            else:
                warnings.append({
                    "code": "DEPENDENCY_CHECK_SKIPPED",
                    "message": "Dependency status unknown",
                })

        # Check 2: Artifacts
        checks_run += 1
        if context.artifacts_available:
            missing_artifacts = [
                k for k, v in context.artifacts_available.items() if not v
            ]
            if not missing_artifacts:
                checks_passed += 1
            else:
                evidence_required.extend(missing_artifacts)
                warnings.append({
                    "code": "MISSING_ARTIFACTS",
                    "message": f"Missing artifacts: {', '.join(missing_artifacts)}",
                    "artifacts": missing_artifacts,
                })
        else:
            checks_passed += 1  # No artifacts required

        # Check 3: Reviewer approvals (if phase requires it)
        if context.reviewers_approved is not None:
            checks_run += 1
            if len(context.reviewers_approved) >= 1:
                checks_passed += 1
            else:
                warnings.append({
                    "code": "NO_REVIEWER_APPROVAL",
                    "message": "No reviewer approvals yet",
                })

        # Determine verdict
        passed = len(critical_issues) == 0
        if critical_issues:
            verdict = "REJECT"
            severity = GateSeverity.CRITICAL
        elif warnings or evidence_required:
            verdict = "CONDITIONAL"
            severity = GateSeverity.WARNING
        else:
            verdict = "APPROVE"
            severity = GateSeverity.INFO

        return UnifiedGateResult(
            passed=passed,
            gate_type=GateType.PHASE_TRANSITION,
            verdict=verdict,
            severity=severity,
            checks_run=checks_run,
            checks_passed=checks_passed,
            critical_issues=critical_issues,
            warnings=warnings,
            evidence_required=evidence_required,
        )

    def _check_worker_output(
        self,
        context: WorkerOutputContext,
        **kwargs,
    ) -> UnifiedGateResult:
        """
        Check worker output quality using VerificationGate logic.

        Validates:
        1. Code changes have corresponding tests
        2. Bug fixes have reproduction tests
        3. No tests skipped/disabled
        4. Coverage didn't decrease significantly
        5. Output size within limits
        6. Required evidence provided
        """
        checks_run = 0
        checks_passed = 0
        critical_issues = []
        warnings = []
        evidence_required = []

        # Import VerificationGate if available
        try:
            from scripts.collaboration.verification_gate import (
                VerificationGate,
                get_shared_gate,
            )
            vg = get_shared_gate(strict_mode=self.config.strict_mode)

            from scripts.collaboration.verification_gate import CompletionContext
            vg_context = CompletionContext(
                role_id=context.role_id,
                has_code_changes=context.has_code_changes,
                has_test_changes=context.has_test_changes,
                is_bug_fix=self._is_likely_bug_fix(context.task_description),
                test_run_count=1 if context.test_results else 0,
                all_passed=context.test_results.get("all_passed", False) if context.test_results else False,
                tests_skipped=context.test_results.get("skipped", 0) if context.test_results else 0,
                coverage_delta=context.coverage_delta,
                output_lines=len(context.output.split("\n")) if context.output else 0,
                was_sliced=len(context.output.split("\n")) > self.config.max_output_lines if context.output else False,
                claims_complete=context.claims_complete,
                evidence=self._extract_evidence(context),
            )

            vg_result = vg.check(vg_context)

            # Convert VerificationGate result to UnifiedGateResult format
            if vg_result.red_flags:
                for flag in vg_result.red_flags:
                    issue = {
                        "code": flag.id,
                        "message": flag.description,
                        "severity": flag.severity,
                    }
                    if flag.severity == "critical":
                        critical_issues.append(issue)
                    else:
                        warnings.append(issue)

            if vg_result.missing_evidence:
                for item in vg_result.missing_evidence:
                    evidence_required.append(item.key)

            checks_run = vg.red_flag_count + vg.evidence_item_count
            checks_passed = checks_run - len(critical_issues) - len(warnings)

        except ImportError:
            logger.warning("VerificationGate not available, using basic checks")
            critical_issues, warnings, evidence_required, checks_run, checks_passed = \
                self._basic_worker_output_checks(context)

        # Determine verdict
        passed = len(critical_issues) <= self.config.allowed_critical_flags
        if critical_issues and not passed:
            verdict = "REJECT"
            severity = GateSeverity.CRITICAL
        elif warnings or evidence_required:
            verdict = "CONDITIONAL"
            severity = GateSeverity.WARNING
        else:
            verdict = "APPROVE"
            severity = GateSeverity.INFO

        return UnifiedGateResult(
            passed=passed,
            gate_type=GateType.WORKER_OUTPUT,
            verdict=verdict,
            severity=severity,
            checks_run=checks_run,
            checks_passed=checks_passed,
            critical_issues=critical_issues,
            warnings=warnings,
            evidence_required=evidence_required,
        )

    def _basic_worker_output_checks(
        self,
        context: WorkerOutputContext,
    ) -> tuple:
        """Basic fallback checks when VerificationGate is unavailable."""
        checks_run = 0
        checks_passed = 0
        critical_issues = []
        warnings = []
        evidence_required = []

        # Basic check: code without tests
        checks_run += 1
        if context.has_code_changes and not context.has_test_changes:
            critical_issues.append({
                "code": "no_test_for_new_behavior",
                "message": "Code changes without corresponding tests",
            })
        else:
            checks_passed += 1

        # Basic check: output size
        checks_run += 1
        output_lines = len(context.output.split("\n")) if context.output else 0
        if output_lines > self.config.max_output_lines:
            warnings.append({
                "code": "output_exceeds_limit",
                "message": f"Output ({output_lines} lines) exceeds limit ({self.config.max_output_lines})",
            })
        else:
            checks_passed += 1

        # Basic check: evidence
        checks_run += 1
        if context.claims_complete and not context.test_results:
            evidence_required.append("test_results")
            evidence_required.append("build_status")
        else:
            checks_passed += 1

        return critical_issues, warnings, evidence_required, checks_run, checks_passed

    @staticmethod
    def _is_likely_bug_fix(task_description: str) -> bool:
        """Heuristically determine if task looks like a bug fix."""
        bug_keywords = [
            "fix", "bug", "error", "fail", "crash", "broken",
            "修复", "错误", "失败", "崩溃", "异常",
        ]
        return any(kw in task_description.lower() for kw in bug_keywords)

    @staticmethod
    def _extract_evidence(context: WorkerOutputContext) -> Dict[str, Any]:
        """Extract evidence from worker output context."""
        evidence = {}
        if context.test_results:
            evidence["test_results"] = context.test_results
        if context.build_status:
            evidence["build_status"] = context.build_status
        if context.diff_summary:
            evidence["diff_summary"] = context.diff_summary
        return evidence

    def get_statistics(self) -> Dict[str, Any]:
        """Get gate engine statistics."""
        total = self._statistics["total_checks"]
        return {
            **self._statistics,
            "pass_rate": (
                (self._statistics["passed"] / total * 100)
                if total > 0
                else 0.0
            ),
            "custom_checkers_registered": sum(
                len(checkers)
                for checkers in self._custom_checkers.values()
            ),
        }

    def reset_statistics(self) -> None:
        """Reset statistics counters."""
        self._statistics = {
            "total_checks": 0,
            "passed": 0,
            "failed": 0,
            "conditional": 0,
        }


def get_shared_gate_engine(
    config: Optional[UnifiedGateConfig] = None,
) -> UnifiedGateEngine:
    """
    Get or create shared singleton instance of UnifiedGateEngine.

    Args:
        config: Optional configuration for the engine

    Returns:
        Shared UnifiedGateEngine instance
    """
    if not hasattr(get_shared_gate_engine, "_instance"):
        get_shared_gate_engine._instance = UnifiedGateEngine(config=config)
    return get_shared_gate_engine._instance
