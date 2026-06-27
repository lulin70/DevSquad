#!/usr/bin/env python3
"""
Tests for RBAC fail-closed default behavior (硬约束 HC-1).

Verifies that MultiAgentDispatcher defaults to rbac_fail_closed=True,
ensuring RBAC infrastructure errors result in denied dispatch rather
than silent fail-open.  This aligns with the project hard constraint:
"共识门在关键决策失败时必须安全降级，禁止fail-open直接执行".

Test layers:
  1. Signature test — default parameter value is True
  2. Behavioral test — RBAC exception triggers fail-closed denial
  3. Override test — explicit rbac_fail_closed=False still allows fail-open
"""

from __future__ import annotations

import inspect
import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.dispatch_rbac import DispatchRBAC
from scripts.collaboration.dispatcher import MultiAgentDispatcher


class TestRbacFailClosedDefault(unittest.TestCase):
    """Layer 1: Verify default parameter value enforces fail-closed."""

    def test_rbac_fail_closed_defaults_to_true(self) -> None:
        """硬约束: rbac_fail_closed 默认必须为 True (fail-closed)."""
        sig = inspect.signature(MultiAgentDispatcher.__init__)
        param = sig.parameters.get("rbac_fail_closed")
        self.assertIsNotNone(param, "rbac_fail_closed parameter must exist")
        self.assertTrue(
            param.default is True,
            f"rbac_fail_closed must default to True (fail-closed), got {param.default}",
        )


class TestRbacFailClosedBehavior(unittest.TestCase):
    """Layer 2: Verify RBAC exception triggers fail-closed denial by default."""

    def _create_dispatcher_with_broken_rbac(
        self, rbac_fail_closed: bool | None = None
    ) -> MultiAgentDispatcher:
        """Create a dispatcher whose RBAC check will raise an exception."""
        kwargs: dict = {
            "enable_warmup": False,
            "enable_compression": False,
            "enable_permission": True,
            "enable_memory": False,
            "enable_skillify": False,
            "enable_quality_guard": False,
            "enable_anchor_check": False,
            "enable_retrospective": False,
            "enable_usage_tracker": False,
            "enable_feedback_loop": False,
            "enable_execution_guard": False,
            "enable_two_stage_review": False,
            "enable_redesign_audit": False,
            "enable_severity_router": False,
            "development_mode": True,
            "enable_audit_logger": False,
        }
        if rbac_fail_closed is not None:
            kwargs["rbac_fail_closed"] = rbac_fail_closed

        dispatcher = MultiAgentDispatcher(**kwargs)

        # Inject a broken RBAC that always raises
        broken_rbac = MagicMock(spec=DispatchRBAC)
        broken_rbac.check_dispatch_permission.side_effect = RuntimeError(
            "RBAC infrastructure failure"
        )
        dispatcher._rbac = broken_rbac
        return dispatcher

    def test_rbac_exception_denies_by_default(self) -> None:
        """默认情况下，RBAC 异常必须拒绝（fail-closed）。"""
        dispatcher = self._create_dispatcher_with_broken_rbac()
        self.assertTrue(
            dispatcher._rbac_fail_closed,
            "Default dispatcher must have rbac_fail_closed=True",
        )

        result = dispatcher.dispatch("test task", roles=["architect"])
        self.assertFalse(result.success, "Dispatch must fail when RBAC is broken")
        self.assertTrue(
            any("RBAC" in err or "fail-closed" in err for err in result.errors),
            f"Errors should mention RBAC failure, got: {result.errors}",
        )

    def test_explicit_fail_open_still_works(self) -> None:
        """显式 rbac_fail_closed=False 时，RBAC 异常放行（向后兼容）。"""
        dispatcher = self._create_dispatcher_with_broken_rbac(rbac_fail_closed=False)
        self.assertFalse(dispatcher._rbac_fail_closed)

        # With fail-open, the dispatch should proceed past RBAC check
        # (it may still fail later for other reasons, but not from RBAC)
        result = dispatcher.dispatch("test task", roles=["architect"])
        # Should NOT have RBAC fail-closed error
        self.assertFalse(
            any("fail-closed" in err for err in result.errors),
            "fail-open mode should not produce fail-closed errors",
        )


class TestRbacFailClosedDisabledRbac(unittest.TestCase):
    """Layer 3: When RBAC is disabled, fail-closed flag has no effect."""

    def test_no_rbac_no_fail_closed_check(self) -> None:
        """当无 RBAC 配置时，rbac_fail_closed 不影响正常调度。"""
        dispatcher = MultiAgentDispatcher(
            enable_warmup=False,
            enable_compression=False,
            enable_permission=False,  # Disable permission entirely
            enable_memory=False,
            enable_skillify=False,
            enable_quality_guard=False,
            enable_anchor_check=False,
            enable_retrospective=False,
            enable_usage_tracker=False,
            enable_feedback_loop=False,
            enable_execution_guard=False,
            enable_two_stage_review=False,
            enable_redesign_audit=False,
            enable_severity_router=False,
            development_mode=True,
            enable_audit_logger=False,
        )
        # Default should still be True
        self.assertTrue(dispatcher._rbac_fail_closed)

        # Dispatch should work fine without RBAC
        result = dispatcher.dispatch("test task", roles=["architect"])
        # Should not have RBAC errors (RBAC not configured)
        self.assertFalse(
            any("RBAC" in err for err in result.errors),
            f"Without RBAC configured, no RBAC errors expected, got: {result.errors}",
        )


if __name__ == "__main__":
    unittest.main()
