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
import pytest
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


class TestT1_DispatcherDataModels:
    """T1: 数据模型测试"""

    def test_01_dispatch_result_default(self):
        r = DispatchResult(success=True, task_description="test")
        assert r.success
        assert r.task_description == "test"
        assert r.matched_roles == []
        assert r.duration_seconds == 0.0
        assert isinstance(r.errors, list)

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
        assert d["success"] == True
        assert d["task_description"] == "test task"
        assert d["matched_roles"] == ["architect", "tester"]
        assert "warn1" in d["errors"]

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
        assert "Multi-Agent" in md
        assert "设计系统" in md
        assert "✅ 成功" in md
        assert "architect" in md

    def test_04_dispatch_result_to_markdown_failure(self):
        r = DispatchResult(
            success=False,
            task_description="失败任务",
            errors=["error1", "error2"],
        )
        md = r.to_markdown()
        assert "❌ 失败" in md
        assert "error1" in md

    def test_05_role_templates_complete(self):
        expected_roles = ["architect", "product-manager", "tester", "solo-coder", "ui-designer"]
        for rid in expected_roles:
            assert rid in ROLE_TEMPLATES
            assert "name" in ROLE_TEMPLATES[rid]
            assert "prompt" in ROLE_TEMPLATES[rid]
            assert "keywords" in ROLE_TEMPLATES[rid]

    def test_06_role_keywords_non_empty(self):
        for rid, info in ROLE_TEMPLATES.items():
            assert len(info["keywords"]) > 0, f"{rid} has no keywords"


class TestT2_TaskAnalysis:
    """T2: 任务分析与角色匹配"""

    @pytest.fixture
    def dispatcher(self):
        """创建测试用的 dispatcher fixture"""
        tmp = tempfile.mkdtemp(prefix="mas_test_t2_")
        disp = MultiAgentDispatcher(
            persist_dir=tmp,
            enable_warmup=False,
            enable_memory=False,
            enable_skillify=False,
        )
        yield disp
        disp.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)

    def test_01_match_architect(self, dispatcher):
        roles = dispatcher.analyze_task("设计微服务架构，支持高并发")
        role_ids = [r["role_id"] for r in roles]
        assert "architect" in role_ids

    def test_02_match_tester(self, dispatcher):
        roles = dispatcher.analyze_task("编写单元测试和自动化测试用例")
        role_ids = [r["role_id"] for r in roles]
        assert "tester" in role_ids

    def test_03_match_solo_coder(self, dispatcher):
        roles = dispatcher.analyze_task("实现用户登录功能代码开发")
        role_ids = [r["role_id"] for r in roles]
        assert "solo-coder" in role_ids

    def test_04_match_ui_designer(self, dispatcher):
        roles = dispatcher.analyze_task("设计前端UI界面和交互原型")
        role_ids = [r["role_id"] for r in roles]
        assert "ui-designer" in role_ids

    def test_05_match_product_manager(self, dispatcher):
        roles = dispatcher.analyze_task("编写PRD需求文档和用户故事")
        role_ids = [r["role_id"] for r in roles]
        assert "product-manager" in role_ids

    def test_06_multi_role_match(self, dispatcher):
        roles = dispatcher.analyze_task("设计系统架构并编写测试用例")
        role_ids = [r["role_id"] for r in roles]
        assert "architect" in role_ids
        assert "tester" in role_ids

    def test_07_no_match_fallback(self, dispatcher):
        roles = dispatcher.analyze_task("随便说点什么不相关的话")
        assert len(roles) > 0
        assert roles[0]["role_id"] == "solo-coder"

    def test_08_confidence_ordering(self, dispatcher):
        roles = dispatcher.analyze_task("设计架构并测试")
        confidences = [r["confidence"] for r in roles]
        assert confidences == sorted(confidences, reverse=True)

    def test_09_return_structure(self, dispatcher):
        roles = dispatcher.analyze_task("测试任务")
        for r in roles:
            assert "role_id" in r
            assert "name" in r
            assert "confidence" in r
            assert "reason" in r

    def test_10_explicit_roles_override(self, dispatcher):
        result = dispatcher.dispatch("测试任务", roles=["architect"])
        assert "architect" in result.matched_roles


