#!/usr/bin/env python3

import pytest

from scripts.collaboration.consensus import ConsensusEngine
from scripts.collaboration.coordinator import Coordinator
from scripts.collaboration.models import (
    BatchMode,
    DecisionOutcome,
    EntryStatus,
    EntryType,
    ExecutionPlan,
    Reference,
    ReferenceType,
    ScheduleResult,
    ScratchpadEntry,
    TaskDefinition,
    Vote,
    WorkerResult,
)
from scripts.collaboration.scratchpad import Scratchpad
from scripts.collaboration.worker import Worker, WorkerFactory


class TestScratchpad:
    def setup_method(self):
        self.sp = Scratchpad()

    def test_write_and_read(self):
        entry = ScratchpadEntry(
            worker_id="w1",
            role_id="architect",
            entry_type=EntryType.FINDING,
            content="Use microservices architecture",
            confidence=0.8,
        )
        entry_id = self.sp.write(entry)
        assert entry_id.startswith("entry-")

        results = self.sp.read()
        assert len(results) == 1
        assert results[0].content == "Use microservices architecture"
        assert results[0].entry_type == EntryType.FINDING

    def test_read_with_type_filter(self):
        self.sp.write(ScratchpadEntry(entry_type=EntryType.FINDING, content="finding 1"))
        self.sp.write(ScratchpadEntry(entry_type=EntryType.CONFLICT, content="conflict 1"))
        self.sp.write(ScratchpadEntry(entry_type=EntryType.FINDING, content="finding 2"))

        findings = self.sp.read(entry_type=EntryType.FINDING)
        assert len(findings) == 2
        conflicts = self.sp.read(entry_type=EntryType.CONFLICT)
        assert len(conflicts) == 1

    def test_read_with_worker_filter(self):
        self.sp.write(ScratchpadEntry(worker_id="w1", content="from w1"))
        self.sp.write(ScratchpadEntry(worker_id="w2", content="from w2"))

        results = self.sp.read(worker_id="w1")
        assert len(results) == 1
        assert results[0].worker_id == "w1"

    def test_resolve_entry(self):
        entry = ScratchpadEntry(content="unresolved finding")
        entry_id = self.sp.write(entry)

        self.sp.resolve(entry_id, "Decision made")
        results = self.sp.read()
        assert results[0].status == EntryStatus.RESOLVED

    def test_get_conflicts(self):
        self.sp.write(ScratchpadEntry(entry_type=EntryType.FINDING, content="ok"))
        self.sp.write(ScratchpadEntry(entry_type=EntryType.CONFLICT, content="dispute"))
        self.sp.write(ScratchpadEntry(entry_type=EntryType.CONFLICT, content="another dispute"))

        conflicts = self.sp.get_conflicts()
        assert len(conflicts) == 2

    def test_get_stats(self):
        self.sp.write(ScratchpadEntry(entry_type=EntryType.FINDING, content="f1"))
        self.sp.write(ScratchpadEntry(entry_type=EntryType.CONFLICT, content="c1"))

        stats = self.sp.get_stats()
        assert stats["total_entries"] == 2
        assert "finding" in stats["by_type"]
        assert "conflict" in stats["by_type"]

    def test_get_summary(self):
        self.sp.write(
            ScratchpadEntry(
                worker_id="arch-1",
                role_id="architect",
                entry_type=EntryType.FINDING,
                content="Test finding",
                confidence=0.9,
            )
        )
        summary = self.sp.get_summary()
        assert "Test finding" in summary

    def test_clear(self):
        self.sp.write(ScratchpadEntry(content="entry"))
        self.sp.clear()
        assert len(self.sp.read()) == 0

    def test_export_json(self):
        self.sp.write(ScratchpadEntry(content="export test"))
        json_str = self.sp.export_json()
        assert "export test" in json_str

    def test_read_limit(self):
        for i in range(10):
            self.sp.write(ScratchpadEntry(content=f"entry {i}"))
        results = self.sp.read(limit=3)
        assert len(results) == 3

    def test_entry_references(self):
        ref = Reference(
            reference_type=ReferenceType.SUPPORTS,
            target_entry_id="entry-abc",
            summary="Supports earlier finding",
        )
        entry = ScratchpadEntry(
            content="New finding",
            references=[ref],
        )
        self.sp.write(entry)
        results = self.sp.read()
        assert len(results[0].references) == 1
        assert results[0].references[0].reference_type == ReferenceType.SUPPORTS


