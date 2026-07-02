"""Content-aware compression: ContentRouter + SmartCrusher.

Inspired by headroom's ContentRouter + SmartCrusher architecture. Detects the
content type of a text block and applies a structure-aware compression strategy
instead of uniform truncation.

Spec reference: docs/spec/v3.10.0_spec.md §5.3
"""

from __future__ import annotations

import json
import re
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .ccr_store import CCRStore


class ContentType(Enum):
    """Content type detected by ContentRouter for compression routing."""

    JSON_ARRAY = "json_array"
    CODE = "code"
    LOG = "log"
    PLAIN_TEXT = "plain_text"
    HTML = "html"
    DIFF = "diff"


# Patterns used by ContentRouter.detect — ordered by specificity (most specific first)
_LOG_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}|^\[\d{2}:\d{2}:\d{2}\]|"
    r"\b(DEBUG|INFO|WARN(?:ING)?|ERROR|FATAL|TRACE)\b",
    re.IGNORECASE,
)
_DIFF_PATTERN = re.compile(r"^(?:---|\+\+\+|@@|diff --git)", re.MULTILINE)
_HTML_PATTERN = re.compile(r"<(?:html|div|span|p|table|ul|ol|li|head|body)\b", re.IGNORECASE)
_CODE_PATTERN = re.compile(
    r"^\s*(?:def |class |import |from |func |func\b|public |private |"
    r"package |func\s+\w+\(|void\s+\w+\()",
    re.MULTILINE,
)


class ContentRouter:
    """Detect content type of a text block for compression routing.

    Detection order (most specific → least specific):
        DIFF → HTML → JSON_ARRAY → LOG → CODE → PLAIN_TEXT
    """

    def detect(self, text: str) -> ContentType:
        """Classify ``text`` into a ContentType for SmartCrusher routing.

        Args:
            text: The text block to classify.

        Returns:
            The detected ContentType. Defaults to PLAIN_TEXT when no specific
            signals match.
        """
        if not text or not text.strip():
            return ContentType.PLAIN_TEXT

        stripped = text.lstrip()

        if _DIFF_PATTERN.search(stripped):
            return ContentType.DIFF

        if _HTML_PATTERN.search(stripped):
            return ContentType.HTML

        if stripped.startswith("["):
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, list):
                    return ContentType.JSON_ARRAY
            except (json.JSONDecodeError, ValueError):
                pass

        if _LOG_PATTERN.search(stripped):
            return ContentType.LOG

        if _CODE_PATTERN.search(stripped):
            return ContentType.CODE

        return ContentType.PLAIN_TEXT


