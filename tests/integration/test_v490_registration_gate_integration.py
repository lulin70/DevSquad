"""
V4.9.0 W3 Registration Gate Integration Tests

集成测试：registration_gate.py 与 defect_ledger、dispatch_audit 的真实集成。
覆盖：三态判定、信号抽取、D4死锁规避、advisory报告、跨模块数据流。
"""

import pytest

from scripts.collaboration.config_manager import RegistrationGateConfig
from scripts.collaboration.defect_ledger import DefectLedger
from scripts.collaboration.dispatch_audit import DispatchAuditLogger
from scripts.collaboration.registration_gate import RegistrationGate

pytestmark = pytest.mark.integration


class TestRegistrationGateDefectLedgerIntegration:
    """登记闸与缺陷台账集成"""

    def test_tracked_signal_pass(self, tmp_path):
        """测试已登记信号通过（tracked → PASS）"""
        audit_path = tmp_path / "tracked_audit.db"
        ledger_path = tmp_path / "tracked_defects.json"

        # Step 1: 审计发现 critical break-vuln
        logger = DispatchAuditLogger(str(audit_path))
        logger.log_dispatch_start("task-001", "mock", ["security"])
        logger.log_dispatch_end(
            task_id="task-001",
            success=False,
            findings={"break-vuln": ["SQL injection"]},
            failure_class="product_failed",
        )
        logger.close()

        # Step 2: 已登记缺陷（open 状态）
        ledger = DefectLedger(ledger_path=ledger_path, audit_db_path=audit_path)
        ledger.add(
            signal_ref="audit:event=1&finding=0",
            summary="Fix SQL injection - Critical security issue",
        )

        # Step 3: 运行 registration gate（应判定为 tracked → PASS）
        config = RegistrationGateConfig(enabled=True, audit_db_path=str(audit_path), ledger_path=str(ledger_path))
        gate = RegistrationGate(config)

        result = gate.evaluate()

        # 验证：三态判定为 tracked
        assert result["verdict"] == "pass"
        assert result["status"] == "tracked"
        assert len(result["tracked_signals"]) == 1
        assert "SQL injection" in result["tracked_signals"][0]

    def test_unregistered_signal_fail(self, tmp_path):
        """测试未登记信号失败（unregistered → FAIL）"""
        audit_path = tmp_path / "unreg_audit.db"
        ledger_path = tmp_path / "empty_defects.json"

        # Step 1: 审计发现问题
        logger = DispatchAuditLogger(str(audit_path))
        logger.log_dispatch_start("task-002", "mock", ["tester"])
        logger.log_dispatch_end(
            task_id="task-002",
            success=False,
            findings={"break-vuln": ["Unhandled exception"]},
            failure_class="product_failed",
        )
        logger.close()

        # Step 2: 空台账（未登记）
        DefectLedger(ledger_path=ledger_path, audit_db_path=audit_path)
        # 不添加任何缺陷，台账为空（实例化确保文件存在）

        # Step 3: 运行 registration gate（应判定为 unregistered → FAIL）
        config = RegistrationGateConfig(enabled=True, audit_db_path=str(audit_path), ledger_path=str(ledger_path))
        gate = RegistrationGate(config)

        result = gate.evaluate()

        # 验证：三态判定为 unregistered
        assert result["verdict"] == "fail"
        assert result["status"] == "unregistered"
        assert len(result["unregistered_signals"]) == 1
        assert "Unhandled exception" in result["unregistered_signals"][0]

        # 验证：提供 reopen 指引
        assert "file a defect" in result["fail_reason"].lower()

    def test_regressed_signal_fail_with_reopen_guidance(self, tmp_path):
        """测试回归信号失败（regressed → FAIL）+ reopen 指引"""
        audit_path = tmp_path / "regressed_audit.db"
        ledger_path = tmp_path / "regressed_defects.json"

        # Step 1: 审计发现问题
        logger = DispatchAuditLogger(str(audit_path))
        logger.log_dispatch_start("task-003", "mock", ["architect"])
        logger.log_dispatch_end(
            task_id="task-003",
            success=False,
            findings={"spec": ["Missing documentation"]},
            failure_class="product_failed",
        )
        logger.close()

        # Step 2: 缺陷已关闭（closed 状态 = 回归）
        ledger = DefectLedger(ledger_path=ledger_path, audit_db_path=audit_path)
        defect = ledger.add(
            signal_ref="audit:event=1&finding=0",
            summary="Add documentation - Documentation is missing",
        )
        defect_id = defect.id
        # 标记为 fixed 并关闭
        ledger.update(defect_id, commit_sha="abc123", summary="Added documentation")
        ledger.close(defect_id, run_ref="audit:event=2")

        # Step 3: 运行 registration gate（应判定为 regressed → FAIL）
        config = RegistrationGateConfig(enabled=True, audit_db_path=str(audit_path), ledger_path=str(ledger_path))
        gate = RegistrationGate(config)

        result = gate.evaluate()

        # 验证：三态判定为 regressed
        assert result["verdict"] == "fail"
        assert result["status"] == "regressed"
        assert len(result["regressed_signals"]) == 1

        # 验证：提供 reopen 指引（D4 死锁规避）
        assert "reopen" in result["fail_reason"].lower()
        assert defect_id in result["regressed_signals"][0]


