#!/usr/bin/env python3
"""
DependencyHallucinationChecker — V4.3.0 P1-7 (Phase 1)

Anti-Slopsquatting defense module. Scans AI-generated code for import
statements that reference hallucinated (non-existent) packages which
attackers could register as malicious lookalikes.

Threat model
------------
CSA 2026 + USENIX Security 2025 report that 5.2%–21.7% of AI-suggested
package imports reference non-existent packages. Attackers enumerate
model hallucinations and register malicious packages under those names
(Slopsquatting). Real-world incidents: `huggingface-cli`, `react-codeshift`,
`aws-cdk`, `ccxt-mexc-futures`, `@solana-launchpad/sdk`.

Detection pipeline (6 steps, priority descending)
-------------------------------------------------
1. Exact match against SUSPICIOUS blacklist → SUSPICIOUS
2. Exact match against KNOWN_GOOD whitelist → KNOWN_GOOD
3. Levenshtein ≤2 to Top-1000 package → SUSPICIOUS (typo)
4. Confusion rule (two real package names concatenated) → SUSPICIOUS
5. High-frequency hallucination suffix pattern → UNKNOWN (high-priority)
6. None of the above → UNKNOWN

fail-secure policy (Security Role 7-Role review revision)
---------------------------------------------------------
If the static dataset files (known_good.json / suspicious.json /
top_targets.json) are missing or corrupted, **all non-stdlib packages
degrade to UNKNOWN** — never to KNOWN_GOOD. This prevents false "safe"
classifications when the dataset is unavailable. The pipeline also never
raises on data loading errors; it logs a warning and continues with an
empty dataset, ensuring UNKNOWN downgrade.

Anti-ghost-feature contract
---------------------------
- Triggered naturally by SecuritySkill.scan_dependencies() and by the
  dispatch post-worker hook (dispatch_hooks.py). No separate manual call
  required.
- Module-level `_call_counter_er` tracks invocations; CI's
  E2E test E13 (``test_e2e_dispatch_increments_all_five_counters``) reads this counter to detect zero-call
  ghosts.
- DependencyScanResult.to_markdown() renders a "安全检查" section in the
  user-visible Markdown report.

Out of scope (V4.4.0+)
----------------------
- Real-time PyPI/npm API verification (hook reserved, not implemented)
- LLM-based semantic detection
- Modifying InputValidator (this module reuses patterns, not the class)

Spec reference: docs/prd/V4.3.0_PRD.md §9.2 P1-7
             docs/architecture/V4.3.0_ARCHITECTURE.md §9.2
             docs/analysis/2026-07-25_P1-7_dependency_hallucination_review.md
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DATA_DIR = (
    Path(__file__).resolve().parent
    / "data"
    / "dependency_hallucination"
)
_KNOWN_GOOD_PATH = _DATA_DIR / "known_good.json"
_SUSPICIOUS_PATH = _DATA_DIR / "suspicious.json"
_TOP_TARGETS_PATH = _DATA_DIR / "top_targets.json"

# Levenshtein distance threshold for typo-squatting detection
_LEVENSHTEIN_THRESHOLD = 2

# Maximum code size to scan (256 KB) — prevents pathological inputs
_MAX_CODE_BYTES = 256 * 1024

# Python standard library modules (3.12+) — never flagged
_PYTHON_STDLIB = frozenset(
    {
        "os", "sys", "json", "re", "io", "pathlib", "collections", "typing",
        "datetime", "time", "math", "random", "itertools", "functools",
        "operator", "dataclasses", "enum", "abc", "copy", "pickle",
        "shelve", "sqlite3", "csv", "xml", "html", "http", "urllib",
        "socket", "ssl", "asyncio", "threading", "multiprocessing",
        "logging", "warnings", "unittest", "doctest", "pdb", "profile",
        "timeit", "trace", "argparse", "getopt", "configparser", "netrc",
        "os.path", "subprocess", "signal", "mmap", "ctypes", "struct",
        "codecs", "unicodedata", "stringprep", "rlcompleter", "linecache",
        "tokenize", "keyword", "token", "tabnanny", "compileall", "dis",
        "inspect", "types", "traceback", "gc", "sysconfig", "builtins",
        "importlib", "pkgutil", "modulefinder", "runpy", "atexit", "hashlib", "hmac", "secrets", "base64", "binascii", "quopri",
        "uu", "binhex", "crypt", "fractions", "decimal",
        "statistics", "numbers", "cmath", "array", "bisect", "heapq", "queue", "weakref", "errno", "select", "selectors", "contextlib", "contextvars", "tomllib", "uuid", "graphlib",
    }
)

# Node.js built-in modules — never flagged
_NODE_BUILTINS = frozenset(
    {
        "assert", "buffer", "child_process", "cluster", "console",
        "constants", "crypto", "dgram", "diagnostics_channel", "dns",
        "events", "fs", "http", "http2", "https", "inspector", "module",
        "net", "os", "path", "perf_hooks", "process", "punycode",
        "querystring", "readline", "repl", "stream", "string_decoder",
        "sys", "timers", "tls", "trace_events", "tty", "url", "util",
        "v8", "vm", "wasi", "worker_threads", "zlib",
    }
)

# Python import extraction patterns
# Note: AI hallucinations may generate invalid Python like `import aws-cdk`
# (hyphens are illegal in Python identifiers). We deliberately accept hyphens
# in the regex so we can flag these hallucinations rather than silently miss them.
_PYTHON_IMPORT_PATTERNS = (
    re.compile(r"^\s*import\s+([a-zA-Z_][a-zA-Z0-9_-]*)", re.MULTILINE),
    re.compile(
        r"^\s*from\s+([a-zA-Z_][a-zA-Z0-9_.-]*)\s+import",
        re.MULTILINE,
    ),
)

# JavaScript/TypeScript import extraction patterns
# Match: import x from 'pkg' / import { x } from 'pkg' / require('pkg')
# Note: require() may not be at line start (e.g., `const x = require('pkg')`)
_JS_IMPORT_PATTERNS = (
    re.compile(
        r"""^\s*import\s+[^;]*?\s+from\s+['"]([^'"]+)['"]""",
        re.MULTILINE,
    ),
    re.compile(
        r"""\brequire\(\s*['"]([^'"]+)['"]\s*\)""",
        re.MULTILINE,
    ),
)

# High-frequency hallucination suffix patterns (from Snyk/Socket research)
_SUSPICIOUS_SUFFIXES = (
    "-helper", "-utils", "-sdk", "-validator", "-middleware",
    "-secure", "-extra", "-pro", "-plus", "-advanced",
    "-ultimate", "-premium",
)


# ---------------------------------------------------------------------------
# Module-level call counter (anti-ghost feature)
# ---------------------------------------------------------------------------

_call_counter_er: int = 0


def get_call_count() -> int:
    """Return the number of times security_scan_dependencies has been called.

    Used by E2E test E13 (``test_e2e_dispatch_increments_all_five_counters``) to detect ghost features
    (modules that exist but are never invoked).
    """
    return _call_counter_er


# ---------------------------------------------------------------------------
# Enums and data classes
# ---------------------------------------------------------------------------


class DependencyCategory(Enum):
    """Three-tier classification for imported packages.

    Priority order (safety-first): SUSPICIOUS > KNOWN_GOOD > UNKNOWN.
    When multiple rules could apply, the most conservative wins.
    """

    KNOWN_GOOD = "known_good"
    UNKNOWN = "unknown"
    SUSPICIOUS = "suspicious"


class DependencySeverity(Enum):
    """Severity levels for dependency findings."""

    INFO = "info"        # KNOWN_GOOD
    WARNING = "warning"  # UNKNOWN
    CRITICAL = "critical"  # SUSPICIOUS


@dataclass
class DependencyFinding:
    """Single dependency finding.

    Attributes:
        package_name: The imported package name (top-level, no submodules)
        ecosystem: Package ecosystem, "pypi" or "npm"
        category: Three-tier classification result
        severity: Severity level derived from category
        import_statement: The original import line from source code
        line_number: 1-based line number where the import appears
        reason: Human-readable explanation of the classification
        suggested_fix: Suggested real package name, if known (else None)
    """

    package_name: str
    ecosystem: str
    category: DependencyCategory
    severity: DependencySeverity
    import_statement: str
    line_number: int
    reason: str
    suggested_fix: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize finding to a dictionary for JSON/report rendering."""
        return {
            "package_name": self.package_name,
            "ecosystem": self.ecosystem,
            "category": self.category.value,
            "severity": self.severity.value,
            "import_statement": self.import_statement,
            "line_number": self.line_number,
            "reason": self.reason,
            "suggested_fix": self.suggested_fix,
        }


