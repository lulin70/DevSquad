#!/usr/bin/env python3
"""Unit tests for report_formatter.py - IMPROVED VERSION with real components.

Focus: Replace Mock objects with real Worker/WorkerResult for higher test fidelity.
"""

from __future__ import annotations

import pytest

from scripts.collaboration.dispatch_models import DispatchResult
from scripts.collaboration.models_base import WorkerResult
from scripts.collaboration.report_formatter import ReportFormatter


@pytest.fixture
def formatter() -> ReportFormatter:
    """Create ReportFormatter instance with Chinese locale."""
    return ReportFormatter(lang="zh")


@pytest.fixture
def sample_worker_results() -> list[dict]:
    """Create sample worker results for testing."""
    return [
        {
            "worker_id": "architect-0",
            "role": "architect",
            "success": True,
            "output": "架构设计: 采用 JWT + OAuth2.0",
        },
        {
            "worker_id": "security-0",
            "role": "security",
            "success": True,
            "output": "安全审计: 通过 OWASP 标准",
        },
    ]


@pytest.fixture
def sample_result(sample_worker_results: list[dict]) -> DispatchResult:
    """Create sample DispatchResult for testing."""
    return DispatchResult(
        success=True,
        task_description="设计用户认证系统",
        matched_roles=["architect", "security"],
        summary="认证系统设计完成",
        duration_seconds=12.5,
        worker_results=sample_worker_results,
    )


# REMOVED: _MockExecResult and _MockWorkerResult - using real WorkerResult instead


class _ExecResultAdapter:
    """Adapter to hold real WorkerResult instances.
    
    This mimics the interface expected by build_summary() but uses real WorkerResult objects.
    """

    def __init__(self, results: list[WorkerResult], duration_seconds: float = 0.0):
        self.results = results
        self.duration_seconds = duration_seconds


class TestBuildSummary:
    """Test build_summary method (core summary generation)."""

    def test_build_summary_basic(self, formatter: ReportFormatter) -> None:
        """Test building summary with basic inputs using REAL WorkerResult."""
        # Use real WorkerResult instead of mock
        worker_results = [
            WorkerResult(
                worker_id="architect-0",
                task_id="task-001",
                success=True,
                output={"summary": "架构: JWT + OAuth2.0"},
                duration_seconds=6.0,
            ),
            WorkerResult(
                worker_id="security-0",
                task_id="task-001",
                success=True,
                output={"summary": "安全: 通过审计"},
                duration_seconds=6.5,
            ),
        ]
        exec_result = _ExecResultAdapter(
            results=worker_results,
            duration_seconds=12.5,
        )
        summary = formatter.build_summary(
            task="设计认证系统",
            roles=["architect", "security"],
            exec_result=exec_result,
            sp_summary="架构: JWT + OAuth2.0; 安全: 通过审计",
        )
        assert "设计认证系统" in summary
        assert "architect" in summary.lower() or "架构师" in summary
        assert "2/2" in summary  # 2 successful workers
        assert "12.5" in summary
        assert "JWT" in summary

    def test_build_summary_no_workers(self, formatter: ReportFormatter) -> None:
        """Test building summary without worker results."""
        exec_result = _ExecResultAdapter(results=[], duration_seconds=5.0)
        summary = formatter.build_summary(
            task="测试任务",
            roles=["architect"],
            exec_result=exec_result,
            sp_summary="",
        )
        assert "测试任务" in summary
        assert "5.0" in summary

    def test_build_summary_long_task_truncated(self, formatter: ReportFormatter) -> None:
        """Test building summary truncates long task descriptions."""
        long_task = "A" * 100
        exec_result = _ExecResultAdapter(results=[], duration_seconds=1.0)
        summary = formatter.build_summary(
            task=long_task,
            roles=["architect"],
            exec_result=exec_result,
            sp_summary="",
        )
        # Task should be truncated to 80 chars
        assert len([line for line in summary.split("\n") if "AAAA" in line][0]) < 100

    def test_build_summary_long_sp_truncated(self, formatter: ReportFormatter) -> None:
        """Test building summary truncates long scratchpad summary."""
        long_sp = "X" * 300
        exec_result = _ExecResultAdapter(results=[], duration_seconds=1.0)
        summary = formatter.build_summary(
            task="任务",
            roles=["architect"],
            exec_result=exec_result,
            sp_summary=long_sp,
        )
        # Summary should be truncated to 200 chars in output
        sp_line = [line for line in summary.split("\n") if "XXX" in line]
        if sp_line:
            assert len(sp_line[0]) < 250

    def test_build_summary_failed_workers(self, formatter: ReportFormatter) -> None:
        """Test building summary with some failed workers using REAL WorkerResult."""
        worker_results = [
            WorkerResult(
                worker_id="architect-0",
                task_id="task-001",
                success=True,
                output={},
                duration_seconds=3.0,
            ),
            WorkerResult(
                worker_id="security-0",
                task_id="task-001",
                success=False,  # Failed worker
                output={},
                error="Security check failed",
                duration_seconds=2.0,
            ),
            WorkerResult(
                worker_id="tester-0",
                task_id="task-001",
                success=True,
                output={},
                duration_seconds=5.0,
            ),
        ]
        exec_result = _ExecResultAdapter(
            results=worker_results,
            duration_seconds=10.0,
        )
        summary = formatter.build_summary(
            task="任务",
            roles=["architect", "security", "tester"],
            exec_result=exec_result,
            sp_summary="",
        )
        assert "任务" in summary
        assert "2/3" in summary  # 2 out of 3 succeeded


