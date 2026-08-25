#!/usr/bin/env python3
"""Contract tests for V4.5.4 Module Fiber + Coeffect cross-module public APIs.

These tests verify the **stable contracts** between the new ModuleFiber,
Coeffect, and dispatcher integration — fields, types, and naming conventions
that other code depends on. Breaking these contracts is a major version
bump, not a minor change.

Contracts under test (V4.5.4 P12.3):
  C1 FiberState enum has 6 members: inactive/activating/active/deactivating/failed/degraded
  C2 ALLOWED_TRANSITIONS dict covers all 6 states with valid targets
  C3 ModuleFiber exposes: module_id/state/depends_on/last_error/retry_count/activated_at
  C4 ModuleFiber.is_usable() → True iff state in (ACTIVE, DEGRADED)
  C5 CoeffectProvider Protocol has depends_on() and get_fiber() methods
  C6 CoeffectResolver.resolve_activation_order() returns list[str] with all modules
  C7 CoeffectResolver.detect_cycle() returns None on DAG, list on cycle
  C8 CoeffectCycleError.cycle attribute is list[str]
  C9 DispatcherConfig has 5 new V4.5.4 fields with documented defaults
  C10 ModuleFiberRegistry is thread-safe (concurrent register/get OK)
"""

from __future__ import annotations

import threading

import pytest

HERE = __file__
pytestmark = pytest.mark.contract


# ── C1: FiberState enum has 6 members ──────────────────────────────────────


class TestFiberStateContract:
    """C1: FiberState enum must expose exactly 6 lifecycle states."""

    def test_six_states_present(self):
        from scripts.collaboration.module_fiber import FiberState

        assert len(list(FiberState)) == 6

    def test_state_values(self):
        from scripts.collaboration.module_fiber import FiberState

        assert FiberState.INACTIVE.value == "inactive"
        assert FiberState.ACTIVATING.value == "activating"
        assert FiberState.ACTIVE.value == "active"
        assert FiberState.DEACTIVATING.value == "deactivating"
        assert FiberState.FAILED.value == "failed"
        assert FiberState.DEGRADED.value == "degraded"

    def test_state_string_serialization(self):
        """FiberState must be JSON-serializable as its .value string."""
        import json

        from scripts.collaboration.module_fiber import FiberState

        for s in FiberState:
            payload = json.dumps({"state": s.value})
            assert json.loads(payload)["state"] == s.value


# ── C2: ALLOWED_TRANSITIONS contract ───────────────────────────────────────


class TestAllowedTransitionsContract:
    """C2: ALLOWED_TRANSITIONS covers all 6 states."""

    def test_all_states_have_transition_table(self):
        from scripts.collaboration.module_fiber import ALLOWED_TRANSITIONS, FiberState

        for s in FiberState:
            assert s in ALLOWED_TRANSITIONS, f"missing {s!r} in transition table"
            assert isinstance(ALLOWED_TRANSITIONS[s], set)

    def test_self_transitions_not_allowed(self):
        """A state cannot transition to itself (would cause infinite loop)."""
        from scripts.collaboration.module_fiber import ALLOWED_TRANSITIONS

        for state, targets in ALLOWED_TRANSITIONS.items():
            assert state not in targets, (
                f"Self-transition {state} -> {state} would cause infinite loop"
            )


# ── C3: ModuleFiber exposed attributes ────────────────────────────────────


class TestModuleFiberFieldsContract:
    """C3: ModuleFiber exposes a stable public API surface."""

    def test_module_fiber_required_fields(self):
        from scripts.collaboration.module_fiber import ModuleFiber

        fiber = ModuleFiber("contract_test")
        # Required attributes
        assert hasattr(fiber, "module_id")
        assert hasattr(fiber, "state")
        assert hasattr(fiber, "depends_on")
        assert hasattr(fiber, "last_error")
        assert hasattr(fiber, "retry_count")
        assert hasattr(fiber, "activated_at")
        assert hasattr(fiber, "transition_history")

    def test_module_fiber_default_values(self):
        from scripts.collaboration.module_fiber import FiberState, ModuleFiber

        fiber = ModuleFiber("x")
        assert fiber.module_id == "x"
        assert fiber.state == FiberState.INACTIVE
        assert fiber.depends_on == ()
        assert fiber.last_error is None
        assert fiber.retry_count == 0
        assert fiber.activated_at is None
        assert fiber.transition_history == []


# ── C4: is_usable() contract ──────────────────────────────────────────────


class TestIsUsableContract:
    """C4: ModuleFiber.is_usable() iff state in (ACTIVE, DEGRADED)."""

    def test_active_is_usable(self):
        from scripts.collaboration.module_fiber import FiberState, ModuleFiber

        f = ModuleFiber("x")
        f.transition(FiberState.ACTIVATING)
        f.transition(FiberState.ACTIVE)
        assert f.is_usable() is True

    def test_degraded_is_usable(self):
        from scripts.collaboration.module_fiber import FiberState, ModuleFiber

        f = ModuleFiber("x")
        f.transition(FiberState.ACTIVATING)
        f.transition(FiberState.DEGRADED)
        assert f.is_usable() is True

    def test_failed_not_usable(self):
        from scripts.collaboration.module_fiber import FiberState, ModuleFiber

        f = ModuleFiber("x")
        f.transition(FiberState.ACTIVATING)
        f.transition(FiberState.FAILED)
        assert f.is_usable() is False

    def test_inactive_not_usable(self):
        from scripts.collaboration.module_fiber import ModuleFiber

        f = ModuleFiber("x")
        assert f.is_usable() is False


