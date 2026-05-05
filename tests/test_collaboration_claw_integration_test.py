#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WorkBuddy (Claw) Integration Test Suite

Tests per WORKBUDDY_CLAW_INTEGRATION_SPEC.md Section 5:
  Plan A: Memory Bridge (T-A01 ~ T-A08)
  Plan B: News Feed (T-B01 ~ T-B04)
  Diagnostics (T-D01 ~ T-D02)

All tests use real Claw path when available, graceful degrade otherwise.
"""

import os
import sys
import unittest
from datetime import datetime
from typing import List, Dict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from scripts.collaboration.memory_bridge import (
    WorkBuddyClawSource,
    MemoryBridge,
    MemoryQuery,
    MemoryType,
    MemoryStats,
    MemoryItem,
)


class TestClawSourceAvailability(unittest.TestCase):
    """T-A01/T-A02: Claw source availability detection"""

    def test_default_path_exists(self):
        source = WorkBuddyClawSource()
        if source.is_available:
            self.assertTrue(source.base_path.exists())
        else:
            self.assertFalse(source.is_available)

    def test_custom_nonexistent_path(self):
        source = WorkBuddyClawSource(base_path="/nonexistent/path/that/does/not/exist")
        self.assertFalse(source.is_available)

    def test_graceful_degrade_on_missing(self):
        source = WorkBuddyClawSource(base_path="/tmp/fake_claw_xyz")
        items = source.load_all_memories()
        self.assertIsInstance(items, list)
        self.assertEqual(len(items), 0)


class TestClawCoreMemories(unittest.TestCase):
    """T-A03: Load core memory files"""

    def setUp(self):
        self.source = WorkBuddyClawSource()

    @unittest.skipUnless(
        WorkBuddyClawSource().is_available,
        "Claw directory not available"
    )
    def test_load_core_memories_returns_items(self):
        core = self.source._load_core_memories()
        self.assertGreaterEqual(len(core), 2,
                                "Should have at least SOUL.md + USER.md")

    @unittest.skipUnless(
        WorkBuddyClawSource().is_available,
        "Claw directory not available"
    )
    def test_core_memory_types_are_valid(self):
        core = self.source._load_core_memories()
        valid_types = {MemoryType.SEMANTIC, MemoryType.KNOWLEDGE,
                       MemoryType.EPISODIC, MemoryType.PATTERN}
        for item in core:
            self.assertIn(item.memory_type, valid_types)

    @unittest.skipUnless(
        WorkBuddyClawSource().is_available,
        "Claw directory not available"
    )
    def test_core_memory_has_source_tag(self):
        core = self.source._load_core_memories()
        for item in core:
            self.assertEqual(item.source, "workbuddy-claw")


class TestClawDailyMemories(unittest.TestCase):
    """T-A04: Load daily work memories"""

    def setUp(self):
        self.source = WorkBuddyClawSource()

    @unittest.skipUnless(
        WorkBuddyClawSource().is_available,
        "Claw directory not available"
    )
    def test_daily_memories_exist(self):
        daily = self.source._load_workbuddy_daily_memories()
        self.assertGreater(len(daily), 0,
                           "Should have at least some daily log files")

    @unittest.skipUnless(
        WorkBuddyClawSource().is_available,
        "Claw directory not available"
    )
    def test_daily_memories_limited_to_30(self):
        daily = self.source._load_workbuddy_daily_memories()
        self.assertLessEqual(len(daily), 30)

    @unittest.skipUnless(
        WorkBuddyClawSource().is_available,
        "Claw directory not available"
    )
    def test_daily_memory_ids_have_date_prefix(self):
        daily = self.source._load_workbuddy_daily_memories()
        if daily:
            self.assertTrue(daily[0].id.startswith("wb-daily-"))


class TestClawIndexSearch(unittest.TestCase):
    """T-A05/T-A06: INDEX-based search"""

    def setUp(self):
        self.source = WorkBuddyClawSource()

    @unittest.skipUnless(
        WorkBuddyClawSource().is_available,
        "Claw directory not available"
    )
    def test_index_search_returns_results(self):
        results = self.source.search_by_index("\u590d\u65e6", limit=5)
        if results:
            self.assertIsInstance(results[0], MemoryItem)

    @unittest.skipUnless(
        WorkBuddyClawSource().is_available,
        "Claw directory not available"
    )
    def test_index_search_respects_limit(self):
        results = self.source.search_by_index("user", limit=2)
        self.assertLessEqual(len(results), 2)

    def test_fallback_search_on_missing_index(self):
        fake_source = WorkBuddyClawSource(base_path="/tmp/fake_claw")
        results = fake_source.search_by_index("anything", limit=3)
        self.assertEqual(len(results), 0)

    def test_empty_query_returns_empty(self):
        source = WorkBuddyClawSource(base_path="/tmp/fake")
        results = source.search_by_index("", limit=5)
        self.assertEqual(len(results), 0)


class TestClawRecallIntegration(unittest.TestCase):
    """T-A07/T-A08: recall() integration with Claw"""

    def setUp(self):
        self.bridge = MemoryBridge()

    def tearDown(self):
        try:
            self.bridge.shutdown()
        except Exception:
            pass

    def test_recall_works_without_claw(self):
        query = MemoryQuery(query_text="test query about microservices")
        result = self.bridge.recall(query)
        self.assertIsNotNone(result)
        self.assertIsInstance(result.memories, list)

    @unittest.skipUnless(
        WorkBuddyClawSource().is_available,
        "Claw directory not available"
    )
    def test_recall_with_claw_includes_claw_items(self):
        query = MemoryQuery(query_text="test", limit=20)
        result = self.bridge.recall(query)
        self.assertIsNotNone(result)
        if self.bridge._claw_enabled:
            all_claw = self.bridge._claw_source.load_all_memories()
            self.assertGreater(len(all_claw), 0,
                               "Claw source should have items when enabled")


class TestClawAINewsFeed(unittest.TestCase):
    """T-B01~T-B04: AI News feed functionality"""

    def setUp(self):
        self.source = WorkBuddyClawSource()

    def test_news_feed_returns_list(self):
        news = self.source.get_latest_ai_news(days=7)
        self.assertIsInstance(news, list)

    @unittest.skipUnless(
        WorkBuddyClawSource().is_available,
        "Claw directory not available"
    )
    def test_news_feed_has_content_when_available(self):
        news = self.source.get_latest_ai_news(days=30)
        if news:
            first = news[0]
            self.assertTrue(first.id.startswith("wb-news-"))
            self.assertEqual(first.domain, "ai-news")
            self.assertIn("sources", first.metadata or {})

    def test_news_date_filtering(self):
        news = self.source.get_latest_ai_news(days=1)
        if news:
            cutoff = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            for item in news:
                date_str = item.id.replace("wb-news-", "")
                try:
                    item_date = datetime.strptime(date_str, "%Y%m%d")
                    self.assertGreaterEqual(item_date.date(), cutoff.date())
                except ValueError:
                    pass

    def test_news_missing_file_returns_empty(self):
        fake = WorkBuddyClawSource(base_path="/tmp/no_automation_here")
        news = fake.get_latest_ai_news(days=7)
        self.assertEqual(news, [])

    @unittest.skipUnless(
        WorkBuddyClawSource().is_available,
        "Claw directory not available"
    )
    def test_bridge_ai_news_method(self):
        bridge = MemoryBridge()
        try:
            news = bridge.get_workbuddy_ai_news(7)
            self.assertIsInstance(news, list)
        finally:
            try:
                bridge.shutdown()
            except Exception:
                pass


class TestClawDiagnostics(unittest.TestCase):
    """T-D01/T-D02: Diagnostics and statistics"""

    def test_diagnostics_contains_claw_section(self):
        bridge = MemoryBridge()
        try:
            diag = bridge.print_diagnostics()
            self.assertIn("WorkBuddy (Claw) Bridge", diag)
            if bridge._claw_enabled:
                self.assertIn("Available: Yes", diag)
            else:
                self.assertIn("Available: No", diag)
        finally:
            try:
                bridge.shutdown()
            except Exception:
                pass

    def test_statistics_contains_claw_fields(self):
        bridge = MemoryBridge()
        try:
            stats = bridge.get_statistics()
            self.assertIsInstance(stats.claw_enabled, bool)
            self.assertIsInstance(stats.claw_item_count, int)
            if stats.claw_enabled:
                self.assertGreater(stats.claw_item_count, 0)
        finally:
            try:
                bridge.shutdown()
            except Exception:
                pass


class TestClawExtractTags(unittest.TestCase):
    """Utility method tests"""

    def test_extract_tags_chinese(self):
        tags = WorkBuddyClawSource._extract_tags(
            "\u8fd9\u662f\u4e00\u4e2a\u6d4b\u8bd5\u6587\u672c\uff0c\u542b\u6709Python\u548cAI\u5173\u952e\u8bcd"
        )
        self.assertTrue(len(tags) > 0, "Should extract at least one Chinese tag")

    def test_extract_tags_english(self):
        tags = WorkBuddyClawSource._extract_tags(
            "This is a test text with Python and machine learning keywords"
        )
        self.assertTrue(any("python" in t.lower() for t in tags))

    def test_extract_tags_limit(self):
        long_text = "word" * 100
        tags = WorkBuddyClawSource._extract_tags(long_text)
        self.assertLessEqual(len(tags), 15)


class TestClawExtractSection(unittest.TestCase):
    """Section extraction tests"""

    def test_extract_existing_section(self):
        content = "# Main\n\n## Background\nSome background info\n\n## Details\nMore details\n"
        result = WorkBuddyClawSource._extract_section(content, "Background")
        self.assertIsNotNone(result)
        self.assertIn("background", result.lower())

    def test_extract_missing_section(self):
        content = "# Main\n## Background\nInfo\n"
        result = WorkBuddyClawSource._extract_section(content, "NonExistent")
        self.assertIsNone(result)

    def test_extract_empty_content(self):
        result = WorkBuddyClawSource._extract_section("", "Any")
        self.assertIsNone(result)


class TestClawParseAutomationLog(unittest.TestCase):
    """Automation log parsing tests"""

    def test_parse_standard_format(self):
        content = (
            "## 2026-04-17 08:00\n"
            "**\u6267\u884c\u72b6\u6001**: \u6210\u529f\n"
            "**\u4fe1\u606f\u6765\u6e90**: gaovi.com, web_search\n"
            "**\u63a8\u9001\u6761\u6570**: 5\n"
            "**\u6838\u5fc3\u4e3b\u9898**:\n"
            "- Topic A\n"
            "- Topic B\n"
            "**\u5907\u6ce8**: Test notes\n"
            "\n"
            "## 2026-04-16 08:00\n"
            "**\u6267\u884c\u72b6\u6001**: \u6210\u529f\n"
            "**\u4fe1\u606f\u6765\u6e90**: other.com\n"
        )
        source = WorkBuddyClawSource(base_path="/tmp/fake_for_test")
        entries = source._parse_automation_log(content)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["date"].strftime("%Y-%m-%d"), "2026-04-17")
        self.assertTrue(any("gaovi" in s for s in entries[0]["sources"]))
        self.assertEqual(entries[0]["status"], "\u6210\u529f")

    def test_parse_empty_content(self):
        source = WorkBuddyClawSource(base_path="/tmp/fake_for_test")
        entries = source._parse_automation_log("")
        self.assertEqual(entries, [])

    def test_parse_no_dates(self):
        content = "Just some text without date headers\nMore text\n"
        source = WorkBuddyClawSource(base_path="/tmp/fake_for_test")
        entries = source._parse_automation_log(content)
        self.assertEqual(entries, [])


class TestClawLoadAllMemories(unittest.TestCase):
    """Full load test"""

    def test_load_all_combines_core_and_daily(self):
        source = WorkBuddyClawSource()
        if source.is_available:
            all_items = source.load_all_memories()
            core_count = len(source._load_core_memories())
            daily_count = len(source._load_workbuddy_daily_memories())
            self.assertEqual(len(all_items), core_count + daily_count)

    def test_all_items_tagged_with_source(self):
        source = WorkBuddyClawSource()
        if source.is_available:
            all_items = source.load_all_memories()
            for item in all_items:
                self.assertEqual(item.source, "workbuddy-claw")


def run_all_tests():
    suite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.testsRun - len(result.failures) - len(result.errors)


if __name__ == "__main__":
    passed = run_all_tests()
    total = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__]).countTestCases()
    print(f"\n{'='*60}")
    print(f"WorkBuddy Claw Integration Test Results: {passed}/{total} passed")
    if passed == total:
        print("ALL CLAW INTEGRATION TESTS PASSED!")
    print(f"{'='*60}")
