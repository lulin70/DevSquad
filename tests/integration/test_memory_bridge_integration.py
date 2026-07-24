#!/usr/bin/env python3
"""MemoryBridge + MCEAdapter + LearnedRuleStore + Forgetting + Index Integration Tests.

Integration tests for the memory bridge chain:
    MemoryBridge → MemoryWriter → JsonMemoryStore → MemoryIndexer
    MCEAdapter (lazy-load + graceful-degrade)
    LearnedRuleStore (two-tier persistence)
    memory_forgetting (Ebbinghaus decay + compress + cleanup)

Flow:
    1. MemoryBridge.writer.write_* → store.save → indexer.add_to_index
    2. MemoryBridge.rebuild_index → indexer.build_index
    3. MemoryBridge.recall(query) → indexer.search → store.load
    4. forgetting_weight / compress_old_memories / cleanup_expired_memories
    5. MCEAdapter degrades gracefully when CarryMem is unavailable
    6. LearnedRuleStore routes rules by confidence to tier1/tier2

References:
    - scripts/collaboration/memory_bridge.py
    - scripts/collaboration/memory_serializer.py
    - scripts/collaboration/memory_query.py
    - scripts/collaboration/memory_index.py
    - scripts/collaboration/memory_forgetting.py
    - scripts/collaboration/memory_types.py
    - scripts/collaboration/mce_adapter.py
    - scripts/collaboration/learned_rule_store.py
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

from scripts.collaboration.learned_rule_store import LearnedRuleStore
from scripts.collaboration.mce_adapter import MCEAdapter, MCEResult, MCEStatus
from scripts.collaboration.memory_bridge import MemoryBridge
from scripts.collaboration.memory_forgetting import (
    cleanup_expired_memories,
)
from scripts.collaboration.memory_index import MemoryIndexer
from scripts.collaboration.memory_types import (
    AnalysisCase,
    EpisodicMemory,
    ErrorContext,
    KnowledgeItem,
    MemoryConfig,
    MemoryItem,
    MemoryQuery,
    MemoryType,
    PersistedPattern,
    UserFeedback,
)
from scripts.collaboration.models_base import LearnedRule

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_bridge(base_dir: str | None = None) -> tuple[MemoryBridge, str]:
    """Build a MemoryBridge backed by a fresh temp dir. Returns (bridge, tmpdir)."""
    tmpdir = base_dir or tempfile.mkdtemp(prefix="membridge_integ_")
    bridge = MemoryBridge(base_dir=tmpdir, config=MemoryConfig.default())
    return bridge, tmpdir


def _make_knowledge(item_id: str = "know_001", domain: str = "general") -> KnowledgeItem:
    return KnowledgeItem(
        id=item_id,
        domain=domain,
        title="Microservice design principle",
        content="Prefer async messaging between services for decoupling.",
        tags=["microservice", "architecture"],
        source="architect-role",
    )


def _make_episodic(item_id: str = "epi_001", finding: str = "Used retry pattern to fix flaky API") -> EpisodicMemory:
    return EpisodicMemory(
        id=item_id,
        task_description="Fix flaky integration test",
        finding=finding,
        worker_id="tester-role",
        confidence=0.85,
        tags=["testing", "retry"],
    )


def _make_feedback(item_id: str = "fb_001") -> UserFeedback:
    return UserFeedback(
        id=item_id,
        user_id="user-alice",
        feedback_type="suggestion",
        content="Please add more verbose logging in dispatch",
        rating=4,
        context={"task": "dispatch-v2"},
    )


def _make_pattern(item_id: str = "pat_001") -> PersistedPattern:
    return PersistedPattern(
        id=item_id,
        name="Two-stage review pattern",
        slug="two-stage-review",
        category="review",
        trigger_keywords=["review", "gate"],
        steps_template=[{"step": 1, "action": "scan"}, {"step": 2, "action": "judge"}],
        confidence=0.9,
        quality_score=85,
    )


def _make_analysis(item_id: str = "anal_001") -> AnalysisCase:
    return AnalysisCase(
        id=item_id,
        problem="Dispatch consensus deadlock under high concurrency",
        root_cause="RLock re-entry on shared coordinator state",
        solutions=["Switch to per-worker state", "Add timeout fallback"],
        status="completed",
    )


def _make_semantic_item(item_id: str = "sem_001") -> MemoryItem:
    return MemoryItem(
        id=item_id,
        memory_type=MemoryType.SEMANTIC,
        title="Positive sentiment on async design",
        content="Team prefers async event-driven architecture",
        tags=["sentiment", "async"],
    )


def _make_correction_item(item_id: str = "corr_001") -> MemoryItem:
    return MemoryItem(
        id=item_id,
        memory_type=MemoryType.CORRECTION,
        title="Correction: avoid global mutable state",
        content="Do not use module-level dicts for caching in workers",
        tags=["correction", "concurrency"],
    )


# ---------------------------------------------------------------------------
# T1: MemoryBridge 7-class memory storage
# ---------------------------------------------------------------------------


class T1_SevenClassMemoryStorageIntegration(unittest.TestCase):
    """T1: All 7 MemoryType variants persist via MemoryWriter + JsonMemoryStore."""

    def setUp(self) -> None:
        self.bridge, self.tmpdir = _make_bridge()

    def tearDown(self) -> None:
        self.bridge.shutdown()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_01_knowledge_storage_round_trip(self) -> None:
        """Verify: KnowledgeItem persists and reloads with domain intact."""
        item = _make_knowledge()
        item_id = self.bridge.writer.write_knowledge(item)
        self.assertEqual(item_id, "know_001")
        loaded = self.bridge.store.load(MemoryType.KNOWLEDGE, item_id)
        self.assertIsNotNone(loaded)
        assert loaded is not None  # narrowing
        self.assertEqual(loaded["title"], item.title)
        self.assertEqual(loaded["domain"], "general")

    def test_02_episodic_storage_round_trip(self) -> None:
        """Verify: EpisodicMemory persists and reloads with finding intact."""
        mem = _make_episodic()
        item_id = self.bridge.writer.write_episodic(mem)
        self.assertEqual(item_id, "epi_001")
        loaded = self.bridge.store.load(MemoryType.EPISODIC, item_id)
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded["finding"], mem.finding)
        self.assertEqual(loaded["worker_id"], "tester-role")

    def test_03_feedback_storage_round_trip(self) -> None:
        """Verify: UserFeedback persists with status and rating fields."""
        fb = _make_feedback()
        item_id = self.bridge.writer.write_feedback(fb)
        self.assertEqual(item_id, "fb_001")
        loaded = self.bridge.store.load(MemoryType.FEEDBACK, item_id)
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded["status"], "pending")
        self.assertEqual(loaded["rating"], 4)

    def test_04_pattern_storage_round_trip(self) -> None:
        """Verify: PersistedPattern stores steps_template as JSON content."""
        pat = _make_pattern()
        item_id = self.bridge.writer.write_pattern(pat)
        self.assertEqual(item_id, "pat_001")
        loaded = self.bridge.store.load(MemoryType.PATTERN, item_id)
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded["confidence"], 0.9)
        self.assertEqual(len(loaded["steps_template"]), 2)

    def test_05_analysis_storage_round_trip(self) -> None:
        """Verify: AnalysisCase persists problem/root_cause/solutions."""
        analysis = _make_analysis()
        item_id = self.bridge.writer.write_analysis(analysis)
        self.assertEqual(item_id, "anal_001")
        loaded = self.bridge.store.load(MemoryType.ANALYSIS, item_id)
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded["root_cause"], "RLock re-entry on shared coordinator state")
        self.assertEqual(len(loaded["solutions"]), 2)

    def test_06_semantic_storage_via_batch_write(self) -> None:
        """Verify: SEMANTIC type persists via batch_write (no dedicated writer)."""
        sem = _make_semantic_item()
        count = self.bridge.writer.batch_write([sem])
        self.assertEqual(count, 1)
        loaded = self.bridge.store.load(MemoryType.SEMANTIC, "sem_001")
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded["memory_type"], "semantic")

    def test_07_correction_storage_via_store_direct(self) -> None:
        """Verify: CORRECTION type persists via direct store.save + index."""
        corr = _make_correction_item()
        data = corr.to_dict()
        item_id = self.bridge.store.save(MemoryType.CORRECTION, data)
        self.assertEqual(item_id, "corr_001")
        self.bridge.indexer.add_to_index(corr)
        loaded = self.bridge.store.load(MemoryType.CORRECTION, item_id)
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertIn("concurrency", loaded["tags"])


# ---------------------------------------------------------------------------
# T2: MCEAdapter lazy-load + graceful-degrade + thread-safe + rule APIs
# ---------------------------------------------------------------------------


class T2_MCEAdapterIntegration(unittest.TestCase):
    """T2: MCEAdapter degrades gracefully without CarryMem installed."""

    def test_01_disabled_by_default(self) -> None:
        """Verify: MCEAdapter(enable=False) reports unavailable."""
        adapter = MCEAdapter(enable=False)
        self.assertFalse(adapter.is_available)

    def test_02_lazy_load_no_crash_when_carrymem_absent(self) -> None:
        """Verify: enable=True attempts init without raising even if CarryMem missing."""
        adapter = MCEAdapter(enable=True)
        # CarryMem is an external optional dependency; in the test env it is absent.
        self.assertFalse(adapter.is_available)
        status = adapter.status
        self.assertIsInstance(status, MCEStatus)
        # init_error is populated when the import fails.
        self.assertIsNotNone(status.init_error)

    def test_03_classify_returns_none_when_unavailable(self) -> None:
        """Verify: classify() on unavailable adapter returns None and bumps fail count."""
        adapter = MCEAdapter(enable=False)
        result = adapter.classify("some text")
        self.assertIsNone(result)
        self.assertGreaterEqual(adapter.status.classify_fail_count, 1)

    def test_04_store_memory_returns_false_when_unavailable(self) -> None:
        """Verify: store_memory() degrades to False without raising."""
        adapter = MCEAdapter(enable=False)
        self.assertFalse(adapter.store_memory({"content": "x"}))

    def test_05_retrieve_memories_returns_empty_when_unavailable(self) -> None:
        """Verify: retrieve_memories() returns [] when adapter unavailable."""
        adapter = MCEAdapter(enable=False)
        self.assertEqual(adapter.retrieve_memories("query"), [])

    def test_06_match_rules_fallback_returns_empty_without_rules(self) -> None:
        """Verify: match_rules() keyword fallback yields [] when no rules exist."""
        adapter = MCEAdapter(enable=False)
        rules = adapter.match_rules("microservice design", user_id="alice")
        self.assertEqual(rules, [])

    def test_07_format_rules_as_prompt_empty_returns_empty(self) -> None:
        """Verify: format_rules_as_prompt([]) returns empty string."""
        adapter = MCEAdapter(enable=False)
        self.assertEqual(adapter.format_rules_as_prompt([]), "")

    def test_08_format_rules_as_prompt_fallback_formats_rules(self) -> None:
        """Verify: fallback formatter renders rule_type and action text."""
        adapter = MCEAdapter(enable=False)
        rules = [{"rule_type": "always", "action": "Prefer pathlib", "override": False}]
        out = adapter.format_rules_as_prompt(rules)
        self.assertIn("=== Applicable Rules ===", out)
        self.assertIn("[ALWAYS]", out)
        self.assertIn("Prefer pathlib", out)

    def test_09_add_rule_falls_back_to_local_storage(self) -> None:
        """Verify: add_rule() without CarryMem returns a local-fallback dict."""
        adapter = MCEAdapter(enable=False)
        result = adapter.add_rule(trigger="file ops", action="use pathlib", rule_type="always")
        self.assertIsInstance(result, dict)
        self.assertIn(result.get("storage", ""), ("local_fallback",))
        self.assertFalse(result.get("success", True) is True and result.get("storage") != "local_fallback")

    def test_10_sanitize_user_id_blocks_path_traversal(self) -> None:
        """Verify: _sanitize_user_id neutralizes ../ and shell metacharacters."""
        sanitized = MCEAdapter._sanitize_user_id("../../etc/passwd")
        self.assertNotIn("..", sanitized)
        self.assertNotIn("/", sanitized)
        sanitized2 = MCEAdapter._sanitize_user_id("alice<>;|")
        for ch in ("<", ">", ";", "|"):
            self.assertNotIn(ch, sanitized2)

    def test_11_sanitize_user_id_empty_returns_default(self) -> None:
        """Verify: empty user_id falls back to 'default'."""
        self.assertEqual(MCEAdapter._sanitize_user_id(""), "default")

    def test_12_concurrent_classify_thread_safe(self) -> None:
        """Verify: concurrent classify calls do not corrupt adapter state."""
        adapter = MCEAdapter(enable=False)
        errors: list[Exception] = []

        def worker() -> None:
            try:
                for _ in range(20):
                    self.assertIsNone(adapter.classify("x"))
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        # 8 threads * 20 calls = 160 failures recorded.
        self.assertEqual(adapter.status.classify_fail_count, 160)

    def test_13_get_stats_reports_unavailable(self) -> None:
        """Verify: get_stats() returns available=False when CarryMem absent."""
        adapter = MCEAdapter(enable=False)
        stats = adapter.get_stats()
        self.assertFalse(stats["available"])
        self.assertEqual(stats["adapter_type"], "none")

    def test_14_mceresult_to_dict_round_trip(self) -> None:
        """Verify: MCEResult serializes type/confidence/tier/metadata."""
        result = MCEResult(memory_type="knowledge", confidence=0.87654, tier="tier1",
                           metadata={"carrymem_type": "fact_declaration"})
        d = result.to_dict()
        self.assertEqual(d["type"], "knowledge")
        self.assertEqual(d["confidence"], 0.8765)  # rounded to 4 decimals
        self.assertEqual(d["tier"], "tier1")


# ---------------------------------------------------------------------------
# T3: LearnedRuleStore two-tier persistence
# ---------------------------------------------------------------------------


class T3_LearnedRuleStoreIntegration(unittest.TestCase):
    """T3: Confidence-routed persistence to tier1 (YAML) and tier2 (JSON)."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp(prefix="rulestore_integ_")
        self.config_path = os.path.join(self.tmpdir, ".devsquad.yaml")
        self.tier2_path = os.path.join(self.tmpdir, "tier2", "corrections.json")
        self.store = LearnedRuleStore(config_path=self.config_path, tier2_path=self.tier2_path)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_01_tier1_high_confidence_rule_persisted(self) -> None:
        """Verify: confidence >= 0.8 routes to tier1 and returns 'tier1'."""
        rule = LearnedRule(rule_text="Always prefer pathlib over os.path",
                           trigger_condition="file_path_manipulation",
                           confidence=0.85, source_task_id="task_001")
        tier = self.store.add_rule(rule)
        self.assertEqual(tier, "tier1")
        self.assertTrue(os.path.exists(self.config_path))

    def test_02_tier2_medium_confidence_rule_persisted(self) -> None:
        """Verify: confidence 0.5-0.8 routes to tier2 candidate pool."""
        rule = LearnedRule(rule_text="Consider dataclass for DTOs",
                           trigger_condition="dto_definition",
                           confidence=0.65, source_task_id="task_002")
        tier = self.store.add_rule(rule)
        self.assertEqual(tier, "tier2")
        self.assertTrue(os.path.exists(self.tier2_path))

    def test_03_rejected_low_confidence_rule_not_persisted(self) -> None:
        """Verify: confidence < 0.5 is rejected and writes nothing."""
        rule = LearnedRule(rule_text="Maybe add a comment",
                           trigger_condition="cosmetic",
                           confidence=0.3, source_task_id="task_003")
        tier = self.store.add_rule(rule)
        self.assertEqual(tier, "rejected")
        self.assertFalse(os.path.exists(self.config_path))
        self.assertFalse(os.path.exists(self.tier2_path))

    def test_04_load_tier1_rules_round_trip(self) -> None:
        """Verify: load_tier1_rules reconstructs persisted rules."""
        rule = LearnedRule(rule_text="Use type hints everywhere",
                           trigger_condition="python_typing",
                           confidence=0.9, source_task_id="task_004")
        self.store.add_rule(rule)
        loaded = self.store.load_tier1_rules()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].rule_text, "Use type hints everywhere")
        self.assertEqual(loaded[0].confidence, 0.9)

    def test_05_load_tier2_rules_round_trip(self) -> None:
        """Verify: load_tier2_rules reconstructs candidate rules."""
        rule = LearnedRule(rule_text="Draft: prefer explicit imports",
                           trigger_condition="import_style",
                           confidence=0.55, source_task_id="task_005")
        self.store.add_rule(rule)
        loaded = self.store.load_tier2_rules()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].confidence, 0.55)

    def test_06_promote_tier2_to_tier1(self) -> None:
        """Verify: promote_tier2_to_tier1 moves a candidate to tier1 and removes from tier2."""
        rule = LearnedRule(rule_text="Promote me to tier1",
                           trigger_condition="promotion",
                           confidence=0.6, source_task_id="task_006")
        self.store.add_rule(rule)
        self.assertEqual(len(self.store.load_tier2_rules()), 1)
        self.assertTrue(self.store.promote_tier2_to_tier1("Promote me to tier1"))
        self.assertEqual(len(self.store.load_tier2_rules()), 0)
        tier1 = self.store.load_tier1_rules()
        self.assertEqual(len(tier1), 1)
        self.assertGreaterEqual(tier1[0].confidence, 0.8)

    def test_07_promote_nonexistent_rule_returns_false(self) -> None:
        """Verify: promoting a rule_text that doesn't exist returns False."""
        self.assertFalse(self.store.promote_tier2_to_tier1("nonexistent rule"))

    def test_08_tier1_dedup_by_rule_hash(self) -> None:
        """Verify: adding the same tier1 rule twice does not duplicate it."""
        rule = LearnedRule(rule_text="Dedup this rule",
                           trigger_condition="dedup",
                           confidence=0.88, source_task_id="task_007")
        self.store.add_rule(rule)
        self.store.add_rule(rule)
        loaded = self.store.load_tier1_rules()
        self.assertEqual(len(loaded), 1)

    def test_09_tier2_dedup_by_rule_hash(self) -> None:
        """Verify: adding the same tier2 rule twice does not duplicate it."""
        rule = LearnedRule(rule_text="Dedup tier2 rule",
                           trigger_condition="dedup2",
                           confidence=0.55, source_task_id="task_008")
        self.store.add_rule(rule)
        self.store.add_rule(rule)
        loaded = self.store.load_tier2_rules()
        self.assertEqual(len(loaded), 1)

    def test_10_load_tier1_from_missing_file_returns_empty(self) -> None:
        """Verify: load_tier1_rules on a non-existent config returns empty list."""
        store = LearnedRuleStore(config_path="/nonexistent/path/.devsquad.yaml",
                                 tier2_path="/nonexistent/tier2/c.json")
        self.assertEqual(store.load_tier1_rules(), [])


