#!/usr/bin/env python3
"""
FeatureUsageTracker - V3.7.0 Feature Usage Statistics

Tracks invocation counts for all DevSquad features, enabling
data-driven decisions about which features to strengthen, simplify,
or deprecate.

Design:
- Thread-safe counter with atomic increments
- Zero overhead when disabled (feature_flag check)
- Periodic persistence to JSON
- Query API for usage reports
"""

import json
import logging
import threading
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class FeatureUsageTracker:
    """
    Thread-safe feature usage counter.

    Usage:
        tracker = FeatureUsageTracker()
        tracker.tick("anchor_check")
        tracker.tick("anchor_check")
        tracker.tick("retrospective")
        print(tracker.report())
        # {"anchor_check": 2, "retrospective": 1}
    """

    KNOWN_FEATURES = frozenset(
        [
            "dispatch",
            "anchor_check",
            "anchor_drift_detected",
            "retrospective",
            "retrospective_stored",
            "retrospective_loaded",
            "fallback_backend_primary",
            "fallback_backend_failover",
            "consensus_vote",
            "consensus_split",
            "consensus_escalated",
            "checkpoint_save",
            "checkpoint_load",
            "workflow_step",
            "workflow_handoff",
            "lifecycle_gate_check",
            "lifecycle_gate_blocked",
            "permission_check",
            "permission_blocked",
            "input_validation",
            "input_blocked",
            "context_compression",
            "memory_capture",
            "memory_recall",
            "skillify_proposal",
            "semantic_matcher",
            "role_matcher",
            "prompt_assembly",
            "verification_gate",
            "task_completion_check",
        ]
    )

    def __init__(self, persist_path: str | None = None, auto_persist_interval: int = 100):
        self._counts: dict[str, int] = defaultdict(int)
        self._first_seen: dict[str, str] = {}
        self._last_seen: dict[str, str] = {}
        self._lock = threading.RLock()
        self._persist_path = persist_path
        self._auto_persist_interval = auto_persist_interval
        self._total_ticks = 0
        self._session_start = datetime.now().isoformat()
        if persist_path:
            self._load(persist_path)

    def tick(self, feature: str, count: int = 1) -> int:
        """Increment usage count for a feature. Returns new count."""
        now = datetime.now().isoformat()
        with self._lock:
            self._counts[feature] += count
            if feature not in self._first_seen:
                self._first_seen[feature] = now
            self._last_seen[feature] = now
            self._total_ticks += count

        if (
            self._persist_path
            and self._auto_persist_interval > 0
            and self._total_ticks % self._auto_persist_interval == 0
        ):
            self.persist()

        return self._counts[feature]

    def get_count(self, feature: str) -> int:
        """Return the invocation count for a feature.

        Args:
            feature: Feature name.

        Returns:
            Number of times the feature has been recorded; 0 if never seen.
        """
        with self._lock:
            return self._counts.get(feature, 0)

    def get_all_counts(self) -> dict[str, int]:
        """Return a copy of all feature invocation counts.

        Returns:
            Dictionary mapping feature name to invocation count.
        """
        with self._lock:
            return dict(self._counts)

    def get_unused_features(self) -> list[str]:
        """Return known features that have never been recorded.

        Returns:
            Sorted list of feature names with zero invocations.
        """
        used = set(self._counts.keys())
        return sorted(self.KNOWN_FEATURES - used)

    def get_low_usage_features(self, threshold: int = 3) -> list[str]:
        """Return features whose invocation count is at or below a threshold.

        Args:
            threshold: Maximum count (inclusive) to be considered low usage.
                Defaults to 3.

        Returns:
            Sorted list of feature names with count <= threshold.
        """
        return sorted(f for f, c in self._counts.items() if c <= threshold)

    def get_high_usage_features(self, top_n: int = 10) -> list[tuple]:
        """Return the most-used features.

        Args:
            top_n: Maximum number of features to return. Defaults to 10.

        Returns:
            List of (feature, count) tuples sorted by count descending.
        """
        with self._lock:
            sorted_features = sorted(self._counts.items(), key=lambda x: x[1], reverse=True)
        return sorted_features[:top_n]

    def report(self) -> dict[str, Any]:
        """Build a summary report of feature usage for the current session.

        Returns:
            Dictionary with session_start, total_invocations, coverage_ratio,
            top/unused/low-usage features, and per-feature detail.
        """
        with self._lock:
            total = sum(self._counts.values())
            return {
                "session_start": self._session_start,
                "total_invocations": total,
                "unique_features_used": len(self._counts),
                "unique_features_available": len(self.KNOWN_FEATURES),
                "coverage_ratio": len(self._counts) / max(len(self.KNOWN_FEATURES), 1),
                "top_features": self.get_high_usage_features(10),
                "unused_features": self.get_unused_features(),
                "low_usage_features": self.get_low_usage_features(3),
                "feature_details": {
                    f: {
                        "count": c,
                        "first_seen": self._first_seen.get(f, ""),
                        "last_seen": self._last_seen.get(f, ""),
                    }
                    for f, c in sorted(self._counts.items(), key=lambda x: x[1], reverse=True)
                },
            }

    def report_markdown(self) -> str:
        """Build a Markdown report of feature usage.

        Returns:
            Markdown string with session metadata, top features table, and
            lists of unused and low-usage features.
        """
        r = self.report()
        lines = [
            "# Feature Usage Report",
            "",
            f"**Session**: {r['session_start']}",
            f"**Total Invocations**: {r['total_invocations']}",
            f"**Features Used**: {r['unique_features_used']}/{r['unique_features_available']} ({r['coverage_ratio']:.0%})",
            "",
            "## Top Features",
            "",
            "| Feature | Count |",
            "|---------|-------|",
        ]
        for feat, count in r["top_features"]:
            lines.append(f"| {feat} | {count} |")

        if r["unused_features"]:
            lines.extend(["", "## Unused Features", ""])
            for f in r["unused_features"]:
                lines.append(f"- {f}")

        if r["low_usage_features"]:
            lines.extend(["", "## Low Usage Features (≤3)", ""])
            for f in r["low_usage_features"]:
                lines.append(f"- {f} ({self._counts.get(f, 0)})")

        lines.extend(["", "---", "*Generated by FeatureUsageTracker V3.7.0*"])
        return "\n".join(lines)

    def persist(self, path: str | None = None):
        """Persist the current usage report to disk as JSON.

        Args:
            path: Optional output path; defaults to the configured persist path.
                When neither is set, the call is a no-op.
        """
        target = path or self._persist_path
        if not target:
            return
        try:
            data = self.report()
            Path(target).parent.mkdir(parents=True, exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.debug("Feature usage persisted to %s", target)
        except (OSError, TypeError, ValueError) as e:
            logger.warning("Failed to persist feature usage: %s", e)

    def _load(self, path: str):
        try:
            if Path(path).exists():
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                for feat, info in data.get("feature_details", {}).items():
                    self._counts[feat] = info.get("count", 0)
                    self._first_seen[feat] = info.get("first_seen", "")
                    self._last_seen[feat] = info.get("last_seen", "")
                logger.info("Loaded %d feature usage records from %s", len(self._counts), path)
        except (json.JSONDecodeError, OSError, KeyError, TypeError) as e:
            logger.warning("Failed to load feature usage: %s", e)

    def reset(self):
        """Clear all usage counts and timestamps, resetting the tracker."""
        with self._lock:
            self._counts.clear()
            self._first_seen.clear()
            self._last_seen.clear()
            self._total_ticks = 0
