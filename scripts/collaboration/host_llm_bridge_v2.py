#!/usr/bin/env python3
"""HostLLMBridge v2 (V4.5.10 hardening; V4.5.11 add PRUNE).

V2 协议（对齐 weiransoft/TraeMultiAgentSkill v2.8.4）:
- marker 严格 7 字段 (request_id/agent_type/task/request_file/prompt_file/timeout_seconds/timestamp)
- prompt 独立文件 (request_{id}.prompt)；request JSON 不再内嵌 prompt
- request_file/prompt_file canonical + commonpath 越界校验

V4.5.10 硬化（PRD docs/prd/V4.5.10_PRD.md）:
- 完全隔离: 默认目录 logs/host_llm_bridge/v2，marker 固定 protocol.v2.marker；
  不读取/重命名/删除 v1 文件
- 路径安全: realpath canonical + commonpath + O_NOFOLLOW（拒绝 symlink）
  + regular-file 校验（TOCTOU 防护在打开时通过 fstat 复核）
- 权限: 目录 0700，文件 0600
- 资源上限: prompt / request JSON / response JSON 超限 fail-closed
- marker 严格 schema: 恰好 7 字段 + 类型校验，失败 fail-closed（拒绝处理）

V4.5.11 增加（PRD docs/prd/V4.5.11_PRD.md）:
- PRUNE_MAX_FILES（默认 100）：创建/响应/清理路径完成后按 mtime 倒序裁剪
  v2 目录内的 request_*.json / request_*.prompt / response_*.json；marker 与
  .tmp 不参与计数；可通过 DEVSQUAD_BRIDGE_PRUNE_MAX_FILES 覆盖；0 = 禁用裁剪。

设计原则:
- V4.5.4 lesson #4: _call_counter_er 命名统一
- V4.5.4 lesson #7: 原子写入 (tempfile + os.replace)

Anti-Ghost: _call_counter_er 递增 on create_request/write_response/read_request。
"""
from __future__ import annotations

import json
import logging
import os
import re
import stat
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

# V2 marker fields (full routing context for host LLM) — upstream-compatible
MARKER_V2_FIELDS: tuple[str, ...] = (
    "request_id",
    "agent_type",
    "task",
    "request_file",
    "prompt_file",
    "timeout_seconds",
    "timestamp",
)

# V4.5.10 resource limits (fail-closed on exceed)
MAX_PROMPT_BYTES = 512 * 1024
MAX_REQUEST_JSON_BYTES = 256 * 1024
MAX_RESPONSE_JSON_BYTES = 4 * 1024 * 1024

DIR_MODE = 0o700
FILE_MODE = 0o600


class HostLLMBridgeV2Error(ValueError):
    """Base error for HostLLMBridge v2 protocol violations."""


class InvalidRequestIdError(HostLLMBridgeV2Error):
    """Raised when request_id format is invalid (security)."""


class RequestFilePathError(HostLLMBridgeV2Error):
    """Raised when a protocol file path is outside the version dir (security)."""


class ResourceLimitError(HostLLMBridgeV2Error):
    """Raised when prompt/request/response exceeds the configured size limit."""


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


def _nofollow_flags() -> int:
    """Return open flags rejecting symlink final component when supported."""
    flags = getattr(os, "O_CLOEXEC", 0)
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    return flags | nofollow


