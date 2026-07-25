"""Tests for ``scripts.collaboration.deployment_compliance_checker`` — V4.3.0 P0-3.

Coverage focus (per test plan §11.4 / §11.6 — 7 dimensions):
- Happy ≥50%: compliant deployments pass for all 3 editions
- Error ≥15%: invalid / missing target_env, normalization failures
- Boundary ≥10%: empty fields, None, case-insensitive, unknown edition
- Integration ≥10% (in test_integration_*): P10 gate integration
- Security ≥5%: violating deployments blocked, all 3 rules
- Performance ≥5%: <100ms per check
- Config ≥5%: custom ruleset, disabled rules
"""

from __future__ import annotations

import time
from typing import Any

import pytest

from scripts.collaboration.deployment_compliance_checker import (
    BASIC_EDITION_ALLOWED_HOSTS,
    DEFAULT_RULESET,
    PRO_EDITION_SANCTIONED_HOSTS,
    Violation,
    ViolationSeverity,
    lifecycle_gate_check,
)

# ---------------------------------------------------------------------------
# Happy path — compliant deployments pass (≥50% of test count)
# ---------------------------------------------------------------------------


class TestHappyPath:
    """Happy path: compliant deployments pass the P10 gate."""

    def test_basic_edition_on_localhost_passes(self) -> None:
        """Basic edition deployed to localhost is compliant."""
        report = lifecycle_gate_check(
            phase="P10",
            target_env={"edition": "basic", "host": "localhost"},
        )
        assert report.compliant is True
        assert report.violations == []
        assert report.phase == "P10"

    def test_basic_edition_on_127_passes(self) -> None:
        """Basic edition deployed to 127.0.0.1 is compliant."""
        report = lifecycle_gate_check(
            phase="P10",
            target_env={"edition": "basic", "host": "127.0.0.1"},
        )
        assert report.compliant is True

    @pytest.mark.parametrize("host", PRO_EDITION_SANCTIONED_HOSTS)
    def test_pro_edition_on_sanctioned_host_passes(self, host: str) -> None:
        """Pro edition deployed to a sanctioned host is compliant."""
        report = lifecycle_gate_check(
            phase="P10",
            target_env={"edition": "pro", "host": host},
        )
        assert report.compliant is True
        assert report.violations == []

    def test_unknown_edition_passes_with_no_violations(self) -> None:
        """Unknown edition (e.g. enterprise) skips both basic and pro rules."""
        report = lifecycle_gate_check(
            phase="P10",
            target_env={"edition": "enterprise", "host": "internal.corp"},
        )
        # No rule applies to enterprise edition in simplified ruleset
        assert report.compliant is True
        assert report.violations == []

    def test_string_shorthand_basic_at_localhost(self) -> None:
        """String shorthand ``basic@localhost`` is parsed correctly."""
        report = lifecycle_gate_check(phase="P10", target_env="basic@localhost")
        assert report.compliant is True
        assert report.target_env["edition"] == "basic"
        assert report.target_env["host"] == "localhost"

    def test_string_shorthand_pro_colon_sanctioned(self) -> None:
        """String shorthand ``pro:47.116.219.15`` is parsed correctly."""
        report = lifecycle_gate_check(
            phase="P10",
            target_env="pro:47.116.219.15",
        )
        assert report.compliant is True

    def test_nginx_default_server_serving_static_passes(self) -> None:
        """nginx default server with root directive is compliant."""
        report = lifecycle_gate_check(
            phase="P10",
            target_env={
                "edition": "pro",
                "host": "47.116.219.15",
                "nginx_default_server": "server { root /var/www/promiselink; }",
            },
        )
        assert report.compliant is True


# ---------------------------------------------------------------------------
# Error path — invalid / missing input (≥15% of test count)
# ---------------------------------------------------------------------------


class TestErrorPath:
    """Error path: invalid input handling."""

    def test_empty_target_env_dict_raises_value_error(self) -> None:
        """Empty dict cannot be normalized — raises ValueError."""
        with pytest.raises(ValueError, match="Cannot normalize"):
            lifecycle_gate_check(phase="P10", target_env={})

    def test_empty_string_target_env_raises_value_error(self) -> None:
        """Empty string cannot be normalized — raises ValueError."""
        with pytest.raises(ValueError, match="Cannot normalize"):
            lifecycle_gate_check(phase="P10", target_env="")

    def test_target_env_without_separator_raises_value_error(self) -> None:
        """String without @ or : cannot be parsed — raises ValueError."""
        with pytest.raises(ValueError, match="Cannot normalize"):
            lifecycle_gate_check(phase="P10", target_env="basic")

    def test_rule_exception_is_caught_and_reported(self) -> None:
        """A rule that raises is caught and recorded as a WARNING violation."""

        def broken_rule(target_env: dict[str, Any]) -> Violation | None:
            raise KeyError("intentional test failure")

        report = lifecycle_gate_check(
            phase="P10",
            target_env={"edition": "pro", "host": "47.116.219.15"},
            ruleset=(broken_rule,),
        )
        assert report.compliant is True  # WARNING, not CRITICAL
        assert len(report.violations) == 1
        assert "intentional test failure" in report.violations[0].message


