"""
DevSquad V4.1.6 — Layered Sub-Skill Architecture

This package provides fine-grained, independently usable skills that wrap
DevSquad's core modules. Each sub-skill is a thin handler (~50 lines) that
imports from the existing collaboration layer — no duplicated logic.

Architecture:
    skills/
    ├── dispatch/      → MultiAgentDispatcher (7-role orchestration)
    ├── intent/        → IntentWorkflowMapper (6 intents × 3 languages)
    ├── review/        → FiveAxisConsensusEngine (5-axis code review)
    ├── security/      → Security audit + PermissionGuard
    ├── test/          → TestQualityGuard + test strategy
    └── retrospective/  → RetrospectiveEngine + pattern extraction

Usage (standalone):
    from skills.dispatch.handler import DispatchSkill
    result = DispatchSkill().run("Fix login bug")

Usage (via registry):
    from skills import SkillRegistry
    skill = SkillRegistry.get("dispatch")
    result = skill.run("Fix login bug")

All sub-skills work with Mock backend by default (no API key needed).
"""

from ._version import __version__
from .registry import BaseSkill, discover_all, get_skill, list_skills

__all__ = ["BaseSkill", "get_skill", "list_skills", "discover_all", "__version__"]