class TestConsensusEngine:
    def setup_method(self):
        self.engine = ConsensusEngine()

    def test_create_proposal(self):
        proposal = self.engine.create_proposal(
            topic="Architecture choice",
            proposer_id="arch-1",
            content="Use microservices",
        )
        assert proposal.proposal_id.startswith("prop-")
        assert proposal.topic == "Architecture choice"
        assert proposal.status == "open"

    def test_cast_vote(self):
        proposal = self.engine.create_proposal(
            topic="DB choice",
            proposer_id="arch-1",
            content="Use PostgreSQL",
        )
        vote = Vote(
            voter_id="arch-1",
            voter_role="architect",
            decision=True,
            reason="Scalable and proven",
            weight=1.5,
        )
        updated = self.engine.cast_vote(proposal.proposal_id, vote)
        assert len(updated.votes) == 1
        assert updated.votes[0].decision is True

    def test_reach_consensus_approved(self):
        proposal = self.engine.create_proposal(
            topic="Framework",
            proposer_id="arch-1",
            content="Use FastAPI",
        )
        self.engine.cast_vote(
            proposal.proposal_id,
            Vote(
                voter_id="arch-1",
                voter_role="architect",
                decision=True,
                weight=1.5,
            ),
        )
        self.engine.cast_vote(
            proposal.proposal_id,
            Vote(
                voter_id="test-1",
                voter_role="tester",
                decision=True,
                weight=1.0,
            ),
        )
        record = self.engine.reach_consensus(proposal.proposal_id)
        assert record.outcome == DecisionOutcome.APPROVED
        assert record.votes_for == 2

    def test_reach_consensus_rejected(self):
        proposal = self.engine.create_proposal(
            topic="Framework",
            proposer_id="arch-1",
            content="Use COBOL",
        )
        self.engine.cast_vote(
            proposal.proposal_id,
            Vote(
                voter_id="arch-1",
                voter_role="architect",
                decision=False,
                weight=1.5,
            ),
        )
        self.engine.cast_vote(
            proposal.proposal_id,
            Vote(
                voter_id="test-1",
                voter_role="tester",
                decision=False,
                weight=1.0,
            ),
        )
        record = self.engine.reach_consensus(proposal.proposal_id)
        assert record.outcome == DecisionOutcome.REJECTED

    def test_cast_vote_invalid_proposal(self):
        with pytest.raises(ValueError):
            self.engine.cast_vote(
                "nonexistent",
                Vote(
                    voter_id="w1",
                    voter_role="architect",
                    decision=True,
                ),
            )

    def test_reach_consensus_invalid_proposal(self):
        with pytest.raises(ValueError):
            self.engine.reach_consensus("nonexistent")

    def test_get_record(self):
        proposal = self.engine.create_proposal(
            topic="Test topic",
            proposer_id="w1",
            content="Test",
        )
        self.engine.cast_vote(
            proposal.proposal_id,
            Vote(
                voter_id="w1",
                voter_role="architect",
                decision=True,
            ),
        )
        record = self.engine.reach_consensus(proposal.proposal_id)
        fetched = self.engine.get_record(record.record_id)
        assert fetched is not None
        assert fetched.topic == "Test topic"

    def test_get_all_records(self):
        p1 = self.engine.create_proposal(topic="T1", proposer_id="w1", content="C1")
        p2 = self.engine.create_proposal(topic="T2", proposer_id="w1", content="C2")
        self.engine.cast_vote(
            p1.proposal_id,
            Vote(
                voter_id="w1",
                voter_role="architect",
                decision=True,
            ),
        )
        self.engine.cast_vote(
            p2.proposal_id,
            Vote(
                voter_id="w1",
                voter_role="architect",
                decision=True,
            ),
        )
        self.engine.reach_consensus(p1.proposal_id)
        self.engine.reach_consensus(p2.proposal_id)
        records = self.engine.get_all_records()
        assert len(records) == 2

    def test_weighted_voting(self):
        proposal = self.engine.create_proposal(
            topic="Weighted test",
            proposer_id="w1",
            content="Test",
        )
        self.engine.cast_vote(
            proposal.proposal_id,
            Vote(
                voter_id="arch-1",
                voter_role="architect",
                decision=True,
                weight=1.5,
            ),
        )
        self.engine.cast_vote(
            proposal.proposal_id,
            Vote(
                voter_id="ui-1",
                voter_role="ui-designer",
                decision=False,
                weight=0.9,
            ),
        )
        record = self.engine.reach_consensus(proposal.proposal_id)
        assert record.total_weight_for > record.total_weight_against
        assert record.outcome == DecisionOutcome.APPROVED


