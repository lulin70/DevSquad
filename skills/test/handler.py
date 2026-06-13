"""Test Strategy Generation Skill - V3.6.8"""

from scripts.collaboration.test_quality_guard import (
    APISignature,
    TestDimension,
    TestQualityGuard,
)
from skills.registry import BaseSkill


class TestSkill(BaseSkill):
    name = "test"
    description = "测试策略生成与质量审计 - API验证/反模式检测/维度覆盖"
    version = "3.6.8"

    SUPPORTED_TYPES = ["unit", "integration", "e2e"]
    COVERAGE_DIMENSIONS = [
        "API validation",
        "Anti-pattern detection",
        "Dimension coverage",
    ]

    def run(self, action="info", **kwargs):
        actions = {
            "generate_strategy": self.generate_strategy,
            "audit_test_quality": self.audit_test_quality,
            "suggest_cases": self.suggest_cases,
            "coverage_dimensions": self.coverage_dimensions,
        }
        fn = actions.get(action)
        if not fn:
            return {"error": f"Unknown action: {action}. Available: {list(actions.keys())}"}
        return fn(**kwargs)

    def generate_strategy(self, code_context: str, test_type: str = "unit") -> dict:
        if test_type not in self.SUPPORTED_TYPES:
            return {"error": f"Unsupported test_type: {test_type}. Use: {self.SUPPORTED_TYPES}"}
        dim_map = {
            "unit": [TestDimension.HAPPY_PATH, TestDimension.ERROR_CASE, TestDimension.BOUNDARY],
            "integration": [TestDimension.INTEGRATION, TestDimension.CONFIGURATION],
            "e2e": [TestDimension.PERFORMANCE, TestDimension.SECURITY, TestDimension.INTEGRATION],
        }
        dims = dim_map.get(test_type, [TestDimension.HAPPY_PATH])
        mock_sig = APISignature(
            name="target_function",
            kind="function",
            params=[{"name": "param1", "type": "str"}, {"name": "param2", "type": "int"}],
        )
        template = TestQualityGuard("", "").generate_test_template(mock_sig, dims)
        return {
            "test_type": test_type,
            "code_context_summary": code_context[:200] if code_context else "",
            "dimensions": [d.value for d in dims],
            "strategy_template": template,
        }

    def audit_test_quality(self, test_file: str) -> dict:
        guard = TestQualityGuard(module_path="", test_path=test_file)
        report = guard.audit()
        return report.to_dict()

    def suggest_cases(self, requirements: str) -> dict:
        suggestions = []
        keywords_map = {
            "登录": ["valid_credentials", "invalid_password", "empty_fields", "account_locked", "session_timeout"],
            "API": ["valid_request", "missing_params", "invalid_format", "rate_limit", "auth_failure"],
            "数据库": ["insert_success", "duplicate_key", "connection_timeout", "transaction_rollback"],
            "文件": ["normal_upload", "large_file", "invalid_type", "permission_denied"],
        }
        matched = False
        for kw, cases in keywords_map.items():
            if kw in requirements:
                suggestions.extend(cases)
                matched = True
        if not matched:
            suggestions = ["happy_path", "error_case", "boundary", "performance_baseline"]
        return {"requirements": requirements, "suggested_cases": suggestions}

    def coverage_dimensions(self) -> list:
        return self.COVERAGE_DIMENSIONS