# ── C5: CoeffectProvider Protocol contract ────────────────────────────────


class TestCoeffectProviderContract:
    """C5: CoeffectProvider Protocol requires depends_on + get_fiber."""

    def test_static_provider_satisfies_protocol(self):
        from scripts.collaboration.coeffect import CoeffectProvider, _StaticProvider

        provider = _StaticProvider("m", ())
        assert isinstance(provider, CoeffectProvider)

    def test_class_without_methods_fails_protocol(self):
        from scripts.collaboration.coeffect import CoeffectProvider

        class NotAProvider:
            pass

        assert not isinstance(NotAProvider(), CoeffectProvider)


# ── C6: CoeffectResolver.resolve_activation_order contract ─────────────────


class TestResolveActivationOrderContract:
    """C6: resolve_activation_order returns list[str] covering all modules."""

    def test_returns_list_of_strings(self):
        from scripts.collaboration.coeffect import CoeffectResolver, _StaticProvider

        r = CoeffectResolver()
        r.register(_StaticProvider("a", ()))
        r.register(_StaticProvider("b", ("a",)))
        order = r.resolve_activation_order()
        assert isinstance(order, list)
        assert all(isinstance(x, str) for x in order)
        assert set(order) == {"a", "b"}

    def test_dependency_order_respected(self):
        from scripts.collaboration.coeffect import CoeffectResolver, _StaticProvider

        r = CoeffectResolver()
        r.register(_StaticProvider("root", ()))
        r.register(_StaticProvider("child", ("root",)))
        order = r.resolve_activation_order()
        assert order.index("root") < order.index("child")


# ── C7: CoeffectResolver.detect_cycle contract ────────────────────────────


class TestDetectCycleContract:
    """C7: detect_cycle returns None on DAG, list on cycle."""

    def test_dag_returns_none(self):
        from scripts.collaboration.coeffect import CoeffectResolver, _StaticProvider

        r = CoeffectResolver()
        r.register(_StaticProvider("a", ()))
        r.register(_StaticProvider("b", ("a",)))
        assert r.detect_cycle() is None

    def test_cycle_returns_list(self):
        from scripts.collaboration.coeffect import CoeffectResolver, _StaticProvider

        r = CoeffectResolver()
        r.register(_StaticProvider("x", ("y",)))
        r.register(_StaticProvider("y", ("x",)))
        cycle = r.detect_cycle()
        assert isinstance(cycle, list)
        assert set(cycle) == {"x", "y"}


# ── C8: CoeffectCycleError contract ──────────────────────────────────────


class TestCoeffectCycleErrorContract:
    """C8: CoeffectCycleError exposes .cycle attribute as list[str]."""

    def test_cycle_attribute_is_list_of_strings(self):
        from scripts.collaboration.coeffect import (
            CoeffectCycleError,
            CoeffectResolver,
            _StaticProvider,
        )

        r = CoeffectResolver()
        r.register(_StaticProvider("p", ("q",)))
        r.register(_StaticProvider("q", ("p",)))
        try:
            r.resolve_activation_order()
        except CoeffectCycleError as e:
            assert isinstance(e.cycle, list)
            assert all(isinstance(x, str) for x in e.cycle)
            assert set(e.cycle) == {"p", "q"}


# ── C9: DispatcherConfig 5 new V4.5.4 fields ──────────────────────────────


class TestDispatcherConfigV454FieldsContract:
    """C9: DispatcherConfig exposes 5 new V4.5.4 fields with documented defaults."""

    EXPECTED_FIELDS = {
        "enable_fiber": True,
        "enable_coeffect": True,
        "enable_modules_cli": True,
        "coeffect_failure_strategy": "degrade",
        "coeffect_max_retries": 1,
    }

    def test_all_5_fields_present(self):
        from scripts.collaboration.dispatcher_config import DispatcherConfig

        names = set(DispatcherConfig.field_names())
        for field in self.EXPECTED_FIELDS:
            assert field in names, f"V4.5.4 field {field!r} missing from DispatcherConfig"

    def test_default_values(self):
        from scripts.collaboration.dispatcher_config import DispatcherConfig

        config = DispatcherConfig()
        for field, expected in self.EXPECTED_FIELDS.items():
            assert getattr(config, field) == expected, (
                f"{field}: expected default {expected!r}, got {getattr(config, field)!r}"
            )


# ── C10: ModuleFiberRegistry thread safety ────────────────────────────────


class TestModuleFiberRegistryThreadSafetyContract:
    """C10: Concurrent register/get must not corrupt internal state."""

    def test_concurrent_registration(self):
        from scripts.collaboration.module_fiber import ModuleFiberRegistry

        reg = ModuleFiberRegistry()
        errors: list[Exception] = []

        def reg_n(i):
            try:
                reg.register(f"mod_{i}")
            except Exception as e:  # noqa: BLE001
                errors.append(e)

        threads = [threading.Thread(target=reg_n, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []
        assert len(reg.all_fibers()) == 20
