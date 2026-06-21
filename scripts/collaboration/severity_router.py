#!/usr/bin/env python3
"""
SeverityRouter — V3.8 #3: Severity-based finding routing + auto-fix loop.

Receives findings from :class:`TwoStageReviewGate` (or any reviewer that
produces :class:`ReviewFinding` objects), classifies them by severity, and
routes them accordingly:

  - CRITICAL  → Block progression, require manual fix
  - HIGH      → Trigger auto-fix subtask (if auto_fixable)
  - MEDIUM    → Track, non-blocking
  - LOW       → Informational, non-blocking
  - INFO      → Informational only

The auto-fix loop runs up to ``max_rounds`` (default 3) times. After each
fix attempt, the caller may re-run the review and feed the new findings
back into the router. If findings remain after exhausting rounds, the
router escalates to manual handling.

Integration
-----------
Wired into :class:`PostDispatchPipeline` (dispatch_steps.py) after the
two-stage review gate. Findings from the review gate and worker outputs
are fed into the router, which produces a :class:`RoutingResult`
summarizing the routing decisions and fix attempts.

Usage::

    from scripts.collaboration.severity_router import SeverityRouter
    from scripts.collaboration.two_stage_review_gate import ReviewFinding, ReviewStage

    router = SeverityRouter(development_mode=True)
    findings = [
        ReviewFinding(ReviewStage.CODE_QUALITY, "critical", "security", "SQL injection"),
        ReviewFinding(ReviewStage.CODE_QUALITY, "warning", "style", "Long line"),
    ]
    result = router.route(findings, context={})
    if result.blocked:
        # CRITICAL findings present — progression blocked
        ...
    # Or run the full auto-fix loop
    result = router.run_fix_loop(findings, context={})
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .event_bus import EventBus
from .two_stage_review_gate import ReviewFinding

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SeverityLevel(Enum):
    """Finding severity levels (ordered from most to least severe)."""

    CRITICAL = "critical"  # Must fix immediately, blocks progression
    HIGH = "high"          # Should fix before merge, auto-fix triggered
    MEDIUM = "medium"      # Should fix, tracked but non-blocking
    LOW = "low"            # Nice to fix, informational
    INFO = "info"          # Informational only

    @classmethod
    def from_string(cls, value: str) -> SeverityLevel:
        """Parse a severity string, defaulting to MEDIUM."""
        normalized = (value or "").lower().strip()
        for member in cls:
            if member.value == normalized:
                return member
        # Common aliases
        if normalized in ("crit", "blocker", "p0", "p1"):
            return cls.CRITICAL
        if normalized in ("warn", "major", "p2", "warning"):
            return cls.HIGH
        if normalized in ("info", "minor", "p3", "p4"):
            return cls.LOW
        return cls.MEDIUM


# Backward-compatibility alias for the V3.8.0 enum name.
Severity = SeverityLevel


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class FixAction:
    """A single fix action derived from a finding.

    Attributes
    ----------
    finding_id:
        Unique identifier for the action (auto-generated when not provided).
    severity:
        The :class:`SeverityLevel` that triggered this action.
    description:
        Human-readable description of what needs to be fixed.
    file_path:
        File path the finding relates to (may be empty).
    suggested_fix:
        Suggested fix text (may be empty).
    auto_fixable:
        True if the router determined this finding can be auto-fixed.
    fix_applied:
        True if an auto-fix was applied (set by :meth:`_trigger_auto_fix`).
    fix_verified:
        True if the fix was verified (e.g. by re-running the review).
    """

    finding_id: str
    severity: SeverityLevel
    description: str
    file_path: str = ""
    suggested_fix: str = ""
    auto_fixable: bool = False
    fix_applied: bool = False
    fix_verified: bool = False

    def is_blocking(self) -> bool:
        """CRITICAL and HIGH findings block progression / trigger fix."""
        return self.severity in (SeverityLevel.CRITICAL, SeverityLevel.HIGH)

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "severity": self.severity.value,
            "description": self.description,
            "file_path": self.file_path,
            "suggested_fix": self.suggested_fix,
            "auto_fixable": self.auto_fixable,
            "fix_applied": self.fix_applied,
            "fix_verified": self.fix_verified,
        }


@dataclass
class RoutingResult:
    """Result of routing findings through the :class:`SeverityRouter`.

    Attributes
    ----------
    actions:
        All :class:`FixAction` objects produced from the findings.
    blocked:
        True if any CRITICAL findings were present (progression blocked).
    auto_fix_triggered:
        True if at least one auto-fix was attempted.
    fix_round:
        Current fix iteration (0 = initial routing, 1+ = auto-fix rounds).
    max_rounds:
        Maximum number of fix rounds configured.
    summary:
        Human-readable summary of the routing result.
    """

    actions: list[FixAction] = field(default_factory=list)
    blocked: bool = False
    auto_fix_triggered: bool = False
    fix_round: int = 0
    max_rounds: int = 3
    summary: str = ""

    @property
    def all_fixed(self) -> bool:
        """True when all blocking actions have been fixed and verified."""
        blocking = [a for a in self.actions if a.is_blocking()]
        if not blocking:
            return True
        return all(a.fix_applied and a.fix_verified for a in blocking)

    @property
    def remaining_issues(self) -> list[FixAction]:
        """Blocking actions that remain unfixed (backward-compat alias)."""
        return [a for a in self.actions if a.is_blocking() and not a.fix_applied]

    @property
    def fixes_applied(self) -> int:
        """Count of actions where a fix was applied."""
        return sum(1 for a in self.actions if a.fix_applied)

    @property
    def iterations(self) -> int:
        """Alias for :attr:`fix_round` (backward-compat)."""
        return self.fix_round

    @property
    def status(self) -> str:
        """Status string: ``success`` / ``partial`` / ``failed`` / ``skipped``."""
        if not self.actions:
            return "skipped"
        blocking = [a for a in self.actions if a.is_blocking()]
        if not blocking:
            return "success"
        if all(a.fix_applied and a.fix_verified for a in blocking):
            return "success"
        if any(a.fix_applied for a in blocking):
            return "partial"
        return "failed"

    def to_dict(self) -> dict[str, Any]:
        return {
            "actions": [a.to_dict() for a in self.actions],
            "blocked": self.blocked,
            "auto_fix_triggered": self.auto_fix_triggered,
            "fix_round": self.fix_round,
            "max_rounds": self.max_rounds,
            "summary": self.summary,
            # Backward-compat fields
            "all_fixed": self.all_fixed,
            "fixes_applied": self.fixes_applied,
            "iterations": self.iterations,
            "remaining_count": len(self.remaining_issues),
            "remaining_issues": [a.to_dict() for a in self.remaining_issues],
            "status": self.status,
            "findings_processed": [a.to_dict() for a in self.actions],
        }


# Backward-compatibility aliases for the V3.8.0 dataclass names.
Finding = FixAction
AutoFixResult = RoutingResult


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


class SeverityRouter:
    """Severity-based routing with auto-fix loop inspired by NodeGuard.

    Flow:
      1. Receive findings from TwoStageReviewGate or any reviewer.
      2. Classify by severity (CRITICAL/HIGH/MEDIUM/LOW/INFO).
      3. CRITICAL → Block progression, require manual fix.
      4. HIGH → Trigger auto-fix subtask (if auto_fixable).
      5. MEDIUM/LOW/INFO → Track, non-blocking.
      6. After auto-fix, re-run review (up to max_rounds).
      7. If still failing after max_rounds → escalate to manual.

    Parameters
    ----------
    event_bus:
        The :class:`EventBus` to subscribe to. A new instance is
        created when None.
    development_mode:
        When True (default), HIGH findings trigger the auto-fix loop.
        When False (production), the router only collects and logs
        findings — no automatic code changes.
    max_fix_iterations:
        Maximum number of fix attempts (default 3). Alias for
        ``max_rounds``.
    max_rounds:
        Maximum number of fix rounds (default 3).
    auto_fix_callable:
        Optional callable invoked to apply a fix. Signature:
        ``(action: FixAction, context: dict) -> bool``. Returns True
        when the fix was applied successfully.
    """

    EVENT_FINDINGS = "severity_router.findings"

    # Categories that are considered auto-fixable (HIGH severity only).
    _AUTO_FIXABLE_CATEGORIES: frozenset[str] = frozenset(
        {
            "anti_pattern_bare_except",
            "anti_pattern_todo_left",
            "anti_pattern_print_debug",
            "missing_docstring",
            "oversized_output",
            "test_coverage_gap",
            "bare_except",
        }
    )

    def __init__(
        self,
        event_bus: EventBus | None = None,
        development_mode: bool = True,
        max_fix_iterations: int = 3,
        *,
        max_rounds: int | None = None,
        auto_fix_callable: Callable[[FixAction, dict[str, Any]], bool] | None = None,
    ) -> None:
        self.event_bus = event_bus or EventBus()
        self.development_mode = development_mode
        # max_rounds takes precedence when explicitly provided.
        self.max_rounds = max_rounds if max_rounds is not None else max_fix_iterations
        self.max_fix_iterations = self.max_rounds  # backward-compat alias
        self.auto_fix_callable = auto_fix_callable
        self._collected_findings: list[FixAction] = []
        self._subscribed: bool = False

    # ------------------------------------------------------------------
    # EventBus subscription (backward compat)
    # ------------------------------------------------------------------

    def subscribe(self) -> None:
        """Subscribe to security/tester finding events on the bus."""
        if self._subscribed:
            return
        self.event_bus.on("security.finding", self._handle_security_finding)
        self.event_bus.on("tester.finding", self._handle_tester_finding)
        self.event_bus.on("review.finding", self._handle_review_finding)
        self._subscribed = True
        logger.debug("SeverityRouter subscribed to event bus")

    def unsubscribe(self) -> None:
        """Remove all this router's handlers from the event bus."""
        self.event_bus.off("security.finding", self._handle_security_finding)
        self.event_bus.off("tester.finding", self._handle_tester_finding)
        self.event_bus.off("review.finding", self._handle_review_finding)
        self._subscribed = False

    def _handle_security_finding(self, **kwargs: Any) -> None:
        self._add_finding_from_event("security", **kwargs)

    def _handle_tester_finding(self, **kwargs: Any) -> None:
        self._add_finding_from_event("tester", **kwargs)

    def _handle_review_finding(self, **kwargs: Any) -> None:
        self._add_finding_from_event("review_gate", **kwargs)

    def _add_finding_from_event(self, source: str, **kwargs: Any) -> None:
        severity = SeverityLevel.from_string(str(kwargs.get("severity", "medium")))
        action = FixAction(
            finding_id=kwargs.get("finding_id") or str(uuid.uuid4()),
            severity=severity,
            description=str(kwargs.get("description", "")),
            file_path=str(kwargs.get("file_path", "")),
            suggested_fix=str(kwargs.get("suggestion", "")),
            auto_fixable=bool(kwargs.get("auto_fixable", False)),
        )
        self._collected_findings.append(action)
        logger.debug(
            "SeverityRouter collected %s finding from %s: %s",
            action.severity.value,
            source,
            action.description,
        )

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def route(
        self,
        findings: list[ReviewFinding],
        context: dict[str, Any] | None = None,
    ) -> RoutingResult:
        """Route findings by severity and produce a :class:`RoutingResult`.

        Parameters
        ----------
        findings:
            List of :class:`ReviewFinding` objects (from
            :class:`TwoStageReviewGate` or any reviewer).
        context:
            Optional context dict (e.g. spec, code_changes, task info).
            Passed to the auto-fix callable when one is configured.

        Returns
        -------
        RoutingResult
        """
        context = context or {}
        actions: list[FixAction] = []
        blocked = False
        auto_fix_triggered = False

        for finding in findings:
            severity = self._classify_severity(finding)
            action = FixAction(
                finding_id=str(uuid.uuid4()),
                severity=severity,
                description=finding.description,
                file_path=getattr(finding, "file_path", ""),
                suggested_fix=getattr(finding, "suggestion", ""),
                auto_fixable=self._is_auto_fixable(finding, severity),
            )
            actions.append(action)

            if severity == SeverityLevel.CRITICAL:
                blocked = True
            elif (
                severity == SeverityLevel.HIGH
                and action.auto_fixable
                and self.development_mode
            ):
                # Attempt auto-fix immediately (single round)
                fixed = self._trigger_auto_fix(action, context)
                if fixed:
                    auto_fix_triggered = True

        # Non-blocking severity logging
        for action in actions:
            if action.severity == SeverityLevel.MEDIUM:
                logger.warning("MEDIUM finding: %s", action.description)
            elif action.severity in (SeverityLevel.LOW, SeverityLevel.INFO):
                logger.debug("%s finding: %s", action.severity.value, action.description)

        summary = self._build_summary(actions, blocked, auto_fix_triggered, 0)
        return RoutingResult(
            actions=actions,
            blocked=blocked,
            auto_fix_triggered=auto_fix_triggered,
            fix_round=0,
            max_rounds=self.max_rounds,
            summary=summary,
        )

    # ------------------------------------------------------------------
    # Severity classification
    # ------------------------------------------------------------------

    @staticmethod
    def _classify_severity(finding: ReviewFinding) -> SeverityLevel:
        """Map a :class:`ReviewFinding` to a :class:`SeverityLevel`.

        The finding's ``severity`` string is the primary signal:
          - "critical" → CRITICAL
          - "warning"  → HIGH (warnings should be fixed before merge)
          - "info"     → INFO

        Certain categories are downgraded based on their nature:
          - ``acceptance_criteria_not_evident`` → MEDIUM (heuristic)
          - ``missing_docstring`` / ``oversized_output`` → LOW (style)
          - ``anti_pattern_todo_left`` / ``anti_pattern_print_debug`` → LOW
        """
        # Allow pre-classified findings (FixAction) to pass through.
        if isinstance(finding, FixAction):
            return finding.severity

        severity_str = getattr(finding, "severity", "warning").lower()
        category = getattr(finding, "category", "")

        # Category-based downgrades for style/heuristic findings
        if category in ("missing_docstring", "oversized_output"):
            return SeverityLevel.LOW
        if category in ("anti_pattern_todo_left", "anti_pattern_print_debug"):
            return SeverityLevel.LOW
        if category == "acceptance_criteria_not_evident":
            return SeverityLevel.MEDIUM
        if category == "test_coverage_gap":
            return SeverityLevel.MEDIUM

        # Map the finding's severity string
        if severity_str == "critical":
            return SeverityLevel.CRITICAL
        if severity_str == "warning":
            return SeverityLevel.HIGH
        if severity_str == "info":
            return SeverityLevel.INFO
        # Fallback parse (handles "high", "medium", "low", aliases)
        return SeverityLevel.from_string(severity_str)

    @staticmethod
    def classify(severity: str | SeverityLevel) -> SeverityLevel:
        """Classify a severity string into a :class:`SeverityLevel` member."""
        if isinstance(severity, SeverityLevel):
            return severity
        return SeverityLevel.from_string(severity)

    @staticmethod
    def should_auto_fix(finding: ReviewFinding | FixAction) -> bool:
        """Return True if the finding severity triggers auto-fix."""
        if isinstance(finding, FixAction):
            return finding.is_blocking()
        severity = SeverityRouter._classify_severity(finding)
        return severity in (SeverityLevel.CRITICAL, SeverityLevel.HIGH)

    def _is_auto_fixable(
        self, finding: ReviewFinding, severity: SeverityLevel
    ) -> bool:
        """Determine if a finding is auto-fixable.

        Only HIGH-severity findings with known auto-fixable categories
        are considered auto-fixable. CRITICAL findings always require
        manual intervention.
        """
        if severity != SeverityLevel.HIGH:
            return False
        category = getattr(finding, "category", "")
        return category in self._AUTO_FIXABLE_CATEGORIES

    # ------------------------------------------------------------------
    # Auto-fix
    # ------------------------------------------------------------------

    def _trigger_auto_fix(
        self, action: FixAction, context: dict[str, Any]
    ) -> bool:
        """Trigger a fix for the given action.

        When an ``auto_fix_callable`` is configured, it is invoked.
        Otherwise, the method returns False (no fix applied) — the loop
        will still run up to ``max_rounds`` but no fixes will be applied.
        This preserves the contract that fixes are only applied when a
        callable is configured.

        Returns
        -------
        bool
            True if the fix was applied successfully.
        """
        if not self.development_mode:
            logger.info(
                "SeverityRouter: production mode — skipping auto-fix for %s",
                action.description,
            )
            return False

        if self.auto_fix_callable is not None:
            try:
                success = bool(self.auto_fix_callable(action, context))
            except (RuntimeError, ValueError, AttributeError, OSError) as exc:
                logger.warning("SeverityRouter: auto_fix_callable failed: %s", exc)
                return False
            if success:
                action.fix_applied = True
                action.fix_verified = True
            return success

        # No callable configured — no fix applied.
        logger.debug(
            "SeverityRouter: no auto_fix_callable — no fix applied for %s",
            action.description,
        )
        return False

    def _should_escalate(self, result: RoutingResult) -> bool:
        """Check if the result requires manual escalation.

        Escalation is needed when:
          - CRITICAL findings are present (always require manual fix), OR
          - After exhausting max_rounds, blocking actions remain unfixed.
        """
        if result.blocked:
            return True
        if result.fix_round >= result.max_rounds:
            remaining = [a for a in result.actions if a.is_blocking() and not a.fix_applied]
            return bool(remaining)
        return False

    # ------------------------------------------------------------------
    # Full auto-fix loop
    # ------------------------------------------------------------------

    def run_fix_loop(
        self,
        findings: list[ReviewFinding],
        context: dict[str, Any] | None = None,
        max_rounds: int | None = None,
        *,
        # Backward-compat signature (used by dispatch_steps.py):
        fix_callable: Callable[[list[FixAction]], list[FixAction]] | None = None,
        ci_check_callable: Callable[[], bool] | None = None,
    ) -> RoutingResult:
        """Run the full auto-fix loop.

        Parameters
        ----------
        findings:
            Findings to process.
        context:
            Optional context dict passed to the auto-fix callable.
        max_rounds:
            Override the configured max rounds for this call.
        fix_callable:
            **Legacy signature.** A callable that takes the list of
            blocking :class:`FixAction` objects and returns the list of
            *remaining* (unfixed) actions. When provided, this is used
            instead of :attr:`auto_fix_callable`.
        ci_check_callable:
            **Legacy signature.** A callable that runs a CI check and
            returns True on pass. When None, CI is assumed to pass.

        Returns
        -------
        RoutingResult
        """
        context = context or {}
        effective_max = max_rounds if max_rounds is not None else self.max_rounds

        # Initial routing
        result = self.route(findings, context)
        result.max_rounds = effective_max

        # If nothing blocking, we're done.
        blocking = [a for a in result.actions if a.is_blocking()]
        if not blocking:
            result.summary = self._build_summary(
                result.actions, result.blocked, False, 0
            )
            return result

        # CRITICAL findings always block — no auto-fix loop for them.
        critical = [a for a in blocking if a.severity == SeverityLevel.CRITICAL]
        if critical:
            result.blocked = True
            result.summary = self._build_summary(
                result.actions, True, False, 0
            )
            return result

        # Production mode: do not auto-fix
        if not self.development_mode:
            result.summary = self._build_summary(
                result.actions, False, False, 0
            ) + "\n(production mode — auto-fix skipped)"
            return result

        # Auto-fix loop for HIGH-severity findings
        round_num = 0
        while round_num < effective_max:
            round_num += 1
            current_blocking = [
                a for a in result.actions if a.is_blocking() and not a.fix_applied
            ]
            if not current_blocking:
                break

            logger.info(
                "SeverityRouter: auto-fix round %d/%d (%d blocking remaining)",
                round_num,
                effective_max,
                len(current_blocking),
            )

            if fix_callable is not None:
                # Legacy signature: fix_callable takes a list and returns
                # the list of remaining (unfixed) actions.
                try:
                    remaining = fix_callable(list(current_blocking))
                    remaining_ids = {
                        getattr(a, "finding_id", id(a)) for a in (remaining or [])
                    }
                    for action in current_blocking:
                        if action.finding_id not in remaining_ids:
                            action.fix_applied = True
                            action.fix_verified = True
                except (RuntimeError, ValueError, AttributeError, OSError) as exc:
                    logger.warning("SeverityRouter: fix_callable failed: %s", exc)
                    result.fix_round = round_num
                    result.summary = self._build_summary(
                        result.actions, result.blocked, True, round_num
                    )
                    return result
            else:
                # New signature: trigger auto-fix per action
                for action in current_blocking:
                    if action.auto_fixable:
                        fixed = self._trigger_auto_fix(action, context)
                        if fixed:
                            result.auto_fix_triggered = True

            # Run CI check after each round (legacy)
            if ci_check_callable is not None:
                try:
                    ci_passed = ci_check_callable()
                except (RuntimeError, OSError, ValueError) as exc:
                    logger.warning("SeverityRouter: CI check failed: %s", exc)
                    ci_passed = False
                if not ci_passed:
                    logger.warning(
                        "SeverityRouter: CI check failed after round %d", round_num
                    )
                    result.fix_round = round_num
                    result.summary = self._build_summary(
                        result.actions, result.blocked, True, round_num
                    )
                    return result

            result.fix_round = round_num

        result.fix_round = round_num if round_num else 0
        result.summary = self._build_summary(
            result.actions, result.blocked, result.auto_fix_triggered, result.fix_round
        )
        return result

    # ------------------------------------------------------------------
    # Backward-compat: collect_findings + run_auto_fix_loop
    # ------------------------------------------------------------------

    def collect_findings(
        self,
        worker_results: list[dict[str, Any]],
        review_result: Any | None = None,
    ) -> list[FixAction]:
        """Collect findings from worker outputs and a review result.

        Returns
        -------
        List of :class:`FixAction` objects (also stored internally).
        """
        findings: list[FixAction] = []

        # From worker results
        for wr in worker_results:
            wr_findings = wr.get("findings") or []
            if not isinstance(wr_findings, list):
                continue
            for f in wr_findings:
                if not isinstance(f, dict):
                    continue
                findings.append(
                    FixAction(
                        finding_id=f.get("finding_id") or str(uuid.uuid4()),
                        severity=SeverityLevel.from_string(str(f.get("severity", "medium"))),
                        description=str(f.get("description", "")),
                        file_path=str(f.get("file_path", "")),
                        suggested_fix=str(f.get("suggestion", "")),
                    )
                )

        # From review result
        if review_result is not None:
            findings.extend(self._extract_review_findings(review_result))

        # Merge with any event-bus-collected findings
        findings.extend(self._collected_findings)
        self._collected_findings = findings
        return findings

    @staticmethod
    def _extract_review_findings(review_result: Any) -> list[FixAction]:
        """Extract findings from a TwoStageReviewResult-like object."""
        findings: list[FixAction] = []
        # blocking_findings / blocking_issues → CRITICAL
        # warnings → HIGH
        for attr, default_severity in (
            ("blocking_findings", SeverityLevel.CRITICAL),
            ("blocking_issues", SeverityLevel.CRITICAL),
            ("warnings", SeverityLevel.HIGH),
        ):
            issues = getattr(review_result, attr, None) or []
            for issue in issues:
                if isinstance(issue, dict):
                    severity_str = str(issue.get("severity", default_severity.value))
                    findings.append(
                        FixAction(
                            finding_id=issue.get("finding_id") or str(uuid.uuid4()),
                            severity=SeverityLevel.from_string(severity_str),
                            description=str(issue.get("description", "")),
                            file_path=str(issue.get("file_path", "")),
                            suggested_fix=str(issue.get("suggestion", "")),
                        )
                    )
                else:
                    # Treat as object with attributes (ReviewFinding)
                    severity_str = getattr(issue, "severity", default_severity.value)
                    # ReviewFinding.severity is "critical"/"warning"/"info"
                    mapped = SeverityLevel.CRITICAL if severity_str == "critical" else default_severity
                    findings.append(
                        FixAction(
                            finding_id=str(uuid.uuid4()),
                            severity=mapped,
                            description=getattr(issue, "description", str(issue)),
                            file_path=getattr(issue, "file_path", ""),
                            suggested_fix=getattr(issue, "suggestion", ""),
                        )
                    )
        return findings

    def run_auto_fix_loop(
        self,
        findings: list[FixAction] | None = None,
        fix_callable: Callable[[list[FixAction]], list[FixAction]] | None = None,
        ci_check_callable: Callable[[], bool] | None = None,
    ) -> RoutingResult:
        """Backward-compat wrapper for :meth:`run_fix_loop`.

        Accepts :class:`FixAction` objects (the V3.8.0 ``Finding`` type)
        and delegates to :meth:`run_fix_loop`.
        """
        if findings is None:
            findings = self._collected_findings

        # Convert FixAction objects to ReviewFinding-like inputs by
        # passing them through directly (run_fix_loop handles FixAction
        # inputs via _classify_severity's pass-through for FixAction).
        result = self.run_fix_loop(
            findings=findings,  # type: ignore[arg-type]
            context={},
            fix_callable=fix_callable,
            ci_check_callable=ci_check_callable,
        )
        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_summary(
        self,
        actions: list[FixAction],
        blocked: bool,
        auto_fix_triggered: bool,
        fix_round: int,
    ) -> str:
        """Build a human-readable summary string."""
        status = "BLOCKED" if blocked else ("FIXED" if auto_fix_triggered else "OK")
        critical = sum(1 for a in actions if a.severity == SeverityLevel.CRITICAL)
        high = sum(1 for a in actions if a.severity == SeverityLevel.HIGH)
        medium = sum(1 for a in actions if a.severity == SeverityLevel.MEDIUM)
        low = sum(1 for a in actions if a.severity == SeverityLevel.LOW)
        info = sum(1 for a in actions if a.severity == SeverityLevel.INFO)
        fixed = sum(1 for a in actions if a.fix_applied)
        lines = [
            f"SeverityRouter: {status}",
            f"  Total actions: {len(actions)} "
            f"({critical} critical, {high} high, {medium} medium, {low} low, {info} info)",
            f"  Fixes applied: {fixed}",
            f"  Auto-fix triggered: {auto_fix_triggered}",
            f"  Fix rounds: {fix_round}",
        ]
        if blocked:
            lines.append("  CRITICAL findings present — manual escalation required.")
        return "\n".join(lines)

    def get_collected_findings(self) -> list[FixAction]:
        """Return the currently collected findings (does not clear)."""
        return list(self._collected_findings)

    def clear(self) -> None:
        """Clear all collected findings."""
        self._collected_findings = []


__all__ = [
    "AutoFixResult",
    "Finding",
    "FixAction",
    "RoutingResult",
    "Severity",
    "SeverityLevel",
    "SeverityRouter",
]