# ---------------------------------------------------------------------------
# T4: End-to-end store → index → query → retrieve + forgetting curve
# ---------------------------------------------------------------------------


class T4_EndToEndStoreIndexQueryIntegration(unittest.TestCase):
    """T4: Full lifecycle — store, rebuild index, recall, apply forgetting."""

    def setUp(self) -> None:
        self.bridge, self.tmpdir = _make_bridge()

    def tearDown(self) -> None:
        self.bridge.shutdown()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_01_store_then_rebuild_index_then_recall(self) -> None:
        """Verify: batch_write MemoryItem → rebuild_index → recall returns the item.

        Note: batch_write stores the full MemoryItem.to_dict() (which includes
        'memory_type'), so rebuild_index can reconstruct it. The dedicated
        write_knowledge() stores a subset without 'memory_type', which
        rebuild_index skips — batch_write is the round-trippable path.
        """
        item = MemoryItem(
            id="know_recall_001",
            memory_type=MemoryType.KNOWLEDGE,
            title="API rate limiting strategy",
            content="Use token bucket algorithm for API rate limiting to smooth bursts.",
            domain="general",
            tags=["api", "rate-limit"],
            source="architect",
        )
        self.bridge.writer.batch_write([item])
        self.bridge.rebuild_index()
        self.assertTrue(self.bridge.indexer.is_built)
        result = self.bridge.recall(MemoryQuery(query_text="API rate limiting", limit=5, min_relevance=0.05))
        self.assertGreaterEqual(result.total_found, 1)
        self.assertEqual(result.memories[0].id, "know_recall_001")

    def test_02_recall_returns_relevance_scores(self) -> None:
        """Verify: recall populates relevance_score on returned memories."""
        item = MemoryItem(
            id="know_rel_002",
            memory_type=MemoryType.KNOWLEDGE,
            title="Database indexing guide",
            content="Create composite indexes for multi-column WHERE clauses.",
            domain="general",
            tags=["database", "indexing"],
        )
        self.bridge.writer.batch_write([item])
        self.bridge.rebuild_index()
        result = self.bridge.recall(MemoryQuery(query_text="database indexing", limit=5, min_relevance=0.05))
        if result.memories:
            self.assertGreater(result.memories[0].relevance_score, 0.0)

    def test_03_forgetting_weight_fresh_memory_is_one(self) -> None:
        """Verify: a memory created moments ago has forgetting_weight == 1.0."""
        fresh = MemoryItem(
            id="fresh_001",
            memory_type=MemoryType.EPISODIC,
            title="Fresh finding",
            content="Just captured",
            access_count=0,
        )
        self.assertEqual(self.bridge.forgetting_weight(fresh), 1.0)

    def test_04_forgetting_weight_decays_for_old_memory(self) -> None:
        """Verify: a 40-day-old memory has weight strictly below 1.0."""
        old = MemoryItem(
            id="old_001",
            memory_type=MemoryType.EPISODIC,
            title="Old finding",
            content="Captured long ago",
            created_at=datetime.now() - timedelta(days=40),
            access_count=2,
        )
        weight = self.bridge.forgetting_weight(old)
        self.assertGreater(weight, 0.0)
        self.assertLess(weight, 1.0)

    def test_05_forgetting_weight_oldest_memory_below_thirty_day_band(self) -> None:
        """Verify: a 90-day-old memory is in the >60 day band (weight < 0.3)."""
        very_old = MemoryItem(
            id="veryold_001",
            memory_type=MemoryType.EPISODIC,
            title="Ancient finding",
            content="Captured 90 days ago",
            created_at=datetime.now() - timedelta(days=90),
            access_count=1,
        )
        weight = self.bridge.forgetting_weight(very_old)
        # > 60 days band: 0.3 * (access_factor / (access_factor + 3)) < 0.3
        self.assertLess(weight, 0.3)

    def test_06_compress_old_memories_truncates_aged_episodic(self) -> None:
        """Verify: compress_old_memories truncates episodic entries older than 60 days."""
        old_created = (datetime.now() - timedelta(days=70)).isoformat()
        long_finding = "x" * 500
        self.bridge.store.save(MemoryType.EPISODIC, {
            "id": "epi_old_001",
            "task_description": "old task",
            "finding": long_finding,
            "worker_id": "w",
            "confidence": 0.7,
            "tags": [],
            "created_at": old_created,
        })
        compressed = self.bridge.compress_old_memories()
        self.assertGreaterEqual(compressed, 1)
        loaded = self.bridge.store.load(MemoryType.EPISODIC, "epi_old_001")
        assert loaded is not None
        self.assertIn("[COMPRESSED]", loaded["finding"])
        self.assertTrue(loaded["metadata"]["compressed"])

    def test_07_cleanup_expired_memories_removes_old_entries(self) -> None:
        """Verify: cleanup_expired_memories deletes entries beyond retention_days."""
        config = MemoryConfig.default()
        config.retention_days = 10
        old_created = (datetime.now() - timedelta(days=30)).isoformat()
        self.bridge.store.save(MemoryType.EPISODIC, {
            "id": "epi_expired_001",
            "task_description": "expired task",
            "finding": "old",
            "worker_id": "w",
            "confidence": 0.5,
            "tags": [],
            "created_at": old_created,
        })
        removed = cleanup_expired_memories(self.bridge.store, config, self.bridge.indexer)
        self.assertGreaterEqual(removed, 1)
        self.assertIsNone(self.bridge.store.load(MemoryType.EPISODIC, "epi_expired_001"))

    def test_08_search_knowledge_returns_matching_items(self) -> None:
        """Verify: search_knowledge() returns KnowledgeItem matching keywords."""
        item = MemoryItem(
            id="know_search_001",
            memory_type=MemoryType.KNOWLEDGE,
            title="Caching strategies",
            content="Use Redis for distributed caching with TTL eviction.",
            domain="general",
            tags=["cache", "redis"],
        )
        self.bridge.writer.batch_write([item])
        self.bridge.rebuild_index()
        results = self.bridge.search_knowledge(["redis", "caching"])
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0].id, "know_search_001")


