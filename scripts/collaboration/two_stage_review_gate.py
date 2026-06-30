#!/usr/bin/env python3
"""
TwoStageReviewGate — V3.8 #2: Two-stage code review gate.

Splits the post-dispatch review into two independent stages:

  Stage 1 — Spec compliance check (ReviewStage.SPEC_COMPLIANCE)
      Verifies that the implementation matches the plan/spec:
        - All planned files were created/modified
        - All planned functions/classes exist
        - Acceptance criteria are met

  Stage 2 — Code quality review (ReviewStage.CODE_QUALITY)
      Checks code quality dimensions:
        - Security issues (SQL injection, hardcoded secrets, etc.)
        - Error handling (bare except, missing error handling)
        - Test coverage (missing tests for new code)
        - Code style (anti-patterns, oversized outputs)

Critical findings in *either* stage block progression (StageResult.FAIL).
Non-critical findings are collected as warnings (StageResult.WARN).

Integration
-----------
The gate is usable standalone via :func:`run_two_stage_review` and is
also wired into :class:`PostDispatchPipeline` (dispatch_steps.py) as a
new step that runs after consensus and before completion. It is
configurable via ``enable_two_stage_review`` (default True).

V3.8.1 P1 Refactoring
---------------------
The internal checker methods and security/anti-pattern constants have
been extracted into :mod:`scripts.collaboration.review_checkers` as the
:class:`ReviewCheckers` class. :class:`TwoStageReviewGate` delegates to
it via composition. All public symbols remain importable from this
module for backward compatibility.

Usage::

    from scripts.collaboration.two_stage_review_gate import (
        TwoStageReviewGate,
        run_two_stage_review,
    )

    gate = TwoStageReviewGate()
    result = gate.review(
        spec={
            "planned_files": ["src/auth.py"],
            "planned_functions": ["login", "logout"],
            "acceptance_criteria": ["User can login"],
        },
        code_changes={
            "files": {
                "src/auth.py": {"content": "def login(): ..."},
            },
        },
    )
    if not result.overall_passed:
        # result.blocking_findings contains critical findings
        ...

    # Or use the convenience function
    result = run_two_stage_review(spec, code_changes)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .redesign_auditor import RedesignAuditor

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ReviewStage(Enum):
    """Identifier for which review stage produced a finding."""

    SPEC_COMPLIANCE = "spec_compliance"  # Stage 1: Does code match the plan/spec?
    CODE_QUALITY = "code_quality"        # Stage 2: Is the code quality acceptable?
    REDESIGN = "redesign"                # Stage 3 (V3.9): Can the code be simpler?


class StageResult(Enum):
    """Outcome of a single review stage.

    ``FAIL`` blocks progression (critical findings present).
    ``WARN`` means non-critical findings only (passes with warnings).
    ``PASS`` means no findings at all.
    """

    PASS = "pass"  # nosec B105 — enum value for gate status, not a password
    WARN = "warn"
    FAIL = "fail"  # Blocks progression


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ReviewFinding:
    """A single finding produced by a review stage.

    severity is one of: ``"critical"``, ``"warning"``, ``"info"``.
    Critical findings block progression (produce StageResult.FAIL).
    """

    stage: ReviewStage
    severity: str  # "critical" / "warning" / "info"
    category: str  # e.g., "missing_test", "spec_deviation", "security_issue"
    description: str
    file_path: str = ""
    line_range: str = ""
    suggestion: str = ""

    def is_critical(self) -> bool:
        return self.severity == "critical"

    def is_warning(self) -> bool:
        return self.severity == "warning"

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage.value,
            "severity": self.severity,
            "category": self.category,
            "description": self.description,
            "file_path": self.file_path,
            "line_range": self.line_range,
            "suggestion": self.suggestion,
        }


@dataclass
class TwoStageReviewResult:
    """Result of running :class:`TwoStageReviewGate`.

    Attributes
    ----------
    stage1_result:
        Outcome of Stage 1 (spec compliance).
    stage2_result:
        Outcome of Stage 2 (code quality).
    stage3_result:
        Outcome of Stage 3 (redesign audit, V3.9). Defaults to PASS when
        the redesign audit is disabled.
    findings:
        All findings (critical + warning + info) produced by all stages.
    redesign_findings:
        Raw :class:`RedesignFinding` objects from Stage 3 (V3.9). Empty
        when the redesign audit is disabled.
    overall_passed:
        True only if all enabled stages did not FAIL (no critical findings).
    blocking_findings:
        Critical findings that blocked progression (empty when passed).
    summary:
        Human-readable summary of the review.
    """

    stage1_result: StageResult = StageResult.PASS
    stage2_result: StageResult = StageResult.PASS
    stage3_result: StageResult = StageResult.PASS
    findings: list[ReviewFinding] = field(default_factory=list)
    redesign_findings: list[Any] = field(default_factory=list)
    overall_passed: bool = True
    blocking_findings: list[ReviewFinding] = field(default_factory=list)
    summary: str = ""

    # ------------------------------------------------------------------
    # Backward-compatibility properties (used by dispatch_steps.py and
    # older consumers that expect the V3.8.0 field names).
    # ------------------------------------------------------------------

    @property
    def passed(self) -> bool:
        """Alias for :attr:`overall_passed`."""
        return self.overall_passed

    @property
    def stage1_passed(self) -> bool:
        """True if Stage 1 did not FAIL."""
        return self.stage1_result != StageResult.FAIL

    @property
    def stage2_passed(self) -> bool:
        """True if Stage 2 did not FAIL."""
        return self.stage2_result != StageResult.FAIL

    @property
    def stage3_passed(self) -> bool:
        """True if Stage 3 (redesign) did not FAIL (V3.9)."""
        return self.stage3_result != StageResult.FAIL

    @property
    def blocking_issues(self) -> list[ReviewFinding]:
        """Alias for :attr:`blocking_findings`."""
        return self.blocking_findings

    @property
    def warnings(self) -> list[ReviewFinding]:
        """Non-critical findings (severity == 'warning')."""
        return [f for f in self.findings if f.severity == "warning"]

    def to_dict(self) -> dict[str, Any]:
        redesign_dicts: list[dict[str, Any]] = []
        for rf in self.redesign_findings:
            if hasattr(rf, "__dict__") or hasattr(rf, "severity"):
                redesign_dicts.append(
                    {
                        "severity": getattr(rf, "severity", ""),
                        "category": getattr(rf, "category", ""),
                        "current": getattr(rf, "current", ""),
                        "suggested": getattr(rf, "suggested", ""),
                        "saving_lines": getattr(rf, "saving_lines", 0),
                    }
                )
            elif isinstance(rf, dict):
                redesign_dicts.append(rf)
        return {
            "passed": self.overall_passed,
            "overall_passed": self.overall_passed,
            "stage1_passed": self.stage1_passed,
            "stage2_passed": self.stage2_passed,
            "stage3_passed": self.stage3_passed,
            "stage1_result": self.stage1_result.value,
            "stage2_result": self.stage2_result.value,
            "stage3_result": self.stage3_result.value,
            "findings": [f.to_dict() for f in self.findings],
            "redesign_findings": redesign_dicts,
            "blocking_issues": [f.to_dict() for f in self.blocking_findings],
            "blocking_findings": [f.to_dict() for f in self.blocking_findings],
            "warnings": [f.to_dict() for f in self.warnings],
            "blocking_count": len(self.blocking_findings),
            "warning_count": len(self.warnings),
            "summary": self.summary,
        }


# Backward-compatibility alias for the V3.8.0 dataclass name.
ReviewIssue = ReviewFinding


# ---------------------------------------------------------------------------
# Gate
# ---------------------------------------------------------------------------
#
# Import ReviewCheckers after the data structures above are defined so that
# review_checkers.py can import ReviewFinding/ReviewStage/StageResult without
# hitting a partially-initialized module. The noqa suppresses E402.
from .review_checkers import ReviewCheckers  # noqa: E402


class TwoStageReviewGate:
    """Two-stage (V3.9: three-stage) code review gate inspired by Superpowers.

    Stage 1 (Spec Compliance): Checks if the implementation matches the
    plan/spec.

      - Verifies all planned files were created/modified
      - Verifies all planned functions/classes exist
      - Verifies acceptance criteria are met

    Stage 2 (Code Quality): Checks code quality dimensions.

      - Security issues (SQL injection, hardcoded secrets, etc.)
      - Error handling (bare except, missing error handling)
      - Test coverage (missing tests for new code)
      - Code style (line length, naming, complexity)

    Stage 3 (Redesign Audit, V3.9): Checks if the code can be simpler.

      - YAGNI: unnecessary code/functions/classes
      - STDLIB: custom implementations that have stdlib equivalents
      - DUPLICATE: repeated code that can be extracted
      - OVERENGINEERING: excessive abstraction or unnecessary config

    Critical findings in any stage block progression.

    Parameters
    ----------
    enable_two_stage_review:
        Master switch. When False, :meth:`review` returns a passing
        result immediately (no-op). This preserves backward
        compatibility for deployments that don't want the gate.
    strict_mode:
        When True (default), missing spec requirements are treated as
        critical. When False, they are downgraded to warnings.
    enable_redesign_audit:
        V3.9 master switch for Stage 3 (redesign audit). When True
        (default), :class:`RedesignAuditor` runs after Stages 1 and 2.
        When False, Stage 3 is skipped (backward compatible with V3.8).
    redesign_auditor:
        Optional injected :class:`RedesignAuditor` instance (for testing
        or advanced configuration). When ``None`` and
        ``enable_redesign_audit`` is True, a default instance is created.
    """

    def __init__(
        self,
        enable_two_stage_review: bool = True,
        strict_mode: bool = True,
        enable_redesign_audit: bool = True,
        redesign_auditor: RedesignAuditor | None = None,
    ) -> None:
        self.enable_two_stage_review = enable_two_stage_review
        self.strict_mode = strict_mode
        self.enable_redesign_audit = enable_redesign_audit
        # Delegate checker methods to ReviewCheckers via composition.
        self._checkers = ReviewCheckers(strict_mode=strict_mode)
        # V3.9-02: Stage 3 — RedesignAuditor (lazy-init when not injected).
        self._redesign_auditor: RedesignAuditor | None = redesign_auditor

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def review(
        self,
        spec: dict[str, Any] | None = None,
        code_changes: dict[str, Any] | None = None,
        *,
        # Backward-compatibility kwargs (used by dispatch_steps.py):
        plan: Any = None,
        worker_results: list[dict[str, Any]] | None = None,
        spec_requirements: dict[str, Any] | None = None,
    ) -> TwoStageReviewResult:
        """Run both review stages and return the combined result.

        Two calling conventions are supported:

        1. **New API** (preferred)::

               gate.review(spec={...}, code_changes={...})

           Where ``spec`` may contain ``planned_files``, ``planned_functions``,
           ``acceptance_criteria``, ``required_roles``, ``total_tasks``,
           ``completed_tasks``, ``failed_tasks``; and ``code_changes`` may
           contain ``files`` (dict of path -> {content, ...}) and optionally
           ``worker_results``.

        2. **Legacy API** (backward compat)::

               gate.review(plan=plan, worker_results=wr, spec_requirements=sr)

        Returns
        -------
        TwoStageReviewResult
        """
        if not self.enable_two_stage_review:
            return TwoStageReviewResult()

        # Normalize inputs — support both new and legacy calling conventions.
        spec, code_changes = self._normalize_inputs(
            spec, code_changes, plan, worker_results, spec_requirements
        )

        # Stage 1: spec compliance (delegated to ReviewCheckers)
        stage1_result, stage1_findings = self._checkers.check_spec_compliance(
            spec, code_changes
        )

        # Stage 2: code quality (delegated to ReviewCheckers)
        stage2_result, stage2_findings = self._checkers.check_code_quality(
            code_changes
        )

        all_findings = stage1_findings + stage2_findings

        # V3.9-02: Stage 3 — Redesign audit (code simplicity check).
        # Runs after Stages 1 and 2 when enabled. CRITICAL findings from
        # the auditor (e.g. >50 lines of dead code) block progression.
        stage3_result = StageResult.PASS
        stage3_findings: list[ReviewFinding] = []
        redesign_findings_raw: list[Any] = []
        if self.enable_redesign_audit:
            stage3_result, stage3_findings, redesign_findings_raw = self._run_redesign_audit(
                code_changes
            )
            all_findings.extend(stage3_findings)

        blocking = [f for f in all_findings if f.is_critical()]
        overall_passed = (
            stage1_result != StageResult.FAIL
            and stage2_result != StageResult.FAIL
            and stage3_result != StageResult.FAIL
        )

        summary = self._build_summary(
            stage1_result, stage2_result, stage3_result, all_findings, blocking
        )

        result = TwoStageReviewResult(
            stage1_result=stage1_result,
            stage2_result=stage2_result,
            stage3_result=stage3_result,
            findings=all_findings,
            redesign_findings=redesign_findings_raw,
            overall_passed=overall_passed,
            blocking_findings=blocking,
            summary=summary,
        )

        logger.info(
            "TwoStageReviewGate: stage1=%s stage2=%s stage3=%s passed=%s blocking=%d findings=%d",
            stage1_result.value,
            stage2_result.value,
            stage3_result.value,
            overall_passed,
            len(blocking),
            len(all_findings),
        )
        return result

    # ------------------------------------------------------------------
    # Input normalization (backward compat)
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_inputs(
        spec: dict[str, Any] | None,
        code_changes: dict[str, Any] | None,
        plan: Any,
        worker_results: list[dict[str, Any]] | None,
        spec_requirements: dict[str, Any] | None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Normalize inputs to the (spec, code_changes) dict format.

        Supports the legacy (plan, worker_results, spec_requirements)
        calling convention by converting them into the new format.
        """
        spec = dict(spec) if spec else {}
        code_changes = dict(code_changes) if code_changes else {}

        # Merge legacy spec_requirements into spec
        if spec_requirements:
            for key, value in spec_requirements.items():
                spec.setdefault(key, value)

        # Convert legacy plan object/dict into spec fields
        if plan is not None:
            total = getattr(plan, "total_tasks", None)
            completed = getattr(plan, "completed_tasks", None)
            failed = getattr(plan, "failed_tasks", None)
            if total is None and isinstance(plan, dict):
                total = plan.get("total_tasks")
                completed = plan.get("completed_tasks")
                failed = plan.get("failed_tasks")
            if total is not None:
                spec.setdefault("total_tasks", total)
            if completed is not None:
                spec.setdefault("completed_tasks", completed)
            if failed is not None:
                spec.setdefault("failed_tasks", failed)

        # Convert legacy worker_results into code_changes.files + outputs
        if worker_results is not None and "files" not in code_changes:
            code_changes.setdefault("worker_results", worker_results)
            # Build a synthetic "files" view from worker outputs so the
            # Stage 2 checks (which scan file contents) can run.
            files: dict[str, dict[str, Any]] = {}
            combined_outputs: list[str] = []
            for wr in worker_results:
                role_id = wr.get("role_id", "unknown")
                output = str(wr.get("output", "") or "")
                if output:
                    combined_outputs.append(output)
                    # Expose each worker output as a synthetic file path
                    files[f"<{role_id}_output>"] = {
                        "content": output,
                        "role_id": role_id,
                    }
            if files:
                code_changes.setdefault("files", files)
            if combined_outputs:
                code_changes.setdefault("outputs", "\n".join(combined_outputs))

        return spec, code_changes

    # ------------------------------------------------------------------
    # V3.9-02: Stage 3 — Redesign audit
    # ------------------------------------------------------------------

    def _get_redesign_auditor(self) -> RedesignAuditor:
        """Lazily instantiate the RedesignAuditor when first needed."""
        if self._redesign_auditor is None:
            self._redesign_auditor = RedesignAuditor()
        return self._redesign_auditor

    def _run_redesign_audit(
        self, code_changes: dict[str, Any]
    ) -> tuple[StageResult, list[ReviewFinding], list[Any]]:
        """Run Stage 3: RedesignAuditor on the combined code.

        Concatenates all file contents from ``code_changes['files']``
        (plus ``code_changes['outputs']`` as a fallback) and passes the
        combined source to :meth:`RedesignAuditor.audit`.

        Severity mapping (RedesignFinding → ReviewFinding):
          - CRITICAL → "critical" (blocks progression)
          - HIGH     → "warning"
          - MEDIUM   → "warning"
          - LOW      → "info"

        Returns
        -------
        tuple
            (stage_result, review_findings, raw_redesign_findings)
        """
        try:
            auditor = self._get_redesign_auditor()
            combined_code = self._extract_code_for_audit(code_changes)
            if not combined_code.strip():
                return StageResult.PASS, [], []
            raw_findings = auditor.audit(combined_code)
        except (ValueError, AttributeError, TypeError, RuntimeError) as exc:
            logger.warning("RedesignAuditor failed: %s", exc)
            return StageResult.PASS, [], []

        review_findings: list[ReviewFinding] = []
        has_critical = False
        for rf in raw_findings:
            severity = self._map_redesign_severity(rf.severity)
            if severity == "critical":
                has_critical = True
            review_findings.append(
                ReviewFinding(
                    stage=ReviewStage.REDESIGN,
                    severity=severity,
                    category=rf.category,
                    description=rf.current,
                    suggestion=rf.suggested,
                )
            )

        stage_result = StageResult.FAIL if has_critical else (
            StageResult.WARN if review_findings else StageResult.PASS
        )
        return stage_result, review_findings, raw_findings

    @staticmethod
    def _extract_code_for_audit(code_changes: dict[str, Any]) -> str:
        """Extract combined source code from code_changes for auditing.

        Concatenates file contents from ``files`` dict; falls back to
        ``outputs`` string when no files are present.
        """
        parts: list[str] = []
        files = code_changes.get("files")
        if isinstance(files, dict):
            for path, info in files.items():
                if isinstance(info, dict):
                    content = info.get("content", "")
                elif isinstance(info, str):
                    content = info
                else:
                    content = ""
                if content:
                    parts.append(f"# === {path} ===\n{content}")
        elif isinstance(files, list):
            for entry in files:
                if isinstance(entry, dict):
                    content = entry.get("content", "")
                    path = entry.get("path", "<unknown>")
                    if content:
                        parts.append(f"# === {path} ===\n{content}")

        if not parts:
            outputs = code_changes.get("outputs")
            if isinstance(outputs, str) and outputs.strip():
                parts.append(outputs)

        return "\n\n".join(parts)

    @staticmethod
    def _map_redesign_severity(redesign_severity: str) -> str:
        """Map RedesignFinding severity to ReviewFinding severity.

        CRITICAL → "critical" (blocks progression)
        HIGH     → "warning"
        MEDIUM   → "warning"
        LOW      → "info"
        """
        sev = redesign_severity.upper()
        if sev == "CRITICAL":
            return "critical"
        if sev in ("HIGH", "MEDIUM"):
            return "warning"
        return "info"

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def _build_summary(
        self,
        stage1: StageResult,
        stage2: StageResult,
        stage3: StageResult,
        findings: list[ReviewFinding],
        blocking: list[ReviewFinding],
    ) -> str:
        """Build a human-readable summary string."""
        status = "PASSED" if not blocking else "BLOCKED"
        lines = [
            f"Two-Stage Review: {status}",
            f"  Stage 1 (Spec Compliance): {stage1.value.upper()}",
            f"  Stage 2 (Code Quality):    {stage2.value.upper()}",
            f"  Stage 3 (Redesign Audit):  {stage3.value.upper()}",
            f"  Total findings: {len(findings)} "
            f"({len(blocking)} critical, "
            f"{len([f for f in findings if f.severity == 'warning'])} warning, "
            f"{len([f for f in findings if f.severity == 'info'])} info)",
        ]
        if blocking:
            lines.append("  Blocking findings:")
            for f in blocking[:5]:
                lines.append(f"    - [{f.category}] {f.description}")
        return "\n".join(lines)

    def format_report(self, result: TwoStageReviewResult) -> str:
        """Format a :class:`TwoStageReviewResult` as a Markdown report.

        Parameters
        ----------
        result:
            The review result to format.

        Returns
        -------
        str
            Markdown-formatted report.
        """
        lines: list[str] = []
        status_badge = "PASS" if result.overall_passed else "FAIL"
        lines.append("# Two-Stage Code Review Report")
        lines.append("")
        lines.append(f"**Overall Status:** {status_badge}")
        lines.append("")
        lines.append("## Stage Results")
        lines.append("")
        lines.append("| Stage | Result |")
        lines.append("|-------|--------|")
        lines.append(f"| Stage 1: Spec Compliance | {result.stage1_result.value} |")
        lines.append(f"| Stage 2: Code Quality | {result.stage2_result.value} |")
        lines.append(f"| Stage 3: Redesign Audit | {result.stage3_result.value} |")
        lines.append("")

        if result.blocking_findings:
            lines.append("## Blocking Findings (Critical)")
            lines.append("")
            for f in result.blocking_findings:
                lines.append(f"- **[{f.category}]** {f.description}")
                if f.file_path:
                    lines.append(f"  - File: `{f.file_path}`")
                if f.suggestion:
                    lines.append(f"  - Suggestion: {f.suggestion}")
            lines.append("")

        warnings = [f for f in result.findings if f.severity == "warning"]
        if warnings:
            lines.append("## Warnings")
            lines.append("")
            for f in warnings:
                lines.append(f"- **[{f.category}]** {f.description}")
                if f.file_path:
                    lines.append(f"  - File: `{f.file_path}`")
            lines.append("")

        infos = [f for f in result.findings if f.severity == "info"]
        if infos:
            lines.append("## Informational")
            lines.append("")
            for f in infos:
                lines.append(f"- **[{f.category}]** {f.description}")
            lines.append("")

        # V3.9-02: Redesign suggestions (Stage 3 raw findings)
        if result.redesign_findings:
            lines.append("## Redesign Suggestions (Stage 3)")
            lines.append("")
            for rf in result.redesign_findings:
                severity = getattr(rf, "severity", "")
                category = getattr(rf, "category", "")
                current = getattr(rf, "current", "")
                suggested = getattr(rf, "suggested", "")
                saving = getattr(rf, "saving_lines", 0)
                lines.append(
                    f"- **[{severity}/{category}]** {current} → {suggested}"
                    f" (saves ~{saving} lines)"
                )
            lines.append("")

        lines.append("## Summary")
        lines.append("")
        lines.append("```")
        lines.append(result.summary)
        lines.append("```")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------


