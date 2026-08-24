"""Unit tests for coeffect (V4.5.4 P12.3.2).

Coverage:
- Kahn's algorithm topological sort (linear, multi-root, complex DAG)
- Iterative DFS cycle detection (self-loop, 2-cycle, 3-cycle, deep cycle)
- Dangling depends_on detection
- @with_coeffect decorator zero-intrusion (no __init__ modification)
- CoeffectProvider Protocol runtime_checkable
- CoeffectError / CoeffectCycleError / CoeffectDanglingError
- Thread safety smoke (run resolver concurrently)
- Anti-ghost counter
"""

from __future__ import annotations

import threading

import pytest

from scripts.collaboration.coeffect import (
    CoeffectCycleError,
    CoeffectDanglingError,
    CoeffectError,
    CoeffectProvider,
    CoeffectResolver,
    _StaticProvider,
    with_coeffect,
)
from scripts.collaboration.module_fiber import FiberState, get_call_counter_er

# ── 1. CoeffectProvider Protocol runtime_checkable ──────────────────────────


class TestCoeffectProviderProtocol:
    def test_static_provider_is_provider(self):
        p = _StaticProvider("x", ())
        assert isinstance(p, CoeffectProvider)

    def test_arbitrary_class_is_not_provider(self):
        class NotAProvider:
            pass

        assert not isinstance(NotAProvider(), CoeffectProvider)


# ── 2. Kahn's algorithm topological sort ────────────────────────────────────


class TestKahnTopologicalSort:
    def test_single_module(self):
        r = CoeffectResolver()
        r.register(_StaticProvider("only", ()))
        assert r.resolve_activation_order() == ["only"]

    def test_two_independent(self):
        r = CoeffectResolver()
        r.register(_StaticProvider("a", ()))
        r.register(_StaticProvider("b", ()))
        order = r.resolve_activation_order()
        assert set(order) == {"a", "b"}
        # Alphabetical: a before b
        assert order == ["a", "b"]

    def test_simple_chain(self):
        r = CoeffectResolver()
        r.register(_StaticProvider("a", ()))
        r.register(_StaticProvider("b", ("a",)))
        r.register(_StaticProvider("c", ("b",)))
        order = r.resolve_activation_order()
        assert order == ["a", "b", "c"]

    def test_diamond(self):
        r = CoeffectResolver()
        r.register(_StaticProvider("root", ()))
        r.register(_StaticProvider("left", ("root",)))
        r.register(_StaticProvider("right", ("root",)))
        r.register(_StaticProvider("top", ("left", "right")))
        order = r.resolve_activation_order()
        assert order[0] == "root"
        assert order[-1] == "top"
        assert order.index("left") < order.index("top")
        assert order.index("right") < order.index("top")

    def test_multi_roots(self):
        r = CoeffectResolver()
        r.register(_StaticProvider("a", ()))
        r.register(_StaticProvider("b", ()))
        r.register(_StaticProvider("c", ("a", "b")))
        order = r.resolve_activation_order()
        assert order.index("a") < order.index("c")
        assert order.index("b") < order.index("c")

    def test_real_devsquad_topology(self):
        """8 modules from PRD §0 D2."""
        r = CoeffectResolver()
        # tier 0
        r.register(_StaticProvider("effect_registry", ()))
        r.register(_StaticProvider("risk_register", ()))
        r.register(_StaticProvider("viewpoint_registry", ()))
        r.register(_StaticProvider("dora_metrics_collector", ()))
        r.register(_StaticProvider("audit_logger", ()))
        # tier 1
        r.register(_StaticProvider("artifact_store", ("effect_registry",)))
        r.register(_StaticProvider("error_budget_tracker", ("dora_metrics_collector",)))
        r.register(_StaticProvider("gap_analyzer", ("viewpoint_registry",)))
        r.register(_StaticProvider("cli_audit", ("audit_logger",)))
        order = r.resolve_activation_order()
        # tier-0 must come before tier-1
        for t1 in ("artifact_store", "error_budget_tracker", "gap_analyzer", "cli_audit"):
            assert t1 in order
        assert order.index("effect_registry") < order.index("artifact_store")
        assert order.index("dora_metrics_collector") < order.index("error_budget_tracker")
        assert order.index("viewpoint_registry") < order.index("gap_analyzer")
        assert order.index("audit_logger") < order.index("cli_audit")


# ── 3. Cycle detection ──────────────────────────────────────────────────────


