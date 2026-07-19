"""Tests for DispatcherConfig dataclass — V4.1.2 Phase 3 Wave 2 P1-4.

Verifies that:
1. DispatcherConfig has all 43 fields matching ``MultiAgentDispatcher.__init__`` params
2. Default values match the ``__init__`` defaults exactly
3. ``from_kwargs`` + ``to_init_kwargs`` round-trip preserves all data
4. ``MultiAgentDispatcher.from_config(config)`` is equivalent to
   ``MultiAgentDispatcher(**config.to_init_kwargs())``
5. ``with_updates`` returns a new config with the right field changes
6. ``diff_from_default`` correctly reports non-default fields
7. Unknown kwargs are captured in ``extra`` and re-emitted by ``to_init_kwargs``
8. Field type annotations match (PermissionLevel enum, DispatchRBAC, DispatchAuditLogger)
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import get_type_hints

import pytest

from scripts.collaboration.dispatch_audit import DispatchAuditLogger
from scripts.collaboration.dispatch_rbac import DispatchRBAC
from scripts.collaboration.dispatcher import MultiAgentDispatcher
from scripts.collaboration.dispatcher_config import DispatcherConfig
from scripts.collaboration.permission_guard import PermissionLevel

pytestmark = [pytest.mark.unit]


# ---------------------------------------------------------------------------
# 1. Field coverage — all __init__ params (except **kwargs) are dataclass fields
# ---------------------------------------------------------------------------


def _init_params() -> dict[str, inspect.Parameter]:
    """Return the parameter map for ``MultiAgentDispatcher.__init__``."""
    sig = inspect.signature(MultiAgentDispatcher.__init__)
    return {
        name: p
        for name, p in sig.parameters.items()
        if name not in ("self", "kwargs") and p.kind != p.VAR_KEYWORD
    }


class TestFieldCoverage:
    """Every ``__init__`` parameter must have a corresponding dataclass field."""

    def test_init_param_count_is_43(self) -> None:
        """Sanity check: __init__ still has 43 explicit parameters."""
        params = _init_params()
        assert len(params) == 43, (
            f"Expected 43 explicit params, got {len(params)}; "
            f"if __init__ signature changed, update DispatcherConfig."
        )

    def test_every_init_param_is_a_dataclass_field(self) -> None:
        """Each ``__init__`` param must map 1:1 to a DispatcherConfig field."""
        params = _init_params()
        field_names = DispatcherConfig.field_names()
        missing = set(params) - field_names
        assert not missing, (
            f"__init__ params missing from DispatcherConfig: {sorted(missing)}"
        )

    def test_every_dataclass_field_is_an_init_param(self) -> None:
        """No extra dataclass fields (except ``extra``) beyond __init__ params."""
        params = _init_params()
        field_names = DispatcherConfig.field_names()
        extras = field_names - set(params)
        assert not extras, (
            f"DispatcherConfig fields not in __init__: {sorted(extras)}"
        )


# ---------------------------------------------------------------------------
# 2. Default value parity — dataclass defaults match __init__ defaults
# ---------------------------------------------------------------------------


class TestDefaultParity:
    """Default values in DispatcherConfig must match ``__init__`` exactly."""

    def test_default_values_match_init(self) -> None:
        """For every field, ``DispatcherConfig().<field>`` == ``__init__`` default."""
        params = _init_params()
        config = DispatcherConfig()
        mismatches: list[str] = []
        for name, param in params.items():
            if param.default is inspect.Parameter.empty:
                mismatches.append(f"{name}: no default in __init__")
                continue
            init_default = param.default
            config_value = getattr(config, name)
            # Compare by value; PermissionLevel is an Enum so == works.
            if config_value != init_default:
                mismatches.append(
                    f"{name}: __init__={init_default!r} vs config={config_value!r}"
                )
        assert not mismatches, "Default mismatches:\n  " + "\n  ".join(mismatches)

    def test_extra_is_empty_dict_by_default(self) -> None:
        assert DispatcherConfig().extra == {}

    def test_default_permission_level_is_default(self) -> None:
        assert DispatcherConfig().permission_level is PermissionLevel.DEFAULT

    def test_default_rbac_fail_closed_is_true(self) -> None:
        """HC-1 hard constraint: rbac_fail_closed must default to True (fail-closed)."""
        assert DispatcherConfig().rbac_fail_closed is True

    def test_default_enable_feedback_loop_is_auto(self) -> None:
        """``enable_feedback_loop`` accepts 'auto' sentinel for auto-detection."""
        assert DispatcherConfig().enable_feedback_loop == "auto"


# ---------------------------------------------------------------------------
# 3. Round-trip — from_kwargs ↔ to_init_kwargs
# ---------------------------------------------------------------------------


class TestRoundTrip:
    """``from_kwargs(to_init_kwargs())`` must be idempotent."""

    def test_empty_kwargs_round_trips(self) -> None:
        config = DispatcherConfig.from_kwargs()
        assert config == DispatcherConfig()

    def test_known_kwargs_round_trip(self) -> None:
        kwargs = {
            "enable_warmup": False,
            "persist_dir": "/tmp/x",
            "compression_threshold": 50000,
            "permission_level": PermissionLevel.BYPASS,
            "lang": "en",
            "stream": True,
        }
        config = DispatcherConfig.from_kwargs(**kwargs)
        round_trip = config.to_init_kwargs()
        for k, v in kwargs.items():
            assert round_trip[k] == v, f"{k}: expected {v!r}, got {round_trip[k]!r}"

    def test_unknown_kwargs_go_to_extra(self) -> None:
        """Unknown kwargs must be captured in ``extra`` (forwarded to EnterpriseFeature)."""
        config = DispatcherConfig.from_kwargs(
            enable_warmup=False,
            enterprise_custom_flag="some_value",
            another_extra=42,
        )
        assert config.extra == {"enterprise_custom_flag": "some_value", "another_extra": 42}

    def test_extra_is_re_emitted_by_to_init_kwargs(self) -> None:
        """``to_init_kwargs`` must merge ``extra`` back so __init__ sees the kwargs."""
        config = DispatcherConfig.from_kwargs(enable_warmup=False, custom_flag="x")
        kwargs = config.to_init_kwargs()
        assert kwargs["custom_flag"] == "x"
        assert kwargs["enable_warmup"] is False

    def test_field_values_take_precedence_over_extra(self) -> None:
        """Field values cannot be silently overridden by ``extra``.

        ``from_kwargs()`` (the safe path) routes field-named kwargs to the
        dataclass field and never into ``extra``. Direct mutation of ``extra``
        is the caller's responsibility — ``to_init_kwargs()`` merges ``extra``
        last, which would override the field value. This documents the
        contract: use ``from_kwargs()`` or ``with_updates()`` to stay safe.
        """
        # ``from_kwargs()`` is safe: field-named kwargs never enter ``extra``.
        safe_config = DispatcherConfig.from_kwargs(enable_warmup=False)
        assert safe_config.to_init_kwargs()["enable_warmup"] is False
        assert "enable_warmup" not in safe_config.extra

        # Direct mutation of ``extra`` with a field name is documented foot-gun:
        # ``to_init_kwargs()`` would let ``extra`` win. Verify the contract.
        unsafe_config = DispatcherConfig(enable_warmup=False)
        unsafe_config.extra["enable_warmup"] = True
        unsafe_kwargs = unsafe_config.to_init_kwargs()
        assert unsafe_kwargs["enable_warmup"] is True  # extra wins (documented)

    def test_complex_types_round_trip(self) -> None:
        """Path, enum, and union types survive the round-trip."""
        config = DispatcherConfig(
            persist_dir="/tmp/p",
            audit_db_path=Path("/tmp/audit.db"),
            permission_level=PermissionLevel.AUTO,
            enable_feedback_loop=False,  # bool, not "auto"
            rbac=None,
        )
        kwargs = config.to_init_kwargs()
        assert kwargs["persist_dir"] == "/tmp/p"
        assert kwargs["audit_db_path"] == Path("/tmp/audit.db")
        assert kwargs["permission_level"] is PermissionLevel.AUTO
        assert kwargs["enable_feedback_loop"] is False
        assert kwargs["rbac"] is None


# ---------------------------------------------------------------------------
# 4. from_config equivalence — same as __init__(**to_init_kwargs())
# ---------------------------------------------------------------------------


class TestFromConfigEquivalence:
    """``MultiAgentDispatcher.from_config(cfg)`` ≡ ``MultiAgentDispatcher(**cfg.to_init_kwargs())``."""

    def test_from_config_returns_multi_agent_dispatcher(self, tmp_path: Path) -> None:
        config = DispatcherConfig(
            persist_dir=str(tmp_path),
            enable_warmup=False,
            enable_memory=False,
            enable_audit_logger=False,
        )
        disp = MultiAgentDispatcher.from_config(config)
        assert isinstance(disp, MultiAgentDispatcher)
        disp.shutdown()

    def test_from_config_matches_init_kwargs(self, tmp_path: Path) -> None:
        """Field values are observable on the dispatcher instance, matching __init__."""
        config = DispatcherConfig(
            persist_dir=str(tmp_path),
            enable_warmup=False,
            enable_compression=False,
            enable_memory=False,
            enable_audit_logger=False,
            lang="en",
            stream=True,
            compression_threshold=50000,
            permission_level=PermissionLevel.PLAN,
        )
        disp = MultiAgentDispatcher.from_config(config)
        try:
            assert disp.enable_warmup is False
            assert disp.enable_compression is False
            assert disp.enable_memory is False
            assert disp.lang == "en"
            assert disp.stream is True
            assert disp.compression_threshold == 50000
            assert disp.permission_level is PermissionLevel.PLAN
        finally:
            disp.shutdown()

    def test_legacy_init_still_works(self, tmp_path: Path) -> None:
        """Backward compat: 43-kwarg __init__ entry point remains functional."""
        disp = MultiAgentDispatcher(
            persist_dir=str(tmp_path),
            enable_warmup=False,
            enable_memory=False,
            enable_audit_logger=False,
        )
        assert isinstance(disp, MultiAgentDispatcher)
        disp.shutdown()

    def test_injected_components_are_passed_through(self, tmp_path: Path) -> None:
        """Injected RBAC / audit_logger survive the from_config path."""
        rbac = DispatchRBAC()
        audit_logger = DispatchAuditLogger(db_path=tmp_path / "audit.db")
        config = DispatcherConfig(
            persist_dir=str(tmp_path),
            enable_warmup=False,
            enable_memory=False,
            enable_audit_logger=True,
            rbac=rbac,
            audit_logger=audit_logger,
        )
        disp = MultiAgentDispatcher.from_config(config)
        try:
            assert disp._rbac is rbac
            assert disp._audit_logger is audit_logger
        finally:
            disp.shutdown()


# ---------------------------------------------------------------------------
# 5. with_updates — functional-style partial updates
# ---------------------------------------------------------------------------


class TestWithUpdates:
    """``with_updates`` returns a new config with applied changes."""

    def test_with_updates_returns_new_instance(self) -> None:
        cfg = DispatcherConfig()
        new_cfg = cfg.with_updates(enable_warmup=False)
        assert new_cfg is not cfg
        assert isinstance(new_cfg, DispatcherConfig)

    def test_with_updates_applies_known_fields(self) -> None:
        cfg = DispatcherConfig()
        new_cfg = cfg.with_updates(enable_warmup=False, lang="en", stream=True)
        assert new_cfg.enable_warmup is False
        assert new_cfg.lang == "en"
        assert new_cfg.stream is True
        # Unchanged fields retain their original values.
        assert new_cfg.enable_memory == cfg.enable_memory

    def test_with_updates_routes_unknown_to_extra(self) -> None:
        cfg = DispatcherConfig()
        new_cfg = cfg.with_updates(enable_warmup=False, custom_flag="x")
        assert new_cfg.enable_warmup is False
        assert new_cfg.extra == {"custom_flag": "x"}

    def test_with_updates_preserves_existing_extra(self) -> None:
        cfg = DispatcherConfig.from_kwargs(first_extra=1)
        new_cfg = cfg.with_updates(second_extra=2)
        assert new_cfg.extra == {"first_extra": 1, "second_extra": 2}


# ---------------------------------------------------------------------------
# 6. diff_from_default — only report non-default fields
# ---------------------------------------------------------------------------


class TestDiffFromDefault:
    """``diff_from_default`` returns only fields whose value differs from default."""

    def test_no_diff_for_default_config(self) -> None:
        assert DispatcherConfig().diff_from_default() == {}

    def test_diff_reports_only_changed_fields(self) -> None:
        cfg = DispatcherConfig(enable_warmup=False, lang="en")
        diff = cfg.diff_from_default()
        assert diff == {"enable_warmup": False, "lang": "en"}

    def test_diff_includes_complex_types(self) -> None:
        cfg = DispatcherConfig(permission_level=PermissionLevel.BYPASS)
        diff = cfg.diff_from_default()
        assert diff == {"permission_level": PermissionLevel.BYPASS}


# ---------------------------------------------------------------------------
# 7. Type annotations — verify the field types match the imports
# ---------------------------------------------------------------------------


class TestTypeAnnotations:
    """Field type annotations should reference the correct types."""

    def test_permission_level_field_is_enum(self) -> None:
        hints = get_type_hints(DispatcherConfig)
        assert hints["permission_level"] is PermissionLevel

    def test_rbac_field_accepts_none(self) -> None:
        hints = get_type_hints(DispatcherConfig)
        # ``DispatchRBAC | None`` shows up as ``Optional[DispatchRBAC]`` / Union.
        rbac_hint = hints["rbac"]
        # Accept either ``Optional[DispatchRBAC]`` or ``DispatchRBAC | None`` form.
        assert DispatchRBAC in getattr(rbac_hint, "__args__", (rbac_hint,))

    def test_audit_logger_field_accepts_none(self) -> None:
        hints = get_type_hints(DispatcherConfig)
        audit_hint = hints["audit_logger"]
        assert DispatchAuditLogger in getattr(audit_hint, "__args__", (audit_hint,))

    def test_enable_feedback_loop_is_union(self) -> None:
        """``enable_feedback_loop: bool | str`` — accepts 'auto' sentinel."""
        hints = get_type_hints(DispatcherConfig)
        fbl_hint = hints["enable_feedback_loop"]
        args = getattr(fbl_hint, "__args__", ())
        assert bool in args
        assert str in args


# ---------------------------------------------------------------------------
# 8. Repr / inspection helpers
# ---------------------------------------------------------------------------


class TestReprAndHelpers:
    """Repr should be readable; ``field_names`` is the canonical name set."""

    def test_repr_excludes_extra(self) -> None:
        """``extra`` is marked ``repr=False`` to avoid leaking injected kwargs."""
        cfg = DispatcherConfig.from_kwargs(secret_token="abc123")
        repr_str = repr(cfg)
        assert "secret_token" not in repr_str
        assert "extra" not in repr_str

    def test_field_names_count_is_43(self) -> None:
        """Sanity: ``field_names()`` returns exactly 43 names (matches __init__)."""
        assert len(DispatcherConfig.field_names()) == 43

    def test_field_names_excludes_extra(self) -> None:
        assert "extra" not in DispatcherConfig.field_names()

    def test_field_names_returns_set(self) -> None:
        assert isinstance(DispatcherConfig.field_names(), set)
