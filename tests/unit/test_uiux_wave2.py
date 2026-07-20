"""Wave 2 UI/UX Enhancement tests.

Tests for:
- W2-T1: Dark mode color palette (LIGHT_MODE_COLORS, DARK_MODE_COLORS) + render_theme_toggle
- W2-T2: SVG role icons (ROLE_SVG_ICONS) + get_role_icon helper
- W2-T3: Toast notification system (TOAST_COLORS, show_toast)
"""

from __future__ import annotations

import re
from unittest.mock import patch

from scripts.dashboard.components import (
    _TOAST_COUNTER_KEY,
    DashboardConfig,
    get_role_icon,
    show_toast,
)

# ── W2-T1: Dark mode colors ──


class TestDarkModeColors:
    """Verify: LIGHT_MODE_COLORS and DARK_MODE_COLORS are valid Morandi-tuned palettes."""

    _HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")

    def test_light_mode_has_8_colors(self):
        """LIGHT_MODE_COLORS should define 8 color tokens."""
        assert len(DashboardConfig.LIGHT_MODE_COLORS) == 8

    def test_dark_mode_has_8_colors(self):
        """DARK_MODE_COLORS should define 8 color tokens (same keys as light)."""
        assert len(DashboardConfig.DARK_MODE_COLORS) == 8
        assert set(DashboardConfig.LIGHT_MODE_COLORS.keys()) == set(
            DashboardConfig.DARK_MODE_COLORS.keys()
        )

    def test_light_mode_colors_are_hex(self):
        """All light mode colors must be valid hex strings."""
        for name, value in DashboardConfig.LIGHT_MODE_COLORS.items():
            assert self._HEX_RE.match(value), f"{name}={value} is not valid hex"

    def test_dark_mode_colors_are_hex(self):
        """All dark mode colors must be valid hex strings."""
        for name, value in DashboardConfig.DARK_MODE_COLORS.items():
            assert self._HEX_RE.match(value), f"{name}={value} is not valid hex"

    def test_light_mode_uses_morandi_primary(self):
        """Light mode accent-primary should match Morandi primary (#7B9EA8)."""
        assert DashboardConfig.LIGHT_MODE_COLORS["accent-primary"].upper() == "#7B9EA8"

    def test_dark_mode_differs_from_light(self):
        """Dark mode colors should differ from light mode (otherwise toggle is a no-op)."""
        diffs = [
            k
            for k in DashboardConfig.LIGHT_MODE_COLORS
            if DashboardConfig.LIGHT_MODE_COLORS[k] != DashboardConfig.DARK_MODE_COLORS[k]
        ]
        assert len(diffs) >= 6, f"Only {len(diffs)} colors differ between light/dark"

    def test_dark_bg_is_dark(self):
        """Dark mode bg-primary should be visually dark (low luminance)."""
        hex_val = DashboardConfig.DARK_MODE_COLORS["bg-primary"].lstrip("#")
        r, g, b = int(hex_val[0:2], 16), int(hex_val[2:4], 16), int(hex_val[4:6], 16)
        # Relative luminance per WCAG: 0.2126 R + 0.7152 G + 0.0722 B
        luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
        assert luminance < 80, f"Dark bg luminance too high: {luminance}"

    def test_light_bg_is_light(self):
        """Light mode bg-primary should be visually light (high luminance)."""
        hex_val = DashboardConfig.LIGHT_MODE_COLORS["bg-primary"].lstrip("#")
        r, g, b = int(hex_val[0:2], 16), int(hex_val[2:4], 16), int(hex_val[4:6], 16)
        luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
        assert luminance > 180, f"Light bg luminance too low: {luminance}"


# ── W2-T1: Dark mode toggle ──


