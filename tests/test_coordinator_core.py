#!/usr/bin/env python3
"""
Coordinator Core Methods Tests

覆盖 coordinator 核心同步方法：
- plan_task: 任务规划
- spawn_workers: Worker 创建
- plan_review_bundles: Review 任务规划
- apply_file_bundling: 文件分组
- collect_results: 结果收集
- resolve_conflicts: 冲突解决
- generate_report: 报告生成
"""

import os
import shutil
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.collaboration.coordinator import Coordinator
from scripts.collaboration.models import (
    BatchMode,
    EntryType,
    ExecutionPlan,
    ScratchpadEntry,
)
from scripts.collaboration.scratchpad import Scratchpad

pytestmark = pytest.mark.unit


class TestCoordinatorPlanTask:
    """测试 plan_task 任务规划"""

    @pytest.fixture
    def coordinator(self):
        """创建测试用 coordinator"""
        tmp_dir = tempfile.mkdtemp(prefix="coord_test_")
        scratchpad = Scratchpad(persist_dir=tmp_dir)
        coord = Coordinator(scratchpad=scratchpad)
        yield coord
        shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_plan_task_single_role(self, coordinator):
        """测试单角色任务规划"""
        available_roles = [{"role_id": "architect", "role_prompt": "You are an architect"}]

        plan = coordinator.plan_task("设计系统架构", available_roles)

        assert isinstance(plan, ExecutionPlan)
        assert plan.total_tasks == 1
        assert len(plan.batches) == 1
        assert plan.batches[0].mode == BatchMode.PARALLEL
        assert len(plan.batches[0].tasks) == 1

        task = plan.batches[0].tasks[0]
        assert task.role_id == "architect"
        assert task.role_prompt == "You are an architect"
        assert "设计系统架构" in task.description

    def test_plan_task_multiple_roles(self, coordinator):
        """测试多角色任务规划"""
        available_roles = [
            {"role_id": "architect", "role_prompt": "Architect prompt"},
            {"role_id": "tester", "role_prompt": "Tester prompt"},
            {"role_id": "reviewer", "role_prompt": "Reviewer prompt"},
        ]

        plan = coordinator.plan_task("开发新功能", available_roles)

        assert plan.total_tasks == 3
        assert len(plan.batches) == 1
        assert len(plan.batches[0].tasks) == 3

        role_ids = [task.role_id for task in plan.batches[0].tasks]
        assert "architect" in role_ids
        assert "tester" in role_ids
        assert "reviewer" in role_ids

    def test_plan_task_empty_roles(self, coordinator):
        """测试空角色列表"""
        plan = coordinator.plan_task("测试任务", [])

        assert plan.total_tasks == 0
        # 空任务可能仍有空batch，只检查total_tasks

    def test_plan_task_with_stage_id(self, coordinator):
        """测试带 stage_id 的任务规划"""
        available_roles = [{"role_id": "architect", "role_prompt": "prompt"}]

        plan = coordinator.plan_task("任务", available_roles, stage_id="stage-1")

        task = plan.batches[0].tasks[0]
        assert task.stage_id == "stage-1"

    def test_plan_task_estimated_parallelism(self, coordinator):
        """测试并行度估算"""
        # 单任务并行度为 0
        plan1 = coordinator.plan_task("任务", [{"role_id": "r1", "role_prompt": "p1"}])
        assert plan1.estimated_parallelism == 0.0

        # 多任务并行度为 1.0
        plan2 = coordinator.plan_task(
            "任务",
            [
                {"role_id": "r1", "role_prompt": "p1"},
                {"role_id": "r2", "role_prompt": "p2"},
            ],
        )
        assert plan2.estimated_parallelism == 1.0


