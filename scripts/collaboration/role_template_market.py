#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Role Template Market

A marketplace for sharing and discovering role templates:
- Users can publish their custom role templates
- Community members can browse, install, and rate templates
- Templates include role prompts, rules, and configuration presets
- Compatible with SkillRegistry for cross-session persistence

Usage:
    from scripts.collaboration.role_template_market import RoleTemplateMarket

    market = RoleTemplateMarket()
    market.publish(template)
    results = market.search("security auditor")
    market.install(results[0].template_id)

Version: v1.0
Created: 2026-05-01
"""

import json
import hashlib
import logging
import os
import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_SAFE_ID_RE = re.compile(r'[^\w\-.]')


@dataclass
class RoleTemplate:
    """A reusable role template definition."""
    template_id: str = ""
    name: str = ""
    description: str = ""
    role_id: str = ""
    role_prompt: str = ""
    author: str = ""
    version: str = "1.0.0"
    category: str = "general"
    tags: List[str] = field(default_factory=list)
    rules: List[Dict[str, Any]] = field(default_factory=list)
    config_overrides: Dict[str, Any] = field(default_factory=dict)
    rating: float = 0.0
    install_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def __post_init__(self):
        if not self.template_id:
            raw = f"{self.name}:{self.role_id}:{self.author}:{datetime.now().isoformat()}"
            self.template_id = f"tpl-{hashlib.md5(raw.encode()).hexdigest()[:8]}"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RoleTemplate':
        valid_keys = cls.__dataclass_fields__.keys()
        return cls(**{k: v for k, v in data.items() if k in valid_keys})

    def validate(self) -> List[str]:
        """Validate template fields. Returns list of error messages."""
        errors = []
        if not self.name or len(self.name) < 2:
            errors.append("name must be at least 2 characters")
        if not self.role_id or len(self.role_id) < 2:
            errors.append("role_id must be at least 2 characters")
        if not self.role_prompt or len(self.role_prompt) < 10:
            errors.append("role_prompt must be at least 10 characters")
        if not self.author:
            errors.append("author is required")
        if self.rating < 0 or self.rating > 5:
            errors.append("rating must be between 0 and 5")
        return errors


@dataclass
class TemplateRating:
    """A user rating for a template."""
    template_id: str = ""
    user_id: str = ""
    score: float = 0.0
    comment: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class RoleTemplateMarket:
    """
    Role Template Market - discover, share, and install role templates.

    Features:
    - Publish custom role templates for community use
    - Search templates by keyword, category, or tags
    - Rate and review templates
    - Install templates for use in dispatch sessions
    - Export/import templates as JSON files
    """

    def __init__(self, storage_dir: Optional[str] = None):
        """
        Initialize Role Template Market.

        Args:
            storage_dir: Directory for template persistence
                         (default: data/role_templates)
        """
        self.storage_dir = Path(storage_dir or "data/role_templates")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._templates: Dict[str, RoleTemplate] = {}
        self._ratings: Dict[str, List[TemplateRating]] = {}
        self._load_from_disk()

    def _load_from_disk(self):
        """Load templates from disk storage."""
        templates_file = self.storage_dir / "templates.json"
        if templates_file.exists():
            try:
                data = json.loads(templates_file.read_text(encoding='utf-8'))
                for tpl_data in data:
                    tpl = RoleTemplate.from_dict(tpl_data)
                    self._templates[tpl.template_id] = tpl
            except Exception as e:
                logger.warning("Failed to load templates: %s", e)

        ratings_file = self.storage_dir / "ratings.json"
        if ratings_file.exists():
            try:
                data = json.loads(ratings_file.read_text(encoding='utf-8'))
                for r_data in data:
                    rating = TemplateRating(**r_data)
                    tid = rating.template_id
                    if tid not in self._ratings:
                        self._ratings[tid] = []
                    self._ratings[tid].append(rating)
            except Exception as e:
                logger.warning("Failed to load ratings: %s", e)

    def _save_to_disk(self):
        """Persist templates and ratings to disk."""
        try:
            templates_file = self.storage_dir / "templates.json"
            templates_data = [tpl.to_dict() for tpl in self._templates.values()]
            templates_file.write_text(
                json.dumps(templates_data, indent=2, ensure_ascii=False),
                encoding='utf-8'
            )

            ratings_file = self.storage_dir / "ratings.json"
            all_ratings = []
            for ratings_list in self._ratings.values():
                all_ratings.extend([asdict(r) for r in ratings_list])
            ratings_file.write_text(
                json.dumps(all_ratings, indent=2, ensure_ascii=False),
                encoding='utf-8'
            )
        except Exception as e:
            logger.warning("Failed to save templates: %s", e)

    def publish(self, template: RoleTemplate) -> str:
        """
        Publish a role template to the market.

        Args:
            template: RoleTemplate to publish

        Returns:
            str: template_id of the published template

        Raises:
            ValueError: If template validation fails
        """
        errors = template.validate()
        if errors:
            raise ValueError(f"Template validation failed: {'; '.join(errors)}")

        self._templates[template.template_id] = template
        self._save_to_disk()
        logger.info("Published template: %s (%s)", template.name, template.template_id)
        return template.template_id

    def search(self, query: str = "", category: str = "",
               tags: List[str] = None, limit: int = 20) -> List[RoleTemplate]:
        """
        Search templates by keyword, category, or tags.

        Args:
            query: Search keyword (matches name, description, role_id)
            category: Filter by category
            tags: Filter by tags (OR match)
            limit: Maximum results to return

        Returns:
            List of matching RoleTemplate objects, sorted by rating
        """
        results = []
        query_lower = query.lower() if query else ""

        for tpl in self._templates.values():
            if category and tpl.category != category:
                continue

            if tags:
                if not any(t in tpl.tags for t in tags):
                    continue

            if query_lower:
                searchable = f"{tpl.name} {tpl.description} {tpl.role_id} {' '.join(tpl.tags)}".lower()
                if query_lower not in searchable:
                    continue

            results.append(tpl)

        results.sort(key=lambda t: t.rating, reverse=True)
        return results[:limit]

    def get(self, template_id: str) -> Optional[RoleTemplate]:
        """Get a template by ID."""
        return self._templates.get(template_id)

    def install(self, template_id: str) -> Optional[RoleTemplate]:
        """
        Install a template for use in dispatch sessions.

        Increments install count and returns the template.

        Args:
            template_id: Template ID to install

        Returns:
            RoleTemplate if found, None otherwise
        """
        tpl = self._templates.get(template_id)
        if not tpl:
            return None

        tpl.install_count += 1
        tpl.updated_at = datetime.now().isoformat()
        self._save_to_disk()

        install_dir = self.storage_dir / "installed"
        install_dir.mkdir(exist_ok=True)
        safe_id = _SAFE_ID_RE.sub('_', template_id)
        install_file = install_dir / f"{safe_id}.json"
        install_file.write_text(
            json.dumps(tpl.to_dict(), indent=2, ensure_ascii=False),
            encoding='utf-8'
        )

        logger.info("Installed template: %s (%s)", tpl.name, template_id)
        return tpl

    def rate(self, template_id: str, user_id: str, score: float,
             comment: str = "") -> bool:
        """
        Rate a template.

        Args:
            template_id: Template ID to rate
            user_id: Rater's user ID
            score: Rating score (0-5)
            comment: Optional comment

        Returns:
            True if rating was recorded, False if template not found
        """
        tpl = self._templates.get(template_id)
        if not tpl:
            return False

        if score < 0 or score > 5:
            raise ValueError("Score must be between 0 and 5")

        rating = TemplateRating(
            template_id=template_id,
            user_id=user_id,
            score=score,
            comment=comment,
        )

        if template_id not in self._ratings:
            self._ratings[template_id] = []
        self._ratings[template_id].append(rating)

        all_scores = [r.score for r in self._ratings[template_id]]
        tpl.rating = round(sum(all_scores) / len(all_scores), 1)
        tpl.updated_at = datetime.now().isoformat()

        self._save_to_disk()
        return True

    def list_categories(self) -> List[str]:
        """List all available template categories."""
        return sorted(set(tpl.category for tpl in self._templates.values()))

    def get_popular(self, limit: int = 10) -> List[RoleTemplate]:
        """Get most popular templates by install count."""
        sorted_tpls = sorted(
            self._templates.values(),
            key=lambda t: t.install_count,
            reverse=True
        )
        return sorted_tpls[:limit]

    def export_template(self, template_id: str, output_path: str) -> bool:
        """Export a template to a JSON file."""
        tpl = self._templates.get(template_id)
        if not tpl:
            return False
        try:
            Path(output_path).write_text(
                json.dumps(tpl.to_dict(), indent=2, ensure_ascii=False),
                encoding='utf-8'
            )
            return True
        except Exception as e:
            logger.warning("Export failed: %s", e)
            return False

    def import_template(self, input_path: str) -> Optional[str]:
        """Import a template from a JSON file."""
        try:
            data = json.loads(Path(input_path).read_text(encoding='utf-8'))
            tpl = RoleTemplate.from_dict(data)
            return self.publish(tpl)
        except Exception as e:
            logger.warning("Import failed: %s", e)
            return None

    def get_stats(self) -> Dict[str, Any]:
        """Get market statistics."""
        return {
            "total_templates": len(self._templates),
            "total_categories": len(self.list_categories()),
            "total_ratings": sum(len(r) for r in self._ratings.values()),
            "total_installs": sum(t.install_count for t in self._templates.values()),
            "avg_rating": round(
                sum(t.rating for t in self._templates.values()) / len(self._templates), 1
            ) if self._templates else 0.0,
        }


__all__ = ["RoleTemplate", "TemplateRating", "RoleTemplateMarket"]
