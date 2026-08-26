#!/usr/bin/env python3
"""Integration tests for SecuritySkill + DependencyHallucinationChecker (V4.3.0 P1-7).

Validates the Skill integration point required by the anti-ghost-feature
contract: the new module must be reachable via the SecuritySkill public
API, not just via direct module import.

Spec: docs/analysis/2026-07-25_P1-7_dependency_hallucination_review.md
      docs/architecture/V4.3.0_ARCHITECTURE.md §9.2 (Skill integration)
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.dependency_hallucination_checker import (
    get_call_count,
)
from skills.security.handler import SecuritySkill


def _reset_call_counter_er() -> None:
    import scripts.collaboration.dependency_hallucination_checker as mod
    mod._call_counter_er = 0


class T1_SecuritySkillScanDependenciesAPI(unittest.TestCase):
    """T1: SecuritySkill.scan_dependencies() public API contract."""

    def setUp(self) -> None:
        _reset_call_counter_er()
        self.skill = SecuritySkill()

    def test_01_clean_code_returns_is_clean_true(self) -> None:
        """Verify: clean code returns is_clean=True via Skill API."""
        result = self.skill.scan_dependencies("import requests\nimport numpy\n")
        self.assertTrue(result["is_clean"])
        self.assertEqual(result["stats"]["suspicious"], 0)
        self.assertEqual(result["stats"]["unknown"], 0)
        self.assertEqual(result["stats"]["known_good"], 2)

    def test_02_suspicious_package_detected(self) -> None:
        """Verify: hallucinated package detected via Skill API."""
        result = self.skill.scan_dependencies("import huggingface_cli\n")
        self.assertFalse(result["is_clean"])
        self.assertEqual(result["stats"]["suspicious"], 1)
        suspicious = [f for f in result["findings"] if f["category"] == "suspicious"]
        self.assertEqual(len(suspicious), 1)
        self.assertEqual(suspicious[0]["package_name"], "huggingface_cli")

    def test_03_markdown_section_rendered(self) -> None:
        """Verify: result contains user-visible Markdown section (anti-ghost)."""
        result = self.skill.scan_dependencies("import requests\n")
        self.assertIn("安全检查", result["markdown"])
        self.assertIn("依赖幻觉检测", result["markdown"])

    def test_04_call_counter_increments_via_skill(self) -> None:
        """Verify: Skill invocation increments module call counter (anti-ghost)."""
        before = get_call_count()
        self.skill.scan_dependencies("import requests\n")
        self.skill.scan_dependencies("import numpy\n")
        after = get_call_count()
        self.assertEqual(after, before + 2)


class T2_SecuritySkillRunModeDispatch(unittest.TestCase):
    """T2: SecuritySkill.run(mode='scan_dependencies', ...) dispatch."""

    def setUp(self) -> None:
        _reset_call_counter_er()
        self.skill = SecuritySkill()

    def test_01_run_mode_scan_dependencies(self) -> None:
        """Verify: run(mode='scan_dependencies', code=...) dispatches correctly."""
        result = self.skill.run(
            mode="scan_dependencies",
            code="import huggingface_cli\n",
        )
        self.assertFalse(result["is_clean"])
        self.assertEqual(result["stats"]["suspicious"], 1)

    def test_02_run_mode_scan_dependencies_clean(self) -> None:
        """Verify: clean code via run() mode dispatch."""
        result = self.skill.run(
            mode="scan_dependencies",
            code="import requests\n",
        )
        self.assertTrue(result["is_clean"])

    def test_03_run_mode_scan_dependencies_blocking_raises(self) -> None:
        """Verify: blocking=True via run() raises RuntimeError on SUSPICIOUS."""
        with self.assertRaises(RuntimeError):
            self.skill.run(
                mode="scan_dependencies",
                code="import huggingface_cli\n",
                blocking=True,
            )

    def test_04_run_mode_scan_dependencies_ecosystem_override(self) -> None:
        """Verify: ecosystem parameter is forwarded via run() dispatch."""
        result = self.skill.run(
            mode="scan_dependencies",
            code="const x = require('express');\n",
            ecosystem="npm",
        )
        self.assertEqual(result["ecosystem_detected"], "npm")
        self.assertTrue(result["is_clean"])


class T3_SecuritySkillAuditTaskIncludesDepCheck(unittest.TestCase):
    """T3: Full audit_task() flow is not broken by the new method."""

    def setUp(self) -> None:
        _reset_call_counter_er()
        self.skill = SecuritySkill()

    def test_01_audit_task_still_works(self) -> None:
        """Verify: audit_task() still functions after adding scan_dependencies."""
        result = self.skill.audit_task("Write a Python function to read a file")
        self.assertIn("overall_status", result)
        self.assertIn("injection_scan", result)

    def test_02_run_default_mode_still_works(self) -> None:
        """Verify: default run() mode (audit) still works."""
        result = self.skill.run(task_description="Read a config file safely")
        self.assertIn("overall_status", result)

    def test_03_run_scan_mode_still_works(self) -> None:
        """Verify: run(mode='scan') still works (no regression)."""
        result = self.skill.run(mode="scan", text="normal text without injection")
        self.assertIn("is_safe", result)


class T4_SecuritySkillModuleIntegration(unittest.TestCase):
    """T4: SecuritySkill correctly wraps the module's three-tier classification."""

    def setUp(self) -> None:
        _reset_call_counter_er()
        self.skill = SecuritySkill()

    def test_01_typo_squatting_via_skill(self) -> None:
        """Verify: typo-squatting (Levenshtein) detected via Skill API."""
        result = self.skill.scan_dependencies("import reqeusts\n")
        self.assertFalse(result["is_clean"])
        self.assertEqual(result["stats"]["suspicious"], 1)

    def test_02_unknown_package_via_skill(self) -> None:
        """Verify: novel package classified as UNKNOWN via Skill API."""
        result = self.skill.scan_dependencies("import zzz-novel-xyz-package\n")
        self.assertFalse(result["is_clean"])
        self.assertEqual(result["stats"]["unknown"], 1)

    def test_03_mixed_findings_via_skill(self) -> None:
        """Verify: mixed KNOWN_GOOD + SUSPICIOUS + UNKNOWN classified correctly."""
        code = (
            "import requests\n"           # KNOWN_GOOD
            "import huggingface_cli\n"    # SUSPICIOUS
            "import zzz-novel-xyz\n"      # UNKNOWN
        )
        result = self.skill.scan_dependencies(code)
        self.assertFalse(result["is_clean"])
        self.assertEqual(result["stats"]["known_good"], 1)
        self.assertEqual(result["stats"]["suspicious"], 1)
        self.assertEqual(result["stats"]["unknown"], 1)

    def test_04_blocking_mode_raises_with_package_name(self) -> None:
        """Verify: blocking mode error message includes package name."""
        with self.assertRaises(RuntimeError) as ctx:
            self.skill.scan_dependencies(
                "import huggingface_cli\n", blocking=True
            )
        self.assertIn("huggingface_cli", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
