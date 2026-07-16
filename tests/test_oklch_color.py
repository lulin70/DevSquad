"""V4.1.0 P1-UI-3 — OKLCH color space detection tests."""

from __future__ import annotations

from scripts.qa.uiux_analyzer import UIUXAnalyzer


class TestParseOklchColor:
    def test_parse_valid_oklch(self):
        result = UIUXAnalyzer._parse_oklch_color("oklch(0.7 0.15 250)")
        assert result is not None
        lightness, chroma, hue = result
        assert lightness == 0.7
        assert chroma == 0.15
        assert hue == 250

    def test_parse_valid_oklch_uppercase(self):
        result = UIUXAnalyzer._parse_oklch_color("OKLCH(0.5 0.1 0)")
        assert result is not None
        assert result == (0.5, 0.1, 0.0)

    def test_parse_valid_with_extra_whitespace(self):
        result = UIUXAnalyzer._parse_oklch_color("oklch(  0.8  0.2  180  )")
        assert result is not None
        assert result == (0.8, 0.2, 180.0)

    def test_parse_invalid_format_returns_none(self):
        assert UIUXAnalyzer._parse_oklch_color("rgb(255, 0, 0)") is None
        assert UIUXAnalyzer._parse_oklch_color("#ff0000") is None
        assert UIUXAnalyzer._parse_oklch_color("not a color") is None
        assert UIUXAnalyzer._parse_oklch_color("oklch(0.7 0.15)") is None  # only 2 parts
        assert UIUXAnalyzer._parse_oklch_color("oklch()") is None  # empty
        assert UIUXAnalyzer._parse_oklch_color("oklch(abc def ghi)") is None

    def test_parse_invalid_lightness_returns_none(self):
        # L out of [0, 1] range
        assert UIUXAnalyzer._parse_oklch_color("oklch(1.5 0.1 100)") is None
        assert UIUXAnalyzer._parse_oklch_color("oklch(-0.1 0.1 100)") is None

    def test_parse_negative_chroma_returns_none(self):
        assert UIUXAnalyzer._parse_oklch_color("oklch(0.5 -0.1 100)") is None

    def test_parse_hue_out_of_range_returns_none(self):
        assert UIUXAnalyzer._parse_oklch_color("oklch(0.5 0.1 400)") is None
        assert UIUXAnalyzer._parse_oklch_color("oklch(0.5 0.1 -10)") is None

    def test_parse_empty_string_returns_none(self):
        assert UIUXAnalyzer._parse_oklch_color("") is None
        assert UIUXAnalyzer._parse_oklch_color("   ") is None


class TestOklchToRgb:
    def test_oklch_to_rgb_white(self):
        # L=1, C=0 → white
        r, g, b = UIUXAnalyzer._oklch_to_rgb(1.0, 0.0, 0.0)
        assert r == 255
        assert g == 255
        assert b == 255

    def test_oklch_to_rgb_black(self):
        # L=0, C=0 → black
        r, g, b = UIUXAnalyzer._oklch_to_rgb(0.0, 0.0, 0.0)
        assert r == 0
        assert g == 0
        assert b == 0

    def test_oklch_to_rgb_gray(self):
        # L=0.5, C=0 → some gray
        r, g, b = UIUXAnalyzer._oklch_to_rgb(0.5, 0.0, 0.0)
        assert r == g == b  # achromatic
        assert 0 < r < 255

    def test_oklch_to_rgb_clamps_to_range(self):
        # Extreme values must be clamped to 0-255
        r, g, b = UIUXAnalyzer._oklch_to_rgb(0.0, 0.4, 30.0)
        assert 0 <= r <= 255
        assert 0 <= g <= 255
        assert 0 <= b <= 255

    def test_oklch_to_rgb_returns_integers(self):
        r, g, b = UIUXAnalyzer._oklch_to_rgb(0.7, 0.15, 250)
        assert isinstance(r, int)
        assert isinstance(g, int)
        assert isinstance(b, int)