class TestWorker:
    def setup_method(self):
        self.sp = Scratchpad()
        self.worker = Worker(
            worker_id="arch-test",
            role_id="architect",
            role_prompt="You are a system architect.",
            scratchpad=self.sp,
        )

    def test_execute_returns_worker_result(self):
        task = TaskDefinition(
            description="Design auth system",
            role_id="architect",
            role_prompt="You are a system architect.",
        )
        result = self.worker.execute(task)
        assert isinstance(result, WorkerResult)
        assert result.worker_id == "arch-test"
        assert result.success is True
        assert result.output is not None

    def test_execute_writes_to_scratchpad(self):
        task = TaskDefinition(
            description="Design caching layer",
            role_id="architect",
            role_prompt="You are a system architect.",
        )
        self.worker.execute(task)
        entries = self.sp.read()
        assert len(entries) > 0

    def test_write_finding(self):
        entry = ScratchpadEntry(
            entry_type=EntryType.FINDING,
            content="Redis recommended for caching",
            confidence=0.85,
        )
        entry_id = self.worker.write_finding(entry)
        assert entry_id.startswith("entry-")

    def test_write_question(self):
        entry_id = self.worker.write_question(
            question="What is the expected QPS?",
            to_roles=["product-manager"],
        )
        assert entry_id.startswith("entry-")
        questions = self.sp.read(entry_type=EntryType.QUESTION)
        assert len(questions) == 1

    def test_write_conflict(self):
        self.sp.write(
            ScratchpadEntry(
                entry_id="entry-existing",
                content="Use SQL",
            )
        )
        entry_id = self.worker.write_conflict(
            conflict="Should use NoSQL instead",
            conflicting_entry_id="entry-existing",
            reason="Better for unstructured data",
        )
        assert entry_id.startswith("entry-")
        conflicts = self.sp.get_conflicts()
        assert len(conflicts) >= 1

    def test_read_scratchpad(self):
        self.sp.write(
            ScratchpadEntry(
                worker_id="other-worker",
                content="Existing finding",
            )
        )
        entries = self.worker.read_scratchpad()
        assert len(entries) >= 1


class TestWorkerFactory:
    def setup_method(self):
        self.sp = Scratchpad()

    def test_create_worker(self):
        worker = WorkerFactory.create(
            worker_id="w-test",
            role_id="architect",
            role_prompt="You are an architect.",
            scratchpad=self.sp,
        )
        assert worker.worker_id == "w-test"
        assert worker.role_id == "architect"

    def test_create_batch(self):
        configs = [
            {"role_id": "architect", "role_prompt": "Architect prompt"},
            {"role_id": "tester", "role_prompt": "Tester prompt"},
        ]
        workers = WorkerFactory.create_batch(configs, scratchpad=self.sp)
        assert len(workers) == 2
        assert workers[0].role_id == "architect"
        assert workers[1].role_id == "tester"


