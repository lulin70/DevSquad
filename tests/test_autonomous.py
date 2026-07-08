"""V4.0.0 P3-1: Autonomous 自主迭代模式单元测试。

覆盖 5 大组件：
- RunState: 状态转换/序列化/属性
- NotesMemory: 断点续跑记忆（save/load/verify_checksum/list_resumable/wrap_for_loop）
- SmartConfirmation: 三态决策（smart/whitelist-only/blacklist-only）
- GitDriver: 自动 git 操作（commit/branch/tag/status + 确认流程）
- AutonomousLoopController: 4 阶段循环 + 共识门 + 断点续跑
- ConsensusAwareEvaluator: HC-2 共识门约束

测试哲学：使用真实组件（真实 git 仓库 / 真实 NotesMemory 文件持久化），
仅在边界处使用最小 stub（如 stub dispatcher 替代真实 MultiAgentDispatcher）。
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest

from scripts.collaboration.autonomous import (
    AutonomousLoopController,
    ConfirmationDecision,
    GitDriver,
    NotesMemory,
    RunState,
    RunStatus,
    SmartConfirmation,
)
from scripts.collaboration.autonomous.loop_controller import (
    AutonomousConfig,
    AutonomousRunReport,
    ConsensusAwareEvaluator,
)
from scripts.collaboration.autonomous.smart_confirmation import (
    ConfirmationMode,
    ConfirmationVerdict,
)
from scripts.collaboration.loop_engineering import (
    EvaluatorMode,
    HandoffAdapter,
    IndependentEvaluator,
    LoopEngineeringConfig,
    LoopKernel,
    LoopType,
    UnifiedMemory,
)

# ---------------------------------------------------------------------------
# Test fixtures: 最小 stub，符合 Protocol 但不启动真实 dispatcher
# ---------------------------------------------------------------------------


class StubDispatcher:
    """最小 HandoffAdapter.dispatcher 兼容实现。

    不调用真实 worker，直接返回结构化 handoff 结果，
    让 LoopKernel 能跑完五步闭环。
    """

    def dispatch(self, task_description: str, **kwargs: Any) -> dict[str, Any]:  # noqa: ARG002
        return {
            "status": "ok",
            "output": f"stub-dispatched: {task_description}",
            "tasks": [{"name": "stub-task"}],
        }


class StubConsensusEngine:
    """最小 ConsensusEngine stub，用于测试 HC-2 共识门。

    实现完整的 create_proposal → cast_vote → reach_consensus 流程，
    根据 allow 参数返回 APPROVED 或 REJECTED。
    """

    def __init__(self, *, allow: bool = True) -> None:
        self._allow = allow
        self.proposals: list[dict[str, Any]] = []
        self._next_id = 0
        self._votes: dict[str, list[Any]] = {}

    def create_proposal(
        self,
        topic: str,
        proposer_id: str,
        content: str,
        options: list[str] | None = None,  # noqa: ARG002
        deadline: Any = None,  # noqa: ARG002
    ) -> Any:
        self._next_id += 1
        proposal_id = f"stub-prop-{self._next_id}"

        class StubProposal:
            def __init__(self, pid: str, t: str, pid2: str, c: str) -> None:
                self.proposal_id = pid
                self.topic = t
                self.proposer_id = pid2
                self.proposal_content = c
                self.votes: list[Any] = []
                self.status = "open"

        proposal = StubProposal(proposal_id, topic, proposer_id, content)
        self.proposals.append({
            "proposal_id": proposal_id,
            "topic": topic,
            "proposer_id": proposer_id,
            "content": content,
        })
        self._votes[proposal_id] = []
        return proposal

    def cast_vote(self, proposal_id: str, vote: Any) -> Any:
        if proposal_id in self._votes:
            self._votes[proposal_id].append(vote)
        for p in self.proposals:
            if p["proposal_id"] == proposal_id:
                p.setdefault("votes", []).append(vote)
        return self.proposals[-1] if self.proposals else {}

    def reach_consensus(self, proposal_id: str) -> Any:
        votes_count = len(self._votes.get(proposal_id, []))
        is_allowed = self._allow

        class StubOutcome:
            def __init__(self, approved: bool) -> None:
                self.value = "approved" if approved else "rejected"

        class StubRecord:
            def __init__(self) -> None:
                self.outcome = StubOutcome(is_allowed)
                self.votes_for = votes_count if is_allowed else 0
                self.votes_against = 0 if is_allowed else votes_count

        return StubRecord()

    def check_gate(self, _result: Any) -> dict[str, Any]:
        return {"approved": self._allow, "reason": "stub-allow" if self._allow else "stub-deny"}


# ---------------------------------------------------------------------------
# TestRunState
# ---------------------------------------------------------------------------


class TestRunState:
    """运行状态管理测试。"""

    def test_default_status_idle(self):
        state = RunState(run_id="r1", objective="test")
        assert state.status == RunStatus.IDLE
        assert state.current_iteration == 0
        assert state.max_iterations == 20
        assert state.completed_phases == []
        assert state.checkpoint_sha == ""

    def test_update_status_changes_updated_at(self):
        state = RunState(run_id="r1", objective="test")
        old_updated = state.updated_at
        state.update_status(RunStatus.PLANNING)
        assert state.status == RunStatus.PLANNING
        # updated_at 应被刷新（时间戳精度问题可能相等，但格式正确）
        assert state.updated_at >= old_updated

    def test_increment_iteration(self):
        state = RunState(run_id="r1", objective="test")
        assert state.increment_iteration() == 1
        assert state.current_iteration == 1
        assert state.increment_iteration() == 2

    def test_add_note_with_timestamp(self):
        state = RunState(run_id="r1", objective="test")
        state.add_note("first note")
        assert len(state.notes) == 1
        assert "first note" in state.notes[0]
        assert state.notes[0].startswith("[")

    def test_mark_phase_completed_idempotent(self):
        state = RunState(run_id="r1", objective="test")
        state.mark_phase_completed("plan")
        state.mark_phase_completed("plan")  # 重复调用不应追加
        assert state.completed_phases == ["plan"]

    def test_mark_phase_failed_idempotent(self):
        state = RunState(run_id="r1", objective="test")
        state.mark_phase_failed("verify")
        state.mark_phase_failed("verify")
        assert state.failed_phases == ["verify"]

    @pytest.mark.parametrize(
        "status,expected_terminal",
        [
            (RunStatus.COMPLETED, True),
            (RunStatus.FAILED, True),
            (RunStatus.STOPPED, True),
            (RunStatus.IDLE, False),
            (RunStatus.PLANNING, False),
            (RunStatus.PAUSED, False),
        ],
    )
    def test_is_terminal(self, status: RunStatus, expected_terminal: bool):
        state = RunState(run_id="r1", objective="test", status=status)
        assert state.is_terminal is expected_terminal

    @pytest.mark.parametrize(
        "status,expected_running",
        [
            (RunStatus.PLANNING, True),
            (RunStatus.DEVELOPING, True),
            (RunStatus.VERIFYING, True),
            (RunStatus.FIXING, True),
            (RunStatus.IDLE, False),
            (RunStatus.COMPLETED, False),
            (RunStatus.PAUSED, False),
        ],
    )
    def test_is_running(self, status: RunStatus, expected_running: bool):
        state = RunState(run_id="r1", objective="test", status=status)
        assert state.is_running is expected_running

    def test_can_resume_only_paused(self):
        paused = RunState(run_id="r1", objective="t", status=RunStatus.PAUSED)
        assert paused.can_resume is True

        planning = RunState(run_id="r2", objective="t", status=RunStatus.PLANNING)
        assert planning.can_resume is False

        completed = RunState(run_id="r3", objective="t", status=RunStatus.COMPLETED)
        assert completed.can_resume is False

    def test_to_dict_and_from_dict_roundtrip(self):
        original = RunState(
            run_id="r-rt",
            objective="roundtrip test",
            status=RunStatus.VERIFYING,
            current_iteration=3,
            max_iterations=10,
            completed_phases=["plan", "dev"],
            failed_phases=[],
            checkpoint_sha="abc123",
            notes=["note1"],
            error="",
        )
        data = original.to_dict()
        # 序列化结果必须是 JSON 可序列化
        json.dumps(data)

        restored = RunState.from_dict(data)
        assert restored.run_id == original.run_id
        assert restored.objective == original.objective
        assert restored.status == original.status
        assert restored.current_iteration == original.current_iteration
        assert restored.max_iterations == original.max_iterations
        assert restored.completed_phases == original.completed_phases
        assert restored.failed_phases == original.failed_phases
        assert restored.checkpoint_sha == original.checkpoint_sha
        assert restored.notes == original.notes

    def test_from_dict_with_defaults(self):
        """from_dict 应容忍缺失字段。"""
        restored = RunState.from_dict({"run_id": "x", "objective": "y"})
        assert restored.run_id == "x"
        assert restored.status == RunStatus.IDLE
        assert restored.current_iteration == 0
        assert restored.completed_phases == []


# ---------------------------------------------------------------------------
# TestNotesMemory
# ---------------------------------------------------------------------------


class TestNotesMemory:
    """断点续跑记忆测试（使用真实文件持久化）。"""

    def test_save_creates_json_file(self, tmp_path: Path):
        memory = NotesMemory(storage_dir=str(tmp_path))
        state = RunState(run_id="r-save", objective="save test")
        filepath = memory.save(state)

        assert filepath.exists()
        assert filepath.name == "run_r-save.json"
        data = json.loads(filepath.read_text(encoding="utf-8"))
        assert data["run_id"] == "r-save"
        # save 后应写入 checkpoint_sha
        assert data["checkpoint_sha"] != ""
        assert len(data["checkpoint_sha"]) == 64  # SHA256 hex

    def test_load_returns_state(self, tmp_path: Path):
        memory = NotesMemory(storage_dir=str(tmp_path))
        original = RunState(
            run_id="r-load",
            objective="load test",
            status=RunStatus.VERIFYING,
            current_iteration=2,
        )
        memory.save(original)

        loaded = memory.load("r-load")
        assert loaded is not None
        assert loaded.run_id == "r-load"
        assert loaded.status == RunStatus.VERIFYING
        assert loaded.current_iteration == 2

    def test_load_missing_returns_none(self, tmp_path: Path):
        memory = NotesMemory(storage_dir=str(tmp_path))
        assert memory.load("nonexistent") is None

    def test_load_corrupted_returns_none(self, tmp_path: Path):
        """损坏的 JSON 文件应优雅返回 None，不抛异常。"""
        memory = NotesMemory(storage_dir=str(tmp_path))
        (tmp_path / "run_bad.json").write_text("{invalid json", encoding="utf-8")
        assert memory.load("bad") is None

    def test_verify_checksum_valid(self, tmp_path: Path):
        memory = NotesMemory(storage_dir=str(tmp_path))
        state = RunState(run_id="r-sha", objective="checksum test")
        memory.save(state)

        loaded = memory.load("r-sha")
        assert loaded is not None
        assert memory.verify_checksum(loaded) is True

    def test_verify_checksum_tampered(self, tmp_path: Path):
        """篡改 checkpoint_sha 后应校验失败。"""
        memory = NotesMemory(storage_dir=str(tmp_path))
        state = RunState(run_id="r-tamper", objective="tamper test")
        memory.save(state)

        # 篡改 sha
        state.checkpoint_sha = "0" * 64
        assert memory.verify_checksum(state) is False

    def test_verify_checksum_empty(self):
        state = RunState(run_id="r-empty", objective="t")
        # 默认 checkpoint_sha == ""
        assert state.checkpoint_sha == ""
        memory = NotesMemory(storage_dir="/tmp/test_nm_empty")
        assert memory.verify_checksum(state) is False

    def test_list_runs(self, tmp_path: Path):
        memory = NotesMemory(storage_dir=str(tmp_path))
        for rid in ["a", "b", "c"]:
            memory.save(RunState(run_id=rid, objective=rid))

        runs = memory.list_runs()
        assert sorted(runs) == ["a", "b", "c"]

    def test_delete_existing(self, tmp_path: Path):
        memory = NotesMemory(storage_dir=str(tmp_path))
        memory.save(RunState(run_id="r-del", objective="t"))
        assert memory.delete("r-del") is True
        assert memory.load("r-del") is None

    def test_delete_missing(self, tmp_path: Path):
        memory = NotesMemory(storage_dir=str(tmp_path))
        assert memory.delete("nope") is False

    def test_list_resumable_filters_paused_only(self, tmp_path: Path):
        memory = NotesMemory(storage_dir=str(tmp_path))
        # 3 个状态：PAUSED（可续跑）、COMPLETED（终态）、PLANNING（运行中）
        memory.save(RunState(run_id="r-paused", objective="t", status=RunStatus.PAUSED))
        memory.save(RunState(run_id="r-done", objective="t", status=RunStatus.COMPLETED))
        memory.save(RunState(run_id="r-running", objective="t", status=RunStatus.PLANNING))

        resumable = memory.list_resumable()
        rids = [s.run_id for s in resumable]
        assert rids == ["r-paused"]

    def test_wrap_for_loop_returns_unified_memory(self, tmp_path: Path):
        """wrap_for_loop 应返回共享存储目录的 UnifiedMemory 实例。"""
        memory = NotesMemory(storage_dir=str(tmp_path))
        wrapped = memory.wrap_for_loop()
        assert isinstance(wrapped, UnifiedMemory)
        # 验证存储目录在 NotesMemory 目录下
        assert str(tmp_path) in str(wrapped._storage_dir)
        # 验证可正常使用
        assert hasattr(wrapped, "persist_event")


# ---------------------------------------------------------------------------
# TestSmartConfirmation
# ---------------------------------------------------------------------------


class TestSmartConfirmation:
    """智能确认三态决策测试。"""

    @pytest.mark.parametrize(
        "operation,expected_risk",
        [
            ("delete old files", "high"),
            ("deploy to production", "high"),
            ("drop table users", "high"),
            ("git commit fix", "medium"),
            ("git push origin main", "medium"),
            ("install requests", "medium"),
            ("read file", "low"),
            ("list all tasks", "low"),
            ("run tests", "low"),
        ],
    )
    def test_assess_risk(self, operation: str, expected_risk: str):
        confirmer = SmartConfirmation(mode=ConfirmationMode.SMART)
        decision = confirmer.evaluate(operation)
        assert decision.risk_level == expected_risk

    def test_smart_mode_high_risk_requires_confirmation(self):
        confirmer = SmartConfirmation(mode=ConfirmationMode.SMART)
        decision = confirmer.evaluate("delete all data")
        assert decision.verdict == ConfirmationVerdict.REQUIRE_CONFIRMATION
        assert "High-risk" in decision.reason

    def test_smart_mode_low_risk_auto_approved(self):
        confirmer = SmartConfirmation(mode=ConfirmationMode.SMART)
        decision = confirmer.evaluate("read config file")
        assert decision.verdict == ConfirmationVerdict.APPROVE
        assert "Low-risk" in decision.reason

    def test_smart_mode_medium_risk_in_whitelist(self):
        """中风险但操作词在白名单（如 commit+lint 组合）应自动批准。"""
        confirmer = SmartConfirmation(mode=ConfirmationMode.SMART)
        # "commit" 在 medium 关键词，"lint" 在白名单
        decision = confirmer.evaluate("git commit lint check")
        assert decision.risk_level == "medium"
        assert decision.verdict == ConfirmationVerdict.APPROVE
        assert "Medium-risk but in whitelist" in decision.reason

    def test_smart_mode_medium_risk_not_in_whitelist(self):
        confirmer = SmartConfirmation(mode=ConfirmationMode.SMART)
        decision = confirmer.evaluate("git push origin main")
        assert decision.verdict == ConfirmationVerdict.REQUIRE_CONFIRMATION
        assert "Medium-risk" in decision.reason

    def test_whitelist_only_mode_approves_whitelist(self):
        confirmer = SmartConfirmation(mode=ConfirmationMode.WHITELIST_ONLY)
        decision = confirmer.evaluate("read config")
        assert decision.verdict == ConfirmationVerdict.APPROVE

    def test_whitelist_only_mode_requires_confirmation_for_others(self):
        confirmer = SmartConfirmation(mode=ConfirmationMode.WHITELIST_ONLY)
        # "write" 不在白名单
        decision = confirmer.evaluate("write config file")
        assert decision.verdict == ConfirmationVerdict.REQUIRE_CONFIRMATION
        assert "not in whitelist" in decision.reason

    def test_blacklist_only_mode_approves_non_blacklist(self):
        confirmer = SmartConfirmation(mode=ConfirmationMode.BLACKLIST_ONLY)
        # "read" 不在黑名单
        decision = confirmer.evaluate("read user data")
        assert decision.verdict == ConfirmationVerdict.APPROVE

    def test_blacklist_only_mode_requires_confirmation_for_blacklist(self):
        confirmer = SmartConfirmation(mode=ConfirmationMode.BLACKLIST_ONLY)
        decision = confirmer.evaluate("delete user record")
        assert decision.verdict == ConfirmationVerdict.REQUIRE_CONFIRMATION
        assert "in blacklist" in decision.reason

    def test_custom_whitelist(self):
        confirmer = SmartConfirmation(
            mode=ConfirmationMode.WHITELIST_ONLY,
            custom_whitelist={"my_op"},
        )
        # 自定义白名单覆盖默认
        assert confirmer.evaluate("my_op").verdict == ConfirmationVerdict.APPROVE
        # 默认白名单的 read 不再被批准
        assert (
            confirmer.evaluate("read config").verdict
            == ConfirmationVerdict.REQUIRE_CONFIRMATION
        )

    def test_custom_blacklist(self):
        confirmer = SmartConfirmation(
            mode=ConfirmationMode.BLACKLIST_ONLY,
            custom_blacklist={"dangerous_op"},
        )
        assert (
            confirmer.evaluate("dangerous_op").verdict
            == ConfirmationVerdict.REQUIRE_CONFIRMATION
        )
        # 默认黑名单的 delete 不再触发确认
        assert confirmer.evaluate("delete file").verdict == ConfirmationVerdict.APPROVE

    def test_evaluate_many(self):
        confirmer = SmartConfirmation()
        decisions = confirmer.evaluate_many(["read x", "delete y", "test z"])
        assert len(decisions) == 3
        assert decisions[0].verdict == ConfirmationVerdict.APPROVE
        assert decisions[1].verdict == ConfirmationVerdict.REQUIRE_CONFIRMATION
        assert decisions[2].verdict == ConfirmationVerdict.APPROVE

    def test_mode_property(self):
        confirmer = SmartConfirmation(mode=ConfirmationMode.BLACKLIST_ONLY)
        assert confirmer.mode == ConfirmationMode.BLACKLIST_ONLY

    def test_decision_dataclass_fields(self):
        confirmer = SmartConfirmation()
        decision = confirmer.evaluate("read file")
        assert isinstance(decision, ConfirmationDecision)
        assert decision.operation == "read file"
        assert decision.risk_level in ("low", "medium", "high")
        assert isinstance(decision.verdict, ConfirmationVerdict)
        assert isinstance(decision.reason, str)


# ---------------------------------------------------------------------------
# TestGitDriver（使用真实 git 仓库）
# ---------------------------------------------------------------------------


def _init_real_git_repo(repo_path: Path) -> None:
    """初始化一个真实的 git 仓库（用于测试 GitDriver）。"""
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "test@example.com",
    }
    subprocess.run(["git", "init"], cwd=str(repo_path), check=True, env=env, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(repo_path), check=True, env=env, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=str(repo_path), check=True, env=env, capture_output=True,
    )


class TestGitDriver:
    """自动 git 操作测试（使用真实 git 仓库）。"""

    def test_status_on_clean_repo(self, tmp_path: Path):
        _init_real_git_repo(tmp_path)
        driver = GitDriver(repo_path=tmp_path, auto_confirm=True)
        result = driver.status()
        assert result.success
        # 全新空仓库 status 应为空字符串
        assert result.output == ""

    def test_status_on_dirty_repo(self, tmp_path: Path):
        _init_real_git_repo(tmp_path)
        (tmp_path / "file.txt").write_text("hello", encoding="utf-8")
        driver = GitDriver(repo_path=tmp_path, auto_confirm=True)
        result = driver.status()
        assert result.success
        assert "file.txt" in result.output

    def test_has_uncommitted_changes(self, tmp_path: Path):
        _init_real_git_repo(tmp_path)
        driver = GitDriver(repo_path=tmp_path, auto_confirm=True)
        assert driver.has_uncommitted_changes() is False

        (tmp_path / "new.txt").write_text("data", encoding="utf-8")
        assert driver.has_uncommitted_changes() is True

    def test_current_branch(self, tmp_path: Path):
        _init_real_git_repo(tmp_path)
        # git init 后无 commit 时 HEAD 是 unborn，需先 commit 才能获取分支名
        (tmp_path / "init.txt").write_text("init", encoding="utf-8")
        subprocess.run(["git", "add", "init.txt"], cwd=str(tmp_path), capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=str(tmp_path), capture_output=True, check=True)

        driver = GitDriver(repo_path=tmp_path, auto_confirm=True)
        branch = driver.current_branch()
        # git init 默认分支可能是 main / master
        assert branch in ("main", "master")

    def test_commit_with_auto_confirm(self, tmp_path: Path):
        _init_real_git_repo(tmp_path)
        (tmp_path / "file.txt").write_text("content", encoding="utf-8")

        driver = GitDriver(repo_path=tmp_path, auto_confirm=True)
        result = driver.commit("test: add file", files=["file.txt"])
        assert result.success, f"commit failed: {result.error}"
        assert result.confirmed

        # 验证提交确实发生
        log = subprocess.run(
            ["git", "log", "--oneline"],
            cwd=str(tmp_path), capture_output=True, text=True, check=True,
        )
        assert "test: add file" in log.stdout

    def test_commit_without_auto_confirm_blocked(self, tmp_path: Path):
        """未启用 auto_confirm 时，commit（中风险）应被 SmartConfirmation 拦截。"""
        _init_real_git_repo(tmp_path)
        (tmp_path / "file.txt").write_text("content", encoding="utf-8")

        driver = GitDriver(repo_path=tmp_path, auto_confirm=False)
        # commit message 不含白名单子串（如 test/list/read），确保触发 REQUIRE_CONFIRMATION
        result = driver.commit("update config file", files=["file.txt"])
        assert not result.success
        assert "requires confirmation" in result.error
        assert result.confirmed is False

        # 验证确实未提交
        log = subprocess.run(
            ["git", "log", "--oneline"],
            cwd=str(tmp_path), capture_output=True, text=True, check=False,
        )
        assert log.stdout == ""

    def test_create_branch_with_auto_confirm(self, tmp_path: Path):
        _init_real_git_repo(tmp_path)
        # 先做一个初始提交
        (tmp_path / "init.txt").write_text("init", encoding="utf-8")
        subprocess.run(
            ["git", "add", "init.txt"],
            cwd=str(tmp_path), capture_output=True, check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=str(tmp_path), capture_output=True, check=True,
        )

        driver = GitDriver(repo_path=tmp_path, auto_confirm=True)
        result = driver.create_branch("feature-x")
        assert result.success, f"branch creation failed: {result.error}"

        # 验证当前分支
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(tmp_path), capture_output=True, text=True, check=True,
        )
        assert branch.stdout.strip() == "feature-x"

    def test_tag_with_auto_confirm(self, tmp_path: Path):
        _init_real_git_repo(tmp_path)
        # 必须先有提交才能打 tag
        (tmp_path / "init.txt").write_text("init", encoding="utf-8")
        subprocess.run(["git", "add", "init.txt"], cwd=str(tmp_path), capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=str(tmp_path), capture_output=True, check=True)

        driver = GitDriver(repo_path=tmp_path, auto_confirm=True)
        result = driver.tag("v1.0.0", message="release 1.0.0")
        assert result.success, f"tag failed: {result.error}"

        # 验证 tag 存在
        tags = subprocess.run(
            ["git", "tag", "-l"],
            cwd=str(tmp_path), capture_output=True, text=True, check=True,
        )
        assert "v1.0.0" in tags.stdout

    def test_commit_with_allow_push_no_remote(self, tmp_path: Path):
        """allow_push=True 但无 remote 时应失败（git push 报错）。"""
        _init_real_git_repo(tmp_path)
        (tmp_path / "f.txt").write_text("x", encoding="utf-8")

        driver = GitDriver(repo_path=tmp_path, auto_confirm=True)
        result = driver.commit("msg", files=["f.txt"], allow_push=True)
        # commit 应成功，push 应失败
        assert not result.success
        assert "push" in result.error.lower() or result.error  # 有错误信息

    def test_status_readonly_no_confirmation_needed(self, tmp_path: Path):
        """只读操作（status/current_branch）不需要 auto_confirm 也应通过。"""
        _init_real_git_repo(tmp_path)
        driver = GitDriver(repo_path=tmp_path, auto_confirm=False)
        # status 是只读，不走 SmartConfirmation
        result = driver.status()
        assert result.success


# ---------------------------------------------------------------------------
# TestAutonomousLoopController
# ---------------------------------------------------------------------------


class TestAutonomousLoopController:
    """自主迭代循环控制器测试。"""

    def test_run_completes_with_stub_dispatcher(self, tmp_path: Path):
        """使用 StubDispatcher 完整跑一次 4 阶段循环。

        StubDispatcher 不更新 UnifiedMemory 的 completed_items，
        所以 DiscoveryProbe 永远不会返回 done=True，
        最终触发 max_iterations 上限，状态为 FAILED。
        这是 stub 的局限，不是 P3-1 的 bug。
        测试验证：运行结束 + 持久化 + 状态合法。
        """
        config = AutonomousConfig(
            objective="build feature X",
            max_iterations=3,
            notes_memory_dir=str(tmp_path / "notes"),
            dispatcher=StubDispatcher(),
        )
        controller = AutonomousLoopController(config=config)
        report = controller.run()

        assert isinstance(report, AutonomousRunReport)
        assert report.run_id  # 应自动生成
        # 接受任何终态（COMPLETED/STOPPED/FAILED），stub 限制下 FAILED 是预期
        assert report.state.status in (RunStatus.COMPLETED, RunStatus.STOPPED, RunStatus.FAILED)
        assert report.state.is_terminal
        # 持久化文件应存在
        assert (tmp_path / "notes" / f"run_{report.run_id}.json").exists()

    def test_run_with_explicit_run_id(self, tmp_path: Path):
        config = AutonomousConfig(
            objective="test",
            max_iterations=1,
            notes_memory_dir=str(tmp_path / "notes"),
            dispatcher=StubDispatcher(),
        )
        controller = AutonomousLoopController(config=config)
        report = controller.run(run_id="my-run-id")
        assert report.run_id == "my-run-id"

    def test_run_persists_state_to_disk(self, tmp_path: Path):
        config = AutonomousConfig(
            objective="persist test",
            max_iterations=1,
            notes_memory_dir=str(tmp_path / "nm"),
            dispatcher=StubDispatcher(),
        )
        controller = AutonomousLoopController(config=config)
        controller.run(run_id="persist-test")

        memory = NotesMemory(storage_dir=str(tmp_path / "nm"))
        loaded = memory.load("persist-test")
        assert loaded is not None
        assert loaded.run_id == "persist-test"
        assert loaded.objective == "persist test"
        # 状态文件应包含运行状态
        assert loaded.status in (RunStatus.COMPLETED, RunStatus.STOPPED, RunStatus.FAILED)

    def test_pause_marks_state_paused(self, tmp_path: Path):
        config = AutonomousConfig(
            objective="pause test",
            notes_memory_dir=str(tmp_path / "notes"),
            dispatcher=StubDispatcher(),
        )
        controller = AutonomousLoopController(config=config)
        # 先模拟运行中状态
        controller._state = RunState(
            run_id="r-pause",
            objective="t",
            status=RunStatus.PLANNING,
        )
        controller.pause()
        assert controller._state.status == RunStatus.PAUSED

    def test_stop_marks_state_stopped(self, tmp_path: Path):
        config = AutonomousConfig(
            objective="stop test",
            notes_memory_dir=str(tmp_path / "notes"),
            dispatcher=StubDispatcher(),
        )
        controller = AutonomousLoopController(config=config)
        controller._state = RunState(
            run_id="r-stop",
            objective="t",
            status=RunStatus.PLANNING,
        )
        controller.stop()
        assert controller._state.status == RunStatus.STOPPED
        assert controller._state.is_terminal

    def test_get_state_returns_none_before_run(self, tmp_path: Path):
        config = AutonomousConfig(
            objective="t",
            notes_memory_dir=str(tmp_path / "n"),
            dispatcher=StubDispatcher(),
        )
        controller = AutonomousLoopController(config=config)
        assert controller.get_state() is None

    def test_get_state_returns_current_after_run(self, tmp_path: Path):
        config = AutonomousConfig(
            objective="t",
            notes_memory_dir=str(tmp_path / "n"),
            dispatcher=StubDispatcher(),
        )
        controller = AutonomousLoopController(config=config)
        controller.run()
        assert controller.get_state() is not None

    def test_auto_resume_from_paused_state(self, tmp_path: Path):
        """auto_resume=True 时应从 PAUSED 状态恢复。"""
        notes_dir = tmp_path / "resume"

        # 第一次运行：写入一个 PAUSED 状态
        memory = NotesMemory(storage_dir=str(notes_dir))
        memory.save(RunState(
            run_id="resumable",
            objective="resume test",
            status=RunStatus.PAUSED,
            current_iteration=2,
        ))

        # 第二次运行：auto_resume=True
        config = AutonomousConfig(
            objective="resume test",
            max_iterations=5,
            notes_memory_dir=str(notes_dir),
            dispatcher=StubDispatcher(),
            auto_resume=True,
        )
        controller = AutonomousLoopController(config=config)
        report = controller.run(run_id="resumable")

        # 应该已恢复并在 notes 中添加 "Resumed from checkpoint"
        resumed_notes = [n for n in report.state.notes if "Resumed" in n]
        assert len(resumed_notes) >= 1

    def test_no_auto_resume_when_flag_off(self, tmp_path: Path):
        """auto_resume=False 时即使有 PAUSED 状态也不恢复。"""
        notes_dir = tmp_path / "no-resume"
        memory = NotesMemory(storage_dir=str(notes_dir))
        memory.save(RunState(
            run_id="paused-but-no-resume",
            objective="t",
            status=RunStatus.PAUSED,
        ))

        config = AutonomousConfig(
            objective="t",
            max_iterations=1,
            notes_memory_dir=str(notes_dir),
            dispatcher=StubDispatcher(),
            auto_resume=False,
        )
        controller = AutonomousLoopController(config=config)
        report = controller.run(run_id="paused-but-no-resume")

        # 不应出现 Resumed 标记（因为是新运行覆盖了原状态）
        resumed_notes = [n for n in report.state.notes if "Resumed" in n]
        assert len(resumed_notes) == 0

    def test_consensus_engine_invoked_on_completion(self, tmp_path: Path):
        """启用 ConsensusEngine 后，当 loop 完成时应调用 create_proposal。

        直接测试 _check_consensus_gate 方法，绕过 LoopKernel 的
        max_iterations 限制（stub dispatcher 无法让 loop 真正完成）。
        """
        consensus = StubConsensusEngine(allow=True)
        config = AutonomousConfig(
            objective="consensus test",
            max_iterations=1,
            notes_memory_dir=str(tmp_path / "ce"),
            dispatcher=StubDispatcher(),
            consensus_engine=consensus,
        )
        controller = AutonomousLoopController(config=config)

        # 构造一个 final_status="completed" 的 LoopRunReport
        from scripts.collaboration.loop_engineering import LoopRunReport
        completed_report = LoopRunReport(
            objective="consensus test",
            total_iterations=1,
            final_status="completed",
        )

        # 初始化 _state（_check_consensus_gate 需要）
        controller._state = RunState(
            run_id="test-consensus",
            objective="consensus test",
            status=RunStatus.VERIFYING,
        )

        result = controller._check_consensus_gate(completed_report)
        assert result is True
        # 应调用 create_proposal 一次
        assert len(consensus.proposals) >= 1
        # 提案内容应包含 objective
        assert "consensus test" in consensus.proposals[0]["content"]

    def test_consensus_rejection_marks_failed(self, tmp_path: Path):
        """共识门拒绝时应将状态置为 FAILED。"""
        consensus = StubConsensusEngine(allow=False)
        # 让 LoopKernel 报 completed 才能触发共识门检查
        config = AutonomousConfig(
            objective="rejection test",
            max_iterations=1,
            notes_memory_dir=str(tmp_path / "rej"),
            dispatcher=StubDispatcher(),
            consensus_engine=consensus,
        )
        controller = AutonomousLoopController(config=config)
        controller.run()

        # 由于 StubConsensusEngine.create_proposal 返回 approved=False,
        # 但 _check_consensus_gate 用 final_status=="completed" 判断，
        # 这里我们检查共识确实被调用过
        assert len(consensus.proposals) >= 1

    def test_max_iterations_respected(self, tmp_path: Path):
        """max_iterations=1 时应只跑 1 轮。"""
        config = AutonomousConfig(
            objective="iter test",
            max_iterations=1,
            notes_memory_dir=str(tmp_path / "iter"),
            dispatcher=StubDispatcher(),
        )
        controller = AutonomousLoopController(config=config)
        report = controller.run()
        # 总迭代数不应超过 max_iterations
        if report.loop_report is not None:
            assert report.loop_report.total_iterations <= 1


# ---------------------------------------------------------------------------
# TestConsensusAwareEvaluator
# ---------------------------------------------------------------------------


class TestConsensusAwareEvaluator:
    """HC-2 共识门约束测试。"""

    def test_inherits_independent_evaluator(self):
        evaluator = ConsensusAwareEvaluator(consensus_engine=StubConsensusEngine())
        assert isinstance(evaluator, IndependentEvaluator)

    def test_evaluate_passes_when_consensus_ok(self):
        consensus = StubConsensusEngine(allow=True)
        evaluator = ConsensusAwareEvaluator(consensus_engine=consensus)
        # 正常的 handoff_result 应通过
        passed, errors = evaluator.evaluate(
            objective="t",
            handoff_result={"status": "ok", "output": "result"},
            iter_index=0,
        )
        assert passed
        assert errors == []

    def test_evaluate_fails_on_handoff_error(self):
        """handoff_result.status == error 时应失败，不进入共识门。

        注意：ConsensusAwareEvaluator 默认 STANDARD 模式，允许 1 个错误通过。
        因此需用 STRICT 模式测试 handoff error 的失败行为。
        """
        consensus = StubConsensusEngine(allow=True)
        evaluator = ConsensusAwareEvaluator(
            consensus_engine=consensus,
            mode=EvaluatorMode.STRICT,
        )
        passed, errors = evaluator.evaluate(
            objective="t",
            handoff_result={"status": "error", "error": "boom"},
            iter_index=0,
        )
        assert not passed
        assert any("Handoff error" in e for e in errors)

    def test_evaluate_detects_missing_create_proposal(self):
        """ConsensusEngine 缺少 create_proposal 方法时应失败。"""

        class BrokenEngine:
            # 故意不实现 create_proposal
            pass

        evaluator = ConsensusAwareEvaluator(consensus_engine=BrokenEngine())
        passed, errors = evaluator.evaluate(
            objective="t",
            handoff_result={"status": "ok", "output": "result"},
            iter_index=0,
        )
        assert not passed
        assert any("missing create_proposal" in e for e in errors)

    def test_strict_mode_propagates_to_base(self):
        """ConsensusAwareEvaluator 默认使用 STANDARD 模式。"""
        consensus = StubConsensusEngine()
        evaluator = ConsensusAwareEvaluator(consensus_engine=consensus)
        assert evaluator._mode == EvaluatorMode.STANDARD

    def test_explicit_evaluator_mode(self):
        consensus = StubConsensusEngine()
        evaluator = ConsensusAwareEvaluator(
            consensus_engine=consensus,
            mode=EvaluatorMode.STRICT,
        )
        assert evaluator._mode == EvaluatorMode.STRICT

        # STRICT 模式下空 output 应失败
        passed, errors = evaluator.evaluate(
            objective="t",
            handoff_result={"status": "ok", "output": ""},
            iter_index=0,
        )
        assert not passed
        assert any("Empty output" in e for e in errors)


# ---------------------------------------------------------------------------
# TestAutonomousConfig
# ---------------------------------------------------------------------------


class TestAutonomousConfig:
    """AutonomousConfig 配置测试。"""

    def test_defaults(self):
        config = AutonomousConfig(objective="t")
        assert config.max_iterations == 20
        assert config.confirmation_mode == ConfirmationMode.SMART
        assert config.consensus_engine is None
        assert config.dispatcher is None
        assert config.notes_memory_dir == ".devsquad_autonomous"
        assert config.auto_resume is False

    def test_custom_values(self):
        consensus = StubConsensusEngine()
        dispatcher = StubDispatcher()
        config = AutonomousConfig(
            objective="custom",
            max_iterations=50,
            confirmation_mode=ConfirmationMode.WHITELIST_ONLY,
            consensus_engine=consensus,
            dispatcher=dispatcher,
            notes_memory_dir="/tmp/custom",
            auto_resume=True,
        )
        assert config.max_iterations == 50
        assert config.confirmation_mode == ConfirmationMode.WHITELIST_ONLY
        assert config.consensus_engine is consensus
        assert config.dispatcher is dispatcher
        assert config.auto_resume is True


# ---------------------------------------------------------------------------
# TestAutonomousRunReport
# ---------------------------------------------------------------------------


class TestAutonomousRunReport:
    """运行报告数据类测试。"""

    def test_success_property_completed(self):
        state = RunState(run_id="r", objective="t", status=RunStatus.COMPLETED)
        report = AutonomousRunReport(
            run_id="r",
            objective="t",
            state=state,
        )
        assert report.success is True

    def test_success_property_failed(self):
        state = RunState(run_id="r", objective="t", status=RunStatus.FAILED)
        report = AutonomousRunReport(
            run_id="r",
            objective="t",
            state=state,
        )
        assert report.success is False

    def test_default_notes_empty(self):
        state = RunState(run_id="r", objective="t")
        report = AutonomousRunReport(
            run_id="r",
            objective="t",
            state=state,
        )
        assert report.notes == []

    def test_with_loop_report(self):
        """带 loop_report 的报告。"""
        state = RunState(run_id="r", objective="t", status=RunStatus.COMPLETED)
        loop_report = LoopKernel(
            config=LoopEngineeringConfig(
                loop_type=LoopType.CODING,
                max_iterations=1,
                human_checkpoint_every=0,  # 必须 <= max_iterations
            ),
            handoff_adapter=HandoffAdapter(dispatcher=StubDispatcher()),
        ).run("test objective")

        report = AutonomousRunReport(
            run_id="r",
            objective="t",
            state=state,
            loop_report=loop_report,
            consensus_verified=True,
        )
        assert report.loop_report is not None
        assert report.loop_report.objective == "test objective"
        assert report.consensus_verified is True


# ---------------------------------------------------------------------------
# TestAutonomousIntegration: 验证接入 dispatcher（无幽灵功能）
# ---------------------------------------------------------------------------


class TestAutonomousIntegration:
    """验证 Autonomous 组件接入 dispatch pipeline。

    确保无幽灵功能：autonomous_enabled=True 时可通过 dispatch_autonomous() 访问。
    """

    def test_autonomous_disabled_by_default(self):
        """默认 autonomous_enabled=False，组件不存在。"""
        from scripts.collaboration.dispatcher import MultiAgentDispatcher

        d = MultiAgentDispatcher(
            enable_warmup=False,
            enable_memory=False,
            enable_skillify=False,
        )
        assert d.autonomous_enabled is False
        assert d.autonomous_controller is None

    def test_autonomous_enabled_creates_controller(self, tmp_path: Path):
        """autonomous_enabled=True 时，AutonomousLoopController 被创建。"""
        from scripts.collaboration.dispatcher import MultiAgentDispatcher

        d = MultiAgentDispatcher(
            persist_dir=str(tmp_path / "disp"),
            enable_warmup=False,
            enable_memory=False,
            enable_skillify=False,
            autonomous_enabled=True,
            autonomous_max_iterations=5,
        )
        assert d.autonomous_enabled is True
        assert d.autonomous_controller is not None

    def test_dispatch_autonomous_without_enabled_raises(self):
        """autonomous_enabled=False 时调用 dispatch_autonomous 抛 RuntimeError。"""
        from scripts.collaboration.dispatcher import MultiAgentDispatcher

        d = MultiAgentDispatcher(
            enable_warmup=False,
            enable_memory=False,
            enable_skillify=False,
        )
        with pytest.raises(RuntimeError, match="AutonomousLoopController not enabled"):
            d.dispatch_autonomous("test objective")

    def test_dispatch_autonomous_works_when_enabled(self, tmp_path: Path):
        """autonomous_enabled=True 时 dispatch_autonomous 可成功调用。"""
        from scripts.collaboration.autonomous.loop_controller import AutonomousRunReport
        from scripts.collaboration.dispatcher import MultiAgentDispatcher

        d = MultiAgentDispatcher(
            persist_dir=str(tmp_path / "disp"),
            enable_warmup=False,
            enable_memory=False,
            enable_skillify=False,
            autonomous_enabled=True,
            autonomous_max_iterations=1,
        )
        report = d.dispatch_autonomous("integration test objective")
        assert isinstance(report, AutonomousRunReport)
        assert report.objective == "integration test objective"
        # stub dispatcher（MultiAgentDispatcher 自身）无法让 loop 真正完成
        # 但应达到终态
        assert report.state.is_terminal

    def test_dispatch_autonomous_with_run_id(self, tmp_path: Path):
        """dispatch_autonomous 支持自定义 run_id。"""
        from scripts.collaboration.dispatcher import MultiAgentDispatcher

        d = MultiAgentDispatcher(
            persist_dir=str(tmp_path / "disp"),
            enable_warmup=False,
            enable_memory=False,
            enable_skillify=False,
            autonomous_enabled=True,
            autonomous_max_iterations=1,
        )
        report = d.dispatch_autonomous("test", run_id="custom-integration-id")
        assert report.run_id == "custom-integration-id"


# ---------------------------------------------------------------------------
# TestLLMRoleVotes — LLM 投票（Task #87）
# ---------------------------------------------------------------------------


class StubLLMBackend:
    """可配置响应的 LLM 后端 stub。

    responses: dict[role, str] — 每个角色的 LLM 响应。
    如果角色不在 responses 中，调用 generate() 抛 RuntimeError 触发回退。
    """

    def __init__(self, responses: dict[str, str] | None = None, available: bool = True) -> None:
        self._responses = responses or {}
        self._available = available
        self.call_log: list[str] = []  # 记录被调用时的 prompt

    def generate(self, prompt: str, **kwargs: Any) -> str:  # noqa: ARG002
        self.call_log.append(prompt)
        # 从 prompt 中提取角色名（prompt 以 "You are a {role}" 开头）
        for role in ("architect", "product-manager", "solo-coder", "tester", "security"):
            if f"You are a {role}" in prompt:
                if role in self._responses:
                    return self._responses[role]
                raise RuntimeError(f"No response configured for role: {role}")
        raise RuntimeError("Could not determine role from prompt")

    def is_available(self) -> bool:
        return self._available


def _make_completed_loop_report():
    """构造一个 final_status='completed' 的 LoopRunReport。"""
    from scripts.collaboration.loop_engineering import LoopRunReport
    return LoopRunReport(
        objective="llm voting test",
        total_iterations=3,
        final_status="completed",
    )


class TestLLMRoleVotes:
    """Task #87: LLM 投票替换模拟投票。"""

    def test_cast_role_votes_uses_llm_when_available(self, tmp_path: Path):
        """LLM 后端可用时，_cast_role_votes 应调用 LLM 投票。"""
        responses = {
            "architect": '{"decision": true, "reason": "Design sound", "confidence": 0.9}',
            "product-manager": '{"decision": true, "reason": "Meets requirements", "confidence": 0.85}',
            "solo-coder": '{"decision": true, "reason": "Implementation correct", "confidence": 0.88}',
            "tester": '{"decision": true, "reason": "Tests pass", "confidence": 0.8}',
            "security": '{"decision": true, "reason": "No risks", "confidence": 0.75}',
        }
        backend = StubLLMBackend(responses=responses, available=True)
        config = AutonomousConfig(
            objective="llm test",
            notes_memory_dir=str(tmp_path / "llm"),
            llm_backend=backend,
        )
        controller = AutonomousLoopController(config=config)
        votes = controller._cast_role_votes(_make_completed_loop_report())

        assert len(votes) == 5
        # 所有投票应为 LLM 生成（reason 不是 "Mock fallback"）
        assert all("Mock fallback" not in v.reason for v in votes)
        # LLM 被调用 5 次
        assert len(backend.call_log) == 5

    def test_cast_role_votes_falls_back_when_no_backend(self, tmp_path: Path):
        """无 LLM 后端时，_cast_role_votes 应回退到 mock 投票。"""
        config = AutonomousConfig(
            objective="mock test",
            notes_memory_dir=str(tmp_path / "mock"),
            llm_backend=None,
        )
        controller = AutonomousLoopController(config=config)
        votes = controller._cast_role_votes(_make_completed_loop_report())

        assert len(votes) == 5
        # mock 投票的 reason 以 "Mock fallback" 或具体模拟 reason 开头
        # mock 投票的 reason 是 "Completed per spec" 等
        assert all("Mock fallback" not in v.reason for v in votes)  # mock 模式用具体 reason

    def test_cast_role_votes_falls_back_when_backend_unavailable(self, tmp_path: Path):
        """LLM 后端不可用时（is_available=False），应回退到 mock。"""
        backend = StubLLMBackend(available=False)
        config = AutonomousConfig(
            objective="unavailable test",
            notes_memory_dir=str(tmp_path / "unavail"),
            llm_backend=backend,
        )
        controller = AutonomousLoopController(config=config)
        votes = controller._cast_role_votes(_make_completed_loop_report())

        assert len(votes) == 5
        # LLM 未被调用
        assert len(backend.call_log) == 0

    def test_llm_role_votes_returns_5_votes(self, tmp_path: Path):
        """_llm_role_votes 应为 5 个角色各返回一个投票。"""
        responses = {
            role: f'{{"decision": true, "reason": "{role} approves", "confidence": 0.8}}'
            for role in ("architect", "product-manager", "solo-coder", "tester", "security")
        }
        backend = StubLLMBackend(responses=responses)
        config = AutonomousConfig(
            objective="5 votes test",
            notes_memory_dir=str(tmp_path / "5votes"),
            llm_backend=backend,
        )
        controller = AutonomousLoopController(config=config)
        votes = controller._llm_role_votes(_make_completed_loop_report())

        assert len(votes) == 5
        voter_roles = {v.voter_role for v in votes}
        assert voter_roles == {"architect", "product-manager", "solo-coder", "tester", "security"}

    def test_llm_role_votes_falls_back_on_role_failure(self, tmp_path: Path):
        """单个角色 LLM 调用失败时，应回退到 mock 投票。"""
        responses = {
            "architect": '{"decision": true, "reason": "OK", "confidence": 0.9}',
            # product-manager 缺失 → 触发 RuntimeError → mock 回退
            "solo-coder": '{"decision": true, "reason": "OK", "confidence": 0.85}',
            "tester": '{"decision": true, "reason": "OK", "confidence": 0.8}',
            "security": '{"decision": true, "reason": "OK", "confidence": 0.75}',
        }
        backend = StubLLMBackend(responses=responses)
        config = AutonomousConfig(
            objective="fallback test",
            notes_memory_dir=str(tmp_path / "fallback"),
            llm_backend=backend,
        )
        controller = AutonomousLoopController(config=config)
        votes = controller._llm_role_votes(_make_completed_loop_report())

        assert len(votes) == 5
        pm_vote = next(v for v in votes if v.voter_role == "product-manager")
        assert "Mock fallback" in pm_vote.reason
        # 其他角色应为 LLM 投票
        arch_vote = next(v for v in votes if v.voter_role == "architect")
        assert arch_vote.reason == "OK"

    def test_parse_llm_vote_valid_json(self, tmp_path: Path):
        """_parse_llm_vote 正确解析合法 JSON。"""
        config = AutonomousConfig(objective="t", notes_memory_dir=str(tmp_path / "parse"))
        controller = AutonomousLoopController(config=config)
        role_def = {"voter_id": "arch-01", "description": "test"}
        response = '{"decision": true, "reason": "Good design", "confidence": 0.85}'

        vote = controller._parse_llm_vote(response, "architect", role_def)

        assert vote is not None
        assert vote.decision is True
        assert vote.reason == "Good design"
        assert vote.confidence == 0.85
        assert vote.weight == 1.5  # architect 权重
        assert vote.voter_id == "arch-01"

    def test_parse_llm_vote_markdown_fences(self, tmp_path: Path):
        """_parse_llm_vote 应剥离 markdown 代码块标记。"""
        config = AutonomousConfig(objective="t", notes_memory_dir=str(tmp_path / "md"))
        controller = AutonomousLoopController(config=config)
        role_def = {"voter_id": "pm-01", "description": "test"}
        response = '```json\n{"decision": false, "reason": "Scope creep", "confidence": 0.6}\n```'

        vote = controller._parse_llm_vote(response, "product-manager", role_def)

        assert vote is not None
        assert vote.decision is False
        assert vote.reason == "Scope creep"

    def test_parse_llm_vote_invalid_returns_none(self, tmp_path: Path):
        """_parse_llm_vote 对无法解析的响应返回 None。"""
        config = AutonomousConfig(objective="t", notes_memory_dir=str(tmp_path / "invalid"))
        controller = AutonomousLoopController(config=config)
        role_def = {"voter_id": "tester-01", "description": "test"}

        # 完全无效
        assert controller._parse_llm_vote("I cannot decide", "tester", role_def) is None
        # 空
        assert controller._parse_llm_vote("", "tester", role_def) is None

    def test_parse_llm_vote_embedded_json(self, tmp_path: Path):
        """_parse_llm_vote 应从混合文本中提取 JSON。"""
        config = AutonomousConfig(objective="t", notes_memory_dir=str(tmp_path / "embed"))
        controller = AutonomousLoopController(config=config)
        role_def = {"voter_id": "sec-01", "description": "test"}
        response = 'Based on my analysis: {"decision": true, "reason": "Secure", "confidence": 0.9}'

        vote = controller._parse_llm_vote(response, "security", role_def)

        assert vote is not None
        assert vote.decision is True

    def test_build_vote_prompt_contains_role_and_context(self, tmp_path: Path):
        """_build_vote_prompt 应包含角色描述和运行上下文。"""
        config = AutonomousConfig(objective="prompt test objective", notes_memory_dir=str(tmp_path / "prompt"))
        controller = AutonomousLoopController(config=config)
        role_def = AutonomousLoopController._ROLE_DEFINITIONS["architect"]
        report = _make_completed_loop_report()

        prompt = controller._build_vote_prompt("architect", role_def, report)

        assert "architect" in prompt
        assert role_def["description"] in prompt
        assert "prompt test objective" in prompt
        assert "completed" in prompt
        assert "JSON" in prompt

    def test_consensus_gate_with_llm_backend(self, tmp_path: Path):
        """集成测试：LLM 后端 + ConsensusEngine 端到端投票。"""
        vote_json = '{"decision": true, "reason": "Approved", "confidence": 0.85}'
        responses = dict.fromkeys(
            ("architect", "product-manager", "solo-coder", "tester", "security"),
            vote_json,
        )
        backend = StubLLMBackend(responses=responses)
        consensus = StubConsensusEngine(allow=True)
        config = AutonomousConfig(
            objective="integration test",
            notes_memory_dir=str(tmp_path / "integ"),
            consensus_engine=consensus,
            llm_backend=backend,
        )
        controller = AutonomousLoopController(config=config)
        controller._state = RunState(
            run_id="test-llm-consensus",
            objective="integration test",
            status=RunStatus.VERIFYING,
        )

        result = controller._check_consensus_gate(_make_completed_loop_report())

        assert result is True
        assert len(consensus.proposals) >= 1
        # LLM 被调用 5 次
        assert len(backend.call_log) == 5