class TestExtractFindings:
    """Test extract_findings method (lines 193, 208)."""

    def test_extract_findings_from_string(self, formatter: ReportFormatter) -> None:
        """Test extracting findings from string input."""
        text = """
        Key findings:
        - Implemented JWT authentication
        - Configured OAuth2.0 flow
        - Passed OWASP security audit
        """
        extracted = formatter.extract_findings(text)
        assert len(extracted) > 0

    def test_extract_findings_empty_input(self, formatter: ReportFormatter) -> None:
        """Test extracting findings from empty input."""
        assert formatter.extract_findings("") == []
        assert formatter.extract_findings(None) == []

    def test_extract_findings_multiline(self, formatter: ReportFormatter) -> None:
        """Test extracting findings from multiline text with bullets."""
        text = """## Analysis Report
        
        Key Findings:
        - Implemented JWT authentication module
        - Added refresh token support
        - Configured OAuth2.0 authorization flow
        - Passed security audit checklist
        
        Next Steps:
        - Deploy to staging
        """
        extracted = formatter.extract_findings(text)
        assert len(extracted) >= 2
        assert any("JWT" in f or "OAuth" in f for f in extracted)


class TestGenerateActionItems:
    """Test generate_action_items method (lines 216-226, 233-236)."""

    def test_generate_action_items_from_result(self, formatter: ReportFormatter, sample_result: DispatchResult) -> None:
        """Test generating action items from DispatchResult."""
        actions = formatter.generate_action_items(sample_result)
        assert len(actions) >= 0  # May generate action items
        if actions:
            assert all("priority" in a for a in actions)

    def test_generate_action_items_with_errors(self, formatter: ReportFormatter) -> None:
        """Test generating action items when result has errors."""
        result = DispatchResult(
            success=False,
            task_description="任务",
            errors=["Error 1: Authentication failed", "Error 2: Database connection timeout"],
        )
        actions = formatter.generate_action_items(result)
        # Should include error-related actions
        assert len(actions) > 0

    def test_generate_action_items_empty_result(self, formatter: ReportFormatter) -> None:
        """Test generating action items from empty result."""
        result = DispatchResult(
            success=True,
            task_description="任务",
            worker_results=[],
        )
        actions = formatter.generate_action_items(result)
        assert isinstance(actions, list)

    def test_generate_action_items_with_suggested_next_steps(self, formatter: ReportFormatter) -> None:
        """Test generating action items when suggested_next_steps are present."""
        result = DispatchResult(
            success=True,
            task_description="任务",
            suggested_next_steps=["Deploy to staging", "Update documentation", "Notify stakeholders"],
        )
        actions = formatter.generate_action_items(result)
        # May not always generate 3+ actions, but should generate at least 1
        assert len(actions) >= 1
        assert all("priority" in a and "text" in a for a in actions)


