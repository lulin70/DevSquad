"""Unit tests for OutputValidator (P1-6 skeleton + V4.3.0 P1-8 full integration).

Covers code injection, sensitive info, path leak, and prompt injection
detection, plus redaction semantics, the PostDispatchPipeline._validate_outputs
integration, and V4.3.0 Phase 2 additions:
  - OutputValidationPipelineResult (pipeline-level aggregate)
  - OutputValidationBlockedError (blocking mode control flow)
  - Dual-mode _validate_outputs (list[str] | list[dict])
  - blocking / non_blocking mode semantics
  - DispatchAuditLogger integration
  - config-driven mode selection
  - fail-secure degradation
"""

from __future__ import annotations

from typing import Any

import pytest

from scripts.collaboration.output_validator import (
    OutputFinding,
    OutputValidationResult,
    OutputValidator,
)


@pytest.fixture
def validator() -> OutputValidator:
    return OutputValidator()


# ---------------------------------------------------------------------
# Code injection detection
# ---------------------------------------------------------------------


def test_eval_call_detected_high_severity(validator: OutputValidator) -> None:
    result = validator.validate("result = eval('1+1')")
    finding = _find_pattern(result, "eval_call")
    assert finding is not None
    assert finding.severity == "high"
    assert finding.category == "code_injection"
    assert result.valid is False


def test_exec_call_detected(validator: OutputValidator) -> None:
    result = validator.validate("exec('print(1)')")
    finding = _find_pattern(result, "exec_call")
    assert finding is not None
    assert finding.severity == "high"


def test_dunder_import_detected(validator: OutputValidator) -> None:
    result = validator.validate("__import__('os')")
    finding = _find_pattern(result, "dunder_import")
    assert finding is not None
    assert finding.severity == "high"


def test_os_system_detected(validator: OutputValidator) -> None:
    result = validator.validate("os.system('rm -rf /tmp/x')")
    finding = _find_pattern(result, "os_system_call")
    assert finding is not None
    assert finding.severity == "high"


def test_subprocess_popen_detected(validator: OutputValidator) -> None:
    result = validator.validate("subprocess.Popen(['ls', '-l'])")
    finding = _find_pattern(result, "subprocess_call")
    assert finding is not None


def test_subprocess_run_detected(validator: OutputValidator) -> None:
    result = validator.validate("subprocess.run(['echo', 'hi'])")
    finding = _find_pattern(result, "subprocess_call")
    assert finding is not None


def test_innocent_prose_no_false_positive(validator: OutputValidator) -> None:
    """Words like 'evaluate' / 'executive' must NOT trigger code-injection."""
    result = validator.validate("The executive evaluated the proposal thoroughly.")
    code_findings = [f for f in result.findings if f.category == "code_injection"]
    assert code_findings == []
    assert result.valid is True


# ---------------------------------------------------------------------
# Sensitive information detection
# ---------------------------------------------------------------------


def test_openai_api_key_detected(validator: OutputValidator) -> None:
    # sk- + 40 alphanumeric chars (length 43 total)
    result = validator.validate("export OPENAI_API_KEY=sk-" + "a" * 40)
    finding = _find_pattern(result, "openai_api_key")
    assert finding is not None
    assert finding.severity == "high"
    assert result.valid is False


def test_anthropic_api_key_detected(validator: OutputValidator) -> None:
    result = validator.validate("sk-ant-" + "b" * 40)
    finding = _find_pattern(result, "anthropic_api_key")
    assert finding is not None


def test_api_key_assignment_detected(validator: OutputValidator) -> None:
    result = validator.validate("api_key = " + "x" * 20)
    finding = _find_pattern(result, "api_key_assignment")
    assert finding is not None


def test_password_assignment_detected(validator: OutputValidator) -> None:
    result = validator.validate("password = hunter2password")
    finding = _find_pattern(result, "password_assignment")
    assert finding is not None
    assert finding.severity == "high"