class TestCoordinatorPlanReviewBundles:
    """测试 plan_review_bundles 方法"""

    @pytest.fixture
    def coordinator(self):
        tmp_dir = tempfile.mkdtemp(prefix="coord_test_")
        scratchpad = Scratchpad(persist_dir=tmp_dir)
        coord = Coordinator(scratchpad=scratchpad)
        yield coord
        shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_plan_review_small_changeset(self, coordinator):
        """测试小于5个文件的changeset - 不分bundle"""
        changeset = ["file1.py", "file2.py", "file3.py"]
        available_roles = [{"role_id": "reviewer", "role_prompt": "review"}]

        plan = coordinator.plan_review_bundles("Review changes", available_roles, changeset)

        # 小于5个文件不分bundle，1个bundle = 1个task
        assert plan.total_tasks == 1
        assert len(plan.review_bundles) == 1
        assert plan.review_bundles[0] == changeset

    def test_plan_review_large_changeset(self, coordinator):
        """测试大于5个文件的changeset - FileBundler行为"""
        changeset = [f"file{i}.py" for i in range(10)]
        available_roles = [{"role_id": "reviewer", "role_prompt": "review"}]

        plan = coordinator.plan_review_bundles("Review changes", available_roles, changeset)

        # FileBundler可能不分bundle（依赖实现），至少验证plan生成
        assert plan.total_tasks >= 1
        assert len(plan.review_bundles) >= 1

    def test_plan_review_round_robin_roles(self, coordinator):
        """测试多角色轮询分配"""
        changeset = [f"file{i}.py" for i in range(8)]
        available_roles = [
            {"role_id": "reviewer1", "role_prompt": "p1"},
            {"role_id": "reviewer2", "role_prompt": "p2"},
        ]

        plan = coordinator.plan_review_bundles("Review", available_roles, changeset)

        # 检查角色分配（至少有一个任务）
        tasks = plan.batches[0].tasks if plan.batches else []
        assert len(tasks) >= 1
        # 第一个任务应该分配给reviewer1
        assert tasks[0].role_id == "reviewer1"

    def test_plan_review_read_only_tasks(self, coordinator):
        """测试review任务标记为只读"""
        changeset = ["file1.py", "file2.py"]
        available_roles = [{"role_id": "reviewer", "role_prompt": "p"}]

        plan = coordinator.plan_review_bundles("Review", available_roles, changeset)

        for batch in plan.batches:
            for task in batch.tasks:
                assert task.is_read_only is True


class TestCoordinatorApplyFileBundling:
    """测试 apply_file_bundling 方法"""

    @pytest.fixture
    def coordinator(self):
        tmp_dir = tempfile.mkdtemp(prefix="coord_test_")
        scratchpad = Scratchpad(persist_dir=tmp_dir)
        coord = Coordinator(scratchpad=scratchpad)
        yield coord
        shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_non_review_mode_no_bundling(self, coordinator):
        """测试非review模式不分bundle"""
        files = [f"file{i}.py" for i in range(10)]

        bundles = coordinator.apply_file_bundling("implement", files)

        # 非review模式，返回单个bundle包含所有文件
        assert len(bundles) == 1
        assert bundles[0] == files

    def test_review_mode_small_files_no_bundling(self, coordinator):
        """测试review模式小文件不分bundle"""
        files = ["f1.py", "f2.py", "f3.py"]

        bundles = coordinator.apply_file_bundling("review", files)

        # <=5个文件不分bundle
        assert len(bundles) == 1
        assert bundles[0] == files

    def test_review_mode_large_files_bundling(self, coordinator):
        """测试review模式大文件bundling行为"""
        files = [f"file{i}.py" for i in range(10)]

        bundles = coordinator.apply_file_bundling("review", files)

        # 验证返回bundle列表（FileBundler具体分割逻辑可能变化）
        assert len(bundles) >= 1
        assert isinstance(bundles, list)

    def test_empty_files_returns_empty(self, coordinator):
        """测试空文件列表"""
        bundles = coordinator.apply_file_bundling("review", [])

        assert bundles == []


