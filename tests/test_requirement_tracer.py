#!/usr/bin/env python3
"""Tests for RequirementTracer — V4.3.0 P1-1.

Coverage:
  - Unit: parse_requirements() extracts P0-1/P1-4 style IDs from markdown
  - Unit: find_implementations() scans source code for ID references
  - Unit: trace_matrix() builds a full traceability matrix
  - Edge cases: missing PRD file, deduplication, Chinese keywords,
    unknown requirement IDs, empty codebase

Spec reference: docs/prd/V4.3.0_PRD.md §3.2 (P1-1)
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))  # noqa: E402

from scripts.collaboration.requirement_tracer import (  # noqa: E402
    Requirement,
    RequirementTracer,
    TraceResult,
)


def _write(path: Path, content: str) -> Path:
    """Write content to a file and return its path."""
    path.write_text(content, encoding="utf-8")
    return path


class TestParseRequirements(unittest.TestCase):
    """Unit tests for RequirementTracer.parse_requirements()."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)

    def test_parses_simple_requirement_ids(self):
        prd = _write(
            Path(self.tmpdir.name) / "prd.md",
            "# PRD\n\n#### P0-1: First requirement\nSome text.\n"
            "#### P1-4: Second requirement\n",
        )
        tracer = RequirementTracer(codebase_root=self.tmpdir.name)
        reqs = tracer.parse_requirements(prd)
        ids = [r.req_id for r in reqs]
        self.assertIn("P0-1", ids)
        self.assertIn("P1-4", ids)

    def test_dedupes_repeated_ids(self):
        # Same ID appearing multiple times → only one Requirement.
        prd = _write(
            Path(self.tmpdir.name) / "prd.md",
            "P0-1: first mention\nP0-1: second mention\nP1-2: other\n",
        )
        tracer = RequirementTracer(codebase_root=self.tmpdir.name)
        reqs = tracer.parse_requirements(prd)
        ids = [r.req_id for r in reqs]
        self.assertEqual(ids.count("P0-1"), 1)
        self.assertEqual(len(reqs), 2)

    def test_sorted_by_id(self):
        prd = _write(
            Path(self.tmpdir.name) / "prd.md",
            "P2-1 z\nP0-1 a\nP1-4 m\n",
        )
        tracer = RequirementTracer(codebase_root=self.tmpdir.name)
        reqs = tracer.parse_requirements(prd)
        self.assertEqual([r.req_id for r in reqs], ["P0-1", "P1-4", "P2-1"])

    def test_records_source_file_and_line(self):
        prd = _write(
            Path(self.tmpdir.name) / "prd.md",
            "line1\nline2 P0-1\n",
        )
        tracer = RequirementTracer(codebase_root=self.tmpdir.name)
        reqs = tracer.parse_requirements(prd)
        self.assertEqual(reqs[0].line_number, 2)
        self.assertEqual(reqs[0].source_file, str(prd))

    def test_chinese_keywords_extracted(self):
        # A line containing 需求/实现/验收 should populate keywords.
        prd = _write(
            Path(self.tmpdir.name) / "prd.md",
            "P0-1: 需求 description here\nP1-2: 实现 note\n",
        )
        tracer = RequirementTracer(codebase_root=self.tmpdir.name)
        reqs = tracer.parse_requirements(prd)
        by_id = {r.req_id: r for r in reqs}
        self.assertIn("需求", by_id["P0-1"].keywords)
        self.assertIn("实现", by_id["P1-2"].keywords)

    def test_no_chinese_keywords_returns_empty_list(self):
        prd = _write(
            Path(self.tmpdir.name) / "prd.md",
            "P0-1: plain English requirement\n",
        )
        tracer = RequirementTracer(codebase_root=self.tmpdir.name)
        reqs = tracer.parse_requirements(prd)
        self.assertEqual(reqs[0].keywords, [])

    def test_missing_prd_raises(self):
        tracer = RequirementTracer(codebase_root=self.tmpdir.name)
        with self.assertRaises(FileNotFoundError):
            tracer.parse_requirements(Path(self.tmpdir.name) / "nope.md")

    def test_description_truncated_to_120(self):
        long_line = "P0-1: " + "x" * 200
        prd = _write(
            Path(self.tmpdir.name) / "prd.md", long_line + "\n"
        )
        tracer = RequirementTracer(codebase_root=self.tmpdir.name)
        reqs = tracer.parse_requirements(prd)
        self.assertLessEqual(len(reqs[0].description), 120)

    def test_does_not_match_substrings(self):
        # "XP0-1" should not match P0-1 (word boundary).
        prd = _write(
            Path(self.tmpdir.name) / "prd.md",
            "XP0-1 should not match\n",
        )
        tracer = RequirementTracer(codebase_root=self.tmpdir.name)
        reqs = tracer.parse_requirements(prd)
        self.assertEqual(reqs, [])


