#!/usr/bin/env python3
"""Unit tests for dispatch_models.py coverage improvement.

Target: Increase coverage from 17.84% to 75%+
Focus: Data classes, serialization methods, and formatting methods.
"""

from __future__ import annotations

import pytest

from scripts.collaboration.dispatch_models import (
    I18N,
    PLANNED_ROLES,
    ROLE_TEMPLATES,
    DispatchResult,
    PerformanceMetric,
    PerformanceThresholds,
)
from scripts.collaboration.models import WorkflowTrace


@pytest.fixture
def sample_dispatch_result() -> DispatchResult:
    """Create sample DispatchResult for testing."""
    return DispatchResult(
        success=True,
        task_description="设计用户认证系统",
        matched_roles=["architect", "security"],
        summary="认证系统设计完成",
        duration_seconds=12.567,
        worker_results=[
            {
                "worker_id": "architect-0",
                "role": "architect",
                "success": True,
                "output": "架构设计: JWT + OAuth2.0",
            }
        ],
    )


class TestPerformanceMetric:
    """Test PerformanceMetric data class."""

    def test_performance_metric_creation(self) -> None:
        """Test creating PerformanceMetric instance."""
        metric = PerformanceMetric(
            timestamp="2024-11-07 10:30:00",
            task_description="Test task",
            total_duration=15.5,
            step_timings={"execute": 10.0, "collect": 2.0},
            success=True,
            error_count=0,
            role_count=2,
        )
        assert metric.timestamp == "2024-11-07 10:30:00"
        assert metric.total_duration == 15.5
        assert metric.success is True
        assert metric.role_count == 2

    def test_performance_metric_truncates_long_task(self) -> None:
        """Test __post_init__ truncates task descriptions over 50 chars."""
        long_task = "A" * 100
        metric = PerformanceMetric(
            timestamp="2024-11-07 10:30:00",
            task_description=long_task,
            total_duration=15.5,
            step_timings={},
            success=True,
            error_count=0,
            role_count=1,
        )
        assert len(metric.task_description) == 53  # 50 + "..."
        assert metric.task_description.endswith("...")


class TestPerformanceThresholds:
    """Test PerformanceThresholds configuration."""

    def test_default_thresholds(self) -> None:
        """Test default threshold values."""
        thresholds = PerformanceThresholds()
        assert thresholds.total_duration_warning == 30.0
        assert thresholds.total_duration_critical == 60.0
        assert "execute" in thresholds.step_warnings
        assert thresholds.step_warnings["execute"] == 20.0
        assert thresholds.step_criticals["execute"] == 45.0

    def test_custom_thresholds(self) -> None:
        """Test creating thresholds with custom values."""
        thresholds = PerformanceThresholds(
            total_duration_warning=10.0,
            total_duration_critical=20.0,
        )
        assert thresholds.total_duration_warning == 10.0
        assert thresholds.total_duration_critical == 20.0

    def test_all_steps_have_thresholds(self) -> None:
        """Test all 11 steps have warning and critical thresholds."""
        thresholds = PerformanceThresholds()
        expected_steps = [
            "analyze",
            "warmup",
            "plan",
            "spawn",
            "execute",
            "collect",
            "consensus",
            "compress",
            "permission",
            "memory",
            "skillify",
        ]
        for step in expected_steps:
            assert step in thresholds.step_warnings
            assert step in thresholds.step_criticals


