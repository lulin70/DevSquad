"""Lightweight event bus for dispatch pipeline decoupling."""
import logging
from collections import defaultdict
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class EventBus:
    """Simple synchronous event bus for dispatch pipeline events.

    Events flow:
        dispatch.started → pre_dispatch.* → dispatch.executing →
        post_dispatch.* → dispatch.completed
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable]] = defaultdict(list)

    def on(self, event: str, handler: Callable) -> None:
        """Register a handler for an event."""
        self._handlers[event].append(handler)

    def emit(self, event: str, **kwargs: Any) -> None:
        """Emit an event, calling all registered handlers."""
        for handler in self._handlers.get(event, []):
            try:
                handler(**kwargs)
            except (RuntimeError, ValueError, TypeError, AttributeError) as e:
                logger.debug("Event handler failed for %s: %s", event, e)

    def off(self, event: str, handler: Callable | None = None) -> None:
        """Remove a handler. If handler is None, remove all handlers for event."""
        if handler is None:
            self._handlers.pop(event, None)
        else:
            self._handlers[event] = [h for h in self._handlers[event] if h != handler]

    def clear(self) -> None:
        """Remove all handlers."""
        self._handlers.clear()
