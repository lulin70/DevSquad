#!/usr/bin/env python3
"""
YagniChecker — YAGNI ladder check for micro-tasks.

Inspired by DietrichGebert/ponytail. Before executing a micro-task,
checks if it actually needs to exist, or if a simpler solution exists.

The ladder (each rung checked in order):
  1. Does this need to exist? → SKIP if not (YAGNI)
  2. Stdlib does it? → USE_STDLIB
  3. Installed dependency does it? → USE_DEPENDENCY
  4. One line? → ONE_LINER
  5. Only then: MINIMAL (the minimum that works)

"Lazy, not negligent": trust-boundary validation, data-loss handling,
security, and accessibility are NEVER on the chopping block.

Integration
-----------
The checker is usable standalone via :meth:`YagniChecker.check`.
:meth:`YagniChecker.check_micro_task` accepts a ``MicroTask`` from
:mod:`scripts.collaboration.micro_task_planner` when available.

Usage::

    from scripts.collaboration.yagni_checker import YagniChecker

    checker = YagniChecker()
    result = checker.check("Parse JSON response from API")
    if result.verdict == "USE_STDLIB":
        print(result.shortcut_marker)  # "shortcut: use stdlib json.loads() / json.dumps()"
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

__all__ = ["YagniChecker", "YagniResult"]


@dataclass
class YagniResult:
    """Result of a YAGNI ladder check.

    Attributes
    ----------
    verdict:
        One of SKIP|USE_STDLIB|USE_DEPENDENCY|ONE_LINER|MINIMAL|NECESSARY.
    reason:
        Human-readable explanation of the verdict.
    upgrade_path:
        Suggested next step (how to act on the verdict).
    shortcut_marker:
        Short tag like ``"shortcut: <reason>"`` (empty for NECESSARY/MINIMAL).
    """

    verdict: str  # SKIP|USE_STDLIB|USE_DEPENDENCY|ONE_LINER|MINIMAL|NECESSARY
    reason: str
    upgrade_path: str
    shortcut_marker: str  # "shortcut: <reason>"


class YagniChecker:
    """YAGNI ladder checker for micro-tasks.

    Walks the ladder in order and returns the first matching verdict.
    Security, error-handling, data-loss, test, and accessibility tasks
    are NEVER skipped (they return NECESSARY).

    The ladder
    ----------
    1. NECESSARY — matches a never-skip pattern (security/error/test/a11y).
    2. SKIP — exploratory task without concrete output.
    3. USE_STDLIB — Python stdlib already provides a solution.
    4. USE_DEPENDENCY — an installed third-party dependency provides it.
    5. ONE_LINER — task can be done in a single line of code.
    6. MINIMAL — task is necessary; implement the minimum that works.
    """

    # Patterns that should NEVER be skipped (security/error/data-loss).
    NEVER_SKIP_PATTERNS: list[str] = [
        r"(?i)(validate|check|verify|sanitize|escape|escape_html)",
        r"(?i)(error|exception|catch|handle|fallback|retry)",
        r"(?i)(permission|auth|rbac|access|authorize)",
        r"(?i)(backup|save|persist|commit|rollback)",
        r"(?i)(test|assert|fixture|mock)",
        r"(?i)(accessibility|a11y|wcag|aria)",
    ]

    # Common Python stdlib solutions.
    STDLIB_PATTERNS: list[tuple[str, str]] = [
        (r"(?i)(parse\s+json|json\s+parse)", "json.loads() / json.dumps()"),
        (r"(?i)(parse\s+url|url\s+parse)", "urllib.parse.urlparse()"),
        (r"(?i)(regex|pattern\s+match)", "re module"),
        (r"(?i)(date\s+format|format\s+date)", "datetime.strftime()"),
        (r"(?i)(uuid|generate\s+id)", "uuid.uuid4()"),
        (r"(?i)(base64|encode\s+base64)", "base64 module"),
        (r"(?i)(hash|sha256|md5)", "hashlib module"),
        (r"(?i)(temp\s+file|temp\s+dir)", "tempfile module"),
        (r"(?i)(copy|deep\s+copy|clone)", "copy.copy() / copy.deepcopy()"),
        (r"(?i)(counter|count\s+items|frequency)", "collections.Counter"),
        (r"(?i)(merge\s+dict|combine\s+dict)", "{**a, **b} or dict.update()"),
        (r"(?i)(sort|sorted|order\s+by)", "sorted() or list.sort()"),
        (r"(?i)(group\s+by|groupby)", "itertools.groupby"),
        (r"(?i)(unique|deduplicate|remove\s+duplicates)", "set() or dict.fromkeys()"),
    ]

    # Common third-party dependency solutions.
    DEPENDENCY_PATTERNS: list[tuple[str, str]] = [
        (r"(?i)(http\s+request|fetch\s+url|get\s+url|http\s+get|http\s+post)", "requests"),
        (r"(?i)(html\s+parsing|parse\s+html)", "BeautifulSoup"),
        (r"(?i)(web\s+scraping|scrape\s+page)", "BeautifulSoup / scrapy"),
        (r"(?i)(date\s+parsing|parse\s+date\s+string|natural\s+date)", "dateutil.parser"),
        (r"(?i)(markdown\s+render|render\s+markdown)", "markdown library"),
        (r"(?i)(yaml\s+parse|parse\s+yaml|load\s+yaml)", "PyYAML yaml.safe_load()"),
        (r"(?i)(schema\s+validation|validate\s+schema|json\s+schema)", "pydantic / jsonschema"),
        (r"(?i)(env\s+config|load\s+env|environment\s+variables)", "python-dotenv"),
    ]

    # Patterns for purely exploratory tasks (no concrete output).
    EXPLORATORY_PATTERNS: list[str] = [
        r"(?i)^\s*(explore|investigate|look\s+into|research|consider|think\s+about|brainstorm|ponder)\b",
        r"(?i)\b(explore|investigate|look\s+into|research|consider|think\s+about|brainstorm|ponder)\s+(the\s+)?\w+\s*(options|approaches|alternatives|possibilities|trade-?offs)\b",
    ]

    # Patterns for one-liner tasks.
    ONE_LINER_PATTERNS: list[str] = [
        r"(?i)^\s*(set|print|import|return|assign|configure)\s+\w+\s*(=|to|\s)",
        r"(?i)\b(set\s+\w+\s*(=|to)\s+\w+)\b",
        r"(?i)\b(print|echo)\s*\(",
        r"(?i)\b(import|from\s+\w+\s+import)\s+\w+",
    ]

    # Concrete action verbs that indicate a real task (not exploratory).
    CONCRETE_VERBS: list[str] = [
        r"(?i)\b(create|write|implement|build|add|fix|modify|update|delete|remove|refactor)\b",
    ]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check(
        self,
        task_description: str,
        task_details: dict[str, Any] | None = None,
    ) -> YagniResult:
        """Check if a micro-task is necessary using the YAGNI ladder.

        Parameters
        ----------
        task_description:
            Natural-language description of the micro-task.
        task_details:
            Optional dict with extra context (e.g. ``file_paths``,
            ``verification_cmd``). Currently informational only.

        Returns
        -------
        YagniResult
            The verdict, reason, upgrade path, and shortcut marker.
        """
        # Edge case: empty / None description → SKIP.
        if not task_description or not task_description.strip():
            return YagniResult(
                verdict="SKIP",
                reason="Empty task description — nothing to do.",
                upgrade_path="Provide a concrete task description or drop the task.",
                shortcut_marker="shortcut: empty task skipped",
            )

        # 1. NEVER_SKIP patterns → NECESSARY (security/error/test/a11y).
        # Check both the description and file_paths from task_details.
        never_skip_hint = self._match_never_skip(task_description, task_details)
        if never_skip_hint is not None:
            return YagniResult(
                verdict="NECESSARY",
                reason=(
                    f"Task matches never-skip pattern (security/error/test/a11y): "
                    f"{never_skip_hint}"
                ),
                upgrade_path=(
                    "Implement fully — trust-boundary, data-loss, security, "
                    "and accessibility tasks are never on the chopping block."
                ),
                shortcut_marker="",  # No shortcut for NECESSARY tasks.
            )

        # 2. Exploratory task without concrete output → SKIP (YAGNI).
        if self._is_exploratory(task_description):
            return YagniResult(
                verdict="SKIP",
                reason="Exploratory task without concrete output — YAGNI.",
                upgrade_path=(
                    "Skip or merge with a concrete implementation task. "
                    "If exploration is genuinely needed, reframe as 'document X' "
                    "or 'list options for Y'."
                ),
                shortcut_marker="shortcut: exploratory task skipped",
            )

        # 3. Stdlib provides it → USE_STDLIB.
        stdlib_match = self._match_stdlib(task_description)
        if stdlib_match is not None:
            return YagniResult(
                verdict="USE_STDLIB",
                reason=f"Python stdlib already provides this: {stdlib_match}.",
                upgrade_path=f"Use {stdlib_match} instead of writing custom code.",
                shortcut_marker=f"shortcut: use stdlib {stdlib_match}",
            )

        # 4. Installed dependency provides it → USE_DEPENDENCY.
        dep_match = self._match_dependency(task_description)
        if dep_match is not None:
            return YagniResult(
                verdict="USE_DEPENDENCY",
                reason=f"Installed dependency already provides this: {dep_match}.",
                upgrade_path=f"Use {dep_match} instead of writing custom code.",
                shortcut_marker=f"shortcut: use dependency {dep_match}",
            )

        # 5. One-liner → ONE_LINER.
        if self._is_one_liner(task_description):
            return YagniResult(
                verdict="ONE_LINER",
                reason="Task can be completed in a single line of code.",
                upgrade_path=(
                    "Implement as a one-liner; no abstraction, no helper, "
                    "no wrapper needed."
                ),
                shortcut_marker="shortcut: one-liner implementation",
            )

        # 6. Otherwise → MINIMAL.
        return YagniResult(
            verdict="MINIMAL",
            reason="Task is necessary — implement the minimum that works.",
            upgrade_path=(
                "Implement the simplest version that passes verification. "
                "No speculative abstractions, no future-proofing."
            ),
            shortcut_marker="",
        )

    def check_micro_task(self, micro_task: Any) -> YagniResult:
        """Check a ``MicroTask`` from :mod:`micro_task_planner`.

        Parameters
        ----------
        micro_task:
            An object with ``title`` and ``description`` attributes
            (e.g. :class:`scripts.collaboration.micro_task_planner.MicroTask`).

        Returns
        -------
        YagniResult
            The verdict for the combined title + description text.
        """
        title = getattr(micro_task, "title", "") or ""
        description = getattr(micro_task, "description", "") or ""
        file_paths = getattr(micro_task, "file_paths", []) or []
        text = f"{title} {description}".strip() or title or description
        return self.check(
            text,
            task_details={"file_paths": list(file_paths)},
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _match_never_skip(
        self,
        task_description: str,
        task_details: dict[str, Any] | None,
    ) -> str | None:
        """Return the matching never-skip pattern, or None.

        Checks both the task description and any file_paths in task_details.
        If a file_path contains a security/test-related name (e.g. ``auth.py``,
        ``test_foo.py``), the task is treated as NECESSARY even if the
        description doesn't match a never-skip pattern.
        """
        # Check description against never-skip patterns.
        for pattern in self.NEVER_SKIP_PATTERNS:
            if re.search(pattern, task_description):
                return pattern
        # Check file_paths from task_details for security/test indicators.
        if task_details:
            file_paths = task_details.get("file_paths") or []
            for path in file_paths:
                path_lower = str(path).lower()
                if any(kw in path_lower for kw in ("test", "auth", "security", "permission", "a11y")):
                    return f"file_path indicator: {path}"
        return None

    def _is_exploratory(self, task_description: str) -> bool:
        """Return True if the task is purely exploratory (no concrete output).

        A task is exploratory when it starts with an exploration verb
        AND contains no concrete action verb (create/write/implement/...).
        """
        # Must match an exploratory pattern.
        if not any(re.search(p, task_description) for p in self.EXPLORATORY_PATTERNS):
            return False
        # If it ALSO contains a concrete verb, it's not purely exploratory.
        return not any(re.search(p, task_description) for p in self.CONCRETE_VERBS)

    def _match_stdlib(self, task_description: str) -> str | None:
        """Return the matching stdlib solution, or None."""
        for pattern, solution in self.STDLIB_PATTERNS:
            if re.search(pattern, task_description):
                return solution
        return None

    def _match_dependency(self, task_description: str) -> str | None:
        """Return the matching dependency solution, or None."""
        for pattern, solution in self.DEPENDENCY_PATTERNS:
            if re.search(pattern, task_description):
                return solution
        return None

    def _is_one_liner(self, task_description: str) -> bool:
        """Return True if the task can be done in a single line of code."""
        stripped = task_description.strip()
        if not stripped:
            return False
        # Match against one-liner patterns AND keep it short (single step).
        return any(
            re.search(p, stripped) for p in self.ONE_LINER_PATTERNS
        ) and len(stripped) <= 80
