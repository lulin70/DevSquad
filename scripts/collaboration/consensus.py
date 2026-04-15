#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Consensus - 共识机制

设计决策（门禁2解决）：
- 权重投票：架构师 1.5x，产品经理 1.2x，其他 1.0x
- 否决权：任何角色可投否决票（weight < 0），一票否决触发升级
- 升级机制：
  - 简单多数(>51%) → 通过
  - 分裂/有否决 → 升级到人工决策或 Coordinator 裁决
  - 超时 → 按权重倾向决定 + 标记为 ESCALATED
"""

from datetime import datetime
from typing import Dict, List, Optional

from .models import (
    Vote,
    DecisionProposal,
    ConsensusRecord,
    DecisionOutcome,
    ROLE_WEIGHTS,
    CONSENSUS_THRESHOLDS,
)


class ConsensusEngine:
    def __init__(self):
        self._records: Dict[str, ConsensusRecord] = {}
        self._proposals: Dict[str, DecisionProposal] = {}

    def create_proposal(self, topic: str, proposer_id: str,
                         content: str, options: Optional[List[str]] = None,
                         deadline: Optional[datetime] = None) -> DecisionProposal:
        proposal = DecisionProposal(
            topic=topic,
            proposer_id=proposer_id,
            proposal_content=content,
            options=options or ["approve", "reject"],
            deadline=deadline,
        )
        self._proposals[proposal.proposal_id] = proposal
        return proposal

    def cast_vote(self, proposal_id: str, vote: Vote) -> DecisionProposal:
        proposal = self._proposals.get(proposal_id)
        if not proposal:
            raise ValueError(f"Proposal {proposal_id} not found")
        if proposal.status != "open":
            raise ValueError(f"Proposal {proposal_id} is {proposal.status}")
        proposal.votes.append(vote)
        return proposal

    def reach_consensus(self, proposal_id: str) -> ConsensusRecord:
        proposal = self._proposals.get(proposal_id)
        if not proposal:
            raise ValueError(f"Proposal {proposal_id} not found")

        votes_for = [v for v in proposal.votes if v.decision]
        votes_against = [v for v in proposal.votes if not v.decision]
        votes_abstain_count = len(proposal.votes) - len(votes_for) - len(votes_against)

        total_weight_for = sum(v.weight for v in votes_for if v.weight > 0)
        total_weight_against = sum(abs(v.weight) for v in votes_against if v.weight < 0)
        total_weight_normal_against = sum(v.weight for v in votes_against if v.weight > 0)

        has_veto = any(v.weight < 0 for v in proposal.votes)

        participants = [v.voter_id for v in proposal.votes]

        outcome, final_decision, escalation_reason = self._determine_outcome(
            proposal=proposal,
            votes_for=votes_for,
            votes_against=votes_against,
            total_weight_for=total_weight_for,
            total_weight_against=total_weight_against,
            total_weight_normal_against=total_weight_normal_against,
            has_veto=has_veto,
            votes_abstain=votes_abstain_count,
        )

        record = ConsensusRecord(
            record_id=f"consensus-{proposal_id[:8]}",
            topic=proposal.topic,
            outcome=outcome,
            final_decision=final_decision,
            votes_for=len(votes_for),
            votes_against=len(votes_against),
            votes_abstain=votes_abstain_count,
            total_weight_for=total_weight_for,
            total_weight_against=total_weight_against,
            participants=participants,
            escalation_reason=escalation_reason,
        )

        self._records[record.record_id] = record
        proposal.status = "closed"
        return record

    def _determine_outcome(self, proposal, votes_for, votes_against,
                            total_weight_for, total_weight_against,
                            total_weight_normal_against, has_veto, votes_abstain) -> tuple:
        total_votes = len(votes_for) + len(votes_against) + votes_abstain

        if has_veto:
            return (
                DecisionOutcome.ESCALATED,
                f"存在否决票，升级到人工决策。赞成权重:{total_weight_for:.1f}, 反对权重:{total_weight_against:.1f}",
                "Veto vote detected",
            )

        if total_votes == 0:
            return (
                DecisionOutcome.TIMEOUT,
                "无投票记录",
                "No votes cast",
            )

        weight_ratio = total_weight_for / (total_weight_for + total_weight_normal_against + 0.001)
        count_ratio = len(votes_for) / (len(votes_for) + len(votes_against) + 0.001)

        if weight_ratio >= CONSENSUS_THRESHOLDS["unanimous"]:
            return DecisionOutcome.APPROVED, proposal.proposal_content, None
        elif weight_ratio >= CONSENSUS_THRESHOLDS["super_majority"]:
            return DecisionOutcome.APPROVED, proposal.proposal_content, None
        elif weight_ratio >= CONSENSUS_THRESHOLDS["simple_majority"]:
            return DecisionOutcome.APPROVED, proposal.proposal_content, None
        elif count_ratio >= 0.4 and count_ratio <= 0.6:
            return (
                DecisionOutcome.SPLIT,
                f"意见分裂 ({count_ratio:.0%}赞成)，需要进一步讨论",
                "Split decision",
            )
        else:
            return (
                DecisionOutcome.REJECTED,
                f"未通过共识门槛 (赞成率:{count_ratio:.0%})",
                "Below threshold",
            )

    def get_record(self, record_id: str) -> Optional[ConsensusRecord]:
        return self._records.get(record_id)

    def get_all_records(self) -> List[ConsensusRecord]:
        return list(self._records.values())
