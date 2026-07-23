#!/usr/bin/env python3
"""
JudgeAgent — V3.8 #4: Judge Agent + History Learning.

Receives findings from reviewers (e.g. :class:`TwoStageReviewGate`,
security/tester workers) and arbitrates between them:

  1. **Deduplication** — Detect duplicate findings (same issue,
     different wording) and merge them.
  2. **Conflict resolution** — When two reviewers disagree on
     severity/category for the same issue, the judge picks the winner.
  3. **Confidence filtering** — Filter out low-confidence findings
     (threshold ≥0.7 by default).
  4. **Historical learning** — Use past decisions to inform current
     ones. **Off by default**; when enabled, records which findings
     were accepted/rejected by humans and uses TF-IDF / SequenceMatcher
     similarity to find similar past findings. History is *suggest
     only* — never auto-decides.

Inspired by Qodo PR-Agent's judge layer.

Integration
-----------
The agent is usable standalone via :meth:`JudgeAgent.judge` and is
designed to be wired into the post-dispatch pipeline (after the
two-stage review gate and severity router) to consolidate findings
before they are reported to the user.

Usage::

    from scripts.collaboration.judge_agent import JudgeAgent
    from scripts.collaboration.two_stage_review_gate import (
        ReviewFinding, ReviewStage,
    )

    judge = JudgeAgent()
    findings = [
        ReviewFinding(ReviewStage.CODE_QUALITY, "critical", "security", "SQL injection"),
        ReviewFinding(ReviewStage.CODE_QUALITY, "critical", "security", "SQL Injection vulnerability"),
        ReviewFinding(ReviewStage.CODE_QUALITY, "warning", "style", "Long line"),
    ]
    result = judge.judge(findings, context={})
    # result.accepted_findings  → deduplicated, accepted findings
    # result.rejected_count     → duplicates / low-confidence rejects
    # result.merged_count       → number of MERGE decisions
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from enum import Enum
from typing import Any

from .two_stage_review_gate import ReviewFinding

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class JudgeAction(Enum):
    """Actions the judge can take on a finding (or group of findings)."""

    ACCEPT = "accept"        # Finding accepted, will be reported
    REJECT = "reject"        # Finding rejected (duplicate, false positive)
    MERGE = "merge"          # Findings merged into one
    DOWNGRADE = "downgrade"  # Severity reduced
    UPGRADE = "upgrade"      # Severity increased
    DEFER = "defer"          # Defer to human judgment


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class JudgeDecision:
    """A single judge decision.

    Attributes
    ----------
    action:
        The :class:`JudgeAction` taken.
    finding_ids:
        IDs of the findings this decision applies to. For ``MERGE``,
        this contains all merged finding IDs.
    rationale:
        Human-readable explanation of the decision.
    confidence:
        Judge confidence in this decision (0.0-1.0).
    merged_finding:
        For ``MERGE`` actions, the consolidated :class:`ReviewFinding`.
        ``None`` for other actions.
    """

    action: JudgeAction
    finding_ids: list[str]
    rationale: str
    confidence: float = 1.0
    merged_finding: ReviewFinding | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action.value,
            "finding_ids": list(self.finding_ids),
            "rationale": self.rationale,
            "confidence": round(self.confidence, 3),
            "merged_finding": self.merged_finding.to_dict() if self.merged_finding else None,
        }


@dataclass
class JudgeResult:
    """Result of running :meth:`JudgeAgent.judge`.

    Attributes
    ----------
    decisions:
        All :class:`JudgeDecision` objects produced.
    accepted_findings:
        Findings that survived arbitration (post-dedup, post-filter).
    rejected_count:
        Number of findings rejected (duplicates, low-confidence).
    merged_count:
        Number of MERGE decisions made.
    deferred_count:
        Number of findings deferred to human judgment.
    history_used:
        True if historical decisions influenced the outcome.
    summary:
        Human-readable summary.
    """

    decisions: list[JudgeDecision] = field(default_factory=list)
    accepted_findings: list[ReviewFinding] = field(default_factory=list)
    rejected_count: int = 0
    merged_count: int = 0
    deferred_count: int = 0
    history_used: bool = False
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "decisions": [d.to_dict() for d in self.decisions],
            "accepted_findings": [f.to_dict() for f in self.accepted_findings],
            "rejected_count": self.rejected_count,
            "merged_count": self.merged_count,
            "deferred_count": self.deferred_count,
            "history_used": self.history_used,
            "summary": self.summary,
        }


# ---------------------------------------------------------------------------
# History record
# ---------------------------------------------------------------------------


@dataclass
class HistoryRecord:
    """A single historical decision record (for history learning).

    Stored as JSON on disk. Each record captures the finding text,
    category, severity, the judge action taken, whether a human
    overrode it, and a timestamp.
    """

    finding_text: str
    category: str
    severity: str
    action: str  # JudgeAction.value
    human_override: bool = False
    timestamp: float = 0.0
    record_id: str = ""

    def __post_init__(self) -> None:
        if not self.record_id:
            self.record_id = str(uuid.uuid4())
        if not self.timestamp:
            self.timestamp = time.time()

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "finding_text": self.finding_text,
            "category": self.category,
            "severity": self.severity,
            "action": self.action,
            "human_override": self.human_override,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> HistoryRecord:
        return cls(
            finding_text=str(d.get("finding_text", "")),
            category=str(d.get("category", "")),
            severity=str(d.get("severity", "")),
            action=str(d.get("action", "accept")),
            human_override=bool(d.get("human_override", False)),
            timestamp=float(d.get("timestamp", 0.0) or 0.0),
            record_id=str(d.get("record_id", "")) or str(uuid.uuid4()),
        )


# ---------------------------------------------------------------------------
# Judge Agent
# ---------------------------------------------------------------------------


class JudgeAgent:
    """Judge agent for finding arbitration, inspired by Qodo PR-Agent.

    Responsibilities:
      1. Deduplication — Detect duplicate findings (same issue, different wording)
      2. Conflict resolution — When two reviewers disagree, judge picks the winner
      3. Confidence filtering — Filter out low-confidence findings (threshold ≥0.7)
      4. Historical learning — Use past decisions to inform current ones

    History learning is **OFF by default**. When enabled:
      - Records which findings were accepted/rejected by humans
      - Uses TF-IDF similarity to find similar past findings
      - Suggests action based on past outcomes (suggest only, never auto-decide)

    Parameters
    ----------
    confidence_threshold:
        Minimum confidence (0.0-1.0) for a finding to be accepted.
        Findings below this threshold are rejected. Default 0.7.
    similarity_threshold:
        Minimum text similarity (0.0-1.0) for two findings to be
        considered duplicates. Default 0.85.
    enable_history:
        Whether to load and use historical decisions. Default False.
        Use :meth:`enable_history_learning` to enable after construction.
    """

    # Default confidence assigned to findings that don't carry one.
    # Most ReviewFinding objects don't have an explicit confidence
    # attribute, so we treat them as fully confident (1.0) and let
    # the judge's own logic decide.
    DEFAULT_FINDING_CONFIDENCE: float = 1.0

    def __init__(
        self,
        confidence_threshold: float = 0.7,
        similarity_threshold: float = 0.85,
        enable_history: bool = False,
    ) -> None:
        self.confidence_threshold = confidence_threshold
        self.similarity_threshold = similarity_threshold
        self.history_enabled = enable_history
        self._storage_path: str | None = None
        self._history: list[HistoryRecord] = []

        if enable_history:
            # History enabled without a path — use a default in-memory
            # store (no persistence). record_decision will be a no-op
            # for persistence but still track in-memory.
            self._history = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def judge(
        self,
        findings: list[ReviewFinding],
        context: dict[str, Any] | None = None,
    ) -> JudgeResult:
        """Main entry point — arbitrate a list of findings.

        Parameters
        ----------
        findings:
            List of :class:`ReviewFinding` objects to judge.
        context:
            Optional context dict (e.g. task info, reviewer metadata).

        Returns
        -------
        JudgeResult
        """
        context = context or {}
        if not findings:
            return JudgeResult(
                decisions=[],
                accepted_findings=[],
                summary="JudgeAgent: no findings to judge.",
            )

        # Assign IDs to findings (for tracking). We attach the ID via
        # a side-channel dict because ReviewFinding is a frozen-ish
        # dataclass (it isn't actually frozen, but we don't want to
        # mutate the input).
        finding_ids: dict[int, str] = {
            id(f): str(uuid.uuid4()) for f in findings
        }

        decisions: list[JudgeDecision] = []
        history_used = False

        # Step 1: Deduplication
        dedup_decisions, unique_findings = self._deduplicate_with_decisions(
            findings, finding_ids
        )
        decisions.extend(dedup_decisions)

        # Step 2: Conflict resolution
        conflict_decisions, post_conflict = self._resolve_conflicts_with_decisions(
            unique_findings, finding_ids
        )
        decisions.extend(conflict_decisions)
        # post_conflict may have updated severities — use it going forward.
        current_findings = post_conflict

        # Step 3: Confidence filtering
        filter_decisions, post_filter = self._filter_by_confidence_with_decisions(
            current_findings, finding_ids, self.confidence_threshold
        )
        decisions.extend(filter_decisions)
        current_findings = post_filter

        # Step 4: Historical learning (suggest only)
        if self.history_enabled and self._history:
            history_decisions, history_used = self._apply_history_with_decisions(
                current_findings, finding_ids
            )
            decisions.extend(history_decisions)

        # Accepted findings = those that survived all stages and were
        # not rejected/deferred by any decision.
        rejected_ids: set[str] = set()
        deferred_ids: set[str] = set()
        for d in decisions:
            if d.action == JudgeAction.REJECT:
                rejected_ids.update(d.finding_ids)
            elif d.action == JudgeAction.DEFER:
                deferred_ids.update(d.finding_ids)
        accepted = [
            f for f in current_findings
            if finding_ids[id(f)] not in rejected_ids
            and finding_ids[id(f)] not in deferred_ids
        ]

        rejected_count = len(rejected_ids)
        merged_count = sum(1 for d in decisions if d.action == JudgeAction.MERGE)
        deferred_count = len(deferred_ids)

        summary = self._build_summary(
            total_input=len(findings),
            accepted=len(accepted),
            rejected=rejected_count,
            merged=merged_count,
            deferred=deferred_count,
            history_used=history_used,
        )

        return JudgeResult(
            decisions=decisions,
            accepted_findings=accepted,
            rejected_count=rejected_count,
            merged_count=merged_count,
            deferred_count=deferred_count,
            history_used=history_used,
            summary=summary,
        )

    # ------------------------------------------------------------------
    # Deduplication
    # ------------------------------------------------------------------

    def _deduplicate(
        self, findings: list[ReviewFinding]
    ) -> list[JudgeDecision]:
        """Detect duplicates via text similarity.

        Returns a list of MERGE/REJECT decisions. Findings above the
        similarity threshold are merged; the duplicates are rejected.
        """
        # We need IDs — but _deduplicate is the legacy signature that
        # doesn't take IDs. Delegate to the new signature with synthetic IDs.
        finding_ids: dict[int, str] = {
            id(f): str(uuid.uuid4()) for f in findings
        }
        return self._deduplicate_with_decisions(findings, finding_ids)[0]

    def _deduplicate_with_decisions(
        self,
        findings: list[ReviewFinding],
        finding_ids: dict[int, str],
    ) -> tuple[list[JudgeDecision], list[ReviewFinding]]:
        """Detect duplicates and return (decisions, unique_findings).

        For each group of duplicate findings:
          - The first finding is kept (canonical).
          - A MERGE decision is recorded with the merged finding.
          - Subsequent duplicates get a REJECT decision.
        """
        decisions: list[JudgeDecision] = []
        unique: list[ReviewFinding] = []
        # Track which original IDs were merged into each canonical finding.
        # Each entry is (canonical_finding, [finding_ids_merged_into_it]).
        merged_groups: list[tuple[ReviewFinding, list[str]]] = []

        for finding in findings:
            fid = finding_ids[id(finding)]
            duplicate_of = None
            for canonical, _ in merged_groups:
                if self._is_duplicate(finding, canonical):
                    duplicate_of = canonical
                    break

            if duplicate_of is None:
                # New unique finding
                unique.append(finding)
                merged_groups.append((finding, [fid]))
            else:
                # Duplicate — find the canonical's group and add this ID.
                for canon, ids in merged_groups:
                    if canon is duplicate_of:
                        ids.append(fid)
                        break

        # Emit MERGE decisions for groups with >1 finding.
        for canon, ids in merged_groups:
            if len(ids) > 1:
                merged_finding = ReviewFinding(
                    stage=canon.stage,
                    severity=canon.severity,
                    category=canon.category,
                    description=canon.description,
                    file_path=canon.file_path,
                    line_range=canon.line_range,
                    suggestion=canon.suggestion,
                )
                decisions.append(
                    JudgeDecision(
                        action=JudgeAction.MERGE,
                        finding_ids=list(ids),
                        rationale=(
                            f"Merged {len(ids)} duplicate findings on "
                            f"'{canon.description[:60]}'"
                        ),
                        confidence=0.9,
                        merged_finding=merged_finding,
                    )
                )
                # The duplicates (all but the first ID) are also REJECTed
                # so they don't appear in accepted_findings.
                for dup_id in ids[1:]:
                    decisions.append(
                        JudgeDecision(
                            action=JudgeAction.REJECT,
                            finding_ids=[dup_id],
                            rationale="Duplicate of an already-accepted finding.",
                            confidence=0.9,
                        )
                    )

        return decisions, unique

    def _is_duplicate(
        self, a: ReviewFinding, b: ReviewFinding
    ) -> bool:
        """Return True if two findings are duplicates.

        Two findings are duplicates when:
          - They are in the same category (or one is empty), AND
          - They have the same severity (duplicates are the same issue
            reported the same way; different severities → conflict
            resolution instead), AND
          - Their descriptions are highly similar (≥ similarity_threshold).
        """
        # Category must match (allowing empty categories to match anything).
        if a.category and b.category and a.category != b.category:
            return False
        # Severity must match — different severities on the same issue
        # are a conflict (handled by _resolve_conflicts), not a duplicate.
        if a.severity != b.severity:
            return False
        # Description similarity.
        sim = self._text_similarity(a.description, b.description)
        return sim >= self.similarity_threshold

    @staticmethod
    def _text_similarity(a: str, b: str) -> float:
        """Compute text similarity between two strings.

        Uses :class:`difflib.SequenceMatcher` (no external deps).
        Returns a float in [0.0, 1.0].
        """
        if not a or not b:
            return 0.0
        # Normalize: lowercase, strip, collapse whitespace.
        a_norm = " ".join(a.lower().split())
        b_norm = " ".join(b.lower().split())
        if a_norm == b_norm:
            return 1.0
        return SequenceMatcher(None, a_norm, b_norm).ratio()

    # ------------------------------------------------------------------
    # Conflict resolution
    # ------------------------------------------------------------------

    def _resolve_conflicts(
        self, findings: list[ReviewFinding]
    ) -> list[JudgeDecision]:
        """Resolve conflicting findings (legacy signature)."""
        finding_ids: dict[int, str] = {
            id(f): str(uuid.uuid4()) for f in findings
        }
        return self._resolve_conflicts_with_decisions(findings, finding_ids)[0]

    def _resolve_conflicts_with_decisions(
        self,
        findings: list[ReviewFinding],
        finding_ids: dict[int, str],
    ) -> tuple[list[JudgeDecision], list[ReviewFinding]]:
        """Resolve conflicts where two findings disagree on severity.

        When two findings are about the same issue (high similarity)
        but have different severities, the judge picks the higher
        severity (defensive — never downgrade via conflict resolution).
        Returns (decisions, possibly-updated findings).

        Also updates ``finding_ids`` in place when a finding object is
        replaced (so the ID mapping stays consistent).
        """
        decisions: list[JudgeDecision] = []
        # Work on a copy so we can mutate severities.
        updated: list[ReviewFinding] = list(findings)

        severity_rank = {"info": 0, "low": 1, "warning": 2, "medium": 2,
                         "high": 3, "critical": 4}

        for i, a in enumerate(updated):
            for j in range(i + 1, len(updated)):
                b = updated[j]
                # Same issue but different severity → conflict.
                if (a.severity != b.severity
                        and self._text_similarity(a.description, b.description)
                        >= self.similarity_threshold):
                    # Pick the higher severity.
                    rank_a = severity_rank.get(a.severity, 0)
                    rank_b = severity_rank.get(b.severity, 0)
                    if rank_a >= rank_b:
                        winner, loser = a, b
                        loser_idx = j
                    else:
                        winner, loser = b, a
                        loser_idx = i
                    # Upgrade the loser to the winner's severity.
                    loser_id = finding_ids[id(loser)]
                    new_loser = ReviewFinding(
                        stage=loser.stage,
                        severity=winner.severity,
                        category=loser.category,
                        description=loser.description,
                        file_path=loser.file_path,
                        line_range=loser.line_range,
                        suggestion=loser.suggestion,
                    )
                    # Update the finding_ids mapping: remove the old
                    # object's id, add the new object's id with the
                    # same UUID.
                    del finding_ids[id(loser)]
                    finding_ids[id(new_loser)] = loser_id
                    updated[loser_idx] = new_loser
                    decisions.append(
                        JudgeDecision(
                            action=JudgeAction.UPGRADE,
                            finding_ids=[loser_id],
                            rationale=(
                                f"Severity upgraded from '{loser.severity}' to "
                                f"'{winner.severity}' to match conflicting "
                                f"finding on the same issue."
                            ),
                            confidence=0.8,
                        )
                    )
                    # Update local reference if 'a' was replaced.
                    if loser_idx == i:
                        a = new_loser
        return decisions, updated

    # ------------------------------------------------------------------
    # Confidence filtering
    # ------------------------------------------------------------------

    def _filter_by_confidence(
        self,
        findings: list[ReviewFinding],
        threshold: float = 0.7,
    ) -> list[JudgeDecision]:
        """Filter low-confidence findings (legacy signature)."""
        finding_ids: dict[int, str] = {
            id(f): str(uuid.uuid4()) for f in findings
        }
        return self._filter_by_confidence_with_decisions(
            findings, finding_ids, threshold
        )[0]

    def _filter_by_confidence_with_decisions(
        self,
        findings: list[ReviewFinding],
        finding_ids: dict[int, str],
        threshold: float = 0.7,
    ) -> tuple[list[JudgeDecision], list[ReviewFinding]]:
        """Filter findings below the confidence threshold.

        ReviewFinding doesn't carry an explicit confidence, so we
        derive a heuristic confidence:
          - Critical findings → 1.0 (always kept)
          - Findings with a suggestion → 0.9 (actionable)
          - Findings with a file_path → 0.8 (located)
          - Otherwise → 0.5 (rejected by default)

        Returns (reject_decisions, surviving_findings).
        """
        decisions: list[JudgeDecision] = []
        surviving: list[ReviewFinding] = []
        for f in findings:
            conf = self._derive_confidence(f)
            if conf >= threshold:
                surviving.append(f)
            else:
                decisions.append(
                    JudgeDecision(
                        action=JudgeAction.REJECT,
                        finding_ids=[finding_ids[id(f)]],
                        rationale=(
                            f"Confidence {conf:.2f} below threshold "
                            f"{threshold:.2f}."
                        ),
                        confidence=conf,
                    )
                )
        return decisions, surviving

    @staticmethod
    def _derive_confidence(finding: ReviewFinding) -> float:
        """Derive a heuristic confidence for a ReviewFinding."""
        # If the finding carries an explicit confidence attribute, use it.
        explicit = getattr(finding, "confidence", None)
        if isinstance(explicit, (int, float)):
            return float(explicit)
        if finding.severity == "critical":
            return 1.0
        if finding.suggestion:
            return 0.9
        if finding.file_path:
            return 0.8
        return 0.5

    # ------------------------------------------------------------------
    # Historical learning
    # ------------------------------------------------------------------

    def _apply_history(
        self, findings: list[ReviewFinding]
    ) -> list[JudgeDecision]:
        """Apply historical patterns (legacy signature)."""
        finding_ids: dict[int, str] = {
            id(f): str(uuid.uuid4()) for f in findings
        }
        return self._apply_history_with_decisions(findings, finding_ids)[0]

    def _apply_history_with_decisions(
        self,
        findings: list[ReviewFinding],
        finding_ids: dict[int, str],
    ) -> tuple[list[JudgeDecision], bool]:
        """Suggest actions based on historical decisions.

        For each finding, find the most similar past record. If a
        similar record exists (similarity ≥ 0.7) and the past action
        was REJECT, suggest DEFER (suggest only — never auto-reject).
        Returns (decisions, history_used).
        """
        decisions: list[JudgeDecision] = []
        history_used = False

        for f in findings:
            best_record, best_sim = self._find_similar_history(f)
            if best_record is None or best_sim < 0.7:
                continue
            history_used = True
            # Suggest only: if history says REJECT, defer to human.
            if best_record.action == JudgeAction.REJECT.value:
                decisions.append(
                    JudgeDecision(
                        action=JudgeAction.DEFER,
                        finding_ids=[finding_ids[id(f)]],
                        rationale=(
                            f"Similar past finding was rejected "
                            f"(similarity={best_sim:.2f}). Deferring to "
                            f"human judgment."
                        ),
                        confidence=best_sim,
                    )
                )
            elif best_record.action == JudgeAction.ACCEPT.value:
                # History says accept — record a low-confidence ACCEPT
                # suggestion (informational; the finding is already
                # accepted by default).
                decisions.append(
                    JudgeDecision(
                        action=JudgeAction.ACCEPT,
                        finding_ids=[finding_ids[id(f)]],
                        rationale=(
                            f"Similar past finding was accepted "
                            f"(similarity={best_sim:.2f})."
                        ),
                        confidence=best_sim,
                    )
                )
        return decisions, history_used

    def _find_similar_history(
        self, finding: ReviewFinding
    ) -> tuple[HistoryRecord | None, float]:
        """Find the most similar historical record for a finding.

        Returns (best_record, best_similarity). If no history exists,
        returns (None, 0.0).
        """
        if not self._history:
            return None, 0.0
        best: HistoryRecord | None = None
        best_sim = 0.0
        for record in self._history:
            sim = self._text_similarity(finding.description, record.finding_text)
            if sim > best_sim:
                best_sim = sim
                best = record
        return best, best_sim

    # ------------------------------------------------------------------
    # History storage
    # ------------------------------------------------------------------

    def enable_history_learning(self, storage_path: str) -> None:
        """Enable history learning, loading records from ``storage_path``.

        Creates the file (and parent directories) if it doesn't exist.

        Parameters
        ----------
        storage_path:
            Path to a JSON file containing a list of :class:`HistoryRecord`
            dicts. The file will be created if missing.
        """
        self.history_enabled = True
        self._storage_path = storage_path
        # Ensure parent directory exists.
        parent = os.path.dirname(storage_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        # Load existing records.
        self._history = self._load_history()

    def _load_history(self) -> list[HistoryRecord]:
        """Load history records from the storage path."""
        if not self._storage_path:
            return []
        if not os.path.exists(self._storage_path):
            return []
        try:
            with open(self._storage_path, encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                return []
            return [HistoryRecord.from_dict(d) for d in data if isinstance(d, dict)]
        except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
            logger.warning("JudgeAgent: failed to load history from %s: %s",
                           self._storage_path, exc)
            return []

    def _save_history(self) -> None:
        """Persist history records to the storage path."""
        if not self._storage_path:
            return  # In-memory only.
        try:
            with open(self._storage_path, "w", encoding="utf-8") as f:
                json.dump([r.to_dict() for r in self._history], f, indent=2)
        except (OSError, TypeError, ValueError) as exc:
            logger.warning("JudgeAgent: failed to save history to %s: %s",
                           self._storage_path, exc)

    def record_decision(
        self,
        decision: JudgeDecision,
        human_override: bool = False,
    ) -> None:
        """Record a decision for future learning.

        Records one :class:`HistoryRecord` per finding ID in the
        decision. Only meaningful when history learning is enabled;
        otherwise this is a no-op.

        Parameters
        ----------
        decision:
            The :class:`JudgeDecision` to record.
        human_override:
            True if a human overrode the judge's decision.
        """
        if not self.history_enabled:
            return
        # We don't have the original finding text here (only IDs),
        # so we record the merged_finding description if available,
        # or the rationale as a fallback.
        text = ""
        if decision.merged_finding is not None:
            text = decision.merged_finding.description
        elif decision.rationale:
            text = decision.rationale
        category = ""
        severity = ""
        if decision.merged_finding is not None:
            category = decision.merged_finding.category
            severity = decision.merged_finding.severity
        for _fid in decision.finding_ids:
            record = HistoryRecord(
                finding_text=text,
                category=category,
                severity=severity,
                action=decision.action.value,
                human_override=human_override,
            )
            self._history.append(record)
        self._save_history()

    def get_history_stats(self) -> dict[str, Any]:
        """Statistics about historical decisions.

        Returns a dict with counts by action, total records, and
        human-override rate.
        """
        total = len(self._history)
        if total == 0:
            return {
                "total": 0,
                "by_action": {},
                "human_overrides": 0,
                "human_override_rate": 0.0,
                "history_enabled": self.history_enabled,
            }
        by_action: dict[str, int] = {}
        overrides = 0
        for r in self._history:
            by_action[r.action] = by_action.get(r.action, 0) + 1
            if r.human_override:
                overrides += 1
        return {
            "total": total,
            "by_action": by_action,
            "human_overrides": overrides,
            "human_override_rate": round(overrides / total, 3),
            "history_enabled": self.history_enabled,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_summary(
        self,
        total_input: int,
        accepted: int,
        rejected: int,
        merged: int,
        deferred: int,
        history_used: bool,
    ) -> str:
        """Build a human-readable summary string."""
        lines = [
            f"JudgeAgent: {accepted}/{total_input} findings accepted.",
            f"  Rejected: {rejected}",
            f"  Merged: {merged}",
            f"  Deferred: {deferred}",
            f"  History used: {history_used}",
        ]
        return "\n".join(lines)


__all__ = [
    "HistoryRecord",
    "JudgeAction",
    "JudgeAgent",
    "JudgeDecision",
    "JudgeResult",
]