@dataclass
class DependencyScanResult:
    """Result of a dependency hallucination scan.

    Attributes:
        is_clean: True if no SUSPICIOUS and no UNKNOWN findings
        findings: List of DependencyFinding, one per imported package
        summary: Human-readable one-line summary
        stats: Counts per category, e.g. {"known_good": N, "unknown": N, "suspicious": N}
        scan_duration_ms: Wall-clock scan duration in milliseconds
        timestamp: ISO-8601 timestamp of scan completion
        ecosystem_detected: Ecosystem auto-detected from code, or the explicit input
    """

    is_clean: bool
    findings: list[DependencyFinding]
    summary: str
    stats: dict[str, int] = field(default_factory=dict)
    scan_duration_ms: float = 0.0
    timestamp: str = field(
        default_factory=lambda: datetime.now().isoformat()
    )
    ecosystem_detected: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        """Serialize result summary to a dictionary."""
        return {
            "is_clean": self.is_clean,
            "findings_count": len(self.findings),
            "findings": [f.to_dict() for f in self.findings],
            "summary": self.summary,
            "stats": self.stats,
            "scan_duration_ms": self.scan_duration_ms,
            "timestamp": self.timestamp,
            "ecosystem_detected": self.ecosystem_detected,
        }

    def to_markdown(self) -> str:
        """Render the result as a Markdown "安全检查" section.

        This section is embedded in the user-visible dispatch report
        to satisfy the anti-ghost-feature "user visibility" contract.
        """
        lines = [
            "## 安全检查（依赖幻觉检测）",
            "",
            f"- 扫描时间: {self.timestamp}",
            f"- 检测生态: {self.ecosystem_detected}",
            f"- 扫描耗时: {self.scan_duration_ms:.2f} ms",
            f"- 总计 import: {len(self.findings)}",
            (
                f"- 分类统计: "
                f"KNOWN_GOOD={self.stats.get('known_good', 0)}, "
                f"UNKNOWN={self.stats.get('unknown', 0)}, "
                f"SUSPICIOUS={self.stats.get('suspicious', 0)}"
            ),
            "",
        ]
        if self.is_clean:
            lines.append("✅ 所有 import 均为已知良好包，未检测到幻觉风险。")
            return "\n".join(lines)

        suspicious = [
            f for f in self.findings
            if f.category == DependencyCategory.SUSPICIOUS
        ]
        unknown = [
            f for f in self.findings
            if f.category == DependencyCategory.UNKNOWN
        ]
        if suspicious:
            lines.append(f"### 🚨 SUSPICIOUS ({len(suspicious)} 项)")
            lines.append("")
            for f in suspicious:
                fix = (
                    f" → 建议替换为 `{f.suggested_fix}`"
                    if f.suggested_fix
                    else ""
                )
                lines.append(
                    f"- **L{f.line_number} `{f.package_name}`** "
                    f"({f.ecosystem}): {f.reason}{fix}"
                )
            lines.append("")
        if unknown:
            lines.append(f"### ⚠️ UNKNOWN ({len(unknown)} 项)")
            lines.append("")
            for f in unknown:
                lines.append(
                    f"- **L{f.line_number} `{f.package_name}`** "
                    f"({f.ecosystem}): {f.reason}"
                )
            lines.append("")
        lines.append(
            "> 详见 [Slopsquatting 防御文档]"
            "(docs/analysis/2026-07-25_P1-7_dependency_hallucination_review.md)"
        )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Dataset loader (lazy + cached + fail-secure)
