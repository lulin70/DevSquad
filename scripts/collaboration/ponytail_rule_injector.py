"""Ponytail-style minimal implementation rule injector.

Inspired by DietrichGebert/ponytail's ``AGENTS.md`` behavior constraint layer
and the 「懒惰阶梯」 (ladder of laziness) decision model.

This module provides a **static prompt injection** — a "lazy senior developer
manifesto" appended to every Worker's prompt when
``quality_control.minimal_implementation`` is enabled in ``.devsquad.yaml``.

V4.3.0 P1-1 adds lite/full dual-mode support:
    - ``full`` mode (default): 16 red lines, backward compatible with V3.10.0
    - ``lite`` mode: 8 core red lines for test/UI roles
    - ``ultra`` mode is intentionally absent (dead code removed per PRD §3.2)

Mode selection (highest priority first):
    1. ``mode`` argument to :meth:`PonytailRuleInjector.build_injection`
    2. ``mode`` argument to :meth:`PonytailRuleInjector.__init__`
    3. ``quality_control.ponytail_mode`` in ``.devsquad.yaml`` (``"lite"`` | ``"full"``)
    4. Default: ``"full"`` (backward compatible with V3.10.0)

Complement to :mod:`scripts.collaboration.yagni_checker`:
    - ``YagniChecker`` is a **runtime decision tree** that returns a verdict
      (NECESSARY / SKIP / USE_STDLIB / USE_DEPENDENCY / ONE_LINER / MINIMAL)
      for a specific micro-task.
    - ``PonytailRuleInjector`` is a **static behavior rule** injected into the
      prompt so the LLM internalizes the lazy-by-default mindset before
      generating any output.

Spec reference: docs/prd/V4.3.0_PRD.md §3.2 (P1-1)
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

# V4.3.0 P1-1: Lite mode ruleset — 8 core red lines for test/UI roles.
# Collapses the "never skip" list into a single red line to keep the
# injection short for roles that do not produce production code.
PONYTAIL_RULES_LITE = """\
## Minimal Implementation Rules (Ponytail — Lite)

You are a lazy senior developer. Lazy means efficient, not careless.
Before producing any output, stop at the first rung that holds:

1. Does this need to be built at all? (YAGNI)
2. Does it already exist in this codebase? Reuse it.
3. Does the standard library already do this? Use it.
4. Does a native platform feature cover it? Use it.
5. Does an already-installed dependency solve it? Use it.
6. Can this be one line? Make it one line.
7. Only then: write the minimum code/doc that works.

