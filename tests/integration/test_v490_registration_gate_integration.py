"""
V4.9.0 W3 Registration Gate Integration Tests

集成测试：registration_gate.py 与 defect_ledger、dispatch_audit 的真实集成。
覆盖：三态判定、信号抽取、D4死锁规避、advisory报告、跨模块数据流。
"""

import pytest

from scripts.collaboration.defect_ledger import DefectLedger, DefectLedgerError
from scripts.collaboration.dispatch_audit import DispatchAuditLogger
from scripts.collaboration.registration_gate import (
    RegistrationGate,
    RegistrationGateResult,
    unfiled_signal_report,
)
from scripts.collaboration.two_stage_review_gate import ReviewFinding, ReviewStage

pytestmark = pytest.mark.integration

# 一条确定性产品失败错误文本（不含环境阻断标记 → product_failed）
_PRODUCT_FAILURE = {"success": False, "error": "worker failed: empty content"}


def _finding(category: str, severity: str, stage: ReviewStage = ReviewStage.CODE_QUALITY) -> ReviewFinding:
    """真实 ReviewFinding（BV 类别码放在 category）。"""
    return ReviewFinding(
        stage=stage,
        severity=severity,
        category=category,
        description=f"review hit {category}",
        file_path="api/routes/dispatch.py",
        line_range="42",
        suggestion=f"Review and fix {category}.",
    )


def _finding_dict(category: str, severity: str, stage: ReviewStage = ReviewStage.CODE_QUALITY) -> dict:
    return _finding(category, severity, stage).to_dict()


def _log_end(
    logger: DispatchAuditLogger,
    user_id: str,
    *,
    findings: list[dict] | None = None,
    failure_class: str | None = None,
    success: bool = False,
) -> None:
    """写一个真实的 dispatch_end 审计事件。"""
    logger.log_dispatch_end(
        user_id=user_id,
        success=success,
        duration=1.0,
        findings=findings,
        failure_class=failure_class,
    )


