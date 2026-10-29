"""
V4.9.0 W4 Feature Gate Integration Tests

集成测试：feature_gate.py 与 dispatch pipeline 的真实集成。
覆盖：anchor 锚定、现算覆盖矩阵、篡改检测、双侧交叉验证。
"""

import json

import pytest

from scripts.collaboration.config_manager import FeatureGateConfig
from scripts.collaboration.dispatch_models import DispatchResult
from scripts.collaboration.feature_gate import FeatureGate

pytestmark = pytest.mark.integration


class TestFeatureGateDispatchIntegration:
    """特性门与 dispatch 管道集成"""

    def test_anchor_and_verify_full_cycle(self, tmp_path):
        """测试完整周期：anchor 锚定 → dispatch → verify 重算"""
        checklist_path = tmp_path / "checklist.json"

        # 创建验收清单
        checklist = {
            "version": "1",
            "feature": "test-feature",
            "items": [
                {
                    "id": "T1",
                    "description": "Unit tests pass",
                    "command": "python3 -c 'print(\"test_pass\")'",
                    "expected": "test_pass",
                    "kind": "exact_match",
                },
                {
                    "id": "T2",
                    "description": "Lint check",
                    "command": "python3 -c 'print(\"lint_ok\")'",
                    "expected": "lint_ok",
                    "kind": "exact_match",
                },
            ],
        }
        checklist_path.write_text(json.dumps(checklist, indent=2))

        # Step 1: anchor 锚定（dispatch 前，Step 1）
        config = FeatureGateConfig(enabled=True, checklist_path=str(checklist_path))
        gate = FeatureGate(config)

        anchor_result = gate.anchor()
        assert anchor_result["checklist_sha256"] is not None
        assert len(anchor_result["checklist_sha256"]) == 64  # SHA256 hex
        assert anchor_result["descriptions"] == ["Unit tests pass", "Lint check"]

        # Step 2: 模拟 dispatch 运行...（中间可能有其他步骤）

        # Step 3: verify 重算（dispatch 后，Step 23.5）
        verify_result = gate.verify()

        # 验证：① SHA256 一致（无篡改）
        assert verify_result["checklist_sha256"] == anchor_result["checklist_sha256"]
        assert not verify_result["checklist_tampered"]

        # 验证：② 现算覆盖矩阵（命令真实执行）
        assert verify_result["verdict"] == "pass"  # 两个测试都通过
        coverage = verify_result["coverage_matrix"]
        assert len(coverage) == 2
        assert coverage[0]["id"] == "T1"
        assert coverage[0]["status"] == "pass"
        assert coverage[1]["id"] == "T2"
        assert coverage[1]["status"] == "pass"

    def test_tamper_detection(self, tmp_path):
        """测试篡改检测：anchor 后修改 checklist"""
        checklist_path = tmp_path / "checklist_tamper.json"

        # 原始清单
        original = {
            "version": "1",
            "feature": "tamper-test",
            "items": [
                {
                    "id": "T1",
                    "description": "Original test",
                    "command": "python3 -c 'exit(0)'",
                    "expected": "",
                    "kind": "exit_zero",
                }
            ],
        }
        checklist_path.write_text(json.dumps(original, indent=2))

        config = FeatureGateConfig(enabled=True, checklist_path=str(checklist_path))
        gate = FeatureGate(config)

        # Step 1: anchor
        anchor_result = gate.anchor()
        original_sha256 = anchor_result["checklist_sha256"]

        # Step 2: 篡改清单（模拟攻击者降低验收标准）
        tampered = original.copy()
        tampered["items"][0]["description"] = "Tampered test (easier)"
        checklist_path.write_text(json.dumps(tampered, indent=2))

        # Step 3: verify（应检测到篡改）
        # 需要重新读取配置以加载被篡改的文件
        gate_verify = FeatureGate(config)
        verify_result = gate_verify.verify()

        # 验证：① SHA256 不一致
        assert verify_result["checklist_sha256"] != original_sha256
        assert verify_result["checklist_tampered"]

        # 验证：② verdict 自动为 FAIL
        assert verify_result["verdict"] == "fail"
        assert "tampered" in verify_result.get("fail_reason", "").lower()

    def test_waived_items_disclosure(self, tmp_path):
        """测试豁免项全链路披露"""
        checklist_path = tmp_path / "checklist_waive.json"

        checklist = {
            "version": "1",
            "feature": "waive-test",
            "items": [
                {
                    "id": "T1",
                    "description": "Passing test",
                    "command": "python3 -c 'exit(0)'",
                    "expected": "",
                    "kind": "exit_zero",
                },
                {
                    "id": "T2",
                    "description": "Waived failing test",
                    "command": "python3 -c 'exit(1)'",
                    "expected": "",
                    "kind": "exit_zero",
                    "waive": True,
                    "waive_reason": "Known issue, fix scheduled for v4.9.1",
                },
            ],
        }
        checklist_path.write_text(json.dumps(checklist, indent=2))

        config = FeatureGateConfig(enabled=True, checklist_path=str(checklist_path))
        gate = FeatureGate(config)

        gate.anchor()
        verify_result = gate.verify()

        # 验证：verdict 仍为 pass（豁免项不影响）
        assert verify_result["verdict"] == "pass"

        # 验证：豁免项出现在覆盖矩阵中
        coverage = verify_result["coverage_matrix"]
        waived_item = [c for c in coverage if c["id"] == "T2"][0]
        assert waived_item["status"] == "waived"
        assert "Known issue" in waived_item["waive_reason"]


