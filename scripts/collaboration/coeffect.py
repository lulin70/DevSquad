#!/usr/bin/env python3
"""Coeffect — V4.5.4 P12.3.2 — Explicit dependency declaration + topological resolution.

Replaces implicit import-order coupling with explicit depends_on() metadata.
Provides Kahn's algorithm topological sort + iterative DFS cycle detection.

V4.5.3 lesson #5 applied: cross-module private state via public method.
V4.5.4 lesson (cycle safety): max_iter safety cap on Kahn's algorithm.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable

from .module_fiber import ModuleFiber, _inc_call_counter_er

logger = logging.getLogger(__name__)


# ── Errors ──────────────────────────────────────────────────────────────────


class CoeffectError(Exception):
    """Base error for Coeffect operations."""


class CoeffectCycleError(CoeffectError):
    """Raised when a dependency cycle is detected."""

    def __init__(self, cycle: list[str]) -> None:
        super().__init__(f"Coeffect cycle detected: {' -> '.join(cycle)}")
        self.cycle = cycle


class CoeffectDanglingError(CoeffectError):
    """Raised when depends_on references an unregistered module."""


# ── Provider Protocol + decorator ───────────────────────────────────────────


@runtime_checkable
class CoeffectProvider(Protocol):
    """Mix-in protocol: modules that declare dependencies.

    V4.5.3 lesson #5: cross-module private state MUST use public method.
    This protocol exposes get_fiber() and depends_on() as public APIs.
    """

    def depends_on(self) -> tuple[str, ...]: ...
    def get_fiber(self) -> ModuleFiber: ...


def with_coeffect(
    module_id: str,
    *,
    depends_on: tuple[str, ...] = (),
) -> Callable[[type], type]:
    """Decorator: attach module_id + depends_on to a class (zero-intrusion).

    V4.5.4 D2: 8 existing modules use this decorator WITHOUT modifying __init__.
    """

    def decorator(cls: type) -> type:
        cls.__devsquad_module_id__ = module_id  # type: ignore[attr-defined]
        cls.__devsquad_depends_on__ = depends_on  # type: ignore[attr-defined]

        def depends_on_fn(cls_or_self: Any) -> tuple[str, ...]:
            return cls.__devsquad_depends_on__  # type: ignore[attr-defined]

        def get_fiber_fn(self: Any) -> ModuleFiber:
            cached = getattr(self, "_fiber_cache", None)
            if cached is None:
                cached = ModuleFiber(
                    module_id=cls.__devsquad_module_id__,  # type: ignore[attr-defined]
                    depends_on=cls.__devsquad_depends_on__,  # type: ignore[attr-defined]
                )
                self._fiber_cache = cached
            return cached

        cls.depends_on = classmethod(depends_on_fn)  # type: ignore[attr-defined]
        cls.get_fiber = get_fiber_fn  # type: ignore[attr-defined]
        return cls

    return decorator


# ── Resolver ────────────────────────────────────────────────────────────────


class _StaticProvider:
    """Minimal CoeffectProvider for static (no-instance) registration."""

    def __init__(self, module_id: str, depends_on: tuple[str, ...]) -> None:
        self.__devsquad_module_id__ = module_id
        self.__devsquad_depends_on__ = depends_on

    def depends_on(self) -> tuple[str, ...]:
        return self.__devsquad_depends_on__

    def get_fiber(self) -> ModuleFiber:  # type: ignore[override]
        raise NotImplementedError("static provider has no fiber")


class CoeffectResolver:
    """Topological sort + cycle detection for module activation order.

    V4.5.4 lesson: explicit cycle detection is mandatory; Kahn's algorithm
    has a hard `max_iter` cap to prevent infinite loops on degenerate inputs.
    """

    def __init__(self) -> None:
        self._modules: dict[str, CoeffectProvider] = {}
        self._graph: dict[str, set[str]] = {}
        self._lock = threading.Lock()
        _inc_call_counter_er()

    def register(self, provider: CoeffectProvider) -> None:
        """Register a CoeffectProvider. Idempotent for same module_id."""
        module_id = getattr(provider, "__devsquad_module_id__", None) or provider.__class__.__name__
        deps = provider.depends_on()
        with self._lock:
            self._modules[module_id] = provider
            self._graph[module_id] = set(deps)
        _inc_call_counter_er()

    def resolve_activation_order(self) -> list[str]:
        """Kahn's algorithm topological sort.

        Raises:
            CoeffectCycleError: when a cycle is detected (or iteration cap hit).
        """
        _inc_call_counter_er()
        with self._lock:
            in_degree = {n: len(self._graph.get(n, set())) for n in self._modules}
            adj: dict[str, list[str]] = {n: [] for n in self._modules}
            for node, deps in self._graph.items():
                for dep in deps:
                    if dep in adj:
                        adj[dep].append(node)

            available = sorted([n for n, d in in_degree.items() if d == 0])
            result: list[str] = []
            completed: set[str] = set()
            # SAFETY: hard cap on iterations to prevent infinite loop on cycles
            max_iter = (len(self._modules) + 1) * (len(self._modules) + 1) + 100
            iter_count = 0
            while available:
                iter_count += 1
                if iter_count > max_iter:
                    break
                n = available.pop(0)
                result.append(n)
                completed.add(n)
                for m in adj[n]:
                    if m in completed:
                        continue
                    in_degree[m] -= 1
                    if in_degree[m] == 0 and m not in available:
                        available.append(m)
                available.sort()
            if len(result) != len(self._modules):
                cycle = self._detect_cycle_locked() or []
                raise CoeffectCycleError(cycle)
            return result

    def all_modules(self) -> dict[str, CoeffectProvider]:
        """Snapshot of all registered CoeffectProvider modules.

        Returns a copy so callers can iterate without holding the lock.
        """
        with self._lock:
            return dict(self._modules)

    def detect_cycle(self) -> list[str] | None:
        """Public cycle detection entry point (acquires lock)."""
        _inc_call_counter_er()
        with self._lock:
            return self._detect_cycle_locked()

    def _detect_cycle_locked(self) -> list[str] | None:
        """Iterative DFS-based cycle detection. Returns cycle path or None.

        Assumes the lock is already held by the caller.
        """
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = dict.fromkeys(self._modules, WHITE)
        parent: dict[str, str | None] = dict.fromkeys(self._modules)

        for start in sorted(self._modules):
            if color[start] != WHITE:
                continue
            # Iterative DFS using a stack of (node, neighbor_iter)
            stack: list[tuple[str, Any]] = [
                (start, iter(sorted(self._graph.get(start, set()))))
            ]
            color[start] = GRAY
            while stack:
                node, neighbors = stack[-1]
                advanced = False
                for nxt in neighbors:
                    if color[nxt] == GRAY:
                        # Cycle detected: reconstruct path
                        cycle: list[str] = [nxt, node]
                        p = parent[node]
                        while p is not None and p != nxt:
                            cycle.append(p)
                            p = parent[p]
                        cycle.append(nxt)
                        return list(reversed(cycle))
                    if color[nxt] == WHITE:
                        parent[nxt] = node
                        color[nxt] = GRAY
                        stack[-1] = (node, neighbors)  # keep current iter
                        stack.append((nxt, iter(sorted(self._graph.get(nxt, set())))))
                        advanced = True
                        break
                if not advanced:
                    color[node] = BLACK
                    stack.pop()
        return None

    def validate_dependencies(self) -> list[CoeffectError]:
        """Find dangling depends_on (referring to non-registered modules)."""
        _inc_call_counter_er()
        errors: list[CoeffectError] = []
        with self._lock:
            for module_id, deps in self._graph.items():
                for dep in deps:
                    if dep not in self._modules:
                        errors.append(
                            CoeffectDanglingError(
                                f"{module_id}.depends_on() references unregistered module {dep!r}"
                            )
                        )
        return errors
