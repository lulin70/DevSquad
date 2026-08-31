#!/usr/bin/env python3
"""
HostLLMBridge Backend (V4.5.2).

B path: direct bridge to the programming AI host (Trae/ClaudeCode).
No API key needed — the host executes the prompt via a pure-file
request/response protocol.

Design (§5 in V4.5.2_ARCHITECTURE.md):
  - HostLLMBridge: protocol layer (create_request/wait_for_response/
    write_response/marker handling). Pure stdlib (os, json, time, uuid).
  - HostBridgeBackend: LLMBackend wrapper that calls the protocol
    and adds platform detection + fuse skip (consecutive same-reason
    failures → permanently skip B path).

File protocol:
  bridge_dir/
    protocol.marker               # sentinel: {"request_id": "...", "ts": ...}
    request_{request_id}.json     # outgoing request
    response_{request_id}.json    # incoming response

Anti-Ghost: _call_counter_er increments on every generate() / create_request()
invocation. CI (scripts/check_module_activation.py) asserts counter > 0.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import uuid
from typing import Any

from .backend_paths import BackendUnavailable
from .llm_backend import LLMBackend

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level Anti-Ghost counter
# ---------------------------------------------------------------------------
# CI: scripts/check_module_activation.py checks this > 0
_call_counter_er: int = 0


def get_call_counter_er() -> int:
    """Return module activation counter (for Anti-Ghost verification)."""
    return _call_counter_er


# ---------------------------------------------------------------------------
# File helpers (module-level, reused by bridge + tests)
# ---------------------------------------------------------------------------


def _atomic_write_json(path: str, payload: dict[str, Any]) -> None:
    """Write JSON atomically via temp file + rename."""
    tmp = path + f".tmp.{uuid.uuid4().hex[:8]}"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception:
        # Best-effort cleanup of partial temp file
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass
        raise


def _prune_old_files(bridge_dir: str, max_files: int) -> int:
    """V4.5.11: prune oldest request/response files in v1 bridge dir.

    Mirrors the v2 implementation behavior:
    - max_files == 0 disables pruning (returns 0).
    - marker (`protocol.marker`) and `.tmp` files are not counted.
    - only files matching ``request_*.json`` / ``response_*.json``.
    """
    if max_files <= 0:
        return 0
    if not os.path.isdir(bridge_dir):
        return 0
    entries: list[tuple[float, str]] = []
    request_re = re.compile(r"^request_.+\.json$")
    response_re = re.compile(r"^response_.+\.json$")
    try:
        for name in os.listdir(bridge_dir):
            path = os.path.join(bridge_dir, name)
            if not os.path.isfile(path):
                continue
            if name.startswith(".") or name.endswith(".tmp"):
                continue
            if name == "protocol.marker":
                continue
            if not (request_re.match(name) or response_re.match(name)):
                continue
            try:
                entries.append((os.path.getmtime(path), path))
            except OSError:
                continue
    except OSError:
        logger.debug("HostLLMBridge._prune_old_files: iter failed for %s", bridge_dir)
        return 0
    excess = len(entries) - max_files
    if excess <= 0:
        return 0
    entries.sort(key=lambda pair: pair[0])
    removed = 0
    for _, path in entries[:excess]:
        try:
            os.remove(path)
            removed += 1
        except OSError:
            continue
    return removed


# Module-level default + env override (mirrors HostLLMBridgeV2)
PRUNE_MAX_FILES_DEFAULT = 100


def _try_read_json(path: str) -> dict[str, Any] | None:
    """Read JSON file; return None on parse error (caller may retry)."""
    try:
        with open(path, encoding="utf-8") as f:
            content = f.read()
        return json.loads(content)
    except (OSError, json.JSONDecodeError):
        return None


# ---------------------------------------------------------------------------
# Protocol layer — HostLLMBridge (pure file protocol)
# ---------------------------------------------------------------------------


class HostLLMBridge:
    """Pure-file request/response protocol with programming AI hosts.

    Reuses the v2.8.4 upstream design. Zero external dependencies
    (only stdlib: os, json, time, uuid, re).

    Lifecycle:
      1. create_request() writes request_*.json + protocol.marker
      2. Host (or FakeHostRunner) reads marker, processes request, writes
         response_*.json atomically.
      3. wait_for_response() polls for response_*.json, parses, returns.
    """

    DEFAULT_TIMEOUT = 600
    POLL_INTERVAL = 0.5
    MAX_JSON_RETRIES = 3
    JSON_RETRY_INTERVAL = 0.1

    # V4.5.11: bridge log retention (PRUNE_MAX_FILES, default 100).
    PRUNE_MAX_FILES_DEFAULT = 100

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

    # request_id safety: only alphanumerics + underscore (prevent path traversal)
    _REQUEST_ID_RE = re.compile(r"^[a-zA-Z0-9_]{1,64}$")

    def __init__(self, bridge_dir: str | None = None) -> None:
        """Initialize bridge; auto-create bridge_dir under project root.

        Args:
            bridge_dir: Override bridge directory (for tests). If None,
                defaults to ``<project_root>/logs/host_llm_bridge/v1``
                (V4.5.10: versioned dir keeps v1/v2 fully isolated).
        """
        if bridge_dir is None:
            bridge_dir = self._default_bridge_dir()
        self.bridge_dir = bridge_dir
        os.makedirs(self.bridge_dir, exist_ok=True)

    # ---- public API ----

    def create_request(
        self,
        agent_type: str,
        task: str,
        context: dict[str, Any],
        prompt: str,
        timeout_seconds: int | None = None,
    ) -> str:
        """Create a request file + marker; return request_id.

        Args:
            agent_type: Role identifier (architect/security/tester/...).
            task: Short task description.
            context: Arbitrary context dict.
            prompt: Full prompt text to forward to host.
            timeout_seconds: Optional timeout hint.

        Returns:
            The generated request_id (also used as filename component).

        Raises:
            ValueError: If context is not serializable.
        """
        global _call_counter_er
        _call_counter_er += 1

        request_id = f"req_{uuid.uuid4().hex[:16]}"
        self._assert_safe_id(request_id)

        payload = {
            "request_id": request_id,
            "agent_type": agent_type,
            "task": task,
            "context": context,
            "prompt": prompt,
            "timeout_seconds": timeout_seconds or self.DEFAULT_TIMEOUT,
            "created_at": time.time(),
        }

        request_path = self._request_path(request_id)
        marker_path = self._marker_path()

        # Write request file atomically (write-then-rename)
        _atomic_write_json(request_path, payload)
        _atomic_write_json(
            marker_path,
            {"request_id": request_id, "ts": time.time()},
        )
        logger.info("HostLLMBridge.create_request: %s (agent=%s)", request_id, agent_type)
        # V4.5.11: prune v1 dir to PRUNE_MAX_FILES (best-effort)
        _prune_old_files(self.bridge_dir, self._resolve_prune_max_files())
        return request_id

    def wait_for_response(
        self,
        request_id: str,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        """Poll for response_{request_id}.json until success/failure/timeout.

        Args:
            request_id: The request_id returned by create_request().
            timeout: Max wait seconds (default DEFAULT_TIMEOUT=600).

        Returns:
            Dict with keys: success (bool), output (str), error (str),
            and on timeout: timeout=True.
        """
        self._assert_safe_id(request_id)
        timeout = timeout or self.DEFAULT_TIMEOUT
        deadline = time.time() + timeout
        response_path = self._response_path(request_id)

        while time.time() < deadline:
            if os.path.exists(response_path):
                data = self._try_read_json(response_path)
                if data is not None:
                    return data
            time.sleep(self.POLL_INTERVAL)

        logger.warning("HostLLMBridge.wait_for_response: timeout request_id=%s", request_id)
        return {
            "request_id": request_id,
            "success": False,
            "output": "",
            "error": f"timeout after {timeout}s",
            "timeout": True,
        }

    @staticmethod
    def write_response(
        request_id: str,
        success: bool,
        output: str,
        error: str = "",
        bridge_dir: str | None = None,
    ) -> str:
        """Static method: write a response file atomically.

        Used by real hosts (Trae/ClaudeCode) and FakeHostRunner.

        Returns:
            The absolute response file path.
        """
        if bridge_dir is None:
            bridge_dir = HostLLMBridge._default_bridge_dir()
        os.makedirs(bridge_dir, exist_ok=True)
        HostLLMBridge._assert_safe_id(request_id)
        response_path = os.path.join(bridge_dir, f"response_{request_id}.json")
        payload = {
            "request_id": request_id,
            "success": success,
            "output": output,
            "error": error,
            "completed_at": time.time(),
        }
        _atomic_write_json(response_path, payload)
        # Clear marker (best-effort)
        marker_path = os.path.join(bridge_dir, "protocol.marker")
        try:
            if os.path.exists(marker_path):
                os.remove(marker_path)
        except OSError as e:
            logger.debug("Marker cleanup failed (non-fatal): %s", e)
        # V4.5.11: prune v1 dir to PRUNE_MAX_FILES (best-effort)
        _prune_old_files(bridge_dir, HostLLMBridge._resolve_prune_max_files())
        return response_path

    @staticmethod
    def read_marker(bridge_dir: str | None = None) -> dict[str, Any] | None:
        """Read protocol.marker; return None if missing or invalid."""
        if bridge_dir is None:
            bridge_dir = HostLLMBridge._default_bridge_dir()
        marker_path = os.path.join(bridge_dir, "protocol.marker")
        if not os.path.exists(marker_path):
            return None
        return _try_read_json(marker_path)

    @staticmethod
    def clear_marker(bridge_dir: str | None = None) -> None:
        """Best-effort marker removal."""
        if bridge_dir is None:
            bridge_dir = HostLLMBridge._default_bridge_dir()
        marker_path = os.path.join(bridge_dir, "protocol.marker")
        try:
            if os.path.exists(marker_path):
                os.remove(marker_path)
        except OSError as e:
            logger.debug("clear_marker failed (non-fatal): %s", e)

    @staticmethod
    def validate_request_id(request_id: str) -> bool:
        """Public check: only alphanumerics + underscore, 1-64 chars."""
        return bool(HostLLMBridge._REQUEST_ID_RE.match(request_id))

    # ---- internal helpers ----

    @staticmethod
    def _default_bridge_dir() -> str:
        """Default bridge dir: <project_root>/logs/host_llm_bridge/v1.

        V4.5.10: versioned subdir isolates v1 protocol files from v2
        (which uses logs/host_llm_bridge/v2 + protocol.v2.marker).
        """
        # scripts/collaboration/host_llm_bridge.py → project root is 2 levels up
        here = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(here))
        return os.path.join(project_root, "logs", "host_llm_bridge", "v1")

    @staticmethod
    def _assert_safe_id(request_id: str) -> None:
        if not HostLLMBridge.validate_request_id(request_id):
            raise ValueError(
                f"Invalid request_id (must match [a-zA-Z0-9_]{{1,64}}): {request_id!r}"
            )

    def _request_path(self, request_id: str) -> str:
        return os.path.join(self.bridge_dir, f"request_{request_id}.json")

    def _response_path(self, request_id: str) -> str:
        return os.path.join(self.bridge_dir, f"response_{request_id}.json")

    def _marker_path(self) -> str:
        return os.path.join(self.bridge_dir, "protocol.marker")

    def _try_read_json(self, path: str) -> dict[str, Any] | None:
        """Tolerant reader: handles partially-written JSON with retries."""
        for _ in range(self.MAX_JSON_RETRIES):
            data = _try_read_json(path)
            if data is not None:
                return data
            time.sleep(self.JSON_RETRY_INTERVAL)
        logger.warning(
            "HostLLMBridge: failed to parse JSON after %d retries: %s",
            self.MAX_JSON_RETRIES,
            path,
        )
        return None


# ---------------------------------------------------------------------------
# LLMBackend adapter — HostBridgeBackend
# ---------------------------------------------------------------------------


class HostBridgeBackend(LLMBackend):
    """LLMBackend adapter for HostLLMBridge (B path).

    V4.5.2: B path in B→A→C resolve order. No API key required;
    the host (Trae/ClaudeCode) executes the prompt.

    V4.5.6: SUBAGENT_TYPE_MAP for resolving agent_type → TRAE Task subagent_type.
    Architect maps to 'search' (code-search heavy), others default to
    'general_purpose_task'.

    Failure semantics:
      - Single host failure: degrade gracefully (next call still uses B).
      - Consecutive same-reason failures (≥ FUSE_THRESHOLD): permanently
        disable B via _fuse_skip; is_available() returns False.
    """

    # V4.5.2: B path
    path = "B"

    # Fuse: 2 consecutive same-reason failures → skip B
    FUSE_THRESHOLD = 2

    # V4.5.6: SUBAGENT_TYPE_MAP for Task tool dispatch (weiransoft v2.8.4 §对齐)
    SUBAGENT_TYPE_MAP: dict[str, str] = {
        "architect": "search",  # architecture analysis needs code search
        "product-manager": "general_purpose_task",
        "test-expert": "general_purpose_task",
        "solo-coder": "general_purpose_task",
        "ui-designer": "general_purpose_task",
    }

    @staticmethod
    def resolve_subagent_type(agent_type: str) -> str:
        """Resolve agent_type → TRAE Task subagent_type.

        Default: 'general_purpose_task'.
        """
        return HostBridgeBackend.SUBAGENT_TYPE_MAP.get(
            agent_type, "general_purpose_task"
        )

    def __init__(
        self,
        bridge_dir: str | None = None,
        timeout_seconds: int = 600,
    ) -> None:
        """Initialize HostBridgeBackend.

        Args:
            bridge_dir: Override bridge directory (for tests).
            timeout_seconds: Per-request timeout (default 600s).
        """
        self.bridge = HostLLMBridge(bridge_dir=bridge_dir)
        self.timeout = timeout_seconds
        self._failures: dict[str, int] = {}  # reason -> count
        self._fuse_skip: bool = False

    def __repr__(self) -> str:
        return (
            f"HostBridgeBackend(bridge_dir={self.bridge.bridge_dir}, "
            f"timeout={self.timeout}, fuse_skip={self._fuse_skip})"
        )

    # ---- platform detection ----

    def _detect_platform(self) -> str:
        """Detect which host platform is active.

        Returns:
            'host_llm' (TRAE), 'claude_code' (ClaudeCode/ANTHROPIC), or 'unknown'.
        """
        if os.environ.get("TRAE_ENV") or os.environ.get("TRAE_AGENT_PATH"):
            return "host_llm"
        if os.environ.get("CLAUDE_CODE_ENV") or os.environ.get("ANTHROPIC_ENV"):
            return "claude_code"
        return "unknown"

    # ---- LLMBackend interface ----

    def is_available(self) -> bool:
        """True if a programming AI host is detected and B is not fuse-skipped."""
        if self._fuse_skip:
            return False
        return self._detect_platform() != "unknown"

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate via HostLLMBridge protocol.

        Args:
            prompt: Prompt text to forward to host.
            **kwargs: Recognized keys: role_name (→ agent_type), task_description,
                agent_type, context (extra dict).

        Returns:
            Host response output text.

        Raises:
            BackendUnavailable: If B is not available (no host / fuse-skipped).
            RuntimeError: If host reports failure (error wrapped for fuse counting).
        """
        if not self.is_available():
            raise BackendUnavailable(
                "Host Bridge 不可用（未检测到编程 AI 宿主 或 B 路径已熔断）"
            )

        agent_type = kwargs.get("agent_type") or kwargs.get("role_name") or "general"
        task = kwargs.get("task_description", "")
        extra_context: dict[str, Any] = kwargs.get("context", {}) or {}
        if "role_name" in kwargs:
            extra_context.setdefault("role_name", kwargs["role_name"])

        request_id = self.bridge.create_request(
            agent_type=agent_type,
            task=task,
            context=extra_context,
            prompt=prompt,
            timeout_seconds=self.timeout,
        )
        result = self.bridge.wait_for_response(request_id, timeout=self.timeout)

        if not result.get("success"):
            reason = result.get("error", "unknown")
            self._record_failure(reason)
            raise RuntimeError(f"HostLLMBridge failure: {reason}")

        return result.get("output", "")

    def generate_stream(self, prompt: str, **kwargs: Any) -> Any:
        """Streaming not natively supported; fall back to generate()."""
        yield self.generate(prompt, **kwargs)

    # ---- fuse skip ----

    def _record_failure(self, reason: str) -> None:
        """Consecutive same-reason failures (≥ FUSE_THRESHOLD) → skip B."""
        self._failures[reason] = self._failures.get(reason, 0) + 1
        if self._failures[reason] >= self.FUSE_THRESHOLD:
            self._fuse_skip = True
            logger.warning(
                "HostBridgeBackend: fuse-skipped after %d consecutive %s failures",
                self._failures[reason],
                reason,
            )

    @property
    def is_fuse_skipped(self) -> bool:
        """True if B path has been permanently disabled by fuse."""
        return self._fuse_skip