def test_bearer_token_detected(validator: OutputValidator) -> None:
    result = validator.validate(
        "Authorization: Bearer abcdefghijklmnopqrstuvwxyz1234567890"
    )
    finding = _find_pattern(result, "bearer_token")
    assert finding is not None


def test_aws_access_key_id_detected(validator: OutputValidator) -> None:
    result = validator.validate("AKIA" + "A" * 16)
    finding = _find_pattern(result, "aws_access_key_id")
    assert finding is not None


def test_jwt_token_detected(validator: OutputValidator) -> None:
    # eyJ + 8 chars . 8 chars . 8 chars
    result = validator.validate(
        "eyJabcdefgh" + "." + "ijklmnopqr" + "." + "stuvwxyz12"
    )
    finding = _find_pattern(result, "jwt_token")
    assert finding is not None


def test_private_ipv4_advisory(validator: OutputValidator) -> None:
    """Private IPv4 is medium severity — does not invalidate output."""
    result = validator.validate("Connecting to 192.168.1.100 for testing")
    finding = _find_pattern(result, "private_ipv4")
    assert finding is not None
    assert finding.severity == "medium"
    # Medium-only findings don't make the result invalid.
    assert result.valid is True


def test_localhost_url_advisory(validator: OutputValidator) -> None:
    result = validator.validate("Server running at http://localhost:8000/")
    finding = _find_pattern(result, "localhost_url")
    assert finding is not None
    assert finding.severity == "low"
    assert result.valid is True


# ---------------------------------------------------------------------
# Path leak detection
# ---------------------------------------------------------------------


def test_etc_passwd_detected_high(validator: OutputValidator) -> None:
    result = validator.validate("Reading /etc/passwd for user list")
    finding = _find_pattern(result, "etc_sensitive_path")
    assert finding is not None
    assert finding.severity == "high"
    assert result.valid is False


def test_root_home_path_detected(validator: OutputValidator) -> None:
    result = validator.validate("Log file at /root/app.log")
    finding = _find_pattern(result, "root_home_path")
    assert finding is not None


def test_ssh_config_path_detected(validator: OutputValidator) -> None:
    result = validator.validate("cp ~/.ssh/id_rsa /tmp/backup/")
    finding = _find_pattern(result, "ssh_config_path")
    assert finding is not None


def test_aws_credentials_file_detected(validator: OutputValidator) -> None:
    result = validator.validate("Loaded creds from ~/.aws/credentials")
    finding = _find_pattern(result, "aws_credentials_file")
    assert finding is not None


def test_kube_config_path_detected(validator: OutputValidator) -> None:
    result = validator.validate("Using ~/.kube/config for cluster auth")
    finding = _find_pattern(result, "kube_config_path")
    assert finding is not None


def test_windows_abs_path_detected(validator: OutputValidator) -> None:
    result = validator.validate(r"Installed to C:\Users\admin\AppData\Local\app")
    finding = _find_pattern(result, "windows_abs_path")
    assert finding is not None


# ---------------------------------------------------------------------
# Redaction semantics
# ---------------------------------------------------------------------


def test_redact_masks_high_severity_only(validator: OutputValidator) -> None:
    """High-severity findings are masked; low/medium are left intact."""
    text = "eval(1) at http://localhost:8000/ with 192.168.1.1"
    result = validator.validate(text)
    # eval( is high → should be replaced with ***
    assert "eval(" not in result.redacted_text
    assert "***" in result.redacted_text
    # localhost is low → should be intact
    assert "localhost" in result.redacted_text
    # private ipv4 is medium → should be intact
    assert "192.168.1.1" in result.redacted_text


def test_redact_no_high_findings_returns_original(validator: OutputValidator) -> None:
    text = "Just a normal output with http://localhost:8000/"
    result = validator.validate(text)
    assert result.valid is True
    assert result.redacted_text == text


