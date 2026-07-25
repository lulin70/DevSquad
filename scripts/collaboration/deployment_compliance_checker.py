#!/usr/bin/env python3
"""DeploymentComplianceChecker — V4.3.0 P0-3 (Phase 0 simplified version).

P10 lifecycle gate checker that validates deployment targets against
DevSquad project hard constraints. Prevents violating deployments
(e.g., basic edition to cloud) before they happen.

Architecture reference: docs/architecture/V4.3.0_ARCHITECTURE.md §9.1
Test plan: docs/testing/V4.3.0_TEST_PLAN.md §11 (E2E-02, E2E-06)
PRD: docs/prd/V4.3.0_PRD.md §9.2 (P0-3)

Skill integration (anti-ghost feature):
- Integration point: ``unified_gate_engine.py`` P10 lifecycle gate
- Trigger: dispatcher auto-invokes via ``lifecycle_gate_check(phase="P10", ...)``
- User visibility: Markdown report "部署合规" section + deployment block message
- CI check: module call count > 0 (verified by ``check_module_activation.py``)

Simplified ruleset (3 rules — see ``DEFAULT_RULESET``):
1. ``BASIC_EDITION_NO_CLOUD`` — basic edition must run on localhost only
   (project_memory Hard Constraint: 基础版必须在用户本地运行)
2. ``PRO_EDITION_SANCTIONED_HOST_ONLY`` — pro edition only on 47.116.219.15
   (project_memory: 专业版网关地址统一为 47.116.219.15:8001)
3. ``NGINX_DEFAULT_SERVER_OFFICIAL_SITE`` — nginx default server must
   serve official static files, must not proxy to app containers
   (project_memory: nginx 默认 server 策略)

Historical lesson (2026-07-12): basic edition was deployed to cloud
server 47.116.219.15 because pre-deployment hard-constraint check was
missing. This module is the post-incident "防违规部署兜底" mitigation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Sanctioned hosts (project_memory Hard Constraints)
# ---------------------------------------------------------------------------
# Basic edition: localhost only — never cloud (数据从不出家门原则)
BASIC_EDITION_ALLOWED_HOSTS: tuple[str, ...] = (
    "localhost",
    "127.0.0.1",
    "0.0.0.0",  # local binding
    "::1",
)

# Pro edition: sanctioned cloud host only (临时使用 47.116.219.15:8001)
PRO_EDITION_SANCTIONED_HOSTS: tuple[str, ...] = (
    "47.116.219.15",
    "gateway.promiselink.cn",  # post-ICP official domain
)

# Cloud-host prefixes/patterns that indicate non-local deployment
_CLOUD_HOST_INDICATORS: tuple[str, ...] = (
    "47.116.219.15",  # Aliyun ECS
    "8.218.",  # Aliyun international
    "47.92.",  # Aliyun ECS
    "39.96.",  # Aliyun ECS
    "121.89.",  # Aliyun ECS
    ".aliyuncs.com",
    ".amazonaws.com",
    ".cloud.google.com",
    ".azurewebsites.net",
    ".tencentcloudapi.com",
)


class ViolationSeverity(str, Enum):
    """Severity levels for compliance violations."""

    CRITICAL = "critical"  # Hard constraint violation — must block
    WARNING = "warning"  # Soft constraint — advisory only


@dataclass
class Violation:
    """A single compliance violation detected by a rule."""

    rule_id: str
    message: str
    severity: ViolationSeverity
    target_env: dict[str, Any] = field(default_factory=dict)
    suggestion: str = ""


@dataclass
class ComplianceReport:
    """Result of a P10 deployment compliance check.

    Attributes
    ----------
    compliant:
        ``True`` if no CRITICAL violations were raised. When ``False``,
        the deployment MUST be blocked by the lifecycle gate.
    violations:
        All violations (any severity) in evaluation order.
    checked_at:
        ISO-8601 timestamp of the check.
    phase:
        Lifecycle phase that triggered the check (e.g. ``"P10"``).
    target_env:
        Normalized target environment dict that was checked.
    """

    compliant: bool
    violations: list[Violation] = field(default_factory=list)
    checked_at: str = field(default_factory=lambda: datetime.now().isoformat())
    phase: str = ""
    target_env: dict[str, Any] = field(default_factory=dict)

    @property
    def critical_violations(self) -> list[Violation]:
        """CRITICAL-severity violations (must block deployment)."""
        return [v for v in self.violations if v.severity == ViolationSeverity.CRITICAL]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dict for Markdown report / audit log."""
        return {
            "compliant": self.compliant,
            "phase": self.phase,
            "checked_at": self.checked_at,
            "target_env": self.target_env,
            "violations": [
                {
                    "rule_id": v.rule_id,
                    "message": v.message,
                    "severity": v.severity.value,
                    "suggestion": v.suggestion,
                }
                for v in self.violations
            ],
        }


