"""自主迭代循环控制器：4 阶段 plan→dev→verify→fix。

复用 P1-1 的 LoopKernel 实现循环逻辑，不重复造轮子（架构师共识）。
与 ConsensusEngine 协调：不绕过共识门 HC-2。

4 阶段映射到 LoopKernel：
- plan = Discovery (发现本轮该做什么)
- dev = Handoff (派发工作)
- verify = Verification + ConsensusEngine 共识门
- fix = Scheduling decision FIX → 下一轮 Discovery
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from ..loop_engineering import (
    HandoffAdapter,
    IndependentEvaluator,
    LoopEngineeringConfig,
    LoopKernel,
    LoopRunReport,
    LoopType,
)
from .notes_memory import NotesMemory
from .run_state import RunState, RunStatus
from .sleep_guard import SleepGuard, SleepGuardConfig
from .smart_confirmation import ConfirmationMode, SmartConfirmation

logger = logging.getLogger(__name__)


@dataclass
class AutonomousConfig:
    """自主迭代配置。"""

    objective: str
    max_iterations: int = 20
    confirmation_mode: ConfirmationMode = ConfirmationMode.SMART
    consensus_engine: Any = None  # ConsensusEngine | None
    dispatcher: Any = None  # MultiAgentDispatcher | None
    notes_memory_dir: str = ".devsquad_autonomous"
    auto_resume: bool = False  # 是否自动从断点续跑
    sleep_guard_config: SleepGuardConfig | None = None  # None=禁用 SleepGuard
    llm_backend: Any = None  # LLMBackend | None; None=回退到 mock 投票


@dataclass
class AutonomousRunReport:
    """自主迭代运行报告。"""

    run_id: str
    objective: str
    state: RunState
    loop_report: LoopRunReport | None = None
    consensus_verified: bool = False
    notes: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """是否成功完成。"""
        return self.state.status == RunStatus.COMPLETED


class AutonomousLoopController:
    """自主迭代循环控制器。

    4 阶段循环：plan → dev → verify → fix
    复用 LoopKernel 的 5 步闭环，叠加共识门和断点续跑。

    Usage:
        controller = AutonomousLoopController(config=config)
        report = controller.run()
        if report.success:
            print("Iteration completed successfully")
    """

    def __init__(self, config: AutonomousConfig) -> None:
        self._config = config
        self._confirmer = SmartConfirmation(mode=config.confirmation_mode)
        self._memory = NotesMemory(storage_dir=config.notes_memory_dir)
        self._state: RunState | None = None
        self._sleep_guard: SleepGuard | None = None
        if config.sleep_guard_config is not None:
            self._sleep_guard = SleepGuard(config=config.sleep_guard_config)

    def run(self, run_id: str | None = None) -> AutonomousRunReport:
        """启动自主迭代。

        Args:
            run_id: 可选的运行 ID。若提供且 auto_resume=True，尝试从断点续跑。

        Returns:
            AutonomousRunReport 包含运行状态和 LoopKernel 报告。
        """
        # 断点续跑
        if run_id and self._config.auto_resume:
            existing = self._memory.load(run_id)
            if existing and existing.can_resume:
                self._state = existing
                self._state.add_note("Resumed from checkpoint")
                logger.info("Resumed run %s from iteration %d", run_id, existing.current_iteration)

        # 新建运行
        if self._state is None:
            self._state = RunState(
                run_id=run_id or f"auto-{uuid4().hex[:8]}",
                objective=self._config.objective,
                max_iterations=self._config.max_iterations,
            )

        self._state.update_status(RunStatus.PLANNING)
        self._memory.save(self._state)

        if self._sleep_guard is not None and self._sleep_guard.should_stop():
            self._state.update_status(RunStatus.FAILED)
            self._state.error = "SleepGuard hard stop: too many consecutive failures"
            self._memory.save(self._state)
            return AutonomousRunReport(
                run_id=self._state.run_id,
                objective=self._config.objective,
                state=self._state,
                consensus_verified=False,
                notes=self._state.notes,
            )

        if self._sleep_guard is not None:
            self._sleep_guard.maybe_sleep()

        try:
            # 复用 LoopKernel 执行 4 阶段循环
            loop_report = self._run_loop_kernel()
            self._state.loop_report = loop_report

            # 共识门检查
            if self._config.consensus_engine is not None:
                consensus_passed = self._check_consensus_gate(loop_report)
                if not consensus_passed:
                    self._state.update_status(RunStatus.FAILED)
                    self._state.error = "Consensus gate rejected the result"
                    self._memory.save(self._state)
                    return AutonomousRunReport(
                        run_id=self._state.run_id,
                        objective=self._config.objective,
                        state=self._state,
                        loop_report=loop_report,
                        consensus_verified=False,
                        notes=self._state.notes,
                    )

            # 根据循环结果更新状态
            if loop_report.final_status == "completed":
                self._state.update_status(RunStatus.COMPLETED)
                self._state.mark_phase_completed("plan")
                self._state.mark_phase_completed("dev")
                self._state.mark_phase_completed("verify")
                if self._sleep_guard is not None:
                    self._sleep_guard.record_success()
            elif loop_report.final_status == "stopped":
                self._state.update_status(RunStatus.STOPPED)
                if self._sleep_guard is not None:
                    self._sleep_guard.record_failure()
            else:
                self._state.update_status(RunStatus.FAILED)
                self._state.error = loop_report.error or "Loop failed"
                if self._sleep_guard is not None:
                    self._sleep_guard.record_failure()

            self._memory.save(self._state)

            return AutonomousRunReport(
                run_id=self._state.run_id,
                objective=self._config.objective,
                state=self._state,
                loop_report=loop_report,
                consensus_verified=self._config.consensus_engine is not None,
                notes=self._state.notes,
            )

        except Exception as e:
            self._state.update_status(RunStatus.FAILED)
            self._state.error = str(e)
            self._memory.save(self._state)
            if self._sleep_guard is not None:
                self._sleep_guard.record_failure()
            logger.exception("Autonomous run failed")
            return AutonomousRunReport(
                run_id=self._state.run_id,
                objective=self._config.objective,
                state=self._state,
                consensus_verified=False,
                notes=self._state.notes,
            )

    def pause(self) -> None:
        """暂停运行（可后续恢复）。"""
        if self._state and self._state.is_running:
            self._state.update_status(RunStatus.PAUSED)
            self._memory.save(self._state)

    def stop(self) -> None:
        """停止运行。"""
        if self._state:
            self._state.update_status(RunStatus.STOPPED)
            self._memory.save(self._state)

    def get_state(self) -> RunState | None:
        """获取当前运行状态。"""
        return self._state

    def get_sleep_guard_stats(self) -> Any:
        """获取 SleepGuard 统计（若启用）。"""
        if self._sleep_guard is None:
            return None
        return self._sleep_guard.stats

    def _run_loop_kernel(self) -> LoopRunReport:
        """复用 LoopKernel 执行 4 阶段循环。"""
        loop_config = LoopEngineeringConfig(
            loop_type=LoopType.CODING,
            max_iterations=self._config.max_iterations,
            human_checkpoint_every=0,  # 自主模式不触发人类检查点
        )

        # 注入 dispatcher 到 HandoffAdapter（若有）
        handoff = HandoffAdapter(dispatcher=self._config.dispatcher)

        # 注入共识引擎到 Evaluator（若有）
        evaluator = IndependentEvaluator()
        if self._config.consensus_engine is not None:
            evaluator = ConsensusAwareEvaluator(
                consensus_engine=self._config.consensus_engine,
            )

        kernel = LoopKernel(
            config=loop_config,
            handoff_adapter=handoff,
            evaluator=evaluator,
            memory=self._memory.wrap_for_loop(),
        )

        return kernel.run(self._config.objective)

    def _check_consensus_gate(self, loop_report: LoopRunReport) -> bool:
        """共识门检查（HC-2: 不绕过共识门）。

        关键约束：自主模式不绕过 ConsensusEngine 前置共识门。
        实现真实多角色投票：创建提案→5 角色投票→reach_consensus→根据 outcome 返回。
        LLM 后端可用时调用真实 LLM 投票，否则回退到 mock 投票。
        """
        if self._config.consensus_engine is None:
            return True  # 无共识引擎，跳过

        try:
            proposal_content = (
                f"Autonomous run: {self._config.objective}\n"
                f"Status: {loop_report.final_status}\n"
                f"Iterations: {loop_report.total_iterations}\n"
                f"Objective: {self._config.objective}"
            )
            proposal = self._config.consensus_engine.create_proposal(
                topic=f"Autonomous run {self._state.run_id}",
                proposer_id="autonomous-controller",
                content=proposal_content,
            )

            votes = self._cast_role_votes(loop_report)
            for vote in votes:
                self._config.consensus_engine.cast_vote(proposal.proposal_id, vote)

            record = self._config.consensus_engine.reach_consensus(proposal.proposal_id)
            logger.info(
                "Consensus gate: outcome=%s, for=%d, against=%d",
                record.outcome, record.votes_for, record.votes_against,
            )
            return record.outcome.value == "approved"
        except (AttributeError, RuntimeError, ValueError) as e:
            logger.warning("Consensus gate check failed: %s", e)
            return False

    def _cast_role_votes(self, loop_report: LoopRunReport) -> list[Any]:
        """分发角色投票：LLM 可用时调用真实 LLM，否则回退 mock。"""
        if self._config.llm_backend is not None and self._config.llm_backend.is_available():
            votes = self._llm_role_votes(loop_report)
            if votes:
                return votes
            logger.warning("LLM voting returned empty, falling back to mock.")
        return self._simulate_role_votes(loop_report)

    # ---- LLM 投票 ----

    _ROLE_DEFINITIONS: dict[str, dict[str, str]] = {
        "architect": {
            "voter_id": "arch-01",
            "description": "Focus on design quality, architectural soundness, and technical feasibility.",
        },
        "product-manager": {
            "voter_id": "pm-01",
            "description": "Focus on requirements coverage, user value, and scope alignment.",
        },
        "solo-coder": {
            "voter_id": "coder-01",
            "description": "Focus on implementation correctness, code quality, and completeness.",
        },
        "tester": {
            "voter_id": "tester-01",
            "description": "Focus on verification coverage, test results, and edge cases.",
        },
        "security": {
            "voter_id": "sec-01",
            "description": "Focus on security risks, vulnerability exposure, and data safety.",
        },
    }

    _ROLE_WEIGHTS: dict[str, float] = {
        "architect": 1.5,
        "product-manager": 1.2,
        "solo-coder": 1.0,
        "tester": 1.0,
        "security": 1.0,
    }

    def _build_vote_prompt(self, role: str, role_def: dict[str, str], loop_report: LoopRunReport) -> str:
        """为指定角色构造 LLM 投票 prompt。"""
        errors = getattr(loop_report, "errors", []) or []
        errors_text = "\n".join(f"- {e}" for e in errors[:5]) if errors else "(none)"
        return (
            f"You are a {role} on a multi-role AI team evaluating an autonomous run.\n\n"
            f"## Run Context\n"
            f"Objective: {self._config.objective}\n"
            f"Final Status: {loop_report.final_status}\n"
            f"Total Iterations: {loop_report.total_iterations}\n"
            f"Errors:\n{errors_text}\n\n"
            f"## Your Role: {role}\n"
            f"{role_def['description']}\n\n"
            f"## Vote Instructions\n"
            f"Based on your role's perspective, decide if this autonomous run should be approved.\n"
            f"Respond ONLY with JSON (no markdown fences, no extra text):\n"
            f'{{"decision": true_or_false, "reason": "one sentence", "confidence": 0.0_to_1.0}}'
        )

    def _parse_llm_vote(self, response: str, role: str, role_def: dict[str, str]) -> Any | None:
        """解析 LLM 返回的 JSON 投票，失败返回 None。"""
        import json
        import re

        text = response.strip()
        # 移除可能的 markdown fences
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # 尝试提取第一个 JSON 对象
            match = re.search(r"\{[^{}]*\}", text)
            if not match:
                return None
            try:
                data = json.loads(match.group(0))
            except json.JSONDecodeError:
                return None

        from ..models_base import Vote

        decision = bool(data.get("decision", False))
        reason = str(data.get("reason", "LLM vote"))[:200]
        confidence = float(data.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))

        return Vote(
            voter_id=role_def["voter_id"],
            voter_role=role,
            decision=decision,
            reason=reason,
            weight=self._ROLE_WEIGHTS[role],
            confidence=confidence,
        )

    def _llm_role_votes(self, loop_report: LoopRunReport) -> list[Any]:
        """调用 LLM 为 5 个角色分别投票。单个角色失败时回退到 mock 投票。"""
        votes: list[Any] = []
        for role, role_def in self._ROLE_DEFINITIONS.items():
            prompt = self._build_vote_prompt(role, role_def, loop_report)
            try:
                response = self._config.llm_backend.generate(
                    prompt, temperature=0.3, max_tokens=200,
                )
                vote = self._parse_llm_vote(response, role, role_def)
                if vote is not None:
                    votes.append(vote)
                    continue
            except Exception as e:  # noqa: BLE001 — LLM 后端可能抛各种异常，全部回退到 mock
                logger.warning("LLM vote for %s failed: %s — using mock fallback.", role, e)

            # 单角色回退到 mock
            votes.extend(self._mock_single_role_vote(role, role_def, loop_report))
        return votes

    @staticmethod
    def _mock_single_role_vote(role: str, role_def: dict[str, str], loop_report: LoopRunReport) -> list[Any]:
        """单角色 mock 投票回退（LLM 失败时使用）。"""
        from ..models_base import Vote

        status = loop_report.final_status
        if status == "completed":
            decision, reason, confidence = True, "Mock fallback: completed", 0.75
        elif status == "failed":
            decision, reason, confidence = False, "Mock fallback: failed", 0.75
        else:
            decision, reason, confidence = False, "Mock fallback: stopped", 0.5

        weights = AutonomousLoopController._ROLE_WEIGHTS
        return [
            Vote(
                voter_id=role_def["voter_id"],
                voter_role=role,
                decision=decision,
                reason=reason,
                weight=weights[role],
                confidence=confidence,
            )
        ]

    @staticmethod
    def _simulate_role_votes(loop_report: LoopRunReport) -> list[Any]:
        """模拟 5 角色基于 loop_report 状态的投票（占位实现，Task #87 替换为 LLM 投票）。

        投票逻辑：
        - completed: 全员赞成（tester/security 中等信心）
        - failed: 全员反对（coder 可能部分赞成）
        - stopped: 分裂投票（architect/pm 赞成部分进展，tester 反对）
        """
        from ..models_base import Vote

        # 角色权重表（architect=1.5, pm=1.2, 其余=1.0）
        role_weights = {
            "architect": 1.5,
            "product-manager": 1.2,
            "solo-coder": 1.0,
            "tester": 1.0,
            "security": 1.0,
        }

        # 按状态定义各角色的 (decision, reason, confidence)
        status = loop_report.final_status
        vote_matrix: dict[str, list[tuple[str, str, bool, str, float]]] = {
            "completed": [
                ("arch-01", "architect", True, "Completed per spec", 0.85),
                ("pm-01", "product-manager", True, "Meets requirements", 0.80),
                ("coder-01", "solo-coder", True, "Implementation done", 0.90),
                ("tester-01", "tester", True, "Verification passed", 0.75),
                ("sec-01", "security", True, "No security concerns", 0.70),
            ],
            "failed": [
                ("arch-01", "architect", False, "Failed to meet objective", 0.80),
                ("pm-01", "product-manager", False, "Requirements not met", 0.80),
                ("coder-01", "solo-coder", False, "Implementation failed", 0.85),
                ("tester-01", "tester", False, "Verification failed", 0.90),
                ("sec-01", "security", False, "Cannot verify security", 0.75),
            ],
            "stopped": [
                ("arch-01", "architect", True, "Partial progress useful", 0.60),
                ("pm-01", "product-manager", True, "Some value delivered", 0.55),
                ("coder-01", "solo-coder", False, "Hit iteration limit", 0.70),
                ("tester-01", "tester", False, "Not fully verified", 0.80),
                ("sec-01", "security", False, "Incomplete security review", 0.65),
            ],
        }

        rows = vote_matrix.get(status, vote_matrix["stopped"])
        return [
            Vote(
                voter_id=vid,
                voter_role=role,
                decision=decision,
                reason=reason,
                weight=role_weights[role],
                confidence=confidence,
            )
            for vid, role, decision, reason, confidence in rows
        ]


class ConsensusAwareEvaluator(IndependentEvaluator):
    """整合共识引擎的 Evaluator。

    在独立评估后叠加共识门检查，确保自主模式不绕过共识门（HC-2）。
    """

    def __init__(self, consensus_engine: Any, mode: Any = None) -> None:
        from ..loop_engineering.models import EvaluatorMode

        super().__init__(mode=mode or EvaluatorMode.STANDARD)
        self._consensus_engine = consensus_engine

    def evaluate(self, objective: str, handoff_result: dict, iter_index: int) -> tuple[bool, list[str]]:
        """独立评估 + ConsensusEngine 连通性验证。

        注意：完整的共识投票在 AutonomousLoopController._check_consensus_gate
        中执行（循环结束后）。此处仅验证 ConsensusEngine 可访问，确保
        自主模式不会因引擎不可用而静默绕过 HC-2。
        """
        passed, errors = super().evaluate(objective, handoff_result, iter_index)

        if not passed:
            return passed, errors

        if self._consensus_engine is not None:
            try:
                if not hasattr(self._consensus_engine, "create_proposal"):
                    errors.append("ConsensusEngine missing create_proposal method")
                    return False, errors
                if not hasattr(self._consensus_engine, "cast_vote"):
                    errors.append("ConsensusEngine missing cast_vote method")
                    return False, errors
                if not hasattr(self._consensus_engine, "reach_consensus"):
                    errors.append("ConsensusEngine missing reach_consensus method")
                    return False, errors
            except (AttributeError, RuntimeError) as e:
                errors.append(f"ConsensusEngine connectivity check failed: {e}")
                return False, errors

        return passed, errors


__all__ = [
    "AutonomousConfig",
    "AutonomousLoopController",
    "AutonomousRunReport",
    "ConsensusAwareEvaluator",
]
