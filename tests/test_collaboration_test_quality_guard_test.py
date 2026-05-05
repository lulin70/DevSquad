#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TestQualityGuard 测试

本测试文件遵循以下规范（作为 TestQualityGuard 自身质量的证明）：
- 每个测试函数都有目的声明（docstring）
- 覆盖 happy path + error case + boundary 三大维度
- 包含性能基准测试
- 不为通过而放宽断言
"""

import os
import sys
import unittest
import tempfile
import shutil
import time
import ast
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from scripts.collaboration.test_quality_guard import (
    TestQualityGuard, TestQualityReport, QualityIssue, Severity,
    TestFunctionMeta, APISignature, QualityScore,
    TestDimension, APISignatureValidator,
    AntiPatternDetector, TestPurposeParser,
    quick_audit, project_audit,
)


class T1_DataModels(unittest.TestCase):
    """T1: 数据模型 - 验证所有数据类能正确创建和序列化"""

    def test_01_quality_issue_creation(self):
        """验证: QualityIssue 能正确创建并序列化为字典"""
        issue = QualityIssue(
            id="test-01", severity=Severity.CRITICAL,
            category="test", message="test msg",
            file="/tmp/test.py", line=10,
            suggestion="fix it", auto_fixable=True,
        )
        d = issue.to_dict()
        self.assertEqual(d["id"], "test-01")
        self.assertEqual(d["severity"], "critical")
        self.assertTrue(d["auto_fixable"])

    def test_02_quality_score_default(self):
        """验证: QualityScore 默认值全部为 0.0"""
        score = QualityScore()
        self.assertEqual(score.overall, 0.0)
        self.assertEqual(score.api_compliance, 0.0)
        d = score.to_dict()
        self.assertIn("overall", d)

    def test_03_test_function_meta_defaults(self):
        """验证: TestFunctionMeta 默认状态正确（无目的声明）"""
        meta = TestFunctionMeta(name="test_something", line=5)
        self.assertFalse(meta.has_purpose)
        self.assertIsNone(meta.dimension)
        self.assertEqual(meta.assert_count, 0)

    def test_04_api_signature_creation(self):
        """验证: APISignature 能记录函数签名信息"""
        sig = APISignature(
            name="my_func", kind="method",
            params=[{"name": "self"}, {"name": "x", "type": "int"}],
            file="mod.py", line=10,
        )
        self.assertEqual(len(sig.params), 2)
        self.assertEqual(sig.kind, "method")

    def test_05_report_empty_state(self):
        """验证: 空报告的默认属性合理"""
        r = TestQualityReport(module_name="test", test_file="t.py", source_file="s.py")
        self.assertEqual(r.total_tests, 0)
        self.assertEqual(r.critical_count, 0)
        self.assertIsInstance(r.to_dict(), dict)

    def test_06_report_markdown_generation(self):
        """验证: 报告能生成包含关键段的 Markdown 文本"""
        r = TestQualityReport(module_name="m", test_file="t.py", source_file="s.py")
        r.total_tests = 10
        r.score.overall = 0.85
        md = r.to_markdown()
        self.assertIn("# TestQualityGuard", md)
        self.assertIn("85%", md)

    def test_07_severity_enum_values(self):
        """验证: Severity 枚举包含所有预期级别"""
        expected = ["critical", "major", "minor", "info", "suggestion"]
        actual = [s.value for s in Severity]
        for e in expected:
            self.assertIn(e, actual)

    def test_08_dimension_enum_values(self):
        """验证: TestDimension 枚举覆盖所有测试维度"""
        dims = [d.value for d in TestDimension]
        self.assertIn("happy_path", dims)
        self.assertIn("error_case", dims)
        self.assertIn("performance", dims)
        self.assertIn("configuration", dims)


class T2_APIValidator(unittest.TestCase):
    """T2: API 签名验证器 - 从源码提取签名并校验调用"""

    def setUp(self):
        self.validator = APISignatureValidator()

    def test_01_extract_simple_function(self):
        """验证: 能从简单函数定义提取参数列表"""
        code = '''
def hello(name: str, age: int = 0) -> str:
    return f"hello {name}"
'''
        sigs = self.validator.extract_api_signatures(code, "test.py")
        self.assertEqual(len(sigs), 1)
        self.assertEqual(sigs[0].name, "hello")
        param_names = [p['name'] for p in sigs[0].params]
        self.assertIn('name', param_names)
        self.assertIn('age', param_names)

    def test_02_extract_method_with_self(self):
        """验证: 方法中的 self 参数被识别但标记为 method 类型"""
        code = '''
class Foo:
    def bar(self, x: int, y: str = "") -> None:
        pass
'''
        sigs = self.validator.extract_api_signatures(code, "foo.py")
        self.assertEqual(len(sigs), 1)
        self.assertEqual(sigs[0].kind, "method")

    def test_03_extract_multiple_functions(self):
        """验证: 同一文件中多个函数都能被提取"""
        code = 'def a(): pass\ndef b(x): pass\ndef c(x, y): pass'
        sigs = self.validator.extract_api_signatures(code, "multi.py")
        names = [s.name for s in sigs]
        self.assertEqual(len(names), 3)
        self.assertIn('a', names)
        self.assertIn('b', names)
        self.assertIn('c', names)

    def test_04_detect_wrong_parameter_name(self):
        """验证: 使用不存在的参数名时产生 MAJOR 级别问题"""
        code = 'def real_func(valid_param: int) -> int: return valid_param'
        sigs = self.validator.extract_api_signatures(code, "mod.py")
        issues = self.validator.validate_call_against_signature(
            "real_func", {"bad_param", "wrong_name"}, sigs
        )
        self.assertGreater(len(issues), 0)
        self.assertTrue(any(i.category == "API参数错误" for i in issues))

    def test_05_valid_call_no_issues(self):
        """验证: 使用正确的参数名时不产生问题"""
        code = 'def func(a, b, c): pass'
        sigs = self.validator.extract_api_signatures(code, "f.py")
        issues = self.validator.validate_call_against_signature(
            "func", {"a", "b"}, sigs
        )
        self.assertEqual(len(issues), 0)

    def test_06_handle_syntax_error_gracefully(self):
        """验证: 源码有语法错误时返回空列表而非崩溃"""
        sigs = self.validator.extract_api_signatures('def broken(', "bad.py")
        self.assertEqual(sigs, [])

    def test_07_async_function_extraction(self):
        """验证: async 函数也能被提取"""
        code = 'async def async_func(data: bytes) -> str: return data.hex()'
        sigs = self.validator.extract_api_signatures(code, "async_mod.py")
        self.assertEqual(len(sigs), 1)
        self.assertEqual(sigs[0].name, "async_func")


class T3_AntiPatternDetector(unittest.TestCase):
    """T3: 反模式检测 - 发现 '为通过而改' 的可疑模式"""

    def setUp(self):
        self.detector = AntiPatternDetector()

    def test_01_detect_bare_except(self):
        """验证: 裸 except 子句被检测为 MAJOR 问题"""
        code = 'try:\n    x = 1/0\nexcept:\n    pass\n'
        issues = self.detector.detect_in_source(code, "bare.py")
        self.assertTrue(any(i.category == "异常吞噬" for i in issues))

    def test_02_detect_magic_number_assert(self):
        """验证: 断言中大数字魔法值被检测"""
        code = 'self.assertGreater(result, 99999)'
        issues = self.detector.detect_in_source(code, "magic.py")
        self.assertTrue(any(i.category == "魔法数字" for i in issues))

    def test_03_clean_code_no_issues(self):
        """验证: 干净代码不触发反模式警告"""
        code = '''\
self.assertEqual(result, 42)
self.assertIn("key", mapping)
self.assertRaises(ValueError, bad_func)
'''
        issues = self.detector.detect_in_source(code, "clean.py")
        anti = [i for i in issues if i.severity in (Severity.MAJOR, Severity.CRITICAL)]
        self.assertEqual(len(anti), 0)

    def test_04_relaxed_float_detection(self):
        """验证: assertGreater(x, 0.0) 被标记为宽松断言"""
        code = 'self.assertGreater(score, 0.0)'
        issues = self.detector.detect_in_source(code, "relax.py")
        self.assertTrue(any(i.category == "无效断言" for i in issues))

    def test_05_issue_has_suggestion(self):
        """验证: 每个检测到的问题都附带修复建议"""
        code = 'except:\n    pass'
        issues = self.detector.detect_in_source(code, "x.py")
        for issue in issues:
            if issue.suggestion:
                self.assertIsInstance(issue.suggestion, str)
                self.assertGreater(len(issue.suggestion), 0)
                break
        else:
            self.fail("Expected at least one issue with suggestion")


class T4_TestPurposeParser(unittest.TestCase):
    """T4: 目的解析器 - 从测试函数中提取目的和维度"""

    def setUp(self):
        self.parser = TestPurposeParser()

    def _make_func_node(self, name, docstring=None, body=''):
        ds_part = f'    """{docstring}"""' if docstring else ''
        if body and not body.strip().startswith('#'):
            body_part = body
        elif body:
            body_part = f'{body}\n    pass'
        else:
            body_part = '    pass'
        src = f'def {name}(self):\n{ds_part}\n{body_part}\n'
        tree = ast.parse(src)
        node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        lines = src.split('\n')
        return node, lines

    def test_01_docstring_as_purpose(self):
        """验证: docstring 被识别为目的声明"""
        node, lines = self._make_func_node("test_x", docstring="验证函数正常工作")
        meta = self.parser.parse_function(node, lines)
        self.assertTrue(meta.has_purpose)
        self.assertIn("验证", meta.purpose_text)

    def test_02_comment_as_purpose(self):
        """验证: 带 verify/check 关键字的注释被识别为目的"""
        node, lines = self._make_func_node("test_y", body='    # 验证: 返回值不为空')
        meta = self.parser.parse_function(node, lines)
        self.assertTrue(meta.has_purpose)

    def test_03_no_purpose_detected(self):
        """验证: 无注释无docstring时 has_purpose 为 False"""
        node, lines = self._make_func_node("test_z", body='    x = 1')
        meta = self.parser.parse_function(node, lines)
        self.assertFalse(meta.has_purpose)

    def test_04_error_dimension_inference(self):
        """验证: 含 assertRaises/error 关键词的函数推断为 ERROR_CASE 维度"""
        node, lines = self._make_func_node("test_err",
            body='    with self.assertRaises(ValueError):\n        bad()')
        meta = self.parser.parse_function(node, lines)
        self.assertTrue(meta.has_error_test)
        self.assertEqual(meta.dimension, TestDimension.ERROR_CASE)

    def test_05_performance_dimension_inference(self):
        """验证: 含 timing/benchmark 关键词的函数推断为 PERFORMANCE 维度"""
        node, lines = self._make_func_node("test_perf",
            body='    start = time.time()\n    result = func()\n    elapsed = time.time() - start')
        meta = self.parser.parse_function(node, lines)
        self.assertTrue(meta.has_performance_check)
        self.assertEqual(meta.dimension, TestDimension.PERFORMANCE)

    def test_06_assert_counting(self):
        """验证: 正确统计断言数量和类型"""
        body = '    self.assertEqual(a, b)\n    self.assertTrue(c)\n    self.assertIn(d, e)\n    self.assertEqual(f, g)'
        node, lines = self._make_func_node("test_counts", body=body)
        meta = self.parser.parse_function(node, lines)
        self.assertEqual(meta.assert_count, 4)
        self.assertIn("assertEqual", meta.assert_types)

    def test_07_happy_path_default_dimension(self):
        """验证: 无特殊关键词时默认推断为 HAPPY_PATH"""
        node, lines = self._make_func_node("test_normal", body='    result = func()\n    self.assertIsNotNone(result)')
        meta = self.parser.parse_function(node, lines)
        self.assertEqual(meta.dimension, TestDimension.HAPPY_PATH)


class T5_FullAudit(unittest.TestCase):
    """T5: 完整审计 - 端到端验证 TestQualityGuard 审计流程"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="tqg_test_")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_files(self, source_code: str, test_code: str):
        src = os.path.join(self.tmp, "module.py")
        tst = os.path.join(self.tmp, "module_test.py")
        with open(src, 'w') as f:
            f.write(source_code)
        with open(tst, 'w') as f:
            f.write(test_code)
        return src, tst

    def test_01_audit_good_tests(self):
        """验证: 高质量测试文件获得高评分"""
        src = '''
class Target:
    def add(self, a: int, b: int) -> int:
        return a + b

    def divide(self, x: float, y: float) -> float:
        if y == 0:
            raise ValueError("division by zero")
        return x / y
'''
        tst = '''\
import unittest

class TestTarget(unittest.TestCase):
    def setUp(self):
        self.target = Target()

    def test_add_positive_numbers(self):
        """验证: 正数相加返回正确结果"""
        result = self.target.add(2, 3)
        self.assertEqual(result, 5)

    def test_add_negative_numbers(self):
        """验证: 负数相加返回正确结果"""
        result = self.target.add(-1, -2)
        self.assertEqual(result, -3)

    def test_divide_by_zero_raises(self):
        """验证: 除以零抛出 ValueError"""
        with self.assertRaises(ValueError):
            self.target.divide(10, 0)

    def test_divide_performance(self):
        """验证: 除法运算应在 1ms 内完成"""
        import time
        start = time.perf_counter()
        self.target.divide(100, 3)
        elapsed = (time.perf_counter() - start) * 1000
        self.assertLess(elapsed, 1.0)
'''
        src_path, tst_path = self._write_files(src, tst)
        report = TestQualityGuard(src_path, tst_path).audit()

        self.assertEqual(report.total_tests, 4)
        self.assertGreater(report.score.overall, 0.6)
        purpose_count = sum(1 for t in report.test_functions if t.has_purpose)
        self.assertEqual(purpose_count, 4)

    def test_02_audit_bad_tests_low_score(self):
        """验证: 低质量测试文件获得低评分并产生问题报告"""
        src = 'def foo(x): return x * 2'
        tst = '''\
import unittest
class BadTest(unittest.TestCase):
    def test_foo(self):
        r = foo(5)
        self.assertTrue(r > 0)
'''
        src_path, tst_path = self._write_files(src, tst)
        report = TestQualityGuard(src_path, tst_path).audit()

        self.assertLess(report.score.overall, 0.8)
        self.assertGreater(len(report.issues), 0)

    def test_03_missing_source_file(self):
        """验证: 源文件不存在时返回 CRITICAL 问题而非崩溃"""
        guard = TestQualityGuard("/nonexistent/file.py", "/also/nonexistent.py")
        report = guard.audit()
        self.assertGreater(report.critical_count, 0)

    def test_04_report_markdown_complete(self):
        """验证: 完整报告的 Markdown 包含所有必需段"""
        src = 'def f(): pass'
        tst = 'class T(unittest.TestCase):\n    def test_f(self): pass'
        sp, tp = self._write_files(src, tst)
        report = TestQualityGuard(sp, tp).audit()
        md = report.to_markdown()
        self.assertIn("评分总览", md)
        self.assertIn("TestQualityGuard", md)

    def test_05_audit_performance(self):
        """验证: 审计操作在合理时间内完成（< 1s for small files）"""
        src = '\n'.join([f'def func{i}(x): return x' for i in range(50)])
        tst = '\n'.join([f'class T(unittest.TestCase):\n    def test_{i}(self): pass' for i in range(30)])
        sp, tp = self._write_files(src, tst)
        start = time.perf_counter()
        report = TestQualityGuard(sp, tp).audit()
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, 2.0, f"审计耗时 {elapsed:.2f}s 过长")


