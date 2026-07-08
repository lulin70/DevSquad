"""V4.0.0 P3-1: Autonomous 自主迭代模式。

借鉴 TraeMultiAgentSkill 的 autonomous/ 理念，但复用 P1-1 的 LoopKernel：
- 4 阶段循环: plan → dev → verify → fix
- 断点续跑 (SHA256 校验 + 备份恢复)
- 智能确认三态 (smart/whitelist-only/blacklist-only)
- 自动 git 操作
- 与 ConsensusEngine 协调（不绕过共识门 HC-2）
- SleepGuard 防止无限循环（指数退避 + 硬停止）

6 组件（架构师共识：精简自 9 组件）：
- loop_controller: 4 阶段循环控制（复用 LoopKernel）
- run_state: 运行状态管理
- notes_memory: 断点续跑记忆
- smart_confirmation: 智能确认三态决策
- git_driver: 自动 git 操作
- sleep_guard: 无限循环防护（指数退避 + 硬停止）
"""

from .git_driver import GitDriver
from .loop_controller import AutonomousLoopController
from .notes_memory import NotesMemory
from .run_state import RunState, RunStatus
from .sleep_guard import GuardState, SleepGuard, SleepGuardConfig, SleepGuardStats
from .smart_confirmation import ConfirmationDecision, SmartConfirmation

__all__ = [
    "AutonomousLoopController",
    "ConfirmationDecision",
    "GitDriver",
    "GuardState",
    "NotesMemory",
    "RunState",
    "RunStatus",
    "SleepGuard",
    "SleepGuardConfig",
    "SleepGuardStats",
    "SmartConfirmation",
]
