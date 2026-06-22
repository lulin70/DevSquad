#!/usr/bin/env python3
"""
PromptDials — Three-dimension prompt tuning.

Inspired by Leonxlnx/taste-skill's VARIANCE/MOTION/DENSITY dials.
Provides more intuitive prompt control than the existing 3-variant system
(``concise``/``balanced``/``detailed``) in :mod:`prompt_assembler`.

Three dials (each 1-5, default 3):
  - VERBOSITY: 1=terse, 3=balanced, 5=exhaustive
  - CREATIVITY: 1=conservative, 3=balanced, 5=innovative
  - RISK_TOLERANCE: 1=safest, 3=balanced, 5=aggressive

Backward compatible:
  - ``variant="concise"``  → ``(1, 3, 3)``
  - ``variant="balanced"`` → ``(3, 3, 3)``
  - ``variant="detailed"`` → ``(5, 3, 3)``

Integration
-----------
:meth:`PromptDials.from_variant` converts a legacy variant string.
:meth:`PromptDials.to_variant` converts back to the closest variant.
:meth:`PromptDials.apply_to_prompt` prepends the fragment to any prompt,
making it compatible with :class:`prompt_assembler.PromptAssembler`.

Usage::

    from scripts.collaboration.prompt_dials import PromptDials

    dials = PromptDials(verbosity=2, creativity=4, risk_tolerance=3)
    fragment = dials.to_prompt_fragment()
    prompt = dials.apply_to_prompt("Design the auth module.")
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["PromptDials"]


@dataclass
class PromptDials:
    """Three-dimension prompt tuning dials.

    Attributes
    ----------
    verbosity:
        1=terse, 3=balanced, 5=exhaustive. Clamped to [1, 5].
    creativity:
        1=conservative, 3=balanced, 5=innovative. Clamped to [1, 5].
    risk_tolerance:
        1=safest, 3=balanced, 5=aggressive. Clamped to [1, 5].
    """

    verbosity: int = 3
    creativity: int = 3
    risk_tolerance: int = 3

    def __post_init__(self) -> None:
        # Clamp values to 1-5.
        self.verbosity = max(1, min(5, self.verbosity))
        self.creativity = max(1, min(5, self.creativity))
        self.risk_tolerance = max(1, min(5, self.risk_tolerance))

    # ------------------------------------------------------------------
    # Backward compatibility with the 3-variant system
    # ------------------------------------------------------------------

    @classmethod
    def from_variant(cls, variant: str) -> PromptDials:
        """Backward compat: convert variant string to dials.

        Mapping:
          - ``"concise"``  → ``(1, 3, 3)``
          - ``"balanced"`` → ``(3, 3, 3)``
          - ``"detailed"`` → ``(5, 3, 3)``
          - any other value → ``(3, 3, 3)`` (balanced default)
        """
        mapping: dict[str, PromptDials] = {
            "concise": cls(verbosity=1, creativity=3, risk_tolerance=3),
            "balanced": cls(verbosity=3, creativity=3, risk_tolerance=3),
            "detailed": cls(verbosity=5, creativity=3, risk_tolerance=3),
        }
        return mapping.get(variant, cls())  # default balanced

    def to_variant(self) -> str:
        """Convert dials back to the closest legacy variant string.

        Returns
        -------
        str
            One of ``"concise"``/``"balanced"``/``"detailed"``.
            Non-default creativity/risk_tolerance always maps to ``"balanced"``
            (no legacy equivalent).
        """
        # Only map back when creativity and risk are at default.
        if self.creativity != 3 or self.risk_tolerance != 3:
            return "balanced"
        if self.verbosity <= 1:
            return "concise"
        if self.verbosity >= 5:
            return "detailed"
        return "balanced"

    # ------------------------------------------------------------------
    # Prompt fragment generation
    # ------------------------------------------------------------------

    def to_prompt_fragment(self) -> str:
        """Generate prompt fragment based on dial values.

        Returns
        -------
        str
            A space-joined instruction string covering all three dials.
            Empty string when all dials are at default (3, 3, 3) —
            callers can use :attr:`is_default` to skip injection.
        """
        if self.is_default:
            return ""

        parts: list[str] = []
        parts.append(self._verbosity_fragment())
        parts.append(self._creativity_fragment())
        parts.append(self._risk_fragment())
        return " ".join(p for p in parts if p)

    def _verbosity_fragment(self) -> str:
        if self.verbosity <= 1:
            return "Be terse. Use minimal code. No explanations."
        if self.verbosity == 2:
            return "Be concise. Minimal explanations, only when essential."
        if self.verbosity == 3:
            return "Be balanced. Explain key decisions briefly."
        if self.verbosity == 4:
            return "Be detailed. Explain decisions and trade-offs."
        return "Be exhaustive. Full explanations, all trade-offs, all edge cases."

    def _creativity_fragment(self) -> str:
        if self.creativity <= 1:
            return "Use only established, conventional patterns."
        if self.creativity == 2:
            return "Prefer proven solutions; consider minor variations."
        if self.creativity == 3:
            return "Balance conventional and creative approaches."
        if self.creativity == 4:
            return "Explore multiple approaches including non-traditional ones."
        return "Explore 3+ approaches including non-traditional ones. Be innovative."

    def _risk_fragment(self) -> str:
        if self.risk_tolerance <= 1:
            return "Use only battle-tested, proven solutions. Avoid all risk."
        if self.risk_tolerance == 2:
            return "Prefer safe, well-tested solutions."
        if self.risk_tolerance == 3:
            return "Balance safety and pragmatism."
        if self.risk_tolerance == 4:
            return "Accept calculated risks for significant gains."
        return "Be aggressive. Optimize for impact, accept higher risk."

    # ------------------------------------------------------------------
    # Application helpers
    # ------------------------------------------------------------------

    def apply_to_prompt(self, prompt: str) -> str:
        """Prepend the dial fragment to an existing prompt.

        If all dials are at default, the prompt is returned unchanged.

        Parameters
        ----------
        prompt:
            The original prompt text.

        Returns
        -------
        str
            ``"<fragment>\\n\\n<prompt>"`` when dials are non-default,
            otherwise ``prompt`` unchanged.
        """
        fragment = self.to_prompt_fragment()
        if not fragment:
            return prompt
        return f"{fragment}\n\n{prompt}"

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_default(self) -> bool:
        """True if all dials are at default (3, 3, 3)."""
        return (
            self.verbosity == 3
            and self.creativity == 3
            and self.risk_tolerance == 3
        )
