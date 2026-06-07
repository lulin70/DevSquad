#!/usr/bin/env python3
"""
Structured JSON Logging for DevSquad

Production-grade structured logging with JSON output format.
Provides sensitive data masking, field filtering, and compatibility
with standard Python logging.

Usage:
    from scripts.collaboration.structured_logging import (
        setup_structured_logging,
        get_json_logger,
    )

    # Setup global logging
    setup_structured_logging(level=logging.INFO)

    # Get logger
    logger = get_json_logger("my_module")
    logger.info("Task completed", extra={"task_id": "abc123", "duration_ms": 150})

Output:
    {"timestamp":"2024-01-15T10:30:00.000Z","level":"INFO","logger":"my_module",
     "message":"Task completed","task_id":"abc123","duration_ms":150,...}
"""

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any


class SensitiveDataFilter:
    """
    Filter for masking sensitive data in log messages.

    Patterns detected:
    - API keys: sk-*, api_key=*
    - Tokens: bearer *, authorization headers
    - Passwords: password=*, passwd=*
    - Email addresses (partial mask)
    - IP addresses (optional)
    """

    SENSITIVE_PATTERNS = [
        (re.compile(r'(api[_-]?key["\s]*[:=]\s*)["\']?[\w\-]{20,}["\']?', re.IGNORECASE), r'\1***'),
        (re.compile(r'(sk-[a-zA-Z0-9]{20,})'), r'***'),
        (re.compile(r'(bearer\s+)[^\s]+', re.IGNORECASE), r'\1***'),
        (re.compile(r'(authorization["\s]*[:=]\s*)[^\s,}"]+', re.IGNORECASE), r'\1***'),
        (re.compile(r'(password["\s]*[:=]\s*)[^\s,}"]+', re.IGNORECASE), r'\1***'),
        (re.compile(r'(passwd["\s]*[:=]\s*)[^\s,}"]+', re.IGNORECASE), r'\1***'),
        (re.compile(r'(secret["\s]*[:=]\s*)[^\s,}"]+', re.IGNORECASE), r'\1***'),
        (re.compile(r'(token["\s]*[:=]\s*)[^\s,}"]{10,}', re.IGNORECASE), r'\1***'),
        (re.compile(r'([\w.+-]+@[\w-]+\.[\w.-]*)', re.IGNORECASE), lambda m: _mask_email(m.group(1))),
    ]

    @classmethod
    def mask(cls, text: str) -> str:
        """
        Apply all sensitive data patterns to mask values.

        Args:
            text: Input text that may contain sensitive data

        Returns:
            Text with sensitive values masked
        """
        result = text
        for pattern, replacement in cls.SENSITIVE_PATTERNS:
            result = pattern.sub(replacement, result)
        return result

    @classmethod
    def mask_dict(cls, data: dict[str, Any]) -> dict[str, Any]:
        """
        Recursively mask sensitive fields in a dictionary.

        Args:
            data: Dictionary potentially containing sensitive data

        Returns:
            Dictionary with sensitive values masked
        """
        sensitive_keys = {
            "api_key", "apikey", "api-key", "secret", "token", "password",
            "passwd", "authorization", "auth", "credential", "key",
        }

        masked = {}
        for key, value in data.items():
            if key.lower() in sensitive_keys:
                if isinstance(value, str) and len(value) > 3:
                    masked[key] = value[:3] + "***"
                else:
                    masked[key] = "***"
            elif isinstance(value, dict):
                masked[key] = cls.mask_dict(value)
            elif isinstance(value, str):
                masked[key] = cls.mask(value)
            else:
                masked[key] = value
        return masked


def _mask_email(email: str) -> str:
    """Mask email address preserving domain."""
    if "@" not in email:
        return email
    local, domain = email.rsplit("@", 1)
    if len(local) <= 2:
        return f"***@{domain}"
    return f"{local[0]}***@{domain}"