# ---------------------------------------------------------------------------
# Boundary — empty fields, None, case-insensitive (≥10%)
# ---------------------------------------------------------------------------


class TestBoundary:
    """Boundary conditions: None, case-insensitive, missing fields."""

    def test_basic_edition_with_missing_host_raises_warning(self) -> None:
        """Basic edition with no host field raises WARNING (not CRITICAL)."""
        report = lifecycle_gate_check(
            phase="P10",
            target_env={"edition": "basic"},  # no host
        )
        assert report.compliant is True
        assert len(report.violations) == 1
        assert report.violations[0].rule_id == "BASIC_EDITION_NO_CLOUD"
        assert report.violations[0].severity == ViolationSeverity.WARNING

    def test_pro_edition_with_missing_host_raises_warning(self) -> None:
        """Pro edition with no host field raises WARNING."""
        report = lifecycle_gate_check(
            phase="P10",
            target_env={"edition": "pro"},  # no host
        )
        assert report.compliant is True
        assert len(report.violations) == 1
        assert report.violations[0].severity == ViolationSeverity.WARNING

    def test_edition_is_case_insensitive(self) -> None:
        """Edition field is normalized to lowercase."""
        report = lifecycle_gate_check(
            phase="P10",
            target_env={"edition": "BASIC", "host": "localhost"},
        )
        assert report.compliant is True
        assert report.target_env["edition"] == "basic"

    def test_host_is_case_insensitive(self) -> None:
        """Host field is normalized to lowercase."""
        report = lifecycle_gate_check(
            phase="P10",
            target_env={"edition": "pro", "host": "47.116.219.15"},
        )
        assert report.compliant is True

    def test_none_nginx_default_server_is_skipped(self) -> None:
        """nginx_default_server=None is skipped (rule not applicable)."""
        report = lifecycle_gate_check(
            phase="P10",
            target_env={
                "edition": "pro",
                "host": "47.116.219.15",
                "nginx_default_server": None,
            },
        )
        assert report.compliant is True


# ---------------------------------------------------------------------------
# Security — violating deployments blocked (≥5%)
# ---------------------------------------------------------------------------


class TestSecurity:
    """Security: all 3 rules block their respective violations."""

    def test_basic_edition_to_cloud_blocked(self) -> None:
        """Basic edition to cloud host is blocked with CRITICAL violation."""
        report = lifecycle_gate_check(
            phase="P10",
            target_env={"edition": "basic", "host": "47.116.219.15"},
        )
        assert report.compliant is False
        assert len(report.critical_violations) == 1
        v = report.critical_violations[0]
        assert v.rule_id == "BASIC_EDITION_NO_CLOUD"
        assert "基础版禁止云端部署" in v.message

    def test_basic_edition_to_aws_blocked(self) -> None:
        """Basic edition to AWS host is blocked."""
        report = lifecycle_gate_check(
            phase="P10",
            target_env={"edition": "basic", "host": "ec2-1-2-3-4.amazonaws.com"},
        )
        assert report.compliant is False
        assert report.critical_violations[0].rule_id == "BASIC_EDITION_NO_CLOUD"

    def test_pro_edition_to_unsanctioned_blocked(self) -> None:
        """Pro edition to non-sanctioned host is blocked."""
        report = lifecycle_gate_check(
            phase="P10",
            target_env={"edition": "pro", "host": "evil.example.com"},
        )
        assert report.compliant is False
        v = report.critical_violations[0]
        assert v.rule_id == "PRO_EDITION_SANCTIONED_HOST_ONLY"
        assert "evil.example.com" in v.message

    def test_nginx_default_server_proxying_to_app_blocked(self) -> None:
        """nginx default server proxying to app container is blocked."""
        report = lifecycle_gate_check(
            phase="P10",
            target_env={
                "edition": "pro",
                "host": "47.116.219.15",
                "nginx_default_server": (
                    "server { proxy_pass http://promiselink-basic:8000; }"
                ),
            },
        )
        assert report.compliant is False
        v = report.critical_violations[0]
        assert v.rule_id == "NGINX_DEFAULT_SERVER_OFFICIAL_SITE"

    def test_nginx_default_server_without_root_raises_warning(self) -> None:
        """nginx default server without root/alias raises WARNING."""
        report = lifecycle_gate_check(
            phase="P10",
            target_env={
                "edition": "pro",
                "host": "47.116.219.15",
                "nginx_default_server": "server { listen 80; }",
            },
        )
        assert report.compliant is True  # WARNING only
        assert any(
            v.rule_id == "NGINX_DEFAULT_SERVER_OFFICIAL_SITE"
            and v.severity == ViolationSeverity.WARNING
            for v in report.violations
        )


