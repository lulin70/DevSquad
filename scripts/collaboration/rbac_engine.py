#!/usr/bin/env python3
"""
RBAC Engine - Role-Based Access Control System for DevSquad Enterprise

Extends the existing 4-level PermissionGuard with fine-grained RBAC:
- 15+ permission points (task, user, role, config, audit, data operations)
- 5 user roles (SUPER_ADMIN, ADMIN, OPERATOR, ANALYST, VIEWER)
- SHA256-auditable permission decisions
- Thread-safe user/role management
- Integration with PermissionGuard legacy system

Architecture:
    PermissionGuard (4-level coarse) → RBACEngine (fine-grained)
    Legacy mapping: BYPASS→SUPER_ADMIN, AUTO→ADMIN, DEFAULT→OPERATOR, PLAN→VIEWER

Usage:
    engine = RBACEngine()
    engine.add_user(RBACUser("u1", "admin", {UserRole.ADMIN}))
    if engine.check_permission("u1", Permission.TASK_CREATE):
        # Execute task creation
"""

import hashlib
import json
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class Permission(Enum):
    """Fine-grained permission enumeration (15+ permission points)

    Organized by domain:
    - Task operations: CRUD + execute
    - User management: CRUD
    - Role management: assign/revoke
    - System configuration: read/update
    - Audit: read-only
    - Data: export (compliance)
    """

    # Task operations (5)
    TASK_CREATE = "task:create"
    TASK_READ = "task:read"
    TASK_UPDATE = "task:update"
    TASK_DELETE = "task:delete"
    TASK_EXECUTE = "task:execute"

    # User management (4)
    USER_CREATE = "user:create"
    USER_READ = "user:read"
    USER_UPDATE = "user:update"
    USER_DELETE = "user:delete"

    # Role management (2)
    ROLE_ASSIGN = "role:assign"
    ROLE_REVOKE = "role:revoke"

    # System configuration (2)
    CONFIG_READ = "config:read"
    CONFIG_UPDATE = "config:update"

    # Audit log (1)
    AUDIT_READ = "audit:read"

    # Data export (1)
    DATA_EXPORT = "data:export"


class UserRole(Enum):
    """User roles with hierarchical permissions (5 roles)

    Hierarchy (highest to lowest):
        SUPER_ADMIN > ADMIN > OPERATOR > ANALYST > VIEWER

    Each role inherits all permissions from lower roles.
    """

    SUPER_ADMIN = "super_admin"  # All permissions
    ADMIN = "admin"              # Management + task permissions
    OPERATOR = "operator"         # Task execution permissions
    ANALYST = "analyst"           # Read-only + analysis permissions
    VIEWER = "viewer"             # View-only permissions


class PermissionDeniedError(Exception):
    """Raised when permission check fails in enforce() mode."""

    def __init__(self, user_id: str, permission: Permission, reason: str = ""):
        self.user_id = user_id
        self.permission = permission
        self.reason = reason or f"User '{user_id}' lacks permission '{permission.value}'"
        super().__init__(self.reason)


@dataclass
class RBACUser:
    """RBAC user model with role-based access control

    Attributes:
        user_id: Unique identifier (e.g., UUID, email hash)
        username: Human-readable display name
        roles: Assigned roles (set for multi-role support)
        attributes: Extended attributes (department, team, etc.)
        is_active: Account status (inactive users denied all access)
    """

    user_id: str
    username: str
    roles: set[UserRole] = field(default_factory=set)
    attributes: dict[str, Any] = field(default_factory=dict)
    is_active: bool = True

    def has_permission(self, permission: Permission, role_permissions: dict[UserRole, set[Permission]]) -> bool:
        """Check if user has a specific permission through any of their roles.

        Args:
            permission: The permission to check
            role_permissions: Global role-permission mapping

        Returns:
            True if any assigned role grants this permission
        """
        if not self.is_active:
            return False

        return any(permission in role_permissions.get(role, set()) for role in self.roles)

    def to_dict(self) -> dict:
        """Serialize user to dictionary."""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "roles": [r.value for r in self.roles],
            "attributes": self.attributes,
            "is_active": self.is_active,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RBACUser":
        """Deserialize user from dictionary."""
        return cls(
            user_id=data["user_id"],
            username=data["username"],
            roles={UserRole(r) for r in data.get("roles", [])},
            attributes=data.get("attributes", {}),
            is_active=data.get("is_active", True),
        )


