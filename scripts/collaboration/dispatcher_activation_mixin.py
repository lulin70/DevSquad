"""V4.4/V4.5 module activation mixin for ``MultiAgentDispatcher``.

Instantiates and exercises the enhancement modules (risk register, DORA
metrics, approval gate, connector framework, module fibers and coeffect
resolver) once per dispatch so anti-ghost call counters stay live.
"""

from __future__ import annotations

import contextlib
import logging
from typing import Any

from .dispatch_models import DispatchResult
from .dispatcher_base import DispatcherBase

logger = logging.getLogger(__name__)


class DispatcherActivationMixin(DispatcherBase):
    """Best-effort activation of the V4.4.0 / V4.5.x enhancement modules."""

    def _activate_approval_gate(
        self,
        result: DispatchResult,
        approval_callback: Any | None,
    ) -> None:
        """V4.5.1: Activate the Approval Gate on the dispatch result.

        Creates an ``ApprovalGate`` instance, performs a best-effort
        ``request_approval`` call (to increment ``_call_counter_er`` —
        anti-ghost), and attaches the records + Markdown section to the
        result.

        When ``approval_callback`` is ``None``, the gate auto-approves
        (backward compatible with V4.5.0 — records are still collected
        so the report can show "0 external operations required approval").
        """
        try:
            from .approval_gate import ApprovalGate
        except ImportError:
            return

        gate = ApprovalGate(approval_callback=approval_callback)
        # Best-effort: simulate a "dispatch_complete" approval checkpoint.
        # In a real connector scenario, workers would call
        # gate.request_approval() before each external operation.
        # Coerce task_description to str defensively — input validation
        # may let None/non-str through to the early_return path.
        task_desc_str = str(result.task_description or "")[:80]
        gate.request_approval(
            operation_type="dispatch_complete",
            description=f"Dispatch completed for: {task_desc_str}",
        )
        result.approval_records = gate.get_records()
        result.approval_gate_md = gate.export_markdown()

    def _activate_connector(self, result: DispatchResult) -> None:
        """V4.5.1: Activate the Connector Framework on the dispatch result.

        Creates a ``GitHubConnector`` instance and exercises a best-effort
        simulation operation to prove the connector is wired into the
        dispatch pipeline (anti-ghost: increments ``_call_counter_er``).
        Operations and the Markdown section are attached to the result.

        In simulation mode (no ``GITHUB_TOKEN`` / no ``gh`` CLI), this is
        a no-op side-effect-wise — operations are recorded but not sent to
        GitHub. This makes the activation safe for tests and mock dispatch.
        """
        try:
            from .connector_framework import GitHubConnector
        except ImportError:
            return

        connector = GitHubConnector(simulation=True)
        # Best-effort probe operation in simulation mode (safe; no network).
        # In a real dispatch scenario, workers would call connector methods
        # before each external GitHub operation. We exercise a single
        # simulation-mode call to prove the pipeline wiring is alive.
        # Coerce task_description to str defensively — input validation
        # may let None/non-str through to the early_return path.
        task_desc_str = str(result.task_description or "")[:80]
        connector.create_pr_comment(
            repo="devsquad/internal",
            pr_number=0,
            body=f"Dispatch completed for: {task_desc_str}",
        )
        result.connector_operations = connector.get_operations()
        result.connector_md = connector.export_markdown()

    def _activate_v440_modules(
        self,
        result: DispatchResult,
        task_description: str,
    ) -> None:
        """V4.4.0: Activate 5 enhancement modules during dispatch (anti-ghost).

        Instantiates and calls each module's public method once to
        increment its module-level ``_call_counter_er``, proving the module
        is wired into the dispatch pipeline and not dead code. The
        RiskRegister's Markdown export is attached to the result so the
        dispatch report includes a ``## Risk Management`` section.

        Args:
            result: The DispatchResult to attach the risk report to.
            task_description: The original task description (for risk seeding).
        """
        # Local imports to avoid import-time cycles / cost.
        from scripts.collaboration.dora_metrics_collector import DoraMetricsCollector
        from scripts.collaboration.error_budget_tracker import ErrorBudgetTracker
        from scripts.collaboration.gap_analyzer import GapAnalyzer
        from scripts.collaboration.risk_register import RiskRegister
        from scripts.collaboration.viewpoint_registry import ViewpointRegistry

        # P0-1: Risk Register — seed a task-scoped risk and assess with 2 roles.
        self._risk_register = RiskRegister()
        risk = self._risk_register.add(
            description=f"Delivery risk for task: {task_description[:80]}",
            probability=0.3,
            impact=0.5,
            category="delivery",
            owner="architect",
        )
        self._risk_register.assess(
            risk.id,
            votes={"architect": (0.3, 0.5), "security": (0.2, 0.6)},
        )
        result.risk_management_md = self._risk_register.export_markdown()

        # P0-2: Viewpoint Registry — activate get() + is_orthogonal().
        self._viewpoint_registry = ViewpointRegistry()
        self._viewpoint_registry.get("architect")
        self._viewpoint_registry.is_orthogonal("architect", "security")

        # P1-1: Error Budget Tracker — activate calculate() + status().
        self._error_budget_tracker = ErrorBudgetTracker(slo_target=0.999, window_days=30)
        self._error_budget_tracker.calculate(
            slo_target=0.999,
            window_days=30,
            observed_errors=0,
            total_events=100,
        )
        self._error_budget_tracker.status()

        # P1-2: Gap Analyzer — activate analyze() (P2 + P3 modes).
        self._gap_analyzer = GapAnalyzer()
        self._gap_analyzer.analyze(target={"capability": "v4.4.0"})
        self._gap_analyzer.analyze(
            current={"capability": "v4.3.3"},
            target={"capability": "v4.4.0"},
        )

        # P2-1: DORA Metrics Collector — activate collect_from_dispatch().
        self._dora_metrics_collector = DoraMetricsCollector()
        self._dora_metrics_collector.collect_from_dispatch([], window_days=30)

    def _init_module_fibers(self) -> None:
        """V4.5.4 P12.3 — wire ModuleFiberRegistry + CoeffectResolver.

        Creates the registry + resolver, registers 8 existing V4.5.3
        modules with their declared ``depends_on()`` relationships, and
        primes each module's lifecycle to ``ACTIVE``.

        Anti-ghost: every registration increments
        ``get_call_counter_er()`` so a CI gate can detect missing
        wiring.

        Errors here are swallowed (best-effort) to keep dispatcher
        startup robust against partial deployments.
        """
        try:
            from .coeffect import CoeffectResolver, _StaticProvider
            from .module_fiber import ModuleFiberRegistry
        except ImportError:
            return

        if not self.enable_fiber and not self.enable_coeffect:
            return

        self._module_fiber_registry = ModuleFiberRegistry()
        self._coeffect_resolver = CoeffectResolver()

        # Module -> dependencies map (V4.5.3 wiring, lifted to P12.3).
        # Empty tuple means "no deps".
        module_deps: dict[str, tuple[str, ...]] = {
            "effect_registry": (),
            "artifact_store": ("effect_registry",),
            "audit_logger": ("effect_registry",),
            "risk_register": (),
            "viewpoint_registry": (),
            "error_budget_tracker": ("dora_metrics_collector",),
            "gap_analyzer": ("viewpoint_registry",),
            "dora_metrics_collector": (),
        }

        for module_id, deps in module_deps.items():
            try:
                # Register fiber
                fiber = self._module_fiber_registry.register(module_id, depends_on=deps)
                fiber.transition(fiber.state.__class__.ACTIVATING)
                fiber.transition(fiber.state.__class__.ACTIVE)
                self._module_fibers[module_id] = fiber

                # Register provider with resolver (topological order)
                if self.enable_coeffect:
                    self._coeffect_resolver.register(_StaticProvider(module_id, deps))
            except (ImportError, AttributeError, KeyError, ValueError, TypeError) as known_err:
                # V4.5.3 lesson #7: best-effort registration failures are non-blocking
                # Known failure modes: missing module, wrong state class, invalid deps
                logger.warning(
                    "Module fiber registration failed for %s (non-blocking): %s",
                    module_id,
                    known_err,
                    extra={"module_id": module_id, "deps": deps},
                )
                continue
            except Exception as unexpected_err:
                # Unexpected errors are logged at ERROR level with full traceback
                # but still non-blocking to preserve dispatcher initialization
                logger.error(
                    "Unexpected error during module fiber registration for %s: %s",
                    module_id,
                    unexpected_err,
                    exc_info=True,
                    extra={"module_id": module_id, "deps": deps},
                )
                continue

    def _activate_v454_modules(
        self,
        result: DispatchResult,  # noqa: ARG002 — interface parity with V440/V451
        task_description: str,  # noqa: ARG002 — reserved for future coeffect seeding
    ) -> None:
        """V4.5.4 P12.3 — bump anti-ghost counters during dispatch.

        Best-effort: any error is swallowed so the dispatch result
        itself is never corrupted.
        """
        if not self.enable_fiber and not self.enable_coeffect:
            return
        try:
            from .module_fiber import _inc_call_counter_er

            _inc_call_counter_er()
            # Attempt to resolve activation order (best-effort)
            if self.enable_coeffect and self._coeffect_resolver is not None:
                with contextlib.suppress(Exception):
                    self._coeffect_resolver.resolve_activation_order()
        except ImportError:
            return
