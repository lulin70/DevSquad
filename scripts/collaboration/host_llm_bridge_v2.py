#!/usr/bin/env python3
"""HostLLMBridge v2 (V4.5.5).

V2 协议升级（对齐 weiransoft/TraeMultiAgentSkill v2.8.4）:
- marker 7 字段 (request_id/agent_type/task/request_file/prompt_file/timeout_seconds/timestamp)
- prompt 独立文件 (request_{id}.prompt)
- request_file 路径越界校验 (os.path.commonpath)

向后兼容:
- read_marker() 自动检测字段数 (2 字段 v1 / 7 字段 v2)
- create_request() 仅生成 v2 格式 (不再生成 v1)
- 旧 v1 marker 在启动时一次性清理为 protocol.marker.v1.bak

设计原则 (V4.5.3 lessons):
- lesson #1: __slots__ + __init__ 双管齐下
- lesson #7: best-effort try/except (marker 清理 + 文件 IO)
- lesson #8: global state + lock pattern (_call_counter_er + _call_counter_lock)
- V4.5.4 lesson #4: 命名统一 _call_counter_er (SSOT 在 module_fiber.py)
- V4.5.4 lesson #7: 原子写入 (tempfile + os.replace)

Anti-Ghost: _call_counter_er 递增 on create_request/write_response/read_request。
"""
from __future__ import annotations