class TestDarkModeToggle:
    """Verify: render_theme_toggle reads/writes session_state and injects script."""

    def test_toggle_returns_bool_true_when_enabled(self):
        """When session_state has dark_mode=True, toggle should return True."""
        with patch("scripts.dashboard.components.st") as mock_st:
            mock_st.session_state = {"dark_mode": True}
            mock_st.toggle.return_value = True
            from scripts.dashboard.components import render_theme_toggle

            result = render_theme_toggle()
            assert result is True

    def test_toggle_returns_bool_false_when_disabled(self):
        """When session_state has dark_mode=False, toggle should return False."""
        with patch("scripts.dashboard.components.st") as mock_st:
            mock_st.session_state = {"dark_mode": False}
            mock_st.toggle.return_value = False
            from scripts.dashboard.components import render_theme_toggle

            result = render_theme_toggle()
            assert result is False

    def test_toggle_writes_session_state(self):
        """Toggle should persist user choice to session_state['dark_mode']."""
        with patch("scripts.dashboard.components.st") as mock_st:
            mock_st.session_state = {"dark_mode": False}
            mock_st.toggle.return_value = True
            from scripts.dashboard.components import render_theme_toggle

            render_theme_toggle()
            assert mock_st.session_state["dark_mode"] is True

    def test_toggle_injects_dark_script_when_enabled(self):
        """When dark mode enabled, injected script should set data-theme=dark."""
        with patch("scripts.dashboard.components.st") as mock_st:
            mock_st.session_state = {"dark_mode": False}
            mock_st.toggle.return_value = True
            from scripts.dashboard.components import render_theme_toggle

            render_theme_toggle()
            # Inspect the markdown call
            args, kwargs = mock_st.markdown.call_args
            html = args[0] if args else kwargs.get("body", "")
            assert "data-theme" in html
            assert "'dark'" in html or '"dark"' in html

    def test_toggle_injects_light_script_when_disabled(self):
        """When dark mode disabled, injected script should set data-theme=light."""
        with patch("scripts.dashboard.components.st") as mock_st:
            mock_st.session_state = {"dark_mode": True}
            mock_st.toggle.return_value = False
            from scripts.dashboard.components import render_theme_toggle

            render_theme_toggle()
            args, kwargs = mock_st.markdown.call_args
            html = args[0] if args else kwargs.get("body", "")
            assert "data-theme" in html
            assert "'light'" in html or '"light"' in html


# ── W2-T2: SVG role icons ──


class TestRoleSvgIcons:
    """Verify: ROLE_SVG_ICONS defines valid Lucide-style SVG inner content for 7 roles."""

    def test_svg_icons_defined_for_all_core_roles(self):
        """Every CORE_ROLES entry should have a corresponding SVG icon."""
        for role in DashboardConfig.CORE_ROLES:
            assert role in DashboardConfig.ROLE_SVG_ICONS, f"Missing SVG for role: {role}"

    def test_svg_icons_count_matches_core_roles(self):
        """ROLE_SVG_ICONS should have exactly 7 entries (one per core role)."""
        assert len(DashboardConfig.ROLE_SVG_ICONS) == 7

    def test_each_svg_has_path_or_geometry(self):
        """Each SVG inner content should contain at least one geometry element."""
        geometry_tags = ("<path", "<line", "<circle", "<rect", "<polygon", "<polyline")
        for role, inner in DashboardConfig.ROLE_SVG_ICONS.items():
            assert any(tag in inner for tag in geometry_tags), (
                f"Role {role} SVG has no geometry elements"
            )

    def test_no_svg_uses_fill_black_or_fill_white(self):
        """SVG icons should be single-color stroke (no hardcoded fill), except palette dots."""
        for role, inner in DashboardConfig.ROLE_SVG_ICONS.items():
            # Disallow fill="black" / fill="white" / fill="#000" / fill="#fff"
            assert 'fill="black"' not in inner.lower(), f"{role} uses fill=black"
            assert 'fill="white"' not in inner.lower(), f"{role} uses fill=white"

    def test_architect_icon_has_landmark_polygon(self):
        """Architect icon should include a polygon (landmark roof)."""
        assert "<polygon" in DashboardConfig.ROLE_SVG_ICONS["architect"]

    def test_security_icon_has_shield_path(self):
        """Security icon should include a shield-like path."""
        # Lucide shield-check uses a path starting with M20 13c0 5...
        assert "M20 13" in DashboardConfig.ROLE_SVG_ICONS["security"]

    def test_solo_coder_icon_has_code_brackets(self):
        """Solo-coder icon should include code bracket paths (m18 16, m6 8)."""
        inner = DashboardConfig.ROLE_SVG_ICONS["solo-coder"]
        assert "m18 16" in inner
        assert "m6 8" in inner

    def test_devops_icon_has_two_circles(self):
        """DevOps icon (settings-2) should have two circles."""
        inner = DashboardConfig.ROLE_SVG_ICONS["devops"]
        assert inner.count("<circle") == 2

    def test_ui_designer_icon_has_palette_path(self):
        """UI-designer icon should have the Lucide palette path starting with M12 2C6.5."""
        assert "M12 2C6.5" in DashboardConfig.ROLE_SVG_ICONS["ui-designer"]

    def test_tester_icon_has_flask_path(self):
        """Tester icon should have flask-conical path (M10 2v7.31)."""
        assert "M10 2v7.31" in DashboardConfig.ROLE_SVG_ICONS["tester"]

    def test_product_manager_icon_has_clipboard_rect(self):
        """Product-manager icon should have a clipboard rect at top."""
        assert "<rect" in DashboardConfig.ROLE_SVG_ICONS["product-manager"]


