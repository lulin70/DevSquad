#!/usr/bin/env python3
"""
Tests for CLICommandClassifier (ROADMAP P2-UI-1: impeccable 23-command vocabulary alignment).

Covers T1-T22: classify() per-category, structure completeness, suggested_alias,
audit_cli() report fields, suggest_command() intent matching, COMMAND_CATEGORIES
cardinality, and boundary inputs. Includes an e2e-marked end-to-end audit flow
test validating the real DevSquad CLI command surface discovered from cli.py.

Spec reference: ROADMAP P2-UI-1
"""

import pytest

from scripts.collaboration.cli_command_classifier import CLICommandClassifier


class TestClassifyCreateCategory:
    """T1: classify() 创建类命令 → category="create"."""

    def setup_method(self):
        self.clf = CLICommandClassifier()

    @pytest.mark.parametrize("cmd", ["create", "generate", "init", "scaffold"])
    def test_create_category_commands(self, cmd):
        result = self.clf.classify(cmd)
        assert result["category"] == "create"
        assert result["aligned"] is True


class TestClassifyReviewCategory:
    """T2: classify() 审查类命令 → category="review"."""

    def setup_method(self):
        self.clf = CLICommandClassifier()

    @pytest.mark.parametrize("cmd", ["review", "audit", "inspect", "analyze"])
    def test_review_category_commands(self, cmd):
        result = self.clf.classify(cmd)
        assert result["category"] == "review"
        assert result["aligned"] is True


class TestClassifyNavigateCategory:
    """T3: classify() 导航类命令 → category="navigate"."""

    def setup_method(self):
        self.clf = CLICommandClassifier()

    @pytest.mark.parametrize("cmd", ["list", "show", "find", "search"])
    def test_navigate_category_commands(self, cmd):
        result = self.clf.classify(cmd)
        assert result["category"] == "navigate"
        assert result["aligned"] is True


class TestClassifyConfigureCategory:
    """T4: classify() 配置类命令 → category="configure"."""

    def setup_method(self):
        self.clf = CLICommandClassifier()

    @pytest.mark.parametrize("cmd", ["config", "set", "enable", "disable"])
    def test_configure_category_commands(self, cmd):
        result = self.clf.classify(cmd)
        assert result["category"] == "configure"
        assert result["aligned"] is True


class TestClassifyExecuteCategory:
    """T5: classify() 执行类命令 → category="execute"."""

    def setup_method(self):
        self.clf = CLICommandClassifier()

    @pytest.mark.parametrize("cmd", ["run", "dispatch", "execute", "start"])
    def test_execute_category_commands(self, cmd):
        result = self.clf.classify(cmd)
        assert result["category"] == "execute"
        assert result["aligned"] is True


class TestClassifyMaintainCategory:
    """T6: classify() 维护类命令 → category="maintain"."""

    def setup_method(self):
        self.clf = CLICommandClassifier()

    @pytest.mark.parametrize("cmd", ["clean", "fix", "update", "upgrade"])
    def test_maintain_category_commands(self, cmd):
        result = self.clf.classify(cmd)
        assert result["category"] == "maintain"
        assert result["aligned"] is True


class TestClassifyStopCategory:
    """T7: classify() 终止类命令 → category="stop"."""

    def setup_method(self):
        self.clf = CLICommandClassifier()

    @pytest.mark.parametrize("cmd", ["stop", "cancel", "abort"])
    def test_stop_category_commands(self, cmd):
        result = self.clf.classify(cmd)
        assert result["category"] == "stop"
        assert result["aligned"] is True


class TestClassifyUnknown:
    """T8: classify() 未知命令 → category="unknown", aligned=False."""

    def setup_method(self):
        self.clf = CLICommandClassifier()

    def test_unknown_command_category(self):
        result = self.clf.classify("foobar")
        assert result["category"] == "unknown"
        assert result["aligned"] is False

    def test_unknown_command_not_in_vocabulary(self):
        result = self.clf.classify("xyzzy")
        assert result["aligned"] is False
        assert result["category"] == "unknown"


