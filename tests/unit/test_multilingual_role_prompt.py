#!/usr/bin/env python3
"""Unit tests for V4.4.2 P1-1 Multilingual Role Prompt.

Verifies that:
- All 7 roles in ROLE_REGISTRY have ``prompt_i18n`` and ``name_i18n`` dicts
  with ``en`` and ``ja`` keys.
- ``get_localized_prompt`` / ``get_localized_name`` return the correct
  translation for ``en`` / ``ja`` and fall back to the original Chinese
  ``prompt`` / ``name`` for ``zh`` and any unrecognized language.
- The module-level ``_call_counter_er`` increments on every
  ``get_localized_prompt`` call (anti-ghost verification).
- ``RoleDefinition`` constructed without i18n fields remains backward
  compatible (empty dicts, fallback to ``prompt``/``name``).
- ``ROLE_TEMPLATES`` exposes the new ``prompt_i18n`` / ``name_i18n`` keys
  so downstream consumers can access them.

Test plan reference: docs/prd/V4.4.2_PRD.md §3.3 (AC-1, AC-5, AC-6).
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.dispatch_models import ROLE_TEMPLATES
from scripts.collaboration.models_dispatch import (
    ROLE_REGISTRY,
    RoleDefinition,
)

pytestmark = pytest.mark.unit

_EXPECTED_ROLES = [
    "architect",
    "product-manager",
    "tester",
    "solo-coder",
    "ui-designer",
    "devops",
    "security",
]


# ── AC-1: 7 roles × 3 languages prompt 全部存在 ──────────────────────────


def test_role_has_en_ja_prompts() -> None:
    """AC-1: every role has prompt_i18n with exactly {"en", "ja"} keys."""
    for rid in _EXPECTED_ROLES:
        rdef = ROLE_REGISTRY[rid]
        assert len(rdef.prompt_i18n) == 2, (
            f"role {rid} prompt_i18n should have 2 entries, got {len(rdef.prompt_i18n)}"
        )
        assert set(rdef.prompt_i18n.keys()) == {"en", "ja"}, (
            f"role {rid} prompt_i18n keys should be {{'en', 'ja'}}, got {set(rdef.prompt_i18n.keys())}"
        )


def test_role_has_en_ja_names() -> None:
    """AC-1: every role has name_i18n with exactly {"en", "ja"} keys."""
    for rid in _EXPECTED_ROLES:
        rdef = ROLE_REGISTRY[rid]
        assert len(rdef.name_i18n) == 2, (
            f"role {rid} name_i18n should have 2 entries, got {len(rdef.name_i18n)}"
        )
        assert set(rdef.name_i18n.keys()) == {"en", "ja"}, (
            f"role {rid} name_i18n keys should be {{'en', 'ja'}}, got {set(rdef.name_i18n.keys())}"
        )


# ── get_localized_prompt fallback behavior ─────────────────────────────


def test_get_localized_prompt_zh_fallback() -> None:
    """AC-5: ``zh`` falls back to the original ``self.prompt``."""
    arch = ROLE_REGISTRY["architect"]
    assert arch.get_localized_prompt("zh") == arch.prompt


def test_get_localized_prompt_en() -> None:
    """AC-2/AC-3: ``en`` returns the English prompt."""
    arch = ROLE_REGISTRY["architect"]
    en_prompt = arch.get_localized_prompt("en")
    assert en_prompt == arch.prompt_i18n["en"]
    assert "System Architect" in en_prompt


def test_get_localized_prompt_ja() -> None:
    """AC-4: ``ja`` returns the Japanese prompt."""
    arch = ROLE_REGISTRY["architect"]
    ja_prompt = arch.get_localized_prompt("ja")
    assert ja_prompt == arch.prompt_i18n["ja"]
    assert "システムアーキテクト" in ja_prompt


def test_get_localized_prompt_unknown_lang_fallback() -> None:
    """AC-5: unknown lang (e.g. ``fr``) falls back to ``self.prompt``."""
    arch = ROLE_REGISTRY["architect"]
    assert arch.get_localized_prompt("fr") == arch.prompt


# ── get_localized_name behavior ────────────────────────────────────────


def test_get_localized_name_zh_fallback() -> None:
    """``zh`` falls back to the original ``self.name``."""
    arch = ROLE_REGISTRY["architect"]
    assert arch.get_localized_name("zh") == arch.name


def test_get_localized_name_en() -> None:
    """``en`` returns the English name."""
    arch = ROLE_REGISTRY["architect"]
    assert arch.get_localized_name("en") == "Architect"


def test_get_localized_name_ja() -> None:
    """``ja`` returns the Japanese name."""
    arch = ROLE_REGISTRY["architect"]
    assert arch.get_localized_name("ja") == "アーキテクト"


# ── AC-6: anti-ghost counter ───────────────────────────────────────────


def test_call_counter_increments() -> None:
    """AC-6: ``_call_counter_er`` increments after ``get_localized_prompt``."""
    import scripts.collaboration.models_dispatch as md

    before = md._call_counter_er
    ROLE_REGISTRY["tester"].get_localized_prompt("en")
    assert md._call_counter_er > before, (
        f"_call_counter_er did not increment: before={before}, after={md._call_counter_er}"
    )


# ── Backward compatibility ─────────────────────────────────────────────


def test_backward_compatible_empty_i18n() -> None:
    """AC-5: RoleDefinition with empty prompt_i18n still works."""
    bare = RoleDefinition(
        role_id="custom",
        name="自定义",
        aliases=[],
        prompt="你是自定义角色。",
        keywords=[],
        weight=1.0,
        description="custom role",
    )
    assert bare.prompt_i18n == {}
    assert bare.name_i18n == {}
    # All langs fall back to prompt/name.
    assert bare.get_localized_prompt("en") == bare.prompt
    assert bare.get_localized_prompt("zh") == bare.prompt
    assert bare.get_localized_name("ja") == bare.name
    assert bare.get_localized_name("zh") == bare.name


# ── ROLE_TEMPLATES propagation ─────────────────────────────────────────


def test_role_templates_include_i18n() -> None:
    """ROLE_TEMPLATES dict includes prompt_i18n and name_i18n keys."""
    for rid in _EXPECTED_ROLES:
        template = ROLE_TEMPLATES[rid]
        assert "prompt_i18n" in template, f"role {rid} missing prompt_i18n in ROLE_TEMPLATES"
        assert "name_i18n" in template, f"role {rid} missing name_i18n in ROLE_TEMPLATES"
        assert template["prompt_i18n"] == ROLE_REGISTRY[rid].prompt_i18n
        assert template["name_i18n"] == ROLE_REGISTRY[rid].name_i18n