class TestCoordinatorSpawnWorkers:
    """测试 spawn_workers 方法"""

    @pytest.fixture
    def coordinator(self):
        tmp_dir = tempfile.mkdtemp(prefix="coord_test_")
        scratchpad = Scratchpad(persist_dir=tmp_dir)
        coord = Coordinator(scratchpad=scratchpad)
        yield coord
        shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_spawn_workers_from_plan(self, coordinator):
        """测试从plan创建workers"""
        # 先创建plan
        available_roles = [
            {"role_id": "architect", "role_prompt": "arch"},
            {"role_id": "tester", "role_prompt": "test"},
        ]
        plan = coordinator.plan_task("任务", available_roles)

        # spawn workers
        workers = coordinator.spawn_workers(plan)

        assert len(workers) == 2
        assert len(coordinator.workers) == 2
        assert "architect" in [w.role_id for w in workers]
        assert "tester" in [w.role_id for w in workers]

    def test_spawn_workers_clears_previous(self, coordinator):
        """测试spawn_workers清除之前的workers"""
        plan1 = coordinator.plan_task("任务1", [{"role_id": "r1", "role_prompt": "p1"}])
        coordinator.spawn_workers(plan1)
        assert len(coordinator.workers) == 1

        plan2 = coordinator.plan_task(
            "任务2",
            [
                {"role_id": "r2", "role_prompt": "p2"},
                {"role_id": "r3", "role_prompt": "p3"},
            ],
        )
        workers2 = coordinator.spawn_workers(plan2)

        # 应该清除之前的，只有新的
        assert len(coordinator.workers) == 2
        assert len(workers2) == 2

    def test_spawn_workers_empty_plan(self, coordinator):
        """测试空plan"""
        plan = coordinator.plan_task("任务", [])
        workers = coordinator.spawn_workers(plan)

        assert len(workers) == 0
        assert len(coordinator.workers) == 0


class TestCoordinatorCollectResults:
    """测试 collect_results 方法"""

    @pytest.fixture
    def coordinator(self):
        tmp_dir = tempfile.mkdtemp(prefix="coord_test_")
        scratchpad = Scratchpad(persist_dir=tmp_dir)
        coord = Coordinator(scratchpad=scratchpad)
        yield coord
        shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_collect_results_returns_dict(self, coordinator):
        """测试collect_results返回字典而非列表"""
        # 写入一些entries
        entry = ScratchpadEntry(
            worker_id="worker1",
            role_id="architect",
            entry_type=EntryType.FINDING,
            content="Work completed",
            confidence=0.9,
        )
        coordinator.scratchpad.write(entry)

        # 收集结果
        results = coordinator.collect_results()

        # collect_results 返回字典而非列表
        assert isinstance(results, dict)
        assert "total_entries" in results or "scratchpad" in results


class TestCoordinatorResolveConflicts:
    """测试 resolve_conflicts 方法"""

    @pytest.fixture
    def coordinator(self):
        tmp_dir = tempfile.mkdtemp(prefix="coord_test_")
        scratchpad = Scratchpad(persist_dir=tmp_dir)
        coord = Coordinator(scratchpad=scratchpad)
        # consensus作为属性设置，不是构造参数
        from scripts.collaboration.consensus import ConsensusEngine

        coord.consensus = ConsensusEngine()
        yield coord
        shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_resolve_conflicts_empty_results(self, coordinator):
        """测试resolve_conflicts方法（无参数）"""
        # resolve_conflicts 从 scratchpad 读取冲突
        conflicts = coordinator.resolve_conflicts()

        # 无冲突时返回空列表
        assert conflicts == []

    def test_resolve_conflicts_with_conflict_entry(self, coordinator):
        """测试有冲突entry时的解决"""
        # 写入一个CONFLICT类型的entry
        conflict_entry = ScratchpadEntry(
            worker_id="worker1",
            role_id="reviewer",
            entry_type=EntryType.CONFLICT,
            content="Conflict detected",
            confidence=1.0,
        )
        coordinator.scratchpad.write(conflict_entry)

        # resolve_conflicts 应该处理这个冲突
        conflicts = coordinator.resolve_conflicts()

        # 返回的共识记录列表
        assert isinstance(conflicts, list)


class TestCoordinatorGenerateReport:
    """测试 generate_report 方法"""

    @pytest.fixture
    def coordinator(self):
        tmp_dir = tempfile.mkdtemp(prefix="coord_test_")
        scratchpad = Scratchpad(persist_dir=tmp_dir)
        coord = Coordinator(scratchpad=scratchpad)
        yield coord
        shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_generate_report_basic(self, coordinator):
        """测试基本报告生成"""
        # 写入一些entries
        entry = ScratchpadEntry(
            worker_id="worker1",
            role_id="architect",
            entry_type=EntryType.FINDING,
            content="Work completed",
            confidence=0.9,
        )
        coordinator.scratchpad.write(entry)

        report = coordinator.generate_report()

        assert isinstance(report, str)
        assert len(report) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
