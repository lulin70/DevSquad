#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OperationCategory Extension for PermissionGuard (P1-2)

Adds three-tier operation classification to existing 4-level permission model:
  - ALWAYS_SAFE: Read-only, local queries (auto-approved at most levels)
  - NEEDS_REVIEW: Write ops, external API calls (requires confirmation or AI check)
  - FORBIDDEN: Dangerous ops (delete, secrets, eval) (denied unless BYPASS)

Spec reference: SPEC_V35_Agent_Skills_Quality_Framework.md Section 7.2
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class OperationCategory(Enum):
    """
    Three-tier operation classification for fine-grained permission control.

    Hierarchy:
      ALWAYS_SAFE → Auto-approved at DEFAULT/AUTO levels
      NEEDS_REVIEW → Requires explicit approval or AI risk assessment
      FORBIDDEN     → Blocked unless BYPASS level + explicit override
    """
    ALWAYS_SAFE = "always_safe"
    NEEDS_REVIEW = "needs_review"
    FORBIDDEN = "forbidden"


# Default classification mapping for common operations
OPERATION_CLASSIFICATION: Dict[str, OperationCategory] = {
    # === Always Safe Operations ===
    "read_config": OperationCategory.ALWAYS_SAFE,
    "read_file": OperationCategory.ALWAYS_SAFE,
    "read_scratchpad": OperationCategory.ALWAYS_SAFE,
    "list_directory": OperationCategory.ALWAYS_SAFE,
    "query_status": OperationCategory.ALWAYS_SAFE,
    "get_role_info": OperationCategory.ALWAYS_SAFE,
    "validate_input": OperationCategory.ALWAYS_SAFE,

    # === Needs Review Operations ===
    "write_scratchpad": OperationCategory.NEEDS_REVIEW,
    "write_file": OperationCategory.NEEDS_REVIEW,
    "create_file": OperationCategory.NEEDS_REVIEW,
    "modify_file": OperationCategory.NEEDS_REVIEW,
    "call_llm": OperationCategory.NEEDS_REVIEW,
    "network_request": OperationCategory.NEEDS_REVIEW,
    "git_operation": OperationCategory.NEEDS_REVIEW,
    "modify_config": OperationCategory.NEEDS_REVIEW,
    "install_template": OperationCategory.NEEDS_REVIEW,
    "publish_template": OperationCategory.NEEDS_REVIEW,

    # === Forbidden Operations ===
    "delete_file": OperationCategory.FORBIDDEN,
    "execute_shell": OperationCategory.FORBIDDEN,
    "access_secrets": OperationCategory.FORBIDDEN,
    "eval_code": OperationCategory.FORBIDDEN,
    "import_module": OperationCategory.FORBIDDEN,
    "spawn_process": OperationCategory.FORBIDDEN,
    "modify_system_path": OperationCategory.FORBIDDEN,
    "environment_write": OperationCategory.FORBIDDEN,
}


@dataclass
class ClassifiedOperation:
    """An operation with its category classification."""
    operation_id: str
    category: OperationCategory
    description: str
    risk_factors: List[str]
    requires_confirmation: bool
    override_allowed: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "category": self.category.value,
            "description": self.description,
            "risk_factors": self.risk_factors,
            "requires_confirmation": self.requires_confirmation,
            "override_allowed": self.override_allowed,
        }


