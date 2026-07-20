"""Wave 4 UI/UX Enhancement tests.

Tests for:
- W4-T2: Keyboard shortcuts (KEYBOARD_SHORTCUTS, render_keyboard_shortcuts)

Note: W4-T1 (responsive) and W4-T3 (theme switcher) were deferred to V4.3
per 7-Role consensus (low ROI for desktop tool / over-engineering).
"""

from __future__ import annotations

from unittest.mock import patch

from scripts.dashboard.components import (
    KEYBOARD_SHORTCUTS,
)

# ── W4-T2: Keyboard shortcuts ──


class TestKeyboardShortcuts:
    """Verify: KEYBOARD_SHORTCUTS defines 9 shortcuts with required fields."""

    def test_keyboard_shortcuts_has_9_entries(self):
        """Should define 7 page nav + 1 refresh + 1 help = 9 shortcuts."""
        assert len(KEYBOARD_SHORTCUTS) == 9

    def test_shortcut_keys_are_unique(self):
        """All shortcut keys should be unique (dict guarantee)."""
        # Dict keys are inherently unique; this is a sanity check
        keys = list(KEYBOARD_SHORTCUTS.keys())
        assert len(keys) == len(set(keys))

    def test_each_shortcut_has_action_and_label(self):
        """Each shortcut must have 'action' and 'label' fields."""
        for key, meta in KEYBOARD_SHORTCUTS.items():
            assert "action" in meta, f"Missing action for key: {key}"
            assert "label" in meta, f"Missing label for key: {key}"
            assert isinstance(meta["action"], str) and meta["action"], f"Empty action for {key}"
            assert isinstance(meta["label"], str) and meta["label"], f"Empty label for {key}"

    def test_digit_keys_1_to_7_map_to_pages(self):
        """Keys 1-7 should map to page:<Name> actions."""
        expected_pages = {
            "1": "Overview",
            "2": "Phases",
            "3": "Mapping",
            "4": "Gates",
            "5": "Performance",
            "6": "Task Dispatch",
            "7": "DAG",
        }
        for key, page_name in expected_pages.items():
            assert key in KEYBOARD_SHORTCUTS, f"Missing key: {key}"
            assert KEYBOARD_SHORTCUTS[key]["action"] == f"page:{page_name}", (
                f"Key {key} action mismatch: {KEYBOARD_SHORTCUTS[key]['action']}"
            )

    def test_r_key_maps_to_refresh(self):
        """Key 'r' should map to 'refresh' action."""
        assert "r" in KEYBOARD_SHORTCUTS
        assert KEYBOARD_SHORTCUTS["r"]["action"] == "refresh"

    def test_question_mark_maps_to_help(self):
        """Key '?' should map to 'show_help' action."""
        assert "?" in KEYBOARD_SHORTCUTS
        assert KEYBOARD_SHORTCUTS["?"]["action"] == "show_help"

    def test_no_conflict_with_command_palette_cmd_k(self):
        """Keyboard shortcuts should NOT include Cmd+K (owned by command palette)."""
        # 'k' alone is OK; what we forbid is hijacking Cmd+K
        # This test ensures we don't accidentally add a 'k' shortcut
        # that would fire when user presses just 'k' (without modifier)
        assert "k" not in KEYBOARD_SHORTCUTS, (
            "Plain 'k' shortcut would conflict with Cmd+K command palette"
        )

    def test_actions_are_unique(self):
        """All shortcut actions should be unique (no two keys → same action)."""
        actions = [meta["action"] for meta in KEYBOARD_SHORTCUTS.values()]
        assert len(actions) == len(set(actions)), "Duplicate actions found"

    def test_all_7_dashboard_pages_covered(self):
        """All 7 dashboard pages should have a 1-7 shortcut."""
        page_actions = {
            meta["action"]
            for meta in KEYBOARD_SHORTCUTS.values()
            if meta["action"].startswith("page:")
        }
        expected = {
            "page:Overview",
            "page:Phases",
            "page:Mapping",
            "page:Gates",
            "page:Performance",
            "page:Task Dispatch",
            "page:DAG",
        }
        assert page_actions == expected


