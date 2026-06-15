"""Security Audit Skill - V3.7.0

Encapsulates security components for comprehensive task auditing:
  - InputValidator: 21 pattern injection detection
  - OperationClassifier: Three-tier operation classification
  - PermissionGuard: Four-level permission control

Provides unified audit interface for secure multi-agent collaboration.
"""

from typing import Any

from scripts.collaboration.input_validator import InputValidator
from scripts.collaboration.operation_classifier import (
    OperationCategory,
    OperationClassifier,
)
from scripts.collaboration.permission_guard import (
    ActionType,
    PermissionGuard,
    PermissionLevel,
    ProposedAction,
)
from skills.registry import BaseSkill


class SecuritySkill(BaseSkill):
    """Security audit skill combining injection detection, operation classification, and permission control."""

    name = "security"
    description = "Security auditing: injection detection, operation classification, permission control (V3.7.0)"
    version = "3.7.0"

    INJECTION_PATTERNS_COUNT = 21
    INJECTION_CATEGORIES = {
        "instruction_override": [
            "ignore previous instructions",
            "forget previous context",
            "disregard above",
        ],
        "role_jacking": [
            "you are now a different role",
            "new instructions",
            "override settings",
        ],
        "system_prompt_leak": [
            "reveal your instructions",
            "show system prompt",
            "what are your instructions",
        ],
        "persona_adoption": [
            "pretend you are",
            "act as if you are",
            "jailbreak",
        ],
        "privilege_escalation": [
            "developer mode",
            "sudo mode",
            "DAN mode",
        ],
        "multilingual_injection": [
            "Chinese injection patterns",
            "Japanese injection patterns",
        ],
    }

    OPERATION_LEVELS = {
        OperationCategory.ALWAYS_SAFE: {
            "label": "ALWAYS_SAFE",
            "description": "Read-only operations auto-approved at most levels",
            "examples": ["read_config", "read_file", "query_status"],
            "default_action": "Auto-approve",
        },
        OperationCategory.NEEDS_REVIEW: {
            "label": "NEEDS_REVIEW",
            "description": "Write operations requiring confirmation or AI risk assessment",
            "examples": ["write_file", "call_llm", "git_operation"],
            "default_action": "Request confirmation",
        },
        OperationCategory.FORBIDDEN: {
            "label": "FORBIDDEN",
            "description": "Dangerous operations blocked unless BYPASS level override",
            "examples": ["delete_file", "execute_shell", "access_secrets"],
            "default_action": "Block or escalate",
        },
    }

    PERMISSION_LEVELS = {
        PermissionLevel.PLAN: {
            "order": 0,
            "label": "PLAN",
            "description": "Read-only mode - all write operations denied",
            "use_case": "Analysis, research, design tasks",
            "risk_tolerance": "Zero write risk",
        },
        PermissionLevel.DEFAULT: {
            "order": 1,
            "label": "DEFAULT",
            "description": "Standard mode - dangerous operations require user confirmation",
            "use_case": "Standard coding tasks",
            "risk_tolerance": "Medium - confirmation required",
        },
        PermissionLevel.AUTO: {
            "order": 2,
            "label": "AUTO",
            "description": "AI-judged safe operations with guardrails and whitelist",
            "use_case": "Trusted contexts with automated safeguards",
            "risk_tolerance": "Medium-high - AI assessment",
        },
        PermissionLevel.BYPASS: {
            "order": 3,
            "label": "BYPASS",
            "description": "Skip all checks - highest trust level for controlled environments only",
            "use_case": "Sensitive operations requiring manual auth",
            "risk_tolerance": "Full trust - manual oversight",
        },
    }

    def __init__(self):
        self._validator = InputValidator(strict_mode=False)
        self._classifier = OperationClassifier()
        self._guard = PermissionGuard(current_level=PermissionLevel.DEFAULT)

    def scan_input(self, text: str) -> dict[str, Any]:
        """
        Scan input for prompt injection patterns using InputValidator.

        Detects 21 injection patterns across categories:
          - Instruction override attempts
          - Role/persona jacking
          - System prompt extraction
          - Privilege escalation
          - Multilingual injection vectors

        Args:
            text: Input text to scan for injection patterns

        Returns:
            Dict with detection results:
                - is_safe: Boolean indicating if input passed validation
                - injection_patterns: List of detected injection patterns
                - suspicious_patterns: List of suspicious but non-blocking patterns
                - risk_level: low/medium/high/critical
                - details: Full validation result from InputValidator
        """
        if not text or not isinstance(text, str):
            return {
                "is_safe": False,
                "injection_patterns": [],
                "suspicious_patterns": [],
                "risk_level": "critical",
                "details": {"reason": "Invalid input type or empty text"},
            }

        injection_detected = self._validator.check_prompt_injection(text)
        suspicious_detected = self._validator.check_suspicious_patterns(text)

        full_validation = self._validator.validate_task(text)

        pattern_count = len(injection_detected) + len(suspicious_detected)

        if pattern_count == 0:
            risk_level = "low"
        elif len(injection_detected) == 0 and len(suspicious_detected) <= 2:
            risk_level = "medium"
        elif len(injection_detected) <= 3:
            risk_level = "high"
        else:
            risk_level = "critical"

        return {
            "is_safe": full_validation.valid,
            "injection_patterns": injection_detected,
            "suspicious_patterns": suspicious_detected,
            "pattern_count": pattern_count,
            "total_patterns_available": self.INJECTION_PATTERNS_COUNT,
            "risk_level": risk_level,
            "sanitized_input": full_validation.sanitized_input,
            "details": {
                "valid": full_validation.valid,
                "reason": full_validation.reason,
            },
        }

    def classify_operation(
        self,
        operation: str,
        target: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Classify an operation into three-tier category using OperationClassifier.

        Categories:
          - ALWAYS_SAFE: Auto-approved read-only ops
          - NEEDS_REVIEW: Write ops needing confirmation
          - FORBIDDEN: Dangerous blocked ops

        Args:
            operation: Operation identifier (e.g., "write_file", "delete_file")
            target: Optional target path/URL for context
            context: Additional context (source_role, etc.)

        Returns:
            Dict with classification result:
                - category: ALWAYS_SAFE/NEEDS_REVIEW/FORBIDDEN
                - description: Human-readable operation description
                - risk_factors: List of identified risk factors
                - requires_confirmation: Whether user must confirm
                - override_allowed: Whether override is possible
        """
        classified = self._classifier.classify(
            operation_id=operation,
            target=target,
            context=context,
        )

        return {
            **classified.to_dict(),
            "level_info": self.OPERATION_LEVELS.get(classified.category, {}),
        }

    def check_permissions(
        self,
        action: str,
        user_role: str = "viewer",
        target: str | None = None,
        description: str = "",
    ) -> dict[str, Any]:
        """
        Check permissions for an action using PermissionGuard four-level system.

        Levels (low to high):
          - PLAN (0): Read-only, writes denied
          - DEFAULT (1): Confirmation required for dangerous ops
          - AUTO (2): AI classifier + whitelist
          - BYPASS (3): Skip all checks

        Args:
            action: Action type string (file_read/file_write/delete/shell/etc.)
            user_role: User role identifier (default: "viewer")
            target: Optional target path/URL
            description: Action description for audit trail

        Returns:
            Dict with permission decision:
                - outcome: ALLOWED/DENIED/PROMPT/ESCALATED
                - reason: Decision explanation
                - requires_confirmation: Whether user must confirm
                - confidence: Decision confidence [0.1, 1.0]
                - risk_score: Calculated risk [0.0, 1.0]
                - current_level: Current permission level
        """
        action_type_map = {
            "file_read": ActionType.FILE_READ,
            "file_create": ActionType.FILE_CREATE,
            "file_write": ActionType.FILE_MODIFY,
            "file_modify": ActionType.FILE_MODIFY,
            "file_delete": ActionType.FILE_DELETE,
            "shell": ActionType.SHELL_EXECUTE,
            "shell_execute": ActionType.SHELL_EXECUTE,
            "network": ActionType.NETWORK_REQUEST,
            "network_request": ActionType.NETWORK_REQUEST,
            "git": ActionType.GIT_OPERATION,
            "git_operation": ActionType.GIT_OPERATION,
            "env": ActionType.ENVIRONMENT,
            "environment": ActionType.ENVIRONMENT,
            "process": ActionType.PROCESS_SPAWN,
            "process_spawn": ActionType.PROCESS_SPAWN,
        }

        action_type = action_type_map.get(action.lower(), ActionType.FILE_READ)

        proposed = ProposedAction(
            action_type=action_type,
            target=target or "",
            description=description,
            source_role_id=user_role,
        )

        decision = self._guard.check(proposed)

        return {
            **decision.to_dict(),
            "current_level": self._guard.current_level.value,
            "level_info": self.PERMISSION_LEVELS.get(self._guard.current_level, {}),
        }

    def audit_task(self, task_description: str) -> dict[str, Any]:
        """
        Comprehensive security audit combining all three checks.

        Performs:
          1. Injection detection on task description
          2. Operation classification (extracts operations from text)
          3. Permission check simulation

        Args:
            task_description: Task description to audit comprehensively

        Returns:
            Dict with complete audit report:
                - overall_status: PASS/WARN/FAIL/BLOCK
                - injection_scan: Results from scan_input()
                - operations_found: List of classified operations extracted from task
                - permission_summary: Summary of permission requirements
                - recommendations: List of security recommendations
                - audit_metadata: Timestamp, version, etc.
        """
        from datetime import datetime

        injection_result = self.scan_input(task_description)

        operations_found = []
        operation_keywords = {
            "read_file": ["read", "open", "load", "view", "display"],
            "write_file": ["write", "save", "create", "generate", "output"],
            "modify_file": ["modify", "edit", "update", "change", "refactor"],
            "delete_file": ["delete", "remove", "clean", "purge"],
            "execute_shell": ["run", "execute", "command", "shell", "script"],
            "network_request": ["fetch", "download", "upload", "api", "http", "request"],
            "git_operation": ["commit", "push", "pull", "merge", "branch"],
            "access_secrets": ["secret", "password", "credential", "api_key", "token"],
        }

        task_lower = task_description.lower()
        for op_id, keywords in operation_keywords.items():
            if any(kw in task_lower for kw in keywords):
                classified = self.classify_operation(operation=op_id)
                operations_found.append(
                    {
                        "operation_id": op_id,
                        **classified,
                    }
                )

        permission_summary = {
            "min_required_level": "DEFAULT",
            "requires_confirmation": any(op.get("requires_confirmation") for op in operations_found),
            "forbidden_operations": [
                op["operation_id"] for op in operations_found if op.get("category") == "forbidden"
            ],
            "safe_operations": [op["operation_id"] for op in operations_found if op.get("category") == "always_safe"],
        }

        if permission_summary["forbidden_operations"]:
            permission_summary["min_required_level"] = "BYPASS"

        recommendations = []

        if not injection_result["is_safe"]:
            recommendations.append(
                f"⚠️ BLOCK: {len(injection_result['injection_patterns'])} injection pattern(s) detected - "
                "task rejected for safety"
            )
            overall_status = "BLOCK"

        elif injection_result["risk_level"] in ("high", "critical"):
            recommendations.append(
                f"⚠️ WARN: High-risk injection indicators found ({injection_result['pattern_count']} patterns)"
            )
            overall_status = "WARN"

        elif permission_summary["forbidden_operations"]:
            forbidden_list = ", ".join(permission_summary["forbidden_operations"])
            recommendations.append(f"🚫 FAIL: Forbidden operation(s) detected: {forbidden_list}")
            overall_status = "FAIL"

        elif permission_summary["requires_confirmation"]:
            review_ops = [op["operation_id"] for op in operations_found if op.get("category") == "needs_review"]
            if review_ops:
                recommendations.append(
                    f"✅ PASS: Task contains operations requiring confirmation: {', '.join(review_ops[:5])}"
                )
            else:
                recommendations.append("✅ PASS: No security issues detected")
            overall_status = "PASS"

        else:
            recommendations.append("✅ PASS: Task appears safe for execution")
            overall_status = "PASS"

        if len(operations_found) == 0:
            recommendations.append("ℹ️ INFO: No specific operations detected in task description")

        return {
            "overall_status": overall_status,
            "injection_scan": injection_result,
            "operations_found": operations_found,
            "operation_count": len(operations_found),
            "permission_summary": permission_summary,
            "recommendations": recommendations,
            "audit_metadata": {
                "timestamp": datetime.now().isoformat(),
                "skill_version": self.version,
                "task_length": len(task_description),
            },
        }

    def run(self, *args, **kwargs):
        """
        Main entry point for the security skill.

        Supports multiple calling patterns:

        1. Input scanning: run(mode="scan", text="...")
        2. Operation classification: run(mode="classify", operation="...")
        3. Permission check: run(mode="check", action="...", user_role="...")
        4. Full audit: run(mode="audit", task_description="...") or default
        """
        mode = kwargs.get("mode", "audit")

        if mode == "scan":
            text = kwargs.get("text", "") or kwargs.get("input", "")
            return self.scan_input(text)

        elif mode == "classify":
            operation = kwargs.get("operation", "")
            target = kwargs.get("target")
            context = kwargs.get("context")
            return self.classify_operation(operation=operation, target=target, context=context)

        elif mode == "check":
            action = kwargs.get("action", "")
            user_role = kwargs.get("user_role", "viewer")
            target = kwargs.get("target")
            description = kwargs.get("description", "")
            return self.check_permissions(
                action=action,
                user_role=user_role,
                target=target,
                description=description,
            )

        else:
            task = (
                kwargs.get("task_description", "")
                or kwargs.get("task", "")
                or kwargs.get("text", "")
                or (str(args[0]) if args else "")
            )

            return self.audit_task(task_description=task)