class TestCycleDetection:
    def test_self_loop(self):
        r = CoeffectResolver()
        r.register(_StaticProvider("a", ("a",)))
        with pytest.raises(CoeffectCycleError):
            r.resolve_activation_order()

    def test_two_cycle(self):
        r = CoeffectResolver()
        r.register(_StaticProvider("x", ("y",)))
        r.register(_StaticProvider("y", ("x",)))
        with pytest.raises(CoeffectCycleError) as exc:
            r.resolve_activation_order()
        assert "x" in exc.value.cycle
        assert "y" in exc.value.cycle

    def test_three_cycle(self):
        r = CoeffectResolver()
        r.register(_StaticProvider("a", ("b",)))
        r.register(_StaticProvider("b", ("c",)))
        r.register(_StaticProvider("c", ("a",)))
        with pytest.raises(CoeffectCycleError) as exc:
            r.resolve_activation_order()
        cycle = set(exc.value.cycle)
        assert cycle == {"a", "b", "c"}

    def test_cycle_with_extras(self):
        r = CoeffectResolver()
        r.register(_StaticProvider("root", ()))
        r.register(_StaticProvider("a", ("b", "root")))
        r.register(_StaticProvider("b", ("a",)))
        with pytest.raises(CoeffectCycleError):
            r.resolve_activation_order()

    def test_detect_cycle_public_method(self):
        r = CoeffectResolver()
        r.register(_StaticProvider("x", ("y",)))
        r.register(_StaticProvider("y", ("x",)))
        cycle = r.detect_cycle()
        assert cycle is not None
        assert set(cycle) == {"x", "y"}

    def test_no_cycle_returns_none(self):
        r = CoeffectResolver()
        r.register(_StaticProvider("a", ()))
        r.register(_StaticProvider("b", ("a",)))
        assert r.detect_cycle() is None


# ── 4. Dangling dependency detection ───────────────────────────────────────


class TestDanglingDependency:
    def test_dangling_reported(self):
        r = CoeffectResolver()
        r.register(_StaticProvider("a", ("missing",)))
        errors = r.validate_dependencies()
        assert len(errors) == 1
        assert isinstance(errors[0], CoeffectDanglingError)

    def test_no_dangling_returns_empty(self):
        r = CoeffectResolver()
        r.register(_StaticProvider("a", ()))
        r.register(_StaticProvider("b", ("a",)))
        assert r.validate_dependencies() == []

    def test_multiple_dangling(self):
        r = CoeffectResolver()
        r.register(_StaticProvider("a", ("x", "y", "z")))
        errors = r.validate_dependencies()
        assert len(errors) == 3


# ── 5. @with_coeffect decorator (zero-intrusion) ────────────────────────────


class TestWithCoeffectDecorator:
    def test_decorator_attaches_metadata(self):
        @with_coeffect("test_mod", depends_on=("dep1",))
        class MyModule:
            def __init__(self):
                self.x = 1

        # __init__ unchanged
        m = MyModule()
        assert m.x == 1
        # New public methods added
        assert m.depends_on() == ("dep1",)

    def test_decorator_creates_fiber(self):
        @with_coeffect("m2", depends_on=("a",))
        class M2:
            def __init__(self):
                pass

        m = M2()
        f = m.get_fiber()
        assert f.module_id == "m2"
        assert f.depends_on == ("a",)
        # Fiber is cached (zero-intrusion: same instance)
        assert m.get_fiber() is f

    def test_decorator_no_dependencies(self):
        @with_coeffect("solo")
        class Solo:
            def __init__(self):
                pass

        m = Solo()
        assert m.depends_on() == ()

    def test_real_artifact_store_class_meta(self):
        """Test that the decorator pattern would work on a real class."""
        @with_coeffect("artifact_store_test", depends_on=("effect_registry",))
        class ArtifactStoreTest:
            pass

        m = ArtifactStoreTest()
        assert m.depends_on() == ("effect_registry",)
        f = m.get_fiber()
        f.transition(FiberState.ACTIVATING)
        f.transition(FiberState.ACTIVE)
        assert f.is_usable()


# ── 6. Error hierarchy ──────────────────────────────────────────────────────


class TestErrorHierarchy:
    def test_cycle_error_inherits_error(self):
        assert issubclass(CoeffectCycleError, CoeffectError)

    def test_dangling_error_inherits_error(self):
        assert issubclass(CoeffectDanglingError, CoeffectError)


# ── 7. Thread safety smoke ──────────────────────────────────────────────────


class TestThreadSafety:
    def test_concurrent_registration(self):
        r = CoeffectResolver()
        errors = []

        def reg(i):
            try:
                r.register(_StaticProvider(f"m{i}", ()))
            except Exception as e:  # noqa: BLE001
                errors.append(e)

        threads = [threading.Thread(target=reg, args=(i,)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []
        assert len(r._modules) == 50


# ── 8. Anti-ghost counter ──────────────────────────────────────────────────


class TestAntiGhostCounter:
    def test_register_increments_counter(self):
        before = get_call_counter_er()
        r = CoeffectResolver()
        r.register(_StaticProvider("test_inc", ()))
        after = get_call_counter_er()
        assert after > before
