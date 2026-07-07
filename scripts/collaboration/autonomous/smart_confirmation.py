"""智能确认三态决策：smart/whitelist-only/blacklist-only。

控制自主迭代中哪些操作需要人类确认。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ConfirmationMode(str, Enum):
    """三种确认模式。"""

    SMART = "smart"  # 智能判断：高风险操作需确认，低风险自动执行
    WHITELIST_ONLY = "whitelist-only"  # 仅白名单操作自动执行，其他都需确认
    BLACKLIST_ONLY = "blacklist-only"  # 仅黑名单操作需确认，其他自动执行


class ConfirmationVerdict(str, Enum):
    """确认决策结果。"""

    APPROVE = "approve"  # 自动批准
    REQUIRE_CONFIRMATION = "require_confirmation"  # 需要人类确认
    REJECT = "reject"  # 自动拒绝


@dataclass
class ConfirmationDecision:
    """确认决策。"""

    verdict: ConfirmationVerdict
    reason: str
    operation: str
    risk_level: str  # "low" | "medium" | "high"


# 高风险操作关键词（需确认）
_HIGH_RISK_KEYWORDS = {
    "delete", "drop", "truncate", "force", "reset", "wipe",
    "production", "prod", "release", "deploy", "publish",
    "migration", "schema_change", "rollback",
}

# 中风险操作关键词
_MEDIUM_RISK_KEYWORDS = {
    "commit", "push", "merge", "tag", "branch",
    "install", "uninstall", "upgrade", "downgrade",
    "config_change", "env_change",
}

# 白名单（自动批准）
_WHITELIST_OPERATIONS = {
    "read", "list", "status", "query", "test", "lint", "format",
    "analyze", "discover", "validate",
}


class SmartConfirmation:
    """智能确认三态决策器。

    Usage:
        confirmer = SmartConfirmation(mode=ConfirmationMode.SMART)
        decision = confirmer.evaluate("delete old files")
        if decision.verdict == ConfirmationVerdict.REQUIRE_CONFIRMATION:
            # 等待人类确认
            ...
    """

    def __init__(
        self,
        mode: ConfirmationMode = ConfirmationMode.SMART,
        custom_whitelist: set[str] | None = None,
        custom_blacklist: set[str] | None = None,
    ) -> None:
        self._mode = mode
        self._whitelist = custom_whitelist or _WHITELIST_OPERATIONS
        self._blacklist = custom_blacklist or _HIGH_RISK_KEYWORDS

    def evaluate(self, operation: str) -> ConfirmationDecision:
        """评估操作是否需要确认。"""
        op_lower = operation.lower()

        risk = self._assess_risk(op_lower)

        if self._mode == ConfirmationMode.WHITELIST_ONLY:
            return self._evaluate_whitelist(op_lower, operation, risk)

        if self._mode == ConfirmationMode.BLACKLIST_ONLY:
            return self._evaluate_blacklist(op_lower, operation, risk)

        # SMART 模式
        return self._evaluate_smart(op_lower, operation, risk)

    def _assess_risk(self, op_lower: str) -> str:
        """评估操作风险等级。"""
        if any(kw in op_lower for kw in _HIGH_RISK_KEYWORDS):
            return "high"
        if any(kw in op_lower for kw in _MEDIUM_RISK_KEYWORDS):
            return "medium"
        return "low"

    def _evaluate_whitelist(
        self, op_lower: str, operation: str, risk: str
    ) -> ConfirmationDecision:
        """WHITELIST_ONLY: 仅白名单自动执行。"""
        if any(kw in op_lower for kw in self._whitelist):
            return ConfirmationDecision(
                verdict=ConfirmationVerdict.APPROVE,
                reason=f"Operation in whitelist (risk: {risk})",
                operation=operation,
                risk_level=risk,
            )
        return ConfirmationDecision(
            verdict=ConfirmationVerdict.REQUIRE_CONFIRMATION,
            reason=f"Operation not in whitelist (risk: {risk})",
            operation=operation,
            risk_level=risk,
        )

    def _evaluate_blacklist(
        self, op_lower: str, operation: str, risk: str
    ) -> ConfirmationDecision:
        """BLACKLIST_ONLY: 仅黑名单需确认。"""
        if any(kw in op_lower for kw in self._blacklist):
            return ConfirmationDecision(
                verdict=ConfirmationVerdict.REQUIRE_CONFIRMATION,
                reason=f"Operation in blacklist (risk: {risk})",
                operation=operation,
                risk_level=risk,
            )
        return ConfirmationDecision(
            verdict=ConfirmationVerdict.APPROVE,
            reason=f"Operation not in blacklist (risk: {risk})",
            operation=operation,
            risk_level=risk,
        )

    def _evaluate_smart(
        self, op_lower: str, operation: str, risk: str
    ) -> ConfirmationDecision:
        """SMART: 基于风险等级智能判断。"""
        if risk == "high":
            return ConfirmationDecision(
                verdict=ConfirmationVerdict.REQUIRE_CONFIRMATION,
                reason="High-risk operation requires confirmation",
                operation=operation,
                risk_level=risk,
            )
        if risk == "medium":
            # 中风险：白名单自动通过，其他需确认
            if any(kw in op_lower for kw in self._whitelist):
                return ConfirmationDecision(
                    verdict=ConfirmationVerdict.APPROVE,
                    reason="Medium-risk but in whitelist",
                    operation=operation,
                    risk_level=risk,
                )
            return ConfirmationDecision(
                verdict=ConfirmationVerdict.REQUIRE_CONFIRMATION,
                reason="Medium-risk operation requires confirmation",
                operation=operation,
                risk_level=risk,
            )
        # 低风险：自动批准
        return ConfirmationDecision(
            verdict=ConfirmationVerdict.APPROVE,
            reason="Low-risk operation auto-approved",
            operation=operation,
            risk_level=risk,
        )

    def evaluate_many(self, operations: list[str]) -> list[ConfirmationDecision]:
        """批量评估操作。"""
        return [self.evaluate(op) for op in operations]

    @property
    def mode(self) -> ConfirmationMode:
        return self._mode
