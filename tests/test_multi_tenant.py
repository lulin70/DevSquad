"""Tests for MultiTenantManager - Enterprise Multi-Tenancy Support."""

import pytest

from scripts.collaboration.multi_tenant import (
    IsolationLevel,
    MultiTenantManager,
    QuotaExceededError,
    QuotaManager,
    Tenant,
    TenantContext,
)


class TestIsolationLevel:
    def test_isolation_levels_exist(self):
        assert IsolationLevel.SHARED_DATABASE is not None
        assert IsolationLevel.SCHEMA_PER_TENANT is not None
        assert IsolationLevel.DATABASE_PER_TENANT is not None

    def test_isolation_level_values(self):
        assert IsolationLevel.SHARED_DATABASE.value == "shared_db"
        assert IsolationLevel.SCHEMA_PER_TENANT.value == "schema_per_tenant"
        assert IsolationLevel.DATABASE_PER_TENANT.value == "db_per_tenant"


class TestTenant:
    def test_create_tenant_defaults(self):
        tenant = Tenant(tenant_id="t1", name="Test Tenant")
        assert tenant.tenant_id == "t1"
        assert tenant.name == "Test Tenant"
        assert tenant.isolation_level == IsolationLevel.SHARED_DATABASE
        assert tenant.is_active is True
        assert tenant.quota_limits == {}

    def test_tenant_with_quota_limits(self):
        tenant = Tenant(
            tenant_id="t1",
            name="Test",
            quota_limits={"tasks": 100, "users": 10},
        )
        assert tenant.quota_limits["tasks"] == 100

    def test_check_quota_within_limit(self):
        tenant = Tenant(
            tenant_id="t1", name="Test", quota_limits={"tasks": 100}
        )
        assert tenant.check_quota("tasks", 50) is True
        assert tenant.check_quota("tasks", 100) is True

    def test_check_quota_exceeds_limit(self):
        tenant = Tenant(
            tenant_id="t1", name="Test", quota_limits={"tasks": 100}
        )
        assert tenant.check_quota("tasks", 101) is False

    def test_check_quota_no_limit_configured(self):
        tenant = Tenant(tenant_id="t1", name="Test")
        assert tenant.check_quota("tasks", 9999) is True

    def test_get_set_quota_limit(self):
        tenant = Tenant(tenant_id="t1", name="Test")
        assert tenant.get_quota_limit("tasks") is None
        tenant.set_quota_limit("tasks", 500)
        assert tenant.get_quota_limit("tasks") == 500

    def test_tenant_serialization(self):
        tenant = Tenant(
            tenant_id="t1",
            name="Test",
            isolation_level=IsolationLevel.SCHEMA_PER_TENANT,
            quota_limits={"tasks": 100},
        )
        d = tenant.to_dict()
        assert d["tenant_id"] == "t1"
        assert d["isolation_level"] == "schema_per_tenant"
        assert d["quota_limits"]["tasks"] == 100

        restored = Tenant.from_dict(d)
        assert restored.tenant_id == "t1"
        assert restored.isolation_level == IsolationLevel.SCHEMA_PER_TENANT

    def test_tenant_context_is_set(self):
        ctx = TenantContext()
        assert ctx.is_set() is False
        ctx.tenant_id = "t1"
        assert ctx.is_set() is True

    def test_tenant_context_clear(self):
        ctx = TenantContext(tenant_id="t1", user_id="u1")
        ctx.clear()
        assert ctx.tenant_id is None
        assert ctx.user_id is None


