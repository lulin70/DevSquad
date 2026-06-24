#!/usr/bin/env python3
"""
SkillStorage - Skill persistence and data management

Manages in-memory storage of execution records, patterns, and proposals.
Provides query, export, and publishing capabilities.
"""

import json
import re
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Any

from .skillifier import (
    ExecutionRecord,
    ProposalStatus,
    SkillProposal,
    SuccessPattern,
)


class SkillStorage:
    """Manages storage and retrieval of execution records, patterns, and proposals."""

    def __init__(self) -> None:
        self._records: list[ExecutionRecord] = []
        self._patterns: list[SuccessPattern] = []
        self._proposals: dict[str, SkillProposal] = {}
        self._lock = threading.RLock()

    # ================================================================
    # Record Management
    # ================================================================

    def record_execution(self, record: ExecutionRecord) -> None:
        """Finalize and append an execution record to the store.

        Args:
            record: ExecutionRecord to finalize and persist in memory.
        """
        with self._lock:
            record.finalize()
            self._records.append(record)

    def get_records(
        self, since: datetime | None = None, until: datetime | None = None, success_only: bool = True
    ) -> list[ExecutionRecord]:
        """Query stored execution records by time range and success status.

        Args:
            since: Optional inclusive lower bound on record start_time.
            until: Optional inclusive upper bound on record start_time.
            success_only: When True (default), only successful records are returned.

        Returns:
            List of ExecutionRecord matching the filters.
        """
        results = self._records
        if since:
            results = [r for r in results if r.start_time >= since]
        if until:
            results = [r for r in results if r.start_time <= until]
        if success_only:
            results = [r for r in results if r.success]
        return list(results)

    # ================================================================
    # Pattern Management
    # ================================================================

    def add_pattern(self, pattern: SuccessPattern) -> None:
        """Add a success pattern to the store, skipping duplicates by pattern_id.

        Args:
            pattern: SuccessPattern to add.
        """
        with self._lock:
            existing_ids = {p.pattern_id for p in self._patterns}
            if pattern.pattern_id not in existing_ids:
                self._patterns.append(pattern)

    def add_patterns(self, patterns: list[SuccessPattern]) -> None:
        """Add multiple success patterns, skipping duplicates by pattern_id.

        Args:
            patterns: List of SuccessPattern instances to add.
        """
        with self._lock:
            existing_ids = {p.pattern_id for p in self._patterns}
            for pattern in patterns:
                if pattern.pattern_id not in existing_ids:
                    self._patterns.append(pattern)
                    existing_ids.add(pattern.pattern_id)

    def get_patterns(self) -> list[SuccessPattern]:
        """Return a copy of all stored success patterns.

        Returns:
            List of SuccessPattern currently in storage.
        """
        return list(self._patterns)

    # ================================================================
    # Proposal Management
    # ================================================================

    def add_proposal(self, proposal: SkillProposal) -> None:
        """Add or replace a skill proposal keyed by proposal_id.

        Args:
            proposal: SkillProposal to store.
        """
        with self._lock:
            self._proposals[proposal.proposal_id] = proposal

    def get_proposal(self, proposal_id: str) -> SkillProposal | None:
        """Retrieve a single proposal by id.

        Args:
            proposal_id: Identifier of the proposal to retrieve.

        Returns:
            SkillProposal with the given id, or None if not found.
        """
        return self._proposals.get(proposal_id)

    def get_proposals(self, status: ProposalStatus | None = None) -> list[SkillProposal]:
        """List proposals, optionally filtered by status.

        Args:
            status: Optional ProposalStatus value to filter by.

        Returns:
            List of SkillProposal matching the status filter (or all if None).
        """
        props = list(self._proposals.values())
        if status:
            props = [p for p in props if p.status == status]
        return props

    # ================================================================
    # Publishing & Discovery
    # ================================================================

    def approve_and_publish(self, proposal_id: str, approver: str = "system") -> bool:
        """Mark a proposal as published, recording the approver and timestamp.

        Args:
            proposal_id: Identifier of the proposal to publish.
            approver: Name of the approver (default "system").

        Returns:
            True if the proposal exists (already published or newly published),
            False if the proposal id is unknown.
        """
        with self._lock:
            proposal = self._proposals.get(proposal_id)
            if not proposal:
                return False
            if proposal.status == ProposalStatus.PUBLISHED:
                return True
            proposal.status = ProposalStatus.PUBLISHED
            proposal.approved_by = approver
            proposal.published_at = datetime.now()
            return True

    def suggest_skills_for_task(self, task_description: str) -> list[SkillProposal]:
        """Suggest approved/published skills whose trigger conditions match a task.

        Args:
            task_description: Natural language description of the task.

        Returns:
            List of up to 10 SkillProposal sorted by relevance score (descending).
        """
        task_lower = task_description.lower()
        task_words = set(re.findall(r"\w{3,}", task_lower))
        scored = []
        for prop in self._proposals.values():
            if prop.status not in (ProposalStatus.APPROVED, ProposalStatus.PUBLISHED):
                continue
            score = 0.0
            for tc in prop.trigger_conditions:
                if tc.lower() in task_lower:
                    score += 2.0
                for tw in task_words:
                    if tw in tc.lower():
                        score += 0.5
            if prop.quality_score >= 70:
                score += 1.0
            if score > 0:
                scored.append((score, prop))

        scored.sort(key=lambda x: -x[0])
        return [p for _, p in scored[:10]]

    # ================================================================
    # Query & Export
    # ================================================================

    def export_patterns(self) -> str:
        """Serialize all success patterns to a JSON string.

        Returns:
            Indented JSON string of pattern dictionaries.
        """
        return json.dumps([p.to_dict() for p in self._patterns], indent=2, ensure_ascii=False, default=str)

    def export_state(self) -> dict:
        """Export a serializable snapshot of the storage state.

        Returns:
            Dictionary with record/pattern/proposal counts, pattern dicts,
            and proposal ids.
        """
        with self._lock:
            return {
                "records_count": len(self._records),
                "patterns_count": len(self._patterns),
                "proposals_count": len(self._proposals),
                "patterns": [p.to_dict() for p in self._patterns],
                "proposal_ids": list(self._proposals.keys()),
            }

    def get_statistics(self) -> dict[str, Any]:
        """Compute aggregate statistics over records, patterns, and proposals.

        Returns:
            Dictionary with totals, published count, average confidence,
            and average quality score.
        """
        with self._lock:
            published = sum(1 for p in self._proposals.values() if p.status == ProposalStatus.PUBLISHED)
            avg_confidence = 0.0
            if self._patterns:
                avg_confidence = sum(p.confidence for p in self._patterns) / len(self._patterns)
            avg_quality = 0.0
            validated = [p for p in self._proposals.values() if p.validation_result]
            if validated:
                avg_quality = sum(p.quality_score for p in validated) / len(validated)
            return {
                "total_records": len(self._records),
                "successful_records": sum(1 for r in self._records if r.success),
                "total_patterns": len(self._patterns),
                "total_proposals": len(self._proposals),
                "published_skills": published,
                "avg_pattern_confidence": round(avg_confidence, 3),
                "avg_quality_score": round(avg_quality, 1),
            }

    # ================================================================
    # Public Accessors (replacing direct private attribute access)
    # ================================================================

    def get_all_records(self) -> list[ExecutionRecord]:
        """Return the full internal records list (not a copy, for performance)."""
        return self._records

    def set_all_records(self, records: list[ExecutionRecord]) -> None:
        """Replace the internal records list."""
        self._records = records

    def get_all_patterns(self) -> list[SuccessPattern]:
        """Return the full internal patterns list (not a copy, for performance)."""
        return self._patterns

    def set_all_patterns(self, patterns: list[SuccessPattern]) -> None:
        """Replace the internal patterns list."""
        self._patterns = patterns

    def get_all_proposals(self) -> dict[str, SkillProposal]:
        """Return the full internal proposals dict (not a copy, for performance)."""
        return self._proposals

    def set_all_proposals(self, proposals: dict[str, SkillProposal]) -> None:
        """Replace the internal proposals dict."""
        self._proposals = proposals

    @contextmanager
    def thread_safe(self) -> Iterator[None]:
        """Context manager for thread-safe operations on storage data.

        Usage:
            with storage.thread_safe():
                records = storage.get_all_records()
                # ... modify records ...
        """
        with self._lock:
            yield