class SmartCrusher:
    """Structure-aware compressor that delegates to per-type crushing methods.

    Each crush method preserves semantically important elements (errors,
    first/last items, anomalies) while aggressively compressing repetitive
    bulk content.
    """

    def __init__(
        self,
        json_max_representative: int = 5,
        log_max_context_lines: int = 3,
        ccr_store: CCRStore | None = None,
    ) -> None:
        """Configure crush limits.

        Args:
            json_max_representative: Max representative items retained per
                JSON array (in addition to first/last/error items).
            log_max_context_lines: Context lines retained around each
                ERROR/WARN log entry.
            ccr_store: Optional CCRStore for reversible compression. When set,
                the original text is stored and a ``retrieve full: trace_id=X``
                marker is appended to the crush header.
        """
        self._json_max_rep = json_max_representative
        self._log_max_ctx = log_max_context_lines
        self._ccr_store = ccr_store

    def crush(self, text: str, content_type: ContentType | None = None) -> str:
        """Route ``text`` to the appropriate per-type crusher.

        Args:
            text: The text to compress.
            content_type: Optional pre-detected type. When None, ContentRouter
                detects automatically.

        Returns:
            Compressed text. Short inputs (<=200 chars) are returned unchanged.
            When a CCRStore is configured and compression occurs, the original
            is stored and a ``retrieve full: trace_id=...`` marker is injected
            into the crush header.
        """
        if len(text) <= 200:
            return text

        if content_type is None:
            content_type = ContentRouter().detect(text)

        if content_type == ContentType.JSON_ARRAY:
            crushed = self.crush_json_array(text)
        elif content_type == ContentType.LOG:
            crushed = self.crush_log(text)
        else:
            return text  # CODE/HTML/DIFF/PLAIN_TEXT: defer to existing compressor

        # CCR marker: store original + inject trace_id when compression happened
        if self._ccr_store is not None and crushed != text:
            trace_id = self._ccr_store.store(
                text, metadata={"content_type": content_type.value}
            )
            crushed = self._inject_trace_id(crushed, trace_id)
        return crushed

    @staticmethod
    def _inject_trace_id(crushed: str, trace_id: str) -> str:
        """Append ``retrieve full: trace_id=X`` to the crush header line.

        Header format before: ``[N items compressed to M]``
        Header format after:  ``[N items compressed to M; retrieve full: trace_id=X]``
        """
        lines = crushed.split("\n", 1)
        header = lines[0]
        rest = lines[1] if len(lines) > 1 else ""
        if header.startswith("[") and header.endswith("]"):
            header = header[:-1] + f"; retrieve full: trace_id={trace_id}]"
        else:
            header = header + f" [retrieve full: trace_id={trace_id}]"
        return header + ("\n" + rest if rest else "")

    def crush_json_array(self, text: str) -> str:
        """Compress a JSON array string.

        Strategy:
            1. Parse JSON array.
            2. Extract constant fields shared by all items.
            3. Retain first, last, error/anomaly items + a representative sample.
            4. Emit a summary header with compression stats.

        Args:
            text: A JSON array string.

        Returns:
            Compressed representation. Returns original text on parse failure
            or when the array is too small to benefit from compression.
        """
        try:
            items = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            return text

        if not isinstance(items, list) or len(items) <= 5:
            return text

        total = len(items)
        constants = self._extract_constant_fields(items)
        keepers = self._select_keepers(items)

        parts: list[str] = [
            f"[{total} items compressed to {len(keepers)}]",
        ]
        if constants:
            parts.append(f"constant_fields: {json.dumps(constants, ensure_ascii=False)}")
        parts.append("representative_items:")
        for item in keepers:
            parts.append(json.dumps(item, ensure_ascii=False))

        return "\n".join(parts)

    def crush_log(self, text: str) -> str:
        """Compress log output by retaining ERROR/WARN lines + context.

        Strategy:
            1. Split into lines.
            2. Retain first/last few lines for context.
            3. Retain all lines containing ERROR/WARN/FATAL.
            4. Emit a summary line with total/saved counts.

        Args:
            text: Log output text.

        Returns:
            Compressed log retaining errors and boundaries.
        """
        lines = text.split("\n")
        if len(lines) <= 20:
            return text

        total = len(lines)
        kept: list[str] = []
        seen_indices: set[int] = set()

        # Boundary context (first/last N lines)
        boundary = min(self._log_max_ctx, 3)
        for i in list(range(boundary)) + list(range(max(0, total - boundary), total)):
            if 0 <= i < total and i not in seen_indices:
                kept.append(lines[i])
                seen_indices.add(i)

        # Error/warning lines
        for i, line in enumerate(lines):
            if i in seen_indices:
                continue
            if re.search(r"\b(ERROR|WARN(?:ING)?|FATAL|CRITICAL)\b", line, re.IGNORECASE):
                kept.append(line)
                seen_indices.add(i)

        # Deduplicate while preserving order
        deduped: list[str] = []
        seen_set: set[str] = set()
        for line in kept:
            if line not in seen_set:
                deduped.append(line)
                seen_set.add(line)

        header = f"[{total} log lines compressed to {len(deduped)}]"
        return header + "\n" + "\n".join(deduped)

    def _extract_constant_fields(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        """Find fields with identical values across all items.

        Args:
            items: List of dict items from a JSON array.

        Returns:
            Dict of field→value pairs that are constant across all items.
            Returns empty dict if fewer than 2 items or no dict items.
        """
        dicts = [it for it in items if isinstance(it, dict)]
        if len(dicts) < 2:
            return {}

        first = dicts[0]
        constants: dict[str, Any] = {}
        for key, value in first.items():
            if all(d.get(key) == value for d in dicts[1:]):
                constants[key] = value
        return constants

    def _select_keepers(self, items: list[Any]) -> list[Any]:
        """Select representative items: first, last, anomalies, + sample.

        Args:
            items: Full list of JSON array items.

        Returns:
            List of items to retain (first, last, error items, and up to
            ``json_max_representative`` evenly-spaced samples).
        """
        total = len(items)
        keepers: list[Any] = []

        # First and last
        keepers.append(items[0])
        if total > 1:
            keepers.append(items[-1])

        # Error/anomaly items (dicts with error/status fields)
        error_statuses = ("error", "failed", "FAIL", "ERROR")
        for item in items:
            if (
                isinstance(item, dict)
                and (item.get("error") or item.get("status") in error_statuses)
                and item not in keepers
            ):
                keepers.append(item)

        # Evenly-spaced representative sample
        sample_count = min(self._json_max_rep, total)
        if sample_count > 0 and total > 2:
            step = max(1, total // sample_count)
            for i in range(0, total, step):
                if items[i] not in keepers:
                    keepers.append(items[i])
                if len(keepers) >= self._json_max_rep + 2:
                    break

        # Deduplicate preserving order
        seen: set[str] = set()
        result: list[Any] = []
        for item in keepers:
            key = json.dumps(item, sort_keys=True, ensure_ascii=False)
            if key not in seen:
                seen.add(key)
                result.append(item)
        return result