class HostLLMBridgeV2:
    """V2 协议: 7 字段 marker + 独立 prompt + 版本隔离 + 路径/资源硬化."""

    DEFAULT_TIMEOUT = 600
    POLL_INTERVAL = 0.5
    MAX_JSON_RETRIES = 3
    JSON_RETRY_INTERVAL = 0.1
    REQUEST_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_]{1,128}$")

    # V4.5.10: versioned marker filename + versioned default dir
    VERSION_SUBDIR = "v2"
    MARKER_FILENAME = "protocol.v2.marker"

    # V4.5.11: bridge log retention (PRUNE_MAX_FILES).
    # Counts request_*.json + request_*.prompt + response_*.json (NOT marker/tmp).
    PRUNE_MAX_FILES_DEFAULT = 100
    # Filename patterns considered for retention accounting.
    _PRUNE_FILE_PATTERNS = (
        re.compile(r"^request_.+\.(?:json|prompt)$"),
        re.compile(r"^response_.+\.json$"),
    )

    @classmethod
    def _resolve_prune_max_files(cls) -> int:
        """Resolve PRUNE_MAX_FILES from env override (fail-loud on garbage)."""
        raw = os.environ.get("DEVSQUAD_BRIDGE_PRUNE_MAX_FILES", "").strip()
        if not raw:
            return cls.PRUNE_MAX_FILES_DEFAULT
        try:
            value = int(raw)
        except ValueError as exc:
            raise ValueError(
                f"Invalid DEVSQUAD_BRIDGE_PRUNE_MAX_FILES={raw!r}: must be int ≥ 0"
            ) from exc
        if value < 0:
            raise ValueError(
                f"Invalid DEVSQUAD_BRIDGE_PRUNE_MAX_FILES={value}: must be ≥ 0"
            )
        return value

    def __init__(self, bridge_dir: str | Path | None = None) -> None:
        """Initialize v2 bridge.

        Args:
            bridge_dir: Override bridge directory (the v2 version dir).
                Defaults to ``<project_root>/logs/host_llm_bridge/v2``.
                v1 files are never read, renamed, or deleted.
        """
        _inc_call_counter_er()
        if bridge_dir is None:
            bridge_dir = self._default_bridge_dir()
        self.bridge_dir = Path(bridge_dir)
        self._ensure_private_dir(self.bridge_dir)

    @classmethod
    def _default_bridge_dir(cls) -> Path:
        """Default v2 dir: <project_root>/logs/host_llm_bridge/v2."""
        here = Path(__file__).resolve().parent.parent.parent
        return here / "logs" / "host_llm_bridge" / cls.VERSION_SUBDIR

    @staticmethod
    def _ensure_private_dir(path: Path) -> None:
        """Create dir 0700; tighten permissions of existing dirs (best-effort)."""
        path.mkdir(parents=True, exist_ok=True, mode=DIR_MODE)
        with suppress(OSError):
            os.chmod(path, DIR_MODE)

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

        Files (all inside the v2 version dir):
            request_{id}.json   — metadata + prompt_file pointer (NO inline prompt)
            request_{id}.prompt — prompt-only file (canonical source)
            protocol.v2.marker  — 7-field marker (written last)

        Returns:
            request_id (format: ``{timestamp}_{uuid_short}``).
        """
        _inc_call_counter_er()
        timeout = timeout_seconds if timeout_seconds else self.DEFAULT_TIMEOUT
        request_id = self._generate_request_id()
        self._assert_safe_id(request_id)

        prompt_bytes = len(prompt.encode("utf-8"))
        if prompt_bytes > MAX_PROMPT_BYTES:
            raise ResourceLimitError(
                f"prompt exceeds limit: {prompt_bytes} > {MAX_PROMPT_BYTES} bytes"
            )

        request_path = self._request_path(request_id)
        prompt_path = self._prompt_path(request_id)

        # 1. request_{id}.json — metadata + prompt_file pointer (no inline prompt)
        request_data = {
            "request_id": request_id,
            "agent_type": agent_type,
            "task": task,
            "context": context or {},
            "timeout_seconds": timeout,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "request_file": str(request_path),
            "prompt_file": str(prompt_path),
        }
        self._write_json_atomic(request_path, request_data)

        # 2. request_{id}.prompt — prompt-only file (canonical source)
        self._write_prompt_atomic(prompt_path, prompt)

        # 3. protocol.v2.marker — 7-field v2 marker (published last)
        marker = MarkerV2(
            request_id=request_id,
            agent_type=agent_type,
            task=task,
            request_file=str(request_path),
            prompt_file=str(prompt_path),
            timeout_seconds=timeout,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self._write_marker_v2(marker)

        # V4.5.11: prune oldest files in the version dir to PRUNE_MAX_FILES
        self._prune_old_files(self.bridge_dir, self._resolve_prune_max_files())

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
            data = self._safe_read_json(response_path)
            if data is not None:
                self._cleanup_request_files(request_id)
                # V4.5.11: post-cleanup retention sweep
                self._prune_old_files(self.bridge_dir, self._resolve_prune_max_files())
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
        payload_bytes = len((output + error).encode("utf-8"))
        if payload_bytes > MAX_RESPONSE_JSON_BYTES:
            raise ResourceLimitError(
                f"response payload exceeds limit: {payload_bytes} > "
                f"{MAX_RESPONSE_JSON_BYTES} bytes"
            )
        bdir = (
            Path(bridge_dir)
            if bridge_dir
            else HostLLMBridgeV2._default_bridge_dir()
        )
        HostLLMBridgeV2._ensure_private_dir(bdir)
        response_path = bdir / f"response_{request_id}.json"
        response_data = {
            "request_id": request_id,
            "success": success,
            "output": output,
            "error": error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        HostLLMBridgeV2._write_json_atomic_static(response_path, response_data)
        # Clear version-scoped marker (best-effort, V4.5.3 lesson #7)
        marker_path = bdir / HostLLMBridgeV2.MARKER_FILENAME
        with suppress(OSError):
            marker_path.unlink(missing_ok=True)
        return str(response_path)

    @staticmethod
    def read_request(
        request_id: str,
        bridge_dir: str | Path | None = None,
    ) -> dict[str, Any] | None:
        """Read request_{id}.json with canonical path security checks."""
        _inc_call_counter_er()
        if not HostLLMBridgeV2.validate_request_id(request_id):
            raise InvalidRequestIdError(f"invalid request_id: {request_id!r}")
        bdir = (
            Path(bridge_dir)
            if bridge_dir
            else HostLLMBridgeV2._default_bridge_dir()
        )
        request_path = bdir / f"request_{request_id}.json"
        data = HostLLMBridgeV2._safe_read_json_static(request_path)
        if data is None:
            return None
        # Security: protocol file paths must stay inside the version dir
        for key in ("request_file", "prompt_file"):
            file_ref = data.get(key, "")
            if file_ref:
                HostLLMBridgeV2._validate_path_within(file_ref, bdir)
        return data

    @staticmethod
    def read_marker(
        bridge_dir: str | Path | None = None,
    ) -> dict[str, Any] | None:
        """Read protocol.v2.marker with strict 7-field schema validation.

        Fail-closed: missing fields, extra fields, wrong types, invalid
        request_id, or out-of-dir paths all return None (marker refused).
        v1-format markers are never processed by the v2 reader.
        """
        _inc_call_counter_er()
        bdir = (
            Path(bridge_dir)
            if bridge_dir
            else HostLLMBridgeV2._default_bridge_dir()
        )
        marker_path = bdir / HostLLMBridgeV2.MARKER_FILENAME
        data = HostLLMBridgeV2._safe_read_json_static(marker_path)
        if data is None:
            return None
        try:
            HostLLMBridgeV2._validate_marker_schema(data, bdir)
        except HostLLMBridgeV2Error as exc:
            logger.warning("HostLLMBridgeV2: marker refused (fail-closed): %s", exc)
            return None
        return {**data, "_format": "v2"}

    @staticmethod
    def _validate_marker_schema(data: dict[str, Any], bdir: Path) -> None:
        """Strict marker schema: exactly 7 fields + types + in-dir paths."""
        keys = set(data.keys())
        expected = set(MARKER_V2_FIELDS)
        if keys != expected:
            raise HostLLMBridgeV2Error(
                f"marker schema mismatch: missing={sorted(expected - keys)} "
                f"extra={sorted(keys - expected)}"
            )
        for key in ("request_id", "agent_type", "task", "timestamp"):
            if not isinstance(data[key], str) or not data[key]:
                raise HostLLMBridgeV2Error(f"marker field {key!r} must be non-empty str")
        timeout = data["timeout_seconds"]
        if isinstance(timeout, bool) or not isinstance(timeout, int) or timeout <= 0:
            raise HostLLMBridgeV2Error(
                f"marker field 'timeout_seconds' must be positive int, got {timeout!r}"
            )
        if not HostLLMBridgeV2.validate_request_id(data["request_id"]):
            raise HostLLMBridgeV2Error(
                f"marker request_id invalid: {data['request_id']!r}"
            )
        for key in ("request_file", "prompt_file"):
            HostLLMBridgeV2._validate_path_within(data[key], bdir)

    @staticmethod
    def _prune_old_files(bridge_dir: Path, max_files: int) -> int:
        """Prune oldest retention-counted files down to ``max_files``.

        Returns:
            int: number of files removed.

        Notes:
            - ``max_files == 0`` disables pruning (returns 0).
            - marker / .tmp files are not counted and not removed.
            - Files outside the version dir are never touched.
            - Failures (best-effort) are logged at debug level only.
        """
        if max_files <= 0:
            return 0
        if not bridge_dir.exists():
            return 0
        try:
            entries: list[tuple[float, Path]] = []
            for child in bridge_dir.iterdir():
                if not child.is_file():
                    continue
                name = child.name
                if name.startswith(".") or name.endswith(".tmp"):
                    continue
                if name == HostLLMBridgeV2.MARKER_FILENAME:
                    continue
                if not any(pattern.match(name) for pattern in HostLLMBridgeV2._PRUNE_FILE_PATTERNS):
                    continue
                try:
                    entries.append((child.stat().st_mtime, child))
                except OSError:
                    continue
        except OSError:
            logger.debug("HostLLMBridgeV2._prune_old_files: iter failed for %s", bridge_dir)
            return 0
        excess = len(entries) - max_files
        if excess <= 0:
            return 0
        # oldest first
        entries.sort(key=lambda pair: pair[0])
        removed = 0
        for _, path in entries[:excess]:
            try:
                path.unlink()
                removed += 1
            except OSError as exc:
                logger.debug(
                    "HostLLMBridgeV2._prune_old_files: cannot remove %s: %s", path, exc
                )
        return removed

    @staticmethod
    def clear_marker(bridge_dir: str | Path | None = None) -> None:
        """Clear the v2 marker file (best-effort)."""
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
        """Validate request_id format: ``[a-zA-Z0-9_]{1,128}``."""
        if not isinstance(request_id, str) or not request_id:
            return False
        return bool(HostLLMBridgeV2.REQUEST_ID_PATTERN.match(request_id))

    # ---- path / file security helpers ----

    @staticmethod
    def _validate_path_within(path_str: str, base_dir: Path) -> None:
        """Canonical path check: realpath must stay inside base_dir.

        Raises RequestFilePathError on traversal or outside-base paths.
        Final-component symlinks are additionally rejected at open time
        via O_NOFOLLOW (see _safe_open).
        """
        try:
            real_target = os.path.realpath(path_str)
            real_base = os.path.realpath(str(base_dir))
            common = os.path.commonpath([real_target, real_base])
            if common != real_base:
                raise RequestFilePathError(
                    f"path outside version dir: {path_str}"
                )
        except ValueError as exc:
            raise RequestFilePathError(
                f"path validation failed: {path_str}: {exc}"
            ) from exc

    @staticmethod
    def _safe_open(path: Path, flags: int) -> int:
        """Open with O_NOFOLLOW (reject symlink) and fstat regular-file check.

        TOCTOU-safe: the file type is verified on the opened fd, not on a
        prior exists() probe.
        """
        fd = os.open(str(path), flags | _nofollow_flags())
        try:
            st = os.fstat(fd)
            if not stat.S_ISREG(st.st_mode):
                raise RequestFilePathError(f"not a regular file: {path}")
        except Exception:
            with suppress(OSError):
                os.close(fd)
            raise
        return fd

    @staticmethod
    def _safe_read_json_static(path: Path) -> dict[str, Any] | None:
        """Read JSON with O_NOFOLLOW, regular-file check, and size limit."""
        if not os.path.exists(path):
            return None
        try:
            fd = HostLLMBridgeV2._safe_open(path, os.O_RDONLY)
        except RequestFilePathError as exc:
            logger.warning("refusing unsafe file %s: %s", path, exc)
            return None
        except OSError as exc:
            logger.warning("cannot open %s: %s", path, exc)
            return None
        try:
            st = os.fstat(fd)
            if st.st_size > MAX_RESPONSE_JSON_BYTES:
                logger.warning("refusing oversized file %s (%d bytes)", path, st.st_size)
                return None
            with os.fdopen(fd, encoding="utf-8") as f:
                content = f.read()
            fd = -1  # fdopen took ownership
            return json.loads(content)
        except json.JSONDecodeError as exc:
            logger.warning("invalid JSON in %s: %s", path, exc)
            return None
        except OSError as exc:
            logger.warning("read %s failed: %s", path, exc)
            return None
        finally:
            if fd >= 0:
                with suppress(OSError):
                    os.close(fd)

    def _safe_read_json(self, path: Path) -> dict[str, Any] | None:
        """Instance wrapper with JSON retry for partially-written files.

        V4.5.13 lesson: an ABSENT file is normal polling (no listener yet),
        not a decode failure — return immediately without retry noise.
        Only an existing-but-unparseable file is retried and warned about.
        """
        for _ in range(self.MAX_JSON_RETRIES):
            if not path.exists():
                return None
            data = self._safe_read_json_static(path)
            if data is not None:
                return data
            time.sleep(self.JSON_RETRY_INTERVAL)
        logger.warning(
            "JSON decode failed after %d retries: %s", self.MAX_JSON_RETRIES, path
        )
        return None

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
        """Write 7-field v2 marker (overwrite, published last)."""
        self._write_json_atomic(self._marker_path(), marker.to_dict())

    def _write_prompt_atomic(self, path: Path, prompt: str) -> None:
        """Write prompt-only file atomically (tmp 0600 + os.replace)."""
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        fd = os.open(
            str(tmp_path),
            os.O_WRONLY | os.O_CREAT | os.O_TRUNC | _nofollow_flags(),
            FILE_MODE,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(prompt)
            os.replace(str(tmp_path), str(path))
        except Exception:
            with suppress(OSError):
                os.unlink(tmp_path)
            raise

    def _write_json_atomic(self, path: Path, data: dict[str, Any]) -> None:
        """Atomic JSON write (tempfile 0600 + os.replace)."""
        self.__class__._write_json_atomic_static(path, data)

    @staticmethod
    def _write_json_atomic_static(path: Path, data: dict[str, Any]) -> None:
        """Atomic JSON write (static, shared by all writers)."""
        payload = json.dumps(data, ensure_ascii=False, indent=2)
        payload_bytes = len(payload.encode("utf-8"))
        if payload_bytes > MAX_REQUEST_JSON_BYTES:
            raise ResourceLimitError(
                f"JSON payload exceeds limit: {payload_bytes} > "
                f"{MAX_REQUEST_JSON_BYTES} bytes"
            )
        fd, tmp_str = tempfile.mkstemp(
            dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(payload)
            os.chmod(tmp_str, FILE_MODE)
            os.replace(tmp_str, str(path))
        except Exception:
            with suppress(OSError):
                os.unlink(tmp_str)
            raise

    def _cleanup_request_files(self, request_id: str) -> None:
        """Cleanup request + prompt files after response read (version-scoped)."""
        for path in (self._request_path(request_id), self._prompt_path(request_id)):
            with suppress(OSError):
                path.unlink(missing_ok=True)

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
    "ResourceLimitError",
    "MARKER_V2_FIELDS",
    "MAX_PROMPT_BYTES",
    "MAX_REQUEST_JSON_BYTES",
    "MAX_RESPONSE_JSON_BYTES",
    "get_call_counter_er",
    "_inc_call_counter_er",
]