class TestRegistrationGateDefectLedgerIntegration:
    """登记闸与缺陷台账集成"""

    def test_tracked_signal_pass(self, tmp_path):
        """测试已登记信号通过（tracked → PASS）"""
        audit_path = tmp_path / "tracked_audit.db"
        ledger_path = tmp_path / "tracked_defects.json"

        # Step 1: 审计发现 critical BV 问题
        logger = DispatchAuditLogger(audit_path)
        logger.log_dispatch_start("task-001", "mock", ["security"])
        _log_end(
            logger,
            "task-001",
            findings=[_finding_dict("VULN-1", "critical")],
            failure_class="product_failed",
        )
        logger.close()

        # Step 2: 已登记缺陷（open 状态），signal_ref 指向事件 2 的第 0 个 finding
        ledger = DefectLedger(ledger_path=ledger_path, audit_db_path=audit_path)
        ledger.add("audit:event=2&finding=0", "Fix SQL injection - Critical security issue")

        # Step 3: 运行 registration gate（应判定为 tracked → PASS）
        gate = RegistrationGate()
        result = gate.evaluate(
            worker_results=None,
            errors=None,
            findings=[_finding("VULN-1", "critical")],
            ledger_path=ledger_path,
        )

        # 验证：三态判定为 tracked，且记录覆盖它的 DEF 号
        assert result.verdict == "pass"
        assert result.signals == [
            {
                "type": "review:break-vuln:VULN-1",
                "status": "tracked",
                "tracked_by": ["DEF-001"],
                "closed_ids": [],
            }
        ]
        assert result.violations == []

    def test_unregistered_signal_fail(self, tmp_path):
        """测试未登记信号失败（unregistered → FAIL）"""
        audit_path = tmp_path / "unreg_audit.db"
        ledger_path = tmp_path / "empty_defects.json"

        # Step 1: 审计发现产品失败
        logger = DispatchAuditLogger(audit_path)
        logger.log_dispatch_start("task-002", "mock", ["tester"])
        _log_end(
            logger,
            "task-002",
            findings=[_finding_dict("missing_test", "warning", ReviewStage.SPEC_COMPLIANCE)],
            failure_class="product_failed",
        )
        logger.close()

        # Step 2: 空台账（未登记；台账文件不存在即合法空台账）
        gate = RegistrationGate()
        result = gate.evaluate(
            worker_results=[_PRODUCT_FAILURE],
            errors=None,
            findings=None,
            ledger_path=ledger_path,
        )

        # 验证：三态判定为 unregistered
        assert result.verdict == "fail"
        assert len(result.signals) == 1
        assert result.signals[0]["type"] == "failure:product_failed"
        assert result.signals[0]["status"] == "unregistered"

        # 验证：提供真实立案指引（design D6）
        assert "no live DEF ticket" in result.violations[0]
        assert "devsquad defect add" in result.violations[0]

    def test_regressed_signal_fail_with_reopen_guidance(self, tmp_path):
        """测试回归信号失败（regressed → FAIL）+ reopen 指引"""
        audit_path = tmp_path / "regressed_audit.db"
        ledger_path = tmp_path / "regressed_defects.json"

        # Step 1: 事件 1 = 发现，事件 2 = 干净回归跑
        logger = DispatchAuditLogger(audit_path)
        logger.log_dispatch_start("task-003", "mock", ["architect"])
        _log_end(logger, "task-003", findings=[], failure_class="product_failed")
        _log_end(logger, "task-verify", success=True, failure_class="none")
        logger.close()

        # Step 2: 缺陷已关闭（closed 状态 = 回归）
        ledger = DefectLedger(ledger_path=ledger_path, audit_db_path=audit_path)
        defect = ledger.add("audit:event=2&failure=product_failed", "Fix product failure")
        ledger.update(defect.id, "abc123", "Fixed the product failure")
        ledger.close(defect.id, "audit:event=3")

        # Step 3: 运行 registration gate（应判定为 regressed → FAIL）
        gate = RegistrationGate()
        result = gate.evaluate(
            worker_results=[_PRODUCT_FAILURE],
            errors=None,
            findings=None,
            ledger_path=ledger_path,
        )

        # 验证：三态判定为 regressed
        assert result.verdict == "fail"
        assert result.signals[0]["status"] == "regressed"
        assert result.signals[0]["tracked_by"] == []
        assert result.signals[0]["closed_ids"] == ["DEF-001"]

        # 验证：提供 reopen 指引（D4 死锁规避），并点名已关闭的 DEF
        assert "reopen" in result.violations[0]
        assert "DEF-001" in result.violations[0]


