#!/usr/bin/env python3
"""DispatcherConfig — Strongly-typed configuration dataclass for MultiAgentDispatcher.

Replaces the 43-parameter ``__init__`` signature of
:class:`scripts.collaboration.dispatcher.MultiAgentDispatcher` with a
semantic-grouped dataclass. New code should use::

    from scripts.collaboration.dispatcher_config import DispatcherConfig
    from scripts.collaboration.dispatcher import MultiAgentDispatcher

    config = DispatcherConfig(enable_warmup=False, persist_dir="/tmp/x")
    dispatcher = MultiAgentDispatcher.from_config(config)

The legacy ``MultiAgentDispatcher(**kwargs)`` entry point remains
supported for backward compatibility (5219 existing tests rely on it).

Groups (43 fields + extra kwargs):
    - Feature flags (16): ``enable_*`` booleans
    - Paths (4): persist_dir / memory_dir / audit_db_path / plugins_dropin_dir
    - Injected components (9): planner / router / agents / cache / rbac / logger / adapter / backend
    - Numerical thresholds (4): compression / max_fix / qa_pixel / autonomous_iter
    - Enums/strings (4): permission_level / lang / stream / development_mode
    - Boolean toggles (2): rbac_fail_closed / redis_url
    - QA (1): qa_enabled (V4.0.0 P1-2)
    - Autonomous (1): autonomous_enabled (V4.0.0 P3-1)
    - Plugins (2): plugins_enabled / plugins_no_hot_reload (V4.0.0 P3-2)
    - Extra: kwargs forwarded to EnterpriseFeature (backward compat)
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

from .dispatch_audit import DispatchAuditLogger
from .dispatch_rbac import DispatchRBAC
from .permission_guard import PermissionLevel

__all__ = ["DispatcherConfig"]


@dataclass(slots=True)
class DispatcherConfig:
    """Strongly-typed configuration for :class:`MultiAgentDispatcher`.

    Field names and defaults mirror ``MultiAgentDispatcher.__init__`` exactly
    so that ``MultiAgentDispatcher(**config.to_init_kwargs())`` is equivalent
    to ``MultiAgentDispatcher.from_config(config)``.
    """

    # ── Group 1: Feature flags (16) ──────────────────────────────────────
    enable_warmup: bool = True
    enable_compression: bool = True
    enable_permission: bool = True
    enable_memory: bool = True
    enable_skillify: bool = True
    enable_quality_guard: bool = True
    enable_anchor_check: bool = True
    enable_retrospective: bool = True
    enable_usage_tracker: bool = True
    # ``enable_feedback_loop`` accepts ``"auto"`` for auto-detection; preserve union type.
    enable_feedback_loop: bool | str = "auto"
    enable_redis_cache: bool = False
    enable_execution_guard: bool = True
    enable_two_stage_review: bool = True
    enable_redesign_audit: bool = True
    enable_severity_router: bool = True
    enable_audit_logger: bool = True

    # ── Group 2: Paths (4) ───────────────────────────────────────────────
    persist_dir: str | None = None
    memory_dir: str | None = None
    audit_db_path: str | Path | None = None
    plugins_dropin_dir: str | Path | None = None

    # ── Group 3: Injected components (9) — kept as Any for DI flexibility ─
    micro_task_planner: Any = None
    severity_router: Any = None
    judge_agent: Any = None
    content_cache: Any = None
    code_graph: Any = None
    rbac: DispatchRBAC | None = None
    audit_logger: DispatchAuditLogger | None = None
    mce_adapter: Any = None
    llm_backend: Any = None

    # ── Group 4: Numerical thresholds (4) ────────────────────────────────
    compression_threshold: int = 100000
    max_fix_iterations: int = 3
    qa_pixel_diff_threshold: float = 0.01
    autonomous_max_iterations: int = 20

    # ── Group 5: Enums/strings (4) ───────────────────────────────────────
    permission_level: PermissionLevel = PermissionLevel.DEFAULT
    lang: str = "auto"
    stream: bool = False
    development_mode: bool = True

    # ── Group 6: Boolean toggles / external services (2) ─────────────────
    # HC-1: fail-closed by default (硬约束: 禁止 fail-open).
    rbac_fail_closed: bool = True
    redis_url: str | None = None

    # ── Group 7: QA — UI/UX 巡检与视觉回归 (V4.0.0 P1-2) ─────────────────
    qa_enabled: bool = False

    # ── Group 8: Autonomous 自主迭代模式 (V4.0.0 P3-1) ───────────────────
    autonomous_enabled: bool = False

    # ── Group 9: 插件热加载 (V4.0.0 P3-2) ───────────────────────────────
    plugins_enabled: bool = False
    plugins_no_hot_reload: bool = False

    # ── Group 10: Backward-compat — kwargs 透传给 EnterpriseFeature ─────
    # Any unknown kwargs from legacy callers are preserved here so
    # ``to_init_kwargs()`` can re-emit them into ``**kwargs``.
    extra: dict[str, Any] = field(default_factory=dict, repr=False)

    # ── Conversion helpers ───────────────────────────────────────────────

    @classmethod
    def from_kwargs(cls, **kwargs: Any) -> DispatcherConfig:
        """Build a :class:`DispatcherConfig` from legacy ``__init__`` kwargs.

        Unknown keys (not matching any field) are captured in ``extra`` so
        that they can be forwarded to ``EnterpriseFeature(**kwargs)`` by
        :meth:`to_init_kwargs`.
        """
        field_names = {f.name for f in fields(cls) if f.name != "extra"}
        known = {k: v for k, v in kwargs.items() if k in field_names}
        extra = {k: v for k, v in kwargs.items() if k not in field_names}
        return cls(**known, extra=extra)

    def to_init_kwargs(self) -> dict[str, Any]:
        """Inverse of :meth:`from_kwargs` — emit kwargs for ``__init__``.

        Guarantees that::

            MultiAgentDispatcher(**config.to_init_kwargs())

        is equivalent to::

            MultiAgentDispatcher.from_config(config)
        """
        kwargs: dict[str, Any] = {}
        for f in fields(self):
            if f.name == "extra":
                continue
            kwargs[f.name] = getattr(self, f.name)
        # Merge extra last so explicit fields cannot be silently overridden
        # by legacy kwargs (extra keys are, by construction, non-field names).
        kwargs.update(self.extra)
        return kwargs

    def with_updates(self, **changes: Any) -> DispatcherConfig:
        """Return a copy with the given field changes applied.

        Thin wrapper around :func:`dataclasses.replace` that also routes
        unknown keys into ``extra`` (mirroring :meth:`from_kwargs` semantics).
        """
        from dataclasses import replace

        field_names = {f.name for f in fields(self) if f.name != "extra"}
        known = {k: v for k, v in changes.items() if k in field_names}
        extra_changes = {k: v for k, v in changes.items() if k not in field_names}
        new = replace(self, **known)
        if extra_changes:
            new_extra = dict(self.extra)
            new_extra.update(extra_changes)
            new.extra = new_extra
        return new

    # ── Inspection helpers (useful in tests + debugging) ─────────────────

    @classmethod
    def field_names(cls) -> set[str]:
        """Return the set of all dataclass field names (excluding ``extra``)."""
        return {f.name for f in fields(cls) if f.name != "extra"}

    def diff_from_default(self) -> dict[str, Any]:
        """Return only the fields whose value differs from the default."""
        defaults: dict[str, Any] = {}
        for f in fields(self):
            if f.name == "extra":
                continue
            # ``f.default`` is the literal default value for primitives;
            # ``f.default_factory`` is for mutables. We handle both.
            if f.default is not field:  # dataclass.field sentinel
                defaults[f.name] = f.default
            elif f.default_factory is not field:
                defaults[f.name] = f.default_factory()
            else:
                # No default (shouldn't happen for our schema), skip.
                continue
        return {
            f.name: getattr(self, f.name)
            for f in fields(self)
            if f.name != "extra" and getattr(self, f.name) != defaults.get(f.name)
        }
