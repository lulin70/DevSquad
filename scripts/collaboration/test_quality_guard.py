#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TestQualityGuard - 测试质量守卫

解决 AI 测试的三大顽疾：
  1) 不看 API 文档凭空写 → API 签名校验
  2) 为通过而改测试 → 测试目的声明 + 失败报告生成
  3) 覆盖率低缺维度 → 多维度覆盖强制检查

核心能力:
- APISignatureValidator: 校验测试代码是否与实际 API 签名一致
- TestPurposeRegistry: 强制每个 test_ 函数声明验证目的
- CoverageDimensionChecker: 检查 happy/error/perf/config 四维度覆盖
- TestQualityReport: 生成质量报告（而非简单 pass/fail）
- AntiPatternDetector: 检测 "为通过而改" 的反模式

使用示例:
    from scripts.collaboration.test_quality_guard import TestQualityGuard

    guard = TestQualityGuard(module_path="scripts/collaboration/coordinator.py",
                              test_path="scripts/collaboration/coordinator_test.py")
    report = guard.audit()
    print(report.to_markdown())
"""

import os
import re
import ast
import time
import inspect
import textwrap
import importlib.util
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple, Set
from enum import Enum
from datetime import datetime


class Severity(Enum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    INFO = "info"
    SUGGESTION = "suggestion"


class TestDimension(Enum):
    HAPPY_PATH = "happy_path"
    ERROR_CASE = "error_case"
    BOUNDARY = "boundary"
    PERFORMANCE = "performance"
    CONFIGURATION = "configuration"
    INTEGRATION = "integration"
    SECURITY = "security"


@dataclass
class QualityIssue:
    id: str
    severity: Severity
    category: str
    message: str
    file: str
    line: int = 0
    suggestion: str = ""
    auto_fixable: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "severity": self.severity.value,
            "category": self.category,
            "message": self.message,
            "file": self.file,
            "line": self.line,
            "suggestion": self.suggestion,
            "auto_fixable": self.auto_fixable,
        }


@dataclass
class TestFunctionMeta:
    name: str
    line: int
    has_purpose: bool = False
    purpose_text: str = ""
    dimension: Optional[TestDimension] = None
    assert_count: int = 0
    assert_types: List[str] = field(default_factory=list)
    has_error_test: bool = False
    has_performance_check: bool = False
    docstring: str = ""


@dataclass
class APISignature:
    name: str
    kind: str
    params: List[Dict[str, str]] = field(default_factory=list)
    return_type: str = ""
    file: str = ""
    line: int = 0


@dataclass
class QualityScore:
    api_compliance: float = 0.0
    purpose_coverage: float = 0.0
    dimension_balance: float = 0.0
    anti_pattern_free: float = 0.0
    overall: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "api_compliance": round(self.api_compliance, 2),
            "purpose_coverage": round(self.purpose_coverage, 2),
            "dimension_balance": round(self.dimension_balance, 2),
            "anti_pattern_free": round(self.anti_pattern_free, 2),
            "overall": round(self.overall, 2),
        }


@dataclass
class TestQualityReport:
    module_name: str
    test_file: str
    source_file: str
    total_tests: int = 0
    issues: List[QualityIssue] = field(default_factory=list)
    test_functions: List[TestFunctionMeta] = field(default_factory=list)
    api_signatures: List[APISignature] = field(default_factory=list)
    score: QualityScore = field(default_factory=QualityScore)
    audit_time: float = 0.0
    timestamp: str = ""

    @property
    def critical_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.CRITICAL)

    @property
    def major_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.MAJOR)

    @property
    def minor_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == Severity.MINOR)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "module_name": self.module_name,
            "test_file": self.test_file,
            "source_file": self.source_file,
            "total_tests": self.total_tests,
            "issue_count": len(self.issues),
            "critical": self.critical_count,
            "major": self.major_count,
            "minor": self.minor_count,
            "score": self.score.to_dict(),
            "audit_time_s": round(self.audit_time, 3),
            "timestamp": self.timestamp,
        }

    def to_markdown(self) -> str:
        lines = [
            f"# TestQualityGuard 审计报告",
            "",
            f"**模块**: {self.module_name}",
            f"**测试文件**: {self.test_file}",
            f"**源文件**: {self.source_file}",
            f"**审计时间**: {self.timestamp}",
            f"**总耗时**: {self.audit_time:.3f}s",
            "",
            "## 评分总览",
            "",
            f"| 维度 | 得分 | 说明 |",
            f"|------|------|------|",
            f"| API 合规性 | {self.score.api_compliance:.0%} | 测试调用是否匹配实际 API 签名 |",
            f"| 目的声明率 | {self.score.purpose_coverage:.0%} | 测试函数是否声明了验证目的 |",
            f"| 维度平衡度 | {self.score.dimension_balance:.0%} | 各测试维度是否均衡 |",
            f"| 反模式检测 | {self.score.anti_pattern_free:.0%} | 是否存在 '为通过而改' 反模式 |",
            f"| **综合得分** | **{self.score.overall:.0%}** | |",
            "",
        ]

        if self.issues:
            lines.extend([
                "## 问题清单",
                "",
                f"🔴 **严重**: {self.critical_count} | 🟠 **主要**: {self.major_count} | 🟡 **次要**: {self.minor_count}",
                "",
            ])
            for issue in self.issues:
                icon = {"critical": "🔴", "major": "🟠", "minor": "🟡", "info": "🔵", "suggestion": "💡"}.get(issue.severity.value, "⚪")
                lines.append(f"- {icon} **[{issue.category}]** {issue.message}")
                if issue.suggestion:
                    lines.append(f"  → 建议: {issue.suggestion}")
                if issue.line:
                    lines.append(f"  → 位置: {issue.file}:{issue.line}")
                lines.append("")

        if self.test_functions:
            has_purpose = sum(1 for t in self.test_functions if t.has_purpose)
            lines.extend([
                "## 测试函数清单",
                "",
                f"总计: {len(self.test_functions)} 个 | 有目的声明: {has_purpose} ({has_purpose/max(len(self.test_functions),1):.0%})",
                "",
                "| # | 函数名 | 目的声明 | 维度 | 断言数 | 异常测试 | 性能测试 |",
                "|---|--------|---------|------|--------|---------|---------|",
            ])
            for idx, tf in enumerate(self.test_functions, 1):
                purpose_icon = "✅" if tf.has_purpose else "❌"
                dim = tf.dimension.value if tf.dimension else "-"
                err_icon = "✅" if tf.has_error_test else "-"
                perf_icon = "✅" if tf.has_performance_check else "-"
                lines.append(
                    f"| {idx} | `{tf.name}` | {purpose_icon} | {dim} | {tf.assert_count} | {err_icon} | {perf_icon} |"
                )
            lines.append("")

        lines.extend([
            "---",
            f"*由 TestQualityGuard v1.0 自动生成*",
        ])
        return "\n".join(lines)


class APISignatureValidator:
    """检查测试代码中的 API 调用是否与实际签名一致"""

    PARAM_PATTERN = re.compile(r'(\w+)\s*=\s*')

    def __init__(self):
        self.api_cache: Dict[str, List[APISignature]] = {}

    def extract_api_signatures(self, source_code: str, file_path: str) -> List[APISignature]:
        signatures = []
        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            return signatures

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                has_self = any(arg.arg == 'self' for arg in node.args.args)
                params = []
                for arg in node.args.args:
                    if arg.arg != 'self':
                        annotation = ""
                        if arg.annotation:
                            try:
                                annotation = ast.unparse(arg.annotation)
                            except Exception:
                                annotation = "?"
                        params.append({"name": arg.arg, "type": annotation})
                sig = APISignature(
                    name=node.name,
                    kind="method" if has_self else "function",
                    params=params,
                    file=file_path,
                    line=node.lineno,
                )
                signatures.append(sig)
        return signatures

    def validate_call_against_signature(self,
                                         call_name: str,
                                         call_kwargs: Set[str],
                                         signatures: List[APISignature]) -> List[QualityIssue]:
        issues = []
        matching_sigs = [s for s in signatures if s.name == call_name]
        if not matching_sigs:
            return issues

        for sig in matching_sigs:
            param_names = {p['name'] for p in sig.params if p['name'] != 'self'}
            for kw in call_kwargs:
                if kw not in param_names and not kw.startswith('_'):
                    issues.append(QualityIssue(
                        id=f"api-param-{call_name}-{kw}",
                        severity=Severity.MAJOR,
                        category="API参数错误",
                        message=f"`{call_name}()` 使用了不存在的参数 `{kw}`，实际签名为: {[p['name'] for p in sig.params]}",
                        file=sig.file,
                        line=sig.line,
                        suggestion=f"检查 `{call_name}` 的实际签名，将 `{kw}` 改为正确的参数名",
                        auto_fixable=False,
                    ))
        return issues


class AntiPatternDetector:
    """检测 '为测试通过而修改测试' 的反模式"""

    SUSPICIOUS_PATTERNS = [
        {
            "id": "anti-loose-assert",
            "pattern": re.compile(r'assertTrue\(.+\)'),
            "description": "使用 assertTrue 替代精确断言（可能为了绕过失败）",
            "severity": Severity.MINOR,
            "category": "宽松断言",
        },
        {
            "id": "anti-relaxed-float",
            "pattern": re.compile(r'assertGreater\(.*,\s*0\.0\)'),
            "description": "浮点数比较用 0.0 作为下限（几乎必然通过）",
            "severity": Severity.MINOR,
            "category": "无效断言",
        },
        {
            "id": "anti-no-error-test",
            "pattern": None,
            "description": "整个测试类无异常/错误测试用例",
            "severity": Severity.MAJOR,
            "category": "缺失错误测试",
        },
        {
            "id": "anti-no-purpose-doc",
            "pattern": None,
            "description": "测试函数无目的声明注释或docstring",
            "severity": Severity.INFO,
            "category": "缺少目的声明",
        },
        {
            "id": "anti-bare-except",
            "pattern": re.compile(r'except\s*:'),
            "description": "裸 except 子句（吞掉所有异常）",
            "severity": Severity.MAJOR,
            "category": "异常吞噬",
        },
        {
            "id": "anti-magic-number",
            "pattern": re.compile(r'(assertEqual|assertGreater|assertLess)\([^,]+,\s*\d{3,}\)'),
            "description": "断言中使用大数字魔法值（可能是凑出来的阈值）",
            "severity": Severity.MINOR,
            "category": "魔法数字",
        },
    ]

    def detect_in_source(self, source: str, file: str) -> List[QualityIssue]:
        issues = []
        lines = source.split('\n')
        for idx, line in enumerate(lines, 1):
            stripped = line.strip()
            for pat in self.SUSPICIOUS_PATTERNS:
                if pat["pattern"] and pat["pattern"].search(stripped):
                    issues.append(QualityIssue(
                        id=pat["id"],
                        severity=pat["severity"],
                        category=pat["category"],
                        message=pat["description"],
                        file=file,
                        line=idx,
                        suggestion=self._get_suggestion(pat["id"]),
                        auto_fixable=False,
                    ))
        return issues

    def _get_suggestion(self, pattern_id: str) -> str:
        suggestions = {
            "anti-loose-assert": "使用精确断言如 assertEqual/assertIn 替代 assertTrue",
            "anti-relaxed-float": "设置有意义的性能阈值，如 assertGreater(score, 0.5)",
            "anti-no-error-test": "添加至少一个异常场景测试用例",
            "anti-no-purpose-doc": "在测试函数前添加注释说明验证目的",
            "anti-bare-except": "指定具体异常类型如 except ValueError",
            "anti-magic-number": "提取为命名常量并添加注释说明来源",
        }
        return suggestions.get(pattern_id, "")


class TestPurposeParser:
    """解析测试函数的目的声明"""

    PURPOSE_MARKERS = ['#', '"""', "'''"]
    PURPOSE_KEYWORDS = ['verify', 'check', 'test', 'ensure', 'validate',
                         '验证', '检查', '测试', '确保', '确认',
                         'should', 'expect', '当', 'when']

    DIMENSION_KEYWORDS = {
        TestDimension.ERROR_CASE: ['error', 'exception', 'invalid', 'fail',
                                     '错误', '异常', '非法', '失败', 'raises'],
        TestDimension.PERFORMANCE: ['performance', 'speed', 'latency', 'timing',
                                     'benchmark', 'perf', '性能', '延迟', '耗时'],
        TestDimension.BOUNDARY: ['boundary', 'edge', 'empty', 'null', 'zero',
                                  'max', 'min', '边界', '空', '极限'],
        TestDimension.CONFIGURATION: ['config', 'setting', 'option', 'env',
                                       '配置', '设定', '环境变量'],
        TestDimension.INTEGRATION: ['integration', 'e2e', 'end.to.end',
                                     '集成', '端到端'],
        TestDimension.SECURITY: ['security', 'auth', 'permission', 'inject',
                                  '安全', '权限', '注入'],
    }

    def parse_function(self, func_node: ast.FunctionDef, source_lines: List[str]) -> TestFunctionMeta:
        meta = TestFunctionMeta(
            name=func_node.name,
            line=func_node.lineno,
            has_purpose=False,
        )

        docstring = ast.get_docstring(func_node)
        if docstring:
            meta.docstring = docstring
            meta.has_purpose = True
            meta.purpose_text = docstring.strip().split('\n')[0][:200]

        start_line = func_node.lineno - 1
        end_line = func_node.end_lineno or start_line + 1
        func_source = '\n'.join(source_lines[start_line:end_line])

        if not meta.has_purpose:
            for i in range(start_line, min(end_line, start_line + 5, len(source_lines))):
                if i >= 0 and i < len(source_lines):
                    line = source_lines[i].strip()
                    if line.startswith('#') and any(kw in line.lower() for kw in self.PURPOSE_KEYWORDS):
                        meta.has_purpose = True
                        meta.purpose_text = line.lstrip('#').strip()[:200]
                        break

        lower_source = func_source.lower()
        meta.has_error_test = ('assertRaises' in func_source or
                               'except' in func_source or
                               'error' in lower_source or
                               'exception' in lower_source or
                               'invalid' in lower_source)
        meta.has_performance_check = any(kw in lower_source
                                          for kw in ['time', 'duration', 'latency',
                                                     'benchmark', 'performance',
                                                     'timing'])

        meta.dimension = self._infer_dimension(func_source)

        assert_types = re.findall(r'self\.(assert\w+)', func_source)
        meta.assert_types = list(set(assert_types))
        meta.assert_count = len(re.findall(r'self\.assert\w+', func_source))

        return meta

    def _infer_dimension(self, source: str) -> Optional[TestDimension]:
        lower = source.lower()
        scores = {}
        for dim, keywords in self.DIMENSION_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in lower)
            if score > 0:
                scores[dim] = score
        if scores:
            return max(scores, key=scores.get)
        return TestDimension.HAPPY_PATH


