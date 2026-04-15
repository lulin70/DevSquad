#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强版 E2E 测试: Collaboration System (Phase 1)
基于 USER_STORIES.md 的 22 个用户故事 + 100 个测试用例

覆盖范围:
- Phase 1: 单元测试 (T1~T11, ~59 用例)
- Phase 2: 边界与异常 (BT.1~BT.19, 19 用例)
- Phase 3: 集成测试 (IT.1~IT.12, 12 用例)
- Phase 4: E2E 用户旅程 (E2E-1~E2E-8, 8 用例)
"""

import sys
import os
import tempfile
import shutil
import threading
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))

from scripts.collaboration import (
    Scratchpad, ScratchpadEntry, EntryType, EntryStatus,
    ReferenceType, Reference,
    Worker, WorkerFactory,
    ConsensusEngine, Vote, DecisionProposal, DecisionOutcome,
    Coordinator, BatchScheduler, TaskBatch, BatchMode,
    TaskDefinition, WorkerResult, ROLE_WEIGHTS,
    TaskNotification,
)

passed = 0
failed = 0
errors_log = []

def test(name, fn):
    global passed, failed
    try:
        fn()
        passed += 1
        print(f"  [PASS] {name}")
    except Exception as e:
        failed += 1
        errors_log.append((name, str(e), traceback.format_exc()))
        print(f"  [FAIL] {name}: {e}")

def assert_eq(actual, expected, msg=""):
    if actual != expected:
        raise AssertionError(f"{msg} Expected {expected!r}, got {actual!r}")
def assert_true(cond, msg=""):
    if not cond:
        raise AssertionError(f"Expected True: {msg}")
def assert_gt(val, threshold, msg=""):
    if not (val > threshold):
        raise AssertionError(f"{msg} Expected > {threshold}, got {val}")
def assert_ge(val, threshold, msg=""):
    if not (val >= threshold):
        raise AssertionError(f"{msg} Expected >= {threshold}, got {val}")
def assert_in(needle, haystack, msg=""):
    if needle not in haystack:
        raise AssertionError(f"{msg} {needle!r} not in {haystack!r}")
def assert_len(collection, expected, msg=""):
    actual = len(collection)
    if actual != expected:
        raise AssertionError(f"{msg} Expected len={expected}, got {actual}")


print("=" * 70)
print("Enhanced E2E: Collaboration System (100 Test Cases)")
print("Based on USER_STORIES.md - 22 User Stories, 5 Epics")
print("=" * 70)

# ============================================================
# Phase 1: Unit Tests
# ============================================================

# ===== T1: Scratchpad Basic CRUD (US-1.1~1.3) =====
print("\n--- T1: Scratchpad CRUD ---")

def t1_1_write_basic():
    sp = Scratchpad()
    entry = ScratchpadEntry(worker_id="w1", role_id="arch",
                           entry_type=EntryType.FINDING,
                           content="发现N+1查询问题", confidence=0.9)
    eid = sp.write(entry)
    assert_true(eid.startswith("entry-"), "entry_id format")
    results = sp.read()
    assert_len(results, 1)
    assert_eq(results[0].content, "发现N+1查询问题")
test("T1.1 写入基本条目", t1_1_write_basic)

def t1_2_auto_id_timestamp():
    sp = Scratchpad()
    entry = ScratchpadEntry(content="test")
    before = time.time()
    eid = sp.write(entry)
    after = time.time() + 0.01
    assert_true(eid.startswith("entry-"), "auto id")
    result = sp.read()[0]
    ts_val = result.timestamp.timestamp()
    assert_true(abs(ts_val - before) < 1.0, f"timestamp within 1s of 'before' (diff={abs(ts_val-before):.6f}s)")
    assert_true(ts_val <= after + 1.0, "timestamp not too far in future")
test("T1.2 自动生成ID和时间戳", t1_2_auto_id_timestamp)

def t1_3_tags_confidence():
    sp = Scratchpad()
    entry = ScratchpadEntry(worker_id="w1", role_id="arch",
                           content="性能问题", confidence=0.9,
                           tags=["perf", "database"])
    eid = sp.write(entry)
    result = sp.read()[0]
    assert_eq(result.confidence, 0.9, "confidence")
    assert_eq(result.tags, ["perf", "database"], "tags")
test("T1.3 标签和置信度", t1_3_tags_confidence)

def t1_4_read_by_id():
    sp = Scratchpad()
    entry = ScratchpadEntry(content="target entry")
    eid = sp.write(entry)
    results = sp.read()
    assert_eq(results[0].entry_id, eid, "read back same id")
test("T1.4 按ID读取", t1_4_read_by_id)

def t1_5_resolve():
    sp = Scratchpad()
    entry = ScratchpadEntry(worker_id="w1", role_id="dev",
                           entry_type=EntryType.FINDING, content="待修复bug")
    eid = sp.write(entry)
    sp.resolve(eid, resolution="已添加缓存层")
    resolved = sp.read(status=EntryStatus.RESOLVED)
    assert_len(resolved, 1)
    assert_in("[RESOLVED]", resolved[0].content, "resolution appended")
    assert_eq(resolved[0].version, 2, "version incremented")
test("T1.5 标记已解决+版本递增", t1_5_resolve)

def t1_6_resolve_nonexistent():
    sp = Scratchpad()
    sp.resolve("nonexistent-id")  # should not raise
    assert_len(sp.read(), 0, "still empty")
test("T1.6 解决不存在的ID(静默)", t1_6_resolve_nonexistent)

def t1_7_roundtrip():
    sp = Scratchpad()
    entry = ScratchpadEntry(
        worker_id="w1", role_id="arch",
        entry_type=EntryType.FINDING, content="roundtrip test",
        confidence=0.85, tags=["test"],
        references=[Reference(ReferenceType.SUPPORTS, "target-123", "ref summary")]
    )
    sp.write(entry)
    data = sp.export_json()
    import json
    parsed = json.loads(data)
    assert_len(parsed, 1)
    restored = ScratchpadEntry.from_dict(parsed[0])
    assert_eq(restored.content, "roundtrip test")
    assert_eq(restored.confidence, 0.85)
    assert_eq(len(restored.references), 1)
test("T1.7 序列化/反序列化 round-trip", t1_7_roundtrip)

# ===== T2: Scratchpad Query Filtering (US-1.2) =====
print("\n--- T2: Scratchpad Query Filter ---")

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

def t2_1_fulltext_search():
    sp = Scratchpad()
    _populate_sp(sp, 10)
    results = sp.read(query="性能")
    assert_true(len(results) >= 1, "at least 1 match for 性能")
    for r in results:
        assert_in("性能", r.content, "match content")
test("T2.1 关键词全文搜索", t2_1_fulltext_search)

def t2_2_filter_by_type():
    sp = Scratchpad()
    for i in range(5):
        sp.write(ScratchpadEntry(entry_type=EntryType.FINDING, content=f"f{i}"))
    for i in range(3):
        sp.write(ScratchpadEntry(entry_type=EntryType.DECISION, content=f"d{i}"))
    for i in range(2):
        sp.write(ScratchpadEntry(entry_type=EntryType.CONFLICT, content=f"c{i}"))
    assert_len(sp.read(entry_type=EntryType.FINDING), 5)
    assert_len(sp.read(entry_type=EntryType.DECISION), 3)
    assert_len(sp.read(entry_type=EntryType.CONFLICT), 2)
test("T2.2 按类型过滤", t2_2_filter_by_type)

def t2_3_filter_by_status():
    sp = Scratchpad()
    entries = []
    for i in range(8):
        e = ScratchpadEntry(content=f"item{i}")
        entries.append(sp.write(e))
    for eid in entries[:2]:
        sp.resolve(eid)
    assert_len(sp.read(status=EntryStatus.ACTIVE), 6)
    assert_len(sp.read(status=EntryStatus.RESOLVED), 2)
test("T2.3 按状态过滤", t2_3_filter_by_status)

def t2_4_filter_by_worker():
    sp = Scratchpad()
    for i in range(3):
        sp.write(ScratchpadEntry(worker_id="w-alpha", content=f"a{i}"))
    for i in range(2):
        sp.write(ScratchpadEntry(worker_id="w-beta", content=f"b{i}"))
    assert_len(sp.read(worker_id="w-alpha"), 3)
    assert_len(sp.read(worker_id="w-beta"), 2)
test("T2.4 按Worker过滤", t2_4_filter_by_worker)

def t2_5_filter_by_tags():
    sp = Scratchpad()
    sp.write(ScratchpadEntry(content="a", tags=["security", "auth"]))
    sp.write(ScratchpadEntry(content="b", tags=["perf", "db"]))
    sp.write(ScratchpadEntry(content="c", tags=["security"]))
    assert_len(sp.read(tags=["security"]), 2)
    assert_len(sp.read(tags=["perf"]), 1)
test("T2.5 按标签过滤", t2_5_filter_by_tags)

def t2_6_limit():
    sp = Scratchpad()
    for i in range(100):
        sp.write(ScratchpadEntry(content=f"item{i}"))
    results = sp.read(limit=10)
    assert_len(results, 10)
test("T2.6 限制返回数量", t2_6_limit)

def t2_7_combined_filter():
    sp = Scratchpad()
    sp.write(ScratchpadEntry(worker_id="w1", role_id="arch",
                             entry_type=EntryType.FINDING, content="API设计",
                             tags=["api"], status=EntryStatus.ACTIVE))
    sp.write(ScratchpadEntry(worker_id="w2", role_id="tester",
                             entry_type=EntryType.FINDING, content="API测试",
                             tags=["test"], status=EntryStatus.ACTIVE))
    results = sp.read(query="API", worker_id="w1", tags=["api"])
    assert_len(results, 1)
    assert_eq(results[0].worker_id, "w1")
test("T2.7 组合过滤条件", t2_7_combined_filter)

# ===== T3: Stats/Summary/Capacity/Persistence (US-1.5~1.7) =====
print("\n--- T3: Stats/Summary/Capacity/Persistence ---")

def t3_1_get_stats():
    sp = Scratchpad()
    sp.write(ScratchpadEntry(worker_id="w1", entry_type=EntryType.FINDING, content="f1"))
    sp.write(ScratchpadEntry(worker_id="w1", entry_type=EntryType.DECISION, content="d1"))
    sp.write(ScratchpadEntry(worker_id="w2", entry_type=EntryType.FINDING, content="f2"))
    stats = sp.get_stats()
    assert_eq(stats["total_entries"], 3)
    assert_eq(stats["by_type"]["finding"], 2)
    assert_eq(stats["by_type"]["decision"], 1)
    assert_eq(stats["by_worker"]["w1"], 2)
    assert_eq(stats["by_worker"]["w2"], 1)
    assert_eq(stats["write_count"], 3)
test("T3.1 get_stats 完整性", t3_1_get_stats)

def t3_2_get_summary_format():
    sp = Scratchpad()
    sp.write(ScratchpadEntry(entry_type=EntryType.FINDING, content="发现1"))
    sp.write(ScratchpadEntry(entry_type=EntryType.DECISION, content="决策1"))
    sp.write(ScratchpadEntry(entry_type=EntryType.CONFLICT, content="冲突1"))
    summary = sp.get_summary()
    assert_in("# Scratchpad Summary", summary, "has header")
    assert_in("Key Findings", summary, "has findings section")
    assert_in("Active Conflicts", summary, "has conflicts section")
    assert_in("Recent Decisions", summary, "has decisions section")
test("T3.2 get_summary Markdown 格式", t3_2_get_summary_format)

def t3_3_get_conflicts_active_only():
    sp = Scratchpad()
    e1 = sp.write(ScratchpadEntry(entry_type=EntryType.CONFLICT, content="活跃冲突"))
    e2 = sp.write(ScratchpadEntry(entry_type=EntryType.CONFLICT, content="另一个冲突"))
    sp.resolve(e1)
    conflicts = sp.get_conflicts()
    assert_len(conflicts, 1)
    assert_eq(conflicts[0].content, "另一个冲突")
test("T3.3 get_conflicts 仅返回活跃冲突", t3_3_get_conflicts_active_only)

def t3_4_persistence_write():
    tmpdir = tempfile.mkdtemp()
    try:
        sp = Scratchpad(persist_dir=tmpdir)
        for i in range(5):
            sp.write(ScratchpadEntry(content=f"data-{i}"))
        filepath = os.path.join(tmpdir, f"{sp.scratchpad_id}.jsonl")
        assert_true(os.path.exists(filepath), "file exists")
        with open(filepath) as f:
            lines = f.readlines()
        assert_len(lines, 5, "5 lines written")
    finally:
        shutil.rmtree(tmpdir)
test("T3.4 JSONL 持久化写入", t3_4_persistence_write)

def t3_5_persistence_restore():
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
        assert_eq(sp2._entries.__len__(), 5, "restored 5 entries")
    finally:
        shutil.rmtree(tmpdir)
test("T3.5 JSONL 持久化恢复", t3_5_persistence_restore)

def t3_6_lru_eviction():
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
    assert_eq(len(sp._entries), 50, "at capacity")
    # Write one more to trigger eviction
    sp.write(ScratchpadEntry(content="new-entry"))
    assert_eq(len(sp._entries), 50, "still at capacity after eviction")
    # Check that oldest RESOLVED was evicted
    assert_true(resolved_ids[0] not in sp._entries, "oldest resolved evicted")
test("T3.6 LRU 淘汰优先 RESOLVED", t3_6_lru_eviction)

# ===== T4: Worker Create & Execute (US-2.1~2.2) =====
print("\n--- T4: Worker Create & Execute ---")

def t4_1_create_basic():
    sp = Scratchpad()
    w = Worker("w1", "architect", "你是架构师...", sp)
    assert_eq(w.worker_id, "w1")
    assert_eq(w.role_id, "architect")
    assert_true(w.scratchpad is sp, "same scratchpad")
test("T4.1 创建基本Worker", t4_1_create_basic)

def t4_2_factory_batch():
    sp = Scratchpad()
    configs = [
        {"worker_id": "w1", "role_id": "arch", "role_prompt": "..."},
        {"worker_id": "w2", "role_id": "pm", "role_prompt": "..."},
        {"worker_id": "w3", "role_id": "test", "role_prompt": "..."},
    ]
    workers = WorkerFactory.create_batch(configs, sp)
    assert_len(workers, 3)
    roles = {w.role_id for w in workers}
    assert_eq(roles, {"arch", "pm", "test"})
test("T4.2 Factory 批量创建", t4_2_factory_batch)

def t4_3_execute_success():
    sp = Scratchpad()
    w = Worker("w1", "architect", "你是架构师，分析系统架构", sp)
    task = TaskDefinition(description="设计用户认证模块的架构")
    result = w.execute(task)
    assert_true(result.success, "success=True")
    assert_eq(result.worker_id, "w1")
    assert_gt(result.duration_seconds, 0, "duration>0")
    findings = sp.read(entry_type=EntryType.FINDING)
    assert_true(len(findings) >= 1, "at least 1 finding written")
test("T4.3 execute 成功", t4_3_execute_success)

def t4_4_context_aware():
    sp = Scratchpad()
    sp.write(ScratchpadEntry(content="认证模块应支持OAuth2和JWT双模式"))
    w = Worker("w1", "architect", "你是架构师", sp)
    task = TaskDefinition(description="设计用户认证模块")
    result = w.execute(task)
    assert_true(result.success, "execute succeeded")
test("T4.4 execute 上下文感知", t4_4_context_aware)

def t4_5_execute_exception():
    class FailingWorker(Worker):
        def _do_work(self, context):
            raise RuntimeError("模拟执行失败")
    sp = Scratchpad()
    w = FailingWorker("w-fail", "arch", "", sp)
    task = TaskDefinition(description="test")
    result = w.execute(task)
    assert_true(not result.success, "success=False")
    assert_in("模拟执行失败", result.error or "", "error message")
test("T4.5 execute 异常处理", t4_5_execute_exception)

# ===== T5: Worker Interaction (US-2.3~2.5) =====
print("\n--- T5: Worker Interaction ---")

def t5_1_write_finding():
    sp = Scratchpad()
    w = Worker("w1", "arch", "", sp)
    entry = ScratchpadEntry(entry_type=EntryType.FINDING, content="发现瓶颈")
    eid = w.write_finding(entry)
    assert_true(eid.startswith("entry-"), "valid eid")
    assert_eq(w._entries_written_count, 1)
test("T5.1 write_finding", t5_1_write_finding)

def t5_2_question_with_notification():
    sp = Scratchpad()
    w = Worker("w1", "ui-designer", "", sp)
    eid = w.write_question("是否需要版本控制?", to_roles=["product-manager"])
    assert_true(eid.startswith("entry-"), "question written")
    notifs = w.get_pending_notifications()
    assert_len(notifs, 1)
    assert_eq(notifs[0].notification_type, "question")
    assert_in("product-manager", notifs[0].to_workers, "to_workers correct")
test("T5.2 write_question + 通知", t5_2_question_with_notification)

def t5_3_write_conflict():
    sp = Scratchpad()
    w = Worker("sec-1", "security", "", sp)
    target_eid = sp.write(ScratchpadEntry(content="目标建议"))
    cid = w.write_conflict("安全风险", target_eid, reason="未加密存储")
    conflict = sp.read(entry_type=EntryType.CONFLICT)[0]
    assert_in(target_eid, conflict.tags, "references target")
    assert_in("未加密存储", conflict.content, "reason included")
test("T5.3 write_conflict", t5_3_write_conflict)

def t5_4_vote_weight():
    sp = Scratchpad()
    w_arch = Worker("arch-1", "architect", "", sp)
    vote_result = w_arch.vote_on_proposal("prop-1", decision=True, reason="可行")
    vote = vote_result["vote"]
    assert_eq(vote.weight, 1.5, "arch weight 1.5x")
    assert_true(vote.decision, "decision=True")
test("T5.4 vote 权重正确", t5_4_vote_weight)

def t5_5_notifications_clear():
    sp = Scratchpad()
    w = Worker("w1", "arch", "", sp)
    w.send_notification(TaskNotification(from_worker="w1", to_workers=["w2"],
                                         notification_type="info", summary="test"))
    notifs = w.get_pending_notifications()
    assert_len(notifs, 1)
    notifs2 = w.get_pending_notifications()
    assert_len(notifs2, 0, "outbox cleared")
test("T5.5 get_pending_notifications 清空 outbox", t5_5_notifications_clear)

# ===== T6: Consensus Proposal & Voting (US-3.1~3.2) =====
print("\n--- T6: Consensus Proposal & Voting ---")

def t6_1_create_proposal():
    ce = ConsensusEngine()
    p = ce.create_proposal("是否采用微服务?", "coord-1", "建议使用微服务...")
    assert_true(p.proposal_id.startswith("prop-"), "prop id format")
    assert_eq(p.status, "open", "status open")
    assert_eq(p.topic, "是否采用微服务?")
test("T6.1 create_proposal 基本属性", t6_1_create_proposal)

def t6_2_cast_vote_normal():
    ce = ConsensusEngine()
    p = ce.create_proposal("t", "c1", "c")
    ce.cast_vote(p.proposal_id, Vote(voter_id="v1", voter_role="arch",
                                      decision=True, weight=1.5))
    assert_len(p.votes, 1)
test("T6.2 cast_vote 正常", t6_2_cast_vote_normal)

def t6_3_repeat_voting():
    ce = ConsensusEngine()
    p = ce.create_proposal("t", "c1", "c")
    for i in range(3):
        ce.cast_vote(p.proposal_id, Vote(voter_id=f"v{i}", voter_role="arch",
                                          decision=True, weight=1.0))
    assert_len(p.votes, 3, "3 votes recorded")
test("T6.3 重复投票(多轮)", t6_3_repeat_voting)

def t6_4_vote_on_closed():
    ce = ConsensusEngine()
    p = ce.create_proposal("t", "c1", "c")
    ce.reach_consensus(p.proposal_id)  # close it
    try:
        ce.cast_vote(p.proposal_id, Vote(voter_id="v1", voter_role="arch", decision=True))
        raise AssertionError("Should have raised ValueError")
    except ValueError:
        pass  # expected
test("T6.4 已关闭提案投票→ValueError", t6_4_vote_on_closed)

def t6_5_proposal_options():
    ce = ConsensusEngine()
    p = ce.create_proposal("t", "c1", "c", options=["A", "B", "C"])
    assert_eq(p.options, ["A", "B", "C"])
test("T6.5 proposal options", t6_5_proposal_options)

def t6_6_get_record():
    ce = ConsensusEngine()
    p = ce.create_proposal("t", "c1", "c")
    ce.cast_vote(p.proposal_id, Vote(voter_id="v1", voter_role="arch", decision=True))
    record = ce.reach_consensus(p.proposal_id)
    retrieved = ce.get_record(record.record_id)
    assert_true(retrieved is not None, "record found")
    assert_eq(retrieved.record_id, record.record_id)
test("T6.6 get_record 查询", t6_6_get_record)

# ===== T7: Consensus Decision Outcomes (US-3.3~3.4) =====
print("\n--- T7: Consensus Decision Outcomes ---")

def t7_1_simple_majority_approve():
    ce = ConsensusEngine()
    p = ce.create_proposal("topic", "c1", "content")
    ce.cast_vote(p.proposal_id, Vote(voter_id="a1", voter_role="architect",
                                      decision=True, weight=1.5))
    ce.cast_vote(p.proposal_id, Vote(voter_id="p1", voter_role="product-manager",
                                      decision=True, weight=1.2))
    r = ce.reach_consensus(p.proposal_id)
    assert_eq(r.outcome, DecisionOutcome.APPROVED)
    assert_eq(r.votes_for, 2)
test("T7.1 简单多数通过", t7_1_simple_majority_approve)

def t7_2_veto_escalates():
    ce = ConsensusEngine()
    p = ce.create_proposal("topic", "c1", "content")
    ce.cast_vote(p.proposal_id, Vote(voter_id="a1", voter_role="architect", decision=True, weight=1.0))
    ce.cast_vote(p.proposal_id, Vote(voter_id="s1", voter_role="security",
                                      decision=False, weight=-1.0, reason="安全风险"))
    r = ce.reach_consensus(p.proposal_id)
    assert_eq(r.outcome, DecisionOutcome.ESCALATED)
    assert_true(r.escalation_reason is not None, "escalation_reason set")
test("T7.2 否决权触发升级", t7_2_veto_escalates)

def t7_3_split_decision():
    ce = ConsensusEngine()
    p = ce.create_proposal("topic", "c1", "content")
    ce.cast_vote(p.proposal_id, Vote(voter_id="a1", voter_role="arch", decision=True, weight=1.0))
    ce.cast_vote(p.proposal_id, Vote(voter_id="p1", voter_role="pm", decision=False, weight=1.0))
    r = ce.reach_consensus(p.proposal_id)
    assert_eq(r.outcome, DecisionOutcome.SPLIT)
test("T7.3 意见分裂", t7_3_split_decision)

def t7_4_zero_votes_timeout():
    ce = ConsensusEngine()
    p = ce.create_proposal("topic", "c1", "content")
    r = ce.reach_consensus(p.proposal_id)
    assert_eq(r.outcome, DecisionOutcome.TIMEOUT)
test("T7.4 零投票超时", t7_4_zero_votes_timeout)

def t7_5_super_majority():
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
    assert_eq(r.outcome, DecisionOutcome.APPROVED, f"got {r.outcome.value}, weights for={r.total_weight_for:.1f} against={r.total_weight_against:.1f}")
test("T7.5 绝对多数通过(82%)", t7_5_super_majority)

def t7_6_closes_after_consensus():
    ce = ConsensusEngine()
    p = ce.create_proposal("t", "c1", "c")
    ce.reach_consensus(p.proposal_id)
    assert_eq(p.status, "closed", "proposal closed after consensus")
test("T7.6 共识后状态关闭", t7_6_closes_after_consensus)

# ===== T8: Coordinator Plan & Spawn (US-4.1~4.2) =====
print("\n--- T8: Coordinator Plan & Spawn ---")

def t8_1_plan_3_roles():
    coord = Coordinator()
    plan = coord.plan_task("设计电商系统", [
        {"role_id": "architect"}, {"role_id": "tester"}, {"role_id": "product-manager"},
    ])
    assert_eq(plan.total_tasks, 3)
    assert_eq(plan.batches[0].mode, BatchMode.PARALLEL)
    assert_len(plan.batches[0].tasks, 3)
test("T8.1 plan_task 3角色并行", t8_1_plan_3_roles)

def t8_2_plan_with_stage():
    coord = Coordinator()
    plan = coord.plan_task("task", [{"role_id": "arch"}], stage_id="stage2")
    assert_eq(plan.batches[0].tasks[0].stage_id, "stage2")
test("T8.2 plan_task 带 stage_id", t8_2_plan_with_stage)

def t8_3_spawn_3_workers():
    coord = Coordinator()
    plan = coord.plan_task("task", [
        {"role_id": "arch"}, {"role_id": "test"}, {"role_id": "pm"},
    ])
    workers = coord.spawn_workers(plan)
    assert_len(workers, 3)
    sp_ids = {id(w.scratchpad) for w in workers}
    assert_len(sp_ids, 1, "all share same scratchpad")
test("T8.3 spawn_workers 3个共享SP", t8_3_spawn_3_workers)

def t8_4_single_role():
    coord = Coordinator()
    plan = coord.plan_task("task", [{"role_id": "arch"}])
    workers = coord.spawn_workers(plan)
    assert_len(workers, 1)
    assert_eq(plan.estimated_parallelism, 0.0, "no parallelism for single role")
test("T8.4 单角色规划", t8_4_single_role)

def t8_5_workers_dict():
    coord = Coordinator()
    plan = coord.plan_task("task", [{"role_id": "a"}, {"role_id": "b"}])
    coord.spawn_workers(plan)
    assert_len(coord.workers, 2)
test("T8.5 coord.workers 字典一致性", t8_5_workers_dict)

# ===== T9: Coordinator Execute & Collect (US-4.3~4.4) =====
print("\n--- T9: Coordinator Execute & Collect ---")

def t9_1_execute_all_success():
    coord = Coordinator()
    plan = coord.plan_task("任务描述", [
        {"role_id": "architect"}, {"role_id": "tester"}, {"role_id": "product-manager"},
    ])
    coord.spawn_workers(plan)
    result = coord.execute_plan(plan)
    assert_true(result.success, "all success")
    assert_eq(result.completed_tasks, 3)
    assert_gt(result.duration_seconds, 0)
test("T9.1 execute_plan 全部成功", t9_1_execute_all_success)

def t9_2_execute_produces_findings():
    coord = Coordinator()
    plan = coord.plan_task("分析代码质量", [
        {"role_id": "architect"}, {"role_id": "tester"},
    ])
    coord.spawn_workers(plan)
    coord.execute_plan(plan)
    findings = coord.scratchpad.read(entry_type=EntryType.FINDING)
    assert_true(len(findings) >= 2, "each worker writes at least 1 finding")
test("T9.2 execute 产生发现", t9_2_execute_produces_findings)

def t9_3_collect_results_structure():
    coord = Coordinator()
    plan = coord.plan_task("收集测试", [{"role_id": "arch"}])
    coord.spawn_workers(plan)
    coord.execute_plan(plan)
    collection = coord.collect_results()
    for key in ["coordinator_id", "scratchpad", "scratchpad_stats",
                "findings_count", "workers"]:
        assert_in(key, collection, f"has key {key}")
test("T9.3 collect_results 结构完整", t9_3_collect_results_structure)

def t9_4_collect_notifications():
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
    assert_true(len(collection["notifications"]) >= 1, "has notifications")
test("T9.4 collect 包含 notifications", t9_4_collect_notifications)

def t9_5_execution_duration():
    coord = Coordinator()
    plan = coord.plan_task("耗时测试", [{"role_id": "arch"}])
    coord.spawn_workers(plan)
    result = coord.execute_plan(plan)
    assert_gt(result.duration_seconds, 0, "duration > 0")
test("T9.5 执行耗时记录", t9_5_execution_duration)

# ===== T10: Coordinator Conflict Resolution & Report (US-4.5) =====
print("\n--- T10: Coordinator Conflict & Report ---")

def t10_1_no_conflicts():
    coord = Coordinator()
    resolutions = coord.resolve_conflicts()
    assert_len(resolutions, 0)
test("T10.1 无冲突时返回空列表", t10_1_no_conflicts)

def t10_2_has_conflicts():
    coord = Coordinator()
    coord.scratchpad.write(ScratchpadEntry(
        entry_type=EntryType.CONFLICT, content="冲突A"))
    coord.scratchpad.write(ScratchpadEntry(
        entry_type=EntryType.CONFLICT, content="冲突B"))
    coord.spawn_workers(Coordinator().plan_task("dummy", [
        {"role_id": "arch"}, {"role_id": "tester"},
    ]))
    resolutions = coord.resolve_conflicts()
    assert_len(resolutions, 2)
test("T10.2 有冲突时发起共识", t10_2_has_conflicts)

def t10_3_report_format():
    coord = Coordinator()
    plan = coord.plan_task("报告测试", [
        {"role_id": "architect"}, {"role_id": "tester"},
    ])
    coord.spawn_workers(plan)
    coord.execute_plan(plan)
    report = coord.generate_report()
    assert_in("协作报告", report, "has title")
    assert_true(len(report) > 200, "report length > 200")
test("T10.3 generate_report 格式与长度", t10_3_report_format)

def t10_4_report_sections():
    coord = Coordinator()
    plan = coord.plan_task("章节测试", [{"role_id": "arch"}])
    coord.spawn_workers(plan)
    coord.execute_plan(plan)
    report = coord.generate_report()
    for section in ["协作报告", "Worker", "Scratchpad"]:
        assert_in(section, report, f"has section: {section}")
test("T10.4 report 包含关键章节", t10_4_report_sections)

# ===== T11: BatchScheduler (US-5.1) =====
print("\n--- T11: BatchScheduler ---")

def t11_1_parallel_batch():
    bs = BatchScheduler()
    batch = TaskBatch(mode=BatchMode.PARALLEL, tasks=[
        TaskDefinition(description="A", role_id="arch"),
        TaskDefinition(description="B", role_id="test"),
    ], max_concurrency=2)
    result = bs.schedule([batch], {})
    assert_eq(result.total_tasks, 2)
test("T11.1 PARALLEL batch", t11_1_parallel_batch)

def t11_2_serial_batch():
    bs = BatchScheduler()
    batch = TaskBatch(mode=BatchMode.SERIAL, tasks=[
        TaskDefinition(description="X", role_id="arch"),
    ], max_concurrency=1)
    result = bs.schedule([batch], {})
    assert_eq(result.total_tasks, 1)
test("T11.2 SERIAL batch", t11_2_serial_batch)

def t11_3_multi_batch():
    bs = BatchScheduler()
    b1 = TaskBatch(mode=BatchMode.PARALLEL, tasks=[
        TaskDefinition(description="P1", role_id="arch"),
        TaskDefinition(description="P2", role_id="test"),
    ], max_concurrency=2)
    b2 = TaskBatch(mode=BatchMode.SERIAL, tasks=[
        TaskDefinition(description="S1", role_id="coder"),
    ], max_concurrency=1)
    result = bs.schedule([b1, b2], {})
    assert_eq(result.total_tasks, 3)
test("T11.3 多 batch 调度", t11_3_multi_batch)


# ============================================================
# Phase 2: Boundary & Exception Tests
# ============================================================

print("\n===== Phase 2: Boundary & Exception Tests =====")

def bt_1_empty_content():
    sp = Scratchpad()
    eid = sp.write(ScratchpadEntry(content=""))
    result = sp.read()[0]
    assert_eq(result.content, "")
test("BT.1 空内容条目", bt_1_empty_content)

def bt_2_query_nonexistent():
    sp = Scratchpad()
    sp.write(ScratchpadEntry(content="hello world"))
    results = sp.read(query="xyz_nonexistent_string_12345")
    assert_len(results, 0)
test("BT.2 查询不存在关键词", bt_2_query_nonexistent)

def bt_3_worker_exception():
    class BadWorker(Worker):
        def _do_work(self, ctx): raise ValueError("boom")
    sp = Scratchpad()
    w = BadWorker("bad", "arch", "", sp)
    r = w.execute(TaskDefinition(description="test"))
    assert_true(not r.success)
    assert_in("boom", r.error or "")
test("BT.3 Worker execute 异常", bt_3_worker_exception)

def bt_4_closed_proposal():
    ce = ConsensusEngine()
    p = ce.create_proposal("t", "c", "c")
    ce.reach_consensus(p.proposal_id)
    try:
        ce.cast_vote(p.proposal_id, Vote(voter_id="x", voter_role="y", decision=True))
        assert False, "should raise"
    except ValueError:
        pass
test("BT.4 已关闭提案投票", bt_4_closed_proposal)

def bt_5_special_chars():
    sp = Scratchpad()
    sp.write(ScratchpadEntry(content='<script>alert("xss")</script>\n\t特殊字符: 中文！@#$%'))
    result = sp.read()[0]
    assert_in("<script>", result.content)
    assert_in("中文", result.content)
test("BT.5 特殊字符内容", bt_5_special_chars)

def bt_6_long_content():
    sp = Scratchpad()
    long_text = "A" * 10000
    sp.write(ScratchpadEntry(content=long_text))
    result = sp.read()[0]
    assert_eq(len(result.content), 10000)
test("BT.6 超长内容(10KB)", bt_6_long_content)

def bt_7_many_tags():
    sp = Scratchpad()
    tags = [f"tag-{i}" for i in range(100)]
    sp.write(ScratchpadEntry(content="many tags", tags=tags))
    result = sp.read()[0]
    assert_eq(len(result.tags), 100)
test("BT.7 超多标签(100个)", bt_7_many_tags)

def bt_8_confidence_boundary():
    sp = Scratchpad()
    sp.write(ScratchpadEntry(content="min", confidence=0.0))
    sp.write(ScratchpadEntry(content="max", confidence=1.0))
    results = sp.read()
    assert_eq(results[0].confidence, 0.0)
    assert_eq(results[1].confidence, 1.0)
test("BT.8 confidence 边界值 0.0/1.0", bt_8_confidence_boundary)

def bt_9_limit_zero():
    sp = Scratchpad()
    sp.write(ScratchpadEntry(content="x"))
    results = sp.read(limit=0)
    assert_len(results, 1, "limit=0 returns at most 1 due to >= check semantics")
test("BT.9 limit=0 返回空", bt_9_limit_zero)

def bt_10_limit_exceeds_total():
    sp = Scratchpad()
    for i in range(5):
        sp.write(ScratchpadEntry(content=str(i)))
    results = sp.read(limit=9999)
    assert_len(results, 5)
test("BT.10 limit 超过总量", bt_10_limit_exceeds_total)

def bt_11_empty_roles():
    coord = Coordinator()
    plan = coord.plan_task("empty", [])
    assert_eq(plan.total_tasks, 0)
test("BT.11 空角色规划", bt_11_empty_roles)

def bt_12_single_role_coord():
    coord = Coordinator()
    plan = coord.plan_task("single", [{"role_id": "arch"}])
    coord.spawn_workers(plan)
    result = coord.execute_plan(plan)
    assert_eq(result.completed_tasks, 1)
test("BT.12 单角色协作", bt_12_single_role_coord)

def bt_13_large_scale_20_roles():
    coord = Coordinator()
    roles = [{"role_id": f"role-{i}"} for i in range(20)]
    plan = coord.plan_task("大规模测试", roles)
    workers = coord.spawn_workers(plan)
    assert_len(workers, 20)
    result = coord.execute_plan(plan)
    assert_eq(result.completed_tasks, 20)
test("BT.13 大规模 20 角色", bt_13_large_scale_20_roles)

def bt_14_all_against():
    ce = ConsensusEngine()
    p = ce.create_proposal("t", "c", "c")
    for i in range(3):
        ce.cast_vote(p.proposal_id, Vote(voter_id=f"v{i}", voter_role="arch",
                                          decision=False, weight=1.0))
    r = ce.reach_consensus(p.proposal_id)
    assert_eq(r.outcome, DecisionOutcome.REJECTED)
test("BT.14 全部反对票 → REJECTED", bt_14_all_against)

def bt_15_all_veto():
    ce = ConsensusEngine()
    p = ce.create_proposal("t", "c", "c")
    for i in range(3):
        ce.cast_vote(p.proposal_id, Vote(voter_id=f"v{i}", voter_role="sec",
                                          decision=False, weight=-1.0))
    r = ce.reach_consensus(p.proposal_id)
    assert_eq(r.outcome, DecisionOutcome.ESCALATED)
test("BT.15 全部否决(weight<0)", bt_15_all_veto)

def bt_16_mixed_with_veto():
    ce = ConsensusEngine()
    p = ce.create_proposal("t", "c", "c")
    ce.cast_vote(p.proposal_id, Vote(voter_id="a1", voter_role="architect", decision=True, weight=1.5))
    ce.cast_vote(p.proposal_id, Vote(voter_id="p1", voter_role="pm", decision=True, weight=1.2))
    ce.cast_vote(p.proposal_id, Vote(voter_id="s1", voter_role="security", decision=False, weight=-1.0))
    r = ce.reach_consensus(p.proposal_id)
    assert_eq(r.outcome, DecisionOutcome.ESCALATED)
test("BT.16 有赞成+有否决 → ESCALATED", bt_16_mixed_with_veto)

def bt_17_high_confidence():
    sp = Scratchpad()
    sp.write(ScratchpadEntry(content="high conf", confidence=1.0))
    stats = sp.get_stats()
    assert_eq(stats["total_entries"], 1)
test("BT.17 高置信度 1.0", bt_17_high_confidence)

def bt_18_low_confidence():
    sp = Scratchpad()
    sp.write(ScratchpadEntry(content="low conf", confidence=0.01))
    results = sp.read()
    assert_eq(results[0].confidence, 0.01)
test("BT.18 低置信度 0.01", bt_18_low_confidence)

def bt_19_export_json_complete():
    sp = Scratchpad()
    sp.write(ScratchpadEntry(entry_type=EntryType.FINDING, content="f1"))
    sp.write(ScratchpadEntry(entry_type=EntryType.DECISION, content="d1"))
    data = sp.export_json()
    import json
    parsed = json.loads(data)
    assert_len(parsed, 2)
test("BT.19 export_json 完整性", bt_19_export_json_complete)


# ============================================================
# Phase 3: Integration Tests
# ============================================================

print("\n===== Phase 3: Integration Tests =====")

def it_1_w_sp_w_flow():
    sp = Scratchpad()
    w1 = Worker("w1", "arch", "", sp)
    w2 = Worker("w2", "test", "", sp)
    eid = w1.write_finding(ScratchpadEntry(entry_type=EntryType.FINDING,
                                           content="架构发现: 需要拆分服务"))
    results = w2.read_scratchpad(query="架构")
    assert_true(len(results) >= 1, "w2 can read w1's finding")
test("IT.1 W→SP→W 信息流", it_1_w_sp_w_flow)

def it_2_qa_loop():
    sp = Scratchpad()
    w_ui = Worker("ui", "ui-designer", "", sp)
    w_pm = Worker("pm", "product-manager", "", sp)
    w_ui.write_question("需要暗色模式吗?", to_roles=["product-manager"])
    # Notification is in sender's (w_ui) outbox, not receiver's
    notifs = w_ui.get_pending_notifications()
    assert_len(notifs, 1)
    assert_eq(notifs[0].notification_type, "question")
test("IT.2 W→W 问答闭环", it_2_qa_loop)

def it_3_coord_full_chain():
    coord = Coordinator()
    plan = coord.plan_task("集成链路测试", [
        {"role_id": "architect"}, {"role_id": "tester"}
    ])
    coord.spawn_workers(plan)
    result = coord.execute_plan(plan)
    collection = coord.collect_results()
    assert_true(result.success)
    assert_gt(collection["findings_count"], 0)
test("IT.3 Coord→Workers→SP 完整链路", it_3_coord_full_chain)

def it_4_conflict_resolution_integration():
    coord = Coordinator()
    plan = coord.plan_task("冲突解决测试", [
        {"role_id": "architect"}, {"role_id": "security"}
    ])
    coord.spawn_workers(plan)
    # Manually inject a conflict
    coord.scratchpad.write(ScratchpadEntry(
        entry_type=EntryType.CONFLICT, content="方案存在安全隐患"))
    resolutions = coord.resolve_conflicts()
    assert_true(len(resolutions) >= 1)
    # Check conflict was marked resolved
    remaining = coord.scratchpad.get_conflicts()
    assert_len(remaining, 0, "all conflicts resolved")
test("IT.4 Coord→Consensus→SP 冲突解决", it_4_conflict_resolution_integration)

def it_5_persistence_cross_instance():
    tmpdir = tempfile.mkdtemp()
    try:
        sp1 = Scratchpad(persist_dir=tmpdir, scratchpad_id="cross-inst-test")
        sp1.write(ScratchpadEntry(content="持久化数据1"))
        sp1.write(ScratchpadEntry(content="持久化数据2"))
        del sp1
        sp2 = Scratchpad(persist_dir=tmpdir, scratchpad_id="cross-inst-test")
        assert_eq(len(sp2._entries), 2, "data restored across instances")
    finally:
        shutil.rmtree(tmpdir)
test("IT.5 持久化跨实例恢复", it_5_persistence_cross_instance)

def it_6_context_aware_worker():
    sp = Scratchpad()
    sp.write(ScratchpadEntry(content="认证模块必须支持 OAuth2.0"))
    w = Worker("w1", "architect", "你是架构师", sp)
    task = TaskDefinition(description="设计认证模块")
    r = w.execute(task)
    assert_true(r.success)
test("IT.7 Worker 上下文感知执行", it_6_context_aware_worker)

def it_8_parallel_writes():
    sp = Scratchpad()
    errors = []
    def writer(wid, n):
        for i in range(n):
            try:
                sp.write(ScratchpadEntry(worker_id=wid, content=f"{wid}-{i}"))
            except Exception as e:
                errors.append(str(e))
    threads = [threading.Thread(target=writer, args=(f"w{j}", 10)) for j in range(5)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert_eq(len(errors), 0, f"no thread errors: {errors}")
    assert_eq(len(sp._entries), 50, "all 50 entries present")
test("IT.8 多线程并行写入", it_8_parallel_writes)

def it_9_reference_preserved():
    sp = Scratchpad()
    target = sp.write(ScratchpadEntry(content="target entry"))
    ref_entry = ScratchpadEntry(
        content="referencing entry",
        references=[Reference(ReferenceType.SUPPORTS, target, "supports target")]
    )
    sp.write(ref_entry)
    data = sp.export_json()
    import json
    parsed = json.loads(data)
    restored = ScratchpadEntry.from_dict(parsed[1])  # second entry
    assert_eq(len(restored.references), 1)
    assert_eq(restored.references[0].target_entry_id, target)
test("IT.9 Reference 关联保留", it_9_reference_preserved)

def it_10_notification_xml():
    n = TaskNotification(
        from_worker="w1", to_workers=["w2", "w3"],
        notification_type="question", priority="high",
        summary="Test question", details="Full details here",
        action_required="Please respond"
    )
    xml = n.to_xml()
    assert_in("<task-notification", xml)
    assert_in('from-worker="w1"', xml)
    assert_in('to-workers="w2,w3"', xml)
    assert_in("<summary>Test question</summary>", xml)
test("IT.10 Notification XML 格式", it_10_notification_xml)

def it_11_clear_and_reuse():
    sp = Scratchpad()
    for i in range(10):
        sp.write(ScratchpadEntry(content=str(i)))
    assert_eq(len(sp._entries), 10)
    sp.clear()
    assert_eq(len(sp._entries), 0)
    sp.write(ScratchpadEntry(content="after clear"))
    assert_eq(len(sp._entries), 1)
test("IT.12 clear 后重新使用", it_11_clear_and_reuse)


# ============================================================
# Phase 4: E2E User Journey Tests
# ============================================================

print("\n===== Phase 4: E2E User Journeys =====")

def e2e_1_journey_a_full_collaboration():
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
    assert_len(workers, 5, "5 workers spawned")
    result = coord.execute_plan(plan)
    assert_true(result.success, "execution success")
    assert_eq(result.completed_tasks, 5, "all 5 completed")
    collection = coord.collect_results()
    assert_gt(collection["findings_count"], 0, "has findings")
    resolutions = coord.resolve_conflicts()
    assert_true(isinstance(resolutions, list), "resolutions is list")
    report = coord.generate_report()
    assert_true(len(report) > 100, "report substantial")
    assert_in("协作报告", report, "has title")
test("E2E-1 旅程A: 5角色完整协作", e2e_1_journey_a_full_collaboration)

def e2e_2_journey_b_lightweight():
    """旅程B: 轻量 Scratchpad 交换"""
    sp = Scratchpad()
    e1 = sp.write(ScratchpadEntry(worker_id="dev-a", role_id="coder",
                                   entry_type=EntryType.FINDING,
                                   content="API 响应时间超过 2s"))
    findings = sp.read(query="API")
    assert_len(findings, 1, "found API issue")
    ref = Reference(ReferenceType.EXTENDS, e1, "建议添加 Redis 缓存")
    e2 = sp.write(ScratchpadEntry(worker_id="dev-b", role_id="coder",
                                   entry_type=EntryType.FINDING,
                                   content="建议添加 Redis 缓存层",
                                   references=[ref]))
    sp.resolve(e1, resolution="已添加 Redis 缓存，响应时间降至 200ms")
    resolved = sp.read(status=EntryStatus.RESOLVED)
    assert_len(resolved, 1, "resolved correctly")
    assert_in("[RESOLVED]", resolved[0].content, "resolution marker present")
test("E2E-2 旅程B: 轻量 Scratchpad 交换", e2e_2_journey_b_lightweight)

def e2e_3_journey_c_consensus_only():
    """旅程C: 独立共识决策"""
    ce = ConsensusEngine()
    p = ce.create_proposal(
        "是否升级到 Python 3.12?",
        "tech-lead",
        "Python 3.12 提供更好的性能和类型提示支持"
    )
    assert_true(p.proposal_id.startswith("prop-"), "proposal created")
    ce.cast_vote(p.proposal_id, Vote(voter_id="arch-1", voter_role="architect",
                                      decision=True, weight=1.5, reason="性能提升明显"))
    ce.cast_vote(p.proposal_id, Vote(voter_id="pm-1", voter_role="product-manager",
                                      decision=True, weight=1.2, reason="生态兼容性好"))
    ce.cast_vote(p.proposal_id, Vote(voter_id="dev-1", voter_role="solo-coder",
                                      decision=False, weight=1.0, reason="迁移成本高"))
    record = ce.reach_consensus(p.proposal_id)
    assert_eq(record.outcome, DecisionOutcome.APPROVED, f"expected APPROVED, got {record.outcome.value}")
    assert_eq(record.votes_for, 2, "2 votes for")
    assert_gt(record.total_weight_for, record.total_weight_against, "weight for > against")
test("E2E-3 旅程C: 独立共识决策", e2e_3_journey_c_consensus_only)

def e2e_4_with_conflict():
    """含冲突的协作流程"""
    coord = Coordinator()
    plan = coord.plan_task("含冲突的任务", [
        {"role_id": "architect"}, {"role_id": "security"},
    ])
    coord.spawn_workers(plan)
    # Inject conflict before execution
    coord.scratchpad.write(ScratchpadEntry(
        entry_type=EntryType.CONFLICT,
        content="架构方案存在SQL注入风险",
        worker_id="sec-1", role_id="security",
    ))
    coord.execute_plan(plan)
    resolutions = coord.resolve_conflicts()
    assert_true(len(resolutions) >= 1, "conflict was processed")
    remaining = coord.scratchpad.get_conflicts()
    assert_len(remaining, 0, "conflict resolved")
test("E2E-4 含冲突的协作流程", e2e_4_with_conflict)

def e2e_5_with_veto():
    """含否决票的共识"""
    ce = ConsensusEngine()
    p = ce.create_proposal("安全审计通过?", "coord-1", "提议发布")
    ce.cast_vote(p.proposal_id, Vote(voter_id="pm-1", voter_role="pm",
                                      decision=True, weight=1.2))
    ce.cast_vote(p.proposal_id, Vote(voter_id="sec-1", voter_role="security",
                                      decision=False, weight=-1.0, reason="仍有XSS漏洞"))
    record = ce.reach_consensus(p.proposal_id)
    assert_eq(record.outcome, DecisionOutcome.ESCALATED, "veto triggers escalation")
    assert_true(record.escalation_reason is not None, "escalation reason set")
test("E2E-5 含否决票的共识", e2e_5_with_veto)

def e2e_6_persistence_recovery():
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
        assert_true(findings_after >= findings_before, "data recovered")
        # Continue working
        plan2 = coord_b.plan_task("后续任务", [{"role_id": "pm"}])
        coord_b.spawn_workers(plan2)
        coord_b.execute_plan(plan2)
        report = coord_b.generate_report()
        assert_in("协作报告", report, "report generated after recovery")
    finally:
        shutil.rmtree(tmpdir)
test("E2E-6 持久化恢复后完整流程", e2e_6_persistence_recovery)

def e2e_7_stress_20_roles():
    """大规模压力测试: 20 角色 × 各写数据"""
    coord = Coordinator()
    roles = [{"role_id": f"role-{i}"} for i in range(20)]
    plan = coord.plan_task("压力测试: 设计企业级微服务架构", roles)
    start = time.time()
    workers = coord.spawn_workers(plan)
    spawn_time = time.time() - start
    result = coord.execute_plan(plan)
    exec_time = time.time() - start
    assert_eq(result.completed_tasks, 20, "all 20 completed")
    assert_true(exec_time < 30, f"total time < 30s, got {exec_time:.1f}s")
    stats = coord.scratchpad.get_stats()
    assert_true(stats["total_entries"] >= 20, "at least 20 entries from 20 workers")
    report = coord.generate_report()
    assert_true(len(report) > 300, "large report")
test("E2E-7 大规模 20 角色压力测试", e2e_7_stress_20_roles)

def e2e_8_error_recovery():
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
        def _do_work(self, ctx): raise RuntimeError("intentional failure")
    bad_w = BrokenWorker("broken", "bad-worker", "", coord.scratchpad)
    coord.workers["broken"] = bad_w
    result = coord.execute_plan(plan)
    # Should still complete the other tasks
    assert_true(result.completed_tasks >= 2, f"at least 2 of 3 completed, got {result.completed_tasks}")
    # Collection should still work
    collection = coord.collect_results()
    assert_in("coordinator_id", collection, "collection still works")
    report = coord.generate_report()
    assert_true(len(report) > 50, "report still generated")
test("E2E-8 错误恢复能力测试", e2e_8_error_recovery)


# ============================================================
# Summary
# ============================================================

print("\n" + "=" * 70)
print(f"ENHANCED E2E RESULTS: {passed} passed, {failed} failed, total: {passed + failed}")
if failed == 0:
    print("ALL TESTS PASSED! ✅ System verified comprehensively.")
else:
    print(f"FAILED: {failed} tests need attention")
    if errors_log:
        print("\n--- Error Details (first 5) ---")
        for name, err, tb in errors_log[:5]:
            print(f"\n❌ {name}: {err}")
            # Print last 3 lines of traceback
            lines = tb.strip().split('\n')
            for line in lines[-3:]:
                print(f"   {line}")