class TestT3_FullDispatch:
    """T3: 完整调度流程"""

    @pytest.fixture
    def dispatcher(self):
        """创建启用所有组件的 dispatcher fixture"""
        tmp = tempfile.mkdtemp(prefix="mas_test_t3_")
        disp = MultiAgentDispatcher(
            persist_dir=tmp,
            enable_warmup=True,
            enable_compression=True,
            enable_permission=True,
            enable_memory=True,
            enable_skillify=True,
        )
        yield disp
        disp.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)

    def test_01_single_role_dispatch(self, dispatcher):
        result = dispatcher.dispatch("设计用户认证模块的架构")
        assert isinstance(result, DispatchResult)
        assert isinstance(result.summary, str)
        assert result.duration_seconds > 0

    def test_02_multi_role_dispatch(self, dispatcher):
        result = dispatcher.dispatch("设计架构并编写测试方案",
                                     roles=["architect", "tester"])
        assert isinstance(result.matched_roles, list)
        assert len(result.matched_roles) >= 2

    def test_03_dispatch_has_worker_results(self, dispatcher):
        result = dispatcher.dispatch("实现一个简单的功能")
        assert isinstance(result.worker_results, list)

    def test_04_dispatch_has_scratchpad(self, dispatcher):
        result = dispatcher.dispatch("分析项目结构")
        assert isinstance(result.scratchpad_summary, str)

    def test_05_dispatch_to_dict_roundtrip(self, dispatcher):
        result = dispatcher.dispatch("快速任务")
        d = result.to_dict()
        assert "success" in d
        assert "task_description" in d
        assert "matched_roles" in d
        assert "duration_seconds" in d

    def test_06_dispatch_to_markdown_valid(self, dispatcher):
        result = dispatcher.dispatch("生成报告的任务")
        md = result.to_markdown()
        assert "#" in md
        assert len(md) > 50

    def test_07_timing_info_present(self, dispatcher):
        result = dispatcher.dispatch("计时测试")
        assert "timing" in result.details
        assert isinstance(result.details["timing"], dict)
        timing = result.details["timing"]
        assert "analyze" in timing
        assert "execute" in timing

    def test_08_dry_run_mode(self, dispatcher):
        result = dispatcher.dispatch("模拟任务", dry_run=True)
        assert result.success
        assert "DRY RUN" in result.summary
        assert len(result.worker_results) == 0

    def test_09_consensus_mode(self, dispatcher):
        result = dispatcher.dispatch("需要共识的决策", mode="consensus")
        assert isinstance(result.consensus_records, list)

    def test_10_sequential_mode(self, dispatcher):
        result = dispatcher.dispatch("顺序执行任务", mode="sequential")
        assert isinstance(result, DispatchResult)


