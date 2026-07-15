#!/usr/bin/env python3
"""Module 2 (Matt P0-2): GLOSSARY.md + ADR — RoleSkillLoader.load_glossary().

Tests for ``RoleSkillLoader.load_glossary()`` added as part of V4.1.0
Matt Pocock skills fusion.

Acceptance criteria (PRD §3.1 P0-2): GLOSSARY.md >=30 terms + 5 ADRs +
RoleSkillLoader integration tests.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.role_skill_loader import RoleSkillLoader

# ======================================================================
# Module 2 — Matt Pocock GLOSSARY: load_glossary()
# ======================================================================


class TestLoadGlossaryDefaultPath(unittest.TestCase):
    """T1-T3: load_glossary with default path (real GLOSSARY.md)."""

    def setUp(self) -> None:
        self.loader = RoleSkillLoader()

    def test_loads_real_glossary(self) -> None:
        """Verify: load_glossary() finds and reads the real GLOSSARY.md."""
        content = self.loader.load_glossary()
        self.assertTrue(content, "GLOSSARY.md should not be empty")
        self.assertIn("GLOSSARY", content)

    def test_glossary_contains_expected_terms(self) -> None:
        """Verify: GLOSSARY.md contains key Matt Pocock + DevSquad terms."""
        content = self.loader.load_glossary()
        # Matt Pocock terms
        for term in ["Deep module", "Shallow module", "Seam", "Deletion test",
                      "Red-capable", "Grilling", "ADR"]:
            self.assertIn(term, content, f"GLOSSARY should contain '{term}'")
        # DevSquad terms
        for term in ["Consensus", "Gate", "Worker", "Iron Rule"]:
            self.assertIn(term, content, f"GLOSSARY should contain '{term}'")

    def test_glossary_has_sufficient_term_count(self) -> None:
        """Verify: GLOSSARY.md has >=30 terms (PRD acceptance criteria)."""
        content = self.loader.load_glossary()
        # Count bold terms (lines with | **Term** | pattern)
        import re
        bold_terms = re.findall(r"\|\s*\*\*([^*]+)\*\*\s*\|", content)
        # Deduplicate (some terms may appear in multiple sections)
        unique_terms = {t.strip() for t in bold_terms}
        self.assertGreaterEqual(
            len(unique_terms), 30,
            f"GLOSSARY should have >=30 terms, found {len(unique_terms)}: {unique_terms}",
        )


class TestLoadGlossaryCustomPath(unittest.TestCase):
    """T4-T6: load_glossary with custom path."""

    def test_loads_custom_glossary(self) -> None:
        """Verify: load_glossary(custom_path) reads the specified file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write("# Custom Glossary\n\n| **Term** | Definition |\n|---|---|\n| **Foo** | Bar |")
            f.flush()
            custom_path = f.name

        try:
            loader = RoleSkillLoader()
            content = loader.load_glossary(glossary_path=custom_path)
            self.assertIn("Custom Glossary", content)
            self.assertIn("Foo", content)
        finally:
            os.unlink(custom_path)

    def test_nonexistent_path_returns_empty(self) -> None:
        """Verify: load_glossary returns empty string for non-existent path."""
        loader = RoleSkillLoader()
        content = loader.load_glossary(glossary_path="/nonexistent/path/GLOSSARY.md")
        self.assertEqual(content, "")

    def test_empty_glossary_returns_empty(self) -> None:
        """Verify: load_glossary returns empty string for empty file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write("")
            f.flush()
            empty_path = f.name

        try:
            loader = RoleSkillLoader()
            content = loader.load_glossary(glossary_path=empty_path)
            self.assertEqual(content, "")
        finally:
            os.unlink(empty_path)


class TestGlossaryIntegration(unittest.TestCase):
    """T7-T8: Integration with RoleSkillLoader and prompt injection."""

    def test_loader_singleton_can_load_glossary(self) -> None:
        """Verify: shared loader singleton can load GLOSSARY."""
        from scripts.collaboration.role_skill_loader import get_shared_loader
        loader = get_shared_loader()
        content = loader.load_glossary()
        self.assertTrue(content)

    def test_glossary_content_suitable_for_prompt_injection(self) -> None:
        """Verify: GLOSSARY content is reasonable size for prompt injection."""
        loader = RoleSkillLoader()
        content = loader.load_glossary()
        # Should be non-empty but not excessively large (< 50KB for prompt)
        self.assertGreater(len(content), 100)
        self.assertLess(len(content), 50000, "GLOSSARY too large for prompt injection")


class TestADRSystem(unittest.TestCase):
    """T9-T10: ADR system validation (5 ADRs required by PRD)."""

    def _get_project_root(self) -> Path:
        """Derive project root from test file location."""
        return Path(__file__).parent.parent

    def test_adr_directory_exists(self) -> None:
        """Verify: docs/adr/ directory exists."""
        adr_dir = self._get_project_root() / "docs" / "adr"
        self.assertTrue(adr_dir.is_dir(), "docs/adr/ directory should exist")

    def test_five_adrs_exist(self) -> None:
        """Verify: at least 5 ADR files exist (PRD acceptance criteria)."""
        adr_dir = self._get_project_root() / "docs" / "adr"
        adr_files = list(adr_dir.glob("ADR-*.md"))
        self.assertGreaterEqual(
            len(adr_files), 5,
            f"Should have >=5 ADR files, found {len(adr_files)}: {[f.name for f in adr_files]}",
        )

    def test_adr_readme_lists_all_adrs(self) -> None:
        """Verify: ADR README.md lists all ADRs in the table."""
        readme = self._get_project_root() / "docs" / "adr" / "README.md"
        content = readme.read_text(encoding="utf-8")
        for adr_num in ["ADR-001", "ADR-002", "ADR-003", "ADR-004", "ADR-005"]:
            self.assertIn(adr_num, content, f"README should list {adr_num}")


if __name__ == "__main__":
    unittest.main()
