"""Contract tests — V4.5.4 vs V4.5.7 coeffect API compatibility.

Design §2.2 API mapping contract:
    - V4.5.4 CoeffectResolver keeps its sync topological-sort API unchanged.
    - V4.5.7 AsyncCoeffectResolver.resolve(req) is the drop-in sync entry
      (zero caller modification).
    - aresolve(req) returns an Awaitable[CoeffectResult].
    - Dataclass field sets and the 6-state enum are frozen contracts.
"""

from __future__ import annotations

import asyncio
import inspect

import pytest

from scripts.collaboration.async_coeffect_resolver import (
    AsyncCoeffectResolver,
    CoeffectRequest,
    CoeffectResult,
    CoeffectState,
)
from scripts.collaboration.coeffect import (
    CoeffectProvider,
    CoeffectResolver,
    _StaticProvider,
    with_coeffect,
)

pytestmark = pytest.mark.contract


class TestV454ApiUnchanged:
    def test_sync_resolver_api_surface(self):
        """V4.5.4 public API must remain importable and callable."""
        resolver = CoeffectResolver()
        resolver.register(_StaticProvider("a", ()))
        resolver.register(_StaticProvider("b", ("a",)))
        assert resolver.resolve_activation_order() == ["a", "b"]

    def test_v454_decorators_and_protocols_intact(self):
        assert callable(with_coeffect)
        assert isinstance(_StaticProvider("x", ()), CoeffectProvider)


class TestV457ApiContract:
    def test_resolve_is_sync_drop_in(self):
        """resolve(req) -> CoeffectResult synchronously — zero caller change
        vs the documented V4.5.7 mapping (design §2.2 row 1)."""
        resolver = AsyncCoeffectResolver()
        req = CoeffectRequest(name="contract", payload={"executor": lambda: 7})
        result = resolver.resolve(req)
        assert isinstance(result, CoeffectResult)
        assert result.state == CoeffectState.COMPLETED
        assert result.value == 7

    def test_aresolve_returns_awaitable(self):
        """aresolve(req) is a coroutine function returning CoeffectResult
        (design §2.2 row 2)."""
        assert inspect.iscoroutinefunction(AsyncCoeffectResolver.aresolve)
        resolver = AsyncCoeffectResolver()
        req = CoeffectRequest(name="async-contract", payload={"executor": lambda: 1})
        coro = resolver.aresolve(req)
        assert inspect.iscoroutine(coro)
        result = asyncio.run(coro)
        assert isinstance(result, CoeffectResult)

    def test_request_field_set_frozen(self):
        fields = set(CoeffectRequest.__dataclass_fields__)
        assert fields == {"name", "payload", "timeout"}

    def test_result_field_set_frozen(self):
        fields = set(CoeffectResult.__dataclass_fields__)
        assert fields == {"state", "value", "error"}
