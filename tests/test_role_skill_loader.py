#!/usr/bin/env python3
"""Tests for RoleSkillLoader — SKILL.md loading and prompt injection."""

from pathlib import Path

from scripts.collaboration.role_skill_loader import (
    RoleSkillLoader,
    SkillContent,
    _parse_frontmatter,
    get_shared_loader,
)


class TestFrontmatterParsing:
    """Tests for _parse_frontmatter."""

    def test_parse_valid_frontmatter(self):
        content = "---\nname: create-prd\ndescription: Create a PRD\n---\n## Instructions\nDo stuff."
        meta, body = _parse_frontmatter(content)
        assert meta["name"] == "create-prd"
        assert meta["description"] == "Create a PRD"
        assert "## Instructions" in body

    def test_parse_no_frontmatter(self):
        content = "Just plain markdown content."
        meta, body = _parse_frontmatter(content)
        assert meta == {}
        assert body == content

    def test_parse_empty_frontmatter(self):
        content = "---\n---\nBody text."
        meta, body = _parse_frontmatter(content)
        assert meta == {}
        assert "Body text." in body

    def test_parse_frontmatter_with_quotes(self):
        content = "---\nname: \"my skill\"\ndescription: 'a skill'\n---\nBody."
        meta, body = _parse_frontmatter(content)
        assert meta["name"] == "my skill"
        assert meta["description"] == "a skill"


class TestSkillContent:
    """Tests for SkillContent dataclass."""

    def test_to_prompt_text_basic(self):
        skill = SkillContent(
            skill_id="product-manager/create-prd",
            name="Create PRD",
            description="Create a PRD",
            role_id="product-manager",
            instructions="1. Gather info\n2. Write PRD",
        )
        text = skill.to_prompt_text()
        assert "## Methodology: Create PRD" in text
        assert "1. Gather info" in text

    def test_to_prompt_text_truncation(self):
        skill = SkillContent(
            skill_id="test/long",
            name="Long Skill",
            description="",
            role_id="test",
            instructions="x" * 5000,
        )
        text = skill.to_prompt_text(max_length=200)
        assert len(text) <= 250  # Allow some overhead
        assert "truncated" in text


