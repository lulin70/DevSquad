"""Wave 3 UI/UX Enhancement tests.

Tests for:
- W3-T1: Command palette (COMMAND_PALETTE_ITEMS, render_command_palette)
- W3-T2: i18n (TRANSLATIONS, I18nManager, t)
- W3-T3: Skeleton screens (SKELETON_KINDS, render_skeleton)
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from scripts.dashboard.components import (
    COMMAND_PALETTE_ITEMS,
    SKELETON_KINDS,
)
from scripts.dashboard.i18n import (
    _DEFAULT_LOCALE,
    _LOCALE_KEY,
    _SUPPORTED_LOCALES,
    TRANSLATIONS,
    I18nManager,
    get_default_locale,
    get_supported_locales,
    t,
)

# ── W3-T1: Command palette ──


class TestCommandPaletteItems:
    """Verify: COMMAND_PALETTE_ITEMS defines 8 commands with required fields."""

    def test_command_palette_has_8_items(self):
        """Should have 7 page commands + 1 toggle command = 8 total."""
        assert len(COMMAND_PALETTE_ITEMS) == 8

    def test_each_item_has_required_fields(self):
        """Each item must have id, label, hint, action fields."""
        for item in COMMAND_PALETTE_ITEMS:
            assert "id" in item, f"Missing id: {item}"
            assert "label" in item, f"Missing label: {item}"
            assert "hint" in item, f"Missing hint: {item}"
            assert "action" in item, f"Missing action: {item}"

    def test_each_item_id_is_unique(self):
        """All item ids should be unique."""
        ids = [it["id"] for it in COMMAND_PALETTE_ITEMS]
        assert len(ids) == len(set(ids)), "Duplicate ids found"

    def test_each_item_action_is_unique(self):
        """All item actions should be unique."""
        actions = [it["action"] for it in COMMAND_PALETTE_ITEMS]
        assert len(actions) == len(set(actions)), "Duplicate actions found"

    def test_page_commands_use_page_prefix(self):
        """Page commands should use 'page:<Name>' action format."""
        page_items = [it for it in COMMAND_PALETTE_ITEMS if it["action"].startswith("page:")]
        # 7 page commands (Overview/Phases/Mapping/Gates/Performance/Task Dispatch/DAG)
        assert len(page_items) == 7

    def test_toggle_command_uses_toggle_prefix(self):
        """Toggle command should use 'toggle:<target>' action format."""
        toggle_items = [it for it in COMMAND_PALETTE_ITEMS if it["action"].startswith("toggle:")]
        assert len(toggle_items) == 1
        assert toggle_items[0]["action"] == "toggle:dark_mode"

    def test_hint_for_pages_are_digits_1_to_7(self):
        """Page command hints should be digits 1-7 for keyboard shortcuts."""
        page_items = [it for it in COMMAND_PALETTE_ITEMS if it["action"].startswith("page:")]
        hints = [it["hint"] for it in page_items]
        for h in hints:
            assert h in {"1", "2", "3", "4", "5", "6", "7"}, f"Invalid hint: {h}"

    def test_toggle_command_hint_is_d(self):
        """Toggle dark mode hint should be 'D'."""
        toggle_item = next(
            it for it in COMMAND_PALETTE_ITEMS if it["action"] == "toggle:dark_mode"
        )
        assert toggle_item["hint"] == "D"

    def test_all_7_core_pages_covered(self):
        """All 7 dashboard pages should be covered by command palette."""
        page_actions = {it["action"] for it in COMMAND_PALETTE_ITEMS if it["action"].startswith("page:")}
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


class TestRenderCommandPalette:
    """Verify: render_command_palette injects HTML/CSS/JS without errors."""

    def test_render_command_palette_runs_without_error(self):
        """render_command_palette should execute without raising."""
        with patch("scripts.dashboard.components.st") as mock_st:
            from scripts.dashboard.components import render_command_palette

            render_command_palette()
            assert mock_st.markdown.called

    def test_html_contains_overlay_div(self):
        """HTML should contain the cmd-palette-overlay div."""
        with patch("scripts.dashboard.components.st") as mock_st:
            from scripts.dashboard.components import render_command_palette

            render_command_palette()
            args, kwargs = mock_st.markdown.call_args
            html = args[0] if args else ""
            assert 'id="cmd-palette-overlay"' in html
            assert "cmd-palette-overlay" in html

    def test_html_contains_search_input(self):
        """HTML should contain a search input."""
        with patch("scripts.dashboard.components.st") as mock_st:
            from scripts.dashboard.components import render_command_palette

            render_command_palette()
            args, kwargs = mock_st.markdown.call_args
            html = args[0] if args else ""
            assert 'id="cmd-palette-search"' in html
            assert "Search commands" in html

    def test_html_contains_cmd_k_shortcut_handler(self):
        """JS should handle Cmd+K / Ctrl+K shortcut."""
        with patch("scripts.dashboard.components.st") as mock_st:
            from scripts.dashboard.components import render_command_palette

            render_command_palette()
            args, kwargs = mock_st.markdown.call_args
            html = args[0] if args else ""
            assert "e.key === 'k'" in html
            assert "e.metaKey" in html
            assert "e.ctrlKey" in html

    def test_html_contains_escape_handler(self):
        """JS should handle Escape to close."""
        with patch("scripts.dashboard.components.st") as mock_st:
            from scripts.dashboard.components import render_command_palette

            render_command_palette()
            args, kwargs = mock_st.markdown.call_args
            html = args[0] if args else ""
            assert "Escape" in html

    def test_html_contains_arrow_navigation(self):
        """JS should support Arrow Up/Down navigation."""
        with patch("scripts.dashboard.components.st") as mock_st:
            from scripts.dashboard.components import render_command_palette

            render_command_palette()
            args, kwargs = mock_st.markdown.call_args
            html = args[0] if args else ""
            assert "ArrowDown" in html
            assert "ArrowUp" in html
            assert "Enter" in html

    def test_html_injects_items_json(self):
        """HTML should embed COMMAND_PALETTE_ITEMS as JSON for JS."""
        with patch("scripts.dashboard.components.st") as mock_st:
            from scripts.dashboard.components import render_command_palette

            render_command_palette()
            args, kwargs = mock_st.markdown.call_args
            html = args[0] if args else ""
            # Items JSON should contain all 8 command labels
            for item in COMMAND_PALETTE_ITEMS:
                assert item["label"] in html, f"Missing label: {item['label']}"

    def test_html_has_role_dialog_and_aria_modal(self):
        """Overlay should have role=dialog and aria-modal=true for a11y."""
        with patch("scripts.dashboard.components.st") as mock_st:
            from scripts.dashboard.components import render_command_palette

            render_command_palette()
            args, kwargs = mock_st.markdown.call_args
            html = args[0] if args else ""
            assert 'role="dialog"' in html
            assert 'aria-modal="true"' in html
            assert 'aria-label="Command palette"' in html


# ── W3-T2: i18n translations ──


class TestI18nTranslations:
    """Verify: TRANSLATIONS table is complete and well-formed."""

    def test_translations_has_entries(self):
        """TRANSLATIONS should have a non-trivial number of entries."""
        assert len(TRANSLATIONS) >= 25

    def test_each_entry_has_zh_and_en(self):
        """Every translation entry must have both 'zh' and 'en' keys."""
        for key, entry in TRANSLATIONS.items():
            assert "zh" in entry, f"Missing 'zh' for key: {key}"
            assert "en" in entry, f"Missing 'en' for key: {key}"
            assert isinstance(entry["zh"], str) and entry["zh"], f"Empty zh for {key}"
            assert isinstance(entry["en"], str) and entry["en"], f"Empty en for {key}"

    def test_page_translations_present(self):
        """All 7 page titles should have translations."""
        page_keys = [
            "page.overview",
            "page.phases",
            "page.mapping",
            "page.gates",
            "page.performance",
            "page.task_dispatch",
            "page.dag",
        ]
        for k in page_keys:
            assert k in TRANSLATIONS, f"Missing page translation: {k}"

    def test_button_translations_present(self):
        """Common buttons should have translations."""
        btn_keys = ["btn.run_all", "btn.reset_state", "btn.generate_report", "btn.refresh"]
        for k in btn_keys:
            assert k in TRANSLATIONS, f"Missing button translation: {k}"

    def test_status_translations_present(self):
        """All 6 status labels should have translations."""
        status_keys = [
            "status.pending",
            "status.running",
            "status.completed",
            "status.failed",
            "status.skipped",
            "status.blocked",
        ]
        for k in status_keys:
            assert k in TRANSLATIONS, f"Missing status translation: {k}"

    def test_zh_and_en_differ(self):
        """Chinese and English translations should differ (no copy-paste errors)."""
        for key, entry in TRANSLATIONS.items():
            assert entry["zh"] != entry["en"], f"zh==en for key: {key}"

    def test_translation_keys_use_dot_notation(self):
        """All keys should follow 'category.name' dot notation."""
        for key in TRANSLATIONS:
            assert "." in key, f"Key missing dot notation: {key}"
            parts = key.split(".")
            assert len(parts) >= 2, f"Key should have at least 2 parts: {key}"


class TestI18nTFunction:
    """Verify: t() returns correct translation for given key/locale."""

    def test_t_returns_zh_for_zh_locale(self):
        """t('page.overview', 'zh') should return Chinese translation."""
        assert t("page.overview", "zh") == TRANSLATIONS["page.overview"]["zh"]

    def test_t_returns_en_for_en_locale(self):
        """t('page.overview', 'en') should return English translation."""
        assert t("page.overview", "en") == TRANSLATIONS["page.overview"]["en"]

    def test_t_returns_key_for_unknown_key(self):
        """Unknown key should return the key itself (developer signal)."""
        assert t("nonexistent.key", "zh") == "nonexistent.key"

    def test_t_falls_back_to_default_for_unknown_locale(self):
        """Unknown locale should fall back to default locale."""
        # 'fr' is not supported; should fall back to default (zh)
        result = t("page.overview", "fr")  # type: ignore[arg-type]
        assert result == TRANSLATIONS["page.overview"][_DEFAULT_LOCALE]

    def test_t_uses_session_locale_when_locale_none(self):
        """When locale=None, t() should use the active session locale."""
        with patch("scripts.dashboard.i18n.st") as mock_st:
            mock_st.session_state = {_LOCALE_KEY: "en"}
            result = t("page.overview")
            assert result == TRANSLATIONS["page.overview"]["en"]

    def test_t_uses_default_locale_outside_streamlit_context(self):
        """When st.session_state raises, t() should use default locale."""
        with patch("scripts.dashboard.i18n.st") as mock_st:
            # Configure .get to raise to simulate non-streamlit context
            mock_st.session_state.get.side_effect = RuntimeError("no streamlit")
            result = t("page.overview")
            assert result == TRANSLATIONS["page.overview"][_DEFAULT_LOCALE]


class TestI18nManager:
    """Verify: I18nManager reads/writes session_state correctly."""

    def test_get_locale_returns_default_when_unset(self):
        """When session_state has no locale, should return default."""
        with patch("scripts.dashboard.i18n.st") as mock_st:
            mock_st.session_state = {}
            assert I18nManager.get_locale() == _DEFAULT_LOCALE

    def test_get_locale_returns_stored_value(self):
        """When session_state has locale='en', should return 'en'."""
        with patch("scripts.dashboard.i18n.st") as mock_st:
            mock_st.session_state = {_LOCALE_KEY: "en"}
            assert I18nManager.get_locale() == "en"

    def test_get_locale_returns_default_for_invalid_value(self):
        """Invalid locale value should fall back to default."""
        with patch("scripts.dashboard.i18n.st") as mock_st:
            mock_st.session_state = {_LOCALE_KEY: "fr"}
            assert I18nManager.get_locale() == _DEFAULT_LOCALE

    def test_set_locale_persists_to_session_state(self):
        """set_locale('en') should write to session_state."""
        with patch("scripts.dashboard.i18n.st") as mock_st:
            mock_st.session_state = {}
            I18nManager.set_locale("en")
            assert mock_st.session_state[_LOCALE_KEY] == "en"

    def test_set_locale_raises_for_invalid_locale(self):
        """set_locale with unsupported value should raise ValueError."""
        with patch("scripts.dashboard.i18n.st"), pytest.raises(ValueError):
            I18nManager.set_locale("fr")  # type: ignore[arg-type]

    def test_supported_locales_contains_zh_and_en(self):
        """Supported locales should include 'zh' and 'en'."""
        assert "zh" in _SUPPORTED_LOCALES
        assert "en" in _SUPPORTED_LOCALES

    def test_get_supported_locales_returns_tuple(self):
        """get_supported_locales() should return the supported tuple."""
        assert get_supported_locales() == _SUPPORTED_LOCALES

    def test_get_default_locale_returns_zh(self):
        """Default locale should be 'zh' per DevSquad convention."""
        assert get_default_locale() == "zh"


# ── W3-T3: Skeleton screens ──


class TestSkeletonKinds:
    """Verify: SKELETON_KINDS defines 3 kinds with positive counts."""

    def test_skeleton_kinds_has_3_entries(self):
        """Should define metric, phase_row, chart kinds."""
        assert set(SKELETON_KINDS.keys()) == {"metric", "phase_row", "chart"}

    def test_skeleton_kinds_counts_are_positive(self):
        """Each kind's default count should be positive."""
        for kind, count in SKELETON_KINDS.items():
            assert count > 0, f"{kind} has non-positive count: {count}"

    def test_metric_default_count_is_4(self):
        """Metric skeleton should default to 4 cards (top row)."""
        assert SKELETON_KINDS["metric"] == 4

    def test_phase_row_default_count_is_5(self):
        """Phase row skeleton should default to 5 rows."""
        assert SKELETON_KINDS["phase_row"] == 5

    def test_chart_default_count_is_1(self):
        """Chart skeleton should default to 1 placeholder."""
        assert SKELETON_KINDS["chart"] == 1