class TestQuotaManager:
    def setup_method(self):
        self.qm = QuotaManager()

    def test_check_and_increment_within_limit(self):
        result = self.qm.check_and_increment("t1", "tasks", limit=100)
        assert result is True

    def test_check_and_increment_exceeds_limit(self):
        for _ in range(3):
            self.qm.check_and_increment("t1", "tasks", limit=3)
        result = self.qm.check_and_increment("t1", "tasks", limit=3)
        assert result is False

    def test_get_usage(self):
        self.qm.check_and_increment("t1", "tasks", limit=100)
        self.qm.check_and_increment("t1", "tasks", limit=100)
        usage = self.qm.get_usage("t1")
        assert usage["tasks"] == 2

    def test_get_usage_for_resource(self):
        self.qm.check_and_increment("t1", "tasks", limit=100)
        assert self.qm.get_usage_for_resource("t1", "tasks") == 1
        assert self.qm.get_usage_for_resource("t1", "users") == 0

    def test_decrement(self):
        self.qm.check_and_increment("t1", "tasks", limit=100)
        self.qm.check_and_increment("t1", "tasks", limit=100)
        new_val = self.qm.decrement("t1", "tasks")
        assert new_val == 1

    def test_decrement_does_not_go_below_zero(self):
        new_val = self.qm.decrement("t1", "tasks", amount=10)
        assert new_val == 0

    def test_reset_usage(self):
        self.qm.check_and_increment("t1", "tasks", limit=100)
        self.qm.reset_usage("t1", "tasks")
        assert self.qm.get_usage_for_resource("t1", "tasks") == 0

    def test_reset_all_tenants(self):
        self.qm.check_and_increment("t1", "tasks", limit=100)
        self.qm.check_and_increment("t2", "tasks", limit=100)
        self.qm.reset_all_tenants()
        assert self.qm.get_usage("t1") == {}
        assert self.qm.get_usage("t2") == {}

    def test_get_stats(self):
        self.qm.check_and_increment("t1", "tasks", limit=100)
        stats = self.qm.get_stats()
        assert stats["total_tenants_tracked"] == 1
        assert "tasks" in stats["resource_types"]


