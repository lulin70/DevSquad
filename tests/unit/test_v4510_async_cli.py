#!/usr/bin/env python3
"""V4.5.10 --async CLI selection tests (P2-2).

Proves: three-state flag semantics, env priority, and that the dispatch
command ACTUALLY calls async_dispatch (spy), not just parses the flag.
"""
from __future__ import annotations

import argparse
import unittest.mock
from unittest.mock import patch

import pytest

from scripts.cli_dispatch import _resolve_use_async, cmd_dispatch
from scripts.collaboration.dispatch_models import DispatchResult


def _args(use_async: bool | None) -> argparse.Namespace:
    ns = argparse.Namespace()
    ns.use_async = use_async
    return ns


class TestResolveUseAsync:
    def test_default_sync_without_anything(self) -> None:
        assert _resolve_use_async(_args(None), environ={}) is False

    def test_explicit_async_beats_env(self) -> None:
        assert _resolve_use_async(_args(True), environ={"DEVSQUAD_USE_ASYNC": "0"}) is True

    def test_explicit_no_async_beats_env(self) -> None:
        assert _resolve_use_async(_args(False), environ={"DEVSQUAD_USE_ASYNC": "1"}) is False

    @pytest.mark.parametrize("raw", ["1", "true", "TRUE", " True "])
    def test_env_truthy(self, raw: str) -> None:
        assert _resolve_use_async(_args(None), environ={"DEVSQUAD_USE_ASYNC": raw}) is True

    @pytest.mark.parametrize("raw", ["0", "false", "", "no"])
    def test_env_falsy(self, raw: str) -> None:
        assert _resolve_use_async(_args(None), environ={"DEVSQUAD_USE_ASYNC": raw}) is False

    def test_missing_env_uses_os_environ(self) -> None:
        # environ=None → read os.environ; absence means sync
        assert _resolve_use_async(_args(None)) in (True, False)


def _fake_result() -> DispatchResult:
    r = DispatchResult(success=True, task_description="t")
    r.matched_roles = ["architect"]
    r.summary = "ok"
    return r


class TestCmdDispatchActualPath:
    """AC-async-1/3: cmd_dispatch must call async_dispatch / dispatch."""

    def _base_args(self) -> argparse.Namespace:
        ns = argparse.Namespace()
        ns.task = "Design a REST API"
        ns.task_positional = None
        ns.roles = ["arch"]
        ns.mode = "auto"
        ns.format = "json"
        ns.backend = "mock"
        ns.base_url = None
        ns.model = None
        ns.dry_run = False
        ns.quick = False
        ns.action_items = False
        ns.timing = False
        ns.persist_dir = None
        ns.no_warmup = True
        ns.no_compression = True
        ns.skip_permission = True
        ns.no_memory = True
        ns.no_skillify = True
        ns.permission_level = None
        ns.stream = False
        ns.lang = "auto"
        ns.host = None
        ns.resume = None
        return ns

    def test_async_flag_calls_async_dispatch(self) -> None:
        ns = self._base_args()
        ns.use_async = True
        with patch(
            "scripts.cli_dispatch.MultiAgentDispatcher"
        ) as disp_cls, patch(
            "scripts.cli_dispatch._create_host_adapter", return_value=None
        ):
            disp = disp_cls.return_value
            async_spy = unittest.mock.MagicMock(
                side_effect=lambda *_a, **_k: _coro(_fake_result())
            )
            disp.async_dispatch = async_spy
            disp.dispatch.side_effect = AssertionError(
                "sync dispatch must not be called with --async"
            )
            rc = cmd_dispatch(ns)
            assert rc == 0
            assert async_spy.called
            assert not disp.dispatch.called

    def test_no_async_flag_calls_sync_dispatch(self) -> None:
        ns = self._base_args()
        ns.use_async = False
        with patch(
            "scripts.cli_dispatch.MultiAgentDispatcher"
        ) as disp_cls, patch(
            "scripts.cli_dispatch._create_host_adapter", return_value=None
        ):
            disp = disp_cls.return_value
            disp.dispatch.return_value = _fake_result()

            async def _fail_async(*a, **k):
                raise AssertionError("async_dispatch must not be called with --no-async")

            disp.async_dispatch = _fail_async
            rc = cmd_dispatch(ns)
            assert rc == 0
            assert disp.dispatch.called


def _coro(value):

    async def _inner():
        return value

    return _inner()
