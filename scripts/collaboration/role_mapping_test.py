#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Role Mapping Test Suite

Tests for ROLE_REGISTRY, ROLE_ALIASES, and resolve_role_id() in models.py.
Covers the critical user path: CLI short IDs → canonical IDs.
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from scripts.collaboration.models import (
    ROLE_REGISTRY, ROLE_ALIASES, resolve_role_id,
    get_core_roles, get_planned_roles, get_all_role_ids, get_cli_role_list,
)
from scripts.collaboration.dispatcher import (
    ROLE_TEMPLATES, PLANNED_ROLES, MultiAgentDispatcher,
)


class TestRoleAliases(unittest.TestCase):
    """Test ROLE_ALIASES mapping correctness."""

    def test_01_alias_pm_to_product_manager(self):
        self.assertEqual(resolve_role_id("pm"), "product-manager")

    def test_02_alias_coder_to_solo_coder(self):
        self.assertEqual(resolve_role_id("coder"), "solo-coder")

    def test_03_alias_ui_to_ui_designer(self):
        self.assertEqual(resolve_role_id("ui"), "ui-designer")

    def test_04_alias_dev_to_solo_coder(self):
        self.assertEqual(resolve_role_id("dev"), "solo-coder")

    def test_05_alias_arch_to_architect(self):
        self.assertEqual(resolve_role_id("arch"), "architect")

    def test_06_alias_test_to_tester(self):
        self.assertEqual(resolve_role_id("test"), "tester")

    def test_07_alias_qa_to_tester(self):
        self.assertEqual(resolve_role_id("qa"), "tester")


class TestResolveRoleId(unittest.TestCase):
    """Test resolve_role_id() behavior for all input types."""

    def test_01_canonical_id_passthrough(self):
        for rid in ROLE_REGISTRY:
            self.assertEqual(resolve_role_id(rid), rid)

    def test_02_alias_resolution(self):
        for alias, canonical in ROLE_ALIASES.items():
            self.assertEqual(resolve_role_id(alias), canonical)

    def test_03_planned_role_passthrough(self):
        for rid in get_planned_roles():
            result = resolve_role_id(rid)
            self.assertEqual(result, rid, f"Planned role {rid} should pass through as-is")

    def test_04_unknown_role_passthrough(self):
        unknown = "nonexistent-role"
        self.assertEqual(resolve_role_id(unknown), unknown)

    def test_05_empty_string(self):
        self.assertEqual(resolve_role_id(""), "")

    def test_06_case_sensitivity(self):
        self.assertNotEqual(resolve_role_id("PM"), "product-manager")
        self.assertNotEqual(resolve_role_id("Coder"), "solo-coder")


class TestRoleCompleteness(unittest.TestCase):
    """Verify all CLI roles can be resolved to valid templates or planned roles."""

    CLI_ROLES = [
        "architect", "pm", "coder", "tester", "ui",
        "devops", "security", "data", "reviewer", "optimizer",
    ]

    def test_01_all_cli_roles_resolvable(self):
        for cli_role in self.CLI_ROLES:
            resolved = resolve_role_id(cli_role)
            is_core = resolved in ROLE_TEMPLATES
            is_planned = resolved in PLANNED_ROLES
            self.assertTrue(
                is_core or is_planned,
                f"CLI role '{cli_role}' resolves to '{resolved}' which is neither core nor planned"
            )

    def test_02_core_roles_count(self):
        self.assertEqual(len(get_core_roles()), 5, "Should have exactly 5 core roles with prompt templates")

    def test_03_planned_roles_count(self):
        self.assertEqual(len(get_planned_roles()), 5, "Should have exactly 5 planned roles")

    def test_04_total_roles_match_cli(self):
        total = len(ROLE_REGISTRY)
        self.assertGreaterEqual(total, len(self.CLI_ROLES),
                                f"Registry({total}) should cover all {len(self.CLI_ROLES)} CLI roles")


class TestDispatchWithAliasedRoles(unittest.TestCase):
    """Integration test: dispatch() with aliased role IDs."""

    def setUp(self):
        self.dispatcher = MultiAgentDispatcher()

    def tearDown(self):
        self.dispatcher.shutdown()

    def test_01_dispatch_with_short_ids(self):
        result = self.dispatcher.dispatch(
            task_description="Test task",
            roles=["pm", "coder", "ui"],
            dry_run=True,
        )
        self.assertTrue(result.success)
        self.assertIn("product-manager", result.matched_roles)
        self.assertIn("solo-coder", result.matched_roles)
        self.assertIn("ui-designer", result.matched_roles)

    def test_02_dispatch_with_mixed_ids(self):
        result = self.dispatcher.dispatch(
            task_description="Test task",
            roles=["architect", "pm", "tester"],
            dry_run=True,
        )
        self.assertTrue(result.success)
        self.assertIn("architect", result.matched_roles)
        self.assertIn("product-manager", result.matched_roles)
        self.assertIn("tester", result.matched_roles)

    def test_03_dispatch_with_planned_role(self):
        result = self.dispatcher.dispatch(
            task_description="Test task",
            roles=["devops", "security"],
            dry_run=True,
        )
        self.assertTrue(result.success)
        self.assertIn("devops", result.matched_roles)
        self.assertIn("security", result.matched_roles)

    def test_04_dispatch_with_all_cli_roles(self):
        all_roles = ["architect", "pm", "coder", "tester", "ui",
                     "devops", "security", "data", "reviewer", "optimizer"]
        result = self.dispatcher.dispatch(
            task_description="Test task",
            roles=all_roles,
            dry_run=True,
        )
        self.assertTrue(result.success)
        self.assertEqual(len(result.matched_roles), 10)


class TestRoleTemplateIntegrity(unittest.TestCase):
    """Verify each core role has required fields."""

    def test_01_all_core_roles_have_required_fields(self):
        required_fields = {"name", "prompt", "keywords"}
        for rid, template in ROLE_TEMPLATES.items():
            missing = required_fields - set(template.keys())
            self.assertEqual(missing, set(),
                             f"Core role '{rid}' missing fields: {missing}")

    def test_02_all_core_roles_have_non_empty_prompt(self):
        for rid in get_core_roles():
            rdef = ROLE_REGISTRY[rid]
            self.assertTrue(len(rdef.prompt) > 0,
                            f"Core role '{rid}' has empty prompt template")

    def test_03_all_core_roles_have_keywords(self):
        for rid in get_core_roles():
            rdef = ROLE_REGISTRY[rid]
            self.assertTrue(len(rdef.keywords) > 0,
                            f"Core role '{rid}' has no keywords defined")

    def test_04_all_planned_roles_have_status_planned(self):
        for rid, rdef in get_planned_roles().items():
            self.assertEqual(rdef.status, "planned",
                             f"Planned role '{rid}' status should be 'planned'")


if __name__ == "__main__":
    unittest.main(verbosity=2)