# ── W2-T2: get_role_icon helper ──


class TestGetRoleIcon:
    """Verify: get_role_icon returns SVG or emoji depending on fmt parameter."""

    def test_default_fmt_returns_svg(self):
        """Default fmt should return an SVG string."""
        result = get_role_icon("architect")
        assert result.startswith("<svg")
        assert "</svg>" in result

    def test_svg_fmt_returns_svg(self):
        """fmt='svg' should return an SVG string."""
        result = get_role_icon("tester", fmt="svg")
        assert result.startswith("<svg")
        assert "</svg>" in result

    def test_emoji_fmt_returns_emoji(self):
        """fmt='emoji' should return the legacy emoji."""
        result = get_role_icon("architect", fmt="emoji")
        assert result == "🏗️"

    def test_svg_uses_current_color(self):
        """SVG should use stroke='currentColor' for theme adaptation."""
        result = get_role_icon("security")
        assert 'stroke="currentColor"' in result

    def test_svg_has_correct_dimensions(self):
        """SVG should be 16x16 with 24x24 viewBox (Lucide standard)."""
        result = get_role_icon("devops")
        assert 'width="16"' in result
        assert 'height="16"' in result
        assert 'viewBox="0 0 24 24"' in result

    def test_unknown_role_svg_returns_default(self):
        """Unknown role should return a default square icon (SVG)."""
        result = get_role_icon("nonexistent-role")
        assert result.startswith("<svg")
        assert "<rect" in result  # default has a rect

    def test_unknown_role_emoji_returns_question_mark(self):
        """Unknown role should return ❓ in emoji format."""
        result = get_role_icon("nonexistent-role", fmt="emoji")
        assert result == "❓"

    def test_svg_contains_role_specific_inner(self):
        """SVG should contain the role-specific inner content from ROLE_SVG_ICONS."""
        result = get_role_icon("solo-coder")
        # solo-coder inner contains "m18 16"
        assert "m18 16" in result

    def test_all_core_roles_return_valid_svg(self):
        """All 7 core roles should return valid SVG without falling back to default."""
        for role in DashboardConfig.CORE_ROLES:
            result = get_role_icon(role)
            assert result.startswith("<svg"), f"{role} did not return SVG"
            assert "</svg>" in result, f"{role} SVG not closed"


# ── W2-T3: Toast colors ──


class TestToastColors:
    """Verify: TOAST_COLORS defines 4 levels with Morandi-aligned hex values."""

    _HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")

    def test_toast_colors_has_4_levels(self):
        """TOAST_COLORS should have info/success/warning/error levels."""
        expected = {"info", "success", "warning", "error"}
        assert set(DashboardConfig.TOAST_COLORS.keys()) == expected

    def test_toast_colors_are_hex(self):
        """All toast colors must be valid hex strings."""
        for level, value in DashboardConfig.TOAST_COLORS.items():
            assert self._HEX_RE.match(value), f"{level}={value} is not valid hex"

    def test_info_color_matches_morandi_info(self):
        """Toast info color should match Morandi info (#9DB5C2)."""
        assert DashboardConfig.TOAST_COLORS["info"].upper() == "#9DB5C2"

    def test_success_color_matches_morandi_success(self):
        """Toast success color should match Morandi success (#8FA886)."""
        assert DashboardConfig.TOAST_COLORS["success"].upper() == "#8FA886"

    def test_warning_color_matches_morandi_warning(self):
        """Toast warning color should match Morandi warning (#C9A87C)."""
        assert DashboardConfig.TOAST_COLORS["warning"].upper() == "#C9A87C"

    def test_error_color_matches_morandi_danger(self):
        """Toast error color should match Morandi danger (#B58484)."""
        assert DashboardConfig.TOAST_COLORS["error"].upper() == "#B58484"