import json
import logging
import os
import re
import tempfile
import threading
import time
import uuid
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level Anti-Ghost counter (V4.5.3 lesson #4 naming unified)
# ---------------------------------------------------------------------------
_call_counter_er: int = 0
_call_counter_lock = threading.Lock()


def _inc_call_counter_er() -> None:
    """Increment HostLLMBridge v2 module activation counter (thread-safe)."""
    global _call_counter_er
    with _call_counter_lock:
        _call_counter_er += 1


def get_call_counter_er() -> int:
    """Return module activation counter (for Anti-Ghost verification).

    CI (scripts/check_module_activation.py) asserts this > 0 after dispatch.
    """
    return _call_counter_er


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# V2 marker fields (full routing context for host LLM)
MARKER_V2_FIELDS: tuple[str, ...] = (
    "request_id",
    "agent_type",
    "task",
    "request_file",
    "prompt_file",
    "timeout_seconds",
    "timestamp",
)

# V1 legacy fields (backward-compat read only)
MARKER_V1_FIELDS: tuple[str, ...] = ("request_id", "ts")


class HostLLMBridgeV2Error(ValueError):
    """Base error for HostLLMBridge v2 protocol violations."""


class InvalidRequestIdError(HostLLMBridgeV2Error):
    """Raised when request_id format is invalid (security)."""


class RequestFilePathError(HostLLMBridgeV2Error):
    """Raised when request_file path is outside bridge_dir (security)."""


@dataclass(frozen=True, slots=True)
class MarkerV2:
    """V2 marker dataclass (immutable, type-safe)."""

    request_id: str
    agent_type: str
    task: str
    request_file: str
    prompt_file: str
    timeout_seconds: int
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize to JSON-compatible dict (preserves key order)."""
        return {
            "request_id": self.request_id,
            "agent_type": self.agent_type,
            "task": self.task,
            "request_file": self.request_file,
            "prompt_file": self.prompt_file,
            "timeout_seconds": self.timeout_seconds,
            "timestamp": self.timestamp,
        }


class HostLLMBridgeV2:
    """V2 协议: marker 7 字段 + prompt 独立 + commonpath 安全校验."""

    DEFAULT_TIMEOUT = 600
    POLL_INTERVAL = 0.5
    MAX_JSON_RETRIES = 3
    JSON_RETRY_INTERVAL = 0.1
    MAX_REQUEST_ID_LEN = 128
    REQUEST_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_]{1,128}$")

    MARKER_FILENAME = "protocol.marker"
    MARKER_V1_BACKUP_SUFFIX = ".v1.bak"

    def __init__(self, bridge_dir: str | Path | None = None) -> None:
        """Initialize v2 bridge.

        Args:
            bridge_dir: Override bridge directory. Defaults to
                ``<project_root>/logs/host_llm_bridge`` (auto-created).
        """
        _inc_call_counter_er()
        if bridge_dir is None:
            bridge_dir = self._default_bridge_dir()
        self.bridge_dir = Path(bridge_dir)
        self.bridge_dir.mkdir(parents=True, exist_ok=True)
        # Cleanup legacy v1 marker (one-time migration on init)
        self._migrate_legacy_marker_v1()

    @staticmethod
    def _default_bridge_dir() -> Path:
        """Default bridge dir: <project_root>/logs/host_llm_bridge."""
        # scripts/collaboration/host_llm_bridge_v2.py → project root is 3 levels up
        here = Path(__file__).resolve().parent.parent.parent
        return here / "logs" / "host_llm_bridge"

    # ---- public API ----

    def create_request(
        self,
        agent_type: str,
        task: str,
        context: dict[str, Any] | None,
        prompt: str,
        timeout_seconds: int | None = None,
    ) -> str:
        """Create v2 request: writes 3 files atomically.

        Files:
            request_{id}.json  — full request metadata (incl. prompt inline)
            request_{id}.prompt — prompt-only file (host LLM can stream-read)
            protocol.marker    — 7-field marker (overwrite)

        Returns:
            request_id (format: ``{timestamp}_{uuid_short}``).
        """
        _inc_call_counter_er()
        timeout = timeout_seconds if timeout_seconds else self.DEFAULT_TIMEOUT
        request_id = self._generate_request_id()
        self._assert_safe_id(request_id)

        # 1. request_{id}.json — full metadata
        request_data = {
            "request_id": request_id,
            "agent_type": agent_type,
            "task": task,
            "context": context or {},
            "prompt": prompt,
            "timeout_seconds": timeout,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "request_file": str(self._request_path(request_id)),
            "prompt_file": str(self._prompt_path(request_id)),
        }
        self._write_json_atomic(self._request_path(request_id), request_data)

        # 2. request_{id}.prompt — prompt-only file
        self._write_prompt_atomic(self._prompt_path(request_id), prompt)

        # 3. protocol.marker — 7-field v2 marker
        marker = MarkerV2(
            request_id=request_id,
            agent_type=agent_type,
            task=task,
            request_file=str(self._request_path(request_id)),
            prompt_file=str(self._prompt_path(request_id)),
            timeout_seconds=timeout,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self._write_marker_v2(marker)

        logger.info(
            "HostLLMBridgeV2.create_request: %s (agent=%s, timeout=%ds)",
            request_id, agent_type, timeout,
        )
        return request_id

    def wait_for_response(
        self,
        request_id: str,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        """Poll response_{id}.json until success/failure/timeout.

        Returns dict: {success, output, error, timeout, request_id}.
        """
        _inc_call_counter_er()
        if not self.validate_request_id(request_id):
            return {
                "success": False,
                "error": f"invalid request_id: {request_id}",
                "timeout": False,
                "request_id": request_id,
            }
        timeout_val = timeout if timeout else self.DEFAULT_TIMEOUT
        response_path = self._response_path(request_id)
        deadline = time.monotonic() + timeout_val
        while time.monotonic() < deadline:
            if response_path.exists():
                data = self._try_read_json(response_path)
                if data is not None:
                    self._cleanup_request_files(request_id)
                    return {
                        "success": data.get("success", False),
                        "output": data.get("output", ""),
                        "error": data.get("error", ""),
                        "timeout": False,
                        "request_id": request_id,
                    }
            time.sleep(self.POLL_INTERVAL)
        return {
            "success": False,
            "error": f"timeout after {timeout_val}s waiting for response",
            "timeout": True,
            "request_id": request_id,
        }

    @staticmethod
    def write_response(
        request_id: str,
        success: bool,
        output: str,
        error: str = "",
        bridge_dir: str | Path | None = None,
    ) -> str:
        """Write response file atomically (for host LLM to call).

        Returns absolute response file path.
        """
        _inc_call_counter_er()
        if not HostLLMBridgeV2.validate_request_id(request_id):
            raise InvalidRequestIdError(f"invalid request_id: {request_id!r}")
        bdir = (
            Path(bridge_dir)
            if bridge_dir
            else HostLLMBridgeV2._default_bridge_dir()
        )
        bdir.mkdir(parents=True, exist_ok=True)
        response_path = bdir / f"response_{request_id}.json"
        response_data = {
            "request_id": request_id,
            "success": success,
            "output": output,
            "error": error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        HostLLMBridgeV2._write_json_atomic_static(response_path, response_data)
        # Clear marker (best-effort, V4.5.3 lesson #7)
        marker_path = bdir / HostLLMBridgeV2.MARKER_FILENAME
        with suppress(OSError):
            marker_path.unlink(missing_ok=True)
        return str(response_path)

    @staticmethod
    def read_request(
        request_id: str,
        bridge_dir: str | Path | None = None,
    ) -> dict[str, Any] | None:
        """Read request_{id}.json with commonpath security check."""
        _inc_call_counter_er()
        if not HostLLMBridgeV2.validate_request_id(request_id):
            raise InvalidRequestIdError(f"invalid request_id: {request_id!r}")
        bdir = (
            Path(bridge_dir)
            if bridge_dir
            else HostLLMBridgeV2._default_bridge_dir()
        )
        request_path = bdir / f"request_{request_id}.json"
        if not request_path.exists():
            return None
        with open(request_path, encoding="utf-8") as f:
            data = json.load(f)
        # Security: validate request_file path stays inside bridge_dir
        request_file = data.get("request_file", "")
        if request_file:
            HostLLMBridgeV2._validate_request_file_path(request_file, bdir)
        return data

    @staticmethod
    def read_marker(
        bridge_dir: str | Path | None = None,
    ) -> dict[str, Any] | None:
        """Read marker, backward-compatible with v1 2-field format."""
        _inc_call_counter_er()
        bdir = (
            Path(bridge_dir)
            if bridge_dir
            else HostLLMBridgeV2._default_bridge_dir()
        )
        marker_path = bdir / HostLLMBridgeV2.MARKER_FILENAME
        if not marker_path.exists():
            return None
        try:
            with open(marker_path, encoding="utf-8") as f:
                content = f.read().strip()
            if not content:
                return None
            data = json.loads(content)
            # Detect v1 vs v2: 2-field vs 7-field
            if "agent_type" in data:
                return {**data, "_format": "v2"}
            return {**data, "_format": "v1"}  # backward compat
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("HostLLMBridgeV2.read_marker failed: %s", exc)
            return None

    @staticmethod
    def clear_marker(bridge_dir: str | Path | None = None) -> None:
        """Clear marker file (best-effort)."""
        bdir = (
            Path(bridge_dir)
            if bridge_dir
            else HostLLMBridgeV2._default_bridge_dir()
        )
        marker_path = bdir / HostLLMBridgeV2.MARKER_FILENAME
        with suppress(OSError):
            marker_path.unlink(missing_ok=True)

    @staticmethod
    def validate_request_id(request_id: str) -> bool:
        """Validate request_id format: ``[a-zA-Z0-9_]{1,128}``.

        Returns True if valid, False otherwise.
        """
        if not isinstance(request_id, str) or not request_id:
            return False
        return bool(HostLLMBridgeV2.REQUEST_ID_PATTERN.match(request_id))

    # ---- private helpers ----

    def _generate_request_id(self) -> str:
        """Generate unique request_id: ``{YYYYMMDD_HHMMSS}_{uuid8}``."""
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        short_uuid = uuid.uuid4().hex[:8]
        return f"{ts}_{short_uuid}"

    def _request_path(self, request_id: str) -> Path:
        return self.bridge_dir / f"request_{request_id}.json"

    def _prompt_path(self, request_id: str) -> Path:
        return self.bridge_dir / f"request_{request_id}.prompt"

    def _response_path(self, request_id: str) -> Path:
        return self.bridge_dir / f"response_{request_id}.json"

    def _marker_path(self) -> Path:
        return self.bridge_dir / self.MARKER_FILENAME

    def _write_marker_v2(self, marker: MarkerV2) -> None:
        """Write 7-field v2 marker (overwrite)."""
        data = marker.to_dict()
        self._write_json_atomic(self._marker_path(), data)

    def _write_prompt_atomic(self, path: Path, prompt: str) -> None:
        """Write prompt-only file atomically (text mode)."""
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(prompt)
        os.replace(str(tmp_path), str(path))

    def _write_json_atomic(self, path: Path, data: dict[str, Any]) -> None:
        """Atomic JSON write (tempfile + os.replace)."""
        self.__class__._write_json_atomic_static(path, data)

    @staticmethod
    def _write_json_atomic_static(path: Path, data: dict[str, Any]) -> None:
        """Atomic JSON write (static, shared by all writers)."""
        # Write to tmp first, then rename (atomic on POSIX)
        fd, tmp_str = tempfile.mkstemp(
            dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_str, str(path))
        except Exception:
            # Cleanup tmp on failure (V4.5.3 lesson #7)
            with suppress(OSError):
                os.unlink(tmp_str)
            raise

    def _try_read_json(self, path: Path) -> dict[str, Any] | None:
        """Tolerant reader: handles partially-written JSON with retries."""
        for _ in range(self.MAX_JSON_RETRIES):
            try:
                with open(path, encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                time.sleep(self.JSON_RETRY_INTERVAL)
            except OSError as exc:
                logger.warning("read %s: %s", path, exc)
                return None
        logger.warning("JSON decode failed after %d retries: %s", self.MAX_JSON_RETRIES, path)
        return None

    def _cleanup_request_files(self, request_id: str) -> None:
        """Cleanup request + prompt files after response read."""
        for path in (self._request_path(request_id), self._prompt_path(request_id)):
            with suppress(OSError):
                path.unlink(missing_ok=True)

    def _migrate_legacy_marker_v1(self) -> None:
        """One-time migration: backup v1 marker if detected."""
        marker_path = self._marker_path()
        if not marker_path.exists():
            return
        try:
            with open(marker_path, encoding="utf-8") as f:
                content = f.read().strip()
            if not content:
                return
            data = json.loads(content)
            # Detect v1: no agent_type field
            if "agent_type" not in data:
                backup = marker_path.with_name(
                    marker_path.name + self.MARKER_V1_BACKUP_SUFFIX
                )
                os.replace(str(marker_path), str(backup))
                logger.info(
                    "HostLLMBridgeV2: migrated v1 marker → %s", backup.name
                )
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("v1 marker migration skipped: %s", exc)

    @staticmethod
    def _validate_request_file_path(
        request_file: str,
        bridge_dir: Path,
    ) -> None:
        """Security: request_file must be inside bridge_dir.

        Raises RequestFilePathError if path traversal detected.
        """
        try:
            abs_req = os.path.abspath(request_file)
            abs_bridge = os.path.abspath(str(bridge_dir))
            common = os.path.commonpath([abs_req, abs_bridge])
            if common != abs_bridge:
                raise RequestFilePathError(
                    f"request_file outside bridge_dir: {request_file}"
                )
        except ValueError as exc:
            # commonpath may raise on different drives (Windows) — re-raise as security error
            raise RequestFilePathError(
                f"request_file path validation failed: {request_file}: {exc}"
            ) from exc

    @staticmethod
    def _assert_safe_id(request_id: str) -> None:
        if not HostLLMBridgeV2.validate_request_id(request_id):
            raise InvalidRequestIdError(
                f"invalid request_id (must match [a-zA-Z0-9_]{{1,128}}): {request_id!r}"
            )


__all__ = [
    "HostLLMBridgeV2",
    "MarkerV2",
    "HostLLMBridgeV2Error",
    "InvalidRequestIdError",
    "RequestFilePathError",
    "MARKER_V2_FIELDS",
    "MARKER_V1_FIELDS",
    "get_call_counter_er",
    "_inc_call_counter_er",
]
