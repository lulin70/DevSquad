"""OutputValidator — Post-dispatch output safety validator (P1-6 skeleton).

Scans worker outputs / dispatch reports for four classes of risky content
before they are persisted or returned to the caller:

1. **Code injection** — ``eval(``, ``exec(``, ``__import__``, ``os.system``,
   ``subprocess.Popen``, shell metacharacters in unsanitised contexts.
2. **Sensitive information leakage** — API keys (OpenAI/Anthropic/etc.),
   bearer tokens, passwords in assignment form, private IP addresses,
   internal URLs.
3. **Path leakage** — absolute POSIX paths (``/etc/``, ``/root/``,
   ``/home/``), Windows absolute paths (``C:\\``), ``~/.ssh/`` and other
   private directory references.
4. **Prompt injection** (V4.2.0 P0-3) — LLM output containing instruction
   hijacking patterns: "ignore previous instructions", "you are now...",
   "system:" role injection, destructive commands. Detects attacks where
   a Worker's LLM output tries to manipulate downstream consumers.

The validator is non-blocking by default: it returns a structured
:class:`OutputValidationResult` listing all findings, and the caller
decides whether to log, warn, or block. Integration into
``PostDispatchPipeline._validate_outputs()`` logs findings at WARNING level
and masks sensitive substrings in the returned report.

This is the **skeleton** (V4.1.2 Phase 2). Full integration with
blocking semantics, configurable thresholds, and per-role policies is
deferred to Phase 3.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Literal

logger = logging.getLogger(__name__)


FindingCategory = Literal["code_injection", "sensitive_info", "path_leak", "prompt_injection"]
FindingSeverity = Literal["low", "medium", "high"]


@dataclass(slots=True)
class OutputFinding:
    """A single risky-content finding in a scanned output.

    Attributes
    ----------
    category:
        One of ``code_injection`` / ``sensitive_info`` / ``path_leak``.
    severity:
        Risk severity — ``high`` findings should be masked before the
        output is returned to callers; ``medium`` / ``low`` are advisory.
    pattern_name:
        Human-readable name of the matched pattern (e.g. ``"openai_api_key"``).
    matched_text:
        The exact substring that triggered the finding.
    redacted_text:
        The matched substring with sensitive characters replaced by ``***``
        — safe to include in logs.
    span:
        ``(start, end)`` character offsets of the match within the
        scanned text. Used by :meth:`OutputValidator.redact` to mask
        the original text.
    """

    category: FindingCategory
    severity: FindingSeverity
    pattern_name: str
    matched_text: str
    redacted_text: str
    span: tuple[int, int]


@dataclass(slots=True)
class OutputValidationResult:
    """Aggregate result of scanning one output blob.

    Attributes
    ----------
    valid:
        ``True`` if no ``high``-severity findings were raised. ``valid``
        is the gate flag: when False, callers should mask or reject the
        output before returning it to a user.
    findings:
        All findings (any severity) in scan order.
    redacted_text:
        Copy of the scanned text with every high-severity finding masked
        via ``***``. Safe for logging.
    """

    valid: bool
    findings: list[OutputFinding] = field(default_factory=list)
    redacted_text: str = ""

    @property
    def high_severity_count(self) -> int:
        """Number of high-severity findings."""
        return sum(1 for f in self.findings if f.severity == "high")

    @property
    def medium_severity_count(self) -> int:
        """Number of medium-severity findings."""
        return sum(1 for f in self.findings if f.severity == "medium")


class OutputValidator:
    """Scan worker outputs for code injection, sensitive info, and path leaks.

    The validator is pure (no I/O) and stateless. It compiles its regex
    patterns once at class-definition time for efficiency.

    Usage::

        validator = OutputValidator()
        result = validator.validate(worker_output_text)
        if not result.valid:
            logger.warning("Output has %d high-severity findings", result.high_severity_count)
            safe_text = result.redacted_text
    """

    # ------------------------------------------------------------------
    # Pattern definitions
    # ------------------------------------------------------------------

    # Code injection: dangerous Python builtins and shell-out calls.
    # Match the function-call form (with optional whitespace before the
    # opening paren) so we don't false-positive on innocent prose like
    # "evaluate" or "executive".
    CODE_INJECTION_PATTERNS: list[tuple[str, str, FindingSeverity]] = [
        (r"\beval\s*\(", "eval_call", "high"),
        (r"\bexec\s*\(", "exec_call", "high"),
        (r"\b__import__\s*\(", "dunder_import", "high"),
        (r"\bcompile\s*\(\s*['\"]", "compile_with_literal", "medium"),
        (r"\bos\.system\s*\(", "os_system_call", "high"),
        (r"\bos\.popen\s*\(", "os_popen_call", "high"),
        (r"\bsubprocess\.(Popen|run|call|check_output|check_call)\s*\(", "subprocess_call", "high"),
        (r"\bos\.exec(l|le|vp|vpe)?\s*\(", "os_exec_family", "high"),
    ]

    # Sensitive information: well-known API key formats, bearer tokens,
    # password assignments, and private/internal network URLs.
    SENSITIVE_INFO_PATTERNS: list[tuple[str, str, FindingSeverity]] = [
        # OpenAI: sk-... (40+ alphanumeric)
        (r"sk-[A-Za-z0-9]{32,}", "openai_api_key", "high"),
        # Anthropic: sk-ant-...
        (r"sk-ant-[A-Za-z0-9_\-]{32,}", "anthropic_api_key", "high"),
        # Generic API key assignment: api_key=..., apikey=..., API_KEY=...
        (r"(?i)\b(api[_-]?key|apikey)\s*[=:]\s*['\"]?[A-Za-z0-9_\-]{16,}", "api_key_assignment", "high"),
        # Bearer tokens in Authorization headers
        (r"(?i)\bAuthorization\s*:\s*Bearer\s+[A-Za-z0-9_\-\.]{16,}", "bearer_token", "high"),
        # Password assignments: password=..., passwd=..., pwd=...
        (r"(?i)\b(pass(word|wd)?|pwd)\s*[=:]\s*['\"]?[^\s'\"]{6,}", "password_assignment", "high"),
        # AWS access key ID (20 chars, starts with AKIA)
        (r"\bAKIA[0-9A-Z]{16}\b", "aws_access_key_id", "high"),
        # AWS secret access key (40 chars base64-ish, after "aws_secret" context)
        (r"(?i)aws_secret[_-]?access[_-]?key\s*[=:]\s*['\"]?[A-Za-z0-9/+=]{40}", "aws_secret_key", "high"),
        # Generic secret= assignment
        (r"(?i)\bsecret\s*[=:]\s*['\"]?[A-Za-z0-9_\-]{16,}", "secret_assignment", "high"),
        # Private IPv4 addresses (RFC1918) — advisory
        (r"\b(?:10|172\.(?:1[6-9]|2[0-9]|3[01])|192\.168)\.\d{1,3}\.\d{1,3}\b", "private_ipv4", "medium"),
        # Internal URLs (localhost / 127.0.0.1 / .internal / .local)
        (r"\bhttps?://(?:localhost|127\.0\.0\.1|0\.0\.0\.0)(?::\d+)?(?:/|\b)", "localhost_url", "low"),
        (r"\bhttps?://[a-z0-9-]+\.(?:internal|local|corp)\b", "internal_domain", "medium"),
        # JWT tokens (three base64 segments separated by dots)
        (r"\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\b", "jwt_token", "high"),
    ]

    # Path leakage: absolute paths that reveal server filesystem layout.
    PATH_LEAK_PATTERNS: list[tuple[str, str, FindingSeverity]] = [
        # Sensitive POSIX directories
        (r"/etc/(?:passwd|shadow|hosts|sudoers|ssh/)", "etc_sensitive_path", "high"),
        (r"/root/\S+", "root_home_path", "high"),
        (r"/home/[a-z_][a-z0-9_-]*/\.(?:ssh|gnupg|bash_history|aws|kube)\b", "user_private_path", "high"),
        # SSH/GPG/Kube config files anywhere
        (r"~/?\.ssh/(?:id_[a-z]+|config|known_hosts|authorized_keys)", "ssh_config_path", "high"),
        (r"~/?\.kube/config\b", "kube_config_path", "high"),
        # Generic absolute POSIX path — advisory (may be legitimate)
        (r"/(?:var|opt|srv|usr/local)/(?:[a-z0-9_-]+/){1,4}[a-z0-9_-]+\.\w{1,5}", "server_abs_path", "low"),
        # Windows absolute paths (C:\Users\..., C:\Program Files\...)
        (r"\b[A-Z]:\\(?:Users|Program Files|Windows|inetpub)\\[^\s'\"]+", "windows_abs_path", "medium"),
        # Cloud-provider credential paths
        (r"~/?\.aws/credentials\b", "aws_credentials_file", "high"),
        (r"~/?\.config/gcloud/(?:credentials|application_default_credentials)\.json\b", "gcloud_credentials_file", "high"),
    ]

    # V4.2.0 P0-3: Prompt injection — LLM output containing instruction
    # hijacking patterns that try to manipulate downstream consumers.
    # Four sub-categories: ignore / role-hijack / inject / destructive.
    PROMPT_INJECTION_PATTERNS: list[tuple[str, str, FindingSeverity]] = [
        # --- ignore: attempts to discard prior instructions ---
        (r"(?i)\bignore\s+(?:all\s+)?(?:previous|prior|above|earlier)\s+instructions?\b", "ignore_prior_instructions", "high"),
        (r"(?i)\bdisregard\s+(?:all\s+)?(?:previous|prior|above)\s+(?:instructions?|prompts?)\b", "disregard_prior", "high"),
        (r"(?i)\bforget\s+(?:everything|all|previous|prior)\b", "forget_context", "high"),
        (r"(?i)\b(?:clear|reset)\s+(?:your\s+)?(?:context|memory|instructions?)\b", "clear_context", "high"),
        # --- role-hijack: attempts to change the AI's role ---
        (r"(?i)\byou\s+are\s+now\s+(?:a|an)\s+", "role_hijack_now", "high"),
        (r"(?i)\bact\s+as\s+(?:if\s+you\s+(?:are|were)\s+)?(?:a|an)\s+", "act_as_role", "high"),
        (r"(?i)\bpretend\s+(?:you\s+are|to\s+be)\s+", "pretend_role", "high"),
        (r"(?i)\b(?:new|switch\s+to|change\s+to)\s+role\s*:", "role_switch", "high"),
        (r"(?i)\bfrom\s+now\s+on\s*,?\s+you\s+(?:are|will)\s+", "from_now_on_role", "high"),
        # --- inject: fake system/developer messages ---
        (r"(?i)\b(?:system|developer|admin)\s*:\s*", "fake_system_message", "high"),
        (r"\[(?:SYSTEM|DEV|ADMIN|OVERRIDE)\]", "fake_system_tag", "high"),
        (r"<\|?(?:system|im_start|im_end)\|?>", "special_token_injection", "high"),
        (r"(?i)\b(?:new|override|additional)\s+instructions?\s*:", "override_instructions", "high"),
        # --- destructive: attempts to cause harm ---
        (r"(?i)\b(?:delete|remove|drop)\s+(?:all|every|the\s+entire)\b", "destructive_delete_all", "high"),
        (r"(?i)\bdrop\s+table\b", "destructive_drop_table", "high"),
        (r"(?i)\brm\s+-rf?\s+/", "destructive_rm_rf", "high"),
        (r"(?i)\bformat\s+[a-z]:\s*", "destructive_format", "high"),
        (r"(?i)\bshutdown\s+(?:now|immediately|-h\s+now)\b", "destructive_shutdown", "high"),
    ]

    # Compiled pattern cache (class-level for reuse).
    _COMPILED_CODE_INJECTION: list[tuple[re.Pattern[str], str, FindingSeverity]] = []
    _COMPILED_SENSITIVE_INFO: list[tuple[re.Pattern[str], str, FindingSeverity]] = []
    _COMPILED_PATH_LEAK: list[tuple[re.Pattern[str], str, FindingSeverity]] = []
    _COMPILED_PROMPT_INJECTION: list[tuple[re.Pattern[str], str, FindingSeverity]] = []

    def __init__(self) -> None:
        # Compile once at instance construction (deferred from class-level
        # to avoid heavy work at import time).
        if not OutputValidator._COMPILED_CODE_INJECTION:
            OutputValidator._COMPILED_CODE_INJECTION = [
                (re.compile(p), name, sev) for p, name, sev in self.CODE_INJECTION_PATTERNS
            ]
            OutputValidator._COMPILED_SENSITIVE_INFO = [
                (re.compile(p), name, sev) for p, name, sev in self.SENSITIVE_INFO_PATTERNS
            ]
            OutputValidator._COMPILED_PATH_LEAK = [
                (re.compile(p), name, sev) for p, name, sev in self.PATH_LEAK_PATTERNS
            ]
            OutputValidator._COMPILED_PROMPT_INJECTION = [
                (re.compile(p), name, sev) for p, name, sev in self.PROMPT_INJECTION_PATTERNS
            ]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate(self, text: str) -> OutputValidationResult:
        """Scan ``text`` for risky content.

        Args:
            text: Worker output or dispatch report text to scan.

        Returns:
            An :class:`OutputValidationResult` with all findings and a
            redacted copy of ``text`` (high-severity spans replaced by
            ``***``).
        """
        findings: list[OutputFinding] = []
        findings.extend(self._scan_code_injection(text))
        findings.extend(self._scan_sensitive_info(text))
        findings.extend(self._scan_path_leak(text))
        findings.extend(self._scan_prompt_injection(text))

        # Sort by span start so redaction offsets are processed left-to-right.
        findings.sort(key=lambda f: f.span[0])

        redacted = self._redact(text, findings)
        valid = not any(f.severity == "high" for f in findings)
        return OutputValidationResult(valid=valid, findings=findings, redacted_text=redacted)

    def redact(self, text: str) -> str:
        """Convenience: scan ``text`` and return the redacted form.

        Equivalent to ``self.validate(text).redacted_text`` but slightly
        faster when the caller doesn't need the structured findings.
        """
        return self.validate(text).redacted_text

    # ------------------------------------------------------------------
    # Scanners
    # ------------------------------------------------------------------

    def _scan_code_injection(self, text: str) -> list[OutputFinding]:
        return self._scan(text, self._COMPILED_CODE_INJECTION, "code_injection")

    def _scan_sensitive_info(self, text: str) -> list[OutputFinding]:
        return self._scan(text, self._COMPILED_SENSITIVE_INFO, "sensitive_info")

    def _scan_path_leak(self, text: str) -> list[OutputFinding]:
        return self._scan(text, self._COMPILED_PATH_LEAK, "path_leak")

    def _scan_prompt_injection(self, text: str) -> list[OutputFinding]:
        return self._scan(text, self._COMPILED_PROMPT_INJECTION, "prompt_injection")

    @staticmethod
    def _scan(
        text: str,
        compiled: list[tuple[re.Pattern[str], str, FindingSeverity]],
        category: FindingCategory,
    ) -> list[OutputFinding]:
        findings: list[OutputFinding] = []
        for pattern, name, severity in compiled:
            for match in pattern.finditer(text):
                matched = match.group(0)
                redacted = OutputValidator._mask(matched)
                findings.append(
                    OutputFinding(
                        category=category,
                        severity=severity,
                        pattern_name=name,
                        matched_text=matched,
                        redacted_text=redacted,
                        span=match.span(),
                    )
                )
        return findings

    # ------------------------------------------------------------------
    # Redaction helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _mask(text: str) -> str:
        """Mask sensitive content: keep first 2 + last 2 chars, ``***`` in the middle."""
        if len(text) <= 8:
            return "***"
        return f"{text[:2]}***{text[-2:]}"

    @staticmethod
    def _redact(text: str, findings: list[OutputFinding]) -> str:
        """Replace high-severity finding spans in ``text`` with ``***``.

        Lower-severity findings are left intact (they are advisory).
        Spans are processed right-to-left so earlier offsets remain valid
        as we mutate the string.
        """
        high_spans = [f.span for f in findings if f.severity == "high"]
        if not high_spans:
            return text
        # Process right-to-left to keep offsets stable.
        high_spans.sort(reverse=True)
        result = text
        for start, end in high_spans:
            result = result[:start] + "***" + result[end:]
        return result


__all__ = [
    "OutputFinding",
    "OutputValidationResult",
    "OutputValidator",
]
