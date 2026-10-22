#!/usr/bin/env python3
"""devsquad doctor — provider connectivity self-check (P12.1.4).

Verifies that configured LLM providers can be reached, measures latency,
and reports the model list. Designed to be the first stop for users
debugging "dispatch returned an error".

Usage:
    devsquad doctor                      # check all configured providers
    devsquad doctor --provider moka      # check only MOKA
    devsquad doctor --provider openai    # check only OpenAI
    devsquad doctor --provider anthropic # check only Anthropic
    devsquad doctor --format json        # JSON output

Detection logic:
    - Provider considered "configured" if its API key env var is set.
    - For configured providers, makes a lightweight API call (e.g. /models)
      with a 5s timeout to verify connectivity.
    - For unconfigured providers, reports "not configured" + fix hint.

This module is intentionally lightweight — it does NOT block the
dispatch pipeline. It is a read-only diagnostic tool.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from scripts.collaboration.cli_command_classifier import CLICommandClassifier

# Provider registry — central place to add new providers
PROVIDERS = {
    "moka": {
        "api_key_env": "MOKA_API_KEY",
        "base_url_env": "MOKA_BASE_URL",
        "default_base_url": "https://api.moka-ai.com/v1",
        "model_list_path": "/models",
        "fix_hint_unconfigured": "Set MOKA_API_KEY environment variable",
    },
    "openai": {
        "api_key_env": "DEVSQUAD_OPENAI_API_KEY",
        "base_url_env": "DEVSQUAD_OPENAI_BASE_URL",
        "default_base_url": "https://api.openai.com/v1",
        "model_list_path": "/models",
        "fix_hint_unconfigured": "Set DEVSQUAD_OPENAI_API_KEY environment variable",
    },
    "anthropic": {
        "api_key_env": "DEVSQUAD_ANTHROPIC_API_KEY",
        "base_url_env": "DEVSQUAD_ANTHROPIC_BASE_URL",
        "default_base_url": "https://api.anthropic.com",
        "model_list_path": "/v1/models",
        "fix_hint_unconfigured": "Set DEVSQUAD_ANTHROPIC_API_KEY environment variable",
    },
}


@dataclass
class ProviderReport:
    """Diagnostic report for a single provider.

    Attributes:
        provider: Provider name (moka/openai/anthropic).
        configured: True if API key env var is set.
        reachable: True if lightweight API call succeeded.
        latency_ms: Round-trip latency in ms (None if not reachable).
        models: List of model names (None if not reachable).
        error: Error message if check failed.
        fix_hint: Human-readable fix suggestion.
    """

    provider: str
    configured: bool
    reachable: bool
    latency_ms: float | None = None
    models: list[str] = field(default_factory=list)
    error: str | None = None
    fix_hint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "configured": self.configured,
            "reachable": self.reachable,
            "latency_ms": self.latency_ms,
            "models": self.models,
            "error": self.error,
            "fix_hint": self.fix_hint,
        }


def _is_configured(provider: str) -> bool:
    """Check if the provider has its API key env var set."""
    if provider not in PROVIDERS:
        return False
    key_env = PROVIDERS[provider]["api_key_env"]
    val = os.environ.get(key_env)
    if val is None:
        return False
    return bool(val.strip())


def _check_connectivity(provider: str, timeout: float = 5.0) -> tuple[bool, float, list[str], str | None]:
    """Make a lightweight API call to verify connectivity.

    Returns:
        (reachable, latency_ms, models, error)
    """
    cfg = PROVIDERS.get(provider)
    if cfg is None:
        return False, 0.0, [], f"Unknown provider: {provider}"

    api_key = os.environ.get(cfg["api_key_env"], "")
    base_url = (os.environ.get(cfg["base_url_env"]) or cfg["default_base_url"]).rstrip("/")
    parsed = urllib.parse.urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False, 0.0, [], "Provider base URL must use http or https"
    url = base_url + cfg["model_list_path"]

    headers: dict[str, str] = {"Accept": "application/json"}
    if provider == "anthropic":
        headers["x-api-key"] = api_key
        headers["anthropic-version"] = "2023-06-01"
    else:
        headers["Authorization"] = f"Bearer {api_key}"

    req = urllib.request.Request(url, headers=headers, method="GET")
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310 - validated provider HTTP(S) URL
            body = resp.read().decode("utf-8")
            latency = (time.time() - start) * 1000.0
            try:
                data = json.loads(body) if body else {}
                # Provider-specific response parsing
                if isinstance(data, dict) and "data" in data:
                    raw_models = data.get("data", [])
                    models = [str(m.get("id", m.get("name", m))) if isinstance(m, dict) else str(m) for m in raw_models]
                elif isinstance(data, list):
                    models = [str(m) for m in data]
                else:
                    models = []
            except json.JSONDecodeError:
                models = []
            return True, latency, models, None
    except urllib.error.HTTPError as exc:
        latency = (time.time() - start) * 1000.0
        return False, latency, [], f"HTTP {exc.code}: {exc.reason}"
    except urllib.error.URLError as exc:
        latency = (time.time() - start) * 1000.0
        return False, latency, [], f"Connection failed: {exc.reason}"
    except (TimeoutError, OSError) as exc:
        latency = (time.time() - start) * 1000.0
        return False, latency, [], f"Timeout: {exc}"


def diagnose_provider(provider: str, timeout: float = 5.0) -> ProviderReport:
    """Run diagnostic check for a single provider.

    Args:
        provider: One of 'moka', 'openai', 'anthropic'.
        timeout: HTTP timeout in seconds.

    Returns:
        ProviderReport with all diagnostic info.
    """
    if provider not in PROVIDERS:
        return ProviderReport(
            provider=provider,
            configured=False,
            reachable=False,
            error=f"Unknown provider: {provider}",
            fix_hint=f"Valid providers: {', '.join(PROVIDERS.keys())}",
        )

    configured = _is_configured(provider)
    if not configured:
        return ProviderReport(
            provider=provider,
            configured=False,
            reachable=False,
            error="API key not configured",
            fix_hint=PROVIDERS[provider]["fix_hint_unconfigured"],
        )

    reachable, latency, models, error = _check_connectivity(provider, timeout)
    return ProviderReport(
        provider=provider,
        configured=True,
        reachable=reachable,
        latency_ms=latency if reachable else None,
        models=models,
        error=error,
        fix_hint=None,
    )


def diagnose_all(timeout: float = 5.0) -> list[ProviderReport]:
    """Diagnose all known providers."""
    return [diagnose_provider(p, timeout) for p in PROVIDERS]


# ---------------------------------------------------------------------------
# Command vocabulary check (P1-E1 wiring: CLICommandClassifier -> doctor)
# ---------------------------------------------------------------------------


def _registered_cli_commands() -> tuple[set[str], dict[str, set[str]]]:
    """Introspect the real CLI registry (same source of truth as the doc_command gate).

    Lazy import because scripts.cli imports this module at load time.

    Returns:
        Tuple of (top-level command names incl. aliases, second-level command
        names keyed by group command, e.g., {"sessions": {"list", "show"}}).
    """
    from scripts.cli import build_parser  # lazy: avoids circular import

    parser = build_parser()
    top: set[str] = set()
    groups: dict[str, set[str]] = {}
    for action in parser._actions:
        if not isinstance(action, argparse._SubParsersAction):
            continue
        for name, sub_parser in action.choices.items():
            top.add(name)
            subs: set[str] = set()
            for sub_action in sub_parser._actions:
                if isinstance(sub_action, argparse._SubParsersAction):
                    subs.update(sub_action.choices.keys())
                elif sub_action.choices and not sub_action.option_strings:
                    subs.update(sub_action.choices)
            if subs:
                groups[name] = subs
    return top, groups


def _locate(command: str, top: set[str], groups: dict[str, set[str]]) -> str:
    """Describe where a command is registered (top-level or group subcommands)."""
    if command in top:
        return "top-level"
    owners = [g for g, subs in groups.items() if command in subs]
    return f"subcommand of {'/'.join(owners)}" if owners else "unknown"


def check_command_vocabulary(word: str) -> dict[str, Any]:
    """Check a command word against the DevSquad registry and the impeccable vocabulary.

    E1 wiring (V4.8.0 P1): ``CLICommandClassifier`` was implemented and tested
    but had no production consumer; this function is its wired consumer. It
    answers "did I mistype a command?" with registry facts and category-aware
    suggestions.

    Args:
        word: The command word the user wants to check (e.g., a typo).

    Returns:
        Dict with keys: input, normalized, registered, registered_where,
        category, aligned, suggested_alias, close_matches (list of dicts with
        command/where/category), hint.
    """
    classifier = CLICommandClassifier()
    normalized = word.strip().lower()
    top, groups = _registered_cli_commands()
    all_known: set[str] = set(top)
    for subs in groups.values():
        all_known.update(subs)

    classification = classifier.classify(normalized)
    registered = normalized in all_known

    located_matches: list[dict[str, Any]] = []
    if not registered:
        for match in difflib.get_close_matches(normalized, sorted(all_known), n=3, cutoff=0.6):
            category = str(classifier.classify(match)["category"])
            located_matches.append(
                {
                    "command": match,
                    "where": _locate(match, top, groups),
                    "category": category if category != "unknown" else None,
                }
            )

    where = _locate(normalized, top, groups) if registered else None

    if registered:
        hint = f"'{normalized}' is a registered command ({where}); run `devsquad {normalized} --help`"
    elif located_matches:
        best = located_matches[0]
        category_note = f", {best['category']} category" if best["category"] else ""
        hint = f"did you mean '{best['command']}'? ({best['where']}{category_note})"
    else:
        hint = "no similar command found; run `devsquad --help` to list commands"

    return {
        "input": word,
        "normalized": normalized,
        "registered": registered,
        "registered_where": where,
        "category": classification["category"],
        "aligned": classification["aligned"],
        "suggested_alias": classification["suggested_alias"],
        "close_matches": located_matches,
        "hint": hint,
    }


def format_command_section(check: dict[str, Any]) -> str:
    """Format a command vocabulary check as a human-readable text block."""
    lines: list[str] = ["[COMMAND VOCABULARY]"]
    lines.append(f"  Input:      '{check['input']}'")
    if check["registered"]:
        lines.append(f"  Registered: ✓ {check['registered_where']} command")
        if check["category"] != "unknown":
            lines.append(f"  Category:   {check['category']}")
        aligned = "✓ in impeccable vocabulary" if check["aligned"] else "✗ not in impeccable vocabulary"
        lines.append(f"  Aligned:    {aligned}")
        if check["suggested_alias"]:
            lines.append(f"  Alias hint: suggested impeccable alias: '{check['suggested_alias']}'")
    else:
        lines.append("  Registered: ✗ not a DevSquad command")
        if check["close_matches"]:
            for m in check["close_matches"]:
                category_note = f", {m['category']} category" if m["category"] else ""
                lines.append(f"  Closest:    {m['command']} ({m['where']}{category_note})")
        else:
            lines.append("  Closest:    (none)")
    lines.append(f"  Hint:       {check['hint']}")
    return "\n".join(lines)


def format_text(reports: list[ProviderReport]) -> str:
    """Format reports as a human-readable text table."""
    lines: list[str] = []
    lines.append("=" * 78)
    lines.append("DevSquad Doctor — Provider Connectivity Check")
    lines.append("=" * 78)
    for r in reports:
        lines.append("")
        lines.append(f"[{r.provider.upper()}]")
        status_config = "✓ configured" if r.configured else "✗ NOT configured"
        lines.append(f"  Configured: {status_config}")
        if r.configured:
            status_reach = f"✓ reachable ({r.latency_ms:.0f}ms)" if r.reachable else "✗ unreachable"
            lines.append(f"  Reachable:  {status_reach}")
            if r.reachable and r.models:
                lines.append(f"  Models:     {len(r.models)} available")
                for m in r.models[:5]:  # show first 5
                    lines.append(f"               - {m}")
                if len(r.models) > 5:
                    lines.append(f"               ... and {len(r.models) - 5} more")
            if r.error:
                lines.append(f"  Error:      {r.error}")
        if r.fix_hint:
            lines.append(f"  Fix:        {r.fix_hint}")
    lines.append("")
    lines.append("=" * 78)
    return "\n".join(lines)


def format_json(reports: list[ProviderReport], command_check: dict[str, Any] | None = None) -> str:
    """Format reports (and optional command vocabulary check) as JSON."""
    payload: dict[str, Any] = {"version": "V4.5.2", "reports": [r.to_dict() for r in reports]}
    if command_check is not None:
        payload["command_vocabulary"] = command_check
    return json.dumps(
        payload,
        indent=2,
        ensure_ascii=False,
    )


def cmd_doctor(args: Any) -> int:
    """CLI entry point for `devsquad doctor`.

    Args:
        args: argparse Namespace with `provider`, `format`, `timeout`, and
            optional `command` attributes.

    Returns:
        Exit code (0 on success).
    """
    fmt = getattr(args, "format", "text")
    provider = getattr(args, "provider", "all")
    timeout = getattr(args, "timeout", 5.0)
    command_word = getattr(args, "command_word", None)

    reports = diagnose_all(timeout) if provider == "all" else [diagnose_provider(provider, timeout)]
    command_check = check_command_vocabulary(command_word) if command_word is not None else None

    if fmt == "json":
        print(format_json(reports, command_check))
    else:
        print(format_text(reports))
        if command_check is not None:
            print()
            print(format_command_section(command_check))

    # Non-zero exit if any provider is configured but unreachable
    if any(r.configured and not r.reachable for r in reports):
        return 1
    return 0