class TestClassifyStructure:
    """T9: classify() 返回结构完整性."""

    def setup_method(self):
        self.clf = CLICommandClassifier()

    def test_result_has_all_required_keys(self):
        result = self.clf.classify("create")
        assert set(result.keys()) == {"command", "category", "aligned", "suggested_alias"}

    def test_result_value_types(self):
        result = self.clf.classify("review")
        assert isinstance(result["command"], str)
        assert isinstance(result["category"], str)
        assert isinstance(result["aligned"], bool)
        # suggested_alias is str | None
        assert result["suggested_alias"] is None or isinstance(result["suggested_alias"], str)

    def test_aligned_command_has_no_suggested_alias(self):
        result = self.clf.classify("init")
        assert result["aligned"] is True
        assert result["suggested_alias"] is None


class TestSuggestedAlias:
    """T10: classify() suggested_alias 对未对齐命令提供建议."""

    def setup_method(self):
        self.clf = CLICommandClassifier()

    def test_devsquad_demo_suggests_run(self):
        result = self.clf.classify("demo")
        assert result["aligned"] is False
        assert result["suggested_alias"] == "run"

    def test_devsquad_status_suggests_show(self):
        result = self.clf.classify("status")
        assert result["suggested_alias"] == "show"

    def test_devsquad_spec_suggests_create(self):
        result = self.clf.classify("spec")
        assert result["suggested_alias"] == "create"

    def test_truly_unknown_command_has_no_alias(self):
        result = self.clf.classify("xyzzy")
        assert result["suggested_alias"] is None


class TestAuditCli:
    """T11-T16: audit_cli() 报告字段."""

    def setup_method(self):
        self.clf = CLICommandClassifier()
        self.report = self.clf.audit_cli()

    def test_total_commands_positive(self):
        # T11
        assert self.report["total_commands"] > 0

    def test_aligned_count_non_negative(self):
        # T12
        assert self.report["aligned_count"] >= 0

    def test_aligned_percentage_range(self):
        # T13
        pct = self.report["aligned_percentage"]
        assert isinstance(pct, float)
        assert 0.0 <= pct <= 100.0

    def test_by_category_has_all_seven_impeccable_categories(self):
        # T14
        by_category = self.report["by_category"]
        for cat in CLICommandClassifier.COMMAND_CATEGORIES:
            assert cat in by_category, f"Missing category: {cat}"
        assert "unknown" in by_category

    def test_unaligned_list_structure(self):
        # T15
        unaligned = self.report["unaligned"]
        assert isinstance(unaligned, list)
        for item in unaligned:
            assert isinstance(item, dict)
            assert item["aligned"] is False
            assert item["category"] == "unknown"
            assert "command" in item
            assert "suggested_alias" in item

    def test_recommendations_non_empty(self):
        # T16 — DevSquad has unaligned commands, so recommendations must exist
        recs = self.report["recommendations"]
        assert isinstance(recs, list)
        assert len(recs) > 0

    def test_audit_internal_consistency(self):
        total = self.report["total_commands"]
        aligned = self.report["aligned_count"]
        unaligned_count = len(self.report["unaligned"])
        assert aligned + unaligned_count == total


class TestSuggestCommand:
    """T17-T20: suggest_command() 意图匹配."""

    def setup_method(self):
        self.clf = CLICommandClassifier()

    def test_check_code_quality_suggests_review_audit(self):
        # T17
        suggestions = self.clf.suggest_command("check code quality")
        assert "review" in suggestions
        assert "audit" in suggestions

    def test_start_a_task_suggests_execute_words(self):
        # T18
        suggestions = self.clf.suggest_command("start a task")
        assert "run" in suggestions
        assert "dispatch" in suggestions
        assert "execute" in suggestions

    def test_list_available_skills_suggests_navigate_words(self):
        # T19
        suggestions = self.clf.suggest_command("list available skills")
        assert "list" in suggestions
        assert "show" in suggestions

    def test_unknown_intent_returns_empty_list(self):
        # T20
        suggestions = self.clf.suggest_command("xyzzy qwerty zzz")
        assert suggestions == []

    def test_suggestions_are_from_impeccable_vocabulary(self):
        all_words = {
            w for words in CLICommandClassifier.COMMAND_CATEGORIES.values() for w in words
        }
        suggestions = self.clf.suggest_command("I want to create and run something")
        for s in suggestions:
            assert s in all_words


