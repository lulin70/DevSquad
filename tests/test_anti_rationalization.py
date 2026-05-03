#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for AntiRationalizationEngine (P0-1)

Coverage:
  - Unit: get_table() per role (7 roles)
  - Unit: format_for_prompt() markdown output
  - Unit: Universal + specific merge logic
  - Unit: Edge cases (unknown role, max_entries, cache)
  - Integration: PromptAssembler injection point
  - Regression: Existing prompt assembly unaffected

Spec reference: SPEC_V35_Agent_Skills_Quality_Framework.md Section 6.1
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.anti_rationalization import (
    AntiRationalizationEngine,
    RationalizationRow,
    get_shared_engine,
)


class TestRationalizationRow(unittest.TestCase):
    """Test RationalizationRow dataclass."""

    def test_creation(self):
        row = RationalizationRow(
            excuse="I'll do it later",
            reality="Later never comes",
        )
        self.assertEqual(row.excuse, "I'll do it later")
        self.assertEqual(row.reality, "Later never comes")

    def test_fields_are_strings(self):
        row = RationalizationRow(excuse="test", reality="test2")
        self.assertIsInstance(row.excuse, str)
        self.assertIsInstance(row.reality, str)


class TestUniversalTable(unittest.TestCase):
    """Test universal anti-rationalization table."""

    def setUp(self):
        self.engine = AntiRationalizationEngine()

    def test_universal_table_not_empty(self):
        table = self.engine._UNIVERSAL_TABLE
        self.assertGreater(len(table), 0, "Universal table must not be empty")

    def test_universal_table_has_at_least_5_entries(self):
        self.assertGreaterEqual(self.engine.universal_count, 5)

    def test_all_universal_entries_are_rationalization_rows(self):
        for row in self.engine._UNIVERSAL_TABLE:
            self.assertIsInstance(row, RationalizationRow)

    def test_universal_entries_have_non_empty_excuse(self):
        for row in self.engine._UNIVERSAL_TABLE:
            self.assertTrue(len(row.excuse.strip()) > 0)

    def test_universal_entries_have_non_empty_reality(self):
        for row in self.engine._UNIVERSAL_TABLE:
            self.assertTrue(len(row.reality.strip()) > 0)


class TestRoleSpecificTables(unittest.TestCase):
    """Test per-role anti-rationalization tables."""

    ALL_ROLES = [
        "architect",
        "product-manager",
        "security",
        "tester",
        "solo-coder",
        "devops",
        "ui-designer",
    ]

    def setUp(self):
        self.engine = AntiRationalizationEngine()

    def test_all_7_roles_have_tables(self):
        for role in self.ALL_ROLES:
            self.assertTrue(
                self.engine.has_role(role),
                f"Role '{role}' must have a specific table",
            )

    def test_each_role_has_at_least_3_entries(self):
        for role in self.ALL_ROLES:
            size = len(self.engine._ROLE_SPECIFIC_TABLES.get(role, []))
            self.assertGreaterEqual(
                size, 3,
                f"Role '{role}' must have at least 3 entries, got {size}",
            )

    def test_architect_has_architecture_specific_entries(self):
        table = self.engine.get_table("architect")
        excuses = [r.excuse.lower() for r in table]
        self.assertTrue(
            any("architecture" in e or "good enough" in e or "optimize" in e
                for e in excuses),
            "Architect table should have architecture-specific entries",
        )

    def test_security_has_security_specific_entries(self):
        table = self.engine.get_table("security")
        excuses = [r.excuse.lower() for r in table]
        self.assertTrue(
            any("internal tool" in e or "security" in e or "framework" in e
                for e in excuses),
            "Security table should have security-specific entries",
        )

    def test_tester_has_testing_specific_entries(self):
        table = self.engine.get_table("tester")
        excuses = [r.excuse.lower() for r in table]
        self.assertTrue(
            any("write tests" in e or "too simple" in e or "manual" in e
                for e in excuses),
            "Tester table should have testing-specific entries",
        )

    def test_coder_has_ai_code_specific_entry(self):
        table = self.engine.get_table("solo-coder")
        excuses = [r.excuse.lower() for r in table]
        self.assertTrue(
            any("ai-generated" in e or "probably fine" in e
                for e in excuses),
            "Coder table MUST have 'AI-generated code' entry "
            "(most dangerous rationalization for multi-AI systems)",
        )

    def test_unknown_role_returns_only_universal(self):
        table = self.engine.get_table("nonexistent_role_xyz")
        self.assertEqual(len(table), self.engine.universal_count)

    def test_list_all_roles_returns_sorted_list(self):
        roles = self.engine.list_all_roles()
        self.assertEqual(len(roles), 7)
        self.assertEqual(roles, sorted(roles))


class TestGetTableMerge(unittest.TestCase):
    """Test that get_table() correctly merges universal + specific."""

    def setUp(self):
        self.engine = AntiRationalizationEngine()

    def test_merged_table_larger_than_universal_alone(self):
        for role in ["architect", "tester", "solo-coder"]:
            merged = self.engine.get_table(role)
            self.assertGreater(
                len(merged), self.engine.universal_count,
                f"Merged table for '{role}' should be larger than universal alone",
            )

    def test_merged_contains_universal_entries(self):
        universal = self.engine._UNIVERSAL_TABLE
        merged = self.engine.get_table("architect")
        universal_excuses = {r.excuse for r in universal}
        merged_excuses = {r.excuse for r in merged}
        self.assertTrue(
            universal_excuses.issubset(merged_excuses),
            "Merged table must contain all universal entries",
        )

    def test_merged_contains_specific_entries(self):
        specific = self.engine._ROLE_SPECIFIC_TABLES["architect"]
        merged = self.engine.get_table("architect")
        specific_excuses = {r.excuse for r in specific}
        merged_excuses = {r.excuse for r in merged}
        self.assertTrue(
            specific_excuses.issubset(merged_excuses),
            "Merged table must contain all role-specific entries",
        )