class TestRegistrationGateD4DeadlockAvoidanceIntegration:
    """D4 死锁规避集成测试"""

    def test_fixed_state_still_counts_as_tracked(self, tmp_path):
        """测试 fixed 状态仍算 tracked（避免死锁）"""
        audit_path = tmp_path / "fixed_audit.db"
        ledger_path = tmp_path / "fixed_defects.json"

        logger = DispatchAuditLogger(audit_path)
        _log_end(logger, "task-fixed", findings=[], failure_class="product_failed")
        logger.close()

        # 缺陷已修复（fixed）但未关闭
        ledger = DefectLedger(ledger_path=ledger_path, audit_db_path=audit_path)
        defect = ledger.add("audit:event=1&failure=product_failed", "Optimize performance - Performance regression")
        ledger.update(defect.id, "def456", "Optimized performance")

        # 运行 registration gate
        result = RegistrationGate().evaluate(
            worker_results=[_PRODUCT_FAILURE],
            errors=None,
            findings=None,
            ledger_path=ledger_path,
        )

        # 验证：fixed 状态算 tracked → PASS（避免死锁）
        assert result.verdict == "pass"
        assert result.signals[0]["status"] == "tracked"
        assert result.signals[0]["tracked_by"] == ["DEF-001"]
        # run 仍然失败（worker 自身失败），但 gate 不阻止

    def test_multiple_states_classification(self, tmp_path):
        """测试多信号分类：tracked + unregistered + regressed 混合"""
        audit_path = tmp_path / "multi_audit.db"
        ledger_path = tmp_path / "multi_defects.json"

        # 事件 1 = 发现（两个 BV critical + product_failed），事件 2 = 干净回归跑
        logger = DispatchAuditLogger(audit_path)
        logger.log_dispatch_start("task-multi", "mock", ["tester"])
        _log_end(
            logger,
            "task-multi",
            findings=[
                _finding_dict("VULN-1", "critical"),
                _finding_dict("BREAK-1", "critical"),
            ],
            failure_class="product_failed",
        )
        _log_end(logger, "task-verify", success=True, failure_class="none")
        logger.close()

        # 台账状态：VULN-1=open（tracked），BREAK-1=closed（regressed），
        # failure:product_failed 未登记（unregistered）
        ledger = DefectLedger(ledger_path=ledger_path, audit_db_path=audit_path)
        ledger.add("audit:event=2&finding=0", "Fix Issue A - Tracked issue")
        defect_b = ledger.add("audit:event=2&finding=1", "Fix Issue B - Regressed issue")
        ledger.update(defect_b.id, "ghi789", "Fixed Issue B")
        ledger.close(defect_b.id, "audit:event=3")

        # 运行 registration gate
        result = RegistrationGate().evaluate(
            worker_results=[_PRODUCT_FAILURE],
            errors=None,
            findings=[_finding("VULN-1", "critical"), _finding("BREAK-1", "critical")],
            ledger_path=ledger_path,
        )

        # 验证：有 unregistered 和 regressed → FAIL
        assert result.verdict == "fail"
        assert result.to_dict()["summary"] == {
            "mandatory": 3,
            "tracked": 1,
            "unregistered": 1,
            "regressed": 1,
        }

        # 验证：分类正确
        by_type = {signal["type"]: signal for signal in result.signals}
        assert by_type["review:break-vuln:VULN-1"]["status"] == "tracked"
        assert by_type["failure:product_failed"]["status"] == "unregistered"
        assert by_type["review:break-vuln:BREAK-1"]["status"] == "regressed"
        assert by_type["review:break-vuln:BREAK-1"]["closed_ids"] == ["DEF-002"]


class TestRegistrationGateAdvisoryReportIntegration:
    """advisory 报告集成测试"""

    def test_unfiled_signal_report_advisory_only(self, tmp_path):
        """测试 unfiled_signal_report（warning/spec）不改退出码"""
        audit_path = tmp_path / "advisory_audit.db"
        ledger_path = tmp_path / "advisory_defects.json"

        # 审计发现 warning 和 spec（非强制：非 BV-critical）
        logger = DispatchAuditLogger(audit_path)
        _log_end(
            logger,
            "task-advisory",
            findings=[
                _finding_dict("BREAK-2", "warning"),
                _finding_dict("missing_edge_case", "warning", ReviewStage.SPEC_COMPLIANCE),
            ],
            success=True,
        )
        logger.close()

        # 空台账，运行 registration gate
        result = RegistrationGate().evaluate(
            worker_results=None,
            errors=None,
            findings=None,
            ledger_path=ledger_path,
        )

        # 验证：advisory 不改 verdict（仍为 pass，且无强制信号）
        assert result.verdict == "pass"
        assert result.signals == []

        # 验证：unfiled_signal_report 列出建议（独立 advisory API，不进 gate 结果）
        advisory, warnings = unfiled_signal_report(ledger_path=ledger_path, audit_db_path=audit_path)
        assert warnings == []
        assert len(advisory) == 2
        assert {item["type"] for item in advisory} == {
            "review:break-vuln:BREAK-2",
            "review:spec:missing_edge_case",
        }
        assert all(item["seen_count"] == 1 for item in advisory)