Never skip (red line): input validation, error handling that prevents
data loss, security, accessibility, anything explicitly requested by
the user.
"""

# V4.3.0 P1-1: 16 red lines for full mode (backward compatible with the
# original PONYTAIL_RULES content). Each red line has a stable ID
# (RL-01..RL-16) so violations can be reported unambiguously.
# Composition: 7 ladder rungs + 4 "Rules:" + 5 "Not lazy about" = 16.
PONYTAIL_RED_LINES: tuple[str, ...] = (
    # 7 ladder rungs (YAGNI essentials)
    "RL-01: YAGNI — does this need to be built at all?",
    "RL-02: Reuse existing code in this codebase.",
    "RL-03: Use the standard library.",
    "RL-04: Use native platform features.",
    "RL-05: Use already-installed dependencies.",
    "RL-06: Make it one line if possible.",
    "RL-07: Write the minimum code/doc that works.",
    # 4 "Rules:" section
    "RL-08: No abstractions that weren't explicitly requested.",
    "RL-09: No new dependency if it can be avoided.",
    "RL-10: Deletion over addition. Boring over clever. Fewest files possible.",
    "RL-11: Mark intentional simplifications with a `ponytail:` comment.",
    # 5 "Not lazy about" section (never skip)
    "RL-12: Input validation at trust boundaries.",
    "RL-13: Error handling that prevents data loss.",
    "RL-14: Security.",
    "RL-15: Accessibility.",
    "RL-16: Anything explicitly requested by the user.",
)

# V4.3.0 P1-1: 8 core red lines for lite mode. The 7 ladder rungs plus
# one collapsed "never skip" red line (RL-12 aggregates the 5 never-skip
# items into a single essential red line).
PONYTAIL_RED_LINES_LITE: tuple[str, ...] = (
    "RL-01: YAGNI — does this need to be built at all?",
    "RL-02: Reuse existing code in this codebase.",
    "RL-03: Use the standard library.",
    "RL-04: Use native platform features.",
    "RL-05: Use already-installed dependencies.",
    "RL-06: Make it one line if possible.",
    "RL-07: Write the minimum code/doc that works.",
    "RL-12: Never skip input validation, error handling, security, "
    "accessibility, or explicitly requested items.",
)

# V4.3.0 P1-1: Supported modes. ``ultra`` is intentionally absent — it was
# dead code removed per PRD §3.2 P1-1.
_SUPPORTED_MODES: tuple[str, ...] = ("lite", "full")

# Simple violation indicator patterns for :meth:`check_red_line_violation`.
# Maps red line ID → tuple of lowercase phrases that indicate a violation.
# Intentionally minimal (YAGNI) — this is a heuristic nudge, not a lint
# system. Only red lines that can be detected via simple substring match
# are included; structural red lines (e.g., YAGNI) are not checkable here.
_VIOLATION_PATTERNS: dict[str, tuple[str, ...]] = {
    "RL-12": ("skip input validation", "no input validation", "ignore validation"),
    "RL-13": ("swallow exceptions", "ignore errors", "pass on error"),
    "RL-14": ("skip security", "ignore security", "no security check"),
    "RL-15": ("skip accessibility", "ignore a11y", "no accessibility"),
    "RL-16": ("skip user request", "ignore explicit request"),
}


class PonytailRuleInjector:
    """Injects ponytail-style minimal implementation rules into prompts.

    Reads configuration from the ``quality_control`` section of
    ``.devsquad.yaml`` and produces the injection text. Supports lite/full
    dual modes per V4.3.0 P1-1.

    Usage::

        injector = PonytailRuleInjector(qc_config)
        text = injector.build_injection()
        if text:
            prompt += text

    Mode selection (highest priority first):
        1. ``mode`` argument to :meth:`build_injection`
        2. ``mode`` argument to :meth:`__init__`
        3. ``quality_control.ponytail_mode`` in config (``"lite"`` | ``"full"``)
        4. Default: ``"full"`` (backward compatible with V3.10.0)
    """

    def __init__(
        self,
        qc_config: dict[str, Any] | None = None,
        mode: str | None = None,
    ) -> None:
        """Initialize the injector with QC configuration and optional mode.

        Args:
            qc_config: The ``quality_control`` config dict from
                ``.devsquad.yaml``. If ``None``, defaults to disabled.
            mode: Optional mode override (``"lite"`` or ``"full"``). If
                ``None``, falls back to ``qc_config["quality_control"]
                ["ponytail_mode"]``, then to ``"full"``.

        Raises:
            ValueError: If ``mode`` is not ``"lite"`` or ``"full"``.
        """
        self._qc_config = qc_config or {}
        qc = self._qc_config.get("quality_control", {})
        self._enabled: bool = qc.get("minimal_implementation", False)
        self._markers: bool = qc.get("ponytail_markers", True)
        # Resolve mode: explicit param > config > default "full".
        configured_mode = qc.get("ponytail_mode", "full")
        self._mode = mode if mode is not None else configured_mode
        if self._mode not in _SUPPORTED_MODES:
            raise ValueError(
                f"Unsupported ponytail_mode: {self._mode!r}. "
                f"Supported: {_SUPPORTED_MODES}"
            )

    @property
    def enabled(self) -> bool:
        """Whether ponytail minimal-implementation rules are enabled."""
        return self._enabled

    @property
    def markers_enabled(self) -> bool:
        """Whether ``ponytail:`` comment markers are enabled."""
        return self._markers

    @property
    def mode(self) -> str:
        """Active ponytail mode (``"lite"`` or ``"full"``)."""
        return self._mode

    @property
    def red_lines(self) -> tuple[str, ...]:
        """Red lines for the active mode (8 for lite, 16 for full)."""
        return (
            PONYTAIL_RED_LINES_LITE if self._mode == "lite" else PONYTAIL_RED_LINES
        )

    def build_injection(self, mode: str | None = None) -> str:
        """Build the ponytail rule injection text.

        Args:
            mode: Optional mode override (``"lite"`` or ``"full"``). If
                ``None``, uses the mode resolved in :meth:`__init__`.

        Returns:
            The injection text, or empty string if disabled.

        Raises:
            ValueError: If ``mode`` is not ``"lite"`` or ``"full"``.
        """
        if not self._enabled:
            return ""
        active_mode = self._resolve_mode(mode)
        rules_text = (
            PONYTAIL_RULES_LITE if active_mode == "lite" else PONYTAIL_RULES
        )
        parts = [rules_text]
        if not self._markers:
            parts.append(
                "(Note: `ponytail:` markers are disabled in config; "
                "do not add them to output.)"
            )
        return "\n".join(parts)

    def _resolve_mode(self, mode: str | None) -> str:
        """Resolve the effective mode, validating overrides.

        Args:
            mode: Optional mode override. If ``None``, uses ``self._mode``.

        Returns:
            The resolved mode (``"lite"`` or ``"full"``).

        Raises:
            ValueError: If ``mode`` is not a supported value.
        """
        if mode is None:
            return self._mode
        if mode not in _SUPPORTED_MODES:
            raise ValueError(
                f"Unsupported ponytail mode: {mode!r}. "
                f"Supported: {_SUPPORTED_MODES}"
            )
        return mode

    def check_red_line_violation(self, content: str) -> list[str]:
        """Check content for red line violations (simple heuristic).

        Scans ``content`` for lowercase phrases that indicate a red line
        is being violated (e.g., "skip input validation" → RL-12). Only
        red lines active in the current mode are checked.

        Args:
            content: The content to check (e.g., LLM-generated code or text).

        Returns:
            List of violated red line IDs (e.g., ``["RL-12", "RL-14"]``).
            Empty list if no violations detected.

        Example:
            >>> injector = PonytailRuleInjector(
            ...     {"quality_control": {"minimal_implementation": True}})
            >>> injector.check_red_line_violation("let's skip input validation")
            ['RL-12']
        """
        if not content:
            return []
        lowered = content.lower()
        active_ids = {line.split(":", 1)[0] for line in self.red_lines}
        violations: list[str] = []
        for red_line_id, patterns in _VIOLATION_PATTERNS.items():
            if red_line_id not in active_ids:
                continue
            if any(pattern in lowered for pattern in patterns):
                violations.append(red_line_id)
        return violations

    def is_enabled(self) -> bool:
        """Backward-compatible alias for :attr:`enabled`."""
        return self._enabled