class TestRegistrationGateD4DeadlockAvoidanceIntegration:
    """D4 死锁规避集成测试"""

    def test_fixed_state_still_counts_as_tracked(self, tmp_path):
        """测试 fixed 状态仍算 tracked（避免死锁）"""
        audit_path = tmp_path / "fixed_audit.db"
        ledger_path = tmp_path / "fixed_defects.json"

        # 审计发现问题
        logger = DispatchAuditLogger(str(audit_path))
        logger.log_dispatch_start("task-fixed", "mock", ["coder"])
        logger.log_dispatch_end(
            task_id="task-fixed",
            success=False,
            findings={"spec": ["Performance issue"]},
            failure_class="product_failed",
        )
        logger.close()

        # 缺陷已修复（fixed）但未关闭
        ledger = DefectLedger(ledger_path=ledger_path, audit_db_path=audit_path)
        defect = ledger.add(
            signal_ref="audit:event=1&finding=0",
            summary="Optimize performance - Performance regression",
        )
        ledger.update(defect.id, commit_sha="def456", summary="Optimized performance")

        # 运行 registration gate
        config = RegistrationGateConfig(enabled=True, audit_db_path=str(audit_path), ledger_path=str(ledger_path))
        gate = RegistrationGate(config)

        result = gate.evaluate()

        # 验证：fixed 状态算 tracked → PASS（避免死锁）
        assert result["verdict"] == "pass"
        assert result["status"] == "tracked"
        # run 仍然失败（success=False），但 gate 不阻止

    def test_multiple_states_classification(self, tmp_path):
        """测试多信号分类：tracked + unregistered + regressed 混合"""
        audit_path = tmp_path / "multi_audit.db"
        ledger_path = tmp_path / "multi_defects.json"

        # 审计发现三个问题
        logger = DispatchAuditLogger(str(audit_path))
        logger.log_dispatch_start("task-multi", "mock", ["tester"])
        logger.log_dispatch_end(
            task_id="task-multi",
            success=False,
            findings={
                "break-vuln": ["Issue A"],  # 已登记（open）
                "spec": ["Issue B", "Issue C"],  # B未登记，C已关闭
            },
            failure_class="product_failed",
        )
        logger.close()

        # 台账状态：A=open, C=closed
        ledger = DefectLedger(ledger_path=ledger_path, audit_db_path=audit_path)
        ledger.add(signal_ref="audit:event=1&finding=0", summary="Fix Issue A - Tracked issue")
        defect_c = ledger.add(signal_ref="audit:event=1&finding=2", summary="Fix Issue C - Regressed issue")
        ledger.update(defect_c.id, commit_sha="ghi789", summary="Fixed Issue C")
        ledger.close(defect_c.id, run_ref="audit:event=2")

        # 运行 registration gate
        config = RegistrationGateConfig(enabled=True, audit_db_path=str(audit_path), ledger_path=str(ledger_path))
        gate = RegistrationGate(config)

        result = gate.evaluate()

        # 验证：有 unregistered 和 regressed → FAIL
        assert result["verdict"] == "fail"
        # 验证：分类正确
        assert len(result["tracked_signals"]) == 1  # Issue A
        assert len(result["unregistered_signals"]) == 1  # Issue B
        assert len(result["regressed_signals"]) == 1  # Issue C


class TestRegistrationGateAdvisoryReportIntegration:
    """advisory 报告集成测试"""

    def test_unfiled_signal_report_advisory_only(self, tmp_path):
        """测试 unfiled_signal_report（warning/spec）不改退出码"""
        audit_path = tmp_path / "advisory_audit.db"
        ledger_path = tmp_path / "advisory_defects.json"

        # 审计发现 warning 和 spec（非强制）
        logger = DispatchAuditLogger(str(audit_path))
        logger.log_dispatch_start("task-advisory", "mock", ["coder"])
        logger.log_dispatch_end(
            task_id="task-advisory",
            success=True,  # 成功，但有建议
            findings={"warning": ["Code smell in utils.py"], "spec": ["Missing edge case test"]},
            failure_class=None,
        )
        logger.close()

        # 空台账
        DefectLedger(ledger_path=ledger_path, audit_db_path=audit_path)
        # 不添加任何缺陷（实例化确保文件存在）

        # 运行 registration gate
        config = RegistrationGateConfig(enabled=True, audit_db_path=str(audit_path), ledger_path=str(ledger_path))
        gate = RegistrationGate(config)

        result = gate.evaluate()

        # 验证：advisory 不改 verdict（仍为 pass）
        assert result["verdict"] == "pass"

        # 验证：unfiled_signal_report 中列出建议
        assert "unfiled_signal_report" in result
        advisory = result["unfiled_signal_report"]
        assert len(advisory) == 2
        assert any("Code smell" in sig for sig in advisory)
        assert any("Missing edge case" in sig for sig in advisory)