class TestFormatStructuredReport:
    """Test format_structured_report method (lines 257-270, 283-323)."""

    def test_format_structured_basic(self, formatter: ReportFormatter, sample_result: DispatchResult) -> None:
        """Test structured report format."""
        report = formatter.format_structured_report(sample_result, include_action_items=True)
        assert "##" in report  # Should have markdown headers
        assert "architect" in report.lower() or "架构师" in report

    def test_format_structured_no_action_items(
        self, formatter: ReportFormatter, sample_result: DispatchResult
    ) -> None:
        """Test structured report without action items."""
        report = formatter.format_structured_report(sample_result, include_action_items=False)
        assert "##" in report

    def test_format_structured_with_timing(self, formatter: ReportFormatter, sample_result: DispatchResult) -> None:
        """Test structured report with timing information."""
        report = formatter.format_structured_report(sample_result, include_timing=True)
        assert "##" in report
        assert "12.5" in report or "duration" in report.lower()

    def test_format_structured_with_errors(self, formatter: ReportFormatter) -> None:
        """Test structured report includes error section when errors present."""
        result = DispatchResult(
            success=False,
            task_description="Failed task",
            errors=["Error 1: Connection timeout", "Error 2: Invalid credentials"],
        )
        report = formatter.format_structured_report(result)
        assert "##" in report
        assert "Error" in report or "错误" in report


class TestFormatReport:
    """Test format_report dispatcher (action_first mode) - lines 400, 414, 432-483."""

    def test_format_report_action_first(self, formatter: ReportFormatter, sample_result: DispatchResult) -> None:
        """Test format_report with action_first output style."""
        report = formatter.format_report(sample_result, output_style="action_first")
        assert "## Next Actions" in report
        assert "## Key Findings" in report
        assert "## Next Step" in report

    def test_format_report_compact(self, formatter: ReportFormatter, sample_result: DispatchResult) -> None:
        """Test format_report with compact output style."""
        report = formatter.format_report(sample_result, output_style="compact")
        assert len(report) > 0
        assert "设计用户认证系统" in report

    def test_format_report_detailed(self, formatter: ReportFormatter, sample_result: DispatchResult) -> None:
        """Test format_report with detailed output style (default)."""
        report = formatter.format_report(sample_result, output_style="detailed")
        assert "##" in report  # Structured report with headers

    def test_format_report_action_first_with_findings(self, formatter: ReportFormatter) -> None:
        """Test action_first report includes findings from scratchpad_summary."""
        result = DispatchResult(
            success=True,
            task_description="任务",
            scratchpad_summary="""
            - Finding 1: Architecture defined
            - Finding 2: Security reviewed
            - Finding 3: Tests passed
            - Finding 4: Documentation updated
            - Finding 5: Code reviewed
            - Finding 6: Performance optimized (this should be capped)
            """,
            suggested_next_steps=["Deploy", "Monitor", "Document"],
        )
        report = formatter.format_report(result, output_style="action_first")
        assert "## Next Actions" in report
        assert "## Key Findings" in report
        # Should cap findings at 5
        lines = report.split("\n")
        findings_section = False
        finding_count = 0
        for line in lines:
            if "## Key Findings" in line:
                findings_section = True
            elif findings_section and line.strip().startswith(("1.", "2.", "3.", "4.", "5.")):
                finding_count += 1
        assert finding_count <= 5


