#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
V3 Dispatcher 集成测试

测试 MultiAgentDispatcher 的端到端功能：
- 任务分析和角色匹配
- 完整调度流程（Coordinator → Worker → Scratchpad）
- 所有 v3 组件集成（Warmup/Compress/Permission/Memory/Skillify）
- Dry-run 模式
- 错误处理和边界条件
"""

import os
import sys
import unittest
import tempfile
import shutil
import time
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from scripts.collaboration.dispatcher import (
    MultiAgentDispatcher,
    DispatchResult,
    create_dispatcher,
    quick_collaborate,
    ROLE_TEMPLATES,
)


class TestT1_DispatcherDataModels(unittest.TestCase):
    """T1: 数据模型测试"""

    def test_01_dispatch_result_default(self):
        r = DispatchResult(success=True, task_description="test")
        self.assertTrue(r.success)
        self.assertEqual(r.task_description, "test")
        self.assertEqual(r.matched_roles, [])
        self.assertEqual(r.duration_seconds, 0.0)
        self.assertIsInstance(r.errors, list)

    def test_02_dispatch_result_to_dict(self):
        r = DispatchResult(
            success=True,
            task_description="test task",
            matched_roles=["architect", "tester"],
            summary="done",
            duration_seconds=1.5,
            errors=["warn1"],
        )
        d = r.to_dict()
        self.assertEqual(d["success"], True)
        self.assertEqual(d["task_description"], "test task")
        self.assertEqual(d["matched_roles"], ["architect", "tester"])
        self.assertIn("warn1", d["errors"])

    def test_03_dispatch_result_to_markdown(self):
        r = DispatchResult(
            success=True,
            task_description="设计系统",
            matched_roles=["architect"],
            summary="完成设计",
            duration_seconds=2.0,
            worker_results=[{"role": "architect", "success": True, "output": "架构文档"}],
        )
        md = r.to_markdown()
        self.assertIn("Multi-Agent", md)
        self.assertIn("设计系统", md)
        self.assertIn("✅ 成功", md)
        self.assertIn("architect", md)

    def test_04_dispatch_result_to_markdown_failure(self):
        r = DispatchResult(
            success=False,
            task_description="失败任务",
            errors=["error1", "error2"],
        )
        md = r.to_markdown()
        self.assertIn("❌ 失败", md)
        self.assertIn("error1", md)

    def test_05_role_templates_complete(self):
        expected_roles = ["architect", "product-manager", "tester", "solo-coder", "ui-designer"]
        for rid in expected_roles:
            self.assertIn(rid, ROLE_TEMPLATES)
            self.assertIn("name", ROLE_TEMPLATES[rid])
            self.assertIn("prompt", ROLE_TEMPLATES[rid])
            self.assertIn("keywords", ROLE_TEMPLATES[rid])

    def test_06_role_keywords_non_empty(self):
        for rid, info in ROLE_TEMPLATES.items():
            self.assertGreater(len(info["keywords"]), 0, f"{rid} has no keywords")


class TestT2_TaskAnalysis(unittest.TestCase):
    """T2: 任务分析与角色匹配"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="mas_test_t2_")
        self.disp = MultiAgentDispatcher(
            persist_dir=self.tmp,
            enable_warmup=False,
            enable_memory=False,
            enable_skillify=False,
        )

    def tearDown(self):
        self.disp.shutdown()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_01_match_architect(self):
        roles = self.disp.analyze_task("设计微服务架构，支持高并发")
        role_ids = [r["role_id"] for r in roles]
        self.assertIn("architect", role_ids)

    def test_02_match_tester(self):
        roles = self.disp.analyze_task("编写单元测试和自动化测试用例")
        role_ids = [r["role_id"] for r in roles]
        self.assertIn("tester", role_ids)

    def test_03_match_solo_coder(self):
        roles = self.disp.analyze_task("实现用户登录功能代码开发")
        role_ids = [r["role_id"] for r in roles]
        self.assertIn("solo-coder", role_ids)

    def test_04_match_ui_designer(self):
        roles = self.disp.analyze_task("设计前端UI界面和交互原型")
        role_ids = [r["role_id"] for r in roles]
        self.assertIn("ui-designer", role_ids)

    def test_05_match_product_manager(self):
        roles = self.disp.analyze_task("编写PRD需求文档和用户故事")
        role_ids = [r["role_id"] for r in roles]
        self.assertIn("product-manager", role_ids)

    def test_06_multi_role_match(self):
        roles = self.disp.analyze_task("设计系统架构并编写测试用例")
        role_ids = [r["role_id"] for r in roles]
        self.assertIn("architect", role_ids)
        self.assertIn("tester", role_ids)

    def test_07_no_match_fallback(self):
        roles = self.disp.analyze_task("随便说点什么不相关的话")
        self.assertGreater(len(roles), 0)
        self.assertEqual(roles[0]["role_id"], "solo-coder")

    def test_08_confidence_ordering(self):
        roles = self.disp.analyze_task("设计架构并测试")
        confidences = [r["confidence"] for r in roles]
        self.assertEqual(confidences, sorted(confidences, reverse=True))

    def test_09_return_structure(self):
        roles = self.disp.analyze_task("测试任务")
        for r in roles:
            self.assertIn("role_id", r)
            self.assertIn("name", r)
            self.assertIn("confidence", r)
            self.assertIn("reason", r)

    def test_10_explicit_roles_override(self):
        result = self.disp.dispatch("测试任务", roles=["architect"])
        self.assertIn("architect", result.matched_roles)