class TestFormatForPrompt(unittest.TestCase):
    """Test format_for_prompt() produces valid markdown."""

    def setUp(self):
        self.engine = AntiRationalizationEngine()

    def test_format_returns_non_empty_for_known_role(self):
        output = self.engine.format_for_prompt("architect")
        self.assertTrue(len(output) > 0)

    def test_format_returns_empty_for_empty_table(self):
        engine = AntiRationalizationEngine()
        engine._UNIVERSAL_TABLE = []
        engine._ROLE_SPECIFIC_TABLES = {}
        output = engine.format_for_prompt("any_role")
        self.assertEqual(output, "")

    def test_format_contains_markdown_table_header(self):
        output = self.engine.format_for_prompt("tester")
        self.assertIn("| Excuse", output)
        self.assertIn("|---|", output)

    def test_format_contains_quality_guardrails_heading(self):
        output = self.engine.format_for_prompt("coder")
        self.assertIn("Quality Guardrails", output)

    def test_format_contains_rule_statement(self):
        output = self.engine.format_for_prompt("security")
        self.assertIn("non-negotiable", output.lower())

    def test_format_contains_all_rows_as_table_rows(self):
        output = self.engine.format_for_prompt("devops")
        table = self.engine.get_table("devops")
        for row in table[:3]:
            self.assertIn(row.excuse, output)

    def test_pipe_characters_in_content_are_escaped(self):
        row_with_pipe = RationalizationRow(
            excuse="a | b | c",
            reality="x | y",
        )
        engine = AntiRationalizationEngine()
        engine._UNIVERSAL_TABLE = [row_with_pipe]
        output = engine.format_for_prompt("any_role")
        self.assertNotIn("a | b | c", output)

    def test_format_caches_results(self):
        output1 = self.engine.format_for_prompt("architect")
        output2 = self.engine.format_for_prompt("architect")
        self.assertIs(output1, output2, "Cached result should return same object")


class TestMaxEntriesLimit(unittest.TestCase):
    """Test max_entries_per_role parameter for token budget control."""

    def test_max_entries_limits_output_size(self):
        engine = AntiRationalizationEngine(max_entries_per_role=3)
        table = engine.get_table("architect")
        self.assertLessEqual(len(table), 3)

    def test_max_entries_zero_means_all(self):
        engine = AntiRationalizationEngine(max_entries_per_role=0)
        full_engine = AntiRationalizationEngine()
        self.assertEqual(
            engine.get_table_size("tester"),
            full_engine.get_table_size("tester"),
        )

    def test_max_entries_truncates_from_start(self):
        engine = AntiRationalizationEngine(max_entries_per_role=2)
        table = engine.get_table("solo-coder")
        self.assertEqual(len(table), 2)

    def test_max_entries_affects_format_output(self):
        limited = AntiRationalizationEngine(max_entries_per_role=1)
        unlimited = AntiRationalizationEngine()
        limited_out = limited.format_for_prompt("architect")
        unlimited_out = unlimited.format_for_prompt("architect")
        self.assertLess(len(limited_out), len(unlimited_out))

    def test_get_table_size_respects_limit(self):
        engine = AntiRationalizationEngine(max_entries_per_role=5)
        full_size = engine.get_table_size("tester")
        self.assertLessEqual(full_size, 5)


class TestSharedSingleton(unittest.TestCase):
    """Test get_shared_engine singleton pattern."""

    def test_singleton_returns_same_instance(self):
        e1 = get_shared_engine()
        e2 = get_shared_engine()
        self.assertIs(e1, e2)

    def test_singleton_is_anti_rationalization_engine(self):
        engine = get_shared_engine()
        self.assertIsInstance(engine, AntiRationalizationEngine)

    def test_singleton_default_max_entries_is_zero(self):
        engine = get_shared_engine()
        self.assertEqual(engine._max_entries, 0)


class TestTotalEntriesProperty(unittest.TestCase):
    """Test aggregate statistics."""

    def setUp(self):
        self.engine = AntiRationalizationEngine()

    def test_total_entries_positive(self):
        self.assertGreater(self.engine.total_entries, 0)

    def test_total_entries_sufficient_coverage(self):
        self.assertGreaterEqual(self.engine.total_entries, 15,
                                 "Must have universal entries + role-specific entries")


class TestIntegrationPromptAssembly(unittest.TestCase):
    """Integration: AR content can be injected into prompt assembly context."""

    def setUp(self):
        self.engine = AntiRationalizationEngine()

    def test_ar_content_can_be_prepended_to_any_prompt(self):
        base_prompt = "You are an architect. Design the system."
        ar_content = self.engine.format_for_prompt("architect")
        combined = base_prompt + ar_content
        self.assertIn("Quality Guardrails", combined)
        self.assertIn("architect".lower(), combined.lower())

    def test_ar_content_does_not_break_existing_prompt_structure(self):
        base_prompt = "# Role: Architect\n\n## Task\n\nDesign auth system."
        ar_content = self.engine.format_for_prompt("architect")
        combined = base_prompt + ar_content
        self.assertTrue(combined.startswith("# Role"))
        self.assertIn("Design auth system", combined)
        self.assertIn("non-negotiable", combined)

    def test_all_roles_produce_valid_injectable_content(self):
        for role in [
            "architect", "product-manager", "security",
            "tester", "solo-coder", "devops", "ui-designer"
        ]:
            content = self.engine.format_for_prompt(role)
            self.assertGreater(len(content), 0,
                               f"Role '{role}' must produce non-empty content")


if __name__ == "__main__":
    unittest.main()