# ---------------------------------------------------------------------------

_loaded_known_good: set[str] | None = None
_loaded_suspicious: set[str] | None = None
_loaded_top_targets: set[str] | None = None
_loaded_suffix_patterns: tuple[str, ...] | None = None
_loaded_confusion_pairs: list[dict[str, Any]] | None = None


def _load_json_safe(path: Path, default: Any) -> Any:
    """Load a JSON file with fail-secure error handling.

    On any error (missing file, invalid JSON, permission error), returns
    the provided default. Never raises.
    """
    try:
        if not path.exists():
            logger.warning("Dataset missing: %s — using fail-secure default", path)
            return default
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError, ValueError) as e:
        logger.warning(
            "Dataset corrupted %s: %s — using fail-secure default", path, e
        )
        return default


def _ensure_datasets_loaded() -> None:
    """Lazily load all three datasets on first use.

    Idempotent: subsequent calls are no-ops. Thread-unsafe by design
    (DevSquad dispatch pipeline is single-threaded per dispatch).
    """
    global _loaded_known_good, _loaded_suspicious, _loaded_top_targets
    global _loaded_suffix_patterns, _loaded_confusion_pairs

    if _loaded_known_good is not None:
        return

    known_good_data = _load_json_safe(_KNOWN_GOOD_PATH, {"pypi": [], "npm": []})
    suspicious_data = _load_json_safe(
        _SUSPICIOUS_PATH,
        {
            "pypi": [],
            "npm": [],
            "high_frequency_suffix_patterns": [],
            "confusion_pairs": [],
        },
    )
    top_targets_data = _load_json_safe(
        _TOP_TARGETS_PATH, {"pypi": [], "npm": []}
    )

    _loaded_known_good = set(known_good_data.get("pypi", [])) | set(
        known_good_data.get("npm", [])
    )
    _loaded_suspicious = set(suspicious_data.get("pypi", [])) | set(
        suspicious_data.get("npm", [])
    )
    _loaded_top_targets = set(top_targets_data.get("pypi", [])) | set(
        top_targets_data.get("npm", [])
    )
    _loaded_suffix_patterns = tuple(
        suspicious_data.get("high_frequency_suffix_patterns", [])
    )
    _loaded_confusion_pairs = suspicious_data.get("confusion_pairs", [])


