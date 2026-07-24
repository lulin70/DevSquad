#!/usr/bin/env python3
"""DualLayerContextManager + MemoryBridge + MCEAdapter Integration Tests
(V4.2.1 P2-3 — Test Pyramid Lift).

End-to-end integration tests for the dual-layer context trio. Verifies
CROSS-MODULE interactions among:

    scripts/collaboration/dual_layer_context.py — DualLayerContextManager
        (set_project / get_project / set_task / get_task / get_combined /
         build_prompt_context / cleanup_expired / clear_task_context)
    scripts/collaboration/memory_bridge.py     — MemoryBridge
        (recall / search_knowledge / capture_execution / record_feedback /
         persist_pattern / get_statistics / rebuild_index)
    scripts/collaboration/mce_adapter.py       — MCEAdapter
        (classify / retrieve_memories / match_rules / format_rules_as_prompt /
         add_rule / is_available / shutdown)

Flow:
    1. DualLayerContextManager isolates project-layer and task-layer context.
    2. MCEAdapter (unavailable by default) degrades gracefully; MemoryBridge
       recalls without MCE classification.
    3. MemoryBridge.recall results are injected into the task layer; project
       knowledge is injected into the project layer; build_prompt_context
       merges both.
    4. TTL expiry on context entries that reference recalled memories.
    5. Boundary (empty context, concurrent access, TTL=0, huge context).

Test categories:
    T1: DualLayerContextManager project + task layer isolation
    T2: MemoryBridge + MCEAdapter rule retrieval
    T3: DualLayerContextManager + MemoryBridge context injection
    T4: TTL expiry + context refresh
    T5: Boundary (empty context, concurrent access, TTL=0, huge context)
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.dual_layer_context import DualLayerContextManager
from scripts.collaboration.mce_adapter import MCEAdapter
from scripts.collaboration.memory_bridge import MemoryBridge
from scripts.collaboration.memory_types import (
    EpisodicMemory,
    KnowledgeItem,
    MemoryConfig,
    MemoryQuery,
    UserFeedback,
)
from scripts.collaboration.models_base import EntryType, ScratchpadEntry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_bridge() -> tuple[MemoryBridge, str]:
    """Build a MemoryBridge backed by a fresh temp dir. Returns (bridge, tmpdir)."""
    tmpdir = tempfile.mkdtemp(prefix="dualctx_integ_")
    bridge = MemoryBridge(base_dir=tmpdir, config=MemoryConfig.default())
    return bridge, tmpdir


def _make_episodic(
    item_id: str = "epi_001",
    finding: str = "Used retry pattern to fix flaky API integration test",
) -> EpisodicMemory:
    """Build an EpisodicMemory with content long enough for TF-IDF matching."""
    return EpisodicMemory(
        id=item_id,
        task_description="Fix flaky integration test with retry pattern",
        finding=finding,
        worker_id="tester-role",
        confidence=0.85,
        tags=["testing", "retry", "flaky"],
    )


def _make_knowledge(item_id: str = "know_001") -> KnowledgeItem:
    """Build a KnowledgeItem with architecture-level content."""
    return KnowledgeItem(
        id=item_id,
        domain="architecture",
        title="Microservice design principle",
        content="Prefer async messaging between services for decoupling and resilience.",
        tags=["microservice", "architecture", "async"],
        source="architect-role",
    )


def _make_feedback(item_id: str = "fb_001") -> UserFeedback:
    """Build a UserFeedback item for testing record_feedback."""
    return UserFeedback(
        id=item_id,
        user_id="user-alice",
        feedback_type="suggestion",
        content="Add retry logic for transient API failures",
        rating=4,
    )


# ---------------------------------------------------------------------------
# T1: DualLayerContextManager project + task layer isolation
# ---------------------------------------------------------------------------


class T1_DualLayerProjectTaskIsolation(unittest.TestCase):
    """T1: Project and task layers are independent dictionaries."""

    def setUp(self) -> None:
        self._ctx = DualLayerContextManager()

    def test_01_project_and_task_are_independent_dicts(self) -> None:
        """Verify: project_context and task_context are separate dicts."""
        self.assertIsNot(self._ctx.project_context, self._ctx.task_context)

    def test_02_same_key_in_both_layers_does_not_conflict(self) -> None:
        """Verify: setting the same key in both layers keeps both values."""
        self._ctx.set_project("shared", "project-value")
        self._ctx.set_task("shared", "task-value")
        self.assertEqual(self._ctx.get_project("shared"), "project-value")
        self.assertEqual(self._ctx.get_task("shared"), "task-value")

    def test_03_get_combined_merges_both_layers(self) -> None:
        """Verify: get_combined includes entries from both project and task layers."""
        self._ctx.set_project("proj_key", "proj_val")
        self._ctx.set_task("task_key", "task_val")
        combined = self._ctx.get_combined()
        self.assertEqual(combined["proj_key"], "proj_val")
        self.assertEqual(combined["task_key"], "task_val")

    def test_04_clear_task_context_leaves_project_intact(self) -> None:
        """Verify: clear_task_context empties only the task layer."""
        self._ctx.set_project("p", "1")
        self._ctx.set_task("t", "2")
        self._ctx.clear_task_context()
        self.assertEqual(self._ctx.get_project("p"), "1")
        self.assertIsNone(self._ctx.get_task("t"))

    def test_05_clear_all_empties_both_layers(self) -> None:
        """Verify: clear_all removes entries from both layers."""
        self._ctx.set_project("p", "1")
        self._ctx.set_task("t", "2")
        self._ctx.clear_all()
        self.assertEqual(len(self._ctx.project_context), 0)
        self.assertEqual(len(self._ctx.task_context), 0)

    def test_06_build_prompt_context_has_separate_sections(self) -> None:
        """Verify: build_prompt_context produces Project and Task sections."""
        self._ctx.set_project("arch", "microservice")
        self._ctx.set_task("current", "fix bug")
        prompt = self._ctx.build_prompt_context()
        self.assertIn("## Project Context", prompt)
        self.assertIn("## Task Context", prompt)

    def test_07_get_stats_reports_both_layer_counts(self) -> None:
        """Verify: get_stats returns counts for project, task, and total."""
        self._ctx.set_project("a", 1)
        self._ctx.set_project("b", 2)
        self._ctx.set_task("c", 3)
        stats = self._ctx.get_stats()
        self.assertEqual(stats["project_entries"], 2)
        self.assertEqual(stats["task_entries"], 1)
        self.assertEqual(stats["total_entries"], 3)

    def test_08_eviction_respects_per_layer_max_limits(self) -> None:
        """Verify: inserting beyond max_project evicts the oldest project entry."""
        ctx = DualLayerContextManager(max_project_entries=2, max_task_entries=2)
        ctx.set_project("first", 1)
        ctx.set_project("second", 2)
        ctx.set_project("third", 3)
        self.assertEqual(len(ctx.project_context), 2)
        self.assertIsNone(ctx.get_project("first"))


# ---------------------------------------------------------------------------
# T2: MemoryBridge + MCEAdapter rule retrieval
# ---------------------------------------------------------------------------


class T2_MemoryBridgeMCEAdapterRuleRetrieval(unittest.TestCase):
    """T2: MemoryBridge recall + MCEAdapter graceful degradation."""

    def setUp(self) -> None:
        self._bridge, self._tmpdir = _make_bridge()

    def tearDown(self) -> None:
        self._bridge.shutdown()
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_01_mce_adapter_unavailable_by_default(self) -> None:
        """Verify: MCEAdapter with enable=False reports is_available=False."""
        adapter = MCEAdapter(enable=False)
        self.assertFalse(adapter.is_available)

    def test_02_mce_classify_returns_none_when_unavailable(self) -> None:
        """Verify: classify() returns None when CarryMem is not installed."""
        adapter = MCEAdapter(enable=False)
        self.assertIsNone(adapter.classify("some text"))

    def test_03_mce_match_rules_returns_empty_when_unavailable(self) -> None:
        """Verify: match_rules() returns [] when no rules and no CarryMem."""
        adapter = MCEAdapter(enable=False)
        rules = adapter.match_rules("design API", user_id="test-user")
        self.assertEqual(rules, [])

    def test_04_memory_bridge_recall_without_mce_still_works(self) -> None:
        """Verify: MemoryBridge.recall works when MCE is unavailable."""
        self._bridge.writer.write_episodic(_make_episodic())
        result = self._bridge.recall(MemoryQuery(query_text="retry pattern flaky", limit=5))
        self.assertIsNotNone(result)
        self.assertIsInstance(result.memories, list)

    def test_05_memory_bridge_recall_empty_query_returns_empty(self) -> None:
        """Verify: recall with an empty query returns no memories."""
        result = self._bridge.recall(MemoryQuery(query_text="", limit=5))
        self.assertEqual(result.memories, [])
        self.assertEqual(result.total_found, 0)

    def test_06_memory_bridge_recall_finds_written_episodic(self) -> None:
        """Verify: after writing an episodic memory, recall finds it by keyword."""
        self._bridge.writer.write_episodic(_make_episodic(
            finding="Implement retry pattern for flaky API calls in integration tests",
        ))
        result = self._bridge.recall(MemoryQuery(query_text="retry flaky API", limit=5, min_relevance=0.01))
        self.assertGreaterEqual(len(result.memories), 1)

    def test_07_mce_format_rules_as_prompt_empty_returns_empty_string(self) -> None:
        """Verify: format_rules_as_prompt with no rules returns ''."""
        adapter = MCEAdapter(enable=False)
        self.assertEqual(adapter.format_rules_as_prompt([]), "")

    def test_08_mce_format_rules_as_prompt_formats_rules(self) -> None:
        """Verify: format_rules_as_prompt formats a non-empty rule list."""
        adapter = MCEAdapter(enable=False)
        rules = [{"rule_type": "always", "action": "Use type hints", "override": False}]
        prompt = adapter.format_rules_as_prompt(rules)
        self.assertIn("ALWAYS", prompt)
        self.assertIn("Use type hints", prompt)


# ---------------------------------------------------------------------------
# T3: DualLayerContextManager + MemoryBridge context injection
# ---------------------------------------------------------------------------


class T3_DualLayerContextMemoryBridgeInjection(unittest.TestCase):
    """T3: MemoryBridge recall results injected into DualLayerContextManager."""

    def setUp(self) -> None:
        self._bridge, self._tmpdir = _make_bridge()
        self._ctx = DualLayerContextManager()

    def tearDown(self) -> None:
        self._bridge.shutdown()
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_01_store_recall_result_in_task_layer(self) -> None:
        """Verify: recalled memories are stored in the task context layer."""
        self._bridge.writer.write_episodic(_make_episodic())
        result = self._bridge.recall(MemoryQuery(query_text="retry flaky", limit=5, min_relevance=0.01))
        self._ctx.set_task("recalled_memories", len(result.memories), source="MemoryBridge")
        self.assertGreaterEqual(self._ctx.get_task("recalled_memories"), 0)
        entry = self._ctx.task_context["recalled_memories"]
        self.assertEqual(entry.source, "MemoryBridge")

    def test_02_store_project_knowledge_in_project_layer(self) -> None:
        """Verify: knowledge memories are stored in the project context layer."""
        self._bridge.writer.write_knowledge(_make_knowledge())
        items = self._bridge.reader.read_knowledge(domain="architecture")
        for item in items:
            self._ctx.set_project(item.title, item.content, source="MemoryBridge")
        self.assertIn("Microservice design principle", self._ctx.project_context)

    def test_03_build_prompt_context_includes_recalled_memories(self) -> None:
        """Verify: build_prompt_context includes memory-sourced entries."""
        self._ctx.set_project("arch_decision", "Use async messaging", source="MemoryBridge")
        self._ctx.set_task("current_finding", "Retry pattern applied", source="MemoryBridge")
        prompt = self._ctx.build_prompt_context()
        self.assertIn("Use async messaging", prompt)
        self.assertIn("Retry pattern applied", prompt)

    def test_04_context_injection_recall_set_task_get_combined(self) -> None:
        """Verify: full injection chain — recall → set_task → get_combined."""
        self._bridge.writer.write_episodic(_make_episodic())
        result = self._bridge.recall(MemoryQuery(query_text="retry flaky", limit=5, min_relevance=0.01))
        self._ctx.set_task("memory_count", result.total_found, source="MemoryBridge")
        combined = self._ctx.get_combined()
        self.assertIn("memory_count", combined)

    def test_05_capture_execution_result_stored_in_context(self) -> None:
        """Verify: capture_execution return value can be stored in context."""
        entry = ScratchpadEntry(
            worker_id="tester",
            role_id="tester",
            entry_type=EntryType.FINDING,
            content="Found and fixed a race condition in the dispatch pipeline",
            confidence=0.85,
        )
        captured_id = self._bridge.capture_execution(
            execution_record=None,
            scratchpad_entries=[entry],
        )
        self._ctx.set_task("last_capture_id", captured_id, source="MemoryBridge.capture")
        self.assertIsNotNone(self._ctx.get_task("last_capture_id"))

    def test_06_get_combined_with_specific_keys_filters(self) -> None:
        """Verify: get_combined(keys=[...]) returns only the requested keys."""
        self._ctx.set_project("wanted", "yes")
        self._ctx.set_project("unwanted", "no")
        self._ctx.set_task("also_wanted", "yes")
        combined = self._ctx.get_combined(keys=["wanted", "also_wanted"])
        self.assertIn("wanted", combined)
        self.assertNotIn("unwanted", combined)

    def test_07_context_entry_source_tracks_origin(self) -> None:
        """Verify: the source field on a ContextEntry tracks its origin."""
        self._ctx.set_project("key", "value", source="MemoryBridge.recall")
        entry = self._ctx.project_context["key"]
        self.assertEqual(entry.source, "MemoryBridge.recall")

    def test_08_clear_task_context_after_task_isolates_tasks(self) -> None:
        """Verify: clearing task context between tasks prevents leakage."""
        self._ctx.set_task("task1_data", "first", source="task1")
        self._ctx.clear_task_context()
        self._ctx.set_task("task2_data", "second", source="task2")
        self.assertIsNone(self._ctx.get_task("task1_data"))
        self.assertEqual(self._ctx.get_task("task2_data"), "second")


# ---------------------------------------------------------------------------
# T4: TTL expiry + context refresh
# ---------------------------------------------------------------------------


class T4_TTLExpiryAndContextRefresh(unittest.TestCase):
    """T4: TTL-based expiry and context refresh semantics."""

    def setUp(self) -> None:
        self._ctx = DualLayerContextManager()

    def test_01_project_entry_with_ttl_not_expired_immediately(self) -> None:
        """Verify: a project entry with a 60s TTL is not expired right away."""
        self._ctx.set_project("fresh", "value", ttl=60)
        self.assertIsNotNone(self._ctx.get_project("fresh"))

    def test_02_project_entry_with_ttl_expired_after_time(self) -> None:
        """Verify: a project entry with a past TTL is treated as expired."""
        self._ctx.set_project("old", "value", ttl=1)
        entry = self._ctx.project_context["old"]
        entry.timestamp = (datetime.now() - timedelta(seconds=120)).isoformat()
        self.assertIsNone(self._ctx.get_project("old"))

    def test_03_task_entry_expired_returns_default(self) -> None:
        """Verify: an expired task entry returns the default value."""
        self._ctx.set_task("stale", "data", ttl=1)
        entry = self._ctx.task_context["stale"]
        entry.timestamp = (datetime.now() - timedelta(seconds=100)).isoformat()
        self.assertEqual(self._ctx.get_task("stale", default="fallback"), "fallback")

    def test_04_cleanup_expired_removes_only_expired_entries(self) -> None:
        """Verify: cleanup_expired removes expired entries, keeps fresh ones."""
        self._ctx.set_project("fresh", "1", ttl=60)
        self._ctx.set_project("old", "2", ttl=1)
        self._ctx.project_context["old"].timestamp = (
            datetime.now() - timedelta(seconds=100)
        ).isoformat()
        removed = self._ctx.cleanup_expired()
        self.assertEqual(removed, 1)
        self.assertIsNotNone(self._ctx.get_project("fresh"))

    def test_05_get_project_on_expired_entry_deletes_it(self) -> None:
        """Verify: accessing an expired project entry triggers its deletion."""
        self._ctx.set_project("temp", "val", ttl=1)
        self._ctx.project_context["temp"].timestamp = (
            datetime.now() - timedelta(seconds=50)
        ).isoformat()
        self._ctx.get_project("temp")
        self.assertNotIn("temp", self._ctx.project_context)

    def test_06_get_combined_excludes_expired_entries(self) -> None:
        """Verify: get_combined skips entries whose TTL has expired."""
        self._ctx.set_project("alive", "1", ttl=60)
        self._ctx.set_project("dead", "2", ttl=1)
        self._ctx.project_context["dead"].timestamp = (
            datetime.now() - timedelta(seconds=50)
        ).isoformat()
        combined = self._ctx.get_combined()
        self.assertIn("alive", combined)
        self.assertNotIn("dead", combined)

    def test_07_build_prompt_context_excludes_expired(self) -> None:
        """Verify: build_prompt_context omits expired entries."""
        self._ctx.set_project("alive", "visible", ttl=60)
        self._ctx.set_project("dead", "hidden", ttl=1)
        self._ctx.project_context["dead"].timestamp = (
            datetime.now() - timedelta(seconds=50)
        ).isoformat()
        prompt = self._ctx.build_prompt_context()
        self.assertIn("visible", prompt)
        self.assertNotIn("hidden", prompt)

    def test_08_refresh_entry_by_re_setting_extends_ttl(self) -> None:
        """Verify: re-setting an entry refreshes its timestamp and TTL."""
        self._ctx.set_project("refreshed", "v1", ttl=1)
        self._ctx.project_context["refreshed"].timestamp = (
            datetime.now() - timedelta(seconds=50)
        ).isoformat()
        self._ctx.set_project("refreshed", "v2", ttl=60)
        self.assertEqual(self._ctx.get_project("refreshed"), "v2")


# ---------------------------------------------------------------------------
# T5: Boundary (empty context, concurrent access, TTL=0, huge context)
# ---------------------------------------------------------------------------


class T5_BoundaryAndEdgeCases(unittest.TestCase):
    """T5: Boundary conditions — empty, concurrent, TTL=0, huge context."""

    def setUp(self) -> None:
        self._ctx = DualLayerContextManager()

    def test_01_get_project_on_empty_returns_default(self) -> None:
        """Verify: get_project on a missing key returns the default."""
        self.assertIsNone(self._ctx.get_project("missing"))
        self.assertEqual(self._ctx.get_project("missing", default=42), 42)

    def test_02_get_task_on_empty_returns_default(self) -> None:
        """Verify: get_task on a missing key returns the default."""
        self.assertIsNone(self._ctx.get_task("missing"))
        self.assertEqual(self._ctx.get_task("missing", default="d"), "d")

    def test_03_get_combined_on_empty_returns_empty_dict(self) -> None:
        """Verify: get_combined on an empty manager returns {}."""
        self.assertEqual(self._ctx.get_combined(), {})

    def test_04_build_prompt_context_on_empty_returns_empty_string(self) -> None:
        """Verify: build_prompt_context with no entries returns ''."""
        self.assertEqual(self._ctx.build_prompt_context(), "")

    def test_05_concurrent_set_task_from_multiple_threads(self) -> None:
        """Verify: concurrent set_task calls from many threads don't corrupt."""
        def _writer(idx: int) -> None:
            self._ctx.set_task(f"key-{idx}", idx)

        threads = [threading.Thread(target=_writer, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(self._ctx.task_context), 20)

    def test_06_ttl_zero_entry_expires_immediately(self) -> None:
        """Verify: an entry with TTL=0 is considered expired on next access."""
        self._ctx.set_task("instant", "val", ttl=0)
        # TTL=0 means any elapsed time > 0 expires it; sleep briefly.
        import time
        time.sleep(0.01)
        self.assertIsNone(self._ctx.get_task("instant"))

    def test_07_huge_context_within_max_limit(self) -> None:
        """Verify: filling context up to (but not beyond) max limit works."""
        ctx = DualLayerContextManager(max_project_entries=50, max_task_entries=50)
        for i in range(50):
            ctx.set_project(f"p{i}", i)
            ctx.set_task(f"t{i}", i)
        self.assertEqual(len(ctx.project_context), 50)
        self.assertEqual(len(ctx.task_context), 50)

    def test_08_memory_bridge_recall_with_disabled_config_returns_empty(self) -> None:
        """Verify: recall on a disabled MemoryBridge returns no memories."""
        bridge = MemoryBridge(
            base_dir=tempfile.mkdtemp(prefix="disabled_bridge_"),
            config=MemoryConfig(enabled=False),
        )
        try:
            result = bridge.recall(MemoryQuery(query_text="anything", limit=5))
            self.assertEqual(result.memories, [])
            self.assertEqual(result.total_found, 0)
        finally:
            bridge.shutdown()


if __name__ == "__main__":
    unittest.main()