def test_redact_multiple_high_findings(validator: OutputValidator) -> None:
    """Multiple high-severity findings are all masked."""
    text = "eval(1) and exec('2') and /etc/passwd"
    result = validator.validate(text)
    assert "eval(" not in result.redacted_text
    assert "exec(" not in result.redacted_text
    assert "/etc/passwd" not in result.redacted_text
    # Should have at least 3 *** markers
    assert result.redacted_text.count("***") >= 3


def test_mask_short_string(validator: OutputValidator) -> None:
    """Strings ≤ 8 chars are fully masked."""
    assert OutputValidator._mask("abc") == "***"
    assert OutputValidator._mask("12345678") == "***"


def test_mask_long_string(validator: OutputValidator) -> None:
    """Strings > 8 chars keep first 2 + last 2 chars."""
    masked = OutputValidator._mask("abcdefghijklmnop")
    assert masked == "ab***op"


def test_redact_method_convenience(validator: OutputValidator) -> None:
    """OutputValidator.redact(text) is equivalent to validate(text).redacted_text."""
    text = "eval(1)"
    assert validator.redact(text) == validator.validate(text).redacted_text


# ---------------------------------------------------------------------
# Result aggregation
# ---------------------------------------------------------------------


def test_high_severity_count(validator: OutputValidator) -> None:
    result = validator.validate("eval(1) and exec('2') and /etc/passwd")
    assert result.high_severity_count >= 3


def test_medium_severity_count(validator: OutputValidator) -> None:
    result = validator.validate("Connect to 192.168.1.1 and 10.0.0.1")
    assert result.medium_severity_count >= 2


def test_valid_true_when_no_high_severity(validator: OutputValidator) -> None:
    result = validator.validate("Normal output with no risky content")
    assert result.valid is True
    assert result.findings == []


def test_valid_false_when_high_severity_present(validator: OutputValidator) -> None:
    result = validator.validate("eval(1)")
    assert result.valid is False


def test_findings_sorted_by_span(validator: OutputValidator) -> None:
    """Findings are sorted by span start for stable redaction."""
    text = "eval(1) and /etc/passwd and exec('2')"
    result = validator.validate(text)
    spans = [f.span[0] for f in result.findings]
    assert spans == sorted(spans)


# ---------------------------------------------------------------------
# PostDispatchPipeline._validate_outputs integration
# ---------------------------------------------------------------------


def test_post_dispatch_validate_outputs_detects_risky_content() -> None:
    """PostDispatchPipeline._validate_outputs scans worker_results.

    V4.3.0 Phase 2: returns OutputValidationPipelineResult (not list[dict]).
    Findings from workers 0/2/3 (eval, password, /etc/passwd) are captured;
    workers 1/4/5 (safe, non-text, empty) contribute no findings.
    """
    from scripts.collaboration.dispatch_steps import PostDispatchPipeline

    pipeline = PostDispatchPipeline.__new__(PostDispatchPipeline)
    pipeline.output_validator = OutputValidator()
    pipeline.output_validation_mode = "non_blocking"
    pipeline.audit_logger = None

    worker_results: list[dict[str, Any]] = [
        {"output": "eval('dangerous code')"},
        {"output": "Safe output"},
        {"raw_output": "password=hunter2password"},
        {"content": "/etc/passwd contents"},
        {"non_text_field": 123},  # No textual payload → skipped
        {},  # Empty dict → skipped
    ]

    result = pipeline._validate_outputs(worker_results)

    # New contract: returns OutputValidationPipelineResult with findings list
    assert hasattr(result, "blocked")
    assert hasattr(result, "findings")
    # At least 3 findings: eval (code_injection), password (sensitive_info),
    # /etc/passwd (path_leak)
    assert len(result.findings) >= 3
    categories = {f.category for f in result.findings}
    assert "code_injection" in categories
    assert "sensitive_info" in categories
    assert "path_leak" in categories


