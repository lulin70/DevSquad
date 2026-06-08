#!/usr/bin/env python3
"""
Multi-Tenant Manager - Enterprise Multi-Tenancy Support for DevSquad

Enables SaaS-style multi-tenant isolation with three levels:
- Shared Database (row-level isolation): Cost-effective for small tenants
- Schema-per-Tenant: Balanced isolation and performance
- Database-per-Tenant: Maximum isolation for enterprise

Features:
- Tenant lifecycle management (create, deactivate, reactivate)
- Thread-local tenant context (automatic request scoping)
- Quota management with configurable limits
- Per-tenant configuration
- Integration with RBACEngine for tenant-aware permissions

Architecture:
    Request → MultiTenantManager.set_context(tenant_id)
             → All operations scoped to tenant
             → RBACEngine.enforce(user_id, permission) [tenant-aware]
             → MultiTenantManager.clear_context()

Usage:
    mtm = MultiTenantManager()
    mtm.create_tenant(Tenant(tenant_id="acme", name="Acme Corp"))

    # Set context for current thread/request
    mtm.set_context("acme", "user-123")
    ctx = mtm.get_context()
    assert ctx.tenant_id == "acme"

    # Check quota before operation
    if mtm.quota_manager.check_and_increment("acme", "tasks", limit=1000):
        create_task(...)
"""

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any


class IsolationLevel(Enum):
    """Tenant isolation levels determining data separation strategy.

    Levels (from lowest to highest isolation):
        SHARED_DATABASE:
            All tenants share same database/table.
            Row-level filtering via tenant_id column.
            Lowest cost, simplest ops, acceptable for non-sensitive data.

        SCHEMA_PER_TENANT:
            Each tenant gets dedicated schema within shared database.
            Logical separation with some performance benefits.
            Good balance of isolation and operational complexity.

        DATABASE_PER_TENANT:
            Each tenant has completely isolated database instance.
            Maximum security and performance isolation.
            Highest cost and operational overhead.
            Required for regulated industries (HIPAA, PCI-DSS).
    """

    SHARED_DATABASE = "shared_db"
    SCHEMA_PER_TENANT = "schema_per_tenant"
    DATABASE_PER_TENANT = "db_per_tenant"


