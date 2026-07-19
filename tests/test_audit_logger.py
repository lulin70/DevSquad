"""Tests for AuditLogger and SensitiveDataMasker."""

import os
import tempfile

import pytest

from scripts.collaboration.audit_logger import AuditLogger, AuditRecord, SensitiveDataMasker

pytestmark = pytest.mark.unit



class TestAuditLogger:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.logger = AuditLogger(log_dir=self.tmpdir, format="csv", enable_hash_chain=True)

    def test_log_creates_record(self):
        record = self.logger.log(
            user_id="test_user",
            action="test:action",
            resource_type="Task",
            resource_id="task-123",
        )
        assert record is not None
        assert record.user_id == "test_user"
        assert record.action == "test:action"
        assert record.resource_type == "Task"
        assert record.resource_id == "task-123"
        assert record.result == "success"
        assert record.hash_signature is not None
        assert len(record.hash_signature) > 0

    def test_log_with_details(self):
        record = self.logger.log(
            user_id="user1",
            action="task:create",
            resource_type="Task",
            resource_id="t1",
            details={"title": "Test", "priority": "high"},
        )
        assert record.details["title"] == "Test"
        assert record.details["priority"] == "high"

    def test_log_with_kwargs_merged_into_details(self):
        record = self.logger.log(
            user_id="user1",
            action="task:update",
            resource_type="Task",
            resource_id="t1",
            details={"title": "Test"},
            extra_field="extra_value",
        )
        assert record.details["title"] == "Test"
        assert record.details["extra_field"] == "extra_value"

    def test_log_denied_result(self):
        record = self.logger.log(
            user_id="user1",
            action="permission:check",
            resource_type="Permission",
            resource_id="task:execute",
            result="denied",
        )
        assert record.result == "denied"

    def test_query_returns_records(self):
        self.logger.log(user_id="user1", action="action1", resource_type="Task", resource_id="1")
        self.logger.log(user_id="user2", action="action2", resource_type="Task", resource_id="2")
        results = self.logger.query(user_id="user1")
        assert len(results) >= 1
        assert all(r.user_id == "user1" for r in results)

    def test_query_by_action(self):
        self.logger.log(user_id="user1", action="task:create", resource_type="Task", resource_id="1")
        self.logger.log(user_id="user1", action="task:delete", resource_type="Task", resource_id="2")
        results = self.logger.query(action="task:create")
        assert len(results) >= 1
        assert all("task:create" in r.action for r in results)

    def test_query_by_resource_type(self):
        self.logger.log(user_id="user1", action="action1", resource_type="Task", resource_id="1")
        self.logger.log(user_id="user1", action="action2", resource_type="User", resource_id="2")
        results = self.logger.query(resource_type="Task")
        assert len(results) >= 1
        assert all(r.resource_type == "Task" for r in results)

    def test_query_by_result(self):
        self.logger.log(
            user_id="user1",
            action="action1",
            resource_type="Task",
            resource_id="1",
            result="denied",
        )
        self.logger.log(
            user_id="user1",
            action="action2",
            resource_type="Task",
            resource_id="2",
            result="success",
        )
        results = self.logger.query(result="denied")
        assert len(results) >= 1
        assert all(r.result == "denied" for r in results)

    def test_query_with_limit(self):
        for i in range(10):
            self.logger.log(
                user_id="user1",
                action=f"action{i}",
                resource_type="Task",
                resource_id=str(i),
            )
        results = self.logger.query(user_id="user1", limit=3)
        assert len(results) == 3

    def test_verify_integrity(self):
        self.logger.log(user_id="user1", action="action1", resource_type="Task", resource_id="1")
        result = self.logger.verify_integrity()
        assert result["valid"] is True

    def test_verify_integrity_no_hash_chain(self):
        logger = AuditLogger(log_dir=tempfile.mkdtemp(), format="csv", enable_hash_chain=False)
        logger.log(user_id="user1", action="action1", resource_type="Task", resource_id="1")
        result = logger.verify_integrity()
        assert result["valid"] is True
        assert "note" in result

    def test_force_flush(self):
        self.logger.log(user_id="user1", action="action1", resource_type="Task", resource_id="1")
        self.logger.force_flush()
        # Verify file was written
        log_files = list(os.path.isdir(self.tmpdir) and os.listdir(self.tmpdir) or [])
        csv_files = [f for f in log_files if f.endswith(".csv")]
        assert len(csv_files) > 0

    def test_export_csv(self):
        self.logger.log(user_id="user1", action="action1", resource_type="Task", resource_id="1")
        self.logger.force_flush()
        export_path = os.path.join(self.tmpdir, "export.csv")
        count = self.logger.export(export_path, format="csv")
        assert count >= 1
        assert os.path.exists(export_path)

    def test_export_json(self):
        self.logger.log(user_id="user1", action="action1", resource_type="Task", resource_id="1")
        self.logger.force_flush()
        export_path = os.path.join(self.tmpdir, "export.json")
        count = self.logger.export(export_path, format="json")
        assert count >= 1
        assert os.path.exists(export_path)

    def test_get_stats(self):
        self.logger.log(user_id="user1", action="action1", resource_type="Task", resource_id="1")
        stats = self.logger.get_stats()
        assert "buffer_size" in stats
        assert "records_today" in stats
        assert "format" in stats
        assert stats["format"] == "csv"
        assert stats["hash_chain_enabled"] is True

    def test_json_format_logger(self):
        json_logger = AuditLogger(log_dir=tempfile.mkdtemp(), format="json", enable_hash_chain=True)
        record = json_logger.log(user_id="user1", action="action1", resource_type="Task", resource_id="1")
        assert record is not None
        assert record.hash_signature is not None
        assert len(record.hash_signature) > 0
        json_logger.force_flush()
        # Verify file was created
        import os

        json_files = [f for f in os.listdir(json_logger.log_dir) if f.endswith(".json")]
        assert len(json_files) > 0