class TestRenderSkeleton:
    """Verify: render_skeleton injects correct HTML for each kind."""

    def test_render_skeleton_metric_runs_without_error(self):
        """render_skeleton('metric') should execute without raising."""
        with patch("scripts.dashboard.components.st") as mock_st:
            from scripts.dashboard.components import render_skeleton

            render_skeleton("metric")
            assert mock_st.markdown.called

    def test_render_skeleton_phase_row_runs_without_error(self):
        """render_skeleton('phase_row') should execute without raising."""
        with patch("scripts.dashboard.components.st") as mock_st:
            from scripts.dashboard.components import render_skeleton

            render_skeleton("phase_row")
            assert mock_st.markdown.called

    def test_render_skeleton_chart_runs_without_error(self):
        """render_skeleton('chart') should execute without raising."""
        with patch("scripts.dashboard.components.st") as mock_st:
            from scripts.dashboard.components import render_skeleton

            render_skeleton("chart")
            assert mock_st.markdown.called

    def test_render_skeleton_unknown_kind_falls_back_to_metric(self):
        """Unknown kind should fall back to 'metric'."""
        with patch("scripts.dashboard.components.st") as mock_st:
            from scripts.dashboard.components import render_skeleton

            render_skeleton("nonexistent")
            args, kwargs = mock_st.markdown.call_args
            html = args[0] if args else ""
            assert "skeleton-metric-row" in html

    def test_render_skeleton_metric_contains_4_elements_by_default(self):
        """Default metric skeleton should render 4 metric cards."""
        with patch("scripts.dashboard.components.st") as mock_st:
            from scripts.dashboard.components import render_skeleton

            render_skeleton("metric")
            args, kwargs = mock_st.markdown.call_args
            html = args[0] if args else ""
            # Count occurrences of "skeleton-metric" (excluding the row container)
            # Each metric element has class "skeleton skeleton-metric"
            count = html.count("skeleton skeleton-metric")
            assert count == 4

    def test_render_skeleton_phase_row_contains_5_elements_by_default(self):
        """Default phase_row skeleton should render 5 phase rows."""
        with patch("scripts.dashboard.components.st") as mock_st:
            from scripts.dashboard.components import render_skeleton

            render_skeleton("phase_row")
            args, kwargs = mock_st.markdown.call_args
            html = args[0] if args else ""
            count = html.count("skeleton skeleton-phase-row")
            assert count == 5

    def test_render_skeleton_chart_contains_bars(self):
        """Chart skeleton should contain 5 animated bars (div elements only)."""
        with patch("scripts.dashboard.components.st") as mock_st:
            from scripts.dashboard.components import render_skeleton

            render_skeleton("chart")
            args, kwargs = mock_st.markdown.call_args
            html = args[0] if args else ""
            # Count only the bar div elements (CSS rules add 2 more occurrences)
            assert html.count('class="skeleton-chart-bar"') == 5

    def test_render_skeleton_custom_count_overrides_default(self):
        """count=2 should override the default count for metric."""
        with patch("scripts.dashboard.components.st") as mock_st:
            from scripts.dashboard.components import render_skeleton

            render_skeleton("metric", count=2)
            args, kwargs = mock_st.markdown.call_args
            html = args[0] if args else ""
            assert html.count("skeleton skeleton-metric") == 2

    def test_render_skeleton_count_clamped_to_min_1(self):
        """count=0 should be clamped to 1."""
        with patch("scripts.dashboard.components.st") as mock_st:
            from scripts.dashboard.components import render_skeleton

            render_skeleton("metric", count=0)
            args, kwargs = mock_st.markdown.call_args
            html = args[0] if args else ""
            assert html.count("skeleton skeleton-metric") == 1

    def test_render_skeleton_count_clamped_to_max_20(self):
        """count=100 should be clamped to 20."""
        with patch("scripts.dashboard.components.st") as mock_st:
            from scripts.dashboard.components import render_skeleton

            render_skeleton("metric", count=100)
            args, kwargs = mock_st.markdown.call_args
            html = args[0] if args else ""
            assert html.count("skeleton skeleton-metric") == 20

    def test_render_skeleton_contains_shimmer_animation(self):
        """CSS should define skeleton-shimmer keyframes."""
        with patch("scripts.dashboard.components.st") as mock_st:
            from scripts.dashboard.components import render_skeleton

            render_skeleton("metric")
            args, kwargs = mock_st.markdown.call_args
            html = args[0] if args else ""
            assert "@keyframes skeleton-shimmer" in html
            assert "animation: skeleton-shimmer" in html

    def test_render_skeleton_has_role_status_and_aria_live(self):
        """Skeleton should have role=status and aria-live=polite for a11y."""
        with patch("scripts.dashboard.components.st") as mock_st:
            from scripts.dashboard.components import render_skeleton

            render_skeleton("metric")
            args, kwargs = mock_st.markdown.call_args
            html = args[0] if args else ""
            assert 'role="status"' in html
            assert 'aria-live="polite"' in html

    def test_render_skeleton_dark_mode_overrides_present(self):
        """CSS should include dark mode overrides for skeleton colors."""
        with patch("scripts.dashboard.components.st") as mock_st:
            from scripts.dashboard.components import render_skeleton

            render_skeleton("metric")
            args, kwargs = mock_st.markdown.call_args
            html = args[0] if args else ""
            assert '[data-theme="dark"] .skeleton' in html
