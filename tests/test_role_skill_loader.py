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


# ======================================================================
# V4.1.0 P1-5 to-prd — create-prd SKILL.md Seam-First Design
# ======================================================================


class TestCreatePrdSeamFirstDesign:
    """P1-5: create-prd SKILL.md must include seam-first design content."""

    def _get_skill_path(self) -> Path:
        """Return the path to the real create-prd SKILL.md."""
        from scripts.collaboration.role_skill_loader import _SKILLS_BASE_DIR

        return _SKILLS_BASE_DIR / "product-manager" / "create-prd" / "SKILL.md"

    def test_skill_md_contains_seam_first_design_section(self):
        """Verify: SKILL.md has a 'Seam-First Design' section."""
        content = self._get_skill_path().read_text(encoding="utf-8")
        assert "## Seam-First Design" in content

    def test_skill_md_contains_seams_identification_template(self):
        """Verify: SKILL.md has a 'Seams Identification' subsection template."""
        content = self._get_skill_path().read_text(encoding="utf-8")
        assert "Seams Identification" in content
        # The template should reference the seam-table columns
        assert "Current Choice" in content
        assert "Alternatives Considered" in content

    def test_skill_md_loadable_by_role_skill_loader(self):
        """Verify: create-prd SKILL.md loads cleanly via RoleSkillLoader."""
        loader = RoleSkillLoader()
        skill = loader.get_skill("product-manager", "create-prd")
        assert skill is not None
        assert skill.name == "create-prd"

    def test_to_prompt_text_contains_seam_first_content(self):
        """Verify: loaded skill's to_prompt_text() includes seam-first content."""
        loader = RoleSkillLoader()
        skill = loader.get_skill("product-manager", "create-prd")
        assert skill is not None
        # Use a generous max_length so the seam-first section (at end of file)
        # is not truncated away by the default 2000-char cap.
        text = skill.to_prompt_text(max_length=10000)
        assert "Seam-First Design" in text
        assert "Seams Identification" in text

    def test_existing_create_prd_skill_still_loads(self):
        """Verify: existing create-prd skill still loads (regression check)."""
        loader = RoleSkillLoader()
        skills = loader.load_skills("product-manager", no_cache=True)
        names = [s.name for s in skills]
        assert "create-prd" in names


# ======================================================================
# V4.1.0 P1-UI-2 — ui-designer/uiux-audit SKILL.md + 7 Design Pillars
# ======================================================================


