#!/usr/bin/env python3
"""DispatchEffect Protocol — V4.5.3 P12.2.3.

Abstracts "revertible side-effect" for dispatch pipeline. P12.2 ships with
3 filesystem-only effect types:

- ``WriteFileEffect``: write content to disk (revert: delete or restore)
- ``DeleteFileEffect``: delete file (revert: restore original content)
- ``RenameFileEffect``: rename src→dst (revert: rename back)

Revert semantics:
    - Idempotent: calling revert() multiple times is safe
    - Best-effort: failures are reported but do not raise

Anti-ghost: Registry-level counter (see effect_registry.py).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

# ---------- Data classes ----------


@dataclass
class EffectContext:
    """Input to effect apply()/revert().

    Attributes:
        effect_id: Unique ID for this effect instance.
        effect_type: Type identifier (e.g. "write_file").
        payload: Effect-specific parameters (path, content, original_content, etc.).
        applied_at: Unix timestamp when apply() was called (set by registry).
    """

    effect_id: str
    effect_type: str
    payload: dict[str, Any]
    applied_at: float = field(default_factory=time.time)


@dataclass
class EffectOutcome:
    """Result of effect apply()/revert().

    Attributes:
        success: True if operation completed.
        error: Error message if any.
        side_data: Effect-specific return data (e.g. SHA-256 of written content).
    """

    success: bool
    error: str | None = None
    side_data: dict[str, Any] = field(default_factory=dict)


# ---------- Protocol ----------


class DispatchEffect(Protocol):
    """Protocol for revertible side-effects.

    Implementations must define apply() and revert(). Both must be
    idempotent and must not raise on failure (return EffectOutcome
    with success=False instead).
    """

    def apply(self, ctx: EffectContext) -> EffectOutcome: ...
    def revert(self, ctx: EffectContext) -> EffectOutcome: ...


# ---------- Concrete implementations ----------


class WriteFileEffect:
    """Write content to a file. Revert: delete file (or restore original)."""

    def apply(self, ctx: EffectContext) -> EffectOutcome:
        path_str = ctx.payload.get("path")
        # Resolve content (supports base64 for binary)
        if "content_b64" in ctx.payload:
            import base64

            content: str | bytes = base64.b64decode(ctx.payload["content_b64"])
        else:
            content = ctx.payload.get("content", "")
        if not isinstance(path_str, str) or not path_str:
            return EffectOutcome(success=False, error="missing or invalid 'path'")
        if not isinstance(content, (str, bytes)):
            return EffectOutcome(
                success=False, error=f"content must be str/bytes, got {type(content).__name__}"
            )

        path = Path(path_str)
        original_existed = path.exists()

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, str):
                path.write_text(content, encoding="utf-8")
            else:
                path.write_bytes(content)
        except OSError as exc:
            return EffectOutcome(success=False, error=str(exc))

        import hashlib

        sha = hashlib.sha256(
            content.encode("utf-8") if isinstance(content, str) else content
        ).hexdigest()
        return EffectOutcome(
            success=True,
            side_data={
                "sha256": sha,
                "original_existed": original_existed,
            },
        )

    def revert(self, ctx: EffectContext) -> EffectOutcome:
        path_str = ctx.payload.get("path")
        if not isinstance(path_str, str) or not path_str:
            return EffectOutcome(success=False, error="missing or invalid 'path'")
        path = Path(path_str)

        # If original content provided (base64 binary or str), restore it
        original_b64 = ctx.payload.get("original_content_b64")
        if isinstance(original_b64, str):
            try:
                import base64

                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(base64.b64decode(original_b64))
                return EffectOutcome(success=True)
            except OSError as exc:
                return EffectOutcome(success=False, error=str(exc))
        original_content = ctx.payload.get("original_content")
        if isinstance(original_content, str):
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(original_content, encoding="utf-8")
                return EffectOutcome(success=True)
            except OSError as exc:
                return EffectOutcome(success=False, error=str(exc))

        # Otherwise: delete the file (idempotent)
        if not path.exists():
            return EffectOutcome(success=True)  # already gone
        try:
            path.unlink()
        except OSError as exc:
            return EffectOutcome(success=False, error=str(exc))
        return EffectOutcome(success=True)


class DeleteFileEffect:
    """Delete a file. Revert: restore original content."""

    def apply(self, ctx: EffectContext) -> EffectOutcome:
        path_str = ctx.payload.get("path")
        if not isinstance(path_str, str) or not path_str:
            return EffectOutcome(success=False, error="missing or invalid 'path'")
        path = Path(path_str)

        if not path.exists():
            return EffectOutcome(success=True)  # already gone

        try:
            path.unlink()
        except OSError as exc:
            return EffectOutcome(success=False, error=str(exc))
        return EffectOutcome(success=True)

    def revert(self, ctx: EffectContext) -> EffectOutcome:
        path_str = ctx.payload.get("path")
        if not isinstance(path_str, str) or not path_str:
            return EffectOutcome(success=False, error="missing or invalid 'path'")
        path = Path(path_str)
        original_content = ctx.payload.get("original_content")

        # Idempotent: if file already exists with expected content, success
        if path.exists():
            return EffectOutcome(success=True)

        if not isinstance(original_content, str):
            # Cannot restore without original_content
            return EffectOutcome(
                success=False,
                error="cannot revert delete without 'original_content' payload",
            )

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(original_content, encoding="utf-8")
        except OSError as exc:
            return EffectOutcome(success=False, error=str(exc))
        return EffectOutcome(success=True)


class RenameFileEffect:
    """Rename src → dst. Revert: rename back dst → src."""

    def apply(self, ctx: EffectContext) -> EffectOutcome:
        src = ctx.payload.get("src")
        dst = ctx.payload.get("dst")
        if not isinstance(src, str) or not src:
            return EffectOutcome(success=False, error="missing or invalid 'src'")
        if not isinstance(dst, str) or not dst:
            return EffectOutcome(success=False, error="missing or invalid 'dst'")
        src_path = Path(src)
        dst_path = Path(dst)
        if not src_path.exists():
            return EffectOutcome(success=False, error=f"src not found: {src}")
        try:
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            src_path.rename(dst_path)
        except OSError as exc:
            return EffectOutcome(success=False, error=str(exc))
        return EffectOutcome(success=True)

    def revert(self, ctx: EffectContext) -> EffectOutcome:
        src = ctx.payload.get("src")
        dst = ctx.payload.get("dst")
        if not isinstance(src, str) or not isinstance(dst, str):
            return EffectOutcome(success=False, error="missing src/dst")
        src_path = Path(src)
        dst_path = Path(dst)
        # Idempotent: if src exists, already reverted
        if src_path.exists():
            return EffectOutcome(success=True)
        if not dst_path.exists():
            return EffectOutcome(success=True)  # nothing to revert
        try:
            dst_path.rename(src_path)
        except OSError as exc:
            return EffectOutcome(success=False, error=str(exc))
        return EffectOutcome(success=True)
