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

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

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
    base_url = os.environ.get(cfg["base_url_env"], cfg["default_base_url"]).rstrip("/")
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
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            latency = (time.time() - start) * 1000.0
            try:
                data = json.loads(body) if body else {}
                # Provider-specific response parsing
                if isinstance(data, dict) and "data" in data:
                    raw_models = data.get("data", [])
                    models = [
                        str(m.get("id", m.get("name", m)))
                        if isinstance(m, dict)
                        else str(m)
                        for m in raw_models
                    ]
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


def format_json(reports: list[ProviderReport]) -> str:
    """Format reports as JSON."""
    return json.dumps(
        {"version": "V4.5.2", "reports": [r.to_dict() for r in reports]},
        indent=2,
        ensure_ascii=False,
    )


def cmd_doctor(args: Any) -> int:
    """CLI entry point for `devsquad doctor`.

    Args:
        args: argparse Namespace with `provider` and `format` attributes.

    Returns:
        Exit code (0 on success).
    """
    fmt = getattr(args, "format", "text")
    provider = getattr(args, "provider", "all")
    timeout = getattr(args, "timeout", 5.0)

    reports = (
        diagnose_all(timeout)
        if provider == "all"
        else [diagnose_provider(provider, timeout)]
    )

    if fmt == "json":
        print(format_json(reports))
    else:
        print(format_text(reports))

    # Non-zero exit if any provider is configured but unreachable
    if any(r.configured and not r.reachable for r in reports):
        return 1
    return 0