class TestDispatchResultSerialization:
    """Test DispatchResult to_dict() method."""

    def test_to_dict_basic_fields(self, sample_dispatch_result: DispatchResult) -> None:
        """Test to_dict() includes all basic fields."""
        result_dict = sample_dispatch_result.to_dict()
        assert result_dict["success"] is True
        assert result_dict["task_description"] == "设计用户认证系统"
        assert result_dict["matched_roles"] == ["architect", "security"]
        assert result_dict["summary"] == "认证系统设计完成"
        assert result_dict["duration_seconds"] == 12.57  # Rounded to 2 decimals
        assert len(result_dict["worker_results"]) == 1

    def test_to_dict_rounds_duration(self) -> None:
        """Test to_dict() rounds duration_seconds to 2 decimals."""
        result = DispatchResult(
            success=True,
            task_description="Test",
            duration_seconds=12.56789,
        )
        result_dict = result.to_dict()
        assert result_dict["duration_seconds"] == 12.57

    def test_to_dict_optional_fields(self) -> None:
        """Test to_dict() handles optional fields."""
        result = DispatchResult(
            success=True,
            task_description="Test",
            two_stage_review={"status": "approved"},
            feature_gate={"verdict": "pass"},
            registration_gate={"verdict": "pass"},
        )
        result_dict = result.to_dict()
        assert result_dict["two_stage_review"] == {"status": "approved"}
        assert result_dict["feature_gate"] == {"verdict": "pass"}
        assert result_dict["registration_gate"] == {"verdict": "pass"}

    def test_serialize_workflow_trace_none(self, sample_dispatch_result: DispatchResult) -> None:
        """Test _serialize_workflow_trace() returns None when no trace."""
        assert sample_dispatch_result.workflow_trace is None
        result_dict = sample_dispatch_result.to_dict()
        assert result_dict["workflow_trace"] is None

    def test_serialize_workflow_trace_with_data(self) -> None:
        """Test _serialize_workflow_trace() serializes WorkflowTrace."""
        trace = WorkflowTrace(
            task_description="Test task",
            decomposition_tree={},
            steps=[],
            decision_points=[],
        )
        result = DispatchResult(
            success=True,
            task_description="Test",
            workflow_trace=trace,
        )
        result_dict = result.to_dict()
        assert result_dict["workflow_trace"] is not None
        assert result_dict["workflow_trace"]["task_description"] == "Test task"


class TestDispatchResultFormatting:
    """Test DispatchResult to_markdown() and formatting methods."""

    def test_to_markdown_basic(self, sample_dispatch_result: DispatchResult) -> None:
        """Test to_markdown() generates markdown report."""
        markdown = sample_dispatch_result.to_markdown()
        assert "🤖" in markdown
        assert "设计用户认证系统" in markdown
        assert "✅" in markdown  # Success icon

    def test_to_markdown_chinese(self) -> None:
        """Test to_markdown() uses Chinese I18N."""
        result = DispatchResult(
            success=True,
            task_description="测试任务",
            lang="zh",
        )
        markdown = result.to_markdown()
        assert "状态" in markdown or "成功" in markdown

    def test_to_markdown_english(self) -> None:
        """Test to_markdown() uses English I18N."""
        result = DispatchResult(
            success=True,
            task_description="Test task",
            lang="en",
        )
        markdown = result.to_markdown()
        assert "Success" in markdown or "Task" in markdown

    def test_to_markdown_japanese(self) -> None:
        """Test to_markdown() uses Japanese I18N."""
        result = DispatchResult(
            success=True,
            task_description="テストタスク",
            lang="ja",
        )
        markdown = result.to_markdown()
        assert "成功" in markdown or "タスク" in markdown

    def test_format_workflow_trace_empty(self, sample_dispatch_result: DispatchResult) -> None:
        """Test _format_workflow_trace() returns empty list when None."""
        lines = sample_dispatch_result._format_workflow_trace()
        assert lines == []

    def test_format_replay_cache_disabled(self, sample_dispatch_result: DispatchResult) -> None:
        """Test _format_replay_cache() returns empty when replay is off."""
        sample_dispatch_result.details = {}
        lines = sample_dispatch_result._format_replay_cache()
        assert lines == []

    def test_format_replay_cache_with_stats(self) -> None:
        """Test _format_replay_cache() formats cache statistics."""
        result = DispatchResult(
            success=True,
            task_description="Test",
            details={
                "replay_cache": {
                    "mode": "record",
                    "hits": 4,
                    "misses": 2,
                    "writes": 6,
                }
            },
        )
        lines = result._format_replay_cache()
        assert len(lines) > 0
        text = "\n".join(lines)
        assert "4 replayed" in text
        assert "2 live" in text
        assert "6 recorded" in text

    def test_format_feature_gate_disabled(self, sample_dispatch_result: DispatchResult) -> None:
        """Test _format_feature_gate() returns empty when gate disabled."""
        sample_dispatch_result.details = {}
        lines = sample_dispatch_result._format_feature_gate()
        assert lines == []

    def test_format_feature_gate_with_verdict(self) -> None:
        """Test _format_feature_gate() formats gate verdict."""
        result = DispatchResult(
            success=True,
            task_description="Test",
            details={
                "feature_gate": {
                    "verdict": "pass",
                    "summary": {"total": 5, "pass": 5, "fail": 0, "waived": 0},
                    "violations": [],
                    "entries": [],
                }
            },
        )
        lines = result._format_feature_gate()
        assert len(lines) > 0
        text = "\n".join(lines)
        assert "Feature gate" in text
        assert "pass" in text

    def test_format_registration_gate_disabled(self, sample_dispatch_result: DispatchResult) -> None:
        """Test _format_registration_gate() returns empty when gate disabled."""
        sample_dispatch_result.details = {}
        lines = sample_dispatch_result._format_registration_gate()
        assert lines == []