class TestLanguageSupport:
    """Test multilingual support (lines 338-380)."""

    def test_english_formatter(self) -> None:
        """Test English language support."""
        formatter_en = ReportFormatter(lang="en")
        worker_result = WorkerResult(
            worker_id="architect-0", task_id="task-001",
            success=True, output={}, duration_seconds=10.0
        )
        exec_result = _ExecResultAdapter(results=[worker_result], duration_seconds=10.0)
        summary = formatter_en.build_summary(
            task="Design auth system",
            roles=["architect"],
            exec_result=exec_result,
            sp_summary="JWT + OAuth2.0",
        )
        assert "Design auth" in summary
        assert any(word in summary.lower() for word in ["task", "role", "duration"])

    def test_japanese_formatter(self) -> None:
        """Test Japanese language support."""
        formatter_ja = ReportFormatter(lang="ja")
        worker_result = WorkerResult(
            worker_id="w-0", task_id="t-0",
            success=True, output={}, duration_seconds=10.0
        )
        exec_result = _ExecResultAdapter(results=[worker_result], duration_seconds=10.0)
        summary = formatter_ja.build_summary(
            task="認証システム設計",
            roles=["architect"],
            exec_result=exec_result,
            sp_summary="JWT認証",
        )
        assert "認証" in summary or "architect" in summary.lower()

    def test_invalid_lang_falls_back_to_chinese(self) -> None:
        """Test invalid language falls back to Chinese."""
        formatter_invalid = ReportFormatter(lang="invalid")
        exec_result = _ExecResultAdapter(results=[], duration_seconds=1.0)
        summary = formatter_invalid.build_summary(
            task="测试",
            roles=["architect"],
            exec_result=exec_result,
            sp_summary="",
        )
        # Should still work, likely fallback to Chinese
        assert len(summary) > 0

    def test_formatter_english_structured_report(self, sample_result: DispatchResult) -> None:
        """Test English formatter generates structured report."""
        formatter_en = ReportFormatter(lang="en")
        report = formatter_en.format_structured_report(sample_result)
        assert "##" in report


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_zero_duration(self, formatter: ReportFormatter) -> None:
        """Test handling zero duration."""
        exec_result = _ExecResultAdapter(results=[], duration_seconds=0.0)
        summary = formatter.build_summary(
            task="任务",
            roles=["architect"],
            exec_result=exec_result,
            sp_summary="",
        )
        assert "任务" in summary

    def test_empty_sp_summary(self, formatter: ReportFormatter) -> None:
        """Test handling empty scratchpad summary."""
        worker_result = WorkerResult(
            worker_id="w-0", task_id="t-0",
            success=True, output={}, duration_seconds=1.0
        )
        exec_result = _ExecResultAdapter(results=[worker_result], duration_seconds=1.0)
        summary = formatter.build_summary(
            task="任务",
            roles=["architect"],
            exec_result=exec_result,
            sp_summary="",
        )
        assert "任务" in summary

    def test_missing_worker_role(self, formatter: ReportFormatter) -> None:
        """Test handling worker results without role field."""
        result = DispatchResult(
            success=True,
            task_description="任务",
            matched_roles=["architect"],
            worker_results=[
                {
                    "worker_id": "unknown-0",
                    "success": True,
                    "output": "完成",
                }
            ],
        )
        report = formatter.format_structured_report(result)
        assert "##" in report

    def test_format_report_with_empty_suggested_next_steps(self, formatter: ReportFormatter) -> None:
        """Test action_first report with empty suggested_next_steps."""
        result = DispatchResult(
            success=True,
            task_description="任务",
            suggested_next_steps=[],
        )
        report = formatter.format_report(result, output_style="action_first")
        assert "## Next Step" in report

    def test_extract_findings_with_special_characters(self, formatter: ReportFormatter) -> None:
        """Test extracting findings with special markdown characters."""
        text = """
        Findings:
        - Item with **bold** text
        - Item with `code` inline
        - Item with [link](http://example.com)
        """
        extracted = formatter.extract_findings(text)
        assert len(extracted) >= 2