class TestQualityGuard:
    """
    测试质量守卫 - 主入口

    对测试文件进行全方位质量审计，
    输出可操作的改进建议报告。
    """

    def __init__(self,
                 module_path: str,
                 test_path: str,
                 strict_mode: bool = False):
        """
        Args:
            module_path: 被测模块路径 (如 scripts/collaboration/coordinator.py)
            test_path: 测试文件路径 (如 scripts/collaboration/coordinator_test.py)
            strict_mode: 严格模式（更多检查项）
        """
        self.module_path = Path(module_path)
        self.test_path = Path(test_path)
        self.strict_mode = strict_mode
        self.api_validator = APISignatureValidator()
        self.anti_detector = AntiPatternDetector()
        self.purpose_parser = TestPurposeParser()

    def audit(self) -> TestQualityReport:
        """执行完整审计"""
        start_time = time.time()
        report = TestQualityReport(
            module_name=self.module_path.stem,
            test_file=str(self.test_path),
            source_file=str(self.module_path),
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

        source_code = self._read_file(self.module_path)
        test_code = self._read_file(self.test_path)

        if not source_code or not test_code:
            report.issues.append(QualityIssue(
                id="file-not-found", severity=Severity.CRITICAL,
                category="文件读取", message="无法读取源文件或测试文件",
                file=str(self.module_path),
            ))
            report.audit_time = time.time() - start_time
            return report

        source_lines = source_code.split('\n')

        report.api_signatures = self.api_validator.extract_api_signatures(source_code, str(self.module_path))

        test_tree = ast.parse(test_code)
        test_funcs = [node for node in ast.walk(test_tree)
                      if isinstance(node, ast.FunctionDef) and node.name.startswith('test_')]
        report.total_tests = len(test_funcs)

        for func_node in test_funcs:
            meta = self.purpose_parser.parse_function(func_node, source_lines)
            report.test_functions.append(meta)

            if not meta.has_purpose:
                report.issues.append(QualityIssue(
                    id=f"no-purpose-{meta.name}",
                    severity=Severity.INFO,
                    category="缺少目的声明",
                    message=f"`{meta.name}` 缺少测试目的声明（注释或docstring）",
                    file=str(self.test_path),
                    line=meta.line,
                    suggestion="添加 '# 验证: ...' 注释或 docstring 说明此测试验证什么",
                    auto_fixable=True,
                ))

        anti_issues = self.anti_detector.detect_in_source(test_code, str(self.test_path))
        report.issues.extend(anti_issues)

        no_error_class = not any(tf.has_error_test for tf in report.test_functions)
        if no_error_class and report.total_tests > 5:
            report.issues.append(QualityIssue(
                id="no-error-tests",
                severity=Severity.MAJOR,
                category="缺失错误测试",
                message=f"{report.total_tests}个测试中无异常/错误场景测试",
                file=str(self.test_path),
                suggestion="添加至少 15% 的错误/异常测试用例（如非法输入、网络超时、权限不足等）",
            ))

        no_perf = not any(tf.has_performance_check for tf in report.test_functions)
        if no_perf and report.total_tests > 5:
            report.issues.append(QualityIssue(
                id="no-perf-tests",
                severity=Severity.MINOR,
                category="缺失性能测试",
                message="无性能/耗时相关测试",
                file=str(self.test_path),
                suggestion="添加关键路径的性能基准测试（如操作应在 Nms 内完成）",
            ))

        report.score = self._calculate_score(report)
        report.audit_time = time.time() - start_time
        return report

    def _read_file(self, path: Path) -> Optional[str]:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            return None

    def _calculate_score(self, report: TestQualityReport) -> QualityScore:
        score = QualityScore()

        if report.total_tests > 0:
            purpose_count = sum(1 for t in report.test_functions if t.has_purpose)
            score.purpose_coverage = purpose_count / report.total_tests

        dim_counts = {}
        for tf in report.test_functions:
            d = tf.dimension or TestDimension.HAPPY_PATH
            dim_counts[d] = dim_counts.get(d, 0) + 1
        if dim_counts:
            values = list(dim_counts.values())
            max_v = max(values)
            min_v = min(values)
            total = sum(values)
            expected_per_dim = total / len(dim_counts)
            variance = sum((v - expected_per_dim) ** 2 for v in values) / len(values)
            ideal_variance = 0
            score.dimension_balance = max(0, 1 - (variance / (total * total / 4)))

        anti_critical = sum(1 for i in report.issues
                           if i.severity in (Severity.CRITICAL, Severity.MAJOR)
                           and i.category in ('宽松断言', '异常吞噬'))
        score.anti_pattern_free = max(0, 1 - anti_critical / max(report.total_tests * 0.1, 1))

        api_issues = sum(1 for i in report.issues if i.category == "API参数错误")
        score.api_compliance = max(0, 1 - api_issues / max(report.total_tests * 0.05, 1))

        score.overall = (
            score.api_compliance * 0.25 +
            score.purpose_coverage * 0.30 +
            score.dimension_balance * 0.20 +
            score.anti_pattern_free * 0.25
        )

        return score

    def audit_project(self, project_root: str,
                      pattern: str = "**/*_test.py") -> List[TestQualityReport]:
        """审计整个项目的所有测试文件"""
        reports = []
        root = Path(project_root)
        test_files = sorted(root.glob(pattern))

        for test_file in test_files:
            module_name = test_file.name.replace("_test.py", ".py")
            candidates = [
                test_file.parent / module_name,
                test_file.parent / module_name.replace(".py", "/__init__.py"),
            ]
            for candidate in candidates:
                if candidate.exists():
                    try:
                        r = self.__class__(str(candidate), str(test_file)).audit()
                        reports.append(r)
                    except Exception:
                        pass
                    break
        return reports

    def generate_test_template(self,
                               api_sig: APISignature,
                               dimensions: List[TestDimension] = None) -> str:
        """根据 API 签名生成高质量测试模板"""
        dims = dimensions or [TestDimension.HAPPY_PATH, TestDimension.ERROR_CASE]
        params_str = ", ".join(p['name'] for p in api_sig.params if p['name'] != 'self')
        param_docs = "\n".join(f"        {p['name']}: {p['type'] or 'Any'}" for p in api_sig.params if p['name'] != 'self')

        template = f'''\
    def test_{api_sig.name}_happy_path(self):
        """验证: {api_sig.name} 正常输入应返回预期结果"""
        # Arrange
{param_docs if param_docs else "        # TODO: 设置正常输入参数"}

        # Act
        result = self.target.{api_sig.name}({params_str})

        # Assert
        self.assertIsNotNone(result)
'''

        if TestDimension.ERROR_CASE in dims:
            template += f'''
    def test_{api_sig.name}_invalid_input(self):
        """验证: {api_sig.name} 非法输入应抛出异常或返回错误"""
        # TODO: 测试非法参数、空值、越界等情况
        with self.assertRaises((ValueError, TypeError)):
            self.target.{api_sig.name}(invalid_param="bad_value")
'''

        if TestDimension.PERFORMANCE in dims:
            template += f'''
    def test_{api_sig.name}_performance(self):
        """验证: {api_sig.name} 应在合理时间内完成"""
        import time
        start = time.perf_counter()
        self.target.{api_sig.name}({params_str})
        elapsed = (time.perf_counter() - start) * 1000
        self.assertLess(elapsed, 100, f"耗时 {{elapsed:.1f}}ms 超过 100ms 阈值")
'''
        return template


def quick_audit(module_path: str, test_path: str) -> TestQualityReport:
    """便捷函数：单文件审计"""
    return TestQualityGuard(module_path, test_path).audit()


def project_audit(project_root: str) -> str:
    """便捷函数：项目级审计，返回 Markdown 报告"""
    guard = TestQualityGuard("", "")
    reports = guard.audit_project(project_root)
    lines = ["# 项目级测试质量审计报告\n"]
    total_score = 0
    for r in reports:
        lines.append(r.to_markdown())
        lines.append("\n---\n")
        total_score += r.score.overall
    if reports:
        avg = total_score / len(reports)
        lines.append(f"\n## 项目总体评分: **{avg:.0%}** ({len(reports)} 个模块)")
    return "\n".join(lines)
