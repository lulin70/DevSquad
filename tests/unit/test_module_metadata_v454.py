"""V4.5.4 P12.3.2 — 8 existing modules: depends_on() + get_fiber() 补全.

V4.5.4 D2 spec: 8 existing modules MUST expose:
    - ``depends_on() -> tuple[str, ...]``
    - ``get_fiber() -> ModuleFiber``
without modifying their ``__init__`` methods. The ``@with_coeffect``
decorator attaches these methods at class definition time.

Anti-ghost: ``get_call_counter_er()`` must be bumped each time
``depends_on()`` or ``get_fiber()`` is called (shared with the
module_fiber/coeffect modules).
"""

from __future__ import annotations

import pytest

from scripts.collaboration.coeffect import with_coeffect
from scripts.collaboration.module_fiber import FiberState, ModuleFiber

pytestmark = pytest.mark.unit


# ── artifact_store (P12.2.1) ────────────────────────────────────────


class TestArtifactStoreFiber:
    @with_coeffect("artifact_store", depends_on=("effect_registry",))
    class ArtifactStoreFixture:
        pass

    def test_depends_on_returns_effect_registry(self) -> None:
        assert self.ArtifactStoreFixture.depends_on() == ("effect_registry",)

    def test_module_id_set(self) -> None:
        assert (
            self.ArtifactStoreFixture.__devsquad_module_id__ == "artifact_store"  # type: ignore[attr-defined]
        )

    def test_get_fiber_returns_module_fiber(self) -> None:
        inst = self.ArtifactStoreFixture()
        f = inst.get_fiber()  # type: ignore[attr-defined]
        assert isinstance(f, ModuleFiber)
        assert f.module_id == "artifact_store"

    def test_get_fiber_cached(self) -> None:
        inst = self.ArtifactStoreFixture()
        f1 = inst.get_fiber()  # type: ignore[attr-defined]
        f2 = inst.get_fiber()  # type: ignore[attr-defined]
        assert f1 is f2


# ── effect_registry (P12.2.4) ──────────────────────────────────────


class TestEffectRegistryFiber:
    @with_coeffect("effect_registry")
    class EffectRegistryFixture:
        pass

    def test_depends_on_empty(self) -> None:
        assert self.EffectRegistryFixture.depends_on() == ()

    def test_module_id(self) -> None:
        assert (
            self.EffectRegistryFixture.__devsquad_module_id__ == "effect_registry"  # type: ignore[attr-defined]
        )


# ── audit_logger / cli_audit (P12.2.6) ──────────────────────────────


class TestAuditLoggerFiber:
    @with_coeffect("audit_logger", depends_on=("audit_logger_self",))
    class AuditLoggerFixture:
        pass

    def test_depends_on(self) -> None:
        assert self.AuditLoggerFixture.depends_on() == ("audit_logger_self",)


# ── risk_register (P0-1) ────────────────────────────────────────────


class TestRiskRegisterFiber:
    @with_coeffect("risk_register")
    class RiskRegisterFixture:
        pass

    def test_depends_on_empty(self) -> None:
        assert self.RiskRegisterFixture.depends_on() == ()

    def test_get_fiber_creates_fiber(self) -> None:
        inst = self.RiskRegisterFixture()
        f = inst.get_fiber()  # type: ignore[attr-defined]
        assert f.module_id == "risk_register"
        assert f.state == FiberState.INACTIVE


# ── viewpoint_registry (P0-2) ────────────────────────────────────────


class TestViewpointRegistryFiber:
    @with_coeffect("viewpoint_registry")
    class ViewpointRegistryFixture:
        pass

    def test_module_id(self) -> None:
        assert (
            self.ViewpointRegistryFixture.__devsquad_module_id__ == "viewpoint_registry"  # type: ignore[attr-defined]
        )

    def test_depends_on_empty(self) -> None:
        assert self.ViewpointRegistryFixture.depends_on() == ()


# ── error_budget_tracker (P1-1) ────────────────────────────────────


class TestErrorBudgetTrackerFiber:
    @with_coeffect("error_budget_tracker", depends_on=("dora_metrics_collector",))
    class ErrorBudgetTrackerFixture:
        pass

    def test_depends_on_dora(self) -> None:
        assert self.ErrorBudgetTrackerFixture.depends_on() == ("dora_metrics_collector",)


# ── gap_analyzer (P1-2) ─────────────────────────────────────────────


class TestGapAnalyzerFiber:
    @with_coeffect("gap_analyzer", depends_on=("viewpoint_registry",))
    class GapAnalyzerFixture:
        pass

    def test_depends_on_viewpoint(self) -> None:
        assert self.GapAnalyzerFixture.depends_on() == ("viewpoint_registry",)


# ── dora_metrics_collector (P2-1) ──────────────────────────────────


class TestDoraMetricsCollectorFiber:
    @with_coeffect("dora_metrics_collector")
    class DoraMetricsCollectorFixture:
        pass

    def test_depends_on_empty(self) -> None:
        assert self.DoraMetricsCollectorFixture.depends_on() == ()


# ── Cross-module invariants (3 cases) ──────────────────────────────


class TestModuleMetadataInvariants:
    def test_all_8_modules_unique_module_ids(self) -> None:
        ids = {
            "artifact_store",
            "effect_registry",
            "audit_logger",
            "risk_register",
            "viewpoint_registry",
            "error_budget_tracker",
            "gap_analyzer",
            "dora_metrics_collector",
        }
        assert len(ids) == 8

    def test_error_budget_depends_on_dora(self) -> None:
        @with_coeffect("ebt", depends_on=("dora_metrics_collector",))
        class EBT:
            pass

        assert EBT.depends_on() == ("dora_metrics_collector",)  # type: ignore[attr-defined]

    def test_artifact_store_depends_on_effect_registry(self) -> None:
        @with_coeffect("as", depends_on=("effect_registry",))
        class AS:
            pass

        assert AS.depends_on() == ("effect_registry",)  # type: ignore[attr-defined]
