#!/usr/bin/env python3
"""E2E tests for V4.4.2 P1-1 Multilingual Role Prompt.

Verifies the full user journey: user dispatches a task in a specific
language → dispatcher resolves the language → worker receives a
localized role prompt. Tests use the Mock backend (no real LLM calls).

Per Iron Rule 4 (side-effect verification), each test asserts the
prompt **actually passed to the worker** (via ``worker.role_prompt``),
not just the return value of ``get_localized_prompt``.

Per Iron Rule 5 (user journey priority), the tests start from
``MultiAgentDispatcher(...).dispatch(...)`` — the same entry point real
users call — and inspect the resulting worker state.

Test plan reference: docs/prd/V4.4.2_PRD.md §3.3 (AC-2..AC-6) and §7
(E2E user journey).
"""
from __future__ import annotations

import scripts.collaboration.models_dispatch as _md
from scripts.collaboration.dispatcher import MultiAgentDispatcher


def _reset_call_counter() -> None:
    """Reset the module-level counter so each test starts from a known state."""
    _md._call_counter = 0


def _first_worker_prompt(disp: MultiAgentDispatcher) -> str:
    """Return the role_prompt of the first worker spawned by the dispatcher.

    The dispatcher's coordinator keeps the last batch of workers in
    ``coordinator.workers``; reading ``role_prompt`` is the side-effect
    proof that the localized prompt reached the worker (Iron Rule 4).
    """
    workers = list(disp.coordinator.workers.values())
    assert workers, "dispatcher spawned no workers"
    return workers[0].role_prompt


def test_e2e_chinese_task_uses_chinese_prompt() -> None:
    """AC-2: dispatch with lang='zh' → worker prompt contains '架构师'."""
    _reset_call_counter()
    disp = MultiAgentDispatcher(lang="zh")
    try:
        # Pass roles=["architect"] explicitly so the test is deterministic
        # and focused on i18n behavior (not role-matching keywords).
        disp.dispatch("设计一个支付网关的架构", roles=["architect"])
        prompt = _first_worker_prompt(disp)
        assert "架构师" in prompt, f"expected Chinese prompt, got: {prompt[:80]!r}"
    finally:
        disp.shutdown()


def test_e2e_english_task_uses_english_prompt() -> None:
    """AC-3: dispatch with lang='en' → worker prompt contains 'Architect'."""
    _reset_call_counter()
    disp = MultiAgentDispatcher(lang="en")
    try:
        disp.dispatch("Design a payment gateway architecture", roles=["architect"])
        prompt = _first_worker_prompt(disp)
        assert "Architect" in prompt, f"expected English prompt, got: {prompt[:80]!r}"
        # Negative check: the Chinese prompt must NOT leak through.
        assert "你是系统架构师" not in prompt, "Chinese prompt leaked into EN dispatch"
    finally:
        disp.shutdown()


def test_e2e_japanese_task_uses_japanese_prompt() -> None:
    """AC-4: dispatch with lang='ja' → worker prompt contains 'アーキテクト'."""
    _reset_call_counter()
    disp = MultiAgentDispatcher(lang="ja")
    try:
        disp.dispatch("決済ゲートウェイのアーキテクチャを設計する", roles=["architect"])
        prompt = _first_worker_prompt(disp)
        assert "アーキテクト" in prompt, f"expected Japanese prompt, got: {prompt[:80]!r}"
        # Negative check: the Chinese prompt must NOT leak through.
        assert "你是系统架构师" not in prompt, "Chinese prompt leaked into JA dispatch"
    finally:
        disp.shutdown()


def test_e2e_anti_ghost_counter_incremented() -> None:
    """AC-6: after dispatch, ``models_dispatch._call_counter > 0``."""
    _reset_call_counter()
    assert _md._call_counter == 0, "counter not reset"
    disp = MultiAgentDispatcher(lang="en")
    try:
        disp.dispatch("Design a payment gateway architecture", roles=["architect"])
        assert _md._call_counter > 0, (
            "get_localized_prompt was never called during dispatch — i18n path is dead code"
        )
    finally:
        disp.shutdown()


def test_e2e_backward_compatible_default_lang() -> None:
    """AC-5: default dispatcher (lang='auto') resolves to zh prompt."""
    _reset_call_counter()
    # Default constructor uses lang="auto" which _resolve_language maps to "zh".
    disp = MultiAgentDispatcher()
    try:
        disp.dispatch("设计一个支付网关的架构", roles=["architect"])
        prompt = _first_worker_prompt(disp)
        # Default lang is "zh" → prompt must be the original Chinese prompt.
        assert "架构师" in prompt, (
            f"expected Chinese prompt for default lang, got: {prompt[:80]!r}"
        )
    finally:
        disp.shutdown()