class TestCoordinator:
    def setup_method(self):
        self.sp = Scratchpad()
        self.coord = Coordinator(
            scratchpad=self.sp,
            enable_compression=False,
        )

    def test_plan_task(self):
        available_roles = [
            {"role_id": "architect", "name": "Architect", "role_prompt": "You are an architect."},
            {"role_id": "tester", "name": "Tester", "role_prompt": "You are a tester."},
        ]
        plan = self.coord.plan_task(
            task_description="Design and test auth system",
            available_roles=available_roles,
        )
        assert isinstance(plan, ExecutionPlan)
        assert plan.total_tasks > 0

    def test_spawn_workers(self):
        available_roles = [
            {"role_id": "architect", "name": "Architect", "role_prompt": "You are an architect."},
        ]
        plan = self.coord.plan_task(
            task_description="Design system",
            available_roles=available_roles,
        )
        workers = self.coord.spawn_workers(plan)
        assert len(workers) > 0
        assert all(isinstance(w, Worker) for w in workers)

    def test_execute_plan(self):
        available_roles = [
            {"role_id": "architect", "name": "Architect", "role_prompt": "You are an architect."},
        ]
        plan = self.coord.plan_task(
            task_description="Design system",
            available_roles=available_roles,
        )
        self.coord.spawn_workers(plan)
        result = self.coord.execute_plan(plan)
        assert isinstance(result, ScheduleResult)
        assert result.total_tasks > 0

    def test_collect_results(self):
        available_roles = [
            {"role_id": "architect", "name": "Architect", "role_prompt": "You are an architect."},
        ]
        plan = self.coord.plan_task(
            task_description="Design system",
            available_roles=available_roles,
        )
        self.coord.spawn_workers(plan)
        self.coord.execute_plan(plan)
        results = self.coord.collect_results()
        assert isinstance(results, dict)

    def test_resolve_conflicts_no_conflicts(self):
        records = self.coord.resolve_conflicts()
        assert isinstance(records, list)

    def test_coordinator_with_llm_backend_none(self):
        coord = Coordinator(scratchpad=self.sp, llm_backend=None)
        assert coord.llm_backend is None

    def test_generate_report(self):
        available_roles = [
            {"role_id": "architect", "name": "Architect", "role_prompt": "You are an architect."},
        ]
        plan = self.coord.plan_task(
            task_description="Design system",
            available_roles=available_roles,
        )
        self.coord.spawn_workers(plan)
        self.coord.execute_plan(plan)
        report = self.coord.generate_report()
        assert isinstance(report, str)
        assert len(report) > 0


class TestInputValidatorIntegration:
    def test_dispatch_rejects_empty_task(self):
        from scripts.collaboration.dispatcher import MultiAgentDispatcher

        disp = MultiAgentDispatcher(enable_warmup=False, enable_memory=False, enable_skillify=False)
        result = disp.dispatch("")
        assert result.success is False
        summary_lower = result.summary.lower()
        assert (
            "validation" in summary_lower
            or "invalid" in summary_lower
            or "太短" in result.summary
            or "描述" in result.summary
        )

    def test_dispatch_rejects_short_task(self):
        from scripts.collaboration.dispatcher import MultiAgentDispatcher

        disp = MultiAgentDispatcher(enable_warmup=False, enable_memory=False, enable_skillify=False)
        result = disp.dispatch("Hi")
        assert result.success is False

    def test_dispatch_rejects_xss_task(self):
        from scripts.collaboration.dispatcher import MultiAgentDispatcher

        disp = MultiAgentDispatcher(enable_warmup=False, enable_memory=False, enable_skillify=False)
        result = disp.dispatch('<script>alert("xss")</script> Design a system')
        assert result.success is False

    def test_dispatch_accepts_valid_task(self):
        from scripts.collaboration.dispatcher import MultiAgentDispatcher

        disp = MultiAgentDispatcher(enable_warmup=False, enable_memory=False, enable_skillify=False)
        result = disp.dispatch("Design a user authentication system")
        assert result.success is True


class TestConsensusEngineEdgeCases:
    """补充 ConsensusEngine 的错误路径与边界条件。"""

    def setup_method(self):
        self.engine = ConsensusEngine()

    def test_cast_vote_on_closed_proposal_raises(self):
        proposal = self.engine.create_proposal(topic="T", proposer_id="w1", content="C")
        self.engine.cast_vote(
            proposal.proposal_id,
            Vote(voter_id="w1", voter_role="architect", decision=True),
        )
        self.engine.reach_consensus(proposal.proposal_id)
        with pytest.raises(ValueError):
            self.engine.cast_vote(
                proposal.proposal_id,
                Vote(voter_id="w2", voter_role="architect", decision=True),
            )

    def test_reach_consensus_with_veto_is_escalated(self):
        proposal = self.engine.create_proposal(topic="T", proposer_id="w1", content="C")
        self.engine.cast_vote(
            proposal.proposal_id,
            Vote(voter_id="w1", voter_role="architect", decision=True, weight=1.5),
        )
        self.engine.cast_vote(
            proposal.proposal_id,
            Vote(voter_id="sec-1", voter_role="security", decision=False, weight=-1.0),
        )
        record = self.engine.reach_consensus(proposal.proposal_id)
        assert record.outcome == DecisionOutcome.ESCALATED
        assert record.escalation_reason is not None

    def test_reach_consensus_with_no_votes_is_timeout(self):
        proposal = self.engine.create_proposal(topic="T", proposer_id="w1", content="C")
        record = self.engine.reach_consensus(proposal.proposal_id)
        assert record.outcome == DecisionOutcome.TIMEOUT

    def test_reach_consensus_split_decision(self):
        proposal = self.engine.create_proposal(topic="T", proposer_id="w1", content="C")
        self.engine.cast_vote(
            proposal.proposal_id,
            Vote(voter_id="w1", voter_role="architect", decision=True, weight=1.0),
        )
        self.engine.cast_vote(
            proposal.proposal_id,
            Vote(voter_id="w2", voter_role="coder", decision=True, weight=1.0),
        )
        self.engine.cast_vote(
            proposal.proposal_id,
            Vote(voter_id="w3", voter_role="tester", decision=False, weight=1.0),
        )
        self.engine.cast_vote(
            proposal.proposal_id,
            Vote(voter_id="w4", voter_role="pm", decision=False, weight=1.0),
        )
        record = self.engine.reach_consensus(proposal.proposal_id)
        assert record.outcome == DecisionOutcome.SPLIT

    def test_get_record_missing_returns_none(self):
        assert self.engine.get_record("missing-record-id") is None

    def test_get_all_records_initially_empty(self):
        assert self.engine.get_all_records() == []