class OperationClassifier:
    """
    Classifies operations into three-tier categories.

    Usage:
        classifier = OperationClassifier()
        classified = classifier.classify("delete_file", "/tmp/important.txt")
        if classified.category == OperationCategory.FORBIDDEN:
            # Block or escalate
            pass
    """

    def __init__(
        self,
        custom_classifications: Optional[Dict[str, OperationCategory]] = None,
        strict_mode: bool = False,
    ):
        """
        Initialize classifier.

        Args:
            custom_classifications: Override default classifications
            strict_mode: If True, unknown operations are classified as FORBIDDEN
                           If False (default), unknown operations are NEEDS_REVIEW
        """
        self._classifications = dict(OPERATION_CLASSIFICATION)
        if custom_classifications:
            self._classifications.update(custom_classifications)
        self._strict_mode = strict_mode

    def classify(
        self,
        operation_id: str,
        target: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ClassifiedOperation:
        """
        Classify an operation into a category.

        Args:
            operation_id: The operation identifier
            target: Optional target path/URL for context
            context: Additional context (source role, etc.)

        Returns:
            ClassifiedOperation with full details
        """
        base_category = self._classifications.get(operation_id)

        if base_category is None:
            if self._strict_mode:
                base_category = OperationCategory.FORBIDDEN
            else:
                base_category = OperationCategory.NEEDS_REVIEW

        description = self._get_description(operation_id)
        risk_factors = self._assess_risk_factors(operation_id, target, context)

        return ClassifiedOperation(
            operation_id=operation_id,
            category=base_category,
            description=description,
            risk_factors=risk_factors,
            requires_confirmation=(
                base_category == OperationCategory.NEEDS_REVIEW or
                base_category == OperationCategory.FORBIDDEN
            ),
            override_allowed=base_category != OperationCategory.FORBIDDEN,
        )

    def batch_classify(
        self,
        operations: List[Dict[str, Any]],
    ) -> List[ClassifiedOperation]:
        """
        Classify multiple operations at once.

        Args:
            operations: List of dicts with 'operation_id' and optional 'target', 'context'

        Returns:
            List of ClassifiedOperation results
        """
        return [
            self.classify(
                op.get('operation_id', ''),
                op.get('target'),
                op.get('context'),
            )
            for op in operations
        ]

    def is_allowed(
        self,
        operation_id: str,
        permission_level: str = "DEFAULT",
        target: Optional[str] = None,
    ) -> tuple:
        """
        Quick check if operation is allowed at given permission level.

        Returns:
            (allowed: bool, reason: str)
        """
        classified = self.classify(operation_id, target)

        if classified.category == OperationCategory.ALWAYS_SAFE:
            return True, "Operation is always safe"

        if classified.category == OperationCategory.FORBIDDEN:
            if permission_level.upper() == "BYPASS":
                return True, "Allowed via BYPASS override"
            return False, f"Operation '{operation_id}' is forbidden"

        if classified.category == OperationCategory.NEEDS_REVIEW:
            if permission_level.upper() in ("AUTO", "BYPASS"):
                return True, f"Auto-approved at {permission_level} level"
            if permission_level.upper() == "PLAN":
                return False, "Write operations denied in PLAN mode"
            return True, "Requires user confirmation"

        return False, "Unknown category"

    def get_forbidden_operations(self) -> List[str]:
        """Return list of all operations classified as FORBIDDEN."""
        return [
            op_id
            for op_id, cat in self._classifications.items()
            if cat == OperationCategory.FORBIDDEN
        ]

    def get_review_required_operations(self) -> List[str]:
        """Return list of all operations classified as NEEDS_REVIEW."""
        return [
            op_id
            for op_id, cat in self._classifications.items()
            if cat == OperationCategory.NEEDS_REVIEW
        ]

    def add_custom_classification(
        self,
        operation_id: str,
        category: OperationCategory,
    ):
        """Add or update custom operation classification."""
        self._classifications[operation_id] = category

    def _get_description(self, operation_id: str) -> str:
        descriptions = {
            "read_config": "Read configuration values",
            "write_file": "Write or modify file contents",
            "delete_file": "Delete file from filesystem",
            "execute_shell": "Execute shell command",
            "call_llm": "Call LLM API for inference",
            "access_secrets": "Access secret keys or credentials",
            "eval_code": "Evaluate arbitrary code string",
            "read_scratchpad": "Read shared scratchpad data",
            "write_scratchpad": "Write to shared scratchpad",
        }
        return descriptions.get(operation_id, f"Operation: {operation_id}")

    def _assess_risk_factors(
        self,
        operation_id: str,
        target: Optional[str],
        context: Optional[Dict[str, Any]],
    ) -> List[str]:
        factors = []
        category = self._classifications.get(operation_id, OperationCategory.NEEDS_REVIEW)

        if category == OperationCategory.FORBIDDEN:
            factors.append("High-risk operation category")

        if target:
            dangerous_patterns = ["/etc/", "/var/", ".env", "secret", "credential"]
            for pattern in dangerous_patterns:
                if pattern.lower() in target.lower():
                    factors.append(f"Target contains sensitive pattern: {pattern}")

        if context:
            source_role = context.get("source_role_id", "")
            if source_role == "solo-coder" and category == OperationCategory.FORBIDDEN:
                factors.append("Coder attempting forbidden operation")

        return factors


def create_default_classifier() -> OperationClassifier:
    """Create classifier with default classifications."""
    return OperationClassifier()


def create_strict_classifier(
    custom_classifications: Optional[Dict[str, OperationCategory]] = None,
) -> OperationClassifier:
    """Create classifier in strict mode (unknown ops = FORBIDDEN)."""
    return OperationClassifier(
        custom_classifications=custom_classifications,
        strict_mode=True,
    )
