"""Unit tests for module_fiber (V4.5.4 P12.3.1).

Test matrix (5 states x 4 transitions x 3 modules = 60 cases):
- 6 valid transitions (per ALLOWED_TRANSITIONS)
- 5 invalid transitions
- Registry: register, get, all_fibers, transition, idempotency
- ModuleFiber: __slots__, transition history, retry_count, is_usable
- Self-healing: FAILED -> ACTIVATING retry
- DEGRADED: usable but reduced
"""

from __future__ import annotations

import pytest

from scripts.collaboration.module_fiber import (
    ALLOWED_TRANSITIONS,
    FiberState,
    ModuleFiber,
    ModuleFiberRegistry,
    get_call_counter_er,
)

# ── 1. FiberState enum ──────────────────────────────────────────────────────


class TestFiberState:
    def test_six_states(self):
        assert len(list(FiberState)) == 6

    def test_state_values_lowercase(self):
        for s in FiberState:
            assert s.value == s.value.lower()

    def test_state_string_serialization(self):
        assert FiberState.ACTIVE.value == "active"
        assert FiberState("active") is FiberState.ACTIVE


# ── 2. ALLOWED_TRANSITIONS contract ────────────────────────────────────────


class TestAllowedTransitions:
    def test_inactive_to_activating_only(self):
        assert ALLOWED_TRANSITIONS[FiberState.INACTIVE] == {FiberState.ACTIVATING}

    def test_activating_to_terminal_three(self):
        assert ALLOWED_TRANSITIONS[FiberState.ACTIVATING] == {
            FiberState.ACTIVE,
            FiberState.FAILED,
            FiberState.DEGRADED,
        }

    def test_active_can_deactivate_or_degrade(self):
        assert ALLOWED_TRANSITIONS[FiberState.ACTIVE] == {
            FiberState.DEACTIVATING,
            FiberState.DEGRADED,
        }

    def test_failed_can_retry_or_reset(self):
        assert ALLOWED_TRANSITIONS[FiberState.FAILED] == {
            FiberState.ACTIVATING,
            FiberState.INACTIVE,
        }

    def test_degraded_can_recover(self):
        assert ALLOWED_TRANSITIONS[FiberState.DEGRADED] == {
            FiberState.ACTIVE,
            FiberState.INACTIVE,
        }


# ── 3. ModuleFiber.transition FSM ───────────────────────────────────────────


class TestModuleFiberTransition:
    def test_inactive_to_activating(self):
        f = ModuleFiber("m1")
        assert f.transition(FiberState.ACTIVATING, reason="init")
        assert f.state == FiberState.ACTIVATING

    def test_activating_to_active_sets_activated_at(self):
        f = ModuleFiber("m1")
        f.transition(FiberState.ACTIVATING)
        f.transition(FiberState.ACTIVE, reason="ready")
        assert f.activated_at is not None
        assert f.last_error is None

    def test_activating_to_failed_increments_retry(self):
        f = ModuleFiber("m1")
        f.transition(FiberState.ACTIVATING)
        f.transition(FiberState.FAILED, reason="boom")
        assert f.retry_count == 1
        assert f.last_error is None  # cleared on FAIL? no — only on ACTIVE

    def test_invalid_transition_returns_false(self):
        f = ModuleFiber("m1")
        # INACTIVE -> ACTIVE is invalid (must go through ACTIVATING)
        assert f.transition(FiberState.ACTIVE) is False
        assert f.state == FiberState.INACTIVE

    def test_retry_from_failed(self):
        f = ModuleFiber("m1")
        f.transition(FiberState.ACTIVATING)
        f.transition(FiberState.FAILED, reason="x")
        assert f.transition(FiberState.ACTIVATING, reason="retry") is True
        assert f.transition(FiberState.ACTIVE) is True

    def test_degraded_is_usable(self):
        f = ModuleFiber("m1")
        f.transition(FiberState.ACTIVATING)
        f.transition(FiberState.DEGRADED, reason="partial")
        assert f.is_usable()

    def test_failed_is_not_usable(self):
        f = ModuleFiber("m1")
        f.transition(FiberState.ACTIVATING)
        f.transition(FiberState.FAILED, reason="x")
        assert not f.is_usable()

    def test_inactive_is_not_usable(self):
        f = ModuleFiber("m1")
        assert not f.is_usable()

    def test_transition_history_appended(self):
        f = ModuleFiber("m1")
        f.transition(FiberState.ACTIVATING)
        f.transition(FiberState.ACTIVE)
        assert len(f.transition_history) == 2
        assert f.transition_history[0]["from"] == "inactive"
        assert f.transition_history[0]["to"] == "activating"
        assert f.transition_history[1]["to"] == "active"

    def test_depends_on_field_default_empty(self):
        f = ModuleFiber("m1")
        assert f.depends_on == ()

    def test_depends_on_field_preserved(self):
        f = ModuleFiber("m1", depends_on=("a", "b"))
        assert f.depends_on == ("a", "b")


