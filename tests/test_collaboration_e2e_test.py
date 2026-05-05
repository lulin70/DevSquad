#!/usr/bin/env python3
"""E2E Test: Collaboration System (Coordinator + Scratchpad + Worker)"""
import sys, os, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))

passed = 0
failed = 0

def test(name, fn):
    global passed, failed
    try:
        fn()
        passed += 1
        print(f"  [PASS] {name}")
    except Exception as e:
        failed += 1
        print(f"  [FAIL] {name}: {e}")

print("=" * 60)
print("E2E: Collaboration System")
print("=" * 60)

# ===== Group 1: Scratchpad =====
print("\n--- Scratchpad ---")

def test_scratchpad_create():
    from scripts.collaboration import Scratchpad
    sp = Scratchpad()
    assert sp.scratchpad_id.startswith("scratchpad-")
test("Scratchpad create", test_scratchpad_create)

def test_scratchpad_write_read():
    from scripts.collaboration import Scratchpad, ScratchpadEntry, EntryType
    sp = Scratchpad()
    entry = ScratchpadEntry(
        worker_id="w1", role_id="architect",
        entry_type=EntryType.FINDING,
        content="发现数据库查询存在N+1问题",
        confidence=0.9, tags=["performance", "database"],
    )
    eid = sp.write(entry)
    results = sp.read(query="N+1")
    assert len(results) == 1
    assert "N+1" in results[0].content
test("Scratchpad write & read", test_scratchpad_write_read)

def test_scratchpad_resolve():
    from scripts.collaboration import Scratchpad, ScratchpadEntry, EntryType, EntryStatus
    sp = Scratchpad()
    entry = ScratchpadEntry(
        worker_id="w1", role_id="architect",
        entry_type=EntryType.FINDING, content="待解决问题",
    )
    eid = sp.write(entry)
    sp.resolve(eid, resolution="已添加缓存层")
    resolved = sp.read(status=EntryStatus.RESOLVED)
    assert len(resolved) == 1
    assert "缓存层" in resolved[0].content
test("Scratchpad resolve", test_scratchpad_resolve)

def test_scratchpad_conflicts():
    from scripts.collaboration import Scratchpad, ScratchpadEntry, EntryType
    sp = Scratchpad()
    sp.write(ScratchpadEntry(worker_id="w1", role_id="architect",
                           entry_type=EntryType.CONFLICT, content="技术方案A"))
    conflicts = sp.get_conflicts()
    assert len(conflicts) == 1
test("Scratchpad get_conflicts", test_scratchpad_conflicts)

def test_scratchpad_summary():
    from scripts.collaboration import Scratchpad, ScratchpadEntry, EntryType
    sp = Scratchpad()
    sp.write(ScratchpadEntry(worker_id="w1", role_id="architect",
                           entry_type=EntryType.FINDING, content="发现1"))
    sp.write(ScratchpadEntry(worker_id="w2", role_id="tester",
                           entry_type=EntryType.DECISION, content="决策1"))
    summary = sp.get_summary()
    assert "Key Findings" in summary or "findings" in summary.lower()
test("Scratchpad get_summary", test_scratchpad_summary)

def test_scratchpad_stats():
    from scripts.collaboration import Scratchpad
    sp = Scratchpad()
    stats = sp.get_stats()
    assert "total_entries" in stats
test("Scratchpad get_stats", test_scratchpad_stats)

# ===== Group 2: Worker =====
print("\n--- Worker ---")

def test_worker_create():
    from scripts.collaboration import Scratchpad, Worker
    sp = Scratchpad()
    w = Worker("w1", "architect", "你是架构师...", sp)
    assert w.worker_id == "w1"
    assert w.role_id == "architect"
test("Worker create", test_worker_create)

def test_worker_execute():
    from scripts.collaboration import Scratchpad, Worker, TaskDefinition
    sp = Scratchpad()
    w = Worker("w1", "architect", "你是架构师，分析系统架构", sp)
    task = TaskDefinition(description="设计用户认证模块的架构")
    result = w.execute(task)
    assert result.success
    assert result.worker_id == "w1"
    assert result.task_id == task.task_id
test("Worker execute task", test_worker_execute)

def test_worker_write_finding():
    from scripts.collaboration import Scratchpad, Worker, ScratchpadEntry, EntryType
    sp = Scratchpad()
    w = Worker("w1", "architect", "", sp)
    entry = ScratchpadEntry(entry_type=EntryType.FINDING, content="发现性能瓶颈在DB查询")
    eid = w.write_finding(entry)
    assert eid.startswith("entry-")
    results = sp.read()
    assert len(results) >= 1
test("Worker write_finding to scratchpad", test_worker_write_finding)

def test_worker_write_question():
    from scripts.collaboration import Scratchpad, Worker
    sp = Scratchpad()
    w = Worker("w1", "architect", "", sp)
    eid = w.write_question("这个API是否需要版本控制？", to_roles=["product-manager"])
    assert eid.startswith("entry-")
    notifs = w.get_pending_notifications()
    assert len(notifs) == 1
    assert "question" in notifs[0].notification_type
test("Worker write question + notification", test_worker_write_question)

# ===== Group 3: Consensus =====
print("\n--- Consensus ---")

def test_consensus_create_proposal():
    from scripts.collaboration import ConsensusEngine
    ce = ConsensusEngine()
    p = ce.create_proposal("是否采用微服务架构？", "coord-1",
                            "建议使用微服务架构以获得更好的扩展性")
    assert p.proposal_id.startswith("prop-")
    assert p.status == "open"
test("Consensus create proposal", test_consensus_create_proposal)