def reset_dataset_cache() -> None:
    """Reset the cached datasets. For testing only."""
    global _loaded_known_good, _loaded_suspicious, _loaded_top_targets
    global _loaded_suffix_patterns, _loaded_confusion_pairs
    _loaded_known_good = None
    _loaded_suspicious = None
    _loaded_top_targets = None
    _loaded_suffix_patterns = None
    _loaded_confusion_pairs = None


# ---------------------------------------------------------------------------
# Import extraction
# ---------------------------------------------------------------------------


def _detect_ecosystem(code: str) -> str:
    """Auto-detect ecosystem from code content.

    Heuristic: Python code contains `def ` / `import ` / `from ` / `class `;
    JS/TS code contains `require(` / `const ` / `let ` / `=>` / `function*`.
    """
    if any(p.search(code) for p in _PYTHON_IMPORT_PATTERNS):
        return "pypi"
    if any(p.search(code) for p in _JS_IMPORT_PATTERNS):
        return "npm"
    # Fallback: look for Python-specific keywords
    if re.search(r"^\s*def\s+\w+\(", code, re.MULTILINE):
        return "pypi"
    if re.search(r"^\s*(const|let|var)\s+\w+\s*=", code, re.MULTILINE):
        return "npm"
    return "pypi"  # default


def _extract_imports(
    code: str,
    ecosystem: str,
) -> list[tuple[str, int, str]]:
    """Extract (package_name, line_number, import_statement) tuples.

    Args:
        code: Source code to scan
        ecosystem: "pypi" or "npm"

    Returns:
        List of (top-level package name, 1-based line number, original line)
    """
    imports: list[tuple[str, int, str]] = []
    # Deduplicate by package name across the whole file (keep first occurrence
    # line number). Without this, 1000 lines of `import requests` would
    # produce 1000 findings instead of 1.
    seen_packages: set[str] = set()

    patterns = (
        _PYTHON_IMPORT_PATTERNS if ecosystem == "pypi" else _JS_IMPORT_PATTERNS
    )
    stdlib = _PYTHON_STDLIB if ecosystem == "pypi" else _NODE_BUILTINS

    for pattern in patterns:
        for match in pattern.finditer(code):
            line_num = code.count("\n", 0, match.start()) + 1
            raw_pkg = match.group(1)
            original_line = match.group(0).strip()

            # Normalize: take top-level package only (split on / for npm scoped)
            if ecosystem == "npm":
                if raw_pkg.startswith("@"):
                    parts = raw_pkg.split("/", 1)
                    pkg_name = parts[0] + "/" + parts[1] if len(parts) > 1 else parts[0]
                else:
                    pkg_name = raw_pkg.split("/", 1)[0]
            else:
                # Python: take top-level module (split on .)
                pkg_name = raw_pkg.split(".")[0]

            # Skip stdlib / builtins
            if pkg_name in stdlib:
                continue

            # Skip relative imports (shouldn't match due to regex, but be safe)
            if pkg_name.startswith(".") or pkg_name.startswith("/"):
                continue

            # Deduplicate by package name (cross-line): keep first occurrence
            if pkg_name in seen_packages:
                continue
            seen_packages.add(pkg_name)
            imports.append((pkg_name, line_num, original_line))

    return imports