class TestRegistrationGateEnvironmentBlockedIntegration:
    """environment_blocked 拒绝集成测试"""

    def test_environment_blocked_rejection(self, tmp_path):
        """测试 environment_blocked 拒绝立案"""
        audit_path = tmp_path / "blocked_audit.db"
        ledger_path = tmp_path / "blocked_defects.json"

        # 审计记录环境阻断
        logger = DispatchAuditLogger(str(audit_path))
        logger.log_dispatch_start("task-blocked", "mock", ["devops"])
        logger.log_dispatch_end(task_id="task-blocked", success=False, findings={}, failure_class="environment_blocked")
        logger.close()

        # 台账（不应该有 environment_blocked 的缺陷）
        DefectLedger(ledger_path=ledger_path, audit_db_path=audit_path)
        # 环境阻断不需要登记缺陷（实例化确保文件存在）

        # 运行 registration gate
        config = RegistrationGateConfig(enabled=True, audit_db_path=str(audit_path), ledger_path=str(ledger_path))
        gate = RegistrationGate(config)

        result = gate.evaluate()

        # 验证：environment_blocked 不要求登记 → PASS
        # （或根据设计返回 blocked 状态）
        # 根据 PRD §4.2，environment_blocked 拒绝立案
        assert result["verdict"] in ["pass", "blocked"]
        # 不应有 unregistered_signals（因为环境问题不算产品缺陷）


class TestRegistrationGateFeatureGateErrorAttributionIntegration:
    """feature_gate 错误归因 product_failed 集成测试（PRD W3 ⑨）"""

    def test_feature_gate_error_counts_as_product_failed(self, tmp_path):
        """测试 feature_gate 错误文本归因为 product_failed"""
        audit_path = tmp_path / "fgate_audit.db"
        ledger_path = tmp_path / "fgate_defects.json"

        # 模拟 dispatch 失败：feature_gate 验证失败
        logger = DispatchAuditLogger(str(audit_path))
        logger.log_dispatch_start("task-fgate", "mock", ["architect"])
        logger.log_dispatch_end(
            task_id="task-fgate",
            success=False,
            findings={
                # feature_gate 错误文本被归因为产品缺陷
                "spec": ["Feature gate verification failed: T1 did not pass"]
            },
            failure_class="product_failed",
        )
        logger.close()

        # 未登记缺陷
        DefectLedger(ledger_path=ledger_path, audit_db_path=audit_path)
        # feature_gate 失败未登记（实例化确保文件存在）

        # 运行 registration gate
        config = RegistrationGateConfig(enabled=True, audit_db_path=str(audit_path), ledger_path=str(ledger_path))
        gate = RegistrationGate(config)

        result = gate.evaluate()

        # 验证：feature_gate 失败应被识别为 unregistered → FAIL
        assert result["verdict"] == "fail"
        assert result["status"] == "unregistered"
        assert len(result["unregistered_signals"]) == 1
        assert "Feature gate" in result["unregistered_signals"][0]


class TestRegistrationGatePersistenceIntegration:
    """持久化和跨进程集成测试"""

    def test_ledger_corruption_fail_closed(self, tmp_path):
        """测试台账损坏时 fail-closed（D7）"""
        audit_path = tmp_path / "corrupt_audit.db"
        ledger_path = tmp_path / "corrupt_defects.json"

        # 创建有效审计
        logger = DispatchAuditLogger(str(audit_path))
        logger.log_dispatch_start("task-corrupt", "mock", ["tester"])
        logger.log_dispatch_end(
            task_id="task-corrupt",
            success=False,
            findings={"break-vuln": ["Critical issue"]},
            failure_class="product_failed",
        )
        logger.close()

        # 创建损坏的台账文件
        ledger_path.write_text("{ invalid json }")

        # 运行 registration gate（应 fail-closed）
        config = RegistrationGateConfig(enabled=True, audit_db_path=str(audit_path), ledger_path=str(ledger_path))
        gate = RegistrationGate(config)

        result = gate.evaluate()

        # 验证：损坏台账 = 不能证明登记 = FAIL
        assert result["verdict"] == "fail"
        assert (
            "ledger" in result.get("fail_reason", "").lower()
            or "cannot verify" in result.get("fail_reason", "").lower()
        )