class TestT3_FullDispatch(unittest.TestCase):
    """T3: 完整调度流程"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="mas_test_t3_")
        self.disp = MultiAgentDispatcher(
            persist_dir=self.tmp,
            enable_warmup=True,
            enable_compression=True,
            enable_permission=True,
            enable_memory=True,
            enable_skillify=True,
        )

    def tearDown(self):
        self.disp.shutdown()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_01_single_role_dispatch(self):
        result = self.disp.dispatch("设计用户认证模块的架构")
        self.assertIsInstance(result, DispatchResult)
        self.assertIsInstance(result.summary, str)
        self.assertGreater(result.duration_seconds, 0)

    def test_02_multi_role_dispatch(self):
        result = self.disp.dispatch("设计架构并编写测试方案",
                                     roles=["architect", "tester"])
        self.assertIsInstance(result.matched_roles, list)
        self.assertGreaterEqual(len(result.matched_roles), 2)

    def test_03_dispatch_has_worker_results(self):
        result = self.disp.dispatch("实现一个简单的功能")
        self.assertIsInstance(result.worker_results, list)

    def test_04_dispatch_has_scratchpad(self):
        result = self.disp.dispatch("分析项目结构")
        self.assertIsInstance(result.scratchpad_summary, str)

    def test_05_dispatch_to_dict_roundtrip(self):
        result = self.disp.dispatch("快速任务")
        d = result.to_dict()
        self.assertIn("success", d)
        self.assertIn("task_description", d)
        self.assertIn("matched_roles", d)
        self.assertIn("duration_seconds", d)

    def test_06_dispatch_to_markdown_valid(self):
        result = self.disp.dispatch("生成报告的任务")
        md = result.to_markdown()
        self.assertIn("#", md)
        self.assertGreater(len(md), 50)

    def test_07_timing_info_present(self):
        result = self.disp.dispatch("计时测试")
        self.assertIn("timing", result.details)
        self.assertIsInstance(result.details["timing"], dict)
        timing = result.details["timing"]
        self.assertIn("analyze", timing)
        self.assertIn("execute", timing)

    def test_08_dry_run_mode(self):
        result = self.disp.dispatch("模拟任务", dry_run=True)
        self.assertTrue(result.success)
        self.assertIn("DRY RUN", result.summary)
        self.assertEqual(len(result.worker_results), 0)

    def test_09_consensus_mode(self):
        result = self.disp.dispatch("需要共识的决策", mode="consensus")
        self.assertIsInstance(result.consensus_records, list)

    def test_10_sequential_mode(self):
        result = self.disp.dispatch("顺序执行任务", mode="sequential")
        self.assertIsInstance(result, DispatchResult)


class TestT4_ComponentIntegration(unittest.TestCase):
    """T4: 各组件集成验证"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="mas_test_t4_")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_01_warmup_enabled(self):
        disp = MultiAgentDispatcher(persist_dir=self.tmp, enable_warmup=True)
        status = disp.get_status()
        self.assertTrue(status["components"]["warmup_manager"])
        metrics = status.get("warmup_metrics")
        self.assertIsNotNone(metrics)
        disp.shutdown()

    def test_02_warmup_disabled(self):
        disp = MultiAgentDispatcher(persist_dir=self.tmp, enable_warmup=False)
        status = disp.get_status()
        self.assertIsNone(status.get("warmup_metrics"))
        disp.shutdown()

    def test_03_compression_enabled(self):
        disp = MultiAgentDispatcher(persist_dir=self.tmp, enable_compression=True)
        result = disp.dispatch("压缩测试任务" * 10)
        if result.compression_info:
            self.assertIsInstance(result.compression_info, dict)
        disp.shutdown()

    def test_04_compression_disabled(self):
        disp = MultiAgentDispatcher(persist_dir=self.tmp, enable_compression=False)
        result = disp.dispatch("无压缩任务")
        self.assertIsNone(result.compression_info)
        disp.shutdown()

    def test_05_permission_checks_present(self):
        disp = MultiAgentDispatcher(persist_dir=self.tmp, enable_permission=True)
        result = disp.dispatch("权限检查任务")
        self.assertIsInstance(result.permission_checks, list)
        if result.permission_checks:
            pc = result.permission_checks[0]
            self.assertIn("action", pc)
            self.assertIn("allowed", pc)
        disp.shutdown()

    def test_06_permission_disabled(self):
        disp = MultiAgentDispatcher(persist_dir=self.tmp, enable_permission=False)
        result = disp.dispatch("无权限任务")
        self.assertEqual(len(result.permission_checks), 0)
        disp.shutdown()

    def test_07_memory_bridge_stats(self):
        mem_dir = os.path.join(self.tmp, "mem_store")
        disp = MultiAgentDispatcher(
            persist_dir=self.tmp,
            memory_dir=mem_dir,
            enable_memory=True,
        )
        result = disp.dispatch("记忆桥接测试")
        if result.memory_stats:
            self.assertIn("total_memories", result.memory_stats)
        disp.shutdown()

    def test_08_memory_disabled(self):
        disp = MultiAgentDispatcher(persist_dir=self.tmp, enable_memory=False)
        result = disp.dispatch("无记忆任务")
        self.assertIsNone(result.memory_stats)
        disp.shutdown()

    def test_09_skillify_proposals(self):
        disp = MultiAgentDispatcher(persist_dir=self.tmp, enable_skillify=True)
        result = disp.dispatch("Skill学习测试 - 实现功能并测试")
        self.assertIsInstance(result.skill_proposals, list)
        disp.shutdown()

    def test_10_all_components_active(self):
        disp = MultiAgentDispatcher(
            persist_dir=self.tmp,
            enable_warmup=True,
            enable_compression=True,
            enable_permission=True,
            enable_memory=True,
            enable_skillify=True,
            enable_quality_guard=True,
        )
        status = disp.get_status()
        for comp_name, active in status["components"].items():
            self.assertTrue(active, f"Component {comp_name} should be active")
        disp.shutdown()