# ---------------------------------------------------------------------------
# Levenshtein distance (no external dependency)
# ---------------------------------------------------------------------------


def _levenshtein(a: str, b: str, max_distance: int | None = None) -> int:
    """Compute Levenshtein edit distance between two strings.

    Uses the standard dynamic programming algorithm with O(len(a) * len(b))
    time and O(min(len(a), len(b))) space.

    Args:
        a, b: Strings to compare
        max_distance: If provided, early-exit and return ``max_distance + 1``
            as soon as the running minimum distance exceeds this threshold.
            This is a performance optimization for typo-squatting detection
            where we only care whether distance ≤ threshold.
    """
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    # Length filter: edit distance >= |len difference|
    if max_distance is not None and abs(len(a) - len(b)) > max_distance:
        return max_distance + 1

    # Ensure b is the shorter string for space efficiency
    if len(b) > len(a):
        a, b = b, a

    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        row_min = i
        for j, cb in enumerate(b, 1):
            insert_cost = current[j - 1] + 1
            delete_cost = previous[j] + 1
            substitute_cost = previous[j - 1] + (0 if ca == cb else 1)
            cell = min(insert_cost, delete_cost, substitute_cost)
            current.append(cell)
            if cell < row_min:
                row_min = cell
        # Early termination: if every cell in this row exceeds max_distance,
        # the final distance cannot improve below it.
        if max_distance is not None and row_min > max_distance:
            return max_distance + 1
        previous = current

    return previous[-1]


def _find_typo_target(package: str, top_targets: set[str]) -> str | None:
    """Find a top target within Levenshtein threshold of the given package.

    Args:
        package: Package name to check
        top_targets: Set of top target package names

    Returns:
        The closest target within threshold, or None if no match
    """
    # Optimization: only check targets with similar length
    pkg_len = len(package)
    pkg_chars = frozenset(package)
    best_match: str | None = None
    best_distance = _LEVENSHTEIN_THRESHOLD + 1

    for target in top_targets:
        # Length filter: edit distance >= |len difference|
        if abs(len(target) - pkg_len) > _LEVENSHTEIN_THRESHOLD:
            continue
        # Character set filter: if package has > threshold chars not in target,
        # edit distance must exceed threshold (each char needs ≥1 insertion).
        # This prunes the vast majority of candidates without running DP.
        unique_chars = len(pkg_chars - frozenset(target))
        if unique_chars > _LEVENSHTEIN_THRESHOLD:
            continue
        distance = _levenshtein(package, target, max_distance=_LEVENSHTEIN_THRESHOLD)
        if distance < best_distance:
            best_distance = distance
            best_match = target
        # Short-circuit: exact or distance=1 match cannot be beaten
        if best_distance <= 1:
            break

    return best_match if best_distance <= _LEVENSHTEIN_THRESHOLD else None


# ---------------------------------------------------------------------------
# Classification pipeline
# ---------------------------------------------------------------------------


def _normalize_package_name(package: str) -> list[str]:
    """Generate normalized variants of a package name for matching.

    AI hallucinations may use either hyphens or underscores (e.g.,
    `huggingface-cli` vs `huggingface_cli`). We check all variants against
    the blacklist/whitelist to catch both forms.

    Returns:
        List of name variants to check (original first, then alternatives)
    """
    variants = [package]
    if "-" in package:
        variants.append(package.replace("-", "_"))
    if "_" in package:
        variants.append(package.replace("_", "-"))
    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for v in variants:
        if v not in seen:
            seen.add(v)
            unique.append(v)
    return unique


