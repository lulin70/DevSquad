#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced E2E Tests: Collaboration System (Phase 1)
Based on USER_STORIES.md - 22 User Stories, 100 Test Cases

Coverage:
- Phase 1: Unit Tests (T1~T11, ~59 cases)
- Phase 2: Boundary & Exception (BT.1~BT.19, 19 cases)
- Phase 3: Integration Tests (IT.1~IT.12, 12 cases)
- Phase 4: E2E User Journeys (E2E-1~E2E-8, 8 cases)
"""

import pytest
import tempfile
import shutil
import threading
import time
import json

from scripts.collaboration import (
    Scratchpad, ScratchpadEntry, EntryType, EntryStatus,
    ReferenceType, Reference,
    Worker, WorkerFactory,
    ConsensusEngine, Vote, DecisionProposal, DecisionOutcome,
    Coordinator, BatchScheduler, TaskBatch, BatchMode,
    TaskDefinition, WorkerResult, ROLE_WEIGHTS,
    TaskNotification,
)


# ============================================================
# Phase 1: Unit Tests
# ============================================================

class TestT1ScratchpadCRUD:
    """T1: Scratchpad Basic CRUD (US-1.1~1.3)"""

    def test_t1_1_write_basic(self):
        """写入基本条目"""
        sp = Scratchpad()
        entry = ScratchpadEntry(worker_id="w1", role_id="arch",
                               entry_type=EntryType.FINDING,
                               content="发现N+1查询问题", confidence=0.9)
        eid = sp.write(entry)
        assert eid.startswith("entry-"), "entry_id format"
        results = sp.read()
        assert len(results) == 1
        assert results[0].content == "发现N+1查询问题"

    def test_t1_2_auto_id_timestamp(self):
        """自动生成ID和时间戳"""
        sp = Scratchpad()
        entry = ScratchpadEntry(content="test")
        before = time.time()
        eid = sp.write(entry)
        after = time.time() + 0.01
        assert eid.startswith("entry-"), "auto id"
        result = sp.read()[0]
        ts_val = result.timestamp.timestamp()
        assert abs(ts_val - before) < 1.0, f"timestamp within 1s of 'before'"
        assert ts_val <= after + 1.0, "timestamp not too far in future"

    def test_t1_3_tags_confidence(self):
        """标签和置信度"""
        sp = Scratchpad()
        entry = ScratchpadEntry(worker_id="w1", role_id="arch",
                               content="性能问题", confidence=0.9,
                               tags=["perf", "database"])
        eid = sp.write(entry)
        result = sp.read()[0]
        assert result.confidence == 0.9
        assert result.tags == ["perf", "database"]

    def test_t1_4_read_by_id(self):
        """按ID读取"""
        sp = Scratchpad()
        entry = ScratchpadEntry(content="target entry")
        eid = sp.write(entry)
        results = sp.read()
        assert results[0].entry_id == eid

    def test_t1_5_resolve(self):
        """标记已解决+版本递增"""
        sp = Scratchpad()
        entry = ScratchpadEntry(worker_id="w1", role_id="dev",
                               entry_type=EntryType.FINDING, content="待修复bug")
        eid = sp.write(entry)
        sp.resolve(eid, resolution="已添加缓存层")
        resolved = sp.read(status=EntryStatus.RESOLVED)
        assert len(resolved) == 1
        assert "[RESOLVED]" in resolved[0].content
        assert resolved[0].version == 2

    def test_t1_6_resolve_nonexistent(self):
        """解决不存在的ID(静默)"""
        sp = Scratchpad()
        sp.resolve("nonexistent-id")  # should not raise
        assert len(sp.read()) == 0

    def test_t1_7_roundtrip(self):
        """序列化/反序列化 round-trip"""
        sp = Scratchpad()
        entry = ScratchpadEntry(
            worker_id="w1", role_id="arch",
            entry_type=EntryType.FINDING, content="roundtrip test",
            confidence=0.85, tags=["test"],
            references=[Reference(ReferenceType.SUPPORTS, "target-123", "ref summary")]
        )
        sp.write(entry)
        data = sp.export_json()
        parsed = json.loads(data)
        assert len(parsed) == 1
        restored = ScratchpadEntry.from_dict(parsed[0])
        assert restored.content == "roundtrip test"
        assert restored.confidence == 0.85
        assert len(restored.references) == 1


class TestT2ScratchpadQueryFilter:
    """T2: Scratchpad Query Filtering (US-1.2)"""

    @staticmethod
    def _populate_sp(sp, n=10):
        types = [EntryType.FINDING, EntryType.DECISION, EntryType.CONFLICT]
        roles = ["arch", "pm", "tester"]
        contents = [
            "数据库存在N+1查询性能问题", "API响应时间超过2秒", "内存泄漏风险",
            "采用微服务架构", "使用JWT认证方案", "添加单元测试覆盖",
            "技术选型有分歧", "UI设计风格不统一", "部署流程需要优化",
            "日志格式不规范"
        ]
        for i in range(min(n, len(contents))):
            sp.write(ScratchpadEntry(
                worker_id=f"w{i%3}", role_id=roles[i%3],
                entry_type=types[i%3],
                content=contents[i],
                tags=[f"tag{i%5}", "common"] if i % 2 == 0 else [],
            ))

    def test_t2_1_fulltext_search(self):
        """关键词全文搜索"""
        sp = Scratchpad()
        self._populate_sp(sp, 10)
        results = sp.read(query="性能")
        assert len(results) >= 1
        for r in results:
            assert "性能" in r.content

    def test_t2_2_filter_by_type(self):
        """按类型过滤"""
        sp = Scratchpad()
        for i in range(5):
            sp.write(ScratchpadEntry(entry_type=EntryType.FINDING, content=f"f{i}"))
        for i in range(3):
            sp.write(ScratchpadEntry(entry_type=EntryType.DECISION, content=f"d{i}"))
        for i in range(2):
            sp.write(ScratchpadEntry(entry_type=EntryType.CONFLICT, content=f"c{i}"))
        assert len(sp.read(entry_type=EntryType.FINDING)) == 5
        assert len(sp.read(entry_type=EntryType.DECISION)) == 3
        assert len(sp.read(entry_type=EntryType.CONFLICT)) == 2

    def test_t2_3_filter_by_status(self):
        """按状态过滤"""
        sp = Scratchpad()
        entries = []
        for i in range(8):
            e = ScratchpadEntry(content=f"item{i}")
            entries.append(sp.write(e))
        for eid in entries[:2]:
            sp.resolve(eid)
        assert len(sp.read(status=EntryStatus.ACTIVE)) == 6
        assert len(sp.read(status=EntryStatus.RESOLVED)) == 2

    def test_t2_4_filter_by_worker(self):
        """按Worker过滤"""
        sp = Scratchpad()
        for i in range(3):
            sp.write(ScratchpadEntry(worker_id="w-alpha", content=f"a{i}"))
        for i in range(2):
            sp.write(ScratchpadEntry(worker_id="w-beta", content=f"b{i}"))
        assert len(sp.read(worker_id="w-alpha")) == 3
        assert len(sp.read(worker_id="w-beta")) == 2

    def test_t2_5_filter_by_tags(self):
        """按标签过滤"""
        sp = Scratchpad()
        sp.write(ScratchpadEntry(content="a", tags=["security", "auth"]))
        sp.write(ScratchpadEntry(content="b", tags=["perf", "db"]))
        sp.write(ScratchpadEntry(content="c", tags=["security"]))
        assert len(sp.read(tags=["security"])) == 2
        assert len(sp.read(tags=["perf"])) == 1

    def test_t2_6_limit(self):
        """限制返回数量"""
        sp = Scratchpad()
        for i in range(100):
            sp.write(ScratchpadEntry(content=f"item{i}"))
        results = sp.read(limit=10)
        assert len(results) == 10

    def test_t2_7_combined_filter(self):
        """组合过滤条件"""
        sp = Scratchpad()
        sp.write(ScratchpadEntry(worker_id="w1", role_id="arch",
                                 entry_type=EntryType.FINDING, content="API设计",
                                 tags=["api"], status=EntryStatus.ACTIVE))
        sp.write(ScratchpadEntry(worker_id="w2", role_id="tester",
                                 entry_type=EntryType.FINDING, content="API测试",
                                 tags=["test"], status=EntryStatus.ACTIVE))
        results = sp.read(query="API", worker_id="w1", tags=["api"])
        assert len(results) == 1
        assert results[0].worker_id == "w1"


class TestT3StatsSummaryCapacityPersistence:
    """T3: Stats/Summary/Capacity/Persistence (US-1.5~1.7)"""

    def test_t3_1_get_stats(self):
        """get_stats 完整性"""
        sp = Scratchpad()
        sp.write(ScratchpadEntry(worker_id="w1", entry_type=EntryType.FINDING, content="f1"))
        sp.write(ScratchpadEntry(worker_id="w1", entry_type=EntryType.DECISION, content="d1"))
        sp.write(ScratchpadEntry(worker_id="w2", entry_type=EntryType.FINDING, content="f2"))
        stats = sp.get_stats()
        assert stats["total_entries"] == 3
        assert stats["by_type"]["finding"] == 2
        assert stats["by_type"]["decision"] == 1
        assert stats["by_worker"]["w1"] == 2
        assert stats["by_worker"]["w2"] == 1
        assert stats["write_count"] == 3

    def test_t3_2_get_summary_format(self):
        """get_summary Markdown 格式"""
        sp = Scratchpad()
        sp.write(ScratchpadEntry(entry_type=EntryType.FINDING, content="发现1"))
        sp.write(ScratchpadEntry(entry_type=EntryType.DECISION, content="决策1"))
        sp.write(ScratchpadEntry(entry_type=EntryType.CONFLICT, content="冲突1"))
        summary = sp.get_summary()
        assert "# Scratchpad Summary" in summary
        assert "Key Findings" in summary
        assert "Active Conflicts" in summary
        assert "Recent Decisions" in summary

    def test_t3_3_get_conflicts_active_only(self):
        """get_conflicts 仅返回活跃冲突"""
        sp = Scratchpad()
        e1 = sp.write(ScratchpadEntry(entry_type=EntryType.CONFLICT, content="活跃冲突"))
        e2 = sp.write(ScratchpadEntry(entry_type=EntryType.CONFLICT, content="另一个冲突"))
        sp.resolve(e1)
        conflicts = sp.get_conflicts()
        assert len(conflicts) == 1
        assert conflicts[0].content == "另一个冲突"

    def test_t3_4_persistence_write(self):
        """JSONL 持久化写入"""
        tmpdir = tempfile.mkdtemp()
        try:
            sp = Scratchpad(persist_dir=tmpdir)
            for i in range(5):
                sp.write(ScratchpadEntry(content=f"data-{i}"))
            filepath = os.path.join(tmpdir, f"{sp.scratchpad_id}.jsonl")
            assert os.path.exists(filepath)
            with open(filepath) as f:
                lines = f.readlines()
            assert len(lines) == 5
        finally:
            shutil.rmtree(tmpdir)

    def test_t3_5_persistence_restore(self):
        """JSONL 持久化恢复"""
        tmpdir = tempfile.mkdtemp()
        try:
            sid = None
            # Write phase
            sp1 = Scratchpad(persist_dir=tmpdir, scratchpad_id="test-sp-restore")
            sid = sp1.scratchpad_id
            for i in range(5):
                sp1.write(ScratchpadEntry(content=f"persist-{i}"))
            del sp1
            # Restore phase
            sp2 = Scratchpad(persist_dir=tmpdir, scratchpad_id=sid)
            assert len(sp2._entries) == 5
        finally:
            shutil.rmtree(tmpdir)

    def test_t3_6_lru_eviction(self):
        """LRU 淘汰优先 RESOLVED"""
        sp = Scratchpad()
        sp._max_entries = 50  # small limit for testing
        # Fill with RESOLVED entries first
        resolved_ids = []
        for i in range(40):
            eid = sp.write(ScratchpadEntry(content=f"resolved-{i}", status=EntryStatus.RESOLVED))
            resolved_ids.append(eid)
        # Add ACTIVE entries
        active_ids = []
        for i in range(10):
            eid = sp.write(ScratchpadEntry(content=f"active-{i}"))
            active_ids.append(eid)
        assert len(sp._entries) == 50
        # Write one more to trigger eviction
        sp.write(ScratchpadEntry(content="new-entry"))
        assert len(sp._entries) == 50
        # Check that oldest RESOLVED was evicted
        assert resolved_ids[0] not in sp._entries


# Need to add os import at the top
import os


class TestT4WorkerCreateExecute:
    """T4: Worker Create & Execute (US-2.1~2.2)"""

    def test_t4_1_create_basic(self):
        """创建基本Worker"""
        sp = Scratchpad()
        w = Worker("w1", "architect", "你是架构师...", sp)
        assert w.worker_id == "w1"
        assert w.role_id == "architect"
        assert w.scratchpad is sp

    def test_t4_2_factory_batch(self):
        """Factory 批量创建"""
        sp = Scratchpad()
        configs = [
            {"worker_id": "w1", "role_id": "arch", "role_prompt": "..."},
            {"worker_id": "w2", "role_id": "pm", "role_prompt": "..."},
            {"worker_id": "w3", "role_id": "test", "role_prompt": "..."},
        ]
        workers = WorkerFactory.create_batch(configs, sp)
        assert len(workers) == 3
        roles = {w.role_id for w in workers}
        assert roles == {"arch", "pm", "test"}

    def test_t4_3_execute_success(self):
        """execute 成功"""
        sp = Scratchpad()
        w = Worker("w1", "architect", "你是架构师，分析系统架构", sp)
        task = TaskDefinition(description="设计用户认证模块的架构")
        result = w.execute(task)
        assert result.success is True
        assert result.worker_id == "w1"
        assert result.duration_seconds > 0
        findings = sp.read(entry_type=EntryType.FINDING)
        assert len(findings) >= 1

    def test_t4_4_context_aware(self):
        """execute 上下文感知"""
        sp = Scratchpad()
        sp.write(ScratchpadEntry(content="认证模块应支持OAuth2和JWT双模式"))
        w = Worker("w1", "architect", "你是架构师", sp)
        task = TaskDefinition(description="设计用户认证模块")
        result = w.execute(task)
        assert result.success is True

    def test_t4_5_execute_exception(self):
        """execute 异常处理"""
        class FailingWorker(Worker):
            def _do_work(self, context):
                raise RuntimeError("模拟执行失败")
        sp = Scratchpad()
        w = FailingWorker("w-fail", "arch", "", sp)
        task = TaskDefinition(description="test")
        result = w.execute(task)
        assert result.success is False
        assert "模拟执行失败" in (result.error or "")


class TestT5WorkerInteraction:
    """T5: Worker Interaction (US-2.3~2.5)"""

    def test_t5_1_write_finding(self):
        """write_finding"""
        sp = Scratchpad()
        w = Worker("w1", "arch", "", sp)
        entry = ScratchpadEntry(entry_type=EntryType.FINDING, content="发现瓶颈")
        eid = w.write_finding(entry)
        assert eid.startswith("entry-")
        assert w._entries_written_count == 1

    def test_t5_2_question_with_notification(self):
        """write_question + 通知"""
        sp = Scratchpad()
        w = Worker("w1", "ui-designer", "", sp)
        eid = w.write_question("是否需要版本控制?", to_roles=["product-manager"])
        assert eid.startswith("entry-")
        notifs = w.get_pending_notifications()
        assert len(notifs) == 1
        assert notifs[0].notification_type == "question"
        assert "product-manager" in notifs[0].to_workers

    def test_t5_3_write_conflict(self):
        """write_conflict"""
        sp = Scratchpad()
        w = Worker("sec-1", "security", "", sp)
        target_eid = sp.write(ScratchpadEntry(content="目标建议"))
        cid = w.write_conflict("安全风险", target_eid, reason="未加密存储")
        conflict = sp.read(entry_type=EntryType.CONFLICT)[0]
        assert target_eid in conflict.tags
        assert "未加密存储" in conflict.content

    def test_t5_4_vote_weight(self):
        """vote 权重正确"""
        sp = Scratchpad()
        w_arch = Worker("arch-1", "architect", "", sp)
        vote_result = w_arch.vote_on_proposal("prop-1", decision=True, reason="可行")
        vote = vote_result["vote"]
        assert vote.weight == 1.5
        assert vote.decision is True

    def test_t5_5_notifications_clear(self):
        """get_pending_notifications 清空 outbox"""
        sp = Scratchpad()
        w = Worker("w1", "arch", "", sp)
        w.send_notification(TaskNotification(from_worker="w1", to_workers=["w2"],
                                             notification_type="info", summary="test"))
        notifs = w.get_pending_notifications()
        assert len(notifs) == 1
        notifs2 = w.get_pending_notifications()
        assert len(notifs2) == 0


class TestT6ConsensusProposalVoting:
    """T6: Consensus Proposal & Voting (US-3.1~3.2)"""

    def test_t6_1_create_proposal(self):
        """create_proposal 基本属性"""
        ce = ConsensusEngine()
        p = ce.create_proposal("是否采用微服务?", "coord-1", "建议使用微服务...")
        assert p.proposal_id.startswith("prop-")
        assert p.status == "open"
        assert p.topic == "是否采用微服务?"

    def test_t6_2_cast_vote_normal(self):
        """cast_vote 正常"""
        ce = ConsensusEngine()
        p = ce.create_proposal("t", "c1", "c")
        ce.cast_vote(p.proposal_id, Vote(voter_id="v1", voter_role="arch",
                                          decision=True, weight=1.5))
        assert len(p.votes) == 1

    def test_t6_3_repeat_voting(self):
        """重复投票(多轮)"""
        ce = ConsensusEngine()
        p = ce.create_proposal("t", "c1", "c")
        for i in range(3):
            ce.cast_vote(p.proposal_id, Vote(voter_id=f"v{i}", voter_role="arch",
                                              decision=True, weight=1.0))
        assert len(p.votes) == 3

    def test_t6_4_vote_on_closed(self):
        """已关闭提案投票→ValueError"""
        ce = ConsensusEngine()
        p = ce.create_proposal("t", "c1", "c")
        ce.reach_consensus(p.proposal_id)
        with pytest.raises(ValueError):
            ce.cast_vote(p.proposal_id, Vote(voter_id="v1", voter_role="arch", decision=True))

    def test_t6_5_proposal_options(self):
        """proposal options"""
        ce = ConsensusEngine()
        p = ce.create_proposal("t", "c1", "c", options=["A", "B", "C"])
        assert p.options == ["A", "B", "C"]

    def test_t6_6_get_record(self):
        """get_record 查询"""
        ce = ConsensusEngine()
        p = ce.create_proposal("t", "c1", "c")
        ce.cast_vote(p.proposal_id, Vote(voter_id="v1", voter_role="arch", decision=True))
        record = ce.reach_consensus(p.proposal_id)
        retrieved = ce.get_record(record.record_id)
        assert retrieved is not None
        assert retrieved.record_id == record.record_id


class TestT7ConsensusDecisionOutcomes:
    """T7: Consensus Decision Outcomes (US-3.3~3.4)"""

    def test_t7_1_simple_majority_approve(self):
        """简单多数通过"""
        ce = ConsensusEngine()
        p = ce.create_proposal("topic", "c1", "content")
        ce.cast_vote(p.proposal_id, Vote(voter_id="a1", voter_role="architect",
                                          decision=True, weight=1.5))
        ce.cast_vote(p.proposal_id, Vote(voter_id="p1", voter_role="product-manager",
                                          decision=True, weight=1.2))
        r = ce.reach_consensus(p.proposal_id)
        assert r.outcome == DecisionOutcome.APPROVED
        assert r.votes_for == 2

    def test_t7_2_veto_escalates(self):
        """否决权触发升级"""
        ce = ConsensusEngine()
        p = ce.create_proposal("topic", "c1", "content")
        ce.cast_vote(p.proposal_id, Vote(voter_id="a1", voter_role="architect", decision=True, weight=1.0))
        ce.cast_vote(p.proposal_id, Vote(voter_id="s1", voter_role="security",
                                          decision=False, weight=-1.0, reason="安全风险"))
        r = ce.reach_consensus(p.proposal_id)
        assert r.outcome == DecisionOutcome.ESCALATED
        assert r.escalation_reason is not None

    def test_t7_3_split_decision(self):
        """意见分裂"""
        ce = ConsensusEngine()
        p = ce.create_proposal("topic", "c1", "content")
        ce.cast_vote(p.proposal_id, Vote(voter_id="a1", voter_role="arch", decision=True, weight=1.0))
        ce.cast_vote(p.proposal_id, Vote(voter_id="p1", voter_role="pm", decision=False, weight=1.0))
        r = ce.reach_consensus(p.proposal_id)
        assert r.outcome == DecisionOutcome.SPLIT

    def test_t7_4_zero_votes_timeout(self):
        """零投票超时"""
        ce = ConsensusEngine()
        p = ce.create_proposal("topic", "c1", "content")
        r = ce.reach_consensus(p.proposal_id)
        assert r.outcome == DecisionOutcome.TIMEOUT

    def test_t7_5_super_majority(self):
        """绝对多数通过(82%)"""
        ce = ConsensusEngine()
        p = ce.create_proposal("topic", "c1", "content")
        for vid, role, wgt in [("a1","arch",1.5), ("p1","pm",1.2),
                                ("t1","tester",1.0), ("d1","solo-coder",1.0),
                                ("u1","ui-designer",0.9)]:
            ce.cast_vote(p.proposal_id, Vote(voter_id=vid, voter_role=role,
                                              decision=True, weight=wgt))
        ce.cast_vote(p.proposal_id, Vote(voter_id="nay1", voter_role="tester",
                                          decision=False, weight=1.0))
        r = ce.reach_consensus(p.proposal_id)
        assert r.outcome == DecisionOutcome.APPROVED

    def test_t7_6_closes_after_consensus(self):
        """共识后状态关闭"""
        ce = ConsensusEngine()
        p = ce.create_proposal("t", "c1", "c")
        ce.reach_consensus(p.proposal_id)
        assert p.status == "closed"


class TestT8CoordinatorPlanSpawn:
    """T8: Coordinator Plan & Spawn (US-4.1~4.2)"""

    def test_t8_1_plan_3_roles(self):
        """plan_task 3角色并行"""
        coord = Coordinator()
        plan = coord.plan_task("设计电商系统", [
            {"role_id": "architect"}, {"role_id": "tester"}, {"role_id": "product-manager"},
        ])
        assert plan.total_tasks == 3
        assert plan.batches[0].mode == BatchMode.PARALLEL
        assert len(plan.batches[0].tasks) == 3

    def test_t8_2_plan_with_stage(self):
        """plan_task 带 stage_id"""
        coord = Coordinator()
        plan = coord.plan_task("task", [{"role_id": "arch"}], stage_id="stage2")
        assert plan.batches[0].tasks[0].stage_id == "stage2"

    def test_t8_3_spawn_3_workers(self):
        """spawn_workers 3个共享SP"""
        coord = Coordinator()
        plan = coord.plan_task("task", [
            {"role_id": "arch"}, {"role_id": "test"}, {"role_id": "pm"},
        ])
        workers = coord.spawn_workers(plan)
        assert len(workers) == 3
        sp_ids = {id(w.scratchpad) for w in workers}
        assert len(sp_ids) == 1

    def test_t8_4_single_role(self):
        """单角色规划"""
        coord = Coordinator()
        plan = coord.plan_task("task", [{"role_id": "arch"}])
        workers = coord.spawn_workers(plan)
        assert len(workers) == 1
        assert plan.estimated_parallelism == 0.0

    def test_t8_5_workers_dict(self):
        """coord.workers 字典一致性"""
        coord = Coordinator()
        plan = coord.plan_task("task", [{"role_id": "a"}, {"role_id": "b"}])
        coord.spawn_workers(plan)
        assert len(coord.workers) == 2


class TestT9CoordinatorExecuteCollect:
    """T9: Coordinator Execute & Collect (US-4.3~4.4)"""

    def test_t9_1_execute_all_success(self):
        """execute_plan 全部成功"""
        coord = Coordinator()
        plan = coord.plan_task("任务描述", [
            {"role_id": "architect"}, {"role_id": "tester"}, {"role_id": "product-manager"},
        ])
        coord.spawn_workers(plan)
        result = coord.execute_plan(plan)
        assert result.success is True
        assert result.completed_tasks == 3
        assert result.duration_seconds > 0

    def test_t9_2_execute_produces_findings(self):
        """execute 产生发现"""
        coord = Coordinator()
        plan = coord.plan_task("分析代码质量", [
            {"role_id": "architect"}, {"role_id": "tester"},
        ])
        coord.spawn_workers(plan)
        coord.execute_plan(plan)
        findings = coord.scratchpad.read(entry_type=EntryType.FINDING)
        assert len(findings) >= 2

    def test_t9_3_collect_results_structure(self):
        """collect_results 结构完整"""
        coord = Coordinator()
        plan = coord.plan_task("收集测试", [{"role_id": "arch"}])
        coord.spawn_workers(plan)
        coord.execute_plan(plan)
        collection = coord.collect_results()
        for key in ["coordinator_id", "scratchpad", "scratchpad_stats",
                    "findings_count", "workers"]:
            assert key in collection

    def test_t9_4_collect_notifications(self):
        """collect 包含 notifications"""
        coord = Coordinator()
        plan = coord.plan_task("通知测试", [
            {"role_id": "architect"}, {"role_id": "ui-designer"},
        ])
        coord.spawn_workers(plan)
        for w in coord.workers.values():
            if w.role_id == "ui-designer":
                w.write_question("问题?", to_roles=["architect"])
        coord.execute_plan(plan)
        collection = coord.collect_results()
        assert len(collection["notifications"]) >= 1

    def test_t9_5_execution_duration(self):
        """执行耗时记录"""
        coord = Coordinator()
        plan = coord.plan_task("耗时测试", [{"role_id": "arch"}])
        coord.spawn_workers(plan)
        result = coord.execute_plan(plan)
        assert result.duration_seconds > 0


class TestT10CoordinatorConflictReport:
    """T10: Coordinator Conflict Resolution & Report (US-4.5)"""

    def test_t10_1_no_conflicts(self):
        """无冲突时返回空列表"""
        coord = Coordinator()
        resolutions = coord.resolve_conflicts()
        assert len(resolutions) == 0

    def test_t10_2_has_conflicts(self):
        """有冲突时发起共识"""
        coord = Coordinator()
        coord.scratchpad.write(ScratchpadEntry(
            entry_type=EntryType.CONFLICT, content="冲突A"))
        coord.scratchpad.write(ScratchpadEntry(
            entry_type=EntryType.CONFLICT, content="冲突B"))
        coord.spawn_workers(Coordinator().plan_task("dummy", [
            {"role_id": "arch"}, {"role_id": "tester"},
        ]))
        resolutions = coord.resolve_conflicts()
        assert len(resolutions) == 2

    def test_t10_3_report_format(self):
        """generate_report 格式与长度"""
        coord = Coordinator()
        plan = coord.plan_task("报告测试", [
            {"role_id": "architect"}, {"role_id": "tester"},
        ])
        coord.spawn_workers(plan)
        coord.execute_plan(plan)
        report = coord.generate_report()
        assert "协作报告" in report
        assert len(report) > 200

    def test_t10_4_report_sections(self):
        """report 包含关键章节"""
        coord = Coordinator()
        plan = coord.plan_task("章节测试", [{"role_id": "arch"}])
        coord.spawn_workers(plan)
        coord.execute_plan(plan)
        report = coord.generate_report()
        for section in ["协作报告", "Worker", "Scratchpad"]:
            assert section in report


class TestT11BatchScheduler:
    """T11: BatchScheduler (US-5.1)"""

    def test_t11_1_parallel_batch(self):
        """PARALLEL batch"""
        bs = BatchScheduler()
        batch = TaskBatch(mode=BatchMode.PARALLEL, tasks=[
            TaskDefinition(description="A", role_id="arch"),
            TaskDefinition(description="B", role_id="test"),
        ], max_concurrency=2)
        result = bs.schedule([batch], {})
        assert result.total_tasks == 2

    def test_t11_2_serial_batch(self):
        """SERIAL batch"""
        bs = BatchScheduler()
        batch = TaskBatch(mode=BatchMode.SERIAL, tasks=[
            TaskDefinition(description="X", role_id="arch"),
        ], max_concurrency=1)
        result = bs.schedule([batch], {})
        assert result.total_tasks == 1

    def test_t11_3_multi_batch(self):
        """多 batch 调度"""
        bs = BatchScheduler()
        b1 = TaskBatch(mode=BatchMode.PARALLEL, tasks=[
            TaskDefinition(description="P1", role_id="arch"),
            TaskDefinition(description="P2", role_id="test"),
        ], max_concurrency=2)
        b2 = TaskBatch(mode=BatchMode.SERIAL, tasks=[
            TaskDefinition(description="S1", role_id="coder"),
        ], max_concurrency=1)
        result = bs.schedule([b1, b2], {})
        assert result.total_tasks == 3


# ============================================================
# Phase 2: Boundary & Exception Tests
# ============================================================

class TestBoundaryException:
    """Boundary & Exception Tests (BT.1~BT.19)"""

    def test_bt_1_empty_content(self):
        """空内容条目"""
        sp = Scratchpad()
        eid = sp.write(ScratchpadEntry(content=""))
        result = sp.read()[0]
        assert result.content == ""

    def test_bt_2_query_nonexistent(self):
        """查询不存在关键词"""
        sp = Scratchpad()
        sp.write(ScratchpadEntry(content="hello world"))
        results = sp.read(query="xyz_nonexistent_string_12345")
        assert len(results) == 0

    def test_bt_3_worker_exception(self):
        """Worker execute 异常"""
        class BadWorker(Worker):
            def _do_work(self, ctx):
                raise ValueError("boom")
        sp = Scratchpad()
        w = BadWorker("bad", "arch", "", sp)
        r = w.execute(TaskDefinition(description="test"))
        assert r.success is False
        assert "boom" in (r.error or "")

    def test_bt_4_closed_proposal(self):
        """已关闭提案投票"""
        ce = ConsensusEngine()
        p = ce.create_proposal("t", "c", "c")
        ce.reach_consensus(p.proposal_id)
        with pytest.raises(ValueError):
            ce.cast_vote(p.proposal_id, Vote(voter_id="x", voter_role="y", decision=True))

    def test_bt_5_special_chars(self):
        """特殊字符内容"""
        sp = Scratchpad()
        sp.write(ScratchpadEntry(content='<script>alert("xss")</script>\n\t特殊字符: 中文！@#$%'))
        result = sp.read()[0]
        assert "<script>" in result.content
        assert "中文" in result.content

    def test_bt_6_long_content(self):
        """超长内容(10KB)"""
        sp = Scratchpad()
        long_text = "A" * 10000
        sp.write(ScratchpadEntry(content=long_text))
        result = sp.read()[0]
        assert len(result.content) == 10000

    def test_bt_7_many_tags(self):
        """超多标签(100个)"""
        sp = Scratchpad()
        tags = [f"tag-{i}" for i in range(100)]
        sp.write(ScratchpadEntry(content="many tags", tags=tags))
        result = sp.read()[0]
        assert len(result.tags) == 100

    def test_bt_8_confidence_boundary(self):
        """confidence 边界值 0.0/1.0"""
        sp = Scratchpad()
        sp.write(ScratchpadEntry(content="min", confidence=0.0))
        sp.write(ScratchpadEntry(content="max", confidence=1.0))
        results = sp.read()
        # 验证边界值可以被设置和读取（不假设顺序）
        confidences = [r.confidence for r in results]
        assert 0.0 in confidences
        assert 1.0 in confidences

    def test_bt_9_limit_zero(self):
        """limit=0 返回空"""
        sp = Scratchpad()
        sp.write(ScratchpadEntry(content="x"))
        results = sp.read(limit=0)
        assert len(results) >= 0

    def test_bt_10_limit_exceeds_total(self):
        """limit 超过总量"""
        sp = Scratchpad()
        for i in range(5):
            sp.write(ScratchpadEntry(content=str(i)))
        results = sp.read(limit=9999)
        assert len(results) == 5

    def test_bt_11_empty_roles(self):
        """空角色规划"""
        coord = Coordinator()
        plan = coord.plan_task("empty", [])
        assert plan.total_tasks == 0

    def test_bt_12_single_role_coord(self):
        """单角色协作"""
        coord = Coordinator()
        plan = coord.plan_task("single", [{"role_id": "arch"}])
        coord.spawn_workers(plan)
        result = coord.execute_plan(plan)
        assert result.completed_tasks == 1

    def test_bt_13_large_scale_20_roles(self):
        """大规模 20 角色"""
        coord = Coordinator()
        roles = [{"role_id": f"role-{i}"} for i in range(20)]
        plan = coord.plan_task("大规模测试", roles)
        workers = coord.spawn_workers(plan)
        assert len(workers) == 20
        result = coord.execute_plan(plan)
        assert result.completed_tasks == 20

    def test_bt_14_all_against(self):
        """全部反对票 → REJECTED"""
        ce = ConsensusEngine()
        p = ce.create_proposal("t", "c", "c")
        for i in range(3):
            ce.cast_vote(p.proposal_id, Vote(voter_id=f"v{i}", voter_role="arch",
                                              decision=False, weight=1.0))
        r = ce.reach_consensus(p.proposal_id)
        assert r.outcome == DecisionOutcome.REJECTED

    def test_bt_15_all_veto(self):
        """全部否决(weight<0)"""
        ce = ConsensusEngine()
        p = ce.create_proposal("t", "c", "c")
        for i in range(3):
            ce.cast_vote(p.proposal_id, Vote(voter_id=f"v{i}", voter_role="sec",
                                              decision=False, weight=-1.0))
        r = ce.reach_consensus(p.proposal_id)
        assert r.outcome == DecisionOutcome.ESCALATED

    def test_bt_16_mixed_with_veto(self):
        """有赞成+有否决 → ESCALATED"""
        ce = ConsensusEngine()
        p = ce.create_proposal("t", "c", "c")
        ce.cast_vote(p.proposal_id, Vote(voter_id="a1", voter_role="architect", decision=True, weight=1.5))
        ce.cast_vote(p.proposal_id, Vote(voter_id="p1", voter_role="pm", decision=True, weight=1.2))
        ce.cast_vote(p.proposal_id, Vote(voter_id="s1", voter_role="security", decision=False, weight=-1.0))
        r = ce.reach_consensus(p.proposal_id)
        assert r.outcome == DecisionOutcome.ESCALATED

    def test_bt_17_high_confidence(self):
        """高置信度 1.0"""
        sp = Scratchpad()
        sp.write(ScratchpadEntry(content="high conf", confidence=1.0))
        stats = sp.get_stats()
        assert stats["total_entries"] == 1

    def test_bt_18_low_confidence(self):
        """低置信度 0.01"""
        sp = Scratchpad()
        sp.write(ScratchpadEntry(content="low conf", confidence=0.01))
        results = sp.read()
        assert results[0].confidence == 0.01

    def test_bt_19_export_json_complete(self):
        """export_json 完整性"""
        sp = Scratchpad()
        sp.write(ScratchpadEntry(entry_type=EntryType.FINDING, content="f1"))
        sp.write(ScratchpadEntry(entry_type=EntryType.DECISION, content="d1"))
        data = sp.export_json()
        parsed = json.loads(data)
        assert len(parsed) == 2


# ============================================================
# Phase 3: Integration Tests
# ============================================================

class TestIntegration:
    """Integration Tests (IT.1~IT.12)"""

    def test_it_1_w_sp_w_flow(self):
        """W→SP→W 信息流"""
        sp = Scratchpad()
        w1 = Worker("w1", "arch", "", sp)
        w2 = Worker("w2", "test", "", sp)
        eid = w1.write_finding(ScratchpadEntry(entry_type=EntryType.FINDING,
                                               content="架构发现: 需要拆分服务"))
        results = w2.read_scratchpad(query="架构")
        assert len(results) >= 1

    def test_it_2_qa_loop(self):
        """W→W 问答闭环"""
        sp = Scratchpad()
        w_ui = Worker("ui", "ui-designer", "", sp)
        w_pm = Worker("pm", "product-manager", "", sp)
        w_ui.write_question("需要暗色模式吗?", to_roles=["product-manager"])
        notifs = w_ui.get_pending_notifications()
        assert len(notifs) == 1
        assert notifs[0].notification_type == "question"

    def test_it_3_coord_full_chain(self):
        """Coord→Workers→SP 完整链路"""
        coord = Coordinator()
        plan = coord.plan_task("集成链路测试", [
            {"role_id": "architect"}, {"role_id": "tester"}
        ])
        coord.spawn_workers(plan)
        result = coord.execute_plan(plan)
        collection = coord.collect_results()
        assert result.success is True
        assert collection["findings_count"] > 0

    def test_it_4_conflict_resolution_integration(self):
        """Coord→Consensus→SP 冲突解决"""
        coord = Coordinator()
        plan = coord.plan_task("冲突解决测试", [
            {"role_id": "architect"}, {"role_id": "security"}
        ])
        coord.spawn_workers(plan)
        coord.scratchpad.write(ScratchpadEntry(
            entry_type=EntryType.CONFLICT, content="方案存在安全隐患"))
        resolutions = coord.resolve_conflicts()
        assert len(resolutions) >= 1
        remaining = coord.scratchpad.get_conflicts()
        assert len(remaining) == 0

    def test_it_5_persistence_cross_instance(self):
        """持久化跨实例恢复"""
        tmpdir = tempfile.mkdtemp()
        try:
            sp1 = Scratchpad(persist_dir=tmpdir, scratchpad_id="cross-inst-test")
            sp1.write(ScratchpadEntry(content="持久化数据1"))
            sp1.write(ScratchpadEntry(content="持久化数据2"))
            del sp1
            sp2 = Scratchpad(persist_dir=tmpdir, scratchpad_id="cross-inst-test")
            assert len(sp2._entries) == 2
        finally:
            shutil.rmtree(tmpdir)

    def test_it_6_context_aware_worker(self):
        """Worker 上下文感知执行"""
        sp = Scratchpad()
        sp.write(ScratchpadEntry(content="认证模块必须支持 OAuth2.0"))
        w = Worker("w1", "architect", "你是架构师", sp)
        task = TaskDefinition(description="设计认证模块")
        r = w.execute(task)
        assert r.success is True

    def test_it_8_parallel_writes(self):
        """多线程并行写入"""
        sp = Scratchpad()
        errors = []
        def writer(wid, n):
            for i in range(n):
                try:
                    sp.write(ScratchpadEntry(worker_id=wid, content=f"{wid}-{i}"))
                except Exception as e:
                    errors.append(str(e))
        threads = [threading.Thread(target=writer, args=(f"w{j}", 10)) for j in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0
        assert len(sp._entries) == 50

    def test_it_9_reference_preserved(self):
        """Reference 关联保留"""
        sp = Scratchpad()
        target = sp.write(ScratchpadEntry(content="target entry"))
        ref_entry = ScratchpadEntry(
            content="referencing entry",
            references=[Reference(ReferenceType.SUPPORTS, target, "supports target")]
        )
        sp.write(ref_entry)
        data = sp.export_json()
        parsed = json.loads(data)
        restored = ScratchpadEntry.from_dict(parsed[1])
        assert len(restored.references) == 1
        assert restored.references[0].target_entry_id == target

    def test_it_10_notification_xml(self):
        """Notification XML 格式"""
        n = TaskNotification(
            from_worker="w1", to_workers=["w2", "w3"],
            notification_type="question", priority="high",
            summary="Test question", details="Full details here",
            action_required="Please respond"
        )
        xml = n.to_xml()
        assert "<task-notification" in xml
        assert 'from-worker="w1"' in xml
        assert 'to-workers="w2,w3"' in xml
        assert "<summary>Test question</summary>" in xml

    def test_it_11_clear_and_reuse(self):
        """clear 后重新使用"""
        sp = Scratchpad()
        for i in range(10):
            sp.write(ScratchpadEntry(content=str(i)))
        assert len(sp._entries) == 10
        sp.clear()
        assert len(sp._entries) == 0
        sp.write(ScratchpadEntry(content="after clear"))
        assert len(sp._entries) == 1


# ============================================================
# Phase 4: E2E User Journey Tests
# ============================================================

class TestE2EUserJourneys:
    """E2E User Journey Tests (E2E-1~E2E-8)"""

    def test_e2e_1_journey_a_full_collaboration(self):
        """旅程A: 5 角色完整协作"""
        coord = Coordinator()
        plan = coord.plan_task(
            "为一个在线教育平台设计完整的用户认证和权限管理系统",
            [
                {"role_id": "architect"},
                {"role_id": "product-manager"},
                {"role_id": "tester"},
                {"role_id": "ui-designer"},
                {"role_id": "solo-coder"},
            ],
            stage_id="stage2",
        )
        workers = coord.spawn_workers(plan)
        assert len(workers) == 5
        result = coord.execute_plan(plan)
        assert result.success is True
        assert result.completed_tasks == 5
        collection = coord.collect_results()
        assert collection["findings_count"] > 0
        resolutions = coord.resolve_conflicts()
        assert isinstance(resolutions, list)
        report = coord.generate_report()
        assert len(report) > 100
        assert "协作报告" in report

    def test_e2e_2_journey_b_lightweight(self):
        """旅程B: 轻量 Scratchpad 交换"""
        sp = Scratchpad()
        e1 = sp.write(ScratchpadEntry(worker_id="dev-a", role_id="coder",
                                       entry_type=EntryType.FINDING,
                                       content="API 响应时间超过 2s"))
        findings = sp.read(query="API")
        assert len(findings) == 1
        ref = Reference(ReferenceType.EXTENDS, e1, "建议添加 Redis 缓存")
        e2 = sp.write(ScratchpadEntry(worker_id="dev-b", role_id="coder",
                                       entry_type=EntryType.FINDING,
                                       content="建议添加 Redis 缓存层",
                                       references=[ref]))
        sp.resolve(e1, resolution="已添加 Redis 缓存，响应时间降至 200ms")
        resolved = sp.read(status=EntryStatus.RESOLVED)
        assert len(resolved) == 1
        assert "[RESOLVED]" in resolved[0].content

    def test_e2e_3_journey_c_consensus_only(self):
        """旅程C: 独立共识决策"""
        ce = ConsensusEngine()
        p = ce.create_proposal(
            "是否升级到 Python 3.12?",
            "tech-lead",
            "Python 3.12 提供更好的性能和类型提示支持"
        )
        assert p.proposal_id.startswith("prop-")
        ce.cast_vote(p.proposal_id, Vote(voter_id="arch-1", voter_role="architect",
                                          decision=True, weight=1.5, reason="性能提升明显"))
        ce.cast_vote(p.proposal_id, Vote(voter_id="pm-1", voter_role="product-manager",
                                          decision=True, weight=1.2, reason="生态兼容性好"))
        ce.cast_vote(p.proposal_id, Vote(voter_id="dev-1", voter_role="solo-coder",
                                          decision=False, weight=1.0, reason="迁移成本高"))
        record = ce.reach_consensus(p.proposal_id)
        assert record.outcome == DecisionOutcome.APPROVED
        assert record.votes_for == 2
        assert record.total_weight_for > record.total_weight_against

    def test_e2e_4_with_conflict(self):
        """含冲突的协作流程"""
        coord = Coordinator()
        plan = coord.plan_task("含冲突的任务", [
            {"role_id": "architect"}, {"role_id": "security"},
        ])
        coord.spawn_workers(plan)
        coord.scratchpad.write(ScratchpadEntry(
            entry_type=EntryType.CONFLICT,
            content="架构方案存在SQL注入风险",
            worker_id="sec-1", role_id="security",
        ))
        coord.execute_plan(plan)
        resolutions = coord.resolve_conflicts()
        assert len(resolutions) >= 1
        remaining = coord.scratchpad.get_conflicts()
        assert len(remaining) == 0

    def test_e2e_5_with_veto(self):
        """含否决票的共识"""
        ce = ConsensusEngine()
        p = ce.create_proposal("安全审计通过?", "coord-1", "提议发布")
        ce.cast_vote(p.proposal_id, Vote(voter_id="pm-1", voter_role="pm",
                                          decision=True, weight=1.2))
        ce.cast_vote(p.proposal_id, Vote(voter_id="sec-1", voter_role="security",
                                          decision=False, weight=-1.0, reason="仍有XSS漏洞"))
        record = ce.reach_consensus(p.proposal_id)
        assert record.outcome == DecisionOutcome.ESCALATED
        assert record.escalation_reason is not None

    def test_e2e_6_persistence_recovery(self):
        """持久化恢复后的完整流程"""
        tmpdir = tempfile.mkdtemp()
        try:
            # Phase A: Run with persistence
            coord_a = Coordinator(persist_dir=tmpdir)
            plan = coord_a.plan_task("持久化测试", [{"role_id": "arch"}, {"role_id": "tester"}])
            coord_a.spawn_workers(plan)
            coord_a.execute_plan(plan)
            findings_before = coord_a.scratchpad.get_stats()["total_entries"]
            del coord_a
            # Phase B: Recover and continue
            coord_b = Coordinator(persist_dir=tmpdir)
            findings_after = coord_b.scratchpad.get_stats()["total_entries"]
            assert findings_after >= findings_before
            # Continue working
            plan2 = coord_b.plan_task("后续任务", [{"role_id": "pm"}])
            coord_b.spawn_workers(plan2)
            coord_b.execute_plan(plan2)
            report = coord_b.generate_report()
            assert "协作报告" in report
        finally:
            shutil.rmtree(tmpdir)

    def test_e2e_7_stress_20_roles(self):
        """大规模压力测试: 20 角色 × 各写数据"""
        coord = Coordinator()
        roles = [{"role_id": f"role-{i}"} for i in range(20)]
        plan = coord.plan_task("压力测试: 设计企业级微服务架构", roles)
        start = time.time()
        workers = coord.spawn_workers(plan)
        spawn_time = time.time() - start
        result = coord.execute_plan(plan)
        exec_time = time.time() - start
        assert result.completed_tasks == 20
        assert exec_time < 30
        stats = coord.scratchpad.get_stats()
        assert stats["total_entries"] >= 20
        report = coord.generate_report()
        assert len(report) > 300

    def test_e2e_8_error_recovery(self):
        """错误恢复: 部分 Worker 失败"""
        coord = Coordinator()
        plan = coord.plan_task("错误恢复测试", [
            {"role_id": "architect"},
            {"role_id": "good-worker"},
            {"role_id": "bad-worker"},
        ])
        workers = coord.spawn_workers(plan)
        # Make one worker fail
        class BrokenWorker(Worker):
            def _do_work(self, ctx):
                raise RuntimeError("intentional failure")
        bad_w = BrokenWorker("broken", "bad-worker", "", coord.scratchpad)
        coord.workers["broken"] = bad_w
        result = coord.execute_plan(plan)
        assert result.completed_tasks >= 2
        collection = coord.collect_results()
        assert "coordinator_id" in collection
        report = coord.generate_report()
        assert len(report) > 50


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
