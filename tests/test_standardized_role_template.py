#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for StandardizedRoleTemplate (P1-1: RoleTemplateMarket Standardization).

Spec reference: SPEC_V35_Agent_Skills_Quality_Framework.md Section 7.1
"""

import pytest
from scripts.collaboration.standardized_role_template import (
    StandardizedRoleTemplate,
    create_example_template,
)


class TestStandardizedRoleTemplateFields:
    """Test all V2 required fields exist and work correctly."""

    def test_all_identity_fields_present(self):
        tpl = StandardizedRoleTemplate(
            name="Test Template",
            role_id="tester",
            author="Test Author",
            overview="Test overview",
            when_to_use="When testing",
            process_steps=["Step 1"],
            prompt_template="Test prompt",
        )
        assert tpl.name == "Test Template"
        assert tpl.role_id == "tester"
        assert tpl.author == "Test Author"
        assert tpl.version == "2.0.0"

    def test_context_fields_present(self):
        tpl = StandardizedRoleTemplate(
            name="Test",
            role_id="test",
            author="A",
            overview="What it does",
            when_to_use="Positive case",
            when_not_to_use="Negative case",
            process_steps=["Step 1"],
            prompt_template="Prompt",
        )
        assert tpl.overview == "What it does"
        assert tpl.when_to_use == "Positive case"
        assert tpl.when_not_to_use == "Negative case"

    def test_process_steps_field(self):
        tpl = StandardizedRoleTemplate(
            name="Test",
            role_id="test",
            author="A",
            overview="O",
            when_to_use="W",
            process_steps=["Analyze", "Design", "Implement", "Verify"],
            prompt_template="P",
        )
        assert len(tpl.process_steps) == 4
        assert "Verify" in tpl.process_steps

    def test_rationalizations_field(self):
        rationalizations = [
            {"excuse": "Too simple", "reality": "Simple gets complex"},
            {"excuse": "Later", "reality": "You won't"},
        ]
        tpl = StandardizedRoleTemplate(
            name="Test",
            role_id="test",
            author="A",
            overview="O",
            when_to_use="W",
            process_steps=["S"],
            prompt_template="P",
            rationalizations=rationalizations,
        )
        assert len(tpl.rationalizations) == 2
        assert tpl.rationalizations[0]["excuse"] == "Too simple"

    def test_red_flags_field(self):
        red_flags = [
            {"flag": "no_test", "severity": "critical", "description": "No test for new code"},
            {"flag": "hardcoded", "severity": "warning", "description": "Hardcoded value"},
        ]
        tpl = StandardizedRoleTemplate(
            name="Test",
            role_id="test",
            author="A",
            overview="O",
            when_to_use="W",
            process_steps=["S"],
            prompt_template="P",
            red_flags=red_flags,
        )
        assert len(tpl.red_flags) == 2
        assert tpl.red_flags[0]["severity"] == "critical"

    def test_verification_requirements_field(self):
        vr = ["Must have tests", "Build must pass", "Code reviewed"]
        tpl = StandardizedRoleTemplate(
            name="Test",
            role_id="test",
            author="A",
            overview="O",
            when_to_use="W",
            process_steps=["S"],
            prompt_template="P",
            verification_requirements=vr,
        )
        assert len(tpl.verification_requirements) == 3
        assert "Build must pass" in tpl.verification_requirements

    def test_auto_generated_metadata(self):
        tpl = StandardizedRoleTemplate(
            name="Auto ID Test",
            role_id="auto",
            author="System",
            overview="O",
            when_to_use="W",
            process_steps=["S"],
            prompt_template="P",
        )
        assert tpl.template_id.startswith("std-tpl-")
        assert len(tpl.template_id) > 10
        assert tpl.created_at is not None
        assert tpl.updated_at is not None


class TestValidation:
    """Test validation logic."""

    def test_valid_template_passes(self):
        tpl = StandardizedRoleTemplate(
            name="Valid Template",
            role_id="valid-role",
            author="Author Name",
            overview="This template does X",
            when_to_use="Use when Y happens",
            process_steps=["Do step 1"],
            prompt_template="You are a {role}...",
        )
        errors = tpl.validate()
        assert len(errors) == 0
        assert tpl.is_valid()

    def test_missing_name_fails(self):
        tpl = StandardizedRoleTemplate(
            name="",
            role_id="test",
            author="A",
            overview="O",
            when_to_use="W",
            process_steps=["S"],
            prompt_template="P",
        )
        errors = tpl.validate()
        assert any("name" in e.lower() for e in errors)

    def test_missing_role_id_fails(self):
        tpl = StandardizedRoleTemplate(
            name="Test",
            role_id="",
            author="A",
            overview="O",
            when_to_use="W",
            process_steps=["S"],
            prompt_template="P",
        )
        errors = tpl.validate()
        assert any("role_id" in e.lower() for e in errors)

    def test_missing_author_fails(self):
        tpl = StandardizedRoleTemplate(
            name="Test",
            role_id="test",
            author="",
            overview="O",
            when_to_use="W",
            process_steps=["S"],
            prompt_template="P",
        )
        errors = tpl.validate()
        assert any("author" in e.lower() for e in errors)

    def test_missing_overview_fails(self):
        tpl = StandardizedRoleTemplate(
            name="Test",
            role_id="test",
            author="A",
            overview="",
            when_to_use="W",
            process_steps=["S"],
            prompt_template="P",
        )
        errors = tpl.validate()
        assert any("overview" in e.lower() for e in errors)

    def test_empty_process_steps_fails(self):
        tpl = StandardizedRoleTemplate(
            name="Test",
            role_id="test",
            author="A",
            overview="O",
            when_to_use="W",
            process_steps=[],
            prompt_template="P",
        )
        errors = tpl.validate()
        assert any("process_steps" in e.lower() for e in errors)

    def test_missing_prompt_template_fails(self):
        tpl = StandardizedRoleTemplate(
            name="Test",
            role_id="test",
            author="A",
            overview="O",
            when_to_use="W",
            process_steps=["S"],
            prompt_template="",
        )
        errors = tpl.validate()
        assert any("prompt_template" in e.lower() for e in errors)


class TestLegacyConversion:
    """Test legacy format conversion to V2."""

    def test_from_legacy_basic_fields(self):
        legacy = {
            "name": "Legacy Auditor",
            "description": "Security auditor",
            "role_id": "security",
            "role_prompt": "You are a security auditor...",
            "author": "Legacy Author",
            "category": "security",
        }
        v2 = StandardizedRoleTemplate.from_legacy(legacy)
        assert v2.name == "Legacy Auditor"
        assert v2.role_id == "security"
        assert v2.prompt_template == "You are a security auditor..."

    def test_from_legacy_generates_v2_fields(self):
        legacy = {
            "name": "Old Template",
            "description": "Does something",
            "role_id": "coder",
            "role_prompt": "Code this...",
            "author": "Someone",
            "category": "development",
        }
        v2 = StandardizedRoleTemplate.from_legacy(legacy)
        assert v2.overview != ""  # Should fallback to description
        assert v2.when_to_use != ""
        assert v2.when_not_to_use != ""
        assert len(v2.process_steps) >= 1
        assert len(v2.verification_requirements) >= 1

    def test_from_legacy_preserves_triggers_and_tags(self):
        legacy = {
            "name": "Tagged",
            "description": "D",
            "role_id": "r",
            "role_prompt": "P",
            "author": "A",
            "tags": ["tag1", "tag2"],
            "triggers": ["trigger1", "trigger2"],
        }
        v2 = StandardizedRoleTemplate.from_legacy(legacy)
        assert "tag1" in v2.tags
        assert "trigger1" in v2.triggers


class TestSerialization:
    """Test to_dict / from_dict round-trip."""

    def test_to_dict_contains_all_fields(self):
        tpl = StandardizedRoleTemplate(
            name="Serialize Test",
            role_id="serializer",
            author="Tester",
            overview="O",
            when_to_use="W",
            when_not_to_use="NW",
            process_steps=["S1", "S2"],
            rationalizations=[{"excuse": "E", "reality": "R"}],
            red_flags=[{"flag": "F", "severity": "warning", "description": "D"}],
            verification_requirements=["V1", "V2"],
            prompt_template="PT",
        )
        d = tpl.to_dict()
        assert "name" in d
        assert "overview" in d
        assert "when_to_use" in d
        assert "process_steps" in d
        assert "rationalizations" in d
        assert "red_flags" in d
        assert "verification_requirements" in d

    def test_from_dict_round_trip(self):
        original = StandardizedRoleTemplate(
            name="Round Trip",
            role_id="rt",
            author="Author",
            overview="Overview text",
            when_to_use="Use this",
            when_not_to_use="Don't use that",
            process_steps=["Step A", "Step B"],
            prompt_template="Prompt here",
        )
        d = original.to_dict()
        restored = StandardizedRoleTemplate.from_dict(d)
        assert restored.name == original.name
        assert restored.role_id == original.role_id
        assert restored.overview == original.overview
        assert restored.when_to_use == original.when_to_use
        assert len(restored.process_steps) == len(original.process_steps)


class TestMarkdownGeneration:
    """Test SKILL.md-style markdown output."""

    def test_markdown_contains_all_sections(self):
        tpl = create_example_template()
        md = tpl.to_markdown()

        assert "# OWASP Security Auditor" in md
        assert "## Overview" in md
        assert "## When to Use" in md
        assert "## Process Steps" in md
        assert "## Common Rationalizations" in md
        assert "## Red Flags" in md
        assert "## Verification Requirements" in md

    def test_markdown_contains_rationalization_table(self):
        tpl = create_example_template()
        md = tpl.to_markdown()

        assert "| Excuse | Reality |" in md
        assert "internal tool" in md.lower()

    def test_markdown_contains_red_flags(self):
        tpl = create_example_template()
        md = tpl.to_markdown()

        assert "CRITICAL" in md or "WARNING" in md
        assert "User input not validated" in md or "API keys" in md or "Dynamic SQL" in md

    def test_markdown_contains_verification_checklist(self):
        tpl = create_example_template()
        md = tpl.to_markdown()

        assert "- [ ]" in md  # Checklist format
        assert "OWASP" in md

    def test_empty_optional_sections_omitted(self):
        tpl = StandardizedRoleTemplate(
            name="Minimal",
            role_id="min",
            author="A",
            overview="O",
            when_to_use="W",
            process_steps=["S"],
            prompt_template="P",
        )
        md = tpl.to_markdown()

        # Should not have empty sections
        assert "## Common Rationalizations" not in md
        assert "## Red Flags" not in md


class TestExampleTemplate:
    """Test the example template used for documentation."""

    def test_example_is_valid(self):
        tpl = create_example_template()
        assert tpl.is_valid()

    def test_example_has_all_v2_fields(self):
        tpl = create_example_template()
        assert tpl.name == "OWASP Security Auditor"
        assert tpl.role_id == "security"
        assert len(tpl.process_steps) == 5
        assert len(tpl.rationalizations) == 3
        assert len(tpl.red_flags) == 4
        assert len(tpl.verification_requirements) == 4
        assert len(tpl.prompt_template) > 50

    def test_example_markdown_complete(self):
        tpl = create_example_template()
        md = tpl.to_markdown()

        sections = [
            "# OWASP Security Auditor",
            "## Overview",
            "## When to Use",
            "## Process Steps",
            "## Common Rationalizations",
            "## Red Flags",
            "## Verification Requirements",
        ]
        for section in sections:
            assert section in md, f"Missing section: {section}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