def _check_suspicious_blacklist(
    variants: list[str],
) -> tuple[bool, str | None]:
    """Step 1 of pipeline: check suspicious blacklist.

    Returns ``(matched, suggested_fix)``. When ``matched`` is True,
    ``suggested_fix`` may carry a replacement package name sourced from
    the confusion_pairs dataset (or None when no pair matches).
    """
    assert _loaded_suspicious is not None
    assert _loaded_confusion_pairs is not None

    for variant in variants:
        if variant in _loaded_suspicious:
            suggested = _lookup_confusion_fix(variant)
            return True, suggested
    return False, None


def _lookup_confusion_fix(hallucinated: str) -> str | None:
    """Look up a suggested fix for a hallucinated package in confusion_pairs."""
    assert _loaded_confusion_pairs is not None

    for pair in _loaded_confusion_pairs:
        if pair.get("hallucinated") == hallucinated:
            components: list[str] = pair.get("real_components", [])
            if components:
                return str(components[0])
            return None
    return None


def _check_known_good(variants: list[str]) -> bool:
    """Step 2 of pipeline: check known-good whitelist (any variant match)."""
    assert _loaded_known_good is not None

    return any(v in _loaded_known_good for v in variants)


def _check_confusion_rule(package: str) -> tuple[bool, str, str | None]:
    """Step 4 of pipeline: confusion rule (concatenation of two real packages).

    Returns ``(matched, reason, suggested_fix)``.
    """
    assert _loaded_confusion_pairs is not None

    for pair in _loaded_confusion_pairs:
        hallucinated = pair.get("hallucinated", "")
        components = pair.get("real_components", [])
        if package == hallucinated and len(components) >= 2:
            reason = (
                f"Package appears to be a confusion of real packages: "
                f"{' + '.join(components)}"
            )
            return True, reason, components[0]
    return False, "", None


def _check_suffix_pattern(package: str) -> tuple[bool, str]:
    """Step 5 of pipeline: high-frequency hallucination suffix pattern.

    Returns ``(matched, reason)``.
    """
    assert _loaded_suffix_patterns is not None

    pkg_lower = package.lower()
    for suffix in _loaded_suffix_patterns:
        if pkg_lower.endswith(suffix) and len(pkg_lower) > len(suffix):
            reason = (
                f"Package name ends with high-frequency hallucination "
                f"suffix '{suffix}' — manual review required"
            )
            return True, reason
    return False, ""


