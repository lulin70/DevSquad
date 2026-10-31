"""
V4.9.0 W4 Feature Gate Integration Tests

集成测试：feature_gate.py 与 dispatch pipeline 的真实集成。
覆盖：anchor 锚定、现算覆盖矩阵、篡改检测、双侧交叉验证。
"""

import json
import sys
from typing import Any

import pytest

from scripts.collaboration.config_manager import FeatureGateConfig
from scripts.collaboration.dispatch_audit import DispatchAuditLogger
from scripts.collaboration.dispatch_models import DispatchResult
from scripts.collaboration.dispatcher import MultiAgentDispatcher
from scripts.collaboration.feature_gate import DEFAULT_CHECKLIST_PATH, FeatureGate

pytestmark = pytest.mark.integration

_OK_CMD = f"{sys.executable} -c 'import sys; sys.exit(0)'"
_FAIL_CMD = f"{sys.executable} -c 'raise RuntimeError(\"intentional failure\")'"


class _OkBackend:
    """确定性本地 backend（无网络、无 API key）。"""

    model = "feature-gate-fake-model"

    def is_available(self) -> bool:
        return True

    def generate(self, prompt: str, **kwargs: Any) -> str:
        return "Structured answer: 4"

    def generate_stream(self, prompt: str, **kwargs: Any):
        yield "Structured answer: 4"


def _item(entry_id: str, command: str, description: str, *, waive_reason: str | None = None) -> dict[str, Any]:
    """一个 schema v1 验收清单条目。"""
    item: dict[str, Any] = {
        "id": entry_id,
        "description": description,
        "verify": {"kind": "command", "command": command},
    }
    if waive_reason is not None:
        item["waive_reason"] = waive_reason
    return item


def _write_checklist(tmp_path, name: str, items: list[dict[str, Any]]) -> Any:
    """写入 schema v1 验收清单并返回路径。"""
    checklist_path = tmp_path / name
    checklist_path.write_text(json.dumps({"schema_version": 1, "items": items}, indent=2), encoding="utf-8")
    return checklist_path


class TestFeatureGateDispatchIntegration:
    """特性门与 dispatch 管道集成"""

    def test_anchor_and_verify_full_cycle(self, tmp_path):
        """测试完整周期：anchor 锚定 → dispatch → verify 重算"""
        checklist_path = _write_checklist(
            tmp_path,
            "checklist.json",
            [
                _item("T1", _OK_CMD, "Unit tests pass"),
                _item("T2", _OK_CMD, "Lint check"),
            ],
        )

        # Step 1: anchor 锚定（dispatch 前，Step 1）
        gate = FeatureGate()
        anchor = gate.anchor(checklist_path)

        assert anchor["status"] == "ok"
        assert isinstance(anchor["sha256"], str) and len(anchor["sha256"]) == 64  # SHA256 hex
        assert anchor["descriptions"] == ["Unit tests pass", "Lint check"]

        # Step 2: 模拟 dispatch 运行...（中间可能有其他步骤）

        # Step 3: verify 重算（dispatch 后，Step 23.5）
        result = gate.evaluate(anchor, timeout_seconds=30)

        # 验证：① SHA256 一致（无篡改）
        assert result.anchored_sha256 == anchor["sha256"]
        assert result.computed_sha256 == anchor["sha256"]

        # 验证：② 现算覆盖矩阵（命令真实执行）
        assert result.verdict == "pass"
        assert len(result.entries) == 2
        assert result.entries[0]["id"] == "T1"
        assert result.entries[0]["status"] == "pass"
        assert result.entries[0]["exit_code"] == 0
        assert result.entries[1]["id"] == "T2"
        assert result.entries[1]["status"] == "pass"

    def test_tamper_detection(self, tmp_path):
        """测试篡改检测：anchor 后修改 checklist"""
        checklist_path = _write_checklist(
            tmp_path,
            "checklist_tamper.json",
            [_item("T1", _OK_CMD, "Original test")],
        )

        gate = FeatureGate()

        # Step 1: anchor
        anchor = gate.anchor(checklist_path)
        original_sha256 = anchor["sha256"]

        # Step 2: 篡改清单（模拟攻击者降低验收标准）
        checklist_path.write_text(
            json.dumps({"schema_version": 1, "items": [_item("T1", _OK_CMD, "Tampered test (easier)")]}, indent=2),
            encoding="utf-8",
        )

        # Step 3: verify（同一份 anchor 重新计算，应检测到篡改）
        result = gate.evaluate(anchor, timeout_seconds=30)

        # 验证：① SHA256 不一致
        assert result.computed_sha256 != original_sha256
        assert result.anchored_sha256 == original_sha256

        # 验证：② verdict 自动为 FAIL，且违规说明是 checklist_tampered
        assert result.verdict == "fail"
        assert any("checklist_tampered" in v for v in result.violations)
        assert result.entries == []

    def test_waived_items_disclosure(self, tmp_path):
        """测试豁免项全链路披露"""
        checklist_path = _write_checklist(
            tmp_path,
            "checklist_waive.json",
            [
                _item("T1", _OK_CMD, "Passing test"),
                _item("T2", _FAIL_CMD, "Waived failing test", waive_reason="Known issue, fix scheduled for v4.9.1"),
            ],
        )

        gate = FeatureGate()
        anchor = gate.anchor(checklist_path)
        result = gate.evaluate(anchor, timeout_seconds=30)

        # 验证：verdict 仍为 pass（豁免项不影响）
        assert result.verdict == "pass"

        # 验证：豁免项出现在覆盖矩阵中，且命令从未执行
        waived_item = [entry for entry in result.entries if entry["id"] == "T2"][0]
        assert waived_item["status"] == "waived"
        assert "Known issue" in waived_item["waive_reason"]
        assert "command" not in waived_item
        assert "exit_code" not in waived_item

        # 验证：to_dict 的 waived 列表可披露 id / description / reason
        waived = result.to_dict()["waived"]
        assert waived == [
            {
                "id": "T2",
                "description": "Waived failing test",
                "waive_reason": "Known issue, fix scheduled for v4.9.1",
            }
        ]