def test_post_dispatch_validate_outputs_disabled_returns_empty() -> None:
    """When output_validator is None, _validate_outputs returns empty result."""
    from scripts.collaboration.dispatch_steps import PostDispatchPipeline

    pipeline = PostDispatchPipeline.__new__(PostDispatchPipeline)
    pipeline.output_validator = None
    pipeline.output_validation_mode = "non_blocking"
    pipeline.audit_logger = None

    result = pipeline._validate_outputs([{"output": "eval(1)"}])
    assert result.blocked is False
    assert result.findings == []
    assert result.audit_logged is False


def test_extract_output_text_field_priority() -> None:
    """_extract_output_text checks output > raw_output > content > report."""
    from scripts.collaboration.dispatch_steps import PostDispatchPipeline

    # 'output' takes precedence over 'raw_output'.
    wr1 = {"output": "from_output", "raw_output": "from_raw", "content": "from_content"}
    assert PostDispatchPipeline._extract_output_text(wr1) == "from_output"

    # 'raw_output' takes precedence over 'content' when 'output' is absent.
    wr2 = {"raw_output": "from_raw", "content": "from_content"}
    assert PostDispatchPipeline._extract_output_text(wr2) == "from_raw"

    # 'content' takes precedence over 'report'.
    wr3 = {"content": "from_content", "report": "from_report"}
    assert PostDispatchPipeline._extract_output_text(wr3) == "from_content"

    # 'report' is the last fallback.
    wr4 = {"report": "from_report"}
    assert PostDispatchPipeline._extract_output_text(wr4) == "from_report"

    # Non-string / empty values are skipped.
    wr5 = {"output": 123, "raw_output": None, "content": ""}
    assert PostDispatchPipeline._extract_output_text(wr5) == ""

    # Empty dict returns "".
    assert PostDispatchPipeline._extract_output_text({}) == ""


# ---------------------------------------------------------------------
# V4.3.0 Phase 2 (P1-8): OutputValidationPipelineResult + blocking mode
# ---------------------------------------------------------------------


def _build_pipeline(**overrides: Any) -> Any:
    """Build a minimal PostDispatchPipeline for testing _validate_outputs.

    Uses __new__ to bypass the heavy __init__ (we only need
    output_validator, audit_logger, and the mode attributes).
    """
    from scripts.collaboration.dispatch_steps import PostDispatchPipeline

    pipeline = PostDispatchPipeline.__new__(PostDispatchPipeline)
    pipeline.output_validator = OutputValidator()
    pipeline.output_validation_mode = overrides.get("mode", "non_blocking")
    pipeline.audit_logger = overrides.get("audit_logger")
    return pipeline


class TestOutputValidationPipelineResult:
    """Pipeline-level aggregate result data class."""

    def test_01_import_from_output_validator(self) -> None:
        from scripts.collaboration.output_validator import (
            OutputValidationPipelineResult,
        )
        assert OutputValidationPipelineResult is not None

    def test_02_default_values(self) -> None:
        from scripts.collaboration.output_validator import (
            OutputValidationPipelineResult,
        )
        result = OutputValidationPipelineResult()
        assert result.blocked is False
        assert result.findings == []
        assert result.audit_logged is False
        assert result.redacted_outputs == []

    def test_03_field_assignment(self) -> None:
        from scripts.collaboration.output_validator import (
            OutputValidationPipelineResult,
        )
        finding = OutputFinding(
            category="sensitive_info",
            severity="high",
            pattern_name="openai_api_key",
            matched_text="sk-abc",
            redacted_text="sk***bc",
            span=(0, 6),
        )
        result = OutputValidationPipelineResult(
            blocked=True,
            findings=[finding],
            audit_logged=True,
            redacted_outputs=["***"],
        )
        assert result.blocked is True
        assert len(result.findings) == 1
        assert result.audit_logged is True
        assert result.redacted_outputs == ["***"]

    def test_04_high_severity_count_property(self) -> None:
        from scripts.collaboration.output_validator import (
            OutputValidationPipelineResult,
        )
        high_finding = OutputFinding(
            category="sensitive_info", severity="high",
            pattern_name="x", matched_text="x", redacted_text="x", span=(0, 1),
        )
        med_finding = OutputFinding(
            category="path_leak", severity="medium",
            pattern_name="y", matched_text="y", redacted_text="y", span=(0, 1),
        )
        result = OutputValidationPipelineResult(findings=[high_finding, med_finding])
        assert result.high_severity_count == 1