@dataclass
class Tenant:
    """Tenant model representing an organization/customer.

    Attributes:
        tenant_id: Unique identifier (e.g., UUID, slug)
        name: Display name (e.g., "Acme Corporation")
        isolation_level: Data isolation strategy
        config: Tenant-specific configuration overrides
        quota_limits: Resource usage limits per category
        is_active: Whether tenant is active (inactive = suspended)
        created_at: ISO timestamp of creation
        updated_at: ISO timestamp of last update
        metadata: Extended attributes (plan tier, contact info, etc.)
    """

    tenant_id: str
    name: str
    isolation_level: IsolationLevel = IsolationLevel.SHARED_DATABASE
    config: Dict[str, Any] = field(default_factory=dict)
    quota_limits: Dict[str, int] = field(default_factory=dict)
    is_active: bool = True
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def check_quota(self, resource: str, current_usage: int) -> bool:
        """Check if resource usage is within quota limits.

        Args:
            resource: Resource type to check (e.g., "tasks", "users", "storage_mb")
            current_usage: Current usage count/amount

        Returns:
            True if under or at limit, False if exceeded
        """
        limit = self.quota_limits.get(resource)
        if limit is None:
            return True  # No limit configured
        return current_usage <= limit

    def get_quota_limit(self, resource: str) -> Optional[int]:
        """Get quota limit for a specific resource.

        Args:
            resource: Resource type

        Returns:
            Configured limit or None if unlimited
        """
        return self.quota_limits.get(resource)

    def set_quota_limit(self, resource: str, limit: int) -> None:
        """Set quota limit for a resource.

        Args:
            resource: Resource type
            limit: Maximum allowed usage (None for unlimited)
        """
        self.quota_limits[resource] = limit
        self.updated_at = datetime.utcnow().isoformat()

    def to_dict(self) -> dict:
        """Serialize tenant to dictionary."""
        return {
            "tenant_id": self.tenant_id,
            "name": self.name,
            "isolation_level": self.isolation_level.value,
            "config": self.config,
            "quota_limits": self.quota_limits,
            "is_active": self.is_active,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Tenant":
        """Deserialize tenant from dictionary."""
        return cls(
            tenant_id=data["tenant_id"],
            name=data["name"],
            isolation_level=IsolationLevel(data.get("isolation_level", "shared_db")),
            config=data.get("config", {}),
            quota_limits=data.get("quota_limits", {}),
            is_active=data.get("is_active", True),
            created_at=data.get("created_at", datetime.utcnow().isoformat()),
            updated_at=data.get("updated_at", datetime.utcnow().isoformat()),
            metadata=data.get("metadata", {}),
        )


@dataclass
class TenantContext:
    """Thread-local tenant context for request scoping.

    Automatically isolates all operations to the current tenant
    when set via MultiTenantManager.set_context().

    Thread Safety:
        This object should be stored in threading.local() for
        automatic per-thread isolation.

    Attributes:
        tenant_id: Current tenant identifier (None = system/global context)
        user_id: Current user identifier within tenant
        request_id: Unique request identifier for tracing
        metadata: Request-specific context (IP, User-Agent, etc.)
    """

    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    request_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_set(self) -> bool:
        """Check if context has been initialized.

        Returns:
            True if tenant_id is not None
        """
        return self.tenant_id is not None

    def clear(self) -> None:
        """Reset context to empty state."""
        self.tenant_id = None
        self.user_id = None
        self.request_id = None
        self.metadata.clear()


class QuotaExceededError(Exception):
    """Raised when tenant exceeds their quota limit."""

    def __init__(self, tenant_id: str, resource: str, limit: int, current: int):
        self.tenant_id = tenant_id
        self.resource = resource
        self.limit = limit
        self.current = current
        message = (
            f"Tenant '{tenant_id}' exceeded quota for '{resource}' "
            f"(current: {current}, limit: {limit})"
        )
        super().__init__(message)


class QuotaManager:
    """Resource quota management for tenants.

    Tracks usage per tenant/resource pair and enforces limits.
    Supports monthly reset cycles for recurring quotas.

    Usage:
        qm = QuotaManager()
        if qm.check_and_increment("acme", "tasks", limit=1000):
            create_task(...)
        else:
            handle_quota_exceeded(...)
    """

    def __init__(self):
        self._usage: Dict[str, Dict[str, int]] = {}
        self._lock = threading.Lock()

    def check_and_increment(
        self,
        tenant_id: str,
        resource: str,
        limit: int,
        increment: int = 1,
    ) -> bool:
        """Check quota and atomically increment if under limit.

        Thread-safe atomic operation: checks current usage against
        limit, then increments only if there's room.

        Args:
            tenant_id: Tenant identifier
            resource: Resource type (e.g., "tasks", "api_calls")
            limit: Maximum allowed usage
            increment: Amount to add (default: 1)

        Returns:
            True if incremented successfully (under limit)
            False if would exceed limit (not incremented)

        Example:
            if quota_mgr.check_and_increment("acme", "tasks", limit=1000):
                # Create task - quota slot reserved
            else:
                # Handle quota exceeded
        """
        with self._lock:
            if tenant_id not in self._usage:
                self._usage[tenant_id] = {}

            current = self._usage[tenant_id].get(resource, 0)

            if current + increment > limit:
                return False

            self._usage[tenant_id][resource] = current + increment
            return True

    def get_usage(self, tenant_id: str) -> Dict[str, int]:
        """Get current usage for all resources of a tenant.

        Args:
            tenant_id: Tenant identifier

        Returns:
            Dictionary mapping resource types to current usage counts
        """
        with self._lock:
            return dict(self._usage.get(tenant_id, {}))

    def get_usage_for_resource(self, tenant_id: str, resource: str) -> int:
        """Get usage for a specific resource.

        Args:
            tenant_id: Tenant identifier
            resource: Resource type

        Returns:
            Current usage count (0 if not tracked)
        """
        with self._lock:
            return self._usage.get(tenant_id, {}).get(resource, 0)

    def decrement(self, tenant_id: str, resource: str, amount: int = 1) -> int:
        """Decrement usage (for resource release/cleanup).

        Useful when tasks are deleted or API calls are refunded.
        Usage won't go below 0.

        Args:
            tenant_id: Tenant identifier
            resource: Resource type
            amount: Amount to decrement

        Returns:
            New usage count after decrement
        """
        with self._lock:
            if tenant_id not in self._usage:
                self._usage[tenant_id] = {}

            current = self._usage[tenant_id].get(resource, 0)
            new_value = max(0, current - amount)
            self._usage[tenant_id][resource] = new_value
            return new_value

    def reset_usage(self, tenant_id: str, resource: Optional[str] = None) -> None:
        """Reset usage counters (typically called monthly).

        Args:
            tenant_id: Tenant identifier
            resource: Specific resource to reset (None = all resources)
        """
        with self._lock:
            if tenant_id in self._usage:
                if resource:
                    self._usage[tenant_id].pop(resource, None)
                else:
                    self._usage[tenant_id].clear()

    def reset_all_tenants(self) -> None:
        """Reset usage for all tenants (system-wide reset).

        Warning: Use only for administrative purposes.
        """
        with self._lock:
            self._usage.clear()

    def get_all_usage(self) -> Dict[str, Dict[str, int]]:
        """Get usage for all tenants (admin view).

        Returns:
            Nested dict: {tenant_id: {resource: usage}}
        """
        with self._lock:
            return {
                tid: dict(resources)
                for tid, resources in self._usage.items()
            }

    def get_stats(self) -> Dict[str, Any]:
        """Get quota manager statistics.

        Returns:
            Dictionary with total tenants tracked, resource types, etc.
        """
        with self._lock:
            total_tenants = len(self._usage)
            total_resources = set()
            total_usage = 0

            for resources in self._usage.values():
                total_resources.update(resources.keys())
                total_usage += sum(resources.values())

            return {
                "total_tenants_tracked": total_tenants,
                "total_resource_types": len(total_resources),
                "total_usage_count": total_usage,
                "resource_types": sorted(total_resources),
            }


class MultiTenantManager:
    """Multi-tenant orchestration manager.

    Provides tenant lifecycle management, context scoping, and
    integration point for RBAC and quota systems.

    Context Management:
        Uses threading.local() to automatically scope each thread/request
        to a specific tenant. Call set_context() at request start and
        clear_context() when done (or use context manager).

    Thread Safety:
        All public methods are thread-safe. Context is per-thread.

    Usage:
        mtm = MultiTenantManager()

        # Setup
        mtm.create_tenant(Tenant(
            tenant_id="acme",
            name="Acme Corp",
            quota_limits={"tasks": 1000, "users": 50},
        ))

        # In request handler
        with mtm.context("acme", "user-123"):
            ctx = mtm.get_context()
            assert ctx.tenant_id == "acme"

            # Check quota
            if mtm.check_quota("tasks"):
                perform_operation(...)
    """

    def __init__(self, default_isolation: IsolationLevel = IsolationLevel.SHARED_DATABASE):
        """
        Initialize multi-tenant manager.

        Args:
            default_isolation: Default isolation level for new tenants
        """
        self._tenants: Dict[str, Tenant] = {}
        self._local = threading.local()
        self._default_isolation = default_isolation
        self._lock = threading.RLock()
        self.quota_manager = QuotaManager()
        self.logger = logging.getLogger(__name__)

    def _get_context(self) -> TenantContext:
        """Get or create thread-local context."""
        if not hasattr(self._local, "context"):
            self._local.context = TenantContext()
        return self._local.context

    def create_tenant(self, tenant: Tenant) -> None:
        """Create/register a new tenant.

        Args:
            tenant: Tenant instance with configuration

        Raises:
            ValueError: If tenant_id already exists or is empty
        """
        if not tenant.tenant_id:
            raise ValueError("tenant_id cannot be empty")

        with self._lock:
            if tenant.tenant_id in self._tenants:
                raise ValueError(f"Tenant '{tenant.tenant_id}' already exists")

            if tenant.isolation_level is None:
                tenant.isolation_level = self._default_isolation

            self._tenants[tenant.tenant_id] = tenant
            self.logger.info("Created tenant: %s (%s)", tenant.tenant_id, tenant.name)

    def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        """Retrieve a tenant by ID.

        Args:
            tenant_id: Tenant identifier

        Returns:
            Tenant instance or None if not found
        """
        with self._lock:
            return self._tenants.get(tenant_id)

    def update_tenant(self, tenant_id: str, **kwargs) -> bool:
        """Update tenant attributes.

        Args:
            tenant_id: Tenant identifier
            **kwargs: Attributes to update (name, config, quota_limits, etc.)

        Returns:
            True if updated, False if not found

        Raises:
            KeyError: If tenant not found
        """
        with self._lock:
            tenant = self._tenants.get(tenant_id)
            if not tenant:
                raise KeyError(f"Tenant '{tenant_id}' not found")

            for key, value in kwargs.items():
                if hasattr(tenant, key):
                    setattr(tenant, key, value)

            tenant.updated_at = datetime.utcnow().isoformat()
            return True

    def deactivate_tenant(self, tenant_id: str) -> None:
        """Suspend/deactivate a tenant.

        Deactivated tenants cannot set context but retain data.
        Use reactivate_tenant() to re-enable.

        Args:
            tenant_id: Tenant identifier

        Raises:
            KeyError: If tenant not found
        """
        with self._lock:
            tenant = self._tenants.get(tenant_id)
            if not tenant:
                raise KeyError(f"Tenant '{tenant_id}' not found")

            tenant.is_active = False
            tenant.updated_at = datetime.utcnow().isoformat()
            self.logger.warning("Deactivated tenant: %s", tenant_id)

    def reactivate_tenant(self, tenant_id: str) -> None:
        """Reactivate a previously deactivated tenant.

        Args:
            tenant_id: Tenant identifier

        Raises:
            KeyError: If tenant not found
        """
        with self._lock:
            tenant = self._tenants.get(tenant_id)
            if not tenant:
                raise KeyError(f"Tenant '{tenant_id}' not found")

            tenant.is_active = True
            tenant.updated_at = datetime.utcnow().isoformat()
            self.logger.info("Reactivated tenant: %s", tenant_id)

    def delete_tenant(self, tenant_id: str) -> bool:
        """Permanently delete a tenant and all associated data.

        Warning: This operation cannot be undone. Consider using
        deactivate_tenant() for temporary suspension.

        Args:
            tenant_id: Tenant identifier

        Returns:
            True if deleted, False if not found
        """
        with self._lock:
            if tenant_id in self._tenants:
                del self._tenants[tenant_id]
                self.quota_manager.reset_usage(tenant_id)
                self.logger.warning("Deleted tenant: %s", tenant_id)
                return True
            return False

    def list_tenants(
        self,
        active_only: bool = True,
        isolation_level: Optional[IsolationLevel] = None,
    ) -> List[Tenant]:
        """List tenants with optional filtering.

        Args:
            active_only: If True, exclude inactive tenants
            isolation_level: Filter by isolation level (optional)

        Returns:
            List of matching Tenant instances
        """
        with self._lock:
            tenants = list(self._tenants.values())

            if active_only:
                tenants = [t for t in tenants if t.is_active]

            if isolation_level:
                tenants = [t for t in tenants if t.isolation_level == isolation_level]

            return tenants

    def set_context(
        self,
        tenant_id: str,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None,
        **metadata,
    ) -> TenantContext:
        """Set tenant context for current thread/request.

        Must be called at the beginning of each request to scope
        all subsequent operations to this tenant.

        Args:
            tenant_id: Target tenant identifier
            user_id: User identifier within tenant (optional)
            request_id: Unique request ID for tracing (optional)
            **metadata: Additional context (ip_address, user_agent, etc.)

        Returns:
            The updated TenantContext

        Raises:
            KeyError: If tenant not found or inactive
        """
        with self._lock:
            tenant = self._tenants.get(tenant_id)
            if not tenant:
                raise KeyError(f"Tenant '{tenant_id}' not found")
            if not tenant.is_active:
                raise KeyError(f"Tenant '{tenant_id}' is deactivated")

        ctx = self._get_context()
        ctx.tenant_id = tenant_id
        ctx.user_id = user_id
        ctx.request_id = request_id or str(uuid.uuid4())[:12]
        ctx.metadata.update(metadata)

        self.logger.debug(
            "Set context: tenant=%s user=%s request=%s",
            tenant_id, user_id, ctx.request_id,
        )
        return ctx

    def get_context(self) -> TenantContext:
        """Get current thread's tenant context.

        Returns:
            TenantContext (may have tenant_id=None if not set)
        """
        return self._get_context()

    def clear_context(self) -> None:
        """Clear current thread's tenant context.

        Should be called at end of request processing.
        """
        ctx = self._get_context()
        ctx.clear()
        self.logger.debug("Cleared tenant context")

    def context(self, tenant_id: str, user_id: Optional[str] = None, **kwargs):
        """Context manager for automatic tenant scoping.

        Use with 'with' statement for clean setup/teardown:

        Args:
            tenant_id: Tenant identifier
            user_id: User identifier (optional)
            **kwargs: Additional context metadata

        Yields:
            TenantContext for the duration of the block

        Example:
            with mtm.context("acme", "user-123") as ctx:
                # All operations here are scoped to tenant "acme"
                perform_tenant_specific_operations()
            # Context automatically cleared here
        """
        class _TenantContextManager:
            def __init__(self, manager, tid, uid, **kw):
                self.manager = manager
                self.tid = tid
                self.uid = uid
                self.kwargs = kw

            def __enter__(self):
                return self.manager.set_context(self.tid, self.uid, **self.kwargs)

            def __exit__(self, exc_type, exc_val, exc_tb):
                self.manager.clear_context()
                return False

        return _TenantContextManager(self, tenant_id, user_id, **kwargs)

    def check_quota(self, resource: str, increment: int = 1) -> bool:
        """Check and increment quota for current tenant's context.

        Convenience method that reads tenant from context and
        delegates to QuotaManager.

        Args:
            resource: Resource type to check
            increment: Amount to increment if under limit

        Returns:
            True if quota available and incremented

        Raises:
            RuntimeError: If no tenant context is set
        """
        ctx = self._get_context()
        if not ctx.tenant_id:
            raise RuntimeError("No tenant context set. Call set_context() first.")

        tenant = self.get_tenant(ctx.tenant_id)
        if not tenant:
            raise RuntimeError(f"Tenant '{ctx.tenant_id}' not found")

        limit = tenant.get_quota_limit(resource)
        if limit is None:
            return True  # No limit configured

        return self.quota_manager.check_and_increment(
            ctx.tenant_id, resource, limit, increment
        )

    def get_current_tenant(self) -> Optional[Tenant]:
        """Get the Tenant object for the current context.

        Returns:
            Tenant instance or None if no context set
        """
        ctx = self._get_context()
        if not ctx.tenant_id:
            return None
        return self.get_tenant(ctx.tenant_id)

    def require_tenant(self) -> Tenant:
        """Get current tenant, raising error if not set.

        Useful for operations that must be tenant-scoped.

        Returns:
            Current Tenant instance

        Raises:
            RuntimeError: If no tenant context is set
        """
        ctx = self._get_context()
        if not ctx.tenant_id:
            raise RuntimeError("Tenant context required but not set")

        tenant = self.get_tenant(ctx.tenant_id)
        if not tenant:
            raise RuntimeError(f"Tenant '{ctx.tenant_id}' not found")

        return tenant

    def get_stats(self) -> Dict[str, Any]:
        """Get multi-tenant system statistics.

        Returns:
            Dictionary with tenant counts, quota stats, etc.
        """
        with self._lock:
            active = sum(1 for t in self._tenants.values() if t.is_active)
            inactive = len(self._tenants) - active

            isolation_counts = {}
            for t in self._tenants.values():
                level = t.isolation_level.value
                isolation_counts[level] = isolation_counts.get(level, 0) + 1

            return {
                "total_tenants": len(self._tenants),
                "active_tenants": active,
                "inactive_tenants": inactive,
                "isolation_distribution": isolation_counts,
                "default_isolation": self._default_isolation.value,
                "quota_stats": self.quota_manager.get_stats(),
            }

    def export_tenants(self, output_path: str) -> int:
        """Export all tenant configurations to JSON file.

        Args:
            output_path: Destination file path

        Returns:
            Number of tenants exported
        """
        import json as _json

        with self._lock:
            tenants_data = [t.to_dict() for t in self._tenants.values()]

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w", encoding="utf-8") as f:
            _json.dump(tenants_data, f, indent=2, ensure_ascii=False)

        self.logger.info("Exported %d tenants to %s", len(tenants_data), output_path)
        return len(tenants_data)


from pathlib import Path


if __name__ == "__main__":
    print("Multi-Tenant Manager - Enterprise Multi-Tenancy Support")
    print("=" * 60)

    mtm = MultiTenantManager()

    tenant1 = Tenant(
        tenant_id="acme",
        name="Acme Corporation",
        isolation_level=IsolationLevel.SCHEMA_PER_TENANT,
        quota_limits={
            "tasks": 1000,
            "users": 50,
            "storage_mb": 10240,
        },
        metadata={"plan": "enterprise", "tier": "premium"},
    )

    tenant2 = Tenant(
        tenant_id="startup",
        name="Startup Inc",
        isolation_level=IsolationLevel.SHARED_DATABASE,
        quota_limits={"tasks": 100, "users": 10},
        metadata={"plan": "startup"},
    )

    mtm.create_tenant(tenant1)
    mtm.create_tenant(tenant2)

    print("\n✓ Created tenants:")
    for t in mtm.list_tenants():
        print(f"  - {t.name} ({t.tenant_id}) [{t.isolation_level.value}]")

    print("\n✓ Testing tenant context:")

    with mtm.context("acme", "user-001") as ctx:
        print(f"  Tenant: {ctx.tenant_id}")
        print(f"  User: {ctx.user_id}")
        print(f"  Request ID: {ctx.request_id}")

        current = mtm.get_current_tenant()
        print(f"  Current Tenant: {current.name}")

        for i in range(5):
            if mtm.check_quota("tasks"):
                print(f"  ✓ Task {i+1} quota granted")
            else:
                print(f"  ✗ Task {i+1} quota denied")

    print("\n✓ Testing quota enforcement:")

    small_tenant = Tenant(
        tenant_id="tiny",
        name="Tiny Corp",
        quota_limits={"tasks": 3},
    )
    mtm.create_tenant(small_tenant)

    with mtm.context("tiny", "user-tiny"):
        for i in range(5):
            if mtm.check_quota("tasks"):
                print(f"  ✓ Tiny task {i+1}: OK")
            else:
                print(f"  ✗ Tiny task {i+1}: QUOTA EXCEEDED")

    stats = mtm.get_stats()
    print(f"\n📊 Statistics:")
    print(f"  Total tenants: {stats['total_tenants']}")
    print(f"  Active: {stats['active_tenants']}")
    print(f"  Distribution: {stats['isolation_distribution']}")

    quota_stats = mtm.quota_manager.get_stats()
    print(f"\n  Quota Manager:")
    print(f"  Tracked tenants: {quota_stats['total_tenants_tracked']}")
    print(f"  Resource types: {quota_stats['resource_types']}")
