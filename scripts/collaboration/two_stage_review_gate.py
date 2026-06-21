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
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ReviewStage(Enum):
    """Identifier for which review stage produced a finding."""

    SPEC_COMPLIANCE = "spec_compliance"  # Stage 1: Does code match the plan/spec?
    CODE_QUALITY = "code_quality"        # Stage 2: Is the code quality acceptable?


class StageResult(Enum):
    """Outcome of a single review stage.

    ``FAIL`` blocks progression (critical findings present).
    ``WARN`` means non-critical findings only (passes with warnings).
    ``PASS`` means no findings at all.
    """

    PASS = "pass"
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
    findings:
        All findings (critical + warning + info) produced by both stages.
    overall_passed:
        True only if both stages did not FAIL (no critical findings).
    blocking_findings:
        Critical findings that blocked progression (empty when passed).
    summary:
        Human-readable summary of the review.
    """

    stage1_result: StageResult = StageResult.PASS
    stage2_result: StageResult = StageResult.PASS
    findings: list[ReviewFinding] = field(default_factory=list)
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
    def blocking_issues(self) -> list[ReviewFinding]:
        """Alias for :attr:`blocking_findings`."""
        return self.blocking_findings

    @property
    def warnings(self) -> list[ReviewFinding]:
        """Non-critical findings (severity == 'warning')."""
        return [f for f in self.findings if f.severity == "warning"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.overall_passed,
            "overall_passed": self.overall_passed,
            "stage1_passed": self.stage1_passed,
            "stage2_passed": self.stage2_passed,
            "stage1_result": self.stage1_result.value,
            "stage2_result": self.stage2_result.value,
            "findings": [f.to_dict() for f in self.findings],
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


class TwoStageReviewGate:
    """Two-stage code review gate inspired by Superpowers.

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

    Critical findings in either stage block progression.

    Parameters
    ----------
    enable_two_stage_review:
        Master switch. When False, :meth:`review` returns a passing
        result immediately (no-op). This preserves backward
        compatibility for deployments that don't want the gate.
    strict_mode:
        When True (default), missing spec requirements are treated as
        critical. When False, they are downgraded to warnings.
    """

    # Stage 2 anti-pattern regexes (case-insensitive)
    _ANTI_PATTERN_REGEXES: tuple[tuple[str, re.Pattern[str]], ...] = (
        ("bare_except", re.compile(r"\bexcept\s*:\s*(?:pass|\.\.\.)")),
        ("todo_left", re.compile(r"\b(?:TODO|FIXME|XXX|HACK)\b")),
        ("print_debug", re.compile(r"\bprint\s*\(")),
        ("eval_usage", re.compile(r"\beval\s*\(")),
        ("exec_usage", re.compile(r"\bexec\s*\(")),
    )

    # Security patterns
    _SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
        # API keys / tokens (heuristic — looks for assignment of a long
        # string literal to a secret-looking variable name).
        (
            "hardcoded_api_key",
            re.compile(
                r"\b(?:api[_-]?key|api[_-]?secret|access[_-]?token|secret[_-]?key)"
                r"\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}['\"]",
                re.IGNORECASE,
            ),
        ),
        # Password assignment to a literal
        (
            "hardcoded_password",
            re.compile(
                r"\bpassword\s*[:=]\s*['\"][^'\"]{4,}['\"]",
                re.IGNORECASE,
            ),
        ),
    )

    _SQL_INJECTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
        # String formatting / concatenation in execute() calls
        (
            "sql_injection_format",
            re.compile(
                r"\.execute\s*\(\s*(?:f['\"]|['\"].*%s|['\"].*\.format|['\"].*\+)",
                re.IGNORECASE,
            ),
        ),
        (
            "sql_injection_concat",
            re.compile(
                r"(?:SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER)\b[^;]*\+\s*str\(",
                re.IGNORECASE,
            ),
        ),
    )

    def __init__(
        self,
        enable_two_stage_review: bool = True,
        strict_mode: bool = True,
    ) -> None:
        self.enable_two_stage_review = enable_two_stage_review
        self.strict_mode = strict_mode

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

        # Stage 1: spec compliance
        stage1_result, stage1_findings = self._check_spec_compliance(spec, code_changes)

        # Stage 2: code quality
        stage2_result, stage2_findings = self._check_code_quality(code_changes)

        all_findings = stage1_findings + stage2_findings
        blocking = [f for f in all_findings if f.is_critical()]
        overall_passed = stage1_result != StageResult.FAIL and stage2_result != StageResult.FAIL

        summary = self._build_summary(
            stage1_result, stage2_result, all_findings, blocking
        )

        result = TwoStageReviewResult(
            stage1_result=stage1_result,
            stage2_result=stage2_result,
            findings=all_findings,
            overall_passed=overall_passed,
            blocking_findings=blocking,
            summary=summary,
        )

        logger.info(
            "TwoStageReviewGate: stage1=%s stage2=%s passed=%s blocking=%d findings=%d",
            stage1_result.value,
            stage2_result.value,
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
    # Stage 1: Spec compliance
    # ------------------------------------------------------------------

    def _check_spec_compliance(
        self,
        spec: dict[str, Any],
        code_changes: dict[str, Any],
    ) -> tuple[StageResult, list[ReviewFinding]]:
        """Stage 1: verify the implementation matches the plan/spec."""
        findings: list[ReviewFinding] = []
        findings.extend(self._check_planned_files(spec, code_changes))
        findings.extend(self._check_planned_functions(spec, code_changes))
        findings.extend(self._check_plan_completion(spec, code_changes))
        findings.extend(self._check_required_roles(spec, code_changes))
        findings.extend(self._check_acceptance_criteria(spec, code_changes))

        has_critical = any(f.is_critical() for f in findings)
        if has_critical:
            return StageResult.FAIL, findings
        if findings:
            return StageResult.WARN, findings
        return StageResult.PASS, findings

    def _check_planned_files(
        self,
        spec: dict[str, Any],
        code_changes: dict[str, Any],
    ) -> list[ReviewFinding]:
        """Verify all planned files exist in code_changes."""
        planned_files = spec.get("planned_files") or spec.get("required_files") or []
        if not planned_files:
            return []
        files = code_changes.get("files") or {}
        # Also accept a list of file paths
        if isinstance(files, list):
            present_paths = {f if isinstance(f, str) else f.get("path", "") for f in files}
        else:
            present_paths = set(files.keys())

        findings: list[ReviewFinding] = []
        for planned in planned_files:
            if planned not in present_paths:
                severity = "critical" if self.strict_mode else "warning"
                findings.append(
                    ReviewFinding(
                        stage=ReviewStage.SPEC_COMPLIANCE,
                        severity=severity,
                        category="missing_file",
                        description=f"Planned file not found in code changes: {planned}",
                        file_path=planned,
                        suggestion=f"Create or modify {planned} as specified in the plan.",
                    )
                )
        return findings

    def _check_planned_functions(
        self,
        spec: dict[str, Any],
        code_changes: dict[str, Any],
    ) -> list[ReviewFinding]:
        """Verify planned functions/classes exist in code_changes contents."""
        planned_fns = spec.get("planned_functions") or spec.get("required_functions") or []
        if not planned_fns:
            return []
        files = code_changes.get("files") or {}
        # Build a combined content blob from all files
        if isinstance(files, dict):
            combined = "\n".join(
                str(f.get("content", "")) if isinstance(f, dict) else str(f)
                for f in files.values()
            )
        else:
            combined = "\n".join(
                str(f.get("content", "")) if isinstance(f, dict) else str(f)
                for f in files
            )
        # Also include worker outputs (legacy)
        outputs = code_changes.get("outputs") or ""
        combined = f"{combined}\n{outputs}"

        findings: list[ReviewFinding] = []
        for fn_name in planned_fns:
            # Match `def fn_name(` or `class FnName` or `async def fn_name(`
            pattern = re.compile(
                rf"\b(?:async\s+def|def|class)\s+{re.escape(fn_name)}\s*[\(:]"
            )
            if not pattern.search(combined):
                severity = "critical" if self.strict_mode else "warning"
                findings.append(
                    ReviewFinding(
                        stage=ReviewStage.SPEC_COMPLIANCE,
                        severity=severity,
                        category="missing_function",
                        description=(
                            f"Planned function/class not found in code changes: {fn_name}"
                        ),
                        suggestion=f"Implement `{fn_name}` as specified in the plan.",
                    )
                )
        return findings

    def _check_plan_completion(
        self,
        spec: dict[str, Any],
        _code_changes: dict[str, Any],
    ) -> list[ReviewFinding]:
        """Verify all planned tasks completed (when total_tasks is tracked).

        Note: when ``completed_tasks`` is None (plan does not track
        completion), we skip the completion check rather than blocking.
        """
        findings: list[ReviewFinding] = []
        total = spec.get("total_tasks")
        completed = spec.get("completed_tasks")
        failed = spec.get("failed_tasks")
        if total is None:
            return findings

        if completed is not None and completed < total:
            severity = "critical" if self.strict_mode else "warning"
            findings.append(
                ReviewFinding(
                    stage=ReviewStage.SPEC_COMPLIANCE,
                    severity=severity,
                    category="incomplete_plan",
                    description=f"Plan not fully completed: {completed}/{total} tasks done",
                    suggestion="Complete remaining tasks before review.",
                )
            )
        if failed and failed > 0:
            findings.append(
                ReviewFinding(
                    stage=ReviewStage.SPEC_COMPLIANCE,
                    severity="critical",
                    category="failed_tasks",
                    description=f"{failed} planned task(s) failed",
                    suggestion="Investigate and fix failed tasks.",
                )
            )
        return findings

    def _check_required_roles(
        self,
        spec: dict[str, Any],
        code_changes: dict[str, Any],
    ) -> list[ReviewFinding]:
        """Verify required roles produced output."""
        required_roles = spec.get("required_roles") or []
        if not required_roles:
            return []
        worker_results = code_changes.get("worker_results") or []
        present_roles = {
            wr.get("role_id") for wr in worker_results if wr.get("role_id")
        }
        findings: list[ReviewFinding] = []
        for role in required_roles:
            if role not in present_roles:
                findings.append(
                    ReviewFinding(
                        stage=ReviewStage.SPEC_COMPLIANCE,
                        severity="critical",
                        category="missing_role_output",
                        description=f"Required role did not produce output: {role}",
                        suggestion=f"Ensure the {role} role participates in the dispatch.",
                    )
                )
        return findings

    def _check_acceptance_criteria(
        self,
        spec: dict[str, Any],
        code_changes: dict[str, Any],
    ) -> list[ReviewFinding]:
        """Heuristically verify acceptance criteria are referenced in outputs."""
        criteria = spec.get("acceptance_criteria") or spec.get("required_artifacts") or []
        if not criteria:
            return []
        # Build combined output text
        files = code_changes.get("files") or {}
        if isinstance(files, dict):
            combined = " ".join(
                str(f.get("content", "")) if isinstance(f, dict) else str(f)
                for f in files.values()
            )
        else:
            combined = " ".join(
                str(f.get("content", "")) if isinstance(f, dict) else str(f)
                for f in files
            )
        outputs = code_changes.get("outputs") or ""
        combined = f"{combined} {outputs}".lower()

        findings: list[ReviewFinding] = []
        for criterion in criteria:
            keywords = [w.lower() for w in str(criterion).split() if len(w) > 3]
            if keywords and not any(kw in combined for kw in keywords):
                findings.append(
                    ReviewFinding(
                        stage=ReviewStage.SPEC_COMPLIANCE,
                        severity="warning",  # criteria match is heuristic
                        category="acceptance_criteria_not_evident",
                        description=(
                            f"Acceptance criterion not evident in outputs: {criterion}"
                        ),
                        suggestion=f"Verify the implementation satisfies: {criterion}",
                    )
                )
        return findings

    # ------------------------------------------------------------------
    # Stage 2: Code quality
    # ------------------------------------------------------------------

    def _check_code_quality(
        self,
        code_changes: dict[str, Any],
    ) -> tuple[StageResult, list[ReviewFinding]]:
        """Stage 2: check code quality dimensions."""
        findings: list[ReviewFinding] = []
        findings.extend(self._check_security(code_changes))
        findings.extend(self._check_error_handling(code_changes))
        findings.extend(self._check_test_coverage(code_changes))
        findings.extend(self._check_anti_patterns(code_changes))
        findings.extend(self._check_oversized_outputs(code_changes))

        has_critical = any(f.is_critical() for f in findings)
        if has_critical:
            return StageResult.FAIL, findings
        if findings:
            return StageResult.WARN, findings
        return StageResult.PASS, findings

    def _iter_file_contents(
        self, code_changes: dict[str, Any]
    ) -> list[tuple[str, str]]:
        """Yield (file_path, content) tuples from code_changes."""
        files = code_changes.get("files") or {}
        result: list[tuple[str, str]] = []
        if isinstance(files, dict):
            for path, info in files.items():
                content = info.get("content", "") if isinstance(info, dict) else str(info)
                if content:
                    result.append((path, str(content)))
        elif isinstance(files, list):
            for f in files:
                if isinstance(f, dict):
                    path = f.get("path", "<unknown>")
                    content = f.get("content", "")
                else:
                    path = "<unknown>"
                    content = str(f)
                if content:
                    result.append((path, str(content)))
        return result

    def _check_security(
        self, code_changes: dict[str, Any]
    ) -> list[ReviewFinding]:
        """Basic security checks: hardcoded secrets, SQL injection patterns."""
        findings: list[ReviewFinding] = []
        for file_path, content in self._iter_file_contents(code_changes):
            for name, pattern in self._SECRET_PATTERNS:
                matches = pattern.findall(content)
                if matches:
                    findings.append(
                        ReviewFinding(
                            stage=ReviewStage.CODE_QUALITY,
                            severity="critical",
                            category=f"security_{name}",
                            description=(
                                f"Potential {name} detected {len(matches)} time(s) "
                                f"in {file_path}"
                            ),
                            file_path=file_path,
                            suggestion="Move secrets to environment variables or a secret manager.",
                        )
                    )
            for name, pattern in self._SQL_INJECTION_PATTERNS:
                matches = pattern.findall(content)
                if matches:
                    findings.append(
                        ReviewFinding(
                            stage=ReviewStage.CODE_QUALITY,
                            severity="critical",
                            category=f"security_{name}",
                            description=(
                                f"Potential {name} detected {len(matches)} time(s) "
                                f"in {file_path}"
                            ),
                            file_path=file_path,
                            suggestion="Use parameterized queries instead of string formatting.",
                        )
                    )
        return findings

    def _check_error_handling(
        self, code_changes: dict[str, Any]
    ) -> list[ReviewFinding]:
        """Check for bare except, missing error handling."""
        findings: list[ReviewFinding] = []
        for file_path, content in self._iter_file_contents(code_changes):
            # Bare except: patterns
            bare_except_pattern = re.compile(r"\bexcept\s*:\s*(?:pass|\.\.\.)")
            matches = bare_except_pattern.findall(content)
            if matches:
                findings.append(
                    ReviewFinding(
                        stage=ReviewStage.CODE_QUALITY,
                        severity="warning",
                        category="bare_except",
                        description=(
                            f"Bare except clause detected {len(matches)} time(s) "
                            f"in {file_path}"
                        ),
                        file_path=file_path,
                        suggestion="Catch specific exceptions instead of bare `except:`.",
                    )
                )
            # eval/exec usage (critical)
            for name, pattern in (
                ("eval_usage", re.compile(r"\beval\s*\(")),
                ("exec_usage", re.compile(r"\bexec\s*\(")),
            ):
                matches = pattern.findall(content)
                if matches:
                    findings.append(
                        ReviewFinding(
                            stage=ReviewStage.CODE_QUALITY,
                            severity="critical",
                            category=f"anti_pattern_{name}",
                            description=(
                                f"Anti-pattern '{name}' detected {len(matches)} time(s) "
                                f"in {file_path}"
                            ),
                            file_path=file_path,
                            suggestion=f"Avoid {name} — it is a security risk.",
                        )
                    )
        return findings

    def _check_test_coverage(
        self, code_changes: dict[str, Any]
    ) -> list[ReviewFinding]:
        """Check if new code has corresponding tests."""
        findings: list[ReviewFinding] = []
        files = code_changes.get("files") or {}
        if not files:
            return findings

        # Identify code files vs test files
        code_files: list[tuple[str, str]] = []
        test_files: list[tuple[str, str]] = []
        if isinstance(files, dict):
            items = files.items()
        else:
            items = (
                (f.get("path", "<unknown>"), f) if isinstance(f, dict) else ("<unknown>", f)
                for f in files
            )
        for path, info in items:
            content = info.get("content", "") if isinstance(info, dict) else str(info)
            if not content:
                continue
            lower_path = path.lower()
            if "test" in lower_path or lower_path.endswith(("_test.py", "test.py")):
                test_files.append((path, str(content)))
            elif path.startswith("<") and path.endswith("_output>"):
                # Synthetic worker output — skip test-coverage check
                continue
            else:
                code_files.append((path, str(content)))

        # For each code file with function/class defs, check if tests exist
        has_any_test = len(test_files) > 0
        combined_test_content = "\n".join(c for _, c in test_files).lower()
        for path, content in code_files:
            has_code = any(
                kw in content
                for kw in ("def ", "class ", "function ", "import ")
            )
            if not has_code:
                continue
            has_test_keywords = any(
                kw in content.lower()
                for kw in ("test", "spec", "assert", "pytest", "unittest", "describe(")
            )
            if has_test_keywords:
                continue  # Inline tests present
            if not has_any_test:
                findings.append(
                    ReviewFinding(
                        stage=ReviewStage.CODE_QUALITY,
                        severity="critical",
                        category="missing_test",
                        description=(
                            f"Code changes in {path} have no corresponding test files"
                        ),
                        file_path=path,
                        suggestion="Add a test file covering the new code paths.",
                    )
                )
            else:
                # Tests exist — check if they reference this file/module
                # (heuristic: look for the file's basename without extension)
                import os

                module_name = os.path.splitext(os.path.basename(path))[0].lower()
                if module_name and module_name not in combined_test_content:
                    findings.append(
                        ReviewFinding(
                            stage=ReviewStage.CODE_QUALITY,
                            severity="warning",
                            category="test_coverage_gap",
                            description=(
                                f"Test files exist but do not appear to reference "
                                f"module '{module_name}' ({path})"
                            ),
                            file_path=path,
                            suggestion=f"Add tests that import and exercise {module_name}.",
                        )
                    )
        return findings

    def _check_anti_patterns(
        self, code_changes: dict[str, Any]
    ) -> list[ReviewFinding]:
        """Check for TODO/FIXME, print debugging, etc. (warnings)."""
        findings: list[ReviewFinding] = []
        for file_path, content in self._iter_file_contents(code_changes):
            for name, pattern in self._ANTI_PATTERN_REGEXES:
                # eval/exec are handled by _check_error_handling as critical
                if name in ("eval_usage", "exec_usage"):
                    continue
                matches = pattern.findall(content)
                if matches:
                    findings.append(
                        ReviewFinding(
                            stage=ReviewStage.CODE_QUALITY,
                            severity="warning",
                            category=f"anti_pattern_{name}",
                            description=(
                                f"Anti-pattern '{name}' detected {len(matches)} time(s) "
                                f"in {file_path}"
                            ),
                            file_path=file_path,
                            suggestion=f"Resolve the {name} anti-pattern before merge.",
                        )
                    )
        return findings

    def _check_oversized_outputs(
        self, code_changes: dict[str, Any]
    ) -> list[ReviewFinding]:
        """Flag outputs exceeding 200 lines (warning)."""
        findings: list[ReviewFinding] = []
        for file_path, content in self._iter_file_contents(code_changes):
            line_count = content.count("\n") + 1
            if line_count > 200:
                findings.append(
                    ReviewFinding(
                        stage=ReviewStage.CODE_QUALITY,
                        severity="warning",
                        category="oversized_output",
                        description=(
                            f"{file_path} is {line_count} lines (>200) — consider slicing"
                        ),
                        file_path=file_path,
                        suggestion="Split large files into smaller, focused modules.",
                    )
                )
        return findings

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def _build_summary(
        self,
        stage1: StageResult,
        stage2: StageResult,
        findings: list[ReviewFinding],
        blocking: list[ReviewFinding],
    ) -> str:
        """Build a human-readable summary string."""
        status = "PASSED" if not blocking else "BLOCKED"
        lines = [
            f"Two-Stage Review: {status}",
            f"  Stage 1 (Spec Compliance): {stage1.value.upper()}",
            f"  Stage 2 (Code Quality):    {stage2.value.upper()}",
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
) -> TwoStageReviewResult:
    """Convenience function to run a two-stage review.

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

    Returns
    -------
    TwoStageReviewResult
    """
    gate = TwoStageReviewGate(
        enable_two_stage_review=enable_two_stage_review,
        strict_mode=strict_mode,
    )
    return gate.review(spec=spec, code_changes=code_changes)


__all__ = [
    "ReviewFinding",
    "ReviewIssue",
    "ReviewStage",
    "StageResult",
    "TwoStageReviewGate",
    "TwoStageReviewResult",
    "run_two_stage_review",
]