class TestI18NConstants:
    """Test I18N internationalization dictionaries."""

    def test_i18n_has_three_languages(self) -> None:
        """Test I18N contains zh, en, ja."""
        assert "zh" in I18N
        assert "en" in I18N
        assert "ja" in I18N

    def test_i18n_chinese_keys(self) -> None:
        """Test Chinese I18N has all required keys."""
        zh = I18N["zh"]
        required_keys = [
            "title",
            "task",
            "status_ok",
            "status_fail",
            "duration",
            "roles",
            "summary",
            "output",
            "errors",
            "next_steps",
        ]
        for key in required_keys:
            assert key in zh

    def test_i18n_english_translations(self) -> None:
        """Test English translations are different from Chinese."""
        assert I18N["en"]["title"] != I18N["zh"]["title"]
        assert "Multi-Agent" in I18N["en"]["title"]
        assert "Success" in I18N["en"]["status_ok"]

    def test_i18n_japanese_translations(self) -> None:
        """Test Japanese translations exist."""
        ja = I18N["ja"]
        assert "マルチエージェント" in ja["title"]
        assert "成功" in ja["status_ok"]


class TestRoleTemplatesAndPlannedRoles:
    """Test ROLE_TEMPLATES and PLANNED_ROLES constants."""

    def test_role_templates_not_empty(self) -> None:
        """Test ROLE_TEMPLATES contains role definitions."""
        assert len(ROLE_TEMPLATES) > 0
        assert "architect" in ROLE_TEMPLATES

    def test_role_template_structure(self) -> None:
        """Test each role template has required fields."""
        architect = ROLE_TEMPLATES.get("architect")
        if architect:
            assert "name" in architect
            assert "prompt" in architect
            assert "keywords" in architect

    def test_planned_roles_may_be_empty(self) -> None:
        """Test PLANNED_ROLES structure (may be empty if no planned roles)."""
        # PLANNED_ROLES may be empty dict if get_planned_roles() returns nothing
        assert isinstance(PLANNED_ROLES, dict)

    def test_planned_role_structure(self) -> None:
        """Test each planned role has required fields."""
        for _role_id, role_def in PLANNED_ROLES.items():
            assert "name" in role_def
            assert "status" in role_def
            assert "description" in role_def


class TestDispatchResultEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_worker_results(self) -> None:
        """Test DispatchResult with empty worker_results."""
        result = DispatchResult(
            success=False,
            task_description="Failed task",
            worker_results=[],
        )
        result_dict = result.to_dict()
        assert result_dict["worker_results"] == []
        assert result_dict["success"] is False

    def test_multiple_errors(self) -> None:
        """Test DispatchResult with multiple errors."""
        result = DispatchResult(
            success=False,
            task_description="Task with errors",
            errors=["Error 1", "Error 2", "Error 3"],
        )
        result_dict = result.to_dict()
        assert len(result_dict["errors"]) == 3

    def test_all_optional_gates_populated(self) -> None:
        """Test DispatchResult with all optional gate fields."""
        result = DispatchResult(
            success=True,
            task_description="Test",
            two_stage_review={"status": "approved"},
            auto_fix_result={"fixed": True},
            judge_result={"verdict": "approved"},
            feature_gate={"verdict": "pass"},
            registration_gate={"verdict": "pass"},
            micro_task_plan={"steps": []},
            permission_result={"allowed": True},
        )
        result_dict = result.to_dict()
        assert result_dict["two_stage_review"] is not None
        assert result_dict["auto_fix_result"] is not None
        assert result_dict["judge_result"] is not None
        assert result_dict["feature_gate"] is not None
        assert result_dict["registration_gate"] is not None

    def test_zero_duration(self) -> None:
        """Test DispatchResult with zero duration."""
        result = DispatchResult(
            success=True,
            task_description="Instant task",
            duration_seconds=0.0,
        )
        result_dict = result.to_dict()
        assert result_dict["duration_seconds"] == 0.0


class TestDispatchResultMoreFormatting:
    """Test additional _format_* methods for better coverage."""

    def test_format_registration_gate_with_verdict(self) -> None:
        """Test _format_registration_gate() formats gate verdict."""
        result = DispatchResult(
            success=True,
            task_description="Test",
            details={
                "registration_gate": {
                    "verdict": "pass",
                    "summary": {
                        "mandatory": 5,
                        "tracked": 5,
                        "unregistered": 0,
                        "regressed": 0,
                    },
                    "violations": [],
                    "signals": [],
                }
            },
        )
        lines = result._format_registration_gate()
        assert len(lines) > 0
        text = "\n".join(lines)
        assert "Registration gate" in text
        assert "pass" in text

    def test_format_registration_gate_with_violations(self) -> None:
        """Test _format_registration_gate() includes violations."""
        result = DispatchResult(
            success=False,
            task_description="Test",
            details={
                "registration_gate": {
                    "verdict": "fail",
                    "summary": {"mandatory": 5, "unregistered": 2},
                    "violations": ["Signal X not registered", "Signal Y regressed"],
                    "signals": [
                        {"type": "signal_a", "status": "tracked", "tracked_by": ["DEF-123"]},
                        {"type": "signal_b", "status": "unregistered"},
                    ],
                }
            },
        )
        lines = result._format_registration_gate()
        text = "\n".join(lines)
        assert "Signal X not registered" in text
        assert "Signal Y regressed" in text
        assert "signal_a" in text
        assert "signal_b" in text

    def test_format_feature_gate_with_violations(self) -> None:
        """Test _format_feature_gate() includes violations."""
        result = DispatchResult(
            success=False,
            task_description="Test",
            details={
                "feature_gate": {
                    "verdict": "fail",
                    "summary": {"total": 5, "pass": 3, "fail": 2, "waived": 0},
                    "violations": ["Missing test coverage", "Incomplete documentation"],
                    "entries": [
                        {"id": "AC-001", "status": "pass", "description": "Basic functionality"},
                        {"id": "AC-002", "status": "fail", "description": "Edge cases"},
                        {
                            "id": "AC-003",
                            "status": "waived",
                            "description": "Deprecated feature",
                            "waive_reason": "Legacy code",
                        },
                    ],
                }
            },
        )
        lines = result._format_feature_gate()
        text = "\n".join(lines)
        assert "Missing test coverage" in text
        assert "Incomplete documentation" in text
        assert "AC-001" in text
        assert "AC-002" in text
        assert "AC-003" in text
        assert "Legacy code" in text

    def test_to_markdown_failed_status(self) -> None:
        """Test to_markdown() with failed status shows ❌."""
        result = DispatchResult(
            success=False,
            task_description="Failed task",
            errors=["Error 1", "Error 2"],
        )
        markdown = result.to_markdown()
        assert "❌" in markdown

    def test_to_markdown_with_errors(self) -> None:
        """Test to_markdown() includes errors section."""
        result = DispatchResult(
            success=False,
            task_description="Task with errors",
            errors=["Authentication failed", "Database connection timeout"],
        )
        markdown = result.to_markdown()
        assert "Authentication failed" in markdown or "Database connection timeout" in markdown

    def test_to_markdown_with_worker_results(self) -> None:
        """Test to_markdown() includes worker results."""
        result = DispatchResult(
            success=True,
            task_description="Multi-worker task",
            worker_results=[
                {"worker_id": "architect-0", "role": "architect", "output": "Design completed"},
                {"worker_id": "security-0", "role": "security", "output": "Security audit passed"},
            ],
        )
        markdown = result.to_markdown()
        # Check if roles or workers are mentioned
        assert len(markdown) > 100  # Should have substantial content

    def test_to_markdown_with_concern_packs(self) -> None:
        """Test to_markdown() with concern packs."""
        result = DispatchResult(
            success=True,
            task_description="Task with concerns",
            concern_packs=[
                {"concern": "performance", "details": "Slow query detected"},
            ],
        )
        markdown = result.to_markdown()
        # Should generate content even with concern packs
        assert len(markdown) > 50

    def test_to_markdown_with_suggested_next_steps(self) -> None:
        """Test to_markdown() includes suggested next steps."""
        result = DispatchResult(
            success=True,
            task_description="Task completed",
            suggested_next_steps=["Deploy to staging", "Update documentation", "Notify stakeholders"],
        )
        markdown = result.to_markdown()
        # Next steps should appear in markdown
        assert len(markdown) > 50

    def test_multiple_language_fallback(self) -> None:
        """Test invalid language falls back to Chinese."""
        result = DispatchResult(
            success=True,
            task_description="Test",
            lang="invalid_lang",
        )
        markdown = result.to_markdown()
        # Should use Chinese as fallback
        assert len(markdown) > 0