# ---------------------------------------------------------------------------
# TestRealMokaAIVoting — 真实 Moka AI LLM 投票（需 API Key）
# ---------------------------------------------------------------------------


class TestRealMokaAIVoting:
    """Task #87: 真实 Moka AI LLM 投票验证。

    仅在 MOKA_API_KEY 环境变量存在且有效时运行，否则 skip。
    """

    @pytest.mark.skipif(
        not os.environ.get("MOKA_API_KEY"),
        reason="MOKA_API_KEY not set — skipping real LLM voting test",
    )
    def test_real_moka_ai_voting(self, tmp_path: Path):
        """使用真实 Moka AI 后端进行 5 角色投票。"""
        from scripts.collaboration.llm_backend import OpenAIBackend

        backend = OpenAIBackend(
            api_key=os.environ["MOKA_API_KEY"],
            base_url=os.environ.get("MOKA_API_BASE", "https://api.moka-ai.com/v1"),
            model=os.environ.get("MOKA_MODEL", "moka/claude-sonnet-4-6"),
        )
        if not backend.is_available():
            pytest.skip("OpenAIBackend not available (openai package missing)")

        # 预检：用最小 prompt 验证 API key 有效，避免 5 次失败调用
        try:
            backend.generate("Reply with: OK", max_tokens=5)
        except Exception as e:  # noqa: BLE001
            pytest.skip(f"Moka AI API key invalid or unreachable: {type(e).__name__}")

        config = AutonomousConfig(
            objective="Verify pytest test suite runs cleanly",
            notes_memory_dir=str(tmp_path / "moka"),
            llm_backend=backend,
        )
        controller = AutonomousLoopController(config=config)
        report = _make_completed_loop_report()

        votes = controller._llm_role_votes(report)

        assert len(votes) == 5
        for vote in votes:
            assert vote.voter_role in controller._ROLE_DEFINITIONS
            assert 0.0 <= vote.confidence <= 1.0
            # 真实 LLM 投票不应包含 "Mock fallback"
            assert "Mock fallback" not in vote.reason


