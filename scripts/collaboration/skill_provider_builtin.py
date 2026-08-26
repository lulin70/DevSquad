#!/usr/bin/env python3
"""BuiltinSkillProvider — wraps the existing import-based skill registry (V4.5.0).

Implements the ``SkillProvider`` protocol by delegating to ``skills.registry``
(``list_skills`` / ``get_skill``). This preserves 100% of the existing
import-based registration behavior (backward compatible) while exposing it
through the protocol-native interface so the agent core can swap providers
without touching skill code.

Architecture:
    Agent core (Worker/Coordinator) -> SkillProvider (protocol)
                                            |
                                            v
                                  BuiltinSkillProvider
                                            |
                                            v
                                  skills.registry (import-based, existing)

Anti-ghost: class-level ``_call_counter_er`` increments on every public method
call, proving the provider path is exercised (not ghost code).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class BuiltinSkillProvider:
    """Builtin skill provider wrapping the existing import-based registry.

    Implements the :class:`SkillProvider` protocol. Delegates discovery and
    instantiation to ``skills.registry`` (the existing import-based loader),
    and additionally accepts runtime-registered skill classes via
    :meth:`register`. The existing 8 sub-skills (dispatch/intent/review/
    security/test/retrospective/prototype/teach) are discovered unchanged.

    Backward compatibility: this provider only wraps existing logic; it does
    not alter ``skills.registry`` behavior. All previously available skills
    remain available through the same import path.
    """

    # Anti-ghost counter (class-level). Incremented by every public method.
    _call_counter_er: int = 0

    def __init__(self) -> None:
        # Runtime-registered skills: name -> skill class (BaseSkill subclass).
        self._extra: dict[str, type] = {}

    def register(self, name: str, skill_cls: type) -> None:
        """Register a skill class under a name.

        Args:
            name: Skill identifier (e.g. "my-skill").
            skill_cls: A class (typically a ``BaseSkill`` subclass) exposing
                ``name``/``description`` class attributes and a ``run()``
                method.
        """
        BuiltinSkillProvider._call_counter_er += 1
        self._extra[name] = skill_cls
        logger.debug("BuiltinSkillProvider.register: %s -> %s", name, skill_cls.__name__)

    def discover(self) -> dict[str, Any]:
        """Discover all available skills.

        Returns a dict mapping skill name -> skill info dict. Merges the
        built-in skills (loaded via ``skills.registry.list_skills``) with
        any runtime-registered skills from :meth:`register`.
        """
        BuiltinSkillProvider._call_counter_er += 1
        result: dict[str, Any] = {}
        # Built-in skills (existing import-based discovery).
        for name in self._list_builtin_skills():
            try:
                inst = self._get_builtin_instance(name)
                result[name] = inst.info()
            except Exception as e:  # noqa: BLE001 - discovery must not crash
                logger.warning("BuiltinSkillProvider.discover: skip '%s': %s", name, e)
        # Runtime-registered skills.
        for name, cls in self._extra.items():
            result[name] = {
                "name": name,
                "description": getattr(cls, "description", ""),
                "version": getattr(cls, "version", "1.0.0"),
                "source": "builtin-registered",
            }
        return result

    def instantiate(self, name: str) -> Any:
        """Instantiate a skill by name.

        Args:
            name: Skill identifier.

        Returns:
            A skill instance.

        Raises:
            ValueError: When the skill is not found.
        """
        BuiltinSkillProvider._call_counter_er += 1
        return self._get_instance(name)

    def invoke(self, name: str, **kwargs: Any) -> Any:
        """Invoke a skill by name with keyword arguments.

        Args:
            name: Skill identifier.
            **kwargs: Forwarded to the skill's ``run()`` method.

        Returns:
            The value returned by the skill's ``run()`` method.

        Raises:
            ValueError: When the skill is not found.
        """
        BuiltinSkillProvider._call_counter_er += 1
        inst = self._get_instance(name)
        return inst.run(**kwargs)

    # ------------------------------------------------------------------
    # Internal helpers (no counter increment — avoids double counting)
    # ------------------------------------------------------------------

    @staticmethod
    def _list_builtin_skills() -> list[str]:
        """List built-in skill names via the existing import-based registry."""
        from skills.registry import list_skills

        return list_skills()

    @staticmethod
    def _get_builtin_instance(name: str) -> Any:
        """Instantiate a built-in skill via the existing import-based registry."""
        from skills.registry import get_skill

        return get_skill(name)

    def _get_instance(self, name: str) -> Any:
        """Resolve a skill instance by name (runtime-registered first, then built-in)."""
        if name in self._extra:
            return self._extra[name]()
        try:
            return self._get_builtin_instance(name)
        except ValueError:
            available = sorted(set(self._extra.keys()) | set(self._list_builtin_skills()))
            raise ValueError(
                f"Skill '{name}' not found. Available: {available}"
            ) from None


__version__ = "1.0.0"
__all__ = ["BuiltinSkillProvider"]
