#!/usr/bin/env python3
"""
SkillStorage - Skill persistence and data management

Manages in-memory storage of execution records, patterns, and proposals.
Provides query, export, and publishing capabilities.
"""

import json
import re
import threading
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

    def __init__(self):
        self._records: list[ExecutionRecord] = []
        self._patterns: list[SuccessPattern] = []
        self._proposals: dict[str, SkillProposal] = {}
        self._lock = threading.RLock()

    # ================================================================
    # Record Management
    # ================================================================

    def record_execution(self, record: ExecutionRecord) -> None:
        with self._lock:
            record.finalize()
            self._records.append(record)

    def get_records(
        self, since: datetime = None, until: datetime = None, success_only: bool = True
    ) -> list[ExecutionRecord]:
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
        with self._lock:
            existing_ids = {p.pattern_id for p in self._patterns}
            if pattern.pattern_id not in existing_ids:
                self._patterns.append(pattern)

    def add_patterns(self, patterns: list[SuccessPattern]) -> None:
        with self._lock:
            existing_ids = {p.pattern_id for p in self._patterns}
            for pattern in patterns:
                if pattern.pattern_id not in existing_ids:
                    self._patterns.append(pattern)
                    existing_ids.add(pattern.pattern_id)

    def get_patterns(self) -> list[SuccessPattern]:
        return list(self._patterns)

    # ================================================================
    # Proposal Management
    # ================================================================

    def add_proposal(self, proposal: SkillProposal) -> None:
        with self._lock:
            self._proposals[proposal.proposal_id] = proposal

    def get_proposal(self, proposal_id: str) -> SkillProposal | None:
        return self._proposals.get(proposal_id)

    def get_proposals(self, status=None) -> list[SkillProposal]:
        props = list(self._proposals.values())
        if status:
            props = [p for p in props if p.status == status]
        return props

    # ================================================================
    # Publishing & Discovery
    # ================================================================

    def approve_and_publish(self, proposal_id: str, approver: str = "system") -> bool:
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
        return json.dumps([p.to_dict() for p in self._patterns], indent=2, ensure_ascii=False, default=str)

    def export_state(self) -> dict:
        with self._lock:
            return {
                "records_count": len(self._records),
                "patterns_count": len(self._patterns),
                "proposals_count": len(self._proposals),
                "patterns": [p.to_dict() for p in self._patterns],
                "proposal_ids": list(self._proposals.keys()),
            }

    def get_statistics(self) -> dict[str, Any]:
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