class StructuredFormatter(logging.Formatter):
    """
    JSON Structured Log Formatter for Production.

    Outputs logs in JSON format with consistent structure.
    Compatible with log aggregation systems like ELK, Loki, etc.
    """

    DEFAULT_FIELDS = [
        "timestamp", "level", "logger", "message", "module",
        "function", "line", "thread_name", "process",
    ]

    def __init__(
        self,
        *,
        mask_sensitive: bool = True,
        include_extra: bool = True,
        exclude_fields: list[str] | None = None,
        static_fields: dict[str, Any] | None = None,
    ):
        """
        Initialize the structured formatter.

        Args:
            mask_sensitive: Enable sensitive data masking
            include_extra: Include LogRecord.extra fields in output
            exclude_fields: Fields to exclude from output
            static_fields: Additional static fields added to every log entry
        """
        super().__init__()
        self.mask_sensitive = mask_sensitive
        self.include_extra = include_extra
        self.exclude_fields = set(exclude_fields or [])
        self.static_fields = static_fields or {}

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON string.

        Args:
            record: Python logging LogRecord

        Returns:
            JSON formatted log string
        """
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc)

        log_obj: dict[str, Any] = {
            "timestamp": timestamp.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": self._format_message(record),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "thread_name": record.threadName,
            "process": record.process,
        }

        if record.exc_info and record.exc_info[0] is not None:
            log_obj["exception"] = self.formatException(record.exc_info)

        if record.stack_info:
            log_obj["stack_info"] = self.formatStack(record.stack_info)

        if self.include_extra:
            extra_fields = {
                key: value
                for key, value in vars(record).items()
                if key not in {
                    "name", "msg", "args", "created", "relativeCreated",
                    "thread", "threadName", "msecs", "filename", "funcName",
                    "levelname", "levelno", "pathname", "lineno", "module",
                    "exc_info", "exc_text", "stack_info",
                    "getMessage", "process", "processName", "taskName",
                    "message",
                }
                and key not in self.exclude_fields
                and not key.startswith("_")
            }
            if extra_fields:
                log_obj.update(extra_fields)

        if self.static_fields:
            log_obj.update(self.static_fields)

        if self.mask_sensitive:
            log_obj = self._mask_log_object(log_obj)

        return json.dumps(log_obj, default=str, ensure_ascii=False)

    def _format_message(self, record: logging.LogRecord) -> str:
        """Format message with optional sensitive data masking."""
        message = record.getMessage()
        if self.mask_sensitive:
            message = SensitiveDataFilter.mask(message)
        return message

    def _mask_log_object(self, obj: dict[str, Any]) -> dict[str, Any]:
        """Apply masking to entire log object."""
        return SensitiveDataFilter.mask_dict(obj)


class FieldFilter(logging.Filter):
    """
    Logging filter to include/exclude specific fields.

    Usage:
        handler.addFilter(FieldFilter(include=["request_id", "user_id"]))
        handler.addFilter(FieldFilter(exclude=["debug_info"]))
    """

    def __init__(self, include: list[str] | None = None, exclude: list[str] | None = None):
        super().__init__()
        self.include = set(include or [])
        self.exclude = set(exclude or [])

    def filter(self, record: logging.LogRecord) -> bool:
        if self.include:
            record.__dict__ = {k: v for k, v in record.__dict__.items() if k in self.include or k in {"name", "msg", "args", "created", "levelname", "levelno", "exc_info", "stack_info", "getMessage"}}
        if self.exclude:
            for field in self.exclude:
                record.__dict__.pop(field, None)
        return True


def setup_structured_logging(
    level: int = logging.INFO,
    *,
    mask_sensitive: bool = True,
    service_name: str = "devsquad",
    environment: str = "production",
    log_file: str | None = None,
) -> logging.Logger:
    """
    Configure root logger with structured JSON formatter.

    Args:
        level: Logging level (logging.INFO, logging.DEBUG, etc.)
        mask_sensitive: Enable sensitive data masking
        service_name: Service name included in log entries
        environment: Environment name (production/staging/development)
        log_file: Optional file path for file logging

    Returns:
        Configured root logger
    """
    root_logger = logging.getLogger()

    static_fields = {
        "service": service_name,
        "environment": environment,
    }

    formatter = StructuredFormatter(
        mask_sensitive=mask_sensitive,
        static_fields=static_fields,
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)

    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    root_logger.setLevel(level)

    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    return root_logger


def get_json_logger(name: str) -> logging.Logger:
    """
    Get a logger configured for structured JSON output.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)


class LoggingContext:
    """
    Context manager for adding temporary fields to log records.

    Usage:
        with LoggingContext(request_id="abc123", user_id="user1"):
            logger.info("Processing request")
            # All logs within this block will have request_id and user_id
    """

    def __init__(self, **fields: Any):
        self.fields = fields
        self.old_factory = None

    def __enter__(self):
        self.old_factory = logging.getLogRecordFactory()

        def record_factory(*args, **kwargs):
            record = self.old_factory(*args, **kwargs)
            for key, value in self.fields.items():
                setattr(record, key, value)
            return record

        logging.setLogRecordFactory(record_factory)
        return self

    def __exit__(self, *args):
        if self.old_factory:
            logging.setLogRecordFactory(self.old_factory)


def install_prometheus_logging(metrics_instance=None) -> None:
    """
    Install a logging handler that emits metrics on error/warning events.

    Automatically counts log levels as Prometheus metrics.

    Args:
        metrics_instance: Optional DevSquadMetrics instance (uses default if None)
    """
    try:
        from scripts.collaboration.prometheus_metrics import get_metrics as _get_metrics

        if metrics_instance is None:
            metrics_instance = _get_metrics()
    except ImportError:
        return

    class MetricsHandler(logging.Handler):
        def emit(self, record: logging.LogRecord):
            if record.levelno >= logging.ERROR:
                error_type = "log_error" if record.levelno == logging.ERROR else "log_critical"
                metrics_instance.record_error(error_type, record.name)
            elif record.levelno == logging.WARNING:
                pass

    root = logging.getLogger()
    metrics_handler = MetricsHandler()
    metrics_handler.setLevel(logging.WARNING)
    root.addHandler(metrics_handler)
