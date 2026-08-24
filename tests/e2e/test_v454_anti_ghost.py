"""V4.5.4 P12.3 — Anti-Ghost gate tests (4 cases).

V4.5.4 extends the Anti-Ghost CI gate (check_module_activation.py) from
11 → 14 modules. This file tests the gate's wiring to ensure the 3 new
modules (ModuleFiber_P12.3.1 / CoeffectResolver_P12.3.2 / ModulesCLI_P12.3.3)
are bumped by their representative calls.
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
            cwd="/Users/lin/trae_projects/DevSQuad",
            capture_output=True,
            text=True,
            timeout=30,
        )
        # Gate must pass (exit 0)
        assert result.returncode == 0, (
            f"Anti-ghost gate failed:\n{result.stdout}\n{result.stderr}"
        )