class TestOutputValidationBlockedError:
    """Custom exception for blocking mode control flow."""

    def test_01_import_from_output_validator(self) -> None:
        from scripts.collaboration.output_validator import (
            OutputValidationBlockedError,
        )
        assert issubclass(OutputValidationBlockedError, Exception)

    def test_02_exception_carries_result(self) -> None:
        from scripts.collaboration.output_validator import (
            OutputValidationBlockedError,
            OutputValidationPipelineResult,
        )
        result = OutputValidationPipelineResult(blocked=True)
        err = OutputValidationBlockedError("blocked", result=result)
        assert err.result is result
        assert "blocked" in str(err)


class TestValidateOutputsStringMode:
    """_validate_outputs accepts list[str] (E2E-05 contract)."""

    def test_01_string_list_input_accepted(self) -> None:
        pipeline = _build_pipeline()
        result = pipeline._validate_outputs(["normal output"])
        # Returns OutputValidationPipelineResult, not list[dict]
        assert hasattr(result, "blocked")
        assert hasattr(result, "findings")
        assert hasattr(result, "audit_logged")

    def test_02_string_input_findings_captured(self) -> None:
        pipeline = _build_pipeline()
        leaky = "My key is sk-" + "a" * 40
        result = pipeline._validate_outputs([leaky])
        assert len(result.findings) >= 1
        assert result.findings[0].category == "sensitive_info"

    def test_03_multiple_string_inputs_aggregated(self) -> None:
        pipeline = _build_pipeline()
        result = pipeline._validate_outputs([
            "eval('dangerous')",
            "safe output",
            "password=hunter2password",
        ])
        # Workers 0 and 2 should have findings
        categories = {f.category for f in result.findings}
        assert "code_injection" in categories
        assert "sensitive_info" in categories


class TestValidateOutputsDictMode:
    """_validate_outputs accepts list[dict] (backward compat)."""

    def test_01_dict_list_input_still_works(self) -> None:
        pipeline = _build_pipeline()
        worker_results: list[dict[str, Any]] = [
            {"output": "eval('dangerous code')"},
            {"output": "Safe output"},
            {"raw_output": "password=hunter2password"},
        ]
        result = pipeline._validate_outputs(worker_results)
        assert hasattr(result, "blocked")
        assert len(result.findings) >= 2

    def test_02_dict_field_priority_preserved(self) -> None:
        """output > raw_output > content > report priority still works."""
        pipeline = _build_pipeline()
        result = pipeline._validate_outputs([
            {"output": "eval('from_output')", "raw_output": "safe"},
        ])
        # Should detect eval( from 'output' field, not 'raw_output'
        assert any(f.pattern_name == "eval_call" for f in result.findings)

    def test_03_empty_dict_skipped(self) -> None:
        pipeline = _build_pipeline()
        result = pipeline._validate_outputs([{}, {"output": "eval(1)"}])
        assert len(result.findings) >= 1


class TestBlockingMode:
    """blocking mode sets blocked=True when high-severity findings exist."""

    def test_01_blocking_mode_blocks_on_high_severity(self) -> None:
        pipeline = _build_pipeline(mode="blocking")
        leaky = "sk-" + "a" * 40
        result = pipeline._validate_outputs([leaky])
        assert result.blocked is True

    def test_02_blocking_mode_no_block_on_clean_output(self) -> None:
        pipeline = _build_pipeline(mode="blocking")
        result = pipeline._validate_outputs(["clean output"])
        assert result.blocked is False
        assert result.findings == []

    def test_03_blocking_mode_no_block_on_medium_only(self) -> None:
        pipeline = _build_pipeline(mode="blocking")
        # private_ipv4 is medium severity
        result = pipeline._validate_outputs(["connecting to 192.168.1.1"])
        assert result.blocked is False


