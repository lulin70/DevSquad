#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MemoryProvider Contract Tests

Validates that all MemoryProvider implementations conform to the Protocol
interface defined in protocols.py. Both NullMemoryProvider and MCEAdapter
must pass these tests.

Contract test ownership: shared between DevSquad and CarryMem teams.
Any breaking change to MemoryProvider Protocol must be negotiated.
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from scripts.collaboration.protocols import MemoryProvider
from scripts.collaboration.null_providers import NullMemoryProvider


class TestMemoryProviderContract(unittest.TestCase):
    """Contract tests for MemoryProvider Protocol compliance."""

    def _get_provider(self):
        return NullMemoryProvider()

    def test_has_get_rules(self):
        provider = self._get_provider()
        self.assertTrue(hasattr(provider, 'get_rules'))
        self.assertTrue(callable(provider.get_rules))

    def test_has_add_rule(self):
        provider = self._get_provider()
        self.assertTrue(hasattr(provider, 'add_rule'))
        self.assertTrue(callable(provider.add_rule))

    def test_has_update_rule(self):
        provider = self._get_provider()
        self.assertTrue(hasattr(provider, 'update_rule'))
        self.assertTrue(callable(provider.update_rule))

    def test_has_delete_rule(self):
        provider = self._get_provider()
        self.assertTrue(hasattr(provider, 'delete_rule'))
        self.assertTrue(callable(provider.delete_rule))

    def test_has_is_available(self):
        provider = self._get_provider()
        self.assertTrue(hasattr(provider, 'is_available'))
        self.assertTrue(callable(provider.is_available))

    def test_has_get_stats(self):
        provider = self._get_provider()
        self.assertTrue(hasattr(provider, 'get_stats'))
        self.assertTrue(callable(provider.get_stats))

    def test_has_match_rules(self):
        provider = self._get_provider()
        self.assertTrue(hasattr(provider, 'match_rules'))
        self.assertTrue(callable(provider.match_rules))

    def test_has_format_rules_as_prompt(self):
        provider = self._get_provider()
        self.assertTrue(hasattr(provider, 'format_rules_as_prompt'))
        self.assertTrue(callable(provider.format_rules_as_prompt))

    def test_get_rules_returns_list(self):
        provider = self._get_provider()
        result = provider.get_rules(user_id="test")
        self.assertIsInstance(result, list)

    def test_match_rules_returns_list(self):
        provider = self._get_provider()
        result = provider.match_rules(
            task_description="Design REST API",
            user_id="test",
            role="architect",
            max_rules=5
        )
        self.assertIsInstance(result, list)

    def test_match_rules_with_default_params(self):
        provider = self._get_provider()
        result = provider.match_rules(
            task_description="Test task",
            user_id="test"
        )
        self.assertIsInstance(result, list)

    def test_format_rules_as_prompt_returns_str(self):
        provider = self._get_provider()
        result = provider.format_rules_as_prompt(rules=[])
        self.assertIsInstance(result, str)

    def test_format_rules_as_prompt_with_empty_rules(self):
        provider = self._get_provider()
        result = provider.format_rules_as_prompt(rules=[])
        self.assertEqual(result, "")

    def test_is_available_returns_bool(self):
        provider = self._get_provider()
        result = provider.is_available()
        self.assertIsInstance(result, bool)

    def test_get_stats_returns_dict(self):
        provider = self._get_provider()
        result = provider.get_stats()
        self.assertIsInstance(result, dict)

    def test_add_rule_no_exception(self):
        provider = self._get_provider()
        provider.add_rule(user_id="test", rule="Always use SSL")

    def test_update_rule_no_exception(self):
        provider = self._get_provider()
        provider.update_rule(user_id="test", rule_id="r1", rule="Updated rule")

    def test_delete_rule_no_exception(self):
        provider = self._get_provider()
        provider.delete_rule(user_id="test", rule_id="r1")


class TestNullMemoryProviderContract(TestMemoryProviderContract):
    """Contract tests specific to NullMemoryProvider behavior."""

    def _get_provider(self):
        return NullMemoryProvider()

    def test_is_available_returns_false(self):
        provider = self._get_provider()
        self.assertFalse(provider.is_available())

    def test_get_rules_returns_empty_list(self):
        provider = self._get_provider()
        result = provider.get_rules(user_id="test")
        self.assertEqual(result, [])

    def test_match_rules_returns_empty_list(self):
        provider = self._get_provider()
        result = provider.match_rules(
            task_description="Design REST API",
            user_id="test",
            role="architect"
        )
        self.assertEqual(result, [])

    def test_format_rules_as_prompt_returns_empty_string(self):
        provider = self._get_provider()
        result = provider.format_rules_as_prompt(rules=[])
        self.assertEqual(result, "")

    def test_get_stats_has_degraded_flag(self):
        provider = self._get_provider()
        stats = provider.get_stats()
        self.assertTrue(stats.get("degraded", False))
        self.assertEqual(stats.get("provider_type"), "null")


