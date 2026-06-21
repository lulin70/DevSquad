#!/usr/bin/env python3
"""
RoleSkillLoader - Load SKILL.md methodology frameworks for roles.

Inspired by phuryn/pm-skills: each SKILL.md encodes a proven PM/framework
that the role can follow step-by-step, instead of relying on generic LLM knowledge.

Architecture:
  skills/role_skills/<role_id>/<skill_name>/SKILL.md
  → RoleSkillLoader.load_skills(role_id) → list[SkillContent]
  → PromptAssembler._get_skill_injection() → injected into Worker prompt
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Base directory for role skill files
_SKILLS_BASE_DIR = Path(__file__).parent / "role_skills"


@dataclass
class SkillContent:
    """Parsed content of a single SKILL.md file."""
    skill_id: str
    name: str
    description: str
    role_id: str
    instructions: str  # The main instruction content (after frontmatter)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_prompt_text(self, max_length: int = 2000) -> str:
        """Format as prompt injection text, truncated to max_length."""
        text = f"## Methodology: {self.name}\n{self.instructions}"
        if len(text) > max_length:
            text = text[:max_length] + "\n...(truncated)"
        return text


def _parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Parse YAML frontmatter from SKILL.md content.

    Returns (metadata_dict, body_text).
    If no frontmatter found, returns ({}, full_content).
    """
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', content, re.DOTALL)
    if not match:
        return {}, content

    frontmatter_text = match.group(1)
    body = match.group(2)

    # Simple YAML parsing (no dependency on pyyaml for this)
    metadata: dict[str, Any] = {}
    for line in frontmatter_text.split('\n'):
        line = line.strip()
        if ':' in line and not line.startswith('#'):
            key, _, value = line.partition(':')
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if value:
                metadata[key] = value

    return metadata, body


class RoleSkillLoader:
    """
    Load and manage SKILL.md methodology frameworks for roles.

    Usage:
        loader = RoleSkillLoader()
        skills = loader.load_skills("product-manager")
        for skill in skills:
            print(skill.to_prompt_text())
    """

    # Security patterns to detect in SKILL.md content
    _SECURITY_PATTERNS = [
        (r"ignore\s+(previous|above|all)\s+instructions", "prompt_injection_ignore"),
        (r"you\s+are\s+now\s+(?:a|an)\s+(?!OWASP|Product|Security|System|Test|DevOps|UI)\w+", "role_hijack"),
        (r"system\s*:\s*", "system_prompt_leak"),
        (r"<\|im_start\|>", "chatml_injection"),
        (r"(\bADMIN_PASSWORD\b|\bSECRET_KEY\b|\bAPI_KEY\b)\s*=", "credential_exposure"),
        (r"exec\s*\(|eval\s*\(|__import__\s*\(", "code_injection"),
        (r"rm\s+-rf|del\s+/[sS]|format\s+[cC]:", "destructive_command"),
    ]

    def __init__(self, skills_dir: Path | str | None = None):
        """Initialize with optional custom skills directory.

        Args:
            skills_dir: Override default skills directory.
                        Defaults to scripts/collaboration/role_skills/
        """
        self._skills_dir = Path(skills_dir) if skills_dir else _SKILLS_BASE_DIR
        self._cache: dict[str, list[SkillContent]] = {}

    @staticmethod
    def _scan_skill_content(content: str) -> list[dict[str, str]]:
        """Scan SKILL.md content for security issues.

        Args:
            content: The full SKILL.md content (including frontmatter)

        Returns:
            List of security findings, each with 'pattern', 'type', and 'severity' keys.
            Empty list means content is safe.
        """
        findings = []
        for pattern, issue_type in RoleSkillLoader._SECURITY_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                findings.append({
                    "type": issue_type,
                    "pattern": pattern,
                    "severity": "critical" if issue_type in ("code_injection", "destructive_command", "credential_exposure") else "warning",
                })
        return findings

    def load_skills(self, role_id: str, *, no_cache: bool = False) -> list[SkillContent]:
        """Load all SKILL.md files for a given role.

        Args:
            role_id: Role identifier (e.g., "product-manager")
            no_cache: Force reload from disk

        Returns:
            List of parsed SkillContent objects
        """
        if not no_cache and role_id in self._cache:
            return self._cache[role_id]

        role_dir = self._skills_dir / role_id
        if not role_dir.is_dir():
            logger.debug("No skill directory for role: %s", role_id)
            self._cache[role_id] = []
            return []

        skills: list[SkillContent] = []
        for skill_dir in sorted(role_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.is_file():
                continue

            try:
                content = skill_file.read_text(encoding="utf-8")

                # Security scan
                security_findings = self._scan_skill_content(content)
                critical_findings = [f for f in security_findings if f["severity"] == "critical"]
                if critical_findings:
                    logger.warning(
                        "SKILL.md %s has critical security issues: %s — SKIPPED",
                        skill_file, [f["type"] for f in critical_findings],
                    )
                    continue
                elif security_findings:
                    logger.warning(
                        "SKILL.md %s has security warnings: %s",
                        skill_file, [f["type"] for f in security_findings],
                    )

                metadata, body = _parse_frontmatter(content)

                skill = SkillContent(
                    skill_id=f"{role_id}/{skill_dir.name}",
                    name=metadata.get("name", skill_dir.name),
                    description=metadata.get("description", ""),
                    role_id=role_id,
                    instructions=body.strip(),
                    metadata=metadata,
                )
                skills.append(skill)
            except (OSError, ValueError, KeyError, TypeError) as e:
                logger.warning("Failed to load skill %s: %s", skill_file, e)

        self._cache[role_id] = skills
        logger.info("Loaded %d skills for role %s", len(skills), role_id)
        return skills

    def get_skill(self, role_id: str, skill_name: str) -> SkillContent | None:
        """Get a specific skill by name for a role."""
        skills = self.load_skills(role_id)
        for skill in skills:
            if skill.name == skill_name or skill.skill_id.endswith(f"/{skill_name}"):
                return skill
        return None

    def list_available_skills(self, role_id: str | None = None) -> dict[str, list[str]]:
        """List all available skills, optionally filtered by role.

        Returns:
            Dict mapping role_id to list of skill names
        """
        result: dict[str, list[str]] = {}

        if role_id:
            skills = self.load_skills(role_id)
            if skills:
                result[role_id] = [s.name for s in skills]
        else:
            if not self._skills_dir.is_dir():
                return result
            for rd in sorted(self._skills_dir.iterdir()):
                if rd.is_dir():
                    skills = self.load_skills(rd.name)
                    if skills:
                        result[rd.name] = [s.name for s in skills]

        return result

    def clear_cache(self) -> None:
        """Clear the skill loading cache."""
        self._cache.clear()


# Module-level singleton
_shared_loader: RoleSkillLoader | None = None


def get_shared_loader() -> RoleSkillLoader:
    """Get or create shared singleton RoleSkillLoader."""
    global _shared_loader
    if _shared_loader is None:
        _shared_loader = RoleSkillLoader()
    return _shared_loader
