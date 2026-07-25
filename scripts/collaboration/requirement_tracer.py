"""Requirement tracer — V4.3.0 P1-1.

Traces requirements from PRD markdown documents to their implementations
in source code. Parses requirement IDs (e.g., ``P0-1``, ``P1-4``) from
PRD files and scans the codebase for references to those IDs in comments
and docstrings.

Supports Chinese keywords (需求, 实现, 验收) — a requirement line that
contains any of these keywords is flagged so reviewers can locate
acceptance-criteria sections in bilingual PRDs.

Intentionally keyword-level only (no semantic mapping) per architecture
§3.3 — avoids over-engineering and stays under the complexity budget.

Architecture reference: docs/architecture/V4.3.0_ARCHITECTURE.md §3.3.
Test plan: docs/testing/V4.3.0_TEST_PLAN.md §3 (P1-1 row).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# Requirement ID pattern: P<digit>-<digit> (e.g., P0-1, P1-4, P2-1).
# Word boundaries prevent matching substrings like "XP0-1".
_REQ_ID_PATTERN = re.compile(r"\b(P\d+-\d+)\b")
# Chinese keyword indicators that a line discusses a requirement.
# 需求 = requirement, 实现 = implementation, 验收 = acceptance.
_CN_KEYWORDS: tuple[str, ...] = ("需求", "实现", "验收")
# Source code extensions to scan for requirement references.
_CODE_EXTS: tuple[str, ...] = (".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs")


@dataclass
class Requirement:
    """A requirement parsed from a PRD document.

    Attributes:
        req_id: The requirement ID (e.g., ``"P1-4"``).
        description: The source line text (truncated to 120 chars).
        source_file: Path of the PRD file where the requirement was found.
        line_number: 1-based line number in ``source_file``.
        keywords: Chinese keywords present on the source line.
    """

    req_id: str
    description: str
    source_file: str
    line_number: int
    keywords: list[str] = field(default_factory=list)


@dataclass
class TraceResult:
    """Trace result for a single requirement.

    Attributes:
        requirement: The :class:`Requirement` being traced.
        status: ``"implemented"`` if references found, else ``"missing"``.
        matched_files: Files that reference the requirement ID.
        matched_lines: ``path:line: text`` entries for each reference.
    """

    requirement: Requirement
    status: str
    matched_files: list[str] = field(default_factory=list)
    matched_lines: list[str] = field(default_factory=list)


class RequirementTracer:
    """Traces requirements from PRD docs to code implementations.

    Parses PRD markdown files for requirement IDs (``P0-1``, ``P1-4``),
    then scans source code for references to those IDs in comments and
    docstrings. Supports Chinese keywords (需求, 实现, 验收).

    Example:
        >>> tracer = RequirementTracer(codebase_root="scripts")
        >>> reqs = tracer.parse_requirements("docs/prd/V4.3.0_PRD.md")
        >>> results = tracer.trace_matrix()
    """

    def __init__(
        self,
        codebase_root: str | Path = "scripts",
        prd_path: str | Path | None = None,
    ) -> None:
        """Initialize the tracer.

        Args:
            codebase_root: Directory to scan for implementations.
            prd_path: Optional path to the PRD markdown file. May also be
                passed to :meth:`parse_requirements`.
        """
        self._root = Path(codebase_root)
        self._prd_path = Path(prd_path) if prd_path else None
        self._requirements: list[Requirement] = []

    def parse_requirements(self, prd_path: str | Path) -> list[Requirement]:
        """Parse a PRD markdown file for requirement IDs.

        Args:
            prd_path: Path to the PRD markdown file.

        Returns:
            List of :class:`Requirement` sorted by ID. Duplicate IDs are
            deduped (first occurrence wins).

        Raises:
            FileNotFoundError: If ``prd_path`` does not exist.
        """
        path = Path(prd_path)
        if not path.exists():
            raise FileNotFoundError(f"PRD file not found: {path}")
        self._prd_path = path
        self._requirements = []
        seen: set[str] = set()
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            self._collect_ids_from_line(line, path, lineno, seen)
        self._requirements.sort(key=lambda r: r.req_id)
        return list(self._requirements)

    def _collect_ids_from_line(
        self,
        line: str,
        path: Path,
        lineno: int,
        seen: set[str],
    ) -> None:
        """Extract requirement IDs from a single PRD line (dedupe)."""
        for match in _REQ_ID_PATTERN.finditer(line):
            req_id = match.group(1)
            if req_id in seen:
                continue
            seen.add(req_id)
            keywords = [kw for kw in _CN_KEYWORDS if kw in line]
            self._requirements.append(
                Requirement(
                    req_id=req_id,
                    description=line.strip()[:120],
                    source_file=str(path),
                    line_number=lineno,
                    keywords=keywords,
                )
            )

    def find_implementations(self, requirement_id: str) -> TraceResult:
        """Scan codebase for references to a requirement ID.

        Args:
            requirement_id: The requirement ID (e.g., ``"P1-4"``).

        Returns:
            A :class:`TraceResult` with matched files and lines. If the
            ID was not parsed via :meth:`parse_requirements`, a synthetic
            requirement is created with empty description.
        """
        req = next(
            (r for r in self._requirements if r.req_id == requirement_id),
            None,
        )
        if req is None:
            req = Requirement(
                req_id=requirement_id,
                description="",
                source_file="",
                line_number=0,
            )
        matched_files: list[str] = []
        matched_lines: list[str] = []
        for path in self._root.rglob("*"):
            if not path.is_file():
                continue
            hits = self._scan_file_for_id(path, requirement_id)
            if hits:
                matched_lines.extend(hits)
                matched_files.append(str(path))
        status = "implemented" if matched_files else "missing"
        return TraceResult(
            requirement=req,
            status=status,
            matched_files=matched_files,
            matched_lines=matched_lines,
        )

    def _scan_file_for_id(
        self, path: Path, requirement_id: str
    ) -> list[str]:
        """Scan a single file for references to a requirement ID."""
        if path.suffix not in _CODE_EXTS:
            return []
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return []
        hits: list[str] = []
        for lineno, line in enumerate(text.splitlines(), start=1):
            if requirement_id in line:
                hits.append(f"{path}:{lineno}: {line.strip()[:80]}")
        return hits

    def trace_matrix(self) -> list[TraceResult]:
        """Build a traceability matrix for all parsed requirements.

        Returns:
            List of :class:`TraceResult` sorted by requirement ID. Empty
            if :meth:`parse_requirements` has not been called.
        """
        results = [
            self.find_implementations(r.req_id) for r in self._requirements
        ]
        results.sort(key=lambda t: t.requirement.req_id)
        return results
