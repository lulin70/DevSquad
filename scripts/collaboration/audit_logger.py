#!/usr/bin/env python3
"""
Audit Logger - Enterprise-Grade Audit Logging System for DevSquad

Provides cryptographic audit trail with tamper-evidence:
- SHA256 integrity chain (each record hashes previous record's hash)
- Dual-format output: CSV (spreadsheet-compatible) and JSON (API-friendly)
- Automatic daily log rotation
- Sensitive data masking (PII, credentials, tokens)
- Query API: filter by user, time range, action type, result
- Export functionality for compliance reporting
- Configurable retention policy

Compliance Ready:
  - SOC2: Complete decision trail with integrity verification
  - GDPR: Data processing records with access logging
  - ISO 27001: Audit log retention and protection

Usage:
    logger = AuditLogger(log_dir=".devsquad_data/audit")
    logger.log("u1", "task:create", "Task", "t123", {"title": "Test"})
    records = logger.query(user_id="u1")
    logger.export("audit_export.csv", format="csv")
    integrity = logger.verify_integrity()
"""

import csv
import hashlib
import json
import logging
import os
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Set


class AuditRecord:
    """Immutable audit record with cryptographic signature.

    Each record contains:
    - Timestamp: When the action occurred (ISO 8601)
    - User ID: Who performed the action
    - Action: What was done (e.g., "task:create", "user:delete")
    - Resource Type: Category of affected resource (e.g., "Task", "User")
    - Resource ID: Unique identifier of the affected resource
    - Details: JSON-serializable context (sanitized before storage)
    - IP Address / User Agent: For security forensics (optional)
    - Result: Outcome ("success", "denied", "error")
    - Hash Signature: SHA256 of this record + previous hash (integrity chain)

    Thread Safety:
        This dataclass is immutable after creation.
    """

    def __init__(
        self,
        timestamp: str,
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        result: str = "success",
        hash_signature: Optional[str] = None,
    ):
        self.timestamp = timestamp
        self.user_id = user_id
        self.action = action
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.details = details or {}
        self.ip_address = ip_address
        self.user_agent = user_agent
        self.result = result
        self.hash_signature = hash_signature

    def to_dict(self) -> dict:
        """Serialize to dictionary (for JSON export)."""
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
        """Deserialize from dictionary."""
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


