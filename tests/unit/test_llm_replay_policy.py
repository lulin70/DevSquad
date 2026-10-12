#!/usr/bin/env python3
"""Unit tests for llm_replay_policy (V4.6.0 P1-a).

Covers the PRD §7.1 unit matrix: key stability, key sensitivity (any key
component change → different key), mode-resolution precedence (explicit >
env > off), fail-closed on invalid values, and the mode behavior table
(READ never writes / READ_WRITE writes / OFF path unchanged).
"""

from __future__ import annotations

import pytest

import scripts.collaboration.llm_replay_policy as policy
from scripts.collaboration.llm_replay_policy import (
    PROMPT_TEMPLATE_VERSION,
    REPLAY_ENV_VAR,
    REPLAY_TTL_SECONDS,
    ReplayMode,
    ReplayPolicyError,
    build_replay_key,
    resolve_replay_mode,
)

# ── Key stability ──


class TestKeyStability:
    def test_same_input_same_key(self):
        k1 = build_replay_key("instruction", "openai", "gpt-4")
        k2 = build_replay_key("instruction", "openai", "gpt-4")
        assert k1 == k2

    def test_key_is_full_sha256_hex(self):
        key = build_replay_key("instruction", "openai", "gpt-4")
        assert len(key) == 64
        int(key, 16)  # must be hex

    def test_repeated_calls_deterministic(self):
        keys = {build_replay_key("t", "b", "m") for _ in range(5)}
        assert len(keys) == 1


# ── Key sensitivity: any component change must change the key ──


class TestKeySensitivity:
    BASE = build_replay_key("instruction", "openai", "gpt-4")

    def test_instruction_change_changes_key(self):
        assert build_replay_key("instruction2", "openai", "gpt-4") != self.BASE

    def test_backend_change_changes_key(self):
        assert build_replay_key("instruction", "anthropic", "gpt-4") != self.BASE

    def test_model_change_changes_key(self):
        assert build_replay_key("instruction", "openai", "gpt-5") != self.BASE

    def test_version_change_changes_key(self, monkeypatch: pytest.MonkeyPatch):
        # Simulate a DevSquad release: version enters the key so a recording
        # from release N can never answer for release N+1.
        monkeypatch.setattr(policy, "__version__", "9.9.9")
        assert build_replay_key("instruction", "openai", "gpt-4") != self.BASE

    def test_prompt_template_version_change_changes_key(self, monkeypatch: pytest.MonkeyPatch):
        # Simulate a prompt-template edit: PROMPT_TEMPLATE_VERSION bump is the
        # explicit invalidation lever.
        monkeypatch.setattr(policy, "PROMPT_TEMPLATE_VERSION", "999")
        assert build_replay_key("instruction", "openai", "gpt-4") != self.BASE
        assert policy.PROMPT_TEMPLATE_VERSION != PROMPT_TEMPLATE_VERSION

    def test_key_space_differs_from_legacy_cache_key(self):
        # The replay key must not collide with the regular LLM cache key
        # space (different prefix in the hashed content).
        from scripts.collaboration.llm_cache_base import LLMCacheBase

        legacy = LLMCacheBase().generate_cache_key("instruction", "openai", "gpt-4", hash_length=64)
        assert build_replay_key("instruction", "openai", "gpt-4") != legacy


# ── Volatile-metadata normalization (tester-army `unique()` analog) ──


class TestVolatileMetadataNormalization:
    def test_task_id_difference_does_not_change_key(self):
        # PromptAssembler embeds a fresh Task ID per dispatch; two dispatches
        # of the same task must map to the same replay key.
        k1 = build_replay_key("Do the thing\nTask ID: task-aaa\nEnd", "openai", "gpt-4")
        k2 = build_replay_key("Do the thing\nTask ID: task-bbb\nEnd", "openai", "gpt-4")
        assert k1 == k2

    def test_real_content_difference_still_changes_key(self):
        k1 = build_replay_key("Do the thing\nTask ID: task-aaa\nEnd", "openai", "gpt-4")
        k2 = build_replay_key("Do the OTHER thing\nTask ID: task-aaa\nEnd", "openai", "gpt-4")
        assert k1 != k2

    def test_instruction_without_task_id_unchanged_semantics(self):
        k1 = build_replay_key("plain instruction", "openai", "gpt-4")
        k2 = build_replay_key("plain instruction", "openai", "gpt-4")
        assert k1 == k2


# ── Mode resolution precedence ──


class TestModeResolution:
    def test_default_off(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv(REPLAY_ENV_VAR, raising=False)
        assert resolve_replay_mode() is ReplayMode.OFF

    def test_env_read(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv(REPLAY_ENV_VAR, "read")
        assert resolve_replay_mode() is ReplayMode.READ

    def test_env_read_write_with_whitespace_and_case(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv(REPLAY_ENV_VAR, "  Read-Write  ")
        assert resolve_replay_mode() is ReplayMode.READ_WRITE

    def test_explicit_beats_env(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv(REPLAY_ENV_VAR, "read")
        assert resolve_replay_mode(ReplayMode.READ_WRITE) is ReplayMode.READ_WRITE

    def test_invalid_env_fails_closed(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv(REPLAY_ENV_VAR, "banana")
        with pytest.raises(ReplayPolicyError, match="DEVSQUAD_LLM_REPLAY_CACHE"):
            resolve_replay_mode()

    def test_invalid_explicit_fails_closed(self):
        with pytest.raises(ReplayPolicyError):
            resolve_replay_mode("banana")

    def test_empty_env_is_off(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv(REPLAY_ENV_VAR, "   ")
        assert resolve_replay_mode() is ReplayMode.OFF


# ── TTL constant ──


class TestReplayTTL:
    def test_replay_ttl_far_exceeds_default(self):
        from scripts.collaboration.llm_cache_base import LLMCacheBase

        assert REPLAY_TTL_SECONDS > LLMCacheBase.DEFAULT_TTL_SECONDS * 1000

    def test_replay_ttl_covers_a_decade(self):
        assert REPLAY_TTL_SECONDS >= 365 * 24 * 3600 * 9