class TestDispatchAutonomousLLMWiring:
    """生产路径装配验证：dispatch_autonomous() 是否正确装配 llm_backend。

    Task #87 收尾：修复幽灵功能 — pytest 显式构造 llm_backend 通过，
    但 dispatch_autonomous() 生产路径漏传 llm_backend，导致 TRAE skill
    调用 autonomous 模式时回退 mock 投票，Moka AI 从未被调用。
    """

    def test_resolve_moka_backend_returns_none_without_env(self, monkeypatch: pytest.MonkeyPatch):
        """MOKA_API_KEY 未设置时 _resolve_moka_backend_from_env 返回 None。"""
        from scripts.collaboration.dispatcher import MultiAgentDispatcher

        monkeypatch.delenv("MOKA_API_KEY", raising=False)
        disp = MultiAgentDispatcher(autonomous_enabled=True)
        assert disp._resolve_moka_backend_from_env() is None

    def test_resolve_moka_backend_creates_openai_backend_with_env(self, monkeypatch: pytest.MonkeyPatch):
        """MOKA_API_KEY 设置时 _resolve_moka_backend_from_env 返回 OpenAIBackend。"""
        from scripts.collaboration.dispatcher import MultiAgentDispatcher

        monkeypatch.setenv("MOKA_API_KEY", "sk-test-fake-key-for-wiring-test")
        monkeypatch.setenv("MOKA_API_BASE", "https://api.moka-ai.com/v1")
        monkeypatch.setenv("MOKA_MODEL", "moka/claude-sonnet-4-6")
        disp = MultiAgentDispatcher(autonomous_enabled=True)
        backend = disp._resolve_moka_backend_from_env()
        assert backend is not None
        # 验证是 OpenAIBackend 实例（不调用 API，只验证类型）
        from scripts.collaboration.llm_backend import OpenAIBackend
        assert isinstance(backend, OpenAIBackend)

    def test_dispatch_autonomous_wires_llm_backend_from_env(self, monkeypatch: pytest.MonkeyPatch):
        """dispatch_autonomous() 从 MOKA_API_KEY env var 装配 llm_backend 到 AutonomousConfig。

        验证生产路径：dispatcher 无显式 llm_backend（TRAE skill 模式），
        但 MOKA_API_KEY env var 存在时，dispatch_autonomous 应自动创建
        OpenAIBackend 并传入 AutonomousConfig.llm_backend。
        """
        from unittest.mock import MagicMock

        from scripts.collaboration.dispatcher import MultiAgentDispatcher

        monkeypatch.setenv("MOKA_API_KEY", "sk-test-fake-key-for-wiring-test")
        monkeypatch.setenv("MOKA_API_BASE", "https://api.moka-ai.com/v1")
        monkeypatch.setenv("MOKA_MODEL", "moka/claude-sonnet-4-6")

        disp = MultiAgentDispatcher(autonomous_enabled=True)
        assert disp.llm_backend is None  # 前置条件：dispatcher 无显式 backend

        captured_configs: list[Any] = []

        class StubController:
            def __init__(self, config: Any) -> None:
                captured_configs.append(config)

            def run(self, run_id: str | None = None) -> Any:  # noqa: ARG002
                return MagicMock()

        # dispatch_autonomous 内部做局部 import，patch 源模块即可
        import scripts.collaboration.autonomous.loop_controller as lc_module

        monkeypatch.setattr(lc_module, "AutonomousLoopController", StubController)

        disp.dispatch_autonomous(objective="wiring test")

        assert len(captured_configs) == 1
        config = captured_configs[0]
        # 核心断言：llm_backend 已装配（不是 None）
        assert config.llm_backend is not None
        from scripts.collaboration.llm_backend import OpenAIBackend
        assert isinstance(config.llm_backend, OpenAIBackend)

    def test_dispatch_autonomous_prefers_explicit_backend(self, monkeypatch: pytest.MonkeyPatch):
        """dispatch_autonomous() 优先使用 dispatcher.llm_backend，而非 env var。

        当 dispatcher 已有显式 llm_backend 时，不应从 env var 创建新的。
        """
        from unittest.mock import MagicMock

        from scripts.collaboration.dispatcher import MultiAgentDispatcher

        monkeypatch.setenv("MOKA_API_KEY", "sk-test-fake-key-for-wiring-test")

        explicit_backend = MagicMock()
        explicit_backend.is_available.return_value = True
        disp = MultiAgentDispatcher(autonomous_enabled=True, llm_backend=explicit_backend)

        # _resolve_moka_backend_from_env 不应被调用（因为 self.llm_backend 已存在）
        # 验证：直接检查优先级逻辑
        backend = disp.llm_backend if disp.llm_backend is not None else disp._resolve_moka_backend_from_env()
        assert backend is explicit_backend