class TestRenderKeyboardShortcuts:
    """Verify: render_keyboard_shortcuts injects HTML/CSS/JS without errors."""

    def test_render_runs_without_error(self):
        """render_keyboard_shortcuts should execute without raising."""
        with patch("scripts.dashboard.components.st") as mock_st:
            from scripts.dashboard.components import render_keyboard_shortcuts

            render_keyboard_shortcuts()
            assert mock_st.markdown.called

    def test_html_contains_help_overlay(self):
        """HTML should contain the kbd-help-overlay div."""
        with patch("scripts.dashboard.components.st") as mock_st:
            from scripts.dashboard.components import render_keyboard_shortcuts

            render_keyboard_shortcuts()
            args, kwargs = mock_st.markdown.call_args
            html = args[0] if args else ""
            assert 'id="kbd-help-overlay"' in html
            assert "kbd-help-overlay" in html

    def test_html_contains_all_shortcut_labels(self):
        """HTML should list all 9 shortcut labels in the help dialog."""
        with patch("scripts.dashboard.components.st") as mock_st:
            from scripts.dashboard.components import render_keyboard_shortcuts

            render_keyboard_shortcuts()
            args, kwargs = mock_st.markdown.call_args
            html = args[0] if args else ""
            for meta in KEYBOARD_SHORTCUTS.values():
                assert meta["label"] in html, f"Missing label: {meta['label']}"

    def test_html_contains_keydown_handler(self):
        """JS should attach a keydown event listener."""
        with patch("scripts.dashboard.components.st") as mock_st:
            from scripts.dashboard.components import render_keyboard_shortcuts

            render_keyboard_shortcuts()
            args, kwargs = mock_st.markdown.call_args
            html = args[0] if args else ""
            assert "addEventListener('keydown'" in html or 'addEventListener("keydown"' in html

    def test_html_skips_when_input_focused(self):
        """JS should skip shortcut when input/textarea is focused."""
        with patch("scripts.dashboard.components.st") as mock_st:
            from scripts.dashboard.components import render_keyboard_shortcuts

            render_keyboard_shortcuts()
            args, kwargs = mock_st.markdown.call_args
            html = args[0] if args else ""
            assert "isInputFocused" in html
            assert "input" in html
            assert "textarea" in html

    def test_html_skips_when_modifier_pressed(self):
        """JS should skip shortcut when Ctrl/Meta/Alt is pressed."""
        with patch("scripts.dashboard.components.st") as mock_st:
            from scripts.dashboard.components import render_keyboard_shortcuts

            render_keyboard_shortcuts()
            args, kwargs = mock_st.markdown.call_args
            html = args[0] if args else ""
            assert "e.ctrlKey" in html
            assert "e.metaKey" in html
            assert "e.altKey" in html

    def test_html_has_escape_handler_for_help(self):
        """JS should close help overlay on Escape."""
        with patch("scripts.dashboard.components.st") as mock_st:
            from scripts.dashboard.components import render_keyboard_shortcuts

            render_keyboard_shortcuts()
            args, kwargs = mock_st.markdown.call_args
            html = args[0] if args else ""
            assert "Escape" in html

    def test_html_has_role_dialog_and_aria_modal(self):
        """Help overlay should have role=dialog and aria-modal=true for a11y."""
        with patch("scripts.dashboard.components.st") as mock_st:
            from scripts.dashboard.components import render_keyboard_shortcuts

            render_keyboard_shortcuts()
            args, kwargs = mock_st.markdown.call_args
            html = args[0] if args else ""
            assert 'role="dialog"' in html
            assert 'aria-modal="true"' in html
            assert 'aria-label="Keyboard shortcuts help"' in html

    def test_html_injects_shortcuts_json(self):
        """HTML should embed KEYBOARD_SHORTCUTS as JSON for JS."""
        with patch("scripts.dashboard.components.st") as mock_st:
            from scripts.dashboard.components import render_keyboard_shortcuts

            render_keyboard_shortcuts()
            args, kwargs = mock_st.markdown.call_args
            html = args[0] if args else ""
            # All 9 actions should appear in the embedded JSON
            for meta in KEYBOARD_SHORTCUTS.values():
                assert meta["action"] in html, f"Missing action in JSON: {meta['action']}"

    def test_html_contains_refresh_action_handler(self):
        """JS should handle 'refresh' action via window.location.reload()."""
        with patch("scripts.dashboard.components.st") as mock_st:
            from scripts.dashboard.components import render_keyboard_shortcuts

            render_keyboard_shortcuts()
            args, kwargs = mock_st.markdown.call_args
            html = args[0] if args else ""
            assert "window.location.reload" in html
            assert "refresh" in html

    def test_html_contains_show_help_handler(self):
        """JS should handle 'show_help' action by toggling overlay."""
        with patch("scripts.dashboard.components.st") as mock_st:
            from scripts.dashboard.components import render_keyboard_shortcuts

            render_keyboard_shortcuts()
            args, kwargs = mock_st.markdown.call_args
            html = args[0] if args else ""
            assert "show_help" in html
            assert "classList.toggle" in html