class TestT5_StatusAndHistory(unittest.TestCase):
    """T5: 状态查询和历史记录"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="mas_test_t5_")
        self.disp = MultiAgentDispatcher(
            persist_dir=self.tmp,
            enable_warmup=False,
            enable_memory=False,
            enable_skillify=False,
        )

    def tearDown(self):
        self.disp.shutdown()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_01_get_status_basic(self):
        status = self.disp.get_status()
        self.assertEqual(status["version"], "3.0")
        self.assertIn("components", status)
        self.assertIn("dispatch_count", status)

    def test_02_get_status_has_scratchpad_stats(self):
        status = self.disp.get_status()
        self.assertIn("scratchpad_stats", status)

    def test_03_history_starts_empty(self):
        history = self.disp.get_history()
        self.assertEqual(len(history), 0)

    def test_04_history_grows_with_dispatches(self):
        self.disp.dispatch("任务1")
        self.disp.dispatch("任务2")
        history = self.disp.get_history()
        self.assertEqual(len(history), 2)

    def test_05_history_limit(self):
        for i in range(15):
            self.disp.dispatch(f"任务{i}")
        history = self.disp.get_history(limit=10)
        self.assertLessEqual(len(history), 10)

    def test_06_quick_dispatch_returns_str(self):
        result_str = self.disp.quick_dispatch("快速报告测试")
        self.assertIsInstance(result_str, str)
        self.assertIn("#", result_str)

    def test_07_shutdown_no_error(self):
        disp = MultiAgentDispatcher(
            persist_dir=self.tmp,
            enable_warmup=True,
            enable_memory=True,
        )
        try:
            disp.shutdown()
        except Exception as e:
            self.fail(f"shutdown raised exception: {e}")


class TestT6_FactoryAndConvenience(unittest.TestCase):
    """T6: 工厂函数和便捷方法"""

    def test_01_create_dispatcher_factory(self):
        tmp = tempfile.mkdtemp(prefix="mas_test_t6_")
        try:
            disp = create_dispatcher(persist_dir=tmp)
            self.assertIsInstance(disp, MultiAgentDispatcher)
            disp.shutdown()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_02_quick_collaborate(self):
        tmp = tempfile.mkdtemp(prefix="mas_test_t6_")
        try:
            result = quick_collaborate("便捷协作测试", persist_dir=tmp)
            self.assertIsInstance(result, DispatchResult)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_03_multiple_dispatchers_independent(self):
        tmp1 = tempfile.mkdtemp(prefix="mas_test_6a_")
        tmp2 = tempfile.mkdtemp(prefix="mas_test_6b_")
        try:
            d1 = MultiAgentDispatcher(persist_dir=tmp1)
            d2 = MultiAgentDispatcher(persist_dir=tmp2)
            r1 = d1.dispatch("D1任务")
            r2 = d2.dispatch("D2任务")
            self.assertNotEqual(r1.task_description, r2.task_description)
            d1.shutdown()
            d2.shutdown()
        finally:
            shutil.rmtree(tmp1, ignore_errors=True)
            shutil.rmtree(tmp2, ignore_errors=True)


class TestT7_EdgeCases(unittest.TestCase):
    """T7: 边界条件和异常处理"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="mas_test_t7_")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_01_empty_task(self):
        disp = MultiAgentDispatcher(persist_dir=self.tmp, enable_warmup=False,
                                     enable_memory=False, enable_skillify=False)
        result = disp.dispatch("")
        self.assertIsInstance(result, DispatchResult)
        disp.shutdown()

    def test_02_very_long_task(self):
        disp = MultiAgentDispatcher(persist_dir=self.tmp, enable_warmup=False,
                                     enable_memory=False, enable_skillify=False)
        long_text = "测试" * 1000
        result = disp.dispatch(long_text)
        self.assertIsInstance(result, DispatchResult)
        disp.shutdown()

    def test_03_special_characters_task(self):
        disp = MultiAgentDispatcher(persist_dir=self.tmp, enable_warmup=False,
                                     enable_memory=False, enable_skillify=False)
        result = disp.dispatch("测试特殊字符: <>&\"'中文🎉emoji")
        self.assertIsInstance(result, DispatchResult)
        disp.shutdown()

    def test_04_all_roles_specified(self):
        disp = MultiAgentDispatcher(persist_dir=self.tmp, enable_warmup=False,
                                     enable_memory=False, enable_skillify=False)
        all_roles = list(ROLE_TEMPLATES.keys())
        result = disp.dispatch("全角色任务", roles=all_roles)
        self.assertEqual(set(result.matched_roles), set(all_roles))
        disp.shutdown()

    def test_05_invalid_role_fallback(self):
        disp = MultiAgentDispatcher(persist_dir=self.tmp, enable_warmup=False,
                                     enable_memory=False, enable_skillify=False)
        result = disp.dispatch("测试", roles=["nonexistent-role"])
        self.assertIsInstance(result, DispatchResult)
        disp.shutdown()

    def test_06_rapid_sequential_dispatches(self):
        disp = MultiAgentDispatcher(persist_dir=self.tmp, enable_warmup=False,
                                     enable_memory=False, enable_skillify=False)
        results = []
        for i in range(5):
            r = disp.dispatch(f"快速任务{i}")
            results.append(r)
        self.assertEqual(len(results), 5)
        for r in results:
            self.assertIsInstance(r, DispatchResult)
        disp.shutdown()

    def test_07_custom_persist_dir_created(self):
        custom_dir = os.path.join(self.tmp, "custom_persist")
        disp = MultiAgentDispatcher(persist_dir=custom_dir, enable_warmup=False,
                                     enable_memory=False, enable_skillify=False)
        self.assertTrue(os.path.exists(custom_dir))
        disp.dispatch("目录测试")
        disp.shutdown()

    def test_08_auto_persist_dir_created(self):
        disp = MultiAgentDispatcher(enable_warmup=False, enable_memory=False,
                                     enable_skillify=False)
        self.assertTrue(os.path.exists(disp.persist_dir))
        disp.shutdown()


if __name__ == "__main__":
    unittest.main(verbosity=2)
