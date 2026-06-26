"""Factory functions for creating MultiAgentDispatcher instances.

Provides convenience constructors for common dispatcher usage patterns.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .dispatch_models import DispatchResult

if TYPE_CHECKING:
    from .dispatcher import MultiAgentDispatcher


def create_dispatcher(**kwargs: Any) -> MultiAgentDispatcher:
    """Factory function to create and initialize dispatcher."""
    from .dispatcher import MultiAgentDispatcher as MAD

    return MAD(**kwargs)


def quick_collaborate(task: str, **kwargs: Any) -> DispatchResult:
    """Convenience function: single-call collaboration."""
    disp = create_dispatcher(**kwargs)
    result = disp.dispatch(task)
    disp.shutdown()
    return result


async def async_quick_collaborate(
    task: str, roles: list[str] | None = None, **kwargs: Any
) -> DispatchResult:
    """Async version of quick_collaborate()."""
    disp = create_dispatcher(**kwargs)
    result = await disp.async_dispatch(task, roles=roles, **kwargs)
    disp.shutdown()
    return result