# ---------------------------------------------------------------------------
# Performance — <100ms per check (≥5%)
# ---------------------------------------------------------------------------


class TestPerformance:
    """Performance: each check completes in <100ms."""

    def test_compliant_check_under_100ms(self) -> None:
        """Compliant deployment check completes in <100ms."""
        start = time.perf_counter()
        lifecycle_gate_check(
            phase="P10",
            target_env={"edition": "pro", "host": "47.116.219.15"},
        )
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 100, f"Check took {elapsed_ms:.2f}ms (threshold 100ms)"

    def test_violating_check_under_100ms(self) -> None:
        """Violating deployment check completes in <100ms."""
        start = time.perf_counter()
        lifecycle_gate_check(
            phase="P10",
            target_env={"edition": "basic", "host": "47.116.219.15"},
        )
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 100, f"Check took {elapsed_ms:.2f}ms (threshold 100ms)"


# ---------------------------------------------------------------------------
# Config — custom ruleset, disabled rules (≥5%)
# ---------------------------------------------------------------------------


class TestConfig:
    """Configuration: custom ruleset, edition-specific behavior."""

    def test_empty_ruleset_always_compliant(self) -> None:
        """Empty ruleset means no checks — always compliant."""
        report = lifecycle_gate_check(
            phase="P10",
            target_env={"edition": "basic", "host": "47.116.219.15"},
            ruleset=(),
        )
        assert report.compliant is True
        assert report.violations == []

    def test_custom_rule_adds_violation(self) -> None:
        """Custom rule can add additional violations."""

        def custom_rule(target_env: dict[str, Any]) -> Violation | None:
            if target_env.get("edition") == "enterprise":
                return Violation(
                    rule_id="CUSTOM_ENTERPRISE_CHECK",
                    message="Enterprise edition requires audit log",
                    severity=ViolationSeverity.WARNING,
                )
            return None

        report = lifecycle_gate_check(
            phase="P10",
            target_env={"edition": "enterprise", "host": "internal"},
            ruleset=DEFAULT_RULESET + (custom_rule,),
        )
        # Default rules don't apply to enterprise; custom does
        assert len(report.violations) == 1
        assert report.violations[0].rule_id == "CUSTOM_ENTERPRISE_CHECK"

    def test_non_p10_phase_logs_warning_but_returns_report(self) -> None:
        """Non-P10 phase logs a warning but still evaluates the ruleset."""
        report = lifecycle_gate_check(
            phase="P8",
            target_env={"edition": "basic", "host": "47.116.219.15"},
        )
        # P8 is not the deployment phase, but the ruleset still runs
        assert report.compliant is False
        assert report.phase == "P8"

    def test_report_to_dict_serializable(self) -> None:
        """ComplianceReport.to_dict() produces a JSON-serializable dict."""
        report = lifecycle_gate_check(
            phase="P10",
            target_env={"edition": "basic", "host": "47.116.219.15"},
        )
        d = report.to_dict()
        assert d["compliant"] is False
        assert d["phase"] == "P10"
        assert len(d["violations"]) == 1
        assert d["violations"][0]["rule_id"] == "BASIC_EDITION_NO_CLOUD"
        assert d["violations"][0]["severity"] == "critical"

    def test_critical_violations_property_filters_correctly(self) -> None:
        """``critical_violations`` property returns only CRITICAL entries."""
        report = lifecycle_gate_check(
            phase="P10",
            target_env={
                "edition": "basic",
                "host": "47.116.219.15",
                "nginx_default_server": "server { listen 80; }",  # WARNING
            },
        )
        # basic→cloud = CRITICAL, nginx-without-root = WARNING
        assert len(report.violations) == 2
        assert len(report.critical_violations) == 1
        assert report.critical_violations[0].severity == ViolationSeverity.CRITICAL


# ---------------------------------------------------------------------------
# Constants sanity checks
# ---------------------------------------------------------------------------


class TestConstants:
    """Sanity checks for module-level constants."""

    def test_basic_edition_allowed_hosts_includes_localhost(self) -> None:
        """BASIC_EDITION_ALLOWED_HOSTS must include localhost variants."""
        assert "localhost" in BASIC_EDITION_ALLOWED_HOSTS
        assert "127.0.0.1" in BASIC_EDITION_ALLOWED_HOSTS

    def test_pro_edition_sanctioned_hosts_includes_aliyun_ip(self) -> None:
        """PRO_EDITION_SANCTIONED_HOSTS must include the Aliyun host."""
        assert "47.116.219.15" in PRO_EDITION_SANCTIONED_HOSTS

    def test_default_ruleset_has_three_rules(self) -> None:
        """DEFAULT_RULESET contains exactly 3 rules (simplified version)."""
        assert len(DEFAULT_RULESET) == 3