# ---------------------------------------------------------------------------
# Ruleset (simplified — 3 rules per PRD P0-3)
# ---------------------------------------------------------------------------
def _check_basic_edition_no_cloud(target_env: dict[str, Any]) -> Violation | None:
    """Rule 1: Basic edition must run on localhost, never on cloud hosts.

    project_memory Hard Constraint: 基础版必须在用户本地运行（localhost:8000），
    禁止云端部署基础版容器。
    """
    edition = str(target_env.get("edition", "")).lower()
    if edition != "basic":
        return None

    host = str(target_env.get("host", "")).lower()
    if not host:
        return Violation(
            rule_id="BASIC_EDITION_NO_CLOUD",
            message="基础版部署缺少 host 字段，无法验证本地约束",
            severity=ViolationSeverity.WARNING,
            target_env=target_env,
            suggestion="显式指定 host=localhost 以满足本地部署约束",
        )

    if host in BASIC_EDITION_ALLOWED_HOSTS:
        return None

    # Host is not localhost — check if it's a known cloud host
    is_cloud = any(indicator in host for indicator in _CLOUD_HOST_INDICATORS)
    if is_cloud or not _is_local_host(host):
        return Violation(
            rule_id="BASIC_EDITION_NO_CLOUD",
            message="基础版禁止云端部署（违反硬约束：基础版必须在用户本地运行）",
            severity=ViolationSeverity.CRITICAL,
            target_env=target_env,
            suggestion=(
                "基础版必须在 localhost 运行（数据从不出家门原则）；"
                "如需云端能力，请使用专业版网关 gateway.promiselink.cn"
            ),
        )
    return None


def _check_pro_edition_sanctioned_host_only(
    target_env: dict[str, Any],
) -> Violation | None:
    """Rule 2: Pro edition must deploy to the sanctioned cloud host only.

    project_memory: 专业版网关地址统一为 gateway.promiselink.cn，
    备案前临时使用 47.116.219.15:8001。
    """
    edition = str(target_env.get("edition", "")).lower()
    if edition != "pro":
        return None

    host = str(target_env.get("host", "")).lower()
    if not host:
        return Violation(
            rule_id="PRO_EDITION_SANCTIONED_HOST_ONLY",
            message="专业版部署缺少 host 字段，无法验证受控主机约束",
            severity=ViolationSeverity.WARNING,
            target_env=target_env,
            suggestion=(
                "专业版必须部署到受控主机：47.116.219.15 或 gateway.promiselink.cn"
            ),
        )

    if host in PRO_EDITION_SANCTIONED_HOSTS:
        return None

    return Violation(
        rule_id="PRO_EDITION_SANCTIONED_HOST_ONLY",
        message=(
            f"专业版部署到未授权主机 {host}（违反硬约束：专业版仅允许部署到 "
            "47.116.219.15 或 gateway.promiselink.cn）"
        ),
        severity=ViolationSeverity.CRITICAL,
        target_env=target_env,
        suggestion="专业版必须部署到受控主机：47.116.219.15 或 gateway.promiselink.cn",
    )


def _check_nginx_default_server_official_site(
    target_env: dict[str, Any],
) -> Violation | None:
    """Rule 3: nginx default server must serve official static files.

    project_memory: nginx 默认 server 策略 — 默认 server 块（捕获直接
    IP 访问和未匹配 Host）必须服务官网静态文件，禁止代理到任何应用容器。
    """
    nginx_config = target_env.get("nginx_default_server")
    if nginx_config is None:
        # Not applicable — no nginx default server in this deployment
        return None

    config_str = str(nginx_config).lower()
    # Detect proxy_pass to app containers (basic edition or pro edition)
    forbidden_proxy_patterns = (
        "proxy_pass http://promiselink-basic",
        "proxy_pass http://promiselink-pro",
        "proxy_pass http://localhost:8000",
        "proxy_pass http://127.0.0.1:8000",
        "proxy_pass http://basic",
        "proxy_pass http://pro",
    )
    for pattern in forbidden_proxy_patterns:
        if pattern in config_str:
            return Violation(
                rule_id="NGINX_DEFAULT_SERVER_OFFICIAL_SITE",
                message=(
                    "nginx 默认 server 块禁止代理到应用容器（违反硬约束：默认 server "
                    "必须服务官网静态文件，禁止代理到基础版或专业版容器）"
                ),
                severity=ViolationSeverity.CRITICAL,
                target_env=target_env,
                suggestion=(
                    "默认 server 块应 root 到官网静态文件目录；"
                    "/health 可代理到专业版网关 promiselink-pro:8001"
                ),
            )

    # Must serve static files (root or alias directive)
    if "root " not in config_str and "alias " not in config_str:
        return Violation(
            rule_id="NGINX_DEFAULT_SERVER_OFFICIAL_SITE",
            message=(
                "nginx 默认 server 块必须包含 root 或 alias 指令以服务官网静态文件"
            ),
            severity=ViolationSeverity.WARNING,
            target_env=target_env,
            suggestion="添加 root /var/www/promiselink; 或等价指令",
        )

    return None