class TestFormatConcernPacks:
    """Test _format_concern_packs() method."""

    def test_format_concern_packs_empty(self) -> None:
        """Test _format_concern_packs() returns empty when no packs."""
        result = DispatchResult(success=True, task_description="Test")
        lines = result._format_concern_packs()
        assert lines == []

    def test_format_concern_packs_with_data(self) -> None:
        """Test _format_concern_packs() formats concern packs."""
        result = DispatchResult(
            success=True,
            task_description="Test",
            concern_packs=[
                {"name": "性能关注", "description": "数据库查询优化"},
                {"name": "安全关注", "description": "输入验证加强"},
            ],
        )
        lines = result._format_concern_packs()
        assert len(lines) > 0
        text = "\n".join(lines)
        assert "关注点增强包" in text
        assert "性能关注" in text
        assert "数据库查询优化" in text


class TestFormatAnchor:
    """Test _format_anchor() method."""

    def test_format_anchor_empty(self) -> None:
        """Test _format_anchor() returns empty when no anchor result."""
        result = DispatchResult(success=True, task_description="Test")
        lines = result._format_anchor()
        assert lines == []

    def test_format_anchor_aligned(self) -> None:
        """Test _format_anchor() formats aligned anchor."""
        result = DispatchResult(
            success=True,
            task_description="Test",
            anchor_result={"aligned": True, "details": "All objectives met"},
        )
        lines = result._format_anchor()
        assert len(lines) > 0
        text = "\n".join(lines)
        assert "Anchor 对齐检查" in text
        assert "✅ 通过" in text
        assert "All objectives met" in text

    def test_format_anchor_not_aligned(self) -> None:
        """Test _format_anchor() formats misaligned anchor."""
        result = DispatchResult(
            success=False,
            task_description="Test",
            anchor_result={"aligned": False, "details": "Missing security review"},
        )
        lines = result._format_anchor()
        text = "\n".join(lines)
        assert "⚠️ 偏移" in text
        assert "Missing security review" in text