def run_two_stage_review(
    spec: dict[str, Any],
    code_changes: dict[str, Any],
    *,
    enable_two_stage_review: bool = True,
    strict_mode: bool = True,
    enable_redesign_audit: bool = True,
) -> TwoStageReviewResult:
    """Convenience function to run a two-stage (V3.9: three-stage) review.

    Parameters
    ----------
    spec:
        Spec/plan dictionary. Supported keys: ``planned_files``,
        ``planned_functions``, ``acceptance_criteria``, ``required_roles``,
        ``total_tasks``, ``completed_tasks``, ``failed_tasks``.
    code_changes:
        Code changes dictionary. Supported keys: ``files`` (dict of
        path -> {content, ...} or list of {path, content}), ``outputs``
        (combined output text), ``worker_results`` (legacy).
    enable_two_stage_review:
        Master switch (default True).
    strict_mode:
        When True, missing spec requirements are critical (default True).
    enable_redesign_audit:
        V3.9 master switch for Stage 3 (redesign audit). Default True.

    Returns
    -------
    TwoStageReviewResult
    """
    gate = TwoStageReviewGate(
        enable_two_stage_review=enable_two_stage_review,
        strict_mode=strict_mode,
        enable_redesign_audit=enable_redesign_audit,
    )
    return gate.review(spec=spec, code_changes=code_changes)


__all__ = [
    "RedesignAuditor",
    "ReviewFinding",
    "ReviewIssue",
    "ReviewStage",
    "StageResult",
    "TwoStageReviewGate",
    "TwoStageReviewResult",
    "run_two_stage_review",
]
