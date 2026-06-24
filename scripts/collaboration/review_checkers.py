#!/usr/bin/env python3
"""
ReviewCheckers — V3.8.1 P1: Checker methods extracted from TwoStageReviewGate.

This module contains the internal checker methods used by
:class:`TwoStageReviewGate`. It was split out of
``two_stage_review_gate.py`` to keep the main module focused on the
public API and result data structures.

The :class:`ReviewCheckers` class is used via composition by
:class:`TwoStageReviewGate` and is not intended to be used directly
by external callers. All public symbols remain re-exported from
``two_stage_review_gate.py`` for backward compatibility.

Contents
--------
- Security pattern constants (SECRET_PATTERNS, SQL_INJECTION_PATTERNS,
  ANTI_PATTERN_REGEXES)
- Stage 1 checkers: planned files, planned functions, plan completion,
  required roles, acceptance criteria
- Stage 2 checkers: security, error handling, test coverage,
  anti-patterns, oversized outputs
- Helper: ``iter_file_contents``
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from .two_stage_review_gate import ReviewFinding, ReviewStage, StageResult


class ReviewCheckers:
    """Internal checker methods used by :class:`TwoStageReviewGate`.

    This class holds all the Stage 1 (spec compliance) and Stage 2
    (code quality) checker methods, plus the security/anti-pattern
    regex constants they rely on.

    Parameters
    ----------
    strict_mode:
        When True, missing spec requirements are treated as critical.
        When False, they are downgraded to warnings.
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

    def __init__(self, strict_mode: bool = True) -> None:
        self.strict_mode = strict_mode

    # ------------------------------------------------------------------
    # Stage 1: Spec compliance
    # ------------------------------------------------------------------

    def check_spec_compliance(
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

    def check_code_quality(
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
            items: Iterable[tuple[str, Any]] = files.items()
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


__all__ = ["ReviewCheckers"]
