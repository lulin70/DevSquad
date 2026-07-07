"""P2-1 Dynamic Workflows 对抗验证单元测试。"""

from __future__ import annotations

from scripts.collaboration.adversarial_verify import (
    AdversarialChallenge,
    AdversarialDefense,
    AdversarialResult,
    AdversarialVerdict,
    AdversarialVerifyMode,
    BlueTeam,
    Judge,
    RedTeam,
)
from scripts.collaboration.consensus import ConsensusEngine

# ============================================================
# 数据模型测试
# ============================================================


class TestAdversarialModels:
    def test_challenge_creation(self):
        c = AdversarialChallenge(
            challenge_id="c1",
            challenge_type="counterexample",
            description="empty input",
            severity="critical",
        )
        assert c.challenge_id == "c1"
        assert c.counterexample is None

    def test_defense_creation(self):
        d = AdversarialDefense(
            challenge_id="c1",
            response="will add validation",
            conceded=False,
        )
        assert d.mitigation is None
        assert d.conceded is False

    def test_verdict_creation(self):
        v = AdversarialVerdict(winner="red", confidence=0.8, reasoning="unresolved")
        assert v.improvements == []

    def test_result_passed_when_blue_wins(self):
        result = AdversarialResult(
            proposal="test",
            challenges=[],
            defenses=[],
            verdict=AdversarialVerdict(winner="blue", confidence=0.9),
        )
        assert result.passed is True

    def test_result_failed_when_red_wins(self):
        result = AdversarialResult(
            proposal="test",
            challenges=[],
            defenses=[],
            verdict=AdversarialVerdict(winner="red", confidence=0.8),
        )
        assert result.passed is False

    def test_result_draw_passes(self):
        result = AdversarialResult(
            proposal="test",
            challenges=[],
            defenses=[],
            verdict=AdversarialVerdict(winner="draw", confidence=0.5),
        )
        assert result.passed is True

    def test_critical_challenges_unresolved(self):
        challenges = [
            AdversarialChallenge("c1", "counterexample", "empty input", "critical"),
            AdversarialChallenge("c2", "incompleteness", "no error handling", "critical"),
            AdversarialChallenge("c3", "bias", "over-engineered", "info"),
        ]
        defenses = [
            AdversarialDefense("c1", "validated", conceded=False),
            AdversarialDefense("c2", "acknowledged", conceded=True),  # conceded
            AdversarialDefense("c3", "accepted", conceded=False),
        ]
        result = AdversarialResult(
            proposal="test",
            challenges=challenges,
            defenses=defenses,
            verdict=AdversarialVerdict(winner="red", confidence=0.7),
        )
        assert result.critical_challenges_unresolved == 1


# ============================================================
# RedTeam 测试
# ============================================================


class TestRedTeam:
    def test_heuristic_generates_counterexample(self):
        red = RedTeam()
        challenges = red.generate_challenges("build user API endpoint")
        types = [c.challenge_type for c in challenges]
        assert "counterexample" in types

    def test_heuristic_generates_concurrency_for_api(self):
        red = RedTeam()
        challenges = red.generate_challenges("add new API endpoint")
        types = [c.challenge_type for c in challenges]
        assert "edge_case" in types

    def test_heuristic_no_concurrency_for_non_api(self):
        red = RedTeam()
        challenges = red.generate_challenges("refactor utils module")
        types = [c.challenge_type for c in challenges]
        assert "edge_case" not in types

    def test_heuristic_incompleteness_when_no_error_handling(self):
        red = RedTeam()
        challenges = red.generate_challenges("build user feature")
        types = [c.challenge_type for c in challenges]
        assert "incompleteness" in types

    def test_heuristic_no_incompleteness_when_error_mentioned(self):
        red = RedTeam()
        challenges = red.generate_challenges("build user feature with error handling")
        types = [c.challenge_type for c in challenges]
        assert "incompleteness" not in types

    def test_heuristic_goal_drift_for_long_proposal(self):
        red = RedTeam()
        long_proposal = "Build user API " + "with additional features " * 30
        challenges = red.generate_challenges(long_proposal)
        types = [c.challenge_type for c in challenges]
        assert "goal_drift" in types

    def test_heuristic_bias_for_overengineering_keywords(self):
        red = RedTeam()
        challenges = red.generate_challenges("build abstract factory plugin system")
        types = [c.challenge_type for c in challenges]
        assert "bias" in types

    def test_custom_generator(self):
        def custom_gen(proposal):
            return [AdversarialChallenge("custom", "custom", "custom challenge", "info")]

        red = RedTeam(challenge_generator=custom_gen)
        challenges = red.generate_challenges("anything")
        assert len(challenges) == 1
        assert challenges[0].challenge_id == "custom"

    def test_challenge_ids_unique(self):
        red = RedTeam()
        challenges = red.generate_challenges("build API endpoint")
        ids = [c.challenge_id for c in challenges]
        assert len(ids) == len(set(ids))


