#!/usr/bin/env python3
import hashlib
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SkillEntry:
    skill_id: str = field(
        default_factory=lambda: f"skill-{hashlib.md5(str(datetime.now().isoformat()).encode(), usedforsecurity=False).hexdigest()[:8]}"
    )
    name: str = ""
    description: str = ""
    category: str = "general"
    version: str = "1.0.0"
    handler: str | None = None
    tags: list[str] = field(default_factory=list)
    confidence: float = 0.0
    usage_count: int = 0
    last_used: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the SkillEntry to a JSON-compatible dictionary.

        Returns:
            Dictionary containing all SkillEntry fields.
        """
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "version": self.version,
            "handler": self.handler,
            "tags": self.tags,
            "confidence": self.confidence,
            "usage_count": self.usage_count,
            "last_used": self.last_used,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SkillEntry":
        """Construct a SkillEntry from a dictionary, ignoring unknown keys.

        Args:
            data: Dictionary with SkillEntry field names.

        Returns:
            SkillEntry instance populated from the given data.
        """
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class SkillRegistry:
    """
    Skill registry for DevSquad.

    Manages reusable skill definitions that can be:
    - Auto-discovered from dispatch results
    - Manually registered by users
    - Matched to new tasks by category/tags
    - Persisted to disk for cross-session reuse
    """

    def __init__(self, storage_path: str = "./skills"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.skills: dict[str, SkillEntry] = {}
        self.handlers: dict[str, Callable] = {}
        self._load()

    def register(self, skill: SkillEntry, handler: Callable | None = None) -> str:
        """Register a skill and optional handler in the registry.

        Args:
            skill: SkillEntry describing the skill.
            handler: Optional callable invoked when the skill is executed.

        Returns:
            The skill_id of the registered skill.

        Raises:
            ValueError: When the skill_id contains path traversal characters.
        """
        if ".." in skill.skill_id or "/" in skill.skill_id or "\\" in skill.skill_id:
            raise ValueError(f"Invalid skill_id: {skill.skill_id}")
        self.skills[skill.skill_id] = skill
        if handler:
            self.handlers[skill.skill_id] = handler
        self._save()
        logger.info("Skill registered: %s (%s)", skill.name, skill.skill_id)
        return skill.skill_id

    def unregister(self, skill_id: str) -> bool:
        """Remove a skill and its handler from the registry.

        Args:
            skill_id: Identifier of the skill to remove.

        Returns:
            True when the skill existed and was removed, False otherwise.
        """
        if skill_id in self.skills:
            del self.skills[skill_id]
            self.handlers.pop(skill_id, None)
            self._save()
            return True
        return False

    def get(self, skill_id: str) -> SkillEntry | None:
        """Retrieve a skill entry by id.

        Args:
            skill_id: Identifier of the skill to retrieve.

        Returns:
            The matching SkillEntry, or None when not found.
        """
        return self.skills.get(skill_id)

    def execute(self, skill_id: str, **kwargs: Any) -> Any:
        """Execute a registered skill by id.

        Args:
            skill_id: Identifier of the skill to execute.
            **kwargs: Keyword arguments forwarded to the skill handler.

        Returns:
            The value returned by the skill handler.

        Raises:
            ValueError: When the skill or its handler is not found.
        """
        skill = self.skills.get(skill_id)
        if not skill:
            raise ValueError(f"Skill not found: {skill_id}")

        handler = self.handlers.get(skill_id)
        if not handler:
            raise ValueError(f"No handler for skill: {skill_id}")

        skill.usage_count += 1
        skill.last_used = datetime.now().isoformat()
        self._save()

        return handler(**kwargs)

    def search(self, query: str = "", category: str = "", tags: list[str] | None = None) -> list[SkillEntry]:
        """Search skills by query text, category, and tags.

        Args:
            query: Case-insensitive substring matched against name and
                description. Empty matches all.
            category: Exact category filter. Empty matches all.
            tags: List of tags; skills matching any tag are included.

        Returns:
            List of matching SkillEntry objects sorted by confidence desc.
        """
        results = list(self.skills.values())
        if category:
            results = [s for s in results if s.category == category]
        if tags:
            results = [s for s in results if any(t in s.tags for t in tags)]
        if query:
            q = query.lower()
            results = [s for s in results if q in s.name.lower() or q in s.description.lower()]
        results.sort(key=lambda s: s.confidence, reverse=True)
        return results

    def propose_from_result(
        self, name: str, description: str, category: str = "", confidence: float = 0.0, tags: list[str] | None = None
    ) -> SkillEntry:
        """Create and register a skill proposal from a dispatch result.

        Args:
            name: Human-readable skill name.
            description: Description of what the skill does.
            category: Optional category for the skill.
            confidence: Initial confidence score in [0.0, 1.0].
            tags: Optional list of tags for discovery.

        Returns:
            The newly registered SkillEntry.
        """
        skill = SkillEntry(
            name=name,
            description=description,
            category=category,
            confidence=confidence,
            tags=tags or [],
        )
        self.register(skill)
        return skill

    def list_skills(self, category: str = "") -> list[dict[str, Any]]:
        """List skills as dictionaries, optionally filtered by category.

        Args:
            category: Optional category filter. Empty lists all skills.

        Returns:
            List of skill dictionaries produced by :meth:`SkillEntry.to_dict`.
        """
        skills = list(self.skills.values())
        if category:
            skills = [s for s in skills if s.category == category]
        return [s.to_dict() for s in skills]

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics for the registry.

        Returns:
            Dictionary with total skill count, per-category counts, and
            the number of skills with registered handlers.
        """
        categories: dict[str, int] = {}
        for s in self.skills.values():
            categories[s.category] = categories.get(s.category, 0) + 1
        return {
            "total_skills": len(self.skills),
            "categories": categories,
            "with_handlers": len(self.handlers),
        }

    def _load(self) -> None:
        registry_file = self.storage_path / "registry.json"
        if registry_file.exists():
            try:
                with open(registry_file, encoding="utf-8") as f:
                    data = json.load(f)
                for skill_data in data.get("skills", []):
                    skill = SkillEntry.from_dict(skill_data)
                    self.skills[skill.skill_id] = skill
            except (json.JSONDecodeError, OSError, ValueError) as e:
                logger.warning("Failed to load skill registry: %s", e)

    def _save(self) -> None:
        registry_file = self.storage_path / "registry.json"
        try:
            data = {"skills": [s.to_dict() for s in self.skills.values()]}
            with open(registry_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except (OSError, TypeError, ValueError) as e:
            logger.warning("Failed to save skill registry: %s", e)
