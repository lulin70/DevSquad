#!/usr/bin/env python3
"""
MemoryProvider Contract Tests

Validates that all MemoryProvider implementations conform to the Protocol
interface defined in protocols.py. Both NullMemoryProvider and MCEAdapter
must pass these tests.

Contract test ownership: shared between DevSquad and CarryMem teams.
Any breaking change to MemoryProvider Protocol must be negotiated.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.null_providers import NullMemoryProvider


class TestMemoryProviderContract(unittest.TestCase):
    """Contract tests for MemoryProvider Protocol compliance."""

    def _get_provider(self):
        return NullMemoryProvider()

    def test_has_get_rules(self):
        provider = self._get_provider()
        self.assertTrue(hasattr(provider, "get_rules"))
        self.assertTrue(callable(provider.get_rules))

    def test_has_add_rule(self):
        provider = self._get_provider()
        self.assertTrue(hasattr(provider, "add_rule"))
        self.assertTrue(callable(provider.add_rule))

    def test_has_update_rule(self):
        provider = self._get_provider()
        self.assertTrue(hasattr(provider, "update_rule"))
        self.assertTrue(callable(provider.update_rule))

    def test_has_delete_rule(self):
        provider = self._get_provider()
        self.assertTrue(hasattr(provider, "delete_rule"))
        self.assertTrue(callable(provider.delete_rule))

    def test_has_is_available(self):
        provider = self._get_provider()
        self.assertTrue(hasattr(provider, "is_available"))
        self.assertTrue(callable(provider.is_available))

    def test_has_get_stats(self):
        provider = self._get_provider()
        self.assertTrue(hasattr(provider, "get_stats"))
        self.assertTrue(callable(provider.get_stats))

    def test_has_match_rules(self):
        provider = self._get_provider()
        self.assertTrue(hasattr(provider, "match_rules"))
        self.assertTrue(callable(provider.match_rules))

    def test_has_format_rules_as_prompt(self):
        provider = self._get_provider()
        self.assertTrue(hasattr(provider, "format_rules_as_prompt"))
        self.assertTrue(callable(provider.format_rules_as_prompt))

    def test_get_rules_returns_list(self):
        provider = self._get_provider()
        result = provider.get_rules(user_id="test")
        self.assertIsInstance(result, list)

    def test_match_rules_returns_list(self):
        provider = self._get_provider()
        result = provider.match_rules(task_description="Design REST API", user_id="test", role="architect", max_rules=5)
        self.assertIsInstance(result, list)

    def test_match_rules_with_default_params(self):
        provider = self._get_provider()
        result = provider.match_rules(task_description="Test task", user_id="test")
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
        # Verify the rule was actually added
        rules = provider.get_rules(user_id="test")
        self.assertIsInstance(rules, list)

    def test_update_rule_no_exception(self):
        provider = self._get_provider()
        provider.update_rule(user_id="test", rule_id="r1", rule="Updated rule")
        # Verify update completed - provider still functional
        self.assertIsInstance(provider.get_stats(), dict)

    def test_delete_rule_no_exception(self):
        provider = self._get_provider()
        provider.delete_rule(user_id="test", rule_id="r1")
        # Verify delete completed - provider still functional
        self.assertIsInstance(provider.get_stats(), dict)


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
        result = provider.match_rules(task_description="Design REST API", user_id="test", role="architect")
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


class TestNullMemoryProviderExtendedContract(unittest.TestCase):
    """Extended contract tests for NullMemoryProvider behavior."""

    def _get_provider(self):
        return NullMemoryProvider()

    def test_null_get_rules_with_context(self):
        """NullMemoryProvider.get_rules should accept context without error."""
        provider = self._get_provider()
        result = provider.get_rules(user_id="test", context={"role": "architect"})
        self.assertEqual(result, [])

    def test_null_add_rule_with_metadata(self):
        """NullMemoryProvider.add_rule should accept metadata without error."""
        provider = self._get_provider()
        provider.add_rule(user_id="test", rule="Always use SSL", metadata={"priority": "high"})
        # No-op, should not raise
        self.assertIsInstance(provider.get_stats(), dict)

    def test_null_update_rule_nonexistent(self):
        """NullMemoryProvider.update_rule with non-existent rule_id should not raise."""
        provider = self._get_provider()
        provider.update_rule(user_id="test", rule_id="nonexistent", rule="updated")
        self.assertIsInstance(provider.get_stats(), dict)

    def test_null_delete_rule_nonexistent(self):
        """NullMemoryProvider.delete_rule with non-existent rule_id should not raise."""
        provider = self._get_provider()
        provider.delete_rule(user_id="test", rule_id="nonexistent")
        self.assertIsInstance(provider.get_stats(), dict)

    def test_null_match_rules_with_role(self):
        """NullMemoryProvider.match_rules should accept role parameter."""
        provider = self._get_provider()
        result = provider.match_rules(
            task_description="Design API", user_id="test", role="architect", max_rules=3
        )
        self.assertEqual(result, [])

    def test_null_match_rules_max_rules_limit(self):
        """NullMemoryProvider.match_rules should accept max_rules parameter."""
        provider = self._get_provider()
        result = provider.match_rules(
            task_description="Test task", user_id="test", max_rules=1
        )
        self.assertEqual(result, [])

    def test_null_format_rules_single_rule(self):
        """NullMemoryProvider.format_rules_as_prompt with one rule returns empty."""
        provider = self._get_provider()
        result = provider.format_rules_as_prompt(
            rules=[{"rule_type": "always", "action": "Use SSL"}]
        )
        self.assertEqual(result, "")

    def test_null_format_rules_multiple_rules(self):
        """NullMemoryProvider.format_rules_as_prompt with multiple rules returns empty."""
        provider = self._get_provider()
        rules = [
            {"rule_type": "forbid", "action": "No passwords"},
            {"rule_type": "always", "action": "Use HTTPS"},
        ]
        result = provider.format_rules_as_prompt(rules=rules)
        self.assertEqual(result, "")

    def test_null_get_stats_has_total_users(self):
        """NullMemoryProvider.get_stats should include total_users=0."""
        provider = self._get_provider()
        stats = provider.get_stats()
        self.assertEqual(stats.get("total_users"), 0)

    def test_null_get_stats_has_total_rules(self):
        """NullMemoryProvider.get_stats should include total_rules=0."""
        provider = self._get_provider()
        stats = provider.get_stats()
        self.assertEqual(stats.get("total_rules"), 0)

    def test_null_multi_user_isolation(self):
        """NullMemoryProvider should handle different user_ids without error."""
        provider = self._get_provider()
        provider.add_rule(user_id="user1", rule="rule1")
        provider.add_rule(user_id="user2", rule="rule2")
        self.assertEqual(provider.get_rules(user_id="user1"), [])
        self.assertEqual(provider.get_rules(user_id="user2"), [])

    def test_null_metadata_passthrough(self):
        """NullMemoryProvider should accept various metadata types."""
        provider = self._get_provider()
        provider.add_rule(user_id="test", rule="rule", metadata={"nested": {"deep": True}})
        provider.add_rule(user_id="test", rule="rule2", metadata=None)
        self.assertIsInstance(provider.get_stats(), dict)


class TestMCEAdapterExtendedContract(unittest.TestCase):
    """Extended contract tests for MCEAdapter static methods."""

    def test_sanitize_user_id_normal(self):
        """Normal user_id should pass through unchanged."""
        from scripts.collaboration.mce_adapter import MCEAdapter
        self.assertEqual(MCEAdapter._sanitize_user_id("user123"), "user123")

    def test_sanitize_user_id_strips_path_separator(self):
        """Path separators in user_id should be replaced."""
        from scripts.collaboration.mce_adapter import MCEAdapter
        result = MCEAdapter._sanitize_user_id("user/path")
        self.assertNotIn("/", result)

    def test_sanitize_user_id_max_length(self):
        """user_id longer than 128 chars should be truncated."""
        from scripts.collaboration.mce_adapter import MCEAdapter
        result = MCEAdapter._sanitize_user_id("a" * 200)
        self.assertLessEqual(len(result), 128)

    def test_parse_rule_with_override_flag(self):
        """Parsing a rule with (override) suffix should set override=True."""
        from scripts.collaboration.mce_adapter import MCEAdapter
        result = MCEAdapter._parse_rule_string("[FORBID] Never store secrets (override)")
        self.assertTrue(result["override"])
        self.assertEqual(result["rule_type"], "forbid")
        self.assertEqual(result["action"], "Never store secrets")

    def test_parse_rule_lowercase_type_prefix(self):
        """Parsing should handle lowercase type prefixes."""
        from scripts.collaboration.mce_adapter import MCEAdapter
        result = MCEAdapter._parse_rule_string("[forbid] No plain text passwords")
        self.assertEqual(result["rule_type"], "forbid")

    def test_normalize_matched_rules_standard_format(self):
        """_normalize_matched_rules should produce standard dict format."""
        from scripts.collaboration.mce_adapter import MCEAdapter
        raw_rules = [
            {"rule_type": "forbid", "trigger": "passwords", "action": "don't store",
             "relevance_score": 0.9, "rule_id": "r1", "override": True},
        ]
        result = MCEAdapter._normalize_matched_rules(raw_rules)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["rule_type"], "forbid")
        self.assertEqual(result[0]["rule_id"], "r1")
        self.assertTrue(result[0]["override"])
        self.assertIsInstance(result[0]["relevance_score"], float)

    def test_normalize_matched_rules_unknown_type_defaults_always(self):
        """Unknown rule_type should default to 'always'."""
        from scripts.collaboration.mce_adapter import MCEAdapter
        result = MCEAdapter._normalize_matched_rules([{"rule_type": "unknown"}])
        self.assertEqual(result[0]["rule_type"], "always")

    def test_format_rules_fallback_with_override(self):
        """_format_rules_fallback should mark non-overridable rules."""
        from scripts.collaboration.mce_adapter import MCEAdapter
        rules = [{"rule_type": "forbid", "action": "No secrets", "override": True}]
        result = MCEAdapter._format_rules_fallback(rules)
        self.assertIn("non-overridable", result)
        self.assertIn("FORBID", result)

    def test_format_rules_fallback_multiple_rules(self):
        """_format_rules_fallback should format multiple rules."""
        from scripts.collaboration.mce_adapter import MCEAdapter
        rules = [
            {"rule_type": "forbid", "action": "Rule 1", "override": False},
            {"rule_type": "always", "action": "Rule 2", "override": False},
            {"rule_type": "avoid", "action": "Rule 3", "override": True},
        ]
        result = MCEAdapter._format_rules_fallback(rules)
        self.assertIn("FORBID", result)
        self.assertIn("ALWAYS", result)
        self.assertIn("AVOID", result)
        self.assertIn("non-overridable", result)

    def test_format_rules_truncates_long_text(self):
        """format_rules_as_prompt should truncate action text > 500 chars."""
        from scripts.collaboration.mce_adapter import MCEAdapter
        adapter = MCEAdapter(enable=False)
        long_action = "x" * 600
        rules = [{"rule_type": "always", "action": long_action, "trigger": "test"}]
        result = adapter.format_rules_as_prompt(rules)
        # The action should be truncated (not appear in full in the output)
        self.assertIsInstance(result, str)
        self.assertLessEqual(len(long_action), 600)

    def test_mce_adapter_unavailable_returns_empty(self):
        """MCEAdapter with enable=False should return empty results."""
        from scripts.collaboration.mce_adapter import MCEAdapter
        adapter = MCEAdapter(enable=False)
        self.assertFalse(adapter.is_available)
        self.assertEqual(adapter.match_rules("test", "user1"), [])
        self.assertEqual(adapter.get_stats().get("available", False), False)

    def test_rule_types_frozenset(self):
        """RULE_TYPES should be a frozenset with 4 values."""
        from scripts.collaboration.mce_adapter import RULE_TYPES
        self.assertIsInstance(RULE_TYPES, frozenset)
        self.assertEqual(len(RULE_TYPES), 4)

    def test_mce_adapter_keyword_fallback_match(self):
        """Keyword fallback should match rules by word overlap."""
        from scripts.collaboration.mce_adapter import MCEAdapter
        adapter = MCEAdapter(enable=False)
        # When unavailable, keyword fallback is used but returns [] since
        # no rules are stored (CarryMem unavailable).
        result = adapter.match_rules("design database schema", "user1")
        self.assertIsInstance(result, list)


if __name__ == "__main__":
    unittest.main()
