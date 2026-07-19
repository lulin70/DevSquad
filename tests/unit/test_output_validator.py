"""Unit tests for OutputValidator (P1-6 skeleton).

Covers code injection, sensitive info, and path leak detection,
plus redaction semantics and the PostDispatchPipeline._validate_outputs
integration shim.
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

    Uses a minimal PostDispatchPipeline constructed via __new__ to bypass
    the heavy __init__ (we only need the output_validator attribute and
    the _validate_outputs / _extract_output_text methods).
    """
    from scripts.collaboration.dispatch_steps import PostDispatchPipeline

    pipeline = PostDispatchPipeline.__new__(PostDispatchPipeline)
    pipeline.output_validator = OutputValidator()

    worker_results: list[dict[str, Any]] = [
        {"output": "eval('dangerous code')"},
        {"output": "Safe output"},
        {"raw_output": "password=hunter2password"},
        {"content": "/etc/passwd contents"},
        {"non_text_field": 123},  # No textual payload → skipped
        {},  # Empty dict → skipped
    ]

    findings = pipeline._validate_outputs(worker_results)

    # At least 3 workers should have findings (idx 0, 2, 3).
    worker_indices = {f["worker_idx"] for f in findings}
    assert 0 in worker_indices
    assert 2 in worker_indices
    assert 3 in worker_indices
    # Worker 1 (safe) and 4/5 (no text) should have no findings.
    assert 1 not in worker_indices
    assert 4 not in worker_indices
    assert 5 not in worker_indices


def test_post_dispatch_validate_outputs_disabled_returns_empty() -> None:
    """When output_validator is None, _validate_outputs returns []."""
    from scripts.collaboration.dispatch_steps import PostDispatchPipeline

    pipeline = PostDispatchPipeline.__new__(PostDispatchPipeline)
    pipeline.output_validator = None

    findings = pipeline._validate_outputs([{"output": "eval(1)"}])
    assert findings == []


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
# Helpers
# ---------------------------------------------------------------------


def _find_pattern(result: OutputValidationResult, pattern_name: str) -> OutputFinding | None:
    """Return the first finding with the given pattern_name, or None."""
    for f in result.findings:
        if f.pattern_name == pattern_name:
            return f
    return None