class TestT4_ComponentIntegration:
    """T4: 各组件集成验证"""

    @pytest.fixture
    def tmp_dir(self):
        """临时目录 fixture"""
        tmp = tempfile.mkdtemp(prefix="mas_test_t4_")
        yield tmp
        shutil.rmtree(tmp, ignore_errors=True)

    def test_01_warmup_enabled(self, tmp_dir):
        disp = MultiAgentDispatcher(persist_dir=tmp_dir, enable_warmup=True)
        status = disp.get_status()
        assert status["components"]["warmup_manager"]
        metrics = status.get("warmup_metrics")
        assert metrics is not None
        disp.shutdown()

    def test_02_warmup_disabled(self, tmp_dir):
        disp = MultiAgentDispatcher(persist_dir=tmp_dir, enable_warmup=False)
        status = disp.get_status()
        assert status.get("warmup_metrics") is None
        disp.shutdown()

    def test_03_compression_enabled(self, tmp_dir):
        disp = MultiAgentDispatcher(persist_dir=tmp_dir, enable_compression=True)
        result = disp.dispatch("压缩测试任务" * 10)
        if result.compression_info:
            assert isinstance(result.compression_info, dict)
        disp.shutdown()

    def test_04_compression_disabled(self, tmp_dir):
        disp = MultiAgentDispatcher(persist_dir=tmp_dir, enable_compression=False)
        result = disp.dispatch("无压缩任务")
        assert result.compression_info is None
        disp.shutdown()

    def test_05_permission_checks_present(self, tmp_dir):
        disp = MultiAgentDispatcher(persist_dir=tmp_dir, enable_permission=True)
        result = disp.dispatch("权限检查任务")
        assert isinstance(result.permission_checks, list)
        if result.permission_checks:
            pc = result.permission_checks[0]
            assert "action" in pc
            assert "allowed" in pc
        disp.shutdown()

    def test_06_permission_disabled(self, tmp_dir):
        disp = MultiAgentDispatcher(persist_dir=tmp_dir, enable_permission=False)
        result = disp.dispatch("无权限任务")
        assert len(result.permission_checks) == 0
        disp.shutdown()

    def test_07_memory_bridge_stats(self, tmp_dir):
        mem_dir = os.path.join(tmp_dir, "mem_store")
        disp = MultiAgentDispatcher(
            persist_dir=tmp_dir,
            memory_dir=mem_dir,
            enable_memory=True,
        )
        result = disp.dispatch("记忆桥接测试")
        if result.memory_stats:
            assert "total_memories" in result.memory_stats
        disp.shutdown()

    def test_08_memory_disabled(self, tmp_dir):
        disp = MultiAgentDispatcher(persist_dir=tmp_dir, enable_memory=False)
        result = disp.dispatch("无记忆任务")
        assert result.memory_stats is None
        disp.shutdown()

    def test_09_skillify_proposals(self, tmp_dir):
        disp = MultiAgentDispatcher(persist_dir=tmp_dir, enable_skillify=True)
        result = disp.dispatch("Skill学习测试 - 实现功能并测试")
        assert isinstance(result.skill_proposals, list)
        disp.shutdown()

    def test_10_all_components_active(self, tmp_dir):
        disp = MultiAgentDispatcher(
            persist_dir=tmp_dir,
            enable_warmup=True,
            enable_compression=True,
            enable_permission=True,
            enable_memory=True,
            enable_skillify=True,
            enable_quality_guard=True,
        )
        status = disp.get_status()
        for comp_name, active in status["components"].items():
            assert active, f"Component {comp_name} should be active"
        disp.shutdown()


class TestT5_StatusAndHistory:
    """T5: 状态查询和历史记录"""

    @pytest.fixture
    def dispatcher(self):
        """创建测试用的 dispatcher fixture"""
        tmp = tempfile.mkdtemp(prefix="mas_test_t5_")
        disp = MultiAgentDispatcher(
            persist_dir=tmp,
            enable_warmup=False,
            enable_memory=False,
            enable_skillify=False,
        )
        yield disp
        disp.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)

    def test_01_get_status_basic(self, dispatcher):
        status = dispatcher.get_status()
        assert status["version"] == "3.4.0"
        assert "components" in status
        assert "dispatch_count" in status

    def test_02_get_status_has_scratchpad_stats(self, dispatcher):
        status = dispatcher.get_status()
        assert "scratchpad_stats" in status

    def test_03_history_starts_empty(self, dispatcher):
        history = dispatcher.get_history()
        assert len(history) == 0

    def test_04_history_grows_with_dispatches(self, dispatcher):
        dispatcher.dispatch("任务1")
        dispatcher.dispatch("任务2")
        history = dispatcher.get_history()
        assert len(history) == 2

    def test_05_history_limit(self, dispatcher):
        for i in range(15):
            dispatcher.dispatch(f"任务{i}")
        history = dispatcher.get_history(limit=10)
        assert len(history) <= 10

    def test_06_quick_dispatch_returns_result(self, dispatcher):
        result = dispatcher.quick_dispatch("快速报告测试")
        assert isinstance(result, DispatchResult)
        assert isinstance(result.summary, str)
        assert "#" in result.summary

    def test_07_shutdown_no_error(self, dispatcher):
        # 使用 fixture 提供的 dispatcher 的 persist_dir
        tmp = dispatcher.persist_dir
        disp = MultiAgentDispatcher(
            persist_dir=tmp,
            enable_warmup=True,
            enable_memory=True,
        )
        try:
            disp.shutdown()
        except Exception as e:
            pytest.fail(f"shutdown raised exception: {e}")