class TestUIDesignerUiuxAuditSkill:
    """P1-UI-2: ui-designer/uiux-audit SKILL.md must encode 7 Design Pillars."""

    def _get_skill_path(self) -> Path:
        """Return the path to the real uiux-audit SKILL.md."""
        from scripts.collaboration.role_skill_loader import _SKILLS_BASE_DIR

        return _SKILLS_BASE_DIR / "ui-designer" / "uiux-audit" / "SKILL.md"

    def test_glossary_contains_design_pillars(self):
        """Verify: GLOSSARY.md includes the 'Design Pillars' entry."""
        loader = RoleSkillLoader()
        content = loader.load_glossary()
        assert "Design Pillars" in content

    def test_glossary_contains_all_seven_pillars(self):
        """Verify: GLOSSARY.md mentions all 7 pillar names."""
        loader = RoleSkillLoader()
        content = loader.load_glossary()
        # 7 pillars defined in scripts/qa/deterministic_rule_engine.py SEVEN_PILLARS
        for pillar in (
            "Typography",
            "Color",
            "Spatial",
            "Responsiveness",
            "Interactions",
            "Motion",
            "UX writing",
        ):
            assert pillar in content, f"GLOSSARY.md missing pillar: {pillar}"

    def test_ui_designer_skill_md_loadable(self):
        """Verify: ui-designer/uiux-audit SKILL.md loads cleanly via RoleSkillLoader."""
        loader = RoleSkillLoader()
        skill = loader.get_skill("ui-designer", "uiux-audit")
        assert skill is not None
        assert skill.name == "uiux-audit"
        assert skill.role_id == "ui-designer"

    def test_to_prompt_text_contains_pillar_content(self):
        """Verify: loaded skill's to_prompt_text() includes pillar content."""
        loader = RoleSkillLoader()
        skill = loader.get_skill("ui-designer", "uiux-audit")
        assert skill is not None
        text = skill.to_prompt_text(max_length=10000)
        # Each pillar should be mentioned in the prompt text
        assert "Typography" in text
        assert "Responsiveness" in text
        assert "UX Writing" in text or "UX writing" in text
        # Should reference the 7 pillars framework
        assert "7 Design Pillars" in text or "Design Pillars" in text

    def test_existing_skills_still_loadable(self):
        """Verify: existing skills (architect, product-manager) still load (regression)."""
        loader = RoleSkillLoader()
        # architect
        arch_skills = loader.load_skills("architect", no_cache=True)
        assert len(arch_skills) >= 1
        # product-manager
        pm_skills = loader.load_skills("product-manager", no_cache=True)
        assert len(pm_skills) >= 1

    def test_skill_md_contains_seven_pillar_sections(self):
        """Verify: SKILL.md has a section per pillar."""
        content = self._get_skill_path().read_text(encoding="utf-8")
        # Each pillar should have a dedicated heading
        for pillar in (
            "Typography",
            "Color",
            "Spatial",
            "Responsiveness",
            "Interactions",
            "Motion",
            "UX Writing",
        ):
            assert pillar in content, f"SKILL.md missing pillar section: {pillar}"

    def test_skill_md_has_integration_with_deterministic_rule_engine(self):
        """Verify: SKILL.md documents integration with DeterministicRuleEngine."""
        content = self._get_skill_path().read_text(encoding="utf-8")
        assert "DeterministicRuleEngine" in content
        assert "TasteDials" in content or "Taste Dials" in content


class TestTesterTautologicalTestDetectionSkill:
    """Tests for tester/tautological-test-detection SKILL.md (V4.1.0 P0 atomic skill)."""

    def _get_skill_path(self) -> Path:
        return (
            Path(__file__).resolve().parent.parent
            / "scripts"
            / "collaboration"
            / "role_skills"
            / "tester"
            / "tautological-test-detection"
            / "SKILL.md"
        )

    def test_skill_md_exists(self):
        assert self._get_skill_path().exists()

    def test_skill_md_loadable_by_role_skill_loader(self):
        loader = RoleSkillLoader()
        skills = loader.load_skills("tester", no_cache=True)
        names = [s.name for s in skills]
        assert "tautological-test-detection" in names

    def test_skill_md_contains_detection_patterns(self):
        content = self._get_skill_path().read_text(encoding="utf-8")
        assert "Detection Patterns" in content or "detection pattern" in content.lower()

    def test_skill_md_contains_tautological_vocabulary(self):
        content = self._get_skill_path().read_text(encoding="utf-8")
        for term in ("Tautological test", "Seam", "Red-green"):
            assert term in content, f"Missing vocabulary term: {term}"

    def test_skill_md_contains_failure_modes(self):
        content = self._get_skill_path().read_text(encoding="utf-8")
        assert "Failure Modes" in content

    def test_skill_md_contains_verification_requirements(self):
        content = self._get_skill_path().read_text(encoding="utf-8")
        assert "Verification Requirements" in content

    def test_to_prompt_text_contains_content(self):
        loader = RoleSkillLoader()
        skills = loader.load_skills("tester", no_cache=True)
        skill = next(s for s in skills if s.name == "tautological-test-detection")
        text = skill.to_prompt_text()
        assert len(text) > 100
        assert "tautological" in text.lower()


