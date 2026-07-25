"""Debt collector — V4.3.0 P1-1.

Classifies tech-debt entries (from :mod:`todo_drift_monitor`) by rot risk
(``HIGH`` / ``MEDIUM`` / ``LOW``) based on three signals:

    1. **File last modified date** — older files indicate stale debt.
    2. **Marker type** — ``FIXME`` > ``HACK`` > ``TODO`` > ``XXX`` > ``WIP``.
    3. **Critical module path** — debt in security/cache/auth rots faster.

Integrates with :func:`todo_drift_monitor.scan_tech_debt` to reuse the
existing scan infrastructure (no duplicated regex/tokenizer logic).

Architecture reference: docs/architecture/V4.3.0_ARCHITECTURE.md §3.2.
Test plan: docs/testing/V4.3.0_TEST_PLAN.md §3 (P1-1 row).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from scripts.collaboration.todo_drift_monitor import (
    TechDebtEntry,
    scan_tech_debt,
)

# Marker severity weights: FIXME > HACK > TODO > XXX > WIP (per P1-1 spec).
_MARKER_WEIGHT: dict[str, int] = {
    "FIXME": 4,
    "HACK": 3,
    "TODO": 2,
    "XXX": 1,
    "WIP": 0,
}
# Critical module path substrings — debt in these files rots faster.
_CRITICAL_PATHS: tuple[str, ...] = (
    "security", "cache", "auth", "permission", "rbac",
)
# File age thresholds (seconds). Older files rot faster.
_OLD_AGE_SEC = 90 * 24 * 3600  # 90 days
_STALE_AGE_SEC = 30 * 24 * 3600  # 30 days
# Rot-risk score thresholds.
_HIGH_RISK_SCORE = 4
_MED_RISK_SCORE = 2
_RANK = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}


@dataclass
class ClassifiedDebt:
    """A tech-debt entry with its rot-risk classification.

    Attributes:
        entry: The original :class:`TechDebtEntry` from the scanner.
        rot_risk: ``"HIGH"``, ``"MEDIUM"``, or ``"LOW"``.
        reasons: Human-readable factors contributing to the classification.
    """

    entry: TechDebtEntry
    rot_risk: str
    reasons: list[str] = field(default_factory=list)


class DebtCollector:
    """Collects and classifies tech debt by rot risk.

    Integrates with :func:`todo_drift_monitor.scan_tech_debt` to scan the
    codebase, then classifies each marker by rot risk (HIGH/MEDIUM/LOW).

    Example:
        >>> collector = DebtCollector(root_dir="scripts")
        >>> debts = collector.collect()
        >>> report = collector.to_report()
    """

    def __init__(
        self,
        root_dir: str | Path = "scripts",
        critical_paths: tuple[str, ...] = _CRITICAL_PATHS,
        now: float | None = None,
    ) -> None:
        """Initialize the collector.

        Args:
            root_dir: Directory to scan (default ``scripts``).
            critical_paths: Module path substrings considered critical.
            now: Override current timestamp (for testing). If ``None``,
                uses :func:`time.time`.
        """
        self._root = Path(root_dir)
        self._critical = critical_paths
        self._now = now if now is not None else time.time()

    def collect(self) -> list[ClassifiedDebt]:
        """Scan and classify all tech debt in ``root_dir``.

        Returns:
            List of :class:`ClassifiedDebt` sorted by descending rot risk
            (HIGH first, then MEDIUM, then LOW), with file path as tiebreak.
        """
        entries = scan_tech_debt(str(self._root))
        debts = [self.classify(e) for e in entries]
        debts.sort(
            key=lambda d: (_RANK.get(d.rot_risk, 3), d.entry.file_path)
        )
        return debts

    def classify(self, entry: TechDebtEntry) -> ClassifiedDebt:
        """Classify a single entry by rot risk.

        Args:
            entry: The tech-debt entry to classify.

        Returns:
            A :class:`ClassifiedDebt` with rot_risk and reasons.

        Example:
            >>> from scripts.collaboration.todo_drift_monitor import TechDebtEntry
            >>> entry = TechDebtEntry("scripts/security/x.py", 1, "FIXME", "# FIXME")
            >>> DebtCollector().classify(entry).rot_risk in ("HIGH", "MEDIUM", "LOW")
            True
        """
        reasons: list[str] = []
        score = 0
        # Signal 1: marker type (FIXME/HACK are higher risk).
        weight = _MARKER_WEIGHT.get(entry.marker.upper(), 0)
        if weight >= 3:
            score += 2
            reasons.append(f"high-severity marker {entry.marker}")
        elif weight >= 1:
            score += 1
        # Signal 2: critical module path (security/cache/auth rots faster).
        if any(c in str(entry.file_path).lower() for c in self._critical):
            score += 2
            reasons.append("in critical module path")
        # Signal 3: file age (older files indicate stale debt).
        age = self._file_age(entry.file_path)
        if age >= _OLD_AGE_SEC:
            score += 2
            reasons.append("file older than 90 days")
        elif age >= _STALE_AGE_SEC:
            score += 1
            reasons.append("file older than 30 days")
        risk = self._risk_from_score(score)
        return ClassifiedDebt(entry=entry, rot_risk=risk, reasons=reasons)

    def _file_age(self, file_path: str) -> float:
        """Return file age in seconds (0 if unreadable)."""
        try:
            return self._now - Path(file_path).stat().st_mtime
        except OSError:
            return 0.0

    def _risk_from_score(self, score: int) -> str:
        """Map a numeric score to a rot-risk label."""
        if score >= _HIGH_RISK_SCORE:
            return "HIGH"
        if score >= _MED_RISK_SCORE:
            return "MEDIUM"
        return "LOW"

    def to_report(self) -> str:
        """Format collected debts as a human-readable report.

        Returns:
            Multi-line text report grouped by rot risk (HIGH/MEDIUM/LOW).
        """
        debts = self.collect()
        high = [d for d in debts if d.rot_risk == "HIGH"]
        med = [d for d in debts if d.rot_risk == "MEDIUM"]
        low = [d for d in debts if d.rot_risk == "LOW"]
        lines = [
            f"## Debt Collector Report (root: {self._root})",
            f"- Total: {len(debts)} "
            f"(HIGH: {len(high)}, MEDIUM: {len(med)}, LOW: {len(low)})",
            "",
        ]
        for risk_name, group in (
            ("HIGH", high), ("MEDIUM", med), ("LOW", low)
        ):
            if not group:
                continue
            lines.append(f"### {risk_name} ({len(group)})")
            for d in group:
                e = d.entry
                reason_str = "; ".join(d.reasons) if d.reasons else "n/a"
                lines.append(
                    f"- {e.file_path}:{e.line_number} [{e.marker}] "
                    f"({reason_str}) — {e.content[:60]}"
                )
            lines.append("")
        return "\n".join(lines)