class HostBridgeBackendV2(HostBridgeBackend):
    """LLMBackend adapter for HostLLMBridgeV2 (B path, V4.5.10).

    Inherits all behavior from HostBridgeBackend (platform detection, fuse,
    SUBAGENT_TYPE_MAP, generate semantics) but uses the hardened v2 protocol:
    versioned dir (logs/host_llm_bridge/v2), protocol.v2.marker, strict
    7-field schema, no inline prompt in request JSON.

    Selection is controlled by create_backend() via:
      - DEVSQUAD_V455_DISABLE_HOST_BRIDGE_V2=1  → force v1 (highest priority)
      - DEVSQUAD_HOST_BRIDGE_VERSION=v1|v2      → explicit version
      - default                                  → v2
    """

    def __init__(
        self,
        bridge_dir: str | None = None,
        timeout_seconds: int = 600,
    ) -> None:
        from .host_llm_bridge_v2 import HostLLMBridgeV2

        self.bridge = HostLLMBridgeV2(bridge_dir=bridge_dir)
        self.timeout = timeout_seconds
        self._failures: dict[str, int] = {}
        self._fuse_skip = False

    def __repr__(self) -> str:
        return (
            f"HostBridgeBackendV2(bridge_dir={self.bridge.bridge_dir}, "
            f"timeout={self.timeout}, fuse_skip={self._fuse_skip})"
        )


# Public exports
__all__ = [
    "HostLLMBridge",
    "HostBridgeBackend",
    "HostBridgeBackendV2",
    "get_call_counter_er",
]
