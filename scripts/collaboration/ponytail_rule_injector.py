"""Ponytail-style minimal implementation rule injector.

Inspired by DietrichGebert/ponytail's ``AGENTS.md`` behavior constraint layer
and the 「懒惰阶梯」 (ladder of laziness) decision model.

This module provides a **static prompt injection** — a "lazy senior developer
manifesto" appended to every Worker's prompt when
``quality_control.minimal_implementation`` is enabled in ``.devsquad.yaml``.

Complement to :mod:`scripts.collaboration.yagni_checker`:
    - ``YagniChecker`` is a **runtime decision tree** that returns a verdict
      (NECESSARY / SKIP / USE_STDLIB / USE_DEPENDENCY / ONE_LINER / MINIMAL)
      for a specific micro-task.
    - ``PonytailRuleInjector`` is a **static behavior rule** injected into the
      prompt so the LLM internalizes the lazy-by-default mindset before
      generating any output.

Spec reference: docs/spec/v3.10.0_spec.md §5.2
"""

from __future__ import annotations

from typing import Any

PONYTAIL_RULES = """\
## Minimal Implementation Rules (Ponytail)

You are a lazy senior developer. Lazy means efficient, not careless.
Before producing any output, stop at the first rung that holds:

1. Does this need to be built at all? (YAGNI)
2. Does it already exist in this codebase? Reuse it.
3. Does the standard library already do this? Use it.
4. Does a native platform feature cover it? Use it.
5. Does an already-installed dependency solve it? Use it.
6. Can this be one line? Make it one line.
7. Only then: write the minimum code/doc that works.

Rules:
- No abstractions that weren't explicitly requested.
- No new dependency if it can be avoided.
- Deletion over addition. Boring over clever. Fewest files possible.
- Mark intentional simplifications with a `ponytail:` comment.

Not lazy about (never skip these):
- Input validation at trust boundaries
- Error handling that prevents data loss
- Security
- Accessibility
- Anything explicitly requested by the user
"""


class PonytailRuleInjector:
    """Injects ponytail-style minimal implementation rules into prompts.

    Reads configuration from the ``quality_control`` section of
    ``.devsquad.yaml`` and produces the injection text.

    Usage::

        injector = PonytailRuleInjector(qc_config)
        text = injector.build_injection()
        if text:
            prompt += text
    """

    def __init__(self, qc_config: dict[str, Any] | None = None) -> None:
        """Initialize the injector with QC configuration.

        Args:
            qc_config: The ``quality_control`` config dict from
                ``.devsquad.yaml``. If ``None``, defaults to disabled.
        """
        self._qc_config = qc_config or {}
        qc = self._qc_config.get("quality_control", {})
        self._enabled: bool = qc.get("minimal_implementation", False)
        self._markers: bool = qc.get("ponytail_markers", True)

    @property
    def enabled(self) -> bool:
        """Whether ponytail minimal-implementation rules are enabled."""
        return self._enabled

    @property
    def markers_enabled(self) -> bool:
        """Whether ``ponytail:`` comment markers are enabled."""
        return self._markers

    def build_injection(self) -> str:
        """Build the ponytail rule injection text.

        Returns:
            The injection text, or empty string if disabled.
        """
        if not self._enabled:
            return ""
        parts = [PONYTAIL_RULES]
        if not self._markers:
            parts.append(
                "(Note: `ponytail:` markers are disabled in config; "
                "do not add them to output.)"
            )
        return "\n".join(parts)

    def is_enabled(self) -> bool:
        """Backward-compatible alias for :attr:`enabled`."""
        return self._enabled