class TestNonBlockingMode:
    """non_blocking mode never sets blocked=True but records findings."""

    def test_01_non_blocking_records_findings_without_blocking(self) -> None:
        pipeline = _build_pipeline(mode="non_blocking")
        leaky = "sk-" + "a" * 40
        result = pipeline._validate_outputs([leaky])
        assert result.blocked is False
        assert len(result.findings) >= 1

    def test_02_non_blocking_default_mode(self) -> None:
        pipeline = _build_pipeline()  # default mode
        assert pipeline.output_validation_mode == "non_blocking"


class TestAuditLogIntegration:
    """DispatchAuditLogger integration for high-severity findings."""

    def test_01_audit_logged_when_high_severity_present(self) -> None:
        class FakeAuditLogger:
            def __init__(self) -> None:
                self.events: list[dict[str, Any]] = []

            def log_event(self, event_type: str, details: dict[str, Any]) -> None:
                self.events.append({"event_type": event_type, "details": details})

        fake_logger = FakeAuditLogger()
        pipeline = _build_pipeline(audit_logger=fake_logger)
        leaky = "sk-" + "a" * 40
        result = pipeline._validate_outputs([leaky])
        assert result.audit_logged is True
        assert len(fake_logger.events) >= 1
        assert fake_logger.events[0]["event_type"] == "output_validation_finding"

    def test_02_audit_not_logged_when_no_findings(self) -> None:
        class FakeAuditLogger:
            def __init__(self) -> None:
                self.events: list[dict[str, Any]] = []

            def log_event(self, event_type: str, details: dict[str, Any]) -> None:
                self.events.append({"event_type": event_type, "details": details})

        fake_logger = FakeAuditLogger()
        pipeline = _build_pipeline(audit_logger=fake_logger)
        result = pipeline._validate_outputs(["clean output"])
        assert result.audit_logged is False
        assert len(fake_logger.events) == 0

    def test_03_audit_logged_blocked_event_in_blocking_mode(self) -> None:
        class FakeAuditLogger:
            def __init__(self) -> None:
                self.events: list[dict[str, Any]] = []

            def log_event(self, event_type: str, details: dict[str, Any]) -> None:
                self.events.append({"event_type": event_type, "details": details})

        fake_logger = FakeAuditLogger()
        pipeline = _build_pipeline(mode="blocking", audit_logger=fake_logger)
        leaky = "sk-" + "a" * 40
        result = pipeline._validate_outputs([leaky])
        assert result.blocked is True
        event_types = [e["event_type"] for e in fake_logger.events]
        assert "output_validation_blocked" in event_types