class TestCommandCategoriesCardinality:
    """T21: COMMAND_CATEGORIES 类别数与词表规模.

    Note: impeccable 原始词表为 23 个分类命令词。本分类器采用 27 词扩展同义词集
    （7 类 × 3~4 词 = 27）以覆盖 DevSquad 领域动词。T1-T7 要求全部 27 词存在，
    故此处断言 7 类 + 27 词的内部一致性。
    """

    def test_seven_categories(self):
        assert len(CLICommandClassifier.COMMAND_CATEGORIES) == 7

    def test_total_vocabulary_word_count(self):
        total = sum(len(v) for v in CLICommandClassifier.COMMAND_CATEGORIES.values())
        assert total == 27  # 6 categories × 4 + 1 category × 3

    def test_no_duplicate_words_across_categories(self):
        all_words = [
            w for words in CLICommandClassifier.COMMAND_CATEGORIES.values() for w in words
        ]
        assert len(all_words) == len(set(all_words))

    def test_categories_match_expected_names(self):
        expected = {"create", "review", "navigate", "configure", "execute", "maintain", "stop"}
        assert set(CLICommandClassifier.COMMAND_CATEGORIES.keys()) == expected


class TestBoundaryInputs:
    """T22: 边界输入（空字符串、超长命令、特殊字符）."""

    def setup_method(self):
        self.clf = CLICommandClassifier()

    def test_empty_string_is_unknown(self):
        result = self.clf.classify("")
        assert result["category"] == "unknown"
        assert result["aligned"] is False
        assert result["suggested_alias"] is None

    def test_whitespace_only_is_unknown(self):
        result = self.clf.classify("   ")
        assert result["category"] == "unknown"
        assert result["aligned"] is False

    def test_very_long_string_is_unknown(self):
        result = self.clf.classify("a" * 10_000)
        assert result["category"] == "unknown"
        assert result["aligned"] is False

    def test_special_characters_are_unknown(self):
        result = self.clf.classify("create!@#")
        assert result["category"] == "unknown"
        assert result["aligned"] is False

    def test_case_insensitive_match(self):
        result = self.clf.classify("CREATE")
        assert result["category"] == "create"
        assert result["aligned"] is True

    def test_leading_trailing_whitespace_stripped(self):
        result = self.clf.classify("  review  ")
        assert result["category"] == "review"
        assert result["aligned"] is True

    def test_suggest_command_empty_intent(self):
        assert self.clf.suggest_command("") == []


@pytest.mark.e2e
class TestAuditCliEndToEnd:
    """E2E: 端到端验证 audit_cli() 对真实 DevSquad CLI 命令面的审计.

    模拟真实使用: 实例化分类器 → 运行审计 → 校验报告完整性与已知对齐结果，
    覆盖从命令发现到报告生成的完整链路（用户规则 3: 发布前 e2e 测试）。
    """

    def test_full_audit_flow_returns_consistent_report(self):
        clf = CLICommandClassifier()
        report = clf.audit_cli()

        # 报告结构完整
        required_keys = {
            "total_commands",
            "aligned_count",
            "aligned_percentage",
            "by_category",
            "unaligned",
            "recommendations",
        }
        assert set(report.keys()) >= required_keys

        # 真实 DevSquad CLI 至少发现 12 个规范命令（init/demo/dispatch/status/
        # roles/lifecycle + spec/plan/build/test/review/ship）
        assert report["total_commands"] >= 12

        # 已知对齐命令: init (create), dispatch (execute), review (review)
        by_category = report["by_category"]
        assert "init" in by_category["create"]
        assert "dispatch" in by_category["execute"]
        assert "review" in by_category["review"]

        # 已知未对齐命令落入 unknown
        unknown_commands = by_category["unknown"]
        for expected_unaligned in ["demo", "status", "spec", "build", "ship"]:
            assert expected_unaligned in unknown_commands
        # 对齐率：6 个对齐的（init/dispatch/review/list/show/set）+ 8 个未对齐 = 6/20 = 30.0%
        assert report["aligned_count"] == 6
        assert report["aligned_percentage"] == 30.0

        # 推荐建议覆盖所有未对齐命令
        recs_text = " ".join(report["recommendations"])
        for unaligned_cmd in ["demo", "status", "spec", "build", "ship"]:
            assert unaligned_cmd in recs_text

    def test_real_cli_command_discovery_matches_static_fallback(self):
        # AST 发现的命令应覆盖静态回退清单中的全部命令
        clf = CLICommandClassifier()
        discovered = clf._discover_cli_commands()  # noqa: SLF001
        for cmd in clf.DEVSQUAD_CLI_COMMANDS:
            assert cmd in discovered, f"Discovered commands missing: {cmd}"
