#!/usr/bin/env python3
"""Deterministic rule resolution — V4.5.20 W1-1 (contract C4–C7).

Spec: ``docs/reference/DETERMINISTIC_CONTRACT.md`` §5. The module answers one
question — *which rule applies to this path, and from which layer* — for the
review pipeline (E1) and for the ``rules check`` explainer (E2).

The contract pins down four properties this module must not lose:

* Layers are tried CLI → project → user → system, and the first match wins.
  Nothing is merged (C4, C5).
* The system layer ends in a catch-all, so resolution always returns a rule and
  there is no "no rule found" state (C6).
* Sensitive paths resolve *before* any of those layers and cannot be overridden
  by them, including via ``include`` (C7). The pattern set below is hardcoded on
  purpose: the project-level and user-level rule files are exactly the attack
  surfaces the guard exists to constrain, so their content may not define it.
* Absence of a layer is silent; a layer that exists but will not parse is not.

``Resolution`` carries ``layer`` / ``pattern`` / ``body`` — the three things W1-2
prints.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

LAYER_SECURITY = "security"
LAYER_CLI = "cli"
LAYER_PROJECT = "project"
LAYER_USER = "user"
LAYER_SYSTEM = "system"

SECURITY_GATE = "secret_exclude"
SYSTEM_RULES_FILENAME = "system_rules.json"
_HARDCODED_ORIGIN = "<hardcoded>"

# The sensitive-path globs behind C1. A code constant rather than configuration
# (C7): a guard that a local file can rewrite is not a guard.
SECURITY_PATH_PATTERNS: tuple[str, ...] = (
    "**/.env",
    "**/.env.*",
    "**/*.pem",
    "**/*.key",
    "**/*.p12",
    "**/*.pfx",
    "**/*.jks",
    "**/id_rsa",
    "**/id_dsa",
    "**/id_ecdsa",
    "**/id_ed25519",
    "**/.netrc",
    "**/.npmrc",
    "**/.pypirc",
    "**/.git-credentials",
    "**/.aws/credentials",
    "**/.ssh/**",
    "**/credentials.json",
    "**/service-account*.json",
)


class RuleConfigError(Exception):
    """A rule file is present but unreadable or malformed.

    Absence of a layer is normal and silent (C4); a corrupt one is not, because
    silently skipping it would drop the caller's rules and say nothing.
    """


@dataclass(frozen=True)
class Rule:
    """One rule: a glob plus a body owned by whoever wrote the layer."""

    pattern: str
    body: Mapping[str, Any]

    @classmethod
    def from_dict(cls, payload: Any, origin: Path) -> Rule:
        """Build a rule from one JSON entry, or raise :class:`RuleConfigError`."""
        if not isinstance(payload, dict) or not isinstance(payload.get("pattern"), str):
            raise RuleConfigError(f"{origin}: every rule needs a string 'pattern'")
        body = payload.get("body", {})
        if not isinstance(body, dict):
            raise RuleConfigError(f"{origin}: 'body' must be a JSON object")
        return cls(pattern=payload["pattern"], body=body)


@dataclass(frozen=True)
class RuleSources:
    """Where each layer lives. Only the system layer is always present (C6)."""

    cli: Path | None = None
    project: Path | None = None
    user: Path | None = None
    system: Path = field(default_factory=lambda: Path(__file__).with_name(SYSTEM_RULES_FILENAME))


@dataclass(frozen=True)
class Resolution:
    """The winning rule, plus enough context to explain *why* it won."""

    path: str
    layer: str
    origin: str
    pattern: str
    body: Mapping[str, Any]


def default_sources(repo_root: Path | str | None = None, cli_rule: Path | str | None = None) -> RuleSources:
    """Return the layer paths for a normal run; ``repo_root`` defaults to the CWD."""
    root = Path(repo_root) if repo_root is not None else Path.cwd()
    return RuleSources(
        cli=Path(cli_rule) if cli_rule is not None else None,
        project=root / ".devsquad" / "rule.json",
        user=Path.home() / ".devsquad" / "rule.json",
    )


def matches(path: str, pattern: str) -> bool:
    """Match ``path`` against one glob.

    ``pathlib`` semantics (right-anchored), plus one extension: a leading ``**/``
    may also match zero directories, so ``**/*.py`` covers a top-level file too.
    """
    candidate = PurePosixPath(path)
    if candidate.match(pattern):
        return True
    return pattern.startswith("**/") and candidate.match(pattern[3:])


def load_rules(origin: Path | None) -> tuple[Rule, ...]:
    """Read one layer, returning ``()`` when the file is absent (C4)."""
    if origin is None or not origin.is_file():
        return ()
    try:
        payload = json.loads(origin.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuleConfigError(f"{origin}: {exc}") from exc
    entries = payload.get("rules") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        raise RuleConfigError(f"{origin}: expected a JSON object with a 'rules' list")
    return tuple(Rule.from_dict(entry, origin) for entry in entries)


def security_resolution(path: str) -> Resolution | None:
    """Return the hardcoded sensitive-path verdict for ``path``, if any (C7)."""
    for pattern in SECURITY_PATH_PATTERNS:
        if matches(path, pattern):
            return Resolution(
                path=path,
                layer=LAYER_SECURITY,
                origin=_HARDCODED_ORIGIN,
                pattern=pattern,
                body={"gate": SECURITY_GATE, "reason": "sensitive path"},
            )
    return None


def resolve(path: str, sources: RuleSources | None = None) -> Resolution:
    """Resolve ``path`` to the first matching rule across the four layers.

    Raises:
        RuleConfigError: a layer file is malformed, or the system layer lost its
            catch-all — a packaging bug rather than user error (C6).
    """
    guarded = security_resolution(path)
    if guarded is not None:
        return guarded
    layers = sources or default_sources()
    for layer, origin in (
        (LAYER_CLI, layers.cli),
        (LAYER_PROJECT, layers.project),
        (LAYER_USER, layers.user),
        (LAYER_SYSTEM, layers.system),
    ):
        for rule in load_rules(origin):
            if matches(path, rule.pattern):
                return Resolution(
                    path=path,
                    layer=layer,
                    origin=str(origin),
                    pattern=rule.pattern,
                    body=rule.body,
                )
    raise RuleConfigError(f"{layers.system}: no rule matched {path!r}; the system layer must end in a catch-all (C6)")