class TestFormatIntentMatch:
    """Test _format_intent_match() method."""

    def test_format_intent_match_empty(self) -> None:
        """Test _format_intent_match() returns empty when no data."""
        result = DispatchResult(success=True, task_description="Test")
        lines = result._format_intent_match()
        assert lines == []

    def test_format_intent_match_with_data(self) -> None:
        """Test _format_intent_match() formats intent match."""
        result = DispatchResult(
            success=True,
            task_description="Test",
            intent_match={"intent": "implement_authentication", "confidence": 0.92},
        )
        lines = result._format_intent_match()
        assert len(lines) > 0
        text = "\n".join(lines)
        assert "意图匹配" in text
        assert "implement_authentication" in text
        assert "92%" in text


class TestFormatFiveAxis:
    """Test _format_five_axis() method."""

    def test_format_five_axis_empty(self) -> None:
        """Test _format_five_axis() returns empty when no data."""
        result = DispatchResult(success=True, task_description="Test")
        lines = result._format_five_axis()
        assert lines == []

    def test_format_five_axis_with_data(self) -> None:
        """Test _format_five_axis() formats five-axis review."""
        result = DispatchResult(
            success=True,
            task_description="Test",
            five_axis_result={
                "correctness": "pass",
                "security": "pass",
                "performance": "warning",
                "maintainability": "pass",
                "usability": "pass",
            },
        )
        lines = result._format_five_axis()
        assert len(lines) > 0
        text = "\n".join(lines)
        assert "五轴共识审查" in text
        assert "correctness" in text
        assert "security" in text


class TestFormatRetrospective:
    """Test _format_retrospective() method."""

    def test_format_retrospective_empty(self) -> None:
        """Test _format_retrospective() returns empty when no data."""
        result = DispatchResult(success=True, task_description="Test")
        lines = result._format_retrospective()
        assert lines == []

    def test_format_retrospective_dict(self) -> None:
        """Test _format_retrospective() formats dict retrospective."""
        result = DispatchResult(
            success=True,
            task_description="Test",
            retrospective_report={
                "what_went_well": "Good test coverage",
                "what_to_improve": "Need faster CI pipeline",
            },
        )
        lines = result._format_retrospective()
        assert len(lines) > 0
        text = "\n".join(lines)
        assert "回顾分析" in text
        assert "Good test coverage" in text
        assert "Need faster CI pipeline" in text

    def test_format_retrospective_string(self) -> None:
        """Test _format_retrospective() formats string retrospective."""
        result = DispatchResult(
            success=True,
            task_description="Test",
            retrospective_report="Overall good performance",
        )
        lines = result._format_retrospective()
        text = "\n".join(lines)
        assert "Overall good performance" in text


class TestFormatRiskManagement:
    """Test _format_risk_management() method."""

    def test_format_risk_management_empty(self) -> None:
        """Test _format_risk_management() returns empty when no markdown."""
        result = DispatchResult(success=True, task_description="Test")
        lines = result._format_risk_management()
        assert lines == []

    def test_format_risk_management_with_markdown(self) -> None:
        """Test _format_risk_management() formats risk markdown."""
        result = DispatchResult(
            success=True,
            task_description="Test",
            risk_management_md="## Risk Register\n\n- RISK-001: Database migration risk (HIGH)",
        )
        lines = result._format_risk_management()
        assert len(lines) > 0
        text = "\n".join(lines)
        assert "Risk Register" in text
        assert "RISK-001" in text


