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
    """
    共识决策引擎 - 多 Agent 协作中的冲突解决核心

    实现加权投票共识机制，支持:
    - 权重投票: 架构师 1.5x, 产品经理 1.2x, 其他 1.0x
    - 否决权: weight < 0 的投票触发升级 (ESCALATED)
    - 多级通过门槛: 全票(1.0) > 绝对多数(0.75) > 简单多数(0.51)
    - 分裂检测: 赞成率在 40%~60% 时标记为 SPLIT

    决策结果类型:
        APPROVED: 通过
        REJECTED: 未达门槛
        SPLIT: 意见分裂，需进一步讨论
        ESCALATED: 存在否决票，升级人工
        TIMEOUT: 无投票记录

    使用示例:
        engine = ConsensusEngine()
        proposal = engine.create_proposal(
            topic="技术方案选择",
            proposer_id="coord-001",
            content="建议采用微服务架构",
            options=["方案A-微服务", "方案B-单体", "合并", "升级人工"],
        )
        # 各 Worker 投票...
        record = engine.reach_consensus(proposal.proposal_id)
        print(f"决策结果: {record.outcome.value}")
    """

    def __init__(self):
        """初始化共识引擎（空提案和空记录集合）"""
        self._records: Dict[str, ConsensusRecord] = {}
        self._proposals: Dict[str, DecisionProposal] = {}

    def create_proposal(self, topic: str, proposer_id: str,
                         content: str, options: Optional[List[str]] = None,
                         deadline: Optional[datetime] = None) -> DecisionProposal:
        """
        创建新的决策提案

        Args:
            topic: 提案主题/标题
            proposer_id: 提案发起者 ID（通常是 Coordinator）
            content: 提案详细内容
            options: 投票选项列表（默认 ["approve", "reject"]）
            deadline: 截止时间（预留参数）

        Returns:
            DecisionProposal: 新创建的提案对象（含自动生成的 proposal_id）

        Raises:
            无（始终成功创建）
        """
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
        """
        为提案投出一票

        Args:
            proposal_id: 目标提案 ID
            vote: Vote 对象，包含 voter_id、decision (bool)、reason、weight

        Returns:
            DecisionProposal: 投票后的更新后提案

        Raises:
            ValueError: 提案不存在或已关闭
        """
        proposal = self._proposals.get(proposal_id)
        if not proposal:
            raise ValueError(f"Proposal {proposal_id} not found")
        if proposal.status != "open":
            raise ValueError(f"Proposal {proposal_id} is {proposal.status}")
        proposal.votes.append(vote)
        return proposal

    def reach_consensus(self, proposal_id: str) -> ConsensusRecord:
        """
        对提案进行共识裁决

        汇总所有已投票，计算加权赞成/反对比例，
        根据阈值判定最终结果。裁决后提案自动关闭。

        判定逻辑:
        1. 存在否决票(weight < 0) → ESCALATED
        2. 无投票 → TIMEOUT
        3. 权重比 >= 全票门槛(1.0) → APPROVED
        4. 权重比 >= 绝对多数(0.75) → APPROVED
        5. 权重比 >= 简单多数(0.51) → APPROVED
        6. 计数比在 40%~60% → SPLIT
        7. 其他 → REJECTED

        Args:
            proposal_id: 要裁决的提案 ID

        Returns:
            ConsensusRecord: 共识记录，包含 outcome、票数统计、参与者等

        Raises:
            ValueError: 提案不存在
        """
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
        """
        按 ID 查询单条共识记录

        Args:
            record_id: 共识记录 ID

        Returns:
            Optional[ConsensusRecord]: 记录对象，不存在则返回 None
        """
        return self._records.get(record_id)

    def get_all_records(self) -> List[ConsensusRecord]:
        """
        获取所有共识记录

        Returns:
            List[ConsensusRecord]: 所有已完成的共识裁决记录
        """
        return list(self._records.values())
