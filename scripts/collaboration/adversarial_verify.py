"""V4.0.0 P2-1: Dynamic Workflows 对抗验证。

红蓝对抗验证模式：
- 红方（挑战者）：生成反例、边界 case、目标偏移检测
- 蓝方（防御者）：响应挑战，加固方案
- 裁判：评估胜负，输出改进建议

三大痛点应对：
| 痛点 | DevSquad 现有 | 对抗验证增强 |
|------|-------------|-------------|
| Agentic Laziness | TokenBudget | 红方强制挑战完整性 |
| Self-preferential Bias | 三贤者投票 | 独立红方外部视角 |
| Goal Drift | AnchorChecker | 红方检测目标偏移 |

默认实现使用启发式规则（无 LLM 依赖）。可通过依赖注入替换为 LLM 驱动的实现。
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================
# 数据模型
# ============================================================


@dataclass
class AdversarialChallenge:
    """红方挑战。"""

    challenge_id: str
    challenge_type: str  # "counterexample" | "edge_case" | "goal_drift" | "incompleteness" | "bias"
    description: str
    severity: str  # "critical" | "warning" | "info"
    counterexample: str | None = None


@dataclass
class AdversarialDefense:
    """蓝方防御。"""

    challenge_id: str
    response: str
    mitigation: str | None = None
    conceded: bool = False


@dataclass
class AdversarialVerdict:
    """裁判裁决。"""

    winner: str  # "red" | "blue" | "draw"
    confidence: float  # 0.0 ~ 1.0
    improvements: list[str] = field(default_factory=list)
    reasoning: str = ""


@dataclass
class AdversarialResult:
    """对抗验证最终结果。"""

    proposal: str
    challenges: list[AdversarialChallenge]
    defenses: list[AdversarialDefense]
    verdict: AdversarialVerdict

    @property
    def passed(self) -> bool:
        """是否通过对抗验证（非红方获胜）。"""
        return self.verdict.winner != "red"

    @property
    def critical_challenges_unresolved(self) -> int:
        """未解决的关键挑战数。"""
        conceded_ids = {d.challenge_id for d in self.defenses if d.conceded}
        return sum(
            1 for c in self.challenges
            if c.severity == "critical" and c.challenge_id in conceded_ids
        )


# ============================================================
# 红方 / 蓝方 / 裁判
# ============================================================


class RedTeam:
    """红方：生成反例和边界 case。

    默认使用启发式规则检测 5 类问题：
    - counterexample: 反例（输入边界）
    - edge_case: 边界 case（并发/超时/资源耗尽）
    - goal_drift: 目标偏移
    - incompleteness: 完整性缺失（错误处理/边界条件）
    - bias: 自我偏好偏差（过度工程/偏好特定方案）
    """

    def __init__(self, challenge_generator: Callable[[str], list[AdversarialChallenge]] | None = None) -> None:
        self._generator = challenge_generator

    def generate_challenges(self, proposal: str) -> list[AdversarialChallenge]:
        if self._generator is not None:
            return self._generator(proposal)
        return self._heuristic_challenges(proposal)

    def _heuristic_challenges(self, proposal: str) -> list[AdversarialChallenge]:
        challenges: list[AdversarialChallenge] = []
        prop_lower = proposal.lower()

        # 1. 反例：输入边界
        challenges.append(AdversarialChallenge(
            challenge_id=self._make_id(proposal, "counterexample"),
            challenge_type="counterexample",
            description="What happens with empty/null/invalid input?",
            severity="critical",
            counterexample="Empty input, None value, malformed data",
        ))

        # 2. 边界 case：并发
        if any(kw in prop_lower for kw in ["api", "service", "endpoint", "server", "request"]):
            challenges.append(AdversarialChallenge(
                challenge_id=self._make_id(proposal, "edge_case_concurrent"),
                challenge_type="edge_case",
                description="How does this handle concurrent access and race conditions?",
                severity="warning",
                counterexample="Two requests modifying same resource simultaneously",
            ))

        # 3. 目标偏移
        if len(proposal) > 200 or any(kw in prop_lower for kw in ["also", "additionally", "furthermore"]):
            challenges.append(AdversarialChallenge(
                challenge_id=self._make_id(proposal, "goal_drift"),
                challenge_type="goal_drift",
                description="Proposal may contain scope creep — verify each part addresses the original goal",
                severity="warning",
            ))

        # 4. 完整性：错误处理
        if "error" not in prop_lower and "exception" not in prop_lower and "fail" not in prop_lower:
            challenges.append(AdversarialChallenge(
                challenge_id=self._make_id(proposal, "incompleteness_error"),
                challenge_type="incompleteness",
                description="Error handling not mentioned — what happens on failure?",
                severity="critical",
            ))

        # 5. 偏差：过度工程
        if any(kw in prop_lower for kw in ["abstract", "factory", "plugin", "extensible", "future-proof"]):
            challenges.append(AdversarialChallenge(
                challenge_id=self._make_id(proposal, "bias_overengineer"),
                challenge_type="bias",
                description="Possible over-engineering — is this abstraction needed now?",
                severity="info",
            ))

        return challenges

    @staticmethod
    def _make_id(proposal: str, challenge_type: str) -> str:
        h = hashlib.md5(f"{proposal}:{challenge_type}".encode()).hexdigest()[:8]
        return f"challenge-{challenge_type}-{h}"


class BlueTeam:
    """蓝方：响应挑战，加固方案。

    默认策略：
    - 对明确的反例提供缓解措施
    - 对未覆盖的错误处理让步（conceded=True）
    - 对过度工程警告接受
    """

    def __init__(self, responder: Callable[[list[AdversarialChallenge]], list[AdversarialDefense]] | None = None) -> None:
        self._responder = responder

    def respond(self, challenges: list[AdversarialChallenge]) -> list[AdversarialDefense]:
        if self._responder is not None:
            return self._responder(challenges)
        return [self._heuristic_response(c) for c in challenges]

    def _heuristic_response(self, challenge: AdversarialChallenge) -> AdversarialDefense:
        if challenge.challenge_type == "counterexample":
            return AdversarialDefense(
                challenge_id=challenge.challenge_id,
                response="Input validation will be added at trust boundaries",
                mitigation="Add isinstance/None checks and raise ValueError on invalid input",
                conceded=False,
            )

        if challenge.challenge_type == "edge_case":
            return AdversarialDefense(
                challenge_id=challenge.challenge_id,
                response="Concurrency will be handled with locking or queue-based serialization",
                mitigation="Use asyncio.Lock or threading.Lock for shared resources",
                conceded=False,
            )

        if challenge.challenge_type == "goal_drift":
            return AdversarialDefense(
                challenge_id=challenge.challenge_id,
                response="Scope will be reviewed to ensure alignment with original goal",
                mitigation="Split proposal into must-have and nice-to-have",
                conceded=False,
            )

        if challenge.challenge_type == "incompleteness":
            # 蓝方让步：错误处理确实缺失
            return AdversarialDefense(
                challenge_id=challenge.challenge_id,
                response="Acknowledged — error handling needs to be added",
                mitigation=None,
                conceded=True,
            )

        # bias
        return AdversarialDefense(
            challenge_id=challenge.challenge_id,
            response="Accepted — will simplify if not justified by current requirements",
            mitigation="Apply YAGNI principle",
            conceded=False,
        )


class Judge:
    """裁判：评估胜负并输出改进建议。

    判定规则：
    - 蓝方让步任何 critical 挑战 → 红方胜
    - 蓝方缓解所有 critical 挑战 → 蓝方胜
    - 仅 warning/info 挑战 → 平局
    """

    def __init__(
        self,
        evaluator: Callable[[str, list[AdversarialChallenge], list[AdversarialDefense]], AdversarialVerdict] | None = None,
    ) -> None:
        self._evaluator = evaluator

    def evaluate(
        self,
        proposal: str,
        challenges: list[AdversarialChallenge],
        defenses: list[AdversarialDefense],
    ) -> AdversarialVerdict:
        if self._evaluator is not None:
            return self._evaluator(proposal, challenges, defenses)
        return self._heuristic_verdict(proposal, challenges, defenses)

    def _heuristic_verdict(
        self,
        _proposal: str,
        challenges: list[AdversarialChallenge],
        defenses: list[AdversarialDefense],
    ) -> AdversarialVerdict:
        defense_map = {d.challenge_id: d for d in defenses}

        critical_unresolved = 0
        critical_resolved = 0
        improvements: list[str] = []

        for challenge in challenges:
            defense = defense_map.get(challenge.challenge_id)
            if challenge.severity == "critical":
                if defense is None or defense.conceded:
                    critical_unresolved += 1
                    improvements.append(
                        f"Resolve critical challenge: {challenge.description}"
                    )
                else:
                    critical_resolved += 1

            if challenge.severity == "warning" and defense and defense.mitigation:
                improvements.append(f"Apply mitigation: {defense.mitigation}")

        if critical_unresolved > 0:
            return AdversarialVerdict(
                winner="red",
                confidence=min(0.95, 0.6 + 0.1 * critical_unresolved),
                improvements=improvements,
                reasoning=f"{critical_unresolved} critical challenges unresolved",
            )

        if critical_resolved > 0:
            return AdversarialVerdict(
                winner="blue",
                confidence=min(0.95, 0.6 + 0.1 * critical_resolved),
                improvements=improvements,
                reasoning=f"All {critical_resolved} critical challenges mitigated",
            )

        return AdversarialVerdict(
            winner="draw",
            confidence=0.5,
            improvements=improvements,
            reasoning="No critical challenges raised — minor improvements suggested",
        )


# ============================================================
# 对抗验证编排器
# ============================================================


class AdversarialVerifyMode:
    """对抗验证模式编排器。

    红方挑战 → 蓝方防御 → 裁判裁决

    Usage:
        mode = AdversarialVerifyMode()
        result = mode.execute("Proposal: add new API endpoint /api/v1/users")
        if not result.passed:
            print("Proposal rejected by adversarial verification")
    """

    def __init__(
        self,
        red_team: RedTeam | None = None,
        blue_team: BlueTeam | None = None,
        judge: Judge | None = None,
    ) -> None:
        self._red_team = red_team or RedTeam()
        self._blue_team = blue_team or BlueTeam()
        self._judge = judge or Judge()

    def execute(self, proposal: str) -> AdversarialResult:
        """执行完整对抗验证流程。"""
        challenges = self._red_team.generate_challenges(proposal)
        defenses = self._blue_team.respond(challenges)
        verdict = self._judge.evaluate(proposal, challenges, defenses)
        return AdversarialResult(
            proposal=proposal,
            challenges=challenges,
            defenses=defenses,
            verdict=verdict,
        )

    def execute_with_options(
        self,
        proposal: str,
        options: dict[str, Any] | None = None,
    ) -> AdversarialResult:
        """带配置选项的对抗验证。

        Args:
            proposal: 提案内容。
            options: 配置选项，如 {"skip_bias_check": True}。
        """
        options = options or {}
        result = self.execute(proposal)

        if options.get("skip_info_challenges"):
            result.challenges = [c for c in result.challenges if c.severity != "info"]

        return result


__all__ = [
    "AdversarialChallenge",
    "AdversarialDefense",
    "AdversarialResult",
    "AdversarialVerdict",
    "AdversarialVerifyMode",
    "BlueTeam",
    "Judge",
    "RedTeam",
]