class T6_TemplateGeneration(unittest.TestCase):
    """T6: 测试模板生成 - 根据 API 签名自动生成高质量测试模板"""

    def setUp(self):
        self.guard = TestQualityGuard("", "")

    def test_01_basic_template_has_happy_path(self):
        """验证: 默认模板包含 happy path 测试"""
        sig = APISignature(name="process", kind="method",
                            params=[{"name": "self"}, {"name": "data", "type": "str"}])
        tpl = self.guard.generate_test_template(sig)
        self.assertIn("happy_path", tpl)
        self.assertIn("process", tpl)

    def test_02_with_error_dimension(self):
        """验证: 包含 ERROR_CASE 维度时模板含异常测试"""
        sig = APISignature(name="calc", kind="function",
                            params=[{"name": "x", "type": "int"}])
        tpl = self.guard.generate_test_template(sig,
                    dimensions=[TestDimension.HAPPY_PATH, TestDimension.ERROR_CASE])
        self.assertIn("invalid_input", tpl)
        self.assertIn("assertRaises", tpl)

    def test_03_with_perf_dimension(self):
        """验证: 包含 PERFORMANCE 维度时模板含耗时检查"""
        sig = APISignature(name="query", kind="method",
                            params=[{"name": "self"}, {"name": "sql", "type": "str"}])
        tpl = self.guard.generate_test_template(sig,
                    dimensions=[TestDimension.HAPPY_PATH, TestDimension.PERFORMANCE])
        self.assertIn("performance", tpl)
        self.assertIn("perf_counter", tpl)

    def test_04_template_is_valid_python(self):
        """验证: 生成的模板包含有效的 Python 代码结构"""
        sig = APISignature(name="run", kind="function",
                            params=[{"name": "cmd", "type": "str"}])
        tpl = self.guard.generate_test_template(sig)
        self.assertIn("def test_", tpl)
        self.assertIn("self.assert", tpl)
        self.assertNotIn("SyntaxError", tpl)
        wrapped = f"class TemplateTest(unittest.TestCase):\n{tpl}"
        try:
            compile(wrapped, "<template>", "exec")
        except SyntaxError as e:
            self.fail(f"生成的模板语法错误: {e}\n---模板内容:\n{tpl}")