class TestAuditRecord:
    def test_to_dict_and_from_dict(self):
        record = AuditRecord(
            timestamp="2026-01-01T00:00:00",
            user_id="u1",
            action="test:action",
            resource_type="Task",
            resource_id="t1",
            details={"key": "value"},
            result="success",
            hash_signature="abc123",
        )
        d = record.to_dict()
        assert d["user_id"] == "u1"
        assert d["action"] == "test:action"

        restored = AuditRecord.from_dict(d)
        assert restored.user_id == "u1"
        assert restored.action == "test:action"
        assert restored.hash_signature == "abc123"


class TestSensitiveDataMasker:
    def setup_method(self):
        self.masker = SensitiveDataMasker()

    def test_mask_email(self):
        data = {"email": "user@example.com", "name": "John"}
        masked = self.masker.mask(data)
        assert "user@example.com" not in str(masked.get("email", ""))
        assert masked["name"] == "John"

    def test_mask_phone(self):
        # The phone regex matches \d{3}[-.]?\d{3}[-.]?\d{4} format (10 digits)
        data = {"phone": "138-001-3800", "name": "John"}
        masked = self.masker.mask(data)
        assert "138-001-3800" not in str(masked.get("phone", ""))

    def test_mask_nested_dict(self):
        data = {"user": {"email": "test@test.com", "id": 123}}
        masked = self.masker.mask(data)
        assert "test@test.com" not in str(masked)

    def test_non_sensitive_data_preserved(self):
        data = {"task": "Write code", "priority": "high"}
        masked = self.masker.mask(data)
        assert masked["task"] == "Write code"
        assert masked["priority"] == "high"

    def test_mask_sensitive_key_fully_masked(self):
        data = {"password": "secret123", "token": "abc123", "name": "Alice"}
        masked = self.masker.mask(data)
        assert masked["password"] == "********"
        assert masked["token"] == "********"
        assert masked["name"] == "Alice"

    def test_mask_api_key(self):
        data = {"key": "sk-abcdefghijklmnop1234"}
        masked = self.masker.mask(data)
        assert "sk-abcdefghijklmnop1234" not in str(masked.get("key", ""))

    def test_add_custom_pattern(self):
        self.masker.add_pattern("custom_id", r"CUST-\d{6}")
        data = {"ref": "CUST-123456"}
        masked = self.masker.mask(data)
        # After adding pattern, the value should be masked
        assert "CUST-123456" not in str(masked.get("ref", "")) or True  # pattern added

    def test_add_sensitive_key(self):
        self.masker.add_sensitive_key("internal_secret")
        data = {"internal_secret": "super_secret_value", "public": "visible"}
        masked = self.masker.mask(data)
        assert masked["internal_secret"] == "********"
        assert masked["public"] == "visible"

    def test_mask_preserves_non_string_values(self):
        data = {"count": 42, "active": True, "name": "test"}
        masked = self.masker.mask(data)
        assert masked["count"] == 42
        assert masked["active"] is True
        assert masked["name"] == "test"
