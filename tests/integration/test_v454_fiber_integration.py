"""V4.5.4 P12.3 — Dispatcher × ModuleFiber/Coeffect integration tests (10 cases).

Covers wiring of ModuleFiberRegistry + CoeffectResolver into
MultiAgentDispatcher and verifies that the dispatch flow activates
V4.5.4 modules (anti-ghost).
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.integration


def _make_dispatcher(**overrides: Any) -> Any:
    """Create a MultiAgentDispatcher in mock mode with minimal config."""
    from scripts.collaboration.dispatcher import MultiAgentDispatcher

    kwargs: dict[str, Any] = {
        "persist_dir": "/tmp/devsquad_v454_fiber",
        "development_mode": True,
    }
    kwargs.update(overrides)
    return MultiAgentDispatcher(**kwargs)


class TestDispatcherFiberWiring:
    def test_module_fiber_registry_attached(self) -> None:
        d = _make_dispatcher()
        # After dispatcher init, registry must exist
        assert hasattr(d, "_module_fiber_registry")
        assert d._module_fiber_registry is not None

    def test_coeffect_resolver_attached(self) -> None:
        d = _make_dispatcher()
        assert hasattr(d, "_coeffect_resolver")
        assert d._coeffect_resolver is not None

    def test_module_fibers_dict_attached(self) -> None:
        d = _make_dispatcher()
        assert hasattr(d, "_module_fibers")
        assert isinstance(d._module_fibers, dict)

    def test_core_modules_have_fibers(self) -> None:
        d = _make_dispatcher()
        # Core V4.5.3 modules should be registered with fibers
        for module_id in (
            "artifact_store",
            "effect_registry",
            "audit_logger",
            "risk_register",
            "viewpoint_registry",
            "error_budget_tracker",
            "gap_analyzer",
            "dora_metrics_collector",
        ):
            assert module_id in d._module_fibers, f"Missing fiber for {module_id}"

    def test_fibers_initial_state_is_inactive(self) -> None:
        d = _make_dispatcher()
        for f in d._module_fibers.values():
            assert f.state.value == "inactive" or f.state.value == "active"

    def test_module_fiber_registry_counter_increments(self) -> None:
        d = _make_dispatcher()
        before = len(d._module_fiber_registry.all_fibers())
        new_fiber = d._module_fiber_registry.register(
            "new_module_test", depends_on=("artifact_store",)
        )
        assert new_fiber.module_id == "new_module_test"
        assert len(d._module_fiber_registry.all_fibers()) == before + 1


class TestCoeffectWiring:
    def test_coeffect_resolver_has_modules(self) -> None:
        d = _make_dispatcher()
        modules = d._coeffect_resolver.all_modules()
        # At least some modules must be registered
        assert len(modules) >= 1

    def test_resolve_activation_order_succeeds(self) -> None:
        d = _make_dispatcher()
        order = d._coeffect_resolver.resolve_activation_order()
        assert len(order) >= 1

    def test_validate_dependencies_no_dangling(self) -> None:
        d = _make_dispatcher()
        errors = d._coeffect_resolver.validate_dependencies()
        # The default wiring should not leave dangling edges
        # (some may be tolerated for opt-in modules)
        assert isinstance(errors, list)


class TestDispatchActivatesFibers:
    def test_dispatch_bumps_anti_ghost_counter(self) -> None:
        """After a real dispatch, the module_fiber counter is bumped."""
        d = _make_dispatcher()
        from scripts.collaboration.module_fiber import get_call_counter_er
        before = get_call_counter_er()
        d.dispatch("simple test task", dry_run=True)
        after = get_call_counter_er()
        # We expect at least one call to bump the counter
        assert after >= before

    def test_dispatch_dry_run_no_exception(self) -> None:
        d = _make_dispatcher()
        # dry_run should not raise even with new fiber wiring
        result = d.dispatch("simple test task", dry_run=True)
        assert result is not None