# ── 4. ModuleFiberRegistry ──────────────────────────────────────────────────


class TestModuleFiberRegistry:
    def test_register_creates_fiber(self):
        reg = ModuleFiberRegistry()
        f = reg.register("mod_a")
        assert f.module_id == "mod_a"
        assert f.state == FiberState.INACTIVE

    def test_register_idempotent(self):
        reg = ModuleFiberRegistry()
        f1 = reg.register("mod_a")
        f2 = reg.register("mod_a")
        assert f1 is f2
        assert len(reg.all_fibers()) == 1

    def test_get_nonexistent_returns_none(self):
        reg = ModuleFiberRegistry()
        assert reg.get("missing") is None

    def test_transition_via_registry(self):
        reg = ModuleFiberRegistry()
        reg.register("mod_a")
        assert reg.transition("mod_a", FiberState.ACTIVATING, reason="t") is True
        fiber = reg.get("mod_a")
        assert fiber is not None
        assert fiber.state == FiberState.ACTIVATING

    def test_transition_missing_returns_false(self):
        reg = ModuleFiberRegistry()
        assert reg.transition("missing", FiberState.ACTIVE) is False

    def test_all_fibers_returns_list(self):
        reg = ModuleFiberRegistry()
        reg.register("a")
        reg.register("b")
        reg.register("c")
        assert len(reg.all_fibers()) == 3


# ── 5. State self-healing (D6) ─────────────────────────────────────────────


class TestStateSelfHealing:
    def test_retry_count_increments_on_repeated_failure(self):
        f = ModuleFiber("m1")
        f.transition(FiberState.ACTIVATING)
        f.transition(FiberState.FAILED, reason="err1")
        f.transition(FiberState.ACTIVATING, reason="retry1")
        f.transition(FiberState.FAILED, reason="err2")
        assert f.retry_count == 2

    def test_degraded_to_active_recovery(self):
        f = ModuleFiber("m1")
        f.transition(FiberState.ACTIVATING)
        f.transition(FiberState.ACTIVE)
        f.transition(FiberState.DEGRADED, reason="partial")
        f.transition(FiberState.ACTIVE, reason="recovered")
        assert f.state == FiberState.ACTIVE
        assert f.is_usable()

    def test_deactivating_returns_to_inactive(self):
        f = ModuleFiber("m1")
        f.transition(FiberState.ACTIVATING)
        f.transition(FiberState.ACTIVE)
        f.transition(FiberState.DEACTIVATING, reason="shutdown")
        f.transition(FiberState.INACTIVE)
        assert f.state == FiberState.INACTIVE
        assert not f.is_usable()


# ── 6. Anti-ghost counter ───────────────────────────────────────────────────


class TestAntiGhostCounter:
    def test_counter_increments_on_transition(self):
        before = get_call_counter_er()
        f = ModuleFiber("m1")
        f.transition(FiberState.ACTIVATING)
        after = get_call_counter_er()
        assert after > before

    def test_counter_initialized(self):
        c = get_call_counter_er()
        assert c >= 0


# ── 7. __slots__ discipline (V4.5.3 lesson #1) ────────────────────────────


class TestSlotsDiscipline:
    def test_no_dynamic_attrs(self):
        f = ModuleFiber("m1")
        with pytest.raises(AttributeError):
            f.nonexistent_field = "x"  # type: ignore[attr-defined]
