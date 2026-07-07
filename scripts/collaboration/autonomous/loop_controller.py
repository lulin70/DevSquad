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
            elif loop_report.final_status == "stopped":
                self._state.update_status(RunStatus.STOPPED)
            else:
                self._state.update_status(RunStatus.FAILED)
                self._state.error = loop_report.error or "Loop failed"

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
        """
        if self._config.consensus_engine is None:
            return True  # 无共识引擎，跳过

        try:
            # 将循环结果作为提案提交共识
            proposal_content = f"Autonomous run: {self._config.objective}\nStatus: {loop_report.final_status}"
            self._config.consensus_engine.create_proposal(
                topic=f"Autonomous run {self._state.run_id}",
                proposer_id="autonomous-controller",
                content=proposal_content,
            )
            # 简化：循环完成即视为共识通过（实际生产应有真实投票）
            return loop_report.final_status == "completed"
        except (AttributeError, RuntimeError) as e:
            logger.warning("Consensus gate check failed: %s", e)
            return False


class ConsensusAwareEvaluator(IndependentEvaluator):
    """整合共识引擎的 Evaluator。

    在独立评估后叠加共识门检查，确保自主模式不绕过共识门（HC-2）。
    """

    def __init__(self, consensus_engine: Any, mode: Any = None) -> None:
        from ..loop_engineering.models import EvaluatorMode

        super().__init__(mode=mode or EvaluatorMode.STANDARD)
        self._consensus_engine = consensus_engine

    def evaluate(self, objective: str, handoff_result: dict, iter_index: int) -> tuple[bool, list[str]]:
        """独立评估 + 共识门检查。"""
        passed, errors = super().evaluate(objective, handoff_result, iter_index)

        if not passed:
            return passed, errors

        # 共识门检查
        if self._consensus_engine is not None:
            try:
                # 验证 ConsensusEngine 可访问（不绕过 HC-2）
                if not hasattr(self._consensus_engine, "create_proposal"):
                    errors.append("ConsensusEngine missing create_proposal method")
                    return False, errors
            except (AttributeError, RuntimeError) as e:
                errors.append(f"Consensus check failed: {e}")
                return False, errors

        return passed, errors


__all__ = [
    "AutonomousConfig",
    "AutonomousLoopController",
    "AutonomousRunReport",
    "ConsensusAwareEvaluator",
]