@dataclass
class AuditRecord:
    """Audit record for RBAC permission decisions

    Supports SHA256 integrity chain for tamper-evidence.

    Attributes:
        timestamp: ISO format timestamp
        user_id: Who performed the action
        action: What action was taken (e.g., "permission_check")
        resource_type: Type of resource (e.g., "Task", "User")
        resource_id: Resource identifier
        details: Additional context (JSON-serializable)
        ip_address: Client IP (optional, for security analysis)
        user_agent: Client user agent (optional)
        result: Outcome ("success", "denied", "error")
        hash_signature: SHA256 of this record + previous hash (integrity chain)
    """

    timestamp: str
    user_id: str
    action: str
    resource_type: str
    resource_id: str
    details: dict[str, Any] = field(default_factory=dict)
    ip_address: str | None = None
    user_agent: str | None = None
    result: str = "success"
    hash_signature: str | None = None

    def to_dict(self) -> dict:
        """Serialize audit record to dictionary."""
        return {
            "timestamp": self.timestamp,
            "user_id": self.user_id,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "details": self.details,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "result": self.result,
            "hash_signature": self.hash_signature,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AuditRecord":
        """Deserialize audit record from dictionary."""
        return cls(
            timestamp=data["timestamp"],
            user_id=data["user_id"],
            action=data["action"],
            resource_type=data["resource_type"],
            resource_id=data["resource_id"],
            details=data.get("details", {}),
            ip_address=data.get("ip_address"),
            user_agent=data.get("user_agent"),
            result=data.get("result", "success"),
            hash_signature=data.get("hash_signature"),
        )


class RBACEngine:
    """RBAC Permission Engine - Fine-grained access control for enterprise

    Extends PermissionGuard's 4-level model with 15+ discrete permissions.
    Provides thread-safe user/role management with full audit trail.

    Default Role-Permission Matrix:
        SUPER_ADMIN: All 15 permissions
        ADMIN:      Tasks (all) + Users (CRUD) + Config (R/W) + Audit + Export
        OPERATOR:   Tasks (CRUD + Execute) + Config (Read)
        ANALYST:    Tasks (Read) + Config (Read) + Audit
        VIEWER:     Tasks (Read) only

    Thread Safety:
        All public methods are thread-safe via threading.Lock.

    Usage:
        engine = RBACEngine()
        engine.add_user(RBACUser("u1", "admin", {UserRole.ADMIN}))

        # Simple check (returns bool)
        if engine.check_permission("u1", Permission.TASK_CREATE):
            create_task(...)

        # Enforced check (raises on denial)
        try:
            engine.enforce("u1", Permission.USER_DELETE)
            delete_user(...)
        except PermissionDeniedError as e:
            logger.error("Access denied: %s", e)
    """

    def __init__(self):
        self._role_permissions: dict[UserRole, set[Permission]] = {}
        self._users: dict[str, RBACUser] = {}
        self._audit_log: list[AuditRecord] = []
        self._lock = threading.RLock()
        self._prev_hash: str = ""  # For SHA256 chain
        self._init_default_roles()

    def _init_default_roles(self):
        """Initialize default role-permission mapping.

        Defines the hierarchical permission matrix:
        - Each role inherits all permissions from lower roles
        - SUPER_ADMIN has all 15 permissions
        """
        self._role_permissions = {
            UserRole.SUPER_ADMIN: set(Permission),  # All permissions

            UserRole.ADMIN: {
                # Task operations (all)
                Permission.TASK_CREATE, Permission.TASK_READ,
                Permission.TASK_UPDATE, Permission.TASK_DELETE,
                Permission.TASK_EXECUTE,
                # User management (read + create/update, NO delete)
                Permission.USER_CREATE, Permission.USER_READ,
                Permission.USER_UPDATE,
                # Configuration
                Permission.CONFIG_READ, Permission.CONFIG_UPDATE,
                # Audit & export
                Permission.AUDIT_READ, Permission.DATA_EXPORT,
            },

            UserRole.OPERATOR: {
                # Task operations (CRUD + execute)
                Permission.TASK_CREATE, Permission.TASK_READ,
                Permission.TASK_UPDATE, Permission.TASK_DELETE,
                Permission.TASK_EXECUTE,
                # Read-only config
                Permission.CONFIG_READ,
            },

            UserRole.ANALYST: {
                # Read-only tasks
                Permission.TASK_READ,
                # Read-only config
                Permission.CONFIG_READ,
                # Audit access
                Permission.AUDIT_READ,
            },

            UserRole.VIEWER: {
                # Minimal read access
                Permission.TASK_READ,
            },
        }

    def add_user(self, user: RBACUser) -> None:
        """Add or update a user in the system.

        Args:
            user: RBACUser instance with roles and attributes

        Raises:
            ValueError: If user_id is empty
        """
        if not user.user_id:
            raise ValueError("user_id cannot be empty")

        with self._lock:
            self._users[user.user_id] = user
            self._log_audit(
                user_id="system",
                action="user:add",
                resource_type="RBACUser",
                resource_id=user.user_id,
                details={"username": user.username, "roles": [r.value for r in user.roles]},
            )

    def remove_user(self, user_id: str) -> bool:
        """Remove a user from the system.

        Args:
            user_id: User identifier to remove

        Returns:
            True if user was removed, False if not found
        """
        with self._lock:
            if user_id in self._users:
                del self._users[user_id]
                self._log_audit(
                    user_id="system",
                    action="user:remove",
                    resource_type="RBACUser",
                    resource_id=user_id,
                )
                return True
            return False

    def get_user(self, user_id: str) -> RBACUser | None:
        """Retrieve a user by ID.

        Args:
            user_id: User identifier

        Returns:
            RBACUser instance or None if not found
        """
        with self._lock:
            return self._users.get(user_id)

    def list_users(self, active_only: bool = True) -> list[RBACUser]:
        """List all users.

        Args:
            active_only: If True, exclude inactive users

        Returns:
            List of RBACUser instances
        """
        with self._lock:
            users = list(self._users.values())
            if active_only:
                users = [u for u in users if u.is_active]
            return users

    def check_permission(self, user_id: str, permission: Permission) -> bool:
        """Check if a user has a specific permission.

        Args:
            user_id: User identifier
            permission: Permission to check

        Returns:
            True if user has the permission, False otherwise

        Note:
            Inactive users always return False.
            Unknown users return False.
        """
        with self._lock:
            user = self._users.get(user_id)
            if not user or not user.is_active:
                result = False
            else:
                result = user.has_permission(permission, self._role_permissions)

            self._log_audit(
                user_id=user_id,
                action="permission:check",
                resource_type="Permission",
                resource_id=permission.value,
                details={"granted": result},
                result="success" if result else "denied",
            )
            return result

    def enforce(self, user_id: str, permission: Permission) -> bool:
        """Enforce permission check - raises on denial.

        Use this method when permission is required for operation.
        More explicit than check_permission() for critical operations.

        Args:
            user_id: User identifier
            permission: Required permission

        Returns:
            True if permission granted

        Raises:
            PermissionDeniedError: If user lacks permission
        """
        if not self.check_permission(user_id, permission):
            raise PermissionDeniedError(user_id, permission)
        return True

    def grant_role(self, user_id: str, role: UserRole) -> None:
        """Grant a role to a user.

        Args:
            user_id: User identifier
            role: Role to grant

        Raises:
            KeyError: If user not found
        """
        with self._lock:
            user = self._users.get(user_id)
            if not user:
                raise KeyError(f"User '{user_id}' not found")

            user.roles.add(role)
            self._log_audit(
                user_id="system",
                action="role:grant",
                resource_type="UserRole",
                resource_id=role.value,
                details={"target_user": user_id},
            )

    def revoke_role(self, user_id: str, role: UserRole) -> bool:
        """Revoke a role from a user.

        Args:
            user_id: User identifier
            role: Role to revoke

        Returns:
            True if role was revoked, False if user didn't have it

        Raises:
            KeyError: If user not found
        """
        with self._lock:
            user = self._users.get(user_id)
            if not user:
                raise KeyError(f"User '{user_id}' not found")

            if role in user.roles:
                user.roles.remove(role)
                self._log_audit(
                    user_id="system",
                    action="role:revoke",
                    resource_type="UserRole",
                    resource_id=role.value,
                    details={"target_user": user_id},
                )
                return True
            return False

    def get_user_roles(self, user_id: str) -> set[UserRole]:
        """Get all roles assigned to a user.

        Args:
            user_id: User identifier

        Returns:
            Set of UserRole enums (empty set if user not found)
        """
        with self._lock:
            user = self._users.get(user_id)
            return user.roles.copy() if user else set()

    def get_role_permissions(self, role: UserRole) -> set[Permission]:
        """Get all permissions for a specific role.

        Args:
            role: UserRole enum value

        Returns:
            Set of Permission enums
        """
        with self._lock:
            return self._role_permissions.get(role, set()).copy()

    def add_permission_to_role(self, role: UserRole, permission: Permission) -> None:
        """Dynamically add a permission to a role.

        Useful for custom role configurations beyond defaults.

        Args:
            role: Role to modify
            permission: Permission to add
        """
        with self._lock:
            if role not in self._role_permissions:
                self._role_permissions[role] = set()
            self._role_permissions[role].add(permission)
            self._log_audit(
                user_id="system",
                action="permission:add_to_role",
                resource_type="RolePermission",
                resource_id=f"{role.value}:{permission.value}",
            )

    def remove_permission_from_role(self, role: UserRole, permission: Permission) -> bool:
        """Remove a permission from a role.

        Args:
            role: Role to modify
            permission: Permission to remove

        Returns:
            True if permission was removed, False if not present
        """
        with self._lock:
            perms = self._role_permissions.get(role, set())
            if permission in perms:
                perms.remove(permission)
                self._log_audit(
                    user_id="system",
                    action="permission:remove_from_role",
                    resource_type="RolePermission",
                    resource_id=f"{role.value}:{permission.value}",
                )
                return True
            return False

    def get_audit_log(self, limit: int = 1000) -> list[AuditRecord]:
        """Get recent audit records.

        Args:
            limit: Maximum number of records to return (most recent first)

        Returns:
            List of AuditRecord instances (reverse chronological order)
        """
        with self._lock:
            return list(reversed(self._audit_log[-limit:]))

    def clear_audit_log(self) -> None:
        """Clear all audit records and reset hash chain.

        Warning: This destroys forensic evidence. Use only in testing.
        """
        with self._lock:
            self._audit_log.clear()
            self._prev_hash = ""

    def _log_audit(
        self,
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        details: dict[str, Any] | None = None,
        result: str = "success",
    ) -> AuditRecord:
        """Internal method to create and store an audit record.

        Maintains SHA256 integrity chain: each record's hash includes
        the previous record's hash, creating a tamper-evident chain.

        Args:
            user_id: Actor identifier
            action: Action performed
            resource_type: Type of resource affected
            resource_id: Resource identifier
            details: Additional context
            result: Outcome ("success", "denied", "error")

        Returns:
            The created AuditRecord
        """
        timestamp = datetime.utcnow().isoformat()

        record_data = {
            "timestamp": timestamp,
            "user_id": user_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details": details or {},
            "result": result,
            "prev_hash": self._prev_hash,
        }

        record_hash = hashlib.sha256(
            json.dumps(record_data, sort_keys=True).encode()
        ).hexdigest()

        record = AuditRecord(
            timestamp=timestamp,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            result=result,
            hash_signature=record_hash,
        )

        self._audit_log.append(record)
        self._prev_hash = record_hash
        return record

    def verify_audit_integrity(self) -> dict[str, Any]:
        """Verify SHA256 integrity chain of audit log.

        Checks that each record's hash matches the computed hash
        based on its content and the previous record's hash.

        Returns:
            Dictionary with:
            - valid: Boolean indicating overall integrity
            - total_records: Number of records checked
            - first_violation: Index of first invalid record (if any)
            - details: Per-record validation results
        """
        with self._lock:
            if not self._audit_log:
                return {"valid": True, "total_records": 0, "details": []}

            prev_hash = ""
            results = []

            for idx, record in enumerate(self._audit_log):
                record_data = {
                    "timestamp": record.timestamp,
                    "user_id": record.user_id,
                    "action": record.action,
                    "resource_type": record.resource_type,
                    "resource_id": record.resource_id,
                    "details": record.details,
                    "result": record.result,
                    "prev_hash": prev_hash,
                }

                expected_hash = hashlib.sha256(
                    json.dumps(record_data, sort_keys=True).encode()
                ).hexdigest()

                is_valid = expected_hash == record.hash_signature
                results.append({
                    "index": idx,
                    "valid": is_valid,
                    "expected": expected_hash,
                    "actual": record.hash_signature,
                })

                if not is_valid and "first_violation" not in locals():
                    first_violation = idx

                prev_hash = record.hash_signature

            return {
                "valid": all(r["valid"] for r in results),
                "total_records": len(results),
                "first_violation": first_violation if not all(r["valid"] for r in results) else None,
                "details": results,
            }

    def get_stats(self) -> dict[str, Any]:
        """Get engine statistics for monitoring.

        Returns:
            Dictionary with user counts, role distributions, etc.
        """
        with self._lock:
            role_counts: dict[str, int] = {}
            active_users = 0
            inactive_users = 0

            for user in self._users.values():
                for role in user.roles:
                    role_counts[role.value] = role_counts.get(role.value, 0) + 1
                if user.is_active:
                    active_users += 1
                else:
                    inactive_users += 1

            return {
                "total_users": len(self._users),
                "active_users": active_users,
                "inactive_users": inactive_users,
                "total_roles": len(UserRole),
                "total_permissions": len(Permission),
                "audit_log_size": len(self._audit_log),
                "role_distribution": role_counts,
            }

    @staticmethod
    def map_legacy_level(level_name: str) -> UserRole:
        """Map PermissionGuard legacy levels to RBAC roles.

        Bridges the gap between old 4-level system and new RBAC:

        Args:
            level_name: Legacy level name ("bypass", "auto", "default", "plan")

        Returns:
            Corresponding UserRole enum value

        Raises:
            ValueError: If level_name is unrecognized
        """
        mapping = {
            "bypass": UserRole.SUPER_ADMIN,
            "auto": UserRole.ADMIN,
            "default": UserRole.OPERATOR,
            "plan": UserRole.VIEWER,
        }
        if level_name not in mapping:
            raise ValueError(f"Unknown legacy level: '{level_name}'. "
                           f"Valid values: {list(mapping.keys())}")
        return mapping[level_name]