# ── W2-T3: show_toast ──


class TestShowToast:
    """Verify: show_toast renders HTML with correct level, duration, and escaping."""

    def test_toast_returns_unique_id(self):
        """show_toast should return a unique toast id (toast-N)."""
        with patch("scripts.dashboard.components.st") as mock_st:
            mock_st.session_state = {_TOAST_COUNTER_KEY: 0}
            toast_id = show_toast("hello", level="info")
            assert toast_id.startswith("toast-")
            assert toast_id == "toast-1"

    def test_toast_increments_counter(self):
        """Each toast call should increment the counter in session_state."""
        with patch("scripts.dashboard.components.st") as mock_st:
            mock_st.session_state = {_TOAST_COUNTER_KEY: 5}
            toast_id = show_toast("hello")
            assert toast_id == "toast-6"
            assert mock_st.session_state[_TOAST_COUNTER_KEY] == 6

    def test_toast_html_contains_message(self):
        """The rendered HTML should contain the (escaped) message."""
        with patch("scripts.dashboard.components.st") as mock_st:
            mock_st.session_state = {_TOAST_COUNTER_KEY: 0}
            show_toast("Task completed")
            args, kwargs = mock_st.markdown.call_args
            html = args[0] if args else ""
            assert "Task completed" in html

    def test_toast_html_contains_level_class(self):
        """The rendered HTML should contain toast-{level} class."""
        with patch("scripts.dashboard.components.st") as mock_st:
            mock_st.session_state = {_TOAST_COUNTER_KEY: 0}
            show_toast("done", level="success")
            args, kwargs = mock_st.markdown.call_args
            html = args[0] if args else ""
            assert "toast-success" in html

    def test_toast_unknown_level_falls_back_to_info(self):
        """Unknown level should fall back to 'info'."""
        with patch("scripts.dashboard.components.st") as mock_st:
            mock_st.session_state = {_TOAST_COUNTER_KEY: 0}
            show_toast("oops", level="critical")
            args, kwargs = mock_st.markdown.call_args
            html = args[0] if args else ""
            assert "toast-info" in html
            assert "toast-critical" not in html

    def test_toast_duration_converted_to_ms(self):
        """Duration in seconds should be converted to ms in the inline style."""
        with patch("scripts.dashboard.components.st") as mock_st:
            mock_st.session_state = {_TOAST_COUNTER_KEY: 0}
            show_toast("delayed", level="info", duration=7)
            args, kwargs = mock_st.markdown.call_args
            html = args[0] if args else ""
            assert "7000ms" in html

    def test_toast_duration_clamped_to_min_1(self):
        """Duration < 1 should be clamped to 1 second."""
        with patch("scripts.dashboard.components.st") as mock_st:
            mock_st.session_state = {_TOAST_COUNTER_KEY: 0}
            show_toast("min", duration=0)
            args, kwargs = mock_st.markdown.call_args
            html = args[0] if args else ""
            assert "1000ms" in html

    def test_toast_duration_clamped_to_max_30(self):
        """Duration > 30 should be clamped to 30 seconds."""
        with patch("scripts.dashboard.components.st") as mock_st:
            mock_st.session_state = {_TOAST_COUNTER_KEY: 0}
            show_toast("max", duration=120)
            args, kwargs = mock_st.markdown.call_args
            html = args[0] if args else ""
            assert "30000ms" in html

    def test_toast_html_escapes_angle_brackets(self):
        """Message with <script> should be escaped to prevent XSS."""
        with patch("scripts.dashboard.components.st") as mock_st:
            mock_st.session_state = {_TOAST_COUNTER_KEY: 0}
            show_toast("<script>alert(1)</script>")
            args, kwargs = mock_st.markdown.call_args
            html = args[0] if args else ""
            assert "<script>alert(1)</script>" not in html
            assert "&lt;script&gt;" in html

    def test_toast_html_escapes_quotes(self):
        """Message with double quotes should be escaped."""
        with patch("scripts.dashboard.components.st") as mock_st:
            mock_st.session_state = {_TOAST_COUNTER_KEY: 0}
            show_toast('say "hello"')
            args, kwargs = mock_st.markdown.call_args
            html = args[0] if args else ""
            assert "&quot;" in html

    def test_toast_html_has_container_with_aria_live(self):
        """Toast container should have aria-live='polite' for accessibility."""
        with patch("scripts.dashboard.components.st") as mock_st:
            mock_st.session_state = {_TOAST_COUNTER_KEY: 0}
            show_toast("a11y", level="info")
            args, kwargs = mock_st.markdown.call_args
            html = args[0] if args else ""
            assert 'aria-live="polite"' in html
            assert 'aria-atomic="true"' in html

    def test_toast_html_has_role_alert(self):
        """Toast element should have role='alert' for screen readers."""
        with patch("scripts.dashboard.components.st") as mock_st:
            mock_st.session_state = {_TOAST_COUNTER_KEY: 0}
            show_toast("alert", level="error")
            args, kwargs = mock_st.markdown.call_args
            html = args[0] if args else ""
            assert 'role="alert"' in html

    def test_toast_html_has_unique_id_attribute(self):
        """Toast div should have a unique id attribute."""
        with patch("scripts.dashboard.components.st") as mock_st:
            mock_st.session_state = {_TOAST_COUNTER_KEY: 42}
            toast_id = show_toast("unique")
            args, kwargs = mock_st.markdown.call_args
            html = args[0] if args else ""
            assert f'id="{toast_id}"' in html


