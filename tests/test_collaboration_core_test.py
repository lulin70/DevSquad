#!/usr/bin/env python3
import pytest
from datetime import datetime

from scripts.collaboration.models import (
    TaskDefinition, WorkerResult, ScratchpadEntry, EntryType, EntryStatus,
    Reference, ReferenceType, Vote, DecisionProposal, ConsensusRecord,
    DecisionOutcome, ExecutionPlan, TaskBatch, BatchMode, ScheduleResult,
    ROLE_WEIGHTS, ROLE_REGISTRY, resolve_role_id,
)
from scripts.collaboration.scratchpad import Scratchpad
from scripts.collaboration.worker import Worker, WorkerFactory
from scripts.collaboration.consensus import ConsensusEngine
from scripts.collaboration.coordinator import Coordinator


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
        self.sp.write(ScratchpadEntry(
            worker_id="arch-1",
            role_id="architect",
            entry_type=EntryType.FINDING,
            content="Test finding",
            confidence=0.9,
        ))
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
        entry_id = self.sp.write(entry)
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
        self.engine.cast_vote(proposal.proposal_id, Vote(
            voter_id="arch-1", voter_role="architect",
            decision=True, weight=1.5,
        ))
        self.engine.cast_vote(proposal.proposal_id, Vote(
            voter_id="test-1", voter_role="tester",
            decision=True, weight=1.0,
        ))
        record = self.engine.reach_consensus(proposal.proposal_id)
        assert record.outcome == DecisionOutcome.APPROVED
        assert record.votes_for == 2

    def test_reach_consensus_rejected(self):
        proposal = self.engine.create_proposal(
            topic="Framework",
            proposer_id="arch-1",
            content="Use COBOL",
        )
        self.engine.cast_vote(proposal.proposal_id, Vote(
            voter_id="arch-1", voter_role="architect",
            decision=False, weight=1.5,
        ))
        self.engine.cast_vote(proposal.proposal_id, Vote(
            voter_id="test-1", voter_role="tester",
            decision=False, weight=1.0,
        ))
        record = self.engine.reach_consensus(proposal.proposal_id)
        assert record.outcome == DecisionOutcome.REJECTED

    def test_cast_vote_invalid_proposal(self):
        with pytest.raises(ValueError):
            self.engine.cast_vote("nonexistent", Vote(
                voter_id="w1", voter_role="architect", decision=True,
            ))

    def test_reach_consensus_invalid_proposal(self):
        with pytest.raises(ValueError):
            self.engine.reach_consensus("nonexistent")

    def test_get_record(self):
        proposal = self.engine.create_proposal(
            topic="Test topic", proposer_id="w1", content="Test",
        )
        self.engine.cast_vote(proposal.proposal_id, Vote(
            voter_id="w1", voter_role="architect", decision=True,
        ))
        record = self.engine.reach_consensus(proposal.proposal_id)
        fetched = self.engine.get_record(record.record_id)
        assert fetched is not None
        assert fetched.topic == "Test topic"

    def test_get_all_records(self):
        p1 = self.engine.create_proposal(topic="T1", proposer_id="w1", content="C1")
        p2 = self.engine.create_proposal(topic="T2", proposer_id="w1", content="C2")
        self.engine.cast_vote(p1.proposal_id, Vote(
            voter_id="w1", voter_role="architect", decision=True,
        ))
        self.engine.cast_vote(p2.proposal_id, Vote(
            voter_id="w1", voter_role="architect", decision=True,
        ))
        self.engine.reach_consensus(p1.proposal_id)
        self.engine.reach_consensus(p2.proposal_id)
        records = self.engine.get_all_records()
        assert len(records) == 2

    def test_weighted_voting(self):
        proposal = self.engine.create_proposal(
            topic="Weighted test", proposer_id="w1", content="Test",
        )
        self.engine.cast_vote(proposal.proposal_id, Vote(
            voter_id="arch-1", voter_role="architect",
            decision=True, weight=1.5,
        ))
        self.engine.cast_vote(proposal.proposal_id, Vote(
            voter_id="ui-1", voter_role="ui-designer",
            decision=False, weight=0.9,
        ))
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
        self.sp.write(ScratchpadEntry(
            entry_id="entry-existing",
            content="Use SQL",
        ))
        entry_id = self.worker.write_conflict(
            conflict="Should use NoSQL instead",
            conflicting_entry_id="entry-existing",
            reason="Better for unstructured data",
        )
        assert entry_id.startswith("entry-")
        conflicts = self.sp.get_conflicts()
        assert len(conflicts) >= 1

    def test_read_scratchpad(self):
        self.sp.write(ScratchpadEntry(
            worker_id="other-worker",
            content="Existing finding",
        ))
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
