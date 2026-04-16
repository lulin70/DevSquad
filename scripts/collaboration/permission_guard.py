#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PermissionGuard - 4-Level Permission Guard System

Based on v3-phase2-permission-design.md:
  Level DEFAULT: Dangerous ops require user confirmation
  Level PLAN:     Read-only mode, all writes denied
  Level AUTO:     AI classifier auto-judges + whitelist
  Level BYPASS:   Skip all checks (highest trust only)

Core components:
  - ActionType: 9 operation types (FILE_READ/WRITE/DELETE/SHELL/NETWORK/GIT/ENV/PROCESS)
  - PermissionLevel: 4 security levels (DEFAULT/PLAN/AUTO/BYPASS)
  - DecisionOutcome: 4 verdicts (ALLOWED/DENIED/PROMPT/ESCALATED)
  - Rule Engine: glob + prefix + regex pattern matching
  - AI Classifier: 5-dimension risk scoring [0.0, 1.0]
  - Audit Log: complete decision trail with filtering
"""

import re
import fnmatch
import uuid
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


class PermissionLevel(Enum):
    DEFAULT = "default"
    PLAN = "plan"
    AUTO = "auto"
    BYPASS = "bypass"


class ActionType(Enum):
    FILE_READ = "file_read"
    FILE_CREATE = "file_create"
    FILE_MODIFY = "file_modify"
    FILE_DELETE = "file_delete"
    SHELL_EXECUTE = "shell_execute"
    NETWORK_REQUEST = "network_request"
    GIT_OPERATION = "git_operation"
    ENVIRONMENT = "environment"
    PROCESS_SPAWN = "process_spawn"


class DecisionOutcome(Enum):
    ALLOWED = "allowed"
    DENIED = "denied"
    PROMPT = "prompt"
    ESCALATED = "escalated"


@dataclass
class ProposedAction:
    action_type: ActionType = ActionType.FILE_READ
    target: str = ""
    description: str = ""
    source_worker_id: Optional[str] = None
    source_role_id: Optional[str] = None
    risk_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "action_type": self.action_type.value,
            "target": self.target,
            "description": self.description,
            "source_worker_id": self.source_worker_id,
            "source_role_id": self.source_role_id,
            "risk_score": self.risk_score,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "ProposedAction":
        ts = d.get("timestamp")
        return cls(
            action_type=ActionType(d.get("action_type", "file_read")),
            target=d.get("target", ""),
            description=d.get("description", ""),
            source_worker_id=d.get("source_worker_id"),
            source_role_id=d.get("source_role_id"),
            risk_score=d.get("risk_score", 0.0),
            metadata=d.get("metadata", {}),
            timestamp=datetime.fromisoformat(ts) if ts else datetime.now(),
        )


@dataclass
class PermissionRule:
    rule_id: str
    action_type: ActionType
    pattern: str
    required_level: PermissionLevel
    description: str = ""
    risk_boost: float = 0.0
    tags: List[str] = field(default_factory=list)
    enabled: bool = True

    def to_dict(self) -> Dict:
        return {
            "rule_id": self.rule_id,
            "action_type": self.action_type.value,
            "pattern": self.pattern,
            "required_level": self.required_level.value,
            "description": self.description,
            "risk_boost": self.risk_boost,
            "tags": self.tags,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "PermissionRule":
        return cls(
            rule_id=d["rule_id"],
            action_type=ActionType(d["action_type"]),
            pattern=d["pattern"],
            required_level=PermissionLevel(d["required_level"]),
            description=d.get("description", ""),
            risk_boost=d.get("risk_boost", 0.0),
            tags=d.get("tags", []),
            enabled=d.get("enabled", True),
        )


@dataclass
class PermissionDecision:
    action: ProposedAction
    outcome: DecisionOutcome
    matched_rule: Optional[PermissionRule] = None
    reason: str = ""
    requires_confirmation: bool = False
    confidence: float = 1.0
    decided_at: datetime = field(default_factory=datetime.now)
    decision_id: str = field(default_factory=lambda: f"pd-{uuid.uuid4().hex[:12]}")

    def to_dict(self) -> Dict:
        return {
            "decision_id": self.decision_id,
            "outcome": self.outcome.value,
            "matched_rule": self.matched_rule.rule_id if self.matched_rule else None,
            "reason": self.reason,
            "requires_confirmation": self.requires_confirmation,
            "confidence": self.confidence,
            "decided_at": self.decided_at.isoformat(),
            "action": self.action.to_dict(),
        }


@dataclass
class AuditEntry:
    entry_id: str = field(default_factory=lambda: f"ae-{uuid.uuid4().hex[:12]}")
    action: Optional[ProposedAction] = None
    decision: Optional[PermissionDecision] = None
    duration_ms: int = 0
    guard_level: PermissionLevel = PermissionLevel.DEFAULT
    user_response: Optional[str] = None
    session_id: str = field(default_factory=lambda: f"sess-{uuid.uuid4().hex[:8]}")
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "entry_id": self.entry_id,
            "action": self.action.to_dict() if self.action else None,
            "decision": self.decision.to_dict() if self.decision else None,
            "duration_ms": self.duration_ms,
            "guard_level": self.guard_level.value,
            "user_response": self.user_response,
            "session_id": self.session_id,
            "timestamp": self.timestamp.isoformat(),
        }


# ============================================================
# Default Rules (30 rules covering common scenarios)
# ============================================================

def _build_default_rules() -> List[PermissionRule]:
    return [
        # File Read (low risk)
        PermissionRule("R001", ActionType.FILE_READ, "**/*",
                        PermissionLevel.PLAN, "Read any file", risk_boost=0.0),

        # File Create (medium risk)
        PermissionRule("R002", ActionType.FILE_CREATE, "*.py",
                        PermissionLevel.AUTO, "Create Python file", risk_boost=0.1),
        PermissionRule("R003", ActionType.FILE_CREATE, "*.md",
                        PermissionLevel.AUTO, "Create markdown doc", risk_boost=0.05),
        PermissionRule("R004", ActionType.FILE_CREATE, "*.json",
                        PermissionLevel.DEFAULT, "Create JSON data file", risk_boost=0.15),
        PermissionRule("R005", ActionType.FILE_CREATE, "*",
                        PermissionLevel.DEFAULT, "Create other file type", risk_boost=0.2),

        # File Modify (medium-high risk)
        PermissionRule("R006", ActionType.FILE_MODIFY, "*.py",
                        PermissionLevel.AUTO, "Modify Python source", risk_boost=0.2),
        PermissionRule("R007", ActionType.FILE_MODIFY, "*.md",
                        PermissionLevel.AUTO, "Modify document", risk_boost=0.1),
        PermissionRule("R008", ActionType.FILE_MODIFY, "*.json",
                        PermissionLevel.DEFAULT, "Modify config file", risk_boost=0.25),
        PermissionRule("R009", ActionType.FILE_MODIFY, ".env*",
                        PermissionLevel.BYPASS, "Modify env file", risk_boost=0.8),
        PermissionRule("R010", ActionType.FILE_MODIFY, "*credentials*",
                        PermissionLevel.BYPASS, "Modify credentials", risk_boost=0.95),
        PermissionRule("R011", ActionType.FILE_MODIFY, "*",
                        PermissionLevel.DEFAULT, "Modify other files", risk_boost=0.25),

        # File Delete (high risk)
        PermissionRule("R012", ActionType.FILE_DELETE, "__pycache__/**",
                        PermissionLevel.AUTO, "Delete Python cache", risk_boost=0.1),
        PermissionRule("R013", ActionType.FILE_DELETE, "*.pyc",
                        PermissionLevel.AUTO, "Delete compiled cache", risk_boost=0.1),
        PermissionRule("R014", ActionType.FILE_DELETE, ".git/**",
                        PermissionLevel.BYPASS, "Delete Git dir content", risk_boost=0.99),
        PermissionRule("R015", ActionType.FILE_DELETE, "*",
                        PermissionLevel.BYPASS, "Delete any file", risk_boost=0.9),

        # Shell Execute (very high risk)
        PermissionRule("R016", ActionType.SHELL_EXECUTE, "cat *",
                        PermissionLevel.AUTO, "View file content", risk_boost=0.05),
        PermissionRule("R017", ActionType.SHELL_EXECUTE, "ls *",
                        PermissionLevel.AUTO, "List directory", risk_boost=0.05),
        PermissionRule("R018", ActionType.SHELL_EXECUTE, "git *",
                        PermissionLevel.AUTO, "Git read-only commands", risk_boost=0.1),
        PermissionRule("R019", ActionType.SHELL_EXECUTE, "pip install *",
                        PermissionLevel.DEFAULT, "Install Python package", risk_boost=0.5),
        PermissionRule("R020", ActionType.SHELL_EXECUTE, "rm *",
                        PermissionLevel.BYPASS, "Remove command", risk_boost=0.95),
        PermissionRule("R021", ActionType.SHELL_EXECUTE, "sudo *",
                        PermissionLevel.BYPASS, "Privilege escalation", risk_boost=1.0),
        PermissionRule("R022", ActionType.SHELL_EXECUTE, "*",
                        PermissionLevel.DEFAULT, "Other shell commands", risk_boost=0.6),

        # Network Request (medium-high risk)
        PermissionRule("R023", ActionType.NETWORK_REQUEST, "*pypi.org*",
                        PermissionLevel.AUTO, "PyPI download", risk_boost=0.15),
        PermissionRule("R024", ActionType.NETWORK_REQUEST, "*github.com*",
                        PermissionLevel.DEFAULT, "GitHub API access", risk_boost=0.3),
        PermissionRule("R025", ActionType.NETWORK_REQUEST, "*",
                        PermissionLevel.DEFAULT, "Other network requests", risk_boost=0.5),

        # Git Operations
        PermissionRule("R026", ActionType.GIT_OPERATION, "*",
                        PermissionLevel.AUTO, "Git read operations", risk_boost=0.05),
        PermissionRule("R027", ActionType.GIT_OPERATION, "*commit*|*add*",
                        PermissionLevel.DEFAULT, "Git commit ops", risk_boost=0.3),
        PermissionRule("R028", ActionType.GIT_OPERATION, "*push*",
                        PermissionLevel.DEFAULT, "Git push operation", risk_boost=0.4),
        PermissionRule("R029", ActionType.GIT_OPERATION, "*reset*|*rebase*|*force*",
                        PermissionLevel.BYPASS, "Dangerous git ops", risk_boost=0.9),

        # Environment
        PermissionRule("R030", ActionType.ENVIRONMENT, "*",
                        PermissionLevel.BYPASS, "Modify environment vars", risk_boost=0.7),
    ]


# Sensitive keyword patterns for path traversal / injection detection
_SENSITIVE_PATH_PATTERNS = [
    r"\.\./",           # Path traversal
    r"\.\.\\" ,         # Windows traversal
    r"\x00",            # Null byte
    r"/etc/passwd",     # Sensitive system file
    r"/etc/shadow",
]

_SENSITIVE_KEYWORDS = [
    "credential", "secret", "password", "private_key", "api_key",
    "token", ".env", ".pem", ".key", "id_rsa", ".ssh",
]


class PermissionGuard:
    """
    4级权限守卫系统 - 多 Agent 协作的安全操作检查核心

    安全级别（由低到高）:
        PLAN (0): 只读模式，所有写操作被拒绝
        DEFAULT (1): 危险操作需用户确认
        AUTO (2): AI 分类器自动判断 + 白名单放行
        BYPASS (3): 跳过所有检查（最高信任，仅限受控环境）

    核心能力:
    - check(): 对 ProposedAction 进行权限决策（ALLOWED/DENIED/PROMPT/ESCALATED）
    - auto_classify(): 5维风险评分模型（目标敏感性/破坏性/范围/来源可信度/上下文合理性）
    - 规则引擎: 30条默认规则覆盖 9种操作类型，支持 glob/前缀/regex 模式匹配
    - 审计日志: 完整的决策链路记录，支持多维度过滤查询

    决策流程:
        BYPASS → 直接放行
        PLAN → 只读放行/写入拒绝
        DEFAULT/AUTO → 白名单 → 规则匹配 → 风险评估 → 允许/提示/拒绝

    使用示例:
        guard = PermissionGuard(current_level=PermissionLevel.DEFAULT)
        action = ProposedAction(
            action_type=ActionType.FILE_CREATE,
            target="/path/to/file.py",
            description="创建新模块",
            source_worker_id="arch-abc",
            source_role_id="architect",
        )
        decision = guard.check(action)
        if decision.outcome == DecisionOutcome.PROMPT:
            print(f"需用户确认: {decision.reason}")
    """

    LEVEL_ORDER = {
        PermissionLevel.PLAN: 0,
        PermissionLevel.DEFAULT: 1,
        PermissionLevel.AUTO: 2,
        PermissionLevel.BYPASS: 3,
    }

    def __init__(self,
                 current_level: PermissionLevel = PermissionLevel.DEFAULT,
                 rules: Optional[List[PermissionRule]] = None,
                 audit_log: bool = True,
                 session_id: Optional[str] = None):
        """
        初始化权限守卫

        Args:
            current_level: 当前安全级别（默认 DEFAULT）
            rules: 自定义规则列表（为空则使用 30 条内置默认规则）
            audit_log: 是否启用审计日志记录
            session_id: 会话标识（用于审计追踪，自动生成如未提供）
        """
        self.current_level = current_level
        self.rules: List[PermissionRule] = rules or _build_default_rules()
        self._rule_index: Dict[str, int] = {
            r.rule_id: i for i, r in enumerate(self.rules)
        }
        self._rules_by_type: Dict[ActionType, List[PermissionRule]] = {}
        for r in self.rules:
            self._rules_by_type.setdefault(r.action_type, []).append(r)
        self.audit_log_enabled = audit_log
        self._audit_log: List[AuditEntry] = []
        self._whitelist: Set[str] = set()
        self._lock = threading.RLock()
        self.session_id = session_id or f"sess-{uuid.uuid4().hex[:8]}"

    def check(self, action: ProposedAction) -> PermissionDecision:
        """
        核心权限检查方法 - 对操作提案进行安全决策

        决策流程（按优先级）:
        1. BYPASS 级别 → 直接 ALLOWED
        2. PLAN 级别 → 只读允许 / 写入 DENIED
        3. 白名单匹配 → 直接 ALLOWED
        4. 规则匹配 → 结合风险评分决策:
           - 风险 < 0.3 且级别充足 → ALLOWED
           - 风险 0.3~0.7 或 AUTO 模式 → 调用 auto_classify() 综合判断
           - 风险 > 0.7 → PROMPT (需用户确认)
        5. 无匹配规则 → 低风险允许 / 高风险 PROMPT

        所有决策都会记录到审计日志。

        Args:
            action: 操作提案，包含类型、目标路径、描述、来源信息等

        Returns:
            PermissionDecision: 权限决策结果，包含:
                - outcome: 最终裁决 (ALLOWED/DENIED/PROMPT/ESCALATED)
                - reason: 决策原因说明
                - matched_rule: 匹配到的规则（如有）
                - requires_confirmation: 是否需要用户确认
                - confidence: 决策置信度 [0.1, 1.0]
                - risk_score: 计算后的风险评分 [0.0, 1.0]
        """
        with self._lock:
            start = time.perf_counter()

            if self.current_level == PermissionLevel.BYPASS:
                decision = self._make_decision(action, DecisionOutcome.ALLOWED,
                                                "BYPASS模式: 跳过所有检查")
                self._record_audit(action, decision, start)
                return decision

            if self.current_level == PermissionLevel.PLAN:
                if action.action_type == ActionType.FILE_READ:
                    decision = self._make_decision(action, DecisionOutcome.ALLOWED,
                                                    "PLAN模式允许只读操作")
                else:
                    decision = self._make_decision(action, DecisionOutcome.DENIED,
                                                    f"PLAN模式禁止{action.action_type.value}操作")
                self._record_audit(action, decision, start)
                return decision

            target_str = action.target or ""
            if target_str in self._whitelist or any(
                fnmatch.fnmatch(target_str, p) for p in self._whitelist
            ):
                decision = self._make_decision(action, DecisionOutcome.ALLOWED,
                                                "白名单匹配，直接放行")
                self._record_audit(action, decision, start)
                return decision

            matched_rule = self._match_rule(action)
            base_risk = self._assess_base_risk(action)

            if matched_rule:
                rule_level_val = self.LEVEL_ORDER.get(matched_rule.required_level, 1)
                current_level_val = self.LEVEL_ORDER.get(self.current_level, 1)

                effective_risk = min(1.0, base_risk + matched_rule.risk_boost)

                if current_level_val >= rule_level_val:
                    if effective_risk < 0.3:
                        outcome = DecisionOutcome.ALLOWED
                        reason = f"规则{matched_rule.rule_id}匹配, 风险低({effective_risk:.2f})"
                    elif effective_risk < 0.7 or self.current_level == PermissionLevel.AUTO:
                        auto_score = self.auto_classify(action)
                        combined = (effective_risk + auto_score) / 2
                        if combined < 0.55:
                            outcome = DecisionOutcome.ALLOWED
                            reason = f"规则{matched_rule.rule_id}匹配, 综合风险可接受({combined:.2f})"
                        else:
                            outcome = DecisionOutcome.PROMPT
                            reason = f"规则{matched_rule.rule_id}匹配, 需确认(风险{combined:.2f})"
                    else:
                        outcome = DecisionOutcome.PROMPT
                        reason = f"规则{matched_rule.rule_id}高风险, 需用户确认(风险{effective_risk:.2f})"
                else:
                    if matched_rule.required_level == PermissionLevel.BYPASS:
                        outcome = DecisionOutcome.PROMPT
                        reason = f"BYPASS级操作需人工确认(规则{matched_rule.rule_id}, 风险{effective_risk:.2f})"
                    elif effective_risk > 0.85 and self.current_level == PermissionLevel.PLAN:
                        outcome = DecisionOutcome.DENIED
                        reason = f"当前级别不足且高风险(需{matched_rule.required_level.value}, 当前{self.current_level.value})"
                    else:
                        outcome = DecisionOutcome.PROMPT
                        reason = f"当前级别不足(需{matched_rule.required_level.value}, 当前{self.current_level.value}), 请确认"

                action.risk_score = effective_risk
                requires_conf = outcome == DecisionOutcome.PROMPT
                decision = PermissionDecision(
                    action=action,
                    outcome=outcome,
                    matched_rule=matched_rule,
                    reason=reason,
                    requires_confirmation=requires_conf,
                    confidence=max(0.1, 1.0 - effective_risk),
                )
            else:
                fallback_risk = base_risk
                action.risk_score = fallback_risk
                if fallback_risk < 0.3:
                    outcome = DecisionOutcome.ALLOWED
                    reason = "无匹配规则, 低风险默认允许"
                elif self.current_level == PermissionLevel.AUTO:
                    auto_score = self.auto_classify(action)
                    if auto_score < 0.4:
                        outcome = DecisionOutcome.ALLOWED
                        reason = f"AUTO分类安全(score={auto_score:.2f})"
                    else:
                        outcome = DecisionOutcome.PROMPT
                        reason = f"AUTO分类需确认(score={auto_score:.2f})"
                else:
                    outcome = DecisionOutcome.PROMPT
                    reason = "无匹配规则, 默认需确认"

                requires_conf = outcome == DecisionOutcome.PROMPT
                decision = PermissionDecision(
                    action=action,
                    outcome=outcome,
                    matched_rule=None,
                    reason=reason,
                    requires_confirmation=requires_conf,
                    confidence=0.7,
                )

            self._record_audit(action, decision, start)
            return decision

    def auto_classify(self, action: ProposedAction) -> float:
        """
        AI 风险分类器 - 5维加权评分模型

        对操作提案进行多维度风险评估，返回 [0.0, 1.0] 的风险分数。
        各维度及权重:
            - 目标敏感性 (30%): 路径是否包含敏感关键词/敏感路径模式
            - 破坏性 (25%): 是否包含删除/覆盖/强制等破坏性关键词
            - 作用范围 (20%): 通配符/超长目标路径
            - 来源可信度 (15%): Worker 角色是否在已知信任列表
            - 上下文合理性 (10%): 操作是否与任务相关、描述是否充分

        Args:
            action: 待评估的操作提案

        Returns:
            float: 风险评分 [0.0, 1.0]，越高越危险
                - < 0.3: 低风险，可自动放行
                - 0.3~0.7: 中等风险，需综合判断
                - > 0.7: 高风险，建议用户确认
        """
        score = 0.0
        target_lower = (action.target or "").lower()

        dim_sensitivity = self._dim_target_sensitivity(target_lower)
        dim_destructive = self._dim_destructiveness(action)
        dim_scope = self._dim_scope(action.target or "")
        dim_source = self._dim_source_trust(action.source_role_id)
        dim_context = self._dim_context_reasonable(action)

        weights = [0.30, 0.25, 0.20, 0.15, 0.10]
        dims = [dim_sensitivity, dim_destructive, dim_scope, dim_source, dim_context]
        score = sum(w * d for w, d in zip(weights, dims))
        return max(0.0, min(1.0, score))

    def _match_rule(self, action: ProposedAction) -> Optional[PermissionRule]:
        best_match = None
        best_strictness = -1
        candidates = self._rules_by_type.get(action.action_type, [])
        for rule in candidates:
            if not rule.enabled:
                continue
            if self._pattern_match(rule.pattern, action.target or ""):
                strictness = self.LEVEL_ORDER.get(rule.required_level, 0)
                if strictness > best_strictness:
                    best_match = rule
                    best_strictness = strictness
        return best_match

    def _pattern_match(self, pattern: str, target: str) -> bool:
        if not target:
            return False
        try:
            if fnmatch.fnmatch(target, pattern):
                return True
            if target.startswith(pattern.rstrip("*")):
                return True
            if re.search(pattern, target, re.IGNORECASE):
                return True
        except (re.error, TypeError):
            pass
        if pattern.endswith("*") and target.startswith(pattern[:-1]):
            return True
        return False

    def _assess_base_risk(self, action: ProposedAction) -> float:
        risk = 0.0
        target = action.target or ""

        for kw in _SENSITIVE_KEYWORDS:
            if kw.lower() in target.lower():
                risk += 0.15

        for pat in _SENSITIVE_PATH_PATTERNS:
            if re.search(pat, target, re.IGNORECASE):
                risk += 0.25

        high_risk_actions = {
            ActionType.FILE_DELETE: 0.4,
            ActionType.SHELL_EXECUTE: 0.3,
            ActionType.PROCESS_SPAWN: 0.35,
            ActionType.ENVIRONMENT: 0.3,
        }
        risk += high_risk_actions.get(action.action_type, 0.0)

        if len(target) < 3 and action.action_type != ActionType.FILE_READ:
            risk += 0.1

        return min(1.0, risk)

    def _dim_target_sensitivity(self, target_lower: str) -> float:
        score = 0.0
        for kw in _SENSITIVE_KEYWORDS:
            if kw in target_lower:
                score += 0.2
        for pat in _SENSITIVE_PATH_PATTERNS:
            if re.search(pat, target_lower):
                score += 0.3
        return min(1.0, score)

    def _dim_destructiveness(self, action: ProposedAction) -> float:
        destructive_keywords = ["rm ", "rm-", "delete", "drop", "truncate", "overwrite",
                               "force", "-f", "--force", "clear", "reset", "sudo"]
        content = ((action.target or "") + " " + (action.description or "")).lower()
        count = sum(1 for kw in destructive_keywords if kw in content)
        base = min(1.0, count * 0.25)
        if action.action_type == ActionType.SHELL_EXECUTE and count > 0:
            base = min(1.0, base + 0.2)
        return base

    def _dim_scope(self, target: str) -> float:
        if "*" in target or "?" in target:
            return 0.6
        if len(target) > 200:
            return 0.4
        return 0.1

    def _dim_source_trust(self, role_id: Optional[str]) -> float:
        known_roles = {"architect", "product-manager", "tester",
                       "solo-coder", "ui-designer", "devops"}
        if role_id and role_id in known_roles:
            return 0.1
        return 0.5

    def _dim_context_reasonable(self, action: ProposedAction) -> bool:
        if action.metadata.get("task_related"):
            return 0.1
        if action.description and len(action.description) > 20:
            return 0.2
        return 0.4

    def _make_decision(self, action: ProposedAction,
                       outcome: DecisionOutcome, reason: str) -> PermissionDecision:
        return PermissionDecision(
            action=action,
            outcome=outcome,
            reason=reason,
            confidence=1.0 if outcome != DecisionOutcome.ESCALATED else 0.5,
        )

    def _record_audit(self, action: ProposedAction,
                      decision: PermissionDecision, start_time: float):
        if not self.audit_log_enabled:
            return
        duration_ms = int((time.perf_counter() - start_time) * 1000)
        entry = AuditEntry(
            action=action,
            decision=decision,
            duration_ms=duration_ms,
            guard_level=self.current_level,
            session_id=self.session_id,
        )
        self._audit_log.append(entry)
        if len(self._audit_log) > 10000:
            self._audit_log = self._audit_log[-5000:]

    def add_rule(self, rule: PermissionRule) -> None:
        """
        添加或更新权限规则

        如规则 ID 已存在则更新（替换原规则），否则追加到规则列表。
        同时维护按操作类型分组的索引以加速匹配。

        Args:
            rule: 要添加的权限规则（含 rule_id, action_type, pattern 等）
        """
        with self._lock:
            if rule.rule_id in self._rule_index:
                idx = self._rule_index[rule.rule_id]
                old_type = self.rules[idx].action_type
                if old_type != rule.action_type:
                    type_list = self._rules_by_type.get(old_type, [])
                    if rule in type_list:
                        type_list.remove(rule)
                    self._rules_by_type.setdefault(rule.action_type, []).append(rule)
                self.rules[idx] = rule
            else:
                self._rule_index[rule.rule_id] = len(self.rules)
                self.rules.append(rule)
                self._rules_by_type.setdefault(rule.action_type, []).append(rule)

    def remove_rule(self, rule_id: str) -> bool:
        """
        按ID移除权限规则

        Args:
            rule_id: 要移除的规则标识符

        Returns:
            bool: 是否成功移除（False 表示规则不存在）
        """
        with self._lock:
            if rule_id not in self._rule_index:
                return False
            idx = self._rule_index.pop(rule_id)
            removed = self.rules.pop(idx)
            type_list = self._rules_by_type.get(removed.action_type, [])
            if removed in type_list:
                type_list.remove(removed)
            self._rule_index = {r.rule_id: i for i, r in enumerate(self.rules)}
            return True

    def set_level(self, level: PermissionLevel) -> None:
        """
        动态切换安全级别

        可在运行时提升/降低安全级别，无需重新创建实例。
        典型场景：进入 Plan Mode 时切换为 PLAN 级别。

        Args:
            level: 目标安全级别
        """
        self.current_level = level

    def get_audit_log(self,
                      since: Optional[datetime] = None,
                      until: Optional[datetime] = None,
                      action_type: Optional[ActionType] = None,
                      outcome: Optional[DecisionOutcome] = None,
                      worker_id: Optional[str] = None,
                      limit: Optional[int] = None) -> List[AuditEntry]:
        """
        查询审计日志（支持多维度过滤）

        Args:
            since: 起始时间（含）
            until: 截止时间（含）
            action_type: 按操作类型过滤
            outcome: 按决策结果过滤
            worker_id: 按 Worker ID 过滤
            limit: 最大返回条数

        Returns:
            List[AuditEntry]: 匹配的审计条目列表
        """
        results = self._audit_log
        if since:
            results = [e for e in results if e.timestamp >= since]
        if until:
            results = [e for e in results if e.timestamp <= until]
        if action_type:
            results = [e for e in results
                       if e.action and e.action.action_type == action_type]
        if outcome:
            results = [e for e in results
                       if e.decision and e.decision.outcome == outcome]
        if worker_id:
            results = [e for e in results
                       if e.action and e.action.source_worker_id == worker_id]
        if limit is not None:
            results = results[:limit]
        return list(results)

    def get_security_report(self) -> Dict[str, Any]:
        """
        生成安全报告摘要

        聚合所有审计日志数据，计算统计指标:
        - 各决策结果的计数和占比
        - 平均风险评分
        - 最常被拒绝的操作目标 (Top 5)
        - 当前规则数和白名单数

        Returns:
            Dict[str, Any]: 安全报告字典
        """
        total = len(self._audit_log)
        allowed = sum(1 for e in self._audit_log
                     if e.decision and e.decision.outcome == DecisionOutcome.ALLOWED)
        denied = sum(1 for e in self._audit_log
                    if e.decision and e.decision.outcome == DecisionOutcome.DENIED)
        prompted = sum(1 for e in self._audit_log
                       if e.decision and e.decision.outcome == DecisionOutcome.PROMPT)
        escalated = sum(1 for e in self._audit_log
                         if e.decision and e.decision.outcome == DecisionOutcome.ESCALATED)

        avg_risk = 0.0
        if total > 0:
            risks = [e.action.risk_score for e in self._audit_log if e.action]
            avg_risk = sum(risks) / len(risks) if risks else 0.0

        denied_targets: Dict[str, int] = {}
        for e in self._audit_log:
            if e.decision and e.decision.outcome == DecisionOutcome.DENIED and e.action:
                t = e.action.target or "unknown"
                denied_targets[t] = denied_targets.get(t, 0) + 1
        top_denied = sorted(denied_targets.items(), key=lambda x: x[1], reverse=True)[:5]

        return {
            "total_checks": total,
            "allowed": allowed,
            "denied": denied,
            "prompted": prompted,
            "escalated": escalated,
            "avg_risk_score": round(avg_risk, 3),
            "top_denied_actions": top_denied,
            "guard_level": self.current_level.value,
            "rules_count": len(self.rules),
            "whitelist_count": len(self._whitelist),
        }

    def add_whitelist(self, pattern: str) -> None:
        """将模式加入白名单（匹配时直接放行，跳过规则检查）"""
        self._whitelist.add(pattern)

    def remove_whitelist(self, pattern: str) -> None:
        """从白名单中移除指定模式"""
        self._whitelist.discard(pattern)

    def get_whitelist(self) -> Set[str]:
        """
        获取当前白名单集合

        Returns:
            Set[str]: 白名单模式集合的副本
        """
        return set(self._whitelist)

    def export_rules(self) -> List[Dict]:
        """
        导出所有启用的规则为字典列表

        Returns:
            List[Dict]: 每条规则的 to_dict() 序列化结果
        """
        return [r.to_dict() for r in self.rules if r.enabled]

    def import_rules(self, rules_data: List[Dict]) -> int:
        """
        从字典列表批量导入规则

        跳过格式无效的条目，返回成功导入的数量。

        Args:
            rules_data: 规则字典列表（每项需含 rule_id, action_type, pattern, required_level）

        Returns:
            int: 成功导入的规则数量
        """
        count = 0
        for rd in rules_data:
            try:
                rule = PermissionRule.from_dict(rd)
                self.add_rule(rule)
                count += 1
            except (KeyError, ValueError):
                continue
        return count

    def export_state(self) -> Dict:
        """
        导出完整状态快照

        包含当前级别、所有规则、白名单、会话ID和审计计数。
        可用于持久化或跨实例迁移。

        Returns:
            Dict: 完整状态字典
        """
        with self._lock:
            return {
                "current_level": self.current_level.value,
                "rules": [r.to_dict() for r in self.rules],
                "whitelist": list(self._whitelist),
                "session_id": self.session_id,
                "audit_count": len(self._audit_log),
            }

    def clear_audit_log(self) -> int:
        """
        清空审计日志

        Returns:
            int: 清空前日志中的条目数
        """
        with self._lock:
            count = len(self._audit_log)
            self._audit_log.clear()
            return count
