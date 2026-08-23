#!/usr/bin/env python3
"""ArtifactStore — V4.5.3 P12.2.1.

Persists 7-role Worker output (PRD / patches / tests / reports) to disk
under ``artifacts/{session_id}/{role_id}/{filename}`` namespace with a
JSON manifest.

Design:
    - Anti-ghost: ``_call_counter`` exposed via ``get_call_counter()``
    - Best-effort: write failures do not propagate to Worker (P12.2.2
      handles this by catching at the Worker layer)
    - Manifest: ``artifacts/{session_id}/manifest.json`` with all
      artifacts (atomic rewrite on every write)
    - SHA-256: content hash for tamper detection + dedup hints
    - Schema version: 1 (forward-compatible via ``schema_version`` field)
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import threading
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, cast

# ---------- Public constants ----------

ARTIFACT_SCHEMA_VERSION = 1
MANIFEST_FILENAME = "manifest.json"
DEFAULT_ROOT = "artifacts"


# ---------- Anti-ghost counter ----------

_call_counter: int = 0
_call_counter_lock = threading.Lock()


def _inc_call_counter() -> None:
    """Increment the module-level call counter (thread-safe)."""
    global _call_counter
    with _call_counter_lock:
        _call_counter += 1


def get_call_counter() -> int:
    """Return current anti-ghost counter value."""
    with _call_counter_lock:
        return _call_counter


# ---------- Global registry hook (P12.2.5) ----------

_global_registry: Any = None
_global_registry_lock = threading.Lock()


def _get_global_registry() -> Any:
    """Lazy-loaded singleton EffectRegistry.

    Returns:
        EffectRegistry instance (process-global).

    Note:
        Tests should call ``set_global_registry()`` with a local registry
        to isolate state across test runs.
    """
    global _global_registry
    with _global_registry_lock:
        if _global_registry is None:
            from scripts.collaboration.effect_registry import EffectRegistry

            _global_registry = EffectRegistry()
        return _global_registry


def set_global_registry(registry: Any) -> None:
    """Override the global registry (mainly for testing)."""
    global _global_registry
    with _global_registry_lock:
        _global_registry = registry


# ---------- Exceptions ----------


class ArtifactStoreError(Exception):
    """Raised on ArtifactStore operation failures."""


# ---------- Dataclasses ----------


@dataclass
class Artifact:
    """Metadata for a single persisted artifact.

    Attributes:
        artifact_id: Stable unique ID (UUID4 hex). Key for read/delete.
        session_id: Dispatch session ID.
        role_id: 7-role worker ID (architect/tester/coder/etc.).
        filename: Filename within the role directory.
        sha256: SHA-256 of the content (hex).
        size: Content size in bytes.
        kind: "text" or "binary".
        path: Absolute path on disk.
        created_at: Unix timestamp (seconds since epoch).
    """

    artifact_id: str
    session_id: str
    role_id: str
    filename: str
    sha256: str
    size: int
    kind: str
    path: str
    created_at: float = field(default_factory=lambda: __import__("time").time())


# ---------- Store implementation ----------


class ArtifactStore:
    """Persist Worker output to ``{root}/{session_id}/{role_id}/{filename}``.

    Maintains a per-session manifest at ``{root}/{session_id}/manifest.json``
    with all artifact metadata. Manifest is rewritten atomically on every
    write/delete.
    """

    def __init__(self, root: str | Path | None = None) -> None:
        """Initialize store with root directory.

        Args:
            root: Root directory for artifacts. Defaults to ``./artifacts``.

        Raises:
            ArtifactStoreError: If root cannot be created.
        """
        if root is None:
            root = DEFAULT_ROOT
        self.root = Path(root).resolve()
        try:
            self.root.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ArtifactStoreError(
                f"Cannot create ArtifactStore root {self.root}: {exc}"
            ) from exc
        _inc_call_counter()

    # ---- internal helpers ----

    def _session_dir(self, session_id: str) -> Path:
        return self.root / session_id

    def _role_dir(self, session_id: str, role_id: str) -> Path:
        return self.root / session_id / role_id

    def _manifest_path(self, session_id: str) -> Path:
        return self.root / session_id / MANIFEST_FILENAME

    def _read_manifest(self, session_id: str) -> dict[str, Any]:
        manifest_path = self._manifest_path(session_id)
        if not manifest_path.exists():
            return {"schema_version": ARTIFACT_SCHEMA_VERSION, "artifacts": []}
        try:
            return cast(dict[str, Any], json.loads(manifest_path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError) as exc:
            raise ArtifactStoreError(
                f"Cannot read manifest {manifest_path}: {exc}"
            ) from exc

    def _write_manifest(self, session_id: str, manifest: dict[str, Any]) -> None:
        manifest_path = self._manifest_path(session_id)
        try:
            tmp_path = manifest_path.with_suffix(".json.tmp")
            tmp_path.write_text(
                json.dumps(manifest, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            os.replace(tmp_path, manifest_path)
        except OSError as exc:
            raise ArtifactStoreError(
                f"Cannot write manifest {manifest_path}: {exc}"
            ) from exc

    def _compute_sha256(self, data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def _new_artifact_id(self) -> str:
        return f"art-{uuid.uuid4().hex[:16]}"

    # ---- public API ----

    def write(
        self,
        session_id: str,
        role_id: str,
        filename: str,
        content: str | bytes,
        *,
        kind: str = "text",
    ) -> Artifact:
        """Persist content to disk and update manifest.

        Args:
            session_id: Dispatch session ID.
            role_id: Worker role ID.
            filename: Filename within role directory.
            content: Text (str) or binary (bytes) payload.
            kind: "text" or "binary". Defaults to "text".

        Returns:
            Artifact metadata descriptor.

        Raises:
            ArtifactStoreError: On I/O failures.
        """
        _inc_call_counter()
        if kind not in ("text", "binary"):
            raise ArtifactStoreError(f"Invalid kind: {kind!r}")

        # Normalize content to bytes
        if isinstance(content, str):
            data = content.encode("utf-8")
        elif isinstance(content, bytes):
            data = content
        else:
            raise ArtifactStoreError(
                f"content must be str or bytes, got {type(content).__name__}"
            )

        # Snapshot existing content for revert (P12.2.5)
        # Validate filename first (no path traversal)
        if os.path.sep in filename or (os.path.altsep and os.path.altsep in filename):
            raise ArtifactStoreError(
                f"filename must not contain path separators: {filename!r}"
            )
        if filename in ("", ".", ".."):
            raise ArtifactStoreError(f"Invalid filename: {filename!r}")

        # Ensure role directory exists
        role_dir = self._role_dir(session_id, role_id)
        try:
            role_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ArtifactStoreError(
                f"Cannot create role directory {role_dir}: {exc}"
            ) from exc

        # Snapshot existing content (for revert — P12.2.5)
        _pre_existing_bytes: bytes | None = None
        _fp_for_snapshot = role_dir / filename
        if _fp_for_snapshot.exists():
            try:
                _pre_existing_bytes = _fp_for_snapshot.read_bytes()
            except OSError:
                _pre_existing_bytes = None

        # Write file (atomic: write to .tmp then rename)
        file_path = role_dir / filename
        tmp_path = file_path.with_name(file_path.name + ".tmp")
        try:
            tmp_path.write_bytes(data)
            os.replace(tmp_path, file_path)
        except OSError as exc:
            with contextlib.suppress(OSError):
                tmp_path.unlink()
            raise ArtifactStoreError(
                f"Cannot write artifact {file_path}: {exc}"
            ) from exc

        # Build artifact descriptor
        artifact = Artifact(
            artifact_id=self._new_artifact_id(),
            session_id=session_id,
            role_id=role_id,
            filename=filename,
            sha256=self._compute_sha256(data),
            size=len(data),
            kind=kind,
            path=str(file_path),
        )

        # Update manifest (atomic rewrite)
        manifest = self._read_manifest(session_id)
        # Remove any prior entry for same path (overwrite semantics)
        manifest["artifacts"] = [
            a for a in manifest["artifacts"] if a["filename"] != filename
            or a["role_id"] != role_id
        ]
        manifest["artifacts"].append(asdict(artifact))
        self._write_manifest(session_id, manifest)

        # V4.5.3 P12.2.5: Register effect in global EffectRegistry (binary: encode payload only)
        try:
            from scripts.collaboration.dispatch_effect import (
                EffectContext,
                WriteFileEffect,
            )

            registry = _get_global_registry()
            effect_payload: dict[str, Any] = {"path": str(file_path)}
            if kind == "text":
                effect_payload["content"] = data.decode("utf-8", errors="surrogateescape")
            else:
                # Encode binary as base64-string to keep payload JSON-safe
                import base64

                effect_payload["content_b64"] = base64.b64encode(data).decode("ascii")
            if _pre_existing_bytes is not None:
                effect_payload["original_content_b64"] = _pre_existing_bytes.hex()
            effect_ctx = EffectContext(
                effect_id=artifact.artifact_id,
                effect_type="write_file",
                payload=effect_payload,
            )
            # Apply effect directly (avoid registry.apply which would double-write),
            # then push onto registry stack so revert_all() can roll back later.
            effect = WriteFileEffect()
            outcome = effect.apply(effect_ctx)
            if outcome.success:
                with registry._lock:
                    registry._stack.append((effect, effect_ctx))
        except Exception:  # noqa: BLE001 — best-effort
            # Effect registration failure must NOT break artifact write
            pass

        return artifact

    def read(self, artifact_id: str) -> str | bytes:
        """Read artifact content by ID.

        Args:
            artifact_id: Artifact ID returned by ``write()``.

        Returns:
            ``str`` for text artifacts, ``bytes`` for binary.

        Raises:
            ArtifactStoreError: If artifact not found or read fails.
        """
        _inc_call_counter()
        # Find artifact across all sessions (manifest scan)
        if not self.root.exists():
            raise ArtifactStoreError(f"Artifact {artifact_id} not found")
        for session_dir in self.root.iterdir():
            if not session_dir.is_dir():
                continue
            manifest_path = session_dir / MANIFEST_FILENAME
            if not manifest_path.exists():
                continue
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            for entry in manifest.get("artifacts", []):
                if entry.get("artifact_id") == artifact_id:
                    file_path = Path(entry["path"])
                    if not file_path.exists():
                        raise ArtifactStoreError(
                            f"Artifact file missing: {file_path}"
                        )
                    try:
                        data = file_path.read_bytes()
                    except OSError as exc:
                        raise ArtifactStoreError(
                            f"Cannot read artifact {file_path}: {exc}"
                        ) from exc
                    if entry.get("kind") == "binary":
                        return data
                    return data.decode("utf-8")
        raise ArtifactStoreError(f"Artifact {artifact_id} not found")

    def list(
        self, session_id: str, *, role_id: str | None = None
    ) -> list[Artifact]:
        """List artifacts in a session, optionally filtered by role.

        Args:
            session_id: Dispatch session ID.
            role_id: Optional role ID filter.

        Returns:
            List of Artifact objects, empty if session has no manifest.
        """
        _inc_call_counter()
        try:
            manifest = self._read_manifest(session_id)
        except ArtifactStoreError:
            return []
        results: list[Artifact] = []
        for entry in manifest.get("artifacts", []):
            if role_id is not None and entry.get("role_id") != role_id:
                continue
            try:
                results.append(Artifact(**entry))
            except (TypeError, KeyError):
                # Skip malformed entries (forward compat)
                continue
        return results

    def delete(self, artifact_id: str) -> bool:
        """Delete artifact by ID.

        Removes the file from disk and removes the manifest entry.

        Args:
            artifact_id: Artifact ID returned by ``write()``.

        Returns:
            True if deleted, False if not found.
        """
        _inc_call_counter()
        if not self.root.exists():
            return False
        for session_dir in self.root.iterdir():
            if not session_dir.is_dir():
                continue
            manifest_path = session_dir / MANIFEST_FILENAME
            if not manifest_path.exists():
                continue
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            new_artifacts = []
            deleted = False
            deleted_entry: dict[str, Any] | None = None
            for entry in manifest.get("artifacts", []):
                if entry.get("artifact_id") == artifact_id and not deleted:
                    file_path = Path(entry["path"])
                    if file_path.exists():
                        with contextlib.suppress(OSError):
                            file_path.unlink()
                    deleted = True
                    deleted_entry = entry
                    continue
                new_artifacts.append(entry)
            if deleted:
                manifest["artifacts"] = new_artifacts
                self._write_manifest(session_dir.name, manifest)
                # V4.5.3 P12.2.5: Register DeleteFileEffect in global registry
                try:
                    from scripts.collaboration.dispatch_effect import (
                        DeleteFileEffect,
                        EffectContext,
                    )

                    registry = _get_global_registry()
                    if deleted_entry is not None:
                        effect_ctx = EffectContext(
                            effect_id=artifact_id,
                            effect_type="delete_file",
                            payload={"path": deleted_entry["path"]},
                        )
                        registry.apply(DeleteFileEffect(), effect_ctx)
                except Exception:  # noqa: BLE001
                    pass
                return True
        return False