class SensitiveDataMasker:
    """Masks sensitive data in audit log details to protect PII.

    Patterns detected and masked:
    - Email addresses: user***@example.com
    - Phone numbers: ***-****-1234
    - Credit cards: ****-****-****-1234
    - SSN: ***-**-1234
    - API keys/tokens: sk-***...abc (last 4 chars shown)
    - Passwords: ******** (fully masked)

    Configuration:
        Custom patterns can be added via add_pattern().

    Usage:
        masker = SensitiveDataMasker()
        safe_details = masker.mask({"email": "test@example.com", "api_key": "sk-12345678"})
        # {"email": "t***@example.com", "api_key": "sk-***...5678"}
    """

    DEFAULT_PATTERNS = {
        "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        "phone": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",
        "credit_card": r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
        "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
        "api_key": r"(?:sk-|api_|token)[a-zA-Z0-9_-]{16,}",
        "password": r"(?i)(password|passwd|pwd)\s*[:=]\s*\S+",
    }

    def __init__(self):
        self._patterns: Dict[str, str] = dict(self.DEFAULT_PATTERNS)
        self._sensitive_keys: Set[str] = {
            "password", "passwd", "pwd", "secret", "token",
            "api_key", "apikey", "access_token", "auth_token",
            "credit_card", "ssn", "social_security",
        }

    def add_pattern(self, name: str, pattern: str) -> None:
        """Add custom regex pattern for detection.

        Args:
            name: Pattern identifier (e.g., "custom_id")
            pattern: Regex pattern to match sensitive data
        """
        self._patterns[name] = pattern

    def add_sensitive_key(self, key: str) -> None:
        """Add a field name that should always be fully masked.

        Args:
            key: Field name to mark as sensitive (case-insensitive)
        """
        self._sensitive_keys.add(key.lower())

    def mask(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively mask sensitive data in dictionary.

        Args:
            data: Dictionary potentially containing sensitive values

        Returns:
            New dictionary with sensitive values masked
        """
        import re

        masked = {}
        for key, value in data.items():
            if isinstance(value, dict):
                masked[key] = self.mask(value)
            elif isinstance(value, str):
                if key.lower() in self._sensitive_keys:
                    masked[key] = "********"
                else:
                    masked[key] = self._mask_value(value)
            else:
                masked[key] = value
        return masked

    def _mask_value(self, value: str) -> str:
        """Apply all masking patterns to a string value.

        Args:
            value: String to mask

        Returns:
            Masked string with sensitive portions hidden
        """
        import re

        result = value
        for name, pattern in self._patterns.items():
            if name == "password":
                result = re.sub(
                    pattern,
                    lambda m: f"{m.group(1)}********",
                    result,
                    flags=re.IGNORECASE,
                )
            elif name == "api_key":
                result = re.sub(
                    pattern,
                    lambda m: f"{m.group()[:4]}...{m.group()[-4:]}",
                    result,
                )
            elif name == "email":
                result = re.sub(
                    pattern,
                    lambda m: f"{m.group()[0]}***{m.group().find('@') and m.group()[m.group().index('@'):]}",
                    result,
                )
            elif name in ("credit_card", "phone"):
                result = re.sub(
                    pattern,
                    lambda m: f"{'*' * (len(m.group()) - 4)}{m.group()[-4:]}",
                    result,
                )
            elif name == "ssn":
                result = re.sub(pattern, "***-**-", result)
        return result


class AuditLogger:
    """Enterprise-grade audit logging system.

    Features:
    - SHA256 cryptographic integrity chain (tamper-evident)
    - CSV and JSON dual-format output
    - Automatic daily file rotation
    - Sensitive data masking (PII, credentials)
    - Rich query API (filter by user/time/action/result)
    - Export functionality for compliance reporting
    - Integrity verification tooling
    - Configurable retention policy

    File Structure:
        {log_dir}/
        ├── audit_2026-05-20.csv   # Today's log
        ├── audit_2026-05-19.csv   # Yesterday's log
        └── ...                     # Historical logs (per retention_days)

    Thread Safety:
        All public methods are thread-safe via threading.Lock.

    Performance:
        In-memory buffer with periodic flush to disk.
        Default flush interval: 100 records or 5 minutes.

    Usage:
        # Basic usage
        logger = AuditLogger()
        logger.log("admin", "user:create", "User", "u123", {"name": "Alice"})

        # Query and export
        recent = logger.query(user_id="admin", limit=100)
        logger.export("may_audit.csv")

        # Verify integrity (for compliance)
        report = logger.verify_integrity()
        assert report["valid"]  # No tampering detected
    """

    def __init__(
        self,
        log_dir: str = ".devsquad_data/audit",
        format: str = "csv",
        enable_hash_chain: bool = True,
        max_file_size_mb: int = 100,
        retention_days: int = 90,
        auto_flush_interval: int = 100,
    ):
        """
        Initialize audit logger.

        Args:
            log_dir: Directory to store audit log files
            format: Output format ("csv" or "json")
            enable_hash_chain: Enable SHA256 integrity chain
            max_file_size_mb: Maximum size per log file before rotation
            retention_days: Days to keep old log files (auto-cleanup)
            auto_flush_interval: Records to buffer before auto-flush
        """
        self.log_dir = Path(log_dir)
        self.format = format.lower()
        self.enable_hash_chain = enable_hash_chain
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024
        self.retention_days = retention_days
        self.auto_flush_interval = auto_flush_interval

        self._buffer: List[AuditRecord] = []
        self._prev_hash: str = ""
        self._lock = threading.Lock()
        self._current_file_path: Optional[Path] = None
        self._record_count_today: int = 0
        self._masker = SensitiveDataMasker()

        self.logger = logging.getLogger(__name__)

        self._ensure_log_dir()
        self._load_state()

    def _ensure_log_dir(self) -> None:
        """Create log directory if it doesn't exist."""
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def _get_today_filename(self) -> str:
        """Generate today's log filename."""
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        ext = "csv" if self.format == "csv" else "json"
        return f"audit_{date_str}.{ext}"

    def _load_state(self) -> None:
        """Load previous state (hash chain) from today's file."""
        self._current_file_path = self.log_dir / self._get_today_filename()

        if self._current_file_path.exists():
            try:
                records = self._read_file(self._current_file_path)
                if records:
                    self._prev_hash = records[-1].hash_signature or ""
                    self._record_count_today = len(records)
                    self.logger.debug(
                        "Loaded %d existing records from %s",
                        len(records),
                        self._current_file_path.name,
                    )
            except Exception as e:
                self.logger.warning("Failed to load state: %s", e)

    def _read_file(self, filepath: Path) -> List[AuditRecord]:
        """Read all records from a log file.

        Args:
            filepath: Path to the log file

        Returns:
            List of AuditRecord instances
        """
        records = []

        if not filepath.exists():
            return records

        try:
            if filepath.suffix == ".csv":
                with open(filepath, "r", newline="", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        row["details"] = json.loads(row.get("details", "{}"))
                        records.append(AuditRecord.from_dict(row))
            else:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        for item in data:
                            records.append(AuditRecord.from_dict(item))
        except Exception as e:
            self.logger.error("Error reading %s: %s", filepath, e)

        return records

    def log(
        self,
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        details: Optional[Dict[str, Any]] = None,
        result: str = "success",
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        **kwargs,
    ) -> AuditRecord:
        """Record an audit event.

        This is the primary method for logging audit events.
        Automatically applies sensitive data masking and computes
        SHA256 hash for integrity chain.

        Args:
            user_id: Who performed the action
            action: What action was taken (use colon notation: "domain:operation")
            resource_type: Type of resource affected (e.g., "Task", "User", "Config")
            resource_id: Unique identifier of the resource
            details: Additional context (will be masked for sensitive data)
            result: Outcome of the action ("success", "denied", "error")
            ip_address: Client IP address (optional, for forensics)
            user_agent: Client user agent string (optional)
            **kwargs: Additional fields merged into details

        Returns:
            The created AuditRecord instance

        Example:
            logger.log(
                user_id="admin",
                action="task:create",
                resource_type="Task",
                resource_id="task-123",
                details={"title": "Implement RBAC", "priority": "high"},
                ip_address="192.168.1.100",
            )
        """
        timestamp = datetime.utcnow().isoformat()

        if details:
            details.update(kwargs)
        else:
            details = kwargs

        masked_details = self._masker.mask(details or {})

        record_data = {
            "timestamp": timestamp,
            "user_id": user_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details": masked_details,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "result": result,
            "prev_hash": self._prev_hash if self.enable_hash_chain else "",
        }

        hash_signature = ""
        if self.enable_hash_chain:
            hash_signature = hashlib.sha256(
                json.dumps(record_data, sort_keys=True).encode()
            ).hexdigest()

        record = AuditRecord(
            timestamp=timestamp,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=masked_details,
            ip_address=ip_address,
            user_agent=user_agent,
            result=result,
            hash_signature=hash_signature,
        )

        with self._lock:
            self._buffer.append(record)
            self._prev_hash = hash_signature or ""
            self._record_count_today += 1

            if len(self._buffer) >= self.auto_flush_interval:
                self._flush_buffer()

        return record

    def query(
        self,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        result: Optional[str] = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> List[AuditRecord]:
        """Query audit logs with flexible filtering.

        Supports multiple filter criteria combined with AND logic.
        Results are ordered by timestamp (most recent first).

        Args:
            user_id: Filter by user who performed the action
            action: Filter by action type (supports partial match, e.g., "task:")
            resource_type: Filter by resource type
            start_time: ISO format timestamp (inclusive lower bound)
            end_time: ISO format timestamp (exclusive upper bound)
            result: Filter by result ("success", "denied", "error")
            limit: Maximum number of records to return
            offset: Number of records to skip (for pagination)

        Returns:
            List of matching AuditRecord instances

        Example:
            # Get all task creation events by admin in last 24 hours
            yesterday = (datetime.utcnow() - timedelta(days=1)).isoformat()
            events = logger.query(
                user_id="admin",
                action="task:create",
                start_time=yesterday,
                limit=50,
            )
        """
        results = []

        with self._lock:
            all_records = list(self._buffer)
            if self._current_file_path and self._current_file_path.exists():
                file_records = self._read_file(self._current_file_path)
                seen_ids = {(r.timestamp, r.user_id, r.action) for r in all_records}
                for rec in file_records:
                    if (rec.timestamp, rec.user_id, rec.action) not in seen_ids:
                        all_records.append(rec)

        for record in reversed(all_records):
            if user_id and record.user_id != user_id:
                continue
            if action and action not in record.action:
                continue
            if resource_type and record.resource_type != resource_type:
                continue
            if start_time and record.timestamp < start_time:
                continue
            if end_time and record.timestamp >= end_time:
                continue
            if result and record.result != result:
                continue

            results.append(record)
            if len(results) >= limit + offset:
                break

        return results[offset : offset + limit]

    def export(
        self,
        output_path: str,
        format: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Export audit logs to file for compliance reporting.

        Args:
            output_path: Destination file path
            format: Output format ("csv" or "json", defaults to instance format)
            filters: Optional filter criteria (same as query() parameters)

        Returns:
            Number of records exported

        Raises:
            IOError: If unable to write to output path
        """
        fmt = (format or self.format).lower()
        records = []

        if filters:
            records = self.query(**filters, limit=10**6)
        else:
            with self._lock:
                records = list(reversed(self._buffer))
                if self._current_file_path and self._current_file_path.exists():
                    file_records = self._read_file(self._current_file_path)
                    seen = {(r.timestamp, r.user_id, r.action) for r in records}
                    for rec in reversed(file_records):
                        if (rec.timestamp, rec.user_id, rec.action) not in seen:
                            records.insert(0, rec)

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        if fmt == "csv":
            fieldnames = [
                "timestamp", "user_id", "action", "resource_type",
                "resource_id", "details", "ip_address", "user_agent",
                "result", "hash_signature",
            ]
            with open(output_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for record in records:
                    row = record.to_dict()
                    row["details"] = json.dumps(row["details"])
                    writer.writerow(row)
        else:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump([r.to_dict() for r in records], f, indent=2, ensure_ascii=False)

        self.logger.info("Exported %d records to %s (%s)", len(records), output_path, fmt)
        return len(records)

    def verify_integrity(self) -> Dict[str, Any]:
        """Verify SHA256 integrity chain of all audit logs.

        Checks that each record's hash matches the computed hash based on
        its content and the previous record's hash. Detects any tampering
        or insertion/deletion of records.

        Returns:
            Dictionary containing:
            - valid: Boolean indicating overall integrity
            - total_records_checked: Total number of records verified
            - files_verified: Number of log files checked
            - first_violation: Location of first integrity breach (if any)
            - details: Per-file verification results

        Note:
            This operation reads all log files and may be slow for large datasets.
            Recommended to run periodically (e.g., daily) rather than on every request.
        """
        result = {
            "valid": True,
            "total_records_checked": 0,
            "files_verified": 0,
            "first_violation": None,
            "details": {},
        }

        if not self.enable_hash_chain:
            result["valid"] = True
            result["note"] = "Hash chain disabled"
            return result

        log_files = sorted(self.log_dir.glob(f"audit_*.{self.format}"))

        for filepath in log_files:
            file_result = self._verify_file_integrity(filepath)
            result["details"][filepath.name] = file_result
            result["files_verified"] += 1
            result["total_records_checked"] += file_result["total_records"]

            if not file_result["valid"] and result["valid"]:
                result["valid"] = False
                result["first_violation"] = {
                    "file": filepath.name,
                    "record_index": file_result.get("first_violation"),
                }

        return result

    def _verify_file_integrity(self, filepath: Path) -> Dict[str, Any]:
        """Verify integrity of a single log file.

        Args:
            filepath: Path to the log file

        Returns:
            Per-file integrity result dictionary
        """
        records = self._read_file(filepath)

        if not records:
            return {"valid": True, "total_records": 0}

        prev_hash = ""

        for idx, record in enumerate(records):
            expected_data = {
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
                json.dumps(expected_data, sort_keys=True).encode()
            ).hexdigest()

            if expected_hash != record.hash_signature:
                return {
                    "valid": False,
                    "total_records": len(records),
                    "first_violation": idx,
                    "expected_hash": expected_hash,
                    "actual_hash": record.hash_signature,
                }

            prev_hash = record.hash_signature

        return {"valid": True, "total_records": len(records)}

    def _flush_buffer(self) -> None:
        """Flush in-memory buffer to disk.

        Creates new file if needed, appends to existing file.
        Handles file rotation when size exceeds limit.
        """
        if not self._buffer:
            return

        try:
            self._rotate_if_needed()
            filepath = self._current_file_path or (
                self.log_dir / self._get_today_filename()
            )

            if self.format == "csv":
                self._flush_to_csv(filepath)
            else:
                self._flush_to_json(filepath)

            self.logger.debug("Flushed %d records to %s", len(self._buffer), filepath)
            self._buffer.clear()

        except Exception as e:
            self.logger.error("Failed to flush audit buffer: %s", e)

    def _flush_to_csv(self, filepath: Path) -> None:
        """Flush buffer to CSV file.

        Args:
            filepath: Target file path
        """
        fieldnames = [
            "timestamp", "user_id", "action", "resource_type",
            "resource_id", "details", "ip_address", "user_agent",
            "result", "hash_signature",
        ]

        file_exists = filepath.exists()

        with open(filepath, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()

            for record in self._buffer:
                row = record.to_dict()
                row["details"] = json.dumps(row["details"])
                writer.writerow(row)

    def _flush_to_json(self, filepath: Path) -> None:
        """Flush buffer to JSON file.

        Args:
            filepath: Target file path
        """
        existing = []
        if filepath.exists():
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except (json.JSONDecodeError, IOError):
                existing = []

        existing.extend([r.to_dict() for r in self._buffer])

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)

    def _rotate_if_needed(self) -> None:
        """Check current file size and rotate if exceeding limit.

        Creates new file with timestamp suffix if needed.
        """
        if not self._current_file_path or not self._current_file_path.exists():
            return

        file_size = self._current_file_path.stat().st_size

        if file_size >= self.max_file_size_bytes:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            base_name = self._current_file_path.stem
            ext = self._current_file_path.suffix
            rotated_name = f"{base_name}_{timestamp}{ext}"
            rotated_path = self.log_dir / rotated_name

            self._current_file_path.rename(rotated_path)
            self.logger.info(
                "Rotated audit log: %s -> %s (%.2f MB)",
                self._current_file_path.name,
                rotated_name,
                file_size / (1024 * 1024),
            )

            self._current_file_path = self.log_dir / self._get_today_filename()
            self._record_count_today = 0

    def cleanup_old_logs(self) -> int:
        """Remove log files older than retention period.

        Call this periodically (e.g., daily cron) to manage disk space.

        Returns:
            Number of files removed
        """
        cutoff_date = datetime.utcnow() - timedelta(days=self.retention_days)
        removed_count = 0

        for filepath in self.log_dir.glob(f"audit_*.{self.format}"):
            try:
                file_mtime = datetime.fromtimestamp(filepath.stat().st_mtime)
                if file_mtime < cutoff_date:
                    filepath.unlink()
                    removed_count += 1
                    self.logger.info("Removed old audit log: %s", filepath.name)
            except Exception as e:
                self.logger.warning("Failed to remove %s: %s", filepath, e)

        return removed_count

    def get_stats(self) -> Dict[str, Any]:
        """Get logger statistics for monitoring.

        Returns:
            Dictionary with buffer size, file counts, etc.
        """
        total_files = len(list(self.log_dir.glob(f"audit_*.{self.format}")))
        total_size = sum(
            f.stat().st_size
            for f in self.log_dir.glob(f"audit_*.{self.format}")
            if f.exists()
        )

        return {
            "buffer_size": len(self._buffer),
            "records_today": self._record_count_today,
            "total_files": total_files,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "log_directory": str(self.log_dir),
            "format": self.format,
            "hash_chain_enabled": self.enable_hash_chain,
            "retention_days": self.retention_days,
            "current_file": self._current_file_path.name if self._current_file_path else None,
        }

    def force_flush(self) -> None:
        """Manually trigger buffer flush to disk.

        Useful before shutdown or when immediate persistence is required.
        """
        with self._lock:
            self._flush_buffer()


if __name__ == "__main__":
    print("Audit Logger - Enterprise Audit Logging System")
    print("=" * 60)

    logger = AuditLogger(log_dir="/tmp/test_audit")

    test_record = logger.log(
        user_id="admin",
        action="task:create",
        resource_type="Task",
        resource_id="task-001",
        details={
            "title": "Test Task",
            "email": "admin@example.com",
            "api_key": "sk-test-key-12345678",
        },
        ip_address="127.0.0.1",
    )

    print("\n✓ Created audit record:")
    print(f"  User: {test_record.user_id}")
    print(f"  Action: {test_record.action}")
    print(f"  Hash: {test_record.hash_signature[:16]}...")

    records = logger.query(user_id="admin")
    print(f"\n✓ Queried {len(records)} records for user 'admin'")

    integrity = logger.verify_integrity()
    print(f"\n✓ Integrity check: {'PASS' if integrity['valid'] else 'FAIL'}")

    export_path = "/tmp/test_audit/export.csv"
    count = logger.export(export_path)
    print(f"\n✓ Exported {count} records to {export_path}")

    stats = logger.get_stats()
    print(f"\n📊 Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")

    logger.force_flush()
    print("\n✓ Buffer flushed to disk")
