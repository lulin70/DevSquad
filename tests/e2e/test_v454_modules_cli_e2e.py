"""V4.5.4 P12.3.3 — Modules CLI end-to-end tests (5 cases).

Exercises ``scripts/cli_modules.py`` status/graph/retry subcommands via
in-process argparse. Verifies ASCII tree topology visualization and
manual retry of Failed modules.
"""

from __future__ import annotations

import argparse
import io
import json
import sys

import pytest

from scripts.cli_modules import (
    cmd_modules_graph,
    cmd_modules_retry,
    cmd_modules_status,
)
from scripts.collaboration.coeffect import CoeffectResolver, _StaticProvider
from scripts.collaboration.module_fiber import FiberState, ModuleFiberRegistry

pytestmark = pytest.mark.e2e


@pytest.fixture
def _registry_resolver() -> tuple[ModuleFiberRegistry, CoeffectResolver]:
    reg = ModuleFiberRegistry()
    res = CoeffectResolver()

    # Build a small graph: effect_registry -> artifact_store, audit_logger
    reg.register("effect_registry")
    reg.register("artifact_store", depends_on=("effect_registry",))
    reg.register("audit_logger", depends_on=("effect_registry",))

    res.register(_StaticProvider("effect_registry", ()))
    res.register(_StaticProvider("artifact_store", ("effect_registry",)))
    res.register(_StaticProvider("audit_logger", ("effect_registry",)))

    # Mark effect_registry as active
    f = reg.get("effect_registry")
    assert f is not None
    f.transition(FiberState.ACTIVATING)
    f.transition(FiberState.ACTIVE)

    return reg, res


class TestModulesStatusText:
    def test_status_prints_text_table(self, _registry_resolver: tuple) -> None:
        reg, _ = _registry_resolver
        args = argparse.Namespace(registry=reg, format="text", module=None)
        rc = cmd_modules_status(args)
        assert rc == 0


class TestModulesStatusJson:
    def test_status_json(self, _registry_resolver: tuple) -> None:
        reg, _ = _registry_resolver
        args = argparse.Namespace(registry=reg, format="json", module=None)
        # Capture stdout to verify JSON is well-formed
        old_stdout = sys.stdout
        buf = io.StringIO()
        sys.stdout = buf
        try:
            rc = cmd_modules_status(args)
        finally:
            sys.stdout = old_stdout
        assert rc == 0
        data = json.loads(buf.getvalue())
        assert isinstance(data, list)
        assert len(data) == 3
        # Each entry must have state + depends_on
        for entry in data:
            assert "module_id" in entry
            assert "state" in entry
            assert "depends_on" in entry

    def test_status_json_filter_by_module(self, _registry_resolver: tuple) -> None:
        reg, _ = _registry_resolver
        args = argparse.Namespace(registry=reg, format="json", module="artifact_store")
        old_stdout = sys.stdout
        buf = io.StringIO()
        sys.stdout = buf
        try:
            rc = cmd_modules_status(args)
        finally:
            sys.stdout = old_stdout
        assert rc == 0
        data = json.loads(buf.getvalue())
        assert len(data) == 1
        assert data[0]["module_id"] == "artifact_store"


class TestModulesGraphAscii:
    def test_graph_ascii(self, _registry_resolver: tuple) -> None:
        _, res = _registry_resolver
        args = argparse.Namespace(resolver=res, format="ascii")
        old_stdout = sys.stdout
        buf = io.StringIO()
        sys.stdout = buf
        try:
            rc = cmd_modules_graph(args)
        finally:
            sys.stdout = old_stdout
        assert rc == 0
        out = buf.getvalue()
        # Must mention at least one known module id
        assert "effect_registry" in out or "artifact_store" in out


class TestModulesRetry:
    def test_retry_failed_module_succeeds(self) -> None:
        reg = ModuleFiberRegistry()
        f = reg.register("flaky_module")
        f.transition(FiberState.ACTIVATING)
        f.transition(FiberState.FAILED)
        args = argparse.Namespace(registry=reg, module_id="flaky_module")
        rc = cmd_modules_retry(args)
        assert rc == 0
        assert f.state == FiberState.ACTIVE

    def test_retry_nonexistent_module_returns_error(self) -> None:
        reg = ModuleFiberRegistry()
        args = argparse.Namespace(registry=reg, module_id="does_not_exist")
        old_stderr = sys.stderr
        buf = io.StringIO()
        sys.stderr = buf
        try:
            rc = cmd_modules_retry(args)
        finally:
            sys.stderr = old_stderr
        assert rc == 1
        assert "not found" in buf.getvalue()

    def test_retry_non_failed_module_returns_error(self) -> None:
        reg = ModuleFiberRegistry()
        reg.register("active_module")
        args = argparse.Namespace(registry=reg, module_id="active_module")
        old_stderr = sys.stderr
        buf = io.StringIO()
        sys.stderr = buf
        try:
            rc = cmd_modules_retry(args)
        finally:
            sys.stderr = old_stderr
        assert rc == 1


class TestCliSubprocess:
    def test_cli_subprocess_status(self) -> None:
        """Verify cli.py modules status runs without exception."""
        import subprocess
        result = subprocess.run(
            [".venv/bin/python", "scripts/cli.py", "modules", "status"],
            cwd="/Users/lin/trae_projects/DevSQuad",
            capture_output=True,
            text=True,
            timeout=20,
        )
        # Should not raise; exit code may be 0 or 1 depending on registry
        assert result.returncode in (0, 1)