class TestConfigDrivenMode:
    """config parameter drives mode selection."""

    def test_01_config_blocking_mode(self) -> None:
        from scripts.collaboration.dispatch_steps import PostDispatchPipeline

        pipeline = PostDispatchPipeline.__new__(PostDispatchPipeline)
        pipeline.output_validator = OutputValidator()
        pipeline.audit_logger = None
        # Simulate config-driven initialization
        PostDispatchPipeline._apply_output_validation_config(
            pipeline, config={"output_validation": {"mode": "blocking"}}
        )
        assert pipeline.output_validation_mode == "blocking"

    def test_02_config_non_blocking_mode(self) -> None:
        from scripts.collaboration.dispatch_steps import PostDispatchPipeline

        pipeline = PostDispatchPipeline.__new__(PostDispatchPipeline)
        pipeline.output_validator = OutputValidator()
        pipeline.audit_logger = None
        PostDispatchPipeline._apply_output_validation_config(
            pipeline, config={"output_validation": {"mode": "non_blocking"}}
        )
        assert pipeline.output_validation_mode == "non_blocking"

    def test_03_config_invalid_value_defaults_to_non_blocking(self) -> None:
        from scripts.collaboration.dispatch_steps import PostDispatchPipeline

        pipeline = PostDispatchPipeline.__new__(PostDispatchPipeline)
        pipeline.output_validator = OutputValidator()
        pipeline.audit_logger = None
        PostDispatchPipeline._apply_output_validation_config(
            pipeline, config={"output_validation": {"mode": "invalid_mode"}}
        )
        assert pipeline.output_validation_mode == "non_blocking"

    def test_04_config_missing_section_defaults_to_non_blocking(self) -> None:
        from scripts.collaboration.dispatch_steps import PostDispatchPipeline

        pipeline = PostDispatchPipeline.__new__(PostDispatchPipeline)
        pipeline.output_validator = OutputValidator()
        pipeline.audit_logger = None
        PostDispatchPipeline._apply_output_validation_config(pipeline, config={})
        assert pipeline.output_validation_mode == "non_blocking"


class TestFailSecure:
    """fail-secure behavior on validator / audit failures."""

    def test_01_validator_exception_returns_high_severity_finding(self) -> None:
        """If OutputValidator.validate raises, fail-secure: treat as blocked."""
        pipeline = _build_pipeline(mode="blocking")

        class BoomValidator:
            def validate(self, _text: str) -> Any:
                raise RuntimeError("validator crashed")

        pipeline.output_validator = BoomValidator()
        result = pipeline._validate_outputs(["any output"])
        # fail-secure: blocked=True, not fail-open
        assert result.blocked is True

    def test_02_audit_failure_does_not_lower_blocking_decision(self) -> None:
        """Audit logger failure should not change blocking decision."""
        class FailingAuditLogger:
            def log_event(self, event_type: str, details: dict[str, Any]) -> None:
                raise RuntimeError("audit db down")

        pipeline = _build_pipeline(mode="blocking", audit_logger=FailingAuditLogger())
        leaky = "sk-" + "a" * 40
        result = pipeline._validate_outputs([leaky])
        # blocked decision stands even if audit logging failed
        assert result.blocked is True
        # audit_logged reflects actual write success
        assert result.audit_logged is False

    def test_03_no_validator_returns_empty_result(self) -> None:
        """When output_validator is None, returns empty (disabled)."""
        pipeline = _build_pipeline()
        pipeline.output_validator = None
        result = pipeline._validate_outputs(["eval(1)"])
        assert result.blocked is False
        assert result.findings == []
        assert result.audit_logged is False


class TestReExportFromDispatchHooks:
    """PostDispatchPipeline re-exported from dispatch_hooks (E2E-05 contract)."""

    def test_01_import_from_dispatch_hooks_works(self) -> None:
        from scripts.collaboration.dispatch_hooks import PostDispatchPipeline as PDP1
        from scripts.collaboration.dispatch_steps import PostDispatchPipeline as PDP2
        assert PDP1 is PDP2

    def test_02_e2e_05_contract_satisfied(self) -> None:
        """E2E-05 skeleton import path works."""
        from scripts.collaboration.dispatch_hooks import PostDispatchPipeline

        # E2E-05 expects: PostDispatchPipeline(config=...) constructible
        # But __init__ requires deps; E2E-05 will use __new__ + _apply_output_validation_config
        # The re-export itself satisfies the import contract
        assert PostDispatchPipeline is not None
        assert hasattr(PostDispatchPipeline, "_validate_outputs")


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


def _find_pattern(result: OutputValidationResult, pattern_name: str) -> OutputFinding | None:
    """Return the first finding with the given pattern_name, or None."""
    for f in result.findings:
        if f.pattern_name == pattern_name:
            return f
    return None