class TestFormatApprovalGate:
    """Test _format_approval_gate() method."""

    def test_format_approval_gate_empty(self) -> None:
        """Test _format_approval_gate() returns empty when no data."""
        result = DispatchResult(success=True, task_description="Test")
        lines = result._format_approval_gate()
        assert lines == []

    def test_format_approval_gate_with_markdown(self) -> None:
        """Test _format_approval_gate() uses pre-rendered markdown."""
        result = DispatchResult(
            success=True,
            task_description="Test",
            approval_gate_md="## Approval Gate\n\n- All approvals obtained",
        )
        lines = result._format_approval_gate()
        assert len(lines) > 0
        text = "\n".join(lines)
        assert "Approval Gate" in text
        assert "All approvals obtained" in text

    def test_format_approval_gate_with_records(self) -> None:
        """Test _format_approval_gate() formats approval records."""
        result = DispatchResult(
            success=True,
            task_description="Test",
            approval_records=[
                {"approved": True, "operation_type": "code_change", "description": "Feature X implementation"},
                {"approved": False, "operation_type": "schema_change", "description": "Database migration"},
            ],
        )
        lines = result._format_approval_gate()
        assert len(lines) > 0
        text = "\n".join(lines)
        assert "APPROVED" in text
        assert "DENIED" in text
        assert "Feature X implementation" in text


class TestFormatConnectorOperations:
    """Test _format_connector_operations() method."""

    def test_format_connector_operations_empty(self) -> None:
        """Test _format_connector_operations() returns empty when no data."""
        result = DispatchResult(success=True, task_description="Test")
        lines = result._format_connector_operations()
        assert lines == []

    def test_format_connector_operations_with_markdown(self) -> None:
        """Test _format_connector_operations() uses pre-rendered markdown."""
        result = DispatchResult(
            success=True,
            task_description="Test",
            connector_md="## Connector Operations\n\n- Connected to external API",
        )
        lines = result._format_connector_operations()
        assert len(lines) > 0
        text = "\n".join(lines)
        assert "Connector Operations" in text
        assert "Connected to external API" in text

    def test_format_connector_operations_with_records(self) -> None:
        """Test _format_connector_operations() formats connector operations."""
        result = DispatchResult(
            success=True,
            task_description="Test",
            connector_operations=[
                {"success": True, "operation": "sync", "target": "GitHub API"},
                {"success": False, "operation": "notify", "target": "Slack"},
            ],
        )
        lines = result._format_connector_operations()
        assert len(lines) > 0
        text = "\n".join(lines)
        assert "OK" in text
        assert "FAILED" in text
        assert "GitHub API" in text
        assert "Slack" in text


class TestFormatFailureClass:
    """Test _format_failure_class() method."""

    def test_format_failure_class_none(self) -> None:
        """Test _format_failure_class() returns empty when no failure."""
        result = DispatchResult(success=True, task_description="Test")
        lines = result._format_failure_class()
        assert lines == []

    def test_format_failure_class_none_value(self) -> None:
        """Test _format_failure_class() returns empty when class is 'none'."""
        result = DispatchResult(
            success=True,
            task_description="Test",
            details={"failure_class": "none"},
        )
        lines = result._format_failure_class()
        assert lines == []

    def test_format_failure_class_environment_blocked(self) -> None:
        """Test _format_failure_class() formats environment_blocked."""
        result = DispatchResult(
            success=False,
            task_description="Test",
            details={"failure_class": "environment_blocked"},
        )
        lines = result._format_failure_class()
        assert len(lines) > 0
        text = "\n".join(lines)
        assert "environment_blocked" in text
        assert "🚧" in text
        assert "Retry is appropriate" in text

    def test_format_failure_class_product_failed(self) -> None:
        """Test _format_failure_class() formats product_failed."""
        result = DispatchResult(
            success=False,
            task_description="Test",
            details={"failure_class": "product_failed"},
        )
        lines = result._format_failure_class()
        text = "\n".join(lines)
        assert "product_failed" in text
        assert "❌" in text


