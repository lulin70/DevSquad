#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VerificationGate - Hardened verification requirements for TaskCompletionChecker

Enforces Agent Skills' principle: "Seems right" is NEVER sufficient.
Every completion claim must have supporting evidence.

Integration point: Called by TaskCompletionChecker.check_dispatch_result()
to validate Worker output quality before accepting completion claims.

Spec reference: SPEC_V35_Agent_Skills_Quality_Framework.md Section 6.2
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class RedFlag:
    """A warning signal indicating something may be wrong with Worker output."""
    id: str
    severity: str  # "critical" / "warning" / "info"
    description: str
    detection: Callable[[Any], bool]


@dataclass
class EvidenceItem:
    """A piece of evidence that a Worker should provide to prove completion."""
    key: str
    required: bool = False
    required_for: Optional[List[str]] = None
    description: str = ""
    format_hint: str = ""


@dataclass
class CompletionContext:
    """Context data extracted from a Worker's result for gate evaluation."""
    role_id: str
    has_code_changes: bool = False
    has_test_changes: bool = False
    is_bug_fix: bool = False
    has_repro_test: bool = False
    test_run_count: int = 0
    all_passed: bool = False
    tests_skipped: int = 0
    coverage_delta: float = 0.0
    output_lines: int = 0
    was_sliced: bool = False
    claims_complete: bool = False
    evidence: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GateResult:
    """Result of running VerificationGate against a CompletionContext."""
    passed: bool
    red_flags: List[RedFlag] = field(default_factory=list)
    missing_evidence: List[EvidenceItem] = field(default_factory=list)
    verdict: str = "APPROVE"