class TestFeatureGateReviewIntegration:
    """特性门与 review gate 双侧交叉验证"""

    def test_anchor_descriptions_inject_to_review_gate(self, tmp_path):
        """测试 anchor descriptions 注入 review gate (D8 双侧交叉)"""
        checklist_path = _write_checklist(
            tmp_path,
            "checklist_review.json",
            [
                _item("AC1", _OK_CMD, "Authentication module secure"),
                _item("AC2", _OK_CMD, "Session management tested"),
            ],
        )

        anchor = FeatureGate().anchor(checklist_path)
        descriptions = anchor["descriptions"]

        # 验证：descriptions 应注入 review gate 的 spec_requirements.acceptance_criteria
        # （实际注入由 dispatcher 的 _run_two_stage_review 执行，这里验证 anchor 输出格式正确）
        assert len(descriptions) == 2
        assert "Authentication module secure" in descriptions
        assert "Session management tested" in descriptions

        # 注入端只消费 status == "ok" 的锚定结果（dispatcher 的真实判断条件）
        assert anchor["status"] == "ok"
        assert all(isinstance(d, str) for d in descriptions)


class TestFeatureGateErrorHandlingIntegration:
    """特性门错误处理集成测试"""

    def test_invalid_checklist_schema(self, tmp_path):
        """测试无效清单 schema（fail-closed）"""
        checklist_path = tmp_path / "invalid.json"

        # 缺少必需字段（无 items）
        checklist_path.write_text(json.dumps({"schema_version": 1}), encoding="utf-8")

        gate = FeatureGate()

        # anchor 记录 invalid 状态（fail-closed，不抛出、不静默通过）
        anchor = gate.anchor(checklist_path)
        assert anchor["status"] == "invalid"
        assert any("items" in v for v in anchor["violations"])
        assert anchor["sha256"] is not None  # 文件仍被锚定，证据可追溯

        # evaluate 据此判定 FAIL，且无 entry（不能证明覆盖）
        result = gate.evaluate(anchor, timeout_seconds=30)
        assert result.verdict == "fail"
        assert result.passed is False
        assert result.violations
        assert result.entries == []

    def test_command_execution_failure(self, tmp_path):
        """测试命令执行失败的处理"""
        checklist_path = _write_checklist(
            tmp_path,
            "cmd_fail.json",
            [_item("F1", _FAIL_CMD, "This command will fail")],
        )

        gate = FeatureGate()
        anchor = gate.anchor(checklist_path)
        result = gate.evaluate(anchor, timeout_seconds=30)

        # 验证：命令失败应反映在覆盖矩阵中
        assert result.verdict == "fail"
        assert result.entries[0]["status"] == "fail"
        assert result.entries[0]["exit_code"] != 0
        assert "RuntimeError" in result.entries[0]["stderr_tail"]


class TestFeatureGateDisabledModeIntegration:
    """特性门禁用模式集成测试（D7 五面零痕迹）"""

    def test_disabled_mode_zero_trace(self, tmp_path):
        """测试禁用模式：五面零痕迹（details/attr/Markdown/audit/success）"""
        # 禁用模式是配置层开关：默认关闭，checklist 指向默认路径
        config = FeatureGateConfig(enabled=False)
        assert config.enabled is False
        assert config.checklist == DEFAULT_CHECKLIST_PATH

        # 真实 dispatch 验证零痕迹（默认构造即禁用）
        audit = DispatchAuditLogger()
        disp = MultiAgentDispatcher(llm_backend=_OkBackend(), audit_logger=audit, enable_memory=False)
        try:
            result = disp.dispatch("What is 2+2?", roles=["architect"])
        finally:
            disp.shutdown()

        assert result.success
        # 1. details 中无 gate 字段
        assert "feature_gate" not in result.details
        # 2. result 属性为 None
        assert result.feature_gate is None
        assert result.to_dict()["feature_gate"] is None
        # 3. Markdown 报告中无 gate 章节
        assert "Feature gate" not in result.to_markdown()
        # 4. audit 事件中无 gate 字段
        ends = audit.query(event_type="dispatch_end")
        assert len(ends) == 1
        assert "feature_gate" not in ends[0].details
        # 5. 裸 DispatchResult 默认同样零痕迹
        assert DispatchResult(success=True, task_description="Test dispatch").feature_gate is None