# ── Integration: CSS contains dark mode + toast styles ──


class TestCssContainsWave2Styles:
    """Verify: apply_custom_css injects dark mode + toast styles."""

    def test_apply_custom_css_runs_without_error(self):
        """apply_custom_css should execute without raising (mocked streamlit)."""
        with patch("scripts.dashboard.components.st") as mock_st:
            from scripts.dashboard.components import apply_custom_css

            apply_custom_css()
            assert mock_st.markdown.called

    def test_css_contains_dark_mode_selector(self):
        """CSS should contain [data-theme='dark'] selector."""
        with patch("scripts.dashboard.components.st") as mock_st:
            from scripts.dashboard.components import apply_custom_css

            apply_custom_css()
            args, kwargs = mock_st.markdown.call_args
            css = args[0] if args else ""
            assert '[data-theme="dark"]' in css

    def test_css_contains_css_variables(self):
        """CSS should define --bg-primary and --accent-primary variables."""
        with patch("scripts.dashboard.components.st") as mock_st:
            from scripts.dashboard.components import apply_custom_css

            apply_custom_css()
            args, kwargs = mock_st.markdown.call_args
            css = args[0] if args else ""
            assert "--bg-primary:" in css
            assert "--accent-primary:" in css
            assert "var(--bg-primary)" in css
            assert "var(--accent-primary)" in css

    def test_css_contains_toast_styles(self):
        """CSS should define .toast-container, .toast, and toast-* level classes."""
        with patch("scripts.dashboard.components.st") as mock_st:
            from scripts.dashboard.components import apply_custom_css

            apply_custom_css()
            args, kwargs = mock_st.markdown.call_args
            css = args[0] if args else ""
            assert ".toast-container" in css
            assert ".toast {" in css or ".toast{" in css
            assert ".toast-info" in css
            assert ".toast-success" in css
            assert ".toast-warning" in css
            assert ".toast-error" in css

    def test_css_contains_toast_animations(self):
        """CSS should define toast-in and toast-out keyframes."""
        with patch("scripts.dashboard.components.st") as mock_st:
            from scripts.dashboard.components import apply_custom_css

            apply_custom_css()
            args, kwargs = mock_st.markdown.call_args
            css = args[0] if args else ""
            assert "@keyframes toast-in" in css
            assert "@keyframes toast-out" in css
