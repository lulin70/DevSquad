#!/usr/bin/env python3
import json
import logging
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class SkillEntry:
    skill_id: str = field(default_factory=lambda: f"skill-{hashlib.md5(str(datetime.now().isoformat()).encode()).hexdigest()[:8]}")
    name: str = ""
    description: str = ""
    category: str = "general"
    version: str = "1.0.0"
    handler: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    confidence: float = 0.0
    usage_count: int = 0
    last_used: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'skill_id': self.skill_id, 'name': self.name, 'description': self.description,
            'category': self.category, 'version': self.version, 'handler': self.handler,
            'tags': self.tags, 'confidence': self.confidence, 'usage_count': self.usage_count,
            'last_used': self.last_used, 'created_at': self.created_at, 'metadata': self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SkillEntry':
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
        self.skills: Dict[str, SkillEntry] = {}
        self.handlers: Dict[str, Callable] = {}
        self._load()

    def register(self, skill: SkillEntry, handler: Optional[Callable] = None) -> str:
        if '..' in skill.skill_id or '/' in skill.skill_id or '\\' in skill.skill_id:
            raise ValueError(f"Invalid skill_id: {skill.skill_id}")
        self.skills[skill.skill_id] = skill
        if handler:
            self.handlers[skill.skill_id] = handler
        self._save()
        logger.info("Skill registered: %s (%s)", skill.name, skill.skill_id)
        return skill.skill_id

    def unregister(self, skill_id: str) -> bool:
        if skill_id in self.skills:
            del self.skills[skill_id]
            self.handlers.pop(skill_id, None)
            self._save()
            return True
        return False

    def get(self, skill_id: str) -> Optional[SkillEntry]:
        return self.skills.get(skill_id)

    def execute(self, skill_id: str, **kwargs) -> Any:
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

    def search(self, query: str = "", category: str = "", tags: List[str] = None) -> List[SkillEntry]:
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

    def propose_from_result(self, name: str, description: str, category: str = "",
                            confidence: float = 0.0, tags: List[str] = None) -> SkillEntry:
        skill = SkillEntry(
            name=name, description=description, category=category,
            confidence=confidence, tags=tags or [],
        )
        self.register(skill)
        return skill

    def list_skills(self, category: str = "") -> List[Dict[str, Any]]:
        skills = list(self.skills.values())
        if category:
            skills = [s for s in skills if s.category == category]
        return [s.to_dict() for s in skills]

    def get_stats(self) -> Dict[str, Any]:
        categories = {}
        for s in self.skills.values():
            categories[s.category] = categories.get(s.category, 0) + 1
        return {
            "total_skills": len(self.skills),
            "categories": categories,
            "with_handlers": len(self.handlers),
        }

    def _load(self):
        registry_file = self.storage_path / "registry.json"
        if registry_file.exists():
            try:
                with open(registry_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for skill_data in data.get('skills', []):
                    skill = SkillEntry.from_dict(skill_data)
                    self.skills[skill.skill_id] = skill
            except Exception as e:
                logger.warning("Failed to load skill registry: %s", e)

    def _save(self):
        registry_file = self.storage_path / "registry.json"
        try:
            data = {'skills': [s.to_dict() for s in self.skills.values()]}
            with open(registry_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning("Failed to save skill registry: %s", e)