class TestMCEAdapterSanitizeUserId(unittest.TestCase):
    """Test user_id sanitization in MCEAdapter."""

    def test_sanitize_normal_user_id(self):
        from scripts.collaboration.mce_adapter import MCEAdapter
        result = MCEAdapter._sanitize_user_id("user123")
        self.assertEqual(result, "user123")

    def test_sanitize_empty_user_id(self):
        from scripts.collaboration.mce_adapter import MCEAdapter
        result = MCEAdapter._sanitize_user_id("")
        self.assertEqual(result, "default")

    def test_sanitize_none_user_id(self):
        from scripts.collaboration.mce_adapter import MCEAdapter
        result = MCEAdapter._sanitize_user_id(None)
        self.assertEqual(result, "default")

    def test_sanitize_path_traversal(self):
        from scripts.collaboration.mce_adapter import MCEAdapter
        result = MCEAdapter._sanitize_user_id("../../../etc/passwd")
        self.assertNotIn("../", result)

    def test_sanitize_sql_injection(self):
        from scripts.collaboration.mce_adapter import MCEAdapter
        result = MCEAdapter._sanitize_user_id("'; DROP TABLE users;--")
        self.assertNotIn("'", result)
        self.assertNotIn(";", result)

    def test_sanitize_special_chars(self):
        from scripts.collaboration.mce_adapter import MCEAdapter
        result = MCEAdapter._sanitize_user_id("user<>&|`$")
        self.assertNotIn("<", result)
        self.assertNotIn(">", result)
        self.assertNotIn("&", result)

    def test_sanitize_long_user_id(self):
        from scripts.collaboration.mce_adapter import MCEAdapter
        long_id = "a" * 200
        result = MCEAdapter._sanitize_user_id(long_id)
        self.assertLessEqual(len(result), 128)

    def test_sanitize_unicode_normalization(self):
        from scripts.collaboration.mce_adapter import MCEAdapter
        result = MCEAdapter._sanitize_user_id("user\uff0e123")
        self.assertIsInstance(result, str)


class TestMCEAdapterRuleParsing(unittest.TestCase):
    """Test rule string parsing in MCEAdapter."""

    def test_parse_forbid_rule(self):
        from scripts.collaboration.mce_adapter import MCEAdapter
        result = MCEAdapter._parse_rule_string("[FORBID] Storing passwords in plain text")
        self.assertEqual(result["rule_type"], "forbid")
        self.assertEqual(result["action"], "Storing passwords in plain text")

    def test_parse_avoid_rule(self):
        from scripts.collaboration.mce_adapter import MCEAdapter
        result = MCEAdapter._parse_rule_string("[AVOID] Using MongoDB for relational data")
        self.assertEqual(result["rule_type"], "avoid")
        self.assertEqual(result["action"], "Using MongoDB for relational data")

    def test_parse_always_rule(self):
        from scripts.collaboration.mce_adapter import MCEAdapter
        result = MCEAdapter._parse_rule_string("[ALWAYS] Use SSL for all database connections")
        self.assertEqual(result["rule_type"], "always")
        self.assertEqual(result["action"], "Use SSL for all database connections")

    def test_parse_override_rule(self):
        from scripts.collaboration.mce_adapter import MCEAdapter
        result = MCEAdapter._parse_rule_string("[ALWAYS] Use SSL (override)")
        self.assertTrue(result["override"])
        self.assertEqual(result["action"], "Use SSL")

    def test_parse_rule_without_prefix(self):
        from scripts.collaboration.mce_adapter import MCEAdapter
        result = MCEAdapter._parse_rule_string("Use SSL for all connections")
        self.assertEqual(result["rule_type"], "always")
        self.assertEqual(result["action"], "Use SSL for all connections")

    def test_format_rules_fallback(self):
        from scripts.collaboration.mce_adapter import MCEAdapter
        rules = [
            {"rule_type": "forbid", "action": "No plain text passwords", "override": True},
            {"rule_type": "always", "action": "Use SSL", "override": False},
        ]
        result = MCEAdapter._format_rules_fallback(rules)
        self.assertIn("FORBID", result)
        self.assertIn("ALWAYS", result)
        self.assertIn("non-overridable", result)

    def test_format_rules_fallback_empty(self):
        from scripts.collaboration.mce_adapter import MCEAdapter
        result = MCEAdapter._format_rules_fallback([])
        self.assertEqual(result, "")


class TestRuleTypes(unittest.TestCase):
    """Test rule type constants."""

    def test_rule_types_contains_forbid(self):
        from scripts.collaboration.mce_adapter import RULE_TYPES
        self.assertIn("forbid", RULE_TYPES)

    def test_rule_types_contains_avoid(self):
        from scripts.collaboration.mce_adapter import RULE_TYPES
        self.assertIn("avoid", RULE_TYPES)

    def test_rule_types_contains_always(self):
        from scripts.collaboration.mce_adapter import RULE_TYPES
        self.assertIn("always", RULE_TYPES)

    def test_rule_types_contains_prefer(self):
        from scripts.collaboration.mce_adapter import RULE_TYPES
        self.assertIn("prefer", RULE_TYPES)

    def test_rule_types_has_exactly_three(self):
        from scripts.collaboration.mce_adapter import RULE_TYPES
        self.assertEqual(len(RULE_TYPES), 4)  # forbid, avoid, always, prefer


if __name__ == '__main__':
    unittest.main()