class TestCoordinatorEdgeCases:
    """补充 Coordinator 的错误路径与边界条件。"""

    def test_plan_task_with_empty_roles(self):
        coord = Coordinator(enable_compression=False)
        plan = coord.plan_task("task", available_roles=[])
        assert plan.total_tasks == 0
        assert plan.estimated_parallelism == 0.0

    def test_spawn_workers_with_empty_plan(self):
        coord = Coordinator(enable_compression=False)
        plan = ExecutionPlan(batches=[], total_tasks=0, estimated_parallelism=0.0)
        workers = coord.spawn_workers(plan)
        assert workers == []
        assert coord.workers == {}

    def test_execute_plan_with_empty_plan(self):
        coord = Coordinator(enable_compression=False)
        plan = ExecutionPlan(batches=[], total_tasks=0, estimated_parallelism=0.0)
        result = coord.execute_plan(plan)
        assert result.success is True
        assert result.total_tasks == 0

    def test_execute_batch_sequential_worker_exception(self):
        from scripts.collaboration.models_lifecycle import BatchMode

        coord = Coordinator(enable_compression=False)
        plan = coord.plan_task("task", available_roles=[{"role_id": "architect"}])
        coord.spawn_workers(plan)

        class RaisingWorker:
            worker_id = "forced-worker"
            role_id = "architect"

            def execute(self, _task):
                raise RuntimeError("forced failure")

        coord._worker_index["architect"] = RaisingWorker()

        batch = plan.batches[0]
        batch.mode = BatchMode.SERIAL
        results, errors = coord._execute_batch(batch)
        assert any("forced failure" in e for e in errors)

    def test_execute_parallel_zero_concurrency(self):
        from scripts.collaboration.models_lifecycle import TaskBatch

        coord = Coordinator(enable_compression=False)
        batch = TaskBatch(
            mode=BatchMode.PARALLEL,
            tasks=[TaskDefinition(role_id="architect")],
            max_concurrency=0,
        )
        results = coord._execute_parallel(batch)
        assert results == []

    def test_compress_context_and_stats_when_disabled(self):
        coord = Coordinator(enable_compression=False)
        assert coord.compress_context() is None
        assert coord.get_compression_stats() is None
        assert coord.get_session_memory() is None

    def test_collect_results_with_no_workers(self):
        coord = Coordinator(enable_compression=False)
        results = coord.collect_results()
        assert results["workers"] == []
        assert results["notifications"] == []

    def test_resolve_conflicts_with_no_conflicts(self):
        coord = Coordinator(enable_compression=False)
        records = coord.resolve_conflicts()
        assert records == []

    def test_generate_report_without_execution(self):
        coord = Coordinator(enable_compression=False)
        report = coord.generate_report()
        assert "0.0s" in report
        assert coord.coordinator_id in report

    def test_preload_rules_without_memory_provider(self):
        coord = Coordinator(enable_compression=False)
        assert coord.preload_rules("task") == {}

    def test_get_worker_for_task_missing(self):
        coord = Coordinator(enable_compression=False)
        assert coord._get_worker_for_task(TaskDefinition(role_id="missing")) is None
