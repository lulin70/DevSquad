#!/usr/bin/env python3
"""
VerificationGate - Hardened verification requirements for TaskCompletionChecker

Enforces Agent Skills' principle: "Seems right" is NEVER sufficient.
Every completion claim must have supporting evidence.

Integration point: Called by TaskCompletionChecker.check_dispatch_result()
to validate Worker output quality before accepting completion claims.

Spec reference: SPEC_V35_Agent_Skills_Quality_Framework.md Section 6.2
"""

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

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
    required_for: list[str] | None = None
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
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class GateResult:
    """Result of running VerificationGate against a CompletionContext."""

    passed: bool
    red_flags: list[RedFlag] = field(default_factory=list)
    missing_evidence: list[EvidenceItem] = field(default_factory=list)
    verdict: str = "APPROVE"


@dataclass
class RedCapableResult:
    """Result of Matt Pocock's red-capable gate check (P0-4).

    A debugging command is "red-capable" if it meets all 4 criteria:
    1. on-red-capable — can produce a failing (RED) result
    2. on-deterministic — same input always gives same output
    3. on-fast — completes quickly (no long sleeps/loops)
    4. on-agent-runnable — an AI agent can execute without human input

    Attributes:
        passed: True if all 4 criteria are satisfied.
        failed_criteria: List of criterion names that failed (subset of
            {"on-red-capable", "on-deterministic", "on-fast", "on-agent-runnable"}).
        reasoning: Human-readable explanation of the verdict.
        command: The command string that was evaluated.
    """

    passed: bool
    failed_criteria: list[str] = field(default_factory=list)
    reasoning: str = ""
    command: str = ""


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

    RED_FLAGS: list[RedFlag] = [
        RedFlag(
            id="no_test_for_new_behavior",
            severity="critical",
            description="Worker produced code changes without corresponding tests",
            detection=lambda ctx: ctx.has_code_changes and not ctx.has_test_changes,
        ),
        RedFlag(
            id="tests_pass_first_run",
            severity="warning",
            description=("Tests pass on first run — may not be testing intended behavior"),
            detection=lambda ctx: ctx.test_run_count == 1 and ctx.all_passed and ctx.has_test_changes,
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
            description=("Single Worker output exceeds 100 lines without slicing"),
            detection=lambda ctx: ctx.output_lines > 100 and not ctx.was_sliced,
        ),
        RedFlag(
            id="no_evidence_provided",
            severity="critical",
            description="Worker claims completion without providing evidence",
            detection=lambda ctx: ctx.claims_complete and len(ctx.evidence) == 0,
        ),
    ]

    MANDATORY_EVIDENCE: list[EvidenceItem] = [
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
            format_hint=('e.g., "Modified: dispatcher.py (+23/-5), Added: ar_engine.py (+89)"'),
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
                        flag.id,
                        flag.description,
                        context.role_id,
                    )
            except Exception as e:  # Broad catch: wraps arbitrary detection callables; must not crash gate
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

    def _check_missing_evidence(self, context: CompletionContext) -> list[EvidenceItem]:
        """Check which mandatory evidence items are missing."""
        missing = []
        for item in self.MANDATORY_EVIDENCE:
            if (item.required or item.required_for and context.role_id in item.required_for) and item.key not in context.evidence:
                missing.append(item)
        return missing

    # ------------------------------------------------------------------
    # Module 7 (Matt P0-4): Red-capable gate
    # ------------------------------------------------------------------

    # Patterns that indicate non-deterministic behavior.
    _NON_DETERMINISTIC_PATTERNS: list[str] = [
        r"\brandom\b",
        r"\brandom\.",
        r"\btime\.time\b",
        r"\bdatetime\.now\b",
        r"\bdatetime\.utcnow\b",
        r"\brequests\.",
        r"\burllib\b",
        r"\bhttpx\b",
        r"\baiohttp\b",
        r"\bsocket\b",
        r"\buuid\.uuid4\b",
        r"\bos\.urandom\b",
    ]

    # Patterns that indicate slow execution.
    _SLOW_PATTERNS: list[str] = [
        r"\btime\.sleep\b",
        r"\basyncio\.sleep\b",
        r"\bwhile\s+True\b",
        r"\bfor\s+\w+\s+in\s+range\s*\(\s*\d{4,}\s*\)",  # range(1000+)
    ]

    # Patterns that indicate interactive (non-agent-runnable) commands.
    _INTERACTIVE_PATTERNS: list[str] = [
        r"\binput\s*\(",
        r"\bbreakpoint\s*\(",
        r"\bpdb\b",
        r"\bipdb\b",
        r"\bpudb\b",
        r"\b--interactive\b",
        r"\bpython\s+-i\b",
    ]

    def verify_debug_loop_ready(self, command: str) -> RedCapableResult:
        """Check if a debugging command meets Matt Pocock's red-capable criteria.

        Phase 1 of Matt's debugging methodology: before investigating,
        ensure the feedback loop is red-capable. A command that cannot
        produce a RED (failing) result is useless for debugging.

        The 4 criteria:
        1. **on-red-capable** — command can fail (not a tautology)
        2. **on-deterministic** — same input → same output (no random/network)
        3. **on-fast** — completes quickly (no sleep/infinite loops)
        4. **on-agent-runnable** — executable by an AI agent (no interactive input)

        Args:
            command: The debugging command or code string to evaluate.

        Returns:
            RedCapableResult with pass/fail status and reasoning.
        """
        if not command or not command.strip():
            return RedCapableResult(
                passed=False,
                failed_criteria=["on-red-capable", "on-deterministic", "on-fast", "on-agent-runnable"],
                reasoning="Empty command cannot satisfy any criterion",
                command=command,
            )

        failed: list[str] = []
        reasoning_parts: list[str] = []

        if not self._is_red_capable(command):
            failed.append("on-red-capable")
            reasoning_parts.append("command cannot produce a failing result (tautological or assignment-only)")

        if not self._is_deterministic(command):
            failed.append("on-deterministic")
            reasoning_parts.append("command uses non-deterministic elements (random/time/network)")

        if not self._is_fast(command):
            failed.append("on-fast")
            reasoning_parts.append("command appears slow (sleep/long loops)")

        if not self._is_agent_runnable(command):
            failed.append("on-agent-runnable")
            reasoning_parts.append("command requires interactive input")

        passed = len(failed) == 0
        reasoning = "; ".join(reasoning_parts) if reasoning_parts else "All 4 red-capable criteria satisfied"

        return RedCapableResult(
            passed=passed,
            failed_criteria=failed,
            reasoning=reasoning,
            command=command,
        )

    def _is_red_capable(self, command: str) -> bool:
        """Check if the command can produce a failing (RED) result.

        A command is red-capable if it contains some form of assertion,
        comparison, or test — not just an assignment or echo.
        """
        cmd = command.lower()
        # Red-capable indicators: assertions, tests, comparisons, exits
        red_indicators = [
            "assert",
            "test",
            "pytest",
            "unittest",
            "==",
            "!=",
            "exit(",
            "sys.exit",
            "raise",
            "if ",
            "expect",
            "should",
            "match",
            "grep",
            "diff",
        ]
        return any(ind in cmd for ind in red_indicators)

    def _is_deterministic(self, command: str) -> bool:
        """Check if the command is deterministic (no random/time/network)."""
        return all(not re.search(pattern, command) for pattern in self._NON_DETERMINISTIC_PATTERNS)

    def _is_fast(self, command: str) -> bool:
        """Check if the command appears fast (no sleep/long loops)."""
        return all(not re.search(pattern, command) for pattern in self._SLOW_PATTERNS)

    def _is_agent_runnable(self, command: str) -> bool:
        """Check if the command is agent-runnable (no interactive input)."""
        return all(not re.search(pattern, command) for pattern in self._INTERACTIVE_PATTERNS)

    def build_context_from_worker_result(self, worker_result: dict[str, Any]) -> CompletionContext:
        """
        Build CompletionContext from a raw worker result dict.

        Extracts available fields heuristically from worker result structure.

        Args:
            worker_result: Dict from DispatchResult.worker_results

        Returns:
            Populated CompletionContext
        """
        role_id = worker_result.get("role_id", worker_result.get("role", "unknown"))
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
    def _is_likely_bug_fix(worker_result: dict[str, Any]) -> bool:
        """Heuristically determine if this looks like a bug fix task."""
        task_desc = str(worker_result.get("task_description", "") or worker_result.get("original_task", "")).lower()
        bug_keywords = [
            "fix",
            "bug",
            "error",
            "fail",
            "crash",
            "broken",
            "修复",
            "错误",
            "失败",
            "崩溃",
            "异常",
        ]
        return any(kw in task_desc for kw in bug_keywords)

    def get_red_flag_by_id(self, flag_id: str) -> RedFlag | None:
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


_shared_verification_gate_instance: VerificationGate | None = None


def get_shared_gate(strict_mode: bool = True) -> VerificationGate:
    """
    Get or create shared singleton instance.

    Args:
        strict_mode: If True, critical flags block approval

    Returns:
        Shared VerificationGate instance
    """
    global _shared_verification_gate_instance
    if _shared_verification_gate_instance is None:
        _shared_verification_gate_instance = VerificationGate(strict_mode=strict_mode)
    return _shared_verification_gate_instance
