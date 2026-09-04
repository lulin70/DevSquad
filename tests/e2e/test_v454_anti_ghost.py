"""V4.5.4 P12.3 — Anti-Ghost gate tests (4 cases).

V4.5.4 extends the Anti-Ghost CI gate (check_module_activation.py) from
11 → 14 modules. This file tests the gate's wiring to ensure the 3 new
modules (ModuleFiber_P12.3.1 / CoeffectResolver_P12.3.2 / ModulesCLI_P12.3.3)
are bumped by their representative calls.

V4.5.13: extended to cover 8 previously-scanned-but-unverified counters
(ApprovalGate, ConnectorFramework, DoraMetricsCollector, GapAnalyzer,
ErrorBudgetTracker, RiskRegister, FileBundler, ScratchpadHistoryStore)
plus the v1 HostLLMBridge counter (file-backed protocol under
``logs/host_llm_bridge/v1``).
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e


class TestAntiGhostV454:
    def test_module_fiber_counter_bumped(self) -> None:
        """Constructing a ModuleFiberRegistry bumps get_call_counter_er()."""
        from scripts.collaboration.module_fiber import (
            ModuleFiberRegistry,
            get_call_counter_er,
        )

        before = get_call_counter_er()
        reg = ModuleFiberRegistry()
        reg.register("test")
        after = get_call_counter_er()
        assert after > before

    def test_coeffect_resolver_counter_bumped(self) -> None:
        """Constructing a CoeffectResolver bumps get_call_counter_er()."""
        from scripts.collaboration.coeffect import CoeffectResolver, _StaticProvider
        from scripts.collaboration.module_fiber import get_call_counter_er

        before = get_call_counter_er()
        r = CoeffectResolver()
        r.register(_StaticProvider("a", ()))
        r.register(_StaticProvider("b", ("a",)))
        r.resolve_activation_order()
        after = get_call_counter_er()
        # Construct + 2 registers + 1 resolve = 4 bumps minimum
        assert after >= before + 4

    def test_dispatcher_wires_all_3_new_modules(self) -> None:
        """Dispatcher's _init_module_fibers creates all 3 P12.3 components."""
        from scripts.collaboration.dispatcher import MultiAgentDispatcher

        d = MultiAgentDispatcher(
            persist_dir="/tmp/test_v454_anti_ghost", development_mode=True
        )
        # 3 P12.3 modules must be wired
        assert d._module_fiber_registry is not None
        assert d._coeffect_resolver is not None
        assert d._module_fibers  # non-empty dict

    def test_full_anti_ghost_gate_passes(self) -> None:
        """Run check_module_activation.py and verify exit 0."""
        import subprocess

        result = subprocess.run(
            [".venv/bin/python", "scripts/check_module_activation.py"],
            cwd="/Users/lin/trae_projects/DevSquad",
            capture_output=True,
            text=True,
            timeout=30,
        )
        # Gate must pass (exit 0)
        assert result.returncode == 0, (
            f"Anti-ghost gate failed:\n{result.stdout}\n{result.stderr}"
        )

    # ------------------------------------------------------------------
    # V4.5.13: 8 previously-scanned-but-unverified counters
    # ------------------------------------------------------------------

    def test_approval_gate_counter_bumped(self) -> None:
        """ApprovalGate.request_approval bumps module-level _call_counter_er."""
        from scripts.collaboration import approval_gate as ag_module
        from scripts.collaboration.approval_gate import ApprovalGate

        before = ag_module._call_counter_er
        gate = ApprovalGate()
        gate.request_approval(
            operation_type="anti-ghost",
            description="counter probe",
        )
        after = ag_module._call_counter_er
        assert after > before

    def test_connector_framework_counter_bumped(self) -> None:
        """GitHubConnector simulation probe bumps the module counter."""
        from scripts.collaboration import connector_framework as cf_module
        from scripts.collaboration.connector_framework import GitHubConnector

        before = cf_module._call_counter_er
        probe = GitHubConnector(simulation=True)
        probe.create_pr_comment(repo="o/r", pr_number=0, body="x")
        after = cf_module._call_counter_er
        assert after > before

    def test_dora_metrics_counter_bumped(self) -> None:
        """DoraMetricsCollector.collect_from_dispatch bumps the module counter."""
        from scripts.collaboration import dora_metrics_collector as dmc_module
        from scripts.collaboration.dora_metrics_collector import (
            DoraMetricsCollector,
        )

        before = dmc_module._call_counter_er
        DoraMetricsCollector().collect_from_dispatch([], window_days=30)
        after = dmc_module._call_counter_er
        assert after > before

    def test_gap_analyzer_counter_bumped(self) -> None:
        """GapAnalyzer.add_gap + analyze bumps the module counter."""
        from scripts.collaboration import gap_analyzer as ga_module
        from scripts.collaboration.gap_analyzer import GapAnalyzer

        before = ga_module._call_counter_er
        ga = GapAnalyzer()
        ga.add_gap(
            current_state="a",
            target_state="b",
            work_package="anti-ghost probe",
        )
        ga.analyze(current={"a": "1"}, target={"a": "2"})
        after = ga_module._call_counter_er
        assert after > before

    def test_error_budget_tracker_counter_bumped(self) -> None:
        """ErrorBudgetTracker.calculate bumps the module counter."""
        from scripts.collaboration import error_budget_tracker as ebt_module
        from scripts.collaboration.error_budget_tracker import ErrorBudgetTracker

        before = ebt_module._call_counter_er
        tracker = ErrorBudgetTracker()
        tracker.calculate(
            slo_target=0.999,
            window_days=30,
            observed_errors=0,
            total_events=100,
        )
        after = ebt_module._call_counter_er
        assert after > before

    def test_risk_register_counter_bumped(self) -> None:
        """RiskRegister.add + assess bumps the module counter."""
        from scripts.collaboration import risk_register as rr_module
        from scripts.collaboration.risk_register import RiskRegister

        before = rr_module._call_counter_er
        rr = RiskRegister()
        risk = rr.add(
            description="anti-ghost probe",
            probability=0.1,
            impact=0.1,
            category="delivery",
            owner="probe",
        )
        rr.assess(risk.id, votes={"architect": (0.1, 0.1)})
        after = rr_module._call_counter_er
        assert after > before

    def test_file_bundler_counter_bumped(self) -> None:
        """FileBundler.bundle bumps the module counter."""
        from scripts.collaboration import file_bundler as fb_module
        from scripts.collaboration.file_bundler import FileBundler

        before = fb_module._call_counter_er
        FileBundler().bundle(["a.py", "b.py"], max_per_bundle=2)
        after = fb_module._call_counter_er
        assert after > before

    def test_scratchpad_history_store_counter_bumped(self) -> None:
        """ScratchpadHistoryStore.write bumps the module counter (real SQLite)."""
        import tempfile
        from pathlib import Path

        from scripts.collaboration import scratchpad_history_store as shs_module
        from scripts.collaboration.models_base import (
            EntryType,
            ScratchpadEntry,
        )
        from scripts.collaboration.scratchpad_history_store import (
            ScratchpadHistoryStore,
        )

        before = shs_module._call_counter_er
        with tempfile.TemporaryDirectory() as tmp:
            store = ScratchpadHistoryStore(db_path=str(Path(tmp) / "h.db"))
            entry = ScratchpadEntry(
                worker_id="anti-ghost-probe",
                role_id="architect",
                entry_type=EntryType.FINDING,
                content="probe",
            )
            store.write(entry, scratchpad_id="probe")
            store.search_history(query="probe", limit=5)
            store.close()
        after = shs_module._call_counter_er
        assert after > before

    def test_host_llm_bridge_v1_counter_bumped(self) -> None:
        """HostLLMBridge (v1 protocol) create_request bumps _call_counter_er.

        V4.5.13: previously only the v2 backend was probed, leaving v1
        ghost-prone. This test pins the v1 protocol class counter so the
        anti-ghost gate fails closed if v1 wiring regresses.
        """
        import tempfile
        from pathlib import Path

        from scripts.collaboration import host_llm_bridge as hbb_module
        from scripts.collaboration.host_llm_bridge import HostLLMBridge

        before = hbb_module._call_counter_er
        with tempfile.TemporaryDirectory() as tmp:
            bridge = HostLLMBridge(bridge_dir=str(Path(tmp) / "v1"))
            bridge.create_request(
                agent_type="anti-ghost-v1-probe",
                task="probe",
                context={},
                prompt="probe",
            )
        after = hbb_module._call_counter_er
        assert after > before

    def test_full_anti_ghost_gate_exit_codes(self) -> None:
        """End-to-end: the gate exits 0 (pass) and 1 (forced-zero fail-closed).

        Belt-and-braces: runs the script as a subprocess to verify both
        the success path and the fail-closed contract (force-zeroing
        one counter via a wrapper script).
        """
        import subprocess
        import sys
        import tempfile
        import textwrap

        # Pass path
        result = subprocess.run(
            [sys.executable, "scripts/check_module_activation.py"],
            cwd="/Users/lin/trae_projects/DevSquad",
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stdout + result.stderr

        # Fail-closed path: force ApprovalGate counter to -100 so the
        # post-activation check fails. Mirrors the contract proven in
        # the L-V454-004 discipline (counters are monotonic; the gate
        # fails closed when any counter is non-positive).
        forced = textwrap.dedent(
            """
            import sys
            sys.path.insert(0, ".")
            import scripts.collaboration.approval_gate as ag
            ag._call_counter_er = -100
            import scripts.check_module_activation as cma

            orig = cma._activate_v4513_modules

            def _safe():
                try:
                    orig()
                finally:
                    ag._call_counter_er = -100

            cma._activate_v4513_modules = _safe
            sys.exit(cma.main())
            """
        )
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(forced)
            name = f.name
        fail_r = subprocess.run(
            [sys.executable, name],
            cwd="/Users/lin/trae_projects/DevSquad",
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert fail_r.returncode == 1, (
            f"fail-closed contract broken:\n{fail_r.stdout}\n{fail_r.stderr}"
        )
