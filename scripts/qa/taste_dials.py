"""TasteDials — Visual taste dials (0.0-1.0) for UI/UX audit threshold control.

Inspired by Leonxlnx/taste-skill's Taste Dials (DESIGN_VARIANCE / MOTION_INTENSITY
/ VISUAL_DENSITY).

Distinct from PromptDials (scripts/collaboration/prompt_dials.py):
  - PromptDials: prompt-level control (verbosity/creativity/risk, range 1-5)
  - TasteDials: visual-design-level control (variance/motion/density, range 0.0-1.0)

UIUXAnalyzer loads TasteDials to dynamically adjust audit thresholds:
  - VISUAL_DENSITY high → relax layout density checks (more elements allowed)
  - MOTION_INTENSITY high → relax motion rule thresholds (more animation allowed)
  - DESIGN_VARIANCE high → relax consistency checks (more diversity allowed)

V4.1.0 (UI-P0-2): Initial implementation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Default sensitivity for threshold adjustment (max ±30%)
DEFAULT_SENSITIVITY: float = 0.3

# Valid range for dial values
MIN_DIAL: float = 0.0
MAX_DIAL: float = 1.0

# Default dial value (midpoint = no adjustment)
DEFAULT_DIAL: float = 0.5


@dataclass
class TasteDials:
    """Visual taste dials (0.0-1.0), inspired by taste-skill.

    Three dimensions control UI/UX audit threshold adjustments:
      - design_variance: 0=uniform/consistent, 1=diverse/varied
      - motion_intensity: 0=static/subtle, 1=intense/animated
      - visual_density: 0=spacious/airy, 1=dense/compact

    Attributes:
        design_variance: Controls consistency check strictness (0.0-1.0).
        motion_intensity: Controls motion rule threshold (0.0-1.0).
        visual_density: Controls layout density threshold (0.0-1.0).
        sensitivity: Max adjustment factor for thresholds (default 0.3 = ±30%).
    """

    design_variance: float = DEFAULT_DIAL
    motion_intensity: float = DEFAULT_DIAL
    visual_density: float = DEFAULT_DIAL
    sensitivity: float = DEFAULT_SENSITIVITY

    def __post_init__(self) -> None:
        """Clamp all dial values to valid range [0.0, 1.0]."""
        self.design_variance = self._clamp(self.design_variance)
        self.motion_intensity = self._clamp(self.motion_intensity)
        self.visual_density = self._clamp(self.visual_density)
        # Sensitivity should be positive and reasonable (0-1)
        if self.sensitivity < 0:
            self.sensitivity = 0.0
        elif self.sensitivity > 1.0:
            self.sensitivity = 1.0

    @staticmethod
    def _clamp(value: float) -> float:
        """Clamp a value to [MIN_DIAL, MAX_DIAL].

        Args:
            value: Input value to clamp.

        Returns:
            Value clamped to [0.0, 1.0].
        """
        if value < MIN_DIAL:
            return MIN_DIAL
        if value > MAX_DIAL:
            return MAX_DIAL
        return value

    @property
    def is_default(self) -> bool:
        """Check if all dials are at default values (no adjustment).

        Returns:
            True if all dials are 0.5 and sensitivity is default.
        """
        return (
            self.design_variance == DEFAULT_DIAL
            and self.motion_intensity == DEFAULT_DIAL
            and self.visual_density == DEFAULT_DIAL
        )

    def adjust_threshold(
        self,
        rule_id: str,
        base_threshold: float,
    ) -> float:
        """Adjust an audit threshold based on dial values.

        The adjustment maps dial values to a multiplier:
          - dial=0.5 → multiplier=1.0 (no change)
          - dial=1.0 → multiplier=1+sensitivity (relax, e.g. 1.3)
          - dial=0.0 → multiplier=1-sensitivity (tighten, e.g. 0.7)

        The rule_id determines which dial applies:
          - Rules containing "density" or "layout" → visual_density dial
          - Rules containing "motion" or "animation" → motion_intensity dial
          - Rules containing "variance" or "consistency" → design_variance dial
          - Other rules → no adjustment (return base_threshold)

        Args:
            rule_id: Identifier of the rule (e.g. "layout_element_count").
            base_threshold: Base threshold value before adjustment.

        Returns:
            Adjusted threshold value.
        """
        dial_value = self._get_dial_for_rule(rule_id)
        if dial_value is None:
            return base_threshold

        multiplier = 1.0 + (dial_value - DEFAULT_DIAL) * 2 * self.sensitivity
        return base_threshold * multiplier

    def _get_dial_for_rule(self, rule_id: str) -> float | None:
        """Determine which dial applies to a given rule.

        Args:
            rule_id: Rule identifier string.

        Returns:
            Dial value if a matching dial exists, None otherwise.
        """
        rule_lower = rule_id.lower()
        if any(kw in rule_lower for kw in ("density", "layout", "spacing", "grid")):
            return self.visual_density
        if any(kw in rule_lower for kw in ("motion", "animation", "transition")):
            return self.motion_intensity
        if any(kw in rule_lower for kw in ("variance", "consistency", "uniform")):
            return self.design_variance
        return None

    def to_prompt_fragment(self) -> str:
        """Generate a human-readable description of current dial settings.

        Returns:
            Descriptive string for inclusion in audit reports.
        """
        if self.is_default:
            return "Taste Dials: default (no adjustment)"

        parts: list[str] = []
        if self.design_variance != DEFAULT_DIAL:
            level = "high" if self.design_variance > DEFAULT_DIAL else "low"
            parts.append(f"variance={level}({self.design_variance:.2f})")
        if self.motion_intensity != DEFAULT_DIAL:
            level = "high" if self.motion_intensity > DEFAULT_DIAL else "low"
            parts.append(f"motion={level}({self.motion_intensity:.2f})")
        if self.visual_density != DEFAULT_DIAL:
            level = "high" if self.visual_density > DEFAULT_DIAL else "low"
            parts.append(f"density={level}({self.visual_density:.2f})")
        return f"Taste Dials: {', '.join(parts)}"

    def to_dict(self) -> dict[str, Any]:
        """Serialize dials to a dictionary.

        Returns:
            Dictionary with all dial values and sensitivity.
        """
        return {
            "design_variance": self.design_variance,
            "motion_intensity": self.motion_intensity,
            "visual_density": self.visual_density,
            "sensitivity": self.sensitivity,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TasteDials:
        """Create TasteDials from a dictionary.

        Args:
            data: Dictionary with dial values.

        Returns:
            TasteDials instance.
        """
        return cls(
            design_variance=data.get("design_variance", DEFAULT_DIAL),
            motion_intensity=data.get("motion_intensity", DEFAULT_DIAL),
            visual_density=data.get("visual_density", DEFAULT_DIAL),
            sensitivity=data.get("sensitivity", DEFAULT_SENSITIVITY),
        )


# Preset configurations for common use cases
PRESETS: dict[str, dict[str, float]] = {
    "minimalist": {
        "design_variance": 0.2,  # low variance = uniform
        "motion_intensity": 0.2,  # low motion = static
        "visual_density": 0.3,  # low density = spacious
    },
    "balanced": {
        "design_variance": 0.5,
        "motion_intensity": 0.5,
        "visual_density": 0.5,
    },
    "rich": {
        "design_variance": 0.8,  # high variance = diverse
        "motion_intensity": 0.7,  # high motion = animated
        "visual_density": 0.7,  # high density = compact
    },
}


def create_preset(name: str) -> TasteDials:
    """Create a TasteDials instance from a named preset.

    Args:
        name: Preset name ("minimalist", "balanced", "rich").

    Returns:
        TasteDials instance with preset values.

    Raises:
        KeyError: If preset name is not found.
    """
    if name not in PRESETS:
        raise KeyError(f"Unknown preset: {name}. Available: {list(PRESETS.keys())}")
    return TasteDials(**PRESETS[name])