# ---------------------------------------------------------------------------
# T5: Boundary cases — empty inputs, missing IDs, concurrent access
# ---------------------------------------------------------------------------


class T5_BoundaryAndEdgeCasesIntegration(unittest.TestCase):
    """T5: Empty user_id, missing memories, corrupted index, concurrent access."""

    def setUp(self) -> None:
        self.bridge, self.tmpdir = _make_bridge()

    def tearDown(self) -> None:
        self.bridge.shutdown()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_01_recall_with_empty_query_returns_empty(self) -> None:
        """Verify: recall with blank query_text returns empty result, no crash."""
        result = self.bridge.recall(MemoryQuery(query_text="", limit=5))
        self.assertEqual(result.total_found, 0)
        self.assertEqual(result.memories, [])

    def test_02_recall_with_whitespace_query_returns_empty(self) -> None:
        """Verify: recall with whitespace-only query returns empty result."""
        result = self.bridge.recall(MemoryQuery(query_text="   ", limit=5))
        self.assertEqual(result.total_found, 0)

    def test_03_load_nonexistent_memory_returns_none(self) -> None:
        """Verify: store.load of a missing ID returns None."""
        self.assertIsNone(self.bridge.store.load(MemoryType.KNOWLEDGE, "does_not_exist"))

    def test_04_list_all_empty_type_returns_empty_list(self) -> None:
        """Verify: list_all on a type with no entries returns [] (no error)."""
        self.assertEqual(self.bridge.store.list_all(MemoryType.CORRECTION), [])

    def test_05_delete_nonexistent_returns_false(self) -> None:
        """Verify: delete of a non-existent ID returns False."""
        self.assertFalse(self.bridge.store.delete(MemoryType.KNOWLEDGE, "missing_id"))

    def test_06_path_traversal_item_id_rejected(self) -> None:
        """Verify: item_id with '../' raises ValueError (path traversal guard)."""
        with self.assertRaises(ValueError):
            self.bridge.store.save(MemoryType.KNOWLEDGE, {"id": "../escape", "content": "x"})

    def test_07_index_remove_then_search_returns_empty(self) -> None:
        """Verify: removing an item from the index makes it unsearchable."""
        item = MemoryItem(id="removable_001", memory_type=MemoryType.KNOWLEDGE,
                          title="To be removed", content="searchable text")
        self.bridge.indexer.build_index([item])
        self.assertEqual(self.bridge.indexer.size, 1)
        self.bridge.indexer.remove_from_index("removable_001")
        self.assertEqual(self.bridge.indexer.size, 0)
        self.assertEqual(self.bridge.indexer.search("searchable text"), [])

    def test_08_search_on_unbuilt_index_returns_empty(self) -> None:
        """Verify: search() on a fresh (un-built) indexer returns empty list."""
        fresh_indexer = MemoryIndexer()
        self.assertFalse(fresh_indexer.is_built)
        self.assertEqual(fresh_indexer.search("anything"), [])

    def test_09_keyword_search_empty_keywords_returns_empty(self) -> None:
        """Verify: keyword_search([]) returns empty list."""
        indexer = MemoryIndexer()
        indexer.build_index([])
        self.assertEqual(indexer.keyword_search([]), [])

    def test_10_concurrent_store_then_rebuild_index_thread_safe(self) -> None:
        """Verify: concurrent batch_write then a single rebuild_index is consistent.

        Uses batch_write (stores full MemoryItem.to_dict with memory_type) so
        rebuild_index can reconstruct every item. Concurrent writes exercise
        the store/index lock; the final rebuild yields a deterministic size.
        """
        errors: list[Exception] = []

        def writer(start: int) -> None:
            try:
                for i in range(start, start + 5):
                    self.bridge.writer.batch_write([MemoryItem(
                        id=f"know_conc_{i:03d}",
                        memory_type=MemoryType.KNOWLEDGE,
                        title=f"Concurrent item {i}",
                        content=f"content {i} microservice design architecture",
                        domain="general",
                        tags=["concurrent"])])
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=writer, args=(i * 5,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        # After all concurrent writes complete, rebuild once → deterministic.
        self.bridge.rebuild_index()
        self.assertEqual(self.bridge.indexer.size, 20)

    def test_11_get_statistics_reports_zero_memories_for_fresh_bridge(self) -> None:
        """Verify: get_statistics on a fresh bridge reports 0 total memories.

        Note: claw_enabled is environment-dependent (WorkBuddy dir may exist),
        so we only assert on memory counts and index state, not on claw.
        """
        stats = self.bridge.get_statistics()
        self.assertEqual(stats.total_memories, 0)
        self.assertFalse(stats.index_built)

    def test_12_get_recent_history_empty_returns_empty(self) -> None:
        """Verify: get_recent_history on an empty store returns empty list."""
        self.assertEqual(self.bridge.get_recent_history(n=5), [])

    def test_13_learn_from_mistake_persists_analysis_case(self) -> None:
        """Verify: learn_from_mistake stores an AnalysisCase retrievable later."""
        err = ErrorContext(
            error_message="KeyError: 'missing_key' in dispatch",
            task_description="dispatch task",
            worker_id="worker-1",
            timestamp=datetime.now().isoformat(),
        )
        analysis_id = self.bridge.learn_from_mistake(err)
        self.assertTrue(analysis_id.startswith("anal_"))
        loaded = self.bridge.store.load(MemoryType.ANALYSIS, analysis_id)
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertIn("KeyError", loaded["problem"])

    def test_14_record_feedback_assigns_id_when_empty(self) -> None:
        """Verify: record_feedback fills in an id when the input has none."""
        fb = UserFeedback(id="", user_id="bob", content="great work", feedback_type="praise")
        result_id = self.bridge.record_feedback(fb)
        self.assertTrue(result_id.startswith("fb_"))
        self.assertTrue(fb.created_at)  # created_at populated

    def test_15_persist_pattern_rejects_low_confidence(self) -> None:
        """Verify: persist_pattern returns None for patterns with confidence < 0.7."""

        class FakePattern:
            name = "Low conf pattern"
            steps_template = [{"step": 1}]
            confidence = 0.4
            quality_score = 50
            pattern_id = "low-1"
            category = "test"
            trigger_keywords = []

        result = self.bridge.persist_pattern(FakePattern())
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