class TestRegistrationGateEnvironmentBlockedIntegration:
    """environment_blocked 拒绝集成测试"""

    def test_environment_blocked_rejection(self, tmp_path):
        """测试 environment_blocked 拒绝立案"""
        audit_path = tmp_path / "blocked_audit.db"
        ledger_path = tmp_path / "blocked_defects.json"

        # 审计记录环境阻断
        logger = DispatchAuditLogger(audit_path)
        _log_end(logger, "task-blocked", findings=[], failure_class="environment_blocked")
        logger.close()

        # 运行 registration gate：环境阻断不产生强制信号
        result = RegistrationGate().evaluate(
            worker_results=[{"success": False, "error": "APIConnectionError: connection refused"}],
            errors=None,
            findings=None,
            ledger_path=ledger_path,
        )

        # 验证：environment_blocked 不要求登记 → PASS
        assert result.verdict == "pass"
        assert result.signals == []

        # 验证：台账层面拒绝 environment_blocked 立案（PRD §4.2）
        ledger = DefectLedger(ledger_path=ledger_path, audit_db_path=audit_path)
        with pytest.raises(DefectLedgerError, match="environment_blocked"):
            ledger.add("audit:event=1&failure=environment_blocked", "Environment issue")


class TestRegistrationGateFeatureGateErrorAttributionIntegration:
    """feature_gate 错误归因 product_failed 集成测试（PRD W3 ⑨）"""

    def test_feature_gate_error_counts_as_product_failed(self, tmp_path):
        """测试 feature_gate 错误文本归因为 product_failed"""
        audit_path = tmp_path / "fgate_audit.db"
        ledger_path = tmp_path / "fgate_defects.json"

        # 模拟 dispatch 失败：feature_gate 验证失败被归因为产品缺陷
        logger = DispatchAuditLogger(audit_path)
        _log_end(
            logger,
            "task-fgate",
            findings=[_finding_dict("feature_gate_failure", "critical", ReviewStage.SPEC_COMPLIANCE)],
            failure_class="product_failed",
        )
        logger.close()

        # 未登记缺陷
        result = RegistrationGate().evaluate(
            worker_results=[{"success": False, "error": "Feature gate gap: T1 did not pass"}],
            errors=None,
            findings=None,
            ledger_path=ledger_path,
        )

        # 验证：feature_gate 失败被识别为 product_failed 且未登记 → FAIL
        assert result.verdict == "fail"
        assert result.signals[0]["type"] == "failure:product_failed"
        assert result.signals[0]["status"] == "unregistered"
        assert "devsquad defect add" in result.violations[0]

        # 验证：立案依据（findings/failure_class）已落在真实审计事件里
        verifier = DispatchAuditLogger(audit_path)
        ends = verifier.query(event_type="dispatch_end")
        assert ends[0].details["failure_class"] == "product_failed"
        assert ends[0].details["findings"][0]["category"] == "feature_gate_failure"
        verifier.close()


class TestRegistrationGatePersistenceIntegration:
    """持久化和跨进程集成测试"""

    def test_ledger_corruption_fail_closed(self, tmp_path):
        """测试台账损坏时 fail-closed（D7）"""
        audit_path = tmp_path / "corrupt_audit.db"
        ledger_path = tmp_path / "corrupt_defects.json"

        # 创建有效审计
        logger = DispatchAuditLogger(audit_path)
        _log_end(
            logger,
            "task-corrupt",
            findings=[_finding_dict("VULN-1", "critical")],
            failure_class="product_failed",
        )
        logger.close()

        # 创建损坏的台账文件
        ledger_path.write_text("{ invalid json }", encoding="utf-8")

        # 运行 registration gate（应 fail-closed：抛错而不是静默放行）
        gate = RegistrationGate()
        with pytest.raises(DefectLedgerError, match="not valid JSON"):
            gate.evaluate(
                worker_results=[_PRODUCT_FAILURE],
                errors=None,
                findings=[_finding("VULN-1", "critical")],
                ledger_path=ledger_path,
            )

        # 验证：mixin 的转换结果仍是 FAIL（不能证明登记 = FAIL）
        converted = RegistrationGateResult.internal_error("ledger is not valid JSON")
        assert converted.verdict == "fail"
        assert converted.error is not None