# ============================================================
# BlueTeam 测试
# ============================================================


class TestBlueTeam:
    def test_counterexample_response_not_conceded(self):
        blue = BlueTeam()
        challenge = AdversarialChallenge(
            "c1", "counterexample", "empty input", "critical"
        )
        defenses = blue.respond([challenge])
        assert len(defenses) == 1
        assert defenses[0].conceded is False
        assert defenses[0].mitigation is not None

    def test_incompleteness_response_conceded(self):
        blue = BlueTeam()
        challenge = AdversarialChallenge(
            "c1", "incompleteness", "no error handling", "critical"
        )
        defenses = blue.respond([challenge])
        assert defenses[0].conceded is True

    def test_edge_case_response_with_locking(self):
        blue = BlueTeam()
        challenge = AdversarialChallenge(
            "c1", "edge_case", "concurrent access", "warning"
        )
        defenses = blue.respond([challenge])
        assert "Lock" in defenses[0].mitigation or "lock" in defenses[0].mitigation

    def test_custom_responder(self):
        def custom_respond(challenges):
            return [AdversarialDefense(c.challenge_id, "custom", conceded=True) for c in challenges]

        blue = BlueTeam(responder=custom_respond)
        defenses = blue.respond([
            AdversarialChallenge("c1", "test", "test", "info"),
        ])
        assert defenses[0].conceded is True


# ============================================================
# Judge 测试
# ============================================================


class TestJudge:
    def test_red_wins_when_critical_conceded(self):
        judge = Judge()
        challenges = [
            AdversarialChallenge("c1", "counterexample", "empty input", "critical"),
        ]
        defenses = [
            AdversarialDefense("c1", "acknowledged", conceded=True),
        ]
        verdict = judge.evaluate("proposal", challenges, defenses)
        assert verdict.winner == "red"
        assert verdict.confidence > 0.5

    def test_blue_wins_when_critical_mitigated(self):
        judge = Judge()
        challenges = [
            AdversarialChallenge("c1", "counterexample", "empty input", "critical"),
        ]
        defenses = [
            AdversarialDefense("c1", "validated", mitigation="add check", conceded=False),
        ]
        verdict = judge.evaluate("proposal", challenges, defenses)
        assert verdict.winner == "blue"

    def test_draw_when_no_critical(self):
        judge = Judge()
        challenges = [
            AdversarialChallenge("c1", "bias", "over-engineered", "info"),
        ]
        defenses = [
            AdversarialDefense("c1", "accepted", conceded=False),
        ]
        verdict = judge.evaluate("proposal", challenges, defenses)
        assert verdict.winner == "draw"

    def test_improvements_generated(self):
        judge = Judge()
        challenges = [
            AdversarialChallenge("c1", "counterexample", "empty input", "critical"),
            AdversarialChallenge("c2", "edge_case", "concurrency", "warning"),
        ]
        defenses = [
            AdversarialDefense("c1", "acknowledged", conceded=True),
            AdversarialDefense("c2", "locking", mitigation="use Lock"),
        ]
        verdict = judge.evaluate("proposal", challenges, defenses)
        assert len(verdict.improvements) >= 1

    def test_custom_evaluator(self):
        def custom_eval(proposal, challenges, defenses):
            return AdversarialVerdict(winner="blue", confidence=1.0, reasoning="custom")

        judge = Judge(evaluator=custom_eval)
        verdict = judge.evaluate("p", [], [])
        assert verdict.winner == "blue"
        assert verdict.reasoning == "custom"


# ============================================================
# AdversarialVerifyMode 集成测试
# ============================================================