class TestRgbToOklch:
    def test_rgb_to_oklch_white(self):
        lightness, chroma, hue = UIUXAnalyzer._rgb_to_oklch(255, 255, 255)
        assert lightness > 0.99  # near 1.0
        assert chroma < 0.001  # achromatic (no chroma)

    def test_rgb_to_oklch_black(self):
        lightness, chroma, hue = UIUXAnalyzer._rgb_to_oklch(0, 0, 0)
        assert lightness < 0.01  # near 0
        assert chroma < 0.001

    def test_rgb_to_oklch_red(self):
        # Pure red has a known hue angle ~29 degrees in OKLCH
        lightness, chroma, hue = UIUXAnalyzer._rgb_to_oklch(255, 0, 0)
        assert 0.4 < lightness < 0.7  # lightness around 0.5
        assert chroma > 0.15  # high chroma
        assert 0 <= hue <= 360

    def test_rgb_to_oklch_returns_valid_ranges(self):
        lightness, chroma, hue = UIUXAnalyzer._rgb_to_oklch(128, 64, 200)
        assert 0.0 <= lightness <= 1.0
        assert chroma >= 0.0
        assert 0.0 <= hue <= 360.0


class TestRoundTripConversion:
    def test_round_trip_gray(self):
        # rgb → oklch → rgb for a gray value (achromatic, stable)
        original = (128, 128, 128)
        oklch = UIUXAnalyzer._rgb_to_oklch(*original)
        recovered = UIUXAnalyzer._oklch_to_rgb(*oklch)
        # Allow ±3 tolerance for rounding
        assert abs(recovered[0] - original[0]) <= 3
        assert abs(recovered[1] - original[1]) <= 3
        assert abs(recovered[2] - original[2]) <= 3

    def test_round_trip_white(self):
        original = (255, 255, 255)
        oklch = UIUXAnalyzer._rgb_to_oklch(*original)
        recovered = UIUXAnalyzer._oklch_to_rgb(*oklch)
        assert abs(recovered[0] - original[0]) <= 3
        assert abs(recovered[1] - original[1]) <= 3
        assert abs(recovered[2] - original[2]) <= 3

    def test_round_trip_black(self):
        original = (0, 0, 0)
        oklch = UIUXAnalyzer._rgb_to_oklch(*original)
        recovered = UIUXAnalyzer._oklch_to_rgb(*oklch)
        assert abs(recovered[0] - original[0]) <= 3
        assert abs(recovered[1] - original[1]) <= 3
        assert abs(recovered[2] - original[2]) <= 3


class TestParseColorWithOklch:
    def test_parse_color_supports_oklch(self):
        rgb = UIUXAnalyzer._parse_color("oklch(1.0 0.0 0.0)")
        assert rgb is not None
        assert rgb == (255, 255, 255)

    def test_parse_color_invalid_oklch_returns_none(self):
        assert UIUXAnalyzer._parse_color("oklch(2.0 0.1 100)") is None

    def test_contrast_ratio_with_oklch(self):
        # white vs black expressed as oklch
        ratio = UIUXAnalyzer._compute_contrast_ratio(
            "oklch(1.0 0.0 0.0)", "oklch(0.0 0.0 0.0)"
        )
        assert ratio is not None
        assert ratio > 20.0  # near max contrast (21)


class TestBoundaryValues:
    def test_l_zero_c_zero(self):
        r, g, b = UIUXAnalyzer._oklch_to_rgb(0.0, 0.0, 0.0)
        assert (r, g, b) == (0, 0, 0)

    def test_l_one_c_zero(self):
        r, g, b = UIUXAnalyzer._oklch_to_rgb(1.0, 0.0, 0.0)
        assert (r, g, b) == (255, 255, 255)

    def test_h_zero_and_h_360_equivalent(self):
        # H=0 and H=360 should produce the same color (modulo rounding)
        rgb_0 = UIUXAnalyzer._oklch_to_rgb(0.6, 0.15, 0.0)
        rgb_360 = UIUXAnalyzer._oklch_to_rgb(0.6, 0.15, 360.0)
        assert rgb_0 == rgb_360
