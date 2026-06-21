"""Unified secret/sensitive data detection patterns.

This module provides shared regex patterns for detecting secrets, API keys,
passwords, and other sensitive data across the codebase. Previously duplicated
in 4 modules: review_checkers, content_cache, tech_debt_manager, audit_logger.

Usage:
    from scripts.collaboration.secret_patterns import SECRET_PATTERNS, is_sensitive

    if is_sensitive(text):
        # Skip caching or mask output
        ...
"""

import re

# --- Compiled patterns for secret detection ---

# API key patterns (OpenAI, GitHub, AWS, generic)
SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("openai_api_key", re.compile(r"sk-[a-zA-Z0-9]{20,}")),
    ("github_token", re.compile(r"ghp_[a-zA-Z0-9]{36,}")),
    ("aws_access_key", re.compile(r"(?i)\bAKIA[0-9A-Z]{16}\b")),
    ("aws_secret_key", re.compile(r"(?i)\baws[_-]?secret[_-]?access[_-]?key\b\s*[:=]\s*\S+")),
    ("generic_api_key", re.compile(r"(?i)\b(api[_-]?key|apikey)\b\s*[:=]\s*['\"]?[^\s'\"]{8,}")),
    ("password", re.compile(r"(?i)\b(password|passwd|pwd)\b\s*[:=]\s*['\"]?[^\s'\"]{4,}")),
    ("secret", re.compile(r"(?i)\b(secret|token)\b\s*[:=]\s*['\"]?[^\s'\"]{8,}")),
    ("bearer_token", re.compile(r"(?i)\bBearer\s+[a-zA-Z0-9\-._~+/]+=*")),
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("connection_string", re.compile(r"(?i)(?:mongodb|postgres|redis|amqp)://[^\s]+:[^\s]+@")),
)

# SQL injection patterns (for code review)
SQL_INJECTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("string_concat_query", re.compile(r"(?i)(?:SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER)\b.*\+\s*\w")),
    ("fstring_query", re.compile(r"(?i)(?:SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER)\b.*\{.*\}")),
    ("format_query", re.compile(r"(?i)(?:SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER)\b.*\.format\(")),
    ("percent_query", re.compile(r"(?i)(?:SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER)\b.*%[srdf]")),
)

# Combined pattern for quick "does this text contain anything sensitive?" check
_SENSITIVE_QUICK_CHECK = re.compile(
    r"(?i)"
    r"(?:sk-[a-zA-Z0-9]{20,})"           # OpenAI key
    r"|(?:ghp_[a-zA-Z0-9]{36,})"         # GitHub token
    r"|(?:AKIA[0-9A-Z]{16})"             # AWS access key
    r"|(?:password|passwd|pwd|secret|token|api[_-]?key)\s*[:=]"  # Generic secret assignment
    r"|(?:-----BEGIN.*PRIVATE KEY-----)"  # Private key
)


def is_sensitive(text: str) -> bool:
    """Quick check if text contains any sensitive data.

    Args:
        text: The text to check.

    Returns:
        True if any sensitive pattern is found.
    """
    return bool(_SENSITIVE_QUICK_CHECK.search(text))


def find_secrets(text: str) -> list[tuple[str, str]]:
    """Find all secrets in text.

    Args:
        text: The text to scan.

    Returns:
        List of (pattern_name, matched_value) tuples.
    """
    results: list[tuple[str, str]] = []
    for name, pattern in SECRET_PATTERNS:
        match = pattern.search(text)
        if match:
            results.append((name, match.group(0)))
    return results


def mask_secrets(text: str, mask_char: str = "*") -> str:
    """Mask all secrets in text.

    Args:
        text: The text to mask.
        mask_char: Character to use for masking.

    Returns:
        Text with secrets replaced by mask characters.
    """
    masked = text
    for _, pattern in SECRET_PATTERNS:
        masked = pattern.sub(lambda m: mask_char * len(m.group(0)), masked)
    return masked