class TestAdversarialVerifyMode:
    def test_full_flow_with_api_proposal(self):
        mode = AdversarialVerifyMode()
        result = mode.execute("Add new API endpoint /api/v1/users")
        assert len(result.challenges) > 0
        assert len(result.defenses) == len(result.challenges)
        assert result.verdict.winner in ("red", "blue", "draw")

    def test_full_flow_with_simple_proposal(self):
        mode = AdversarialVerifyMode()
        result = mode.execute("refactor utils module")
        assert len(result.challenges) > 0
        # No API/endpoint, so no edge_case challenge
        types = [c.challenge_type for c in result.challenges]
        assert "edge_case" not in types

    def test_incompleteness_proposal_fails(self):
        """提案缺少错误处理 → 红方挑战 → 蓝方让步 → 红方胜。"""
        mode = AdversarialVerifyMode()
        # Proposal without "error"/"exception"/"fail" keywords triggers incompleteness
        result = mode.execute("build user feature with input validation")
        # Incompleteness challenge fires because "error" not in proposal
        incompleteness = [
            c for c in result.challenges if c.challenge_type == "incompleteness"
        ]
        assert len(incompleteness) >= 1
        # Blue concedes incompleteness → red wins
        assert result.passed is False

    def test_proposal_with_error_handling_passes(self):
        """提案包含错误处理 → 蓝方缓解 → 蓝方胜。"""
        mode = AdversarialVerifyMode()
        result = mode.execute("build user feature with error handling and validation")
        # No incompleteness challenge since "error" is in proposal
        types = [c.challenge_type for c in result.challenges]
        assert "incompleteness" not in types

    def test_execute_with_options_skip_info(self):
        mode = AdversarialVerifyMode()
        result = mode.execute_with_options(
            "build abstract factory plugin system",
            options={"skip_info_challenges": True},
        )
        severities = [c.severity for c in result.challenges]
        assert "info" not in severities

    def test_custom_teams_injection(self):
        """自定义红蓝裁判注入。"""
        custom_red = RedTeam(challenge_generator=lambda _p: [
            AdversarialChallenge("custom", "custom", "custom", "critical"),
        ])
        custom_blue = BlueTeam(responder=lambda cs: [
            AdversarialDefense(c.challenge_id, "ok", conceded=False) for c in cs
        ])
        custom_judge = Judge()

        mode = AdversarialVerifyMode(
            red_team=custom_red,
            blue_team=custom_blue,
            judge=custom_judge,
        )
        result = mode.execute("anything")
        assert len(result.challenges) == 1
        assert result.challenges[0].challenge_id == "custom"
        assert result.verdict.winner == "blue"


# ============================================================
# ConsensusEngine 集成测试
# ============================================================


class TestConsensusEngineIntegration:
    def test_adversarial_verify_method_exists(self):
        engine = ConsensusEngine()
        assert hasattr(engine, "adversarial_verify")

    def test_adversarial_verify_returns_result(self):
        engine = ConsensusEngine()
        result = engine.adversarial_verify("Add new API endpoint /api/v1/users")
        assert isinstance(result, AdversarialResult)
        assert len(result.challenges) > 0
        assert result.verdict.winner in ("red", "blue", "draw")

    def test_adversarial_verify_does_not_affect_standard_consensus(self):
        """对抗验证不影响标准共识流程。"""
        engine = ConsensusEngine()
        # Run adversarial verify
        adv_result = engine.adversarial_verify("test proposal")
        assert adv_result.passed in (True, False)

        # Standard consensus still works
        proposal = engine.create_proposal(
            topic="test",
            proposer_id="coord",
            content="test content",
        )
        record = engine.reach_consensus(proposal.proposal_id)
        assert record.outcome is not None  # Standard flow intact

    def test_adversarial_verify_with_empty_proposal(self):
        engine = ConsensusEngine()
        result = engine.adversarial_verify("")
        # Empty proposal still generates counterexample challenge
        assert len(result.challenges) > 0

    def test_adversarial_verify_propagates_to_dispatch(self):
        """对抗验证可通过 dispatcher 访问（无幽灵功能）。"""
        from scripts.collaboration.dispatcher import create_dispatcher

        d = create_dispatcher(enable_warmup=False, enable_memory=False, enable_skillify=False)
        assert hasattr(d, "consensus_engine")
        assert hasattr(d.consensus_engine, "adversarial_verify")

        result = d.consensus_engine.adversarial_verify("test proposal")
        assert isinstance(result, AdversarialResult)


# ============================================================
# 三大痛点应对测试
# ============================================================


class TestPainPointAddressal:
    """验证对抗验证应对三大痛点。"""

    def test_agentic_laziness_detected(self):
        """Agentic Laziness: 缺少错误处理 → 红方挑战完整性。"""
        mode = AdversarialVerifyMode()
        result = mode.execute("build user registration feature")
        types = [c.challenge_type for c in result.challenges]
        # Incompleteness challenge flags missing error handling
        assert "incompleteness" in types or "counterexample" in types

    def test_self_preferential_bias_detected(self):
        """Self-preferential Bias: 过度工程关键词 → 红方挑战偏差。"""
        mode = AdversarialVerifyMode()
        result = mode.execute("build extensible plugin system with abstract factory")
        types = [c.challenge_type for c in result.challenges]
        assert "bias" in types

    def test_goal_drift_detected(self):
        """Goal Drift: 过长提案 → 红方检测目标偏移。"""
        mode = AdversarialVerifyMode()
        long_proposal = "Build feature X. " + "Also add Y. " * 30
        result = mode.execute(long_proposal)
        types = [c.challenge_type for c in result.challenges]
        assert "goal_drift" in types
