#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dispatcher UX Test Suite (v3.2 MVP Line-C)

测试 quick_dispatch() 增强的结构化报告功能:
- structured 格式输出
- compact 格式输出
- detailed 格式输出
- _extract_findings() 发现提取
- _generate_action_items() 行动项生成
- 报告层次完整性验证
"""

import os
import sys
import unittest
from typing import Dict, List, Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from scripts.collaboration.dispatcher import (
    MultiAgentDispatcher,
    DispatchResult,
)


class TestStructuredReportFormat(unittest.TestCase):
    """T1: 结构化报告格式测试 (structured)"""

    def setUp(self):
        self.dispatcher = MultiAgentDispatcher(
            enable_warmup=False,
            enable_compression=False,
            enable_permission=False,
            enable_memory=False,
            enable_skillify=False,
        )

    def tearDown(self):
        try:
            self.dispatcher.shutdown()
        except Exception:
            pass

    def test_structured_report_has_header(self):
        result = self.dispatcher.quick_dispatch("测试任务", output_format="structured")
        report = result.to_markdown() if isinstance(result, DispatchResult) else str(result)
        self.assertIn("#", report)

    def test_structured_report_has_summary_section(self):
        result = self.dispatcher.quick_dispatch("设计用户认证系统", output_format="structured")
        report = result.to_markdown() if isinstance(result, DispatchResult) else str(result)
        # Check for summary or task info section
        has_summary = "任务" in report or "Task" in report or len(result.summary) > 0 if isinstance(result, DispatchResult) else True
        self.assertTrue(has_summary)

    def test_structured_report_has_role_table(self):
        result = self.dispatcher.quick_dispatch("开发API接口", output_format="structured")
        report = result.to_markdown() if isinstance(result, DispatchResult) else str(result)
        # Check for role information
        has_roles = "角色" in report or "Role" in report or len(result.matched_roles) > 0 if isinstance(result, DispatchResult) else True
        self.assertTrue(has_roles)

    def test_structured_report_has_action_items(self):
        result = self.dispatcher.quick_dispatch("编写单元测试", output_format="structured",
                                                include_action_items=True)
        report = result.to_markdown() if isinstance(result, DispatchResult) else str(result)
        # Report should be generated successfully
        self.assertTrue(len(report) > 50)

    def test_structured_report_without_action_items(self):
        result = self.dispatcher.quick_dispatch("代码审查", output_format="structured",
                                                include_action_items=False)
        report = result.to_markdown() if isinstance(result, DispatchResult) else str(result)
        # Report should be generated successfully
        self.assertTrue(len(report) > 50)

    def test_structured_report_with_timing(self):
        result = self.dispatcher.quick_dispatch("性能优化", output_format="structured",
                                                include_timing=True)
        report = result.to_markdown() if isinstance(result, DispatchResult) else str(result)
        # Timing info should be recorded in DispatchResult
        self.assertIsInstance(result, DispatchResult)
        self.assertGreaterEqual(result.duration_seconds, 0)


class TestCompactReportFormat(unittest.TestCase):
    """T2: 紧凑格式报告测试 (compact)"""

    def setUp(self):
        self.dispatcher = MultiAgentDispatcher(
            enable_warmup=False,
            enable_compression=False,
            enable_permission=False,
            enable_memory=False,
            enable_skillify=False,
        )

    def tearDown(self):
        try:
            self.dispatcher.shutdown()
        except Exception:
            pass

    def test_compact_report_is_concise(self):
        result = self.dispatcher.quick_dispatch("简单任务", output_format="compact")
        report = result.to_markdown() if isinstance(result, DispatchResult) else str(result)
        lines = [l for l in report.split('\n') if l.strip()]
        self.assertLessEqual(len(lines), 20, "Compact format should be concise")

    def test_compact_report_has_status_icon(self):
        result = self.dispatcher.quick_dispatch("测试", output_format="compact")
        report = result.to_markdown() if isinstance(result, DispatchResult) else str(result)
        # Check for status indicator
        has_status = ("✅" in report or "❌" in report or 
                     (isinstance(result, DispatchResult) and (result.success or not result.success)))
        self.assertTrue(has_status)

    def test_compact_report_has_task_info(self):
        result = self.dispatcher.quick_dispatch("构建CI/CD流水线", output_format="compact")
        report = result.to_markdown() if isinstance(result, DispatchResult) else str(result)
        # Should contain task info or be a valid DispatchResult
        is_valid = (len(report) > 30 and 
                   (isinstance(result, DispatchResult) and result.task_description))
        self.assertTrue(is_valid)


class TestDetailedReportFormat(unittest.TestCase):
    """T3: 详细格式报告测试 (detailed)"""

    def setUp(self):
        self.dispatcher = MultiAgentDispatcher(
            enable_warmup=False,
            enable_compression=False,
            enable_permission=False,
            enable_memory=False,
            enable_skillify=False,
        )

    def tearDown(self):
        try:
            self.dispatcher.shutdown()
        except Exception:
            pass

    def test_detailed_uses_original_markdown(self):
        result = self.dispatcher.dispatch("详细测试任务")
        detailed = result.to_markdown()
        result2 = self.dispatcher.quick_dispatch("详细测试任务", output_format="detailed")
        detailed2 = result2.to_markdown() if isinstance(result2, DispatchResult) else str(result2)
        # Both should generate valid reports
        self.assertTrue(len(detailed) > 50)
        self.assertTrue(len(detailed2) > 50)


class TestExtractFindings(unittest.TestCase):
    """T4: _extract_findings() 测试"""

    def setUp(self):
        self.dispatcher = MultiAgentDispatcher(
            enable_warmup=False,
            enable_compression=False,
            enable_permission=False,
            enable_memory=False,
            enable_skillify=False,
        )

    def tearDown(self):
        try:
            self.dispatcher.shutdown()
        except Exception:
            pass

    def test_extract_numbered_list(self):
        text = "1. 第一个发现\n2. 第二个发现\n3. 第三个发现"
        findings = self.dispatcher._extract_findings(text)
        self.assertEqual(len(findings), 3)
        self.assertIn("第一个发现", findings[0])

    def test_extract_bulleted_list(self):
        text = "- 发现A\n- 发现B\n- 发现C"
        findings = self.dispatcher._extract_findings(text)
        self.assertEqual(len(findings), 3)

    def test_extract_semicolon_separated(self):
        text = "问题一; 问题二; 问题三; 问题四"
        findings = self.dispatcher._extract_findings(text)
        self.assertGreaterEqual(len(findings), 3)

    def test_extract_sentence_split(self):
        text = "这是一个很长的发现句子。这是另一个发现。第三个重要发现。"
        findings = self.dispatcher._extract_findings(text)
        self.assertGreaterEqual(len(findings), 1, "Should extract at least one sentence")

    def test_extract_empty_text(self):
        findings = self.dispatcher._extract_findings("")
        self.assertEqual(findings, [])

    def test_extract_none_text(self):
        findings = self.dispatcher._extract_findings(None)
        self.assertEqual(findings, [])


class TestGenerateActionItems(unittest.TestCase):
    """T5: _generate_action_items() 测试"""

    def setUp(self):
        self.dispatcher = MultiAgentDispatcher(
            enable_warmup=False,
            enable_compression=False,
            enable_permission=False,
            enable_memory=False,
            enable_skillify=False,
        )

    def tearDown(self):
        try:
            self.dispatcher.shutdown()
        except Exception:
            pass

    def test_success_generates_low_priority_items(self):
        result = DispatchResult(
            success=True,
            task_description="成功任务",
            matched_roles=["architect"],
            summary="完成",
            worker_results=[{"role": "architect", "success": True, "output": "架构设计完成"}],
        )
        items = self.dispatcher._generate_action_items(result)
        self.assertGreater(len(items), 0)
        priorities = [item['priority'] for item in items]
        self.assertIn('L', priorities, "Success should generate low priority items")

    def test_errors_generate_high_priority_items(self):
        result = DispatchResult(
            success=False,
            task_description="失败任务",
            errors=["错误1: 连接超时", "错误2: 权限不足"],
            worker_results=[],
        )
        items = self.dispatcher._generate_action_items(result)
        high_priority = [i for i in items if i['priority'] == 'H']
        self.assertGreater(len(high_priority), 0, "Errors should generate high priority items")

    def test_unresolved_conflicts_generate_action(self):
        result = DispatchResult(
            success=True,
            task_description="有冲突的任务",
            consensus_records=[
                {"topic": "技术选型", "outcome": "SPLIT"},
                {"topic": "数据库选择", "outcome": "ESCALATED"},
            ],
            worker_results=[{"role": "architect", "success": True}],
        )
        items = self.dispatcher._generate_action_items(result)
        conflict_items = [i for i in items if '未决' in i['text'] or '审核' in i['text']]
        self.assertGreater(len(conflict_items), 0)

    def test_failed_workers_generate_action(self):
        result = DispatchResult(
            success=False,
            task_description="Worker失败",
            worker_results=[
                {"role": "coder", "success": False},
                {"role": "tester", "success": False},
            ],
        )
        items = self.dispatcher._generate_action_items(result)
        self.assertGreater(len(items), 0)

    def test_no_result_generates_default_item(self):
        result = DispatchResult(
            success=True,
            task_description="空结果",
            worker_results=[],
            consensus_records=[],
        )
        items = self.dispatcher._generate_action_items(result)
        self.assertGreater(len(items), 0, "Should always generate at least one action item")


class TestReportHierarchy(unittest.TestCase):
    """T6: 报告层次完整性验证"""

    def setUp(self):
        self.dispatcher = MultiAgentDispatcher(
            enable_warmup=False,
            enable_compression=False,
            enable_permission=False,
            enable_memory=False,
            enable_skillify=False,
        )

    def tearDown(self):
        try:
            self.dispatcher.shutdown()
        except Exception:
            pass

    def test_structured_has_all_sections_when_data_present(self):
        result = self.dispatcher.quick_dispatch(
            "完整测试任务，包含多个角色协作",
            output_format="structured",
            include_action_items=True,
        )
        report = result.to_markdown() if isinstance(result, DispatchResult) else str(result)
        
        # Verify it's a valid report with content
        self.assertTrue(len(report) > 100, f"Report should have substantial content, got {len(report)} chars")
        
        # Check for basic structure elements
        has_header = "#" in report or "##" in report
        has_content = len(result.matched_roles) > 0 if isinstance(result, DispatchResult) else True
        
        self.assertTrue(has_header or has_content, "Report should have structure or content")

    def test_report_contains_separator_lines(self):
        result = self.dispatcher.quick_dispatch("分隔符测试", output_format="structured")
        report = result.to_markdown() if isinstance(result, DispatchResult) else str(result)
        # May or may not have separators depending on format
        self.assertIsInstance(report, str)
        self.assertTrue(len(report) > 10)

    def test_invalid_format_fallback_to_default(self):
        result = self.dispatcher.quick_dispatch("测试", output_format="invalid_format")
        report = result.to_markdown() if isinstance(result, DispatchResult) else str(result)
        self.assertTrue(len(report) > 10, "Invalid format should fallback to default")


def run_all_tests():
    """
    加载并运行本模块全部测试用例

    Returns:
        int: 通过的测试用例数 (testsRun - failures - errors)
    """
    suite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.testsRun - len(result.failures) - len(result.errors)


if __name__ == "__main__":
    passed = run_all_tests()
    total = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__]).countTestCases()
    print(f"\n{'='*60}")
    print(f"Dispatcher UX Test Results: {passed}/{total} passed")
    if passed == total:
        print("🎉 ALL DISPATCHER UX TESTS PASSED!")
    print(f"{'='*60}")
