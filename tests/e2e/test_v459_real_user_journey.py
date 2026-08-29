#!/usr/bin/env python3
"""V4.5.9 E2E — 真实用户 dispatch 旅程（AC-V2，用户规则：发布前模拟真实用户使用）。

旅程 A：sync dispatch（Coordinator gather 桥接，默认 CLI 路径）
旅程 B：async_dispatch（AsyncCoordinator 原生 gather 路径）

均使用 MockBackend，不触网；断言成功、含角色结果、executor=gather 标记。
"""

import asyncio

import pytest

from scripts.collaboration.dispatcher import MultiAgentDispatcher
from scripts.collaboration.llm_backend import MockBackend

ROLES = ["architect", "security", "tester"]
TASK = "设计认证系统"


def _make_dispatcher() -> MultiAgentDispatcher:
    return MultiAgentDispatcher(llm_backend=MockBackend())


@pytest.mark.e2e
def test_journey_a_sync_dispatch_full_report():
    """旅程 A：sync dispatch → success + 3 角色结果 + executor=gather 标记。"""
    disp = _make_dispatcher()
    result = disp.dispatch(TASK, roles=ROLES)

    assert result.success is True, f"errors={result.errors}"
    assert len(result.worker_results) >= len(ROLES)
    role_ids = {wr["role_id"] for wr in result.worker_results}
    assert set(ROLES) <= role_ids
    for wr in result.worker_results:
        assert wr["success"] is True
        assert wr.get("executor") == "gather", f"missing gather marker: {wr}"
        assert wr["output"]


@pytest.mark.e2e
def test_journey_b_async_dispatch_full_report():
    """旅程 B：async_dispatch → success + 3 角色结果 + executor=gather 标记。"""
    disp = _make_dispatcher()
    result = asyncio.run(disp.async_dispatch(TASK, roles=ROLES))

    assert result.success is True, f"errors={result.errors}"
    assert len(result.worker_results) >= len(ROLES)
    role_ids = {wr["role_id"] for wr in result.worker_results}
    assert set(ROLES) <= role_ids
    for wr in result.worker_results:
        assert wr["success"] is True
        assert wr.get("executor") == "gather", f"missing gather marker: {wr}"
        assert wr["output"]