def _is_local_host(host: str) -> bool:
    """Check if a host string refers to the local machine."""
    return host.lower() in BASIC_EDITION_ALLOWED_HOSTS


# Ordered list of rule callables (evaluation order matters for reporting)
DEFAULT_RULESET: tuple = (
    _check_basic_edition_no_cloud,
    _check_pro_edition_sanctioned_host_only,
    _check_nginx_default_server_official_site,
)


# ---------------------------------------------------------------------------
# Public API — invoked by UnifiedGateEngine P10 lifecycle gate
# ---------------------------------------------------------------------------
def lifecycle_gate_check(
    phase: str,
    target_env: dict[str, Any] | str,
    ruleset: tuple = DEFAULT_RULESET,
) -> ComplianceReport:
    """Run P10 deployment compliance check against project hard constraints.

    Args:
        phase:
            Lifecycle phase that triggers the check. Must be ``"P10"`` for
            deployment gate; other phases are accepted but logged at WARNING.
        target_env:
            Target environment descriptor. Accepts either a dict with
            ``edition`` / ``host`` / optional ``nginx_default_server`` keys,
            or a string shorthand (e.g. ``"basic@localhost"``).
        ruleset:
            Tuple of rule callables. Defaults to ``DEFAULT_RULESET`` (3 rules).
            Each callable takes the normalized target_env dict and returns
            a ``Violation`` or ``None``.

    Returns:
        A :class:`ComplianceReport`. ``compliant`` is ``True`` only when
        no CRITICAL violations were raised.

    Raises:
        ValueError: If ``target_env`` is empty or cannot be normalized.

    Skill integration:
        Called by ``UnifiedGateEngine.check(GateType.COMPLIANCE_CHECK, ...)``
        when the lifecycle protocol reaches P10 (deployment phase).
        Violations appear in the Markdown report "部署合规" section.
    """
    if phase != "P10":
        logger.warning(
            "DeploymentComplianceChecker invoked at phase %s (expected P10)", phase
        )

    normalized_env = _normalize_target_env(target_env)
    if not normalized_env:
        raise ValueError(
            f"Cannot normalize target_env: {target_env!r} (expected dict or 'edition@host')"
        )

    violations: list[Violation] = []
    for rule in ruleset:
        try:
            violation = rule(normalized_env)
            if violation is not None:
                violations.append(violation)
        except (KeyError, TypeError, AttributeError) as exc:
            logger.warning("Rule %s failed with %s: %s", rule.__name__, type(exc).__name__, exc)
            violations.append(
                Violation(
                    rule_id=rule.__name__,
                    message=f"规则评估失败: {exc}",
                    severity=ViolationSeverity.WARNING,
                    target_env=normalized_env,
                )
            )

    has_critical = any(v.severity == ViolationSeverity.CRITICAL for v in violations)
    report = ComplianceReport(
        compliant=not has_critical,
        violations=violations,
        phase=phase,
        target_env=normalized_env,
    )

    if has_critical:
        logger.warning(
            "P10 compliance check BLOCKED deployment: %d critical violations",
            len(report.critical_violations),
        )
    else:
        logger.info("P10 compliance check passed: %d warnings", len(violations))

    return report


def _normalize_target_env(target_env: dict[str, Any] | str) -> dict[str, Any]:
    """Normalize the target_env input to a dict.

    Accepts:
    - dict: returned as-is (with edition/host lowercased if strings)
    - str: parsed as ``edition@host`` (e.g. ``"basic@localhost"``)
    - str: parsed as ``edition:host`` (e.g. ``"pro:47.116.219.15"``)

    Returns an empty dict if normalization fails.
    """
    if isinstance(target_env, dict):
        normalized: dict[str, Any] = dict(target_env)
        if "edition" in normalized and isinstance(normalized["edition"], str):
            normalized["edition"] = normalized["edition"].lower()
        if "host" in normalized and isinstance(normalized["host"], str):
            normalized["host"] = normalized["host"].lower()
        return normalized

    if isinstance(target_env, str):
        for sep in ("@", ":"):
            if sep in target_env:
                edition, _, host = target_env.partition(sep)
                return {
                    "edition": edition.strip().lower(),
                    "host": host.strip().lower(),
                }

    return {}


__all__ = [
    "BASIC_EDITION_ALLOWED_HOSTS",
    "ComplianceReport",
    "DEFAULT_RULESET",
    "PRO_EDITION_SANCTIONED_HOSTS",
    "Violation",
    "ViolationSeverity",
    "lifecycle_gate_check",
]