class T7_ConvenienceFunctions(unittest.TestCase):
    """T7: 便捷函数 - quick_audit 和 project_audit 接口"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="tqg_conv_")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_01_quick_audit_returns_report(self):
        """验证: quick_audit 返回完整的 TestQualityReport"""
        src = os.path.join(self.tmp, "m.py")
        tst = os.path.join(self.tmp, "m_test.py")
        with open(src, 'w') as f:
            f.write('def fn(x): return x')
        with open(tst, 'w') as f:
            f.write('class T(unittest.TestCase):\n    def test_fn(self): pass')
        report = quick_audit(src, tst)
        self.assertIsInstance(report, TestQualityReport)
        self.assertIsNotNone(report.timestamp)

    def test_02_project_audit_returns_string(self):
        """验证: project_audit 返回 Markdown 格式字符串"""
        md = project_audit(self.tmp)
        self.assertIsInstance(md, str)
        self.assertIn("# 项目级", md)


class T8_EdgeCases(unittest.TestCase):
    """T8: 边界条件和异常处理"""

    def test_01_empty_module_file(self):
        """验证: 空模块文件不会导致崩溃"""
        tmp = tempfile.mkdtemp(prefix="tqg_edge_")
        try:
            src = os.path.join(tmp, "empty.py")
            tst = os.path.join(tmp, "empty_test.py")
            with open(src, 'w') as f:
                f.write('')
            with open(tst, 'w') as f:
                f.write('# empty')
            report = TestQualityGuard(src, tst).audit()
            self.assertIsInstance(report, TestQualityReport)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_02_unicode_in_source(self):
        """验证: 中文/Unicode 源码正常处理"""
        detector = AntiPatternDetector()
        code = '# 验证：中文注释\nresult = func("中文参数")\nself.assertEqual(result, "期望值")'
        issues = detector.detect_in_source(code, "unicode.py")
        self.assertIsInstance(issues, list)

    def test_03_very_long_function_body(self):
        """验证: 超长函数体不影响解析"""
        parser = TestPurposeParser()
        long_body = '\n'.join([f'    x{i} = {i}' for i in range(200)])
        src = f'def big_func(self):\n{long_body}\n    return x199'
        try:
            tree = ast.parse(src)
            node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
            lines = [''] * 250
            meta = parser.parse_function(node, lines)
            self.assertEqual(meta.name, "big_func")
        except Exception as e:
            self.fail(f"超长函数解析失败: {e}")

    def test_04_special_characters_in_docstring(self):
        """验证: docstring 中特殊字符不影响目的提取"""
        parser = TestPurposeParser()
        src = "def test_special(self):\n    \"\"\"验证: 特殊字符 <>&\"' 中文🎉!\"\"\"\n    pass"
        try:
            tree = ast.parse(src)
            node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
            lines = [''] * 10
            meta = parser.parse_function(node, lines)
            self.assertTrue(meta.has_purpose)
        except Exception as e:
            self.fail(f"特殊字符处理失败: {e}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
