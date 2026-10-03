"""Deterministic filtering of review changeset paths."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from .rule_engine import RuleConfigError, RuleSources, matches, resolve, security_resolution

GATE_NAMES: tuple[str, ...] = (
    "secret_exclude",
    "binary",
    "unsupported_ext",
    "too_large",
    "user_exclude",
    "user_include",
    "default_path",
    "deleted",
)

DEFAULT_EXCLUDE_PATTERNS: tuple[str, ...] = (
    ".git/**",
    "**/.git/**",
    "__pycache__/**",
    "**/__pycache__/**",
    "node_modules/**",
    "**/node_modules/**",
    "dist/**",
    "**/dist/**",
    "build/**",
    "**/build/**",
)


@dataclass(frozen=True)
class ExcludedPath:
    """The one exclusion decision made for a candidate path."""

    path: str
    gate: str
    reason: str


@dataclass
class ReviewFilterResult:
    """Stable output of :class:`DeterministicReviewFilter`."""

    retained_paths: list[str]
    excluded_paths: list[ExcludedPath]
    gate_counts: dict[str, int]
    candidate_count: int

    def to_dict(self) -> dict[str, object]:
        """Return the filter decision in a JSON-compatible shape."""
        return {
            "candidate_count": self.candidate_count,
            "retained_paths": list(self.retained_paths),
            "excluded_paths": [
                {
                    "path": "[REDACTED sensitive path]" if item.gate == "secret_exclude" else item.path,
                    "gate": item.gate,
                    "reason": (
                        "sensitive path excluded before user configuration"
                        if item.gate == "secret_exclude"
                        else item.reason
                    ),
                }
                for item in self.excluded_paths
            ],
            "gate_counts": dict(self.gate_counts),
        }


@dataclass(frozen=True)
class ReviewFilterConfig:
    """Inputs which affect deterministic review filtering."""

    max_size_bytes: int | None = 10 * 1024 * 1024
    user_include: tuple[str, ...] = ()
    user_exclude: tuple[str, ...] = ()
    default_exclude: tuple[str, ...] = DEFAULT_EXCLUDE_PATTERNS
    root: Path | str | None = None
    rule_sources: RuleSources | None = None

    def __post_init__(self) -> None:
        if self.max_size_bytes is not None and self.max_size_bytes < 0:
            raise ValueError("max_size_bytes must be non-negative or None")
        if self.root is not None and not isinstance(self.root, Path):
            object.__setattr__(self, "root", Path(self.root))


class DeterministicReviewFilter:
    """Apply the fixed W1-3 gate sequence to a review changeset."""

    def __init__(
        self,
        config: ReviewFilterConfig | None = None,
        *,
        contents: Mapping[str, bytes | str] | None = None,
    ) -> None:
        self.config = config or ReviewFilterConfig()
        self.contents = {_normalize_path(path): value for path, value in (contents or {}).items()}

    def filter(
        self,
        candidates: Iterable[str | Path],
        *,
        deleted_paths: Iterable[str | Path] = (),
    ) -> ReviewFilterResult:
        paths = _unique_paths(candidates)
        deleted = {_normalize_path(path) for path in deleted_paths}
        retained: list[str] = []
        excluded: list[ExcludedPath] = []
        counts = dict.fromkeys(GATE_NAMES, 0)

        for path in paths:
            decision = self._decide(path, deleted)
            if decision is None:
                retained.append(path)
                if _matches_any(path, self.config.user_include):
                    counts["user_include"] += 1
            else:
                excluded.append(decision)
                counts[decision.gate] += 1

        return ReviewFilterResult(
            retained_paths=retained,
            excluded_paths=excluded,
            gate_counts=counts,
            candidate_count=len(paths),
        )

    def _decide(self, path: str, deleted: set[str]) -> ExcludedPath | None:
        # This is deliberately the first operation for every candidate. It must
        # not be possible for user rules or an explicit include to restore it.
        security = security_resolution(path)
        if security is not None:
            return ExcludedPath(path, "secret_exclude", f"sensitive path matches {security.pattern}")

        if path in deleted:
            return ExcludedPath(path, "deleted", "path was explicitly marked deleted")

        content = self._content(path)
        if _is_binary(content):
            return ExcludedPath(path, "binary", "content is binary")

        try:
            resolution = resolve(path, self.config.rule_sources)
        except RuleConfigError as exc:
            return ExcludedPath(path, "unsupported_ext", f"rule resolution failed closed: {exc}")

        if self.config.max_size_bytes is not None and len(content) > self.config.max_size_bytes:
            return ExcludedPath(
                path,
                "too_large",
                f"content size {len(content)} exceeds {self.config.max_size_bytes} bytes",
            )

        if _matches_any(path, self.config.user_exclude):
            return ExcludedPath(path, "user_exclude", "matched user exclude glob")

        if _matches_any(path, self.config.user_include):
            return None

        if _matches_any(path, self.config.default_exclude):
            return ExcludedPath(path, "default_path", "matched built-in default exclude path")

        kind = resolution.body.get("kind")
        if not isinstance(kind, str) or not kind.strip() or kind == "unclaimed":
            return ExcludedPath(path, "unsupported_ext", "no declared reviewable file type")

        return None

    def _content(self, path: str) -> bytes:
        value: bytes | str | None = self.contents.get(path)
        if value is None and self.config.root is not None:
            try:
                value = (self.config.root / Path(path)).read_bytes()
            except (OSError, ValueError):
                value = None
        if value is None:
            return b""
        return value.encode("utf-8") if isinstance(value, str) else value


def filter_review_paths(
    candidates: Iterable[str | Path],
    *,
    deleted_paths: Iterable[str | Path] = (),
    config: ReviewFilterConfig | None = None,
    contents: Mapping[str, bytes | str] | None = None,
) -> ReviewFilterResult:
    """Filter review paths without touching dispatch or bundle planning."""
    return DeterministicReviewFilter(config, contents=contents).filter(
        candidates,
        deleted_paths=deleted_paths,
    )


# Short alias for callers integrating this module into a review changeset path.
filter_paths = filter_review_paths


def _normalize_path(path: str | Path) -> str:
    normalized = str(path).replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized or "."


def _unique_paths(paths: Iterable[str | Path]) -> list[str]:
    """Keep the first occurrence so one candidate has one final decision."""
    unique: list[str] = []
    seen: set[str] = set()
    for path in paths:
        normalized = _normalize_path(path)
        if normalized not in seen:
            seen.add(normalized)
            unique.append(normalized)
    return unique


def _matches_any(path: str, patterns: Sequence[str]) -> bool:
    return any(matches(path, pattern) for pattern in patterns)


def _is_binary(content: bytes) -> bool:
    if b"\x00" in content:
        return True
    try:
        content.decode("utf-8")
    except UnicodeDecodeError:
        return True
    return False


__all__ = [
    "DEFAULT_EXCLUDE_PATTERNS",
    "DeterministicReviewFilter",
    "ExcludedPath",
    "GATE_NAMES",
    "ReviewFilterConfig",
    "ReviewFilterResult",
    "filter_paths",
    "filter_review_paths",
]