class TestFindImplementations(unittest.TestCase):
    """Unit tests for RequirementTracer.find_implementations()."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)

    def test_finds_implementation_in_code(self):
        # A .py file mentioning P1-4 → implemented.
        _write(
            Path(self.tmpdir.name) / "mod.py",
            "# P1-4: implements the rollback strategy\npass\n",
        )
        tracer = RequirementTracer(codebase_root=self.tmpdir.name)
        result = tracer.find_implementations("P1-4")
        self.assertEqual(result.status, "implemented")
        self.assertTrue(any("mod.py" in f for f in result.matched_files))

    def test_missing_implementation(self):
        # No file references the ID → missing.
        _write(
            Path(self.tmpdir.name) / "mod.py",
            "# no requirement reference here\n",
        )
        tracer = RequirementTracer(codebase_root=self.tmpdir.name)
        result = tracer.find_implementations("P9-9")
        self.assertEqual(result.status, "missing")
        self.assertEqual(result.matched_files, [])

    def test_unknown_id_creates_synthetic_requirement(self):
        # find_implementations works even without parse_requirements first.
        tracer = RequirementTracer(codebase_root=self.tmpdir.name)
        result = tracer.find_implementations("P5-5")
        self.assertEqual(result.requirement.req_id, "P5-5")
        self.assertEqual(result.requirement.description, "")
        self.assertEqual(result.status, "missing")

    def test_uses_parsed_requirement_when_available(self):
        prd = _write(
            Path(self.tmpdir.name) / "prd.md",
            "P1-4: 需求 rollback strategy\n",
        )
        _write(
            Path(self.tmpdir.name) / "mod.py",
            "# P1-4: implemented here\n",
        )
        tracer = RequirementTracer(codebase_root=self.tmpdir.name)
        tracer.parse_requirements(prd)
        result = tracer.find_implementations("P1-4")
        self.assertEqual(result.status, "implemented")
        self.assertIn("需求", result.requirement.keywords)

    def test_skips_non_code_files(self):
        # .md files should not be scanned for implementations.
        _write(
            Path(self.tmpdir.name) / "notes.md",
            "P1-4: mentioned in docs only\n",
        )
        tracer = RequirementTracer(codebase_root=self.tmpdir.name)
        result = tracer.find_implementations("P1-4")
        self.assertEqual(result.status, "missing")

    def test_matched_lines_contain_path_and_text(self):
        _write(
            Path(self.tmpdir.name) / "mod.py",
            "# P1-4: rollback\n",
        )
        tracer = RequirementTracer(codebase_root=self.tmpdir.name)
        result = tracer.find_implementations("P1-4")
        self.assertEqual(len(result.matched_lines), 1)
        self.assertIn("P1-4", result.matched_lines[0])
        self.assertIn("mod.py", result.matched_lines[0])

    def test_scans_multiple_code_extensions(self):
        # .py and .ts files should both be scanned.
        _write(
            Path(self.tmpdir.name) / "a.py",
            "# P0-1 in python\n",
        )
        _write(
            Path(self.tmpdir.name) / "b.ts",
            "// P0-1 in typescript\n",
        )
        tracer = RequirementTracer(codebase_root=self.tmpdir.name)
        result = tracer.find_implementations("P0-1")
        self.assertEqual(len(result.matched_files), 2)

    def test_returns_trace_result_type(self):
        tracer = RequirementTracer(codebase_root=self.tmpdir.name)
        result = tracer.find_implementations("P0-1")
        self.assertIsInstance(result, TraceResult)
        self.assertIsInstance(result.requirement, Requirement)


class TestTraceMatrix(unittest.TestCase):
    """Unit tests for RequirementTracer.trace_matrix()."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)

    def test_empty_when_no_requirements_parsed(self):
        tracer = RequirementTracer(codebase_root=self.tmpdir.name)
        self.assertEqual(tracer.trace_matrix(), [])

    def test_returns_result_for_each_requirement(self):
        prd = _write(
            Path(self.tmpdir.name) / "prd.md",
            "P0-1 a\nP1-2 b\n",
        )
        tracer = RequirementTracer(codebase_root=self.tmpdir.name)
        tracer.parse_requirements(prd)
        results = tracer.trace_matrix()
        self.assertEqual(len(results), 2)
        ids = [r.requirement.req_id for r in results]
        self.assertEqual(ids, ["P0-1", "P1-2"])

    def test_mixed_implemented_and_missing(self):
        prd = _write(
            Path(self.tmpdir.name) / "prd.md",
            "P0-1 implemented req\nP1-2 missing req\n",
        )
        _write(
            Path(self.tmpdir.name) / "mod.py",
            "# P0-1: done\n",
        )
        tracer = RequirementTracer(codebase_root=self.tmpdir.name)
        tracer.parse_requirements(prd)
        results = tracer.trace_matrix()
        by_id = {r.requirement.req_id: r for r in results}
        self.assertEqual(by_id["P0-1"].status, "implemented")
        self.assertEqual(by_id["P1-2"].status, "missing")

    def test_sorted_by_req_id(self):
        prd = _write(
            Path(self.tmpdir.name) / "prd.md",
            "P2-1 c\nP0-1 a\nP1-4 b\n",
        )
        tracer = RequirementTracer(codebase_root=self.tmpdir.name)
        tracer.parse_requirements(prd)
        results = tracer.trace_matrix()
        ids = [r.requirement.req_id for r in results]
        self.assertEqual(ids, ["P0-1", "P1-4", "P2-1"])


if __name__ == "__main__":
    unittest.main()