class TestFeatureGateReviewIntegration:
    """特性门与 review gate 双侧交叉验证"""

    def test_anchor_descriptions_inject_to_review_gate(self, tmp_path):
        """测试 anchor descriptions 注入 review gate (D8 双侧交叉)"""
        checklist_path = tmp_path / "checklist_review.json"

        checklist = {
            "version": "1",
            "feature": "cross-check",
            "items": [
                {
                    "id": "AC1",
                    "description": "Authentication module secure",
                    "command": "python3 -c 'exit(0)'",
                    "expected": "",
                    "kind": "exit_zero",
                },
                {
                    "id": "AC2",
                    "description": "Session management tested",
                    "command": "python3 -c 'exit(0)'",
                    "expected": "",
                    "kind": "exit_zero",
                },
            ],
        }
        checklist_path.write_text(json.dumps(checklist, indent=2))

        config = FeatureGateConfig(enabled=True, checklist_path=str(checklist_path))
        gate = FeatureGate(config)

        anchor_result = gate.anchor()
        descriptions = anchor_result["descriptions"]

        # 验证：descriptions 应注入 review gate 的 spec_requirements.acceptance_criteria
        # （实际注入由 dispatcher 执行，这里验证 anchor 输出格式正确）
        assert len(descriptions) == 2
        assert "Authentication module secure" in descriptions
        assert "Session management tested" in descriptions

        # 模拟 review gate 接收到这些 criteria
        # review gate 应比对 feature_gate 的验收标准与代码审查发现
        # 如果 review 发现未满足 acceptance_criteria，应标记为 BREAK

        # 这里只验证数据格式，实际交叉验证由 dispatcher 协调
        assert all(isinstance(d, str) for d in descriptions)


class TestFeatureGateErrorHandlingIntegration:
    """特性门错误处理集成测试"""

    def test_invalid_checklist_schema(self, tmp_path):
        """测试无效清单 schema（fail-closed）"""
        checklist_path = tmp_path / "invalid.json"

        # 缺少必需字段
        invalid = {
            "version": "1"
            # 缺少 feature 和 items
        }
        checklist_path.write_text(json.dumps(invalid))

        config = FeatureGateConfig(enabled=True, checklist_path=str(checklist_path))
        gate = FeatureGate(config)

        # anchor 应失败（fail-closed）
        with pytest.raises(ValueError, match="Invalid checklist schema"):
            gate.anchor()

    def test_command_execution_failure(self, tmp_path):
        """测试命令执行失败的处理"""
        checklist_path = tmp_path / "cmd_fail.json"

        checklist = {
            "version": "1",
            "feature": "cmd-fail-test",
            "items": [
                {
                    "id": "F1",
                    "description": "This command will fail",
                    "command": "python3 -c 'raise RuntimeError(\"intentional failure\")'",
                    "expected": "",
                    "kind": "exit_zero",
                }
            ],
        }
        checklist_path.write_text(json.dumps(checklist, indent=2))

        config = FeatureGateConfig(enabled=True, checklist_path=str(checklist_path))
        gate = FeatureGate(config)

        gate.anchor()
        verify_result = gate.verify()

        # 验证：命令失败应反映在覆盖矩阵中
        assert verify_result["verdict"] == "fail"
        coverage = verify_result["coverage_matrix"]
        assert coverage[0]["status"] == "fail"
        assert "RuntimeError" in coverage[0].get("actual_output", "")


class TestFeatureGateDisabledModeIntegration:
    """特性门禁用模式集成测试（D7 五面零痕迹）"""

    def test_disabled_mode_zero_trace(self, tmp_path):
        """测试禁用模式：五面零痕迹（details/attr/Markdown/audit/success）"""
        checklist_path = tmp_path / "disabled.json"

        checklist = {
            "version": "1",
            "feature": "disabled-test",
            "items": [{"id": "D1", "description": "test", "command": "exit 0", "expected": "", "kind": "exit_zero"}],
        }
        checklist_path.write_text(json.dumps(checklist))

        # 禁用模式
        config = FeatureGateConfig(enabled=False, checklist_path=str(checklist_path))
        gate = FeatureGate(config)

        # anchor 和 verify 应返回空结果
        anchor_result = gate.anchor()
        verify_result = gate.verify()

        # 验证：禁用时无输出
        assert anchor_result == {}
        assert verify_result == {}

        # 模拟 dispatch_models.DispatchResult
        # 禁用时 result.feature_gate 应为 None
        result = DispatchResult(
            success=True,
            summary="Test dispatch",
            role_outputs={},
            consensus="All good",
            feature_gate=verify_result if verify_result else None,
        )

        assert result.feature_gate is None  # 零痕迹