class TestRoleSkillLoader:
    """Tests for RoleSkillLoader."""

    def _create_skill_dir(self, tmp: Path, role_id: str, skill_name: str, content: str):
        """Helper to create a SKILL.md in the test directory."""
        skill_dir = tmp / role_id / skill_name
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")

    def test_load_skills_empty_dir(self, tmp_path):
        loader = RoleSkillLoader(skills_dir=tmp_path)
        skills = loader.load_skills("product-manager")
        assert skills == []

    def test_load_skills_nonexistent_role(self, tmp_path):
        loader = RoleSkillLoader(skills_dir=tmp_path)
        skills = loader.load_skills("nonexistent-role")
        assert skills == []

    def test_load_single_skill(self, tmp_path):
        self._create_skill_dir(
            tmp_path,
            "product-manager",
            "create-prd",
            "---\nname: create-prd\ndescription: Create a PRD\n---\n## Instructions\nWrite a PRD.",
        )
        loader = RoleSkillLoader(skills_dir=tmp_path)
        skills = loader.load_skills("product-manager")
        assert len(skills) == 1
        assert skills[0].name == "create-prd"
        assert "Write a PRD." in skills[0].instructions

    def test_load_multiple_skills(self, tmp_path):
        self._create_skill_dir(
            tmp_path,
            "product-manager",
            "create-prd",
            "---\nname: create-prd\n---\nPRD content.",
        )
        self._create_skill_dir(
            tmp_path,
            "product-manager",
            "prioritization",
            "---\nname: prioritization-frameworks\n---\nPrio content.",
        )
        loader = RoleSkillLoader(skills_dir=tmp_path)
        skills = loader.load_skills("product-manager")
        assert len(skills) == 2

    def test_load_skills_caching(self, tmp_path):
        self._create_skill_dir(
            tmp_path,
            "product-manager",
            "create-prd",
            "---\nname: create-prd\n---\nContent.",
        )
        loader = RoleSkillLoader(skills_dir=tmp_path)
        skills1 = loader.load_skills("product-manager")
        skills2 = loader.load_skills("product-manager")
        assert skills1 is skills2  # Same object from cache

    def test_load_skills_no_cache(self, tmp_path):
        self._create_skill_dir(
            tmp_path,
            "product-manager",
            "create-prd",
            "---\nname: create-prd\n---\nContent.",
        )
        loader = RoleSkillLoader(skills_dir=tmp_path)
        skills1 = loader.load_skills("product-manager")
        skills2 = loader.load_skills("product-manager", no_cache=True)
        assert skills1 is not skills2  # Different objects

    def test_get_skill_by_name(self, tmp_path):
        self._create_skill_dir(
            tmp_path,
            "product-manager",
            "create-prd",
            "---\nname: create-prd\n---\nContent.",
        )
        loader = RoleSkillLoader(skills_dir=tmp_path)
        skill = loader.get_skill("product-manager", "create-prd")
        assert skill is not None
        assert skill.name == "create-prd"

    def test_get_skill_not_found(self, tmp_path):
        loader = RoleSkillLoader(skills_dir=tmp_path)
        skill = loader.get_skill("product-manager", "nonexistent")
        assert skill is None

    def test_list_available_skills(self, tmp_path):
        self._create_skill_dir(
            tmp_path,
            "product-manager",
            "create-prd",
            "---\nname: create-prd\n---\nContent.",
        )
        self._create_skill_dir(
            tmp_path,
            "architect",
            "adr",
            "---\nname: adr\n---\nADR content.",
        )
        loader = RoleSkillLoader(skills_dir=tmp_path)
        available = loader.list_available_skills()
        assert "product-manager" in available
        assert "architect" in available

    def test_list_available_skills_filtered(self, tmp_path):
        self._create_skill_dir(
            tmp_path,
            "product-manager",
            "create-prd",
            "---\nname: create-prd\n---\nContent.",
        )
        loader = RoleSkillLoader(skills_dir=tmp_path)
        available = loader.list_available_skills(role_id="product-manager")
        assert "product-manager" in available
        assert "architect" not in available

    def test_clear_cache(self, tmp_path):
        self._create_skill_dir(
            tmp_path,
            "product-manager",
            "create-prd",
            "---\nname: create-prd\n---\nContent.",
        )
        loader = RoleSkillLoader(skills_dir=tmp_path)
        loader.load_skills("product-manager")
        loader.clear_cache()
        # After clear, should reload from disk
        skills = loader.load_skills("product-manager")
        assert len(skills) == 1

    def test_skill_file_without_frontmatter(self, tmp_path):
        self._create_skill_dir(
            tmp_path,
            "product-manager",
            "simple-skill",
            "Just plain instructions without frontmatter.",
        )
        loader = RoleSkillLoader(skills_dir=tmp_path)
        skills = loader.load_skills("product-manager")
        assert len(skills) == 1
        assert skills[0].name == "simple-skill"  # Falls back to dir name
        assert "Just plain instructions" in skills[0].instructions

    def test_malformed_skill_file_skipped(self, tmp_path):
        """Files that can't be read should be skipped gracefully."""
        skill_dir = tmp_path / "product-manager" / "bad-skill"
        skill_dir.mkdir(parents=True)
        # Create a directory named SKILL.md instead of a file
        (skill_dir / "SKILL.md").mkdir()
        loader = RoleSkillLoader(skills_dir=tmp_path)
        skills = loader.load_skills("product-manager")
        assert skills == []


class TestGetSharedLoader:
    """Tests for singleton pattern."""

    def test_returns_same_instance(self):
        loader1 = get_shared_loader()
        loader2 = get_shared_loader()
        assert loader1 is loader2


class TestPromptAssemblerSkillInjection:
    """Integration tests for skill injection into PromptAssembler."""

    def test_skill_injection_in_structured_style(self, tmp_path):
        """Structured style should include skill injection."""
        from scripts.collaboration.prompt_assembler import PromptAssembler

        # Create a skill for testing
        skill_dir = tmp_path / "product-manager" / "test-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: test-skill\n---\n## Test Framework\n1. Step one\n2. Step two",
            encoding="utf-8",
        )

        assembler = PromptAssembler(role_id="product-manager", base_prompt="You are PM.")
        # Inject custom loader
        from scripts.collaboration.role_skill_loader import RoleSkillLoader

        assembler._skill_loader = RoleSkillLoader(skills_dir=tmp_path)

        result = assembler.assemble("Write a PRD for SSO feature")
        assert "Methodology Frameworks" in result.instruction

    def test_no_skill_injection_for_role_without_skills(self, tmp_path):
        """Roles without skills should not get injection."""
        from scripts.collaboration.prompt_assembler import PromptAssembler

        assembler = PromptAssembler(role_id="architect", base_prompt="You are architect.")
        from scripts.collaboration.role_skill_loader import RoleSkillLoader

        assembler._skill_loader = RoleSkillLoader(skills_dir=tmp_path)

        result = assembler.assemble("Design microservice architecture")
        assert "Methodology Frameworks" not in result.instruction