class TestSecurityGitGuardrailsSkill:
    """Tests for security/git-guardrails SKILL.md (V4.1.0 P0 atomic skill)."""

    def _get_skill_path(self) -> Path:
        return (
            Path(__file__).resolve().parent.parent
            / "scripts"
            / "collaboration"
            / "role_skills"
            / "security"
            / "git-guardrails"
            / "SKILL.md"
        )

    def test_skill_md_exists(self):
        assert self._get_skill_path().exists()

    def test_skill_md_loadable_by_role_skill_loader(self):
        loader = RoleSkillLoader()
        skills = loader.load_skills("security", no_cache=True)
        names = [s.name for s in skills]
        assert "git-guardrails" in names

    def test_skill_md_contains_three_tier_classification(self):
        content = self._get_skill_path().read_text(encoding="utf-8")
        for tier in ("FORBIDDEN", "NEEDS_REVIEW", "ALWAYS_SAFE"):
            assert tier in content, f"Missing classification tier: {tier}"

    def test_skill_md_contains_protected_branches(self):
        content = self._get_skill_path().read_text(encoding="utf-8")
        assert "main" in content
        assert "master" in content
        assert "Protected branch" in content or "protected" in content.lower()

    def test_skill_md_contains_failure_modes(self):
        content = self._get_skill_path().read_text(encoding="utf-8")
        assert "Failure Modes" in content

    def test_skill_md_contains_verification_requirements(self):
        content = self._get_skill_path().read_text(encoding="utf-8")
        assert "Verification Requirements" in content

    def test_to_prompt_text_contains_content(self):
        loader = RoleSkillLoader()
        skills = loader.load_skills("security", no_cache=True)
        skill = next(s for s in skills if s.name == "git-guardrails")
        text = skill.to_prompt_text()
        assert len(text) > 100
        assert "FORBIDDEN" in text


class TestPMGrillingInterviewSkill:
    """Tests for product-manager/grilling-interview SKILL.md (V4.1.0 P0 atomic skill)."""

    def _get_skill_path(self) -> Path:
        return (
            Path(__file__).resolve().parent.parent
            / "scripts"
            / "collaboration"
            / "role_skills"
            / "product-manager"
            / "grilling-interview"
            / "SKILL.md"
        )

    def test_skill_md_exists(self):
        assert self._get_skill_path().exists()

    def test_skill_md_loadable_by_role_skill_loader(self):
        loader = RoleSkillLoader()
        skills = loader.load_skills("product-manager", no_cache=True)
        names = [s.name for s in skills]
        assert "grilling-interview" in names

    def test_skill_md_contains_one_question_at_a_time(self):
        content = self._get_skill_path().read_text(encoding="utf-8")
        assert "One-question-at-a-time" in content or "one question at a time" in content.lower()

    def test_skill_md_contains_glossary_candidates(self):
        content = self._get_skill_path().read_text(encoding="utf-8")
        assert "GLOSSARY" in content or "glossary" in content.lower()

    def test_skill_md_contains_stateless_mode(self):
        content = self._get_skill_path().read_text(encoding="utf-8")
        assert "stateless" in content.lower()

    def test_skill_md_contains_failure_modes(self):
        content = self._get_skill_path().read_text(encoding="utf-8")
        assert "Failure Modes" in content

    def test_skill_md_contains_verification_requirements(self):
        content = self._get_skill_path().read_text(encoding="utf-8")
        assert "Verification Requirements" in content

    def test_to_prompt_text_contains_content(self):
        loader = RoleSkillLoader()
        skills = loader.load_skills("product-manager", no_cache=True)
        skill = next(s for s in skills if s.name == "grilling-interview")
        text = skill.to_prompt_text()
        assert len(text) > 100
        assert "grilling" in text.lower()

    def test_existing_pm_skills_still_loadable(self):
        """Ensure adding grilling-interview didn't break existing PM skills."""
        loader = RoleSkillLoader()
        skills = loader.load_skills("product-manager", no_cache=True)
        names = [s.name for s in skills]
        assert "create-prd" in names
        assert "assumption-mapping" in names
        assert "grilling-interview" in names