class TestT6_FactoryAndConvenience:
    """T6: 工厂函数和便捷方法"""

    def test_01_create_dispatcher_factory(self):
        tmp = tempfile.mkdtemp(prefix="mas_test_t6_")
        try:
            disp = create_dispatcher(persist_dir=tmp)
            assert isinstance(disp, MultiAgentDispatcher)
            disp.shutdown()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_02_quick_collaborate(self):
        tmp = tempfile.mkdtemp(prefix="mas_test_t6_")
        try:
            result = quick_collaborate("便捷协作测试", persist_dir=tmp)
            assert isinstance(result, DispatchResult)
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
            assert r1.task_description != r2.task_description
            d1.shutdown()
            d2.shutdown()
        finally:
            shutil.rmtree(tmp1, ignore_errors=True)
            shutil.rmtree(tmp2, ignore_errors=True)


class TestT7_EdgeCases:
    """T7: 边界条件和异常处理"""

    @pytest.fixture
    def tmp_dir(self):
        """临时目录 fixture"""
        tmp = tempfile.mkdtemp(prefix="mas_test_t7_")
        yield tmp
        shutil.rmtree(tmp, ignore_errors=True)

    def test_01_empty_task(self, tmp_dir):
        disp = MultiAgentDispatcher(persist_dir=tmp_dir, enable_warmup=False,
                                     enable_memory=False, enable_skillify=False)
        result = disp.dispatch("")
        assert isinstance(result, DispatchResult)
        disp.shutdown()

    def test_02_very_long_task(self, tmp_dir):
        disp = MultiAgentDispatcher(persist_dir=tmp_dir, enable_warmup=False,
                                     enable_memory=False, enable_skillify=False)
        long_text = "测试" * 1000
        result = disp.dispatch(long_text)
        assert isinstance(result, DispatchResult)
        disp.shutdown()

    def test_03_special_characters_task(self, tmp_dir):
        disp = MultiAgentDispatcher(persist_dir=tmp_dir, enable_warmup=False,
                                     enable_memory=False, enable_skillify=False)
        result = disp.dispatch("测试特殊字符: <>&\"'中文🎉emoji")
        assert isinstance(result, DispatchResult)
        disp.shutdown()

    def test_04_all_roles_specified(self, tmp_dir):
        disp = MultiAgentDispatcher(persist_dir=tmp_dir, enable_warmup=False,
                                     enable_memory=False, enable_skillify=False)
        all_roles = list(ROLE_TEMPLATES.keys())
        result = disp.dispatch("全角色任务", roles=all_roles)
        assert set(result.matched_roles) == set(all_roles)
        disp.shutdown()

    def test_05_invalid_role_fallback(self, tmp_dir):
        disp = MultiAgentDispatcher(persist_dir=tmp_dir, enable_warmup=False,
                                     enable_memory=False, enable_skillify=False)
        result = disp.dispatch("测试", roles=["nonexistent-role"])
        assert isinstance(result, DispatchResult)
        disp.shutdown()

    def test_06_rapid_sequential_dispatches(self, tmp_dir):
        disp = MultiAgentDispatcher(persist_dir=tmp_dir, enable_warmup=False,
                                     enable_memory=False, enable_skillify=False)
        results = []
        for i in range(5):
            r = disp.dispatch(f"快速任务{i}")
            results.append(r)
        assert len(results) == 5
        for r in results:
            assert isinstance(r, DispatchResult)
        disp.shutdown()

    def test_07_custom_persist_dir_created(self, tmp_dir):
        custom_dir = os.path.join(tmp_dir, "custom_persist")
        disp = MultiAgentDispatcher(persist_dir=custom_dir, enable_warmup=False,
                                     enable_memory=False, enable_skillify=False)
        assert os.path.exists(custom_dir)
        disp.dispatch("目录测试")
        disp.shutdown()

    def test_08_auto_persist_dir_created(self):
        disp = MultiAgentDispatcher(enable_warmup=False, enable_memory=False,
                                     enable_skillify=False)
        assert os.path.exists(disp.persist_dir)
        disp.shutdown()


if __name__ == "__main__":
    unittest.main(verbosity=2)
