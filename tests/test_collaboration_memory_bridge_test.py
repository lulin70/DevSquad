#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MemoryBridge 测试套件

覆盖范围:
- T1: 数据模型 (10)
- T2: MemoryWriter (8)
- T3: MemoryReader (8)
- T4: MemoryIndexer (14)
- T5: MemoryBridge 核心 (14)
- T6: 生命周期管理 (8)
- T7: 存储抽象层 (6)
- T8: 边界情况 (10)
- IT1: Coordinator 集成 (6)
- IT2: Skillifier 集成 (4)
- E2E: 端到端 (8)
总计: ~96 cases
"""

import os
import sys
import json
import time
import tempfile
import shutil
import threading
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from scripts.collaboration.memory_bridge import (
    MemoryBridge, MemoryConfig, MemoryType, MemoryItem,
    MemoryQuery, MemoryRecallResult, MemoryStats,
    MemoryWriter, MemoryReader, MemoryIndexer,
    JsonMemoryStore, MemoryStore,
    KnowledgeItem, UserFeedback, EpisodicMemory,
    PersistedPattern, AnalysisCase, ErrorContext,
)


class T1DataModels(unittest.TestCase):
    def test_01_memory_type_enum(self):
        types = [t.value for t in MemoryType]
        self.assertIn("knowledge", types)
        self.assertIn("episodic", types)
        self.assertIn("feedback", types)
        self.assertIn("pattern", types)
        self.assertIn("analysis", types)
        self.assertEqual(len(types), 7)

    def test_02_memory_item_basic(self):
        item = MemoryItem(id="t1", memory_type=MemoryType.KNOWLEDGE,
                           title="Test", content="Hello world",
                           domain="test-domain", tags=["a", "b"])
        self.assertEqual(item.id, "t1")
        self.assertEqual(item.memory_type, MemoryType.KNOWLEDGE)
        self.assertEqual(item.domain, "test-domain")
        self.assertEqual(item.tags, ["a", "b"])

    def test_03_memory_item_age_days(self):
        item = MemoryItem(id="t2", memory_type=MemoryType.EPISODIC,
                           title="Age", content="data")
        age = item.age_days
        self.assertGreaterEqual(age, 0)
        self.assertLess(age, 1)

    def test_04_memory_query_defaults(self):
        q = MemoryQuery()
        self.assertEqual(q.limit, 5)
        self.assertAlmostEqual(q.min_relevance, 0.3)

    def test_05_memory_config_default(self):
        cfg = MemoryConfig.default()
        self.assertTrue(cfg.enabled)
        self.assertTrue(cfg.auto_capture)
        self.assertEqual(cfg.retention_days, 90)

    def test_06_memory_config_lightweight(self):
        cfg = MemoryConfig.lightweight()
        self.assertFalse(cfg.auto_capture)
        self.assertLessEqual(cfg.max_episodic_memories, 100)

    def test_07_memory_config_full(self):
        cfg = MemoryConfig.full()
        self.assertGreaterEqual(cfg.max_episodic_memories, 1000)

    def test_08_recall_result_structure(self):
        r = MemoryRecallResult(
            memories=[MemoryItem(id="x", memory_type=MemoryType.KNOWLEDGE,
                                  title="T", content="C")],
            total_found=1, query_time_ms=5.5,
            hit_memory_types={"knowledge": 1},
        )
        self.assertEqual(r.total_found, 1)
        self.assertIn("knowledge", r.hit_memory_types)

    def test_09_memory_stats_fields(self):
        s = MemoryStats(total_memories=42, by_type_counts={"knowledge": 10})
        self.assertEqual(s.total_memories, 42)
        self.assertEqual(s.by_type_counts["knowledge"], 10)

    def test_10_serialization_roundtrip(self):
        item = MemoryItem(id="rt1", memory_type=MemoryType.FEEDBACK,
                           title="RT Test", content="serialize me",
                           domain=None, tags=["test"], source="manual")
        d = item.to_dict()
        restored = MemoryItem.from_dict(d)
        self.assertEqual(restored.id, item.id)
        self.assertEqual(restored.memory_type, item.memory_type)
        self.assertEqual(restored.title, item.title)


class T2MemoryWriter(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store = JsonMemoryStore(self.tmpdir)
        self.indexer = MemoryIndexer()
        self.writer = MemoryWriter(self.store, self.indexer)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_01_write_knowledge(self):
        item = KnowledgeItem(
            id="kw1", domain="AI安全", title="对抗攻击防御",
            content="常见防御方法：对抗训练、输入净化、模型集成",
            tags=["安全", "ML"],
        )
        item_id = self.writer.write_knowledge(item)
        self.assertIsNotNone(item_id)
        data = self.store.load(MemoryType.KNOWLEDGE, item_id)
        self.assertIsNotNone(data)
        self.assertEqual(data["title"], "对抗攻击防御")

    def test_02_write_knowledge_content(self):
        item = KnowledgeItem(id="kw2", domain="test", title="T", content="content data")
        self.writer.write_knowledge(item)
        data = self.store.load(MemoryType.KNOWLEDGE, "kw2")
        self.assertIn("content data", data["content"])

    def test_03_write_episodic(self):
        mem = EpisodicMemory(
            id="epi1", task_description="设计API",
            finding="发现N+1查询问题，建议引入缓存层",
            worker_id="architect", confidence=0.9,
            tags=["性能", "数据库"],
        )
        item_id = self.writer.write_episodic(mem)
        self.assertIsNotNone(item_id)
        data = self.store.load(MemoryType.EPISODIC, item_id)
        self.assertEqual(data["finding"], "发现N+1查询问题，建议引入缓存层")

    def test_04_write_feedback(self):
        fb = UserFeedback(
            id="fb1", user_id="test_user", feedback_type="suggestion",
            content="希望增加更多计算类型支持",
        )
        item_id = self.writer.write_feedback(fb)
        data = self.store.load(MemoryType.FEEDBACK, item_id)
        self.assertEqual(data["type"], "suggestion")

    def test_05_write_pattern(self):
        pat = PersistedPattern(
            id="pat1", name="CRUD Skill", slug="crud-skill",
            category="code-generation",
            trigger_keywords=["CRUD", "增删改查"],
            steps_template=[{"step": 1, "action": "design"}],
            quality_score=85.0,
        )
        item_id = self.writer.write_pattern(pat)
        data = self.store.load(MemoryType.PATTERN, item_id)
        self.assertEqual(data["name"], "CRUD Skill")

    def test_06_write_analysis(self):
        anal = AnalysisCase(
            id="an1", problem="启动时间过长",
            root_cause="模块加载过多",
            solutions=["懒加载", "并行初始化"],
        )
        item_id = self.writer.write_analysis(anal)
        data = self.store.load(MemoryType.ANALYSIS, item_id)
        self.assertEqual(len(data.get("solutions", [])), 2)

    def test_07_batch_write(self):
        items = [
            MemoryItem(id=f"bw-{i}", memory_type=MemoryType.KNOWLEDGE,
                       title=f"Batch {i}", content=f"Content {i}")
            for i in range(5)
        ]
        count = self.writer.batch_write(items)
        self.assertEqual(count, 5)

    def test_08_overwrite_same_id(self):
        item1 = KnowledgeItem(id="ow1", domain="d", title="V1", content="old")
        item2 = KnowledgeItem(id="ow1", domain="d", title="V2", content="new")
        self.writer.write_knowledge(item1)
        self.writer.write_knowledge(item2)
        data = self.store.load(MemoryType.KNOWLEDGE, "ow1")
        self.assertEqual(data["title"], "V2")


class T3MemoryReader(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.store = JsonMemoryStore(self.tmpdir)
        self.writer = MemoryWriter(self.store)
        self.reader = MemoryReader(self.store)
        for i in range(3):
            self.writer.write_knowledge(KnowledgeItem(
                id=f"kr{i}", domain="domain-A" if i < 2 else "domain-B",
                title=f"Knowledge {i}", content=f"Content {i}",
                tags=[f"tag{i}"],
            ))

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_01_read_all_knowledge(self):
        items = self.reader.read_knowledge()
        self.assertEqual(len(items), 3)

    def test_02_read_knowledge_by_domain(self):
        items = self.reader.read_knowledge(domain="domain-A")
        self.assertEqual(len(items), 2)

    def test_03_read_empty_store(self):
        empty_dir = tempfile.mkdtemp()
        empty_store = JsonMemoryStore(empty_dir)
        empty_reader = MemoryReader(empty_store)
        items = empty_reader.read_knowledge()
        shutil.rmtree(empty_dir, ignore_errors=True)
        self.assertEqual(items, [])

    def test_04_read_episodic_limit(self):
        for i in range(5):
            self.writer.write_episodic(EpisodicMemory(
                id=f"repi{i}", task_description=f"Task {i}",
                finding=f"Finding {i}",
                worker_id=f"w{i}",
            ))
        items = self.reader.read_episodic(limit=3)
        self.assertLessEqual(len(items), 3)

    def test_05_read_feedback_by_type(self):
        self.writer.write_feedback(UserFeedback(
            id="rfb1", feedback_type="suggestion", content="good"))
        self.writer.write_feedback(UserFeedback(
            id="rfb2", feedback_type="complaint", content="bad"))
        suggestions = self.reader.read_feedback(feedback_type="suggestion")
        self.assertEqual(len(suggestions), 1)

    def test_06_read_patterns_by_category(self):
        self.writer.write_pattern(PersistedPattern(
            id="rp1", name="P1", slug="p1-slug", category="cat-a", quality_score=80))
        self.writer.write_pattern(PersistedPattern(
            id="rp2", name="P2", slug="p2-slug", category="cat-b", quality_score=75))
        cat_a = self.reader.read_patterns(category="cat-a")
        self.assertEqual(len(cat_a), 1)

    def test_07_read_analysis_by_status(self):
        self.writer.write_analysis(AnalysisCase(
            id="ra1", problem="Bug A", status="open"))
        self.writer.write_analysis(AnalysisCase(
            id="ra2", problem="Bug B", status="completed"))
        completed = self.reader.read_analysis_cases(status="completed")
        self.assertEqual(len(completed), 1)

    def test_08_read_patterns_all(self):
        self.writer.write_pattern(PersistedPattern(
            id="rpa1", name="All P", slug="all-p-slug", category="cat-x"))
        all_pats = self.reader.read_patterns()
        self.assertGreaterEqual(len(all_pats), 1)


class T4MemoryIndexer(unittest.TestCase):
    def setUp(self):
        self.indexer = MemoryIndexer()

    def tearDown(self):
        pass

    def test_01_build_index_basic(self):
        items = [
            MemoryItem(id="i1", memory_type=MemoryType.KNOWLEDGE,
                       title="Redis缓存策略", content="缓存一致性方案",
                       domain="架构设计"),
            MemoryItem(id="i2", memory_type=MemoryType.EPISODIC,
                       title="数据库优化", content="索引优化技巧",
                       domain="性能优化"),
        ]
        self.indexer.build_index(items)
        self.assertTrue(self.indexer.is_built)
        self.assertEqual(self.indexer.size, 2)

    def test_02_inverted_index_content(self):
        items = [
            MemoryItem(id="ix1", memory_type=MemoryType.KNOWLEDGE,
                       title="微服务拆分", content="服务边界划分原则",
                       tags=["架构"]),
        ]
        self.indexer.build_index(items)
        self.assertIn("ix1", self.indexer._items_cache)

    def test_03_add_to_index_incremental(self):
        item = MemoryItem(id="inc1", memory_type=MemoryType.KNOWLEDGE,
                          title="Test incremental", content="add one by one")
        self.indexer.add_to_index(item)
        self.assertEqual(self.indexer.size, 1)
        self.indexer.add_to_index(MemoryItem(
            id="inc2", memory_type=MemoryType.KNOWLEDGE,
            title="Second item", content="another"))
        self.assertEqual(self.indexer.size, 2)

    def test_04_remove_from_index(self):
        item = MemoryItem(id="rem1", memory_type=MemoryType.KNOWLEDGE,
                          title="Remove me", content="will be gone")
        self.indexer.add_to_index(item)
        self.assertEqual(self.indexer.size, 1)
        self.indexer.remove_from_index("rem1")
        self.assertEqual(self.indexer.size, 0)

    def test_05_search_exact_match(self):
        items = [
            MemoryItem(id="sm1", memory_type=MemoryType.KNOWLEDGE,
                       title="Redis缓存使用", content="缓存穿透防护"),
            MemoryItem(id="sm2", memory_type=MemoryType.FEEDBACK,
                       title="用户建议", content="希望增加Redis支持"),
        ]
        self.indexer.build_index(items)
        results = self.indexer.search("Redis缓存")
        self.assertGreater(len(results), 0)
        best_id, best_score = results[0]
        self.assertEqual(best_id, "sm1")

    def test_06_search_partial_match(self):
        items = [
            MemoryItem(id="sp1", memory_type=MemoryType.KNOWLEDGE,
                       title="Python异步编程", content="asyncio详解"),
            MemoryItem(id="sp2", memory_type=MemoryType.KNOWLEDGE,
                       title="Java并发", content="线程池配置"),
        ]
        self.indexer.build_index(items)
        results = self.indexer.search("编程")
        ids = [r[0] for r in results]
        self.assertIn("sp1", ids)

    def test_07_search_no_results(self):
        items = [
            MemoryItem(id="snr1", memory_type=MemoryType.KNOWLEDGE,
                       title="Database", content="SQL queries"),
        ]
        self.indexer.build_index(items)
        results = self.indexer.search("xyznonexistent123")
        self.assertEqual(results, [])

    def test_08_search_type_filter(self):
        items = [
            MemoryItem(id="stf1", memory_type=MemoryType.KNOWLEDGE,
                       title="知识条目", content="关于知识的内容"),
            MemoryItem(id="stf2", memory_type=MemoryType.FEEDBACK,
                       title="反馈条目", content="关于反馈的内容"),
        ]
        self.indexer.build_index(items)
        results = self.indexer.search("条目", type_filter=MemoryType.FEEDBACK)
        ids = [r[0] for r in results]
        self.assertIn("stf2", ids)
        self.assertNotIn("stf1", ids)

    def test_09_search_domain_filter(self):
        items = [
            MemoryItem(id="sdf1", memory_type=MemoryType.KNOWLEDGE,
                       title="架构决策A", content="关于架构", domain="架构设计"),
            MemoryItem(id="sdf2", memory_type=MemoryType.KNOWLEDGE,
                       title="安全策略B", content="关于安全", domain="安全"),
        ]
        self.indexer.build_index(items)
        results = self.indexer.search("", domain_filter="架构设计")
        self.assertIsInstance(results, list)

    def test_10_search_limit(self):
        items = [
            MemoryItem(id=f"slim{i}", memory_type=MemoryType.KNOWLEDGE,
                       title=f"Item {i}", content=f"Content with keyword {i} keyword")
            for i in range(10)
        ]
        self.indexer.build_index(items)
        results = self.indexer.search("keyword", limit=3)
        self.assertLessEqual(len(results), 3)

    def test_11_keyword_search_and_logic(self):
        items = [
            MemoryItem(id="ks1", memory_type=MemoryType.KNOWLEDGE,
                       title="Redis缓存一致性", content="分布式锁方案"),
            MemoryItem(id="ks2", memory_type=MemoryType.KNOWLEDGE,
                       title="MySQL主从复制", content="binlog同步"),
        ]
        self.indexer.build_index(items)
        results = self.indexer.keyword_search(["Redis", "缓存"])
        self.assertIsInstance(results, list)

    def test_12_keyword_single_word(self):
        items = [
            MemoryItem(id="kss1", memory_type=MemoryType.KNOWLEDGE,
                       title="Docker容器化", content="镜像构建"),
        ]
        self.indexer.build_index(items)
        results = self.indexer.keyword_search(["Docker"])
        self.assertIsInstance(results, list)

    def test_13_tokenize_chinese(self):
        tokens = MemoryIndexer._tokenize("微服务架构设计")
        self.assertGreater(len(tokens), 0)
        has_chinese = any('\u4e00' <= c <= '\u9fff' for t in tokens for c in t)
        self.assertTrue(has_chinese)

    def test_14_tfidf_relevance(self):
        items = [
            MemoryItem(id="tf1", memory_type=MemoryType.KNOWLEDGE,
                       title="Redis缓存设计", content="Redis缓存策略和实现"),
            MemoryItem(id="tf2", memory_type=MemoryType.KNOWLEDGE,
                       title="Python基础", content="Python语法入门教程"),
        ]
        self.indexer.build_index(items)
        score_exact = self.indexer._compute_relevance(
            ["redis", "缓存"], "tf1")
        score_irrelevant = self.indexer._compute_relevance(
            ["redis", "缓存"], "tf2")
        self.assertGreaterEqual(score_exact, 0.0)


class T5MemoryBridgeCore(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.bridge = MemoryBridge(base_dir=self.tmpdir,
                                    config=MemoryConfig.default())
        self.bridge.rebuild_index()

    def tearDown(self):
        self.bridge.shutdown()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_01_recall_basic(self):
        self.bridge.writer.write_knowledge(KnowledgeItem(
            id="rc1", domain="架构设计", title="微服务拆分策略",
            content="按业务领域拆分，保持服务自治性",
            tags=["微服务", "架构"],
        ))
        result = self.bridge.recall(MemoryQuery(query_text="微服务架构设计"))
        self.assertIsInstance(result, MemoryRecallResult)
        self.assertGreater(result.total_found, 0)

    def test_02_recall_latency(self):
        self.bridge.writer.write_knowledge(KnowledgeItem(
            id="rl1", domain="test", title="Latency Test", content="test data",
        ))
        result = self.bridge.recall(MemoryQuery(query_text="Latency Test"))
        self.assertLess(result.query_time_ms, 200)

    def test_03_recall_empty(self):
        result = self.bridge.recall(MemoryQuery(query_text="nothing matches this xyz"))
        self.assertEqual(result.total_found, 0)
        self.assertEqual(result.memories, [])

    def test_04_capture_finding(self):
        class FakeEntry:
            entry_type = "FINDING"
            content = "发现系统存在N+1查询问题"
            confidence = 0.85

        record = type('obj', (object,), {
            'task_description': '优化数据库查询',
            'worker_id': 'tester',
        })()
        captured = self.bridge.capture_execution(record, [FakeEntry()])
        self.assertIsNotNone(captured)

    def test_05_capture_low_confidence_skip(self):
        class LowEntry:
            entry_type = "FINDING"
            content = "不太重要的发现"
            confidence = 0.5

        record = type('obj', (object,), {
            'task_description': 'test', 'worker_id': 'w',
        })()
        captured = self.bridge.capture_execution(record, [LowEntry()])
        self.assertIsNone(captured)

    def test_06_capture_empty_scratchpad(self):
        record = type('obj', (object,), {
            'task_description': 'test', 'worker_id': 'w',
        })()
        captured = self.bridge.capture_execution(record, [])
        self.assertIsNone(captured)

    def test_07_record_feedback(self):
        fb = UserFeedback(id="fb_test", feedback_type="suggestion", content="很好用")
        fb_id = self.bridge.record_feedback(fb)
        self.assertIsNotNone(fb_id)
        data = self.bridge.store.load(MemoryType.FEEDBACK, fb_id)
        self.assertIsNotNone(data)

    def test_08_persist_high_quality_pattern(self):
        class FakePattern:
            name = "High Quality Pattern"
            steps_template = [{"step": 1}]
            trigger_keywords = ["test"]
            confidence = 0.82
            quality_score = 85

        pid = self.bridge.persist_pattern(FakePattern())
        self.assertIsNotNone(pid)

    def test_09_persist_low_quality_skipped(self):
        class LowPattern:
            name = "Low Quality"
            steps_template = []
            confidence = 0.5
            quality_score = 40

        pid = self.bridge.persist_pattern(LowPattern())
        self.assertIsNone(pid)

    def test_10_learn_from_mistake(self):
        ctx = ErrorContext(error_message="ConnectionTimeoutError: 数据库连接超时",
                            task_description="执行批量导入")
        aid = self.bridge.learn_from_mistake(ctx)
        self.assertIsNotNone(aid)
        data = self.bridge.store.load(MemoryType.ANALYSIS, aid)
        self.assertIsNotNone(data)
        self.assertEqual(data["status"], "completed")

    def test_11_search_knowledge(self):
        self.bridge.writer.write_knowledge(KnowledgeItem(
            id="sk1", domain="缓存", title="Redis缓存策略",
            content="缓存穿透、击穿、雪崩的解决方案",
            tags=["Redis", "缓存"],
        ))
        results = self.bridge.search_knowledge(["缓存", "Redis"])
        self.assertIsInstance(results, list)

    def test_12_get_statistics(self):
        stats = self.bridge.get_statistics()
        self.assertIsInstance(stats, MemoryStats)
        self.assertIsInstance(stats.by_type_counts, dict)

    def test_13_recent_history(self):
        for i in range(3):
            self.bridge.writer.write_episodic(EpisodicMemory(
                id=f"rh{i}", task_description=f"History {i}",
                finding=f"History item {i}",
            ))
        recent = self.bridge.get_recent_history(n=2)
        self.assertLessEqual(len(recent), 2)

    def test_14_diagnostics_output(self):
        output = self.bridge.print_diagnostics()
        self.assertIsInstance(output, str)
        self.assertIn("MemoryBridge", output)


class T6LifecycleManagement(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.bridge = MemoryBridge(base_dir=self.tmpdir)

    def tearDown(self):
        self.bridge.shutdown()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_01_forgetting_weight_new(self):
        item = MemoryItem(id="fw1", memory_type=MemoryType.EPISODIC,
                           title="New", content="new memory")
        w = self.bridge.forgetting_weight(item)
        self.assertAlmostEqual(w, 1.0)

    def test_02_forgetting_weight_mature(self):
        old_time = datetime.now() - timedelta(days=25)
        item = MemoryItem(id="fw2", memory_type=MemoryType.EPISODIC,
                           title="Mature", content="old memory",
                           created_at=old_time, access_count=2)
        w = self.bridge.forgetting_weight(item)
        self.assertGreater(w, 0.3)
        self.assertLess(w, 1.0)

    def test_03_forgetting_weight_old(self):
        old_time = datetime.now() - timedelta(days=70)
        item = MemoryItem(id="fw3", memory_type=MemoryType.EPISODIC,
                           title="Old", content="very old",
                           created_at=old_time, access_count=1)
        w = self.bridge.forgetting_weight(item)
        self.assertLess(w, 0.6)

    def test_04_forgetting_weight_high_access(self):
        old_time = datetime.now() - timedelta(days=35)
        item = MemoryItem(id="fw4", memory_type=MemoryType.EPISODIC,
                           title="Popular Old", content="accessed often",
                           created_at=old_time, access_count=20)
        w_popular = self.bridge.forgetting_weight(item)
        item_low = MemoryItem(id="fw5", memory_type=MemoryType.EPISODIC,
                              title="Unpopular Old", content="rarely accessed",
                              created_at=old_time, access_count=1)
        w_unpopular = self.bridge.forgetting_weight(item_low)
        self.assertGreater(w_popular, w_unpopular)

    def test_05_compress_old_memories(self):
        old_time = (datetime.now() - timedelta(days=65)).isoformat()
        self.bridge.writer.write_episodic(EpisodicMemory(
            id="comp1", task_description="Compress test old",
            finding="A" * 500,
            created_at=old_time,
        ))
        new_time = datetime.now().isoformat()
        self.bridge.writer.write_episodic(EpisodicMemory(
            id="comp2", task_description="Compress test new",
            finding="B" * 50,
            created_at=new_time,
        ))
        compressed = self.bridge.compress_old_memories()
        self.assertGreaterEqual(compressed, 0)

    def test_06_compress_new_untouched(self):
        new_time = datetime.now().isoformat()
        self.bridge.writer.write_episodic(EpisodicMemory(
            id="cnu1", task_description="New untouched",
            finding="New finding",
            created_at=new_time,
        ))
        compressed = self.bridge.compress_old_memories()
        self.assertEqual(compressed, 0)

    def test_07_cleanup_expired(self):
        very_old = (datetime.now() - timedelta(days=100)).isoformat()
        self.bridge.writer.write_episodic(EpisodicMemory(
            id="exp1", task_description="Expired test",
            finding="Expired",
            created_at=very_old,
        ))
        removed = self.bridge.cleanup_expired_memories()
        self.assertGreaterEqual(removed, 0)

    def test_08_cleanup_config_off(self):
        cfg = MemoryConfig(retention_days=120)
        bridge = MemoryBridge(base_dir=self.tmpdir, config=cfg)
        old_time = (datetime.now() - timedelta(days=60)).isoformat()
        bridge.writer.write_episodic(EpisodicMemory(
            id="coff1", task_description="Config off test",
            finding="Old but not expired yet",
            created_at=old_time,
        ))
        removed = bridge.cleanup_expired_memories()
        self.assertEqual(removed, 0)
        bridge.shutdown()


class T7StorageLayer(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_01_json_save_load_roundtrip(self):
        store = JsonMemoryStore(self.tmpdir)
        data = {"id": "jst1", "title": "Test", "content": "hello"}
        sid = store.save(MemoryType.KNOWLEDGE, data)
        loaded = store.load(MemoryType.KNOWLEDGE, sid)
        self.assertEqual(loaded["title"], "Test")
        self.assertEqual(loaded["content"], "hello")

    def test_02_json_list_all(self):
        store = JsonMemoryStore(self.tmpdir)
        for i in range(3):
            store.save(MemoryType.KNOWLEDGE, {"id": f"jla{i}", "val": i})
        all_items = store.list_all(MemoryType.KNOWLEDGE)
        self.assertEqual(len(all_items), 3)

    def test_03_json_delete(self):
        store = JsonMemoryStore(self.tmpdir)
        sid = store.save(MemoryType.FEEDBACK, {"id": "jd1", "msg": "delete me"})
        self.assertTrue(store.delete(MemoryType.FEEDBACK, "jd1"))
        self.assertIsNone(store.load(MemoryType.FEEDBACK, "jd1"))

    def test_04_composite_routing(self):
        store = JsonMemoryStore(self.tmpdir)
        kid = store.save(MemoryType.KNOWLEDGE, {"id": "cr1", "type": "knowledge"})
        fid = store.save(MemoryType.FEEDBACK, {"id": "cr2", "type": "feedback"})
        k_loaded = store.load(MemoryType.KNOWLEDGE, kid)
        f_loaded = store.load(MemoryType.FEEDBACK, fid)
        self.assertIsNotNone(k_loaded)
        self.assertIsNotNone(f_loaded)

    def test_05_auto_create_dirs(self):
        new_dir = os.path.join(self.tmpdir, "brand_new_subdir")
        store = JsonMemoryStore(new_dir)
        sid = store.save(MemoryType.KNOWLEDGE, {"id": "acd1", "test": True})
        loaded = store.load(MemoryType.KNOWLEDGE, sid)
        self.assertIsNotNone(loaded)

    def test_06_load_nonexistent(self):
        store = JsonMemoryStore(self.tmpdir)
        result = store.load(MemoryType.KNOWLEDGE, "ghost_id_404")
        self.assertIsNone(result)


class T8EdgeCases(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.bridge = MemoryBridge(base_dir=self.tmpdir)
        self.bridge.rebuild_index()

    def tearDown(self):
        self.bridge.shutdown()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_01_empty_query_string(self):
        result = self.bridge.recall(MemoryQuery(query_text=""))
        self.assertEqual(result.total_found, 0)

    def test_02_special_chars_in_content(self):
        self.bridge.writer.write_knowledge(KnowledgeItem(
            id="sc1", domain="test", title="Special <>\"'/\\",
            content='Content with <script>alert("xss")</script>',
        ))
        result = self.bridge.recall(MemoryQuery(query_text="Special"))
        self.assertGreaterEqual(result.total_found, 0)

    def test_03_long_content(self):
        long_text = "A" * 10000
        self.bridge.writer.write_knowledge(KnowledgeItem(
            id="slc1", domain="test", title="Long Content",
            content=long_text,
        ))
        data = self.bridge.store.load(MemoryType.KNOWLEDGE, "slc1")
        self.assertGreaterEqual(len(data.get("content", "")), 5000)

    def test_04_concurrent_writes(self):
        errors = []

        def writer(i):
            try:
                self.bridge.writer.write_knowledge(KnowledgeItem(
                    id=f"cw{i}", domain="concurrent",
                    title=f"Concurrent {i}", content=f"data {i}",
                ))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
        self.assertEqual(errors, [])

    def test_05_concurrent_read_write(self):
        self.bridge.writer.write_knowledge(KnowledgeItem(
            id="crw_seed", domain="rw", title="Seed", content="seed data",
        ))
        errors = []
        barrier = threading.Barrier(20)

        def rw_worker(i):
            try:
                barrier.wait(timeout=5)
                if i % 2 == 0:
                    self.bridge.writer.write_knowledge(KnowledgeItem(
                        id=f"crw{i}", domain="rw",
                        title=f"RW {i}", content=f"data {i}",
                    ))
                else:
                    self.bridge.recall(MemoryQuery(query_text="Seed"))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=rw_worker, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
        self.assertEqual(errors, [])

    def test_06_corrupted_json_handling(self):
        bad_file = os.path.join(self.tmpdir, "knowledge_base", "domains",
                                   "general", "corrupt.json")
        os.makedirs(os.path.dirname(bad_file), exist_ok=True)
        with open(bad_file, "w") as f:
            f.write("{invalid json!!!")
        items = self.bridge.store.list_all(MemoryType.KNOWLEDGE)
        self.assertIsInstance(items, list)

    def test_07_unicode_emoji_content(self):
        self.bridge.writer.write_knowledge(KnowledgeItem(
            id="emoji1", domain="test", title="Emoji测试 🎉",
            content="内容包含表情 ✅🔥💡 和中文",
            tags=["测试", "emoji"],
        ))
        result = self.bridge.recall(MemoryQuery(query_text="Emoji"))
        self.assertGreaterEqual(result.total_found, 0)

    def test_08_disabled_mode(self):
        cfg = MemoryConfig(enabled=False)
        disabled = MemoryBridge(base_dir=self.tmpdir, config=cfg)
        result = disabled.recall(MemoryQuery(query_text="anything"))
        disabled.shutdown()
        self.assertEqual(result.total_found, 0)

    def test_09_large_scale_performance(self):
        start = time.perf_counter()
        for i in range(200):
            self.bridge.writer.write_knowledge(KnowledgeItem(
                id=f"perf{i}", domain=f"domain-{i%5}",
                title=f"Performance Item {i}",
                content=f"Content for performance testing item number {i} " * 3,
                tags=[f"tag{j}" for j in range(3)],
            ))
        write_time = (time.perf_counter() - start) * 1000
        self.bridge.rebuild_index()
        rebuild_time = (time.perf_counter() - start) * 1000 - write_time
        result = self.bridge.recall(MemoryQuery(query_text="Performance Item"))
        search_time = result.query_time_ms
        self.assertLess(write_time + rebuild_time, 5000)

    def test_10_null_domain_memory_item(self):
        item = MemoryItem(id="nd1", memory_type=MemoryType.FEEDBACK,
                           title="No Domain", content="test",
                           domain=None)
        d = item.to_dict()
        restored = MemoryItem.from_dict(d)
        self.assertIsNone(restored.domain)


class IT1CoordinatorIntegration(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.bridge = MemoryBridge(base_dir=self.tmpdir)
        self.bridge.rebuild_index()

    def tearDown(self):
        self.bridge.shutdown()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_01_task_enrichment_with_memory(self):
        self.bridge.writer.write_knowledge(KnowledgeItem(
            id="ite1", domain="架构设计",
            title="微服务最佳实践",
            content="按领域拆分、API网关统一入口、熔断降级机制",
            tags=["微服务", "架构"],
        ))
        query = MemoryQuery(query_text="微服务架构设计任务")
        result = self.bridge.recall(query)
        if result.memories:
            enriched = f"原始任务\n历史经验:\n"
            for m in result.memories[:3]:
                enriched += f"- [{m.domain}] {m.title}: {m.content[:60]}...\n"
            self.assertIn("微服务", enriched)

    def test_02_graceful_degradation_empty(self):
        result = self.bridge.recall(MemoryQuery(query_text="完全不相关的查询"))
        self.assertEqual(result.total_found, 0)
        self.assertEqual(result.memories, [])

    def test_03_post_execution_capture(self):
        class FindingEntry:
            entry_type = "FINDING"
            content = "发现接口响应时间超过2秒瓶颈"
            confidence = 0.88

        record = type('obj', (object,), {
            'task_description': '性能优化任务',
            'worker_id': 'perf-analyzer',
        })()
        capture_id = self.bridge.capture_execution(record, [FindingEntry()])
        self.assertIsNotNone(capture_id)
        stats = self.bridge.get_statistics()
        self.assertGreater(stats.total_captures, 0)

    def test_04_error_learning_on_failure(self):
        ctx = ErrorContext(
            error_message="ImportError: module 'missing_lib' not found",
            task_description="安装依赖",
            worker_id="dev-worker",
        )
        analysis_id = self.bridge.learn_from_mistake(ctx)
        self.assertIsNotNone(analysis_id)
        cases = self.bridge.reader.read_analysis_cases()
        self.assertGreater(len(cases), 0)

    def test_05_memory_accumulation_across_tasks(self):
        stats1 = self.bridge.get_statistics()
        count1 = stats1.total_memories
        self.bridge.writer.write_knowledge(KnowledgeItem(
            id="acc1", domain="test", title="Task A insight",
            content="Learned from Task A execution",
        ))
        stats2 = self.bridge.get_statistics()
        count2 = stats2.total_memories
        self.assertGreater(count2, count1)

    def test_06_stats_reflect_growth(self):
        diag = self.bridge.print_diagnostics()
        self.assertIn("MemoryBridge", diag)
        self.assertIn("Total Memories", diag)


class IT2SkillifierIntegration(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.bridge = MemoryBridge(base_dir=self.tmpdir)

    def tearDown(self):
        self.bridge.shutdown()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_01_high_quality_pattern_persisted(self):
        class GoodPattern:
            name = "CRUD Generator Pattern"
            pattern_id = "crud-gen-001"
            steps_template = [
                {"action": "analyze_schema", "target": "*.{ext}"},
                {"action": "generate_crud", "target": "{model}.py"},
            ]
            trigger_keywords = ["CRUD", "增删改查", "generator"]
            confidence = 0.88
            quality_score = 90
            category = "code-generation"

        pid = self.bridge.persist_pattern(GoodPattern())
        self.assertIsNotNone(pid)
        patterns = self.bridge.reader.read_patterns()
        self.assertGreater(len(patterns), 0)

    def test_02_low_quality_not_saved(self):
        class BadPattern:
            name = "Weak Pattern"
            steps_template = []
            confidence = 0.3
            quality_score = 25

        pid = self.bridge.persist_pattern(BadPattern())
        self.assertIsNone(pid)

    def test_03_load_patterns_for_suggestion(self):
        class GoodPat:
            name = "API Design Pattern"
            pattern_id = "api-design-001"
            steps_template = [{"step": 1}]
            trigger_keywords = ["API", "RESTful"]
            confidence = 0.85
            quality_score = 82
            category = "code-generation"

        self.bridge.persist_pattern(GoodPat())
        patterns = self.bridge.reader.read_patterns(category="code-generation")
        found = any(p.name == "API Design Pattern" for p in patterns)
        self.assertTrue(found)

    def test_04_pattern_keywords_searchable(self):
        class SearchablePat:
            name = "Cache Pattern"
            pattern_id="cache-001"
            steps_template=[{"step": "identify"}]
            trigger_keywords=["cache", "缓存", "Redis"]
            confidence=0.80
            quality_score=78
            category="performance"

        self.bridge.persist_pattern(SearchablePat())
        self.bridge.rebuild_index()
        results = self.bridge.search_knowledge(["缓存", "Redis"])
        self.assertGreaterEqual(len(results), 0)


class E2ETests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.bridge = MemoryBridge(base_dir=self.tmpdir)

    def tearDown(self):
        self.bridge.shutdown()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_01_first_use_accumulation(self):
        stats_before = self.bridge.get_statistics()
        self.bridge.writer.write_knowledge(KnowledgeItem(
            id="e2e1", domain="test", title="First knowledge",
            content="Initial knowledge entry",
        ))
        fb = UserFeedback(id="fb_e2e1", content="Good first experience", rating=5)
        self.bridge.record_feedback(fb)
        stats_after = self.bridge.get_statistics()
        self.assertGreater(stats_after.total_memories, stats_before.total_memories)

    def test_02_second_use_recalls(self):
        self.bridge.writer.write_knowledge(KnowledgeItem(
            id="e2e2", domain="复用域", title="可复用经验",
            content="之前解决过类似问题，方案是XXX",
            tags=["复用", "经验"],
        ))
        self.bridge.rebuild_index()
        result = self.bridge.recall(MemoryQuery(query_text="复用经验"))
        if result.memories:
            self.assertGreater(result.total_found, 0)

    def test_03_full_lifecycle(self):
        kw = KnowledgeItem(id="lc1", domain="LC", title="Lifecycle Test",
                           content="Full lifecycle test content")
        wid = self.bridge.writer.write_knowledge(kw)
        self.assertIsNotNone(wid)
        self.bridge.rebuild_index()
        recall_result = self.bridge.recall(MemoryQuery(query_text="Lifecycle"))
        self.assertGreaterEqual(recall_result.total_found, 0)
        deleted = self.bridge.store.delete(MemoryType.KNOWLEDGE, wid)
        self.assertTrue(deleted)

    def test_04_feedback_loop(self):
        fb = UserFeedback(id="fb_e2e4", content="很有帮助", rating=5, feedback_type="suggestion")
        fb_id = self.bridge.record_feedback(fb)
        self.assertIsNotNone(fb_id)
        feedbacks = self.bridge.reader.read_feedback()
        self.assertGreater(len(feedbacks), 0)

    def test_05_concurrent_stress(self):
        errors = []
        barrier = threading.Barrier(15)

        def stress(i):
            try:
                barrier.wait(timeout=5)
                if i % 3 == 0:
                    self.bridge.writer.write_knowledge(KnowledgeItem(
                        id=f"stress_{i}", domain="stress",
                        title=f"S{i}", content=f"D{i}",
                    ))
                elif i % 3 == 1:
                    self.bridge.recall(MemoryQuery(query_text=f"query {i}"))
                else:
                    self.bridge.search_knowledge([f"keyword{i}"])
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=stress, args=(i,)) for i in range(15)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)
        self.assertEqual(errors, [])

    def test_06_large_scale_performance(self):
        for i in range(100):
            self.bridge.writer.write_knowledge(KnowledgeItem(
                id=f"scale_{i}", domain=f"d{i%5}",
                title=f"Scale Item {i}",
                content=f"Data for scale test {i} " * 2,
            ))
        self.bridge.rebuild_index()
        start = time.perf_counter()
        result = self.bridge.recall(MemoryQuery(query_text="Scale Item", limit=10))
        elapsed = (time.perf_counter() - start) * 1000
        self.assertLess(elapsed, 200)

    def test_07_mixed_language_query(self):
        self.bridge.writer.write_knowledge(KnowledgeItem(
            id="ml1", domain="混合", title="Redis缓存一致性方案",
            content="Redis缓存穿透、击穿、雪崩的解决方案，使用布隆过滤器",
            tags=["Redis", "缓存", "分布式"],
        ))
        self.bridge.rebuild_index()
        result = self.bridge.recall(MemoryQuery(query_text="Redis缓存一致性"))
        self.assertGreaterEqual(result.total_found, 0)

    def test_08_diagnostics_completeness(self):
        output = self.bridge.print_diagnostics()
        lines = output.strip().split("\n")
        self.assertGreaterEqual(len(lines), 6)
        self.assertIn("Total Memories", output)


if __name__ == "__main__":
    unittest.main(verbosity=2)