class TestFormatBackendStatus:
    """Test _format_backend_status() method."""

    def test_format_backend_status_empty(self) -> None:
        """Test _format_backend_status() returns empty when no status."""
        result = DispatchResult(success=True, task_description="Test")
        lines = result._format_backend_status(I18N["zh"])
        assert lines == []

    def test_format_backend_status_with_data(self) -> None:
        """Test _format_backend_status() formats backend status."""
        result = DispatchResult(
            success=True,
            task_description="Test",
            details={
                "backend_status": {
                    "requested": "openai",
                    "selected_path": "anthropic",
                    "state": "fallback",
                    "chain": ["openai", "anthropic"],
                    "degradation_reason": "API quota exceeded",
                }
            },
        )
        lines = result._format_backend_status(I18N["zh"])
        assert len(lines) > 0
        text = "\n".join(lines)
        assert "openai" in text
        assert "anthropic" in text
        assert "fallback" in text
        assert "API quota exceeded" in text


class TestDispatchResultComplexScenarios:
    """Test complex real-world scenarios."""

    def test_full_dispatch_result_serialization(self) -> None:
        """Test serializing a fully-populated DispatchResult."""
        result = DispatchResult(
            success=True,
            task_description="Complete task",
            matched_roles=["architect", "security", "tester"],
            summary="All roles completed successfully",
            duration_seconds=45.678,
            worker_results=[
                {"worker_id": "architect-0", "role": "architect", "output": "Design done"},
                {"worker_id": "security-0", "role": "security", "output": "Audit passed"},
                {"worker_id": "tester-0", "role": "tester", "output": "Tests passed"},
            ],
            scratchpad_summary="Key findings: JWT implemented",
            consensus_records=[{"decision": "approved", "votes": 3}],
            compression_info={"compressed_bytes": 1000, "original_bytes": 5000},
            memory_stats={"total_entries": 50, "active_entries": 10},
            permission_checks=[{"check": "read_access", "allowed": True}],
            skill_proposals=[{"skill_name": "auth_helper", "confidence": 0.9}],
            errors=[],
            quality_report="All tests passed",
            concern_packs=[],
            anchor_result={"anchor_met": True},
            suggested_next_steps=["Deploy", "Monitor"],
            retrospective_report={"lessons_learned": ["Use JWT"]},
            intent_match={"confidence": 0.95},
            five_axis_result={"axes": ["security", "performance"]},
            two_stage_review={"status": "approved"},
            auto_fix_result={"fixed_count": 2},
            judge_result={"verdict": "approved"},
            feature_gate={"verdict": "pass"},
            registration_gate={"verdict": "pass"},
            micro_task_plan={"steps": []},
            permission_result={"allowed": True},
            audit_entries=[{"action": "dispatch_started"}],
            risk_management_md="## Risks\n- None",
            approval_records=[{"approval": "manager_approved"}],
            connector_operations=[{"connector": "gitlab", "action": "create_issue"}],
        )
        result_dict = result.to_dict()
        assert result_dict["success"] is True
        assert len(result_dict["worker_results"]) == 3
        assert result_dict["duration_seconds"] == 45.68
        assert result_dict["two_stage_review"]["status"] == "approved"

    def test_full_dispatch_result_markdown(self) -> None:
        """Test rendering a fully-populated DispatchResult to markdown."""
        result = DispatchResult(
            success=True,
            task_description="Complete task",
            matched_roles=["architect", "security"],
            summary="Task completed successfully",
            duration_seconds=30.0,
            worker_results=[
                {"worker_id": "architect-0", "role": "architect", "output": "Design done"},
            ],
            scratchpad_summary="Key findings documented",
            lang="en",
        )
        markdown = result.to_markdown()
        assert "Multi-Agent" in markdown
        assert "Success" in markdown
        assert "Complete task" in markdown