def test_consensus_vote_and_decide():
    from scripts.collaboration import ConsensusEngine, Vote
    ce = ConsensusEngine()
    p = ce.create_proposal("测试议题", "coord-1", "提案内容")
    ce.cast_vote(p.proposal_id, Vote(voter_id="arch-1", voter_role="architect",
                                  decision=True, weight=1.5, reason="技术可行"))
    ce.cast_vote(p.proposal_id, Vote(voter_id="pm-1", voter_role="product-manager",
                                  decision=True, weight=1.2, reason="业务支持"))
    record = ce.reach_consensus(p.proposal_id)
    assert record.outcome.value == "approved"
    assert record.votes_for == 2
test("Consensus vote & approve (weight majority)", test_consensus_vote_and_decide)

def test_consensus_veto():
    from scripts.collaboration import ConsensusEngine, Vote, DecisionOutcome
    ce = ConsensusEngine()
    p = ce.create_proposal("测试否决", "coord-1", "提案内容")
    ce.cast_vote(p.proposal_id, Vote(voter_id="arch-1", voter_role="architect", decision=True, weight=1.0))
    ce.cast_vote(p.proposal_id, Vote(voter_id="sec-1", voter_role="security",
                                  decision=False,
                                  weight=-1.0, reason="安全风险"))  # veto!
    record = ce.reach_consensus(p.proposal_id)
    assert record.outcome == DecisionOutcome.ESCALATED
test("Consensus veto triggers escalation", test_consensus_veto)

# ===== Group 4: Coordinator =====
print("\n--- Coordinator ---")

def test_coordinator_plan_task():
    from scripts.collaboration import Coordinator
    coord = Coordinator()
    plan = coord.plan_task("设计电商系统核心模块", [
        {"role_id": "architect"},
        {"role_id": "tester"},
        {"role_id": "product-manager"},
    ], stage_id="stage2")
    assert plan.total_tasks == 3
    assert len(plan.batches) == 1
    assert plan.batches[0].mode.value == "parallel"
test("Coordinator plan task (3 roles parallel)", test_coordinator_plan_task)

def test_coordinator_spawn_workers():
    from scripts.collaboration import Coordinator
    coord = Coordinator()
    plan = coord.plan_task("设计认证系统", [
        {"role_id": "architect"},
        {"role_id": "tester"},
    ])
    workers = coord.spawn_workers(plan)
    assert len(workers) == 2
    assert len(coord.workers) == 2
test("Coordinator spawn workers", test_coordinator_spawn_workers)

def test_coordinator_execute_plan():
    from scripts.collaboration import Coordinator
    coord = Coordinator()
    plan = coord.plan_task("代码走读分析", [
        {"role_id": "architect"},
        {"role_id": "tester"},
        {"role_id": "solo-coder"},
    ])
    workers = coord.spawn_workers(plan)
    result = coord.execute_plan(plan)
    assert result.total_tasks == 3
    assert result.completed_tasks == 3
    assert result.success
test("Coordinator execute plan (3 workers)", test_coordinator_execute_plan)

def test_coordinator_collect_results():
    from scripts.collaboration import Coordinator
    coord = Coordinator()
    plan = coord.plan_task("收集结果测试", [
        {"role_id": "architect"}, {"role_id": "tester"}
    ])
    coord.spawn_workers(plan)
    coord.execute_plan(plan)
    collection = coord.collect_results()
    assert "workers" in collection
    assert "findings_count" in collection
    assert "scratchpad" in collection
test("Coordinator collect results", test_coordinator_collect_results)

def test_coordinator_generate_report():
    from scripts.collaboration import Coordinator
    coord = Coordinator()
    plan = coord.plan_task("生成报告测试", [
        {"role_id": "architect"}, {"role_id": "tester"}
    ])
    coord.spawn_workers(plan)
    coord.execute_plan(plan)
    report = coord.generate_report()
    assert "协作报告" in report
    assert "Worker" in report or "worker" in report.lower()
test("Coordinator generate report", test_coordinator_generate_report)

# ===== Group 5: BatchScheduler =====
print("\n--- BatchScheduler ---")

def test_batch_scheduler_parallel():
    from scripts.collaboration import BatchScheduler, TaskBatch, BatchMode, TaskDefinition
    bs = BatchScheduler()
    batch = TaskBatch(mode=BatchMode.PARALLEL, tasks=[
        TaskDefinition(description="任务A", role_id="architect"),
        TaskDefinition(description="任务B", role_id="tester"),
    ], max_concurrency=2)
    workers = {}
    result = bs.schedule([batch], workers)
    assert result.total_tasks == 2
test("BatchScheduler parallel execution", test_batch_scheduler_parallel)

# ===== Group 6: Integration - Full Flow =====
print("\n--- Integration: Full Collaboration Flow ---")

def test_full_collaboration_flow():
    from scripts.collaboration import Coordinator
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
    assert result.completed_tasks == 5
    assert result.duration_seconds > 0

    collection = coord.collect_results()
    assert collection["findings_count"] > 0

    resolutions = coord.resolve_conflicts()
    assert isinstance(resolutions, list)

    report = coord.generate_report()
    assert len(report) > 100
    assert "协作报告" in report
test("Full flow: 5-role collaboration with consensus", test_full_collaboration_flow)

# ===== Summary =====
print("\n" + "=" * 60)
print(f"E2E RESULTS: {passed} passed, {failed} failed")
if failed == 0:
    print("ALL E2E TESTS PASSED - Phase 1 implementation verified!")
else:
    print(f"FAILED: {failed} tests need attention")