class TestMultiTenantManager:
    def setup_method(self):
        self.mtm = MultiTenantManager(
            default_isolation=IsolationLevel.SHARED_DATABASE
        )

    def test_create_tenant(self):
        tenant = Tenant(tenant_id="t1", name="Test Tenant")
        self.mtm.create_tenant(tenant)
        assert self.mtm.get_tenant("t1") is not None
        assert self.mtm.get_tenant("t1").name == "Test Tenant"

    def test_create_tenant_duplicate_raises(self):
        tenant = Tenant(tenant_id="t1", name="Test Tenant")
        self.mtm.create_tenant(tenant)
        with pytest.raises(ValueError, match="already exists"):
            self.mtm.create_tenant(Tenant(tenant_id="t1", name="Duplicate"))

    def test_create_tenant_empty_id_raises(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            self.mtm.create_tenant(Tenant(tenant_id="", name="Empty"))

    def test_get_tenant_not_found(self):
        assert self.mtm.get_tenant("nonexistent") is None

    def test_set_and_clear_context(self):
        tenant = Tenant(tenant_id="t1", name="Test Tenant")
        self.mtm.create_tenant(tenant)
        self.mtm.set_context("t1", "user1")
        current = self.mtm.get_current_tenant()
        assert current is not None
        assert current.tenant_id == "t1"
        self.mtm.clear_context()
        assert self.mtm.get_current_tenant() is None

    def test_context_manager(self):
        tenant = Tenant(tenant_id="t1", name="Test Tenant")
        self.mtm.create_tenant(tenant)
        with self.mtm.context("t1", "user1"):
            current = self.mtm.get_current_tenant()
            assert current is not None
            assert current.tenant_id == "t1"
        assert self.mtm.get_current_tenant() is None

    def test_set_context_unknown_tenant_raises(self):
        with pytest.raises(KeyError, match="not found"):
            self.mtm.set_context("nonexistent", "user1")

    def test_set_context_inactive_tenant_raises(self):
        tenant = Tenant(tenant_id="t1", name="Test Tenant")
        self.mtm.create_tenant(tenant)
        self.mtm.deactivate_tenant("t1")
        with pytest.raises(KeyError, match="deactivated"):
            self.mtm.set_context("t1", "user1")

    def test_check_quota_no_limit(self):
        tenant = Tenant(tenant_id="t1", name="Test Tenant")
        self.mtm.create_tenant(tenant)
        with self.mtm.context("t1", "user1"):
            result = self.mtm.check_quota("tasks")
            assert result is True  # No limit configured

    def test_check_quota_with_limit(self):
        tenant = Tenant(
            tenant_id="t1", name="Test Tenant", quota_limits={"tasks": 3}
        )
        self.mtm.create_tenant(tenant)
        with self.mtm.context("t1", "user1"):
            assert self.mtm.check_quota("tasks") is True
            assert self.mtm.check_quota("tasks") is True
            assert self.mtm.check_quota("tasks") is True
            assert self.mtm.check_quota("tasks") is False  # Exceeded

    def test_check_quota_no_context_raises(self):
        with pytest.raises(RuntimeError, match="No tenant context"):
            self.mtm.check_quota("tasks")

    def test_deactivate_and_reactivate_tenant(self):
        tenant = Tenant(tenant_id="t1", name="Test Tenant")
        self.mtm.create_tenant(tenant)
        self.mtm.deactivate_tenant("t1")
        assert self.mtm.get_tenant("t1").is_active is False
        self.mtm.reactivate_tenant("t1")
        assert self.mtm.get_tenant("t1").is_active is True

    def test_deactivate_unknown_tenant_raises(self):
        with pytest.raises(KeyError, match="not found"):
            self.mtm.deactivate_tenant("nonexistent")

    def test_delete_tenant(self):
        tenant = Tenant(tenant_id="t1", name="Test Tenant")
        self.mtm.create_tenant(tenant)
        assert self.mtm.delete_tenant("t1") is True
        assert self.mtm.get_tenant("t1") is None
        assert self.mtm.delete_tenant("nonexistent") is False

    def test_list_tenants(self):
        self.mtm.create_tenant(Tenant(tenant_id="t1", name="Active"))
        t2 = Tenant(tenant_id="t2", name="Inactive")
        self.mtm.create_tenant(t2)
        self.mtm.deactivate_tenant("t2")
        active = self.mtm.list_tenants(active_only=True)
        assert len(active) == 1
        all_tenants = self.mtm.list_tenants(active_only=False)
        assert len(all_tenants) == 2

    def test_list_tenants_by_isolation(self):
        self.mtm.create_tenant(
            Tenant(
                tenant_id="t1",
                name="Shared",
                isolation_level=IsolationLevel.SHARED_DATABASE,
            )
        )
        self.mtm.create_tenant(
            Tenant(
                tenant_id="t2",
                name="Schema",
                isolation_level=IsolationLevel.SCHEMA_PER_TENANT,
            )
        )
        shared = self.mtm.list_tenants(isolation_level=IsolationLevel.SHARED_DATABASE)
        assert len(shared) == 1
        assert shared[0].tenant_id == "t1"

    def test_update_tenant(self):
        tenant = Tenant(tenant_id="t1", name="Old Name")
        self.mtm.create_tenant(tenant)
        self.mtm.update_tenant("t1", name="New Name")
        assert self.mtm.get_tenant("t1").name == "New Name"

    def test_update_tenant_not_found_raises(self):
        with pytest.raises(KeyError, match="not found"):
            self.mtm.update_tenant("nonexistent", name="New")

    def test_require_tenant(self):
        tenant = Tenant(tenant_id="t1", name="Test")
        self.mtm.create_tenant(tenant)
        with self.mtm.context("t1", "user1"):
            t = self.mtm.require_tenant()
            assert t.tenant_id == "t1"

    def test_require_tenant_no_context_raises(self):
        with pytest.raises(RuntimeError, match="not set"):
            self.mtm.require_tenant()

    def test_get_stats(self):
        self.mtm.create_tenant(Tenant(tenant_id="t1", name="Test1"))
        self.mtm.create_tenant(
            Tenant(
                tenant_id="t2",
                name="Test2",
                isolation_level=IsolationLevel.SCHEMA_PER_TENANT,
            )
        )
        stats = self.mtm.get_stats()
        assert stats["total_tenants"] == 2
        assert stats["active_tenants"] == 2
        assert "quota_stats" in stats

    def test_export_tenants(self):
        import tempfile

        self.mtm.create_tenant(Tenant(tenant_id="t1", name="Test1"))
        self.mtm.create_tenant(Tenant(tenant_id="t2", name="Test2"))
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        count = self.mtm.export_tenants(path)
        assert count == 2
        import os

        os.unlink(path)