class VerificationGate:
    """
    Hardened verification requirements for TaskCompletionChecker.

    Enforces mandatory evidence requirements and detects Red Flags that
    indicate problems with Worker output quality.

    Design borrowed from Agent Skills (addyosmani/agent-skills):
      - Every skill ends with mandatory evidence checklist
      - Red Flags provide early warning signals
      - "Seems right" is NEVER sufficient as acceptance criteria
    """

    RED_FLAGS: List[RedFlag] = [
        RedFlag(
            id="no_test_for_new_behavior",
            severity="critical",
            description="Worker produced code changes without corresponding tests",
            detection=lambda ctx: ctx.has_code_changes and not ctx.has_test_changes,
        ),
        RedFlag(
            id="tests_pass_first_run",
            severity="warning",
            description=(
                "Tests pass on first run — may not be testing intended behavior"
            ),
            detection=lambda ctx: (
                ctx.test_run_count == 1 and ctx.all_passed and ctx.has_test_changes
            ),
        ),
        RedFlag(
            id="no_regression_test_for_bugfix",
            severity="critical",
            description="Bug fix task without failing reproduction test",
            detection=lambda ctx: ctx.is_bug_fix and not ctx.has_repro_test,
        ),
        RedFlag(
            id="tests_skipped_or_disabled",
            severity="critical",
            description="Tests were skipped or disabled to make suite pass",
            detection=lambda ctx: ctx.tests_skipped > 0,
        ),
        RedFlag(
            id="coverage_decreased",
            severity="warning",
            description="Code coverage decreased from baseline",
            detection=lambda ctx: ctx.coverage_delta < -0.01,
        ),
        RedFlag(
            id="output_exceeds_limit",
            severity="warning",
            description=(
                "Single Worker output exceeds 100 lines without slicing"
            ),
            detection=lambda ctx: ctx.output_lines > 100 and not ctx.was_sliced,
        ),
        RedFlag(
            id="no_evidence_provided",
            severity="critical",
            description="Worker claims completion without providing evidence",
            detection=lambda ctx: (
                ctx.claims_complete and len(ctx.evidence) == 0
            ),
        ),
    ]

    MANDATORY_EVIDENCE: List[EvidenceItem] = [
        EvidenceItem(
            key="test_results",
            required=True,
            description="Test execution output showing pass/fail status",
            format_hint='e.g., "pytest: 142 passed, 0 failed in 3.2s"',
        ),
        EvidenceItem(
            key="build_status",
            required_for=["architect", "solo-coder"],
            description="Build success/failure with output",
            format_hint='e.g., "Build succeeded in 1.2s"',
        ),
        EvidenceItem(
            key="diff_summary",
            required=True,
            description="Summary of changes made (files affected, lines changed)",
            format_hint=(
                'e.g., "Modified: dispatcher.py (+23/-5), '
                'Added: ar_engine.py (+89)"'
            ),
        ),
    ]

    def __init__(self, strict_mode: bool = True):
        """
        Initialize VerificationGate.

        Args:
            strict_mode: If True, any critical flag or missing evidence blocks
                        approval. If False, only logs warnings.
        """
        self.strict_mode = strict_mode

    def check(self, context: CompletionContext) -> GateResult:
        """
        Run verification gate against completion context.

        Args:
            context: CompletionContext with Worker result data

        Returns:
            GateResult with passed status, triggered flags,
            missing evidence, and verdict
        """
        triggered_flags = []
        for flag in self.RED_FLAGS:
            try:
                if flag.detection(context):
                    triggered_flags.append(flag)
                    logger.warning(
                        "Red Flag [%s]: %s (role=%s)",
                        flag.id, flag.description, context.role_id,
                    )
            except Exception as e:
                logger.debug("Red flag detection error for %s: %s", flag.id, e)

        missing = self._check_missing_evidence(context)

        critical_flags = [f for f in triggered_flags if f.severity == "critical"]
        critical_missing = [e for e in missing if e.required]

        if critical_flags or critical_missing:
            verdict = "REJECT"
        elif triggered_flags or missing:
            verdict = "CONDITIONAL"
        else:
            verdict = "APPROVE"

        return GateResult(
            passed=(verdict == "APPROVE"),
            red_flags=triggered_flags,
            missing_evidence=missing,
            verdict=verdict,
        )

    def _check_missing_evidence(self, context: CompletionContext) -> List[EvidenceItem]:
        """Check which mandatory evidence items are missing."""
        missing = []
        for item in self.MANDATORY_EVIDENCE:
            if item.required:
                if item.key not in context.evidence:
                    missing.append(item)
            elif item.required_for:
                if context.role_id in item.required_for:
                    if item.key not in context.evidence:
                        missing.append(item)
        return missing

    def build_context_from_worker_result(
        self, worker_result: Dict[str, Any]
    ) -> CompletionContext:
        """
        Build CompletionContext from a raw worker result dict.

        Extracts available fields heuristically from worker result structure.

        Args:
            worker_result: Dict from DispatchResult.worker_results

        Returns:
            Populated CompletionContext
        """
        role_id = worker_result.get(
            "role_id", worker_result.get("role", "unknown")
        )
        output = str(worker_result.get("output", ""))
        success = worker_result.get("success", False)
        errors = worker_result.get("errors", [])

        output_lines = len(output.split("\n")) if output else 0

        evidence = {}
        verification = worker_result.get("verification")
        if isinstance(verification, dict) and verification.get("passed"):
            evidence["verification"] = verification

        return CompletionContext(
            role_id=role_id,
            has_code_changes=output_lines > 10 and success,
            has_test_changes="test" in output.lower()[:500],
            is_bug_fix=self._is_likely_bug_fix(worker_result),
            has_repro_test="reproduce" in output.lower() or "test_" in output.lower(),
            test_run_count=1 if "test" in output.lower() else 0,
            all_passed=success and not errors,
            tests_skipped=worker_result.get("tests_skipped", 0),
            coverage_delta=0.0,
            output_lines=output_lines,
            was_sliced=worker_result.get("was_sliced", False),
            claims_complete=success,
            evidence=evidence,
        )

    @staticmethod
    def _is_likely_bug_fix(worker_result: Dict[str, Any]) -> bool:
        """Heuristically determine if this looks like a bug fix task."""
        task_desc = str(
            worker_result.get("task_description", "")
            or worker_result.get("original_task", "")
        ).lower()
        bug_keywords = [
            "fix", "bug", "error", "fail", "crash", "broken",
            "修复", "错误", "失败", "崩溃", "异常",
        ]
        return any(kw in task_desc for kw in bug_keywords)

    def get_red_flag_by_id(self, flag_id: str) -> Optional[RedFlag]:
        """Look up a specific RedFlag by ID."""
        for flag in self.RED_FLAGS:
            if flag.id == flag_id:
                return flag
        return None

    @property
    def red_flag_count(self) -> int:
        """Total number of defined Red Flags."""
        return len(self.RED_FLAGS)

    @property
    def evidence_item_count(self) -> int:
        """Total number of defined EvidenceItems."""
        return len(self.MANDATORY_EVIDENCE)


def get_shared_gate(strict_mode: bool = True) -> VerificationGate:
    """
    Get or create shared singleton instance.

    Args:
        strict_mode: If True, critical flags block approval

    Returns:
        Shared VerificationGate instance
    """
    if not hasattr(get_shared_gate, "_instance"):
        get_shared_gate._instance = VerificationGate(
            strict_mode=strict_mode
        )
    return get_shared_gate._instance