def _classify_package(
    package: str,
    ecosystem: str,
) -> tuple[DependencyCategory, str, str | None]:
    """Classify a single package through the 6-step pipeline.

    Args:
        package: Top-level package name
        ecosystem: "pypi" or "npm"

    Returns:
        Tuple of (category, reason, suggested_fix)
    """
    assert _loaded_top_targets is not None

    # Generate normalized variants for hyphen/underscore interchange
    variants = _normalize_package_name(package)

    # Step 1: Suspicious blacklist (exact match, all variants)
    matched, suggested = _check_suspicious_blacklist(variants)
    if matched:
        reason = (
            "Package is in the suspicious blacklist "
            "(known hallucination or malicious package)"
        )
        return DependencyCategory.SUSPICIOUS, reason, suggested

    # Step 2: Known-good whitelist (exact match, all variants)
    if _check_known_good(variants):
        reason = (
            "Package is in the known-good whitelist "
            "(Top-N or commonly used)"
        )
        return DependencyCategory.KNOWN_GOOD, reason, None

    # Step 3: Levenshtein typo-squatting detection
    typo_target = _find_typo_target(package, _loaded_top_targets)
    if typo_target is not None and typo_target != package:
        reason = (
            f"Package name is within Levenshtein distance "
            f"{_LEVENSHTEIN_THRESHOLD} of known package '{typo_target}' "
            f"(possible typo-squatting)"
        )
        return DependencyCategory.SUSPICIOUS, reason, typo_target

    # Step 4: Confusion rule (two real package names concatenated)
    matched, reason, suggested = _check_confusion_rule(package)
    if matched:
        return DependencyCategory.SUSPICIOUS, reason, suggested

    # Step 5: High-frequency hallucination suffix pattern
    matched, reason = _check_suffix_pattern(package)
    if matched:
        return DependencyCategory.UNKNOWN, reason, None

    # Step 6: Default to UNKNOWN (fail-secure)
    reason = (
        "Package not found in whitelist or blacklist — "
        "manual review required"
    )
    return DependencyCategory.UNKNOWN, reason, None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def security_scan_dependencies(
    code: str,
    ecosystem: str = "auto",
    blocking: bool = False,
) -> DependencyScanResult:
    """Scan code for dependency hallucination (Slopsquatting attack).

    Args:
        code: Source code to scan (Python or JavaScript/TypeScript)
        ecosystem: Package ecosystem; "pypi" | "npm" | "auto" (detect from code)
        blocking: If True, SUSPICIOUS findings raise RuntimeError instead of
            returning. Default False (non-blocking, report-only).

    Returns:
        DependencyScanResult with findings and statistics.

    Raises:
        RuntimeError: If blocking=True and SUSPICIOUS findings detected.
        ValueError: If code is empty or ecosystem is invalid.

    Anti-ghost-feature contract:
        - Increments module-level _call_counter_er (CI checks > 0)
        - Result.to_markdown() renders user-visible "安全检查" section
        - Triggered automatically by SecuritySkill and dispatch post-worker hook
    """
    global _call_counter_er
    _call_counter_er += 1

    start_time = datetime.now()

    # Input validation
    if not code or not isinstance(code, str):
        raise ValueError("code must be a non-empty string")
    if len(code.encode("utf-8")) > _MAX_CODE_BYTES:
        raise ValueError(
            f"code exceeds maximum size of {_MAX_CODE_BYTES} bytes"
        )

    # Ecosystem detection
    if ecosystem == "auto":
        detected = _detect_ecosystem(code)
    elif ecosystem in ("pypi", "npm"):
        detected = ecosystem
    else:
        raise ValueError(
            f"ecosystem must be 'pypi', 'npm', or 'auto'; got '{ecosystem}'"
        )

    # Ensure datasets are loaded (fail-secure if missing)
    _ensure_datasets_loaded()

    # If datasets failed to load, all sets are empty → all packages UNKNOWN
    # This is the fail-secure behavior documented in the module docstring.

    # Extract imports
    imports = _extract_imports(code, detected)

    # Classify each import
    findings: list[DependencyFinding] = []
    stats = {"known_good": 0, "unknown": 0, "suspicious": 0}

    for pkg_name, line_num, import_stmt in imports:
        category, reason, suggested_fix = _classify_package(pkg_name, detected)
        severity = {
            DependencyCategory.KNOWN_GOOD: DependencySeverity.INFO,
            DependencyCategory.UNKNOWN: DependencySeverity.WARNING,
            DependencyCategory.SUSPICIOUS: DependencySeverity.CRITICAL,
        }[category]

        findings.append(
            DependencyFinding(
                package_name=pkg_name,
                ecosystem=detected,
                category=category,
                severity=severity,
                import_statement=import_stmt,
                line_number=line_num,
                reason=reason,
                suggested_fix=suggested_fix,
            )
        )
        stats[category.value] += 1

    # Sort findings: SUSPICIOUS first, then UNKNOWN, then KNOWN_GOOD
    severity_order = {
        DependencySeverity.CRITICAL: 0,
        DependencySeverity.WARNING: 1,
        DependencySeverity.INFO: 2,
    }
    findings.sort(key=lambda f: (severity_order[f.severity], f.line_number))

    elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
    is_clean = stats["suspicious"] == 0 and stats["unknown"] == 0

    if is_clean:
        summary = (
            f"Scanned {len(findings)} import(s); all known-good."
        )
    else:
        summary = (
            f"Scanned {len(findings)} import(s); "
            f"{stats['suspicious']} SUSPICIOUS, "
            f"{stats['unknown']} UNKNOWN, "
            f"{stats['known_good']} KNOWN_GOOD."
        )

    result = DependencyScanResult(
        is_clean=is_clean,
        findings=findings,
        summary=summary,
        stats=stats,
        scan_duration_ms=elapsed_ms,
        ecosystem_detected=detected,
    )

    # Blocking mode: raise if SUSPICIOUS found
    if blocking and stats["suspicious"] > 0:
        suspicious_names = [
            f.package_name
            for f in findings
            if f.category == DependencyCategory.SUSPICIOUS
        ]
        raise RuntimeError(
            f"Dependency hallucination check failed (blocking mode): "
            f"{len(suspicious_names)} SUSPICIOUS package(s) found: "
            f"{', '.join(suspicious_names[:10])}"
        )

    return result
